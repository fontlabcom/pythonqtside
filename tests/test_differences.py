# this_file: tests/test_differences.py
"""Measured difference tables are derived from the inventory alone."""

import hashlib
import json
from pathlib import Path

from pythonqtside.tooling.differences import analyze, runtime_table, write_report

ROOT = Path(__file__).parents[1] / "src/pythonqtside"


def _cls(native_module, constructors=None, **differences):
    base = {
        "native_attributes_for_pyside_accessors": [],
        "enum_members_only_pyside": [],
        "nested_enums": {},
        "tuple_returns": {},
        "native_bool_predicates": [],
    }
    return {
        "native_module": native_module,
        "constructors": {"native": constructors, "pyside": []},
        "differences": base | differences,
    }


KWARGS = [{"varargs": True, "kwargs": True}]
PAIR = "typing.Tuple[PySide2.QtGui.QTransform, bool]"
NATIVE_OUT = [{"parameters": ["invertible"], "returns": "Any"}]


def _out(native, *pyside, returns=None):
    """tuple_returns record: PySide2 overloads as (parameters, returns[, static])."""
    overloads = [
        {"parameters": p, "returns": r} | ({"static": True} if rest else {})
        for p, r, *rest in pyside
    ]
    return {
        "pyside_returns": returns or sorted({o["returns"] for o in overloads}),
        "pyside_overloads": overloads,
        "native_overloads": native,
    }


INT_PAIR = "typing.Tuple[int, bool]"
STR_PAIR = "typing.Tuple[str, bool]"
INVENTORY = {
    "modules": {
        "QtGui": {
            "classes": {
                "QTransform": _cls(
                    "QtGui",
                    KWARGS,
                    tuple_returns={
                        "inverted": _out(NATIVE_OUT, ([], PAIR)),
                        "gone": _out(None, ([], PAIR)),
                        "map": _out(
                            [{"parameters": ["x", "y"], "returns": "Any"}],
                            (["x"], PAIR),
                        ),
                        "split": _out(
                            [
                                {"parameters": ["a", "ok"], "returns": "Any"},
                                {"parameters": ["b", "ok"], "returns": "Any"},
                            ],
                            (["a"], PAIR),
                        ),
                    },
                    native_bool_predicates=["isInvertible"],
                ),
                "QMatrix4x4": _cls(
                    "QtGui",
                    KWARGS,
                    tuple_returns={"inverted": _out(NATIVE_OUT, ([], PAIR))},
                ),
                "QColor": _cls(
                    "QtGui",
                    KWARGS,
                    tuple_returns={
                        "getRgb": _out(
                            [{"parameters": ["r"], "returns": "Any"}],
                            ([], "typing.Tuple[int, int, int, int]"),
                        )
                    },
                ),
                "QLocale": _cls(
                    "QtCore",
                    KWARGS,
                    tuple_returns={
                        "toInt": _out(
                            [{"parameters": ["s", "ok"], "returns": "int"}],
                            (["s"], INT_PAIR),
                        )
                    },
                ),
                "QHostAddress": _cls(
                    "QtNetwork",
                    KWARGS,
                    tuple_returns={
                        "toIPv4Address": _out(
                            [{"parameters": ["ok"], "returns": "int"}],
                            ([], "int"),
                            ([], INT_PAIR),
                            returns=[INT_PAIR],
                        )
                    },
                ),
                "Absent": _cls(
                    None, None, native_attributes_for_pyside_accessors=["x"]
                ),
            }
        },
        "QtWidgets": {
            "classes": {
                "QWidget": _cls(
                    "QtGui",
                    KWARGS,
                    native_attributes_for_pyside_accessors=["height", "windowTitle"],
                    enum_members_only_pyside=["DrawChildren"],
                    nested_enums={
                        "RenderFlag": {"members_only_pyside": ["IgnoreMask"]},
                        "Opaque": {"members_only_pyside": None},
                    },
                ),
                "QLabel": _cls(
                    "QtGui",
                    [{"varargs": False, "kwargs": False}],
                    native_attributes_for_pyside_accessors=["text"],
                ),
                "QFontDialog": _cls(
                    "QtGui",
                    KWARGS,
                    tuple_returns={
                        "getFont": _out(
                            [{"parameters": ["ok", "parent"], "returns": "Any"}],
                            (
                                ["parent"],
                                "typing.Tuple[PySide2.QtGui.QFont, bool]",
                                "s",
                            ),
                        )
                    },
                ),
                "QInputDialog": _cls(
                    "QtGui",
                    KWARGS,
                    tuple_returns={
                        "getText": _out(
                            [
                                {
                                    "parameters": [
                                        "parent",
                                        "title",
                                        "label",
                                        "echo",
                                        "text",
                                        "ok",
                                        "arg6",
                                    ],
                                    "returns": "str",
                                }
                            ],
                            (
                                ["parent", "title", "label", "echo", "text", "flags"],
                                STR_PAIR,
                                "static",
                            ),
                        )
                    },
                ),
            }
        },
    }
}


