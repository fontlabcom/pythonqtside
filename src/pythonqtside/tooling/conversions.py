# this_file: src/pythonqtside/tooling/conversions.py
"""Measure PySide2 implicit enum -> value-class conversions against native PythonQt.

_inventory.json keeps parameter names but not annotations, so this command reads
the same PySide2 and native stubs the inventory pins, verified against its
recorded SHA256 inputs, and takes routing and native enum layout from it.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from .join import MODULES
from .surface import extract

PACKAGE = Path(__file__).resolve().parents[1]
REASONS = {
    "pyside_enum_or_int_overload": "A PySide2 overload of the same call arity takes an enum or int here; PySide2 dispatches directly, and the native overload set may too.",
    "pyside_numeric_overload": "A PySide2 overload of the same call arity takes float or a numeric sequence here; an int-like enum could dispatch to it.",
    "native_missing": "The routed native class declares no method of this name.",
    "native_int_parameter": "The recorded native signature types this position int.",
    "native_signature_mismatch": "The recorded native signature has no parameter at this position.",
}
# Shiboken converts implicitly only to value types (a public copy constructor in
# the stub) through non-explicit constructors. Stubs omit `explicit`; these Qt 5.15
# value types declare their one-argument enum constructor explicit in the headers.
EXPLICIT = frozenset(
    {
        "QtCore.QEvent",
        "QtGui.QOpenGLBuffer",
        "QtGui.QPageSize",
        "QtOpenGL.QGLBuffer",
        "QtWidgets.QTileRules",
    }
)
# Sibling annotations an int-like enum value could satisfy besides int and enums.
NUMERIC = frozenset({"float", "typing.Sequence[float]", "typing.Sequence[int]"})
LIMITATIONS = [
    "Stubs omit C++ explicit; value types other than the EXPLICIT list are assumed to convert implicitly.",
    "Native stubs record one Any-typed signature per method; PySide2's overload family stands in for the native set.",
    "native_int_parameter and native_signature_mismatch cannot fire on the current native stubs: every measured position is Any-typed and present (both count 0); they guard future stubs only.",
    "Exclusion is per call arity: a sibling overload excludes a position only at the arities it accepts; partial exclusions are keyed index@low-high.",
    "Plain int and QFlags parameters are never converted; only enum types the inventory finds natively.",
    "Constructors and module functions are not adapted; run_app resolves attribute calls only.",
    "Entries repeat per routed subclass: native stubs record no Qt base chain, so isinstance cannot be assumed to follow it.",
    "Derived from declarations; native acceptance is unverified until FontLab runs the checklist.",
]


def _parameters(node: ast.FunctionDef) -> dict:
    args = node.args.posonlyargs + node.args.args
    receiver = bool(args) and args[0].arg in {"self", "cls"}
    names = args[receiver:]
    decorators = {ast.unparse(d).split(".")[-1] for d in node.decorator_list}
    return {
        "parameters": [
            [a.arg, ast.unparse(a.annotation).removeprefix("PySide2.")]
            if a.annotation
            else [a.arg, None]
            for a in names
        ],
        "required": len(names) - len(node.args.defaults),
        "static": "staticmethod" in decorators or not receiver,
    }


def declarations(source: bytes) -> dict[str, dict]:
    """Top-level classes: bases, constructor and method overloads with annotations."""
    result = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods: dict[str, list] = {}
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.setdefault(item.name, []).append(_parameters(item))
        result[node.name] = {
            "bases": [ast.unparse(b).removeprefix("PySide2.") for b in node.bases],
            "methods": methods,
        }
    return result


def _route(inventory: dict, key: str) -> dict | None:
    module, _, name = key.partition(".")
    record = inventory["modules"].get(module, {}).get("classes", {}).get(name)
    return record if record and record["native_module"] else None


def _native_enum(inventory: dict, path: str) -> bool:
    """The enum's owner is routed and the inventory finds the enum type natively."""
    module, owner, enum = path.split(".", 2)
    record = _route(inventory, f"{module}.{owner}")
    layout = record and record["differences"]["nested_enums"].get(enum)
    return bool(layout) and layout["native_layout"] != "absent"


