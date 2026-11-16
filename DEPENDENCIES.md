---
this_file: DEPENDENCIES.md
---

## Conditional installer requirements

Only conditional installer requirements use `packaging==26.3` in an external uv-managed Python environment. FontLab itself imports only the standard library; no permanent project dependency was added. An unavailable helper fails before sibling execution.


# Dependencies

- `fontlab-echopy>=0.1.0`: canonical PythonQt facades (`fontlab_echopy.PythonQt.*`)
  imported by `_routing.py`. Not published on PyPI: install it from the workspace
  wheel together with this package.
- Native PythonQt: provided by FontLab 9 (Qt 5.15, Python 3.11), never replaced by
  another Qt binding; no QApplication is created.
- PySide2 5.15.2.1: reference metadata only. The SHA-verified wheel's stubs give API
  names, keyword tables and constructor arities. It is never imported or installed:
  its wheels require Python <3.11.
- Python standard library ast/zipfile/hashlib/json: inventory extraction, identity
  verification, deterministic JSON.
- hatchling/hatch-vcs: wheel/sdist and Git-tag versions. pytest: tests.

Re-evaluated 2026-10-15 (R046): no new runtime dependency is needed. Qt.py and
similar shims target real Qt bindings and cannot run on PythonQt.

## Documentation build

A separate Python 3.13 docs environment uses the 31-package hash lock at `src_docs/requirements.txt`: ProperDocs 1.6.7, MkDocs 1.6.1, MaterialX 10.1.8 and PyMdown 11.0.1. Search is the sole plugin; light fltheme26 assets provide the shared menu/footer. Runtime dependencies and locks remain separate.
