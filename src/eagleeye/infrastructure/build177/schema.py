from __future__ import annotations
from typing import Any

SCHEMA_177 = r"""
CREATE TABLE IF NOT EXISTS graph_source_profiles_177(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, jurisdiction TEXT NOT NULL, category TEXT NOT NULL,
 access_mode TEXT NOT NULL, base_url TEXT NOT NULL, docs_url TEXT NOT NULL, terms_url TEXT NOT NULL,
 capabilities_json TEXT NOT NULL, constraints_json TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scalable_graphs_177(
 graph_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL, directed INTEGER NOT NULL,
 policy_json TEXT NOT NULL, node_count INTEGER NOT NULL DEFAULT 0, edge_count INTEGER NOT NULL DEFAULT 0,
 revision INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scalable_graph_nodes_177(
 graph_id TEXT NOT NULL, node_id TEXT NOT NULL, node_type TEXT NOT NULL, label TEXT NOT NULL,
 attributes_json TEXT NOT NULL, source_refs_json TEXT NOT NULL, confidence REAL NOT NULL,
 review_status TEXT NOT NULL, valid_from TEXT, valid_to TEXT, observed_at TEXT,
 canonical_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(graph_id,node_id)
);
CREATE TABLE IF NOT EXISTS scalable_graph_edges_177(
 graph_id TEXT NOT NULL, edge_id TEXT NOT NULL, source_node TEXT NOT NULL, target_node TEXT NOT NULL,
 predicate TEXT NOT NULL, directed INTEGER NOT NULL, weight REAL NOT NULL, attributes_json TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, confidence REAL NOT NULL, review_status TEXT NOT NULL,
 valid_from TEXT, valid_to TEXT, observed_at TEXT, canonical_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(graph_id,edge_id)
);
CREATE TABLE IF NOT EXISTS graph_analysis_runs_177(
 run_id TEXT PRIMARY KEY, graph_id TEXT NOT NULL, analysis_type TEXT NOT NULL, parameters_json TEXT NOT NULL,
 result_json TEXT NOT NULL, graph_revision INTEGER NOT NULL, node_count INTEGER NOT NULL, edge_count INTEGER NOT NULL,
 duration_ms REAL NOT NULL, approximation INTEGER NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_cache_177(
 graph_id TEXT NOT NULL, cache_key TEXT NOT NULL, graph_revision INTEGER NOT NULL,
 payload_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 PRIMARY KEY(graph_id,cache_key)
);
CREATE TABLE IF NOT EXISTS graph_benchmarks_177(
 benchmark_id TEXT PRIMARY KEY, graph_id TEXT, node_count INTEGER NOT NULL, edge_count INTEGER NOT NULL,
 build_seconds REAL NOT NULL, analysis_seconds REAL NOT NULL, peak_memory_estimate_bytes INTEGER NOT NULL,
 target_contract_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_events_177(
 event_id TEXT PRIMARY KEY, graph_id TEXT, case_id TEXT, event_type TEXT NOT NULL, details_json TEXT NOT NULL,
 created_at TEXT NOT NULL, previous_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_case ON scalable_graph_nodes_177(graph_id,node_type,review_status);
CREATE INDEX IF NOT EXISTS idx_graph_edges_nodes ON scalable_graph_edges_177(graph_id,source_node,target_node,predicate);
CREATE INDEX IF NOT EXISTS idx_graph_edges_time ON scalable_graph_edges_177(graph_id,valid_from,valid_to,observed_at);
CREATE INDEX IF NOT EXISTS idx_graph_runs_graph ON graph_analysis_runs_177(graph_id,analysis_type,created_at);
"""

def ensure_build177_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_177)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','177.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','177.0')")
    db.conn.commit()
