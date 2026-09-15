from __future__ import annotations
from typing import Any

SCHEMA_228 = r'''
CREATE TABLE IF NOT EXISTS training_examples_228 (
  example_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_ref TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'de',
  instruction_text TEXT NOT NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  response_text TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  quality_labels_json TEXT NOT NULL DEFAULT '{}',
  redaction_status TEXT NOT NULL DEFAULT 'pending',
  review_status TEXT NOT NULL DEFAULT 'pending',
  split_name TEXT NOT NULL DEFAULT '',
  content_sha256 TEXT NOT NULL,
  created_by TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  reviewed_at TEXT NOT NULL DEFAULT '',
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_train228_content ON training_examples_228(content_sha256);
CREATE INDEX IF NOT EXISTS idx_train228_case ON training_examples_228(case_id,review_status,split_name);

CREATE TABLE IF NOT EXISTS training_datasets_228 (
  dataset_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  seed INTEGER NOT NULL,
  train_ratio REAL NOT NULL,
  validation_ratio REAL NOT NULL,
  holdout_ratio REAL NOT NULL,
  example_ids_json TEXT NOT NULL,
  split_manifest_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_by TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  approved_at TEXT NOT NULL DEFAULT '',
  dataset_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id,name,version)
);

CREATE TABLE IF NOT EXISTS training_runs_228 (
  run_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  dataset_id TEXT NOT NULL,
  base_model TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT 'lora',
  training_config_json TEXT NOT NULL,
  reproducibility_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  adapter_path TEXT NOT NULL DEFAULT '',
  adapter_sha256 TEXT NOT NULL DEFAULT '',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  baseline_metrics_json TEXT NOT NULL DEFAULT '{}',
  qualification_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(dataset_id) REFERENCES training_datasets_228(dataset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs228_case ON training_runs_228(case_id,status,created_at);

CREATE TABLE IF NOT EXISTS adapter_registry_228 (
  adapter_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  base_model TEXT NOT NULL,
  adapter_path TEXT NOT NULL,
  adapter_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'qualified',
  qualification_json TEXT NOT NULL,
  activated_by TEXT NOT NULL DEFAULT '',
  activated_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(run_id) REFERENCES training_runs_228(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adapter228_case ON adapter_registry_228(case_id,status);

CREATE TABLE IF NOT EXISTS build228_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  previous_hash TEXT NOT NULL DEFAULT '',
  event_hash TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events228_case ON build228_events(case_id,created_at);
CREATE TRIGGER IF NOT EXISTS trg_events228_no_update BEFORE UPDATE ON build228_events BEGIN SELECT RAISE(ABORT,'build228_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events228_no_delete BEFORE DELETE ON build228_events BEGIN SELECT RAISE(ABORT,'build228_events is immutable'); END;
'''

def ensure_build228_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_228)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','228.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','228.0')")
    db.conn.commit()
