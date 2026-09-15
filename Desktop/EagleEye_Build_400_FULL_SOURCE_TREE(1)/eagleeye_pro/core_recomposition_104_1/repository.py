from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .models import ArtifactModel, CollectionEventModel, ConnectorRunModel, ConnectorSpecModel, ObservationModel
from .orm import ArtifactORM, ConnectorRunORM, ConnectorSpecORM, EventORM, ObservationORM


def _iso(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else str(value)


class CoreRepository1041:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True, connect_args={"check_same_thread": False})
        self.Session = sessionmaker(self.engine, expire_on_commit=False, class_=Session)

    def close(self) -> None:
        self.engine.dispose()

    def upsert_artifact(self, model: ArtifactModel) -> ArtifactModel:
        with self.Session.begin() as session:
            if model.capture_id:
                existing = session.scalar(select(ArtifactORM).where(ArtifactORM.case_id == model.case_id, ArtifactORM.capture_id == model.capture_id))
                if existing:
                    return self._artifact_model(existing)
            row = ArtifactORM(
                artifact_id=model.artifact_id, case_id=model.case_id, capture_id=model.capture_id,
                kind=model.kind.value, storage_uri=model.storage_uri, sha256=model.sha256,
                mime_type=model.mime_type, byte_size=model.byte_size, source_url=model.source_url,
                title=model.title, metadata_json=json.dumps(model.metadata, ensure_ascii=False, sort_keys=True),
                created_at=_iso(model.created_at),
            )
            session.add(row)
        return model

    def get_artifact_by_capture(self, case_id: str, capture_id: str) -> ArtifactModel | None:
        with self.Session() as session:
            row = session.scalar(select(ArtifactORM).where(ArtifactORM.case_id == case_id, ArtifactORM.capture_id == capture_id))
            return self._artifact_model(row) if row else None

    def list_artifacts(self, case_id: str, limit: int = 100) -> list[ArtifactModel]:
        with self.Session() as session:
            rows = session.scalars(select(ArtifactORM).where(ArtifactORM.case_id == case_id).order_by(ArtifactORM.created_at.desc()).limit(limit)).all()
            return [self._artifact_model(r) for r in rows]

    def add_observation(self, model: ObservationModel) -> ObservationModel:
        with self.Session.begin() as session:
            session.add(ObservationORM(
                observation_id=model.observation_id, case_id=model.case_id, artifact_id=model.artifact_id,
                observation_type=model.observation_type, value_raw=model.value_raw,
                value_normalized=model.value_normalized, extractor=model.extractor,
                extractor_version=model.extractor_version, confidence=model.confidence,
                review_status=model.review_status.value, character_start=model.character_start,
                character_end=model.character_end,
                metadata_json=json.dumps(model.metadata, ensure_ascii=False, sort_keys=True),
                created_at=_iso(model.created_at),
            ))
        return model

    def emit_event(self, model: CollectionEventModel) -> CollectionEventModel:
        with self.Session.begin() as session:
            session.add(EventORM(
                event_id=model.event_id, case_id=model.case_id, event_type=model.event_type.value,
                producer=model.producer, artifact_id=model.artifact_id,
                connector_run_id=model.connector_run_id,
                payload_json=json.dumps(model.payload, ensure_ascii=False, sort_keys=True),
                created_at=_iso(model.created_at),
            ))
        return model

    def upsert_connector_spec(self, model: ConnectorSpecModel) -> ConnectorSpecModel:
        with self.Session.begin() as session:
            row = session.get(ConnectorSpecORM, model.connector_id)
            values = dict(
                name=model.name, category=model.category,
                input_types_json=json.dumps(model.input_types), output_types_json=json.dumps(model.output_types),
                public_only=model.public_only, authentication_required=model.authentication_required,
                execution_mode=model.execution_mode, rate_limit_note=model.rate_limit_note,
                legal_note=model.legal_note, implementation=model.implementation,
                enabled=model.enabled, updated_at=_iso(__import__('datetime').datetime.now(__import__('datetime').timezone.utc)),
            )
            if row:
                for key, value in values.items(): setattr(row, key, value)
            else:
                session.add(ConnectorSpecORM(connector_id=model.connector_id, **values))
        return model

    def list_connector_specs(self) -> list[ConnectorSpecModel]:
        with self.Session() as session:
            rows = session.scalars(select(ConnectorSpecORM).order_by(ConnectorSpecORM.category, ConnectorSpecORM.name)).all()
            return [ConnectorSpecModel(
                connector_id=r.connector_id, name=r.name, category=r.category,
                input_types=json.loads(r.input_types_json), output_types=json.loads(r.output_types_json),
                public_only=r.public_only, authentication_required=r.authentication_required,
                execution_mode=r.execution_mode, rate_limit_note=r.rate_limit_note,
                legal_note=r.legal_note, implementation=r.implementation, enabled=r.enabled,
            ) for r in rows]

    def save_connector_run(self, model: ConnectorRunModel) -> ConnectorRunModel:
        with self.Session.begin() as session:
            row = session.get(ConnectorRunORM, model.run_id)
            values = dict(
                case_id=model.case_id, connector_id=model.connector_id, input_value=model.input_value,
                status=model.status, legacy_execution_id=model.legacy_execution_id,
                artifact_id=model.artifact_id,
                result_json=json.dumps(model.result, ensure_ascii=False, sort_keys=True, default=str),
                error=model.error, started_at=_iso(model.started_at),
                completed_at=_iso(model.completed_at) if model.completed_at else None,
            )
            if row:
                for key, value in values.items(): setattr(row, key, value)
            else:
                session.add(ConnectorRunORM(run_id=model.run_id, **values))
        return model

    @staticmethod
    def _artifact_model(row: ArtifactORM) -> ArtifactModel:
        return ArtifactModel(
            artifact_id=row.artifact_id, case_id=row.case_id, capture_id=row.capture_id,
            kind=row.kind, storage_uri=row.storage_uri, sha256=row.sha256,
            mime_type=row.mime_type, byte_size=row.byte_size, source_url=row.source_url,
            title=row.title, metadata=json.loads(row.metadata_json or "{}"), created_at=row.created_at,
        )
