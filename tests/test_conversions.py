# this_file: tests/test_conversions.py
"""Implicit enum -> value-class table, derived from small inline stubs only."""

import hashlib
import json
from pathlib import Path

import pytest

from pythonqtside._app_conversions import _table
from pythonqtside.tooling.conversions import analyze, pack

ROOT = Path(__file__).parents[1] / "src/pythonqtside"

PYSIDE = {
    "QtCore": b"""
class Qt(Shiboken.Object):
    class GlobalColor(object):
        red: Qt.GlobalColor = ...
    class BrushStyle(object):
        SolidPattern: Qt.BrushStyle = ...
    class CursorShape(object):
        WaitCursor: Qt.CursorShape = ...
class QEasingCurve(Shiboken.Object):
    class Type(object):
        OutElastic: QEasingCurve.Type = ...
    def __init__(self, other: PySide2.QtCore.QEasingCurve) -> None: ...
    def __init__(self, type: PySide2.QtCore.QEasingCurve.Type=...) -> None: ...
class QObject(Shiboken.Object):
    def setObjectName(self, name: str) -> None: ...
class QEvent(Shiboken.Object):
    class Type(object):
        None_: QEvent.Type = ...
    def __init__(self, arg__1: PySide2.QtCore.QEvent) -> None: ...
    def __init__(self, type: PySide2.QtCore.QEvent.Type) -> None: ...
class QState(PySide2.QtCore.QObject):
    class ChildMode(object):
        ParallelStates: QState.ChildMode = ...
    def __init__(self, childMode: PySide2.QtCore.QState.ChildMode) -> None: ...
class QStateMachine(PySide2.QtCore.QObject):
    def addState(self, state: PySide2.QtCore.QState) -> None: ...
    def postEvent(self, event: PySide2.QtCore.QEvent) -> None: ...
class QVariantAnimation(PySide2.QtCore.QObject):
    def setEasingCurve(self, easing: PySide2.QtCore.QEasingCurve) -> None: ...
class QRegion(Shiboken.Object):
    class RegionType(object):
        Rectangle: QRegion.RegionType = ...
    def __init__(self, x: int, t: PySide2.QtCore.QRegion.RegionType=...) -> None: ...
class QTimeLine(PySide2.QtCore.QObject):
    def setEasingCurve(self, curve: PySide2.QtCore.QEasingCurve) -> None: ...
    def setRegion(self, r: PySide2.QtCore.QRegion) -> None: ...
""",
    "QtGui": b"""
class QColor(Shiboken.Object):
    def __init__(self, other: PySide2.QtGui.QColor) -> None: ...
    def __init__(self, color: PySide2.QtCore.Qt.GlobalColor) -> None: ...
    def __init__(self, rgb: int) -> None: ...
class QBrush(Shiboken.Object):
    def __init__(self, brush: PySide2.QtGui.QBrush) -> None: ...
    def __init__(self, bs: PySide2.QtCore.Qt.BrushStyle) -> None: ...
    def __init__(self, color: PySide2.QtCore.Qt.GlobalColor, bs: PySide2.QtCore.Qt.BrushStyle=...) -> None: ...
class QCursor(Shiboken.Object):
    def __init__(self, cursor: PySide2.QtGui.QCursor) -> None: ...
    def __init__(self, shape: PySide2.QtCore.Qt.CursorShape) -> None: ...
class QPainter(Shiboken.Object):
    def setBrush(self, brush: PySide2.QtGui.QBrush) -> None: ...
    def setBrush(self, style: PySide2.QtCore.Qt.BrushStyle) -> None: ...
    def setRgb(self, color: PySide2.QtGui.QColor) -> None: ...
    def setRgb(self, rgb: int) -> None: ...
    def drawThing(self, x: int, color: PySide2.QtGui.QColor, y: int=...) -> None: ...
    def nativeInt(self, color: PySide2.QtGui.QColor) -> None: ...
    def gone(self, color: PySide2.QtGui.QColor) -> None: ...
class QWidget(PySide2.QtCore.QObject):
    def setCursor(self, arg__1: PySide2.QtGui.QCursor) -> None: ...
class QLabel(PySide2.QtGui.QWidget):
    def setCursor(self, c: PySide2.QtGui.QCursor) -> None: ...
    def setCursor(self, shape: PySide2.QtCore.Qt.CursorShape) -> None: ...
class QPushButton(PySide2.QtGui.QWidget):
    def setText(self, text: str) -> None: ...
class QFrame(PySide2.QtGui.QWidget):
    def setFrameStyle(self, style: int) -> None: ...
class QGuiApplication(Shiboken.Object):
    @staticmethod
    def setOverrideCursor(arg__1: PySide2.QtGui.QCursor) -> None: ...
class QPalette(Shiboken.Object):
    class ColorGroup(object):
        Active: QPalette.ColorGroup = ...
    class ColorRole(object):
        Window: QPalette.ColorRole = ...
    def setColor(self, cg: PySide2.QtGui.QPalette.ColorGroup, cr: PySide2.QtGui.QPalette.ColorRole, color: PySide2.QtGui.QColor) -> None: ...
    def setColor(self, cr: PySide2.QtGui.QPalette.ColorRole, color: PySide2.QtGui.QColor) -> None: ...
class QOpenGLShaderProgram(Shiboken.Object):
    def setAttributeValue(self, location: int, value: PySide2.QtGui.QColor) -> None: ...
    def setAttributeValue(self, location: int, value: float) -> None: ...
    def setAttributeValue(self, location: int, values: typing.Sequence[float], columns: int, rows: int) -> None: ...
    def setValues(self, color: PySide2.QtGui.QColor) -> None: ...
    def setValues(self, values: typing.Sequence[float]) -> None: ...
    def gap(self, color: PySide2.QtGui.QColor) -> None: ...
    def gap(self, color: PySide2.QtGui.QColor, a: int, b: int) -> None: ...
""",
}

