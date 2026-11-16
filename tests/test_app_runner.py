# this_file: tests/test_app_runner.py
"""Algorithm fixtures are not evidence of FontLab binding compatibility."""

import hashlib
import runpy
import sys
import threading
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar

import pytest

from pythonqtside import run_app
from pythonqtside._app import _ACTIVE_HANDLES
from pythonqtside._app_native import host_application as measured_host_application


class QObject:
    __module__ = "PythonQt.private"
    objects: ClassVar[list] = []

    def __init__(self, parent=None):
        self.owner = parent
        self.deleted = 0
        self.objects.append(self)

    def parent(self):
        return self.owner

    def setParent(self, parent):
        self.owner = parent

    def metaObject(self):
        return self

    def indexOfProperty(self, name):
        return -1

    def inherits(self, name):
        return name == "QWidget" and isinstance(self, QWidget)

    def deleteLater(self):
        self.deleted += 1


class QWidget(QObject):
    def close(self):
        self.closed = True

    def show(self):
        self.shown = True

    def setWindowTitle(self, title):
        self.title = title

    def resize(self, width, height):
        self.width = width

    def isVisible(self):
        return self.shown

    def indexOfProperty(self, name):
        return 1 if name in {"width", "text"} else -1

    def property(self, name):
        return getattr(self, name)


class QTimer(QObject):
    def inherits(self, name):
        return name == "QTimer"

    def stop(self):
        self.stopped = True


class Signal:
    # Receipt pythonqtside-native-signal-wrapper.json: Signal/object ancestry,
    # module QtCore, and exact identity with PythonQt.QtCore.Signal.
    __module__ = "QtCore"

    def __init__(self, *types):
        self.callbacks = []

    def __set_name__(self, owner, name):
        self.name = "_signal_" + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        backend = instance.__dict__.setdefault(self.name, Signal())
        wrapper = Signal()
        wrapper.callbacks = backend.callbacks
        return wrapper

    def __eq__(self, other):
        # The native receipt measures distinct wrappers equal for one backend.
        return type(other) is Signal and self.callbacks is other.callbacks

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self, *args):
        for callback in self.callbacks[:]:
            callback(*args)


class QApplication:
    __module__ = "PythonQt.QtGui"

    @staticmethod
    def instance():
        return HOST


HOST = QWidget()


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    qt.QtGui.QApplication = QApplication
    qt.QtGui.QWidget = QWidget
    qt.QtCore = ModuleType("PythonQt.QtCore")
    qt.QtCore.QCoreApplication = QApplication
    qt.QtCore.QTimer = QTimer
    qt.QtCore.Signal = Signal
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtGui", qt.QtGui)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtCore", qt.QtCore)
    monkeypatch.setattr(
        _app_native, "host_application", lambda: (HOST, (QApplication,))
    )
    QObject.objects.clear()
    yield
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


def script(tmp_path, source, name="app.py"):
    path = tmp_path / name
    path.write_text(source)
    return path


class ProtectedNativeMeta(type):
    """Expose handlers through class lookup only, as measured in PythonQt."""

    def __getattr__(cls, name: str) -> Any:
        for base in cls.__mro__:
            handlers = vars(base).get("_protected_handlers", {})
            if name in handlers:
                return handlers[name]
        raise AttributeError(name)


@pytest.fixture
def protected_widget(monkeypatch: pytest.MonkeyPatch) -> type:
    def handler(instance: QWidget, event: Any, *args: Any, **kwargs: Any) -> tuple:
        caller = sys._getframe(1)
        location = (
            caller.f_code.co_filename,
            caller.f_lineno,
            caller.f_locals.get("own"),
        )
        return instance, event, args, kwargs, location

    class QPlainTextEdit(QWidget, metaclass=ProtectedNativeMeta):
        __module__ = "PythonQt.QtGui"
        _protected_handlers: ClassVar[dict] = dict.fromkeys(
            ("paintEvent", "mousePressEvent", "arbitraryVirtual"), handler
        )

    qt = sys.modules["fontlab_echopy.PythonQt.QtGui"]
    monkeypatch.setattr(qt, "QPlainTextEdit", QPlainTextEdit, raising=False)
    return QPlainTextEdit


