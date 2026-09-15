from __future__ import annotations
from typing import Any

SCHEMA_241 = r"""
CREATE TABLE IF NOT EXISTS reasoning_cycles_241 (
  cycle_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  session_id TEXT NOT NULL DEFAULT '',
  turn_id TEXT NOT NULL DEFAULT '',
  question TEXT NOT NULL,
  primary_hypothesis TEXT NOT NULL,
  counter_hypothesis TEXT NOT NULL,
  primary_confidence REAL NOT NULL,
  counter_confidence REAL NOT NULL,
  supporting_refs_json TEXT NOT NULL,
  counter_supporting_refs_json TEXT NOT NULL,
  contradicting_refs_json TEXT NOT NULL,
  evidence_gaps_json TEXT NOT NULL,
  origin TEXT NOT NULL,
  supersedes_cycle_id TEXT NOT NULL DEFAULT '',
  state_sha256 TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  CHECK(primary_confidence>=0 AND primary_confidence<=1),
  CHECK(counter_confidence>=0 AND counter_confidence<=1)
);
CREATE INDEX IF NOT EXISTS idx_reasoning_cycles241_case ON reasoning_cycles_241(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS reasoning_reviews_241 (
  review_id TEXT PRIMARY KEY,
  cycle_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(cycle_id) REFERENCES reasoning_cycles_241(cycle_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','revise','rejected'))
);
CREATE INDEX IF NOT EXISTS idx_reasoning_reviews241_case ON reasoning_reviews_241(case_id,reviewed_at DESC);

CREATE TABLE IF NOT EXISTS reasoning_next_steps_241 (
  step_id TEXT PRIMARY KEY,
  cycle_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  label TEXT NOT NULL,
  evidence_gap TEXT NOT NULL,
  expected_information_gain REAL NOT NULL,
  gap_reduction REAL NOT NULL,
  opsec_risk REAL NOT NULL,
  priority_score REAL NOT NULL,
  proposed_by TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(cycle_id) REFERENCES reasoning_cycles_241(cycle_id) ON DELETE CASCADE,
  CHECK(expected_information_gain>=0 AND expected_information_gain<=1),
  CHECK(gap_reduction>=0 AND gap_reduction<=1),
  CHECK(opsec_risk>=0 AND opsec_risk<=1),
  CHECK(priority_score>=0 AND priority_score<=1)
);
CREATE INDEX IF NOT EXISTS idx_reasoning_steps241_case ON reasoning_next_steps_241(case_id,priority_score DESC,proposed_at DESC);

CREATE TABLE IF NOT EXISTS reasoning_corrections_241 (
  correction_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  prior_cycle_id TEXT NOT NULL,
  new_cycle_id TEXT NOT NULL UNIQUE,
  trigger_evidence_refs_json TEXT NOT NULL,
  rationale TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(prior_cycle_id) REFERENCES reasoning_cycles_241(cycle_id) ON DELETE RESTRICT,
  FOREIGN KEY(new_cycle_id) REFERENCES reasoning_cycles_241(cycle_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_reasoning_corr241_case ON reasoning_corrections_241(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS reasoning_turn_assessments_241 (
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  turn_id TEXT NOT NULL UNIQUE,
  build240_assessment_id TEXT NOT NULL,
  hypothesis_balance_score REAL NOT NULL,
  contradiction_score REAL NOT NULL,
  gap_score REAL NOT NULL,
  correction_score REAL NOT NULL,
  workflow_score REAL NOT NULL,
  gate TEXT NOT NULL,
  assessment_json TEXT NOT NULL,
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  CHECK(hypothesis_balance_score>=0 AND hypothesis_balance_score<=1),
  CHECK(contradiction_score>=0 AND contradiction_score<=1),
  CHECK(gap_score>=0 AND gap_score<=1),
  CHECK(correction_score>=0 AND correction_score<=1),
  CHECK(workflow_score>=0 AND workflow_score<=1)
);
CREATE INDEX IF NOT EXISTS idx_reasoning_turn241_case ON reasoning_turn_assessments_241(case_id,assessed_at DESC);

CREATE TABLE IF NOT EXISTS reasoning_training_links_241 (
  training_link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  assessment_id TEXT NOT NULL UNIQUE,
  training_example_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(assessment_id) REFERENCES reasoning_turn_assessments_241(assessment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build241_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events241_case ON build241_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_cycles241_no_update BEFORE UPDATE ON reasoning_cycles_241 BEGIN SELECT RAISE(ABORT,'reasoning_cycles_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_cycles241_no_delete BEFORE DELETE ON reasoning_cycles_241 BEGIN SELECT RAISE(ABORT,'reasoning_cycles_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_reviews241_no_update BEFORE UPDATE ON reasoning_reviews_241 BEGIN SELECT RAISE(ABORT,'reasoning_reviews_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_reviews241_no_delete BEFORE DELETE ON reasoning_reviews_241 BEGIN SELECT RAISE(ABORT,'reasoning_reviews_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_steps241_no_update BEFORE UPDATE ON reasoning_next_steps_241 BEGIN SELECT RAISE(ABORT,'reasoning_next_steps_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_steps241_no_delete BEFORE DELETE ON reasoning_next_steps_241 BEGIN SELECT RAISE(ABORT,'reasoning_next_steps_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_corr241_no_update BEFORE UPDATE ON reasoning_corrections_241 BEGIN SELECT RAISE(ABORT,'reasoning_corrections_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_corr241_no_delete BEFORE DELETE ON reasoning_corrections_241 BEGIN SELECT RAISE(ABORT,'reasoning_corrections_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_turnassess241_no_update BEFORE UPDATE ON reasoning_turn_assessments_241 BEGIN SELECT RAISE(ABORT,'reasoning_turn_assessments_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_turnassess241_no_delete BEFORE DELETE ON reasoning_turn_assessments_241 BEGIN SELECT RAISE(ABORT,'reasoning_turn_assessments_241 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events241_no_update BEFORE UPDATE ON build241_events BEGIN SELECT RAISE(ABORT,'build241_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events241_no_delete BEFORE DELETE ON build241_events BEGIN SELECT RAISE(ABORT,'build241_events is immutable'); END;
"""

def ensure_build241_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_241)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','241.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','241.0')")
    db.conn.commit()
