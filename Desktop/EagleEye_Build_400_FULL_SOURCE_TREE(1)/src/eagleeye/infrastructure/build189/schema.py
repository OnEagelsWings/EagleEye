from __future__ import annotations
from typing import Any
SCHEMA_189=r"""
CREATE TABLE IF NOT EXISTS global_source_profiles_189(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,country_code TEXT NOT NULL,source_family TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,query_template TEXT NOT NULL,auth_type TEXT NOT NULL,rate_per_min INTEGER NOT NULL,activation_wave INTEGER NOT NULL,required_fields_json TEXT NOT NULL,status TEXT NOT NULL,fixture_validated INTEGER NOT NULL DEFAULT 0,live_validated INTEGER NOT NULL DEFAULT 0,production_active INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS global_source_fixtures_189(fixture_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,fixture_json TEXT NOT NULL,parser_ok INTEGER NOT NULL,normalized_count INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS global_source_probes_189(probe_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,http_status INTEGER,content_type TEXT,latency_ms INTEGER,parser_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,records_received INTEGER NOT NULL,observed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS global_normalized_candidates_189(candidate_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_record_id TEXT NOT NULL,entity_type TEXT NOT NULL,names_json TEXT NOT NULL,identifiers_json TEXT NOT NULL,relations_json TEXT NOT NULL,source_ref TEXT NOT NULL,observed_at TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS global_source_events_189(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,source_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
"""
def ensure_build189_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_189); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','189.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','189.0')"); db.conn.commit()