@pytest.mark.parametrize("name", ["paintEvent", "mousePressEvent", "arbitraryVirtual"])
@pytest.mark.parametrize("base_call", ["super()", "super(Editor, self)"])
def test_run_app_when_protected_super_lookup_fails_then_call_and_frame_are_preserved(
    tmp_path: Path, protected_widget: type, name: str, base_call: str
) -> None:
    path = script(
        tmp_path,
        f"""from PySide2.QtWidgets import QPlainTextEdit
class Editor(QPlainTextEdit):
    def forward(self, event):
        own = 'original frame'
        return {base_call}.{name}(event, *[locals()['own']], eval('own'))
window = Editor()
""",
    )
    original = path.read_bytes()
    handle = run_app(path)
    window = handle.namespace["window"]
    event = object()
    with pytest.raises(AttributeError):
        getattr(super(type(window), window), name)
    assert getattr(protected_widget, name)(window, event)[0:2] == (window, event)
    assert window.forward(event) == (
        window,
        event,
        ("original frame", "original frame"),
        {},
        (str(path), 5, "original frame"),
    ), "the prepared native handler must run directly from the unchanged method"
    # Keyword call sites go through the keyword adapter (one wrapper frame): native
    # handlers reject keywords, so this frame contract covers keyword-less calls.
    report = handle.reports[str(path)]
    assert report["super_call_sites"] == 1
    assert report["super_locations"] == ({"line": 5, "column": 15},)
    assert report["original_bytes"] == path.read_bytes() == original
    assert report["source_sha256"] == hashlib.sha256(original).hexdigest()
    with pytest.raises(TypeError):
        report["super_locations"][0]["line"] = 99
    handle.close()
    assert handle.reports[str(path)] == report, "provenance must survive close"


def test_run_app_when_python_base_provides_handler_then_ordinary_super_wins(
    tmp_path: Path, protected_widget: type
) -> None:
    handle = run_app(
        script(
            tmp_path,
            """from PySide2.QtWidgets import QPlainTextEdit
class Mixin:
    def paintEvent(self, event): return 'python', self, event
class Editor(Mixin, QPlainTextEdit):
    def paintEvent(self, event): return super().paintEvent(event)
window = Editor()
""",
        )
    )
    window = handle.namespace["window"]
    event = object()
    assert window.paintEvent(event) == ("python", window, event), (
        "a native fallback must never shadow an ordinary Python base handler"
    )


def test_run_app_when_inherited_python_handler_cooperates_then_native_base_runs_once(
    tmp_path: Path, protected_widget: type
) -> None:
    handle = run_app(
        script(
            tmp_path,
            """from PySide2.QtWidgets import QPlainTextEdit
class Mixin:
    def paintEvent(self, event): return 'mixin', super().paintEvent(event)
class Editor(Mixin, QPlainTextEdit):
    def paintEvent(self, event): return 'editor', super().paintEvent(event)
class Child(Editor): pass
window = Child()
""",
        )
    )
    window = handle.namespace["window"]
    event = object()
    result = window.paintEvent(event)
    assert result[:1] == ("editor",) and result[1][:1] == ("mixin",)
    assert result[1][1][0:2] == (window, event), (
        "cooperative MRO must reach native base"
    )


@pytest.mark.parametrize(
    "base_call, expected", [("super()", "first"), ("super(First, self)", "second")]
)
def test_run_app_when_multiple_bases_have_class_only_handlers_then_native_mro_is_used(
    tmp_path: Path, protected_widget: type, base_call: str, expected: str
) -> None:
    class PythonMixin(metaclass=ProtectedNativeMeta):
        _protected_handlers: ClassVar[dict] = {
            "paintEvent": lambda self, event: "python fallback"
        }

    class Empty(QWidget, metaclass=ProtectedNativeMeta):
        __module__ = "PythonQt.QtGui"

    class First(protected_widget):
        __module__ = "PythonQt.QtGui"
        _protected_handlers: ClassVar[dict] = {
            "paintEvent": lambda self, event: "first"
        }

    class Second(protected_widget):
        __module__ = "PythonQt.QtGui"
        _protected_handlers: ClassVar[dict] = {
            "paintEvent": lambda self, event: "second"
        }

    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.PythonMixin, qt.Empty, qt.First, qt.Second = PythonMixin, Empty, First, Second
    handle = run_app(
        script(
            tmp_path,
            f"""from PySide2.QtCore import PythonMixin, Empty, First, Second
class Editor(PythonMixin, Empty, First, Second):
    def forward(self, event): return {base_call}.paintEvent(event)
window = Editor()
""",
        )
    )
    assert handle.namespace["window"].forward(object()) == expected, (
        "fallback must skip Python classes and missing native members, after the super anchor"
    )


