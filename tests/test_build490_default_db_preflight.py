"""Regression: rejected default DB symlink must not initialize report/module dirs."""
from pathlib import Path

import pytest

from eagleeye.bootstrap import paths


@pytest.mark.parametrize("build", ["490", "500"])
def test_rejected_default_db_symlink_has_no_workspace_side_effects(tmp_path, monkeypatch, build):
    monkeypatch.setattr(paths, "BUILD", build)
    installation = tmp_path / "installed"
    installation.mkdir()
    workspace = tmp_path / "internal"
    data = workspace / "data"
    data.mkdir(parents=True)
    legacy = tmp_path / "legacy.db"
    legacy.write_bytes(b"legacy-untouched")
    try:
        (data / "eagleeye.db").symlink_to(legacy)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this host")

    with pytest.raises(ValueError, match="Internal release database cannot contain symbolic links"):
        paths.RuntimePaths.resolve(install_dir=installation, base_dir=workspace)

    assert legacy.read_bytes() == b"legacy-untouched"
    assert not (workspace / "reports").exists()
    assert not (data / "evidence_vault").exists()
