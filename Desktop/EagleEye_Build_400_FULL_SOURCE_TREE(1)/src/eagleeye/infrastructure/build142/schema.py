from __future__ import annotations
from typing import Any

BUILD142_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS professional_reports_142(
  report142_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  source_report131_id TEXT,
  report_type TEXT NOT NULL,
  title TEXT NOT NULL,
  audience TEXT NOT NULL,
  redaction_profile TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  version_no INTEGER NOT NULL DEFAULT 1,
  snapshot_sha256 TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  content_json TEXT NOT NULL,
  citation_coverage REAL NOT NULL DEFAULT 0,
  supported_claims INTEGER NOT NULL DEFAULT 0,
  contested_claims INTEGER NOT NULL DEFAULT 0,
  unresolved_claims INTEGER NOT NULL DEFAULT 0,
  sensitive_items INTEGER NOT NULL DEFAULT 0,
  stale INTEGER NOT NULL DEFAULT 0,
  stale_reason TEXT NOT NULL DEFAULT '',
  review_requested_by TEXT NOT NULL DEFAULT '',
  review_requested_at TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_decision TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  released INTEGER NOT NULL DEFAULT 0,
  released_by TEXT NOT NULL DEFAULT '',
  released_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(source_report131_id) REFERENCES report_drafts_131(report_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_reports142_case ON professional_reports_142(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS report_redaction_rules_142(
  rule_id TEXT PRIMARY KEY,
  report142_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  field_path TEXT NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  replacement TEXT NOT NULL DEFAULT '[REDACTED]',
  automatic INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(report142_id) REFERENCES professional_reports_142(report142_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_redactions142_report ON report_redaction_rules_142(report142_id,created_at);

CREATE TABLE IF NOT EXISTS report_reviews_142(
  review142_id TEXT PRIMARY KEY,
  report142_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  findings_json TEXT NOT NULL DEFAULT '[]',
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(report142_id) REFERENCES professional_reports_142(report142_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_report_reviews142 ON report_reviews_142(report142_id,created_at DESC);

CREATE TABLE IF NOT EXISTS report_releases_142(
  release_id TEXT PRIMARY KEY,
  report142_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  release_no INTEGER NOT NULL,
  release_label TEXT NOT NULL,
  status TEXT NOT NULL,
  audience TEXT NOT NULL,
  redaction_profile TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  export_dir_relpath TEXT NOT NULL,
  html_relpath TEXT NOT NULL DEFAULT '',
  pdf_relpath TEXT NOT NULL DEFAULT '',
  json_relpath TEXT NOT NULL DEFAULT '',
  manifest_relpath TEXT NOT NULL DEFAULT '',
  watermark_text TEXT NOT NULL DEFAULT '',
  file_count INTEGER NOT NULL DEFAULT 0,
  immutable INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(report142_id) REFERENCES professional_reports_142(report142_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(report142_id,release_no)
);
CREATE INDEX IF NOT EXISTS idx_releases142_case ON report_releases_142(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS report_export_files_142(
  export_file_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  file_role TEXT NOT NULL,
  relpath TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(release_id) REFERENCES report_releases_142(release_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(release_id,file_role)
);
CREATE INDEX IF NOT EXISTS idx_export_files142_release ON report_export_files_142(release_id,file_role);

CREATE TABLE IF NOT EXISTS report_integrity_checks_142(
  check_id TEXT PRIMARY KEY,
  release_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  checked_files INTEGER NOT NULL DEFAULT 0,
  failed_files INTEGER NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT '[]',
  checked_by TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  FOREIGN KEY(release_id) REFERENCES report_releases_142(release_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_integrity142_release ON report_integrity_checks_142(release_id,checked_at DESC);

CREATE TABLE IF NOT EXISTS build142_events(
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
CREATE INDEX IF NOT EXISTS idx_build142_events_case ON build142_events(case_id,sequence DESC);
"""


def ensure_build142_schema(db: Any) -> None:
    db.conn.executescript(BUILD142_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','142.0')")
    db.conn.commit()
