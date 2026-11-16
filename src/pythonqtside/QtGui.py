# this_file: src/pythonqtside/QtGui.py
"""QtGui objects routed from FontLab's native PythonQt through Echopy."""
from typing import Any
from ._routing import member, names


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    return member('QtGui', name)


def __dir__() -> list[str]:
    return names('QtGui')
