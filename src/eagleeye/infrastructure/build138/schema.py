from __future__ import annotations

from typing import Any


BUILD138_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS evidence_nodes_138(
  node_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  normalized_value TEXT NOT NULL DEFAULT '',
  attributes_json TEXT NOT NULL DEFAULT '{}',
  review_state TEXT NOT NULL DEFAULT 'candidate',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_nodes138_case ON evidence_nodes_138(case_id,node_type,updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_nodes138_unique ON evidence_nodes_138(case_id,node_type,normalized_value) WHERE normalized_value!='';

CREATE TABLE IF NOT EXISTS evidence_sources_138(
  source_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  canonical_url TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  publisher TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL DEFAULT 'unknown',
  publication_at TEXT NOT NULL DEFAULT '',
  retrieved_at TEXT NOT NULL,
  content_hash TEXT NOT NULL DEFAULT '',
  independence_group TEXT NOT NULL,
  origin_fingerprint TEXT NOT NULL,
  parent_source_id TEXT,
  reliability REAL NOT NULL DEFAULT 0.5,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(parent_source_id) REFERENCES evidence_sources_138(source_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_sources138_case ON evidence_sources_138(case_id,retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_sources138_origin ON evidence_sources_138(case_id,origin_fingerprint,independence_group);

CREATE TABLE IF NOT EXISTS evidence_assertions_138(
  assertion_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  subject_node_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_node_id TEXT NOT NULL,
  assertion_text TEXT NOT NULL,
  epistemic_state TEXT NOT NULL DEFAULT 'lead',
  confidence REAL NOT NULL DEFAULT 0.5,
  valid_from TEXT NOT NULL DEFAULT '',
  valid_to TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  source_count INTEGER NOT NULL DEFAULT 0,
  independence_count INTEGER NOT NULL DEFAULT 0,
  review_note TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(subject_node_id) REFERENCES evidence_nodes_138(node_id) ON DELETE CASCADE,
  FOREIGN KEY(object_node_id) REFERENCES evidence_nodes_138(node_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_assertions138_case ON evidence_assertions_138(case_id,epistemic_state,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_assertions138_subject ON evidence_assertions_138(case_id,subject_node_id,predicate);

CREATE TABLE IF NOT EXISTS evidence_assertion_sources_138(
  link_id TEXT PRIMARY KEY,
  assertion_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  stance TEXT NOT NULL DEFAULT 'supports',
  weight REAL NOT NULL DEFAULT 1.0,
  excerpt TEXT NOT NULL DEFAULT '',
  rationale TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(assertion_id) REFERENCES evidence_assertions_138(assertion_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES evidence_sources_138(source_id) ON DELETE CASCADE,
  UNIQUE(assertion_id,source_id,stance)
);
CREATE INDEX IF NOT EXISTS idx_assertion_sources138_assertion ON evidence_assertion_sources_138(assertion_id,stance);

CREATE TABLE IF NOT EXISTS evidence_provenance_edges_138(
  edge_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  from_object_type TEXT NOT NULL,
  from_object_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  to_object_type TEXT NOT NULL,
  to_object_id TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id,from_object_type,from_object_id,relation_type,to_object_type,to_object_id)
);
CREATE INDEX IF NOT EXISTS idx_provenance138_case ON evidence_provenance_edges_138(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS evidence_warnings_138(
  warning_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  warning_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  object_refs_json TEXT NOT NULL DEFAULT '[]',
  details_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_warnings138_case ON evidence_warnings_138(case_id,status,severity,created_at DESC);

CREATE TABLE IF NOT EXISTS photo_variants_138(
  variant_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_asset_id TEXT NOT NULL,
  variant_mode TEXT NOT NULL,
  label TEXT NOT NULL,
  parameters_json TEXT NOT NULL DEFAULT '{}',
  storage_relpath TEXT NOT NULL,
  filename TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
  byte_size INTEGER NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  ahash64 TEXT NOT NULL,
  dhash64 TEXT NOT NULL,
  metadata_removed INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'ready',
  expires_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_photo_variants138_case ON photo_variants_138(case_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_variants138_dedupe ON photo_variants_138(case_id,parent_asset_id,sha256);


CREATE TABLE IF NOT EXISTS photo_search_runs_138(
  run_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_asset_id TEXT NOT NULL,
  variant_id TEXT,
  copy_id TEXT,
  provider_key TEXT NOT NULL,
  provider_label TEXT NOT NULL,
  provider_url TEXT NOT NULL,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'prepared',
  search_task_id TEXT,
  manual_upload_required INTEGER NOT NULL DEFAULT 1,
  external_upload_performed INTEGER NOT NULL DEFAULT 0,
  result_note TEXT NOT NULL DEFAULT '',
  disclosure_json TEXT NOT NULL DEFAULT '{}',
  approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(variant_id) REFERENCES photo_variants_138(variant_id) ON DELETE CASCADE,
  FOREIGN KEY(copy_id) REFERENCES photo_research_copies_137(copy_id) ON DELETE CASCADE,
  FOREIGN KEY(search_task_id) REFERENCES search_tasks(task_id) ON DELETE SET NULL,
  CHECK((variant_id IS NOT NULL AND copy_id IS NULL) OR (variant_id IS NULL AND copy_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_photo_runs138_case ON photo_search_runs_138(case_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS photo_research_results_138(
  result_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  research_run_type TEXT NOT NULL DEFAULT 'build138',
  research_run_id TEXT NOT NULL,
  parent_asset_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  page_url TEXT NOT NULL,
  image_url TEXT NOT NULL DEFAULT '',
  page_title TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL,
  result_kind TEXT NOT NULL DEFAULT 'unknown',
  review_status TEXT NOT NULL DEFAULT 'candidate',
  local_result_asset_id TEXT,
  notes TEXT NOT NULL DEFAULT '',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES evidence_sources_138(source_id) ON DELETE CASCADE,
  FOREIGN KEY(local_result_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_photo_results138_case ON photo_research_results_138(case_id,updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_results138_unique ON photo_research_results_138(research_run_type,research_run_id,page_url,image_url);

CREATE TABLE IF NOT EXISTS photo_comparisons_138(
  comparison_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  result_id TEXT NOT NULL,
  reference_asset_id TEXT NOT NULL,
  compared_asset_id TEXT NOT NULL,
  exact_sha256 INTEGER NOT NULL DEFAULT 0,
  ahash_distance INTEGER NOT NULL,
  dhash_distance INTEGER NOT NULL,
  image_relation_band TEXT NOT NULL,
  identity_claim INTEGER NOT NULL DEFAULT 0,
  manual_observations_json TEXT NOT NULL DEFAULT '{}',
  review_status TEXT NOT NULL DEFAULT 'candidate',
  review_note TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(result_id) REFERENCES photo_research_results_138(result_id) ON DELETE CASCADE,
  FOREIGN KEY(reference_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(compared_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(result_id,reference_asset_id,compared_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_comparisons138_case ON photo_comparisons_138(case_id,image_relation_band,updated_at DESC);

CREATE TABLE IF NOT EXISTS photo_clusters_138(
  cluster_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  label TEXT NOT NULL,
  algorithm_version TEXT NOT NULL,
  threshold_json TEXT NOT NULL,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS photo_cluster_members_138(
  member_id TEXT PRIMARY KEY,
  cluster_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  created_at TEXT NOT NULL,
  FOREIGN KEY(cluster_id) REFERENCES photo_clusters_138(cluster_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(cluster_id,asset_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_clusters138_case ON photo_cluster_members_138(case_id,cluster_id);

CREATE TABLE IF NOT EXISTS build138_events(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  previous_hash TEXT NOT NULL,
  event_hash TEXT UNIQUE NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build138_events_case ON build138_events(case_id,sequence DESC);
"""


def ensure_build138_schema(db: Any) -> None:
    db.conn.executescript(BUILD138_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','138.0')")
    db.conn.commit()
