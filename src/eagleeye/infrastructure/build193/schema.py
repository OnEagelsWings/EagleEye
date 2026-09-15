from __future__ import annotations
from typing import Any
SCHEMA_193 = r'''
CREATE TABLE IF NOT EXISTS ai_source_profiles_193(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,country TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,status TEXT NOT NULL,query_template TEXT NOT NULL,blockers_json TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_investigation_plans_193(plan_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,subject_json TEXT NOT NULL,countries_json TEXT NOT NULL,intents_json TEXT NOT NULL,lawful_basis TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_source_tasks_193(task_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,sequence_no INTEGER NOT NULL,source_id TEXT NOT NULL,intent TEXT NOT NULL,query_text TEXT NOT NULL,execution_mode TEXT NOT NULL,readiness TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_source_results_193(result_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,task_id TEXT NOT NULL,source_id TEXT NOT NULL,source_ref TEXT NOT NULL,claims_json TEXT NOT NULL,entities_json TEXT NOT NULL,observed_at TEXT NOT NULL,provenance_json TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_syntheses_193(synthesis_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,question TEXT NOT NULL,findings_json TEXT NOT NULL,gaps_json TEXT NOT NULL,contradictions_json TEXT NOT NULL,next_actions_json TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_source_events_193(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,target_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''
def ensure_build193_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_193)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','193.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','193.0')")
    db.conn.commit()
