from __future__ import annotations
from typing import Any
SCHEMA_209=r"""
CREATE TABLE IF NOT EXISTS collection_queues_209(queue_id TEXT PRIMARY KEY,priority INTEGER NOT NULL,max_parallel INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS process_isolation_profiles_209(agent_type TEXT PRIMARY KEY,isolation_mode TEXT NOT NULL,network_default_deny INTEGER NOT NULL,policy_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS production_model_routes_209(route_id TEXT PRIMARY KEY,languages TEXT NOT NULL,task_type TEXT NOT NULL,model_ref TEXT NOT NULL,backend TEXT NOT NULL,max_context INTEGER NOT NULL,local_only INTEGER NOT NULL,status TEXT NOT NULL,local_path TEXT,approved_by TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gpu_inventory_209(inventory_id TEXT PRIMARY KEY,backend TEXT NOT NULL,devices_json TEXT NOT NULL,cuda_available INTEGER NOT NULL,rocm_available INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gpu_allocations_209(allocation_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,device_index INTEGER NOT NULL,memory_mb INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,released_at TEXT);
CREATE TABLE IF NOT EXISTS collection_runs_209(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,source_ids_json TEXT NOT NULL,languages_json TEXT NOT NULL,status TEXT NOT NULL,max_tokens INTEGER NOT NULL,max_cost REAL NOT NULL,used_tokens INTEGER NOT NULL,used_cost REAL NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS collection_jobs_209(job_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,case_id TEXT NOT NULL,agent_type TEXT NOT NULL,priority INTEGER NOT NULL,status TEXT NOT NULL,attempt INTEGER NOT NULL,max_attempts INTEGER NOT NULL,worker_id TEXT,checkpoint_json TEXT NOT NULL,tokens_used INTEGER NOT NULL,cost REAL NOT NULL,error_text TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_collection_jobs_209 ON collection_jobs_209(status,priority,created_at);
CREATE TABLE IF NOT EXISTS gold_datasets_209(dataset_id TEXT PRIMARY KEY,name TEXT NOT NULL,language TEXT NOT NULL,record_count INTEGER NOT NULL,records_json TEXT NOT NULL,gold_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,approved_by TEXT);
CREATE TABLE IF NOT EXISTS gold_benchmarks_209(benchmark_id TEXT PRIMARY KEY,dataset_id TEXT NOT NULL,precision REAL NOT NULL,recall REAL NOT NULL,status TEXT NOT NULL,predictions_json TEXT NOT NULL,created_at TEXT NOT NULL,approved_by TEXT);
"""
def ensure_build209_schema(db: Any)->None:
 db.conn.executescript(SCHEMA_209); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','209.0')"); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','209.0')"); db.conn.commit()
