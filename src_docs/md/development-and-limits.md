---
this_file: src_docs/md/development-and-limits.md
---

# Development and limits

## Reproducible inventory

`src/pythonqtside/_inventory.json` joins eight
PySide2 module stubs with nine captured PythonQt stubs, including private and
combined Qt. It records 648 class declarations, availability, member differences,
constructor arities, enum differences and SHA256 identities for all 21 inputs.
Regenerate it and `_qtwidgets.json` from the read-only sibling Echopy checkout:

```sh
uv run --no-sync python -m pythonqtside.tooling.inventory --echopy ../fontlab-echopy
```

The tool parses ASTs and ZIP members, verifies wheel/manifest and recorded native
hashes, and emits sorted JSON without timestamps or local paths. It never loads
the wheel. The report is 3,607,692 bytes. The widget list changed from 200 to 195:
`Object` is an empty stub helper; `QAccessibleWidget`, `QColormap`,
`QStyleOptionComplex` and `QTreeWidgetItemIterator` also have no native match.

The supplied `_provenance.json` records no host versions: `fontlab_version`,
`python_version` and `qt_version` are explicitly `null`. Nested native enum types
are opaque; their membership remains unknown. Extra uppercase native attributes
are labelled enum candidates, not confirmed values. Constructor shapes describe
declarations, not working overloads. Inherited declarations within the eight
families are included; getter/attribute matches still require native checks.
Errors distinguish unavailable PySide2 names, names owned by another family and
unknown names. Native verification remains the orchestrator's gate.

## Measured adapters (phase 3)

`python -m pythonqtside.tooling.differences` reads only `_inventory.json` and
writes two deterministic files: the report
`_differences.json` (241,816 bytes) and
the small runtime table
`_out_parameters.json` (9,916 bytes),
which is the only file the out-parameter adapter loads. The report covers four categories for
routed classes:

| Category | Measured | Adapter |
| --- | --- | --- |
| PySide2 getter vs native attribute | 5,364 names, 228 classes; natively 4,624 measured, all Qt properties | zero-arg getter, gated by `metaObject().indexOfProperty()` |
| Enum members absent natively | 2,679 names, 125 classes; 1,381 opaque nested enums | none |
| Tuple results from out-parameters | 259 methods | 39: 2 by native predicate, 37 by `PythonQt.BoolResult` |
| Keyword arguments | every native constructor and method rejects them (FontLab measurement) | `_keywords.json`: PySide2 names mapped to positions |

The getter row was measured in FontLab 9 (issue 104, workspace evidence
`pqs-g04/getters/`): on 181 default-constructed classes, every one of the 4,624
names is a Qt property of the instance, so the `indexOfProperty` gate covers all of
them; none is already callable natively, none falls through. The other 740 names
belong to 47 classes that were skipped (application, clipboard, printing, GL,
platform dialogs) or have no default constructor; PythonQt exposes no
`staticMetaObject` to inspect them without an instance. The gate checks the live
instance at call time either way. Outside `run_app`, `compat.pyside_method(widget,
"windowTitle")()` uses the same gate. The measurement never reads property values:
reading `currentFrame` on an empty `QSvgRenderer` segfaults FontLab.

An out-parameter method is adapted only when PySide2 returns `(value, bool)` and
every native overload declares one bool out-parameter (`ok`, `invertible` or
`timedOut`) at the same position.

- Predicate: `QTransform().inverted()` and `QMatrix().inverted()` return the
  native result plus `isInvertible()`. A call with any argument stays native.
- `BoolResult`: the adapter puts a native `PythonQt.BoolResult` in the
  out-parameter slot, shifts later PySide2 arguments after it and returns
  `(value, bool(result))`. Examples: `QLocale().toInt("42")` gives `(42, True)`,
  `QByteArray.toInt(16)`, `QMatrix4x4().inverted()`, `item.itemTransform(other)`,
  `QTcpServer.waitForNewConnection(msec)` (the flag is `timedOut`), and the static
  `QInputDialog.getText/getInt/getDouble/getItem/getMultiLineText`. Static methods adapt on the class too. Parameters that
  PySide2 lets a caller omit before the slot get Qt 5.15's declared defaults
  (`getText` echo `QLineEdit.Normal`, looked up natively when called, and text
  `""`).
