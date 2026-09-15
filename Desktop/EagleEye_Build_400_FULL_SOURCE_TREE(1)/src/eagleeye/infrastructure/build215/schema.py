from __future__ import annotations
from typing import Any

SCHEMA_215 = r'''
CREATE TABLE IF NOT EXISTS ollama_case_config_215(
 case_id TEXT PRIMARY KEY,
 endpoint TEXT NOT NULL,
 selected_model TEXT NOT NULL DEFAULT '',
 context_window INTEGER NOT NULL DEFAULT 8192,
 temperature REAL NOT NULL DEFAULT 0.15,
 max_context_chars INTEGER NOT NULL DEFAULT 80000,
 local_only INTEGER NOT NULL DEFAULT 1,
 updated_by TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ollama_model_snapshots_215(
 snapshot_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 digest TEXT NOT NULL,
 size_bytes INTEGER NOT NULL,
 modified_at TEXT NOT NULL,
 details_json TEXT NOT NULL,
 capabilities_json TEXT NOT NULL,
 parameter_size TEXT NOT NULL,
 quantization_level TEXT NOT NULL,
 status TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ollama_models_215_case ON ollama_model_snapshots_215(case_id,observed_at);
CREATE TABLE IF NOT EXISTS ollama_runs_215(
 run_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 turn_id TEXT,
 run_type TEXT NOT NULL,
 model_name TEXT NOT NULL,
 endpoint TEXT NOT NULL,
 status TEXT NOT NULL,
 request_sha256 TEXT NOT NULL,
 response_sha256 TEXT NOT NULL DEFAULT '',
 prompt_eval_count INTEGER NOT NULL DEFAULT 0,
 eval_count INTEGER NOT NULL DEFAULT 0,
 total_duration_ns INTEGER NOT NULL DEFAULT 0,
 error_code TEXT NOT NULL DEFAULT '',
 actor TEXT NOT NULL,
 created_at TEXT NOT NULL,
 completed_at TEXT NOT NULL DEFAULT '',
 payload_sha256 TEXT NOT NULL,
 build_version TEXT NOT NULL DEFAULT '215.0',
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ollama_runs_215_case ON ollama_runs_215(case_id,created_at);
CREATE TABLE IF NOT EXISTS build215_events(
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
CREATE INDEX IF NOT EXISTS idx_build215_events_case ON build215_events(case_id,created_at);
CREATE TRIGGER IF NOT EXISTS trg_ollama_model_snapshots_215_no_update BEFORE UPDATE ON ollama_model_snapshots_215 BEGIN SELECT RAISE(ABORT,'ollama_model_snapshots_215 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ollama_model_snapshots_215_no_delete BEFORE DELETE ON ollama_model_snapshots_215 BEGIN SELECT RAISE(ABORT,'ollama_model_snapshots_215 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ollama_runs_215_no_update BEFORE UPDATE ON ollama_runs_215 BEGIN SELECT RAISE(ABORT,'ollama_runs_215 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ollama_runs_215_no_delete BEFORE DELETE ON ollama_runs_215 BEGIN SELECT RAISE(ABORT,'ollama_runs_215 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build215_events_no_update BEFORE UPDATE ON build215_events BEGIN SELECT RAISE(ABORT,'build215_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build215_events_no_delete BEFORE DELETE ON build215_events BEGIN SELECT RAISE(ABORT,'build215_events is immutable'); END;
'''


def ensure_build215_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_215)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','215.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','215.0')")
    db.conn.commit()