def test_analyze_when_routed_accessors_then_table_counts_and_top_classes():
    category = analyze(INVENTORY, "digest")["callable_accessors"]
    assert category["table"] == {
        "QtWidgets.QLabel": ["text"],
        "QtWidgets.QWidget": ["height", "windowTitle"],
    }, "missing classes are not routed and must be excluded"
    assert (category["count"], category["classes"]) == (3, 2)
    assert category["top_classes"][0] == ["QtWidgets.QWidget", 2]


def test_analyze_when_enum_members_missing_then_opaque_layouts_stay_unknown():
    category = analyze(INVENTORY, "digest")["enum_members_missing_natively"]
    assert category["table"] == {
        "QtWidgets.QWidget": ["DrawChildren", "RenderFlag.IgnoreMask"]
    }
    assert category["count"] == 2
    assert category["opaque_nested_enums"] == 1, "null membership is not missing"


def test_analyze_when_out_parameters_then_predicate_and_bool_result_adapters():
    category = analyze(INVENTORY, "digest")["out_parameters"]
    assert category["adapters"] == {"QtGui.QTransform": {"inverted": "isInvertible"}}
    assert category["bool_result_adapters"] == {
        "QtCore.QLocale": {
            "toInt": {
                "defaults": {},
                "max_arguments": 1,
                "out_index": 1,
                "out_parameter": "ok",
                "parameters": ["s"],
                "static": False,
            }
        },
        "QtGui.QInputDialog": {
            "getText": {
                "defaults": {"echo": {"native": "QtGui.QLineEdit.Normal"}, "text": ""},
                "max_arguments": 6,
                "out_index": 5,
                "out_parameter": "ok",
                "parameters": ["parent", "title", "label", "echo", "text"],
                "static": True,
            }
        },
        "QtGui.QMatrix4x4": {
            "inverted": {
                "defaults": {},
                "max_arguments": 0,
                "out_index": 0,
                "out_parameter": "invertible",
                "parameters": [],
                "static": False,
            }
        },
    }, "native out-parameter index, defaults before it and PySide2 arity are recorded"
    assert category["unsupported"] == {
        "QtGui.QColor": {"getRgb": "multiple_or_non_flag_outputs"},
        "QtGui.QTransform": {
            "gone": "native_missing",
            "map": "no_native_out_parameter",
            "split": "no_native_out_parameter",
        },
        "QtWidgets.QFontDialog": {"getFont": "stub_runtime_mismatch"},
        "QtGui.QHostAddress": {"toIPv4Address": "ambiguous_pyside_overload"},
    }
    assert category["counts"] == {
        "adapters": 1,
        "ambiguous_pyside_overload": 1,
        "bool_result_adapters": 3,
        "multiple_or_non_flag_outputs": 1,
        "native_missing": 1,
        "no_native_out_parameter": 2,
        "stub_runtime_mismatch": 1,
    }


