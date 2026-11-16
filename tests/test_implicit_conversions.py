# this_file: tests/test_implicit_conversions.py
"""Measured enum -> value-class wrapping; doubles model PythonQt, not prove it."""

import sys
from types import ModuleType
from typing import ClassVar

import pytest

from pythonqtside import _app_conversions, compat, run_app
from pythonqtside._app import _ACTIVE_HANDLES
from pythonqtside._app_native import resolve


def _enum(name, module):
    """PythonQt enum values are int subclasses of a per-enum type (checklist item 1)."""
    return type(name, (int,), {"__module__": module})


class QEasingCurve:
    __module__ = "PythonQt.QtCore"
    Type = _enum("Type", "PythonQt.QtCore")

    def __init__(self, value=None):
        self.value = value


QEasingCurve.OutElastic = QEasingCurve.Type(30)


class Qt:
    __module__ = "PythonQt.QtCore"
    CursorShape = _enum("CursorShape", "PythonQt.QtCore")
    GlobalColor = _enum("GlobalColor", "PythonQt.QtCore")


Qt.WaitCursor = Qt.CursorShape(16)
Qt.red = Qt.GlobalColor(7)


class QCursor:
    __module__ = "PythonQt.QtGui"

    def __init__(self, shape):
        self.shape = shape


class QColor:
    __module__ = "PythonQt.QtGui"

    def __init__(self, color):
        self.color = color


class Recorder:
    """Native-like receiver: records the arguments each method received."""

    def __init__(self):
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return f"native {name}"


class QVariantAnimation(Recorder):
    __module__ = "PythonQt.QtCore"

    def setEasingCurve(self, *args, **kwargs):
        return self._record("setEasingCurve", *args, **kwargs)


class QTcpServer(Recorder):
    __module__ = "PythonQt.QtNetwork"

    def listen(self, *args):
        return self._record("listen", *args)


class QHostAddress:
    __module__ = "PythonQt.QtNetwork"
    SpecialAddress = _enum("SpecialAddress", "PythonQt.QtNetwork")

    def __init__(self, value):
        self.value = value


QHostAddress.LocalHost = QHostAddress.SpecialAddress(2)


class QWidget(Recorder):
    __module__ = "PythonQt.QtGui"

    def setCursor(self, *args):
        return self._record("setCursor", *args)


class QLabel(QWidget):
    __module__ = "PythonQt.QtGui"


class QPushButton(Recorder):
    """Flat like the native stubs ("Native bases: PythonQtInstanceWrapper")."""

    __module__ = "PythonQt.QtGui"

    def setCursor(self, *args):
        return self._record("setCursor", *args)


class QPropertyAnimation(Recorder):
    __module__ = "PythonQt.QtCore"

    def setEasingCurve(self, *args):
        return self._record("setEasingCurve", *args)


class QGuiApplication:
    __module__ = "PythonQt.QtGui"
    calls: ClassVar[list] = []

    @staticmethod
    def setOverrideCursor(cursor):
        QGuiApplication.calls.append(cursor)


class QApplication(QGuiApplication):
    __module__ = "PythonQt.QtGui"


class QPalette(Recorder):
    __module__ = "PythonQt.QtGui"
    ColorGroup = _enum("ColorGroup", "PythonQt.QtGui")
    ColorRole = _enum("ColorRole", "PythonQt.QtGui")

    def setColor(self, *args):
        return self._record("setColor", *args)


QPalette.Active = QPalette.ColorGroup(0)
QPalette.Window = QPalette.ColorRole(10)


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.QtCore = ModuleType("PythonQt.QtCore")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    qt.QtNetwork = ModuleType("PythonQt.QtNetwork")
    for module, classes in (
        (qt.QtCore, (QEasingCurve, Qt, QVariantAnimation, QPropertyAnimation)),
        (
            qt.QtGui,
            (
                QColor,
                QCursor,
                QWidget,
                QLabel,
                QPushButton,
                QGuiApplication,
                QApplication,
                QPalette,
            ),
        ),
        (qt.QtNetwork, (QTcpServer, QHostAddress)),
    ):
        for cls in classes:
            setattr(module, cls.__name__, cls)
    QGuiApplication.calls = []
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    for name in ("QtCore", "QtGui", "QtNetwork"):
        monkeypatch.setitem(
            sys.modules, f"fontlab_echopy.PythonQt.{name}", getattr(qt, name)
        )
    monkeypatch.setattr(_app_native, "host_application", lambda: (QWidget(), ()))
    yield qt
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


