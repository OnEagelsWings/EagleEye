from __future__ import annotations
from typing import Any
SCHEMA_1858=r'''
CREATE TABLE IF NOT EXISTS calibration_source_profiles_1858(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_class TEXT NOT NULL,endpoint TEXT NOT NULL,intents_json TEXT NOT NULL,status TEXT NOT NULL,production_active INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS detector_calibrations_1858(calibration_id TEXT PRIMARY KEY,detector_name TEXT NOT NULL,detector_version TEXT NOT NULL,media_type TEXT NOT NULL,threshold REAL NOT NULL,weight REAL NOT NULL,precision_value REAL NOT NULL,recall_value REAL NOT NULL,false_positive_rate REAL NOT NULL,false_negative_rate REAL NOT NULL,expected_calibration_error REAL NOT NULL,benchmark_ref TEXT NOT NULL,sample_size INTEGER NOT NULL,status TEXT NOT NULL,approved_by TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authenticity_ensemble_runs_1858(ensemble_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_ref TEXT NOT NULL,media_type TEXT NOT NULL,accepted_json TEXT NOT NULL,weighted_score REAL NOT NULL,positive_detectors INTEGER NOT NULL,status TEXT NOT NULL,limitations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_calibration_assessments_1858(assessment_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,claim TEXT NOT NULL,status TEXT NOT NULL,independent_sources INTEGER NOT NULL,evidence_support REAL NOT NULL,evidence_contradict REAL NOT NULL,model_score REAL,limitations_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build1858_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_1858);db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','185.8')");db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','185.8')");db.conn.commit()
