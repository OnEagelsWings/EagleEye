from __future__ import annotations
from typing import Any
SCHEMA_1855 = r'''
CREATE TABLE IF NOT EXISTS genealogy_source_profiles_1855(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS genealogy_searches_1855(search_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,query TEXT NOT NULL,source_ids_json TEXT NOT NULL,lawful_basis TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS genealogy_candidates_1855(candidate_id TEXT PRIMARY KEY,search_id TEXT NOT NULL,source_id TEXT NOT NULL,source_record_id TEXT NOT NULL,source_url TEXT NOT NULL,normalized_json TEXT NOT NULL,status TEXT NOT NULL,automatic_relationship_confirmation INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS genealogy_relationship_assessments_1855(assessment_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,subject_ref TEXT NOT NULL,related_ref TEXT NOT NULL,relationship_type TEXT NOT NULL,status TEXT NOT NULL,source_count INTEGER NOT NULL,primary_evidence_count INTEGER NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build1855_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_1855)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.5')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.5')")
    db.conn.commit()
