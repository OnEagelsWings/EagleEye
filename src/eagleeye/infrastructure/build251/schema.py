from __future__ import annotations
from typing import Any

SCHEMA_251 = r"""
CREATE TABLE IF NOT EXISTS influence_case_profiles_251 (
  profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE,
  objective TEXT NOT NULL, jurisdictions_json TEXT NOT NULL,
  research_scope TEXT NOT NULL, publication_posture TEXT NOT NULL,
  no_agent_scoring INTEGER NOT NULL DEFAULT 1,
  no_autonomous_publication INTEGER NOT NULL DEFAULT 1,
  no_private_mass_collection INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS influence_entities_251 (
  influence_entity_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
  kernel_object_id TEXT NOT NULL, entity_type TEXT NOT NULL, display_name TEXT NOT NULL,
  jurisdiction TEXT NOT NULL, official_domain TEXT NOT NULL,
  identifiers_json TEXT NOT NULL, former_names_json TEXT NOT NULL,
  parent_refs_json TEXT NOT NULL, notes TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_influence_entities251_case ON influence_entities_251(case_id,entity_type,display_name);

CREATE TABLE IF NOT EXISTS influence_edges_251 (
  edge_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
  source_influence_entity_id TEXT NOT NULL, target_influence_entity_id TEXT NOT NULL,
  relation_type TEXT NOT NULL, assertion_class TEXT NOT NULL,
  confidence REAL NOT NULL, evidence_refs_json TEXT NOT NULL,
  temporal_from TEXT NOT NULL, temporal_to TEXT NOT NULL,
  notes TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_influence_edges251_case ON influence_edges_251(case_id,relation_type,assertion_class);

CREATE TABLE IF NOT EXISTS influence_edge_reviews_251 (
  review_id TEXT PRIMARY KEY, edge_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
  decision TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL, kernel_link_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(edge_id) REFERENCES influence_edges_251(edge_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS influence_claim_controls_251 (
  control_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kernel_claim_id TEXT NOT NULL UNIQUE,
  legal_sensitivity TEXT NOT NULL, assertion_class TEXT NOT NULL,
  primary_evidence_required INTEGER NOT NULL,
  hearing_status TEXT NOT NULL, response_ref TEXT NOT NULL,
  publication_status TEXT NOT NULL, publication_note TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS influence_events_251 (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_influence_events251_case ON influence_events_251(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_inf_entity251_no_update BEFORE UPDATE ON influence_entities_251 BEGIN SELECT RAISE(ABORT,'influence_entities_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_entity251_no_delete BEFORE DELETE ON influence_entities_251 BEGIN SELECT RAISE(ABORT,'influence_entities_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_edge251_no_update BEFORE UPDATE ON influence_edges_251 BEGIN SELECT RAISE(ABORT,'influence_edges_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_edge251_no_delete BEFORE DELETE ON influence_edges_251 BEGIN SELECT RAISE(ABORT,'influence_edges_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_review251_no_update BEFORE UPDATE ON influence_edge_reviews_251 BEGIN SELECT RAISE(ABORT,'influence_edge_reviews_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_review251_no_delete BEFORE DELETE ON influence_edge_reviews_251 BEGIN SELECT RAISE(ABORT,'influence_edge_reviews_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_claim251_no_update BEFORE UPDATE ON influence_claim_controls_251 BEGIN SELECT RAISE(ABORT,'influence_claim_controls_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_claim251_no_delete BEFORE DELETE ON influence_claim_controls_251 BEGIN SELECT RAISE(ABORT,'influence_claim_controls_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_evt251_no_update BEFORE UPDATE ON influence_events_251 BEGIN SELECT RAISE(ABORT,'influence_events_251 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_inf_evt251_no_delete BEFORE DELETE ON influence_events_251 BEGIN SELECT RAISE(ABORT,'influence_events_251 is immutable'); END;
"""

def ensure_build251_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_251)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','251.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','251.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('phase10_pack','influence_funding_investigation')")
    db.conn.commit()
