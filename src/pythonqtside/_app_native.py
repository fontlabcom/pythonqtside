# this_file: src/pythonqtside/_app_native.py
"""Measured PythonQt property access and FontLab's existing application."""

import json
import threading
from functools import cache, partial
from importlib import import_module
from pathlib import Path
from types import BuiltinMethodType
from typing import Any

from ._app_conversions import conversion_call
from ._app_dialogs import file_dialog_call
from ._app_flags import flags_call
from ._app_keywords import SIGNAL_METHODS, keyword_method


def native_instance(value: Any) -> bool:
    """Recognize PythonQt's actual wrapper ancestry, including user subclasses."""
    return not isinstance(value, type) and any(
        base.__module__.startswith("PythonQt") for base in type(value).__mro__
    )


def native_class(value: Any) -> bool:
    """Preserve actual class objects; detect native and Python-derived constructors."""
    return isinstance(value, type) and any(
        base.__module__.startswith("PythonQt") for base in value.__mro__
    )


def native_signal_instance(value: Any) -> bool:
    """Measured QtCore.Signal has Signal/object ancestry; identify its actual type."""
    try:
        signal_type = import_module("PythonQt").QtCore.Signal
    except (ModuleNotFoundError, AttributeError):
        return False
    return type(value) is signal_type and all(
        callable(getattr(value, name, None)) for name in ("connect", "disconnect")
    )


def same_connection_receiver(left: Any, right: Any) -> bool:
    """Native Signal wrappers compare backend identity; QObject/Python objects use is."""
    if left is right:
        return True
    if native_signal_instance(left) and native_signal_instance(right):
        return bool(left == right)
    return False


def native_signal_method(value: Any) -> tuple[Any, str] | None:
    """Recognize measured C-bound Signal methods without probing user callables."""
    if type(value) is not BuiltinMethodType:
        return None
    name = value.__name__
    if name in {"connect", "disconnect"} and native_signal_instance(value.__self__):
        return value.__self__, name
    return None


def qobject_instance(value: Any) -> bool:
    """PythonQt QWidget is not isinstance(private.QObject); use measured capabilities."""
    return native_instance(value) and all(
        callable(getattr(value, name, None))
        for name in ("metaObject", "parent", "setParent", "deleteLater")
    )


def widget_instance(value: Any) -> bool:
    """Use Qt inheritance metadata, never the unrelated private QObject wrapper."""
    inherits = getattr(value, "inherits", None)
    return qobject_instance(value) and callable(inherits) and bool(inherits("QWidget"))


def destroyed(value: Any) -> bool:
    """PythonQt guards wrappers of deleted QObjects: a call raises
    ValueError("Trying to call 'parent' on a destroyed QSpinBox object") (measured)."""
    try:
        value.parent()
    except ValueError as error:
        return "on a destroyed" in str(error)
    return False


def byte_call(kind: type, *args: Any, **kwargs: Any) -> Any:
    """``bytes(qbytearray)`` raises in PythonQt; PySide2 reads the buffer. Native
    QByteArray arguments become their ``data()`` bytes (measured)."""
    if args and native_instance(args[0]) and type(args[0]).__name__ == "QByteArray":
        args = (args[0].data(), *args[1:])
    return kind(*args, **kwargs)


def ui_loader(value: Any) -> bool:
    """A native QUiLoader (or Python subclass) instance."""
    return native_instance(value) and any(
        base.__name__ == "QUiLoader" and base.__module__.startswith("PythonQt")
        for base in type(value).__mro__
    )


def close_owned_widget(value: Any) -> None:
    if widget_instance(value):
        value.close()


def stop_owned(value: Any) -> None:
    """Stop the supported timer/process/thread primitives before scheduled deletion."""
    inherits = getattr(value, "inherits", None)
    if not callable(inherits):
        return
    for kind, operation in (
        ("QTimer", "stop"),
        ("QProcess", "kill"),
        ("QThread", "quit"),
    ):
        if inherits(kind):
            if kind == "QProcess" and resolve(value, "state")() == 0:
                continue
            if kind == "QThread" and not resolve(value, "isRunning")():
                continue
            method = getattr(value, operation, None)
            if callable(method):
                method()
            if kind in {"QProcess", "QThread"}:
                wait = getattr(
                    value, "waitForFinished" if kind == "QProcess" else "wait", None
                )
                if not callable(wait):
                    raise RuntimeError(
                        f"Owned {kind} cannot confirm termination; deletion withheld"
                    )
                # waitForFinished is false once errorOccurred(Crashed) fires after
                # kill(), although the process stopped (measured): check the state.
                stopped = wait(1000) or (
                    kind == "QProcess" and resolve(value, "state")() == 0
                )
                if not stopped:
                    raise RuntimeError(
                        f"Owned {kind} did not stop within 1000 ms; deletion withheld"
                    )


