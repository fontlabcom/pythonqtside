# this_file: src/pythonqtside/tooling/flags.py
"""Measure PySide2 QFlags parameters that compete with an enum overload natively.

In FontLab's PythonQt ``QDialogButtonBox.Ok | QDialogButtonBox.Cancel`` is a plain
int, and ``QDialogButtonBox(Ok | Cancel)`` dispatches to the ``Qt.Orientation``
overload: no buttons (pqs-g04/fixtures/probe_overload_connect.json). PySide2 passes
a ``StandardButtons`` value. This command lists, per routed class, the constructor
and method positions where one PySide2 overload takes a QFlags type and another
overload of the same call arity takes an enum there (but none takes int).
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path

from .conversions import _effective, _enums, _route, declarations, load_sources

PACKAGE = Path(__file__).resolve().parents[1]
LIMITATIONS = [
    "QFlags classes are PySide2 nested classes with an empty body that are not enums.",
    "Positions where an overload of the same arity takes int are left out: an int cannot be attributed.",
    "Native acceptance covers the QDialogButtonBox constructor; the modal QMessageBox statics are unverified.",
]


def flag_classes(sources: dict[str, bytes], enums: set[str]) -> set[str]:
    found = set()
    for module, source in sources.items():
        for node in ast.parse(source).body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                path = f"{module}.{node.name}.{getattr(item, 'name', '')}"
                if (
                    isinstance(item, ast.ClassDef)
                    and len(item.body) == 1
                    and isinstance(item.body[0], ast.Expr)
                    and path not in enums
                ):
                    found.add(path)
    return found


def _positions(overloads: list[dict], flags: set[str], enums: set[str]) -> list[dict]:
    result = []
    width = max((len(o["parameters"]) for o in overloads), default=0)
    for index in range(width):
        for arity in range(index + 1, width + 1):
            covering = [
                o for o in overloads if o["required"] <= arity <= len(o["parameters"])
            ]
            found = {o["parameters"][index][1] for o in covering}
            wanted, keep = found & flags, found & enums
            if len(wanted) != 1 or not keep or "int" in found:
                continue
            entry = {"index": index, "flags": wanted.pop(), "keep": sorted(keep)}
            last = result[-1] if result else None
            if (
                last
                and last["index"] == index
                and last["arities"][1] == arity - 1
                and (
                    last["flags"],
                    last["keep"],
                )
                == (entry["flags"], entry["keep"])
            ):
                last["arities"][1] = arity
            else:
                result.append(entry | {"arities": [arity, arity]})
    return result


def _native(inventory: dict, path: str) -> str:
    module, owner, *rest = path.split(".")
    return ".".join(
        [_route(inventory, f"{module}.{owner}")["native_module"], owner, *rest]
    )


def analyze(
    inventory: dict, pyside_sources: dict[str, bytes], inventory_sha256: str
) -> dict:
    enums = _enums(pyside_sources)
    flags = flag_classes(pyside_sources, enums)
    pyside = {m: declarations(s) for m, s in pyside_sources.items()}
    classes = {}
    for module, decls in sorted(pyside.items()):
        for name in sorted(decls):
            key = f"{module}.{name}"
            route = _route(inventory, key)
            if route is None:
                continue
            methods = {"__init__": decls[name]["methods"].get("__init__", [])}
            methods |= {
                m: o
                for m, o in _effective(pyside, key).items()
                if not m.startswith("_")
            }
            for method, overloads in sorted(methods.items()):
                positions = [
                    p
                    | {
                        "flags": _native(inventory, p["flags"]),
                        "keep": [_native(inventory, k) for k in p["keep"]],
                    }
                    for p in _positions(overloads, flags, enums)
                    if _route(inventory, ".".join(p["flags"].split(".")[:2]))
                ]
                if positions:
                    static = method != "__init__" and all(
                        o["static"] for o in overloads
                    )
                    classes.setdefault(f"{route['native_module']}.{name}", {})[
                        method
                    ] = {
                        "static": static,
                        "positions": positions,
                    }
    return {
        "schema_version": 1,
        "inventory_sha256": inventory_sha256,
        "limitations": LIMITATIONS,
        "counts": {
            "flag_classes": len(flags),
            "methods": sum(len(m) for m in classes.values()),
            "positions": sum(
                len(e["positions"]) for m in classes.values() for e in m.values()
            ),
        },
        "classes": classes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--echopy", type=Path, default=Path("../fontlab-echopy"))
    parser.add_argument("--inventory", type=Path, default=PACKAGE / "_inventory.json")
    parser.add_argument("--output", type=Path, default=PACKAGE / "_flags.json")
    args = parser.parse_args()
    data = args.inventory.read_bytes()
    inventory = json.loads(data)
    pyside, _ = load_sources(args.echopy, inventory)
    report = analyze(inventory, pyside, hashlib.sha256(data).hexdigest())
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output.name}: {args.output.stat().st_size} bytes; SHA256 {digest}")
    print(json.dumps(report["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
