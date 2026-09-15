from __future__ import annotations
from typing import Any
SCHEMA_206=r'''
CREATE TABLE IF NOT EXISTS retrieval_source_profiles_206(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,parser_version TEXT NOT NULL,fixture_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_documents_206(document_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_ref TEXT NOT NULL,title TEXT NOT NULL,content_type TEXT NOT NULL,language TEXT,content_sha256 TEXT NOT NULL,prompt_injection INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS case_chunks_206(chunk_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,case_id TEXT NOT NULL,section_ref TEXT NOT NULL,page_number INTEGER,chunk_type TEXT NOT NULL,text TEXT NOT NULL,token_count INTEGER NOT NULL,content_sha256 TEXT NOT NULL,source_ref TEXT NOT NULL,access_label TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_case_chunks_206_case ON case_chunks_206(case_id);
CREATE TABLE IF NOT EXISTS case_tables_206(table_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,case_id TEXT NOT NULL,page_number INTEGER,caption TEXT,cells_json TEXT NOT NULL,source_ref TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_network_snapshots_206(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,account_ids_json TEXT NOT NULL,node_count INTEGER NOT NULL,edge_count INTEGER NOT NULL,activity_json TEXT NOT NULL,topics_json TEXT NOT NULL,citations_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retrieval_queries_206(query_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,filters_json TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_case_contexts_206(context_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,profile_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,conflicts_json TEXT NOT NULL,citations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_case_chat_turns_206(turn_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,context_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,citations_json TEXT NOT NULL,warnings_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_retrieval_feedback_206(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_ref TEXT NOT NULL,verdict TEXT NOT NULL,reason TEXT NOT NULL,analyst TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build206_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_206)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','206.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','206.0')")
 db.conn.commit()