@pytest.mark.parametrize("error_type", [AttributeError, ValueError])
@pytest.mark.parametrize("python_override", [False, True])
def test_run_app_when_super_handler_raises_then_original_error_and_call_line_survive(
    tmp_path: Path,
    protected_widget: type,
    error_type: type[Exception],
    python_override: bool,
) -> None:
    error = error_type("inside handler")
    calls = []

    def fail(instance: QWidget, event: Any) -> None:
        calls.append((instance, event))
        raise error

    protected_widget._protected_handlers["paintEvent"] = fail
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.Mixin = type("Mixin", (), {"paintEvent": fail} if python_override else {})
    path = script(
        tmp_path,
        """from PySide2.QtWidgets import QPlainTextEdit
from PySide2.QtCore import Mixin
class Editor(Mixin, QPlainTextEdit):
    def forward(self, event):
        return super().paintEvent(event)
window = Editor()
""",
    )
    window = run_app(path).namespace["window"]
    event = object()
    with pytest.raises(error_type) as caught:
        window.forward(event)
    assert caught.value is error and calls == [(window, event)], (
        "exceptions inside the selected handler must propagate without retry"
    )
    frames = traceback.extract_tb(caught.value.__traceback__)
    assert (frames[-2].filename, frames[-2].lineno) == (str(path), 5), (
        "native invocation must have the original call site as its immediate caller"
    )


@pytest.mark.parametrize("native_base", ["", ", QPlainTextEdit"])
def test_run_app_when_no_native_base_provides_name_then_original_attribute_error_survives(
    tmp_path: Path, protected_widget: type, native_base: str
) -> None:
    error = AttributeError("original super lookup")

    class PythonDescriptor:
        def __get__(self, instance: Any, owner: type) -> Any:
            if instance is None:
                return lambda instance: "not a native fallback"
            raise error

    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.descriptor = PythonDescriptor()
    handle = run_app(
        script(
            tmp_path,
            f"""from PySide2.QtWidgets import QPlainTextEdit
from PySide2 import QtCore
class PythonBase:
    missing = QtCore.descriptor
class Editor(PythonBase{native_base}):
    def forward(self): return super().missing()
window = Editor()
""",
        )
    )
    with pytest.raises(AttributeError) as caught:
        handle.namespace["window"].forward()
    assert caught.value is error, (
        "no native provider must re-raise the original lookup error"
    )