def test_resolve_when_enum_passed_for_value_class_then_wrapped_and_result_native():
    animation = QVariantAnimation()
    result = resolve(animation, "setEasingCurve")(QEasingCurve.OutElastic)
    assert result == "native setEasingCurve", "the native return value is unchanged"
    ((_, (curve,), _),) = animation.calls
    assert type(curve) is QEasingCurve and curve.value is QEasingCurve.OutElastic


def test_resolve_when_listen_gets_special_address_then_host_address_and_port_kept():
    server = QTcpServer()
    resolve(server, "listen")(QHostAddress.LocalHost, 0)
    ((_, (address, port), _),) = server.calls
    assert type(address) is QHostAddress and address.value is QHostAddress.LocalHost
    assert port == 0


@pytest.mark.parametrize(
    "value", [30, True, Qt.WaitCursor, None, "OutElastic"], ids=repr
)
def test_resolve_when_value_is_not_the_measured_enum_then_passed_unchanged(value):
    animation = QVariantAnimation()
    resolve(animation, "setEasingCurve")(value)
    assert animation.calls == [("setEasingCurve", (value,), {})], (
        "plain ints, bools and other enum types keep native dispatch"
    )


def test_resolve_when_value_class_already_given_then_unchanged():
    curve, animation = QEasingCurve(), QVariantAnimation()
    resolve(animation, "setEasingCurve")(curve)
    assert animation.calls[0][1][0] is curve


def test_resolve_when_keyword_or_out_of_range_arity_then_native_passes_through():
    animation, server = QVariantAnimation(), QTcpServer()
    resolve(animation, "setEasingCurve")(easing=QEasingCurve.OutElastic)
    assert animation.calls[0][2] == {"easing": QEasingCurve.OutElastic}
    resolve(server, "listen")(QHostAddress.LocalHost, 0, "extra")
    assert server.calls[0][1][0] is QHostAddress.LocalHost


def test_resolve_when_python_subclass_overrides_method_then_unchanged():
    class Custom(QVariantAnimation):
        def setEasingCurve(self, value):
            return ("own", value)

    custom = Custom()
    assert resolve(custom, "setEasingCurve")(QEasingCurve.OutElastic) == (
        "own",
        QEasingCurve.OutElastic,
    )


def test_resolve_when_python_subclass_without_override_then_wrapped():
    class Animation(QVariantAnimation):
        pass

    animation = Animation()
    resolve(animation, "setEasingCurve")(QEasingCurve.OutElastic)
    assert type(animation.calls[0][1][0]) is QEasingCurve


def test_resolve_when_receiver_not_native_then_method_is_unchanged():
    class Lookalike:
        def setEasingCurve(self, value):
            return value

    lookalike = Lookalike()
    assert resolve(lookalike, "setEasingCurve") == lookalike.setEasingCurve


def test_resolve_when_flat_native_subclass_then_its_own_entry_applies():
    button, animation = QPushButton(), QPropertyAnimation()
    assert not isinstance(button, QWidget), "the double has no Qt base chain"
    resolve(button, "setCursor")(Qt.WaitCursor)
    resolve(animation, "setEasingCurve")(QEasingCurve.OutElastic)
    assert type(button.calls[0][1][0]) is QCursor
    assert type(animation.calls[0][1][0]) is QEasingCurve


def test_resolve_when_static_method_on_class_then_wrapped():
    resolve(QApplication, "setOverrideCursor")(Qt.WaitCursor)
    (cursor,) = QGuiApplication.calls
    assert type(cursor) is QCursor and cursor.shape is Qt.WaitCursor


def test_resolve_when_native_enum_type_unresolvable_then_unchanged(native):
    del native.QtCore.Qt
    widget = QWidget()
    resolve(widget, "setCursor")(Qt.WaitCursor)
    assert widget.calls == [("setCursor", (Qt.WaitCursor,), {})], (
        "fail closed when the native enum type does not resolve"
    )


