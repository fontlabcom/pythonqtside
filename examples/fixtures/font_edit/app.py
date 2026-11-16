# this_file: examples/fixtures/font_edit/app.py
# SPDX-License-Identifier: Apache-2.0
"""A PySide2 panel that sets a glyph's advance width in FontLab's current font."""

import sys

import fontlab
from PySide2 import QtCore, QtWidgets


class AdvanceWidthPanel(QtWidgets.QWidget):
    applied = QtCore.Signal(float)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advance width")
        self.name_edit = QtWidgets.QLineEdit(".notdef")
        self.width_box = QtWidgets.QSpinBox()
        self.width_box.setRange(0, 4000)
        self.apply_button = QtWidgets.QPushButton("Apply")
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.width_box)
        layout.addWidget(self.apply_button)
        self.name_edit.editingFinished.connect(self.load)
        self.apply_button.clicked.connect(self.apply)
        self.load()

    def glyph(self):
        package = fontlab.flWorkspace.instance().currentPackage
        return package.findName(self.name_edit.text())

    def master_layer(self, glyph):
        return glyph.layers[0]  # a one-master tool: the first master layer

    @QtCore.Slot()
    def load(self):
        self.width_box.setValue(int(self.master_layer(self.glyph()).advanceWidth))

    @QtCore.Slot()
    def apply(self):
        glyph = self.glyph()
        layer = self.master_layer(glyph)
        layer.advanceWidth = self.width_box.value()
        # One Edit > Undo step: the changed layers, then their glyph, in one list.
        fontlab.flItems().notifyChangesApplied("Set advance width", [layer, glyph])
        self.applied.emit(layer.advanceWidth)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    panel = AdvanceWidthPanel()
    panel.show()
    sys.exit(app.exec_())
