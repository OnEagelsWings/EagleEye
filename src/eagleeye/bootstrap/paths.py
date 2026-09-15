from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


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
            if os.name == "nt":
                runtime_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "EagleEye" / "Spearhead"
            else:
                runtime_root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "eagleeye-spearhead"
        else:
            runtime_root = Path(base_dir)

        data_dir = runtime_root / "data"
        reports_dir = runtime_root / "reports"
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
        for path in (data_dir, reports_dir, *values.values()):
            path.mkdir(parents=True, exist_ok=True)

        if db_path is None:
            resolved_db = data_dir / "eagleeye.db"
            legacy_db = data_dir / "eagleeye_pro_95_0.db"
            if not resolved_db.exists() and legacy_db.exists():
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
