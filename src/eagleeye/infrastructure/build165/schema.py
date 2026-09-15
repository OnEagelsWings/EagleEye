from __future__ import annotations
from typing import Any

SCHEMA_165 = r'''
CREATE TABLE IF NOT EXISTS er_field_datasets_165(
 dataset_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 provenance_json TEXT NOT NULL, governance_json TEXT NOT NULL, status TEXT NOT NULL,
 record_count INTEGER NOT NULL, pair_count INTEGER NOT NULL, dataset_sha256 TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS er_field_records_165(
 record_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, entity_ref TEXT NOT NULL,
 source_type TEXT NOT NULL, source_ref TEXT, language TEXT, script TEXT,
 record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS er_field_pairs_165(
 pair_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, left_record_id TEXT NOT NULL,
 right_record_id TEXT NOT NULL, expected_match INTEGER NOT NULL,
 difficulty TEXT NOT NULL, scenario_tags_json TEXT NOT NULL, adjudication_json TEXT NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(dataset_id,left_record_id,right_record_id)
);
CREATE TABLE IF NOT EXISTS er_field_runs_165(
 run_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, engine_name TEXT NOT NULL,
 engine_version TEXT NOT NULL, threshold REAL NOT NULL, metrics_json TEXT NOT NULL,
 slice_metrics_json TEXT NOT NULL, error_analysis_json TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_er_assessments_165(
 assessment_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT,
 assessment_type TEXT NOT NULL, input_sha256 TEXT NOT NULL, output_json TEXT NOT NULL,
 opsec_json TEXT NOT NULL, model_mode TEXT NOT NULL, review_required INTEGER NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS er_release_gates_165(
 gate_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, decision TEXT NOT NULL,
 thresholds_json TEXT NOT NULL, findings_json TEXT NOT NULL, approved_by TEXT,
 approved_at TEXT, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
'''

def ensure_build165_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_165)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','165.0')")
    db.conn.commit()
