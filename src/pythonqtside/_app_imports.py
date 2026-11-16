# this_file: src/pythonqtside/_app_imports.py
"""A retained, private import graph with source provenance and no aliases."""

import builtins
import hashlib
import uuid
from importlib import import_module
from importlib.util import resolve_name
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any

from ._app_source import adapt_source


def freeze(value: Any) -> Any:
    """Freeze nested report structures while retaining native identity objects."""
    if isinstance(value, dict):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    return value


class ImportContext:
    """Route PySide2 and local Python files through one app's private builtins."""

    def __init__(self, handle: Any, root: Path) -> None:
        self.handle = handle
        self.root = root
        self.modules = {}
        self.reports = {}
        self.identities = {}
        self.original_import = builtins.__import__
        self.builtins = dict(vars(builtins), __import__=self.importer)
        suffix = uuid.uuid4().hex
        self.call_name = "_pythonqtside_call_" + suffix
        self.resolve_name = "_pythonqtside_resolve_" + suffix

    def execute(self, path: Path, namespace: dict) -> None:
        """Decode via Python's encoding-cookie rules and retain exact original bytes."""
        import tokenize
        from io import BytesIO

        original = path.read_bytes()
        encoding, _ = tokenize.detect_encoding(BytesIO(original).readline)
        source = original.decode(encoding)
        tree, report = adapt_source(
            source, str(path), call_name=self.call_name, resolve_name=self.resolve_name
        )
        report.update(
            original_bytes=original,
            source_sha256=hashlib.sha256(original).hexdigest(),
            filename=str(path),
            encoding=encoding,
            limitations=("Dynamic exec/eval strings are not adapted.",),
        )
        self.reports[str(path)] = freeze(report)
        namespace.update(__file__=str(path), __builtins__=self.builtins)
        namespace[self.call_name] = self.handle._prepare
        namespace[self.resolve_name] = self.handle._resolve
        exec(compile(tree, str(path), "exec"), namespace)  # noqa: S102 - explicit local source runner

    def _local_path(self, name: str) -> tuple[Path, bool] | None:
        candidate = self.root.joinpath(*name.split("."))
        if candidate.with_suffix(".py").is_file():
            return candidate.with_suffix(".py"), False
        if (candidate / "__init__.py").is_file():
            return candidate / "__init__.py", True
        return None

    def _qt_module(self, name: str) -> ModuleType:
        module = ModuleType(name)
        module.__package__ = "PySide2" if "." in name else ""
        if name == "PySide2":
            module.__path__ = []
            module.__getattr__ = lambda member: self._load("PySide2." + member)
        else:
            target = import_module("pythonqtside." + name.split(".", 1)[1])

            def member(attribute: str) -> Any:
                value = getattr(target, attribute)
                if any(value is cls for cls in self.handle._application_classes):
                    value = self.handle._application
                if isinstance(value, type):
                    self.identities[name + "." + attribute] = value
                return value

            module.__getattr__ = member
            module.__dir__ = lambda: dir(target)
        return module

    def _load(self, name: str) -> ModuleType:
        if name in self.modules:
            return self.modules[name]
        parent_name, _, child = name.rpartition(".")
        parent = self._load(parent_name) if parent_name else None
        if name == "PySide2" or name.startswith("PySide2."):
            module = self._qt_module(name)
            self.modules[name] = module
        else:
            found = self._local_path(name)
            if found is None:
                raise ModuleNotFoundError(
                    f"No private app module named {name!r}", name=name
                )
            path, package = found
            module = ModuleType(name)
            module.__package__ = name if package else parent_name
            if package:
                module.__path__ = [str(path.parent)]
            self.modules[name] = module
            try:
                self.execute(path, vars(module))
            except BaseException:
                self.modules.pop(name, None)
                raise
        if parent is not None:
            setattr(parent, child, module)
        return module

    def importer(
        self,
        name: str,
        globals: dict | None = None,
        locals: dict | None = None,
        fromlist: tuple = (),
        level: int = 0,
    ) -> ModuleType:
        """Match Python's top-package/fromlist return convention in the private graph."""
        self.handle._require_open()
        if level:
            package = (globals or {}).get("__package__", "")
            name = resolve_name("." * level + name, package)
        root = name.partition(".")[0]
        if root != "PySide2" and self._local_path(root) is None:
            return self.original_import(name, globals, locals, fromlist, 0)
        module = self._load(name)
        for item in fromlist or ():
            if (
                item != "*"
                and item not in vars(module)
                and self._local_path(name + "." + item)
            ):
                self._load(name + "." + item)
        return module if fromlist else self._load(root)
