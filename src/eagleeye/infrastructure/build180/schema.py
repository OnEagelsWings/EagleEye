from __future__ import annotations
from typing import Any
SCHEMA_180=r"""
CREATE TABLE IF NOT EXISTS authenticity_source_profiles_180(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_policies_180(policy_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,scope_json TEXT NOT NULL,interval_minutes INTEGER NOT NULL,alert_threshold REAL NOT NULL,status TEXT NOT NULL,approved_by TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_jobs_180(job_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,evidence_id TEXT,media_id TEXT,document_id TEXT,policy_id TEXT,status TEXT NOT NULL,priority TEXT NOT NULL,queued_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,result_json TEXT,error_text TEXT,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_checks_180(check_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,check_type TEXT NOT NULL,status TEXT NOT NULL,score REAL,details_json TEXT NOT NULL,tool_name TEXT NOT NULL,tool_version TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_findings_180(finding_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,case_id TEXT NOT NULL,finding_type TEXT NOT NULL,severity TEXT NOT NULL,confidence REAL NOT NULL,summary TEXT NOT NULL,evidence_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_alerts_180(alert_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,job_id TEXT NOT NULL,finding_id TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,acknowledged_by TEXT,acknowledged_at TEXT,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_events_180(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,previous_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_auth_jobs_180 ON authenticity_jobs_180(status,priority,queued_at);
CREATE INDEX IF NOT EXISTS idx_auth_alerts_180 ON authenticity_alerts_180(case_id,status,severity,created_at);
"""
def ensure_build180_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_180); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','180.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','180.0')"); db.conn.commit()
