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


def test_internal_release_default_runtime_is_separate(monkeypatch, tmp_path):
    """Build 490–500 must not select the historical runtime root."""
    from eagleeye.bootstrap import paths

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setattr(paths, "BUILD", "490.0")
    internal = paths.default_runtime_root()
    monkeypatch.setattr(paths, "BUILD", "398.0")
    legacy = paths.default_runtime_root()
    assert internal != legacy
    assert not internal.exists()
    assert not legacy.exists()


def test_future_internal_release_does_not_copy_legacy_database(monkeypatch, tmp_path):
    """The 490 fix must remain effective through the Build 500 release."""
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "500.0")
    data = tmp_path / "workspace" / "data"
    data.mkdir(parents=True)
    (data / "eagleeye_pro_95_0.db").write_bytes(b"legacy")
    resolved = paths.RuntimePaths.resolve(
        install_dir=tmp_path / "install", base_dir=tmp_path / "workspace"
    )
    assert resolved.db_path == data / "eagleeye.db"
    assert not resolved.db_path.exists()
    assert (data / "eagleeye_pro_95_0.db").read_bytes() == b"legacy"


def test_build500_desktop_uses_isolated_settings_and_fresh_workspace(monkeypatch, tmp_path):
    """A future release must not regress to the legacy desktop settings."""
    monkeypatch.setattr(desktop476, "BUILD", "500.0")
    from eagleeye.bootstrap import paths
    monkeypatch.setattr(paths, "BUILD", "500.0")
    monkeypatch.delenv("EAGLEEYE_SETTINGS_DIR", raising=False)
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    settings = desktop476.settings_directory()
    assert settings.name == "EagleEye-490"
    old = settings.parent / "EagleEye"
    old.mkdir(parents=True)
    old_workspace = tmp_path / "legacy398"
    old_workspace.mkdir()
    (old / "workspace.json").write_text(
        '{"workspace_directory": "' + str(old_workspace).replace("\\\\", "\\\\\\\\") + '"}',
        encoding="utf-8",
    )
    install = tmp_path / "install"
    (install / "data").mkdir(parents=True)
    (install / "data" / "eagleeye.db").write_bytes(b"legacy")
    resolved = desktop476.resolve_workspace(install)
    assert resolved == settings / "workspace"
    assert resolved != old_workspace
    assert resolved != install
    assert (install / "data" / "eagleeye.db").read_bytes() == b"legacy"


def test_internal_diagnostics_do_not_treat_legacy_database_as_current(monkeypatch, tmp_path):
    """A legacy-only workspace must not appear initialized for Build 490/500."""
    from eagleeye.interfaces.web import server

    monkeypatch.setattr(server, "_read_running_workspace", lambda *args, **kwargs: None)
    root = tmp_path / "workspace"
    data = root / "data"
    data.mkdir(parents=True)
    (data / "eagleeye_pro_95_0.db").write_bytes(b"old database")
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(desktop476, "BUILD", build)
        assert desktop476.diagnostics(root)["database_present"] is False
    (data / "eagleeye.db").write_bytes(b"new database")
    assert desktop476.diagnostics(root)["database_present"] is True
    monkeypatch.setattr(desktop476, "BUILD", "398.0")
    (data / "eagleeye.db").unlink()
    assert desktop476.diagnostics(root)["database_present"] is True


def test_internal_release_rejects_explicit_legacy_database_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(tmp_path / "settings"))
    legacy = tmp_path / "legacy398"
    data = legacy / "data"
    data.mkdir(parents=True)
    old = data / "eagleeye_pro_95_0.db"
    old.write_bytes(b"legacy database")
    monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(legacy))
    import pytest
    with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
        desktop476.resolve_workspace(tmp_path / "install")
    assert old.read_bytes() == b"legacy database"
    assert not (data / "eagleeye.db").exists()
    assert not (tmp_path / "settings" / "workspace.json").exists()


