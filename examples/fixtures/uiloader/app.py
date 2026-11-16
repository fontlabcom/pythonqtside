# this_file: examples/fixtures/uiloader/app.py
# SPDX-License-Identifier: Apache-2.0
"""Load a Designer .ui file with QUiLoader and wire its widgets."""

import os
import sys

from PySide2 import QtCore, QtUiTools, QtWidgets


def load_form():
    loader = QtUiTools.QUiLoader()
    ui_file = QtCore.QFile(os.path.join(os.path.dirname(__file__), "form.ui"))
    ui_file.open(QtCore.QFile.ReadOnly)
    form = loader.load(ui_file)
    ui_file.close()
    return form


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = load_form()
    name_edit = window.findChild(QtWidgets.QLineEdit, "nameEdit")
    status = window.findChild(QtWidgets.QLabel, "statusLabel")
    button = window.findChild(QtWidgets.QPushButton, "okButton")
    button.clicked.connect(lambda: status.setText("Hello, " + name_edit.text()))
    window.show()
    sys.exit(app.exec_())
