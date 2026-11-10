from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from eagleeye_pro.version import BUILD


def _internal_release_build(build: str | None = None) -> bool:
    """Keep the internal 490–500 line separate from historical installations."""
    try:
        major = int(str(BUILD if build is None else build).split(".", 1)[0])
    except (TypeError, ValueError):
        return False
    return 490 <= major <= 500


def default_runtime_root() -> Path:
    if os.name == "nt":
        parent = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData"/"Local")))
        return parent / ("EagleEye-Internal" if _internal_release_build() else "EagleEye") / "Spearhead"
    parent = Path(os.environ.get("XDG_DATA_HOME", str(Path.home()/".local"/"share")))
    return parent / ("eagleeye-internal" if _internal_release_build() else "eagleeye-spearhead")


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    base_dir: Path
    install_dir: Path
    data_dir: Path
    reports_dir: Path
    evidence_dir: Path
    capture_dir: Path
    real_capture_74_dir: Path
    local_evidence_75_dir: Path
    graph_ui_76_dir: Path
    report_builder_89_dir: Path
    casefile_pro_90_dir: Path
    enterprise_95_dir: Path
    intake_console_101_dir: Path
    browser_capture_102_dir: Path
    graph_workspace_103_dir: Path
    platform_103_1_dir: Path
    source_adapter_104_dir: Path
    collection_engine_105_dir: Path
    provider_collection_120_dir: Path
    evidence_preservation_121_dir: Path
    secure_storage_dir: Path
    collaboration_dir: Path
    db_path: Path

    @classmethod
    def resolve(
        cls,
        *,
        install_dir: Path,
        base_dir: str | Path | None = None,
        db_path: str | Path | None = None,
    ) -> "RuntimePaths":
        if base_dir is None:
            runtime_root = default_runtime_root()
        else:
            runtime_root = Path(base_dir)

        if db_path is not None and _internal_release_build():
            # SQLite can write to WAL/SHM siblings even when the main DB is safe.
            # Reject redirected sidecars before creating any workspace folders.
            candidate = Path(db_path)
            if any(Path(str(candidate) + suffix).is_symlink() for suffix in ("", "-wal", "-shm")):
                raise ValueError("Internal release database cannot contain symbolic links (including WAL/SHM sidecars)")

        if db_path is not None and _internal_release_build() and Path(db_path).name in {
            "eagleeye_pro_95_0.db", "eagleeye_pro_95_0.db-wal",
            "eagleeye_pro_95_0.db-shm",
        }:
            raise ValueError("Internal release cannot use a legacy database path")

        # A renamed legacy database must not bypass internal workspace isolation.
        if db_path is not None and _internal_release_build():
            chosen = Path(db_path).resolve()
            workspace = runtime_root.resolve()
            if not chosen.is_relative_to(workspace) or chosen == workspace:
                raise ValueError("Internal release database must stay inside its workspace")
            # Reject aliases between the workspace and explicit database.
            # Even in-workspace aliases can silently merge separate case stores.
            raw_candidate = Path(db_path).absolute()
            raw_workspace = runtime_root.absolute()
            if raw_candidate.is_relative_to(raw_workspace):
                cursor = raw_workspace
                for component in raw_candidate.relative_to(raw_workspace).parts:
                    cursor = cursor / component
                    if cursor.is_symlink():
                        raise ValueError("Internal release database path cannot traverse symbolic links")
            installation = Path(install_dir).resolve()
            if chosen.is_relative_to(installation):
                raise ValueError("Internal release database must be separate from installation")

        if _internal_release_build():
            # Do not allow a workspace alias to point at a different installation.
            # Checking the root itself matters even when all child paths resolve
            # consistently beneath that redirected root.
            if any(part.is_symlink() for part in (runtime_root, *runtime_root.parents)):
                raise ValueError("Internal release workspace cannot be a symbolic link")
            workspace = runtime_root.resolve()
            installation = Path(install_dir).resolve()
            if workspace == installation or workspace.is_relative_to(installation) or installation.is_relative_to(workspace):
                raise ValueError("Internal release workspace must be separate from installation")

        data_dir = runtime_root / "data"
        reports_dir = runtime_root / "reports"
        if _internal_release_build():
            # A pre-existing symlink must not redirect a fresh installation into
            # another installation or an unrelated data directory.
            workspace = runtime_root.resolve()
            installation = Path(install_dir).resolve()
            for directory in (data_dir, reports_dir):
                # In-workspace links can also alias independent stores.
                if directory.is_symlink():
                    raise ValueError("Internal release data directories cannot be symbolic links")
                target = directory.resolve()
                if not target.is_relative_to(workspace) or target.is_relative_to(installation):
                    raise ValueError("Internal release data directories must stay inside the workspace")
        values = {
            "evidence_dir": data_dir / "evidence_vault",
            "capture_dir": data_dir / "search_captures",
            "real_capture_74_dir": data_dir / "real_captures_74",
            "local_evidence_75_dir": data_dir / "local_evidence_vault_75",
            "graph_ui_76_dir": reports_dir / "graph_ui_76",
            "report_builder_89_dir": reports_dir / "report_builder_pro_89",
            "casefile_pro_90_dir": reports_dir / "casefile_pro_90",
            "enterprise_95_dir": data_dir / "enterprise_95",
            "intake_console_101_dir": reports_dir / "intake_console_101",
            "browser_capture_102_dir": data_dir / "browser_capture_bridge_102",
            "graph_workspace_103_dir": data_dir / "interactive_graph_workspace_103",
            "platform_103_1_dir": data_dir / "canonical_artifacts_103_1",
            "source_adapter_104_dir": data_dir / "source_adapter_execution_104",
            "collection_engine_105_dir": data_dir / "collection_engine_105",
            "provider_collection_120_dir": data_dir / "provider_collection_120",
            "evidence_preservation_121_dir": data_dir / "evidence_preservation_121",
            "secure_storage_dir": data_dir / "secure_storage",
            "collaboration_dir": reports_dir / "collaboration_bundles",
        }
        if _internal_release_build():
            # Validate every existing nested directory before creating anything:
            # a symlink in evidence_vault or another module directory must not
            # redirect writes to an older installation or outside the workspace.
            workspace = runtime_root.resolve()
            for directory in values.values():
                # Even an in-workspace alias can merge distinct module stores,
                # compromising evidence provenance and backup isolation.
                if directory.is_symlink():
                    raise ValueError("Internal release module directories cannot be symbolic links")
                target = directory.resolve()
                if not target.is_relative_to(workspace):
                    raise ValueError("Internal release module directories must stay inside the workspace")
        # Validate the default DB target before creating any directories. A
        # rejected symlink must not leave a partially initialized workspace.
        if db_path is None and _internal_release_build():
            if any(Path(str(data_dir / "eagleeye.db") + suffix).is_symlink() for suffix in ("", "-wal", "-shm")):
                raise ValueError("Internal release database cannot contain symbolic links (including WAL/SHM sidecars)")
            target = (data_dir / "eagleeye.db").resolve()
            workspace = runtime_root.resolve()
            if not target.is_relative_to(workspace) or target.is_relative_to(Path(install_dir).resolve()):
                raise ValueError("Internal release database must stay inside its workspace")
        for path in (data_dir, reports_dir, *values.values()):
            path.mkdir(parents=True, exist_ok=True)

        if db_path is None:
            resolved_db = data_dir / "eagleeye.db"
            legacy_db = data_dir / "eagleeye_pro_95_0.db"
            # New internal-release workspaces must never import a legacy DB
            # implicitly. Explicit migrations require a separate reviewed action.
            if not _internal_release_build() and not resolved_db.exists() and legacy_db.exists():
                shutil.copy2(legacy_db, resolved_db)
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(legacy_db) + suffix)
                    if sidecar.exists():
                        shutil.copy2(sidecar, Path(str(resolved_db) + suffix))
        else:
            resolved_db = Path(db_path)
            resolved_db.parent.mkdir(parents=True, exist_ok=True)

        return cls(
            base_dir=runtime_root,
            install_dir=install_dir,
            data_dir=data_dir,
            reports_dir=reports_dir,
            db_path=resolved_db,
            **values,
        )