NATIVE = {
    "QtCore": b"""
class QVariantAnimation:
    def setEasingCurve(self, easing: Any) -> None: ...
class QStateMachine:
    def addState(self, state: Any) -> None: ...
    def postEvent(self, event: Any) -> None: ...
class QTimeLine:
    def setEasingCurve(self, curve: Any) -> None: ...
    def setRegion(self, r: Any) -> None: ...
""",
    "QtGui": b"""
class QPainter:
    def setBrush(self, brush: Any) -> None: ...
    def setRgb(self, color: Any) -> None: ...
    def drawThing(self, x: int, color: Any, y: int) -> None: ...
    def nativeInt(self, color: int) -> None: ...
class QWidget:
    def setCursor(self, arg__1: Any) -> None: ...
class QLabel:
    def setCursor(self, arg__1: Any) -> None: ...
class QPushButton:
    def setCursor(self, arg__1: Any) -> None: ...
    def setText(self, text: Any) -> None: ...
class QFrame:
    def setFrameStyle(self, style: int) -> None: ...
class QGuiApplication:
    def setOverrideCursor(arg__1: Any) -> None: ...
class QPalette:
    def setColor(self, arg__1: Any, arg__2: Any, arg__3: Any) -> None: ...
class QOpenGLShaderProgram:
    def setAttributeValue(self, a: Any, b: Any, c: Any, d: Any) -> None: ...
    def setValues(self, a: Any) -> None: ...
    def gap(self, a: Any, b: Any, c: Any) -> None: ...
""",
}


def _cls(native_module, **enums):
    layout = {name: {"native_layout": value} for name, value in enums.items()}
    return {"native_module": native_module, "differences": {"nested_enums": layout}}


