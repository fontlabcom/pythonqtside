# this_file: tests/test_example_dialog.py
"""examples/pyside2_dialog.py imports, constructs and runs against PythonQt doubles (not native proof)."""

# ruff: noqa: F811 - pytest fixtures imported from sibling test modules

import sys
from pathlib import Path
from typing import ClassVar

import pytest
from test_app_runner import QWidget, Signal, native  # noqa: F401

from pythonqtside import run_app

EXAMPLE = Path(__file__).parents[1] / "examples/pyside2_dialog.py"


class QDialog(QWidget):
    __module__ = "PythonQt.QtGui"


class QLabel(QWidget):
    __module__ = "PythonQt.QtGui"

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.text_value = text

    def setText(self, text):
        self.text_value = text


class QPushButton(QWidget):
    __module__ = "PythonQt.QtGui"
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(parent)


class QVBoxLayout:
    __module__ = "PythonQt.QtGui"

    def __init__(self, parent=None):
        self.widgets = []

    def addWidget(self, widget):
        self.widgets.append(widget)


class QFileDialog:
    __module__ = "PythonQt.QtGui"
    answer: ClassVar[str] = "/tmp/Font.ufo"

    @staticmethod
    def getOpenFileName(*args):
        return QFileDialog.answer


@pytest.fixture(autouse=True)
def widgets(native):
    qt = sys.modules["PythonQt"]
    for cls in (QDialog, QLabel, QPushButton, QVBoxLayout, QFileDialog):
        setattr(qt.QtGui, cls.__name__, cls)
    QFileDialog.answer = "/tmp/Font.ufo"


def test_example_when_run_then_dialog_is_built_and_shown():
    handle = run_app(EXAMPLE)
    dialog = handle.namespace["dialog"]
    assert dialog.title == "Open a font" and dialog.shown
    assert dialog.label.text_value == "No file chosen"
    handle.close()


@pytest.mark.parametrize(
    "answer,expected", [("/tmp/Font.ufo", "/tmp/Font.ufo"), ("", "No file chosen")]
)
def test_example_when_button_clicked_then_label_shows_path_from_tuple(answer, expected):
    QFileDialog.answer = answer
    handle = run_app(EXAMPLE)
    dialog = handle.namespace["dialog"]
    dialog.button.clicked.emit()
    assert dialog.label.text_value == expected
    handle.close()