def test_internal_release_rejects_saved_legacy_database_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, "BUILD", "500.0")
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    legacy = tmp_path / "legacy398"
    data = legacy / "data"
    data.mkdir(parents=True)
    (data / "eagleeye_pro_95_0.db").write_bytes(b"legacy")
    import json
    original = json.dumps({"workspace_directory": str(legacy)})
    (settings / "workspace.json").write_text(original, encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
        desktop476.resolve_workspace(tmp_path / "install")
    assert (settings / "workspace.json").read_text(encoding="utf-8") == original
    assert not (data / "eagleeye.db").exists()


def test_folder_picker_cannot_persist_legacy_workspace(monkeypatch, tmp_path):
    """The interactive picker must not bypass the internal-release isolation gate."""
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(tmp_path / "settings"))
    legacy = tmp_path / "legacy398"
    data = legacy / "data"
    data.mkdir(parents=True)
    (data / "eagleeye_pro_95_0.db").write_bytes(b"legacy")
    with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
        desktop476.remember_workspace(legacy)
    assert not (tmp_path / "settings" / "workspace.json").exists()
    assert (data / "eagleeye_pro_95_0.db").read_bytes() == b"legacy"


def test_folder_picker_persists_fresh_internal_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(tmp_path / "settings"))
    root = tmp_path / "Fälle-Übung"
    assert desktop476.remember_workspace(root) == root.resolve()
    assert desktop476.resolve_workspace(tmp_path / "install") == root.resolve()


def test_internal_release_rejects_orphaned_legacy_sqlite_sidecars(monkeypatch, tmp_path):
    """An interrupted legacy database must not be silently adopted."""
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    for suffix in ("-wal", "-shm"):
        root = tmp_path / ("legacy" + suffix)
        data = root / "data"
        data.mkdir(parents=True)
        sidecar = data / ("eagleeye_pro_95_0.db" + suffix)
        sidecar.write_bytes(b"legacy sidecar")
        with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
            desktop476.remember_workspace(root)
        assert sidecar.read_bytes() == b"legacy sidecar"
    assert not (tmp_path / "settings" / "workspace.json").exists()


def test_internal_release_never_uses_program_directory_as_workspace(monkeypatch, tmp_path):
    """An explicit or previously saved install-root selection must fail closed."""
    import json
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    install = tmp_path / "Programm-Übung"
    install.mkdir()
    (install / "data").mkdir()
    original = install / "data" / "eagleeye.db"
    original.write_bytes(b"existing installation database")

    monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(install))
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    assert original.read_bytes() == b"existing installation database"
    assert not (settings / "workspace.json").exists()

    monkeypatch.delenv("EAGLEEYE_DATA_DIR")
    saved = json.dumps({"workspace_directory": str(install)})
    (settings / "workspace.json").write_text(saved, encoding="utf-8")
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    assert original.read_bytes() == b"existing installation database"
    assert (settings / "workspace.json").read_text(encoding="utf-8") == saved


def test_folder_picker_rejects_program_directory_before_persisting(monkeypatch, tmp_path):
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    settings = tmp_path / "settings"
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    install = tmp_path / "EagleEye-Programm"
    install.mkdir()
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.remember_workspace(install, install_dir=install)
    assert not (settings / "workspace.json").exists()

    workspace = tmp_path / "Eigene-Daten"
    assert desktop476.remember_workspace(workspace, install_dir=install) == workspace.resolve()
    assert workspace.is_dir()


def test_internal_release_rejects_nested_install_data_without_mutation(monkeypatch, tmp_path):
    """A data subdirectory of the program installation is not an isolated workspace."""
    import json
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "500.0")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    install = tmp_path / "EagleEye-Programm"
    nested = install / "data" / "Fälle-Übung"
    nested.mkdir(parents=True)
    marker = nested / "existing-case.txt"
    marker.write_text("unchanged", encoding="utf-8")

    monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(nested))
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.remember_workspace(nested, install_dir=install)
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert not (settings / "workspace.json").exists()

    monkeypatch.delenv("EAGLEEYE_DATA_DIR")
    saved = json.dumps({"workspace_directory": str(nested)})
    (settings / "workspace.json").write_text(saved, encoding="utf-8")
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    assert (settings / "workspace.json").read_text(encoding="utf-8") == saved