def test_resolve_when_subclass_entry_is_empty_then_it_shadows_base(monkeypatch):
    position = {
        "index": 0,
        "arities": [1, 1],
        "conversions": {"QtCore.Qt.CursorShape": "QtGui.QCursor"},
    }
    table = {
        "setCursor": (
            ("QtGui.QLabel", {"static": False, "positions": []}),
            ("QtGui.QWidget", {"static": False, "positions": [position]}),
        )
    }
    monkeypatch.setattr(_app_conversions, "_table", lambda: table)
    label, widget = QLabel(), QWidget()
    resolve(label, "setCursor")(Qt.WaitCursor)
    resolve(widget, "setCursor")(Qt.WaitCursor)
    assert label.calls[0][1][0] is Qt.WaitCursor, "most-derived empty entry wins"
    assert type(widget.calls[0][1][0]) is QCursor


def test_resolve_when_palette_two_argument_form_then_colour_wrapped():
    palette = QPalette()
    resolve(palette, "setColor")(QPalette.Window, Qt.red)
    ((_, (role, colour), _),) = palette.calls
    assert role is QPalette.Window, "the role enum is not a value class here"
    assert type(colour) is QColor and colour.color is Qt.red


def test_resolve_when_palette_three_argument_form_then_selected_by_arity():
    palette = QPalette()
    resolve(palette, "setColor")(QPalette.Active, Qt.red, Qt.red)
    ((_, (group, role, colour), _),) = palette.calls
    assert group is QPalette.Active
    assert role is Qt.red, "index 1 converts only in the 2-argument form"
    assert type(colour) is QColor


def _counting_lookups(monkeypatch):
    lookups = []
    real = _app_conversions._lookup

    def counting(root, path):
        lookups.append(path)
        return real(root, path)

    monkeypatch.setattr(_app_conversions, "_lookup", counting)
    return lookups


def test_resolve_when_called_again_then_native_paths_not_resolved_again(monkeypatch):
    lookups = _counting_lookups(monkeypatch)
    widget = QWidget()
    resolve(widget, "setCursor")(Qt.WaitCursor)
    first = len(lookups)
    resolve(widget, "setCursor")(Qt.WaitCursor)
    resolve(QLabel(), "setCursor")(Qt.WaitCursor)
    assert first > 50, f"setCursor has many candidate classes ({first} lookups)"
    assert len(lookups) == first, "each native path is resolved once per PythonQt"
    assert type(widget.calls[1][1][0]) is QCursor


def test_resolve_when_pythonqt_module_replaced_then_cache_not_reused(
    monkeypatch, native
):
    resolve(QWidget(), "setCursor")(Qt.WaitCursor)
    replacement = ModuleType("PythonQt")
    replacement.QtCore, replacement.QtGui = native.QtCore, ModuleType("PythonQt.QtGui")
    monkeypatch.setitem(sys.modules, "PythonQt", replacement)
    widget = QWidget()
    resolve(widget, "setCursor")(Qt.WaitCursor)
    assert widget.calls[0][1][0] is Qt.WaitCursor, (
        "QCursor is absent from the new module: classes come from it, fail closed"
    )


def test_compat_when_new_code_passes_enum_then_wrapped():
    widget = QWidget()
    compat.pyside_method(widget, "setCursor")(Qt.WaitCursor)
    assert type(widget.calls[0][1][0]) is QCursor


def test_run_app_when_pyside_source_passes_enums_then_value_classes_reach_native(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(
        """from PySide2.QtCore import QEasingCurve, QVariantAnimation, Qt
from PySide2.QtNetwork import QHostAddress, QTcpServer
from PySide2.QtWidgets import QWidget
animation = QVariantAnimation()
animation.setEasingCurve(QEasingCurve.OutElastic)
server = QTcpServer()
server.listen(QHostAddress.LocalHost, 0)
widget = QWidget()
widget.setCursor(Qt.WaitCursor)
"""
    )
    handle = run_app(path)
    ns = handle.namespace
    assert type(ns["animation"].calls[0][1][0]) is QEasingCurve
    assert type(ns["server"].calls[0][1][0]) is QHostAddress
    assert type(ns["widget"].calls[0][1][0]) is QCursor
    assert type(ns["animation"]) is QVariantAnimation, "class identity is native"
    handle.close()
