from __future__ import annotations
from typing import Any
SCHEMA_197=r'''
CREATE TABLE IF NOT EXISTS workspace_source_profiles_197(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,region TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,status TEXT NOT NULL,terms_status TEXT NOT NULL,parser_status TEXT NOT NULL,live_status TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS adaptive_workspace_profiles_197(profile_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,mode TEXT NOT NULL,experience_level TEXT NOT NULL,preferences_json TEXT NOT NULL,opsec_policy_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_sessions_197(session_id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,case_id TEXT NOT NULL,current_stage TEXT NOT NULL,context_json TEXT NOT NULL,next_actions_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_guidance_197(guidance_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,module TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,message TEXT NOT NULL,action_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_ai_assessments_197(assessment_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,question TEXT NOT NULL,assessment_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_events_197(event_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build197_schema(db: Any)->None:
    db.conn.executescript(SCHEMA_197)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','197.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','197.0')")
    db.conn.commit()
