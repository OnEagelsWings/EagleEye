from __future__ import annotations

from typing import Any


BUILD135_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS person_profile_sources_135(
  source_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'investigator_statement',
  source_title TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  captured_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_profile_sources135_target ON person_profile_sources_135(target_id,captured_at DESC);

CREATE TABLE IF NOT EXISTS person_profile_attributes_135(
  attribute_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  attribute_key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  known INTEGER NOT NULL DEFAULT 0,
  approximate INTEGER NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'unconfirmed',
  confidence REAL NOT NULL DEFAULT 0.5,
  source_id TEXT,
  investigator_note TEXT NOT NULL DEFAULT '',
  effective_from TEXT NOT NULL DEFAULT '',
  effective_to TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(target_id,attribute_key),
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES person_profile_sources_135(source_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_attributes135_target ON person_profile_attributes_135(target_id,attribute_key);

CREATE TABLE IF NOT EXISTS person_profile_history_135(
  history_id TEXT PRIMARY KEY,
  attribute_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  old_value_json TEXT NOT NULL DEFAULT '',
  new_value_json TEXT NOT NULL,
  old_status TEXT NOT NULL DEFAULT '',
  new_status TEXT NOT NULL,
  change_reason TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  FOREIGN KEY(attribute_id) REFERENCES person_profile_attributes_135(attribute_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_profile_history135_target ON person_profile_history_135(target_id,changed_at DESC);

CREATE TABLE IF NOT EXISTS firefox_case_sessions_135(
  case_id TEXT PRIMARY KEY,
  compartment_id TEXT NOT NULL,
  companion_token_hash TEXT NOT NULL DEFAULT '',
  companion_status TEXT NOT NULL DEFAULT 'unknown',
  last_heartbeat_epoch REAL NOT NULL DEFAULT 0,
  last_port INTEGER NOT NULL DEFAULT 0,
  profile_path_sha256 TEXT NOT NULL,
  registered_at TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS firefox_tab_orders_135(
  order_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  task_ids_json TEXT NOT NULL,
  urls_json TEXT NOT NULL,
  engines_json TEXT NOT NULL,
  destination_hosts_json TEXT NOT NULL,
  status TEXT NOT NULL,
  dispatch_mode TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  delivered_at TEXT NOT NULL DEFAULT '',
  acknowledged_at TEXT NOT NULL DEFAULT '',
  expires_epoch REAL NOT NULL,
  error_text TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tab_orders135_case_status ON firefox_tab_orders_135(case_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS provider_sources_135(
  source_key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  source_category TEXT NOT NULL,
  execution_mode TEXT NOT NULL,
  provider_key TEXT NOT NULL DEFAULT '',
  official_url TEXT NOT NULL,
  allowed_hosts_json TEXT NOT NULL,
  required_anchor_types_json TEXT NOT NULL DEFAULT '[]',
  data_classes_json TEXT NOT NULL DEFAULT '[]',
  auth_profile TEXT NOT NULL DEFAULT 'none',
  terms_profile TEXT NOT NULL DEFAULT 'official_public',
  expected_contract_json TEXT NOT NULL DEFAULT '{}',
  health_url TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  priority INTEGER NOT NULL DEFAULT 50,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_health_135(
  health_id TEXT PRIMARY KEY,
  source_key TEXT NOT NULL,
  status TEXT NOT NULL,
  http_status INTEGER,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  contract_sha256 TEXT NOT NULL DEFAULT '',
  response_fields_json TEXT NOT NULL DEFAULT '[]',
  detail TEXT NOT NULL DEFAULT '',
  checked_at TEXT NOT NULL,
  FOREIGN KEY(source_key) REFERENCES provider_sources_135(source_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_provider_health135_source ON provider_health_135(source_key,checked_at DESC);

CREATE TABLE IF NOT EXISTS provider_contract_baselines_135(
  source_key TEXT PRIMARY KEY,
  contract_sha256 TEXT NOT NULL,
  response_fields_json TEXT NOT NULL,
  baseline_status TEXT NOT NULL DEFAULT 'accepted',
  accepted_by TEXT NOT NULL,
  accepted_at TEXT NOT NULL,
  FOREIGN KEY(source_key) REFERENCES provider_sources_135(source_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS provider_contract_events_135(
  event_id TEXT PRIMARY KEY,
  source_key TEXT NOT NULL,
  previous_sha256 TEXT NOT NULL DEFAULT '',
  observed_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(source_key) REFERENCES provider_sources_135(source_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_source_routes_135(
  route_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  disclosed_anchors_json TEXT NOT NULL,
  recommendations_json TEXT NOT NULL,
  omitted_sources_json TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'candidate_only',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attribute_contradictions_135(
  contradiction_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  contradiction_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  attribute_keys_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  suggested_action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_contradictions135_target ON attribute_contradictions_135(target_id,status,created_at DESC);
"""


def ensure_build135_schema(db: Any) -> None:
    db.conn.executescript(BUILD135_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','135.0')")
    db.conn.commit()
