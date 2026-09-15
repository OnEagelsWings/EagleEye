from __future__ import annotations
from typing import Any

SCHEMA_218 = r'''
CREATE TABLE IF NOT EXISTS digital_source_adapters_218(
 adapter_key TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 adapter_kind TEXT NOT NULL,
 target_types_json TEXT NOT NULL,
 allowed_hosts_json TEXT NOT NULL,
 auth_mode TEXT NOT NULL,
 executable_names_json TEXT NOT NULL,
 network_capable INTEGER NOT NULL DEFAULT 0,
 candidate_only INTEGER NOT NULL DEFAULT 1,
 opsec_risk TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 0,
 health_status TEXT NOT NULL,
 detected_path TEXT NOT NULL DEFAULT '',
 detected_version TEXT NOT NULL DEFAULT '',
 dataset_path TEXT NOT NULL DEFAULT '',
 allowed_sites_json TEXT NOT NULL DEFAULT '[]',
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 CHECK(adapter_kind IN ('http_api','local_cli','reviewed_dataset')),
 CHECK(opsec_risk IN ('low','elevated','high','critical'))
);
CREATE INDEX IF NOT EXISTS idx_digital_source_adapters_218_health ON digital_source_adapters_218(active,health_status,adapter_kind);

CREATE TABLE IF NOT EXISTS digital_source_runs_218(
 run_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL DEFAULT '',
 route_id TEXT NOT NULL DEFAULT '',
 case_id TEXT NOT NULL,
 adapter_key TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value TEXT NOT NULL,
 purpose TEXT NOT NULL,
 execution_mode TEXT NOT NULL,
 status TEXT NOT NULL,
 started_by TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT NOT NULL DEFAULT '',
 result_count INTEGER NOT NULL DEFAULT 0,
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 evidence_source_id TEXT NOT NULL DEFAULT '',
 raw_sha256 TEXT NOT NULL DEFAULT '',
 metrics_json TEXT NOT NULL DEFAULT '{}',
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(status IN ('planned','running','completed','partial','not_found','blocked','failed','cancelled'))
);
CREATE INDEX IF NOT EXISTS idx_digital_source_runs_218_case ON digital_source_runs_218(case_id,started_at);
CREATE INDEX IF NOT EXISTS idx_digital_source_runs_218_request ON digital_source_runs_218(request_id,adapter_key);

CREATE TABLE IF NOT EXISTS digital_source_results_218(
 result_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 adapter_key TEXT NOT NULL,
 result_type TEXT NOT NULL,
 existence_state TEXT NOT NULL,
 platform TEXT NOT NULL,
 profile_url TEXT NOT NULL DEFAULT '',
 display_name TEXT NOT NULL DEFAULT '',
 username TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '',
 location TEXT NOT NULL DEFAULT '',
 organization TEXT NOT NULL DEFAULT '',
 language TEXT NOT NULL DEFAULT 'und',
 confidence REAL NOT NULL DEFAULT 0.0,
 evidence_ref TEXT NOT NULL DEFAULT '',
 independence_key TEXT NOT NULL DEFAULT '',
 fields_json TEXT NOT NULL DEFAULT '{}',
 limitations_json TEXT NOT NULL DEFAULT '[]',
 review_status TEXT NOT NULL DEFAULT 'unreviewed',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES digital_source_runs_218(run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(existence_state IN ('found','possible','not_found','blocked','error')),
 CHECK(review_status IN ('unreviewed','accepted_candidate','rejected','duplicate','needs_more_evidence'))
);
CREATE INDEX IF NOT EXISTS idx_digital_source_results_218_case ON digital_source_results_218(case_id,adapter_key,existence_state);
CREATE UNIQUE INDEX IF NOT EXISTS idx_digital_source_results_218_dedupe ON digital_source_results_218(case_id,adapter_key,independence_key,existence_state);

CREATE TABLE IF NOT EXISTS digital_source_result_reviews_218(
 review_id TEXT PRIMARY KEY,
 result_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 reason TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(result_id) REFERENCES digital_source_results_218(result_id) ON DELETE CASCADE,
 FOREIGN KEY(run_id) REFERENCES digital_source_runs_218(run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('accepted_candidate','rejected','duplicate','needs_more_evidence'))
);
CREATE INDEX IF NOT EXISTS idx_digital_source_reviews_218_result ON digital_source_result_reviews_218(result_id,created_at);

CREATE TABLE IF NOT EXISTS digital_source_health_218(
 health_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 check_type TEXT NOT NULL,
 status TEXT NOT NULL,
 latency_ms INTEGER NOT NULL DEFAULT 0,
 result_count INTEGER NOT NULL DEFAULT 0,
 error_class TEXT NOT NULL DEFAULT '',
 details_json TEXT NOT NULL DEFAULT '{}',
 checked_by TEXT NOT NULL,
 checked_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key),
 CHECK(status IN ('healthy','degraded','unavailable','blocked','not_configured'))
);
CREATE INDEX IF NOT EXISTS idx_digital_source_health_218_adapter ON digital_source_health_218(adapter_key,checked_at);

CREATE TABLE IF NOT EXISTS digital_source_benchmarks_218(
 benchmark_id TEXT PRIMARY KEY,
 adapter_key TEXT NOT NULL,
 title TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value TEXT NOT NULL,
 expected_state TEXT NOT NULL,
 expected_min_results INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(adapter_key) REFERENCES digital_source_adapters_218(adapter_key)
);
CREATE TABLE IF NOT EXISTS digital_source_benchmark_results_218(
 result_id TEXT PRIMARY KEY,
 benchmark_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 adapter_key TEXT NOT NULL,
 passed INTEGER NOT NULL,
 observed_state TEXT NOT NULL,
 observed_results INTEGER NOT NULL,
 metrics_json TEXT NOT NULL,
 evaluated_by TEXT NOT NULL,
 evaluated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(benchmark_id) REFERENCES digital_source_benchmarks_218(benchmark_id) ON DELETE CASCADE,
 FOREIGN KEY(run_id) REFERENCES digital_source_runs_218(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build218_events(
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
CREATE INDEX IF NOT EXISTS idx_build218_events_case ON build218_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_digital_source_reviews_218_no_update BEFORE UPDATE ON digital_source_result_reviews_218 BEGIN SELECT RAISE(ABORT,'digital_source_result_reviews_218 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_digital_source_reviews_218_no_delete BEFORE DELETE ON digital_source_result_reviews_218 BEGIN SELECT RAISE(ABORT,'digital_source_result_reviews_218 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_digital_source_health_218_no_update BEFORE UPDATE ON digital_source_health_218 BEGIN SELECT RAISE(ABORT,'digital_source_health_218 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_digital_source_health_218_no_delete BEFORE DELETE ON digital_source_health_218 BEGIN SELECT RAISE(ABORT,'digital_source_health_218 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build218_events_no_update BEFORE UPDATE ON build218_events BEGIN SELECT RAISE(ABORT,'build218_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build218_events_no_delete BEFORE DELETE ON build218_events BEGIN SELECT RAISE(ABORT,'build218_events is immutable'); END;
'''


def ensure_build218_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_218)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','218.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','218.0')")
    db.conn.commit()