def require_host_thread() -> None:
    """The tested FontLab runtime has no QtCore.QThread.currentThread API."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("run_app must execute on FontLab's main Python thread")


def host_application() -> tuple[Any, tuple[type, ...]]:
    """Require the measured host GUI thread and reuse its Qt application."""
    require_host_thread()
    try:
        qt = import_module("PythonQt")
    except ModuleNotFoundError as error:
        raise RuntimeError("run_app requires FontLab's native PythonQt") from error
    app = qt.QtGui.QApplication.instance()
    if app is None:
        raise RuntimeError("FontLab's existing QApplication is unavailable")
    classes = tuple(
        getattr(module, name)
        for module, name in [
            (qt.QtGui, "QApplication"),
            (qt.QtGui, "QGuiApplication"),
            (qt.QtCore, "QCoreApplication"),
        ]
        if hasattr(module, name)
    )
    return app, classes


def _getter(instance: Any, name: str) -> Any:
    """Only adapt properties confirmed by the instance's actual Qt metaobject."""
    if not native_instance(instance):
        return None
    meta = getattr(instance, "metaObject", None)
    if not callable(meta) or meta().indexOfProperty(name) < 0:
        return None
    return lambda: instance.property(name)


def _super_bases(receiver: super) -> tuple[type, ...]:
    """Search the bound MRO after super's anchor, including class-bound super."""
    if receiver.__self_class__ is None:
        return ()
    mro = receiver.__self_class__.__mro__
    return mro[mro.index(receiver.__thisclass__) + 1 :]


def _super_fallback(receiver: super, name: str) -> Any:
    """Prepare explicit native base dispatch without adding an invocation frame."""
    for base in _super_bases(receiver):
        if not base.__module__.startswith("PythonQt"):
            continue
        method = getattr(base, name, None)
        if callable(method):
            return partial(method, receiver.__self__)
    return _getter(receiver.__self__, name)


@cache
def _out_parameter_tables() -> tuple[dict, dict, frozenset[str]]:
    """Generated _out_parameters.json: predicate and BoolResult tables, method names."""
    path = Path(__file__).with_name("_out_parameters.json")
    table = json.loads(path.read_text(encoding="utf-8"))
    names = {
        m
        for kind in ("predicate", "bool_result")
        for c in table[kind].values()
        for m in c
    }
    return table["predicate"], table["bool_result"], frozenset(names)


def _native_class(key: str) -> type | None:
    module, _, name = key.partition(".")
    try:
        return getattr(getattr(import_module("PythonQt"), module), name)
    except (ModuleNotFoundError, AttributeError):
        return None


def _python_defined(receiver: Any, name: str) -> bool:
    """Instance or non-PythonQt class definitions keep their own Python behavior."""
    if not isinstance(receiver, type) and name in getattr(receiver, "__dict__", {}):
        return True
    mro = receiver.__mro__ if isinstance(receiver, type) else type(receiver).__mro__
    return any(
        name in vars(base) for base in mro if not base.__module__.startswith("PythonQt")
    )


def _measured(table: dict, receiver: Any, name: str) -> Any:
    """The table entry whose native class matches an instance (or a class, if static)."""
    for key, methods in table.items():
        entry = methods.get(name)
        cls = _native_class(key) if entry is not None else None
        if cls is None:
            continue
        if isinstance(receiver, type):
            if (
                isinstance(entry, dict)
                and entry["static"]
                and issubclass(receiver, cls)
            ):
                return entry
        elif isinstance(receiver, cls):
            return entry
    return None


def _out_parameter_call(
    receiver: Any, name: str, method: Any, native_method: bool = False
) -> Any:
    """Measured PySide2 (value, ok) results; returns None when no adapter applies."""
    predicates, bool_results, names = _out_parameter_tables()
    if name not in names or (not native_method and _python_defined(receiver, name)):
        return None
    if not (native_instance(receiver) or native_class(receiver)):
        return None
    if not isinstance(receiver, type):
        predicate = _measured(predicates, receiver, name)
        if predicate is not None:
            return partial(_with_ok, receiver, method, predicate)
    entry = _measured(bool_results, receiver, name)
    return None if entry is None else partial(_with_bool_result, method, entry)


def _with_ok(
    receiver: Any, method: Any, predicate: str, *args: Any, **kwargs: Any
) -> Any:
    """PySide2 zero-argument form returns (native value, native predicate result)."""
    if args or kwargs:  # PythonQt-style out-parameter use stays native.
        return method(*args, **kwargs)
    return method(), getattr(receiver, predicate)()


def _native_default(value: Any) -> Any:
    """Qt declaration default; {"native": "QtGui.QLineEdit.Normal"} resolves lazily."""
    if not isinstance(value, dict):
        return value
    result = import_module("PythonQt")
    for part in value["native"].split("."):
        result = getattr(result, part)
    return result


