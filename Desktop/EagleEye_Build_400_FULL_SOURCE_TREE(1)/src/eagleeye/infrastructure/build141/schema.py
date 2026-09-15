from __future__ import annotations
from typing import Any

BUILD141_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS source_quality_assessments_141(
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  classification TEXT NOT NULL,
  authority_score REAL NOT NULL DEFAULT 0,
  primary_score REAL NOT NULL DEFAULT 0,
  traceability_score REAL NOT NULL DEFAULT 0,
  independence_score REAL NOT NULL DEFAULT 0,
  freshness_score REAL NOT NULL DEFAULT 0,
  stability_score REAL NOT NULL DEFAULT 0,
  transparency_score REAL NOT NULL DEFAULT 0,
  overall_score REAL NOT NULL DEFAULT 0,
  quality_band TEXT NOT NULL,
  strengths_json TEXT NOT NULL DEFAULT '[]',
  weaknesses_json TEXT NOT NULL DEFAULT '[]',
  review_required INTEGER NOT NULL DEFAULT 1,
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES evidence_sources_138(source_id) ON DELETE CASCADE,
  UNIQUE(case_id,source_id)
);
CREATE INDEX IF NOT EXISTS idx_source_quality141_case ON source_quality_assessments_141(case_id,overall_score DESC);

CREATE TABLE IF NOT EXISTS source_snapshots_141(
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  observed_url TEXT NOT NULL DEFAULT '',
  observed_title TEXT NOT NULL DEFAULT '',
  normalized_text_sha256 TEXT NOT NULL,
  normalized_text_length INTEGER NOT NULL DEFAULT 0,
  http_status INTEGER,
  availability_status TEXT NOT NULL,
  content_excerpt TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES evidence_sources_138(source_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_snapshots141_source ON source_snapshots_141(source_id,observed_at DESC);

CREATE TABLE IF NOT EXISTS source_change_events_141(
  change_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  previous_snapshot_id TEXT,
  current_snapshot_id TEXT NOT NULL,
  change_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  affected_assertion_ids_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES evidence_sources_138(source_id) ON DELETE CASCADE,
  FOREIGN KEY(previous_snapshot_id) REFERENCES source_snapshots_141(snapshot_id) ON DELETE SET NULL,
  FOREIGN KEY(current_snapshot_id) REFERENCES source_snapshots_141(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_changes141_case ON source_change_events_141(case_id,status,severity,created_at DESC);

CREATE TABLE IF NOT EXISTS source_risk_findings_141(
  finding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  finding_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  object_refs_json TEXT NOT NULL DEFAULT '[]',
  recommended_action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_risks141_case ON source_risk_findings_141(case_id,status,severity,created_at DESC);

CREATE TABLE IF NOT EXISTS change_aware_analyses_141(
  analysis141_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_analysis140_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  adjusted_claims_json TEXT NOT NULL DEFAULT '[]',
  source_change_impacts_json TEXT NOT NULL DEFAULT '[]',
  next_actions_json TEXT NOT NULL DEFAULT '[]',
  evidence_quality_score REAL NOT NULL DEFAULT 0,
  uncertainty_band TEXT NOT NULL,
  external_ai_used INTEGER NOT NULL DEFAULT 0,
  autonomous_actions INTEGER NOT NULL DEFAULT 0,
  generated_by TEXT NOT NULL DEFAULT 'local_change_aware_reasoner_141',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_analysis140_id) REFERENCES ai_analyses_140(analysis_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_change_analysis141_case ON change_aware_analyses_141(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS opsec_execution_envelopes_141(
  envelope_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  destination_type TEXT NOT NULL,
  destination_label TEXT NOT NULL,
  allowed_action_types_json TEXT NOT NULL DEFAULT '[]',
  data_classes_json TEXT NOT NULL DEFAULT '[]',
  max_identity_anchors INTEGER NOT NULL DEFAULT 0,
  max_external_actions INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  blocked INTEGER NOT NULL DEFAULT 0,
  findings_json TEXT NOT NULL DEFAULT '[]',
  mitigations_json TEXT NOT NULL DEFAULT '[]',
  approval_status TEXT NOT NULL DEFAULT 'draft',
  consumed_actions INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_opsec_envelopes141_case ON opsec_execution_envelopes_141(case_id,approval_status,expires_at);

CREATE TABLE IF NOT EXISTS workflow_optimization_runs_141(
  optimization_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  recommendations_json TEXT NOT NULL DEFAULT '[]',
  duplicate_groups_json TEXT NOT NULL DEFAULT '[]',
  blocked_sources_json TEXT NOT NULL DEFAULT '[]',
  next_best_actions_json TEXT NOT NULL DEFAULT '[]',
  estimated_minutes_saved INTEGER NOT NULL DEFAULT 0,
  applied INTEGER NOT NULL DEFAULT 0,
  applied_by TEXT NOT NULL DEFAULT '',
  applied_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(workflow_id) REFERENCES investigation_workflows_137(workflow_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflow_opt141_case ON workflow_optimization_runs_141(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS photo_result_quality_141(
  photo_quality_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  result_id TEXT NOT NULL,
  source_authority REAL NOT NULL DEFAULT 0,
  provenance_completeness REAL NOT NULL DEFAULT 0,
  temporal_priority REAL NOT NULL DEFAULT 0,
  visual_relation REAL NOT NULL DEFAULT 0,
  context_quality REAL NOT NULL DEFAULT 0,
  overall_score REAL NOT NULL DEFAULT 0,
  quality_band TEXT NOT NULL,
  duplicate_group TEXT NOT NULL DEFAULT '',
  earliest_known_candidate INTEGER NOT NULL DEFAULT 0,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  findings_json TEXT NOT NULL DEFAULT '[]',
  recommended_actions_json TEXT NOT NULL DEFAULT '[]',
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(result_id) REFERENCES photo_research_results_138(result_id) ON DELETE CASCADE,
  UNIQUE(case_id,result_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_quality141_case ON photo_result_quality_141(case_id,overall_score DESC);

CREATE TABLE IF NOT EXISTS photo_research_plans_141(
  plan_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  parent_asset_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  steps_json TEXT NOT NULL DEFAULT '[]',
  provider_diversity INTEGER NOT NULL DEFAULT 0,
  redundant_steps_removed INTEGER NOT NULL DEFAULT 0,
  estimated_minutes INTEGER NOT NULL DEFAULT 0,
  manual_uploads_required INTEGER NOT NULL DEFAULT 0,
  automatic_uploads INTEGER NOT NULL DEFAULT 0,
  identity_claims INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(parent_asset_id) REFERENCES photo_assets_136(asset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_photo_plans141_case ON photo_research_plans_141(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build141_events(
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
CREATE INDEX IF NOT EXISTS idx_build141_events_case ON build141_events(case_id,sequence DESC);
"""

def ensure_build141_schema(db: Any) -> None:
    db.conn.executescript(BUILD141_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','141.0')")
    db.conn.commit()
