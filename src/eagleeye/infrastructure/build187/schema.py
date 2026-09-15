from __future__ import annotations
from typing import Any

SCHEMA_187 = r'''
CREATE TABLE IF NOT EXISTS source_operations_profiles_187(
 source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_class TEXT NOT NULL,mode TEXT NOT NULL,
 endpoint TEXT NOT NULL,status TEXT NOT NULL,production_active INTEGER NOT NULL DEFAULT 0,
 terms_status TEXT NOT NULL,credential_status TEXT NOT NULL,parser_status TEXT NOT NULL,
 rate_limit_per_minute INTEGER NOT NULL,last_success_at TEXT,last_failure_at TEXT,
 consecutive_failures INTEGER NOT NULL DEFAULT 0,average_latency_ms REAL NOT NULL DEFAULT 0,
 quality_score REAL NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_health_events_187(
 event_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,health_status TEXT NOT NULL,http_status INTEGER,
 latency_ms INTEGER,error_code TEXT,error_message TEXT,records_received INTEGER NOT NULL DEFAULT 0,
 observed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_terms_reviews_187(
 review_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,decision TEXT NOT NULL,reviewer TEXT NOT NULL,
 evidence_ref TEXT NOT NULL,valid_until TEXT,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_credentials_state_187(
 source_id TEXT PRIMARY KEY,credential_type TEXT NOT NULL,status TEXT NOT NULL,secret_ref TEXT,
 checked_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_operations_events_187(
 event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,source_id TEXT NOT NULL,payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_workspace_preferences_187(
 principal TEXT PRIMARY KEY,experience_mode TEXT NOT NULL,show_technical_details INTEGER NOT NULL,
 default_source_view TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
'''

def ensure_build187_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_187)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','187.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','187.0')")
    db.conn.commit()
