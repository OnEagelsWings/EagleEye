from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArtifactORM(Base):
    __tablename__ = "core_artifacts_104_1"
    __table_args__ = (
        UniqueConstraint("case_id", "capture_id", name="uq_core_artifact_case_capture_104_1"),
        Index("idx_core_artifact_case_104_1", "case_id", "created_at"),
    )

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ObservationORM(Base):
    __tablename__ = "core_observations_104_1"
    __table_args__ = (Index("idx_core_observation_artifact_104_1", "artifact_id", "created_at"),)

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(64), ForeignKey("core_artifacts_104_1.artifact_id", ondelete="CASCADE"), nullable=False)
    observation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    value_raw: Mapped[str] = mapped_column(Text, nullable=False)
    value_normalized: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extractor: Mapped[str] = mapped_column(String(120), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="candidate", nullable=False)
    character_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class EventORM(Base):
    __tablename__ = "core_events_104_1"
    __table_args__ = (Index("idx_core_event_case_104_1", "case_id", "created_at"),)

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    producer: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connector_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ConnectorSpecORM(Base):
    __tablename__ = "connector_registry_104_1"

    connector_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    input_types_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_types_json: Mapped[str] = mapped_column(Text, nullable=False)
    public_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    authentication_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    rate_limit_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    legal_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    implementation: Mapped[str] = mapped_column(String(240), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ConnectorRunORM(Base):
    __tablename__ = "connector_runs_104_1"
    __table_args__ = (Index("idx_connector_run_case_104_1", "case_id", "started_at"),)

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_id: Mapped[str] = mapped_column(String(100), nullable=False)
    input_value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    legacy_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
