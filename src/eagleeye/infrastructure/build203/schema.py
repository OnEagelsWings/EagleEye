from __future__ import annotations
from typing import Any
SCHEMA_203=r'''
CREATE TABLE IF NOT EXISTS country_source_profiles_203(source_id TEXT PRIMARY KEY,region TEXT NOT NULL,country TEXT NOT NULL,name TEXT NOT NULL,access TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,domain TEXT NOT NULL,languages_json TEXT NOT NULL,status TEXT NOT NULL,fixture_ok INTEGER NOT NULL,parser_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS country_search_plans_203(plan_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,regions_json TEXT NOT NULL,person_json TEXT NOT NULL,mode TEXT NOT NULL,tabs_json TEXT NOT NULL,jobs_json TEXT NOT NULL,ai_tasks_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_profile_snapshots_203(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,profile_json TEXT NOT NULL,claims_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,conflicts_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_copilot_feedback_203(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_type TEXT NOT NULL,item_ref TEXT NOT NULL,verdict TEXT NOT NULL,reason TEXT NOT NULL,analyst TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_chat_turns_203(turn_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,citations_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,warnings_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS country_source_events_203(event_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build203_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_203)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','203.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','203.0')")
 db.conn.commit()
