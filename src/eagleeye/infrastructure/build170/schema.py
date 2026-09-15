from __future__ import annotations
from typing import Any
SCHEMA_170 = r"""
CREATE TABLE IF NOT EXISTS production_candidate_audits_170(audit_id TEXT PRIMARY KEY,status TEXT NOT NULL,score REAL NOT NULL,checks_json TEXT NOT NULL,blockers_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exception_classifications_170(item_id TEXT PRIMARY KEY,file_path TEXT NOT NULL,line_no INTEGER NOT NULL,handler_kind TEXT NOT NULL,classification TEXT NOT NULL,rationale TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_policy_snapshots_170(snapshot_id TEXT PRIMARY KEY,policy_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_release_decisions_170(decision_id TEXT PRIMARY KEY,audit_id TEXT NOT NULL,status TEXT NOT NULL,approvals_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shutdown_checks_170(check_id TEXT PRIMARY KEY,status TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
"""
def ensure_build170_schema(db: Any)->None:
 db.conn.executescript(SCHEMA_170)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','170.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','170.0')")
 db.conn.commit()
