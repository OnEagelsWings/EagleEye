from __future__ import annotations
from typing import Any

SCHEMA_153 = r"""
CREATE TABLE IF NOT EXISTS operation_jobs_153(
    job_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    case_id TEXT,
    operation TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    outcome_code TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    attempts INTEGER NOT NULL DEFAULT 1,
    actor TEXT NOT NULL,
    input_summary_json TEXT NOT NULL DEFAULT '{}',
    output_summary_json TEXT NOT NULL DEFAULT '{}',
    error_class TEXT,
    error_message TEXT,
    retryable INTEGER NOT NULL DEFAULT 0,
    partial INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs153_correlation ON operation_jobs_153(correlation_id);
CREATE INDEX IF NOT EXISTS idx_jobs153_case ON operation_jobs_153(case_id);
CREATE INDEX IF NOT EXISTS idx_jobs153_status ON operation_jobs_153(status);

CREATE TABLE IF NOT EXISTS telemetry_events_153(
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    job_id TEXT,
    case_id TEXT,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    event_name TEXT NOT NULL,
    message TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    attributes_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry153_corr ON telemetry_events_153(correlation_id, created_at);

CREATE TABLE IF NOT EXISTS health_snapshots_153(
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    active_jobs INTEGER NOT NULL,
    failed_jobs INTEGER NOT NULL,
    partial_jobs INTEGER NOT NULL,
    active_threads INTEGER NOT NULL,
    non_daemon_threads INTEGER NOT NULL,
    initialized_services INTEGER NOT NULL,
    database_ok INTEGER NOT NULL,
    findings_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resource_findings_153(
    finding_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    state TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""

def ensure_build153_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_153)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','153.0')")
    db.conn.commit()
