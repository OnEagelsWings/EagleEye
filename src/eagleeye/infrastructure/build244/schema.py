from __future__ import annotations
from typing import Any

SCHEMA_244 = r'''
CREATE TABLE IF NOT EXISTS cockpit_feedback_244 (
  feedback_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, category TEXT NOT NULL,
  rating INTEGER NOT NULL, outcome TEXT NOT NULL, note TEXT NOT NULL,
  related_ref TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cockpit_feedback_reviews_244 (
  review_id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  decision TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(feedback_id) REFERENCES cockpit_feedback_244(feedback_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS cockpit_training_links_244 (
  training_link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, feedback_id TEXT NOT NULL UNIQUE,
  training_example_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cockpit_snapshots_244 (
  snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, state_sha256 TEXT NOT NULL,
  summary_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS build244_events (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cockpit244_case ON cockpit_feedback_244(case_id,created_at);
CREATE INDEX IF NOT EXISTS idx_events244_case ON build244_events(case_id,created_at,event_id);
CREATE TRIGGER IF NOT EXISTS trg_feedback244_no_update BEFORE UPDATE ON cockpit_feedback_244 BEGIN SELECT RAISE(ABORT,'cockpit_feedback_244 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_feedback244_no_delete BEFORE DELETE ON cockpit_feedback_244 BEGIN SELECT RAISE(ABORT,'cockpit_feedback_244 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_feedbackreview244_no_update BEFORE UPDATE ON cockpit_feedback_reviews_244 BEGIN SELECT RAISE(ABORT,'cockpit_feedback_reviews_244 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_feedbackreview244_no_delete BEFORE DELETE ON cockpit_feedback_reviews_244 BEGIN SELECT RAISE(ABORT,'cockpit_feedback_reviews_244 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events244_no_update BEFORE UPDATE ON build244_events BEGIN SELECT RAISE(ABORT,'build244_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events244_no_delete BEFORE DELETE ON build244_events BEGIN SELECT RAISE(ABORT,'build244_events is immutable'); END;
'''

def ensure_build244_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_244)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','244.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','244.0')")
    db.conn.commit()
