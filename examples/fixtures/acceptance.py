# this_file: examples/fixtures/acceptance.py
# SPDX-License-Identifier: Apache-2.0
"""Native acceptance stages for the R036 fixtures; runs inside FontLab only.

Each stage is one short call (FontLab's run_python allows 5 s). Stages that wait
for the host event loop (process output, deferred deletion) are polled by the
host-side runner, ``run_native.py``. Every widget a fixture creates is owned by its
``run_app`` handle and closed here; the stages never touch fonts or preferences.
This code is the FontLab driver, so it uses PythonQt idioms (property reads such
as ``label.text``); only the fixtures themselves are unchanged PySide2 sources.
"""

import gc
import hashlib
from pathlib import Path

from PythonQt import QtCore, QtGui

from pythonqtside import run_app

HERE = Path(__file__).parent
HANDLES = {}
App, Qt = QtGui.QApplication, QtCore.Qt


def _hashes(name: str) -> dict:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((HERE / name).iterdir())
        if p.is_file()
    }


def start(name: str):
    before = _hashes(name)  # before run_app, so startup changes are caught
    HANDLES[name] = (run_app(HERE / name / "app.py"), before)
    return HANDLES[name][0]


def finish(name: str) -> dict:
    handle, before = HANDLES.pop(name)
    handle.close()
    return {
        "closed": handle.closed,
        "cleanup_errors": list(handle.cleanup_errors),
        "sources_unchanged": _hashes(name) == before,
        "reports": len(handle.reports),
    }


def _key(widget, key: int, text: str) -> None:
    App.sendEvent(
        widget, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, Qt.NoModifier, text)
    )


def form() -> dict:
    window = start("form").namespace["form"]
    window.name_edit.setText("Aring")
    window.point_size.setValue(48)
    window.style_box.setCurrentIndex(1)
    window.outline.setChecked(True)
    window.buttons.button(QtGui.QDialogButtonBox.Ok).click()
    result = {
        "values": window.values,
        "dialog_result": window.result(),
        "hidden_after_accept": not window.isVisible(),
    }
    return result | finish("form")


def signals() -> dict:
    panel = start("signals").namespace["panel"]
    counter, result = panel.counter, {}
    counter.increment()
    result["label_after_slot"] = panel.label.text
    result["property_index"] = counter.metaObject().indexOfProperty("value")
    result["property_read"] = counter.property("value")
    result["set_property"] = counter.setProperty("value", 5)
    result["label_after_set_property"] = panel.label.text
    _key(panel.edit, Qt.Key_A, "a")
    _key(panel.edit, Qt.Key_X, "x")
    result["filter_keys"] = list(panel.key_filter.keys)
    result["edit_text_x_swallowed"] = panel.edit.text
    panel.resize(300, 90)
    _key(panel, Qt.Key_B, "b")
    panel.close()
    result["events"] = [list(e) if isinstance(e, tuple) else e for e in panel.events]
    result |= finish("signals")
    # Deletion is deferred to the event loop, so the objects still exist here:
    # an emission after close() must not reach the disconnected slot ...
    counter.valueChanged.emit(9)
    result["label_after_close_emit"] = panel.label.text
    # ... and re-entering the app's code fails clearly.
    try:
        counter.increment()
        result["reentry_after_close"] = "ran"
    except RuntimeError as error:
        result["reentry_after_close"] = str(error)
    HANDLES["signals_closed"] = panel
    return result


def signals_after_close() -> dict:
    panel = HANDLES.pop("signals_closed")
    return {"panel": _alive(panel), "label": _alive(panel.label)}


def _alive(obj) -> bool | str:
    """PythonQt wrappers of deleted QObjects raise on any call (measured)."""
    try:
        obj.parent()
        return True
    except ValueError as error:
        return "destroyed" if "on a destroyed" in str(error) else str(error)


def modelview() -> dict:
    namespace = start("modelview").namespace
    view, model = namespace["view"], namespace["model"]
    index = model.index(0, 1)
    result = {
        "display_via_native_index": index.data(),
        "editable": bool(int(model.flags(index)) & int(Qt.ItemIsEditable)),
        "header": model.headerData(1, Qt.Horizontal, Qt.DisplayRole),
    }
    view.edit(index)
    editor = view.indexWidget(index)
    result["editor"] = type(editor).__name__ if editor is not None else None
    if editor is not None:
        editor.setValue(640)
        # The delegate commits through a queued call: checked in the next stage.
        _key(editor, Qt.Key_Return, "\r")
    return result


def modelview_check() -> dict:
    model = HANDLES["modelview"][0].namespace["model"]
    result = {"after_edit": model.index(0, 1).data(), "rows": model.rows}
    return result | finish("modelview")


def uiloader() -> dict:
    handle = start("uiloader")
    namespace = handle.namespace
    window = namespace["window"]
    result = {
        "class": type(window).__name__,
        "title": window.windowTitle,
        "owned_by_handle": any(window is o for o in handle._objects),
    }
    namespace["name_edit"].setText("Ada")
    namespace["button"].click()
    result["status"] = namespace["status"].text
    return result | finish("uiloader")


