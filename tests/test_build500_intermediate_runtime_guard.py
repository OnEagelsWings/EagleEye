"""Build 500 installer regression: never follow a linked intermediate runtime path."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


INSTALLER = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
spec = importlib.util.spec_from_file_location("eagleeye_install_500_guard", INSTALLER)
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_intermediate_runtime_link_rejected_without_touching_external_directory(tmp_path):
    root = tmp_path / "installation"
    root.mkdir()
    runtime = root / installer.RUNTIME_DIR
    runtime.mkdir()
    external = tmp_path / "legacy-do-not-touch"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    intermediate = runtime / ("Scripts" if os.name == "nt" else "bin")
    try:
        intermediate.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Directory symlink unavailable: {exc}")
    assert installer._runtime_path_linked(root)
    with pytest.raises(RuntimeError, match="Linked runtime paths"):
        installer._ensure_runtime(root, quiet=True)
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert intermediate.is_symlink()
