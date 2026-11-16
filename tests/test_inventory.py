# this_file: tests/test_inventory.py
"""Parse-only inventory fixtures; no Qt runtime is loaded or executed."""

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from pythonqtside.tooling.inventory import build_report, write_reports
from pythonqtside.tooling.join import MODULES, join_surfaces
from pythonqtside.tooling.surface import extract

PYSIDE = """
import a_binding_that_must_never_be_imported
class Object(object): pass
class QWidget:
    class Mode(object):
        One: QWidget.Mode = ...
        Two: QWidget.Mode = ...
    One: QWidget = ...
    Two: QWidget = ...
    @overload
    def __init__(self): ...
    @overload
    def __init__(self, parent=None, *, flags=0): ...
    def title(self) -> str: ...
    def missing(self): ...
    @property
    def decorated(self) -> str: ...
    @decorated.setter
    def decorated(self, value): ...
    class Child:
        class Kind:
            A: QWidget.Child.Kind = ...
    def _hidden(self): ...
"""
NATIVE = """
class QWidget:
    def __init__(self, *args, **kwargs): ...
    def extra(self): ...
    title: str
    decorated: str
    Mode: type
    One: Any
    Extra: Any
"""


def test_extract_when_overloads_properties_and_nested_enums_then_preserves_facts():
    surface = extract(PYSIDE)["classes"]["QWidget"]
    assert surface["methods"] == {"title", "missing"}
    assert surface["properties"] == {"decorated"}
    assert surface["enums"]["Mode"] == {"One", "Two"}
    assert surface["enums"]["Child.Kind"] == {"A"}
    assert len(surface["constructors"]) == 2
    assert surface["constructors"][1] == {
        "required_positional": 0,
        "optional_positional": 1,
        "required_keyword_only": 0,
        "optional_keyword_only": 1,
        "varargs": False,
        "kwargs": False,
    }
    native = extract(NATIVE)["classes"]["QWidget"]
    assert native["attributes"]["title"] == "str"
    assert native["opaque_types"] == {"Mode"}
    assert native["constructors"][0]["varargs"] is True


def test_join_when_modules_move_then_reports_status_and_member_differences():
    upstream = {
        "QtWidgets": extract(PYSIDE),
        "QtCore": extract(
            "class QObject: pass\nclass QTimer: pass\nclass Lost: pass\n"
        ),
    }
    native = {
        "QtGui": extract(NATIVE),
        "private": extract("class QObject: pass"),
        "QtCore": extract("class QTimer: pass"),
    }
    joined = join_surfaces(upstream, native)
    widgets = joined["QtWidgets"]["classes"]
    widget = widgets["QWidget"]
    assert widget["status"] == "native_other_module"
    assert widget["native_module"] == "QtGui"
    assert widgets["Object"]["status"] == "missing"
    diff = widget["differences"]
    assert diff["methods_only_pyside"] == ["missing", "title"]
    assert diff["methods_only_native"] == ["extra"]
    assert diff["native_attributes_for_pyside_accessors"] == ["title"]
    assert diff["enum_members_only_pyside"] == ["Two"]
    assert diff["enum_members_only_native_candidates"] == ["Extra"]
    assert diff["nested_enums"]["Mode"]["members_only_pyside"] is None
    assert joined["QtCore"]["classes"]["QObject"]["status"] == "private_only"
    assert joined["QtCore"]["classes"]["QTimer"]["status"] == "native_same_module"
    assert joined["QtCore"]["classes"]["Lost"]["native_module"] is None


def test_join_when_inherited_methods_then_does_not_report_them_as_native_only():
    upstream = {
        "QtCore": extract("class Base:\n def inherited(self): ..."),
        "QtGui": extract("class Child(PySide2.QtCore.Base):\n def own(self): ..."),
    }
    native = {
        "QtGui": extract("class Child:\n def own(self): ...\n def inherited(self): ...")
    }
    diff = join_surfaces(upstream, native)["QtGui"]["classes"]["Child"]["differences"]
    assert diff["methods_only_native"] == []


def test_extract_when_empty_or_invalid_then_empty_inventory_or_syntax_error():
    assert extract("") == {"classes": {}, "members": set()}
    with pytest.raises(SyntaxError):
        extract("class Broken(")


def test_extract_when_class_has_self_typed_attribute_and_operators_then_not_enum():
    surface = extract(
        "class C:\n default: C\n def __len__(self): ...\n def _private(self): ..."
    )
    cls = surface["classes"]["C"]
    assert cls["is_enum"] is False
    assert cls["methods"] == {"__len__"}


