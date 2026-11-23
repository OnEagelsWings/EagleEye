"""Build 500 must never reuse a runtime linked to another installation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_linked_runtime_is_rejected_before_probe_or_install(tmp_path: Path):
    installer = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = importlib.util.spec_from_file_location("eagleeye_500_runtime_links", installer)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    external = tmp_path / "legacy-runtime"
    external.mkdir()
    root = tmp_path / "build500"
    root.mkdir()
    link = root / module.RUNTIME_DIR
    try:
        link.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable in this test environment")

    assert module._probe(root) == {"ready": False, "reason": "runtime_link_forbidden"}
    with pytest.raises(RuntimeError, match="Linked runtime paths"):
        module._ensure_runtime(root, quiet=True)
    assert external.is_dir()
