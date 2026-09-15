from __future__ import annotations

from typing import Any


BUILD137_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS investigation_workflows_137(
  workflow_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  objective_key TEXT NOT NULL,
  objective_text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  identity_claims_allowed INTEGER NOT NULL DEFAULT 0,
  name_variants_json TEXT NOT NULL DEFAULT '[]',
  anchors_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflows137_case ON investigation_workflows_137(case_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflows137_target ON investigation_workflows_137(target_id,created_at DESC);

CREATE TABLE IF NOT EXISTS investigation_workflow_stages_137(
  stage_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  stage_key TEXT NOT NULL,
  stage_order INTEGER NOT NULL,
  title TEXT NOT NULL,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(workflow_id) REFERENCES investigation_workflows_137(workflow_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(workflow_id,stage_key)
);
CREATE INDEX IF NOT EXISTS idx_workflow_stages137_workflow ON investigation_workflow_stages_137(workflow_id,stage_order);

CREATE TABLE IF NOT EXISTS investigation_workflow_tasks_137(
  workflow_task_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  stage_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  source_key TEXT NOT NULL DEFAULT '',
  task_type TEXT NOT NULL,
  title TEXT NOT NULL,
  query_text TEXT NOT NULL DEFAULT '',
  rationale TEXT NOT NULL DEFAULT '',
  expected_output TEXT NOT NULL DEFAULT '',
  search_task_id TEXT,
  priority INTEGER NOT NULL DEFAULT 50,
  status TEXT NOT NULL DEFAULT 'planned',
  outcome_note TEXT NOT NULL DEFAULT '',
  manual_review_required INTEGER NOT NULL DEFAULT 1,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(workflow_id) REFERENCES investigation_workflows_137(workflow_id) ON DELETE CASCADE,
  FOREIGN KEY(stage_id) REFERENCES investigation_workflow_stages_137(stage_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(search_task_id) REFERENCES search_tasks(task_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks137_workflow ON investigation_workflow_tasks_137(workflow_id,status,priority DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_tasks137_search ON investigation_workflow_tasks_137(search_task_id);

CREATE TABLE IF NOT EXISTS photo_metadata_137(
  metadata_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT,
  image_format TEXT NOT NULL,
  color_mode TEXT NOT NULL,
  frame_count INTEGER NOT NULL DEFAULT 1,
  animated INTEGER NOT NULL DEFAULT 0,
  exif_present INTEGER NOT NULL DEFAULT 0,
  gps_present INTEGER NOT NULL DEFAULT 0,
  icc_present INTEGER NOT NULL DEFAULT 0,
  metadata_keys_json TEXT NOT NULL DEFAULT '[]',
  exif_tag_names_json TEXT NOT NULL DEFAULT '[]',
  safe_summary_json TEXT NOT NULL DEFAULT '{}',
  sensitive_fields_json TEXT NOT NULL DEFAULT '[]',
  analyzed_by TEXT NOT NULL,
  analyzed_at TEXT NOT NULL,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  UNIQUE(asset_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_metadata137_case ON photo_metadata_137(case_id,analyzed_at DESC);

CREATE TABLE IF NOT EXISTS photo_fingerprints_137(
  fingerprint_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  ahash64 TEXT NOT NULL,
  dhash64 TEXT NOT NULL,
  algorithm_version TEXT NOT NULL,
  analyzed_at TEXT NOT NULL,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(asset_id,algorithm_version)
);
CREATE INDEX IF NOT EXISTS idx_photo_fingerprints137_case ON photo_fingerprints_137(case_id,analyzed_at DESC);

CREATE TABLE IF NOT EXISTS photo_similarity_links_137(
  link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  left_asset_id TEXT NOT NULL,
  right_asset_id TEXT NOT NULL,
  ahash_distance INTEGER NOT NULL,
  dhash_distance INTEGER NOT NULL,
  similarity_band TEXT NOT NULL,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(left_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(right_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(case_id,left_asset_id,right_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_similarity137_case ON photo_similarity_links_137(case_id,similarity_band,created_at DESC);

CREATE TABLE IF NOT EXISTS photo_research_copies_137(
  copy_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_asset_id TEXT NOT NULL,
  storage_relpath TEXT NOT NULL,
  filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  metadata_removed INTEGER NOT NULL DEFAULT 1,
  derivation_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  expires_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_photo_copies137_case ON photo_research_copies_137(case_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photo_copies137_dedupe ON photo_research_copies_137(case_id,parent_asset_id,sha256);

CREATE TABLE IF NOT EXISTS photo_research_jobs_137(
  job_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_asset_id TEXT NOT NULL,
  copy_id TEXT NOT NULL,
  provider_key TEXT NOT NULL,
  provider_label TEXT NOT NULL,
  provider_url TEXT NOT NULL,
  purpose TEXT NOT NULL,
  disclosure_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'prepared',
  search_task_id TEXT,
  manual_upload_required INTEGER NOT NULL DEFAULT 1,
  external_upload_performed INTEGER NOT NULL DEFAULT 0,
  result_note TEXT NOT NULL DEFAULT '',
  approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(copy_id) REFERENCES photo_research_copies_137(copy_id) ON DELETE CASCADE,
  FOREIGN KEY(search_task_id) REFERENCES search_tasks(task_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_photo_jobs137_case ON photo_research_jobs_137(case_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS build137_events(
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build137_events_case ON build137_events(case_id,created_at DESC);
"""


def ensure_build137_schema(db: Any) -> None:
    db.conn.executescript(BUILD137_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','137.0')")
    db.conn.commit()