def _with_bool_result(method: Any, entry: dict, *args: Any, **kwargs: Any) -> Any:
    """PySide2 positional call -> native call with BoolResult -> (value, bool(ok))."""
    bool_result = import_module("PythonQt").BoolResult
    index, params, defaults = entry["out_index"], entry["parameters"], entry["defaults"]
    native_style = kwargs or len(args) > entry["max_arguments"]
    missing = [p for p in params[len(args) :] if p not in defaults]
    if native_style or missing or any(isinstance(a, bool_result) for a in args):
        return method(*args, **kwargs)
    filled = [
        *args[:index],
        *(_native_default(defaults[p]) for p in params[len(args) :]),
    ]
    ok = bool_result()
    value = method(*filled, ok, *args[index:])
    return value, bool(ok)


def _conversion_call(
    receiver: Any, name: str, method: Any, native_method: bool = False
) -> Any:
    """Measured implicit enum -> value-class wrapping on native, unoverridden methods."""
    if not (native_instance(receiver) or native_class(receiver)):
        return None
    if not native_method and _python_defined(receiver, name):
        return None
    return conversion_call(receiver, name, method)


def captured_call(method: Any, keywords: bool = False) -> Any:
    """Adapt a bound native slot stored earlier, with or without keywords
    (``resize = label.resize; resize(1, 2)``, or ``base = super().resize``).

    Only the slot's measured ``__self__``/``__name__`` select the keyword table
    entry; the captured callable itself is called, so a captured base dispatch
    never re-resolves to a Python override."""
    if type(method).__name__ != "builtin_qt_slot":
        return method
    receiver = getattr(method, "__self__", None)
    name = getattr(method, "__name__", None)
    if receiver is None or not name or name in SIGNAL_METHODS:
        return method
    return _adapt(receiver, name, method, keywords, native_method=True)


def _keyword_call(
    receiver: Any, name: str, method: Any, native_method: bool = False
) -> Any:
    """Measured keyword-to-positional mapping on native, unoverridden methods."""
    if name in SIGNAL_METHODS or name == "__init__" or native_signal_instance(method):
        return method
    if not (native_instance(receiver) or native_class(receiver)):
        return method
    if not native_method and _python_defined(receiver, name):
        return method
    return keyword_method(receiver, name, method)


def _adapt(
    receiver: Any, name: str, method: Any, keywords: bool, native_method: bool = False
) -> Any:
    """The adapter chain for a native method: out-parameter or enum conversion,
    then QFlags, then (for keyword call sites) keyword mapping outermost.

    ``native_method`` marks a captured bound native slot: it is native by
    construction, so a Python override of the same name on the receiver (a
    cooperative ``base = super().resize``) must not switch the adapters off."""
    adapted = _out_parameter_call(receiver, name, method, native_method)
    if adapted is None and (native_method or not _python_defined(receiver, name)):
        adapted = file_dialog_call(receiver, name, method)
    if adapted is None:
        adapted = _conversion_call(receiver, name, method, native_method)
    adapted = method if adapted is None else adapted
    if (native_method or not _python_defined(receiver, name)) and (
        native_instance(receiver) or native_class(receiver)
    ):
        adapted = flags_call(receiver, name, adapted)
    if keywords:
        adapted = _keyword_call(receiver, name, adapted, native_method)
    return adapted


def resolve(receiver: Any, name: str, keywords: bool = False) -> Any:
    """Retain Python behavior; adapt native Qt property getters and measured out-params.

    ``keywords`` marks a call site that passes keyword arguments: native methods then
    map PySide2 keyword names to positions before the other adapters run."""
    if isinstance(receiver, super):
        instance = receiver.__self__
        try:
            value = getattr(receiver, name)
        except AttributeError:
            fallback = _super_fallback(receiver, name)
            if fallback is not None:
                native = isinstance(fallback, partial) and name not in SIGNAL_METHODS
                return (
                    _adapt(instance, name, fallback, keywords, native_method=True)
                    if native
                    else fallback
                )
            raise
        owner = next(
            (base for base in _super_bases(receiver) if name in vars(base)), None
        )
        if callable(value):
            native = owner is None or owner.__module__.startswith("PythonQt")
            if native and name not in SIGNAL_METHODS:
                return _adapt(instance, name, value, keywords, native_method=True)
            return value
        if owner is not None and not owner.__module__.startswith("PythonQt"):
            return value
        getter = _getter(instance, name)
        return getter if getter is not None else value
    value = getattr(receiver, name)
    if callable(value):
        return _adapt(receiver, name, value, keywords)
    getter = _getter(receiver, name)
    return getter if getter is not None else value
