# this_file: src/pythonqtside/tooling/surface.py
"""Extract declarations with ast, without executing stubs or their imports."""

import ast
from typing import Any

Surface = dict[str, Any]


def _shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, int | bool]:
    """Retain overload arities, not copied signature text or claimed dispatch."""
    args = node.args
    positional = args.posonlyargs + args.args
    receiver = bool(positional and positional[0].arg in {"self", "cls"})
    return {
        "required_positional": max(0, len(positional) - len(args.defaults) - receiver),
        "optional_positional": len(args.defaults),
        "required_keyword_only": args.kw_defaults.count(None),
        "optional_keyword_only": len(args.kw_defaults) - args.kw_defaults.count(None),
        "varargs": args.vararg is not None,
        "kwargs": args.kwarg is not None,
    }


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    """Parameter names and return annotation only; used for out-parameter evidence."""
    names = [a.arg for a in node.args.posonlyargs + node.args.args]
    decorators = {ast.unparse(d).split(".")[-1] for d in node.decorator_list}
    static = "staticmethod" in decorators or not names or names[0] != "self"
    if names and names[0] in {"self", "cls"}:
        names = names[1:]
    returns = ast.unparse(node.returns) if node.returns is not None else None
    signature = {"parameters": names, "returns": returns}
    # Recorded only when true so instance-method records keep their shape.
    return signature | {"static": True} if static else signature


def _attributes(body: list[ast.stmt]) -> dict[str, str]:
    result = {}
    for node in body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            result[node.target.id] = ast.unparse(node.annotation)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = (
                        "int"
                        if isinstance(node.value, ast.Constant)
                        and type(node.value.value) is int
                        else "Any"
                    )
    return {
        name: annotation
        for name, annotation in result.items()
        if not name.startswith("_")
    }


def _is_enum(node: ast.ClassDef, attributes: dict[str, str]) -> bool:
    bases = {ast.unparse(base).split(".")[-1] for base in node.bases}
    methods = any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in node.body
    )
    return bool(bases & {"Enum", "IntEnum", "Flag", "IntFlag"}) or (
        not methods
        and any(
            annotation.split(".")[-1] == node.name for annotation in attributes.values()
        )
    )


def _functions(body: list[ast.stmt], *, special_methods: bool = False) -> Surface:
    result: Surface = {
        "methods": set(),
        "properties": set(),
        "getters": set(),
        "constructors": [],
        "signatures": {},
    }
    for node in body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        shape = _shape(node)
        if node.name == "__init__":
            result["constructors"].append(shape)
        elif not node.name.startswith("_") or (
            special_methods and node.name.startswith("__") and node.name.endswith("__")
        ):
            decorators = {ast.unparse(d).split(".")[-1] for d in node.decorator_list}
            if decorators & {"property", "setter", "getter", "deleter"}:
                result["properties"].add(node.name)
            else:
                result["methods"].add(node.name)
                if not any(shape.values()):
                    result["getters"].add(node.name)
                result["signatures"].setdefault(node.name, []).append(_signature(node))
    return result


def _class(node: ast.ClassDef) -> Surface:
    result = _functions(node.body, special_methods=True)
    attributes = _attributes(node.body)
    children = {
        n.name: _class(n)
        for n in node.body
        if isinstance(n, ast.ClassDef) and not n.name.startswith("_")
    }
    enums = {
        name: set(child["attributes"])
        for name, child in children.items()
        if child["is_enum"]
    }
    for name, child in children.items():
        enums.update({f"{name}.{key}": value for key, value in child["enums"].items()})
    direct_enums = {name for name in enums if "." not in name}
    enum_members = {
        name
        for name, annotation in attributes.items()
        if annotation.split(".")[-1] in direct_enums | {node.name}
    }
    result.update(
        attributes=attributes,
        bases=[ast.unparse(b) for b in node.bases],
        enums=enums,
        enum_members=enum_members,
        enum_candidates={
            n for n, a in attributes.items() if n[0].isupper() and a in {"Any", "int"}
        },
        opaque_types={n for n, a in attributes.items() if a in {"type", "typing.Type"}},
        nested_classes={n: c for n, c in children.items() if not c["is_enum"]},
        is_enum=_is_enum(node, attributes),
        stub_helper=node.name == "Object"
        and [ast.unparse(b) for b in node.bases] == ["object"]
        and all(isinstance(n, ast.Pass) for n in node.body),
    )
    if result["is_enum"]:
        result["enum_members"].update(attributes)
    return result


def extract(source: str | bytes) -> Surface:
    """Read one module at a time; docstrings and imported helpers are discarded."""
    tree = ast.parse(source)
    classes = {
        node.name: _class(node)
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    members = _functions(tree.body)["methods"] | set(_attributes(tree.body))
    return {"classes": classes, "members": members}


def effective_classes(modules: dict[str, Surface]) -> dict[str, Surface]:
    """Expand declared bases in these modules so flattened native members compare fairly."""
    declared = {
        f"{module}.{name}": cls
        for module, data in modules.items()
        for name, cls in data["classes"].items()
    }
    resolved: dict[str, Surface] = {}

    def resolve(key: str, active: tuple[str, ...] = ()) -> Surface:
        if key in active:
            raise ValueError(f"Cyclic stub inheritance: {key}")
        if key in resolved:
            return resolved[key]
        cls = declared[key]
        merged = {
            k: v.copy() if isinstance(v, (dict, set, list)) else v
            for k, v in cls.items()
        }
        for base in reversed(cls["bases"]):
            base = base.removeprefix("PySide2.").removeprefix("PythonQt.")
            base = base if "." in base else key.rpartition(".")[0] + "." + base
            if base in declared:
                parent = resolve(base, (*active, key))
                for field in (
                    "methods",
                    "properties",
                    "getters",
                    "enum_members",
                    "enum_candidates",
                    "opaque_types",
                ):
                    merged[field] |= parent[field]
                for field in ("attributes", "enums", "nested_classes", "signatures"):
                    merged[field] = parent[field] | merged[field]
        resolved[key] = merged
        return merged

    return {key: resolve(key) for key in declared}
