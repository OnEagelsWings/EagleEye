from __future__ import annotations
from typing import Any
SCHEMA_190=r'''
CREATE TABLE IF NOT EXISTS capture_source_profiles_190(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_family TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,status TEXT NOT NULL,opsec_json TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_captures_190(capture_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_url TEXT NOT NULL,final_url TEXT NOT NULL,captured_at TEXT NOT NULL,http_status INTEGER,content_type TEXT,headers_json TEXT NOT NULL,text_content TEXT NOT NULL,html_content TEXT NOT NULL,screenshot_ref TEXT NOT NULL,media_refs_json TEXT NOT NULL,request_meta_json TEXT NOT NULL,response_sha256 TEXT NOT NULL,content_sha256 TEXT NOT NULL,previous_capture_id TEXT NOT NULL,review_status TEXT NOT NULL,opsec_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_diffs_190(diff_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,older_capture_id TEXT NOT NULL,newer_capture_id TEXT NOT NULL,change_type TEXT NOT NULL,added_json TEXT NOT NULL,removed_json TEXT NOT NULL,similarity REAL NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS replay_packages_190(replay_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,capture_id TEXT NOT NULL,manifest_json TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,package_sha256 TEXT NOT NULL,review_required INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS ai_capture_assessments_190(assessment_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,capture_id TEXT NOT NULL,question TEXT NOT NULL,findings_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,confidence REAL NOT NULL,status TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS capture_events_190(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,target_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''
def ensure_build190_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_190); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','190.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','190.0')"); db.conn.commit()