def value_classes(inventory: dict, pyside: dict, enums: set[str]) -> dict:
    """Routed value types constructible implicitly from one native enum argument."""
    result = {}
    for module, classes in pyside.items():
        for name, decl in classes.items():
            key = f"{module}.{name}"
            inits = decl["methods"].get("__init__", [])
            copyable = any(
                o["parameters"] == [[o["parameters"][0][0], key]]
                for o in inits
                if o["parameters"]
            )
            if not copyable or key in EXPLICIT or _route(inventory, key) is None:
                continue
            accepted = {
                o["parameters"][0][1]
                for o in inits
                if o["parameters"] and o["required"] <= 1
            }
            accepted = sorted(e for e in accepted & enums if _native_enum(inventory, e))
            if accepted:
                result[key] = accepted
    return result


def _covers(overload: dict, arity: int) -> bool:
    return overload["required"] <= arity <= len(overload["parameters"])


def _direct(overloads: list[dict], index: int, enums: set[str]) -> str | None:
    """Reason a sibling overload (already filtered to the call arity) wins here."""
    found = {o["parameters"][index][1] for o in overloads}
    if found & enums or "int" in found:
        return "pyside_enum_or_int_overload"
    return "pyside_numeric_overload" if found & NUMERIC else None


def _conversions(typed: list[dict], index: int, values: dict) -> dict:
    owners: dict[str, set[str]] = {}
    for overload in typed:
        value = overload["parameters"][index][1]
        for enum in values[value]:
            owners.setdefault(enum, set()).add(value)
    # An enum two value classes accept at one position is ambiguous: dropped.
    return {e: v.pop() for e, v in sorted(owners.items()) if len(v) == 1}


def _outcomes(overloads, index, values, enums, native_reason) -> list[tuple]:
    """(arity, conversions, reason) for each call arity a typed overload covers."""
    result = []
    width = max(len(o["parameters"]) for o in overloads)
    for arity in range(index + 1, width + 1):
        covering = [o for o in overloads if _covers(o, arity)]
        typed = [o for o in covering if o["parameters"][index][1] in values]
        conversions = _conversions(typed, index, values)
        if conversions:
            reason = _direct(covering, index, enums) or native_reason
            result.append((arity, conversions, reason))
    return result


def _ranges(outcomes: list[tuple]) -> list[list]:
    """Merge consecutive arities with the same outcome: [low, high, conv, reason]."""
    merged: list[list] = []
    for arity, conversions, reason in outcomes:
        last = merged[-1] if merged else None
        if last and last[1] == arity - 1 and last[2:] == [conversions, reason]:
            last[1] = arity
        else:
            merged.append([arity, arity, conversions, reason])
    return merged


def _native_reason(native: list[dict] | None, index: int) -> str | None:
    if native is None:
        return "native_missing"
    for overload in native:
        if len(overload["parameters"]) <= index:
            return "native_signature_mismatch"
        if overload["parameters"][index][1] == "int":
            return "native_int_parameter"
    return None


def _native_methods(native: dict, inventory: dict, key: str) -> dict:
    name = key.partition(".")[2]
    module = _route(inventory, key)["native_module"]
    return native.get(module, {}).get(name, {}).get("methods", {})


def _method(overloads, native, values, enums) -> tuple[list, dict]:
    positions, excluded = [], {}
    width = max(len(o["parameters"]) for o in overloads)
    for index in range(width):
        if not any(
            len(o["parameters"]) > index and o["parameters"][index][1] in values
            for o in overloads
        ):
            continue
        reason = _native_reason(native, index)
        ranges = _ranges(_outcomes(overloads, index, values, enums, reason))
        whole = len({r[3] for r in ranges}) == 1 and ranges[0][3]
        for low, high, conversions, why in ranges:
            if why is None:
                positions.append(
                    {"index": index, "arities": [low, high], "conversions": conversions}
                )
            elif whole:
                excluded[str(index)] = why
            else:
                excluded[f"{index}@{low}-{high}"] = why
    return positions, excluded