def test_join_when_nested_enums_recorded_then_reports_exact_missing_and_extra():
    pyside = extract("class C:\n class Mode(Enum):\n  One = 1\n  Two = 2")
    native = extract("class C:\n class Mode(Enum):\n  One = 1\n  Three = 3")
    report = join_surfaces({"QtCore": pyside}, {"QtCore": native})
    enums = report["QtCore"]["classes"]["C"]["differences"]["nested_enums"]
    assert enums["Mode"] == {
        "native_layout": "nested",
        "members_only_pyside": ["Two"],
        "members_only_native": ["Three"],
    }


def test_join_when_duplicate_native_exports_then_prefers_family_before_combined_private():
    surface = extract("class C: pass")
    native = {m: surface for m in ("QtCore", "QtGui", "Qt", "private")}
    report = join_surfaces({"QtCore": surface, "QtWidgets": surface}, native)
    assert report["QtCore"]["classes"]["C"]["native_module"] == "QtCore"
    assert report["QtWidgets"]["classes"]["C"]["native_module"] == "QtGui"
    combined = join_surfaces({"QtCore": surface}, {"Qt": surface})
    assert combined["QtCore"]["classes"]["C"]["status"] == "native_other_module"


def test_join_when_inheritance_cycles_then_fails_instead_of_recursing_forever():
    surface = extract("class A(B): pass\nclass B(A): pass")
    with pytest.raises(ValueError, match="Cyclic stub inheritance"):
        join_surfaces({"QtCore": surface}, {})


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "echopy"
    source = root / "src/fontlab_echopy"
    (source / "PythonQt").mkdir(parents=True)
    cache = root / ".cache/upstream"
    cache.mkdir(parents=True)
    (source / "_provenance.json").write_text("{}")
    for module in (*[m for m in MODULES if m != "QtWidgets"], "private", "Qt"):
        text = NATIVE if module == "QtGui" else ""
        (source / "PythonQt" / f"{module}.pyi").write_text(text)
    wheel = cache / "PySide2-fixture.whl"
    with ZipFile(wheel, "w") as archive:
        for module in MODULES:
            archive.writestr(
                f"PySide2/{module}.pyi", PYSIDE if module == "QtWidgets" else ""
            )
        archive.writestr(
            "PySide2-5.15.2.1.dist-info/METADATA", "Name: PySide2\nVersion: 5.15.2.1\n"
        )
    manifest = {
        "wheel": wheel.name,
        "version": "5.15.2.1",
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }
    (cache / "pyside-manifest.json").write_text(json.dumps(manifest))
    return root


def test_report_when_inputs_repeat_then_bytes_and_hashes_match(inputs, tmp_path):
    report = build_report(inputs)
    assert report["native_host"] == {
        "fontlab_version": None,
        "python_version": None,
        "qt_version": None,
    }
    assert report["pyside_version"] == "5.15.2.1"
    assert "PythonQt/Qt.pyi" in report["inputs"]
    assert "PySide2/QtWidgets.pyi" in report["inputs"]
    output, widgets = tmp_path / "report.json", tmp_path / "widgets.json"
    write_reports(report, output, widgets)
    first = output.read_bytes(), widgets.read_bytes()
    write_reports(build_report(inputs), output, widgets)
    assert first == (output.read_bytes(), widgets.read_bytes())
    assert json.loads(widgets.read_text())["classes"] == ["QWidget"]
    assert str(tmp_path) not in output.read_text()


def test_report_when_wheel_hash_mismatches_then_fails_before_parsing(inputs):
    wheel = inputs / ".cache/upstream/PySide2-fixture.whl"
    wheel.write_bytes(b"not a zip")
    with pytest.raises(ValueError, match="wheel SHA256"):
        build_report(inputs)


def test_report_when_native_input_missing_then_fails(inputs):
    (inputs / "src/fontlab_echopy/PythonQt/private.pyi").unlink()
    with pytest.raises(FileNotFoundError):
        build_report(inputs)


def test_report_when_native_hash_differs_from_provenance_then_fails(inputs):
    path = inputs / "src/fontlab_echopy/_provenance.json"
    path.write_text(json.dumps({"merged_outputs": {"PythonQt/QtCore.pyi": "wrong"}}))
    with pytest.raises(ValueError, match="Native SHA256"):
        build_report(inputs)


def test_report_when_version_recorded_then_uses_provenance_without_inference(inputs):
    path = inputs / "src/fontlab_echopy/_provenance.json"
    path.write_text(json.dumps({"native_host": {"python_version": "fixture-python"}}))
    assert build_report(inputs)["native_host"] == {
        "fontlab_version": None,
        "python_version": "fixture-python",
        "qt_version": None,
    }


