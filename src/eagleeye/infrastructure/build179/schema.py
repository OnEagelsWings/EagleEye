from __future__ import annotations
from typing import Any
SCHEMA_179=r"""
CREATE TABLE IF NOT EXISTS pattern_source_profiles_179(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,jurisdiction TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,capabilities_json TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pattern_rules_179(rule_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,rule_type TEXT NOT NULL,condition_json TEXT NOT NULL,severity TEXT NOT NULL,window_hours INTEGER NOT NULL,minimum_sources INTEGER NOT NULL,status TEXT NOT NULL,policy_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pattern_runs_179(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL,status TEXT NOT NULL,summary_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pattern_findings_179(finding_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,rule_id TEXT NOT NULL,case_id TEXT NOT NULL,finding_type TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,explanation_json TEXT NOT NULL,evidence_json TEXT NOT NULL,status TEXT NOT NULL,reviewed_by TEXT,reviewed_at TEXT,review_note TEXT,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pattern_events_179(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,rule_id TEXT,event_type TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,previous_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_pattern_rules_179 ON pattern_rules_179(case_id,status,rule_type);
CREATE INDEX IF NOT EXISTS idx_pattern_findings_179 ON pattern_findings_179(case_id,severity,status,created_at);
"""
def ensure_build179_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_179); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','179.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','179.0')"); db.conn.commit()
