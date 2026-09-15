from __future__ import annotations
from typing import Any

SCHEMA_168 = r'''
CREATE TABLE IF NOT EXISTS evidence_registry_168(
 evidence_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_type TEXT NOT NULL,
 source_ref TEXT NOT NULL, original_path TEXT, content_sha256 TEXT NOT NULL,
 byte_size INTEGER NOT NULL DEFAULT 0, media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
 classification TEXT NOT NULL, collected_by TEXT NOT NULL, collected_at TEXT NOT NULL,
 provenance_json TEXT NOT NULL, review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS custody_events_168(
 event_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
 event_type TEXT NOT NULL, actor TEXT NOT NULL, purpose TEXT NOT NULL,
 from_custodian TEXT, to_custodian TEXT, occurred_at TEXT NOT NULL,
 previous_sha256 TEXT, payload_sha256 TEXT NOT NULL,
 UNIQUE(evidence_id, sequence_no)
);
CREATE TABLE IF NOT EXISTS export_profiles_168(
 profile_id TEXT PRIMARY KEY, profile_key TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 include_raw_material INTEGER NOT NULL, include_analysis INTEGER NOT NULL,
 include_personal_data INTEGER NOT NULL, redaction_required INTEGER NOT NULL,
 description TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_packages_168(
 package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL,
 profile_key TEXT NOT NULL, classification TEXT NOT NULL, status TEXT NOT NULL,
 export_dir TEXT NOT NULL, manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, validated_at TEXT,
 validation_status TEXT NOT NULL DEFAULT 'pending', previous_package_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS package_validations_168(
 validation_id TEXT PRIMARY KEY, package_id TEXT NOT NULL, status TEXT NOT NULL,
 checks_json TEXT NOT NULL, validated_by TEXT NOT NULL, validated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handover_approvals_168(
 approval_id TEXT PRIMARY KEY, package_id TEXT NOT NULL, role TEXT NOT NULL,
 reviewer TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL,
 approved_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(package_id, role)
);
CREATE TABLE IF NOT EXISTS handover_receipts_168(
 receipt_id TEXT PRIMARY KEY, package_id TEXT NOT NULL, recipient_agency TEXT NOT NULL,
 recipient_reference TEXT, handed_over_by TEXT NOT NULL, handed_over_at TEXT NOT NULL,
 transfer_method TEXT NOT NULL, receipt_note TEXT NOT NULL, package_sha256 TEXT NOT NULL,
 previous_sha256 TEXT, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence168_case ON evidence_registry_168(case_id, collected_at);
CREATE INDEX IF NOT EXISTS idx_custody168_evidence ON custody_events_168(evidence_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_packages168_case ON authority_packages_168(case_id, created_at);
'''

def ensure_build168_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_168)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','168.0')")
    db.conn.commit()
