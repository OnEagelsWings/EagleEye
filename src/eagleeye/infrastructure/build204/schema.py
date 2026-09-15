from __future__ import annotations
from typing import Any
SCHEMA_204=r'''
CREATE TABLE IF NOT EXISTS social_source_profiles_204(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,scope TEXT NOT NULL,access TEXT NOT NULL,endpoint TEXT NOT NULL,domain TEXT NOT NULL,status TEXT NOT NULL,fixture_ok INTEGER NOT NULL,parser_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_search_plans_204(plan_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,person_json TEXT NOT NULL,tabs_json TEXT NOT NULL,jobs_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_accounts_204(account_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,handle TEXT NOT NULL,profile_json TEXT NOT NULL,source_ref TEXT,observed_at TEXT NOT NULL,status TEXT NOT NULL,payload_sha256 TEXT NOT NULL,is_private INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_posts_204(post_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,account_id TEXT NOT NULL,source_id TEXT NOT NULL,text TEXT NOT NULL,published_at TEXT,source_ref TEXT,relations_json TEXT NOT NULL,status TEXT NOT NULL,payload_sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_identity_candidates_204(match_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,account_ids_json TEXT NOT NULL,masked_handles_json TEXT NOT NULL,signals_json TEXT NOT NULL,score REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_social_profiles_204(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,profile_json TEXT NOT NULL,claims_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,question TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_social_chat_turns_204(turn_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,citations_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,warnings_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_social_feedback_204(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_ref TEXT NOT NULL,verdict TEXT NOT NULL,reason TEXT NOT NULL,analyst TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build204_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_204)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','204.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','204.0')")
 db.conn.commit()