def test_internal_release_rejects_workspace_containing_program_tree(monkeypatch, tmp_path):
    """A workspace parent is not isolated when it contains the installation."""
    import json
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    root = tmp_path / "gemeinsamer-Ordner"
    install = root / "Programm-Übung"
    install.mkdir(parents=True)
    marker = install / "do-not-touch.txt"
    marker.write_text("legacy install unchanged", encoding="utf-8")

    monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(root))
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.remember_workspace(root, install_dir=install)
    assert not (settings / "workspace.json").exists()

    monkeypatch.delenv("EAGLEEYE_DATA_DIR")
    saved = json.dumps({"workspace_directory": str(root)})
    (settings / "workspace.json").write_text(saved, encoding="utf-8")
    with pytest.raises(ValueError, match="getrennt"):
        desktop476.resolve_workspace(install)
    assert (settings / "workspace.json").read_text(encoding="utf-8") == saved
    assert marker.read_text(encoding="utf-8") == "legacy install unchanged"


def test_internal_release_rejects_root_level_legacy_sqlite_without_mutation(monkeypatch, tmp_path):
    """Some older workspaces store their database at the root, not in data/."""
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "500.0")
    settings = tmp_path / "new-settings"
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    install = tmp_path / "new-install"
    install.mkdir()
    for suffix in ("", "-wal", "-shm"):
        root = tmp_path / ("legacy-root" + (suffix or "-db"))
        root.mkdir()
        original = root / ("eagleeye_pro_95_0.db" + suffix)
        original.write_bytes(b"legacy original")
        with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
            desktop476.remember_workspace(root, install_dir=install)
        assert original.read_bytes() == b"legacy original"
        assert not (root / "data" / "eagleeye.db").exists()
        assert not (settings / "workspace.json").exists()
        monkeypatch.setenv("EAGLEEYE_DATA_DIR", str(root))
        with pytest.raises(ValueError, match="ältere EagleEye-Datenbank"):
            desktop476.resolve_workspace(install)
        monkeypatch.delenv("EAGLEEYE_DATA_DIR")
        assert original.read_bytes() == b"legacy original"


def test_internal_release_rejects_explicit_legacy_database_override(monkeypatch, tmp_path):
    """A direct RuntimePaths caller cannot reopen the Build 398 SQLite file."""
    import pytest
    from eagleeye.bootstrap import paths

    legacy_dir = tmp_path / "Build398"
    legacy_dir.mkdir()
    legacy = legacy_dir / "eagleeye_pro_95_0.db"
    legacy.write_bytes(b"original legacy database")
    workspace = tmp_path / "new-workspace"
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        for suffix in ("", "-wal", "-shm"):
            with pytest.raises(ValueError, match="legacy database"):
                paths.RuntimePaths.resolve(
                    install_dir=tmp_path / "new-install",
                    base_dir=workspace,
                    db_path=str(legacy) + suffix,
                )
    assert legacy.read_bytes() == b"original legacy database"
    assert not workspace.exists()


def test_internal_explicit_database_cannot_escape_workspace(monkeypatch, tmp_path):
    """Reject renamed legacy SQLite files and traversal before creating folders."""
    import pytest
    from eagleeye.bootstrap import paths

    workspace = tmp_path / "new-workspace"
    install = tmp_path / "new-install"
    old = tmp_path / "Build398" / "renamed.sqlite3"
    old.parent.mkdir()
    old.write_bytes(b"legacy bytes")
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        for chosen in (old, workspace / ".." / "Build398" / "renamed.sqlite3"):
            with pytest.raises(ValueError, match="inside its workspace"):
                paths.RuntimePaths.resolve(
                    install_dir=install, base_dir=workspace, db_path=chosen
                )
    assert old.read_bytes() == b"legacy bytes"
    assert not workspace.exists()


def test_internal_explicit_database_can_use_workspace_subfolder(monkeypatch, tmp_path):
    """A legitimate explicitly chosen workspace-local database remains supported."""
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "500.0")
    workspace = tmp_path / "Fälle"
    db = workspace / "custom" / "new.sqlite3"
    resolved = paths.RuntimePaths.resolve(
        install_dir=tmp_path / "program", base_dir=workspace, db_path=db
    )
    assert resolved.db_path == db
    assert db.parent.is_dir()
    assert not db.exists()


