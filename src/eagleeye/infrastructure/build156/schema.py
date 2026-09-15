from __future__ import annotations
from typing import Any
SCHEMA_156 = r'''
CREATE TABLE IF NOT EXISTS collection_plans_156(
 plan_id TEXT PRIMARY KEY, case_id TEXT, title TEXT NOT NULL, status TEXT NOT NULL,
 seed_json TEXT NOT NULL, policy_json TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, correlation_id TEXT NOT NULL,
 snapshot_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_queries_156(
 query_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, query_text TEXT NOT NULL,
 query_kind TEXT NOT NULL, params_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(plan_id) REFERENCES collection_plans_156(plan_id)
);
CREATE TABLE IF NOT EXISTS collection_steps_156(
 step_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, connector_id TEXT NOT NULL,
 query_id TEXT, status TEXT NOT NULL, outcome_code TEXT, started_at TEXT,
 finished_at TEXT, records_count INTEGER NOT NULL DEFAULT 0, error_text TEXT,
 provenance_json TEXT NOT NULL DEFAULT '{}', correlation_id TEXT NOT NULL,
 FOREIGN KEY(plan_id) REFERENCES collection_plans_156(plan_id)
);
CREATE TABLE IF NOT EXISTS normalized_records_156(
 record_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, step_id TEXT NOT NULL,
 connector_id TEXT NOT NULL, source_record_id TEXT, entity_kind TEXT NOT NULL,
 normalized_json TEXT NOT NULL, canonical_sha256 TEXT NOT NULL,
 provenance_json TEXT NOT NULL, observed_at TEXT NOT NULL,
 duplicate_of TEXT, review_status TEXT NOT NULL DEFAULT 'candidate',
 FOREIGN KEY(plan_id) REFERENCES collection_plans_156(plan_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_records156_plan_hash ON normalized_records_156(plan_id,canonical_sha256);
CREATE TABLE IF NOT EXISTS identity_candidates_156(
 candidate_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, record_id TEXT NOT NULL,
 candidate_type TEXT NOT NULL, display_label TEXT NOT NULL,
 rationale_json TEXT NOT NULL, confidence_band TEXT NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
 reviewed_at TEXT, reviewed_by TEXT, review_note TEXT,
 FOREIGN KEY(record_id) REFERENCES normalized_records_156(record_id)
);
CREATE TABLE IF NOT EXISTS collection_events_156(
 event_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, event_type TEXT NOT NULL,
 payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL, correlation_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
'''
def ensure_build156_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_156)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','156.0')")
    db.conn.commit()
