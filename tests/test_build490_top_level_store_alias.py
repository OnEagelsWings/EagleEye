"""Internal 490–500 workspaces must never alias their top-level stores."""
import pytest

from eagleeye.bootstrap import paths


@pytest.mark.parametrize("alias,original", [("reports", "data"), ("data", "reports")])
def test_internal_release_rejects_in_workspace_store_alias_before_writing(
    monkeypatch, tmp_path, alias, original
):
    monkeypatch.setattr(paths, "BUILD", "495.0")
    root = tmp_path / "Fälle-Übung"
    root.mkdir()
    (root / original).mkdir()
    marker = root / original / "existing.txt"
    marker.write_text("unchanged", encoding="utf-8")
    try:
        (root / alias).symlink_to(root / original, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable on this runner")

    with pytest.raises(ValueError, match="symbolic links"):
        paths.RuntimePaths.resolve(install_dir=tmp_path / "installation", base_dir=root)
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert not (root / "data" / "eagleeye.db").exists()
