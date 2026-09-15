from __future__ import annotations
from typing import Any
SCHEMA_196=r'''
CREATE TABLE IF NOT EXISTS federation_source_profiles_196(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,region TEXT NOT NULL,source_class TEXT NOT NULL,access_mode TEXT NOT NULL,status TEXT NOT NULL,terms_status TEXT NOT NULL,parser_status TEXT NOT NULL,live_status TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_scopes_196(scope_id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,case_ids_json TEXT NOT NULL,policy_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cross_case_candidates_196(candidate_id TEXT PRIMARY KEY,scope_id TEXT NOT NULL,left_case_id TEXT NOT NULL,right_case_id TEXT NOT NULL,match_type TEXT NOT NULL,match_key_hash TEXT NOT NULL,display_hint TEXT NOT NULL,evidence_json TEXT NOT NULL,score REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_disclosures_196(disclosure_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,requested_by TEXT NOT NULL,approved_by TEXT NOT NULL,fields_json TEXT NOT NULL,purpose TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_ai_assessments_196(assessment_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,assessment_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS federation_events_196(event_id TEXT PRIMARY KEY,scope_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build196_schema(db: Any)->None:
    db.conn.executescript(SCHEMA_196)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','196.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','196.0')")
    db.conn.commit()
