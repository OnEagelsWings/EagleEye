from __future__ import annotations
from typing import Any
SCHEMA_173='''
CREATE TABLE IF NOT EXISTS social_depth_profiles_173(source_id TEXT PRIMARY KEY,operations_json TEXT NOT NULL,thread_model TEXT NOT NULL,history_model TEXT NOT NULL,access_notes TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_threads_173(thread_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,root_record_id TEXT NOT NULL,nodes_json TEXT NOT NULL,edges_json TEXT NOT NULL,depth INTEGER NOT NULL,node_count INTEGER NOT NULL,observed_at TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_account_history_173(history_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,account_ref TEXT NOT NULL,event_type TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,observed_at TEXT NOT NULL,source_refs_json TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_content_events_173(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,record_ref TEXT NOT NULL,event_type TEXT NOT NULL,event_time TEXT,details_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS extended_source_profiles_173(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,jurisdiction TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,terms_url TEXT NOT NULL,status TEXT NOT NULL,entity_kinds_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_depth_events_173(event_id TEXT PRIMARY KEY,case_id TEXT,event_type TEXT NOT NULL,entity_ref TEXT,details_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build173_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_173)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','173.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','173.0')")
 db.conn.commit()
