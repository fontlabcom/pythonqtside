# this_file: tests/test_keywords.py
"""PySide2 keyword arguments mapped to positions; doubles model PythonQt, not prove it."""

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

from pythonqtside import _app_keywords, compat, run_app
from pythonqtside._app import _ACTIVE_HANDLES
from pythonqtside._app_keywords import map_keywords
from pythonqtside._app_native import resolve
from pythonqtside.tooling.keywords import analyze, qt_defaults

ROOT = Path(__file__).parents[1] / "src/pythonqtside"


class Signal:
    """Measured PythonQt signal wrapper: type identity with PythonQt.QtCore.Signal."""

    __module__ = "QtCore"

    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self, *args):
        for callback in self.callbacks[:]:
            callback(*args)

    __call__ = emit  # callable, so resolve() must recognise it as a signal


class builtin_qt_slot:
    """Bound native slot: exposes __self__ and __name__, rejects keywords."""

    def __init__(self, owner, name, function):
        self.__self__, self.__name__, self.function = owner, name, function

    def __call__(self, *args, **kwargs):
        if kwargs:
            raise ValueError("called slot does not support kwargs")
        return self.function(self.__self__, *args)


class NativeSlot:
    """Class-level descriptor producing bound native slots, as PythonQt does."""

    def __init__(self, function):
        self.function = function

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return builtin_qt_slot(instance, self.name, self.function)


class Native:
    """Rejects keywords like PythonQt; records positional calls."""

    __module__ = "PythonQt.QtGui"
    properties = ("text", "interval")
    made: ClassVar[list] = []

    def __init__(self, *args, **kwargs):
        if kwargs:
            raise ValueError("called slot does not support kwargs")
        self.args, self.calls, self.props, self.owner = args, [], {}, None
        self.clicked = Signal()
        self.deleted = False
        Native.made.append(self)

    def metaObject(self):
        return self

    def indexOfProperty(self, name):
        return 1 if name in self.properties else -1

    def setProperty(self, name, value):
        self.props[name] = value
        return True

    def parent(self):
        return self.owner

    def setParent(self, parent):
        self.owner = parent

    def deleteLater(self):
        self.deleted = True

    def inherits(self, name):
        return name == "QWidget"

    def close(self):
        pass

    @NativeSlot
    def resize(self, *args):
        self.calls.append(("resize", args))

    def show(self):
        pass


class QLabel(Native):
    __module__ = "PythonQt.QtGui"


class QTimer(Native):
    __module__ = "PythonQt.QtCore"


class QFileDialog(Native):
    __module__ = "PythonQt.QtGui"
    calls: ClassVar[list] = []

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        if kwargs:
            raise ValueError("called slot does not support kwargs")
        QFileDialog.calls.append(args)
        return "path"


class QLineEdit(Native):
    __module__ = "PythonQt.QtGui"
    Normal = object()


TABLE = {
    "__init__": (
        (
            "QtGui.QLabel",
            {
                "static": False,
                "overloads": [
                    {"parameters": ["parent", "f"], "required": 0, "defaults": {}},
                    {
                        "parameters": ["text", "parent", "f"],
                        "required": 1,
                        "defaults": {},
                    },
                ],
            },
        ),
        (
            "QtCore.QTimer",
            {
                "static": False,
                "overloads": [
                    {"parameters": ["parent"], "required": 0, "defaults": {}}
                ],
            },
        ),
    ),
    "resize": (
        (
            "QtGui.QLabel",
            {
                "static": False,
                "overloads": [
                    {"parameters": ["arg__1"], "required": 1, "defaults": {}},
                    {"parameters": ["w", "h"], "required": 2, "defaults": {}},
                ],
            },
        ),
    ),
    "getSaveFileName": (
        (
            "QtGui.QFileDialog",
            {
                "static": True,
                "overloads": [
                    {
                        "parameters": ["parent", "caption", "dir", "filter", "mode"],
                        "required": 0,
                        "defaults": {
                            "parent": None,
                            "caption": "",
                            "dir": "",
                            "mode": {"native": "QtGui.QLineEdit.Normal"},
                        },
                    }
                ],
            },
        ),
    ),
}


