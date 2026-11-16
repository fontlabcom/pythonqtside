# this_file: tests/test_routing.py
"""Measured namespace routing, without claiming full binding compatibility."""
import sys
import types

import pytest


def test_widget_inventory_routes_widget_classes_without_gui_leak(monkeypatch):
    from pythonqtside import QtGui, QtWidgets
    native = types.ModuleType('fontlab_echopy.PythonQt.QtGui')
    native.QWidget = type('QWidget',(),{})
    native.QColor = type('QColor',(),{})
    monkeypatch.setitem(sys.modules,native.__name__,native)
    assert QtWidgets.QWidget is native.QWidget
    assert QtGui.QColor is native.QColor
    with pytest.raises(AttributeError):
        QtWidgets.QColor
    with pytest.raises(AttributeError):
        QtGui.QWidget
    assert 'QWidget' in dir(QtWidgets) and 'QColor' not in dir(QtWidgets)


def test_qobject_uses_actual_private_native_class_and_signals_are_unchanged(monkeypatch):
    from pythonqtside import QtCore
    native = types.ModuleType('fontlab_echopy.PythonQt.QtCore')
    native.Signal = object()
    private = types.ModuleType('fontlab_echopy.PythonQt.private')
    private.QObject = type('QObject',(),{})
    monkeypatch.setitem(sys.modules,native.__name__,native)
    monkeypatch.setitem(sys.modules,private.__name__,private)
    assert QtCore.QObject is private.QObject
    assert QtCore.Signal is native.Signal
    with pytest.raises(AttributeError):
        QtCore.NotAnActualClass


def test_unknown_namespace_raises_without_fake_modules():
    import pythonqtside
    with pytest.raises(AttributeError):
        pythonqtside.QtImaginary
