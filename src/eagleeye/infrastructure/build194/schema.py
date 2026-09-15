from __future__ import annotations
from typing import Any
SCHEMA_194=r'''
CREATE TABLE IF NOT EXISTS media_source_profiles_194(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,country TEXT NOT NULL,language TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,auth_type TEXT NOT NULL,status TEXT NOT NULL,candidate_only INTEGER NOT NULL,updated_at TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS multimodal_verifications_194(verification_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_ref TEXT NOT NULL,media_type TEXT NOT NULL,question TEXT NOT NULL,source_refs_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS verification_signals_194(signal_id TEXT PRIMARY KEY,verification_id TEXT NOT NULL,signal_type TEXT NOT NULL,direction TEXT NOT NULL,score REAL NOT NULL,method TEXT NOT NULL,details_json TEXT NOT NULL,source_ref TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS verification_evaluations_194(evaluation_id TEXT PRIMARY KEY,verification_id TEXT NOT NULL,status TEXT NOT NULL,support_score REAL NOT NULL,contradiction_score REAL NOT NULL,signal_count INTEGER NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_analyses_194(analysis_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,countries_json TEXT NOT NULL,languages_json TEXT NOT NULL,date_from TEXT NOT NULL,date_to TEXT NOT NULL,sources_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_articles_194(article_id TEXT PRIMARY KEY,analysis_id TEXT NOT NULL,source_id TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,published_at TEXT NOT NULL,language TEXT NOT NULL,country TEXT NOT NULL,article_type TEXT NOT NULL,claims_json TEXT NOT NULL,summary TEXT NOT NULL,provenance_json TEXT NOT NULL,prompt_injection_candidate INTEGER NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news_syntheses_194(synthesis_id TEXT PRIMARY KEY,analysis_id TEXT NOT NULL,article_count INTEGER NOT NULL,source_count INTEGER NOT NULL,countries_json TEXT NOT NULL,perspectives_json TEXT NOT NULL,findings_json TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build194_schema(db: Any)->None:
    db.conn.executescript(SCHEMA_194)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','194.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','194.0')")
    db.conn.commit()
