# this_file: src/pythonqtside/tooling/keywords.py
"""Measure PySide2 keyword parameters for native PythonQt calls.

FontLab's PythonQt rejects every keyword argument to a native constructor or method
("called slot does not support kwargs"; issue 104 evidence pqs-g04/probe_keywords.json).
PySide2 accepts its declared parameter names. This command reads the PySide2 and native
stubs the inventory pins (SHA256-verified) and writes, per routed class, the PySide2
parameter names of every constructor and method overload, plus the Qt 5.15 declaration
defaults that Echopy's native docstrings quote, where they are plain literals.
"""

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

from .conversions import _effective, _route, declarations, load_sources, pack

PACKAGE = Path(__file__).resolve().parents[1]
LIMITATIONS = [
    "FontLab 9 PythonQt rejects keyword arguments on every native constructor and method measured (pqs-g04/probe_keywords.json).",
    "Parameter names come from the PySide2 5.15.2.1 stubs; they mirror the C++ declarations except where PySide2 drops out-parameters.",
    "Tuple-returning PySide2 methods are listed only when _out_parameters.json adapts them; the rest drop out-parameters and are omitted.",
    "Gap defaults are Qt 5.15 declaration defaults quoted in Echopy's native docstrings: nullptr, QString(), true/false, numbers, or Class::Member of a routed class (resolved natively at call time; unresolved means no mapping).",
    "Constructors have no quoted declarations, so a constructor keyword call cannot skip a parameter.",
    "Entries repeat per routed subclass: native stubs record no Qt base chain.",
]
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
LITERALS = {
    "nullptr": None,
    "Q_NULLPTR": None,
    "QString()": "",
    "true": True,
    "false": False,
}


def _literal(text: str, pointer: bool, owners: dict[str, str]) -> tuple[bool, object]:
    """(known, value) for a C++ default; pointers treat 0 as None.

    `Qt::AlignLeft` or `QLineEdit::Normal` become {"native": "QtGui.QLineEdit.Normal"}
    when the owner class is routed; the runtime resolves the path or declines.
    """
    text = text.strip()
    member = re.fullmatch(r"(\w+)::(\w+)", text)
    if member and member.group(1) in owners:
        return True, {
            "native": f"{owners[member.group(1)]}.{member.group(1)}.{member.group(2)}"
        }
    if text in LITERALS:
        return True, LITERALS[text]
    if pointer and text in {"0", "NULL"}:
        return True, None
    if re.fullmatch(r"-?\d+", text):
        return True, int(text)
    if re.fullmatch(r"-?\d+\.\d*f?", text):
        return True, float(text.rstrip("f"))
    return False, None


def _split(params: str) -> list[str]:
    """Top-level commas only: `QString()` and template arguments stay whole."""
    parts, depth, current = [], 0, ""
    for char in params:
        depth += char in "(<"
        depth -= char in ")>"
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    return [p for p in (*parts, current) if p.strip()]


def qt_defaults(docstring: str, method: str, owners: dict[str, str]) -> list[dict]:
    """Per quoted Qt declaration of `method`: {name: literal} for literal defaults."""
    result = []
    for line in docstring.splitlines():
        if not line.startswith("### "):
            continue
        line = LINK.sub(r"\1", line).replace("\\", "")
        match = re.search(rf"\w+::{re.escape(method)}\((.*)\)", line)
        if match is None:
            continue
        found = {}
        for param in _split(match.group(1)):
            named = re.search(r"(\*?)\*(\w+)\*\s*(?:=\s*(.+))?$", param.strip())
            if named and named.group(3) is not None:
                known, value = _literal(named.group(3), bool(named.group(1)), owners)
                if known:
                    found[named.group(2)] = value
        result.append(found)
    return result


def native_docstrings(source: bytes) -> dict[str, dict[str, str]]:
    """Class -> method -> docstring from one native Echopy stub."""
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            result[node.name] = {
                item.name: ast.get_docstring(item) or ""
                for item in node.body
                if isinstance(item, ast.FunctionDef)
            }
    return result


