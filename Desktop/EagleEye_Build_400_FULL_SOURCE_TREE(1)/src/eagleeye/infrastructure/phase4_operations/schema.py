from __future__ import annotations

from typing import Any

from eagleeye_pro.core.database import now_ts


def ensure_phase4_operations_schema_134(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS phase4_operational_policy_134(
          policy_id TEXT PRIMARY KEY,
          feature_profile TEXT NOT NULL DEFAULT 'operational_connector_trust_foundation',
          require_signed_external_manifests INTEGER NOT NULL DEFAULT 1,
          external_connector_code_execution TEXT NOT NULL DEFAULT 'disabled',
          runtime_repair_mode TEXT NOT NULL DEFAULT 'advisory_only',
          ai_trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          max_external_ai_actions INTEGER NOT NULL DEFAULT 0,
          remote_server_mode TEXT NOT NULL DEFAULT 'disabled_loopback_only',
          updated_by TEXT NOT NULL DEFAULT 'system',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runtime_preflight_runs_134(
          run_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          score INTEGER NOT NULL,
          check_count INTEGER NOT NULL,
          blocker_count INTEGER NOT NULL,
          warning_count INTEGER NOT NULL,
          report_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_runtime_preflight134_time
          ON runtime_preflight_runs_134(created_at DESC);
        CREATE TABLE IF NOT EXISTS connector_trusted_signers_134(
          signer_id TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          public_key_b64 TEXT NOT NULL,
          fingerprint_sha256 TEXT NOT NULL UNIQUE,
          active INTEGER NOT NULL DEFAULT 1,
          added_by TEXT NOT NULL,
          added_at TEXT NOT NULL,
          revoked_by TEXT NOT NULL DEFAULT '',
          revoked_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS connector_packages_134(
          package_id TEXT PRIMARY KEY,
          connector_key TEXT NOT NULL,
          provider_key TEXT NOT NULL,
          package_name TEXT NOT NULL,
          package_version TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          signature_algorithm TEXT NOT NULL DEFAULT '',
          signer_fingerprint TEXT NOT NULL DEFAULT '',
          signature_b64 TEXT NOT NULL DEFAULT '',
          trust_state TEXT NOT NULL,
          execution_state TEXT NOT NULL DEFAULT 'catalog_only_no_code_execution',
          source_kind TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(connector_key,package_version)
        );
        CREATE INDEX IF NOT EXISTS idx_connector_packages134_provider
          ON connector_packages_134(provider_key,trust_state);
        CREATE TABLE IF NOT EXISTS connector_contract_runs_134(
          run_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          provider_key TEXT NOT NULL,
          mode TEXT NOT NULL,
          status TEXT NOT NULL,
          check_count INTEGER NOT NULL,
          blocker_count INTEGER NOT NULL,
          warning_count INTEGER NOT NULL,
          report_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(package_id) REFERENCES connector_packages_134(package_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_connector_contract134_package
          ON connector_contract_runs_134(package_id,created_at DESC);
        CREATE TABLE IF NOT EXISTS connector_routing_advice_134(
          advice_id TEXT PRIMARY KEY,
          case_id TEXT,
          target_id TEXT,
          objective_sha256 TEXT NOT NULL,
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          external_actions INTEGER NOT NULL DEFAULT 0,
          content_json TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS phase4_opsec_events_134(
          event_id TEXT PRIMARY KEY,
          case_id TEXT,
          event_type TEXT NOT NULL,
          object_type TEXT NOT NULL DEFAULT '',
          object_id TEXT NOT NULL DEFAULT '',
          actor TEXT NOT NULL,
          details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
        );
        """
    )
    ts = now_ts()
    db.execute(
        """INSERT INTO phase4_operational_policy_134(policy_id,updated_at)
           VALUES('phase4',?)
           ON CONFLICT(policy_id) DO UPDATE SET
             feature_profile='operational_connector_trust_foundation',
             require_signed_external_manifests=1,
             external_connector_code_execution='disabled',
             runtime_repair_mode='advisory_only',
             ai_trust_state='suggestions_only',
             max_external_ai_actions=0,
             remote_server_mode='disabled_loopback_only',
             updated_at=excluded.updated_at""",
        (ts,),
    )
    current = (db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get('value', '')
    try:
        current_number = float(current)
    except (TypeError, ValueError):
        current_number = 0.0
    if current_number < 134.0:
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','134.0')")
