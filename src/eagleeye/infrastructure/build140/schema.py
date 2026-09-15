from __future__ import annotations

from typing import Any


BUILD140_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS ai_analyses_140(
  analysis_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  objective TEXT NOT NULL,
  executive_summary TEXT NOT NULL,
  facts_json TEXT NOT NULL DEFAULT '[]',
  probable_json TEXT NOT NULL DEFAULT '[]',
  hypotheses_json TEXT NOT NULL DEFAULT '[]',
  contradictions_json TEXT NOT NULL DEFAULT '[]',
  chronology_json TEXT NOT NULL DEFAULT '[]',
  open_questions_json TEXT NOT NULL DEFAULT '[]',
  alternative_hypotheses_json TEXT NOT NULL DEFAULT '[]',
  bias_checks_json TEXT NOT NULL DEFAULT '[]',
  prompt_injection_findings_json TEXT NOT NULL DEFAULT '[]',
  evidence_coverage REAL NOT NULL DEFAULT 0,
  uncertainty_band TEXT NOT NULL,
  external_ai_used INTEGER NOT NULL DEFAULT 0,
  autonomous_actions INTEGER NOT NULL DEFAULT 0,
  identity_claims INTEGER NOT NULL DEFAULT 0,
  generated_by TEXT NOT NULL DEFAULT 'local_evidence_reasoner_140',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_analyses140_case ON ai_analyses_140(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS ai_claims_140(
  claim_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT,
  claim_type TEXT NOT NULL,
  statement TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  evidence_assertion_ids_json TEXT NOT NULL DEFAULT '[]',
  source_ids_json TEXT NOT NULL DEFAULT '[]',
  contradiction_refs_json TEXT NOT NULL DEFAULT '[]',
  citation_coverage REAL NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  review_note TEXT NOT NULL DEFAULT '',
  automatic_identity_claim INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(analysis_id) REFERENCES ai_analyses_140(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_claims140_analysis ON ai_claims_140(analysis_id,claim_type,confidence DESC);

CREATE TABLE IF NOT EXISTS ai_recommendations_140(
  recommendation_id TEXT PRIMARY KEY,
  analysis_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT,
  title TEXT NOT NULL,
  rationale TEXT NOT NULL,
  action_type TEXT NOT NULL,
  evidence_gap TEXT NOT NULL DEFAULT '',
  expected_information_gain REAL NOT NULL DEFAULT 0,
  urgency REAL NOT NULL DEFAULT 0,
  opsec_risk REAL NOT NULL DEFAULT 0,
  effort REAL NOT NULL DEFAULT 0,
  priority_score REAL NOT NULL DEFAULT 0,
  required_data_classes_json TEXT NOT NULL DEFAULT '[]',
  external_destination TEXT NOT NULL DEFAULT '',
  manual_approval_required INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'proposed',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(analysis_id) REFERENCES ai_analyses_140(analysis_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations140_case ON ai_recommendations_140(case_id,priority_score DESC);

CREATE TABLE IF NOT EXISTS opsec_action_plans_140(
  plan_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  analysis_id TEXT,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  selected_recommendations_json TEXT NOT NULL DEFAULT '[]',
  action_rows_json TEXT NOT NULL DEFAULT '[]',
  destinations_json TEXT NOT NULL DEFAULT '[]',
  data_classes_json TEXT NOT NULL DEFAULT '[]',
  redactions_json TEXT NOT NULL DEFAULT '[]',
  findings_json TEXT NOT NULL DEFAULT '[]',
  mitigations_json TEXT NOT NULL DEFAULT '[]',
  risk_level TEXT NOT NULL,
  blocked INTEGER NOT NULL DEFAULT 0,
  approval_status TEXT NOT NULL DEFAULT 'draft',
  external_actions INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(analysis_id) REFERENCES ai_analyses_140(analysis_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_opsec_plans140_case ON opsec_action_plans_140(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS disclosure_packages_140(
  package_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  analysis_id TEXT,
  destination_type TEXT NOT NULL,
  destination_label TEXT NOT NULL,
  purpose TEXT NOT NULL,
  selected_claim_ids_json TEXT NOT NULL DEFAULT '[]',
  payload_json TEXT NOT NULL DEFAULT '{}',
  redactions_json TEXT NOT NULL DEFAULT '[]',
  package_sha256 TEXT NOT NULL,
  anchor_count INTEGER NOT NULL DEFAULT 0,
  contains_images INTEGER NOT NULL DEFAULT 0,
  contains_biometrics INTEGER NOT NULL DEFAULT 0,
  external_transfer_performed INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(analysis_id) REFERENCES ai_analyses_140(analysis_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_disclosure_packages140_case ON disclosure_packages_140(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS image_analyses_140(
  image_analysis_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  asset_id TEXT NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  format_name TEXT NOT NULL,
  entropy REAL NOT NULL DEFAULT 0,
  sharpness REAL NOT NULL DEFAULT 0,
  brightness REAL NOT NULL DEFAULT 0,
  contrast REAL NOT NULL DEFAULT 0,
  edge_density REAL NOT NULL DEFAULT 0,
  colorfulness REAL NOT NULL DEFAULT 0,
  clipped_dark_ratio REAL NOT NULL DEFAULT 0,
  clipped_light_ratio REAL NOT NULL DEFAULT 0,
  ela_mean REAL NOT NULL DEFAULT 0,
  ela_hotspot_ratio REAL NOT NULL DEFAULT 0,
  screenshot_likelihood REAL NOT NULL DEFAULT 0,
  face_region_count INTEGER NOT NULL DEFAULT 0,
  quality_band TEXT NOT NULL,
  content_profile TEXT NOT NULL,
  anomaly_hints_json TEXT NOT NULL DEFAULT '[]',
  research_recommendations_json TEXT NOT NULL DEFAULT '[]',
  metadata_summary_json TEXT NOT NULL DEFAULT '{}',
  manipulation_claim INTEGER NOT NULL DEFAULT 0,
  biometric_analysis INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(case_id,asset_id)
);
CREATE INDEX IF NOT EXISTS idx_image_analyses140_case ON image_analyses_140(case_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS image_analysis_comparisons_140(
  comparison_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  reference_asset_id TEXT NOT NULL,
  compared_asset_id TEXT NOT NULL,
  exact_sha256 INTEGER NOT NULL DEFAULT 0,
  ahash_distance INTEGER NOT NULL DEFAULT 64,
  dhash_distance INTEGER NOT NULL DEFAULT 64,
  dimension_ratio REAL NOT NULL DEFAULT 0,
  entropy_delta REAL NOT NULL DEFAULT 0,
  edge_density_delta REAL NOT NULL DEFAULT 0,
  relation_band TEXT NOT NULL,
  transformation_hints_json TEXT NOT NULL DEFAULT '[]',
  identity_claim INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(reference_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  FOREIGN KEY(compared_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE,
  UNIQUE(case_id,reference_asset_id,compared_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_image_comparisons140_case ON image_analysis_comparisons_140(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build140_events(
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
CREATE INDEX IF NOT EXISTS idx_build140_events_case ON build140_events(case_id,sequence DESC);
"""


def ensure_build140_schema(db: Any) -> None:
    db.conn.executescript(BUILD140_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','140.0')")
    db.conn.commit()
