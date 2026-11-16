# this_file: examples/fixtures/lifetime/app.py
# SPDX-License-Identifier: Apache-2.0
"""Open a delete-on-close child dialog, close it, and open it again."""

import sys

from PySide2 import QtCore, QtWidgets


class Child(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Child")


class Main(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parent")
        self.opened = 0
        self.destroyed_children = 0
        self.child = None
        self.button = QtWidgets.QPushButton("Open child", self)
        self.button.clicked.connect(self.open_child)

    def open_child(self):
        self.child = Child(self)
        self.child.destroyed.connect(self.child_destroyed)
        self.child.show()
        self.opened += 1

    def child_destroyed(self, *args):
        self.destroyed_children += 1
        self.child = None


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = Main()
    main.show()
    sys.exit(app.exec_())
