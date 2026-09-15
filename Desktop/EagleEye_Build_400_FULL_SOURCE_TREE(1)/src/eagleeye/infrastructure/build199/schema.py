from __future__ import annotations
from typing import Any
SCHEMA_199=r'''
CREATE TABLE IF NOT EXISTS productive_source_profiles_199(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,region TEXT NOT NULL,endpoint TEXT NOT NULL,access_mode TEXT NOT NULL,status TEXT NOT NULL,terms_status TEXT NOT NULL,fixture_status TEXT NOT NULL,parser_status TEXT NOT NULL,live_status TEXT NOT NULL,activation_status TEXT NOT NULL,config_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_runs_199(run_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,case_id TEXT NOT NULL,query_text TEXT NOT NULL,status TEXT NOT NULL,record_count INTEGER NOT NULL,response_meta_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS extracted_documents_199(document_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_ref TEXT NOT NULL,content_type TEXT NOT NULL,title TEXT NOT NULL,language TEXT NOT NULL,text_content TEXT NOT NULL,claims_json TEXT NOT NULL,entities_json TEXT NOT NULL,prompt_injection_candidate INTEGER NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_hypotheses_199(hypothesis_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,statement TEXT NOT NULL,rationale TEXT NOT NULL,support_refs_json TEXT NOT NULL,contradiction_refs_json TEXT NOT NULL,test_plan_json TEXT NOT NULL,status TEXT NOT NULL,confidence REAL NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_chat_sessions_199(session_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,created_by TEXT NOT NULL,status TEXT NOT NULL,policy_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_chat_messages_199(message_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,citations_json TEXT NOT NULL,actions_json TEXT NOT NULL,review_required INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pilot_runs_199(pilot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,scenario TEXT NOT NULL,user_level TEXT NOT NULL,metrics_json TEXT NOT NULL,findings_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS build199_events(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build199_schema(db:Any)->None:
    db.conn.executescript(SCHEMA_199)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','199.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','199.0')")
    db.conn.commit()
