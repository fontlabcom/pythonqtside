# this_file: src/pythonqtside/_app_dialogs.py
"""PySide2's ``(path, selectedFilter)`` result for the QFileDialog static pickers.

PythonQt's ``getOpenFileName``/``getSaveFileName`` return a str and
``getOpenFileNames`` a tuple; all take ``(parent, caption, dir, filter,
selectedFilter, options)`` (measured in FontLab 9). PySide2 takes ``(parent,
caption, dir, filter, options)`` and code unpacks ``path, _ =
QFileDialog.getOpenFileName(...)``. The adapter inserts ``selectedFilter=""``
before ``options``: it is an out-parameter PythonQt cannot fill, so the returned
filter is always ``""``. PySide2 has no ``selectedFilter`` keyword; passing one
raises TypeError.
"""

from functools import partial
from importlib import import_module
from typing import Any

PICKERS = frozenset({"getOpenFileName", "getSaveFileName", "getOpenFileNames"})
# PySide2 names and defaults, in PySide2 order; native inserts selectedFilter
# before options.
PARAMETERS = (
    ("parent", None),
    ("caption", ""),
    ("dir", ""),
    ("filter", ""),
    ("options", 0),
)
_NAMES = tuple(n for n, _ in PARAMETERS)


def _is_file_dialog(receiver: Any) -> bool:
    try:
        dialog = import_module("PythonQt").QtGui.QFileDialog
    except (ModuleNotFoundError, AttributeError):
        return False
    if isinstance(receiver, type):
        return issubclass(receiver, dialog)
    return isinstance(receiver, dialog)


def file_dialog_call(receiver: Any, name: str, method: Any) -> Any:
    """Adapter for a native, unoverridden picker, or None when none applies."""
    if name not in PICKERS or not _is_file_dialog(receiver):
        return None
    return partial(_with_filter, name, method)


def _with_filter(name: str, method: Any, *args: Any, **kwargs: Any) -> Any:
    if "selectedFilter" in kwargs:
        raise TypeError(
            f"QFileDialog.{name}() got an unexpected keyword argument "
            "'selectedFilter' (PySide2 has none; the filter is returned)"
        )
    if (
        len(args) > len(_NAMES)
        or set(kwargs) - set(_NAMES)
        or set(kwargs) & set(_NAMES[: len(args)])
    ):
        return method(
            *args, **kwargs
        )  # not a PySide2 form: native raises its own error
    given = dict(zip(_NAMES, args)) | kwargs
    if "options" in given:  # native: selectedFilter (unfillable) sits before options
        filled = [given.get(n, d) for n, d in PARAMETERS[:4]]
        filled += ["", given["options"]]
    else:
        last = max((_NAMES.index(n) for n in given), default=-1)
        filled = [given.get(n, d) for n, d in PARAMETERS[: last + 1]]
    result = method(*filled)
    if name == "getOpenFileNames":
        return list(result), ""
    if isinstance(result, tuple) and len(result) == 2:
        return result  # already the (path, filter) pair
    return result, ""
