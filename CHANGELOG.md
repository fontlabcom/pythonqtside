---
this_file: CHANGELOG.md
---

## 1.1.12 (2026-11-16)

- `install.vfpy` is now the short fontlab-instamix stub. It installs
  fontlab-instamix from PyPI when it is missing, then installs this checkout from
  its `[tool.fontlab-install]` table. The large legacy installer is gone.
- README describes the stub install.

## 2026-11-15 — Shared installer source alignment

Copied the reviewed shared installer exactly: dependency constraints and managed origins remain protected; inactive conditional dependencies are filtered before sibling execution in the resolver target Python. FontLab imports remain standard-library-only. Package identity, runtime APIs, dependency declarations, scripts, bundles and legal files are unchanged. The real source-archive check now includes the exact root installer; the prior omission was reproduced before the single allowlist addition.

Focused checks: 4 passed, 2 deselected in 1.30s. This qualifies the local source candidate only. Independent review, combined-main/full delivery gates, genuine release/downloads, installed provider closure and admitted FontLab/native workflows remain separate. No owner-folder installation or native operation ran.

## 2026-11-14 — Functional work order documented

- Added the owner's functional-progress-first guidance and repository-specific priorities, including cross-package compatibility and a later detailed testing pass. Existing mandatory hooks, holds and unfinished work remain in force.
- This change updates guidance and planning only; it establishes no new runtime, installed, native or release result.

## 2026-11-12 — D46 documentation pass (Issue 250)

- Landed this session, all on `main`: the real-Echopy-wheel installed test (`520d029`), the built-wheel contents and installed-import pin (`19821ad`), the owner live-font testing rule in AGENTS.md (`9a9afd1`). Latest release is `v1.1.9` (`b627d0f3`).
- PLAN drops a stale reconciliation line. TODO is unchanged: every open row is a native or publication check that is still open. WORK.md was already a short pointer and is unchanged.
- No code changed.

## 2026-11-11 — Real Echopy wheel installed beside the pythonqtside wheel (Issue 250)

- `tests/test_packaging.py::test_installed_wheels_when_echopy_sibling_built_then_ordinary_tuple_resolves_from_site_packages` builds the Echopy wheel from the sibling checkout (Echopy `fb50215`, origin/main), installs it with this wheel into a fresh venv (`--no-deps`, no `PYTHONPATH`) and checks both packages and all ten lazy modules load from site-packages and that the installed Echopy version matches the built wheel.
- It skips with a reason when the private `fontlab-echopy` sibling is absent, so public CI without it skips; it ran and passed here.
- Not established: installed FontLab behavior (host Python 3.11 arm64) and the release gates; TODO row 12 keeps those open.

## 2026-11-11 — Built wheel contents and installed-wheel import pinned host-free (Issue 250)

- `tests/test_packaging.py` gains three cases beside the two existing build tests. The wheel carries exactly every `src/pythonqtside` file (byte-equal, including the seven `_*.json` data files) and nothing else; its metadata is `pythonqtside`, `Apache-2.0`, with `fontlab-echopy` as the only non-extra dependency. The wheel is installed with `--no-deps` into a fresh `uv venv` and imported with the working directory outside the repository: `pythonqtside` and its ten lazy submodules load from `site-packages` and every `_*.json` parses. No generated data file or manifest hash changed.
- Mutants each fail it: extra wheel package, extra dependency, dependency dropped, licence changed, a data file excluded (two tests), a corrupted JSON file.
- Network: `uv build` and `uv venv` need the registry for hatchling and hatch-vcs unless the uv cache holds them.
- Gate: `.metaswarm/quality.sh coverage` with Echopy `4c48737` (origin/main): 0 changed production modules, tests only; the installed test ran and passed (263 passed, no skip).
- Not established: the real Echopy wheel as an ordinary installed tuple, and anything inside FontLab; TODO row 12 keeps those open.

## 2026-11-11 — Inventory regeneration matches the committed files (Issue 250)

