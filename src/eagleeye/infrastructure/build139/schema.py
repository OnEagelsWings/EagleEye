from __future__ import annotations

from typing import Any


BUILD139_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS identity_candidates_139(
  candidate_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  label TEXT NOT NULL,
  source_node_id TEXT,
  attributes_json TEXT NOT NULL DEFAULT '{}',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  review_status TEXT NOT NULL DEFAULT 'unresolved',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  automatic_merge INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(source_node_id) REFERENCES evidence_nodes_138(node_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_candidates139_case ON identity_candidates_139(case_id,target_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS identity_comparisons_139(
  comparison_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL,
  positive_score REAL NOT NULL DEFAULT 0,
  conflict_score REAL NOT NULL DEFAULT 0,
  overall_score REAL NOT NULL DEFAULT 0,
  result_band TEXT NOT NULL,
  hard_conflict INTEGER NOT NULL DEFAULT 0,
  feature_results_json TEXT NOT NULL DEFAULT '[]',
  missing_fields_json TEXT NOT NULL DEFAULT '[]',
  rationale_json TEXT NOT NULL DEFAULT '[]',
  face_features_used INTEGER NOT NULL DEFAULT 0,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  generated_by TEXT NOT NULL DEFAULT 'local_explainable_rules',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(candidate_id) REFERENCES identity_candidates_139(candidate_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_comparisons139_candidate ON identity_comparisons_139(candidate_id);

CREATE TABLE IF NOT EXISTS identity_decisions_139(
  decision_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  automatic_decision INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(candidate_id) REFERENCES identity_candidates_139(candidate_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_identity_decisions139_case ON identity_decisions_139(case_id,decided_at DESC);

CREATE TABLE IF NOT EXISTS ai_investigation_briefs_139(
  brief_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  objective TEXT NOT NULL,
  facts_json TEXT NOT NULL DEFAULT '[]',
  hypotheses_json TEXT NOT NULL DEFAULT '[]',
  contradictions_json TEXT NOT NULL DEFAULT '[]',
  evidence_gaps_json TEXT NOT NULL DEFAULT '[]',
  next_steps_json TEXT NOT NULL DEFAULT '[]',
  bias_checks_json TEXT NOT NULL DEFAULT '[]',
  disclosure_plan_json TEXT NOT NULL DEFAULT '{}',
  external_ai_used INTEGER NOT NULL DEFAULT 0,
  identity_claims INTEGER NOT NULL DEFAULT 0,
  generated_by TEXT NOT NULL DEFAULT 'local_evidence_assistant',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_briefs139_case ON ai_investigation_briefs_139(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS opsec_assessments_139(
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  action_type TEXT NOT NULL,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  data_classes_json TEXT NOT NULL DEFAULT '[]',
  risk_level TEXT NOT NULL,
  blocked INTEGER NOT NULL DEFAULT 0,
  findings_json TEXT NOT NULL DEFAULT '[]',
  mitigations_json TEXT NOT NULL DEFAULT '[]',
  disclosure_budget_json TEXT NOT NULL DEFAULT '{}',
  retention_hours INTEGER NOT NULL DEFAULT 24,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_opsec_assessments139_case ON opsec_assessments_139(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS face_detections_139(
  detection_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  asset_id TEXT NOT NULL,
  face_index INTEGER NOT NULL,
  x_px INTEGER NOT NULL,
  y_px INTEGER NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  detector_name TEXT NOT NULL,
  detector_version TEXT NOT NULL,
  detection_confidence REAL NOT NULL DEFAULT 0,
  blur_variance REAL NOT NULL DEFAULT 0,
  brightness REAL NOT NULL DEFAULT 0,
  contrast REAL NOT NULL DEFAULT 0,
  face_area_ratio REAL NOT NULL DEFAULT 0,
  clipped INTEGER NOT NULL DEFAULT 0,
  quality_band TEXT NOT NULL,
  research_suitability TEXT NOT NULL,
  crop_relpath TEXT NOT NULL,
  crop_sha256 TEXT NOT NULL,
  biometric_template_created INTEGER NOT NULL DEFAULT 0,
  identity_comparison_performed INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(case_id,asset_id,face_index,crop_sha256)
);
CREATE INDEX IF NOT EXISTS idx_face_detections139_case ON face_detections_139(case_id,asset_id,created_at DESC);

CREATE TABLE IF NOT EXISTS face_research_runs_139(
  run_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  detection_id TEXT NOT NULL,
  provider_key TEXT NOT NULL,
  provider_label TEXT NOT NULL,
  provider_url TEXT NOT NULL,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'prepared',
  search_task_id TEXT,
  manual_upload_required INTEGER NOT NULL DEFAULT 1,
  external_upload_performed INTEGER NOT NULL DEFAULT 0,
  identity_claims INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(detection_id) REFERENCES face_detections_139(detection_id) ON DELETE CASCADE,
  FOREIGN KEY(search_task_id) REFERENCES search_tasks(task_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_face_runs139_case ON face_research_runs_139(case_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS photo_person_links_139(
  link_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  source_result_id TEXT,
  basis_json TEXT NOT NULL DEFAULT '[]',
  support_score REAL NOT NULL DEFAULT 0,
  conflict_score REAL NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'candidate',
  review_note TEXT NOT NULL DEFAULT '',
  face_match_used INTEGER NOT NULL DEFAULT 0,
  biometric_template_used INTEGER NOT NULL DEFAULT 0,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(source_result_id) REFERENCES photo_research_results_138(result_id) ON DELETE SET NULL,
  UNIQUE(case_id,target_id,asset_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_person_links139_case ON photo_person_links_139(case_id,target_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS build139_events(
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
CREATE INDEX IF NOT EXISTS idx_build139_events_case ON build139_events(case_id,sequence DESC);
"""


def ensure_build139_schema(db: Any) -> None:
    db.conn.executescript(BUILD139_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','139.0')")
    db.conn.commit()
