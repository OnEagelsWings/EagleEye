from __future__ import annotations
from typing import Any
SCHEMA_202=r"""
CREATE TABLE IF NOT EXISTS country_source_profiles_202(source_id TEXT PRIMARY KEY,country TEXT NOT NULL,name TEXT NOT NULL,access TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,domain TEXT NOT NULL,status TEXT NOT NULL,fixture_ok INTEGER NOT NULL,parser_ok INTEGER NOT NULL,live_ok INTEGER NOT NULL,terms_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS country_search_plans_202(plan_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,countries_json TEXT NOT NULL,person_json TEXT NOT NULL,mode TEXT NOT NULL,tabs_json TEXT NOT NULL,jobs_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS country_source_events_202(event_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
"""
def ensure_build202_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_202)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','202.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','202.0')")
 db.conn.commit()
