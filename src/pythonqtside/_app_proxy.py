# this_file: src/pythonqtside/_app_proxy.py
"""Explicit host application identity exception for the embedded runner."""

from typing import Any


class ApplicationProxy:
    """Explicit identity exception: embedded application lifecycle is handle-local."""

    def __init__(self, handle: Any, native: Any) -> None:
        self._handle = handle
        self.native_application = native

    def __call__(self, *args: Any, **kwargs: Any) -> "ApplicationProxy":
        self._handle._require_open()
        return self

    def __mro_entries__(self, bases: tuple) -> tuple:
        raise NotImplementedError("Embedded application subclasses are unsupported")

    def instance(self) -> "ApplicationProxy":
        self._handle._require_open()
        return self

    def exec(self) -> int:
        self._handle._require_open()
        return 0

    exec_ = exec

    def quit(self) -> None:
        self._handle.close()

    def exit(self, returnCode: int = 0) -> None:
        self._handle.close()

    closeAllWindows = quit

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"Embedded application member {name!r} is not faithfully scoped; "
            "global application settings and operations are unsupported"
        )
