from __future__ import annotations
from typing import Any

BUILD145_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS phase4_health_snapshots_145(
  snapshot145_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  audit144_id TEXT NOT NULL DEFAULT '',
  backup144_id TEXT NOT NULL DEFAULT '',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  findings_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_health145_case ON phase4_health_snapshots_145(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS phase4_maintenance_runs_145(
  maintenance145_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  dry_run INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL,
  before_json TEXT NOT NULL DEFAULT '{}',
  actions_json TEXT NOT NULL DEFAULT '[]',
  after_json TEXT NOT NULL DEFAULT '{}',
  estimated_savings_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_maintenance145_case ON phase4_maintenance_runs_145(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS phase4_baselines_145(
  baseline145_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  audit144_id TEXT NOT NULL,
  backup144_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending_review',
  baseline_label TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  manifest_relpath TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_decision TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  sealed INTEGER NOT NULL DEFAULT 0,
  sealed_by TEXT NOT NULL DEFAULT '',
  sealed_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(audit144_id) REFERENCES release_candidate_audits_144(audit144_id) ON DELETE RESTRICT,
  FOREIGN KEY(backup144_id) REFERENCES verified_backups_144(backup144_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_baselines145_case ON phase4_baselines_145(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS phase4_release_seals_145(
  seal145_id TEXT PRIMARY KEY,
  baseline145_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  seal_relpath TEXT NOT NULL,
  seal_sha256 TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  verification_count INTEGER NOT NULL DEFAULT 0,
  last_verification_status TEXT NOT NULL DEFAULT '',
  last_verified_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(baseline145_id) REFERENCES phase4_baselines_145(baseline145_id) ON DELETE RESTRICT,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_seals145_case ON phase4_release_seals_145(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build145_events(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  previous_hash TEXT NOT NULL,
  event_hash TEXT UNIQUE NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build145_events_case ON build145_events(case_id,sequence DESC);

-- Phase-4 final query-path hardening. These indexes are additive and safe for
-- old case data because they do not alter rows or uniqueness semantics.
CREATE INDEX IF NOT EXISTS idx_search_tasks145_case_status ON search_tasks(case_id,status,category,created_at);
CREATE INDEX IF NOT EXISTS idx_photo_assets145_case_review ON photo_assets_136(case_id,target_id,review_status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_assertions145_case_state ON evidence_assertions_138(case_id,epistemic_state,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sources145_case_type ON evidence_sources_138(case_id,source_type,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks145_case_status ON investigation_workflow_tasks_137(case_id,status,priority DESC,updated_at DESC);
"""


def ensure_build145_schema(db: Any) -> None:
    db.conn.executescript(BUILD145_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','145.0')")
    db.conn.commit()
