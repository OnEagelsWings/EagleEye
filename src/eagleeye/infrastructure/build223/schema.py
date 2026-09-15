from __future__ import annotations
from typing import Any

SCHEMA_223 = r'''
CREATE TABLE IF NOT EXISTS consolidation_case_config_223(
 case_id TEXT PRIMARY KEY,
 config_version INTEGER NOT NULL DEFAULT 1,
 working_language TEXT NOT NULL DEFAULT 'de',
 max_retrieval_chunks INTEGER NOT NULL DEFAULT 12,
 max_source_actions INTEGER NOT NULL DEFAULT 5,
 live_sources_enabled INTEGER NOT NULL DEFAULT 0,
 canonical_ai_service TEXT NOT NULL DEFAULT 'build223',
 canonical_retrieval_service TEXT NOT NULL DEFAULT 'build216',
 canonical_source_service TEXT NOT NULL DEFAULT 'build223',
 canonical_reliability_service TEXT NOT NULL DEFAULT 'build219',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_by TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(max_retrieval_chunks BETWEEN 1 AND 30),
 CHECK(max_source_actions BETWEEN 1 AND 10),
 CHECK(live_sources_enabled IN (0,1))
);

CREATE TABLE IF NOT EXISTS canonical_component_map_223(
 component_key TEXT PRIMARY KEY,
 canonical_service TEXT NOT NULL,
 legacy_services_json TEXT NOT NULL DEFAULT '[]',
 responsibility TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 CHECK(status IN ('active','compatibility_only','deprecated'))
);

CREATE TABLE IF NOT EXISTS investigation_traces_223(
 trace_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 parent_trace_id TEXT NOT NULL DEFAULT '',
 operation TEXT NOT NULL,
 component TEXT NOT NULL,
 status TEXT NOT NULL,
 started_by TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT NOT NULL DEFAULT '',
 input_sha256 TEXT NOT NULL,
 output_sha256 TEXT NOT NULL DEFAULT '',
 metrics_json TEXT NOT NULL DEFAULT '{}',
 error_class TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(status IN ('running','completed','blocked','failed'))
);
CREATE INDEX IF NOT EXISTS idx_investigation_traces_223_case ON investigation_traces_223(case_id,started_at);
CREATE INDEX IF NOT EXISTS idx_investigation_traces_223_parent ON investigation_traces_223(parent_trace_id);

CREATE TABLE IF NOT EXISTS consolidation_baselines_223(
 baseline_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 baseline_version INTEGER NOT NULL,
 ai_metrics_json TEXT NOT NULL,
 source_metrics_json TEXT NOT NULL,
 retrieval_metrics_json TEXT NOT NULL,
 service_map_json TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_consolidation_baselines_223_case ON consolidation_baselines_223(case_id,created_at);

CREATE TABLE IF NOT EXISTS build223_events(
 event_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 object_type TEXT NOT NULL,
 object_id TEXT NOT NULL,
 actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build223_events_case ON build223_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_component_map_223_no_delete BEFORE DELETE ON canonical_component_map_223 BEGIN SELECT RAISE(ABORT,'canonical_component_map_223 may not be deleted'); END;
CREATE TRIGGER IF NOT EXISTS trg_baselines_223_no_update BEFORE UPDATE ON consolidation_baselines_223 BEGIN SELECT RAISE(ABORT,'consolidation_baselines_223 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_baselines_223_no_delete BEFORE DELETE ON consolidation_baselines_223 BEGIN SELECT RAISE(ABORT,'consolidation_baselines_223 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build223_events_no_update BEFORE UPDATE ON build223_events BEGIN SELECT RAISE(ABORT,'build223_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build223_events_no_delete BEFORE DELETE ON build223_events BEGIN SELECT RAISE(ABORT,'build223_events is immutable'); END;
'''


def ensure_build223_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_223)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','223.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','223.0')")
    db.conn.commit()
