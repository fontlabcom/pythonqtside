# this_file: src/pythonqtside/tooling/differences.py
"""Derive measured PySide2-versus-PythonQt adapter tables from _inventory.json only."""

import argparse
import ast
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
TOP = 10
# Qt semantics: inverted()'s bool out-parameter equals isInvertible() on the same
# value. Pairs apply only when the native class declares the predicate.
PREDICATES = {"inverted": "isInvertible"}
# Native bool* parameter names in the FontLab stubs; PythonQt fills them through
# PythonQt.BoolResult (native probe: QMatrix4x4().inverted(BoolResult())).
OUT_PARAMETERS = ("ok", "invertible", "timedOut")
# Qt 5.15 declaration defaults for native parameters before the out-parameter, as
# quoted in the Echopy QtGui/QtNetwork stub docstrings. PySide2 callers may omit
# them, but PythonQt needs them positionally before the BoolResult. A
# {"native": "Module.Class.Name"} value is looked up in PythonQt at call time.
QT_DEFAULTS = {
    "QInputDialog.getText": {"echo": {"native": "QtGui.QLineEdit.Normal"}, "text": ""},
    "QInputDialog.getMultiLineText": {"text": ""},
    "QInputDialog.getInt": {
        "value": 0,
        "minValue": -2147483647,
        "maxValue": 2147483647,
        "step": 1,
    },
    "QInputDialog.getDouble": {
        "value": 0.0,
        "minValue": -2147483647.0,
        "maxValue": 2147483647.0,
        "decimals": 1,
    },
    "QInputDialog.getItem": {"current": 0, "editable": True},
    "QLocalServer.waitForNewConnection": {"msec": 0},
    "QTcpServer.waitForNewConnection": {"msec": 0},
}
REASONS = {
    "native_missing": "The routed native class declares no method of this name.",
    "multiple_or_non_flag_outputs": "PySide2 returns several values or no trailing bool; native out-parameters carry them.",
    "no_native_out_parameter": "No native overload declares a bool out-parameter at one consistent position.",
    "ambiguous_pyside_overload": "PySide2 also declares a non-tuple overload of the same arity; its result shape is unknown.",
    "stub_runtime_mismatch": "PySide2's documented runtime result differs from its stub annotation.",
}
# Stub annotations PySide2's runtime contradicts. QFontDialog.getFont returns
# (ok, font) at runtime (PySide2 docs: `(ok, font) = QFontDialog.getFont(self)`),
# not the annotated (QFont, bool); the native (ok, parent) overload is also
# undeclared in the stub. Measured-only: excluded (controller ruling, phase 3b).
STUB_RUNTIME_MISMATCHES = {"QFontDialog.getFont"}
LIMITATIONS = [
    "Derived from _inventory.json declarations; native behavior is unverified until FontLab acceptance.",
    "Accessor names are stub matches; run_app still requires metaObject().indexOfProperty() evidence.",
    "Opaque native nested enums have unknown membership and are counted, not listed as missing.",
    "Native constructors declared as *args/**kwargs give no keyword-rejection evidence; constructor_keywords.native records the FontLab measurement instead.",
    "Predicate adapters cover zero-argument PySide2 calls on instances; arguments pass through natively.",
    "BoolResult adapters cover positional PySide2 calls; keyword calls reach them only after _keywords.json maps the keywords to positions, and explicit BoolResult calls pass through.",
]
# Measured in FontLab 9.0.9780 (issue 104). The stubs cannot show this: every native
# constructor stub declares *args/**kwargs.
NATIVE_KEYWORDS = {
    "result": "rejected",
    "scope": "every native constructor and method measured, instance and static",
    "error": "ValueError: Called <signature> with keyword arguments, but called slot does not support kwargs.",
    "evidence": "verification/issue-101-ecosystem/evidence/pqs-g04/probe_keywords.json",
    "adapter": "_keywords.json (python -m pythonqtside.tooling.keywords): PySide2 keyword names mapped to positions in run_app and compat",
}


