from __future__ import annotations

from typing import Any

SCHEMA_148 = r'''
CREATE TABLE IF NOT EXISTS connector_manifests_148(
    connector_id TEXT PRIMARY KEY,
    source_key TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL,
    connector_version TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    publisher TEXT NOT NULL,
    entrypoint TEXT NOT NULL DEFAULT '',
    execution_backend TEXT NOT NULL,
    input_schema_json TEXT NOT NULL,
    output_schema_json TEXT NOT NULL,
    entity_types_json TEXT NOT NULL,
    secret_names_json TEXT NOT NULL,
    allowed_hosts_json TEXT NOT NULL,
    rate_limit_per_minute INTEGER NOT NULL,
    cost_model TEXT NOT NULL,
    legal_status TEXT NOT NULL,
    terms_profile TEXT NOT NULL,
    retention_profile TEXT NOT NULL,
    data_classification_json TEXT NOT NULL,
    health_probe_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    code_sha256 TEXT NOT NULL,
    manifest_fingerprint TEXT NOT NULL,
    signature_status TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    lifecycle_status TEXT NOT NULL DEFAULT 'registered',
    quarantine_reason TEXT NOT NULL DEFAULT '',
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connector_manifest148_type_status
    ON connector_manifests_148(connector_type,lifecycle_status,enabled,label);

CREATE TABLE IF NOT EXISTS connector_contracts_148(
    contract_id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL,
    connector_version TEXT NOT NULL,
    accepted_fingerprint TEXT NOT NULL,
    input_schema_fingerprint TEXT NOT NULL,
    output_schema_fingerprint TEXT NOT NULL,
    accepted_by TEXT NOT NULL,
    accepted_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(connector_id,connector_version,accepted_fingerprint),
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_connector_contract148_current
    ON connector_contracts_148(connector_id,status,accepted_at DESC);

CREATE TABLE IF NOT EXISTS connector_health_148(
    connector_id TEXT PRIMARY KEY,
    health_state TEXT NOT NULL DEFAULT 'terms_review_required',
    contract_state TEXT NOT NULL DEFAULT 'unaccepted',
    last_test_at TEXT NOT NULL DEFAULT '',
    last_success_at TEXT NOT NULL DEFAULT '',
    last_failure_at TEXT NOT NULL DEFAULT '',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_latency_ms INTEGER NOT NULL DEFAULT 0,
    test_summary_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS connector_secret_refs_148(
    ref_id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL,
    secret_name TEXT NOT NULL,
    vault_key TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0,
    configured_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(connector_id,secret_name),
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS connector_secret_leases_148(
    lease_id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL,
    case_id TEXT,
    token_hash TEXT NOT NULL UNIQUE,
    secret_names_json TEXT NOT NULL,
    issued_to TEXT NOT NULL,
    issued_by TEXT NOT NULL,
    expires_epoch INTEGER NOT NULL,
    used_at TEXT NOT NULL DEFAULT '',
    revoked_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_connector_secretlease148_expiry
    ON connector_secret_leases_148(connector_id,expires_epoch,used_at,revoked_at);

CREATE TABLE IF NOT EXISTS connector_runs_148(
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    target_id TEXT,
    connector_id TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    purpose TEXT NOT NULL,
    input_json TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    output_contract_fingerprint TEXT NOT NULL,
    provider_run_id TEXT NOT NULL DEFAULT '',
    browser_task_id TEXT NOT NULL DEFAULT '',
    result_count INTEGER NOT NULL DEFAULT 0,
    quarantine_count INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_class TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_connector_runs148_case_status
    ON connector_runs_148(case_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS connector_quarantine_148(
    quarantine_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    target_id TEXT,
    run_id TEXT NOT NULL,
    connector_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL DEFAULT '',
    source_host TEXT NOT NULL DEFAULT '',
    snippet TEXT NOT NULL DEFAULT '',
    normalized_payload_json TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'new',
    candidate_only INTEGER NOT NULL DEFAULT 1,
    reviewed_by TEXT NOT NULL DEFAULT '',
    review_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(case_id,connector_id,content_fingerprint),
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(run_id) REFERENCES connector_runs_148(run_id) ON DELETE CASCADE,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_connector_quarantine148_case_review
    ON connector_quarantine_148(case_id,review_status,created_at DESC);

CREATE TABLE IF NOT EXISTS connector_contract_tests_148(
    test_id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL,
    manifest_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER NOT NULL,
    checks_json TEXT NOT NULL,
    tested_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(connector_id) REFERENCES connector_manifests_148(connector_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_connector_tests148_connector
    ON connector_contract_tests_148(connector_id,created_at DESC);

CREATE TABLE IF NOT EXISTS connector_events_148(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    case_id TEXT,
    connector_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connector_events148_chain
    ON connector_events_148(case_id,sequence);
'''


def ensure_build148_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_148)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','148.0')")
    db.conn.commit()
