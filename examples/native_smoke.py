# this_file: examples/native_smoke.py
"""Run inside FontLab; no second application or open-font changes."""
from pythonqtside import QtCore, QtWidgets
from PythonQt import private
assert QtCore.QObject is private.QObject
class Emitter(QtCore.QObject):
    fired = QtCore.Signal(int)
parent = QtWidgets.QWidget()
child = Emitter(parent)
try:
    received = []
    callback = received.append
    child.fired.connect(callback)
    child.fired.emit(7)
    child.fired.disconnect(callback)
    child.fired.emit(8)
    assert received == [7] and child.parent() is parent
finally:
    child.deleteLater()
    parent.deleteLater()
