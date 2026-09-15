from __future__ import annotations
from typing import Any

SCHEMA_188 = r'''
CREATE TABLE IF NOT EXISTS records_source_contracts_188(
 source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_family TEXT NOT NULL,authority TEXT NOT NULL,
 endpoint TEXT NOT NULL,access_mode TEXT NOT NULL,auth_type TEXT NOT NULL,query_template TEXT NOT NULL,
 parser_version TEXT NOT NULL,required_fields_json TEXT NOT NULL,activation_wave INTEGER NOT NULL,
 status TEXT NOT NULL,production_active INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records_source_fixtures_188(
 fixture_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,fixture_json TEXT NOT NULL,parser_ok INTEGER NOT NULL,
 normalized_count INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records_source_probes_188(
 probe_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,http_status INTEGER,content_type TEXT,latency_ms INTEGER,
 parser_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,records_received INTEGER NOT NULL,
 observed_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records_source_activations_188(
 activation_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,from_status TEXT NOT NULL,to_status TEXT NOT NULL,
 approved_by TEXT NOT NULL,blockers_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records_normalized_candidates_188(
 candidate_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_record_id TEXT NOT NULL,
 entity_type TEXT NOT NULL,names_json TEXT NOT NULL,identifiers_json TEXT NOT NULL,dates_json TEXT NOT NULL,
 places_json TEXT NOT NULL,relationships_json TEXT NOT NULL,source_ref TEXT NOT NULL,observed_at TEXT NOT NULL,
 review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records_operations_events_188(
 event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,source_id TEXT NOT NULL,payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL
);
'''

def ensure_build188_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_188)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','188.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','188.0')")
    db.conn.commit()
