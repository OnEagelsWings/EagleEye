from __future__ import annotations
from typing import Any
SCHEMA_200=r'''
CREATE TABLE IF NOT EXISTS platform_source_cohort_200(source_id TEXT PRIMARY KEY,cohort TEXT NOT NULL,required INTEGER NOT NULL,fixture_ok INTEGER NOT NULL,parser_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_ok INTEGER NOT NULL,active INTEGER NOT NULL,last_error TEXT NOT NULL,checked_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_index_chunks_200(chunk_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,document_id TEXT NOT NULL,source_ref TEXT NOT NULL,section_ref TEXT NOT NULL,text_content TEXT NOT NULL,token_estimate INTEGER NOT NULL,embedding_ref TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_chat_sessions_200(session_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,created_by TEXT NOT NULL,status TEXT NOT NULL,policy_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_chat_messages_200(message_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,citations_json TEXT NOT NULL,context_json TEXT NOT NULL,actions_json TEXT NOT NULL,review_required INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reference_cases_200(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,scenario TEXT NOT NULL,user_level TEXT NOT NULL,checks_json TEXT NOT NULL,metrics_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quality_benchmarks_200(benchmark_id TEXT PRIMARY KEY,name TEXT NOT NULL,metrics_json TEXT NOT NULL,thresholds_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS release_gates_200(gate_id TEXT PRIMARY KEY,version TEXT NOT NULL,checks_json TEXT NOT NULL,blockers_json TEXT NOT NULL,status TEXT NOT NULL,human_approval_required INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS platform_events_200(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build200_schema(db:Any)->None:
    db.conn.executescript(SCHEMA_200)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','200.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','200.0')")
    db.conn.commit()
