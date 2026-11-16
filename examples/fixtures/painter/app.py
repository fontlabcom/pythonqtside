# this_file: examples/fixtures/painter/app.py
# SPDX-License-Identifier: Apache-2.0
"""QPainter drawing driven by mouse clicks and a key press."""

import sys

from PySide2 import QtCore, QtGui, QtWidgets


class Canvas(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Canvas")
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.resize(200, 120)
        self.points = []
        self.colour = QtGui.QColor("black")
        self.paints = 0

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("white"))
        painter.setPen(QtGui.QPen(self.colour, 9))
        for point in self.points:
            painter.drawPoint(point)
        painter.end()
        self.paints += 1

    def mousePressEvent(self, event):
        self.points.append(event.pos())
        self.update()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_R:
            self.colour = QtGui.QColor("red")
            self.update()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    canvas = Canvas()
    canvas.show()
    sys.exit(app.exec_())
