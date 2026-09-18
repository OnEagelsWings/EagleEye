from __future__ import annotations

from typing import Any


def ensure_evidence_schema_121(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS evidence_packages_121 (
          package_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_ref TEXT DEFAULT '',
          title TEXT NOT NULL,
          source_url TEXT DEFAULT '',
          media_type TEXT NOT NULL,
          byte_size INTEGER NOT NULL,
          raw_relpath TEXT NOT NULL UNIQUE,
          raw_sha256 TEXT NOT NULL,
          metadata_sha256 TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          package_sha256 TEXT NOT NULL,
          captured_at TEXT NOT NULL,
          captured_by TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'preserved',
          candidate_only INTEGER NOT NULL DEFAULT 1,
          export_allowed INTEGER NOT NULL DEFAULT 0,
          redaction_required INTEGER NOT NULL DEFAULT 1,
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_packages_121_case
          ON evidence_packages_121(case_id, captured_at, status);
        CREATE INDEX IF NOT EXISTS idx_evidence_packages_121_hash
          ON evidence_packages_121(raw_sha256, case_id);

        CREATE TABLE IF NOT EXISTS evidence_artifacts_121 (
          artifact_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          layer TEXT NOT NULL,
          media_type TEXT NOT NULL,
          relpath TEXT NOT NULL UNIQUE,
          content_sha256 TEXT NOT NULL,
          byte_size INTEGER NOT NULL,
          parser_name TEXT DEFAULT '',
          parser_version TEXT DEFAULT '',
          parser_config_json TEXT NOT NULL DEFAULT '{}',
          input_sha256 TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          created_by TEXT NOT NULL,
          FOREIGN KEY(package_id) REFERENCES evidence_packages_121(package_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          CHECK(layer IN ('normalized','derived'))
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_artifacts_121_package
          ON evidence_artifacts_121(package_id, layer, created_at);

        CREATE TABLE IF NOT EXISTS evidence_custody_events_121 (
          event_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          actor TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          details_json TEXT NOT NULL,
          previous_hash TEXT NOT NULL,
          event_hash TEXT NOT NULL UNIQUE,
          FOREIGN KEY(package_id) REFERENCES evidence_packages_121(package_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_custody_121_package
          ON evidence_custody_events_121(package_id, timestamp, event_id);

        CREATE TABLE IF NOT EXISTS evidence_exports_121 (
          export_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          export_relpath TEXT NOT NULL UNIQUE,
          manifest_sha256 TEXT NOT NULL,
          package_count INTEGER NOT NULL,
          redaction_profile TEXT NOT NULL,
          created_at TEXT NOT NULL,
          created_by TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        """
    )
    db.conn.commit()
