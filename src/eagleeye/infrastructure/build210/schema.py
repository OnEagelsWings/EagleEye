from __future__ import annotations

from typing import Any

SCHEMA_210 = r"""
CREATE TABLE IF NOT EXISTS monitor_runtime_policies_210(
    policy_id TEXT PRIMARY KEY,
    policy_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_schedules_210(
    schedule_id TEXT PRIMARY KEY,
    monitor_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    name TEXT NOT NULL,
    question TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL,
    timezone TEXT NOT NULL,
    misfire_policy TEXT NOT NULL,
    max_catchup_runs INTEGER NOT NULL,
    jitter_seconds INTEGER NOT NULL,
    status TEXT NOT NULL,
    next_run_at TEXT NOT NULL,
    last_run_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_schedules_due_210
ON monitor_schedules_210(status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_monitor_schedules_case_210
ON monitor_schedules_210(case_id, status, updated_at);

CREATE TABLE IF NOT EXISTS monitor_runs_210(
    run_id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    status TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    error_text TEXT NOT NULL,
    UNIQUE(schedule_id, scheduled_for)
);
CREATE INDEX IF NOT EXISTS idx_monitor_runs_case_210
ON monitor_runs_210(case_id, created_at);
CREATE INDEX IF NOT EXISTS idx_monitor_runs_status_210
ON monitor_runs_210(status, created_at);

CREATE TABLE IF NOT EXISTS monitor_tasks_210(
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    source_id TEXT NOT NULL,
    priority INTEGER NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL,
    remaining_dependencies INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    lease_owner TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    output_sha256 TEXT NOT NULL,
    checkpoint_json TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_tasks_claimable_210
ON monitor_tasks_210(status, available_at, remaining_dependencies, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_monitor_tasks_lease_210
ON monitor_tasks_210(status, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_monitor_tasks_run_210
ON monitor_tasks_210(run_id, status);
CREATE INDEX IF NOT EXISTS idx_monitor_tasks_source_210
ON monitor_tasks_210(source_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_monitor_tasks_partition_210
ON monitor_tasks_210(partition_key, status, created_at);

CREATE TABLE IF NOT EXISTS monitor_task_dependencies_210(
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(task_id, depends_on_task_id)
);
CREATE INDEX IF NOT EXISTS idx_monitor_task_dependencies_parent_210
ON monitor_task_dependencies_210(depends_on_task_id, task_id);

CREATE TABLE IF NOT EXISTS scheduler_leases_210(
    role_key TEXT PRIMARY KEY,
    lease_owner TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_observations_210(
    observation_id TEXT PRIMARY KEY,
    monitor_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    canonical_source_ref TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    published_at TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    claims_json TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    claim_fingerprint TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT NOT NULL,
    prompt_injection_candidate INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL,
    semantic_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(monitor_id, source_id, content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_monitor_observations_monitor_210
ON monitor_observations_210(monitor_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_monitor_observations_claim_210
ON monitor_observations_210(monitor_id, claim_fingerprint);

CREATE TABLE IF NOT EXISTS claim_impacts_210(
    impact_id TEXT PRIMARY KEY,
    monitor_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    impact_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    explanation TEXT NOT NULL,
    old_state_json TEXT NOT NULL,
    new_state_json TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claim_impacts_monitor_210
ON claim_impacts_210(monitor_id, created_at);

CREATE TABLE IF NOT EXISTS alerts_210(
    alert_id TEXT PRIMARY KEY,
    monitor_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    impact_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    status TEXT NOT NULL,
    alert_dedup_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL,
    acknowledged_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_case_210
ON alerts_210(case_id, status, created_at);

CREATE TABLE IF NOT EXISTS alert_outbox_210(
    outbox_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    delivery_idempotency_key TEXT NOT NULL UNIQUE,
    attempt INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    error_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_ready_210
ON alert_outbox_210(status, available_at, created_at);

CREATE TABLE IF NOT EXISTS dead_letter_tasks_210(
    dead_letter_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    error_code TEXT NOT NULL,
    error_text TEXT NOT NULL,
    redacted_input_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    review_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_events_210(
    event_id TEXT PRIMARY KEY,
    monitor_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_events_monitor_210
ON monitor_events_210(monitor_id, created_at);
"""


def ensure_build210_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_210)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','210.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','210.0')")
    db.conn.commit()
