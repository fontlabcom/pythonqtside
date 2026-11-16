---
this_file: TODO.md
---

## Shared installer qualification — 2026-11-15

- [ ] Review and deliver the shared-installer candidate through fresh-main reconciliation, required gates, exact-SHA CI and genuine release/download qualification.
- [ ] After admission, verify installed provider/consumer identity and the applicable Script/Extension/native workflows without clearing existing holds by inference.



# Open tasks

- [ ] Match the inventories and routing to the supported FontLab PythonQt build (the native half): `native_host` versions in Echopy's `_provenance.json` are still null, and standalone PySide6 tests never establish native Qt 6 support. Whenever Echopy regenerates the PythonQt stubs, rerun the regeneration diff (`_inventory.json`, `_qtwidgets.json`) and compare byte for byte.
- [ ] Qualify QFileDialog tuple adaptation, overloads, properties, virtuals and ownership in the actual host, plus genuine artifacts and ordinary dependency resolution.
- [ ] Run the exact repository checks on the integrated source, obtain independent review, commit/push the scoped milestone and verify its remote head.
- [ ] After qualified main integration, inventory obsolete branches/files, preserve unique work and remove only proven stale items with recovery evidence.

- [ ] Qualify the installed native and release gates for the ordinary Echopy + pythonqtside tuple inside FontLab Python 3.11 arm64; built wheel contents, a no-deps installed import and a real-Echopy-wheel tuple outside FontLab are pinned by `tests/test_packaging.py`.

- [ ] Native check of the QFileDialog tuple adapter and examples/pyside2_dialog.py: the adapter must stay (live signatures 2026-11-10: `getOpenFileName`/`getSaveFileName`/`getExistingDirectory` return `str`, `getOpenFileNames` a plain tuple, no `(path, filter)` pair). Remaining: one modal pick through `fl-native.sh` with an owner at the dialog.

- [ ] Verify compatibility against the actual supported FontLab binding and keep standalone/native acceptance separate.

- [ ] Qualify the reviewed documentation source through ordinary main Actions and exact source/output lineage.
- [ ] Retain private Pages configuration and publication holds while native and owner-install gates remain separate.
