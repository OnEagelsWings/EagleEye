"""Build 500 installer must not execute Python through a linked runtime parent."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


def _installer():
    path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = importlib.util.spec_from_file_location("installer500_parent_link_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_linked_runtime_python_parent_is_rejected(tmp_path):
    installer = _installer()
    runtime = tmp_path / installer.RUNTIME_DIR
    runtime.mkdir()
    outside = tmp_path / "external_python"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    parent = runtime / ("Scripts" if os.name == "nt" else "bin")
    try:
        parent.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    assert installer._runtime_path_linked(tmp_path)
    assert installer._probe(tmp_path)["reason"] == "runtime_link_forbidden"
    with pytest.raises(RuntimeError, match="Linked runtime"):
        installer._ensure_runtime(tmp_path, quiet=True)
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
