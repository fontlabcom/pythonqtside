# this_file: tests/test_captured_adapters.py
"""Direct, captured and super calls get the same measured adapters.

Doubles stand in for PythonQt classes at the paths the real generated tables use;
methods are bound ``builtin_qt_slot`` objects with ``__self__``/``__name__`` as
measured (pqs-g04/review1/probe_slot_signal_meta.json). They model, not prove.
"""

import sys
from types import ModuleType

import pytest

from pythonqtside import run_app
from pythonqtside._app import _ACTIVE_HANDLES


class builtin_qt_slot:
    def __init__(self, owner, name, function):
        self.__self__, self.__name__, self.function = owner, name, function

    def __call__(self, *args, **kwargs):
        if kwargs:
            raise ValueError("called slot does not support kwargs")
        return self.function(self.__self__, *args)


class slot:
    """Descriptor: bound native slots on instances, and on the class for statics."""

    def __init__(self, function):
        self.function = function

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        return builtin_qt_slot(
            owner if instance is None else instance, self.name, self.function
        )


class BoolResult:
    __module__ = "PythonQt"

    def __init__(self):
        self.value = False

    def __bool__(self):
        return self.value


class QLocale:
    __module__ = "PythonQt.QtCore"

    @slot
    def toInt(self, s, ok=None):
        if ok is not None:
            ok.value = s.isdigit()
        return int(s)


class QEasingCurve:
    __module__ = "PythonQt.QtCore"
    Type = type("Type", (int,), {"__module__": "PythonQt.QtCore"})

    def __init__(self, value):
        self.value = value


QEasingCurve.OutElastic = QEasingCurve.Type(30)


class QVariantAnimation:
    __module__ = "PythonQt.QtCore"

    def __init__(self):
        self.received = []

    @slot
    def setEasingCurve(self, easing):
        self.received.append(easing)


class QMessageBox:
    __module__ = "PythonQt.QtGui"
    StandardButton = type("StandardButton", (int,), {"__module__": "PythonQt.QtGui"})
    StandardButtons = type("StandardButtons", (int,), {"__module__": "PythonQt.QtGui"})
    received: list = []  # noqa: RUF012 - class-level record of static calls

    @slot
    def question(cls, *args):
        QMessageBox.received.append(args)
        return QMessageBox.StandardButton(1024)


QMessageBox.Ok = QMessageBox.StandardButton(1024)
QMessageBox.Cancel = QMessageBox.StandardButton(4194304)


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.BoolResult = BoolResult
    qt.QtCore = ModuleType("PythonQt.QtCore")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    for cls in (QLocale, QEasingCurve, QVariantAnimation):
        setattr(qt.QtCore, cls.__name__, cls)
    qt.QtGui.QMessageBox = QMessageBox
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    for name in ("QtCore", "QtGui"):
        monkeypatch.setitem(
            sys.modules, f"fontlab_echopy.PythonQt.{name}", getattr(qt, name)
        )
    monkeypatch.setattr(_app_native, "host_application", lambda: (QLocale(), ()))
    QMessageBox.received = []
    yield
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


def _run(tmp_path, source):
    path = tmp_path / "app.py"
    path.write_text(source)
    return run_app(path).namespace


@pytest.mark.parametrize("prefix", ["", "s="])
def test_out_parameter_when_call_direct_or_captured_then_same_tuple(tmp_path, prefix):
    ns = _run(
        tmp_path,
        f"""from PySide2.QtCore import QLocale
locale = QLocale()
direct = locale.toInt({prefix}"42")
convert = locale.toInt
captured = convert({prefix}"42")
""",
    )
    assert ns["direct"] == (42, True)
    assert ns["captured"] == ns["direct"], "captured call keeps (value, ok)"


