from __future__ import annotations
from typing import Any

SCHEMA_245 = r'''
CREATE TABLE IF NOT EXISTS workflow_runs_245 (
  workflow_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, objective TEXT NOT NULL,
  primary_question TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflow245_case ON workflow_runs_245(case_id,created_at);

CREATE TABLE IF NOT EXISTS workflow_checkpoints_245 (
  checkpoint_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, case_id TEXT NOT NULL,
  stage TEXT NOT NULL, summary TEXT NOT NULL, related_refs_json TEXT NOT NULL,
  quality_score REAL NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(workflow_id) REFERENCES workflow_runs_245(workflow_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS workflow_checkpoint_reviews_245 (
  review_id TEXT PRIMARY KEY, checkpoint_id TEXT NOT NULL UNIQUE, workflow_id TEXT NOT NULL,
  case_id TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(checkpoint_id) REFERENCES workflow_checkpoints_245(checkpoint_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_stage_events_245 (
  event_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, case_id TEXT NOT NULL,
  from_stage TEXT NOT NULL, to_stage TEXT NOT NULL, decision TEXT NOT NULL,
  rationale TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL,
  previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workflow_stage245 ON workflow_stage_events_245(workflow_id,created_at,event_id);

CREATE TABLE IF NOT EXISTS workflow_work_items_245 (
  item_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, case_id TEXT NOT NULL,
  stage TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
  priority INTEGER NOT NULL, owner_role TEXT NOT NULL, agent_role TEXT NOT NULL,
  status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workitem245_case ON workflow_work_items_245(case_id,status,priority);
CREATE TABLE IF NOT EXISTS workflow_work_item_events_245 (
  event_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, workflow_id TEXT NOT NULL,
  case_id TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
  actor TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_agent_links_245 (
  link_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, item_id TEXT NOT NULL,
  case_id TEXT NOT NULL, agent_run_id TEXT NOT NULL, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_training_links_245 (
  training_link_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, checkpoint_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL, training_example_id TEXT NOT NULL, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_events_245 (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workflow_events245 ON workflow_events_245(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_checkpoint245_no_update BEFORE UPDATE ON workflow_checkpoints_245 BEGIN SELECT RAISE(ABORT,'workflow_checkpoints_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_checkpoint245_no_delete BEFORE DELETE ON workflow_checkpoints_245 BEGIN SELECT RAISE(ABORT,'workflow_checkpoints_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_checkpointreview245_no_update BEFORE UPDATE ON workflow_checkpoint_reviews_245 BEGIN SELECT RAISE(ABORT,'workflow_checkpoint_reviews_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_checkpointreview245_no_delete BEFORE DELETE ON workflow_checkpoint_reviews_245 BEGIN SELECT RAISE(ABORT,'workflow_checkpoint_reviews_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_stageevents245_no_update BEFORE UPDATE ON workflow_stage_events_245 BEGIN SELECT RAISE(ABORT,'workflow_stage_events_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_stageevents245_no_delete BEFORE DELETE ON workflow_stage_events_245 BEGIN SELECT RAISE(ABORT,'workflow_stage_events_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events245_no_update BEFORE UPDATE ON workflow_events_245 BEGIN SELECT RAISE(ABORT,'workflow_events_245 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events245_no_delete BEFORE DELETE ON workflow_events_245 BEGIN SELECT RAISE(ABORT,'workflow_events_245 is immutable'); END;
'''

def ensure_build245_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_245)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','245.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','245.0')")
    db.conn.commit()
