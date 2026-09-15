from __future__ import annotations
from typing import Any
SCHEMA_205=r'''
CREATE TABLE IF NOT EXISTS news_source_profiles_205(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,country TEXT NOT NULL,language TEXT NOT NULL,access TEXT NOT NULL,endpoint TEXT NOT NULL,source_class TEXT NOT NULL,status TEXT NOT NULL,fixture_ok INTEGER NOT NULL,parser_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_search_plans_205(plan_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,countries_json TEXT NOT NULL,languages_json TEXT NOT NULL,tabs_json TEXT NOT NULL,jobs_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_articles_205(article_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,published_at TEXT,language TEXT,country TEXT,article_type TEXT NOT NULL,text TEXT NOT NULL,claims_json TEXT NOT NULL,entities_json TEXT NOT NULL,wire_fingerprint TEXT NOT NULL,source_ref TEXT NOT NULL,status TEXT NOT NULL,prompt_injection INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_event_clusters_205(cluster_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,label TEXT NOT NULL,article_ids_json TEXT NOT NULL,claims_json TEXT NOT NULL,countries_json TEXT NOT NULL,languages_json TEXT NOT NULL,independent_lines INTEGER NOT NULL,wire_groups INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_social_links_205(link_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,cluster_id TEXT NOT NULL,social_post_ids_json TEXT NOT NULL,signals_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_news_profiles_205(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,profile_json TEXT NOT NULL,hypotheses_json TEXT NOT NULL,conflicts_json TEXT NOT NULL,citations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_news_chat_turns_205(turn_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,snapshot_id TEXT NOT NULL,question TEXT NOT NULL,answer TEXT NOT NULL,citations_json TEXT NOT NULL,warnings_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_news_feedback_205(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_ref TEXT NOT NULL,verdict TEXT NOT NULL,reason TEXT NOT NULL,analyst TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build205_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_205)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','205.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','205.0')")
 db.conn.commit()
