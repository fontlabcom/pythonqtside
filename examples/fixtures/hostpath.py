# this_file: examples/fixtures/hostpath.py
# SPDX-License-Identifier: Apache-2.0
"""sys.path guard executed inside FontLab by the fixture runners.

SETUP saves FontLab's sys.path and every module of the affected packages, puts each
checkout src first, purges the packages, asserts each import comes from its src
and loads the harness as ``MODULE``. TEARDOWN restores the saved path order and
modules exactly, also after a failed SETUP. Variables: ``PACKAGES`` (name -> src;
SETUP builds it from ``pqs``/``echo``/``glyport``), ``harness``, ``MODULE``.
"""

SETUP = r"""
import sys, os, importlib, importlib.util
PACKAGES = {"pythonqtside": pqs, "fontlab_echopy": echo}
if globals().get("glyport"):
    PACKAGES["fontlab_glyport"] = glyport
ROOTS = (*PACKAGES, "PySide2", MODULE)
if not hasattr(sys, "_pqs_fixture_saved"):
    sys._pqs_fixture_saved = (
        list(sys.path),
        {m: mod for m, mod in sys.modules.items() if m.split(".")[0] in ROOTS},
        ROOTS,
    )
for name in [m for m in sys.modules if m.split(".")[0] in ROOTS]:
    del sys.modules[name]
for path in reversed(list(PACKAGES.values())):
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
loaded = {}
for package, path in PACKAGES.items():
    file = importlib.import_module(package).__file__
    assert os.path.realpath(file).startswith(os.path.realpath(path) + os.sep), (package, file, path)
    loaded[package] = file
spec = importlib.util.spec_from_file_location(MODULE, harness)
module = importlib.util.module_from_spec(spec)
sys.modules[MODULE] = module
spec.loader.exec_module(module)
result = loaded
"""

TEARDOWN = r"""
import sys
saved = sys.__dict__.pop("_pqs_fixture_saved", None)
if saved is not None:
    path, modules, roots = saved
    for name in [m for m in sys.modules if m.split(".")[0] in roots]:
        del sys.modules[name]
    sys.modules.update(modules)
    sys.path[:] = path
result = saved is not None
"""