def _agreed(headings: list[dict]) -> dict:
    """Defaults every quoted declaration agrees on (overloads may disagree)."""
    if not headings:
        return {}
    names = set.intersection(*(set(h) for h in headings))
    return {
        n: headings[0][n]
        for n in sorted(names)
        if all(h[n] == headings[0][n] for h in headings)
    }


def _overloads(overloads: list[dict], defaults: dict) -> list[dict]:
    shapes = []
    for overload in overloads:
        names = [p[0] for p in overload["parameters"]]
        shape = {
            "parameters": names,
            "required": overload["required"],
            "defaults": {n: defaults[n] for n in names if n in defaults},
        }
        if names and shape not in shapes:
            shapes.append(shape)
    return shapes


def _tuple_methods(inventory: dict, key: str) -> set[str]:
    module, _, name = key.partition(".")
    record = inventory["modules"][module]["classes"][name]
    return set(record["differences"].get("tuple_returns", {}))


def _adapted(out_parameters: dict, native_key: str) -> set[str]:
    return {
        m
        for kind in ("predicate", "bool_result")
        for m in out_parameters.get(kind, {}).get(native_key, {})
    }


def _out_defaults(out_parameters: dict, native_key: str, method: str) -> dict:
    """Defaults the BoolResult adapter already uses for PySide2-omittable parameters."""
    entry = out_parameters.get("bool_result", {}).get(native_key, {}).get(method)
    return dict(entry["defaults"]) if entry else {}


def analyze(
    inventory: dict,
    pyside_sources: dict[str, bytes],
    native_sources: dict[str, bytes],
    inventory_sha256: str,
    *,
    out_parameters: dict,
) -> dict:
    pyside = {m: declarations(s) for m, s in pyside_sources.items()}
    docs = {m: native_docstrings(s) for m, s in native_sources.items()}
    owners = {"Qt": "QtCore"}
    for data in inventory["modules"].values():
        for name, record in sorted(data["classes"].items()):
            if record["native_module"]:
                owners.setdefault(name, record["native_module"])
    classes, omitted = {}, {}
    for module, decls in sorted(pyside.items()):
        for name in sorted(decls):
            key = f"{module}.{name}"
            route = _route(inventory, key)
            if route is None:
                continue
            native_key = f"{route['native_module']}.{name}"
            native_docs = docs.get(route["native_module"], {}).get(name, {})
            tuples = _tuple_methods(inventory, key) - _adapted(
                out_parameters, native_key
            )
            methods = {"__init__": decls[name]["methods"].get("__init__", [])}
            methods |= {
                m: o
                for m, o in _effective(pyside, key).items()
                if not m.startswith("_")
            }
            for method, overloads in sorted(methods.items()):
                if method in tuples:
                    omitted.setdefault(native_key, []).append(method)
                    continue
                defaults = _agreed(
                    qt_defaults(native_docs.get(method, ""), method, owners)
                )
                defaults |= _out_defaults(out_parameters, native_key, method)
                shapes = _overloads(overloads, {} if method == "__init__" else defaults)
                if shapes:
                    static = method != "__init__" and all(
                        o["static"] for o in overloads
                    )
                    classes.setdefault(native_key, {})[method] = {
                        "static": static,
                        "overloads": shapes,
                    }
    counts = {
        "classes": len(classes),
        "methods": sum(len(m) for m in classes.values()),
        "constructors": sum("__init__" in m for m in classes.values()),
        "gap_defaults": sum(
            len(o["defaults"])
            for m in classes.values()
            for e in m.values()
            for o in e["overloads"]
        ),
        "omitted_tuple_methods": sum(len(v) for v in omitted.values()),
    }
    return {
        "schema_version": 1,
        "inventory_sha256": inventory_sha256,
        "limitations": LIMITATIONS,
        "counts": counts,
        "classes": classes,
        "omitted": omitted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--echopy", type=Path, default=Path("../fontlab-echopy"))
    parser.add_argument("--inventory", type=Path, default=PACKAGE / "_inventory.json")
    parser.add_argument(
        "--out-parameters", type=Path, default=PACKAGE / "_out_parameters.json"
    )
    parser.add_argument("--output", type=Path, default=PACKAGE / "_keywords.json")
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
        json.dumps(pack(report), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output.name}: {args.output.stat().st_size} bytes; SHA256 {digest}")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
