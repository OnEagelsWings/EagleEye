from __future__ import annotations
from typing import Any
SCHEMA_159=r'''
CREATE TABLE IF NOT EXISTS temporal_entities_159(entity_id TEXT PRIMARY KEY,case_id TEXT,entity_type TEXT NOT NULL,label TEXT NOT NULL,attributes_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_relations_159(relation_id TEXT PRIMARY KEY,case_id TEXT,subject_id TEXT NOT NULL,predicate TEXT NOT NULL,object_id TEXT NOT NULL,valid_from TEXT,valid_to TEXT,observed_at TEXT NOT NULL,source_time TEXT,source_ref TEXT,confidence REAL NOT NULL,status TEXT NOT NULL,provenance_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS temporal_conflicts_159(conflict_id TEXT PRIMARY KEY,case_id TEXT,relation_a_id TEXT NOT NULL,relation_b_id TEXT NOT NULL,conflict_type TEXT NOT NULL,severity TEXT NOT NULL,explanation_json TEXT NOT NULL,review_status TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_assistance_159(assistance_id TEXT PRIMARY KEY,case_id TEXT,task_type TEXT NOT NULL,input_sha256 TEXT NOT NULL,output_json TEXT NOT NULL,opsec_json TEXT NOT NULL,model_mode TEXT NOT NULL,review_required INTEGER NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS multilingual_aliases_159(alias_id TEXT PRIMARY KEY,case_id TEXT,canonical_name TEXT NOT NULL,alias_name TEXT NOT NULL,locale TEXT,alias_type TEXT NOT NULL,normalized_json TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
'''
def ensure_build159_schema(db:Any)->None:
 db.conn.executescript(SCHEMA_159); db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','159.0')"); db.conn.commit()