- Regenerated `_inventory.json` and `_qtwidgets.json` in a scratch directory from Echopy origin/main and the pinned PySide2 5.15.2.1 wheel (sha256 `b5e1d92f26b0bbaefff67727ccbb2e1b577f2c0164b349b3d6e80febb4c5bde2`) with a rebuilt `pyside-manifest.json` (sha256 `858dd6c0f437…`, equal to the hash recorded in the inventory inputs). `cmp` showed both outputs byte-identical to the committed files, and the ten Echopy-side input hashes also matched. Nothing in the Echopy checkout changed.
- Evidence: the triage report `issue250/triage/pythonqtside-inventory-diff.md`; the regeneration was run by the triager and not rerun here.
- The TODO row keeps only the native half and a reminder to rerun the diff when Echopy regenerates the PythonQt stubs.

## 2026-11-10 — QFileDialog adapter kept (Issue 250 live signatures)

Read the running FontLab 9 `PythonQt.QtGui.QFileDialog` pickers without opening
a dialog: the open/save/directory pickers return `str`, so the adapter that
produces PySide2's `(path, filter)` pair is still needed. No code changed; the
TODO row now holds only the modal-pick check.

## 2026-11-10 — live font editing rule (Issue 250, D44)

- AGENTS.md: agents test and edit the font open in FontLab 9, starting from the Desktop VFJs, and may save them.

## 2026-11-10 — install.vfpy always reinstalls scripts and dependencies

- Every install copies all files from `Scripts/` afresh and replaces any file
  already at the same path. A symlinked script folder is replaced by a real
  folder; the link target is never written. A directory where a script file
  belongs is still refused.
- Required packages are installed on every run. Packages that no package
  index carries (the fontlab-* packages, pythonqtside) are installed from
  checkouts beside this one through their own `install.vfpy`, once per run
  and safe against cycles. uv receives every other requirement, so version
  ranges, markers and extras are enforced. Without uv, sibling checkouts are
  still installed and only the remaining missing requirements are reported.
- The installer is byte-identical across all eleven installer repositories.

## 2026-11-05 — independently approved documentation applied

[Task 2 final review](../verification/issue-230/task-2-fix2-review.md) records
SPEC PASS / QUALITY APPROVED. The [78-file application receipt](../verification/issue-230/task-2-apply.json)
includes this repository's six guides and preserves all 21 repository heads,
branches, indexes and non-selected diffs. This is applied documentation evidence,
not a new product test, installed artifact, native result or publication.

The complete earlier handoff/history below retains its proposal-stage statements
and dated source pins. Later review, application and delivery status belong in the
[live workspace ledger](../verification/issue-230/progress.md). Original future,
native, artifact and preservation contracts remain binding.

## 2026-11-05 — documentation reconciliation proposal

Prepared repository-specific organization, test and MVP/delivery guidance from current source/test configuration and retained Issue 207–211 evidence. Distinguished current canonical layout from qualified candidates, future plugin ownership and unfinished native/artifact gates. Preserved all prior work and changelog evidence; no runtime completion, installation or publication is claimed. Historical checked tasks now require receipt/current-scope reconciliation rather than being silently counted complete.

## 2026-11-05 — planning chronology reconciliation

The broad old pause is scoped to Issue123; no standaloneQt6 observation establishes hostQt6. All distribution and actual supported-binding/QFileDialog/overload/property/ownership requirements remain open. Historical passing results retain their dated source and acceptance scope in the entries above and original history below. This documentation change creates no new runtime acceptance.

---
this_file: CHANGELOG.md
---

## 2026-11-03 — installer options, licence and cleanup

- `install.vfpy` reads optional `[tool.fontlab-install]` keys: `name` (the distribution
  record), `packages` (`[]` installs scripts only) and `dependencies` (what FontLab needs,
  instead of `project.dependencies`). Symlinks inside `Scripts/` are not copied.
