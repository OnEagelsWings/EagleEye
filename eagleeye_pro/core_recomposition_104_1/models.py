from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactKind(StrEnum):
    WEB_CAPTURE = "web_capture"
    PROVIDER_RESPONSE = "provider_response"
    DOCUMENT = "document"
    SCREENSHOT = "screenshot"
    TEXT = "text"


class ReviewStatus(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISPUTED = "disputed"
    NEEDS_REVIEW = "needs_review"


class EventType(StrEnum):
    ARTIFACT_CREATED = "artifact.created"
    OBSERVATION_CREATED = "observation.created"
    CONNECTOR_STARTED = "connector.started"
    CONNECTOR_COMPLETED = "connector.completed"
    CONNECTOR_FAILED = "connector.failed"
    COLLECTION_STARTED = "collection.started"
    COLLECTION_PAGE_CAPTURED = "collection.page_captured"
    COLLECTION_COMPLETED = "collection.completed"
    COLLECTION_FAILED = "collection.failed"


class ArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    artifact_id: str
    case_id: str
    capture_id: str | None = None
    kind: ArtifactKind
    storage_uri: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime_type: str = "application/octet-stream"
    byte_size: int = Field(ge=0)
    source_url: str = ""
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("source_url")
    @classmethod
    def validate_optional_url(cls, value: str) -> str:
        if value:
            HttpUrl(value)
        return value


class ObservationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    observation_id: str
    case_id: str
    artifact_id: str
    observation_type: str
    value_raw: str
    value_normalized: str = ""
    extractor: str
    extractor_version: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: ReviewStatus = ReviewStatus.CANDIDATE
    character_start: int | None = Field(default=None, ge=0)
    character_end: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class CollectionEventModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str
    case_id: str
    event_type: EventType
    producer: str
    artifact_id: str | None = None
    connector_run_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ConnectorSpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    connector_id: str
    name: str
    category: str
    input_types: list[str]
    output_types: list[str]
    public_only: bool = True
    authentication_required: bool = False
    execution_mode: str = "live_public_lookup"
    rate_limit_note: str = ""
    legal_note: str = ""
    implementation: str
    enabled: bool = True


class ConnectorRunModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    run_id: str
    case_id: str
    connector_id: str
    input_value: str
    status: str
    legacy_execution_id: str | None = None
    artifact_id: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class IntakeRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = ""
    url: str = ""
    text: str = ""
    html_snapshot: str = ""
    title: str = ""
    source_label: str = "fastapi_intake_104_1"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if value:
            HttpUrl(value)
        return value
