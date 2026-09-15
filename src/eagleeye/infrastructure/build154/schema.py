from __future__ import annotations
from typing import Any

SCHEMA_154 = r"""
CREATE TABLE IF NOT EXISTS connector_specs_154(
 connector_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, version TEXT NOT NULL,
 base_url TEXT NOT NULL, allowed_hosts_json TEXT NOT NULL, lifecycle_status TEXT NOT NULL,
 contract_state TEXT NOT NULL, parser_kind TEXT NOT NULL, records_path TEXT NOT NULL,
 timeout_seconds REAL NOT NULL, max_attempts INTEGER NOT NULL, max_response_bytes INTEGER NOT NULL,
 allowed_content_types_json TEXT NOT NULL, terms_reference TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connector154_state ON connector_specs_154(lifecycle_status,contract_state);

CREATE TABLE IF NOT EXISTS connector_runs_154(
 run_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, correlation_id TEXT NOT NULL, case_id TEXT,
 query_json TEXT NOT NULL, status TEXT NOT NULL, outcome_code TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 http_status INTEGER, records_count INTEGER NOT NULL DEFAULT 0, response_bytes INTEGER NOT NULL DEFAULT 0,
 schema_fingerprint TEXT, provenance_json TEXT NOT NULL DEFAULT '{}', error_message TEXT,
 started_at TEXT NOT NULL, finished_at TEXT, duration_ms INTEGER,
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_connector_runs154_corr ON connector_runs_154(correlation_id);
CREATE INDEX IF NOT EXISTS idx_connector_runs154_connector ON connector_runs_154(connector_id,started_at);

CREATE TABLE IF NOT EXISTS connector_health_154(
 health_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, checked_at TEXT NOT NULL, status TEXT NOT NULL,
 consecutive_failures INTEGER NOT NULL, last_success_at TEXT, last_failure_at TEXT,
 latency_ms INTEGER, schema_fingerprint TEXT, schema_drift INTEGER NOT NULL DEFAULT 0,
 details_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
CREATE INDEX IF NOT EXISTS idx_connector_health154_connector ON connector_health_154(connector_id,checked_at);

CREATE TABLE IF NOT EXISTS connector_schema_history_154(
 schema_id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, observed_at TEXT NOT NULL,
 schema_fingerprint TEXT NOT NULL, schema_shape_json TEXT NOT NULL, run_id TEXT NOT NULL,
 FOREIGN KEY(connector_id) REFERENCES connector_specs_154(connector_id)
);
"""

def ensure_build154_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_154)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','154.0')")
    db.conn.commit()
