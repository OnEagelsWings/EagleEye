from __future__ import annotations

from typing import Any

BUILD147_SCHEMA = r'''
CREATE TABLE IF NOT EXISTS research_sources_147(
  source_key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  source_group TEXT NOT NULL,
  category TEXT NOT NULL,
  access_mode TEXT NOT NULL,
  official_url TEXT NOT NULL,
  search_url_template TEXT NOT NULL DEFAULT '',
  provider_key TEXT NOT NULL DEFAULT '',
  allowed_hosts_json TEXT NOT NULL DEFAULT '[]',
  input_types_json TEXT NOT NULL DEFAULT '[]',
  auth_requirement TEXT NOT NULL DEFAULT 'none',
  terms_profile TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'low',
  persona_recommended INTEGER NOT NULL DEFAULT 0,
  native_execution INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  priority INTEGER NOT NULL DEFAULT 50,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_sources147_group ON research_sources_147(source_group,category,priority DESC);

CREATE TABLE IF NOT EXISTS research_plans_147(
  plan_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  objective TEXT NOT NULL,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  full_name TEXT NOT NULL DEFAULT '',
  username TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  organisation TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  aliases_json TEXT NOT NULL DEFAULT '[]',
  source_keys_json TEXT NOT NULL DEFAULT '[]',
  query_variants_json TEXT NOT NULL DEFAULT '[]',
  ai_brief_json TEXT NOT NULL DEFAULT '{}',
  opsec_findings_json TEXT NOT NULL DEFAULT '[]',
  disclosure_budget INTEGER NOT NULL DEFAULT 3,
  max_external_actions INTEGER NOT NULL DEFAULT 12,
  risk_level TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'draft',
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_research_plans147_case ON research_plans_147(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS research_jobs_147(
  job_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT,
  source_key TEXT NOT NULL,
  query_text TEXT NOT NULL,
  query_sha256 TEXT NOT NULL,
  execution_mode TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  priority INTEGER NOT NULL DEFAULT 50,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  not_before_epoch INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_expires_epoch INTEGER NOT NULL DEFAULT 0,
  browser_task_id TEXT NOT NULL DEFAULT '',
  browser_order_id TEXT NOT NULL DEFAULT '',
  provider_run_id TEXT NOT NULL DEFAULT '',
  result_count INTEGER NOT NULL DEFAULT 0,
  blocked_reason TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(plan_id) REFERENCES research_plans_147(plan_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(source_key) REFERENCES research_sources_147(source_key),
  UNIQUE(case_id,source_key,query_sha256)
);
CREATE INDEX IF NOT EXISTS idx_research_jobs147_queue ON research_jobs_147(case_id,status,priority DESC,not_before_epoch,created_at);
CREATE INDEX IF NOT EXISTS idx_research_jobs147_plan ON research_jobs_147(plan_id,status,priority DESC);

CREATE TABLE IF NOT EXISTS social_profile_candidates_147(
  candidate_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  plan_id TEXT,
  job_id TEXT,
  source_key TEXT NOT NULL,
  profile_url TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  username TEXT NOT NULL DEFAULT '',
  display_name TEXT NOT NULL DEFAULT '',
  bio TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  profile_identifier TEXT NOT NULL DEFAULT '',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  source_context TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  candidate_only INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(plan_id) REFERENCES research_plans_147(plan_id) ON DELETE SET NULL,
  FOREIGN KEY(job_id) REFERENCES research_jobs_147(job_id) ON DELETE SET NULL,
  FOREIGN KEY(source_key) REFERENCES research_sources_147(source_key),
  UNIQUE(case_id,source_key,canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_social_candidates147_case ON social_profile_candidates_147(case_id,review_status,confidence DESC);

CREATE TABLE IF NOT EXISTS opsec_assessments_147(
  assessment_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  blocked INTEGER NOT NULL DEFAULT 0,
  findings_json TEXT NOT NULL DEFAULT '[]',
  mitigations_json TEXT NOT NULL DEFAULT '[]',
  active_persona_session_id TEXT NOT NULL DEFAULT '',
  query_exposure_score REAL NOT NULL DEFAULT 0,
  checked_by TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  FOREIGN KEY(plan_id) REFERENCES research_plans_147(plan_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_opsec147_plan ON opsec_assessments_147(plan_id,checked_at DESC);

CREATE TABLE IF NOT EXISTS build147_events(
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
CREATE INDEX IF NOT EXISTS idx_build147_events_case ON build147_events(case_id,sequence DESC);
'''


def ensure_build147_schema(db: Any) -> None:
    db.conn.executescript(BUILD147_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','147.0')")
    db.conn.commit()
