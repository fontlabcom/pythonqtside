# this_file: tests/test_connections.py
"""Native-slot forwarding, crash-safe matching and signal overload selection.

Doubles model the PythonQt behaviour measured in pqs-g04/fixtures; they do not prove it."""

import sys
from functools import partial
from types import ModuleType

import pytest
from test_app_runner import QObject, QWidget, Signal, native, script  # noqa: F401

from pythonqtside import run_app
from pythonqtside._app import _ACTIVE_HANDLES
from pythonqtside._app_cleanup import (
    connection_call,
    disconnect_connections,
    overload_signature,
    same,
    slot_forwarder,
)


class builtin_qt_slot:  # the measured PythonQt type name
    """A native slot: compares only with its own type, like PythonQt's meth_compare."""

    def __init__(self, owner, name, arity):
        self.owner, self.name, self.arity, self.calls = owner, name, arity, []

    def __eq__(self, other):
        assert type(other) is builtin_qt_slot, "a native slot met another type"
        return self.owner is other.owner and self.name == other.name

    __hash__ = None

    def __call__(self, *args):
        if len(args) != self.arity:
            raise ValueError(
                f"Called {self.name}() with wrong number of arguments: {args}"
            )
        self.calls.append(args)


class OverloadSignal(Signal):
    """PythonQt signal wrapper exposing parameterTypes() for every overload.

    Measured (pqs-g04/review2/probe_signal_owner.json): gc.get_referents(signal)
    is [owner] and the repr's address is id(owner); the slot models that."""

    __slots__ = ("owner",)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        backend = instance.__dict__.setdefault(self.name, OverloadSignal())
        wrapper = OverloadSignal()
        wrapper.callbacks = backend.callbacks
        wrapper.label = (self.name.removeprefix("_signal_"), type(instance).__name__)
        wrapper.owner = instance
        return wrapper

    def __repr__(self):
        name, kind = getattr(self, "label", ("?", "?"))
        address = id(getattr(self, "owner", self))
        return f"<qt signal {name} of {kind} instance at {address:#x}>"

    def __eq__(self, other):
        return isinstance(other, Signal) and self.callbacks is other.callbacks

    def parameterTypes(self):
        return [("int",), ("int", "QProcess::ExitStatus")]


@pytest.fixture
def overload_signals(monkeypatch):
    """The process double's signals are the measured native Signal type."""
    monkeypatch.setattr(sys.modules["PythonQt"].QtCore, "Signal", OverloadSignal)
    sys.modules["fontlab_echopy.PythonQt.QtCore"].QProcess = Process


def test_slot_forwarder_when_signal_has_more_arguments_then_trailing_dropped():
    slot = builtin_qt_slot(object(), "clear", 0)
    forward = slot_forwarder(slot)
    forward(True)
    forward(False)
    assert slot.calls == [(), ()], "Qt drops the clicked(bool) argument clear() lacks"
    assert forward.__wrapped__ is slot


def test_slot_forwarder_when_slot_raises_other_error_then_it_propagates():
    def slot(*args):
        raise ValueError("inside the slot")

    with pytest.raises(ValueError, match="inside the slot"):
        slot_forwarder(slot)(1)


def test_same_when_slot_meets_bound_method_then_no_native_comparison():
    owner = object()
    slot = builtin_qt_slot(owner, "reject", 0)
    assert not same(slot, partial(print)), "different types never reach __eq__"
    assert same(slot, builtin_qt_slot(owner, "reject", 0))


def test_connection_call_when_native_slot_then_forwarder_tracked_and_disconnect_mapped():
    signal, records = Signal(), []
    slot = builtin_qt_slot(object(), "reject", 0)
    connection_call(signal, "connect", signal.connect, records)(slot)
    (record,) = records
    assert record[1][0].__wrapped__ is slot and signal.callbacks == [record[1][0]]
    signal.emit()
    assert slot.calls == [()]
    again = builtin_qt_slot(slot.owner, "reject", 0)
    assert (
        connection_call(signal, "disconnect", signal.disconnect, records)(again) is None
    )
    assert not records and not signal.callbacks


def test_connection_call_when_unknown_native_slot_disconnected_then_native_not_called():
    signal, records = Signal(), []

    def refuse(*args):
        raise AssertionError("PythonQt would compare the slot with every handler")

    slot = builtin_qt_slot(object(), "reject", 0)
    assert connection_call(signal, "disconnect", refuse, records)(slot) is False


def test_overload_signature_when_callback_needs_more_arguments_then_longer_overload():
    signal = OverloadSignal()
    assert overload_signature(signal, "finished", lambda code, status: None) == (
        "2finished(int,QProcess::ExitStatus)"
    )
    assert overload_signature(signal, "finished", lambda code: None) is None
    assert overload_signature(signal, "finished", lambda *a: None) is None
    assert overload_signature(signal, "finished", lambda c, s, p=1: None) == (
        "2finished(int,QProcess::ExitStatus)"
    ), "defaulted parameters are not required"
    assert overload_signature(Signal(), "finished", lambda a, b: None) is None


class Process(QObject):
    __module__ = "PythonQt.QtCore"
    finished = OverloadSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overloads = []

    def connect(self, signature, callback):
        self.overloads.append(signature)
        self.callback = callback
        return True

    def disconnect(self, signature, callback):
        assert callback is self.callback
        self.overloads.remove(signature)
        return True