- Keyword calls are first mapped to positions (see "Keyword arguments" below).
  Calls stay native when keywords cannot be mapped, already pass a `BoolResult`,
  pass more positional arguments than the PySide2 form allows (`getDouble`'s
  `step` overload) or omit a parameter without a default.
- A PySide2-style call that passes `None` where PythonQt expects `ok` (for
  example `getText(parent, title, label, echo, text, None)`) is read as PySide2:
  the `BoolResult` goes into the slot and `None` follows it as `flags`. Only an
  explicit `BoolResult` argument marks a call as PythonQt style.

Unsupported methods keep native behavior, each with a recorded reason: 106 lack a
native method, 112 return several values or no flag (`getRgb`,
`QFileDialog.getOpenFileName`), 1 is ambiguous and 1 contradicts its stub.
`QHostAddress.toIPv4Address` also has a same-arity PySide2 overload that returns
a plain int. `QFontDialog.getFont` is annotated `(QFont, bool)`, but PySide2
returns `(ok, font)` at runtime, and the native `(ok, parent)` overload is not in
the stub, so it stays native.

Behaviour change from phase 3: `QMatrix4x4().inverted()` now returns a tuple.

### Implicit enum to value-class conversions (phase 3c)

PySide2 converts an enum to a value type implicitly: `setEasingCurve(QEasingCurve.OutElastic)`
calls `QEasingCurve(OutElastic)` first. FontLab's PythonQt does not: that call
raises "wrong arguments: (30,)", and `QTcpServer().listen(QHostAddress.LocalHost, 0)`
finds no overload. Passing `QEasingCurve(...)` or `QHostAddress(...)` works.

`python -m pythonqtside.tooling.conversions --echopy ../fontlab-echopy` writes
`_implicit_conversions.json`
(34,888 bytes). `_inventory.json` keeps parameter names but no annotations, so
the command reads the PySide2 wheel stubs and native stubs that the inventory
pins. It stops if any SHA256 differs from the inventory's `inputs`, and takes
class routing and native enum layout from the inventory.

- A value class is a routed PySide2 class with a copy constructor (Shiboken
  converts only to value types) and a constructor that takes one native enum.
  Five Qt 5.15 types whose enum constructor is C++ `explicit` are left out
  (QEvent, QOpenGLBuffer, QGLBuffer, QPageSize, QTileRules). That leaves 13:
  QEasingCurve, QHostAddress, QColor, QBrush, QPen, QCursor, QKeySequence,
  QPalette, QLocale, QJsonValue, QNetworkProxy, QSslError and QXmlQuery.
- A position is a parameter typed with one of those classes. Each routed class
  gets its own entries, inherited methods included, because the native stubs
  give every wrapper the base `PythonQtInstanceWrapper` and no Qt base chain, so
  `isinstance(label, QWidget)` cannot be assumed. The table has 610 positions on
  168 classes; each distinct entry is stored once. Examples:
  `setEasingCurve` on QVariantAnimation, QPropertyAnimation and QTimeLine,
  `QTcpServer.listen`, `setCursor` on every widget class, `QPixmap.fill`,
  `setPalette` and the static `setOverrideCursor`.