def test_run_app_when_import_forms_and_successful_exit_then_host_and_classes_are_retained(
    tmp_path,
):
    path = script(
        tmp_path,
        """from PySide2 import QtCore, QtWidgets
from PySide2.QtWidgets import QWidget
import PySide2.QtWidgets as Widgets
import sys
app = QtWidgets.QApplication(sys.argv)
window = QWidget()
same = Widgets.QWidget is QWidget
instance = QtCore.QCoreApplication.instance()
sys.exit(app.exec_())
""",
    )
    before = path.read_bytes()
    globals_before = (sys.path[:], sys.argv[:], Path.cwd(), sys.modules.get("PySide2"))
    handle = run_app(path)
    assert handle.namespace["same"] and handle.namespace["QWidget"] is QWidget
    assert handle.namespace["app"].native_application is HOST
    assert handle.namespace["instance"] is handle.namespace["app"]
    assert globals_before == (
        sys.path[:],
        sys.argv[:],
        Path.cwd(),
        sys.modules.get("PySide2"),
    )
    report = handle.reports[str(path)]
    assert report["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["original_bytes"] == before == path.read_bytes()
    with pytest.raises(TypeError):
        report["locations"][0]["line"] = 99
    handle.close()
    assert handle.reports[str(path)] == report, "source identity must survive close"


def test_run_app_when_delayed_relative_import_then_private_context_lives_until_close(
    tmp_path,
):
    (tmp_path / "helpers").mkdir()
    script(tmp_path / "helpers", "from .child import value\n", "__init__.py")
    script(
        tmp_path / "helpers",
        "from PySide2.QtWidgets import QWidget\nvalue = QWidget\n",
        "child.py",
    )
    path = script(
        tmp_path,
        """from PySide2.QtWidgets import QWidget
window = QWidget()
def later():
    from helpers import value
    return value
""",
    )
    handle = run_app(path)
    later = handle.namespace["later"]
    assert later() is QWidget
    assert "helpers" not in sys.modules and "helpers.child" not in sys.modules
    assert len(handle.reports) == 3
    handle.close()
    with pytest.raises(RuntimeError, match="closed"):
        later()


@pytest.mark.parametrize(
    "failure", ["raise ValueError('helper failure')", "raise SystemExit(3)"]
)
def test_run_app_when_sibling_startup_fails_then_owned_objects_are_cleaned(
    tmp_path, failure
):
    script(
        tmp_path,
        "from PySide2.QtWidgets import QWidget\nchild = QWidget()\n" + failure,
        "broken.py",
    )
    path = script(
        tmp_path,
        "from PySide2.QtWidgets import QWidget\nwindow = QWidget()\nimport broken\n",
    )
    with pytest.raises((ValueError, SystemExit)):
        run_app(path)
    assert len(QObject.objects) == 2 and all(
        obj.deleted == 1 for obj in QObject.objects
    )
    assert not _ACTIVE_HANDLES


def test_run_app_when_root_window_has_children_then_parenting_and_cleanup_are_scoped(
    tmp_path,
):
    path = script(
        tmp_path,
        """from PySide2 import QtCore, QtWidgets
window = QtWidgets.QWidget()
child = QtWidgets.QWidget(window)
layout = QtCore.QTimer()
signal = QtCore.Signal()
signal.connect(lambda: None)
app = QtWidgets.QApplication([])
""",
    )
    host_parent = QWidget()
    handle = run_app(path, parent=host_parent)
    window, child, timer = (
        handle.namespace[name] for name in ("window", "child", "layout")
    )
    signal = handle.namespace["signal"]
    assert window.parent() is host_parent and child.parent() is window
    assert timer.parent() is None and signal.callbacks
    handle.namespace["app"].closeAllWindows()
    assert handle.closed and window.deleted == timer.deleted == 1 and child.deleted == 0
    assert timer.stopped and not signal.callbacks and host_parent.deleted == 0
    handle.close()
    assert window.deleted == 1 and not handle.namespace


def test_run_app_when_no_parent_and_unretained_result_then_active_retention_keeps_ui(
    tmp_path,
):
    path = script(
        tmp_path, "from PySide2.QtWidgets import QWidget\nwindow = QWidget()\n"
    )
    run_app(path)
    handle = next(iter(_ACTIVE_HANDLES))
    assert handle.namespace["window"].parent() is None


@pytest.mark.parametrize(
    "action", ["app.setStyle('Fusion')", "class App(QtWidgets.QApplication): pass"]
)
def test_run_app_when_global_application_mutation_or_subclass_then_rejects(
    tmp_path, action
):
    path = script(
        tmp_path,
        "from PySide2 import QtWidgets\napp = QtWidgets.QApplication([])\n" + action,
    )
    with pytest.raises(NotImplementedError, match="application"):
        run_app(path)


def test_run_app_when_arbitrary_function_returns_host_object_then_it_is_not_owned(
    tmp_path,
):
    path = script(
        tmp_path, "from PySide2 import QtCore\nborrowed = QtCore.borrowed()\n"
    )
    sys.modules["fontlab_echopy.PythonQt.QtCore"].borrowed = lambda: HOST
    handle = run_app(path)
    handle.close()
    assert HOST.deleted == 0, "native API return values belong to the host"


@pytest.mark.parametrize("code", ["None", "0"])
def test_run_app_when_successful_top_level_exit_then_returns_live_handle(
    tmp_path, code
):
    path = script(
        tmp_path,
        f"from PySide2.QtWidgets import QWidget\nwindow = QWidget()\nraise SystemExit({code})\n",
    )
    handle = run_app(path)
    assert not handle.closed and handle.namespace["window"].deleted == 0


def test_run_app_when_successful_exit_originates_in_helper_then_it_still_propagates(
    tmp_path,
):
    script(tmp_path, "raise SystemExit(0)\n", "helper_exit.py")
    with pytest.raises(SystemExit) as caught:
        run_app(script(tmp_path, "import helper_exit\n"))
    assert caught.value.code == 0, "only the entry script's successful exit is handled"


def test_run_app_when_native_subclass_constructor_raises_then_partial_instance_is_cleaned(
    tmp_path,
):
    path = script(
        tmp_path,
        """from PySide2.QtWidgets import QWidget
class Broken(QWidget):
    def __init__(self):
        super().__init__()
        raise ValueError('construction failure')
window = Broken()
""",
    )
    with pytest.raises(ValueError, match="construction failure"):
        run_app(path)
    assert len(QObject.objects) == 1 and QObject.objects[0].deleted == 1


def test_run_app_when_signal_manually_disconnects_then_close_has_no_stale_connection(
    tmp_path,
):
    path = script(
        tmp_path,
        """from PySide2 import QtCore
signal = QtCore.Signal()
def callback(): pass
signal.connect(callback)
signal.disconnect(callback)
""",
    )
    handle = run_app(path)
    assert not handle._connections, (
        "manual disconnect must remove the recorded native signal"
    )
    handle.close()
    assert not handle.cleanup_errors, (
        "successful manual disconnection must remove its cleanup record"
    )


def test_run_app_when_source_encoding_is_latin1_then_original_bytes_and_hash_survive(
    tmp_path,
):
    path = tmp_path / "latin.py"
    original = b"# coding: latin-1\nvalue = 'caf\xe9'\n"
    path.write_bytes(original)
    handle = run_app(path)
    assert handle.namespace["value"] == "caf\u00e9"
    assert (
        handle.reports[str(path)]["source_sha256"]
        == hashlib.sha256(original).hexdigest()
    )
    assert handle.reports[str(path)]["original_bytes"] == path.read_bytes() == original


def test_run_app_when_callback_constructs_after_close_then_rejects(tmp_path):
    handle = run_app(
        script(
            tmp_path,
            "from PySide2.QtWidgets import QWidget\ndef later(): return QWidget()\n",
        )
    )
    later = handle.namespace["later"]
    handle.close()
    with pytest.raises((RuntimeError, NameError)):
        later()


def test_run_app_when_dialog_exec_is_called_then_native_modal_return_is_preserved(
    tmp_path,
):
    class QDialog(QWidget):
        def exec_(self):
            return 23

    sys.modules["fontlab_echopy.PythonQt.QtGui"].QDialog = QDialog
    handle = run_app(
        script(
            tmp_path,
            "from PySide2.QtWidgets import QDialog\ndialog = QDialog()\nresult = dialog.exec_()\n",
        )
    )
    assert handle.namespace["result"] == 23, (
        "dialog modality must not be changed into a no-op application loop"
    )


def test_run_app_when_cleanup_fails_then_original_exception_survives(tmp_path):
    class BrokenDelete(QWidget):
        def deleteLater(self):
            raise RuntimeError("fixture deletion failed")

    sys.modules["fontlab_echopy.PythonQt.QtGui"].QWidget = BrokenDelete
    path = script(
        tmp_path,
        "from PySide2.QtWidgets import QWidget\nwindow = QWidget()\nraise ValueError('original startup error')\n",
    )
    with pytest.raises(ValueError, match="original startup error") as caught:
        run_app(path)
    assert "fixture deletion failed" in caught.value.__notes__[0]


def test_run_app_when_owned_process_is_idle_then_close_does_not_wait_for_nonexistent_work(
    tmp_path,
):
    class QProcess(QObject):
        def inherits(self, name):
            return name == "QProcess"

        def state(self):
            return 0

        def kill(self):
            raise AssertionError("idle process must not be killed")

    sys.modules["fontlab_echopy.PythonQt.QtCore"].QProcess = QProcess
    handle = run_app(
        script(tmp_path, "from PySide2.QtCore import QProcess\nprocess = QProcess()\n")
    )
    process = handle.namespace["process"]
    handle.close()
    assert process.deleted == 1 and not handle.cleanup_errors


def test_run_app_when_owned_process_will_not_stop_then_ancestor_deletion_is_withheld(
    tmp_path,
):
    class QProcess(QObject):
        def inherits(self, name):
            return name == "QProcess"

        def state(self):
            return 2

        def kill(self):
            self.killed = True

        def waitForFinished(self, timeout):
            assert timeout == 1000
            return False

    sys.modules["fontlab_echopy.PythonQt.QtCore"].QProcess = QProcess
    source = "from PySide2 import QtCore, QtWidgets\nwindow = QtWidgets.QWidget()\nprocess = QtCore.QProcess(window)\n"
    handle = run_app(script(tmp_path, source))
    window, process = (handle.namespace[name] for name in ("window", "process"))
    handle.close()
    assert window.deleted == process.deleted == 0 and process.killed
    assert "deletion withheld" in handle.cleanup_errors[0]
    assert handle in _ACTIVE_HANDLES, "unsafe-to-delete objects must remain retained"
    _ACTIVE_HANDLES.discard(handle)  # Fixture objects have no native threads/processes.


def test_owned_acceptance_example_when_run_against_fixture_then_full_callback_path_passes():
    class QLabel(QWidget):
        def __init__(self, text, parent=None):
            super().__init__(parent)
            self.text = text

        def setText(self, text):
            self.text = text

    class QPushButton(QLabel):
        clicked = Signal()

        def click(self):
            self.clicked.emit()

    class QVBoxLayout(QObject):
        def addWidget(self, widget):
            widget.setParent(self.owner)

    qt = sys.modules["fontlab_echopy.PythonQt.QtGui"]
    qt.QLabel, qt.QPushButton, qt.QVBoxLayout = QLabel, QPushButton, QVBoxLayout
    sys.modules["fontlab_echopy.PythonQt.QtCore"].Slot = lambda *types: (
        lambda method: method
    )
    driver = Path(__file__).parents[1] / "examples" / "native_app_acceptance.py"
    handle, evidence = runpy.run_path(str(driver))["run_example"](close=True)
    assert handle.closed and evidence["updates"] == 1 and evidence["width"] == 420
    assert evidence["connections_before"] == 2, (
        "both measured Signal connections must be tracked"
    )
    assert evidence["disconnected_before_deletion"], (
        "signal emissions must verify disconnection while widgets still live"
    )
    assert not handle.cleanup_errors, (
        "example fixture must cover cleanup as well as construction"
    )


def test_run_app_when_measured_native_signal_is_borrowed_then_close_disconnects_before_owned_deletion(
    tmp_path,
):
    from pythonqtside._app_native import native_instance, qobject_instance

    signal = Signal()
    assert type(signal).__module__ == "QtCore" and type(signal).__mro__ == (
        Signal,
        object,
    )
    assert not native_instance(signal) and not qobject_instance(signal), (
        "signal detection must not broaden QObject ownership"
    )
    deliveries = []
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.borrowed_signal = lambda: signal
    qt.deliveries = deliveries

    class AssertDisconnectedWindow(QWidget):
        def deleteLater(self):
            signal.emit()
            assert not signal.callbacks and deliveries == ["delivered"], (
                "borrowed callbacks must be disconnected before deletion"
            )
            super().deleteLater()

    sys.modules["fontlab_echopy.PythonQt.QtGui"].QWidget = AssertDisconnectedWindow
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore, QtWidgets
window = QtWidgets.QWidget()
signal = QtCore.borrowed_signal()
def callback(): QtCore.deliveries.append('delivered')
signal.connect(callback)
""",
        )
    )
    window = handle.namespace["window"]
    assert handle.namespace["signal"] is signal and len(handle._connections) == 1
    assert all(signal is not obj for obj in handle._objects), (
        "native signals are borrowed callback surfaces, not owned QObjects"
    )
    signal.emit()
    assert deliveries == ["delivered"]
    handle.close()
    signal.emit()
    assert (
        deliveries == ["delivered"]
        and window.deleted == 1
        and not handle.cleanup_errors
    )


def test_run_app_when_signal_shaped_python_object_is_not_native_type_then_it_is_not_tracked(
    tmp_path,
):
    class PlainSignal:
        __module__ = "QtCore"

        def connect(self, callback):
            self.callback = callback

        def disconnect(self, callback):
            raise AssertionError(
                "ordinary Python connect/disconnect must remain untouched"
            )

    plain = PlainSignal()
    sys.modules["fontlab_echopy.PythonQt.QtCore"].plain = lambda: plain
    handle = run_app(
        script(
            tmp_path,
            "from PySide2 import QtCore\nsignal = QtCore.plain()\nsignal.connect(lambda: None)\n",
        )
    )
    assert handle.namespace["signal"] is plain and not handle._connections
    handle.close()
    assert not handle.cleanup_errors, (
        "type identity must distinguish native signals from similarly named Python objects"
    )


def test_run_app_when_fresh_native_signal_wrappers_disconnect_then_independent_reconnect_survives_close(
    tmp_path,
):
    class BorrowedEmitter(QWidget):
        clicked = Signal()

    emitter = BorrowedEmitter()
    first, second = emitter.clicked, emitter.clicked
    assert first is not second and first == second, (
        "fixture must reproduce measured backend equality"
    )
    deliveries = []
    callback = lambda: deliveries.append("independent")
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.borrowed_emitter = lambda: emitter
    qt.callback = callback
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore
emitter = QtCore.borrowed_emitter()
callback = QtCore.callback
emitter.clicked.connect(callback)
emitter.clicked.disconnect(callback)
""",
        )
    )
    assert not handle._connections, (
        "successful fresh-wrapper disconnect must remove the tracked record"
    )
    emitter.clicked.connect(callback)  # Independent connection outside this handle.
    handle.close()
    emitter.clicked.emit()
    assert deliveries == ["independent"] and emitter.deleted == 0, (
        "cleanup must preserve borrowed independent connections"
    )
    assert not handle.cleanup_errors


