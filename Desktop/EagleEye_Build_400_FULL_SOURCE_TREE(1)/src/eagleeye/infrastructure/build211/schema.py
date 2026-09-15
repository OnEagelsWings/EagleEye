from __future__ import annotations

from typing import Any


SCHEMA_211 = r"""
CREATE TABLE IF NOT EXISTS evidence_policies_211 (
    policy_id TEXT PRIMARY KEY,
    mission_json TEXT NOT NULL,
    safeguards_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS upstream_projects_211 (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    homepage TEXT NOT NULL,
    license_spdx TEXT NOT NULL,
    integration_mode TEXT NOT NULL,
    executable_names_json TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    distribution_allowed INTEGER NOT NULL DEFAULT 0,
    network_capable INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'catalogued',
    detected_path TEXT NOT NULL DEFAULT '',
    detected_version TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_upstream_projects_211_status
ON upstream_projects_211(review_status, enabled, title);

CREATE TABLE IF NOT EXISTS evidence_sources_211 (
    source_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    original_url TEXT NOT NULL DEFAULT '',
    canonical_url TEXT NOT NULL DEFAULT '',
    final_url TEXT NOT NULL DEFAULT '',
    redirect_chain_json TEXT NOT NULL DEFAULT '[]',
    response_headers_json TEXT NOT NULL DEFAULT '{}',
    observed_at TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT '',
    collector_id TEXT NOT NULL,
    collector_version TEXT NOT NULL,
    upstream_project_id TEXT NOT NULL DEFAULT '',
    capture_mode TEXT NOT NULL,
    legal_scope TEXT NOT NULL,
    candidate_only INTEGER NOT NULL DEFAULT 1,
    content_is_untrusted INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(package_id) REFERENCES evidence_packages_121(package_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_evidence_sources_211_case
ON evidence_sources_211(case_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_sources_211_package
ON evidence_sources_211(package_id);

CREATE TABLE IF NOT EXISTS evidence_statements_211 (
    statement_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL,
    original_value TEXT NOT NULL DEFAULT '',
    value_language TEXT NOT NULL DEFAULT '',
    dataset_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    statement_kind TEXT NOT NULL,
    confidence REAL NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'candidate',
    limitations_json TEXT NOT NULL DEFAULT '[]',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES evidence_sources_211(source_id) ON DELETE RESTRICT,
    FOREIGN KEY(package_id) REFERENCES evidence_packages_121(package_id) ON DELETE RESTRICT,
    CHECK(statement_kind IN ('observation','inference','hypothesis')),
    CHECK(confidence >= 0.0 AND confidence <= 1.0)
);
CREATE INDEX IF NOT EXISTS idx_evidence_statements_211_case
ON evidence_statements_211(case_id, entity_ref, predicate, created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_statements_211_source
ON evidence_statements_211(source_id, created_at);

CREATE TABLE IF NOT EXISTS evidence_statement_links_211 (
    link_id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(statement_id) REFERENCES evidence_statements_211(statement_id) ON DELETE RESTRICT,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_statement_links_211_unique
ON evidence_statement_links_211(statement_id, object_type, object_id, relation);

CREATE TABLE IF NOT EXISTS evidence_statement_reviews_211 (
    review_id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(statement_id) REFERENCES evidence_statements_211(statement_id) ON DELETE RESTRICT,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    CHECK(decision IN ('accepted_as_observation','rejected','needs_more_evidence','superseded'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_statement_reviews_211_statement
ON evidence_statement_reviews_211(statement_id, created_at);

CREATE TABLE IF NOT EXISTS tool_runs_211 (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    package_id TEXT NOT NULL DEFAULT '',
    purpose TEXT NOT NULL,
    input_ref TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    executable_path TEXT NOT NULL DEFAULT '',
    detected_version TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    exit_code INTEGER,
    stdout_sha256 TEXT NOT NULL DEFAULT '',
    stderr_redacted TEXT NOT NULL DEFAULT '',
    artifact_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY(project_id) REFERENCES upstream_projects_211(project_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_tool_runs_211_case
ON tool_runs_211(case_id, created_at, status);

CREATE TABLE IF NOT EXISTS evidence_ledger_events_211 (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_time TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_ledger_events_211_case
ON evidence_ledger_events_211(case_id, event_time, event_id);

CREATE TABLE IF NOT EXISTS evidence_bundles_211 (
    bundle_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    package_ids_json TEXT NOT NULL,
    statement_ids_json TEXT NOT NULL,
    bundle_relpath TEXT NOT NULL UNIQUE,
    manifest_sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_bundles_211_case
ON evidence_bundles_211(case_id, created_at);

CREATE TRIGGER IF NOT EXISTS trg_evidence_sources_211_no_update
BEFORE UPDATE ON evidence_sources_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_sources_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_sources_211_no_delete
BEFORE DELETE ON evidence_sources_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_sources_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_statements_211_no_update
BEFORE UPDATE ON evidence_statements_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_statements_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_statements_211_no_delete
BEFORE DELETE ON evidence_statements_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_statements_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_reviews_211_no_update
BEFORE UPDATE ON evidence_statement_reviews_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_statement_reviews_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_reviews_211_no_delete
BEFORE DELETE ON evidence_statement_reviews_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_statement_reviews_211 is append-only');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_ledger_211_no_update
BEFORE UPDATE ON evidence_ledger_events_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_ledger_events_211 is immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_evidence_ledger_211_no_delete
BEFORE DELETE ON evidence_ledger_events_211 BEGIN
    SELECT RAISE(ABORT, 'evidence_ledger_events_211 is immutable');
END;
"""


def ensure_build211_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_211)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','211.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','211.0')")
    db.conn.commit()
