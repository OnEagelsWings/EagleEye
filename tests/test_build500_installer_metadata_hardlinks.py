"""Build 500: installer metadata must not overwrite files shared with legacy installations."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


def _installer():
    path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = importlib.util.spec_from_file_location("eagleeye_install500_hardlinks", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("filename", ["install-pip-500.log", "install-receipt-500.json", "install-receipt-500.tmp"])
def test_shared_installer_metadata_is_rejected_without_modifying_original(tmp_path, filename):
    installer = _installer()
    original = tmp_path / "legacy" / filename
    original.parent.mkdir()
    original.write_text("legacy data must remain unchanged", encoding="utf-8")
    linked = tmp_path / "new" / filename
    linked.parent.mkdir()
    try:
        os.link(original, linked)
    except (OSError, NotImplementedError):
        pytest.skip("Hard links unavailable on this filesystem")
    with pytest.raises(RuntimeError, match="hard-linked"):
        installer._reject_shared_installer_file(linked)
    assert original.read_text(encoding="utf-8") == "legacy data must remain unchanged"


def test_normal_installer_metadata_is_accepted(tmp_path):
    installer = _installer()
    target = tmp_path / "install-pip-500.log"
    installer._reject_shared_installer_file(target)
    target.write_text("new release", encoding="utf-8")
    installer._reject_shared_installer_file(target)
