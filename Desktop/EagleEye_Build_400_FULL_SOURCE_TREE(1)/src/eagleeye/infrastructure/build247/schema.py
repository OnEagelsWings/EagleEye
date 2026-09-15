from __future__ import annotations
from typing import Any

SCHEMA_247 = r'''
CREATE TABLE IF NOT EXISTS ai_models_247(
 model_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, model_name TEXT NOT NULL, model_digest TEXT NOT NULL,
 version_ref TEXT NOT NULL, backend TEXT NOT NULL, capabilities_json TEXT NOT NULL, languages_json TEXT NOT NULL,
 context_window INTEGER NOT NULL, ram_mb INTEGER NOT NULL, vram_mb INTEGER NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,model_name,model_digest)
);
CREATE TABLE IF NOT EXISTS ai_model_reviews_247(
 review_id TEXT PRIMARY KEY, model_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
 rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_model_health_247(
 health_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, case_id TEXT NOT NULL, status TEXT NOT NULL,
 latency_ms REAL NOT NULL, error_rate REAL NOT NULL, tokens_per_second REAL NOT NULL, detail_json TEXT NOT NULL,
 observed_by TEXT NOT NULL, observed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_health247_model ON ai_model_health_247(model_id,observed_at);
CREATE TABLE IF NOT EXISTS ai_resource_snapshots_247(
 snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, cpu_count INTEGER NOT NULL, ram_total_mb INTEGER NOT NULL,
 ram_available_mb INTEGER NOT NULL, gpu_json TEXT NOT NULL, backend TEXT NOT NULL, observed_by TEXT NOT NULL,
 observed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_routing_policies_247(
 policy_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_type TEXT NOT NULL, language TEXT NOT NULL,
 min_context INTEGER NOT NULL, max_input_tokens INTEGER NOT NULL, max_output_tokens INTEGER NOT NULL,
 max_ram_mb INTEGER NOT NULL, max_vram_mb INTEGER NOT NULL, latency_class TEXT NOT NULL,
 local_only INTEGER NOT NULL, rationale TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_policy_reviews_247(
 review_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
 rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_policy_activations_247(
 activation_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, case_id TEXT NOT NULL, activated_by TEXT NOT NULL,
 activated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_route_decisions_247(
 decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_type TEXT NOT NULL, language TEXT NOT NULL,
 requested_context INTEGER NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
 selected_model_id TEXT NOT NULL, selected_model_name TEXT NOT NULL, backend TEXT NOT NULL, route_status TEXT NOT NULL,
 rationale_json TEXT NOT NULL, resource_snapshot_id TEXT NOT NULL, opsec_level TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_route_reviews_247(
 review_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, decision TEXT NOT NULL,
 rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_training_links_247(
 link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, decision_id TEXT NOT NULL UNIQUE, training_example_id TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_runtime_events_247(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
 object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_events247_case ON ai_runtime_events_247(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_aimodel247_no_update BEFORE UPDATE ON ai_models_247 BEGIN SELECT RAISE(ABORT,'ai_models_247 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aimodel247_no_delete BEFORE DELETE ON ai_models_247 BEGIN SELECT RAISE(ABORT,'ai_models_247 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aimodelrev247_no_update BEFORE UPDATE ON ai_model_reviews_247 BEGIN SELECT RAISE(ABORT,'ai_model_reviews_247 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aipolicy247_no_update BEFORE UPDATE ON ai_routing_policies_247 BEGIN SELECT RAISE(ABORT,'ai_routing_policies_247 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_airoute247_no_update BEFORE UPDATE ON ai_route_decisions_247 BEGIN SELECT RAISE(ABORT,'ai_route_decisions_247 immutable'); END;
'''

def ensure_build247_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_247)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','247.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','247.0')")
    db.conn.commit()