- Exclusions are decided per call arity (phase 3d). A position is excluded at an
  argument count when a PySide2 overload accepting that count takes an enum or
  int there (18), or `float` or a numeric sequence that an int-like enum could
  match (2: `QOpenGLShaderProgram`/`QGLShaderProgram.setAttributeValue`). In
  those cases PySide2 does not convert and the native overload set may not
  either: `QPainter.setBrush`, `setPen`, `fillRect`, `QImage.fill` and
  `QBrush.setColor` stay native at every arity. A sibling with another arity
  no longer blocks a position: `palette.setColor(QPalette.Window, Qt.red)` and
  `palette.setBrush(role, Qt.red)` convert, and so do
  `QImage.setPixelColor(point, Qt.red)`, `QOpenGLTexture.setBorderColor(Qt.red)`
  and the 3-argument `socket.bind(QHostAddress.LocalHost, port, mode)`. The
  3-argument `setColor(group, role, colour)` still has no position at index 1.
  Another 16 positions have no native method. Each exclusion is recorded with
  its reason, keyed `"index"` or, when only some arities are excluded,
  `"index@low-high"`. If the native classes do form a chain,
  a class without a conversion whose base has one gets an empty entry that
  shadows the base, and the most-derived match wins. There are none today.
- Generation fails if a method appears in both this table and
  `_out_parameters.json`.

At call time the argument is wrapped as `V(value)` only when all of these hold:
the receiver is native, the selected method is native, the arguments are
positional (after keyword mapping), their count is within the measured range, and the value is an
instance of the measured native enum type. A plain `int` or `bool`, another enum
type and a ready-made value object pass through unchanged. If the native enum
type cannot be resolved, nothing is wrapped. When a method has several entries
for one index, the actual positional argument count selects the entry. Native
class and enum objects are resolved once per path and `PythonQt` module, so a
`setCursor` lookup does not repeat its ~95 `getattr` chains on every call. Static methods are converted on
class receivers too (`QApplication.setOverrideCursor(Qt.WaitCursor)`). The native
call happens once and its result is returned unchanged. Constructors and module
functions are not converted (`QPen(Qt.red)` stays native), and neither are
unbound instance-method calls (see below).

`run_app` sources get every adapter automatically. New code opts in explicitly:

```python
from pythonqtside import compat
title = compat.pyside_method(widget, "windowTitle")()
inverse, ok = compat.pyside_method(transform, "inverted")()
text, ok = compat.pyside_method(QInputDialog, "getText")(parent, "Title", "Name")
compat.pyside_method(animation, "setEasingCurve")(QEasingCurve.OutElastic)
label = compat.pyside_construct(QLabel, "Name", parent=window)
```

Attribute reads such as `widget.windowTitle` remain native values. Classes are
not patched. A Python override keeps its own behaviour. Within `run_app`, bound
native methods stored first and called later get the full adapter chain, with or
without keywords (`convert = locale.toInt; convert("42")` returns `(42, True)`).
Native `super()` calls get the same adapters, including when native lookup needs
the explicit base-method fallback; Python base methods keep their own behaviour.
Unbound instance-method calls such as `QTransform.inverted(t)` or
`QLocale.toInt(locale, s)` remain native and return PythonQt's single value.

### Keyword arguments (issue 104)

FontLab's PythonQt rejects every keyword argument to a native constructor or
method: `QLabel("Name", parent=window)` raises `ValueError: ... called slot does
not support kwargs` (measured on QWidget, QLabel, QPushButton, QDialog, QTimer,
QLineEdit, QVBoxLayout, QColor, QSize, `setText`, `resize`, `setProperty` and the
static `QColor.fromRgb`; workspace evidence `pqs-g04/probe_keywords.json`).

