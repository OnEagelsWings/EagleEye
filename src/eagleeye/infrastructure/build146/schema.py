from __future__ import annotations
from typing import Any

BUILD146_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS auth_settings_146(
  settings_id TEXT PRIMARY KEY,
  bootstrap_complete INTEGER NOT NULL DEFAULT 0,
  password_min_length INTEGER NOT NULL DEFAULT 15,
  password_max_length INTEGER NOT NULL DEFAULT 128,
  session_idle_minutes INTEGER NOT NULL DEFAULT 30,
  session_absolute_hours INTEGER NOT NULL DEFAULT 12,
  step_up_minutes INTEGER NOT NULL DEFAULT 15,
  bind_client_fingerprint INTEGER NOT NULL DEFAULT 1,
  secure_cookie_required INTEGER NOT NULL DEFAULT 0,
  pepper_version INTEGER NOT NULL DEFAULT 1,
  policy_version TEXT NOT NULL DEFAULT '146.0',
  updated_by TEXT NOT NULL DEFAULT 'system',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_users_146(
  user_id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  username_normalized TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  global_role TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 0,
  session_generation INTEGER NOT NULL DEFAULT 1,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  lock_until_epoch INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_login_at TEXT NOT NULL DEFAULT '',
  password_changed_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_auth146_users_active ON auth_users_146(active,global_role,username_normalized);

CREATE TABLE IF NOT EXISTS password_credentials_146(
  credential_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  hash_algorithm TEXT NOT NULL DEFAULT 'argon2id',
  pepper_version INTEGER NOT NULL DEFAULT 1,
  parameters_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS auth_sessions_146(
  session_id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  csrf_hash TEXT NOT NULL,
  user_id TEXT NOT NULL,
  session_generation INTEGER NOT NULL,
  assurance_level TEXT NOT NULL DEFAULT 'password',
  client_fingerprint TEXT NOT NULL DEFAULT '',
  created_epoch INTEGER NOT NULL,
  last_seen_epoch INTEGER NOT NULL,
  idle_expires_epoch INTEGER NOT NULL,
  absolute_expires_epoch INTEGER NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  revoked_reason TEXT NOT NULL DEFAULT '',
  revoked_by TEXT NOT NULL DEFAULT '',
  revoked_at TEXT NOT NULL DEFAULT '',
  last_rotated_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth146_sessions_user ON auth_sessions_146(user_id,revoked,absolute_expires_epoch);
CREATE INDEX IF NOT EXISTS idx_auth146_sessions_expiry ON auth_sessions_146(revoked,idle_expires_epoch,absolute_expires_epoch);

CREATE TABLE IF NOT EXISTS login_attempts_146(
  attempt_id TEXT PRIMARY KEY,
  username_hash TEXT NOT NULL,
  client_hash TEXT NOT NULL,
  success INTEGER NOT NULL DEFAULT 0,
  blocked INTEGER NOT NULL DEFAULT 0,
  reason_code TEXT NOT NULL,
  elapsed_ms INTEGER NOT NULL DEFAULT 0,
  created_epoch INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth146_attempt_user ON login_attempts_146(username_hash,created_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_auth146_attempt_client ON login_attempts_146(client_hash,created_epoch DESC);

CREATE TABLE IF NOT EXISTS recovery_codes_146(
  recovery_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  code_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  used_at TEXT NOT NULL DEFAULT '',
  used_client_hash TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth146_recovery_user ON recovery_codes_146(user_id,status,created_at DESC);

CREATE TABLE IF NOT EXISTS step_up_grants_146(
  grant_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  action_key TEXT NOT NULL,
  case_id TEXT NOT NULL DEFAULT '',
  assurance_level TEXT NOT NULL DEFAULT 'password_reauth',
  created_epoch INTEGER NOT NULL,
  expires_epoch INTEGER NOT NULL,
  consumed INTEGER NOT NULL DEFAULT 0,
  consumed_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(session_id) REFERENCES auth_sessions_146(session_id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth146_stepup_session ON step_up_grants_146(session_id,action_key,case_id,consumed,expires_epoch);

CREATE TABLE IF NOT EXISTS auth_case_memberships_146(
  membership_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  case_role TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  revoked_by TEXT NOT NULL DEFAULT '',
  revoked_at TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE(case_id,user_id,case_role),
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth146_members_case ON auth_case_memberships_146(case_id,active,case_role);
CREATE INDEX IF NOT EXISTS idx_auth146_members_user ON auth_case_memberships_146(user_id,active,case_id);

CREATE TABLE IF NOT EXISTS auth_security_events_146(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  user_id TEXT,
  username_hash TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL DEFAULT '',
  severity TEXT NOT NULL DEFAULT 'info',
  details_json TEXT NOT NULL DEFAULT '{}',
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_auth146_events_user ON auth_security_events_146(user_id,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_auth146_events_case ON auth_security_events_146(case_id,sequence DESC);

CREATE TABLE IF NOT EXISTS access_decisions_146(
  decision_id TEXT PRIMARY KEY,
  user_id TEXT,
  session_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL DEFAULT '',
  object_type TEXT NOT NULL DEFAULT '',
  object_id TEXT NOT NULL DEFAULT '',
  action_key TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 0,
  reason_code TEXT NOT NULL,
  policy_version TEXT NOT NULL DEFAULT '146.0',
  correlation_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_auth146_access_user ON access_decisions_146(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth146_access_case ON access_decisions_146(case_id,created_at DESC);

CREATE TABLE IF NOT EXISTS webauthn_credentials_146(
  credential_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  credential_data_json TEXT NOT NULL DEFAULT '{}',
  sign_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'not_configured',
  label TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_used_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(user_id) REFERENCES auth_users_146(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth146_webauthn_user ON webauthn_credentials_146(user_id,status);
"""


def ensure_build146_schema(db: Any) -> None:
    db.conn.executescript(BUILD146_SCHEMA)
    from eagleeye_pro.core.database import now_ts
    db.conn.execute(
        "INSERT OR IGNORE INTO auth_settings_146(settings_id,updated_at) VALUES('global',?)",
        (now_ts(),),
    )
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','146.0')")
    db.conn.commit()
