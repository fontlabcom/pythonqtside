# this_file: src/pythonqtside/_app_conversions.py
"""Measured PySide2 implicit enum -> value-class conversions for native calls.

PythonQt rejects e.g. ``setEasingCurve(QEasingCurve.OutElastic)`` where PySide2
converts the enum through ``QEasingCurve(type)``. Positions come from the generated
``_implicit_conversions.json``; callers in ``_app_native`` gate on a native receiver
without a Python override. Values are wrapped only when they are instances of the
measured native enum type; anything else, including plain ints, passes through.
"""

import json
import sys
from functools import cache, partial
from importlib import import_module
from pathlib import Path
from typing import Any


@cache
def _table() -> dict[str, tuple[tuple[str, dict], ...]]:
    """Generated table by method name: (native class path, entry) pairs."""
    path = Path(__file__).with_name("_implicit_conversions.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    by_method: dict[str, list] = {}
    for key, methods in sorted(data["classes"].items()):
        for method, index in sorted(methods.items()):
            by_method.setdefault(method, []).append((key, data["entries"][index]))
    return {method: tuple(pairs) for method, pairs in by_method.items()}


# Native path -> (PythonQt module it came from, object or None). One lookup per
# path: setCursor alone has ~95 candidate classes, resolved on every attribute call.
_RESOLVED: dict[str, tuple[Any, Any]] = {}


def _lookup(root: Any, path: str) -> Any:
    result = root
    for part in path.split("."):
        result = getattr(result, part, None)
        if result is None:
            return None
    return result


def _native(path: str) -> Any:
    """``QtCore.Qt.GlobalColor`` -> the PythonQt object, or None when absent."""
    root = sys.modules.get("PythonQt")
    if root is None:
        try:
            root = import_module("PythonQt")
        except ModuleNotFoundError:
            return None
    cached = _RESOLVED.get(path)
    if cached is None or cached[0] is not root:
        cached = _RESOLVED[path] = (root, _lookup(root, path))
    return cached[1]


def _entry(receiver: Any, candidates: tuple) -> dict | None:
    """The most-derived table class matching the receiver (class: static only)."""
    matches = []
    for key, entry in candidates:
        cls = _native(key)
        if not isinstance(cls, type):
            continue
        if isinstance(receiver, type):
            matched = entry["static"] and issubclass(receiver, cls)
        else:
            matched = isinstance(receiver, cls)
        if matched:
            matches.append((len(cls.__mro__), entry))
    return max(matches, key=lambda m: m[0])[1] if matches else None


def _converted(value: Any, conversions: dict[str, str]) -> Any:
    if type(value) in (int, bool):
        return value
    for enum, target in conversions.items():
        enum_type = _native(enum)
        if isinstance(enum_type, type) and isinstance(value, enum_type):
            cls = _native(target)
            return value if cls is None else cls(value)
    return value


def _with_conversions(method: Any, positions: list, *args: Any, **kwargs: Any) -> Any:
    """Positional PySide2 call -> measured enums wrapped -> one native call."""
    if kwargs:
        return method(*args, **kwargs)
    converted = list(args)
    for position in positions:
        index, (low, high) = position["index"], position["arities"]
        if index < len(args) and low <= len(args) <= high:
            converted[index] = _converted(args[index], position["conversions"])
    return method(*converted)


def conversion_call(receiver: Any, name: str, method: Any) -> Any:
    """A wrapping callable for a measured method, or None when nothing applies."""
    candidates = _table().get(name)
    if candidates is None:
        return None
    entry = _entry(receiver, candidates)
    if entry is None or not entry["positions"]:
        return None
    return partial(_with_conversions, method, entry["positions"])