def test_runtime_table_when_built_then_holds_only_adapter_tables():
    report = analyze(INVENTORY, "digest")
    table = runtime_table(report)
    assert table == {
        "inventory_sha256": "digest",
        "predicate": report["out_parameters"]["adapters"],
        "bool_result": report["out_parameters"]["bool_result_adapters"],
    }


def test_analyze_when_native_constructor_lacks_kwargs_then_keyword_category_lists_it():
    category = analyze(INVENTORY, "digest")["constructor_keywords"]
    assert category["native_without_kwargs"] == ["QtWidgets.QLabel"]
    assert category["status"] == "measured"
    only_kwargs = json.loads(json.dumps(INVENTORY))
    label = only_kwargs["modules"]["QtWidgets"]["classes"]["QLabel"]
    label["constructors"]["native"] = KWARGS
    unmeasured = analyze(only_kwargs, "digest")["constructor_keywords"]
    assert unmeasured["status"] == "unmeasured", (
        "**kwargs stubs give no rejection evidence"
    )
    assert unmeasured["native_without_kwargs"] == []


def test_write_report_when_repeated_then_bytes_are_identical(tmp_path):
    output = tmp_path / "differences.json"
    write_report(analyze(INVENTORY, "digest"), output)
    first = output.read_bytes()
    write_report(analyze(INVENTORY, "digest"), output)
    assert first == output.read_bytes()
    assert json.loads(first)["inventory_sha256"] == "digest"


def test_committed_differences_when_regenerated_then_bytes_and_tables_match():
    inventory = (ROOT / "_inventory.json").read_bytes()
    report = analyze(json.loads(inventory), hashlib.sha256(inventory).hexdigest())
    committed = ROOT / "_differences.json"
    assert (
        json.dumps(report, sort_keys=True, indent=2) + "\n" == committed.read_text()
    ), "regenerate _differences.json with python -m pythonqtside.tooling.differences"
    out = report["out_parameters"]
    assert out["adapters"] == {
        "QtGui.QMatrix": {"inverted": "isInvertible"},
        "QtGui.QTransform": {"inverted": "isInvertible"},
    }
    assert out["counts"]["bool_result_adapters"] == 37
    assert unsupported_reason(out, "QtWidgets.QFontDialog", "getFont") == (
        "stub_runtime_mismatch"
    ), "PySide2 returns (ok, font) at runtime, unlike its stub"
    assert out["counts"]["ambiguous_pyside_overload"] == 1
    assert "no_native_predicate" not in out["counts"]
    unsupported = out["unsupported"]
    assert unsupported["QtNetwork.QHostAddress"]["toIPv4Address"] == (
        "ambiguous_pyside_overload"
    )
    adapters = out["bool_result_adapters"]
    assert adapters["QtGui.QMatrix4x4"]["inverted"]["out_index"] == 0
    assert adapters["QtGui.QInputDialog"]["getText"]["static"] is True
    assert adapters["QtCore.QLocale"]["toInt"]["out_index"] == 1
    table = ROOT / "_out_parameters.json"
    assert json.dumps(runtime_table(report), sort_keys=True, indent=2) + "\n" == (
        table.read_text()
    ), "regenerate _out_parameters.json with python -m pythonqtside.tooling.differences"
    assert table.stat().st_size < 20_000, "the runtime table stays small"
    accessors = report["callable_accessors"]["table"]
    assert "windowTitle" in accessors["QtWidgets.QWidget"]
    assert "text" in accessors["QtWidgets.QLabel"]
    assert "objectName" in accessors["QtCore.QObject"]
    native = report["callable_accessors"]["native"]
    assert native["measured_names"] + native["unmeasured_names"] == 5364
    assert native["uncovered"] == 0, "every measured getter is a Qt property"
    assert report["constructor_keywords"]["status"] == "unmeasured"
    assert report["constructor_keywords"]["native"]["result"] == "rejected", (
        "the FontLab measurement replaces the stubs' missing evidence"
    )
    assert committed.stat().st_size < 1_000_000


def unsupported_reason(out: dict, key: str, method: str) -> str:
    return out["unsupported"][key][method]
