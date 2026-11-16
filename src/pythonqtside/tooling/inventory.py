# this_file: src/pythonqtside/tooling/inventory.py
"""Generate the pinned inventory and widget map using only standard-library parsers."""

import argparse
import hashlib
import json
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

from .join import MODULES, NATIVE_MODULES, join_surfaces
from .surface import Surface, extract

PACKAGE = Path(__file__).resolve().parents[1]
LIMITATIONS = [
    "Host versions come only from _provenance.json native_host; unrecorded fields are null.",
    "Public declarations only; imports, docstrings and private methods are excluded; class dunders are retained and __init__ arities summarized separately.",
    "Bases within the eight PySide2 modules are expanded; external bases are not inspected.",
    "Constructor entries are declared arity shapes, not proven native overloads; variadic stubs give no dispatch evidence.",
    "Native type attributes are opaque; nested enum membership is null, not assumed missing.",
    "Extra native enum candidates are uppercase Any/int attributes, not confirmed enum membership or values.",
    "Accessor matches require a zero-argument declared getter and a same-name native attribute; behavior is unverified.",
    "Object is retained as a missing class declaration and flagged as an empty stub helper.",
]


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read(path: Path, label: str, inputs: dict) -> bytes:
    data = path.read_bytes()
    inputs[label] = {"sha256": hashlib.sha256(data).hexdigest()}
    return data


def _upstream(cache: Path, manifest: dict, inputs: dict) -> dict[str, Surface]:
    wheel = cache / manifest["wheel"]
    digest = _sha(wheel)
    if digest != manifest["sha256"]:
        raise ValueError("PySide2 wheel SHA256 does not match pyside-manifest.json")
    inputs[wheel.name] = {"sha256": digest}
    modules = {}
    with ZipFile(wheel) as archive:
        (metadata_name,) = [
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        ]
        metadata = archive.read(metadata_name)
        inputs[metadata_name] = {
            "sha256": hashlib.sha256(metadata).hexdigest(),
            "container": wheel.name,
        }
        if BytesParser().parsebytes(metadata)["Version"] != manifest["version"]:
            raise ValueError(
                "PySide2 wheel version does not match pyside-manifest.json"
            )
        for module in MODULES:
            name = f"PySide2/{module}.pyi"
            data = archive.read(name)
            inputs[name] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "container": wheel.name,
            }
            modules[module] = extract(data)
    return modules


def _native(source: Path, provenance: dict, inputs: dict) -> dict[str, Surface]:
    modules = {}
    for module in NATIVE_MODULES:
        name = f"PythonQt/{module}.pyi"
        data = _read(source / name, name, inputs)
        recorded = provenance.get("merged_outputs", {}).get(name)
        if recorded is not None and recorded != inputs[name]["sha256"]:
            raise ValueError(f"Native SHA256 does not match _provenance.json: {name}")
        modules[module] = extract(data)
    return modules


def build_report(echopy: Path) -> dict:
    """Verify source identities before joining; store logical names, never local paths."""
    inputs: dict = {}
    cache, source = echopy / ".cache/upstream", echopy / "src/fontlab_echopy"
    manifest = json.loads(
        _read(cache / "pyside-manifest.json", "pyside-manifest.json", inputs)
    )
    provenance = json.loads(
        _read(source / "_provenance.json", "_provenance.json", inputs)
    )
    pyside = _upstream(cache, manifest, inputs)
    native = _native(source, provenance, inputs)
    host = provenance.get("native_host", {})
    return {
        "schema_version": 1,
        "pyside_version": manifest["version"],
        "native_host": {
            key: host.get(key)
            for key in ("fontlab_version", "python_version", "qt_version")
        },
        "inputs": inputs,
        "limitations": LIMITATIONS,
        "modules": join_surfaces(pyside, native),
        "native_modules": {
            m: {"classes": sorted(d["classes"]), "members": sorted(d["members"])}
            for m, d in native.items()
        },
    }


def write_reports(report: dict, output: Path, widgets_output: Path) -> None:
    """Both products derive from one join; sorted JSON has no timestamps."""
    classes = report["modules"]["QtWidgets"]["classes"]
    (wheel,) = [v for k, v in report["inputs"].items() if k.endswith(".whl")]
    widgets = {
        "classes": sorted(
            n for n, c in classes.items() if c["native_module"] is not None
        ),
        "pyside_version": report["pyside_version"],
        "wheel_sha256": wheel["sha256"],
        "source": f"https://pypi.org/project/PySide2/{report['pyside_version']}/",
    }
    for path, data in ((output, report), (widgets_output, widgets)):
        path.write_text(
            json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--echopy", type=Path, default=Path("../fontlab-echopy"))
    parser.add_argument("--output", type=Path, default=PACKAGE / "_inventory.json")
    parser.add_argument(
        "--widgets-output", type=Path, default=PACKAGE / "_qtwidgets.json"
    )
    args = parser.parse_args()
    report = build_report(args.echopy)
    write_reports(report, args.output, args.widgets_output)
    for path in (args.output, args.widgets_output):
        print(f"{path.name}: {path.stat().st_size} bytes; SHA256 {_sha(path)}")
    print(
        json.dumps(
            {m: d["summary"] for m, d in report["modules"].items()}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