def test_run_app_when_different_native_signals_disconnect_then_other_record_remains(
    tmp_path,
):
    class BorrowedEmitter(QWidget):
        clicked = Signal()
        changed = Signal()

    emitter = BorrowedEmitter()
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.borrowed_emitter = lambda: emitter
    qt.callback = lambda: None
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore
emitter = QtCore.borrowed_emitter()
callback = QtCore.callback
emitter.clicked.connect(callback)
emitter.changed.connect(callback)
emitter.changed.disconnect(callback)
""",
        )
    )
    assert len(handle._connections) == 1, (
        "disconnect must match only its actual native signal backend"
    )
    assert handle._connections[0][0] == emitter.clicked
    handle.close()
    assert not emitter.clicked.callbacks and not handle.cleanup_errors


@pytest.fixture
def native_signal_methods(monkeypatch):
    from pythonqtside import _app_native

    # Native receipt: builtin_function_or_method, __name__ connect/disconnect,
    # __self__ exact QtCore.Signal. Substitute only the fixture method type;
    # native C-method acceptance belongs to the controller's FontLab run.
    monkeypatch.setattr(_app_native, "BuiltinMethodType", type(Signal().connect))


def test_run_app_when_borrowed_signal_connect_is_aliased_then_close_disconnects(
    tmp_path, native_signal_methods
):
    signal = Signal()
    deliveries = []
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.borrowed_signal = lambda: signal
    qt.deliveries = deliveries
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore
signal = QtCore.borrowed_signal()
connect = signal.connect
def callback(): QtCore.deliveries.append('delivered')
result = connect(callback)
""",
        )
    )
    assert handle.namespace["signal"] is signal and not handle._objects, (
        "capturing a native method must preserve Signal identity and borrowed ownership"
    )
    assert handle.namespace["connect"].__self__ is signal, (
        "the captured method itself must remain unchanged"
    )
    assert handle.namespace["result"] is None and len(handle._connections) == 1
    signal.emit()
    assert deliveries == ["delivered"], "borrowed callback must run before close"
    handle.close()
    signal.emit()
    assert deliveries == ["delivered"] and not signal.callbacks
    assert not handle.cleanup_errors, "aliased connection must be cleaned once"