@pytest.fixture(autouse=True)
def native(monkeypatch):
    from pythonqtside import _app_native

    qt = ModuleType("PythonQt")
    qt.QtCore = ModuleType("PythonQt.QtCore")
    qt.QtGui = ModuleType("PythonQt.QtGui")
    qt.QtCore.Signal = Signal
    qt.QtCore.QTimer = QTimer
    for cls in (QLabel, QFileDialog, QLineEdit):
        setattr(qt.QtGui, cls.__name__, cls)
    qt.QtGui.QWidget = QLabel
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    for name in ("QtCore", "QtGui"):
        monkeypatch.setitem(
            sys.modules, f"fontlab_echopy.PythonQt.{name}", getattr(qt, name)
        )
    monkeypatch.setattr(_app_keywords, "_table", lambda: TABLE)
    monkeypatch.setattr(_app_native, "host_application", lambda: (QLabel(), ()))
    QFileDialog.calls = []
    yield qt
    for handle in tuple(_ACTIVE_HANDLES):
        handle.close()


ENTRY = TABLE["__init__"][0][1]


def test_map_keywords_when_parent_follows_text_then_positional():
    window = object()
    positional, unused = map_keywords(ENTRY, ("x",), {"parent": window}, leftover=True)
    assert positional == ("x", window) and unused == {}


def test_map_keywords_when_names_fit_no_parameter_then_left_for_properties():
    positional, _ = map_keywords(ENTRY, (), {"text": "x"}, leftover=True)
    assert positional == ("x",), "the text overload places the keyword itself"
    timer = TABLE["__init__"][1][1]
    assert map_keywords(timer, (), {"interval": 5}, leftover=True) == (
        (),
        {"interval": 5},
    )


def test_map_keywords_when_keyword_repeats_positional_then_no_mapping():
    assert map_keywords(ENTRY, ("x",), {"text": "y"}, leftover=False) is None


def test_map_keywords_when_gap_has_no_default_then_no_mapping():
    resize = TABLE["resize"][0][1]
    assert map_keywords(resize, (), {"h": 2}, leftover=False) is None


def test_map_keywords_when_forms_differ_then_ambiguous_and_declined():
    entry = {
        "overloads": [
            {"parameters": ["a", "x"], "required": 0, "defaults": {"a": 1}},
            {"parameters": ["b", "x"], "required": 0, "defaults": {"b": 2}},
        ]
    }
    assert map_keywords(entry, (), {"x": 0}, leftover=False) is None


def test_resolve_when_keyword_call_then_native_receives_positions():
    label = QLabel()
    resolve(label, "resize", keywords=True)(w=10, h=20)
    assert label.calls == [("resize", (10, 20))]


def test_resolve_when_keywords_unmapped_then_native_error_kept():
    label = QLabel()
    with pytest.raises(ValueError, match="does not support kwargs"):
        resolve(label, "resize", keywords=True)(depth=3)


def test_resolve_when_static_gap_then_literal_and_native_defaults_fill():
    resolve(QFileDialog, "getSaveFileName", keywords=True)(None, "Save", filter="*.vfj")
    assert QFileDialog.calls == [(None, "Save", "", "*.vfj")]
    resolve(QFileDialog, "getSaveFileName", keywords=True)(None, "S", "", "", mode=None)
    # the picker adapter reads the fifth PySide2 slot as options and inserts the
    # native selectedFilter "" before it
    assert QFileDialog.calls[1] == (None, "S", "", "", "", None)
    with pytest.raises(ValueError, match="does not support kwargs"):
        resolve(QFileDialog, "getSaveFileName", keywords=True)(mode=QLineEdit.Normal)
    assert len(QFileDialog.calls) == 2, "filter has no default: the gap declines"


def test_resolve_when_native_default_fills_gap_then_resolved_object_passed():
    resolve(QFileDialog, "getSaveFileName", keywords=True)(None, "S", "", "f")
    entry = TABLE["getSaveFileName"][0][1]
    positional, _ = map_keywords(entry, (None,), {"filter": "f"}, leftover=False)
    assert positional == (None, "", "", "f")
    positional, _ = map_keywords(entry, (), {"mode": 7, "filter": "f"}, leftover=False)
    assert positional == (None, "", "", "f", 7)
    entry["overloads"][0]["parameters"].append("tail")
    try:
        entry["overloads"][0]["defaults"]["tail"] = {"native": "QtGui.QLineEdit.Normal"}
        positional, _ = map_keywords(
            entry, (), {"filter": "f", "tail": 1}, leftover=False
        )
        assert positional[4] is QLineEdit.Normal, "native path resolved at call time"
    finally:
        entry["overloads"][0]["parameters"].pop()
        del entry["overloads"][0]["defaults"]["tail"]


