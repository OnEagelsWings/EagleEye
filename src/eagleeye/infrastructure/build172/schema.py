from __future__ import annotations
from typing import Any
SCHEMA_172="""
CREATE TABLE IF NOT EXISTS european_source_profiles_172(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,jurisdiction TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,allowed_hosts_json TEXT NOT NULL,auth_json TEXT NOT NULL,pagination_json TEXT NOT NULL,docs_url TEXT NOT NULL,terms_url TEXT NOT NULL,terms_state TEXT NOT NULL,entity_kinds_json TEXT NOT NULL,sdk_enabled INTEGER NOT NULL,protocol TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS european_terms_reviews_172(review_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,decision TEXT NOT NULL,reviewer TEXT NOT NULL,evidence_ref TEXT NOT NULL,valid_until TEXT,reviewed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS european_source_health_172(health_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,status TEXT NOT NULL,http_status INTEGER,latency_ms INTEGER,schema_sha256 TEXT,error_text TEXT,checked_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS european_normalized_records_172(record_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,source_record_id TEXT NOT NULL,normalized_json TEXT NOT NULL,observed_at TEXT NOT NULL,canonical_sha256 TEXT NOT NULL,review_status TEXT NOT NULL,UNIQUE(source_id,source_record_id,canonical_sha256));
"""
def ensure_build172_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_172)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','172.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','172.0')")
 db.conn.commit()
