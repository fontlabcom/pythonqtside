# this_file: tests/test_review_fixes.py
"""Regression tests for the issue-104 L4 review (R-L4-review.md); doubles, not proof."""

# ruff: noqa: F811 - pytest fixtures imported from sibling test modules

import gc
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from test_app_runner import (  # noqa: F401
    Signal,
    native,
    native_signal_methods,
    protected_widget,
    script,
)
from test_connections import OverloadSignal, Process, overload_signals  # noqa: F401

from pythonqtside import run_app
from pythonqtside._app_cleanup import connection_call

FIXTURES = Path(__file__).parents[1] / "examples/fixtures"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"pqs_test_{name}", FIXTURES / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disconnect_when_callback_not_tracked_then_native_disconnect_called():
    signal, seen = Signal(), []
    signal.connect(seen.append)  # connected outside the handle's tracking
    connection_call(signal, "disconnect", signal.disconnect, [])(seen.append)
    signal.emit(1)
    assert seen == [], "an untracked callback is disconnected natively"


ALIAS = """from PySide2.QtCore import QProcess
process = QProcess()
finished = process.finished
finished.connect(lambda code, status: None)
"""


def test_run_app_when_signal_aliased_then_overload_still_selected(
    tmp_path, overload_signals
):
    handle = run_app(script(tmp_path, ALIAS))
    assert handle.namespace["process"].overloads == [
        "2finished(int,QProcess::ExitStatus)"
    ]


CAPTURED = """from PySide2.QtCore import QProcess
process = QProcess()
connect = process.finished.connect
connect(lambda code, status: None)
"""


def test_run_app_when_connect_captured_then_overload_still_selected(
    tmp_path, overload_signals, native_signal_methods
):
    handle = run_app(script(tmp_path, CAPTURED))
    assert handle.namespace["process"].overloads == [
        "2finished(int,QProcess::ExitStatus)"
    ]


def test_hostpath_when_torn_down_then_prior_path_and_modules_restored(tmp_path):
    hostpath = _load("hostpath")
    for package in ("pythonqtside", "fontlab_echopy"):
        (tmp_path / package / package).mkdir(parents=True)
        (tmp_path / package / package / "__init__.py").write_text("")
    harness = tmp_path / "harness.py"
    harness.write_text("VALUE = 1\n")
    prior_path, prior = (
        list(sys.path),
        {name: sys.modules.get(name) for name in ("pythonqtside", "PySide2")},
    )
    sentinel = ModuleType("PySide2")
    sys.modules["PySide2"] = sentinel
    sys.path.append("/prior/entry")
    expected_path = list(sys.path)
    variables = {
        "pqs": str(tmp_path / "pythonqtside"),
        "echo": str(tmp_path / "fontlab_echopy"),
        "harness": str(harness),
        "MODULE": "pqs_test_harness",
    }
    try:
        namespace = dict(variables)
        exec(hostpath.SETUP, namespace)  # noqa: S102 - the strings run inside FontLab
        assert sys.modules["pythonqtside"].__file__.startswith(str(tmp_path))
        exec(hostpath.TEARDOWN, dict(variables))  # noqa: S102
        assert sys.path == expected_path, "prior sys.path order restored"
        assert sys.modules["PySide2"] is sentinel, "prior modules restored"
        assert sys.modules.get("pythonqtside") is prior["pythonqtside"]
        assert "pqs_test_harness" not in sys.modules
    finally:
        sys.path[:] = prior_path
        for name, module in prior.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_acceptance_when_startup_changes_source_then_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules["PythonQt"].QtCore, "Qt", object(), raising=False)
    acceptance = _load("acceptance")
    (tmp_path / "demo").mkdir()
    source = tmp_path / "demo" / "app.py"
    source.write_text("x = 1\n")

    class Handle:
        closed, cleanup_errors, reports = True, (), {}

        def close(self):
            pass

    def fake_run_app(path):
        source.write_text("x = 2\n")  # startup changes the fixture
        return Handle()

    monkeypatch.setattr(acceptance, "HERE", tmp_path)
    monkeypatch.setattr(acceptance, "run_app", fake_run_app)
    acceptance.start("demo")
    assert acceptance.finish("demo")["sources_unchanged"] is False


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("outcome", ["found", "missing", "error"])
def test_acceptance_when_action_list_converted_then_gc_guarded_and_restored(
    monkeypatch, enabled, outcome
):
    monkeypatch.setattr(sys.modules["PythonQt"].QtCore, "Qt", object(), raising=False)
    acceptance = _load("acceptance")
    action = SimpleNamespace(objectName="actionUndo")
    calls = []

    class Window:
        def menuBar(self):
            return self

        def findChildren(self, kind):
            calls.append(gc.isenabled())
            assert not gc.isenabled(), "native list conversion requires GC disabled"
            if outcome == "error":
                raise ValueError("native conversion failed")
            return [action] if outcome == "found" else []

    window = Window()
    fontlab = ModuleType("fontlab")
    fontlab.MainWindow = lambda: window
    monkeypatch.setitem(sys.modules, "fontlab", fontlab)
    monkeypatch.setattr(acceptance.QtGui, "QAction", object, raising=False)

    def forbidden():
        pytest.fail("use fontlab.MainWindow() instead of enumerating all windows")

    monkeypatch.setattr(acceptance.App, "topLevelWidgets", forbidden, raising=False)
    prior = gc.isenabled()
    try:
        (gc.enable if enabled else gc.disable)()
        if outcome == "error":
            with pytest.raises(ValueError, match="native conversion failed"):
                acceptance._action("actionUndo")
        else:
            expected = action if outcome == "found" else None
            assert acceptance._action("actionUndo") is expected
        assert calls == [False], "only the main window's guarded list is converted"
        assert gc.isenabled() is enabled, "restore the prior GC state in finally"
    finally:
        (gc.enable if prior else gc.disable)()


