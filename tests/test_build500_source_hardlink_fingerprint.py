"""Build 500 source fingerprint must not read shared hard-linked inputs."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("eagleeye_installer_500_hardlink", ROOT / "INSTALL_EAGLEEYE_500.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def test_source_fingerprint_rejects_hardlinked_manifest(tmp_path: Path) -> None:
    if not hasattr(os, "link"):
        pytest.skip("Hard links unavailable")
    root = tmp_path / "release"
    root.mkdir()
    for relative in (
        "INSTALL_EAGLEEYE_500.py", "pyproject.toml",
        "wheelhouse/MANIFEST-SHA256.json", "EAGLEEYE_PRO_458_0.py",
        "RELEASE_MANIFEST_BUILD_458_0.json", "START_EAGLEEYE_PRO.bat", "START_EAGLEEYE_PRO.sh", "EAGLEEYE_INSTALL_DIAGNOSE_500.bat",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic", encoding="utf-8")
    for directory in ("src/eagleeye", "eagleeye_pro", "alembic_104_1"):
        (root / directory).mkdir(parents=True)
    external = tmp_path / "shared-manifest"
    external.write_text("synthetic", encoding="utf-8")
    manifest = root / "wheelhouse/MANIFEST-SHA256.json"
    manifest.unlink()
    try:
        os.link(external, manifest)
    except OSError:
        pytest.skip("Filesystem does not support hard links")
    with pytest.raises(RuntimeError, match="hard-linked Build 500 source"):
        installer._source_fingerprint(root)
