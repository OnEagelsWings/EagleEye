"""Internal-release workspace selection must not normalize away symlink aliases."""
import pytest
from eagleeye.bootstrap import desktop476


def test_internal_workspace_alias_rejected_without_settings_mutation(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, 'BUILD', '490.0')
    settings = tmp_path / 'settings'
    monkeypatch.setenv('EAGLEEYE_SETTINGS_DIR', str(settings))
    target = tmp_path / 'other-workspace'
    target.mkdir()
    marker = target / 'original.txt'
    marker.write_text('unchanged', encoding='utf-8')
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Directory symlinks unavailable')
    with pytest.raises(ValueError, match='symbolischen'):
        desktop476.remember_workspace(alias, install_dir=tmp_path / 'install')
    monkeypatch.setenv('EAGLEEYE_DATA_DIR', str(alias))
    with pytest.raises(ValueError, match='symbolischen'):
        desktop476.resolve_workspace(tmp_path / 'install')
    assert marker.read_text(encoding='utf-8') == 'unchanged'
    assert not (settings / 'workspace.json').exists()


def test_legacy_workspace_alias_contract_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, 'BUILD', '398.0')
    target = tmp_path / 'legacy-workspace'
    target.mkdir()
    alias = tmp_path / 'legacy-alias'
    try:
        alias.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Directory symlinks unavailable')
    assert desktop476._local_path(alias) == target.resolve()
