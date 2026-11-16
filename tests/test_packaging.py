# this_file: tests/test_packaging.py
"""Actual wheels preserve the public API inventory's licence and provenance."""

import os
import sys
import textwrap
import subprocess
import tarfile
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest


def test_wheel_when_built_then_includes_exact_licence_and_notice(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    environment = {
        name: value for name, value in os.environ.items()
        if not name.startswith("SETUPTOOLS_SCM_PRETEND_VERSION")
    }
    result = subprocess.run(
        ["uv", "build", "--no-config", "--wheel", "--out-dir", str(tmp_path)],
        cwd=root, env=environment, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"Expected one wheel, got {wheels}"
    with ZipFile(wheels[0]) as wheel:
        metadata_path = next(
            name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(wheel.read(metadata_path))
        for filename in ("LICENSE", "NOTICE"):
            path = metadata_path.removesuffix("METADATA") + "licenses/" + filename
            assert path in wheel.namelist(), f"Wheel omits {filename}"
            assert wheel.read(path) == (root / filename).read_bytes(), filename
            assert filename in metadata.get_all("License-File", []), filename


def test_sdist_when_guide_relocated_then_keeps_it_and_excludes_private_plan(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    environment = {name: value for name, value in os.environ.items() if not name.startswith("SETUPTOOLS_SCM_PRETEND_VERSION")}
    result = subprocess.run(
        ["uv", "build", "--no-config", "--sdist", "--out-dir", str(tmp_path)],
        cwd=root, env=environment, capture_output=True, text=True,
        timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr
    archives = list(tmp_path.glob("*.tar.gz"))
    assert len(archives) == 1, "Expected one real sdist"
    with tarfile.open(archives[0]) as archive:
        names = archive.getnames()
        guide = next((name for name in names if name.endswith("/src_docs/md/pythonqt-compatibility.md")), None)
        assert guide is not None, "Sdist must retain the relocated complete compatibility guide"
        assert archive.extractfile(guide).read() == (root / "src_docs/md/pythonqt-compatibility.md").read_bytes()
        assert not any("embedded-app-runner.md" in name for name in names), "Private planning must not enter the distribution"
        installer = next(name for name in names if name.endswith("/install.vfpy"))
        assert archive.extractfile(installer).read() == (root / "install.vfpy").read_bytes()
        assert archive.getmember(installer).mode == (root / "install.vfpy").stat().st_mode & 0o777


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "pythonqtside"
LAZY_MODULES = ("compat", "Qt", "QtCore", "QtGui", "QtNetwork", "QtOpenGL", "QtSvg", "QtUiTools",
                "QtWidgets", "QtXmlPatterns")


def _run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, f"{command}: {result.stdout}\n{result.stderr}"
    return result


@pytest.fixture(scope="module")
def wheel_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("wheel")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SETUPTOOLS_SCM_PRETEND_VERSION")}
    _run("uv", "build", "--no-config", "--wheel", "--out-dir", str(out), env=env)
    (wheel,) = out.glob("*.whl")
    return wheel


def test_wheel_when_built_then_carries_every_package_file_and_nothing_else(wheel_path: Path) -> None:
    expected = {"pythonqtside/" + p.relative_to(PACKAGE).as_posix()
                for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    with ZipFile(wheel_path) as wheel:
        names = {n for n in wheel.namelist() if ".dist-info/" not in n}
        for name in names:
            assert wheel.read(name) == (PACKAGE.parent / name).read_bytes(), f"Wheel changes {name}"
    assert names == expected, f"missing {expected - names}, extra {names - expected}"
    assert {n for n in names if n.endswith(".json")} >= {"pythonqtside/_inventory.json", "pythonqtside/_qtwidgets.json"}


def test_wheel_when_built_then_metadata_names_package_and_single_dependency(wheel_path: Path) -> None:
    with ZipFile(wheel_path) as wheel:
        path = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(wheel.read(path))
    assert metadata["Name"] == "pythonqtside" and metadata["License-Expression"] == "Apache-2.0"
    requires = [r for r in metadata.get_all("Requires-Dist", []) if "extra" not in r]
    assert [r.split(">")[0].strip() for r in requires] == ["fontlab-echopy"], requires


def test_installed_wheel_when_imported_outside_repo_then_loads_from_site_packages(wheel_path: Path, tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    _run("uv", "venv", "--python", sys.executable, str(venv))
    python = venv / "bin" / "python"
    _run("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel_path))
    probe = textwrap.dedent(f"""
        import json, pathlib, pythonqtside
        assert "site-packages" in pythonqtside.__file__, pythonqtside.__file__
        for name in {LAZY_MODULES!r}:
            module = getattr(pythonqtside, name)
            assert "site-packages" in module.__file__, (name, module.__file__)
        data = pathlib.Path(pythonqtside.__file__).parent
        assert all(json.loads(p.read_text()) is not None for p in data.glob("_*.json"))
        print(len(list(data.glob("_*.json"))))
    """)
    env = {"PATH": "/usr/bin:/bin"}
    assert _run(str(python), "-c", probe, cwd=tmp_path, env=env).stdout.strip() == str(len(list(PACKAGE.glob("_*.json"))))


ECHOPY = ROOT.parent / "fontlab-echopy"


def test_installed_wheels_when_echopy_sibling_built_then_ordinary_tuple_resolves_from_site_packages(
    wheel_path: Path, tmp_path: Path
) -> None:
    """Install the real Echopy wheel beside this wheel (no PYTHONPATH) and import every lazy module."""
    if not (ECHOPY / "pyproject.toml").is_file():
        pytest.skip("fontlab-echopy sibling checkout is not present (private repository)")
    out = tmp_path / "echopy-wheel"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SETUPTOOLS_SCM_PRETEND_VERSION")}
    _run("uv", "build", "--no-config", "--wheel", "--out-dir", str(out), str(ECHOPY), env=env)
    (echopy_wheel,) = out.glob("*.whl")
    venv = tmp_path / "venv"
    _run("uv", "venv", "--python", sys.executable, str(venv))
    python = venv / "bin" / "python"
    _run("uv", "pip", "install", "--python", str(python), "--no-deps", str(echopy_wheel), str(wheel_path))
    probe = textwrap.dedent(f"""
        import importlib.metadata as md, pythonqtside, fontlab_echopy
        for module in (pythonqtside, fontlab_echopy):
            assert "site-packages" in module.__file__, module.__file__
        for name in {LAZY_MODULES!r}:
            assert "site-packages" in getattr(pythonqtside, name).__file__, name
        print(md.version("fontlab-echopy"))
    """)
    version = _run(str(python), "-c", probe, cwd=tmp_path, env={"PATH": "/usr/bin:/bin"}).stdout.strip()
    assert version in echopy_wheel.name, (version, echopy_wheel.name)
