from __future__ import annotations
from typing import Any

BUILD144_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS release_candidate_audits_144(
  audit144_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL,
  score INTEGER NOT NULL DEFAULT 0,
  blocker_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  pass_count INTEGER NOT NULL DEFAULT 0,
  findings_json TEXT NOT NULL DEFAULT '[]',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  optional_tests INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_audits144_case ON release_candidate_audits_144(case_id,completed_at DESC);

CREATE TABLE IF NOT EXISTS verified_backups_144(
  backup144_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  restore_status TEXT NOT NULL,
  backup_dir_relpath TEXT NOT NULL,
  database_relpath TEXT NOT NULL,
  manifest_relpath TEXT NOT NULL,
  database_sha256 TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL DEFAULT 0,
  artifact_count INTEGER NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  verified_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_backups144_case ON verified_backups_144(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS performance_benchmarks_144(
  benchmark144_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  iterations INTEGER NOT NULL,
  duration_ms REAL NOT NULL,
  operations_per_second REAL NOT NULL,
  p95_ms REAL NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_benchmarks144_case ON performance_benchmarks_144(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS phase4_risks_144(
  risk144_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  summary TEXT NOT NULL,
  remediation TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  source_audit_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_risks144_case ON phase4_risks_144(case_id,status,severity,updated_at DESC);

CREATE TABLE IF NOT EXISTS build144_events(
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
CREATE INDEX IF NOT EXISTS idx_build144_events_case ON build144_events(case_id,sequence DESC);
"""


def ensure_build144_schema(db: Any) -> None:
    db.conn.executescript(BUILD144_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','144.0')")
    db.conn.commit()
