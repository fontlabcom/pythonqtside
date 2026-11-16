# this_file: src/pythonqtside/compat.py
"""Opt-in PySide2-style member access for new code running in FontLab PythonQt."""

from typing import Any

from ._app_keywords import construct, native_init
from ._app_native import resolve

__all__ = ["pyside_construct", "pyside_method"]


def pyside_method(obj: Any, name: str) -> Any:
    """Return ``obj.name`` as PySide2 code would call it, without altering ``obj``.

    Native Qt properties confirmed by ``metaObject().indexOfProperty()`` become
    zero-argument getters. Measured out-parameter methods listed in
    ``_out_parameters.json`` return PySide2's ``(value, ok)`` tuple:
    QTransform/QMatrix ``inverted()`` via the native ``isInvertible()``, and 37
    others (``QLocale.toInt``, ``QInputDialog.getText`` and so on) by passing a
    native ``PythonQt.BoolResult`` in the out-parameter slot. Pass ``obj`` as the
    class for static methods. Keyword calls and calls that already pass a
    ``BoolResult`` stay native. Methods listed in ``_implicit_conversions.json``
    wrap a measured native enum argument as PySide2's implicit value class
    (``setEasingCurve(QEasingCurve.OutElastic)`` passes
    ``QEasingCurve(OutElastic)``); plain ints and other values pass through.
    Keyword arguments, which PythonQt rejects on every native method, are mapped to
    positions by the PySide2 parameter names in ``_keywords.json``.
    Everything else is the ordinary attribute.
    The same rules apply to calls in sources run with ``run_app``.
    """
    return resolve(obj, name, keywords=True)


def pyside_construct(cls: type, *args: Any, **kwargs: Any) -> Any:
    """``cls(*args, **kwargs)`` with PySide2 constructor keywords.

    ``pyside_construct(QLabel, "Name", parent=window)`` calls ``QLabel("Name",
    window)``; keywords naming a Qt property or signal (``QTimer, interval=50``,
    ``QPushButton, "OK", clicked=accept``) are set or connected afterwards. A class
    with its own Python ``__init__`` receives the keywords unchanged.
    """
    if not kwargs or not native_init(cls):
        return cls(*args, **kwargs)
    return construct(cls, args, kwargs)
