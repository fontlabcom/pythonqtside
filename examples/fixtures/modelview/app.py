# this_file: examples/fixtures/modelview/app.py
# SPDX-License-Identifier: Apache-2.0
"""A table model with an editable column and a spin-box delegate."""

import sys

from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import Qt


class GlyphModel(QtCore.QAbstractTableModel):
    HEADERS = ("Glyph", "Advance")

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.rows = rows

    def rowCount(self, parent=QtCore.QModelIndex()):  # noqa: B008 - PySide2 idiom
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):  # noqa: B008 - PySide2 idiom
        return 0 if parent.isValid() else 2

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role in (Qt.DisplayRole, Qt.EditRole):
            return self.rows[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.column() == 1:
            flags |= Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or index.column() != 1:
            return False
        self.rows[index.row()][1] = int(value)
        self.dataChanged.emit(index, index)
        return True


class AdvanceDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QtWidgets.QSpinBox(parent)
        editor.setRange(0, 2000)
        return editor

    def setEditorData(self, editor, index):
        editor.setValue(int(index.data()))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value(), Qt.EditRole)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    model = GlyphModel([["A", 600], ["B", 620]])
    view = QtWidgets.QTableView()
    view.setModel(model)
    delegate = AdvanceDelegate(view)
    view.setItemDelegateForColumn(1, delegate)
    view.resize(260, 120)
    view.show()
    sys.exit(app.exec_())