INVENTORY = {
    "modules": {
        "QtCore": {
            "classes": {
                "Qt": _cls(
                    "QtCore",
                    GlobalColor="opaque_type",
                    BrushStyle="opaque_type",
                    CursorShape="opaque_type",
                ),
                "QEasingCurve": _cls("QtCore", Type="opaque_type"),
                "QObject": _cls("private"),
                "QEvent": _cls("QtCore", Type="opaque_type"),
                "QState": _cls("QtCore", ChildMode="opaque_type"),
                "QStateMachine": _cls("QtCore"),
                "QVariantAnimation": _cls("QtCore"),
                "QRegion": _cls("QtGui", RegionType="opaque_type"),
                "QTimeLine": _cls("QtCore"),
            }
        },
        "QtGui": {
            "classes": {
                "QColor": _cls("QtGui"),
                "QBrush": _cls("QtGui"),
                "QCursor": _cls("QtGui"),
                "QPainter": _cls("QtGui"),
                "QWidget": _cls("QtGui"),
                "QLabel": _cls("QtGui"),
                "QPushButton": _cls("QtGui"),
                "QFrame": _cls("QtGui"),
                "QGuiApplication": _cls("QtGui"),
                "QPalette": _cls(
                    "QtGui", ColorGroup="opaque_type", ColorRole="opaque_type"
                ),
                "QOpenGLShaderProgram": _cls("QtGui"),
            }
        },
    }
}


@pytest.fixture(scope="module")
def report():
    return analyze(INVENTORY, PYSIDE, NATIVE, "sha", out_parameters={})


def test_analyze_when_one_argument_enum_constructor_then_value_class(report):
    assert report["value_classes"] == {
        "QtCore.QEasingCurve": ["QtCore.QEasingCurve.Type"],
        "QtGui.QBrush": ["QtCore.Qt.BrushStyle", "QtCore.Qt.GlobalColor"],
        "QtGui.QColor": ["QtCore.Qt.GlobalColor"],
        "QtGui.QCursor": ["QtCore.Qt.CursorShape"],
    }, (
        "int, two-required-argument, explicit (QEvent) and non-copyable (QState) "
        "constructors are excluded"
    )


def test_analyze_when_parameter_typed_value_class_then_native_keyed_entry(report):
    classes = report["classes"]
    assert classes["QtCore.QVariantAnimation"]["setEasingCurve"] == {
        "static": False,
        "positions": [
            {
                "index": 0,
                "arities": [1, 1],
                "conversions": {"QtCore.QEasingCurve.Type": "QtCore.QEasingCurve"},
            }
        ],
    }
    assert classes["QtGui.QWidget"]["setCursor"]["positions"][0]["conversions"] == {
        "QtCore.Qt.CursorShape": "QtGui.QCursor"
    }
    assert classes["QtGui.QGuiApplication"]["setOverrideCursor"]["static"] is True


def test_analyze_when_position_is_not_first_then_arity_range_recorded(report):
    (position,) = report["classes"]["QtGui.QPainter"]["drawThing"]["positions"]
    assert position == {
        "index": 1,
        "arities": [2, 3],
        "conversions": {"QtCore.Qt.GlobalColor": "QtGui.QColor"},
    }


def test_analyze_when_pyside_has_enum_or_int_overload_then_position_excluded(report):
    painter = report["classes"]["QtGui.QPainter"]
    assert "setBrush" not in painter and "setRgb" not in painter
    assert report["unsupported"]["QtGui.QPainter"]["setBrush"] == {
        "0": "pyside_enum_or_int_overload"
    }
    assert report["unsupported"]["QtGui.QPainter"]["setRgb"] == {
        "0": "pyside_enum_or_int_overload"
    }


def _color(index, low, high):
    conversions = {"QtCore.Qt.GlobalColor": "QtGui.QColor"}
    return {"index": index, "arities": [low, high], "conversions": conversions}


def test_analyze_when_sibling_is_float_or_float_sequence_then_numeric_exclusion(
    report,
):
    """An int-like enum could dispatch to float (QOpenGLShaderProgram.setAttributeValue)."""
    assert "setAttributeValue" not in report["classes"]["QtGui.QOpenGLShaderProgram"]
    unsupported = report["unsupported"]["QtGui.QOpenGLShaderProgram"]
    assert unsupported["setAttributeValue"] == {"1": "pyside_numeric_overload"}, (
        "the 4-argument Sequence[float] form does not cover arity 2; float does"
    )
    assert unsupported["setValues"] == {"0": "pyside_numeric_overload"}
    assert "pyside_numeric_overload" in report["reasons"]


