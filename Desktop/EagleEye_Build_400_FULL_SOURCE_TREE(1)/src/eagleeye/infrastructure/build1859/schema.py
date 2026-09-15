from __future__ import annotations
from typing import Any

SCHEMA_1859 = r'''
CREATE TABLE IF NOT EXISTS resilience_source_profiles_1859(
 source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,
 purpose_json TEXT NOT NULL,status TEXT NOT NULL,production_active INTEGER NOT NULL,
 created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS backup_sets_1859(
 backup_id TEXT PRIMARY KEY,backup_type TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,
 created_by TEXT NOT NULL,source_schema TEXT NOT NULL,target_build TEXT NOT NULL,backup_path TEXT NOT NULL,
 database_sha256 TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,file_count INTEGER NOT NULL,
 encrypted INTEGER NOT NULL,notes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS backup_files_1859(
 backup_id TEXT NOT NULL,relative_path TEXT NOT NULL,size_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
 classification TEXT NOT NULL,PRIMARY KEY(backup_id,relative_path));
CREATE TABLE IF NOT EXISTS migration_runs_1859(
 migration_id TEXT PRIMARY KEY,source_schema TEXT NOT NULL,target_schema TEXT NOT NULL,status TEXT NOT NULL,
 backup_id TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,error_text TEXT NOT NULL,
 preflight_json TEXT NOT NULL,postflight_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS restore_runs_1859(
 restore_id TEXT PRIMARY KEY,backup_id TEXT NOT NULL,status TEXT NOT NULL,requested_by TEXT NOT NULL,
 started_at TEXT NOT NULL,finished_at TEXT,staging_path TEXT NOT NULL,target_path TEXT NOT NULL,
 verification_json TEXT NOT NULL,error_text TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_events_1859(
 event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,object_ref TEXT NOT NULL,payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''

def ensure_build1859_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_1859)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.9')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.9')")
    db.conn.commit()
