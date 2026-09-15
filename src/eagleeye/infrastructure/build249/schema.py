from __future__ import annotations
from typing import Any

SCHEMA_249 = r'''
CREATE TABLE IF NOT EXISTS stress_campaigns_249(
 campaign_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL, profile TEXT NOT NULL,
 status TEXT NOT NULL, config_json TEXT NOT NULL, approved_by TEXT NOT NULL,
 created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stress_results_249(
 result_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, case_id TEXT NOT NULL,
 scenario TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL,
 duration_ms REAL NOT NULL, metrics_json TEXT NOT NULL, findings_json TEXT NOT NULL,
 remediation_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, UNIQUE(campaign_id,scenario)
);
CREATE TABLE IF NOT EXISTS stress_result_reviews_249(
 review_id TEXT PRIMARY KEY, result_id TEXT NOT NULL UNIQUE, campaign_id TEXT NOT NULL, case_id TEXT NOT NULL,
 decision TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS release_blockers_249(
 blocker_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, result_id TEXT NOT NULL, case_id TEXT NOT NULL,
 category TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT, resolution_note TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stress_training_links_249(
 link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, result_id TEXT NOT NULL, training_example_id TEXT NOT NULL,
 stream TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(result_id,stream)
);
CREATE TABLE IF NOT EXISTS stress_events_249(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
 object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stress249_case ON stress_campaigns_249(case_id,created_at);
CREATE INDEX IF NOT EXISTS idx_stress249_results ON stress_results_249(campaign_id,scenario);
CREATE INDEX IF NOT EXISTS idx_stress249_blockers ON release_blockers_249(case_id,status,severity);
CREATE TRIGGER IF NOT EXISTS trg_stress249_result_no_update BEFORE UPDATE ON stress_results_249 BEGIN SELECT RAISE(ABORT,'stress_results_249 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_stress249_review_no_update BEFORE UPDATE ON stress_result_reviews_249 BEGIN SELECT RAISE(ABORT,'stress_result_reviews_249 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_stress249_event_no_update BEFORE UPDATE ON stress_events_249 BEGIN SELECT RAISE(ABORT,'stress_events_249 immutable'); END;
'''

def ensure_build249_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_249)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','249.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','249.0')")
    db.conn.commit()
