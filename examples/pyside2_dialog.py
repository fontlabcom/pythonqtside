# this_file: examples/pyside2_dialog.py
"""A plain PySide2 dialog. Run it unchanged in FontLab:

    from pythonqtside import run_app
    handle = run_app("examples/pyside2_dialog.py")   # keep `handle`; handle.close() cleans up

It uses a subclass, a layout, a signal connection and the (path, filter) result of
QFileDialog.getOpenFileName, which PythonQt returns as a bare path.
"""
from PySide2 import QtWidgets


class OpenDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open a font")
        self.label = QtWidgets.QLabel("No file chosen")
        self.button = QtWidgets.QPushButton("Choose...")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.button.clicked.connect(self.choose)

    def choose(self):
        path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open", "", "UFO (*.ufo)"
        )
        self.label.setText(path or "No file chosen")


dialog = OpenDialog()
dialog.show()
