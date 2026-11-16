# this_file: tests/test_inventory_routing.py
"""Check every committed route against distinct fake native objects."""

import sys
from types import ModuleType

import pytest

from pythonqtside import _routing


@pytest.fixture
def targets(monkeypatch):
    modules = {}
    for module, data in _routing.INVENTORY["native_modules"].items():
        target = ModuleType("fontlab_echopy.PythonQt." + module)
        for name in data["classes"] + data["members"]:
            setattr(target, name, object())
        modules[module] = target
        monkeypatch.setitem(sys.modules, target.__name__, target)
    return modules


def test_all_committed_routes_when_native_present_then_identity_and_dir_match(targets):
    for module, data in _routing.INVENTORY["modules"].items():
        for name, route in (data["classes"] | data["members"]).items():
            if route["native_module"] is None:
                with pytest.raises(
                    AttributeError, match="not available in FontLab's PythonQt"
                ):
                    _routing.member(module, name)
                assert name not in _routing.names(module), (module, name)
            else:
                expected = getattr(targets[route["native_module"]], name)
                assert _routing.member(module, name) is expected, (module, name)
                assert name in _routing.names(module), (module, name)


@pytest.mark.parametrize(
    ("module", "name", "family"),
    [
        ("QtGui", "QWidget", "QtWidgets"),
        ("QtWidgets", "QColor", "QtGui"),
        ("QtGui", "QStringListModel", "QtCore"),
        ("QtCore", "QNetworkAccessManager", "QtNetwork"),
        ("QtWidgets", "QSvgWidget", "QtSvg"),
        ("QtGui", "QTreeWidgetItemIterator", "QtWidgets"),
    ],
)
def test_wrong_family_when_requested_then_identifies_owner(
    targets, module, name, family
):
    with pytest.raises(AttributeError, match=f"exposed by pythonqtside.{family}"):
        _routing.member(module, name)
    assert name not in _routing.names(module)


def test_native_extensions_passthrough_but_absent_names_are_unknown(targets):
    targets["QtCore"].Invented = object()
    assert _routing.member("QtCore", "Invented") is targets["QtCore"].Invented
    assert "Invented" in _routing.names("QtCore")
    with pytest.raises(AttributeError, match="has no known name 'Unknown'"):
        _routing.member("QtCore", "Unknown")
    assert "Unknown" not in _routing.names("QtCore")


def test_native_class_absent_since_capture_then_reports_unavailable(targets):
    del targets["QtGui"].QWidget
    with pytest.raises(AttributeError, match="not available in FontLab's PythonQt"):
        _routing.member("QtWidgets", "QWidget")
    assert "QWidget" not in _routing.names("QtWidgets")


def test_qobject_when_core_present_then_prefers_it_and_keeps_native_helpers(targets):
    targets["QtCore"].QObject = object()
    assert _routing.member("QtCore", "QObject") is targets["QtCore"].QObject
    for name in ("Signal", "Slot", "Property"):
        assert _routing.member("QtCore", name) is getattr(targets["QtCore"], name)
    assert _routing.member("Qt", "QWidget") is targets["Qt"].QWidget
    assert _routing.member("QtGui", "QPrinter") is targets["QtGui"].QPrinter


def test_target_module_unavailable_then_attribute_error_not_import_error(
    targets, monkeypatch
):
    original = _routing.import_module

    def unavailable(name):
        if name.endswith("QtSvg"):
            raise ModuleNotFoundError(name, name=name)
        return original(name)

    monkeypatch.setattr(_routing, "import_module", unavailable)
    with pytest.raises(AttributeError, match="not available in FontLab's PythonQt"):
        _routing.member("QtSvg", "QSvgWidget")
    assert _routing.names("QtSvg") == []


def test_unrelated_dependency_import_error_is_not_hidden(targets, monkeypatch):
    def broken(name):
        raise ModuleNotFoundError("broken dependency", name="broken_dependency")

    monkeypatch.setattr(_routing, "import_module", broken)
    with pytest.raises(ModuleNotFoundError, match="broken dependency"):
        _routing.member("QtSvg", "QSvgWidget")


def test_qobject_when_private_also_absent_then_reports_unavailable(targets):
    del targets["private"].QObject
    with pytest.raises(AttributeError, match="not available in FontLab's PythonQt"):
        _routing.member("QtCore", "QObject")
    assert "QObject" not in _routing.names("QtCore")


def test_widgets_when_native_has_extra_name_then_does_not_leak(targets):
    targets["QtGui"].UnknownWidget = object()
    with pytest.raises(AttributeError, match="has no known name 'UnknownWidget'"):
        _routing.member("QtWidgets", "UnknownWidget")
    assert "UnknownWidget" not in _routing.names("QtWidgets")
