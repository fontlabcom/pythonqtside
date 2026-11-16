# this_file: src/pythonqtside/__init__.py
"""Native Qt5 namespace routing; measured compatibility work is planned separately."""

from importlib import import_module
from types import ModuleType

from ._app import AppHandle, run_app

__all__ = [
    "AppHandle",
    "Qt",
    "QtCore",
    "QtGui",
    "QtNetwork",
    "QtOpenGL",
    "QtSvg",
    "QtUiTools",
    "QtWidgets",
    "QtXmlPatterns",
    "compat",
    "run_app",
]


def __getattr__(name: str) -> ModuleType:
    if name not in __all__:
        raise AttributeError(name)
    module = import_module(__name__ + "." + name)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
