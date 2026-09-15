from __future__ import annotations
from typing import Any
SCHEMA_207=r'''
CREATE TABLE IF NOT EXISTS ai_agent_profiles_207(agent_id TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,permissions_json TEXT NOT NULL,source_scope_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_agent_runs_207(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,question TEXT NOT NULL,status TEXT NOT NULL,current_stage TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_agent_tasks_207(task_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,agent_id TEXT NOT NULL,sequence_no INTEGER NOT NULL,input_json TEXT NOT NULL,output_json TEXT,status TEXT NOT NULL,requires_approval INTEGER NOT NULL,approved_by TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_ai_agent_tasks_207_run ON ai_agent_tasks_207(run_id,sequence_no);
CREATE TABLE IF NOT EXISTS ai_agent_approvals_207(approval_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,task_id TEXT NOT NULL,action TEXT NOT NULL,approved_by TEXT NOT NULL,scope_json TEXT NOT NULL,used INTEGER NOT NULL,expires_at TEXT,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_agent_findings_207(finding_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,case_id TEXT NOT NULL,finding_type TEXT NOT NULL,statement TEXT NOT NULL,status TEXT NOT NULL,confidence REAL NOT NULL,citations_json TEXT NOT NULL,verification_plan_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS social_research_snapshots_207(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,account_ids_json TEXT NOT NULL,platforms_json TEXT NOT NULL,interaction_json TEXT NOT NULL,activity_json TEXT NOT NULL,alias_candidates_json TEXT NOT NULL,citations_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_agent_feedback_207(feedback_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_ref TEXT NOT NULL,verdict TEXT NOT NULL,reason TEXT NOT NULL,analyst TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_agent_events_207(event_id TEXT PRIMARY KEY,run_id TEXT,case_id TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,payload_json TEXT NOT NULL,prev_hash TEXT,event_hash TEXT NOT NULL,created_at TEXT NOT NULL);
'''
def ensure_build207_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_207)
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','207.0')")
 db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','207.0')")
 db.conn.commit()
