from __future__ import annotations
from typing import Any

SCHEMA_240 = r"""
CREATE TABLE IF NOT EXISTS coai_case_snapshots_240 (
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  state_sha256 TEXT NOT NULL,
  entity_count INTEGER NOT NULL,
  claim_count INTEGER NOT NULL,
  accepted_evidence_count INTEGER NOT NULL,
  accepted_edge_count INTEGER NOT NULL,
  verified_claim_count INTEGER NOT NULL,
  open_gap_count INTEGER NOT NULL,
  open_task_count INTEGER NOT NULL,
  contradiction_count INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_coai_snapshot240_case ON coai_case_snapshots_240(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS coai_turn_assessments_240 (
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  turn_id TEXT NOT NULL UNIQUE,
  snapshot_id TEXT NOT NULL,
  answer_sha256 TEXT NOT NULL,
  observation_count INTEGER NOT NULL,
  grounded_observation_count INTEGER NOT NULL,
  accepted_evidence_citation_count INTEGER NOT NULL,
  candidate_reference_count INTEGER NOT NULL,
  contradiction_surfaced INTEGER NOT NULL,
  open_questions_count INTEGER NOT NULL,
  recommended_steps_count INTEGER NOT NULL,
  grounding_score REAL NOT NULL,
  discipline_score REAL NOT NULL,
  gate TEXT NOT NULL,
  assessment_json TEXT NOT NULL,
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(snapshot_id) REFERENCES coai_case_snapshots_240(snapshot_id) ON DELETE RESTRICT,
  CHECK(grounding_score>=0 AND grounding_score<=1),
  CHECK(discipline_score>=0 AND discipline_score<=1)
);
CREATE INDEX IF NOT EXISTS idx_coai_assess240_case ON coai_turn_assessments_240(case_id,assessed_at DESC);

CREATE TABLE IF NOT EXISTS coai_training_links_240 (
  training_link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  assessment_id TEXT NOT NULL UNIQUE,
  training_example_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(assessment_id) REFERENCES coai_turn_assessments_240(assessment_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build240_events (
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
CREATE INDEX IF NOT EXISTS idx_events240_case ON build240_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_snapshot240_no_update BEFORE UPDATE ON coai_case_snapshots_240 BEGIN SELECT RAISE(ABORT,'coai_case_snapshots_240 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_snapshot240_no_delete BEFORE DELETE ON coai_case_snapshots_240 BEGIN SELECT RAISE(ABORT,'coai_case_snapshots_240 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_assess240_no_update BEFORE UPDATE ON coai_turn_assessments_240 BEGIN SELECT RAISE(ABORT,'coai_turn_assessments_240 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_assess240_no_delete BEFORE DELETE ON coai_turn_assessments_240 BEGIN SELECT RAISE(ABORT,'coai_turn_assessments_240 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events240_no_update BEFORE UPDATE ON build240_events BEGIN SELECT RAISE(ABORT,'build240_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events240_no_delete BEFORE DELETE ON build240_events BEGIN SELECT RAISE(ABORT,'build240_events is immutable'); END;
"""

def ensure_build240_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_240)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','240.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','240.0')")
    db.conn.commit()
