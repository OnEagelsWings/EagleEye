from __future__ import annotations
from typing import Any

SCHEMA_236 = r'''
CREATE TABLE IF NOT EXISTS source_fabric_sources_236 (
  fabric_source_id TEXT PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_fabric_revisions_236 (
  revision_id TEXT PRIMARY KEY,
  fabric_source_id TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  title TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL,
  route_class TEXT NOT NULL,
  adapter_family TEXT NOT NULL,
  access_mode TEXT NOT NULL,
  target_types_json TEXT NOT NULL,
  outputs_json TEXT NOT NULL,
  countries_json TEXT NOT NULL,
  languages_json TEXT NOT NULL,
  capabilities_json TEXT NOT NULL,
  cost_class TEXT NOT NULL,
  network_capable INTEGER NOT NULL DEFAULT 0,
  requires_auth INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  health_state TEXT NOT NULL DEFAULT 'unknown',
  opsec_risk TEXT NOT NULL DEFAULT 'elevated',
  governance_state TEXT NOT NULL DEFAULT 'pending_review',
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(fabric_source_id) REFERENCES source_fabric_sources_236(fabric_source_id) ON DELETE CASCADE,
  CHECK(network_capable IN (0,1)), CHECK(requires_auth IN (0,1)), CHECK(active IN (0,1)),
  CHECK(opsec_risk IN ('low','elevated','high','critical')),
  CHECK(governance_state IN ('inherited_approved','pending_review','approved','rejected','deferred')),
  UNIQUE(fabric_source_id,revision_no)
);
CREATE INDEX IF NOT EXISTS idx_fabric236_revision_source ON source_fabric_revisions_236(fabric_source_id,revision_no DESC);

CREATE TABLE IF NOT EXISTS source_fabric_reviews_236 (
  review_id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL UNIQUE,
  fabric_source_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(revision_id) REFERENCES source_fabric_revisions_236(revision_id) ON DELETE CASCADE,
  FOREIGN KEY(fabric_source_id) REFERENCES source_fabric_sources_236(fabric_source_id) ON DELETE CASCADE,
  CHECK(decision IN ('approved','rejected','deferred'))
);

CREATE TABLE IF NOT EXISTS source_fabric_health_236 (
  observation_id TEXT PRIMARY KEY,
  fabric_source_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  health_state TEXT NOT NULL,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  error_class TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  observed_by TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(fabric_source_id) REFERENCES source_fabric_sources_236(fabric_source_id) ON DELETE CASCADE,
  CHECK(health_state IN ('healthy','degraded','unknown','unavailable','quarantined','contract_failed'))
);
CREATE INDEX IF NOT EXISTS idx_fabric236_health_source ON source_fabric_health_236(fabric_source_id,observed_at DESC);

CREATE TABLE IF NOT EXISTS source_fabric_case_bindings_236 (
  binding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  fabric_source_id TEXT NOT NULL,
  source_key TEXT NOT NULL,
  canonical_source_object_id TEXT NOT NULL,
  bound_by TEXT NOT NULL,
  bound_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(fabric_source_id) REFERENCES source_fabric_sources_236(fabric_source_id) ON DELETE CASCADE,
  FOREIGN KEY(canonical_source_object_id) REFERENCES canonical_objects_235(object_id) ON DELETE CASCADE,
  UNIQUE(case_id,fabric_source_id)
);
CREATE INDEX IF NOT EXISTS idx_fabric236_bind_case ON source_fabric_case_bindings_236(case_id,source_key);

CREATE TABLE IF NOT EXISTS source_fabric_training_links_236 (
  training_link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_outcome_id TEXT NOT NULL UNIQUE,
  source_key TEXT NOT NULL,
  training_example_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fabric236_training_case ON source_fabric_training_links_236(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build236_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL DEFAULT '',
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events236_case ON build236_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_fabric236_source_no_update BEFORE UPDATE ON source_fabric_sources_236 BEGIN SELECT RAISE(ABORT,'source_fabric_sources_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_source_no_delete BEFORE DELETE ON source_fabric_sources_236 BEGIN SELECT RAISE(ABORT,'source_fabric_sources_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_revision_no_update BEFORE UPDATE ON source_fabric_revisions_236 BEGIN SELECT RAISE(ABORT,'source_fabric_revisions_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_revision_no_delete BEFORE DELETE ON source_fabric_revisions_236 BEGIN SELECT RAISE(ABORT,'source_fabric_revisions_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_review_no_update BEFORE UPDATE ON source_fabric_reviews_236 BEGIN SELECT RAISE(ABORT,'source_fabric_reviews_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_review_no_delete BEFORE DELETE ON source_fabric_reviews_236 BEGIN SELECT RAISE(ABORT,'source_fabric_reviews_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_health_no_update BEFORE UPDATE ON source_fabric_health_236 BEGIN SELECT RAISE(ABORT,'source_fabric_health_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_health_no_delete BEFORE DELETE ON source_fabric_health_236 BEGIN SELECT RAISE(ABORT,'source_fabric_health_236 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_binding_no_update BEFORE UPDATE ON source_fabric_case_bindings_236 BEGIN SELECT RAISE(ABORT,'source_fabric_case_bindings_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_binding_no_delete BEFORE DELETE ON source_fabric_case_bindings_236 BEGIN SELECT RAISE(ABORT,'source_fabric_case_bindings_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_training_no_update BEFORE UPDATE ON source_fabric_training_links_236 BEGIN SELECT RAISE(ABORT,'source_fabric_training_links_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_fabric236_training_no_delete BEFORE DELETE ON source_fabric_training_links_236 BEGIN SELECT RAISE(ABORT,'source_fabric_training_links_236 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events236_no_update BEFORE UPDATE ON build236_events BEGIN SELECT RAISE(ABORT,'build236_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_events236_no_delete BEFORE DELETE ON build236_events BEGIN SELECT RAISE(ABORT,'build236_events is immutable'); END;
'''


def ensure_build236_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_236)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','236.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','236.0')")
    db.conn.commit()
