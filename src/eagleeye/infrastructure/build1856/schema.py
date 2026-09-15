from __future__ import annotations
from typing import Any
SCHEMA_1856=r'''
CREATE TABLE IF NOT EXISTS guided_source_profiles_1856(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,authority TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,search_url TEXT NOT NULL,intents_json TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS guided_research_routes_1856(route_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,intents_json TEXT NOT NULL,query TEXT NOT NULL,steps_json TEXT NOT NULL,lawful_basis TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build1856_schema(db: Any)->None:
    db.conn.executescript(SCHEMA_1856)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.6')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.6')")
    db.conn.commit()