@pytest.mark.parametrize(
    "connect_call", ["connect(callback)", "emitter.clicked.connect(callback)"]
)
def test_run_app_when_fresh_wrapper_disconnect_is_aliased_then_independent_reconnect_survives(
    tmp_path, native_signal_methods, connect_call
):
    class BorrowedEmitter(QWidget):
        clicked = Signal()

    emitter = BorrowedEmitter()
    deliveries = []
    callback = lambda: deliveries.append("independent")
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.borrowed_emitter = lambda: emitter
    qt.callback = callback
    handle = run_app(
        script(
            tmp_path,
            f"""from PySide2 import QtCore
emitter = QtCore.borrowed_emitter()
callback = QtCore.callback
connect = emitter.clicked.connect
disconnect = emitter.clicked.disconnect
{connect_call}
def detach(): disconnect(callback)
""",
        )
    )
    assert len(handle._connections) == 1, (
        "both connect forms must register the callback"
    )
    handle.namespace["detach"]()
    assert not handle._connections, (
        "aliased disconnect must remove the equal-wrapper record"
    )
    emitter.clicked.connect(callback)
    handle.close()
    emitter.clicked.emit()
    assert deliveries == ["independent"] and emitter.deleted == 0
    assert not handle.cleanup_errors, (
        "independent borrowed reconnect must remain untouched"
    )


