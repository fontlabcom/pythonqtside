# this_file: examples/unchanged_app/app.py
# SPDX-License-Identifier: Apache-2.0
"""Owned standalone PySide2 example; the embedded runner reads it unchanged."""

import sys

from PySide2 import QtCore, QtWidgets


class ExampleWindow(QtWidgets.QWidget):
    updated = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pythonqtside unchanged PySide2 example")
        self.resize(420, 140)
        layout = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel("Click to load a local helper", self)
        self.button = QtWidgets.QPushButton("Update label", self)
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.button.clicked.connect(self.update_label)
        self.updated.connect(self.label.setText)
        self.update_count = 0
        self.last_width = 0
        self.last_text = ""

    @QtCore.Slot()
    def update_label(self):
        import helper

        self.last_width = self.width()
        self.updated.emit(helper.message(self.last_width))
        self.last_text = self.label.text()
        self.update_count += 1


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ExampleWindow()
    window.show()
    sys.exit(app.exec_())
