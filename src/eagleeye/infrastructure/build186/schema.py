from __future__ import annotations
from typing import Any
SCHEMA_186=r'''
CREATE TABLE IF NOT EXISTS release_source_profiles_186(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,status TEXT NOT NULL,production_active INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_release_acceptance_186(acceptance_id TEXT PRIMARY KEY,status TEXT NOT NULL,gate_results_json TEXT NOT NULL,blockers_json TEXT NOT NULL,evidence_json TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,reviewed_at TEXT,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_release_reviews_186(review_id TEXT PRIMARY KEY,acceptance_id TEXT NOT NULL,reviewer TEXT NOT NULL,decision TEXT NOT NULL,note TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_release_events_186(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,object_ref TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''
def ensure_build186_schema(db:Any)->None:
    db.conn.executescript(SCHEMA_186)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','186.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','186.0')")
    db.conn.commit()
