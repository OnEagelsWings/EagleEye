"""Build 490/500 must not initialize through a symlinked workspace root."""

import pytest

from eagleeye.bootstrap import paths


@pytest.mark.parametrize("build", ["490", "500"])
def test_internal_workspace_root_symlink_is_rejected_before_writes(tmp_path, monkeypatch, build):
    monkeypatch.setattr(paths, "BUILD", build)
    installation = tmp_path / "installed"
    installation.mkdir()
    legacy_workspace = tmp_path / "legacy-workspace"
    legacy_workspace.mkdir()
    marker = legacy_workspace / "existing.txt"
    marker.write_text("untouched", encoding="utf-8")
    alias = tmp_path / "internal-alias"
    try:
        alias.symlink_to(legacy_workspace, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this host")

    with pytest.raises(ValueError, match="Internal release workspace cannot be a symbolic link"):
        paths.RuntimePaths.resolve(install_dir=installation, base_dir=alias)

    assert marker.read_text(encoding="utf-8") == "untouched"
    assert not (legacy_workspace / "data").exists()
    assert not (legacy_workspace / "reports").exists()
