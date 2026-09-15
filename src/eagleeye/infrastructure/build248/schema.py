from __future__ import annotations
from typing import Any

SCHEMA_248 = r'''
CREATE TABLE IF NOT EXISTS production_runtime_probes_248(
 probe_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, ollama_found INTEGER NOT NULL, ollama_version TEXT NOT NULL,
 endpoint TEXT NOT NULL, endpoint_healthy INTEGER NOT NULL, preferred_model TEXT NOT NULL, preferred_model_id TEXT NOT NULL,
 model_present INTEGER NOT NULL, observed_models_json TEXT NOT NULL, executable_path TEXT NOT NULL,
 status TEXT NOT NULL, detail_json TEXT NOT NULL, observed_by TEXT NOT NULL, observed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_hardening_snapshots_248(
 snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, database_integrity TEXT NOT NULL, schema_version TEXT NOT NULL,
 access_review_json TEXT NOT NULL, backup_state_json TEXT NOT NULL, opsec_state_json TEXT NOT NULL, runtime_state_json TEXT NOT NULL,
 readiness_score INTEGER NOT NULL, status TEXT NOT NULL, findings_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_hardening_reviews_248(
 review_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
 rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_backup_links_248(
 link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, backup_id TEXT NOT NULL UNIQUE, verification_json TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_training_links_248(
 link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, training_example_id TEXT NOT NULL,
 stream TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(snapshot_id,stream)
);
CREATE TABLE IF NOT EXISTS production_events_248(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
 actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prod248_case ON production_hardening_snapshots_248(case_id,created_at);
CREATE INDEX IF NOT EXISTS idx_probe248_case ON production_runtime_probes_248(case_id,observed_at);
CREATE TRIGGER IF NOT EXISTS trg_prod248_snap_no_update BEFORE UPDATE ON production_hardening_snapshots_248 BEGIN SELECT RAISE(ABORT,'production_hardening_snapshots_248 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_prod248_snap_no_delete BEFORE DELETE ON production_hardening_snapshots_248 BEGIN SELECT RAISE(ABORT,'production_hardening_snapshots_248 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_prod248_review_no_update BEFORE UPDATE ON production_hardening_reviews_248 BEGIN SELECT RAISE(ABORT,'production_hardening_reviews_248 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_prod248_events_no_update BEFORE UPDATE ON production_events_248 BEGIN SELECT RAISE(ABORT,'production_events_248 immutable'); END;
'''

def ensure_build248_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_248)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','248.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','248.0')")
    db.conn.commit()
