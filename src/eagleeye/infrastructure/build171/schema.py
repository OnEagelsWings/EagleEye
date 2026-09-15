from __future__ import annotations
from typing import Any
SCHEMA_171 = r'''
CREATE TABLE IF NOT EXISTS connector_sdk_specs_171(spec_id TEXT PRIMARY KEY,connector_id TEXT NOT NULL UNIQUE,version TEXT NOT NULL,title TEXT NOT NULL,base_url TEXT NOT NULL,allowed_hosts_json TEXT NOT NULL,auth_json TEXT NOT NULL,pagination_json TEXT NOT NULL,input_schema_json TEXT NOT NULL,output_schema_json TEXT NOT NULL,normalization_json TEXT NOT NULL,provenance_json TEXT NOT NULL,limits_json TEXT NOT NULL,lifecycle_status TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connector_fixtures_171(fixture_id TEXT PRIMARY KEY,connector_id TEXT NOT NULL,fixture_kind TEXT NOT NULL,payload_json TEXT NOT NULL,expected_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connector_contract_runs_171(run_id TEXT PRIMARY KEY,connector_id TEXT NOT NULL,status TEXT NOT NULL,checks_json TEXT NOT NULL,failures_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connector_lifecycle_events_171(event_id TEXT PRIMARY KEY,connector_id TEXT NOT NULL,from_status TEXT NOT NULL,to_status TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connector_sdk_snapshots_171(snapshot_id TEXT PRIMARY KEY,manifest_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build171_schema(db: Any)->None:
 db.conn.executescript(SCHEMA_171)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','171.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','171.0')")
 db.conn.commit()