def test_resolve_when_native_default_unresolvable_then_declined(monkeypatch):
    entry = TABLE["getSaveFileName"][0][1]
    defaults = dict(
        entry["overloads"][0]["defaults"], filter={"native": "QtGui.Absent.X"}
    )
    monkeypatch.setitem(entry["overloads"][0], "defaults", defaults)
    with pytest.raises(ValueError, match="does not support kwargs"):
        resolve(QFileDialog, "getSaveFileName", keywords=True)(None, "S", "", mode=1)
    assert QFileDialog.calls == [], "an unresolved native default declines the mapping"


def test_resolve_when_attribute_is_native_signal_then_not_wrapped():
    class Toggle(QLabel):
        __module__ = "PythonQt.QtGui"
        toggled = Signal()  # class level, like PythonQt's signal attributes

    signal = resolve(Toggle(), "toggled", keywords=True)
    assert type(signal) is Signal and callable(signal.connect)


def test_resolve_when_signal_connect_then_never_wrapped():
    label = QLabel()
    assert resolve(label.clicked, "connect", keywords=True) == label.clicked.connect


def test_pyside_construct_when_parent_keyword_then_positional():
    window = QLabel()
    label = compat.pyside_construct(QLabel, "Name", parent=window)
    assert label.args == ("Name", window)


def test_pyside_construct_when_property_and_signal_keywords_then_applied():
    seen = []
    timer = compat.pyside_construct(QTimer, interval=50, clicked=seen.append)
    assert timer.args == () and timer.props == {"interval": 50}
    timer.clicked.emit(1)
    assert seen == [1], "a signal keyword connects the callback"


def test_pyside_construct_when_unknown_keyword_then_attribute_error():
    with pytest.raises(AttributeError, match="no Qt property or signal named 'colour'"):
        compat.pyside_construct(QTimer, colour=1)


def test_pyside_construct_when_python_init_then_keywords_untouched():
    class Own(QLabel):
        def __init__(self, title, parent=None):
            super().__init__(title)
            self.parent_seen = parent

    own = compat.pyside_construct(Own, "x", parent="p")
    assert own.parent_seen == "p" and own.args == ("x",)


APP = """from PySide2 import QtCore, QtWidgets
window = QtWidgets.QWidget()
label = QtWidgets.QLabel("Name", parent=window)
label.resize(w=30, h=40)

class Panel(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super().__init__("Panel", parent=parent)

class Old(QtWidgets.QLabel):
    def __init__(self, parent=None):
        QtWidgets.QLabel.__init__(self, "Old", parent=parent)

panel = Panel(parent=window)
old = Old(window)
timer = QtCore.QTimer(interval=25, clicked=label.resize)
"""


