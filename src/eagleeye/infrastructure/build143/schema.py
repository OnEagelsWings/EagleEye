from __future__ import annotations
from typing import Any

BUILD143_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS research_personas_143(
  persona_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  label TEXT NOT NULL,
  persona_type TEXT NOT NULL,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  jurisdiction TEXT NOT NULL DEFAULT 'DE/EU',
  contact_alias TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'pending_review',
  synthetic_identity_confirmed INTEGER NOT NULL DEFAULT 1,
  no_existing_person_impersonation INTEGER NOT NULL DEFAULT 1,
  requested_by TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  approval_reason TEXT NOT NULL DEFAULT '',
  expires_at TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_personas143_case ON research_personas_143(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS persona_accounts_143(
  account_id TEXT PRIMARY KEY,
  persona_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  account_label TEXT NOT NULL,
  username_alias TEXT NOT NULL DEFAULT '',
  email_alias TEXT NOT NULL DEFAULT '',
  account_origin TEXT NOT NULL,
  secret_ref TEXT NOT NULL DEFAULT '',
  secret_present INTEGER NOT NULL DEFAULT 0,
  terms_reviewed INTEGER NOT NULL DEFAULT 0,
  manual_creation_confirmed INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active',
  expires_at TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(persona_id) REFERENCES research_personas_143(persona_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_persona_accounts143 ON persona_accounts_143(case_id,persona_id,status);

CREATE TABLE IF NOT EXISTS network_egress_profiles_143(
  egress_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  label TEXT NOT NULL,
  mode TEXT NOT NULL,
  proxy_host TEXT NOT NULL DEFAULT '',
  proxy_port INTEGER NOT NULL DEFAULT 0,
  remote_dns INTEGER NOT NULL DEFAULT 1,
  requires_auth INTEGER NOT NULL DEFAULT 0,
  secret_ref TEXT NOT NULL DEFAULT '',
  secret_present INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending_review',
  risk_note TEXT NOT NULL DEFAULT '',
  requested_by TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  approval_reason TEXT NOT NULL DEFAULT '',
  expires_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_egress143_case ON network_egress_profiles_143(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS research_persona_sessions_143(
  session_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  target_id TEXT,
  persona_id TEXT NOT NULL,
  account_id TEXT,
  egress_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  legal_basis TEXT NOT NULL,
  start_url TEXT NOT NULL DEFAULT '',
  require_origin_separation INTEGER NOT NULL DEFAULT 1,
  risk_level TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'draft',
  max_actions INTEGER NOT NULL DEFAULT 20,
  consumed_actions INTEGER NOT NULL DEFAULT 0,
  duration_minutes INTEGER NOT NULL DEFAULT 60,
  profile_relpath TEXT NOT NULL DEFAULT '',
  requested_by TEXT NOT NULL,
  approved_by TEXT NOT NULL DEFAULT '',
  approval_reason TEXT NOT NULL DEFAULT '',
  launched_at TEXT NOT NULL DEFAULT '',
  expires_epoch INTEGER NOT NULL DEFAULT 0,
  closed_at TEXT NOT NULL DEFAULT '',
  close_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL,
  FOREIGN KEY(persona_id) REFERENCES research_personas_143(persona_id) ON DELETE RESTRICT,
  FOREIGN KEY(account_id) REFERENCES persona_accounts_143(account_id) ON DELETE SET NULL,
  FOREIGN KEY(egress_id) REFERENCES network_egress_profiles_143(egress_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_persona_sessions143_case ON research_persona_sessions_143(case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS persona_session_preflights_143(
  preflight_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  status TEXT NOT NULL,
  blocker_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  findings_json TEXT NOT NULL DEFAULT '[]',
  checked_by TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES research_persona_sessions_143(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_preflight143_session ON persona_session_preflights_143(session_id,checked_at DESC);

CREATE TABLE IF NOT EXISTS persona_session_actions_143(
  action_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  destination_host TEXT NOT NULL DEFAULT '',
  details_json TEXT NOT NULL DEFAULT '{}',
  manual_action INTEGER NOT NULL DEFAULT 1,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES research_persona_sessions_143(session_id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_session_actions143 ON persona_session_actions_143(session_id,created_at DESC);

CREATE TABLE IF NOT EXISTS case_access_attestations_143(
  attestation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_access_attestations143 ON case_access_attestations_143(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS build143_events(
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
CREATE INDEX IF NOT EXISTS idx_build143_events_case ON build143_events(case_id,sequence DESC);
"""


def ensure_build143_schema(db: Any) -> None:
    db.conn.executescript(BUILD143_SCHEMA)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','143.0')")
    db.conn.commit()
