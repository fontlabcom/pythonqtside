# this_file: tests/test_file_dialogs.py
"""PySide2's (path, selectedFilter) file-dialog results; fixtures model PythonQt, never open a dialog."""

import sys
from types import ModuleType
from typing import ClassVar

import pytest

from pythonqtside import compat, run_app
from pythonqtside._app import _ACTIVE_HANDLES


class QFileDialog:
    """Native statics return only the path (or list); calls are recorded."""

    __module__ = "PythonQt.QtGui"
    calls: ClassVar[list] = []

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        QFileDialog.calls.append(("open", args) + ((kwargs,) if kwargs else ()))
        return "/tmp/a.ufo"

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        QFileDialog.calls.append(("save", args) + ((kwargs,) if kwargs else ()))
        return "/tmp/b.otf"

    @staticmethod
    def getOpenFileNames(*args, **kwargs):
        QFileDialog.calls.append(("many", args) + ((kwargs,) if kwargs else ()))
        return ("/tmp/c", "/tmp/d")  # PythonQt: a tuple of paths

    @staticmethod
    def getExistingDirectory(*args):
        QFileDialog.calls.append(("dir", args))
        return "/tmp"


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    qt.QtGui.QFileDialog = QFileDialog
    qt.QtCore = ModuleType("PythonQt.QtCore")
    QFileDialog.calls = []
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtGui", qt.QtGui)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtCore", qt.QtCore)
    monkeypatch.setattr(_app_native, "host_application", lambda: (object(), ()))
    yield
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


def test_open_when_called_positionally_then_path_and_empty_filter_tuple():
    result = compat.pyside_method(QFileDialog, "getOpenFileName")(
        None, "Open", "/tmp", "UFO (*.ufo)"
    )
    assert result == ("/tmp/a.ufo", ""), "PySide2 unpacks `path, _filter = ...`"
    assert QFileDialog.calls == [("open", (None, "Open", "/tmp", "UFO (*.ufo)"))]


def test_open_when_called_without_arguments_then_native_call_has_no_arguments():
    assert compat.pyside_method(QFileDialog, "getOpenFileName")() == ("/tmp/a.ufo", "")
    assert QFileDialog.calls == [("open", ())]


def test_save_when_keywords_used_then_mapped_to_positions_with_defaults():
    result = compat.pyside_method(QFileDialog, "getSaveFileName")(
        caption="Save", filter="OTF (*.otf)"
    )
    assert result == ("/tmp/b.otf", "")
    assert QFileDialog.calls == [("save", (None, "Save", "", "OTF (*.otf)"))], (
        "gaps filled with PySide2 defaults"
    )


def test_many_when_called_then_list_and_filter_tuple():
    result = compat.pyside_method(QFileDialog, "getOpenFileNames")(None, "Pick")
    assert result == (["/tmp/c", "/tmp/d"], "")
    assert QFileDialog.calls == [("many", (None, "Pick"))]


@pytest.mark.parametrize(
    "args,kwargs,expected",
    [
        ((None, "c", "d", "f", 4), {}, (None, "c", "d", "f", "", 4)),
        ((), {"options": 1}, (None, "", "", "", "", 1)),
        ((None, "c"), {"options": 4}, (None, "c", "", "", "", 4)),
    ],
)
def test_open_when_options_given_then_native_selected_filter_inserted_before_options(
    args, kwargs, expected
):
    from pythonqtside._app_native import resolve

    result = resolve(QFileDialog, "getOpenFileName", keywords=True)(*args, **kwargs)
    assert result == ("/tmp/a.ufo", ""), (
        "always the PySide2 pair; selectedFilter cannot be filled"
    )
    assert QFileDialog.calls == [("open", expected)], (
        "PySide2 options (5th) goes to native position 6 after selectedFilter ''"
    )


def test_open_when_selected_filter_keyword_then_type_error_and_no_native_call():
    with pytest.raises(TypeError, match="selectedFilter"):
        compat.pyside_method(QFileDialog, "getOpenFileName")(None, selectedFilter="x")
    assert QFileDialog.calls == [], "PySide2 has no selectedFilter parameter"


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((1, 2, 3, 4, 5, 6), {}),
        ((1, 2, 3, 4, 5, 6, 7), {}),
        ((), {"bogus": 1}),
        ((None,), {"parent": None}),
    ],
)
def test_open_when_not_a_pyside2_form_then_native_call_unchanged(args, kwargs):
    compat.pyside_method(QFileDialog, "getOpenFileName")(*args, **kwargs)
    assert QFileDialog.calls == [("open", args) + ((kwargs,) if kwargs else ())]


def test_many_when_keywords_then_mapped_and_list_pair():
    result = compat.pyside_method(QFileDialog, "getOpenFileNames")(
        caption="Pick", options=2
    )
    assert result == (["/tmp/c", "/tmp/d"], "")
    assert QFileDialog.calls == [("many", (None, "Pick", "", "", "", 2))]


def test_open_when_native_already_returns_pair_then_passed_through(monkeypatch):
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a: ("/tmp/x", "UFO (*.ufo)")),
    )
    assert compat.pyside_method(QFileDialog, "getOpenFileName")(None) == (
        "/tmp/x",
        "UFO (*.ufo)",
    )


def test_instance_receiver_when_picker_called_then_pair():
    dialog = QFileDialog()
    assert compat.pyside_method(dialog, "getSaveFileName")(None, "Save") == (
        "/tmp/b.otf",
        "",
    )
    assert QFileDialog.calls == [("save", (None, "Save"))]


def test_subclass_without_override_when_picker_called_then_pair():
    class Mine(QFileDialog):
        __module__ = "mine"

    assert compat.pyside_method(Mine, "getOpenFileName")(None, "Open") == (
        "/tmp/a.ufo",
        "",
    )
    assert compat.pyside_method(Mine(), "getOpenFileName")(None, "Open") == (
        "/tmp/a.ufo",
        "",
    )
    assert QFileDialog.calls == [("open", (None, "Open"))] * 2


def test_existing_directory_when_called_then_plain_string_like_pyside2():
    assert (
        compat.pyside_method(QFileDialog, "getExistingDirectory")(None, "Dir") == "/tmp"
    )


def test_python_subclass_override_when_called_then_its_own_behavior():
    class Mine(QFileDialog):
        __module__ = "mine"

        @staticmethod
        def getOpenFileName(*args):
            return "python"

    assert compat.pyside_method(Mine, "getOpenFileName")() == "python"


def test_run_app_when_source_unpacks_open_file_name_then_it_works(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "from PySide2.QtWidgets import QFileDialog\n"
        "path, flt = QFileDialog.getOpenFileName(None, 'Open', '', 'All (*)')\n"
        "RESULT = (path, flt)\n"
    )
    handle = run_app(str(source))
    assert handle.namespace["RESULT"] == ("/tmp/a.ufo", "")
    handle.close()
