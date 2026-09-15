from __future__ import annotations
from typing import Any
SCHEMA_161 = r'''
CREATE TABLE IF NOT EXISTS connector_credentials_161(
 credential_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, credential_type TEXT NOT NULL,
 secret_ref TEXT NOT NULL, secret_fingerprint TEXT NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, last_validated_at TEXT,
 expires_at TEXT, metadata_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(connector_id,credential_type)
);
CREATE TABLE IF NOT EXISTS connector_acceptance_checks_161(
 check_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, environment TEXT NOT NULL,
 check_type TEXT NOT NULL, outcome TEXT NOT NULL, http_status INTEGER,
 latency_ms INTEGER, rate_limit_json TEXT NOT NULL, schema_fingerprint TEXT,
 details_json TEXT NOT NULL, checked_by TEXT NOT NULL, checked_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_acceptance_decisions_161(
 decision_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, environment TEXT NOT NULL,
 decision TEXT NOT NULL, reason TEXT NOT NULL, evidence_json TEXT NOT NULL,
 approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, expires_at TEXT,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_readiness_snapshots_161(
 snapshot_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, environment TEXT NOT NULL,
 readiness TEXT NOT NULL, score REAL NOT NULL, requirements_json TEXT NOT NULL,
 findings_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_runtime_policies_161(
 connector_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, source_url TEXT NOT NULL,
 reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
'''
def ensure_build161_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_161)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','161.0')")
    db.conn.commit()
