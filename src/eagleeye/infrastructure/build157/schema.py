from __future__ import annotations
from typing import Any
SCHEMA_157 = r'''
CREATE TABLE IF NOT EXISTS er_benchmarks_157(
 benchmark_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
 dataset_sha256 TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 policy_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS er_benchmark_pairs_157(
 pair_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL, left_record_json TEXT NOT NULL,
 right_record_json TEXT NOT NULL, expected_match INTEGER NOT NULL,
 predicted_match INTEGER, predicted_score REAL, explanation_json TEXT,
 FOREIGN KEY(benchmark_id) REFERENCES er_benchmarks_157(benchmark_id)
);
CREATE TABLE IF NOT EXISTS er_benchmark_runs_157(
 run_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL, engine_name TEXT NOT NULL,
 engine_version TEXT NOT NULL, threshold REAL NOT NULL, metrics_json TEXT NOT NULL,
 error_analysis_json TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
 run_sha256 TEXT NOT NULL, FOREIGN KEY(benchmark_id) REFERENCES er_benchmarks_157(benchmark_id)
);
CREATE TABLE IF NOT EXISTS code_consolidation_157(
 item_id TEXT PRIMARY KEY, legacy_path TEXT NOT NULL, canonical_path TEXT NOT NULL,
 disposition TEXT NOT NULL, status TEXT NOT NULL, rationale TEXT NOT NULL,
 recorded_at TEXT NOT NULL, UNIQUE(legacy_path, canonical_path)
);
CREATE TABLE IF NOT EXISTS consolidation_snapshots_157(
 snapshot_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL
);
'''
def ensure_build157_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_157)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','157.0')")
    db.conn.commit()
