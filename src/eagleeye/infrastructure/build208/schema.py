from __future__ import annotations
from typing import Any
SCHEMA_208 = r'''
CREATE TABLE IF NOT EXISTS entity_resolution_profiles_208(profile_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,display_name TEXT NOT NULL,names_json TEXT NOT NULL,scripts_json TEXT NOT NULL,identifiers_json TEXT NOT NULL,attributes_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entity_resolution_candidates_208(candidate_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,left_profile_id TEXT NOT NULL,right_profile_id TEXT NOT NULL,signals_json TEXT NOT NULL,conflicts_json TEXT NOT NULL,score REAL NOT NULL,status TEXT NOT NULL,citations_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_workers_208(worker_id TEXT PRIMARY KEY,name TEXT NOT NULL,capabilities_json TEXT NOT NULL,max_parallel INTEGER NOT NULL,status TEXT NOT NULL,last_heartbeat TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_jobs_208(job_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,case_id TEXT NOT NULL,task_type TEXT NOT NULL,input_json TEXT NOT NULL,status TEXT NOT NULL,priority INTEGER NOT NULL,attempt INTEGER NOT NULL,max_attempts INTEGER NOT NULL,worker_id TEXT,checkpoint_json TEXT NOT NULL,model_route_json TEXT NOT NULL,budget_id TEXT,output_json TEXT,error_text TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_208_queue ON agent_jobs_208(status,priority,created_at);
CREATE TABLE IF NOT EXISTS agent_budgets_208(budget_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,max_tokens INTEGER NOT NULL,used_tokens INTEGER NOT NULL,max_cost REAL NOT NULL,used_cost REAL NOT NULL,currency TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS model_routes_208(route_id TEXT PRIMARY KEY,language TEXT NOT NULL,task_type TEXT NOT NULL,model_ref TEXT NOT NULL,local_only INTEGER NOT NULL,max_context INTEGER NOT NULL,quality_tier TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_benchmarks_208(benchmark_id TEXT PRIMARY KEY,name TEXT NOT NULL,agent_id TEXT NOT NULL,language TEXT NOT NULL,task_type TEXT NOT NULL,metrics_json TEXT NOT NULL,thresholds_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runtime_events_208(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,run_id TEXT,event_type TEXT NOT NULL,actor TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT,event_hash TEXT NOT NULL,created_at TEXT NOT NULL);
'''
def ensure_build208_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_208)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','208.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','208.0')")
    db.conn.commit()
