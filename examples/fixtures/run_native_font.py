# this_file: examples/fixtures/run_native_font.py
# SPDX-License-Identifier: Apache-2.0
"""Owned-font acceptance: an unchanged PySide2 panel edits a font FontLab created
for this run; the edit must undo, redo, save, parse independently and reopen.

MUTATING. Run only in an agent-owned FontLab session (no user documents):

    verification/issue-104/fl-native.sh --mutating --lane L4 -- \
        uv run --project fontlab-remopy python \
        pythonqtside/examples/fixtures/run_native_font.py "$PWD" <out-dir>

The font's .notdef has no master layer until one is written (glyport R021), so a
base step creates it through glyport's accepted undo group (width 500). The app
then sets 640 through FontLab's own API. Each step is its own run_python call.
Prints the receipt, writes <out-dir>/receipt.json; exit 0 only if every check passed.
"""

import json
import sys
import time
from pathlib import Path

from fontlab_remopy import FontLab
from hostpath import SETUP, TEARDOWN  # sys.path guard run inside FontLab

ROOT, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
MODULE = "pqs_fixture_acceptance"
HERE = Path(__file__).resolve().parent
PATHS = {
    "pqs": str(ROOT / "pythonqtside/src"),
    "echo": str(ROOT / "fontlab-echopy/src"),
    "glyport": str(ROOT / "fontlab-glyport/src"),
    "harness": str(HERE / "acceptance.py"),
}

BASE = r"""
import fontlab
from fontlab_glyport.model.fontlab_backend import FontLabBackend
from fontlab_glyport.model import Model
package = fontlab.flWorkspace.instance().findPackageId(font_id)
font = Model(FontLabBackend(packages=[package])).fonts[0]
with font.undo_group("pythonqtside base"):
    font.glyphs[".notdef"].layers[0].width = 500
result = font.glyphs[".notdef"].layers[0].width
"""
STAGE = "import sys\nresult = getattr(sys.modules[MODULE], stage)(*arguments)"


def call(fl, code, **variables):
    reply = fl.run(code, MODULE=MODULE, **PATHS, **variables)
    if reply.value is None:
        raise RuntimeError(reply.stderr[-1500:] or "no result")
    return reply.value


def stage(fl, name, *arguments):
    value = call(fl, STAGE, stage=name, arguments=list(arguments))
    time.sleep(0.2)  # let the host event loop run between steps
    return value


def ids(fl):
    return {f["id"] for f in fl.fonts()}


def notdef_width(path: Path):
    """Independent host-side parse of the saved VFJ (plain json, no FontLab code)."""
    data = json.loads(path.read_text())
    glyph = next(g for g in data["font"]["glyphs"] if g.get("name") == ".notdef")
    layer = next((x for x in glyph.get("layers", []) if x.get("name") == "Regular"), {})
    return layer.get("advanceWidth")


receipt = {"checks": {}}
checks = receipt["checks"]
saved = OUT / "pqs-font-edit.vfj"
saved.unlink(missing_ok=True)


def run(fl):
    """Every step after setup; the caller always restores sys.path."""
    before = ids(fl)
    receipt["user_fonts_before"] = sorted(before)
    fl.new_font(family_name="PythonqtsideFontEdit", style_name="Regular")
    font_id = next(iter(ids(fl) - before))
    receipt["font_id"] = font_id
    try:
        fl.activate_font(font_id=font_id)
        fl.activate_glyph(font_id=font_id, glyph_name=".notdef")
        receipt["base"] = call(fl, BASE, font_id=font_id)
        receipt["start"] = stage(fl, "font_start", font_id)
        receipt["apply"] = stage(fl, "font_apply", font_id, 640)
        receipt["undo"] = stage(fl, "font_trigger", font_id, "actionUndo")
        receipt["after_undo"] = stage(fl, "font_read", font_id)
        receipt["redo"] = stage(fl, "font_trigger", font_id, "actionRedo")
        receipt["after_redo"] = stage(fl, "font_read", font_id)
        receipt["finish"] = stage(fl, "font_finish")
        checks["app_read_base"] = receipt["start"] == {"spin": 500, "native": 500}
        checks["app_edit_applied"] = receipt["apply"]["native"] == 640
        checks["undo_enabled"] = bool(receipt["apply"]["undo_enabled"])
        checks["undo_restores_base"] = receipt["after_undo"]["native"] == 500
        checks["redo_restores_edit"] = receipt["after_redo"]["native"] == 640
        checks["app_closed"] = (
            receipt["finish"]["closed"]
            and not receipt["finish"]["cleanup_errors"]
            and receipt["finish"]["sources_unchanged"]
        )
        fl.save_font(font_id=font_id, path=str(saved))
        checks["saved"] = saved.exists()
        receipt["parsed_width"] = notdef_width(saved) if saved.exists() else None
        checks["independent_parse"] = receipt["parsed_width"] == 640
    except Exception as error:  # noqa: BLE001 - recorded in the receipt
        receipt["error"] = f"{type(error).__name__}: {error}"[:1500]
        try:
            receipt["abort"] = stage(fl, "abort")
        except Exception as abort_error:  # noqa: BLE001
            receipt["abort_error"] = str(abort_error)[:500]
    finally:
        fl.close_font(font_id=font_id)
    if saved.exists():
        before_open = ids(fl)
        fl.open_font(path=str(saved))
        reopened = next(iter(ids(fl) - before_open))
        try:
            receipt["reopened"] = stage(fl, "font_read", reopened)
            checks["reopened_width"] = receipt["reopened"]["native"] == 640
        finally:
            fl.close_font(font_id=reopened)
    receipt["user_fonts_after"] = sorted(ids(fl))
    checks["no_fonts_left"] = (
        receipt["user_fonts_after"] == receipt["user_fonts_before"]
    )


with FontLab() as fl:
    try:
        receipt["setup"] = call(
            fl, SETUP
        )  # before new_font: failing setup opens no font
        run(fl)
    finally:
        call(fl, TEARDOWN)


REQUIRED = (
    "app_read_base",
    "app_edit_applied",
    "undo_enabled",
    "undo_restores_base",
    "redo_restores_edit",
    "app_closed",
    "saved",
    "independent_parse",
    "reopened_width",
    "no_fonts_left",
)
receipt["passed"] = "error" not in receipt and all(checks.get(k) for k in REQUIRED)
text = json.dumps(receipt, indent=1, sort_keys=True, default=str)
(OUT / "receipt.json").write_text(text)
print(text)
sys.exit(0 if receipt["passed"] else 1)