def _routed(inventory: dict):
    for module, data in sorted(inventory["modules"].items()):
        for name, cls in sorted(data["classes"].items()):
            if cls["native_module"] is not None:
                yield f"{module}.{name}", cls


def _category(table: dict[str, list[str]]) -> dict:
    ranked = sorted(table.items(), key=lambda item: (-len(item[1]), item[0]))
    return {
        "count": sum(map(len, table.values())),
        "classes": len(table),
        "top_classes": [[name, len(items)] for name, items in ranked[:TOP]],
        "table": table,
    }


# Measured in FontLab 9.0.9780 (issue 104) without reading property values.
NATIVE_GETTERS = {
    "measured_names": 4624,
    "measured_classes": 181,
    "covered_by_index_of_property": 4624,
    "callable_natively": 0,
    "uncovered": 0,
    "unmeasured_names": 740,
    "unmeasured_classes": "47: 17 skipped (application, clipboard, printing, GL, platform dialogs), 30 without a default constructor; PythonQt has no staticMetaObject",
    "evidence": "verification/issue-101-ecosystem/evidence/pqs-g04/getters/",
    "note": "The run_app and compat getter adapter checks the live instance's metaObject() at call time, so unmeasured classes are gated the same way.",
}


def _accessors(inventory: dict) -> dict:
    table = {
        key: cls["differences"]["native_attributes_for_pyside_accessors"]
        for key, cls in _routed(inventory)
    }
    return _category({k: v for k, v in table.items() if v}) | {"native": NATIVE_GETTERS}


def _enums(inventory: dict) -> dict:
    table, opaque = {}, 0
    for key, cls in _routed(inventory):
        diff = cls["differences"]
        names = list(diff["enum_members_only_pyside"])
        for enum, record in sorted(diff["nested_enums"].items()):
            if record["members_only_pyside"] is None:
                opaque += 1
            else:
                names += [f"{enum}.{m}" for m in record["members_only_pyside"]]
        if names:
            table[key] = sorted(names)
    return _category(table) | {"opaque_nested_enums": opaque}


def _flag_pair(annotation: str) -> bool:
    """True for Tuple[Value, bool]: one value plus a trailing success flag."""
    node = ast.parse(annotation, mode="eval").body
    items = getattr(getattr(node, "slice", None), "elts", [])
    return len(items) == 2 and ast.unparse(items[1]) == "bool"


def _out_parameter(native: list[dict]) -> tuple[int, str] | None:
    """The single bool out-parameter position shared by every native overload."""
    found = set()
    for overload in native:
        hits = [
            (i, n) for i, n in enumerate(overload["parameters"]) if n in OUT_PARAMETERS
        ]
        if len(hits) != 1:
            return None
        found.add(hits[0])
    if len(found) != 1:
        return None
    index, name = found.pop()
    # Every overload must agree on the parameters before the slot, or the
    # adapter cannot know which native names its defaults and arity refer to.
    prefixes = {tuple(o["parameters"][:index]) for o in native}
    return (index, name) if len(prefixes) == 1 else None


def _ambiguous(record: dict) -> bool:
    pairs = [
        o
        for o in record["pyside_overloads"]
        if o["returns"] in record["pyside_returns"]
    ]
    arities = {len(o["parameters"]) for o in pairs}
    others = [o for o in record["pyside_overloads"] if o not in pairs]
    return any(len(o["parameters"]) in arities for o in others)


def _classify(key: str, method: str, record: dict, predicates: list[str]) -> str:
    if record["native_overloads"] is None:
        return "native_missing"
    if f"{key.partition('.')[2]}.{method}" in STUB_RUNTIME_MISMATCHES:
        return "stub_runtime_mismatch"
    if not all(_flag_pair(a) for a in record["pyside_returns"]):
        return "multiple_or_non_flag_outputs"
    if _out_parameter(record["native_overloads"]) is None:
        return "no_native_out_parameter"
    if _ambiguous(record):
        return "ambiguous_pyside_overload"
    return "adapter" if PREDICATES.get(method) in predicates else "bool_result"


