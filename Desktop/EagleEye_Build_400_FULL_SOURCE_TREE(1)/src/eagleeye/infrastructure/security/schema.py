from __future__ import annotations




def _ensure_column(db, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in db.conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        db.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def ensure_security_schema_124(db) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS investigator_security_settings_124(
          settings_id TEXT PRIMARY KEY CHECK(settings_id='global'),
          protection_mode TEXT NOT NULL DEFAULT 'hardened',
          access_lock_enabled INTEGER NOT NULL DEFAULT 0,
          passphrase_salt TEXT NOT NULL DEFAULT '',
          passphrase_verifier TEXT NOT NULL DEFAULT '',
          session_timeout_minutes INTEGER NOT NULL DEFAULT 20,
          failed_attempts INTEGER NOT NULL DEFAULT 0,
          lock_until_epoch INTEGER NOT NULL DEFAULT 0,
          research_browser_mode TEXT NOT NULL DEFAULT 'isolated_firefox',
          proxy_mode TEXT NOT NULL DEFAULT 'none',
          proxy_host TEXT NOT NULL DEFAULT '',
          proxy_port INTEGER NOT NULL DEFAULT 0,
          proxy_remote_dns INTEGER NOT NULL DEFAULT 1,
          block_external_provider_network INTEGER NOT NULL DEFAULT 1,
          allow_default_browser_fallback INTEGER NOT NULL DEFAULT 0,
          clear_profile_before_launch INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS investigator_case_compartments_124(
          compartment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL UNIQUE,
          profile_token TEXT NOT NULL UNIQUE,
          profile_relpath TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          last_used_at TEXT NOT NULL DEFAULT '',
          launch_count INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS investigator_security_events_124(
          event_id TEXT PRIMARY KEY,
          case_id TEXT,
          event_type TEXT NOT NULL,
          severity TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_security_events124_case
          ON investigator_security_events_124(case_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS protected_research_launches_124(
          launch_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          compartment_id TEXT NOT NULL,
          browser_mode TEXT NOT NULL,
          destination_host TEXT NOT NULL,
          destination_fingerprint TEXT NOT NULL,
          status TEXT NOT NULL,
          error_text TEXT NOT NULL DEFAULT '',
          launched_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(task_id) REFERENCES search_tasks(task_id) ON DELETE CASCADE,
          FOREIGN KEY(compartment_id) REFERENCES investigator_case_compartments_124(compartment_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_research_launches124_case
          ON protected_research_launches_124(case_id,launched_at DESC);
        CREATE TABLE IF NOT EXISTS encrypted_secrets_124(
          secret_name TEXT PRIMARY KEY,
          nonce_b64 TEXT NOT NULL,
          ciphertext_b64 TEXT NOT NULL,
          aad_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provider_egress_approvals_124(
          approval_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          purpose TEXT NOT NULL,
          approved_by TEXT NOT NULL,
          status TEXT NOT NULL,
          expires_epoch INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          consumed_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_egress_approvals124_case
          ON provider_egress_approvals_124(case_id,provider,status,expires_epoch);
        CREATE TABLE IF NOT EXISTS evidence_trust_checkpoints_124(
          checkpoint_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          package_count INTEGER NOT NULL,
          checkpoint_sha256 TEXT NOT NULL,
          previous_sha256 TEXT NOT NULL DEFAULT '',
          signature_hmac_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_trust_checkpoints124_case
          ON evidence_trust_checkpoints_124(case_id,created_at DESC);
        """
    )
    _ensure_column(db, "investigator_security_settings_124", "ephemeral_profile_per_launch", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(db, "investigator_security_settings_124", "session_bind_client", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(db, "investigator_security_settings_124", "panic_purge_profiles", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(db, "investigator_security_settings_124", "last_lockdown_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "investigator_case_compartments_124", "rotation_count", "INTEGER NOT NULL DEFAULT 0")
    db.conn.commit()