def test_run_app_when_direct_signal_call_also_passes_prepare_then_it_is_recorded_once(
    tmp_path, native_signal_methods
):
    handle = run_app(
        script(
            tmp_path,
            "from PySide2 import QtCore\nsignal = QtCore.Signal()\nsignal.connect(lambda: None)\n",
        )
    )
    signal = handle.namespace["signal"]
    assert len(handle._connections) == 1, "resolved calls must not be tracked twice"
    handle.close()
    assert not signal.callbacks and not handle.cleanup_errors


def test_run_app_when_aliased_signal_callee_changes_during_arguments_then_original_method_runs(
    tmp_path, native_signal_methods
):
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore
signal = QtCore.Signal()
events = []
connect = signal.connect
def choose():
    events.append('callee')
    return connect
def argument():
    global connect
    events.append('argument')
    connect = lambda callback: events.append('replacement')
    return lambda: None
result = choose()(argument())
""",
        )
    )
    assert handle.namespace["events"] == ["callee", "argument"], (
        "the chosen alias must resolve before arguments rebind its source name"
    )
    assert handle.namespace["result"] is None and len(handle._connections) == 1
    handle.close()
    assert not handle.cleanup_errors


def test_run_app_when_ordinary_callable_has_metadata_traps_then_frame_and_identity_survive(
    tmp_path,
):
    class CallableTrap:
        def __getattribute__(self, name):
            if name in {"__name__", "__self__", "connect", "disconnect"}:
                raise AssertionError("ordinary callable metadata must not be probed")
            return super().__getattribute__(name)

        def __call__(self, value):
            return value

    trap = CallableTrap()
    qt = sys.modules["fontlab_echopy.PythonQt.QtCore"]
    qt.trap = trap
    handle = run_app(
        script(
            tmp_path,
            """from PySide2 import QtCore
