from __future__ import annotations
from typing import Any

SCHEMA_18510 = r"""
CREATE TABLE IF NOT EXISTS redteam_source_profiles_18510(
 source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,
 purpose_json TEXT NOT NULL,status TEXT NOT NULL,production_active INTEGER NOT NULL,
 created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS redteam_campaigns_18510(
 campaign_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,scopes_json TEXT NOT NULL,
 status TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,finished_at TEXT,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS redteam_tests_18510(
 test_id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL,test_type TEXT NOT NULL,target TEXT NOT NULL,
 input_json TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT NOT NULL,severity TEXT NOT NULL,
 created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS redteam_findings_18510(
 finding_id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL,category TEXT NOT NULL,finding_code TEXT NOT NULL,
 severity TEXT NOT NULL,status TEXT NOT NULL,evidence_json TEXT NOT NULL,created_at TEXT NOT NULL,
 reviewer TEXT NOT NULL,review_note TEXT NOT NULL,reviewed_at TEXT,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS redteam_events_18510(
 event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,object_ref TEXT NOT NULL,payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
"""

def ensure_build18510_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_18510)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.10')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.10')")
    db.conn.commit()
