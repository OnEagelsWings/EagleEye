from __future__ import annotations
from typing import Any

SCHEMA_217 = r'''
CREATE TABLE IF NOT EXISTS source_router_catalog_217(
 source_key TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 route_class TEXT NOT NULL,
 adapter_type TEXT NOT NULL,
 input_types_json TEXT NOT NULL,
 expected_outputs_json TEXT NOT NULL,
 requires_auth INTEGER NOT NULL DEFAULT 0,
 network_capable INTEGER NOT NULL DEFAULT 0,
 opsec_risk TEXT NOT NULL,
 data_exposure TEXT NOT NULL,
 estimated_cost TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 0,
 health_status TEXT NOT NULL,
 upstream_ref TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 CHECK(opsec_risk IN ('low','elevated','high','critical'))
);
CREATE INDEX IF NOT EXISTS idx_source_router_catalog_217_class ON source_router_catalog_217(route_class,active,health_status);

CREATE TABLE IF NOT EXISTS investigation_plans_217(
 plan_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 session_id TEXT NOT NULL,
 objective TEXT NOT NULL,
 question_language TEXT NOT NULL,
 known_facts_json TEXT NOT NULL,
 information_gaps_json TEXT NOT NULL,
 identity_risks_json TEXT NOT NULL,
 opsec_risks_json TEXT NOT NULL,
 assumptions_json TEXT NOT NULL,
 completion_criteria_json TEXT NOT NULL,
 retrieved_refs_json TEXT NOT NULL,
 retrieval_run_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 status TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,
 created_by TEXT NOT NULL,
 reviewed_by TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(session_id) REFERENCES ai_chat_sessions_216(session_id) ON DELETE CASCADE,
 CHECK(status IN ('proposed','changes_requested','approved','rejected','materialized'))
);
CREATE INDEX IF NOT EXISTS idx_investigation_plans_217_case ON investigation_plans_217(case_id,updated_at);

CREATE TABLE IF NOT EXISTS source_routes_217(
 route_id TEXT PRIMARY KEY,
 plan_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 gap_key TEXT NOT NULL,
 route_class TEXT NOT NULL,
 source_key TEXT NOT NULL DEFAULT '',
 purpose TEXT NOT NULL,
 target_type TEXT NOT NULL,
 target_value TEXT NOT NULL,
 expected_output TEXT NOT NULL,
 rationale TEXT NOT NULL,
 priority INTEGER NOT NULL,
 opsec_risk TEXT NOT NULL,
 data_exposure TEXT NOT NULL,
 requires_auth INTEGER NOT NULL DEFAULT 0,
 estimated_cost TEXT NOT NULL,
 stop_condition TEXT NOT NULL,
 availability TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(plan_id) REFERENCES investigation_plans_217(plan_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(priority BETWEEN 1 AND 5),
 CHECK(opsec_risk IN ('low','elevated','high','critical')),
 CHECK(availability IN ('available','degraded','unavailable')),
 CHECK(status IN ('proposed','approved','rejected','deferred','blocked','prepared'))
);
CREATE INDEX IF NOT EXISTS idx_source_routes_217_plan ON source_routes_217(plan_id,priority,status);

CREATE TABLE IF NOT EXISTS source_route_reviews_217(
 review_id TEXT PRIMARY KEY,
 plan_id TEXT NOT NULL,
 route_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 edited_target_value TEXT NOT NULL DEFAULT '',
 edited_purpose TEXT NOT NULL DEFAULT '',
 reason TEXT NOT NULL,
 preflight_id TEXT NOT NULL DEFAULT '',
 reviewer TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(plan_id) REFERENCES investigation_plans_217(plan_id) ON DELETE CASCADE,
 FOREIGN KEY(route_id) REFERENCES source_routes_217(route_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('approved','rejected','deferred','blocked'))
);
CREATE INDEX IF NOT EXISTS idx_source_route_reviews_217_route ON source_route_reviews_217(route_id,created_at);

CREATE TABLE IF NOT EXISTS source_execution_requests_217(
 request_id TEXT PRIMARY KEY,
 plan_id TEXT NOT NULL,
 route_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 source_key TEXT NOT NULL,
 request_json TEXT NOT NULL,
 execution_mode TEXT NOT NULL,
 status TEXT NOT NULL,
 linked_object_type TEXT NOT NULL DEFAULT '',
 linked_object_id TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(plan_id) REFERENCES investigation_plans_217(plan_id) ON DELETE CASCADE,
 FOREIGN KEY(route_id) REFERENCES source_routes_217(route_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('ready_local','pending_manual_execution','prepared','unavailable','cancelled'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_execution_requests_217_route ON source_execution_requests_217(route_id);

CREATE TABLE IF NOT EXISTS source_router_benchmarks_217(
 benchmark_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 title TEXT NOT NULL,
 objective TEXT NOT NULL,
 expected_route_classes_json TEXT NOT NULL,
 forbidden_route_classes_json TEXT NOT NULL,
 expected_gap_types_json TEXT NOT NULL,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_router_benchmark_results_217(
 result_id TEXT PRIMARY KEY,
 benchmark_id TEXT NOT NULL,
 plan_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 route_precision REAL NOT NULL,
 route_recall REAL NOT NULL,
 forbidden_hits INTEGER NOT NULL,
 gap_coverage REAL NOT NULL,
 passed INTEGER NOT NULL,
 metrics_json TEXT NOT NULL,
 evaluated_by TEXT NOT NULL,
 evaluated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(benchmark_id) REFERENCES source_router_benchmarks_217(benchmark_id) ON DELETE CASCADE,
 FOREIGN KEY(plan_id) REFERENCES investigation_plans_217(plan_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build217_events(
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
CREATE INDEX IF NOT EXISTS idx_build217_events_case ON build217_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_source_route_reviews_217_no_update BEFORE UPDATE ON source_route_reviews_217 BEGIN SELECT RAISE(ABORT,'source_route_reviews_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_route_reviews_217_no_delete BEFORE DELETE ON source_route_reviews_217 BEGIN SELECT RAISE(ABORT,'source_route_reviews_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_execution_requests_217_no_update BEFORE UPDATE ON source_execution_requests_217 BEGIN SELECT RAISE(ABORT,'source_execution_requests_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_execution_requests_217_no_delete BEFORE DELETE ON source_execution_requests_217 BEGIN SELECT RAISE(ABORT,'source_execution_requests_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_router_benchmark_results_217_no_update BEFORE UPDATE ON source_router_benchmark_results_217 BEGIN SELECT RAISE(ABORT,'source_router_benchmark_results_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_source_router_benchmark_results_217_no_delete BEFORE DELETE ON source_router_benchmark_results_217 BEGIN SELECT RAISE(ABORT,'source_router_benchmark_results_217 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build217_events_no_update BEFORE UPDATE ON build217_events BEGIN SELECT RAISE(ABORT,'build217_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build217_events_no_delete BEFORE DELETE ON build217_events BEGIN SELECT RAISE(ABORT,'build217_events is immutable'); END;
'''


def ensure_build217_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_217)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','217.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','217.0')")
    db.conn.commit()