ordinary = QtCore.trap
alias = locals
execute = exec
evaluate = eval
class Base:
    def value(self): return 9
class Child(Base):
    def value(self):
        own = 11
        execute("extra = 13")
        return super().value(), alias()['own'], evaluate('own + 1'), vars()['extra'], 'own' in dir(), globals()['ordinary'] is ordinary
result = Child().value()
ordinary_result = ordinary(23)
""",
        )
    )
    assert (
        handle.namespace["ordinary"] is trap
        and handle.namespace["ordinary_result"] == 23
    )
    assert handle.namespace["result"] == (9, 11, 12, 13, True, True), (
        "callee preparation must retain the original frame for builtin aliases"
    )
    assert not handle._connections, (
        "ordinary callable must never become a native connection"
    )


def test_prepare_when_other_builtin_or_python_methods_look_native_then_callee_is_unchanged(
    tmp_path,
):
    import socket

    handle = run_app(script(tmp_path, "value = 1\n"))
    signal = Signal()
    python_connect = signal.connect
    assert handle._prepare(python_connect) is python_connect, (
        "unmeasured Python methods must not be mistaken for native C methods"
    )
    with socket.socket() as receiver:
        builtin_connect = receiver.connect
        assert handle._prepare(builtin_connect) is builtin_connect, (
            "a builtin connect requires the exact native Signal receiver"
        )
    assert handle._prepare(locals) is locals, (
        "frame-sensitive builtins must remain unchanged"
    )
    assert not handle._connections


def test_connection_receiver_matching_when_non_native_or_qobject_has_custom_equality_then_equality_is_not_called():
    from pythonqtside._app_native import same_connection_receiver

    class OrdinaryEqualityTrap:
        def __eq__(self, other):
            raise AssertionError("ordinary Python equality must not run")

    class QObjectEqualityTrap(QWidget):
        def __eq__(self, other):
            raise AssertionError("QObject matching must retain object identity")

    plain, other_plain = OrdinaryEqualityTrap(), OrdinaryEqualityTrap()
    native, other_native = QObjectEqualityTrap(), QObjectEqualityTrap()
    assert same_connection_receiver(plain, plain)
    assert not same_connection_receiver(plain, other_plain)
    assert not same_connection_receiver(native, other_native)
    assert not same_connection_receiver(Signal(), plain)


def test_handle_when_closed_from_worker_thread_then_ui_is_untouched(tmp_path):
    handle = run_app(
        script(tmp_path, "from PySide2.QtWidgets import QWidget\nwindow = QWidget()\n")
    )
    errors = []

    def worker():
        try:
            handle.close()
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert errors and not handle.closed and handle.namespace["window"].deleted == 0


def test_host_application_when_not_in_fontlab_or_wrong_thread_then_precise_failure(
    monkeypatch,
):
    host_application = measured_host_application

    def unavailable(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("pythonqtside._app_native.import_module", unavailable)
    with pytest.raises(RuntimeError, match="FontLab"):
        host_application()
    errors = []

    def off_thread():
        try:
            host_application()
        except RuntimeError as error:
            errors.append(str(error))

    worker = threading.Thread(target=off_thread)
    worker.start()
    worker.join()
    assert errors == ["run_app must execute on FontLab's main Python thread"]
