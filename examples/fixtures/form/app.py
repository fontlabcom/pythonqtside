# this_file: examples/fixtures/form/app.py
# SPDX-License-Identifier: Apache-2.0
"""A small PySide2 form: line edit, spin box, combo box, check box and buttons."""

import sys

from PySide2 import QtCore, QtWidgets


class GlyphRequest(QtWidgets.QDialog):
    submitted = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Glyph request")
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Glyph name")
        self.point_size = QtWidgets.QSpinBox()
        self.point_size.setRange(6, 144)
        self.point_size.setValue(12)
        self.style_box = QtWidgets.QComboBox()
        self.style_box.addItems(["Regular", "Bold", "Italic"])
        self.outline = QtWidgets.QCheckBox("Outline")
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Name", self.name_edit)
        layout.addRow("Size", self.point_size)
        layout.addRow("Style", self.style_box)
        layout.addRow(self.outline)
        layout.addRow(self.buttons)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.values = None

    @QtCore.Slot()
    def submit(self):
        self.values = {
            "name": self.name_edit.text(),
            "size": self.point_size.value(),
            "style": self.style_box.currentText(),
            "outline": self.outline.isChecked(),
        }
        self.submitted.emit(self.values)
        self.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    form = GlyphRequest()
    form.show()
    sys.exit(app.exec_())