BORROWED = """from PySide2 import QtCore
process = QtCore.borrowed_process()
finished = process.finished
finished.connect(lambda code, status: None)
"""


def test_run_app_when_borrowed_signal_aliased_then_overload_still_selected(
    tmp_path, overload_signals
):
    borrowed = Process()
    sys.modules["fontlab_echopy.PythonQt.QtCore"].borrowed_process = lambda: borrowed
    handle = run_app(script(tmp_path, BORROWED))
    assert not any(o is borrowed for o in handle._objects), "the sender is borrowed"
    assert borrowed.overloads == ["2finished(int,QProcess::ExitStatus)"]
    handle.close()
    assert borrowed.overloads == [], "close() undoes the overload connection"


SUPER_LOAD = """from PySide2.QtWidgets import QPlainTextEdit
class Editor(QPlainTextEdit):
    def paintEvent(self, event):
        base = super().paintEvent
        self.result = base(event)
editor = Editor()
editor.paintEvent("event")
"""


def test_run_app_when_super_attribute_loaded_then_native_base_reached(
    tmp_path, protected_widget
):
    editor = run_app(script(tmp_path, SUPER_LOAD)).namespace["editor"]
    instance, event = editor.result[:2]
    assert instance is editor and event == "event", (
        "PythonQt super() misses it; forwarded"
    )


SUPER_KEYWORD_FALLBACK = """from PySide2.QtWidgets import QPlainTextEdit
class Editor(QPlainTextEdit):
    def paintEvent(self, event):
        self.result = super().paintEvent(e=event)
editor = Editor()
editor.paintEvent("event")
"""


def test_run_app_when_super_call_uses_keywords_then_native_fallback_gets_positions(
    tmp_path, protected_widget
):
    editor = run_app(script(tmp_path, SUPER_KEYWORD_FALLBACK)).namespace["editor"]
    instance, event, args, kwargs = editor.result[:4]
    assert (instance, event, args, kwargs) == (editor, "event", (), {}), (
        "PySide2's parameter name became a position on the native base fallback"
    )
