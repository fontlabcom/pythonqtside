---
this_file: source_docs/superpowers/plans/embedded-app-runner.md
---
# Embedded app runner implementation slice

Parent authority: workspace issues/101.md R034–R036. This is one implementation
slice of the full ecosystem goal; native models/views, forms, painters, timers,
processes, font edits, corpus adaptation and deployment retain their full scope.

## Global Constraints

- Never load real PySide2/Qt6 binaries into FontLab's Python3.11/Qt5 process.
- Reuse FontLab's existing QApplication and return to its event loop.
- Retain native objects/classes wherever possible; declare every proxy identity.
- Keep original source files byte-identical, host sys.modules/sys.path/cwd/argv
  intact, and callback imports usable after initial execution returns.
- No user font edits, no supplied corpus execution, no force pushes/tag rewrites.
- Work on the existing issue-101-ecosystem feature branch. Preserve .DS_Store.
- Do not spawn subagents. Root owns native integration/final review and docs build.
- Every source has a repository-relative this_file header; use rtk proxy commands.

## Task 1: Retained unchanged-source PySide2 app runner

Own pythonqtside src/, tests/, examples/, README/PLAN/TODO/WORK/CHANGELOG updates
for this task only. Existing uncommitted _app_source.py/_app_native.py and their
tests are seed work; integrate and review them rather than reverting them.

Implement pythonqtside.run_app(path, *, parent=None) -> AppHandle. AppHandle.close()
is idempotent and tears down only its owned UI, disconnects tracked native
callbacks and retains immutable original/source/adaptation identity reports.
Retain live execution/import globals until close; startup errors tear down owned
objects before propagating the original exception. Provide active handle retention
so a one-line run_app call does not lose its widgets to Python GC.

Use stdlib AST/tokenize/import support: adapt ordinary PySide2 imports in a
private builtins import context, not global sys.modules aliases. Support ordinary
from PySide2 import QtCore, QtWidgets, from PySide2.QtWidgets import QWidget,
and import PySide2.QtWidgets as QtWidgets. Also adapt local sibling .py modules
and packages in the same retained context, including a callback that imports a
sibling only after initial script execution returns. Other imports delegate to
the original import implementation. Preserve unrelated global modules/path/cwd/argv.

Keep all routed native class identities. Automatically reuse the existing host
application when the source constructs QApplication/QCoreApplication and uses
instance(), exec()/exec_(), sys.exit(app.exec_()). Return zero from embedded
global-loop calls; catch only successful top-level SystemExit (None/0), propagate
nonzero termination. Application quit/exit/closeAllWindows must close this handle's
UI, never quit FontLab or close its windows. Declare an explicit application proxy
if needed. Reject application subclasses or global application settings that
cannot yet be faithfully scoped; report that boundary rather than pretending
they succeeded. Preserve actual safe native dialog modality.

AST call adaptation must preserve callee-before-argument evaluation, original
filename/line locations, zero-arg super/locals/globals/vars/dir and exec/eval frame
semantics. Dynamic exec/eval strings are not automatically transformed; report
this limitation. Native property getters are permitted only with confirmed Qt
metaObject().indexOfProperty(name) evidence; retain ordinary noncallable Python
attributes so their call errors remain errors. Native super property/method calls
need the measured fallback. QtCore.QThread.currentThread is unavailable here;
require the measured FontLab main Python thread, with precise failures elsewhere.

Own native QObject results from constructors, not arbitrary native function
return values. Stop/disconnect owned asynchronous work when supported and delete
only roots of the owned parent graph; parent=None stays standalone. Parent support
must parent owned root windows only, not layouts or host objects. Do not identify
native QObject inheritance via isinstance(widget, private.QObject): actual probe
returns false. Use actual native wrapper ancestry/capabilities and record limits.

Tests first: fixture import forms, originals/hash immutability, retained delayed
helper imports, relative package import, sibling failure cleanup, nonzero exit,
callee evaluation/frame behavior, live metadata-confirmed getters, ordinary Python
attribute errors, existing app reuse/nonblocking return, parent ownership/cleanup,
closed handle behavior and off-host/wrong-thread failure. Fake native fixtures
prove algorithm/error contracts, not FontLab compatibility. Current six source
and three native-getter fixture tests must remain meaningful and passing.

Add an owned Apache-2.0 unmodified PySide2 example with QWidget/QVBoxLayout/
QLabel/QPushButton, a custom Signal/Slot, width()/text(), delayed helper import,
and ordinary standalone startup. It must import PySide2, not pythonqtside. Supply
an external native acceptance driver via run_app; retain original hashes. Only
owned fixture widgets may be shown/closed. No existing FontLab font edits.

Read official PythonQt Developer documentation (already confirmed:
https://mevislab.github.io/pythonqt/Developer.html) and native seed tests before
implementing. Run uv run --no-sync python -m pytest -q, scoped Ruff and diff checks.
Commit owned task files only. Update progress docs with exact implemented limits;
this task does not establish full R035/R036 or whole ecosystem completion.

Report full implementation, tests/outputs, commits, self-review and remaining
concerns to the named report file; return short status/commit/test summary.

## Task 2: Native integration and scoped task review

Controller executes the owned unchanged example in running FontLab, verifies
real visible window, native callbacks/property calls/delayed imports, existing
application/process identity, responsiveness and cleanup. Create a full diff
review package from the recorded pre-task base; obtain independent spec+quality
review, fix findings with covering tests, then record bounded task completion.
Whole expanded compatibility, final branch review and publication remain pending.
