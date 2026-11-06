"""Regression: a fresh Build 490 must not adopt legacy workspace data."""
from pathlib import Path

from eagleeye.bootstrap import desktop476


def test_build490_default_settings_are_separate_from_legacy(monkeypatch, tmp_path):
    monkeypatch.delenv("EAGLEEYE_SETTINGS_DIR", raising=False)
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    settings = desktop476.settings_directory()
    assert settings.name == "EagleEye-490"
    legacy = settings.parent / "EagleEye"
    legacy.mkdir(parents=True)
    old_workspace = tmp_path / "legacy398"
    old_workspace.mkdir()
    (legacy / "workspace.json").write_text(
        '{"workspace_directory": "' + str(old_workspace).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    install = tmp_path / "installation"
    (install / "data").mkdir(parents=True)
    (install / "data" / "eagleeye.db").write_bytes(b"legacy")
    root = desktop476.resolve_workspace(install)
    assert root == settings / "workspace"
    assert root != old_workspace
    assert root != install
    assert (legacy / "workspace.json").is_file()
    assert (install / "data" / "eagleeye.db").read_bytes() == b"legacy"


def test_build490_explicit_workspace_still_supported(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(tmp_path / "settings"))
    chosen = tmp_path / "Fälle-Übung"
    monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(chosen))
    assert desktop476.resolve_workspace(tmp_path / "install") == chosen.resolve()


def test_build490_runtime_does_not_copy_legacy_database(monkeypatch, tmp_path):
    """An old database in the chosen folder must not be silently promoted."""
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "490.0")
    root = tmp_path / "Fälle-Übung"
    data = root / "data"
    data.mkdir(parents=True)
    legacy = data / "eagleeye_pro_95_0.db"
    legacy.write_bytes(b"legacy database bytes")
    (data / "eagleeye_pro_95_0.db-wal").write_bytes(b"legacy wal")
    (data / "eagleeye_pro_95_0.db-shm").write_bytes(b"legacy shm")

    resolved = paths.RuntimePaths.resolve(install_dir=tmp_path / "install", base_dir=root)
    assert resolved.db_path == data / "eagleeye.db"
    assert not resolved.db_path.exists()
    assert not (data / "eagleeye.db-wal").exists()
    assert not (data / "eagleeye.db-shm").exists()
    assert legacy.read_bytes() == b"legacy database bytes"
    assert (data / "eagleeye_pro_95_0.db-wal").read_bytes() == b"legacy wal"
    assert (data / "eagleeye_pro_95_0.db-shm").read_bytes() == b"legacy shm"


def test_build490_runtime_uses_explicit_database_without_legacy_copy(monkeypatch, tmp_path):
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "490.0")
    root = tmp_path / "workspace"
    explicit = root / "custom" / "case.sqlite3"
    resolved = paths.RuntimePaths.resolve(
        install_dir=tmp_path / "install", base_dir=root, db_path=explicit
    )
    assert resolved.db_path == explicit
    assert explicit.parent.is_dir()
    assert not explicit.exists()
