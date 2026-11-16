---
this_file: src_docs/md/pythonqt-compatibility.md
---

# PySide2 compatibility in FontLab

FontLab 9 ships PythonQt (Qt 5.15, Python 3.11), not PySide2. `pythonqtside` lets
PySide2 code run there in two ways:

- `run_app("app.py")` runs an unchanged PySide2 source inside FontLab and adapts
  every call in it (table below), without touching the file.
- `pythonqtside.QtWidgets` and friends give new code the native classes under
  PySide2 module names, and `pythonqtside.compat` offers the adapters one call at
  a time (`pyside_method`, `pyside_construct`).

Every "adapted" row was measured in FontLab 9.0.9780 first; evidence lives in the
workspace under `verification/issue-101-ecosystem/evidence/` (`pqs-inventory/`,
`pqs-g04/`).

## What works

| PySide2 feature | Native PythonQt behaviour | In `run_app` | Outside `run_app` |
| --- | --- | --- | --- |
| `from PySide2 import QtCore, QtGui, QtWidgets, ...` | no PySide2 module | routed to native classes (559 identities) | `from pythonqtside import QtWidgets` |
| `QApplication(sys.argv)`, `app.exec_()` | must never be created | proxy to FontLab's application; `exec_()` returns 0 | not applicable |
| Getters: `label.text()`, `widget.width()` | properties are values | adapted; all 4,624 measured names covered | `compat.pyside_method(label, "text")()` |
| Keyword arguments: `QLabel("x", parent=w)`, `resize(w=, h=)` | every native call rejects keywords | mapped to positions (`_keywords.json`) | `compat.pyside_construct`, `compat.pyside_method` |
| Constructor property/signal keywords: `QTimer(interval=50)`, `QPushButton("OK", clicked=f)` | rejected | set/connected after construction | `compat.pyside_construct` |
| `(value, ok)` results: `QInputDialog.getText`, `QLocale.toInt` | single value, `BoolResult` slot | tuple, as PySide2 (39 methods) | `compat.pyside_method` |
| Enum where a value class is expected: `setEasingCurve(QEasingCurve.OutElastic)` | "wrong arguments" | wrapped (610 positions) | `compat.pyside_method` |
| QFlags with a competing enum overload: `QDialogButtonBox(Ok \| Cancel)` | `Ok \| Cancel` is an int; the `Orientation` overload wins, no buttons | wrapped in the flags class (12 positions) | pass `QDialogButtonBox.StandardButtons(...)` |
| `clicked.connect(label.clear)` (slot takes fewer arguments) | native slot gets every signal argument and fails | forwarded with Qt-style trimming | connect a `lambda` |
| `process.finished.connect(lambda code, status: ...)` | connects the deprecated `finished(int)`; the callback never runs | the overload matching the callback's arity | `process.connect("2finished(int,QProcess::ExitStatus)", cb)` |
| `path, _ = QFileDialog.getOpenFileName(...)` (also `getSaveFileName`, `getOpenFileNames`) | bare path (str) or tuple of paths | `(path, "")`; the chosen filter cannot be read back; PySide2 positional `(parent, caption, dir, filter, options)` is passed to native as `(parent, caption, dir, filter, "", options)`; a `selectedFilter=` keyword raises TypeError (PySide2 has none); class or instance receivers | `compat.pyside_method` |
| `bytes(process.readAllStandardOutput())` | `TypeError` | `data()` used | `qbytearray.data()` |
| `super().paintEvent(event)` in a subclass | `super()` misses protected handlers | forwarded to the native base | `QtGui.QPlainTextEdit.paintEvent(self, event)` |
| Custom `Signal`, `Slot`, `Property(int, get, set, notify=...)`, event filters, virtual overrides | native | work unchanged (fixture `signals`) | same |
| Model/view with Python models and delegates | native | work unchanged (fixture `modelview`) | same |
| `QUiLoader().load(QFile(...))` | native | works; the loaded widget is owned and closed with the app | close it yourself |
| `QTimer`, `QProcess` | native | stopped/killed by `handle.close()` | stop them yourself |

Keyword mapping covers direct calls, `super().method(...)`, `Base.__init__(self, ...)`,
`super().__init__(...)` and a native method stored first and called later with
keywords. Signal-overload selection also follows an aliased signal
(`finished = process.finished; finished.connect(cb)`) or a stored `connect`, for
owned and borrowed senders alike: a PythonQt signal's only GC referent is its owner
and its repr carries the owner's `id` (measured).

Stored bound native methods and native `super()` calls also receive out-parameter,
enum-conversion and QFlags adapters with positional or keyword arguments. Native
base dispatch is retained even when a Python subclass overrides the method.

## Lifetime

- Only objects the app constructs (and `QUiLoader.load()` results) belong to its
  handle; values returned by other API calls are borrowed.
- `handle.close()` disconnects the app's tracked connections, stops timers, kills
  processes, then closes and `deleteLater()`s its root objects. Deletion completes
  when FontLab's event loop next runs, not within the same `run_python` call.
- A wrapper of a deleted QObject raises `ValueError: Trying to call 'x' on a
  destroyed QLabel object`. There is no `QtCore.QPointer`; that error is the
  validity check.
- After `close()`, app code that a kept Python object still runs raises
  `RuntimeError: The embedded application handle is closed`, or `NameError` once it
  reads a module global, because the app's globals are released.

## Not supported

- PySide2 enum members missing natively (2,679 names) and opaque nested enums.
- 217 PySide2 tuple-returning methods without a native flag (for example
  `getRgb`) and their keywords. The three QFileDialog pickers are adapted but report an empty selected filter.
- `exec`/`eval` strings, `importlib` imports, star imports, namespace packages,
  application subclasses and global application settings.
- Qt 6 and anything PySide2 adds on top of Qt (`QtCore.Property` decorators other
  than the call form above are untested).

## Landmines found while measuring

These crash FontLab; `run_app` avoids the first one, the others need care in any
script:

1. Disconnecting a signal on a receiver that holds both a native slot
   (`buttons.rejected.connect(self.reject)`) and a bound method of the same object
   (`buttons.accepted.connect(self.submit)`) segfaults in PythonQt's slot
   comparison. Connect a `lambda` instead of the native slot.
2. Reading the `currentFrame` property of an empty `QSvgRenderer` segfaults.
3. Unary minus on a wrapper (`-QPoint(1, 2)`) segfaults.

## Native acceptance command

Run the seven unchanged-app fixtures (`examples/fixtures/`) in a running FontLab
with external MCP clients enabled:

```sh
cd ../fontlab-remopy
uv run python ../pythonqtside/examples/fixtures/run_native.py \
    --pythonqtside ../pythonqtside/src --echopy ../fontlab-echopy/src
```

It prints a JSON report and exits 1 if any check fails. Point `--pythonqtside` at
an extracted wheel to check a built artifact. The owned-font fixture
(`run_native_font.py`) edits, saves and reopens a font FontLab creates for the
run; use it only in a FontLab session without your own documents.
