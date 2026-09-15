from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config

from eagleeye_pro.core.database import new_id

from .connectors import ConnectorSDK1041
from .events import TypedEventBus1041
from .models import ArtifactKind, ArtifactModel, EventType
from .repository import CoreRepository1041


class CoreRecomposition1041Service:
    BUILD = "104.1"

    def __init__(self, *, db_path: str | Path, project_root: str | Path, platform: Any, legacy_connectors: Any, audit: Any):
        self.db_path = Path(db_path)
        self.project_root = Path(project_root)
        self.platform = platform
        self.audit = audit
        self.run_migrations()
        self.repository = CoreRepository1041(self.db_path)
        self.events = TypedEventBus1041(self.repository)
        self.connectors = ConnectorSDK1041(self.repository, self.events, legacy_connectors)
        self.migrate_legacy_artifacts()

    def close(self) -> None:
        self.repository.close()

    def _resolve_migration_script_location(self) -> Path:
        """Resolve Alembic scripts for source checkouts and installed wheels.

        Source releases keep ``alembic_104_1`` beside the package tree, while
        wheels install that data directory below ``sys.prefix``.  Resolving
        both layouts prevents an installed wheel from silently depending on
        the original source checkout.
        """
        candidates = (
            self.project_root / "alembic_104_1",
            Path(sys.prefix) / "alembic_104_1",
            Path(__file__).resolve().parents[2] / "alembic_104_1",
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if (resolved / "env.py").is_file() and (resolved / "versions").is_dir():
                return resolved
        searched = ", ".join(str(candidate) for candidate in candidates)
        raise RuntimeError(f"Alembic migration scripts not found; searched: {searched}")

    def run_migrations(self) -> None:
        cfg = Config()
        cfg.set_main_option("script_location", str(self._resolve_migration_script_location()))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        command.upgrade(cfg, "head")

    def migrate_legacy_artifacts(self) -> dict[str, int]:
        rows = self.platform.db.all("SELECT * FROM canonical_captures_103_1 ORDER BY created_at")
        created = 0
        for row in rows:
            if self.repository.get_artifact_by_capture(row["case_id"], row["capture_id"]):
                continue
            path = Path(row.get("manifest_path") or row.get("text_path") or row.get("html_path") or row.get("artifact_dir") or "")
            if path.is_dir():
                path = Path(row.get("manifest_path") or "")
            sha = row.get("content_sha256") or (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else "0" * 64)
            size = path.stat().st_size if path.exists() and path.is_file() else 0
            artifact = ArtifactModel(
                artifact_id=new_id("art1041"), case_id=row["case_id"], capture_id=row["capture_id"],
                kind=ArtifactKind.WEB_CAPTURE, storage_uri=str(path), sha256=sha,
                mime_type="application/json" if path.suffix.lower() == ".json" else "text/plain",
                byte_size=size, source_url=row.get("canonical_url") or "", title=row.get("title") or "",
                metadata={"migrated_from": "canonical_captures_103_1", "evidence_id": row.get("evidence_id") or ""},
                created_at=row.get("created_at"),
            )
            self.repository.upsert_artifact(artifact)
            self.events.publish(case_id=row["case_id"], event_type=EventType.ARTIFACT_CREATED, producer="migration_104_1", artifact_id=artifact.artifact_id, payload={"capture_id": row["capture_id"]})
            created += 1
        return {"scanned": len(rows), "created": created}

    def register_capture(self, capture: dict[str, Any]) -> dict[str, Any]:
        existing = self.repository.get_artifact_by_capture(capture["case_id"], capture["capture_id"])
        if existing:
            return existing.model_dump(mode="json")
        path = Path(capture.get("manifest_path") or capture.get("text_path") or capture.get("html_path") or "")
        sha = capture.get("content_sha256") or "0" * 64
        artifact = ArtifactModel(
            artifact_id=new_id("art1041"), case_id=capture["case_id"], capture_id=capture["capture_id"],
            kind=ArtifactKind.WEB_CAPTURE, storage_uri=str(path), sha256=sha,
            mime_type="application/json" if path.suffix.lower() == ".json" else "text/plain",
            byte_size=path.stat().st_size if path.exists() and path.is_file() else 0,
            source_url=capture.get("canonical_url") or "", title=capture.get("title") or "",
            metadata={"evidence_id": capture.get("evidence_id") or "", "status": capture.get("status") or "candidate_not_claim"},
        )
        self.repository.upsert_artifact(artifact)
        self.events.publish(case_id=artifact.case_id, event_type=EventType.ARTIFACT_CREATED, producer="canonical_intake_104_1", artifact_id=artifact.artifact_id, payload={"capture_id": artifact.capture_id})
        return artifact.model_dump(mode="json")

    def include_finding(self, **kwargs: Any) -> dict[str, Any]:
        result = self.platform.include_finding(**kwargs)
        capture = self.platform.get_capture(result["capture_id"])
        artifact = self.register_capture(capture)
        result["artifact_104_1"] = artifact
        result["recomposition_core"] = True
        return result

    def status(self, case_id: str = "") -> dict[str, Any]:
        case_id = self.platform.resolve_case_id(case_id)
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "artifacts": len(self.repository.list_artifacts(case_id, 10000)),
            "connectors": len(self.repository.list_connector_specs()),
            "storage": "SQLAlchemy repository on existing eagleeye.db",
            "migrations": "Alembic",
            "api": "FastAPI application shell",
            "event_bus": "typed and persisted",
        }
