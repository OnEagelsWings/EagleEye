from __future__ import annotations
from typing import Any
SCHEMA_184 = r'''
CREATE TABLE IF NOT EXISTS validation_source_profiles_184(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,docs_url TEXT NOT NULL,constraints_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_cases_184(validation_case_id TEXT PRIMARY KEY,title TEXT NOT NULL,case_type TEXT NOT NULL,ground_truth_policy TEXT NOT NULL,dataset_ref TEXT NOT NULL,status TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,guardrails_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_items_184(item_id TEXT PRIMARY KEY,validation_case_id TEXT NOT NULL,item_ref TEXT NOT NULL,label TEXT NOT NULL,expected_json TEXT NOT NULL,dimensions_json TEXT NOT NULL,ground_truth_reviewed INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_predictions_184(prediction_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,item_id TEXT NOT NULL,score REAL NOT NULL,predicted_label TEXT NOT NULL,raw_json TEXT NOT NULL,system_name TEXT NOT NULL,system_version TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_runs_184(run_id TEXT PRIMARY KEY,validation_case_id TEXT NOT NULL,system_name TEXT NOT NULL,system_version TEXT NOT NULL,metrics_json TEXT NOT NULL,gate_status TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_gates_184(gate_id TEXT PRIMARY KEY,name TEXT NOT NULL,requirements_json TEXT NOT NULL,status TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_gate_results_184(result_id TEXT PRIMARY KEY,gate_id TEXT NOT NULL,run_id TEXT NOT NULL,status TEXT NOT NULL,checks_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validation_events_184(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL,previous_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_validation_items_184 ON validation_items_184(validation_case_id,label);
CREATE INDEX IF NOT EXISTS idx_validation_runs_184 ON validation_runs_184(validation_case_id,gate_status);
'''
def ensure_build184_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_184)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','184.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','184.0')")
    db.conn.commit()
