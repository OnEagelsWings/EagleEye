from __future__ import annotations
from typing import Any

SCHEMA_219 = r'''
CREATE TABLE IF NOT EXISTS source_reliability_profiles_219(
 adapter_key TEXT PRIMARY KEY,
 state TEXT NOT NULL,
 circuit_state TEXT NOT NULL,
 circuit_open_until TEXT NOT NULL DEFAULT '',
 quarantine_reason TEXT NOT NULL DEFAULT '',
 contract_version TEXT NOT NULL,
 baseline_fingerprint TEXT NOT NULL DEFAULT '',
 last_observed_fingerprint TEXT NOT NULL DEFAULT '',
 consecutive_successes INTEGER NOT NULL DEFAULT 0,
 consecutive_failures INTEGER NOT NULL DEFAULT 0,
 total_checks INTEGER NOT NULL DEFAULT 0,
 total_successes INTEGER NOT NULL DEFAULT 0,
 total_failures INTEGER NOT NULL DEFAULT 0,
 last_success_at TEXT NOT NULL DEFAULT '',
 last_failure_at TEXT NOT NULL DEFAULT '',
 last_checked_at TEXT NOT NULL DEFAULT '',
 quality_json TEXT NOT NULL DEFAULT '{}',
 policy_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(state IN ('not_configured','healthy','degraded','unavailable','cooldown','quarantined')),
 CHECK(circuit_state IN ('closed','open','half_open'))
);
CREATE INDEX IF NOT EXISTS idx_source_reliability_profiles_219_state ON source_reliability_profiles_219(state,circuit_state);

CREATE TABLE IF NOT EXISTS source_health_checks_219(
 check_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 check_type TEXT NOT NULL,
 status TEXT NOT NULL,
 latency_ms INTEGER NOT NULL DEFAULT 0,
 http_status INTEGER NOT NULL DEFAULT 0,
 result_count INTEGER NOT NULL DEFAULT 0,
 observed_fingerprint TEXT NOT NULL DEFAULT '',
 baseline_fingerprint TEXT NOT NULL DEFAULT '',
 required_fields_json TEXT NOT NULL DEFAULT '[]',
 missing_fields_json TEXT NOT NULL DEFAULT '[]',
 unexpected_fields_json TEXT NOT NULL DEFAULT '[]',
 drift_severity TEXT NOT NULL DEFAULT 'none',
 rate_limit_json TEXT NOT NULL DEFAULT '{}',
 retry_after_at TEXT NOT NULL DEFAULT '',
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 details_json TEXT NOT NULL DEFAULT '{}',
 checked_by TEXT NOT NULL,
 checked_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(check_type IN ('fixture','parser_contract','live_run','canary','version','rate_limit','manual')),
 CHECK(status IN ('healthy','degraded','unavailable','rate_limited','contract_failed','drift_detected','blocked','not_configured')),
 CHECK(drift_severity IN ('none','informational','breaking'))
);
CREATE INDEX IF NOT EXISTS idx_source_health_checks_219_adapter ON source_health_checks_219(adapter_key,checked_at);

CREATE TABLE IF NOT EXISTS source_canaries_219(
 canary_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 title TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value TEXT NOT NULL,
 expected_state TEXT NOT NULL,
 expected_min_results INTEGER NOT NULL DEFAULT 0,
 execution_mode TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1,
 contains_personal_data INTEGER NOT NULL DEFAULT 0,
 notes TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(execution_mode IN ('fixture_only','controlled_live')),
 CHECK(expected_state IN ('completed','not_found'))
);
CREATE INDEX IF NOT EXISTS idx_source_canaries_219_adapter ON source_canaries_219(adapter_key,active);

CREATE TABLE IF NOT EXISTS source_drift_events_219(
 drift_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 check_id TEXT NOT NULL,
 drift_type TEXT NOT NULL,
 severity TEXT NOT NULL,
 baseline_fingerprint TEXT NOT NULL,
 observed_fingerprint TEXT NOT NULL,
 changes_json TEXT NOT NULL,
 action_taken TEXT NOT NULL,
 detected_by TEXT NOT NULL,
 detected_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 FOREIGN KEY(check_id) REFERENCES source_health_checks_219(check_id),
 CHECK(severity IN ('informational','breaking')),
 CHECK(action_taken IN ('recorded','degraded','circuit_opened','quarantined'))
);
CREATE INDEX IF NOT EXISTS idx_source_drift_events_219_adapter ON source_drift_events_219(adapter_key,detected_at);

CREATE TABLE IF NOT EXISTS source_reliability_snapshots_219(
 snapshot_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 availability REAL NOT NULL,
 parser_stability REAL NOT NULL,
 precision_score REAL NOT NULL,
 recall_score REAL NOT NULL,
 freshness REAL NOT NULL,
 provenance_quality REAL NOT NULL,
 opsec_score REAL NOT NULL,
 latency_score REAL NOT NULL,
 overall_score REAL NOT NULL,
 state TEXT NOT NULL,
 sample_size INTEGER NOT NULL,
 metrics_json TEXT NOT NULL,
 calculated_by TEXT NOT NULL,
 calculated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key)
);
CREATE INDEX IF NOT EXISTS idx_source_reliability_snapshots_219_adapter ON source_reliability_snapshots_219(adapter_key,calculated_at);

CREATE TABLE IF NOT EXISTS source_reliability_reviews_219(
 review_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 decision TEXT NOT NULL,
 reason TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(decision IN ('confirm_healthy','confirm_degraded','quarantine','release_quarantine','needs_more_observation'))
);
CREATE INDEX IF NOT EXISTS idx_source_reliability_reviews_219_adapter ON source_reliability_reviews_219(adapter_key,created_at);

CREATE TABLE IF NOT EXISTS build219_events(
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
CREATE INDEX IF NOT EXISTS idx_build219_events_case ON build219_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_source_health_checks_219_no_update BEFORE UPDATE ON source_health_checks_219 BEGIN SELECT RAISE(ABORT,'source_health_checks_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_health_checks_219_no_delete BEFORE DELETE ON source_health_checks_219 BEGIN SELECT RAISE(ABORT,'source_health_checks_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_drift_events_219_no_update BEFORE UPDATE ON source_drift_events_219 BEGIN SELECT RAISE(ABORT,'source_drift_events_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_drift_events_219_no_delete BEFORE DELETE ON source_drift_events_219 BEGIN SELECT RAISE(ABORT,'source_drift_events_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_reliability_snapshots_219_no_update BEFORE UPDATE ON source_reliability_snapshots_219 BEGIN SELECT RAISE(ABORT,'source_reliability_snapshots_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_reliability_snapshots_219_no_delete BEFORE DELETE ON source_reliability_snapshots_219 BEGIN SELECT RAISE(ABORT,'source_reliability_snapshots_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_reliability_reviews_219_no_update BEFORE UPDATE ON source_reliability_reviews_219 BEGIN SELECT RAISE(ABORT,'source_reliability_reviews_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_reliability_reviews_219_no_delete BEFORE DELETE ON source_reliability_reviews_219 BEGIN SELECT RAISE(ABORT,'source_reliability_reviews_219 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build219_events_no_update BEFORE UPDATE ON build219_events BEGIN SELECT RAISE(ABORT,'build219_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build219_events_no_delete BEFORE DELETE ON build219_events BEGIN SELECT RAISE(ABORT,'build219_events is immutable'); END;
'''


def ensure_build219_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_219)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','219.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','219.0')")
    db.conn.commit()
