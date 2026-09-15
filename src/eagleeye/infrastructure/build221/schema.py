from __future__ import annotations
from typing import Any

SCHEMA_221 = r'''
CREATE TABLE IF NOT EXISTS ai_research_loops_221(
 loop_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 session_id TEXT NOT NULL,
 objective TEXT NOT NULL,
 working_language TEXT NOT NULL,
 model_name TEXT NOT NULL,
 status TEXT NOT NULL,
 current_role TEXT NOT NULL DEFAULT 'planner',
 current_cycle INTEGER NOT NULL DEFAULT 1,
 max_cycles INTEGER NOT NULL DEFAULT 3,
 source_policy_json TEXT NOT NULL DEFAULT '{}',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('active','awaiting_review','awaiting_action_approval','awaiting_next_cycle','completed','paused','blocked','cancelled')),
 CHECK(current_role IN ('planner','collector_coordinator','verifier','critic','translator','reporter'))
);
CREATE INDEX IF NOT EXISTS idx_ai_research_loops_221_case ON ai_research_loops_221(case_id,created_at);

CREATE TABLE IF NOT EXISTS ai_role_runs_221(
 run_id TEXT PRIMARY KEY,
 loop_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 cycle_no INTEGER NOT NULL,
 role_name TEXT NOT NULL,
 status TEXT NOT NULL,
 model_name TEXT NOT NULL,
 retrieval_run_id TEXT NOT NULL DEFAULT '',
 input_refs_json TEXT NOT NULL DEFAULT '[]',
 output_json TEXT NOT NULL DEFAULT '{}',
 citations_json TEXT NOT NULL DEFAULT '[]',
 grounding_score REAL NOT NULL DEFAULT 0.0,
 request_sha256 TEXT NOT NULL,
 response_sha256 TEXT NOT NULL DEFAULT '',
 prompt_tokens INTEGER NOT NULL DEFAULT 0,
 completion_tokens INTEGER NOT NULL DEFAULT 0,
 error_code TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 completed_at TEXT NOT NULL DEFAULT '',
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(loop_id) REFERENCES ai_research_loops_221(loop_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(role_name IN ('planner','collector_coordinator','verifier','critic','translator','reporter')),
 CHECK(status IN ('running','review_required','approved','changes_requested','rejected','failed','blocked')),
 UNIQUE(loop_id,cycle_no,role_name)
);
CREATE INDEX IF NOT EXISTS idx_ai_role_runs_221_loop ON ai_role_runs_221(loop_id,cycle_no,role_name);

CREATE TABLE IF NOT EXISTS ai_role_reviews_221(
 review_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 loop_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 reason TEXT NOT NULL,
 reviewer TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES ai_role_runs_221(run_id),
 FOREIGN KEY(loop_id) REFERENCES ai_research_loops_221(loop_id) ON DELETE CASCADE,
 CHECK(decision IN ('approved','changes_requested','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_ai_role_reviews_221_loop ON ai_role_reviews_221(loop_id,created_at);

CREATE TABLE IF NOT EXISTS ai_research_actions_221(
 action_id TEXT PRIMARY KEY,
 loop_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 cycle_no INTEGER NOT NULL,
 source_class TEXT NOT NULL,
 source_key TEXT NOT NULL DEFAULT '',
 target_type TEXT NOT NULL,
 target_value TEXT NOT NULL,
 purpose TEXT NOT NULL,
 expected_output TEXT NOT NULL,
 opsec_risk TEXT NOT NULL,
 data_exposure TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL,
 reviewer TEXT NOT NULL DEFAULT '',
 review_reason TEXT NOT NULL DEFAULT '',
 linked_request_type TEXT NOT NULL DEFAULT '',
 linked_request_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(loop_id) REFERENCES ai_research_loops_221(loop_id) ON DELETE CASCADE,
 FOREIGN KEY(run_id) REFERENCES ai_role_runs_221(run_id),
 CHECK(status IN ('proposed','approved','rejected','blocked','prepared','completed')),
 CHECK(opsec_risk IN ('low','elevated','high','critical'))
);
CREATE INDEX IF NOT EXISTS idx_ai_research_actions_221_loop ON ai_research_actions_221(loop_id,status);

CREATE TABLE IF NOT EXISTS ai_research_findings_221(
 finding_id TEXT PRIMARY KEY,
 loop_id TEXT NOT NULL,
 run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 cycle_no INTEGER NOT NULL,
 finding_type TEXT NOT NULL,
 text_value TEXT NOT NULL,
 evidence_refs_json TEXT NOT NULL DEFAULT '[]',
 confidence REAL NOT NULL DEFAULT 0.0,
 language TEXT NOT NULL DEFAULT 'und',
 review_status TEXT NOT NULL DEFAULT 'unreviewed',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(loop_id) REFERENCES ai_research_loops_221(loop_id) ON DELETE CASCADE,
 FOREIGN KEY(run_id) REFERENCES ai_role_runs_221(run_id),
 CHECK(finding_type IN ('observation','inference','hypothesis','contradiction','translation','summary','open_question','next_step')),
 CHECK(review_status IN ('unreviewed','accepted','rejected','needs_revision'))
);
CREATE INDEX IF NOT EXISTS idx_ai_research_findings_221_case ON ai_research_findings_221(case_id,created_at);

CREATE TABLE IF NOT EXISTS build221_events(
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
CREATE INDEX IF NOT EXISTS idx_build221_events_case ON build221_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_ai_role_reviews_221_no_update BEFORE UPDATE ON ai_role_reviews_221 BEGIN SELECT RAISE(ABORT,'ai_role_reviews_221 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_role_reviews_221_no_delete BEFORE DELETE ON ai_role_reviews_221 BEGIN SELECT RAISE(ABORT,'ai_role_reviews_221 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build221_events_no_update BEFORE UPDATE ON build221_events BEGIN SELECT RAISE(ABORT,'build221_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build221_events_no_delete BEFORE DELETE ON build221_events BEGIN SELECT RAISE(ABORT,'build221_events is immutable'); END;
'''


def ensure_build221_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_221)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','221.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','221.0')")
    db.conn.commit()
