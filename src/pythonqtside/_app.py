# this_file: src/pythonqtside/_app.py
"""Retained unchanged-source applications scoped to FontLab's existing Qt host."""

import gc
import re
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any

from . import _app_flags, _app_keywords, _app_native
from ._app_cleanup import cleanup, connection_call, disconnect_connections
from ._app_imports import ImportContext, freeze
from ._app_proxy import ApplicationProxy

_ACTIVE_HANDLES = set()


def _closed(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("The embedded application handle is closed")


class AppHandle:
    """Own constructor-created Qt objects and retain source/import globals until close."""

    def __init__(
        self,
        path: Path,
        parent: Any,
        application: Any,
        application_classes: tuple[type, ...],
    ) -> None:
        self.closed = False
        self.cleanup_errors = ()
        self._objects = []
        self._connections = []
        self._parent = parent
        self._application_classes = application_classes
        self._application = ApplicationProxy(self, application)
        self._namespace = {"__name__": "__main__", "__package__": ""}
        self._context = ImportContext(self, path.parent)
        self._executing = False
        self._constructing = 0

    @property
    def namespace(self) -> MappingProxyType:
        return (
            MappingProxyType(self._namespace)
            if not self.closed
            else MappingProxyType({})
        )

    @property
    def reports(self) -> MappingProxyType:
        return MappingProxyType(dict(self._context.reports))

    @property
    def identity_report(self) -> MappingProxyType:
        return freeze(
            {
                "routed_classes": dict(self._context.identities),
                "application_proxy": type(self._application),
                "native_application_classes": self._application_classes,
                "limits": (
                    "QObject recognition uses native ancestry plus metaObject/parent/deleteLater capabilities.",
                    "Only constructor results are owned; arbitrary API return values are borrowed.",
                    "Dynamic exec/eval source, importlib imports, namespace packages and application subclasses/settings are unsupported.",
                ),
            }
        )

    def _require_open(self) -> None:
        _app_native.require_host_thread()
        if self.closed:
            raise RuntimeError("The embedded application handle is closed")

    def _own(self, value: Any) -> Any:
        if _app_native.qobject_instance(value) and not any(
            value is obj for obj in self._objects
        ):
            self._objects.append(value)
        return value

    def _prepare(self, callee: Any, keywords: bool = False) -> Any:
        signal_method = _app_native.native_signal_method(callee)
        if signal_method is not None:
            self._require_open()
            receiver, name = signal_method
            owner, signal_name = self._signal_owner(receiver)
            return connection_call(
                receiver, name, callee, self._connections, owner, signal_name
            )
        callee = _app_native.captured_call(callee, keywords)
        if any(callee is kind for kind in (bytes, bytearray, memoryview)):
            return partial(_app_native.byte_call, callee)
        # Ordinary Python callables, including aliased frame builtins, run directly.
        if not _app_native.native_class(callee):
            return callee
        if any(base in self._application_classes for base in callee.__mro__):
            raise NotImplementedError("Embedded application subclasses are unsupported")

        keywords = _app_keywords.native_init(callee)

        def construct(*args: Any, **kwargs: Any) -> Any:
            self._require_open()
            self._constructing += 1
            try:
                if kwargs and keywords:
                    return _app_keywords.construct(
                        callee, args, kwargs, self._connect, self._own
                    )
                if keywords:  # measured QFlags positions (_flags.json)
                    native = _app_keywords.native_base(callee)
                    args = _app_flags.convert(native, "__init__", args)
                return self._own(callee(*args, **kwargs))
            finally:
                self._constructing -= 1

        return construct

    def _connect(
        self, signal: Any, slot: Any, owner: Any = None, name: str | None = None
    ) -> Any:
        """Constructor signal keywords connect through the tracked path."""
        return connection_call(
            signal, "connect", signal.connect, self._connections, owner, name
        )(slot)

    def _signal_owner(self, signal: Any) -> tuple[Any, str | None]:
        """The QObject and signal name behind an aliased or captured signal.

        Measured (pqs-g04/review2/probe_signal_owner.json): a PythonQt signal
        wrapper's only GC referent is its owner, and its repr
        (``<qt signal finished of QProcess instance at 0x...>``) carries the
        signal name and ``id(owner)``. Works for owned and borrowed senders."""
        if not _app_native.native_signal_instance(signal):
            return None, None
        match = re.match(
            r"<qt signal (\w+) of \w+ instance at (0x[0-9a-fA-F]+)", repr(signal)
        )
        if match is None:
            return None, None
        name, address = match.group(1), int(match.group(2), 16)
        for owner in gc.get_referents(signal):
            if id(owner) != address or not _app_native.native_instance(owner):
                continue
            try:
                candidate = getattr(owner, name)
            except Exception:  # noqa: BLE001, S112 - destroyed wrappers raise
                continue
            if _app_native.same_connection_receiver(candidate, signal):
                return owner, name
        return None, None

    def _super_init(self, receiver: super, value: Any) -> Any:
        """``super().__init__(parent=p)`` reaching a native constructor."""
        native = None
        for base in _app_native._super_bases(receiver):
            if base.__module__.startswith("PythonQt"):
                native = base
                break
            if "__init__" in vars(base):
                return value
        if native is None:
            return value
        instance = receiver.__self__

        def initialize(*args: Any, **kwargs: Any) -> Any:
            if not kwargs:
                return value(*_app_flags.convert(native, "__init__", args))
            return _app_keywords.initialize(
                value, instance, native, args, kwargs, self._connect
            )

        return initialize

    def _resolve(
        self,
        receiver: Any,
        name: str,
        keywords: bool = False,
        member: str | None = None,
    ) -> Any:
        self._require_open()
        if member is not None:  # `receiver.name.member(...)`, member is (dis)connect
            signal = getattr(receiver, name)
            if _app_native.native_signal_instance(
                signal
            ) and _app_native.native_instance(receiver):
                method = getattr(signal, member)
                return connection_call(
                    signal, member, method, self._connections, receiver, name
                )
            return self._resolve(signal, member, keywords)
        value = _app_native.resolve(receiver, name, keywords)
        if name == "__init__" and isinstance(receiver, super):
            value = self._super_init(receiver, value)
        instance = receiver.__self__ if isinstance(receiver, super) else receiver
        if (
            self._constructing
            and name == "__init__"
            and _app_native.native_instance(instance)
        ):
            self._own(instance)
        if name == "__init__" and _app_native.native_class(receiver):
            native_init = _app_keywords.native_init(receiver)

            def initialize(instance: Any, *args: Any, **kwargs: Any) -> Any:
                if self._constructing:
                    self._own(instance)
                if kwargs and native_init:
                    return _app_keywords.initialize(
                        lambda *a: value(instance, *a),
                        instance,
                        _app_keywords.native_base(receiver),
                        args,
                        kwargs,
                        self._connect,
                    )
                if native_init:
                    native = _app_keywords.native_base(receiver)
                    args = _app_flags.convert(native, "__init__", args)
                return value(instance, *args, **kwargs)

            return initialize
        if (
            name in {"connect", "disconnect"}
            and (
                _app_native.native_instance(receiver)
                or _app_native.native_signal_instance(receiver)
            )
            and callable(value)
        ):
            owner, signal_name = self._signal_owner(receiver)
            return connection_call(
                receiver, name, value, self._connections, owner, signal_name
            )
        if name == "load" and _app_native.ui_loader(receiver):
            # Qt: the caller owns the widget QUiLoader.load() creates.
            return lambda *args, **kwargs: self._own(value(*args, **kwargs))
        if name == "show" and any(receiver is obj for obj in self._objects):

            def show(*args: Any, **kwargs: Any) -> Any:
                self._parent_windows()
                return value(*args, **kwargs)

            return show
        return value

    def _parent_windows(self) -> None:
        if self._parent is not None:
            for obj in self._objects:
                if _app_native.widget_instance(obj) and obj.parent() is None:
                    obj.setParent(self._parent)

    def close(self) -> None:
        """Disconnect, stop owned work and delete owned graph roots once; retain reports."""
        if self.closed:
            return
        _app_native.require_host_thread()
        self.closed = True
        self.cleanup_errors, retained = cleanup(self._objects, self._connections)
        self._connections.clear()
        self._objects[:] = retained
        if not retained:
            _ACTIVE_HANDLES.discard(self)
        self._context.modules.clear()
        if not self._executing:
            self._clear_namespace()

    def _clear_namespace(self) -> None:
        """Drop the app's globals, keeping its adapter names so code that still
        runs after close (a Python object the host kept) fails clearly."""
        self._namespace.clear()
        for name in (self._context.call_name, self._context.resolve_name):
            self._namespace[name] = _closed

    def _disconnect_callbacks(self) -> tuple[str, ...]:
        """Acceptance probe: disconnect while widgets are live, using close's same phase."""
        self._require_open()
        errors = disconnect_connections(self._connections)
        self._connections.clear()
        return errors


def run_app(path: str | Path, *, parent: Any = None) -> AppHandle:
    """Run one original PySide2 source graph without changing the host's import state."""
    application, classes = _app_native.host_application()
    if parent is not None and not _app_native.widget_instance(parent):
        raise TypeError("run_app parent must be a native QWidget")
    path = Path(path).resolve(strict=True)
    handle = AppHandle(path, parent, application, classes)
    _ACTIVE_HANDLES.add(handle)
    handle._executing = True
    try:
        try:
            handle._context.execute(path, handle._namespace)
        except SystemExit as error:
            origin = error.__traceback__
            while origin.tb_next is not None:
                origin = origin.tb_next
            if (
                error.code is not None and error.code != 0
            ) or origin.tb_frame.f_code.co_filename != str(path):
                raise
        if not handle.closed:
            handle._parent_windows()
    except BaseException as error:
        handle.close()
        if handle.cleanup_errors:
            error.add_note(
                "Embedded app cleanup errors: " + "; ".join(handle.cleanup_errors)
            )
        raise
    finally:
        handle._executing = False
        if handle.closed:
            handle._clear_namespace()
    return handle