def _bool_result(name: str, method: str, record: dict) -> dict:
    """How to call natively: BoolResult at out_index, defaults before it."""
    index, out = _out_parameter(record["native_overloads"])
    native = min((o["parameters"] for o in record["native_overloads"]), key=len)
    pairs = [
        o
        for o in record["pyside_overloads"]
        if o["returns"] in record["pyside_returns"]
    ]
    defaults = QT_DEFAULTS.get(f"{name}.{method}", {})
    if not set(defaults) <= set(native[:index]):
        raise ValueError(f"QT_DEFAULTS for {name}.{method} name no native parameter")
    return {
        "defaults": defaults,
        "max_arguments": min(max(len(o["parameters"]) for o in pairs), len(native) - 1),
        "out_index": index,
        "out_parameter": out,
        "parameters": native[:index],
        "static": all(o.get("static", False) for o in pairs),
    }


def _out_parameters(inventory: dict) -> dict:
    adapters, bool_results, unsupported = {}, {}, {}
    counts = dict.fromkeys(REASONS, 0) | {"adapters": 0, "bool_result_adapters": 0}
    for key, cls in _routed(inventory):
        diff, name = cls["differences"], key.partition(".")[2]
        native_key = f"{cls['native_module']}.{name}"
        for method, record in sorted(diff["tuple_returns"].items()):
            kind = _classify(key, method, record, diff["native_bool_predicates"])
            if kind == "adapter":
                adapters.setdefault(native_key, {})[method] = PREDICATES[method]
                counts["adapters"] += 1
            elif kind == "bool_result":
                entry = _bool_result(name, method, record)
                bool_results.setdefault(native_key, {})[method] = entry
                counts["bool_result_adapters"] += 1
            else:
                unsupported.setdefault(key, {})[method] = kind
                counts[kind] += 1
    return {
        "adapters": adapters,
        "bool_result_adapters": bool_results,
        "unsupported": unsupported,
        "counts": counts,
        "reasons": REASONS,
    }


def _constructor_keywords(inventory: dict) -> dict:
    without = [
        key
        for key, cls in _routed(inventory)
        if cls["constructors"]["native"]
        and not any(shape["kwargs"] for shape in cls["constructors"]["native"])
    ]
    return {
        "status": "measured" if without else "unmeasured",
        "native_without_kwargs": without,
        "native": NATIVE_KEYWORDS,
    }


def analyze(inventory: dict, inventory_sha256: str) -> dict:
    """Deterministic report: sorted tables, counts and the source inventory digest."""
    return {
        "schema_version": 2,
        "inventory_sha256": inventory_sha256,
        "limitations": LIMITATIONS,
        "callable_accessors": _accessors(inventory),
        "enum_members_missing_natively": _enums(inventory),
        "out_parameters": _out_parameters(inventory),
        "constructor_keywords": _constructor_keywords(inventory),
    }


def runtime_table(report: dict) -> dict:
    """The small file _app_native loads; the full report stays a report."""
    out = report["out_parameters"]
    return {
        "inventory_sha256": report["inventory_sha256"],
        "predicate": out["adapters"],
        "bool_result": out["bool_result_adapters"],
    }


def write_report(report: dict, output: Path) -> None:
    output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=PACKAGE / "_inventory.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "_differences.json")
    parser.add_argument("--table", type=Path, default=PACKAGE / "_out_parameters.json")
    args = parser.parse_args()
    data = args.inventory.read_bytes()
    report = analyze(json.loads(data), hashlib.sha256(data).hexdigest())
    write_report(report, args.output)
    write_report(runtime_table(report), args.table)
    for path in (args.output, args.table):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.name}: {path.stat().st_size} bytes; SHA256 {digest}")
    keys = ("callable_accessors", "enum_members_missing_natively")
    summary = {k: {f: report[k][f] for f in ("count", "classes")} for k in keys}
    summary["out_parameters"] = report["out_parameters"]["counts"]
    summary["constructor_keywords"] = report["constructor_keywords"]["status"]
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
