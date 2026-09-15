from __future__ import annotations
from typing import Any

SCHEMA_220 = r'''
CREATE TABLE IF NOT EXISTS source_adapters_220(
 adapter_key TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 source_class TEXT NOT NULL,
 adapter_kind TEXT NOT NULL,
 target_types_json TEXT NOT NULL,
 allowed_hosts_json TEXT NOT NULL,
 network_capable INTEGER NOT NULL DEFAULT 0,
 opsec_risk TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 0,
 health_state TEXT NOT NULL,
 circuit_state TEXT NOT NULL DEFAULT 'closed',
 circuit_open_until TEXT NOT NULL DEFAULT '',
 quarantine_reason TEXT NOT NULL DEFAULT '',
 contract_version TEXT NOT NULL,
 required_fields_json TEXT NOT NULL DEFAULT '[]',
 detected_path TEXT NOT NULL DEFAULT '',
 detected_version TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 CHECK(source_class IN ('web_archive','organization_registry','document_metadata','capture_import')),
 CHECK(adapter_kind IN ('http_api','local_tool','controlled_import')),
 CHECK(opsec_risk IN ('low','elevated','high','critical')),
 CHECK(health_state IN ('not_configured','healthy','degraded','unavailable','cooldown','quarantined')),
 CHECK(circuit_state IN ('closed','open','half_open'))
);

CREATE TABLE IF NOT EXISTS source_runs_220(
 run_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 adapter_key TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value_redacted TEXT NOT NULL,
 purpose TEXT NOT NULL,
 options_json TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL,
 started_by TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT NOT NULL DEFAULT '',
 result_count INTEGER NOT NULL DEFAULT 0,
 evidence_source_id TEXT NOT NULL DEFAULT '',
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 raw_sha256 TEXT NOT NULL DEFAULT '',
 metrics_json TEXT NOT NULL DEFAULT '{}',
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(adapter_key) REFERENCES source_adapters_220(adapter_key),
 CHECK(status IN ('running','completed','not_found','failed','blocked'))
);
CREATE INDEX IF NOT EXISTS idx_source_runs_220_case ON source_runs_220(case_id,started_at);

CREATE TABLE IF NOT EXISTS source_results_220(
 result_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 adapter_key TEXT NOT NULL,
 result_type TEXT NOT NULL,
 title TEXT NOT NULL DEFAULT '',
 canonical_url TEXT NOT NULL DEFAULT '',
 display_value TEXT NOT NULL DEFAULT '',
 language TEXT NOT NULL DEFAULT 'und',
 confidence REAL NOT NULL DEFAULT 0.0,
 evidence_ref TEXT NOT NULL,
 independence_key TEXT NOT NULL,
 fields_json TEXT NOT NULL DEFAULT '{}',
 limitations_json TEXT NOT NULL DEFAULT '[]',
 review_status TEXT NOT NULL DEFAULT 'unreviewed',
 candidate_only INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES source_runs_220(run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(review_status IN ('unreviewed','accepted_candidate','rejected','duplicate','needs_more_evidence')),
 UNIQUE(case_id,adapter_key,independence_key)
);
CREATE INDEX IF NOT EXISTS idx_source_results_220_case ON source_results_220(case_id,created_at);

CREATE TABLE IF NOT EXISTS source_health_checks_220(
 check_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 check_type TEXT NOT NULL,
 status TEXT NOT NULL,
 latency_ms INTEGER NOT NULL DEFAULT 0,
 http_status INTEGER NOT NULL DEFAULT 0,
 result_count INTEGER NOT NULL DEFAULT 0,
 observed_fingerprint TEXT NOT NULL DEFAULT '',
 missing_fields_json TEXT NOT NULL DEFAULT '[]',
 rate_limit_json TEXT NOT NULL DEFAULT '{}',
 retry_after_at TEXT NOT NULL DEFAULT '',
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 checked_by TEXT NOT NULL,
 checked_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES source_adapters_220(adapter_key),
 CHECK(status IN ('healthy','degraded','unavailable','rate_limited','contract_failed','blocked','not_configured'))
);
CREATE INDEX IF NOT EXISTS idx_source_health_checks_220_adapter ON source_health_checks_220(adapter_key,checked_at);

CREATE TABLE IF NOT EXISTS source_result_reviews_220(
 review_id TEXT PRIMARY KEY,
 result_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 reason TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(result_id) REFERENCES source_results_220(result_id),
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('accepted_candidate','rejected','duplicate','needs_more_evidence'))
);
CREATE INDEX IF NOT EXISTS idx_source_result_reviews_220_case ON source_result_reviews_220(case_id,created_at);

CREATE TABLE IF NOT EXISTS build220_events(
 event_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 object_type TEXT NOT NULL,
 object_id TEXT NOT NULL,
 actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build220_events_case ON build220_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_source_health_checks_220_no_update BEFORE UPDATE ON source_health_checks_220 BEGIN SELECT RAISE(ABORT,'source_health_checks_220 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_health_checks_220_no_delete BEFORE DELETE ON source_health_checks_220 BEGIN SELECT RAISE(ABORT,'source_health_checks_220 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_result_reviews_220_no_update BEFORE UPDATE ON source_result_reviews_220 BEGIN SELECT RAISE(ABORT,'source_result_reviews_220 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_result_reviews_220_no_delete BEFORE DELETE ON source_result_reviews_220 BEGIN SELECT RAISE(ABORT,'source_result_reviews_220 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build220_events_no_update BEFORE UPDATE ON build220_events BEGIN SELECT RAISE(ABORT,'build220_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build220_events_no_delete BEFORE DELETE ON build220_events BEGIN SELECT RAISE(ABORT,'build220_events is immutable'); END;
'''


def ensure_build220_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_220)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','220.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','220.0')")
    db.conn.commit()