@pytest.mark.parametrize("prefix", ["", "easing="])
def test_conversion_when_call_direct_or_captured_then_value_class(tmp_path, prefix):
    ns = _run(
        tmp_path,
        f"""from PySide2.QtCore import QEasingCurve, QVariantAnimation
animation = QVariantAnimation()
animation.setEasingCurve({prefix}QEasingCurve.OutElastic)
set_easing = animation.setEasingCurve
set_easing({prefix}QEasingCurve.OutElastic)
""",
    )
    direct, captured = ns["animation"].received
    assert type(direct) is QEasingCurve and direct.value == 30
    assert type(captured) is QEasingCurve, "captured call converts the enum"


@pytest.mark.parametrize("keywords", [False, True])
def test_flags_when_call_direct_or_captured_then_flags_class(tmp_path, keywords):
    arguments = (
        'None, "t", "q", '
        f'{"buttons=" if keywords else ""}QMessageBox.Ok | QMessageBox.Cancel, '
        f'{"defaultButton=" if keywords else ""}QMessageBox.Ok'
    )
    _run(
        tmp_path,
        f"""from PySide2.QtWidgets import QMessageBox
QMessageBox.question({arguments})
ask = QMessageBox.question
ask({arguments})
""",
    )
    direct, captured = QMessageBox.received
    assert type(direct[3]) is QMessageBox.StandardButtons and direct[3] == 4195328
    assert type(captured[3]) is QMessageBox.StandardButtons, "captured call wraps flags"


@pytest.mark.parametrize("keywords", [False, True])
@pytest.mark.parametrize("captured", [False, True])
def test_run_app_when_super_calls_native_adapters_then_base_dispatch_kept(
    tmp_path, keywords, captured
):
    ns = _run(
        tmp_path,
        f"""from PySide2.QtCore import QLocale, QEasingCurve, QVariantAnimation
class Locale(QLocale):
    def toInt(self, text):
        {"convert = super().toInt" if captured else ""}
        return {"convert" if captured else "super().toInt"}({"s=" if keywords else ""}text)
class Animation(QVariantAnimation):
    def setEasingCurve(self, value):
        {"convert = super().setEasingCurve" if captured else ""}
        return {"convert" if captured else "super().setEasingCurve"}({"easing=" if keywords else ""}value)
result = Locale().toInt("42")
animation = Animation()
animation.setEasingCurve(QEasingCurve.OutElastic)
""",
    )
    assert ns["result"] == (42, True), "super call keeps the out-parameter adapter"
    easing, = ns["animation"].received
    assert type(easing) is QEasingCurve and easing.value == 30, (
        "super call converts the enum even when a Python override exists"
    )


@pytest.mark.parametrize("keywords", [False, True])
def test_resolve_when_super_lookup_missing_then_fallback_gets_adapters(keywords):
    from pythonqtside._app_native import resolve

    class MissingSuper(super):
        def __getattribute__(self, name):
            if name in {"toInt", "setEasingCurve"}:
                raise AttributeError(name)
            return super().__getattribute__(name)

    # PythonQt class-level lookup supplies the unbound slot for the fallback.
    class NativeLocale(QLocale):
        __module__ = "PythonQt.QtCore"

        def toInt(self, *args):
            return QLocale.toInt.function(self, *args)

    class NativeAnimation(QVariantAnimation):
        __module__ = "PythonQt.QtCore"

        def setEasingCurve(self, *args):
            return QVariantAnimation.setEasingCurve.function(self, *args)

    class Locale(NativeLocale):
        pass

    class Animation(NativeAnimation):
        pass

    locale, animation = Locale(), Animation()
    convert = resolve(MissingSuper(Locale, locale), "toInt", keywords)
    result = convert(s="42") if keywords else convert("42")
    assert result == (42, True), "fallback keeps the out-parameter adapter"
    easing = resolve(MissingSuper(Animation, animation), "setEasingCurve", keywords)
    if keywords:
        easing(easing=QEasingCurve.OutElastic)
    else:
        easing(QEasingCurve.OutElastic)
    assert type(animation.received[0]) is QEasingCurve, "fallback converts enums"
