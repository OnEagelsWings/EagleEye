from __future__ import annotations
from typing import Any
SCHEMA_192 = r'''
CREATE TABLE IF NOT EXISTS graph_source_profiles_192(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,country TEXT NOT NULL,access_mode TEXT NOT NULL,endpoint TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL,blockers_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_graphs_192(graph_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,revision INTEGER NOT NULL,status TEXT NOT NULL,policy_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_graph_nodes_192(node_id TEXT PRIMARY KEY,graph_id TEXT NOT NULL,node_type TEXT NOT NULL,label TEXT NOT NULL,external_ref TEXT NOT NULL,attributes_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,valid_from TEXT NOT NULL,valid_to TEXT NOT NULL,observed_at TEXT NOT NULL,review_status TEXT NOT NULL,sensitive INTEGER NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_graph_edges_192(edge_id TEXT PRIMARY KEY,graph_id TEXT NOT NULL,source_node_id TEXT NOT NULL,target_node_id TEXT NOT NULL,edge_type TEXT NOT NULL,source_refs_json TEXT NOT NULL,confidence REAL NOT NULL,valid_from TEXT NOT NULL,valid_to TEXT NOT NULL,observed_at TEXT NOT NULL,review_status TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_graph_decisions_192(decision_id TEXT PRIMARY KEY,graph_id TEXT NOT NULL,target_node_id TEXT NOT NULL,reviewer TEXT NOT NULL,decision TEXT NOT NULL,note TEXT NOT NULL,created_at TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_graph_events_192(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,target_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,actor TEXT NOT NULL,prev_sha256 TEXT NOT NULL,event_sha256 TEXT NOT NULL);
'''
def ensure_build192_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_192)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','192.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','192.0')")
    db.conn.commit()