def test_analyze_when_sibling_covers_other_arity_then_only_that_arity_excluded(
    report,
):
    """QPalette.setColor(role, Qt.red) converts; the 3-argument role slot does not."""
    entry = report["classes"]["QtGui.QPalette"]["setColor"]
    assert entry["positions"] == [_color(1, 2, 2), _color(2, 3, 3)], (
        "index 1 converts only at arity 2; at arity 3 it is the ColorRole slot"
    )
    assert "QtGui.QPalette" not in report["unsupported"]


def test_analyze_when_sibling_shares_arity_then_partial_key_records_it():
    pyside = dict(PYSIDE)
    pyside["QtGui"] = (
        PYSIDE["QtGui"]
        + b"""
class QImage(Shiboken.Object):
    def paint(self, x: int, color: PySide2.QtGui.QColor, y: int=...) -> None: ...
    def paint(self, x: int, rgb: int, y: int) -> None: ...
"""
    )
    native = dict(NATIVE)
    native["QtGui"] = (
        NATIVE["QtGui"]
        + b"""
class QImage:
    def paint(self, a: Any, b: Any, c: Any) -> None: ...
"""
    )
    inventory = json.loads(json.dumps(INVENTORY))
    inventory["modules"]["QtGui"]["classes"]["QImage"] = _cls("QtGui")
    report = analyze(inventory, pyside, native, "sha", out_parameters={})
    assert report["classes"]["QtGui.QImage"]["paint"]["positions"] == [_color(1, 2, 2)]
    assert report["unsupported"]["QtGui.QImage"]["paint"] == {
        "1@3-3": "pyside_enum_or_int_overload"
    }


def test_analyze_when_typed_arities_have_gap_then_separate_ranges(report):
    entry = report["classes"]["QtGui.QOpenGLShaderProgram"]["gap"]
    assert entry["positions"] == [_color(0, 1, 1), _color(0, 3, 3)], (
        "no typed overload takes 2 arguments: arity 2 is not converted"
    )


def test_analyze_when_native_int_or_missing_then_excluded(report):
    unsupported = report["unsupported"]["QtGui.QPainter"]
    assert unsupported["nativeInt"] == {"0": "native_int_parameter"}
    assert unsupported["gone"] == {"0": "native_missing"}


def test_analyze_when_value_class_enum_not_native_then_not_value_class(report):
    assert "QtCore.QRegion" not in report["value_classes"]
    assert "setRegion" not in report["classes"]["QtCore.QTimeLine"]


def test_analyze_when_subclass_redeclares_with_enum_overload_then_empty_entry(report):
    assert report["classes"]["QtGui.QLabel"]["setCursor"] == {
        "static": False,
        "positions": [],
    }, "an explicit empty entry stops the QWidget entry from matching QLabel"


def test_analyze_when_inherited_without_redeclaration_then_entry_per_subclass(report):
    """Native stubs record only PythonQtInstanceWrapper as a base: no isinstance chain."""
    classes = report["classes"]
    assert (
        classes["QtGui.QPushButton"]["setCursor"]
        == classes["QtGui.QWidget"]["setCursor"]
    )
    assert classes["QtGui.QFrame"]["setCursor"] == {"static": False, "positions": []}, (
        "native QFrame lacks setCursor: an empty entry shadows QWidget's"
    )
    assert report["unsupported"]["QtGui.QFrame"] == {
        "setCursor": {"0": "native_missing"}
    }
    assert set(classes) == {
        "QtCore.QTimeLine",
        "QtCore.QVariantAnimation",
        "QtGui.QGuiApplication",
        "QtGui.QLabel",
        "QtGui.QFrame",
        "QtGui.QPainter",
        "QtGui.QPushButton",
        "QtGui.QWidget",
        "QtGui.QPalette",
        "QtGui.QOpenGLShaderProgram",
    }


def test_analyze_when_out_parameter_table_overlaps_then_error():
    overlap = {"bool_result": {"QtGui.QWidget": {"setCursor": {}}}, "predicate": {}}
    with pytest.raises(ValueError, match="setCursor"):
        analyze(INVENTORY, PYSIDE, NATIVE, "sha", out_parameters=overlap)


