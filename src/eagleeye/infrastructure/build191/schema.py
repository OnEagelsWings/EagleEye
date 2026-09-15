from __future__ import annotations
from typing import Any
SCHEMA_191=r'''
CREATE TABLE IF NOT EXISTS browser_bridge_captures_191(bridge_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,capture_id TEXT NOT NULL,page_url TEXT NOT NULL,title TEXT NOT NULL,dom_sha256 TEXT NOT NULL,screenshot_sha256 TEXT NOT NULL,resources_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS warc_exports_191(warc_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,capture_id TEXT NOT NULL,warc_path TEXT NOT NULL,record_count INTEGER NOT NULL,warc_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,review_required INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_identities_191(identity_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,display_name TEXT NOT NULL,identity_type TEXT NOT NULL,attributes_json TEXT NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_identity_facts_191(fact_id TEXT PRIMARY KEY,identity_id TEXT NOT NULL,fact_type TEXT NOT NULL,fact_value TEXT NOT NULL,valid_from TEXT NOT NULL,valid_to TEXT NOT NULL,observed_at TEXT NOT NULL,source_refs_json TEXT NOT NULL,confidence REAL NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_identity_links_191(link_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,left_identity_id TEXT NOT NULL,right_identity_id TEXT NOT NULL,link_type TEXT NOT NULL,valid_from TEXT NOT NULL,valid_to TEXT NOT NULL,evidence_json TEXT NOT NULL,score REAL NOT NULL,status TEXT NOT NULL,limitations_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_identity_events_191(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,target_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''
def ensure_build191_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_191); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','191.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','191.0')"); db.conn.commit()
