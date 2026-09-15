from __future__ import annotations
from typing import Any

SCHEMA_224 = r'''
CREATE TABLE IF NOT EXISTS ai_eval_suites_224(
 suite_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 title TEXT NOT NULL,
 description TEXT NOT NULL,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('draft','ready','running','completed','archived'))
);
CREATE INDEX IF NOT EXISTS idx_eval_suites_224_case ON ai_eval_suites_224(case_id,created_at);

CREATE TABLE IF NOT EXISTS ai_eval_tasks_224(
 task_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 task_type TEXT NOT NULL,
 title TEXT NOT NULL,
 language TEXT NOT NULL,
 difficulty TEXT NOT NULL,
 prompt_text TEXT NOT NULL,
 context_json TEXT NOT NULL,
 expected_refs_json TEXT NOT NULL,
 expected_behaviors_json TEXT NOT NULL,
 forbidden_claims_json TEXT NOT NULL,
 expected_contradictions_json TEXT NOT NULL,
 weight REAL NOT NULL DEFAULT 1.0,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES ai_eval_suites_224(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(task_type IN ('planning','source_selection','source_criticism','entity_caution','contradiction','translation','dialogue_correction','opsec','reporting','retrieval')),
 CHECK(difficulty IN ('basic','intermediate','advanced','adversarial')),
 CHECK(weight > 0 AND weight <= 10)
);
CREATE INDEX IF NOT EXISTS idx_eval_tasks_224_suite ON ai_eval_tasks_224(suite_id,created_at,task_id);

CREATE TABLE IF NOT EXISTS ai_model_profiles_224(
 profile_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 profile_type TEXT NOT NULL,
 capabilities_json TEXT NOT NULL,
 context_length INTEGER NOT NULL DEFAULT 0,
 parameter_size TEXT NOT NULL DEFAULT '',
 quantization_level TEXT NOT NULL DEFAULT '',
 local_verified INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(profile_type IN ('fast','investigator','reasoning','translation','embedding','general')),
 CHECK(local_verified IN (0,1)),
 CHECK(status IN ('available','unavailable','blocked','review_required'))
);
CREATE INDEX IF NOT EXISTS idx_model_profiles_224_case ON ai_model_profiles_224(case_id,profile_type,model_name);

CREATE TABLE IF NOT EXISTS ai_eval_runs_224(
 run_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 task_id TEXT NOT NULL,
 profile_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 status TEXT NOT NULL,
 response_json TEXT NOT NULL DEFAULT '{}',
 citations_json TEXT NOT NULL DEFAULT '[]',
 metrics_json TEXT NOT NULL DEFAULT '{}',
 request_sha256 TEXT NOT NULL,
 response_sha256 TEXT NOT NULL DEFAULT '',
 started_by TEXT NOT NULL,
 started_at TEXT NOT NULL,
 completed_at TEXT NOT NULL DEFAULT '',
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 human_review_required INTEGER NOT NULL DEFAULT 1,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES ai_eval_suites_224(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(task_id) REFERENCES ai_eval_tasks_224(task_id) ON DELETE CASCADE,
 FOREIGN KEY(profile_id) REFERENCES ai_model_profiles_224(profile_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('running','completed','failed','blocked')),
 CHECK(human_review_required IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_224_suite ON ai_eval_runs_224(suite_id,model_name,task_id);

CREATE TABLE IF NOT EXISTS ai_eval_reviews_224(
 review_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 correctness REAL NOT NULL,
 source_use REAL NOT NULL,
 reasoning_quality REAL NOT NULL,
 translation_quality REAL NOT NULL,
 opsec_quality REAL NOT NULL,
 usefulness REAL NOT NULL,
 decision TEXT NOT NULL,
 notes TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 reviewed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES ai_eval_runs_224(run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('accept','needs_revision','reject'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_reviews_224_run ON ai_eval_reviews_224(run_id);

CREATE TABLE IF NOT EXISTS ai_model_scorecards_224(
 scorecard_id TEXT PRIMARY KEY,
 suite_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 aggregate_score REAL NOT NULL,
 task_scores_json TEXT NOT NULL,
 performance_json TEXT NOT NULL,
 safety_json TEXT NOT NULL,
 recommendation_json TEXT NOT NULL,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(suite_id) REFERENCES ai_eval_suites_224(suite_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('review_required','approved','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_model_scorecards_224_suite ON ai_model_scorecards_224(suite_id,aggregate_score DESC);

CREATE TABLE IF NOT EXISTS ai_routing_recommendations_224(
 recommendation_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 suite_id TEXT NOT NULL,
 routing_json TEXT NOT NULL,
 rationale_json TEXT NOT NULL,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 reviewed_by TEXT NOT NULL DEFAULT '',
 reviewed_at TEXT NOT NULL DEFAULT '',
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(suite_id) REFERENCES ai_eval_suites_224(suite_id) ON DELETE CASCADE,
 CHECK(status IN ('review_required','approved','rejected'))
);

CREATE TABLE IF NOT EXISTS build224_events(
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
CREATE INDEX IF NOT EXISTS idx_build224_events_case ON build224_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_eval_tasks_224_no_update BEFORE UPDATE ON ai_eval_tasks_224 BEGIN SELECT RAISE(ABORT,'ai_eval_tasks_224 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_eval_tasks_224_no_delete BEFORE DELETE ON ai_eval_tasks_224 BEGIN SELECT RAISE(ABORT,'ai_eval_tasks_224 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_eval_runs_224_no_delete BEFORE DELETE ON ai_eval_runs_224 BEGIN SELECT RAISE(ABORT,'ai_eval_runs_224 may not be deleted'); END;
CREATE TRIGGER IF NOT EXISTS trg_build224_events_no_update BEFORE UPDATE ON build224_events BEGIN SELECT RAISE(ABORT,'build224_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build224_events_no_delete BEFORE DELETE ON build224_events BEGIN SELECT RAISE(ABORT,'build224_events is immutable'); END;
'''

def ensure_build224_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_224)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','224.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','224.0')")
    db.conn.commit()
