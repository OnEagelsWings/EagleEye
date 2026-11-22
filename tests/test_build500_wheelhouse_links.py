"""Build 500: offline wheel manifest must not follow filesystem links."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


def _manifest_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build500_wheel_manifest.py"
    spec = importlib.util.spec_from_file_location("build500_wheel_manifest_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel(root: Path) -> Path:
    wheel = root / "eagleeye_personosint_pro-500.0.0-py3-none-any.whl"
    wheel.write_bytes(b"synthetic test wheel")
    return wheel


def test_rejects_symlinked_wheelhouse(tmp_path: Path):
    real = tmp_path / "real"
    real.mkdir()
    _wheel(real)
    link = tmp_path / "wheelhouse"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted")
    with pytest.raises(RuntimeError, match="Wheelhouse symlink"):
        _manifest_module().main(link)


def test_rejects_symlinked_wheel(tmp_path: Path):
    root = tmp_path / "wheelhouse"
    root.mkdir()
    external = _wheel(tmp_path)
    link = root / external.name
    try:
        link.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted")
    with pytest.raises(RuntimeError, match="linked or non-file wheel"):
        _manifest_module().main(root)


def test_rejects_hardlinked_wheel(tmp_path: Path):
    root = tmp_path / "wheelhouse"
    root.mkdir()
    external = _wheel(tmp_path)
    try:
        os.link(external, root / external.name)
    except OSError:
        pytest.skip("Hardlinks not supported")
    with pytest.raises(RuntimeError, match="hardlinked wheel"):
        _manifest_module().main(root)


def test_rejects_symlinked_manifest(tmp_path: Path):
    root = tmp_path / "wheelhouse"
    root.mkdir()
    _wheel(root)
    target = tmp_path / "outside.json"
    target.write_text("unchanged", encoding="utf-8")
    try:
        (root / "MANIFEST-SHA256.json").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted")
    with pytest.raises(RuntimeError, match="manifest symlink"):
        _manifest_module().main(root)
    assert target.read_text(encoding="utf-8") == "unchanged"