def painter() -> dict:
    canvas = start("painter").namespace["canvas"]
    App.sendEvent(
        canvas,
        QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            QtCore.QPointF(50, 40),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        ),
    )
    _key(canvas, Qt.Key_R, "r")
    canvas.repaint()
    image = canvas.grab().toImage()
    ratio = image.devicePixelRatio()
    result = {
        "points": len(canvas.points),
        "paints": canvas.paints,
        "click_pixel": QtGui.QColor(
            image.pixel(int(50 * ratio), int(40 * ratio))
        ).name(),
        "background_pixel": QtGui.QColor(
            image.pixel(int(5 * ratio), int(5 * ratio))
        ).name(),
    }
    return result | finish("painter")


def timer_start() -> dict:
    runner = start("timer_process").namespace["runner"]
    return {"started": True, "ticks": runner.ticks}


def timer_poll() -> dict:
    runner = HANDLES["timer_process"][0].namespace["runner"]
    return {"ticks": runner.ticks, "log": [list(e) for e in runner.log]}


def timer_cancel() -> dict:
    HANDLES["timer_process"][0].namespace["runner"].cancel()
    return timer_poll()


def timer_finish() -> dict:
    runner = HANDLES["timer_process"][0].namespace["runner"]
    result = finish("timer_process")
    HANDLES["timer_process_closed"] = runner
    return result | {"ticks_at_close": runner.ticks}


def timer_after_close() -> dict:
    return {"ticks": HANDLES.pop("timer_process_closed").ticks}


def timer_close_cancels() -> dict:
    """Second run: close() itself must kill the running /bin/sleep."""
    runner = start("timer_process").namespace["runner"]
    sleeper = runner.sleeper
    result = finish("timer_process")
    return result | {"sleeper_state_after_close": int(sleeper.state())}


def lifetime_open() -> dict:
    main = start("lifetime").namespace["main"]
    main.button.click()
    return {"opened": main.opened, "child_visible": main.child.isVisible()}


def lifetime_close_child() -> dict:
    main = HANDLES["lifetime"][0].namespace["main"]
    main.child.close()
    return {"closed": True}


def lifetime_poll() -> dict:
    main = HANDLES["lifetime"][0].namespace["main"]
    return {
        "destroyed_children": main.destroyed_children,
        "child_cleared": main.child is None,
    }


def lifetime_reopen() -> dict:
    main = HANDLES["lifetime"][0].namespace["main"]
    main.button.click()
    result = {"opened": main.opened, "child_visible": main.child.isVisible()}
    HANDLES["lifetime_closed"] = (main, main.child)
    return result | finish("lifetime")


def lifetime_after_close() -> dict:
    main, child = HANDLES.pop("lifetime_closed")
    return {"main": _alive(main), "child": _alive(child)}


def abort() -> dict:
    """Close every handle a failed stage left open (never leave windows behind)."""
    closed = {}
    for name in list(HANDLES):
        entry = HANDLES.pop(name)
        if (
            isinstance(entry, tuple)
            and hasattr(entry[0], "close")
            and hasattr(entry[0], "cleanup_errors")
        ):
            entry[0].close()
            closed[name] = list(entry[0].cleanup_errors)
    return closed


# Owned-font fixture (R036 last item). Mutating: run only in an agent-owned
# FontLab session through fl-native.sh --mutating (run_native_font.py).
def _notdef_width(font_id: int):
    import fontlab

    package = fontlab.flWorkspace.instance().findPackageId(font_id)
    layer = package.findName(".notdef").findLayer("Regular")
    return None if layer is None else layer.advanceWidth


def _action(name: str):
    import fontlab

    window = fontlab.MainWindow()
    enabled = gc.isenabled()
    gc.disable()
    try:
        actions = window.findChildren(QtGui.QAction)
    finally:
        if enabled:
            gc.enable()
    for action in actions:
        if action.objectName == name:
            return action
    return None


def font_start(font_id: int) -> dict:
    panel = start("font_edit").namespace["panel"]
    return {"spin": panel.width_box.value, "native": _notdef_width(font_id)}


def font_apply(font_id: int, width: int) -> dict:
    panel = HANDLES["font_edit"][0].namespace["panel"]
    panel.width_box.setValue(width)
    panel.apply_button.click()
    undo = _action("actionUndo")
    return {
        "native": _notdef_width(font_id),
        "undo_enabled": None if undo is None else undo.enabled,
    }


def font_trigger(font_id: int, name: str) -> dict:
    action = _action(name)
    enabled = None if action is None else action.enabled
    if enabled:
        action.trigger()
    return {"triggered": enabled}


def font_read(font_id: int) -> dict:
    return {"native": _notdef_width(font_id)}


def font_finish() -> dict:
    return finish("font_edit")
