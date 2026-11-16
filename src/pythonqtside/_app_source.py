# this_file: src/pythonqtside/_app_source.py
"""Adapt calls in memory while retaining original filenames and line numbers."""

import ast
import hashlib


class Calls(ast.NodeTransformer):
    """Prepare the callee; keep its invocation in the original Python frame."""

    def __init__(self, call_name: str, resolve_name: str) -> None:
        self.call_name = call_name
        self.resolve_name = resolve_name
        self.locations: list[dict[str, int]] = []
        self.super_locations: list[dict[str, int]] = []

    def visit_Call(self, node: ast.Call) -> ast.Call:
        # Record syntax before visiting children rewrites the inner super call.
        match node.func:
            case ast.Attribute(value=ast.Call(func=ast.Name(id="super"))):
                self.super_locations.append(
                    {"line": node.lineno, "column": node.col_offset}
                )
        if isinstance(node.func, ast.Attribute):
            # The callee attribute is adapted below; only its receiver is visited,
            # so visit_Attribute never rewrites a method being called.
            node.func.value = self.visit(node.func.value)
            node.args = [self.visit(arg) for arg in node.args]
            node.keywords = [self.visit(keyword) for keyword in node.keywords]
        else:
            self.generic_visit(node)
        self.locations.append({"line": node.lineno, "column": node.col_offset})
        callee = node.func
        if isinstance(callee, ast.Attribute):
            # Keyword call sites tell the resolver to map PySide2 keyword names.
            keywords = [ast.Constant(True)] if node.keywords else []
            receiver, attribute = callee.value, [ast.Constant(callee.attr)]
            # `owner.signal.connect(cb)`: pass the owner and signal name too, so a
            # callback can reach the signal overload matching its arity.
            if callee.attr in {"connect", "disconnect"} and isinstance(
                receiver, ast.Attribute
            ):
                attribute = [
                    ast.Constant(receiver.attr),
                    ast.Constant(bool(node.keywords)),
                    ast.Constant(callee.attr),
                ]
                receiver, keywords = receiver.value, []
            callee = ast.copy_location(
                ast.Call(
                    func=ast.Name(id=self.resolve_name, ctx=ast.Load()),
                    args=[receiver, *attribute, *keywords],
                    keywords=[],
                ),
                callee,
            )
        node.func = ast.copy_location(
            ast.Call(
                func=ast.Name(id=self.call_name, ctx=ast.Load()),
                # A keyword call site also maps keywords of a captured native method.
                args=[callee, *([ast.Constant(True)] if node.keywords else [])],
                keywords=[],
            ),
            node.func,
        )
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """``base = super().name`` (a load, not a call): resolve it like a super
        call, so a native base method PythonQt's super() misses is still found and
        a later keyword call is mapped."""
        match node:  # checked before visiting rewrites the inner super() call
            case ast.Attribute(
                value=ast.Call(func=ast.Name(id="super")), ctx=ast.Load()
            ):
                super_load = True
            case _:
                super_load = False
        self.generic_visit(node)
        if super_load:
            self.super_locations.append(
                {"line": node.lineno, "column": node.col_offset}
            )
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id=self.resolve_name, ctx=ast.Load()),
                    args=[node.value, ast.Constant(node.attr), ast.Constant(True)],
                    keywords=[],
                ),
                node,
            )
        return node


def adapt_source(
    source: str, filename: str, *, call_name: str, resolve_name: str
) -> tuple[ast.Module, dict]:
    """Produce a compilable AST and original-source provenance without I/O."""
    tree = ast.parse(source, filename=filename)
    transformer = Calls(call_name, resolve_name)
    tree = ast.fix_missing_locations(transformer.visit(tree))
    return tree, {
        "original_source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "call_sites": len(transformer.locations),
        "locations": transformer.locations,
        # These are rewritten source sites, not counts of runtime fallback use.
        "super_call_sites": len(transformer.super_locations),
        "super_locations": transformer.super_locations,
    }
