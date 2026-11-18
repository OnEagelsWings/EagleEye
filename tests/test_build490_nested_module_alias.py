"""Build 490: nested module paths must not alias other case stores."""
import pytest
from eagleeye.bootstrap import paths


def test_nested_module_symlink_alias_rejected_before_initialization(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD", "490")
    workspace = tmp_path / "new-internal-workspace"
    install = tmp_path / "program"
    install.mkdir()
    source = workspace / "data" / "actual"
    source.mkdir(parents=True)
    alias = workspace / "data" / "enterprise_95"
    try:
        alias.symlink_to(source, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this host")
    with pytest.raises(ValueError, match="cannot traverse symbolic links"):
        paths.RuntimePaths.resolve(install_dir=install, base_dir=workspace)
    assert not (workspace / "reports").exists()
    assert not (source / "eagleeye.db").exists()