def test_internal_runtime_rejects_overlapping_installation_without_mutation(monkeypatch, tmp_path):
    """Direct RuntimePaths callers must not bypass desktop workspace isolation."""
    import pytest
    from eagleeye.bootstrap import paths

    install = tmp_path / "Programm-Übung"
    install.mkdir()
    marker = install / "original.txt"
    marker.write_text("unchanged", encoding="utf-8")
    cases = (install, install / "nested-workspace", tmp_path)
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        for root in cases:
            with pytest.raises(ValueError, match="separate from installation"):
                paths.RuntimePaths.resolve(install_dir=install, base_dir=root)
            assert not (root / "data").exists()
            assert marker.read_text(encoding="utf-8") == "unchanged"


def test_legacy_runtime_overlapping_installation_contract_unchanged(monkeypatch, tmp_path):
    """The new guard applies only to the internal release line."""
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "398.0")
    install = tmp_path / "legacy-program"
    resolved = paths.RuntimePaths.resolve(install_dir=install, base_dir=install)
    assert resolved.data_dir == install / "data"
    assert resolved.data_dir.is_dir()


def test_internal_release_rejects_redirected_data_and_reports(monkeypatch, tmp_path):
    """Symlinked workspace subfolders cannot redirect writes into legacy data."""
    import os
    import pytest
    from eagleeye.bootstrap import paths

    workspace = tmp_path / "new-workspace"
    legacy = tmp_path / "Build398"
    legacy.mkdir()
    marker = legacy / "untouched.txt"
    marker.write_text("legacy", encoding="utf-8")
    workspace.mkdir()
    for folder in ("data", "reports"):
        redirect = workspace / folder
        try:
            redirect.symlink_to(legacy, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Directory symlinks unavailable on this platform")
        for build in ("490.0", "500.0"):
            monkeypatch.setattr(paths, "BUILD", build)
            with pytest.raises(ValueError, match="inside the workspace"):
                paths.RuntimePaths.resolve(
                    install_dir=tmp_path / "new-install", base_dir=workspace
                )
        redirect.unlink()
    assert marker.read_text(encoding="utf-8") == "legacy"
    assert not (legacy / "eagleeye.db").exists()


def test_internal_release_rejects_nested_module_symlink_before_writes(monkeypatch, tmp_path):
    """An evidence subfolder cannot redirect new case files into Build 398."""
    import pytest
    from eagleeye.bootstrap import paths

    workspace = tmp_path / "new-workspace"
    data = workspace / "data"
    data.mkdir(parents=True)
    legacy = tmp_path / "Build398"
    legacy.mkdir()
    marker = legacy / "untouched.txt"
    marker.write_text("legacy", encoding="utf-8")
    try:
        (data / "evidence_vault").symlink_to(legacy, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks unavailable on this platform")
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        with pytest.raises(ValueError, match="module directories"):
            paths.RuntimePaths.resolve(
                install_dir=tmp_path / "new-install", base_dir=workspace
            )
    assert marker.read_text(encoding="utf-8") == "legacy"
    assert not (legacy / "eagleeye.db").exists()
    assert not (workspace / "reports").exists()


def test_internal_release_rejects_workspace_local_database_alias(monkeypatch, tmp_path):
    """An existing SQLite symlink must not alias another case DB in the same workspace."""
    import pytest
    from eagleeye.bootstrap import paths

    workspace = tmp_path / "new-workspace"
    data = workspace / "data"
    data.mkdir(parents=True)
    existing = data / "other-case.sqlite3"
    existing.write_bytes(b"existing case unchanged")
    alias = data / "eagleeye.db"
    try:
        alias.symlink_to(existing)
    except (OSError, NotImplementedError):
        pytest.skip("File symlinks unavailable on this platform")
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        for chosen in (None, alias):
            with pytest.raises(ValueError, match="symbolic link"):
                paths.RuntimePaths.resolve(
                    install_dir=tmp_path / "program", base_dir=workspace, db_path=chosen
                )
    assert existing.read_bytes() == b"existing case unchanged"
    assert not (workspace / "reports").exists()


def test_internal_release_rejects_redirected_sqlite_sidecars_before_mutation(monkeypatch, tmp_path):
    """SQLite must not follow pre-planted WAL/SHM symlinks outside the workspace."""
    import pytest
    from eagleeye.bootstrap import paths

    monkeypatch.setattr(paths, "BUILD", "490.0")
    for suffix in ("-wal", "-shm"):
        root = tmp_path / ("workspace" + suffix)
        data = root / "data"
        data.mkdir(parents=True)
        outside = tmp_path / ("legacy" + suffix)
        outside.write_bytes(b"legacy sidecar")
        link = data / ("eagleeye.db" + suffix)
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks unavailable on this platform")
        with pytest.raises(ValueError, match="sidecars"):
            paths.RuntimePaths.resolve(install_dir=tmp_path / "install", base_dir=root)
        assert outside.read_bytes() == b"legacy sidecar"
        assert link.is_symlink()
        assert not (root / "reports").exists()


def test_internal_explicit_database_rejects_symlinked_sqlite_sidecars(monkeypatch, tmp_path):
    """An explicit DB cannot redirect SQLite WAL/SHM writes into legacy data."""
    import pytest
    from eagleeye.bootstrap import paths

    legacy = tmp_path / "Build398"
    legacy.mkdir()
    target = legacy / "untouched.sqlite3"
    target.write_bytes(b"legacy untouched")
    for build in ("490.0", "500.0"):
        monkeypatch.setattr(paths, "BUILD", build)
        for suffix in ("-wal", "-shm"):
            root = tmp_path / (build + suffix)
            root.mkdir()
            explicit = root / "custom.sqlite3"
            Path(str(explicit) + suffix).symlink_to(target)
            with pytest.raises(ValueError, match="symbolic links"):
                paths.RuntimePaths.resolve(
                    install_dir=tmp_path / "install", base_dir=root,
                    db_path=explicit,
                )
            assert not (root / "data").exists()
            assert target.read_bytes() == b"legacy untouched"


def test_workspace_picker_rejects_redirected_data_directory(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(desktop476, 'BUILD', '490.0')
    monkeypatch.setenv('EAGLEEYE_SETTINGS_DIR', str(tmp_path / 'settings'))
    root = tmp_path / 'fresh'
    root.mkdir()
    legacy = tmp_path / 'legacy398'
    legacy.mkdir()
    (root / 'data').symlink_to(legacy, target_is_directory=True)
    with pytest.raises(ValueError, match='umgeleitete Datenverzeichnisse'):
        desktop476.remember_workspace(root, install_dir=tmp_path / 'install')
    assert not (tmp_path / 'settings' / 'workspace.json').exists()
    assert (root / 'data').is_symlink()


def test_folder_picker_rejects_redirected_evidence_module_before_saving(monkeypatch, tmp_path):
    """A redirected evidence vault must not persist a poisoned workspace selection."""
    import os
    import pytest

    monkeypatch.setattr(desktop476, "BUILD", "490.0")
    settings = tmp_path / "settings"
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    root = tmp_path / "fresh-workspace"
    data = root / "data"
    data.mkdir(parents=True)
    legacy_vault = tmp_path / "old-evidence"
    legacy_vault.mkdir()
    marker = legacy_vault / "original.txt"
    marker.write_text("unchanged", encoding="utf-8")
    try:
        (data / "evidence_vault").symlink_to(legacy_vault, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks require privileges on this platform")
    with pytest.raises(ValueError, match="umgeleitete Datenverzeichnisse"):
        desktop476.remember_workspace(root)
    assert marker.read_text(encoding="utf-8") == "unchanged"
    assert not (settings / "workspace.json").exists()


def test_build490_rejects_in_workspace_evidence_alias(monkeypatch, tmp_path):
    """A symlink to a sibling store must not merge distinct evidence namespaces."""
    import pytest
    from eagleeye.bootstrap.paths import RuntimePaths
    import eagleeye.bootstrap.paths as paths

    monkeypatch.setattr(paths, "BUILD", "490.0")
    root = tmp_path / "fresh"
    evidence = root / "data" / "evidence_vault"
    other = root / "data" / "search_captures"
    other.mkdir(parents=True)
    try:
        evidence.symlink_to(other, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are not supported by this test environment")
    with pytest.raises(ValueError, match="module directories cannot be symbolic links"):
        RuntimePaths.resolve(install_dir=tmp_path / "install", base_dir=root)
    assert evidence.is_symlink()
    assert not (root / "data" / "eagleeye.db").exists()
