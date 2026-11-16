# this_file: examples/fixtures/signals/app.py
# SPDX-License-Identifier: Apache-2.0
"""Custom Signal/Slot/Property declarations, an event filter and virtual overrides."""

import sys

from PySide2 import QtCore, QtWidgets


class Counter(QtCore.QObject):
    valueChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0

    def getValue(self):
        return self._value

    def setValue(self, value):
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    value = QtCore.Property(int, getValue, setValue, notify=valueChanged)

    @QtCore.Slot()
    def increment(self):
        self.setValue(self._value + 1)


class KeyFilter(QtCore.QObject):
    """Records key presses on the watched widget and swallows the X key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.keys = []

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            self.keys.append(event.key())
            return event.key() == QtCore.Qt.Key_X
        return super().eventFilter(watched, event)


class Panel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signals and overrides")
        self.events = []
        self.counter = Counter(self)
        self.label = QtWidgets.QLabel("0", self)
        self.edit = QtWidgets.QLineEdit(self)
        self.edit.move(0, 30)
        self.key_filter = KeyFilter(self)
        self.edit.installEventFilter(self.key_filter)
        self.counter.valueChanged.connect(self.show_value)

    @QtCore.Slot(int)
    def show_value(self, value):
        self.label.setText(str(value))

    def showEvent(self, event):
        self.events.append("show")
        super().showEvent(event)

    def resizeEvent(self, event):
        self.events.append(("resize", event.size().width()))
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        self.events.append(("key", event.key()))
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.events.append("close")
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = Panel()
    panel.resize(240, 80)
    panel.show()
    sys.exit(app.exec_())
