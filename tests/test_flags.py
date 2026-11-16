# this_file: tests/test_flags.py
"""QFlags wrapping where a native enum overload would win; doubles, not proof."""

import json
import sys
from pathlib import Path

import pytest
from test_app_runner import QWidget, native, script  # noqa: F401

from pythonqtside import _app_flags, run_app
from pythonqtside._app_native import resolve
from pythonqtside.tooling.flags import analyze

ROOT = Path(__file__).parents[1] / "src/pythonqtside"


def _enum(name):
    return type(name, (int,), {"__module__": "PythonQt.QtGui"})


class QDialogButtonBox(QWidget):
    __module__ = "PythonQt.QtGui"
    StandardButton = _enum("StandardButton")

    class StandardButtons(int):
        __module__ = "PythonQt.QtGui"

    def __init__(self, *args):
        super().__init__()
        self.args = args


QDialogButtonBox.Ok = QDialogButtonBox.StandardButton(1024)
QDialogButtonBox.Cancel = QDialogButtonBox.StandardButton(4194304)
Orientation = _enum("Orientation")
HORIZONTAL = Orientation(1)

TABLE = {
    "__init__": (
        (
            "QtGui.QDialogButtonBox",
            {
                "static": False,
                "positions": [
                    {
                        "index": 0,
                        "arities": [1, 2],
                        "flags": "QtGui.QDialogButtonBox.StandardButtons",
                        "keep": ["QtCore.Qt.Orientation"],
                    }
                ],
            },
        ),
    )
}


@pytest.fixture(autouse=True)
def flags(native, monkeypatch):  # noqa: F811 - after the PythonQt double
    qt = sys.modules["PythonQt"]
    qt.QtGui.QDialogButtonBox = QDialogButtonBox
    sys.modules["fontlab_echopy.PythonQt.QtGui"].QDialogButtonBox = QDialogButtonBox
    qt.QtCore.Qt = type("Qt", (), {"Orientation": Orientation})
    monkeypatch.setattr(_app_flags, "_table", lambda: TABLE)


def test_run_app_when_or_of_buttons_then_flags_class_passed(tmp_path):
    source = """from PySide2 import QtWidgets
B = QtWidgets.QDialogButtonBox
both = B(B.Ok | B.Cancel)
one = B(B.Ok)
class Box(B):
    def __init__(self):
        super().__init__(B.Ok | B.Cancel)
box = Box()
"""
    ns = run_app(script(tmp_path, source)).namespace
    (value,) = ns["both"].args
    assert type(value) is QDialogButtonBox.StandardButtons and value == 4195328
    assert type(ns["one"].args[0]) is QDialogButtonBox.StandardButtons
    assert type(ns["box"].args[0]) is QDialogButtonBox.StandardButtons


def test_convert_when_competing_enum_or_bool_then_unchanged():
    args = _app_flags.convert(QDialogButtonBox, "__init__", (HORIZONTAL,))
    assert args[0] is HORIZONTAL, "the Orientation overload keeps its enum"
    assert _app_flags.convert(QDialogButtonBox, "__init__", (True,))[0] is True
    assert _app_flags.convert(QDialogButtonBox, "__init__", (1, 2, 3)) == (1, 2, 3)


def test_resolve_when_method_not_in_table_then_unchanged():
    widget = QDialogButtonBox()
    assert resolve(widget, "close") == widget.close


def test_analyze_when_flags_compete_with_enum_then_position_recorded():
    pyside = {
        "QtWidgets": b"""
class QDialogButtonBox(PySide2.QtWidgets.QWidget):
    class StandardButton(object):
        Ok: QDialogButtonBox.StandardButton = ...
    class StandardButtons(object): ...
    def __init__(self, buttons: PySide2.QtWidgets.QDialogButtonBox.StandardButtons, parent: QWidget=...) -> None: ...
    def __init__(self, orientation: PySide2.QtCore.Qt.Orientation, parent: QWidget=...) -> None: ...
    def setCount(self, count: int) -> None: ...
""",
        "QtCore": b"""
class Qt(Shiboken.Object):
    class Orientation(object):
        Horizontal: Qt.Orientation = ...
""",
    }
    route = {"native_module": "QtGui", "differences": {"nested_enums": {}}}
    inventory = {
        "modules": {
            "QtWidgets": {"classes": {"QDialogButtonBox": route}},
            "QtCore": {"classes": {"Qt": {"native_module": "QtCore"}}},
        }
    }
    report = analyze(inventory, pyside, "sha")
    (position,) = report["classes"]["QtGui.QDialogButtonBox"]["__init__"]["positions"]
    assert position == {
        "index": 0,
        "arities": [1, 2],
        "flags": "QtGui.QDialogButtonBox.StandardButtons",
        "keep": ["QtCore.Qt.Orientation"],
    }


def test_committed_flags_table_when_loaded_then_button_box_and_message_box_listed():
    data = json.loads((ROOT / "_flags.json").read_text())
    assert "__init__" in data["classes"]["QtGui.QDialogButtonBox"]
    assert "question" in data["classes"]["QtGui.QMessageBox"]
    assert data["counts"]["positions"] == 12