def _ancestors(pyside: dict, key: str) -> list[str]:
    module, _, name = key.partition(".")
    result = []
    for base in pyside.get(module, {}).get(name, {}).get("bases", []):
        base = base if "." in base else f"{module}.{base}"
        if base.partition(".")[0] in pyside:
            result += [base, *_ancestors(pyside, base)]
    return result


def _effective(pyside: dict, key: str) -> dict[str, list]:
    """Inherited PySide2 methods; a redeclared name hides the base overloads (C++)."""
    module, _, name = key.partition(".")
    decl = pyside.get(module, {}).get(name)
    if decl is None:
        return {}
    merged: dict[str, list] = {}
    for base in decl["bases"]:
        base = base if "." in base else f"{module}.{base}"
        merged |= _effective(pyside, base)
    return merged | decl["methods"]


def _measure(inventory, pyside, native, values, enums) -> tuple[dict, dict]:
    """Every routed class gets its inherited methods: native wrappers expose no
    Qt base chain (stubs: "Native bases: PythonQtInstanceWrapper")."""
    found, unsupported = {}, {}
    for module, classes in sorted(pyside.items()):
        for name in sorted(classes):
            key = f"{module}.{name}"
            if _route(inventory, key) is None:
                continue
            methods = _native_methods(native, inventory, key)
            for method, overloads in sorted(_effective(pyside, key).items()):
                if method.startswith("_"):
                    continue
                positions, excluded = _method(
                    overloads, methods.get(method), values, enums
                )
                static = all(o["static"] for o in overloads)
                found.setdefault(key, {})[method] = (positions, static)
                if excluded:
                    unsupported.setdefault(key, {})[method] = excluded
    return found, unsupported


def _table(inventory: dict, pyside: dict, found: dict) -> tuple[dict, int]:
    """Entries per routed class; an empty entry shadows a converting ancestor."""
    table, shadows = {}, 0
    for key, methods in found.items():
        native_key = (
            f"{_route(inventory, key)['native_module']}.{key.partition('.')[2]}"
        )
        for method, (positions, static) in methods.items():
            inherited = any(
                found.get(a, {}).get(method, ([], False))[0]
                for a in _ancestors(pyside, key)
            )
            if positions or inherited:
                shadows += not positions
                entry = {"static": static, "positions": positions}
                table.setdefault(native_key, {})[method] = entry
    return table, shadows


def _native_paths(inventory: dict, table: dict) -> dict:
    """Rewrite PySide2 module paths of enums and value classes to native modules."""

    def native(path: str) -> str:
        module, owner, *rest = path.split(".")
        routed = _route(inventory, f"{module}.{owner}")["native_module"]
        return ".".join([routed, owner, *rest])

    for methods in table.values():
        for entry in methods.values():
            for position in entry["positions"]:
                position["conversions"] = {
                    native(e): native(v) for e, v in position["conversions"].items()
                }
    return table


def _check_overlap(table: dict, out_parameters: dict) -> None:
    for kind in ("predicate", "bool_result"):
        for key, methods in out_parameters.get(kind, {}).items():
            for method in methods:
                if table.get(key, {}).get(method, {}).get("positions"):
                    raise ValueError(
                        f"{key}.{method} is in both conversion and out-parameter tables"
                    )


def _enums(sources: dict[str, bytes]) -> set[str]:
    return {
        f"{module}.{name}.{enum}"
        for module, source in sources.items()
        for name, cls in extract(source)["classes"].items()
        for enum in cls["enums"]
    }


def _counts(unsupported: dict, table: dict, values: int) -> dict:
    reasons = [r for c in unsupported.values() for m in c.values() for r in m.values()]
    positions = sum(len(e["positions"]) for c in table.values() for e in c.values())
    return {r: reasons.count(r) for r in REASONS} | {
        "value_classes": values,
        "positions": positions,
    }


