# this_file: tests/test_out_parameters.py
"""Measured (value, ok) adapters; fixtures model PythonQt, not prove the binding."""

import subprocess
import sys
from types import ModuleType
from typing import ClassVar

import pytest

from pythonqtside import compat, run_app
from pythonqtside._app import _ACTIVE_HANDLES
from pythonqtside._app_native import resolve


class QTransform:
    """Native receipt: inverted() returns only the transform; isInvertible() exists."""

    __module__ = "PythonQt.QtGui"

    def __init__(self, invertible=True):
        self.ok = invertible
        self.inverse = object()
        self.calls = []

    def inverted(self, *args):
        self.calls.append(args)
        return self.inverse

    def isInvertible(self):
        return self.ok


class BoolResult:
    """PythonQt.BoolResult: native code sets it; Python reads it with bool()."""

    __module__ = "PythonQt"

    def __init__(self):
        self.value = False

    def __bool__(self):
        return self.value


def _out(flag, value):
    if isinstance(flag, BoolResult):
        flag.value = value


class QMatrix4x4:
    """Measured without isInvertible(); native inverted(invertible) takes BoolResult."""

    __module__ = "PythonQt.QtGui"

    def __init__(self):
        self.inverse = object()
        self.calls = []

    def inverted(self, *args):
        self.calls.append(args)
        if args:
            _out(args[0], True)
        return self.inverse


class QLocale:
    """Native toInt(s, ok): the out-parameter follows the PySide2 argument."""

    __module__ = "PythonQt.QtCore"

    def __init__(self):
        self.calls = []

    def toInt(self, s, *rest):
        self.calls.append((s, *rest))
        if rest:
            _out(rest[0], s.isdigit())
        return int(s) if s.isdigit() else 0


class QLineEdit:
    __module__ = "PythonQt.QtGui"
    Normal = "native Normal echo"


class QInputDialog:
    """Static getText(parent, title, label, echo, text, ok, flags); never opens."""

    __module__ = "PythonQt.QtGui"
    calls: ClassVar[list] = []

    @staticmethod
    def getText(parent, title, label, *rest):
        QInputDialog.calls.append((parent, title, label, *rest))
        if len(rest) > 2:
            _out(rest[2], True)
        return "typed"


class QWidget:
    __module__ = "PythonQt.QtGui"
    windowTitle = "native title"

    def metaObject(self):
        return self

    def indexOfProperty(self, name):
        return 0 if name == "windowTitle" else -1

    def property(self, name):
        return getattr(self, name)


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    qt.QtGui.QTransform = QTransform
    qt.QtGui.QMatrix = type("QMatrix", (QTransform,), {"__module__": "PythonQt.QtGui"})
    qt.QtGui.QMatrix4x4 = QMatrix4x4
    qt.QtGui.QWidget = QWidget
    qt.QtGui.QLineEdit = QLineEdit
    qt.QtGui.QInputDialog = QInputDialog
    qt.BoolResult = BoolResult
    qt.QtCore = ModuleType("PythonQt.QtCore")
    qt.QtCore.QLocale = QLocale
    QInputDialog.calls = []
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtGui", qt.QtGui)
    monkeypatch.setitem(sys.modules, "fontlab_echopy.PythonQt.QtCore", qt.QtCore)
    monkeypatch.setattr(_app_native, "host_application", lambda: (QWidget(), ()))
    yield
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


@pytest.mark.parametrize("invertible", [True, False])
def test_resolve_when_measured_inverted_called_without_arguments_then_value_and_ok(
    invertible,
):
    transform = QTransform(invertible)
    value, ok = resolve(transform, "inverted")()
    assert value is transform.inverse, "the native result object must be returned as is"
    assert ok is invertible, "ok comes from the native isInvertible() predicate"
    assert transform.calls == [()]


def test_resolve_when_inverted_receives_arguments_then_native_call_passes_through():
    transform = QTransform()
    flag = object()
    assert resolve(transform, "inverted")(flag) is transform.inverse
    assert transform.calls == [(flag,)], "PythonQt-style out-parameters stay native"


def test_resolve_when_class_is_not_native_then_method_is_unchanged():
    class QTransformLookalike:
        def inverted(self):
            return "python"

    assert resolve(QTransformLookalike(), "inverted")() == "python"


def test_resolve_when_python_subclass_of_measured_native_class_then_adapter_applies():
    class Shear(QTransform):
        pass

    shear = Shear(invertible=False)
    assert resolve(shear, "inverted")() == (shear.inverse, False)


def test_resolve_when_native_inverted_raises_then_adapter_runs_and_error_propagates():
    class Failing(QTransform):
        __module__ = "PythonQt.QtGui"  # native-like: no Python override to skip

        def inverted(self, *args):
            raise TypeError("native requires invertible")

    failing = Failing()
    adapted = resolve(failing, "inverted")
    assert adapted != failing.inverted, "the predicate adapter must wrap the call"
    with pytest.raises(TypeError, match="native requires invertible"):
        adapted()


def test_resolve_when_bool_result_native_call_raises_then_error_propagates():
    class Broken(QLocale):
        __module__ = "PythonQt.QtCore"

        def toInt(self, s, *rest):
            raise ValueError(f"native toInt rejected {len(rest)} out-parameter")

    broken = Broken()
    adapted = resolve(broken, "toInt")
    assert adapted != broken.toInt, "the BoolResult adapter must wrap the call"
    with pytest.raises(ValueError, match="rejected 1 out-parameter"):
        adapted("7")


