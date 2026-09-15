from __future__ import annotations
from typing import Any
SCHEMA_1857=r"""
CREATE TABLE IF NOT EXISTS production_source_profiles_1857(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,mode TEXT NOT NULL,authority TEXT NOT NULL,endpoint TEXT NOT NULL,auth TEXT NOT NULL,rate_limit_per_minute INTEGER NOT NULL,intents_json TEXT NOT NULL,status TEXT NOT NULL,parser_status TEXT NOT NULL,production_active INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_source_fixtures_1857(fixture_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,fixture_json TEXT NOT NULL,schema_fields_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_source_probes_1857(probe_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,http_status INTEGER NOT NULL,content_type TEXT NOT NULL,latency_ms INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,parser_ok INTEGER NOT NULL,observed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS normalized_source_records_1857(record_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,source_ref TEXT NOT NULL,names_json TEXT NOT NULL,identifiers_json TEXT NOT NULL,locations_json TEXT NOT NULL,raw_json TEXT NOT NULL,observed_at TEXT NOT NULL,canonical_sha256 TEXT NOT NULL);
"""
def ensure_build1857_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_1857);db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.7')");db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.7')");db.conn.commit()
