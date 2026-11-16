# this_file: src/pythonqtside/_app_keywords.py
"""PySide2 keyword arguments for native PythonQt calls, which reject every keyword.

``QLabel("x", parent=w)`` raises "called slot does not support kwargs" in FontLab's
PythonQt (pqs-g04/probe_keywords.json). The generated ``_keywords.json`` lists the
PySide2 parameter names of each routed constructor and method overload. A keyword
call becomes a positional one when exactly one positional form fits; a skipped
parameter needs a recorded Qt declaration default. Constructor keywords that name
no parameter set a Qt property or connect a signal after construction, as PySide2
does. Anything ambiguous or unmapped keeps the native call, and its native error.
The table loads on the first call that actually passes keywords.
"""

import json
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from ._app_conversions import _native
from ._app_flags import convert

SIGNAL_METHODS = frozenset({"connect", "disconnect", "emit"})


@cache
def _table() -> dict[str, tuple[tuple[str, dict], ...]]:
    """Generated table by method name: (native class path, entry) pairs."""
    path = Path(__file__).with_name("_keywords.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    by_method: dict[str, list] = {}
    for key, methods in sorted(data["classes"].items()):
        for method, index in sorted(methods.items()):
            by_method.setdefault(method, []).append((key, data["entries"][index]))
    return {method: tuple(pairs) for method, pairs in by_method.items()}


def native_base(cls: type) -> type | None:
    """The first PythonQt class in a (possibly Python-derived) class's MRO."""
    return next((b for b in cls.__mro__ if b.__module__.startswith("PythonQt")), None)


def native_init(cls: type) -> bool:
    """True when ``cls.__init__`` is PythonQt's: no Python class before the first
    PythonQt base defines one (``object.__init__`` comes after it and is ignored)."""
    for base in cls.__mro__:
        if base.__module__.startswith("PythonQt"):
            return True
        if "__init__" in vars(base):
            return False
    return False


def _entry(receiver: Any, name: str) -> dict | None:
    """Most-derived entry matching an instance, a class (static methods) or, for
    ``__init__``, exactly the native class being constructed."""
    matches = []
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
            matches.append((len(cls.__mro__), entry))
    return max(matches, key=lambda m: m[0])[1] if matches else None


_MISSING = object()


def _default(value: Any) -> Any:
    """A recorded default; {"native": path} resolves now or is missing."""
    if isinstance(value, dict):
        resolved = _native(value["native"])
        return _MISSING if resolved is None else resolved
    return value


def _fit(overload: dict, args: tuple, kwargs: dict, leftover: bool) -> tuple | None:
    """(positional, unused keywords) for one overload, or None if it cannot fit."""
    names = overload["parameters"]
    if len(args) > len(names) or any(n in kwargs for n in names[: len(args)]):
        return None
    unused = {k: v for k, v in kwargs.items() if k not in names}
    if unused and not leftover:
        return None
    named = [i for i, n in enumerate(names) if n in kwargs]
    positional = list(args)
    for index in range(len(args), max(named, default=len(args) - 1) + 1):
        name = names[index]
        value = (
            kwargs[name]
            if name in kwargs
            else _default(overload["defaults"].get(name, _MISSING))
        )
        if value is _MISSING:
            return None
        positional.append(value)
    if len(positional) < overload["required"] and not all(
        n in overload["defaults"] for n in names[len(positional) : overload["required"]]
    ):
        return None
    return tuple(positional), unused


def map_keywords(
    entry: dict | None, args: tuple, kwargs: dict, *, leftover: bool
) -> tuple | None:
    """The single positional form the keywords select, with the fewest unused names."""
    if entry is None:
        return (tuple(args), dict(kwargs)) if leftover else None
    fits = [f for o in entry["overloads"] if (f := _fit(o, args, kwargs, leftover))]
    if leftover and not fits:
        parameters = {n for o in entry["overloads"] for n in o["parameters"]}
        if parameters & set(kwargs):  # a parameter keyword that no form can place
            return None
        fits = [(tuple(args), dict(kwargs))]
    if not fits:
        return None
    fewest = min(len(f[1]) for f in fits)
    best = [f for f in fits if len(f[1]) == fewest]
    # Distinct positional forms are ambiguous; native values are compared by identity.
    first = best[0]
    if any(
        len(f[0]) != len(first[0]) or any(a is not b for a, b in zip(f[0], first[0]))
        for f in best[1:]
    ):
        return None
    return first


def _connect(signal: Any, slot: Any, owner: Any = None, name: str | None = None) -> Any:
    return signal.connect(slot)


def apply_leftovers(
    obj: Any, leftover: dict, connect: Callable[[Any, Any], Any] = _connect
) -> None:
    """PySide2 constructor keywords: a Qt property is set, a signal is connected."""
    for name, value in leftover.items():
        meta = getattr(obj, "metaObject", None)
        if callable(meta) and meta().indexOfProperty(name) >= 0:
            if not obj.setProperty(name, value):
                raise TypeError(f"Qt property {name!r} rejected {value!r}")
            continue
        signal = getattr(obj, name, None)
        if callable(getattr(signal, "connect", None)):
            connect(signal, value, obj, name)
            continue
        raise AttributeError(
            f"{type(obj).__name__!r} has no Qt property or signal named {name!r}"
        )


def construct(
    cls: type,
    args: tuple,
    kwargs: dict,
    connect: Callable = _connect,
    own: Callable[[Any], Any] = lambda obj: obj,
) -> Any:
    """``cls(*args, **kwargs)`` for a class whose ``__init__`` is native.

    ``own`` registers the new object before any property or signal keyword is
    applied, so a rejected keyword cannot leave it outside cleanup."""
    base = native_base(cls)
    mapped = map_keywords(_entry(base, "__init__"), args, kwargs, leftover=True)
    if mapped is None:
        return cls(*args, **kwargs)  # PythonQt's own keyword error
    obj = own(cls(*convert(base, "__init__", mapped[0])))
    apply_leftovers(obj, mapped[1], connect)
    return obj


def initialize(
    init: Callable,
    instance: Any,
    base: type,
    args: tuple,
    kwargs: dict,
    connect: Callable = _connect,
) -> Any:
    """``Base.__init__(self, ...)`` or ``super().__init__(...)`` with keywords.

    ``init`` takes the positional arguments only (the instance already bound)."""
    mapped = map_keywords(_entry(base, "__init__"), args, kwargs, leftover=True)
    if mapped is None:
        return init(*args, **kwargs)
    result = init(*convert(base, "__init__", mapped[0]))
    apply_leftovers(instance, mapped[1], connect)
    return result


def keyword_method(receiver: Any, name: str, inner: Callable) -> Callable:
    """Wrap a native method so PySide2 keywords become positional arguments."""

    def call(*args: Any, **kwargs: Any) -> Any:
        if not kwargs:
            return inner(*args)
        mapped = map_keywords(_entry(receiver, name), args, kwargs, leftover=False)
        if mapped is None:
            return inner(*args, **kwargs)
        return inner(*mapped[0])

    return call
