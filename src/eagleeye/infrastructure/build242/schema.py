from __future__ import annotations
from typing import Any

SCHEMA_242 = r'''
CREATE TABLE IF NOT EXISTS agent_runs_242 (
  run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, objective TEXT NOT NULL, status TEXT NOT NULL,
  priority INTEGER NOT NULL, max_tokens INTEGER NOT NULL, max_cost REAL NOT NULL, max_seconds INTEGER NOT NULL,
  tokens_used INTEGER NOT NULL DEFAULT 0, cost_used REAL NOT NULL DEFAULT 0, elapsed_seconds INTEGER NOT NULL DEFAULT 0,
  checkpoint_json TEXT NOT NULL DEFAULT '{}', created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_runs242_case ON agent_runs_242(case_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_tasks_242 (
  task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, role TEXT NOT NULL, sequence_no INTEGER NOT NULL,
  dependencies_json TEXT NOT NULL, status TEXT NOT NULL, human_gate INTEGER NOT NULL DEFAULT 0,
  input_json TEXT NOT NULL, output_json TEXT NOT NULL DEFAULT '{}', checkpoint_json TEXT NOT NULL DEFAULT '{}',
  retry_count INTEGER NOT NULL DEFAULT 0, max_retries INTEGER NOT NULL DEFAULT 2,
  tokens_used INTEGER NOT NULL DEFAULT 0, cost_used REAL NOT NULL DEFAULT 0,
  worker_id TEXT NOT NULL DEFAULT '', error_text TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES agent_runs_242(run_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_tasks242_run ON agent_tasks_242(run_id,sequence_no);

CREATE TABLE IF NOT EXISTS agent_task_approvals_242 (
  approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
  decision TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES agent_tasks_242(task_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected','deferred'))
);

CREATE TABLE IF NOT EXISTS opsec_observations_242 (
  observation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT NOT NULL DEFAULT '', category TEXT NOT NULL,
  severity TEXT NOT NULL, confidence REAL NOT NULL, source_type TEXT NOT NULL, source_ref TEXT NOT NULL,
  details_json TEXT NOT NULL, detected_by TEXT NOT NULL, detected_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(severity IN ('info','low','medium','high','critical')), CHECK(confidence>=0 AND confidence<=1)
);
CREATE INDEX IF NOT EXISTS idx_opsec_obs242_case ON opsec_observations_242(case_id,detected_at DESC);

CREATE TABLE IF NOT EXISTS opsec_observation_reviews_242 (
  review_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
  reviewed_severity TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(observation_id) REFERENCES opsec_observations_242(observation_id) ON DELETE CASCADE,
  CHECK(decision IN ('confirmed','false_positive','needs_context')),
  CHECK(reviewed_severity IN ('info','low','medium','high','critical'))
);

CREATE TABLE IF NOT EXISTS opsec_policy_snapshots_242 (
  policy_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL, origin TEXT NOT NULL,
  weights_json TEXT NOT NULL, thresholds_json TEXT NOT NULL, evidence_count INTEGER NOT NULL,
  training_meta_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  UNIQUE(case_id,version), FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS opsec_policy_reviews_242 (
  policy_review_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
  rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(policy_id) REFERENCES opsec_policy_snapshots_242(policy_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected'))
);
CREATE TABLE IF NOT EXISTS opsec_policy_activations_242 (
  activation_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, case_id TEXT NOT NULL, activated_by TEXT NOT NULL,
  activated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(policy_id) REFERENCES opsec_policy_snapshots_242(policy_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opsec_assessments_242 (
  assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT NOT NULL DEFAULT '', policy_id TEXT NOT NULL,
  risk_score REAL NOT NULL, risk_level TEXT NOT NULL, factors_json TEXT NOT NULL, recommendations_json TEXT NOT NULL,
  containment_json TEXT NOT NULL, assessed_by TEXT NOT NULL, assessed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(risk_score>=0 AND risk_score<=1)
);
CREATE INDEX IF NOT EXISTS idx_opsec_assess242_case ON opsec_assessments_242(case_id,assessed_at DESC);

CREATE TABLE IF NOT EXISTS opsec_responses_242 (
  response_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assessment_id TEXT NOT NULL, action_type TEXT NOT NULL,
  target_ref TEXT NOT NULL, rationale TEXT NOT NULL, automatic INTEGER NOT NULL DEFAULT 0, actor TEXT NOT NULL,
  created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(assessment_id) REFERENCES opsec_assessments_242(assessment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opsec_case_state_242 (
  case_id TEXT PRIMARY KEY, mode TEXT NOT NULL DEFAULT 'normal', manual_gate_required INTEGER NOT NULL DEFAULT 0,
  last_assessment_id TEXT NOT NULL DEFAULT '', last_risk_score REAL NOT NULL DEFAULT 0,
  last_risk_level TEXT NOT NULL DEFAULT 'low', updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opsec_training_links_242 (
  training_link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, observation_id TEXT NOT NULL UNIQUE,
  training_example_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(observation_id) REFERENCES opsec_observations_242(observation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build242_events (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
  object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events242_case ON build242_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_opsec_obs242_no_update BEFORE UPDATE ON opsec_observations_242 BEGIN SELECT RAISE(ABORT,'opsec_observations_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_obs242_no_delete BEFORE DELETE ON opsec_observations_242 BEGIN SELECT RAISE(ABORT,'opsec_observations_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_rev242_no_update BEFORE UPDATE ON opsec_observation_reviews_242 BEGIN SELECT RAISE(ABORT,'opsec_observation_reviews_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_rev242_no_delete BEFORE DELETE ON opsec_observation_reviews_242 BEGIN SELECT RAISE(ABORT,'opsec_observation_reviews_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_pol242_no_update BEFORE UPDATE ON opsec_policy_snapshots_242 BEGIN SELECT RAISE(ABORT,'opsec_policy_snapshots_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_pol242_no_delete BEFORE DELETE ON opsec_policy_snapshots_242 BEGIN SELECT RAISE(ABORT,'opsec_policy_snapshots_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_polrev242_no_update BEFORE UPDATE ON opsec_policy_reviews_242 BEGIN SELECT RAISE(ABORT,'opsec_policy_reviews_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_assess242_no_update BEFORE UPDATE ON opsec_assessments_242 BEGIN SELECT RAISE(ABORT,'opsec_assessments_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsec_resp242_no_update BEFORE UPDATE ON opsec_responses_242 BEGIN SELECT RAISE(ABORT,'opsec_responses_242 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events242_no_update BEFORE UPDATE ON build242_events BEGIN SELECT RAISE(ABORT,'build242_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events242_no_delete BEFORE DELETE ON build242_events BEGIN SELECT RAISE(ABORT,'build242_events is immutable'); END;
'''

def ensure_build242_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_242)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','242.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','242.0')")
    db.conn.commit()
