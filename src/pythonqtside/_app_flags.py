# this_file: src/pythonqtside/_app_flags.py
"""PySide2 QFlags arguments where a native enum overload would win the dispatch.

``QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)`` passes a plain
int in PythonQt, which selects the ``Qt.Orientation`` overload (no buttons). At the
positions in the generated ``_flags.json`` a plain int, or an enum value other than
the competing overload's enum, is wrapped in the native QFlags class first.
"""

import json
from functools import cache, partial
from pathlib import Path
from typing import Any

from ._app_conversions import _native


@cache
def _table() -> dict[str, tuple[tuple[str, dict], ...]]:
    data = json.loads(Path(__file__).with_name("_flags.json").read_text("utf-8"))
    by_method: dict[str, list] = {}
    for key, methods in sorted(data["classes"].items()):
        for method, entry in sorted(methods.items()):
            by_method.setdefault(method, []).append((key, entry))
    return {method: tuple(pairs) for method, pairs in by_method.items()}


def _entry(receiver: Any, name: str) -> dict | None:
    for key, entry in _table().get(name, ()):
        cls = _native(key)
        if not isinstance(cls, type):
            continue
        if name == "__init__":
            matched = receiver is cls
        elif isinstance(receiver, type):
            matched = entry["static"] and issubclass(receiver, cls)
        else:
            matched = isinstance(receiver, cls)
        if matched:
            return entry
    return None


def _wrapped(value: Any, position: dict) -> Any:
    if not isinstance(value, int) or type(value) is bool:
        return value
    if any(
        isinstance(t, type) and isinstance(value, t)
        for t in map(_native, position["keep"])
    ):
        return value
    flags = _native(position["flags"])
    return value if flags is None else flags(value)


def convert(receiver: Any, name: str, args: tuple) -> tuple:
    """Positional arguments with measured QFlags positions wrapped."""
    entry = _entry(receiver, name) if name in _table() else None
    if entry is None:
        return args
    result = list(args)
    for position in entry["positions"]:
        index, (low, high) = position["index"], position["arities"]
        if index < len(args) and low <= len(args) <= high:
            result[index] = _wrapped(args[index], position)
    return tuple(result)


def _with_flags(
    receiver: Any, name: str, method: Any, *args: Any, **kwargs: Any
) -> Any:
    return method(*convert(receiver, name, args), **kwargs)


def flags_call(receiver: Any, name: str, method: Any) -> Any:
    """Wrap a measured method, or return it unchanged."""
    if name not in _table() or _entry(receiver, name) is None:
        return method
    return partial(_with_flags, receiver, name, method)
