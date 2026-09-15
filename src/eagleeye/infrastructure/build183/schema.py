from __future__ import annotations
from typing import Any
SCHEMA_183=r'''
CREATE TABLE IF NOT EXISTS plugin_source_profiles_183(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plugins_183(plugin_id TEXT PRIMARY KEY,version TEXT NOT NULL,manifest_json TEXT NOT NULL,signature TEXT NOT NULL,capabilities_json TEXT NOT NULL,entrypoint TEXT NOT NULL,sbom_sha256 TEXT NOT NULL,status TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plugin_runs_183(run_id TEXT PRIMARY KEY,plugin_id TEXT NOT NULL,case_id TEXT NOT NULL,capability TEXT NOT NULL,input_sha256 TEXT NOT NULL,output_json TEXT NOT NULL,status TEXT NOT NULL,external_uploads INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_assessments_183(assessment_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,claim TEXT NOT NULL,evidence_json TEXT NOT NULL,model_outputs_json TEXT NOT NULL,model_consensus REAL NOT NULL,status TEXT NOT NULL,warnings_json TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plugin_events_183(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,previous_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_plugin_runs_183 ON plugin_runs_183(case_id,plugin_id,status);
CREATE INDEX IF NOT EXISTS idx_ai_assessments_183 ON ai_assessments_183(case_id,status);
'''
def ensure_build183_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_183);db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','183.0')");db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','183.0')");db.conn.commit()