def test_report_when_manifest_version_differs_then_fails(inputs):
    path = inputs / ".cache/upstream/pyside-manifest.json"
    manifest = json.loads(path.read_text())
    manifest["version"] = "wrong"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="wheel version"):
        build_report(inputs)


def test_committed_report_matches_widget_map_and_native_qobject():
    root = Path(__file__).parents[1] / "src/pythonqtside"
    report = json.loads((root / "_inventory.json").read_text())
    widgets = json.loads((root / "_qtwidgets.json").read_text())
    classes = report["modules"]["QtWidgets"]["classes"]
    assert widgets["classes"] == sorted(
        n for n, c in classes.items() if c["native_module"]
    )
    assert "Object" not in widgets["classes"]
    assert report["modules"]["QtCore"]["classes"]["QObject"]["status"] == "private_only"
    assert set(report["modules"]) == set(MODULES)
    assert (root / "_inventory.json").stat().st_size < 5_000_000


TUPLE_PYSIDE = """
class QTransform:
    def inverted(self) -> typing.Tuple[PySide2.QtGui.QTransform, bool]: ...
    def isInvertible(self) -> bool: ...
    def m11(self) -> float: ...
"""
TUPLE_NATIVE = """
class QTransform:
    def inverted(self, invertible: Any) -> Any: ...
    def isInvertible(self) -> bool: ...
    def isAffine(self) -> bool: ...
    def m11(self) -> float: ...
"""


def test_join_when_pyside_returns_tuple_then_records_native_out_parameter_shape():
    report = join_surfaces(
        {"QtGui": extract(TUPLE_PYSIDE)}, {"QtGui": extract(TUPLE_NATIVE)}
    )
    diff = report["QtGui"]["classes"]["QTransform"]["differences"]
    assert diff["tuple_returns"] == {
        "inverted": {
            "pyside_returns": ["typing.Tuple[PySide2.QtGui.QTransform, bool]"],
            "pyside_overloads": [
                {
                    "parameters": [],
                    "returns": "typing.Tuple[PySide2.QtGui.QTransform, bool]",
                }
            ],
            "native_overloads": [{"parameters": ["invertible"], "returns": "Any"}],
        }
    }, "only tuple-returning PySide2 methods and their native shapes are recorded"
    assert diff["native_bool_predicates"] == ["isAffine", "isInvertible"]


def test_join_when_no_tuple_returns_or_native_method_missing_then_records_absence():
    plain = join_surfaces({"QtGui": extract(PYSIDE)}, {"QtGui": extract(NATIVE)})
    diff = plain["QtGui"]["classes"]["QWidget"]["differences"]
    assert diff["tuple_returns"] == {}
    assert diff["native_bool_predicates"] == [], "predicates only accompany tuples"
    missing = join_surfaces({"QtGui": extract(TUPLE_PYSIDE)}, {})
    entry = missing["QtGui"]["classes"]["QTransform"]["differences"]["tuple_returns"]
    assert entry["inverted"]["native_overloads"] is None


STATIC_PYSIDE = """
class QInputDialog:
    @staticmethod
    def getText(parent, title: str, label: str) -> typing.Tuple[str, bool]: ...
class QHostAddress:
    @typing.overload
    def toIPv4Address(self) -> int: ...
    @typing.overload
    def toIPv4Address(self) -> typing.Tuple[int, bool]: ...
"""
STATIC_NATIVE = """
class QInputDialog:
    def getText(self, parent: Any, title: str, label: str, ok: Any) -> str: ...
class QHostAddress:
    def toIPv4Address(self, ok: Any) -> int: ...
    def isNull(self) -> bool: ...
"""


def test_join_when_pyside_static_or_mixed_overloads_then_all_pyside_shapes_recorded():
    report = join_surfaces(
        {"QtGui": extract(STATIC_PYSIDE)}, {"QtGui": extract(STATIC_NATIVE)}
    )
    classes = report["QtGui"]["classes"]
    dialog = classes["QInputDialog"]["differences"]["tuple_returns"]["getText"]
    assert dialog["pyside_overloads"] == [
        {
            "parameters": ["parent", "title", "label"],
            "returns": "typing.Tuple[str, bool]",
            "static": True,
        }
    ], "static PySide2 methods are marked; native stubs declare self"
    host = classes["QHostAddress"]["differences"]
    returns = [
        s["returns"] for s in host["tuple_returns"]["toIPv4Address"]["pyside_overloads"]
    ]
    assert returns == ["int", "typing.Tuple[int, bool]"], "non-tuple overloads are kept"
    assert host["native_bool_predicates"] == ["isNull"]