def test_run_app_when_callback_takes_code_and_status_then_overload_connected(
    tmp_path, overload_signals
):
    source = """from PySide2.QtCore import QProcess
process = QProcess()
seen = []
process.finished.connect(lambda code, status: seen.append((code, status)))
process.finished.connect(lambda code: seen.append(code))
"""
    handle = run_app(script(tmp_path, source))
    process = handle.namespace["process"]
    assert process.overloads == ["2finished(int,QProcess::ExitStatus)"]
    assert len(process.finished.callbacks) == 1, (
        "the one-argument callback stays default"
    )
    assert len(handle._connections) == 2
    handle.close()
    assert process.overloads == [] and not process.finished.callbacks
    assert not handle.cleanup_errors


def test_run_app_when_overload_connection_disconnected_explicitly_then_undone(
    tmp_path, overload_signals
):
    source = """from PySide2.QtCore import QProcess
process = QProcess()
def done(code, status):
    pass
process.finished.connect(done)
process.finished.disconnect(done)
"""
    handle = run_app(script(tmp_path, source))
    process = handle.namespace["process"]
    assert process.overloads == [] and not handle._connections
    assert hasattr(process, "callback"), "the overload connection was made first"


def test_disconnect_connections_when_record_has_undo_then_undo_called():
    calls = []
    records = [(Signal(), (print,), {}, lambda: calls.append("undo"), None)]
    assert disconnect_connections(records) == () and calls == ["undo"]


def test_run_app_when_killed_process_wait_fails_but_stopped_then_no_cleanup_error(
    tmp_path,
):
    class QProcess(QObject):
        def inherits(self, name):
            return name == "QProcess"

        def state(self):
            return 0 if getattr(self, "killed", False) else 2

        def kill(self):
            self.killed = True

        def waitForFinished(self, timeout):
            return False  # measured: errorOccurred(Crashed) makes the wait false

    sys.modules["fontlab_echopy.PythonQt.QtCore"].QProcess = QProcess
    handle = run_app(
        script(tmp_path, "from PySide2.QtCore import QProcess\nprocess = QProcess()\n")
    )
    process = handle.namespace["process"]
    handle.close()
    assert process.killed and process.deleted == 1 and not handle.cleanup_errors
    assert handle not in _ACTIVE_HANDLES


class QByteArray(QObject):
    __module__ = "PythonQt.QtCore"

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def data(self):
        return self.payload


def test_run_app_when_bytes_of_native_byte_array_then_data_used(tmp_path):
    sys.modules["fontlab_echopy.PythonQt.QtCore"].QByteArray = QByteArray
    source = """from PySide2.QtCore import QByteArray
raw = QByteArray(b"hi")
text = bytes(raw).decode()
copy = bytearray(raw)
plain = bytes(3)
"""
    namespace = run_app(script(tmp_path, source)).namespace
    assert namespace["text"] == "hi" and namespace["copy"] == bytearray(b"hi")
    assert namespace["plain"] == bytes(3), "other arguments reach bytes unchanged"


def test_run_app_when_owned_object_already_destroyed_then_no_cleanup_error(tmp_path):
    source = "from PySide2 import QtWidgets\nwindow = QtWidgets.QWidget()\n"
    handle = run_app(script(tmp_path, source))
    window = handle.namespace["window"]

    def parent():
        raise ValueError("Trying to call 'parent' on a destroyed QWidget object")

    window.parent = parent
    handle.close()
    assert not handle.cleanup_errors and window.deleted == 0


class QUiLoader(QObject):
    __module__ = "PythonQt.QtUiTools"

    def load(self, device):
        return QWidget()


def test_run_app_when_ui_loader_creates_widget_then_handle_owns_it(
    tmp_path, monkeypatch
):
    tools = ModuleType("PythonQt.QtUiTools")
    tools.QUiLoader = QUiLoader
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtUiTools", tools)
    source = (
        "from PySide2.QtUiTools import QUiLoader\nwindow = QUiLoader().load(None)\n"
    )
    handle = run_app(script(tmp_path, source))
    window = handle.namespace["window"]
    assert any(window is o for o in handle._objects), "load() results are owned"
    handle.close()
    assert window.deleted == 1 and window.closed


def test_disconnect_connections_when_owner_destroyed_then_skipped():
    class Dead:
        def parent(self):
            raise ValueError("Trying to call 'parent' on a destroyed QDialog object")

    def refuse(*args):
        raise AssertionError("a destroyed sender must not be disconnected")

    signal = Signal()
    signal.disconnect = refuse
    assert disconnect_connections([(signal, (print,), {}, None, Dead())]) == ()


def test_run_app_when_app_code_runs_after_close_then_clear_runtime_error(tmp_path):
    source = """from PySide2 import QtWidgets
def later(widget):
    return widget.parent()
def uses_global():
    return QtWidgets.QWidget()
window = QtWidgets.QWidget()
"""
    handle = run_app(script(tmp_path, source))
    later, uses_global = handle.namespace["later"], handle.namespace["uses_global"]
    window = handle.namespace["window"]
    handle.close()
    with pytest.raises(RuntimeError, match="handle is closed"):
        later(window)
    with pytest.raises(NameError):
        uses_global()  # close() released the app's globals