def test_resolve_when_matrix4x4_inverted_without_arguments_then_bool_result_tuple():
    matrix = QMatrix4x4()
    value, ok = resolve(matrix, "inverted")()
    assert value is matrix.inverse and ok is True
    (call,) = matrix.calls
    assert len(call) == 1 and isinstance(call[0], BoolResult), "native out slot 0"


@pytest.mark.parametrize(("text", "expected"), [("42", (42, True)), ("x", (0, False))])
def test_resolve_when_locale_to_int_then_bool_result_follows_pyside_arguments(
    text, expected
):
    locale = QLocale()
    assert resolve(locale, "toInt")(text) == expected
    (call,) = locale.calls
    assert call[0] == text and isinstance(call[1], BoolResult)


def test_resolve_when_static_get_text_omits_defaults_then_qt_defaults_fill_slots():
    parent = object()
    assert resolve(QInputDialog, "getText")(parent, "T", "L") == ("typed", True)
    (call,) = QInputDialog.calls
    assert call[:5] == (parent, "T", "L", QLineEdit.Normal, ""), (
        "echo resolves natively at call time; text defaults to an empty string"
    )
    assert isinstance(call[5], BoolResult) and len(call) == 6


def test_resolve_when_get_text_has_trailing_flags_then_they_follow_bool_result():
    resolve(QInputDialog, "getText")(None, "T", "L", 2, "seed", "flags")
    (call,) = QInputDialog.calls
    assert call[:5] == (None, "T", "L", 2, "seed") and call[6] == "flags"
    assert isinstance(call[5], BoolResult)


def test_resolve_when_call_is_pythonqt_style_or_keyword_then_native_passes_through():
    explicit = BoolResult()
    assert resolve(QInputDialog, "getText")(None, "T", "L", 0, "", explicit) == "typed"
    assert bool(explicit), "explicit BoolResult calls are untouched"
    locale = QLocale()
    assert resolve(locale, "toInt")(s="5") == 5, "keyword calls are not adapted"
    assert resolve(locale, "toInt")("5", None) == 5, "extra positional: native form"
    assert locale.calls == [("5",), ("5", None)]
    with pytest.raises(TypeError):  # missing required parameter: native error
        resolve(QInputDialog, "getText")(None)


def test_resolve_when_instance_method_called_unbound_on_class_then_not_adapted():
    locale = QLocale()
    assert resolve(QLocale, "toInt")(locale, "3") == 3
    assert locale.calls == [("3",)], "only static methods adapt on class receivers"


def test_resolve_when_python_class_overrides_static_method_then_unchanged():
    class Custom(QInputDialog):
        @staticmethod
        def getText(*args):
            return "own"

    assert resolve(Custom, "getText")(None, "T", "L") == "own"


def test_adapter_when_loaded_then_reads_only_the_small_runtime_table(monkeypatch):
    from pathlib import Path

    from pythonqtside import _app_native

    read = []
    original = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **k: read.append(self.name) or original(self, *a, **k),
    )
    _app_native._out_parameter_tables.cache_clear()
    resolve(QLocale(), "toInt")("1")
    assert read == ["_out_parameters.json"], "the 240 KB report must not load"


def test_compat_when_new_code_uses_pyside_style_then_getter_and_tuple_work():
    widget, transform = QWidget(), QTransform()
    assert compat.pyside_method(widget, "windowTitle")() == "native title"
    assert widget.windowTitle == "native title", "attribute reads stay values"
    assert compat.pyside_method(transform, "inverted")() == (transform.inverse, True)


def test_compat_when_imported_then_no_qt_binding_is_loaded():
    code = "import sys, pythonqtside.compat; assert 'PythonQt' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_run_app_when_pyside_source_calls_getters_and_inverted_then_both_adapt(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(
        """from PySide2.QtGui import QTransform
from PySide2.QtWidgets import QWidget
window = QWidget()
title = window.windowTitle()
plain = window.windowTitle
inverse, ok = QTransform(False).inverted()
singular = QTransform(False)
from PySide2.QtCore import QLocale
from PySide2.QtWidgets import QInputDialog
number, parsed = QLocale().toInt("7")
text, accepted = QInputDialog.getText(window, "Title", "Label")
"""
    )
    handle = run_app(path)
    ns = handle.namespace
    assert (ns["title"], ns["plain"]) == ("native title", "native title")
    assert ns["ok"] is False and ns["inverse"] is not None
    assert (ns["number"], ns["parsed"]) == (7, True)
    assert (ns["text"], ns["accepted"]) == ("typed", True), "dialog double, no UI"
    assert type(ns["singular"]) is QTransform, "constructed class identity is native"
    handle.close()


def test_resolve_when_python_subclass_overrides_inverted_then_override_is_unchanged():
    class Custom(QTransform):
        def inverted(self):
            return ("own", super().inverted())

    custom = Custom()
    assert resolve(custom, "inverted")() == ("own", custom.inverse), (
        "Python overrides keep Python behavior; no measured difference applies"
    )
    custom.inverted = lambda: "instance"
    assert resolve(custom, "inverted")() == "instance"
