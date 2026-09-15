from __future__ import annotations
from typing import Any
SCHEMA_195=r'''
CREATE TABLE IF NOT EXISTS monitoring_source_profiles_195(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,region TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,auth_type TEXT NOT NULL,status TEXT NOT NULL,polling_floor_minutes INTEGER NOT NULL,terms_status TEXT NOT NULL,parser_status TEXT NOT NULL,live_status TEXT NOT NULL,updated_at TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_monitors_195(monitor_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,name TEXT NOT NULL,question TEXT NOT NULL,subjects_json TEXT NOT NULL,source_ids_json TEXT NOT NULL,interval_minutes INTEGER NOT NULL,status TEXT NOT NULL,last_run_at TEXT NOT NULL,next_run_at TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS monitor_observations_195(observation_id TEXT PRIMARY KEY,monitor_id TEXT NOT NULL,source_id TEXT NOT NULL,source_ref TEXT NOT NULL,observed_at TEXT NOT NULL,published_at TEXT NOT NULL,content_type TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL,claims_json TEXT NOT NULL,entities_json TEXT NOT NULL,content_sha256 TEXT NOT NULL,provenance_json TEXT NOT NULL,prompt_injection_candidate INTEGER NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_change_impacts_195(impact_id TEXT PRIMARY KEY,monitor_id TEXT NOT NULL,observation_id TEXT NOT NULL,graph_id TEXT NOT NULL,claim_id TEXT NOT NULL,impact_type TEXT NOT NULL,severity TEXT NOT NULL,reason TEXT NOT NULL,old_state_json TEXT NOT NULL,new_state_json TEXT NOT NULL,created_at TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_alerts_195(alert_id TEXT PRIMARY KEY,monitor_id TEXT NOT NULL,impact_id TEXT NOT NULL,case_id TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,explanation TEXT NOT NULL,recommended_action TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,acknowledged_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS monitoring_ai_assessments_195(assessment_id TEXT PRIMARY KEY,monitor_id TEXT NOT NULL,observation_id TEXT NOT NULL,impact_id TEXT NOT NULL,assessment_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS monitoring_events_195(event_id TEXT PRIMARY KEY,monitor_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build195_schema(db: Any)->None:
    db.conn.executescript(SCHEMA_195)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','195.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','195.0')")
    db.conn.commit()
