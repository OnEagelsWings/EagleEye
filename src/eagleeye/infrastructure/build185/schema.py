from __future__ import annotations
from typing import Any
SCHEMA_185 = r'''
CREATE TABLE IF NOT EXISTS redteam_source_profiles_185(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS redteam_runs_185(run_id TEXT PRIMARY KEY,run_type TEXT NOT NULL,status TEXT NOT NULL,files_scanned INTEGER NOT NULL,lines_scanned INTEGER NOT NULL,severity_counts_json TEXT NOT NULL,findings_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workflow_snapshots_185(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,progress_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build185_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_185)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.0')")
    db.conn.commit()
