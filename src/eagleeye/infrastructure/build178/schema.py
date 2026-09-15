from __future__ import annotations
from typing import Any

SCHEMA_178 = r'''
CREATE TABLE IF NOT EXISTS monitor_source_profiles_178(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, jurisdiction TEXT NOT NULL, category TEXT NOT NULL,
 access_mode TEXT NOT NULL, base_url TEXT NOT NULL, docs_url TEXT NOT NULL, terms_url TEXT NOT NULL,
 capabilities_json TEXT NOT NULL, constraints_json TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitor_profiles_178(
 monitor_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL, query_json TEXT NOT NULL,
 source_ids_json TEXT NOT NULL, interval_minutes INTEGER NOT NULL, expires_at TEXT NOT NULL,
 priority_rules_json TEXT NOT NULL, policy_json TEXT NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitor_runs_178(
 run_id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, case_id TEXT NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL, result_count INTEGER NOT NULL, new_count INTEGER NOT NULL,
 changed_count INTEGER NOT NULL, error_count INTEGER NOT NULL, summary_json TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitor_observations_178(
 observation_id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, run_id TEXT NOT NULL, source_id TEXT NOT NULL,
 source_record_id TEXT NOT NULL, canonical_uri TEXT, observed_at TEXT NOT NULL, published_at TEXT,
 content_json TEXT NOT NULL, canonical_sha256 TEXT NOT NULL, previous_sha256 TEXT,
 change_type TEXT NOT NULL, relevance REAL NOT NULL, review_status TEXT NOT NULL,
 provenance_json TEXT NOT NULL, UNIQUE(monitor_id,source_id,source_record_id,canonical_sha256)
);
CREATE TABLE IF NOT EXISTS monitor_alerts_178(
 alert_id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
 alert_type TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL, details_json TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitor_events_178(
 event_id TEXT PRIMARY KEY, monitor_id TEXT, case_id TEXT, event_type TEXT NOT NULL, details_json TEXT NOT NULL,
 created_at TEXT NOT NULL, previous_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_due_178 ON monitor_profiles_178(status,expires_at,updated_at);
CREATE INDEX IF NOT EXISTS idx_monitor_obs_178 ON monitor_observations_178(monitor_id,source_id,source_record_id,observed_at);
CREATE INDEX IF NOT EXISTS idx_monitor_alerts_178 ON monitor_alerts_178(case_id,severity,status,created_at);
'''

def ensure_build178_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_178)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','178.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','178.0')")
    db.conn.commit()