def test_analyze_when_run_twice_then_identical_json(report):
    again = analyze(INVENTORY, PYSIDE, NATIVE, "sha", out_parameters={})
    assert json.dumps(report, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert report["counts"]["positions"] == 10
    assert report["counts"]["shadow_entries"] == 2


def test_committed_table_when_loaded_then_measured_cases_present():
    table = json.loads((ROOT / "_implicit_conversions.json").read_text())
    _table.cache_clear()
    classes = {}
    for method, pairs in _table().items():
        for key, entry in pairs:
            classes.setdefault(key, {})[method] = entry

    def convs(key, method):
        return classes[key][method]["positions"][0]["conversions"]

    easing = {"QtCore.QEasingCurve.Type": "QtCore.QEasingCurve"}
    assert convs("QtCore.QVariantAnimation", "setEasingCurve") == easing
    assert convs("QtCore.QTimeLine", "setEasingCurve") == easing
    listen = classes["QtNetwork.QTcpServer"]["listen"]["positions"][0]
    assert listen["index"] == 0
    assert listen["conversions"] == {
        "QtNetwork.QHostAddress.SpecialAddress": "QtNetwork.QHostAddress"
    }
    cursor = {"QtCore.Qt.CursorShape": "QtGui.QCursor"}
    assert convs("QtGui.QWidget", "setCursor") == cursor
    assert convs("QtGui.QLabel", "setCursor") == cursor, "inherited, flat native"
    assert convs("QtGui.QPushButton", "setCursor") == cursor
    assert convs("QtCore.QPropertyAnimation", "setEasingCurve") == easing
    assert "QtCore.Qt.GlobalColor" in convs("QtGui.QPixmap", "fill")
    painter = table["unsupported"]["QtGui.QPainter"]
    for method in ("setBrush", "setPen"):
        assert painter[method]["0"] == "pyside_enum_or_int_overload", method
        assert method not in table["classes"]["QtGui.QPainter"], (
            f"QPainter.{method} accepts Qt.red natively: excluded at every arity"
        )
    assert {"1", "4"} <= set(painter["fillRect"])
    assert not [
        p
        for p in classes["QtGui.QPainter"].get("fillRect", {"positions": []})[
            "positions"
        ]
        if p["index"] in (1, 4)
    ]
    for method, value in (("setColor", "QtGui.QColor"), ("setBrush", "QtGui.QBrush")):
        positions = classes["QtGui.QPalette"][method]["positions"]
        two = [p for p in positions if p["index"] == 1]
        assert [p["arities"] for p in two] == [[2, 2]], method
        assert two[0]["conversions"]["QtCore.Qt.GlobalColor"] == value
        assert not [p for p in positions if p["index"] == 1 and p["arities"][1] >= 3]
    assert table["schema_version"] == 2
    assert table["counts"]["native_int_parameter"] == 0
    assert table["counts"]["native_signature_mismatch"] == 0
    assert any("cannot fire" in text for text in table["limitations"])
    shader = table["unsupported"]["QtGui.QOpenGLShaderProgram"]
    assert shader["setAttributeValue"]["1"] == "pyside_numeric_overload"
    assert "setAttributeValue" not in classes.get("QtGui.QOpenGLShaderProgram", {})
    assert len((ROOT / "_implicit_conversions.json").read_bytes()) < 400_000
    inventory = (ROOT / "_inventory.json").read_bytes()
    assert table["inventory_sha256"] == hashlib.sha256(inventory).hexdigest(), (
        "regenerate _implicit_conversions.json after the inventory changes"
    )


def test_pack_when_entries_repeat_then_stored_once_and_round_trip(report):
    packed = pack(report)
    texts = [json.dumps(e, sort_keys=True) for e in packed["entries"]]
    assert len(texts) == len(set(texts)), "each distinct entry appears once"
    unpacked = {
        key: {m: packed["entries"][i] for m, i in methods.items()}
        for key, methods in packed["classes"].items()
    }
    assert unpacked == report["classes"]
