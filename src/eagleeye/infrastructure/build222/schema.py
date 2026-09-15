from __future__ import annotations
from typing import Any

SCHEMA_222 = r'''
CREATE TABLE IF NOT EXISTS phase7_qualification_suites_222(
 suite_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 title TEXT NOT NULL,
 description TEXT NOT NULL,
 status TEXT NOT NULL,
 target_scenario_count INTEGER NOT NULL DEFAULT 10,
 qualification_profile_json TEXT NOT NULL DEFAULT '{}',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('draft','running','development_qualified','conditional','operational_qualified','failed','archived'))
);
CREATE INDEX IF NOT EXISTS idx_phase7_suites_222_case ON phase7_qualification_suites_222(case_id,created_at);

CREATE TABLE IF NOT EXISTS phase7_scenarios_222(
 scenario_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 scenario_key TEXT NOT NULL,
 title TEXT NOT NULL,
 category TEXT NOT NULL,
 language TEXT NOT NULL DEFAULT 'de',
 difficulty TEXT NOT NULL DEFAULT 'medium',
 objective TEXT NOT NULL,
 expected_refs_json TEXT NOT NULL DEFAULT '[]',
 forbidden_claims_json TEXT NOT NULL DEFAULT '[]',
 expected_behaviors_json TEXT NOT NULL DEFAULT '[]',
 expected_route_classes_json TEXT NOT NULL DEFAULT '[]',
 expected_source_classes_json TEXT NOT NULL DEFAULT '[]',
 minimum_cycles INTEGER NOT NULL DEFAULT 1,
 maximum_first_lead_seconds INTEGER NOT NULL DEFAULT 300,
 status TEXT NOT NULL DEFAULT 'active',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES phase7_qualification_suites_222(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 UNIQUE(suite_id,scenario_key),
 CHECK(difficulty IN ('basic','medium','hard','adversarial')),
 CHECK(status IN ('active','disabled','completed'))
);
CREATE INDEX IF NOT EXISTS idx_phase7_scenarios_222_suite ON phase7_scenarios_222(suite_id,category);

CREATE TABLE IF NOT EXISTS phase7_scenario_runs_222(
 run_id TEXT PRIMARY KEY,
 scenario_id TEXT NOT NULL,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 loop_id TEXT NOT NULL,
 model_name TEXT NOT NULL DEFAULT '',
 cycles_completed INTEGER NOT NULL DEFAULT 0,
 first_lead_seconds REAL NOT NULL DEFAULT 0,
 status TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT NOT NULL,
 evaluator TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(scenario_id) REFERENCES phase7_scenarios_222(scenario_id) ON DELETE CASCADE,
 FOREIGN KEY(suite_id) REFERENCES phase7_qualification_suites_222(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('passed','failed','conditional','error'))
);
CREATE INDEX IF NOT EXISTS idx_phase7_runs_222_suite ON phase7_scenario_runs_222(suite_id,finished_at);

CREATE TABLE IF NOT EXISTS phase7_scenario_metrics_222(
 result_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL UNIQUE,
 scenario_id TEXT NOT NULL,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 citation_precision REAL NOT NULL DEFAULT 0,
 citation_recall REAL NOT NULL DEFAULT 0,
 source_grounding REAL NOT NULL DEFAULT 0,
 hallucination_hits INTEGER NOT NULL DEFAULT 0,
 behavior_score REAL NOT NULL DEFAULT 0,
 route_precision REAL NOT NULL DEFAULT 0,
 route_recall REAL NOT NULL DEFAULT 0,
 adapter_precision REAL NOT NULL DEFAULT 0,
 adapter_recall REAL NOT NULL DEFAULT 0,
 false_positive_rate REAL NOT NULL DEFAULT 0,
 contradiction_score REAL NOT NULL DEFAULT 0,
 translation_score REAL NOT NULL DEFAULT 0,
 dialog_continuity REAL NOT NULL DEFAULT 0,
 recovery_score REAL NOT NULL DEFAULT 0,
 opsec_score REAL NOT NULL DEFAULT 0,
 overall_score REAL NOT NULL DEFAULT 0,
 passed INTEGER NOT NULL DEFAULT 0,
 metrics_json TEXT NOT NULL DEFAULT '{}',
 evaluated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES phase7_scenario_runs_222(run_id) ON DELETE CASCADE,
 FOREIGN KEY(scenario_id) REFERENCES phase7_scenarios_222(scenario_id) ON DELETE CASCADE,
 FOREIGN KEY(suite_id) REFERENCES phase7_qualification_suites_222(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_phase7_metrics_222_suite ON phase7_scenario_metrics_222(suite_id,evaluated_at);

CREATE TABLE IF NOT EXISTS phase7_environment_checks_222(
 check_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 check_key TEXT NOT NULL,
 environment TEXT NOT NULL,
 status TEXT NOT NULL,
 details_json TEXT NOT NULL DEFAULT '{}',
 evidence_ref TEXT NOT NULL DEFAULT '',
 checked_by TEXT NOT NULL,
 checked_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES phase7_qualification_suites_222(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('passed','failed','pending','conditional','not_applicable'))
);
CREATE INDEX IF NOT EXISTS idx_phase7_env_222_suite ON phase7_environment_checks_222(suite_id,check_key,checked_at);

CREATE TABLE IF NOT EXISTS phase7_qualification_reports_222(
 report_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 development_status TEXT NOT NULL,
 operational_status TEXT NOT NULL,
 aggregate_score REAL NOT NULL DEFAULT 0,
 gate_results_json TEXT NOT NULL,
 metrics_json TEXT NOT NULL,
 report_path TEXT NOT NULL DEFAULT '',
 generated_by TEXT NOT NULL,
 generated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES phase7_qualification_suites_222(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(development_status IN ('passed','failed','conditional')),
 CHECK(operational_status IN ('passed','failed','pending','conditional'))
);
CREATE INDEX IF NOT EXISTS idx_phase7_reports_222_suite ON phase7_qualification_reports_222(suite_id,generated_at);

CREATE TABLE IF NOT EXISTS build222_events(
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
CREATE INDEX IF NOT EXISTS idx_build222_events_case ON build222_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_phase7_scenario_metrics_222_no_update BEFORE UPDATE ON phase7_scenario_metrics_222 BEGIN SELECT RAISE(ABORT,'phase7_scenario_metrics_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_phase7_scenario_metrics_222_no_delete BEFORE DELETE ON phase7_scenario_metrics_222 BEGIN SELECT RAISE(ABORT,'phase7_scenario_metrics_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_phase7_environment_checks_222_no_update BEFORE UPDATE ON phase7_environment_checks_222 BEGIN SELECT RAISE(ABORT,'phase7_environment_checks_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_phase7_environment_checks_222_no_delete BEFORE DELETE ON phase7_environment_checks_222 BEGIN SELECT RAISE(ABORT,'phase7_environment_checks_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_phase7_qualification_reports_222_no_update BEFORE UPDATE ON phase7_qualification_reports_222 BEGIN SELECT RAISE(ABORT,'phase7_qualification_reports_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_phase7_qualification_reports_222_no_delete BEFORE DELETE ON phase7_qualification_reports_222 BEGIN SELECT RAISE(ABORT,'phase7_qualification_reports_222 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build222_events_no_update BEFORE UPDATE ON build222_events BEGIN SELECT RAISE(ABORT,'build222_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build222_events_no_delete BEFORE DELETE ON build222_events BEGIN SELECT RAISE(ABORT,'build222_events is immutable'); END;
'''


def ensure_build222_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_222)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','222.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','222.0')")
    db.conn.commit()
