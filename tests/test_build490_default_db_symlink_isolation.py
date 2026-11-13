"""Regression: internal builds must not follow a pre-existing default DB symlink."""
from pathlib import Path

import pytest

from eagleeye.bootstrap import paths


@pytest.mark.parametrize("build", ["490", "500"])
def test_internal_default_database_symlink_cannot_escape_workspace(tmp_path, monkeypatch, build):
    monkeypatch.setattr(paths, "BUILD", build)
    workspace = tmp_path / "internal-workspace"
    install = tmp_path / "installed-app"
    install.mkdir()
    legacy = tmp_path / "legacy" / "eagleeye.db"
    legacy.parent.mkdir()
    legacy.write_bytes(b"legacy data must remain untouched")
    db = workspace / "data" / "eagleeye.db"
    db.parent.mkdir(parents=True)
    try:
        db.symlink_to(legacy)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")

    with pytest.raises(ValueError, match="Internal release database cannot contain symbolic links"):
        paths.RuntimePaths.resolve(install_dir=install, base_dir=workspace)

    assert legacy.read_bytes() == b"legacy data must remain untouched"
    assert not (workspace / "reports").exists()


def test_current_build_explicit_database_rejects_in_workspace_parent_alias(tmp_path, monkeypatch):
    """A symlinked parent must not silently alias a second case database."""
    monkeypatch.setattr(paths, "BUILD", "490")
    workspace = tmp_path / "internal"
    install = tmp_path / "app"
    install.mkdir()
    actual = workspace / "data" / "actual"
    actual.mkdir(parents=True)
    alias = workspace / "data" / "alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")
    target = alias / "cases.db"
    with pytest.raises(ValueError, match="cannot traverse symbolic links"):
        paths.RuntimePaths.resolve(
            install_dir=install, base_dir=workspace, db_path=target
        )
    assert not (actual / "cases.db").exists()
    assert not (workspace / "reports").exists()
