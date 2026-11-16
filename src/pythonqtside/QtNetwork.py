# this_file: src/pythonqtside/QtNetwork.py
"""QtNetwork objects routed from FontLab's native PythonQt through Echopy."""
from typing import Any
from ._routing import member, names


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    return member('QtNetwork', name)


def __dir__() -> list[str]:
    return names('QtNetwork')
