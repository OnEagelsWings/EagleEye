from __future__ import annotations

from typing import Any


BUILD136_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS firefox_session_events_136(
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  state_before TEXT NOT NULL DEFAULT '',
  state_after TEXT NOT NULL DEFAULT '',
  details_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_firefox_events136_case ON firefox_session_events_136(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS firefox_recovery_actions_136(
  action_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  action_key TEXT NOT NULL,
  confirmation_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_firefox_recovery136_case ON firefox_recovery_actions_136(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS runtime_diagnostics_136(
  run_id TEXT PRIMARY KEY,
  case_id TEXT,
  status TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  blocker_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  checks_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runtime_diag136_case ON runtime_diagnostics_136(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS photo_assets_136(
  asset_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  source_kind TEXT NOT NULL,
  title TEXT NOT NULL,
  original_filename TEXT NOT NULL DEFAULT '',
  mime_type TEXT NOT NULL DEFAULT '',
  byte_size INTEGER NOT NULL DEFAULT 0,
  width_px INTEGER NOT NULL DEFAULT 0,
  height_px INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL,
  storage_relpath TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  source_page_url TEXT NOT NULL DEFAULT '',
  source_label TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  evidence_integrity TEXT NOT NULL DEFAULT 'original_preserved',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_photo_assets136_case ON photo_assets_136(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_photo_assets136_target ON photo_assets_136(target_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_assets136_local_dedupe ON photo_assets_136(case_id,sha256,source_kind) WHERE source_kind='local_file';

CREATE TABLE IF NOT EXISTS photo_asset_events_136(
  event_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_photo_events136_asset ON photo_asset_events_136(asset_id,created_at DESC);
"""


def ensure_build136_schema(db: Any) -> None:
    db.conn.executescript(BUILD136_SCHEMA)
    columns = {str(row[1]) for row in db.conn.execute("PRAGMA table_info(photo_assets_136)").fetchall()}
    if "width_px" not in columns:
        db.conn.execute("ALTER TABLE photo_assets_136 ADD COLUMN width_px INTEGER NOT NULL DEFAULT 0")
    if "height_px" not in columns:
        db.conn.execute("ALTER TABLE photo_assets_136 ADD COLUMN height_px INTEGER NOT NULL DEFAULT 0")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','136.0')")
    db.conn.commit()