`python -m pythonqtside.tooling.keywords --echopy ../fontlab-echopy` writes
`_keywords.json` (805,916 bytes) from the
pinned PySide2 and native stubs, verified against the inventory's SHA256 inputs.
It lists the PySide2 parameter names of every constructor and method overload of
the 535 routed classes, and 450 gap defaults: Qt 5.15 declaration defaults quoted
in Echopy's native docstrings when they are `nullptr`, `QString()`, `true`/`false`,
a number or `Class::Member` of a routed class, plus the BoolResult adapter's
defaults. 220 tuple-returning methods are left out of the keyword table (the three QFileDialog pickers are adapted separately, see `src_docs/md/pythonqt-compatibility.md`) because PySide2 drops their
out-parameters, so its positions differ from the native ones
(`QFileDialog.getSaveFileName`'s `options` is native position 5, not 4); the 39
adapted ones stay.

A keyword call becomes positional when exactly one positional form fits. A
skipped parameter needs a recorded default; `{"native": ...}` defaults resolve at
call time. Distinct forms, a keyword naming a parameter already passed by
position, or an unresolvable default keep the native call and its native error.
Constructor keywords that name no parameter set a Qt property or connect a
signal after construction, as PySide2 does (`QTimer(interval=50)`,
`QPushButton("OK", clicked=accept)`); other names raise `AttributeError`. Inside
`run_app` these connections are tracked and disconnected by `close()`.

Covered call forms: native constructors and Python subclasses without their own
`__init__`, `super().__init__(parent=parent)`, `Base.__init__(self, parent=p)`,
instance and static methods, `super().method(...)` (also when PythonQt's `super()`
misses the native method; a `base = super().method` load reaches the native base),
and a native method stored first and called later with keywords. Mapped calls then pass through the out-parameter and
conversion adapters, so `QLocale().toInt(s="42")` returns `(42, True)`. Signal
`connect`/`disconnect`/`emit` are never wrapped. In `run_app` only call sites
that pass keywords consult the table, which loads on the first such call.
Outside `run_app`:

```python
from pythonqtside import compat
label = compat.pyside_construct(QLabel, "Name", parent=window)
compat.pyside_method(label, "resize")(w=120, h=30)
```

Native acceptance (FontLab 9.0.9780, `pqs-g04/keywords/`, re-run on the final
code in `pqs-g04/regression/final/keywords.json`): an unchanged app
with all of the forms above, including `QLabel(alignment=Qt.AlignCenter)`,
`QLineEdit(placeholderText=...)`, `QTimer(interval=50, singleShot=True)` and
`QColor.fromRgb(r=10, g=20, b=30)` (alpha from the Qt default), ran and closed
with no cleanup errors.

### Signals, flags and buffers (issue 104)

Measured in FontLab 9 (workspace evidence `pqs-g04/fixtures/`); `run_app` adapts
each one:

- **Native-slot connections.** PythonQt passes every signal argument to a native
  slot, so `button.clicked.connect(label.clear)` fails ("wrong number of
  arguments"); Qt drops trailing arguments. Worse, PythonQt's slot comparison casts
  both operands to slot objects: disconnecting anything from a receiver that holds
  both a native slot (`buttons.rejected.connect(self.reject)`) and a bound method of
  the same object (`buttons.accepted.connect(self.submit)`) segfaults FontLab.
  `run_app` connects native slots through a Python forwarder that retries with fewer
  leading arguments, maps a later `disconnect(self.reject)` to that forwarder, and
  never lets a native slot be compared with another type.
- **Signal overloads.** `process.finished` connects to the deprecated
  `finished(int)`, so a PySide2 `lambda code, status: ...` never runs. When a
  callback needs more positional arguments than PythonQt's default overload
  delivers, `run_app` connects it with `owner.connect("2finished(int,QProcess::ExitStatus)", cb)`
  (overloads come from `signal.parameterTypes()`) and undoes that on disconnect.
- **QFlags against enum overloads.** `QDialogButtonBox.Ok | QDialogButtonBox.Cancel`
  is a plain int, and `QDialogButtonBox(int)` picks the `Qt.Orientation` overload:
  no buttons. `python -m pythonqtside.tooling.flags --echopy ../fontlab-echopy`
  writes `_flags.json` (12 positions on 10 methods,
  e.g. the QDialogButtonBox constructor and `QMessageBox.question`), where a flags
  parameter competes with an enum overload of the same arity. There a plain int, or
  an enum value other than the competing enum, is wrapped in the native flags class.
- **`bytes(QByteArray)`** raises in PythonQt; `bytes`, `bytearray` and `memoryview`
  calls in `run_app` read a native QByteArray through `data()`.
- **Ownership.** Widgets returned by `QUiLoader.load()` are owned like constructor
  results (Qt gives the caller ownership). Owned objects Qt already deleted (a
  delegate's editor) are skipped at close: PythonQt wrappers of deleted QObjects
  raise `ValueError: Trying to call ... on a destroyed ... object` instead of
  crashing. A killed QProcess counts as stopped when its state is NotRunning
  (`waitForFinished` returns false after `errorOccurred(Crashed)`).

## Unchanged-app fixtures (R036)

`examples/fixtures/` holds seven owned PySide2 apps: a form, custom
signals/slots/properties with an event filter and virtual overrides, a table model
with an editable spin-box delegate, a Designer `.ui` form loaded by QUiLoader,
QPainter driven by mouse and key events, QTimer with QProcess success/error/cancel,
and a delete-on-close child dialog reopened. Run them in FontLab:

```sh
cd ../fontlab-remopy
uv run python ../pythonqtside/examples/fixtures/run_native.py \
    --pythonqtside ../pythonqtside/src --echopy ../fontlab-echopy/src
```

Each stage is one short `run_python` call; waits happen on the host side so
FontLab's event loop delivers process output, queued delegate commits and deferred
deletion. The command prints a JSON report and exits 1 if any check fails.

The owned-font fixture (`font_edit/`, driver `run_native_font.py`, mutating) also
passes: an unchanged PySide2 panel sets `.notdef`'s advance width in a font FontLab
created for the run; Edit > Undo and Redo, `save_font`, an independent VFJ parse and
reopen all agree (evidence `pqs-g04/font-edit/receipt.json`). `fontlab.CurrentGlyph()`
is `None` without a glyph window, so the panel uses the workspace's current package.

All seven run unchanged in FontLab 9.0.9780 (evidence `pqs-g04/fixtures/run7-all.json`).
None needed a source change; the adapters above came from them: the form needed
the QFlags and native-slot fixes, the timer the overload, `bytes` and QProcess-stop
fixes, the `.ui` form the `load()` ownership, the model/view the destroyed-object
skip. Each fixture's files are hashed before and after the run.

Lifetime, measured (R035, `pqs-g04/lifetime/` and the fixtures): deleting a parent
deletes its children; `deleteLater()` completes only after control returns to the
event loop, not within the same `run_python` call; a wrapper of a deleted object
raises `ValueError: Trying to call 'setText' on a destroyed QLabel object` (there
is no `QtCore.QPointer`; this check is the validity test). After `handle.close()`
an emission from a still-living object reaches no app callback, owned objects are
gone by the next call, timers stop and processes are killed. App code that still
runs after close (a Python object the host kept) raises `RuntimeError: The
embedded application handle is closed` at its first adapted call, or `NameError`
when it first reads a module global, because close releases the app's globals.

## Running existing applications

Run an ordinary PySide2 script without editing its imports inside FontLab:

```python
from pythonqtside import run_app
handle = run_app("/path/to/app.py")
# The host event loop remains in control; the handle retains widgets and imports.
handle.close()  # Idempotent, scoped to constructor-created objects from this app.
```

`run_app(path, parent=None)` uses a private import graph for ordinary PySide2
imports and local `.py` files/packages, including imports from later callbacks.
Original files remain byte-identical. `handle.reports` contains immutable original
bytes, SHA256, filename, encoding and adapted call locations; `identity_report`
records routed classes and the explicit application proxy. Reports survive close.
The package retains active handles even when the caller discards the return value.

Native class identities remain intact except QApplication/QCoreApplication and
available QGuiApplication: these use one explicit proxy whose `native_application`
is the existing FontLab application. `instance()` reuses that proxy; application
`exec()`/`exec_()` return zero. `quit()`, `exit()` and `closeAllWindows()` close only
this handle. Application subclasses and other application operations/settings
raise `NotImplementedError`. Native dialog `exec_()` keeps its real modality.

Callable getter adaptation requires `metaObject().indexOfProperty()` evidence;
ordinary Python attributes remain ordinary values. Native super calls use the
measured property/unbound-method fallback. Calls stay in the original Python
frame, including aliased `exec`, `eval`, `super`, `locals`, `globals`, `vars`, `dir`.
Dynamic exec/eval strings receive no call adaptation. `importlib` imports,
namespace packages, star imports and nonlocal plugin discovery are not supported.
These limits are recorded; this runner does not establish whole PySide2 compatibility.

Only native QObject results from constructors are owned. Arbitrary native API
returns are borrowed. Cleanup disconnects tracked native signal callbacks, stops
timers and terminates supported processes/threads, then schedules owned graph
roots for deletion. Process/thread waits are bounded to 1000 ms each; work that
fails to stop and its owned ancestors stay retained, with deletion withheld and
details in `cleanup_errors`. Native deletion completion still depends on the host
event loop. `parent` must be a native QWidget; it applies only to unparented owned
root widgets when shown or when startup finishes. All UI operations require the
FontLab main Python thread; QtCore.QThread.currentThread is unavailable here.

The owned Apache-2.0 example in `examples/unchanged_app/app.py` imports PySide2
and has ordinary standalone startup. `examples/native_app_acceptance.py` supplies
the external FontLab acceptance driver. Standalone fixtures exercise the algorithm;
live controller verification is required before claiming host compatibility.

Three standalone tests validate namespace placement and direct class/signal
identity. Installed native checks verify QWidget/QColor placement, actual QObject
class identity, parent identity and a QObject subclass signal: connect, emit 7,
disconnect, emit 8 delivers only 7. Deletion is scheduled on the host event loop;
the ownership and lifetime behaviour is verified by the fixtures (see "Unchanged-app
fixtures (R036)" above).

```sh
uv venv --python 3.12
uv pip install --no-deps -e .
uv pip install pytest
./test.sh
uv build
```

Install fontlab-echopy alongside this package. Versions use hatch-vcs/Git tags.
The factual inventory records upstream version and input SHA256 identities;
no PySide2 runtime, implementation or documentation is redistributed. See NOTICE.

## Status

Released as v0.2.0 (RELEASE.md): importable routed namespace for `fly.qs` and the
compatibility plan. Since then (unreleased, natively accepted in FontLab 9.0.9780,
Python 3.11.6, Qt 5.15.19; evidence in the workspace
`verification/issue-101-ecosystem/evidence/pqs-inventory/` and
`pythonqtside-runner-sdd/`):

- Inventory join of the PySide2 5.15.2.1 stubs with the native PythonQt stubs, and
  exact QtCore/QtGui/QtWidgets routing (559 identities exact, 138 missing names
  raise, 195 QtWidgets names).
- `run_app(path)` for unchanged PySide2 sources: retained private imports, the
  host's QApplication behind a scoped proxy, immutable reports, owned cleanup.
- Protected virtual handlers: unchanged `super().paintEvent()`/
  `super().mousePressEvent()` reach the native base.
- Measured adapters (phases 3–3d): `(value, ok)` out-parameter results through
  `BoolResult`, implicit enum-to-value-class conversions with arity-aware
  exclusions, cached native resolution.

Unsupported: dynamic exec/eval adaptation, importlib and star imports, global
application settings, raw-pointer helpers. Detailed phase evidence is in WORK.md.

## Documentation and acceptance boundary

The compatibility guide is retained in the genuine source distribution at `src_docs/md/pythonqt-compatibility.md`. Historical embedded-app planning remains outside authored website inputs and distributions. Inventory data, native fixtures, runtime routing and dependency locks are unchanged. This site performs no native fixture, inventory recapture or owner installation. Private Pages configuration and publication remain owner-held.
