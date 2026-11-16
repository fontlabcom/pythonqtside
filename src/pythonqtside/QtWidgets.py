# this_file: src/pythonqtside/QtWidgets.py
"""QtWidgets objects routed from FontLab's native PythonQt through Echopy."""
from typing import Any
from ._routing import member, names


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    return member('QtWidgets', name)


def __dir__() -> list[str]:
    return names('QtWidgets')
