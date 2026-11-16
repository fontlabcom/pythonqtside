# this_file: src/pythonqtside/_routing.py
"""Inventory-based namespace placement retaining original native class identity."""

import json
from importlib import import_module
from pathlib import Path
from typing import Any

INVENTORY = json.loads(
    Path(__file__).with_name("_inventory.json").read_text(encoding="utf-8")
)
_ROUTES = {
    module: data["classes"] | data["members"]
    for module, data in INVENTORY["modules"].items()
}
_OWNERS: dict[str, list[str]] = {}
for _module, _entries in _ROUTES.items():
    for _name in _entries:
        _OWNERS.setdefault(_name, []).append(_module)
WIDGET_CLASSES = frozenset(
    n for n, route in _ROUTES["QtWidgets"].items() if route["native_module"]
)


def _target(module: str) -> Any:
    try:
        return import_module("fontlab_echopy.PythonQt." + module)
    except ModuleNotFoundError as error:
        if error.name not in {
            "fontlab_echopy",
            "fontlab_echopy.PythonQt",
            f"fontlab_echopy.PythonQt.{module}",
        }:
            raise
        raise AttributeError(f"Native module {module} is unavailable") from error


def _native_member(module: str, name: str, family: str) -> Any:
    """Translate a missing export/module, without hiding broken dependency imports."""
    try:
        return getattr(_target(module), name)
    except AttributeError:
        pass
    raise AttributeError(
        f"pythonqtside.{family}.{name} is not available in FontLab's PythonQt"
    )


def member(module: str, name: str) -> Any:
    """Resolve the pinned join while preserving each actual native object."""
    if module == "Qt":
        return getattr(_target(module), name)
    route = _ROUTES[module].get(name)
    if route is None and name in _OWNERS:
        owners = ", ".join(f"pythonqtside.{owner}" for owner in _OWNERS[name])
        raise AttributeError(f"{name} is exposed by {owners}")
    if route is None:
        if module != "QtWidgets":
            try:
                return _native_member(module, name, module)
            except AttributeError:
                pass
        raise AttributeError(f"pythonqtside.{module} has no known name {name!r}")
    target = route["native_module"]
    if module == "QtCore" and name == "QObject":
        try:
            return _native_member("QtCore", name, module)
        except AttributeError:
            pass
    if target is None:
        raise AttributeError(
            f"pythonqtside.{module}.{name} is not available in FontLab's PythonQt"
        )
    return _native_member(target, name, module)


def names(module: str) -> list[str]:
    """Advertise resolving joined names and preserve native family extensions."""
    if module == "Qt":
        return sorted(n for n in dir(_target(module)) if not n.startswith("_"))
    try:
        local = set(dir(_target(module))) if module != "QtWidgets" else set()
    except AttributeError:
        local = set()
    public = []
    for name in sorted(
        _ROUTES[module].keys() | {n for n in local if not n.startswith("_")}
    ):
        try:
            member(module, name)
        except AttributeError:
            pass
        else:
            public.append(name)
    return public
