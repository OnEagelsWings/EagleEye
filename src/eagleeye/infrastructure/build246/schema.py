from __future__ import annotations
from typing import Any

SCHEMA_246 = r'''
CREATE TABLE IF NOT EXISTS watchlists_246 (
  watchlist_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, name TEXT NOT NULL,
  purpose TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watchlists246_case ON watchlists_246(case_id,status,created_at);

CREATE TABLE IF NOT EXISTS watch_targets_246 (
  target_id TEXT PRIMARY KEY, watchlist_id TEXT NOT NULL, case_id TEXT NOT NULL,
  target_type TEXT NOT NULL, target_ref TEXT NOT NULL, label TEXT NOT NULL,
  source_key TEXT NOT NULL, source_url TEXT NOT NULL, interval_minutes INTEGER NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watchtargets246_case ON watch_targets_246(case_id,watchlist_id,target_type);

CREATE TABLE IF NOT EXISTS watch_target_state_246 (
  target_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status TEXT NOT NULL,
  last_observed_at TEXT NOT NULL, next_due_at TEXT NOT NULL, last_observation_id TEXT NOT NULL,
  last_change_id TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_observations_246 (
  observation_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, watchlist_id TEXT NOT NULL,
  case_id TEXT NOT NULL, observed_at TEXT NOT NULL, content_sha256 TEXT NOT NULL,
  summary TEXT NOT NULL, source_ref TEXT NOT NULL, source_key TEXT NOT NULL,
  source_url TEXT NOT NULL, metadata_json TEXT NOT NULL, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitorobs246_target ON monitor_observations_246(target_id,observed_at,created_at);

CREATE TABLE IF NOT EXISTS monitor_changes_246 (
  change_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, watchlist_id TEXT NOT NULL,
  case_id TEXT NOT NULL, previous_observation_id TEXT NOT NULL, current_observation_id TEXT NOT NULL,
  change_type TEXT NOT NULL, significance REAL NOT NULL, summary TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitorchanges246_case ON monitor_changes_246(case_id,created_at);

CREATE TABLE IF NOT EXISTS monitor_change_reviews_246 (
  review_id TEXT PRIMARY KEY, change_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  decision TEXT NOT NULL, reviewed_significance REAL NOT NULL, rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_agent_links_246 (
  monitor_run_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, case_id TEXT NOT NULL,
  agent_run_id TEXT NOT NULL UNIQUE, egress_decision TEXT NOT NULL, requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_evidence_links_246 (
  link_id TEXT PRIMARY KEY, change_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL UNIQUE, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_training_links_246 (
  training_link_id TEXT PRIMARY KEY, change_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  training_example_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitor_opsec_links_246 (
  opsec_link_id TEXT PRIMARY KEY, target_id TEXT NOT NULL, case_id TEXT NOT NULL,
  observation_id_242 TEXT NOT NULL UNIQUE, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monitoring_events_246 (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitoringevents246 ON monitoring_events_246(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_watchlist246_no_update BEFORE UPDATE ON watchlists_246 BEGIN SELECT RAISE(ABORT,'watchlists_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_watchlist246_no_delete BEFORE DELETE ON watchlists_246 BEGIN SELECT RAISE(ABORT,'watchlists_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_watchtarget246_no_update BEFORE UPDATE ON watch_targets_246 BEGIN SELECT RAISE(ABORT,'watch_targets_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_watchtarget246_no_delete BEFORE DELETE ON watch_targets_246 BEGIN SELECT RAISE(ABORT,'watch_targets_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorobs246_no_update BEFORE UPDATE ON monitor_observations_246 BEGIN SELECT RAISE(ABORT,'monitor_observations_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorobs246_no_delete BEFORE DELETE ON monitor_observations_246 BEGIN SELECT RAISE(ABORT,'monitor_observations_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorchange246_no_update BEFORE UPDATE ON monitor_changes_246 BEGIN SELECT RAISE(ABORT,'monitor_changes_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorchange246_no_delete BEFORE DELETE ON monitor_changes_246 BEGIN SELECT RAISE(ABORT,'monitor_changes_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorreview246_no_update BEFORE UPDATE ON monitor_change_reviews_246 BEGIN SELECT RAISE(ABORT,'monitor_change_reviews_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitorreview246_no_delete BEFORE DELETE ON monitor_change_reviews_246 BEGIN SELECT RAISE(ABORT,'monitor_change_reviews_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitoringevents246_no_update BEFORE UPDATE ON monitoring_events_246 BEGIN SELECT RAISE(ABORT,'monitoring_events_246 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_monitoringevents246_no_delete BEFORE DELETE ON monitoring_events_246 BEGIN SELECT RAISE(ABORT,'monitoring_events_246 is immutable'); END;
'''

def ensure_build246_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_246)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','246.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','246.0')")
    db.conn.commit()