def analyze(
    inventory: dict,
    pyside_sources: dict[str, bytes],
    native_sources: dict[str, bytes],
    inventory_sha256: str,
    *,
    out_parameters: dict,
) -> dict:
    """Deterministic table: sorted keys, counts, exclusions and source digest."""
    enums = _enums(pyside_sources)
    pyside = {m: declarations(s) for m, s in pyside_sources.items()}
    native = {m: declarations(s) for m, s in native_sources.items()}
    values = value_classes(inventory, pyside, enums)
    found, unsupported = _measure(inventory, pyside, native, values, enums)
    table, shadows = _table(inventory, pyside, found)
    table = _native_paths(inventory, table)
    _check_overlap(table, out_parameters)
    counts = _counts(unsupported, table, len(values)) | {"shadow_entries": shadows}
    return {
        "schema_version": 2,
        "inventory_sha256": inventory_sha256,
        "limitations": LIMITATIONS,
        "reasons": REASONS,
        "counts": counts,
        "value_classes": values,
        "classes": table,
        "unsupported": unsupported,
    }


def pack(report: dict) -> dict:
    """File form: each distinct entry stored once; classes refer to it by index."""
    canonical = {
        json.dumps(e, sort_keys=True)
        for methods in report["classes"].values()
        for e in methods.values()
    }
    entries = sorted(canonical)
    index = {text: i for i, text in enumerate(entries)}
    classes = {
        key: {m: index[json.dumps(e, sort_keys=True)] for m, e in methods.items()}
        for key, methods in report["classes"].items()
    }
    return report | {"classes": classes, "entries": [json.loads(e) for e in entries]}


def _verified(data: bytes, label: str, inputs: dict) -> bytes:
    if hashlib.sha256(data).hexdigest() != inputs[label]["sha256"]:
        raise ValueError(f"{label} SHA256 differs from _inventory.json inputs")
    return data


def load_sources(echopy: Path, inventory: dict) -> tuple[dict, dict]:
    """Read the inventory's pinned PySide2 wheel members and native stubs."""
    inputs = inventory["inputs"]
    (wheel,) = [k for k in inputs if k.endswith(".whl")]
    _verified((echopy / ".cache/upstream" / wheel).read_bytes(), wheel, inputs)
    with ZipFile(echopy / ".cache/upstream" / wheel) as archive:
        pyside = {
            m: _verified(archive.read(f"PySide2/{m}.pyi"), f"PySide2/{m}.pyi", inputs)
            for m in MODULES
        }
    stubs = echopy / "src/fontlab_echopy/PythonQt"
    native = {
        m: _verified((stubs / f"{m}.pyi").read_bytes(), f"PythonQt/{m}.pyi", inputs)
        for m in sorted(
            {
                c["native_module"]
                for d in inventory["modules"].values()
                for c in d["classes"].values()
            }
            - {None}
        )
    }
    return pyside, native


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--echopy", type=Path, default=Path("../fontlab-echopy"))
    parser.add_argument("--inventory", type=Path, default=PACKAGE / "_inventory.json")
    parser.add_argument(
        "--out-parameters", type=Path, default=PACKAGE / "_out_parameters.json"
    )
    parser.add_argument(
        "--output", type=Path, default=PACKAGE / "_implicit_conversions.json"
    )
    args = parser.parse_args()
    data = args.inventory.read_bytes()
    inventory = json.loads(data)
    pyside, native = load_sources(args.echopy, inventory)
    out_parameters = json.loads(args.out_parameters.read_text(encoding="utf-8"))
    report = analyze(
        inventory,
        pyside,
        native,
        hashlib.sha256(data).hexdigest(),
        out_parameters=out_parameters,
    )
    args.output.write_text(
        json.dumps(pack(report), sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output.name}: {args.output.stat().st_size} bytes; SHA256 {digest}")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