- Removed the finished `plans-phase3*.md` working plans (kept in Git history).

## 2026-11-03 — install.vfpy fixes from runs inside FontLab 9

Verified by installing all nine packages inside FontLab 9 (Python 3.11.6, arm64).
- Dependencies with console scripts (glyphsLib, fontTools) failed: uv writes them to
  `site-packages/../../../bin`, which resolves through the venv link to the FontLab
  folder. `bin`, `share` and `include` there now link back into `.venv`.
- A failed install appends a `"failed"` record with the traceback and uv's output to
  `install.log`; List/Uninstall ignore failed records.
- Package records include `WHEEL`, so `uv pip check` accepts them.
- Scripts are copied file by file into FontLab's `Scripts` folder, from a package's
  `Scripts/` folder (exact case) and from folders listed in `[tool.fontlab-install] scripts`.
  Folders shared by several packages merge, e.g. two packages' `Scripts/Kerning`. The
  installer refuses to overwrite a file another package or the user put there; uninstall
  removes only its own files, their `.pyc`, and folders left empty. An older install's
  folder link (`Scripts/Aidus Code`) is replaced by copied files.
- `*.vfpyc` (FontLab's compiled `install.vfpy`) is ignored by Git.

## 2026-11-03 — install.vfpy creates FontLab's venv

FontLab's `python/3.11/site-packages` is now always a real folder; packages are
symlinked into it, so no `.pth` processing is needed. `install.vfpy` creates `.venv` with
uv from FontLab's exact Python version and processor type, and links the venv's
site-packages to FontLab's folder, so `uv pip install --python .venv/bin/python` installs
into FontLab. An older layout (FontLab's folder linked into `.venv`) is migrated.

## 2026-11-03 — reverse-domain extension id and install.log

`[tool.fontlab-install] id = "com.fontlab.pythonqtside"` names this extension. `install.vfpy` keeps
`Extensions/com.fontlab.pythonqtside/install.log` (JSON Lines; the last line lists every installed file),
puts copied code in `Extensions/com.fontlab.pythonqtside/lib/`, and adds Scripts > Extensions >
List Extensions and Uninstall com.fontlab.pythonqtside.

## 2026-11-03 — install.vfpy without uv

`install.vfpy` now needs only FontLab's Python. It asks FontLab for its data folder
(`flPreferences().dataPathDefault`), links a Git checkout or copies a plain folder into
`Extensions/`, and writes a `.pth` plus `.dist-info` into `python/3.11/site-packages`.
uv is used only to add missing dependencies. It never replaces folders it does not own.

## 2026-11-03 — release scripts

Added `build.sh` (uv build into dist/), `publish.sh` (`uv publish`; refuses a dirty
tree or an untagged HEAD) and `install.vfpy` (editable install into FontLab's venv
from inside FontLab). Version stays hatch-vcs from `vX.Y.Z` tags.

<!-- workspace-handoff:2026-11-03 -->
## 2026-11-03 — documentation handoff for November 2–3

No new November 2–3 runtime delivery is attributed here; standalone Qt6 tests elsewhere do not add a Qt 6 backend inside FontLab.

Actual overload/property/ownership behavior remains host/build-specific.

Observed canonical checkout: `issue-101-ecosystem` at `2777e85cd84c`. No source integration is performed by this update.

Updated the requested AGENTS/TODO/PLAN/CHANGELOG/README documentation and
recorded the paused state. Existing project text, examples and history remain;
no runtime source, installation, native session, branch/ref, release or site was
changed by this documentation maintenance. Source/archive/ordinary/native and
promotion acceptance remain separate claims. Detailed workspace evidence is
recorded in the root CHANGELOG and retained verification reports.
<!-- /workspace-handoff -->

# Changes

## 2026-11-10 — Issue 250 documentation round

- AGENTS.md describes the delegation, integration and release workflow.
- WORK.md reset to the current round; the earlier bytes are archived on the owner's workspace data volume, not public.

## 2026-11-03 — Issue 201: QFileDialog pickers return PySide2 tuples

- `QFileDialog.getOpenFileName`, `getSaveFileName` and `getOpenFileNames` now return
  `(path, "")` / `(paths, "")` in `run_app` sources and `compat.pyside_method`, as PySide2
  does; `path, _ = ...` no longer fails. Keywords map to positions. PySide2's
  `(parent, caption, dir, filter, options)` reaches native as `(parent, caption,
  dir, filter, "", options)`: `selectedFilter`, an out-parameter PythonQt cannot
  fill, is inserted as `""` before `options` (final review H1 fixed a version that
  read the fifth PySide2 argument as `selectedFilter` and dropped `options`). A
  `selectedFilter=` keyword raises TypeError, as PySide2 has no such parameter.
  Instance receivers and subclasses without an override are adapted too; a native `(path, filter)` pair passes
  through unchanged.
  Other argument forms reach the native method unchanged. The chosen filter is
  never reported (always `""`). Source-verified with doubles; native check listed in
  the workspace's `verification/issue-201/task-11-gap.md`.
- New `examples/pyside2_dialog.py` (unchanged PySide2 dialog) with a double-backed test.
- 259 offline tests pass.

## 2026-10-23 — Distribution portability and provenance

- Include the unchanged public API inventory NOTICE in wheel licence files and
  metadata; add a real-wheel test for exact LICENSE/NOTICE bytes.

## 2026-10-15 — issue 104 (G04) completed (moved from PLAN.md and TODO.md)

Verified at 10f8a8b: `./test.sh -q` 221 passed; final native re-run in FontLab
9.0.9783 (workspace evidence `pqs-g04/final-close/`): seven fixtures, keyword app
(equal to its final receipt), review drivers 2 and 3, and the owned-font fixture
(10/10) all pass. Independent review: R-L4 → RR-L4 → RR2-L4 → RR3-L4 APPROVE.

- [x] Finish measured differences (`_differences.json`): property/getter conversion
  outside `run_app`, overload and constructor keyword arguments.
  - [x] Keyword table from pinned PySide2 stubs (`_keywords.json`); keyword-to-positional
    adapter for constructors, `Base.__init__`, `super().__init__`, `super()` calls, instance,
    static and stored methods; property/signal constructor keywords. Natively accepted
    (`pqs-g04/keywords/`).
  - [x] Native measurement of the getter table: 4,624 of 5,364 names on 181 classes, all
    covered by the `indexOfProperty` gate (`pqs-g04/getters/`; recorded in
    `_differences.json` `callable_accessors.native`).
- [x] Verify custom signals, slots, properties, event filters and virtual overrides in
  FontLab (R035): fixture `signals`.
- [x] Verify parent ownership, deletion, QPointer-like validity and callback lifetime
  (R035): `pqs-g04/lifetime/probe_lifetime.json` and the fixtures' after-close checks
  (no callback after close, owned objects destroyed by the next call, clear
  `RuntimeError` on re-entry).
- [x] Run the R036 unchanged-app fixtures with `run_app` (form, custom signals/slots/
  properties, model/view with editable delegate, `.ui` via QUiLoader, QPainter with
  mouse/key, QTimer and QProcess success/error/cancel, parent/delete/reopen). No fixture
  needed a source change; the adapters they required are listed under Unreleased.
- [x] One unchanged app edits an owned font and passes undo/save/reopen (after glyport
  R023/R024): `examples/fixtures/run_native_font.py`.
- [x] Publish the compatibility guide (`docs/compatibility.md`) and the runnable native
  acceptance command (`examples/fixtures/run_native.py`); wheel/sdist checks in FontLab
  from the extracted artifacts (workspace `release-104/pythonqtside.md`); release
  readiness reported. The controller tags (candidate 10f8a8b).

Host facts recorded on the way: FontLab 9.0.9780/9.0.9783, Python 3.11.6, Qt 5.15.19;
`QtCore.QPointer` is absent (validity is checked through wrapper behaviour); every native
call rejects keywords. Removed as not feasible (workspace DECISIONS.md D8): a Qt 6 backend
before FontLab ships Qt 6.

## 2026-10-15 — completed checklist (moved from TODO.md)

- Produce source-grounded adapter architecture and phased test plan.
- Package importable pythonqtside namespace for fly.qs with hatch-vcs.
- Implement bounded unchanged-source runner with retained private imports, immutable reports, explicit host application proxy and scoped owned cleanup.
- Add owned unchanged PySide2 example, external acceptance driver and fixture coverage for the runner's algorithm/error contracts.
- Controller: verify owned runner example and teardown in live FontLab.
- Controller: independently review the runner diff and address findings.
- Capture and join PythonQt/PySide2 inventories with runtime-version evidence (report `_inventory.json`; native probe Qt 5.15.19/Python 3.11.6 in workspace evidence/pqs-inventory/runtime.json).
- Implement exact QtCore/QtGui/QtWidgets namespace routing (native: 559 identities exact, 138 missing names raise, 195 QtWidgets names).
- Measured adapters, phases 3–3d (natively accepted; workspace evidence/pqs-inventory/phase3/): `_differences.json` measurement report, `(value, ok)` out-parameter results through `BoolResult` (37+ methods), 604 implicit enum-to-value-class conversions with arity-aware exclusions. Property/getter differences outside `run_app` and overload/constructor keywords remain open.
- Publish routed namespace and compatibility plan as reviewed v0.2.0.
- Verify all three project iterations and downloaded release assets.
- Implement protected base-handler forwarding so unchanged subclasses can call super().paintEvent() and super().mousePressEvent(); verify native viewport event/paint routing and preserve text rendering, owned cleanup and callback errors.

## v0.2.1 (2026-10-16)

PySide2-compatible Qt layer for FontLab's PythonQt: adapters for enums, keyword/optional arguments, stored and super() native calls, signals, model/view, UI loader, painter, timers, lifetime; native acceptance passed on FontLab 9.0.9783 (issues 101/104/106). Release review X5 + X6 fix APPROVE; native evidence verification/issue-106/evidence/pythonqtside-native/.


- Release-gate fixes (issue 106, X5/X6): the owned-font acceptance driver uses
  `fontlab.MainWindow()` and disables GC around `findChildren()`, restoring the
  previous state in `finally`. Captured positional native methods now share the
  out-parameter, enum-conversion and QFlags adapters with direct calls. Native
  `super()` calls use that chain for both normal lookup and the explicit base
  fallback, retaining base dispatch and Python overrides. README and the
  compatibility guide describe the corrected call forms.

- Re-review fixes (issue 104, RR-L4.md, RR2-L4.md): a stored native slot called
  with keywords is adapted as captured (its `__self__`/`__name__` select the
  table entries; no re-resolution, so a cooperative `base = super().resize` keeps
  its base dispatch) and gets the full adapter chain shared with `resolve()`
  (`_adapt`: out-parameter or enum conversion, QFlags, keywords); a
  `super().name` load is resolved like a super call (PythonQt's `super()` misses
  native methods); an aliased or captured signal's owner is recovered from the
  signal itself (its GC referent matching the id in its repr), so borrowed
  senders also get the overload matching the callback.
- Review fixes (issue 104, R-L4-review.md): an untracked `disconnect(cb)` reaches
  PythonQt again (native-slot guard kept); objects built with keywords are owned
  before property/signal keywords apply; keyword mapping now covers
  `super().method(...)` and stored native methods; overload selection survives
  aliased signals and stored `connect` on owned objects; fixture runners restore
  FontLab's prior sys.path and modules (`examples/fixtures/hostpath.py`); fixture
  hashes are taken before `run_app`.

- Compatibility guide `docs/compatibility.md` (feature table, lifetime rules,
  unsupported features, crash landmines, native acceptance command), shipped in
  the sdist. Wheel and sdist checked natively: all seven fixtures pass from the
  extracted artifacts (workspace evidence `pqs-g04/artifacts/`).
- Owned-font fixture (`examples/fixtures/font_edit`, `run_native_font.py`):
  natively accepted (edit, Edit > Undo/Redo, save, independent VFJ parse, reopen).
- Fixture runners follow the workspace sys.path rule: each checkout src first,
  packages purged, `__file__` asserted under its src, sys.path restored.

- PySide2 keyword arguments (issue 104). FontLab's PythonQt rejects keywords on
  every native constructor and method (measured). New generated
  `_keywords.json` (`python -m pythonqtside.tooling.keywords`) records PySide2
  parameter names and literal/native Qt declaration defaults; `run_app` and
  `compat.pyside_method` map keyword calls to positions before the out-parameter
  and conversion adapters, and the new `compat.pyside_construct` does the same
  for constructors. Constructor keywords naming a Qt property or signal are set or
  connected after construction (tracked in `run_app`). `_differences.json`
  (schema 2) records the native keyword measurement. Natively accepted.
- Unchanged-app fixtures and the adapters they needed (issue 104, natively
  accepted): seven owned PySide2 apps in `examples/fixtures/` with a host-side
  runner (`run_native.py`). `run_app` now forwards native-slot connections through
  a Python function (Qt-style argument trimming; avoids a PythonQt segfault when a
  receiver holds a native slot and a bound method of the same object), connects
  callbacks to the signal overload matching their arity (`QProcess.finished`),
  wraps QFlags arguments where an enum overload would win (`_flags.json`,
  `QDialogButtonBox(Ok | Cancel)`), converts `bytes(QByteArray)`, owns
  `QUiLoader.load()` results and skips owned objects Qt already deleted.
- After `close()`, app code that still runs raises `RuntimeError: The embedded
  application handle is closed` at its first adapted call instead of a
  `NameError` on an internal name; signal records keep their sender, and close
  skips senders Qt already deleted.
- Fix: a killed owned QProcess is no longer reported as "did not stop" when
  `waitForFinished` returns false after `errorOccurred(Crashed)`.
- Native getter measurement (issue 104): all 4,624 measured PySide2 getter names
  on 181 classes are Qt properties covered by the `indexOfProperty` gate; recorded
  in `_differences.json` `callable_accessors.native`.

- Conversion table precision (phase 3d). Exclusion is now per call arity: a
  sibling overload excludes a position only at the argument counts it accepts.
  As a result, `palette.setColor(QPalette.Window, Qt.red)`,
  `palette.setBrush(role, Qt.red)`, `image.setPixelColor(point, Qt.red)`,
  `texture.setBorderColor(Qt.red)` and the 3-argument
  `socket.bind(QHostAddress.LocalHost, port, mode)` now convert.
  `float`/numeric-sequence siblings now exclude a position as well
  (`pyside_numeric_overload`), so `setAttributeValue` is dropped. QPainter
  `setPen`/`setBrush`/`fillRect` stay native at every arity.
  The table has 610 positions in 34,888 bytes, schema 2. Native
  class resolution is cached per path and `PythonQt` module.

- Convert PySide2 implicit enum arguments to value classes for native calls:
  `setEasingCurve(QEasingCurve.OutElastic)`,
  `QTcpServer.listen(QHostAddress.LocalHost, 0)`, `widget.setCursor(Qt.WaitCursor)`,
  `pixmap.fill(Qt.red)` and the rest of 604 measured positions on 13 value types,
  repeated for each routed subclass. New
  `pythonqtside.tooling.conversions` writes `_implicit_conversions.json` (33,728
  bytes) from the inventory's SHA-pinned PySide2 and native stubs. A position is
  left out when a PySide2 overload takes an enum or int there (`QPainter.setBrush`,
  `setPen`, `fillRect`, 22 in all) or the native method is missing (16). The runtime
  wraps only instances of the measured native enum type, on native receivers
  without Python overrides, in positional calls of measured arity. Static methods
  convert on class receivers. Constructors are not converted.

- Adapt 37 more PySide2 out-parameter methods to `(value, ok)` through native
  `PythonQt.BoolResult`, among them `QMatrix4x4.inverted`, `QLocale/QByteArray.to*`,
  `QGraphicsItem.itemTransform`, `QMetaEnum.keyToValue`, `waitForNewConnection` and
  the static `QInputDialog.get*`. Static methods adapt on
  class receivers; omitted Qt-defaulted parameters before the slot are filled.
  Keyword calls and explicit `BoolResult` calls stay native. Behaviour change:
  `QMatrix4x4().inverted()` now returns a tuple.
- The inventory records all PySide2 overloads (with a static marker) for
  tuple-returning methods (3,607,692 bytes). The analysis checks that the native
  overloads declare the out-parameter, and reports `QHostAddress.toIPv4Address` as
  an ambiguous PySide2 overload.
- `QFontDialog.getFont` stays native (`stub_runtime_mismatch`): PySide2 returns
  `(ok, font)` at runtime, not the annotated `(QFont, bool)`. The analysis now also
  requires native overloads to agree on the parameters before the out slot.
- The adapter now loads the small generated `_out_parameters.json` instead of the
  whole `_differences.json` report.
- The error-propagation test now runs through the adapter rather than a Python
  override.

- Record PySide2 tuple results, native parameter lists and native bool predicates
  in the inventory (3,535,243 bytes, deterministic).
- Add `pythonqtside.tooling.differences` and `_differences.json`: getter/attribute,
  missing-enum, out-parameter and constructor-keyword categories with counts, top
  classes and explicit adapter/unsupported tables.
- Adapt PySide2 `QTransform.inverted()`/`QMatrix.inverted()` to `(value, ok)` using
  native `isInvertible()` in `run_app` sources and the opt-in
  `pythonqtside.compat.pyside_method`. Arguments pass through natively; the other
  257 tuple methods stay native and are recorded as unsupported.

- Add a reproducible AST/ZIP inventory joining PySide2 5.15.2.1 and captured
  PythonQt declarations with input hashes, availability, member/enum differences
  and constructor arities. Unrecorded host versions remain null.
- Drive all eight namespace families from that join, including relocated QtCore
  models and private QObject, with precise missing/wrong-family/unknown errors.
  Preserve native identities, extensions and existing run_app behavior.
- Regenerate the QtWidgets intersection: 200 names become 195 after removing the
  empty Object helper and four classes absent from the native capture.
- Add host-independent extraction/integrity/determinism fixtures and exhaustive
  committed-route identity/error checks; native acceptance remains pending.

- Add retained `run_app()`/`AppHandle` for unchanged PySide2 source, private local
  imports, immutable provenance and scoped ownership/callback cleanup.
- Reuse FontLab's existing application through an explicit lifecycle proxy;
  reject application subclasses and unscoped application operations/settings.
- Adapt metadata-confirmed native getter and super calls while preserving Python
  call order, frame builtins, source filenames and line locations.
- Add an owned Apache-2.0 standalone PySide2 example and external native acceptance
  driver. Full models/views/forms/async/corpus compatibility remains unverified.
- Recognize the measured native QtCore.Signal wrapper by exact class identity,
  track borrowed signal callbacks and verify disconnection before widget deletion.
- Match distinct native Signal wrappers by confirmed backend equality when
  removing manual-disconnect records; preserve independent borrowed reconnections.
- Track captured native Signal connect/disconnect aliases using measured C-bound
  method metadata; preserve ordinary callable/frame behavior and single tracking
  for direct calls.

- Added adapter architecture, phased compatibility tests and Qt6 transition plan based on upstream documentation and live FontLab observations.
- Verified native custom-widget signal connection, emission and disconnection in the running FontLab host.

- Add modern hatch-vcs package, lazy namespace imports and explicit scope docs.
- Verify standalone identity/error tests and installed native alias/Qt smoke.
- Route QtWidgets by verified upstream inventory and alias actual private QObject.
- Keep full PySide behavior adaptation and Qt6 tasks unchecked in the plan.

## v0.2.0 publication verified

Actual publication and independent downloaded-asset verification complete.
Three full-project iterations pass; installed tagged wheel/sdist each457tests.
Downloaded native smoke covers all eight packages and both formats, including
production ACP/native UI and TypeRig composition. Exact release URLs, immutable
code commit and asset digests are in RELEASE.md. This follow-up changes only
completion evidence; release code and tag are unchanged.

## 2026-10-15 — workspace plan and checklist reconciliation

Completed repository scope archived after reading WORK.md and checking the
workspace evidence. Workspace release/integration gates remain in the parent
PLAN.md. Historical verification limits below remain part of the record.

### Archived PLAN.md

# Plan

No open work. Issue 104 (G04) is complete; its items, evidence and host facts are in
CHANGELOG.md ("2026-10-15 — issue 104 (G04) completed"). New work starts here.

### Archived TODO.md

# Tasks

No open tasks (all moved to CHANGELOG.md on 2026-10-15).

## 2026-11-06 — Private documentation candidate

Added the product-specific light ProperDocs/MaterialX source/generated site and every-main source/output qualification workflow without private Pages operations. Pythonqtside preserves and relocates its authored compatibility guide and private planning source, updates the sdist path and verifies actual archive contents. Runtime products and native acceptance are unchanged.


## 2026-11-07 — Exact frontend notices and English search assets

Added exact upstream frontend notices and source-map provenance for the existing MaterialX 10.1.8 payload. Explicit English configuration and a small build hook reject language, corpus, reference, asset-set or hash drift before omitting the 35 unused language helpers. All nine retained core assets, original product legal files, guides, catalogue rows, media, runtime and dependency/build locks are preserved.

The strict site build and all 35 documentation tests pass. The complete new hook has 100% statement/branch coverage; real Git staging, checkout and archives preserve exact legal bytes. An independently installed matching lock reproduces all 49 output bytes and modes. Existing immutable source/output, epoch, concurrency and full-parity workflow checks remain active. Browser and independent review evidence are separate from these local checks.

Private Pages configuration, grants, requests and publication remain owner-held; this source follow-up adds none.
No product release or installation is claimed. Prior ordinary artifacts remain bound to their recorded revisions; a later Git revision changes genuine hatch-vcs metadata. Full current source archives include these documentation additions; no unchanged-sdist or whole-wheel identity is asserted. Native acceptance and owner installation remain separate.


## 2026-11-07 — installed icon path-tuple inventory refinement

The current HTML/CSS contains 45 distinct ordered SVG path tuples. A complete scan of the four installed MaterialX icon families finds 43 exact installed matches and two unmatched Lucide tuples, refining the earlier known-candidate inventory. The additional installed match is the Font Awesome version caret-down. Its existing CSS header and full notice retain Font Awesome Free 7.1.0, Fonticons and CC-BY-4.0 icon attribution. The official NPM caret SVG has different raw path bytes; no unmodified-primary SVG, whole-geometry or optimizer-recipe equivalence is claimed. The two unmatched Lucide tuples retain their pinned SCSS source attribution.

A new actual-output regression derives these counts and checks installed matches, unmatched CSS references and the caret header. It fails against the prior 42 count and passes with the corrected metadata. All 36 current documentation tests pass; full strict and independent exact-lock builds match every output byte and mode. Only the legal paragraph, corresponding inventory and legal search row change in the site. Runtime, packaging, generators, vendor assets, full notices, existing guidance and the Fly search fix remain exact. Fresh browser verification and independent review are recorded separately. No private Pages operation, delivery, installed-product upgrade or native acceptance is claimed.
