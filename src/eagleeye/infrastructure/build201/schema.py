from __future__ import annotations
from typing import Any
SCHEMA_201=r'''
CREATE TABLE IF NOT EXISTS source_runtime_profiles_201(source_id TEXT PRIMARY KEY,mode TEXT NOT NULL,priority INTEGER NOT NULL,max_parallel INTEGER NOT NULL,min_interval_seconds INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,max_retries INTEGER NOT NULL,backoff_base_seconds INTEGER NOT NULL,circuit_threshold INTEGER NOT NULL,circuit_cooldown_seconds INTEGER NOT NULL,schema_fingerprint TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_jobs_201(job_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,query_json TEXT NOT NULL,mode TEXT NOT NULL,priority INTEGER NOT NULL,status TEXT NOT NULL,attempt INTEGER NOT NULL,next_run_at TEXT NOT NULL,checkpoint_json TEXT NOT NULL,result_count INTEGER NOT NULL,error_code TEXT NOT NULL,error_message TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_runs_201(run_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,source_id TEXT NOT NULL,http_status INTEGER NOT NULL,latency_ms INTEGER NOT NULL,records_received INTEGER NOT NULL,parser_ok INTEGER NOT NULL,schema_fingerprint TEXT NOT NULL,schema_drift INTEGER NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_circuits_201(source_id TEXT PRIMARY KEY,state TEXT NOT NULL,consecutive_failures INTEGER NOT NULL,opened_at TEXT NOT NULL,retry_after TEXT NOT NULL,last_error TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_candidates_201(candidate_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,case_id TEXT NOT NULL,source_id TEXT NOT NULL,source_record_id TEXT NOT NULL,entity_type TEXT NOT NULL,normalized_json TEXT NOT NULL,evidence_json TEXT NOT NULL,confidence REAL NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_events_201(event_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
'''
def ensure_build201_schema(db:Any)->None:
    db.conn.executescript(SCHEMA_201)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','201.1')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','201.1')")
    db.conn.commit()
