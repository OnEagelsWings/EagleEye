from __future__ import annotations
from typing import Any

SCHEMA_239 = r"""
CREATE TABLE IF NOT EXISTS evidence_vault_items_239 (
  vault_item_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  media_type TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  storage_relpath TEXT NOT NULL,
  original_filename TEXT NOT NULL DEFAULT '',
  source_key TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  captured_at TEXT NOT NULL,
  acquisition_method TEXT NOT NULL,
  capture_metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id,content_sha256,source_key,source_url,acquisition_method,captured_at)
);
CREATE INDEX IF NOT EXISTS idx_vault239_case ON evidence_vault_items_239(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vault239_origin ON evidence_vault_items_239(case_id,source_key,source_url,captured_at DESC);

CREATE TABLE IF NOT EXISTS evidence_reviews_239 (
  review_id TEXT PRIMARY KEY,
  vault_item_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  evidence_quality REAL NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  CHECK(decision IN ('accepted','rejected','needs_context')),
  CHECK(evidence_quality>=0 AND evidence_quality<=1)
);

CREATE TABLE IF NOT EXISTS evidence_derivations_239 (
  derivation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  parent_vault_item_id TEXT NOT NULL,
  child_vault_item_id TEXT NOT NULL UNIQUE,
  transformation_type TEXT NOT NULL,
  transformation_params_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(parent_vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  FOREIGN KEY(child_vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  CHECK(parent_vault_item_id<>child_vault_item_id)
);
CREATE INDEX IF NOT EXISTS idx_deriv239_parent ON evidence_derivations_239(parent_vault_item_id,created_at);

CREATE TABLE IF NOT EXISTS evidence_kernel_bindings_239 (
  binding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL UNIQUE,
  canonical_source_object_id TEXT NOT NULL,
  canonical_evidence_object_id TEXT NOT NULL,
  bound_by TEXT NOT NULL,
  bound_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  FOREIGN KEY(canonical_source_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  FOREIGN KEY(canonical_evidence_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_change_events_239 (
  change_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  origin_key TEXT NOT NULL,
  previous_vault_item_id TEXT NOT NULL,
  current_vault_item_id TEXT NOT NULL,
  previous_sha256 TEXT NOT NULL,
  current_sha256 TEXT NOT NULL,
  change_kind TEXT NOT NULL,
  detected_by TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(previous_vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  FOREIGN KEY(current_vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  CHECK(change_kind IN ('content_changed','metadata_only','unchanged'))
);
CREATE INDEX IF NOT EXISTS idx_change239_case ON evidence_change_events_239(case_id,detected_at DESC);

CREATE TABLE IF NOT EXISTS evidence_integrity_checks_239 (
  integrity_check_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL,
  expected_sha256 TEXT NOT NULL,
  observed_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  file_present INTEGER NOT NULL,
  checked_by TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  CHECK(status IN ('ok','missing','hash_mismatch'))
);
CREATE INDEX IF NOT EXISTS idx_integrity239_item ON evidence_integrity_checks_239(vault_item_id,checked_at DESC);

CREATE TABLE IF NOT EXISTS evidence_training_links_239 (
  training_link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL UNIQUE,
  review_id TEXT NOT NULL,
  training_example_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(vault_item_id) REFERENCES evidence_vault_items_239(vault_item_id) ON DELETE CASCADE,
  FOREIGN KEY(review_id) REFERENCES evidence_reviews_239(review_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_vault_snapshots_239 (
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  item_count INTEGER NOT NULL,
  accepted_count INTEGER NOT NULL,
  derived_count INTEGER NOT NULL,
  changed_origin_count INTEGER NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build239_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events239_case ON build239_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_vault239_no_update BEFORE UPDATE ON evidence_vault_items_239 BEGIN SELECT RAISE(ABORT,'evidence_vault_items_239 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_vault239_no_delete BEFORE DELETE ON evidence_vault_items_239 BEGIN SELECT RAISE(ABORT,'evidence_vault_items_239 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_reviews239_no_update BEFORE UPDATE ON evidence_reviews_239 BEGIN SELECT RAISE(ABORT,'evidence_reviews_239 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_reviews239_no_delete BEFORE DELETE ON evidence_reviews_239 BEGIN SELECT RAISE(ABORT,'evidence_reviews_239 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_deriv239_no_update BEFORE UPDATE ON evidence_derivations_239 BEGIN SELECT RAISE(ABORT,'evidence_derivations_239 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_events239_no_update BEFORE UPDATE ON build239_events BEGIN SELECT RAISE(ABORT,'build239_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events239_no_delete BEFORE DELETE ON build239_events BEGIN SELECT RAISE(ABORT,'build239_events is immutable'); END;
"""

def ensure_build239_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_239)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','239.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','239.0')")
    db.conn.commit()
