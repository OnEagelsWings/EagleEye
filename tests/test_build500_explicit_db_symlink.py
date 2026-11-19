"""Build 500: explicit database path must not traverse a symlinked parent."""
import pytest
from eagleeye.bootstrap import paths


def test_build500_rejects_symlinked_explicit_database_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "BUILD", "500.0")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "unrelated-case"
    outside.mkdir()
    alias = workspace / "alias"
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable on this runner")

    with pytest.raises(ValueError, match="symbolic link"):
        paths.RuntimePaths.resolve(
            install_dir=tmp_path / "install",
            base_dir=workspace,
            db_path=alias / "nested" / "case.db",
        )
    assert not (outside / "nested").exists()
    assert not (workspace / "data").exists()


def test_build500_explicit_database_regular_nested_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "BUILD", "500.0")
    workspace = tmp_path / "workspace"
    database = workspace / "nested" / "case.db"
    result = paths.RuntimePaths.resolve(
        install_dir=tmp_path / "install",
        base_dir=workspace,
        db_path=database,
    )
    assert result.db_path == database
    assert database.parent.is_dir()