def test_run_app_when_pyside_keywords_then_positions_properties_and_tracked_signals(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(APP)
    handle = run_app(path)
    ns = handle.namespace
    window = ns["window"]
    assert ns["label"].args == ("Name", window)
    assert ns["label"].calls == [("resize", (30, 40))]
    assert ns["panel"].args == ("Panel", window), "super().__init__ keywords map"
    assert ns["old"].args == ("Old", window), "Base.__init__(self, ...) keywords map"
    assert ns["timer"].props == {"interval": 25}
    assert len(handle._connections) == 1, "a signal keyword connects through tracking"
    signal = ns["timer"].clicked
    handle.close()
    assert signal.callbacks == [], "close() disconnects the constructor connection"


def test_qt_defaults_when_declaration_quoted_then_literals_and_members_kept():
    doc = (
        "### `[static]` [QString](u) QFileDialog::getSaveFileName([QWidget](u) "
        "\\**parent* \\= nullptr, const [QString](u) \\&*caption* \\= QString(), "
        "int *n* \\= 3, QLineEdit::EchoMode *mode* \\= QLineEdit::Normal, "
        "Options *options* \\= Options())"
    )
    (found,) = qt_defaults(doc, "getSaveFileName", {"QLineEdit": "QtGui"})
    assert found == {
        "parent": None,
        "caption": "",
        "n": 3,
        "mode": {"native": "QtGui.QLineEdit.Normal"},
    }, "Options() is not a literal and is left out"


def test_analyze_when_tuple_method_unadapted_then_omitted_and_adapted_kept():
    pyside = {
        "QtWidgets": b"""
class QFileDialog(PySide2.QtWidgets.QDialog):
    def __init__(self, parent: typing.Optional[PySide2.QtWidgets.QWidget]=...) -> None: ...
    @staticmethod
    def getSaveFileName(parent: QWidget=..., caption: str=..., options: Options=...) -> typing.Tuple[str, str]: ...
    @staticmethod
    def getText(parent: QWidget, title: str, label: str, echo: int=..., text: str=...) -> typing.Tuple[str, bool]: ...
    def setLabelText(self, label: int, text: str) -> None: ...
"""
    }
    inventory = {
        "modules": {
            "QtWidgets": {
                "classes": {
                    "QFileDialog": {
                        "native_module": "QtGui",
                        "differences": {
                            "tuple_returns": {"getSaveFileName": {}, "getText": {}}
                        },
                    }
                }
            }
        }
    }
    out = {"bool_result": {"QtGui.QFileDialog": {"getText": {"defaults": {"echo": 0}}}}}
    report = analyze(inventory, pyside, {"QtGui": b""}, "sha", out_parameters=out)
    methods = report["classes"]["QtGui.QFileDialog"]
    assert report["omitted"] == {"QtGui.QFileDialog": ["getSaveFileName"]}
    assert methods["getText"]["overloads"][0]["defaults"] == {"echo": 0}
    assert methods["__init__"]["overloads"][0]["parameters"] == ["parent"]
    assert methods["setLabelText"]["static"] is False


def test_committed_table_when_loaded_then_matches_inventory_and_known_entries():
    data = json.loads((ROOT / "_keywords.json").read_text(encoding="utf-8"))
    inventory = hashlib.sha256((ROOT / "_inventory.json").read_bytes()).hexdigest()
    assert data["inventory_sha256"] == inventory
    label = data["entries"][data["classes"]["QtGui.QLabel"]["__init__"]]
    assert ["text", "parent", "f"] in [o["parameters"] for o in label["overloads"]]
    assert "getSaveFileName" in data["omitted"]["QtGui.QFileDialog"]
    get_text = data["entries"][data["classes"]["QtGui.QInputDialog"]["getText"]]
    assert get_text["overloads"][0]["defaults"]["echo"] == {
        "native": "QtGui.QLineEdit.Normal"
    }


def test_run_app_when_constructor_keyword_fails_after_signal_then_object_still_owned(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(
        "from PySide2 import QtCore\ntimer = QtCore.QTimer(clicked=print, colour=1)\n"
    )
    Native.made.clear()
    with pytest.raises(AttributeError, match="colour"):
        run_app(path)
    (timer,) = [o for o in Native.made if type(o) is QTimer]
    assert timer.deleted, "a constructed object is owned before keywords are applied"
    assert timer.clicked.callbacks == [], "its signal keyword connection was undone"


SUPER_AND_CAPTURED = """from PySide2 import QtWidgets
class Panel(QtWidgets.QLabel):
    def grow(self):
        super().resize(w=7, h=8)
panel = Panel()
panel.grow()
resize = panel.resize
resize(w=1, h=2)
"""


def test_run_app_when_super_or_captured_native_method_gets_keywords_then_mapped(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(SUPER_AND_CAPTURED)
    panel = run_app(path).namespace["panel"]
    assert panel.calls == [("resize", (7, 8)), ("resize", (1, 2))]


COOPERATIVE_SUPER = """from PySide2 import QtWidgets
class Panel(QtWidgets.QLabel):
    def resize(self, w, h):
        base_resize = super().resize
        base_resize(w=w, h=h)
panel = Panel()
panel.resize(3, 4)
"""


def test_run_app_when_captured_super_method_gets_keywords_then_base_dispatch_kept(
    tmp_path,
):
    path = tmp_path / "app.py"
    path.write_text(COOPERATIVE_SUPER)
    panel = run_app(path).namespace["panel"]
    assert panel.calls == [("resize", (3, 4))], (
        "the native base runs once, no recursion"
    )
