from __future__ import annotations

from typing import Any

from eagleeye_pro.core.database import now_ts


def ensure_phase3_release_schema_133(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS phase3_release_policy_133(
          policy_id TEXT PRIMARY KEY,
          feature_freeze INTEGER NOT NULL DEFAULT 1,
          release_profile TEXT NOT NULL DEFAULT 'production_slim',
          require_historical_regression INTEGER NOT NULL DEFAULT 1,
          require_windows_field_validation INTEGER NOT NULL DEFAULT 1,
          require_firefox_field_validation INTEGER NOT NULL DEFAULT 1,
          require_external_security_review INTEGER NOT NULL DEFAULT 1,
          ai_trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          max_external_ai_actions INTEGER NOT NULL DEFAULT 0,
          remote_server_mode TEXT NOT NULL DEFAULT 'disabled_loopback_only',
          updated_by TEXT NOT NULL DEFAULT 'system',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS phase3_candidate_runs_133(
          run_id TEXT PRIMARY KEY,
          case_id TEXT,
          status TEXT NOT NULL,
          score INTEGER NOT NULL,
          check_count INTEGER NOT NULL,
          blocker_count INTEGER NOT NULL,
          warning_count INTEGER NOT NULL,
          report_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_phase3_runs133_time ON phase3_candidate_runs_133(created_at DESC);
        CREATE TABLE IF NOT EXISTS phase3_candidate_checks_133(
          check_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          check_key TEXT NOT NULL,
          title TEXT NOT NULL,
          severity TEXT NOT NULL,
          status TEXT NOT NULL,
          details_json TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES phase3_candidate_runs_133(run_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_phase3_checks133_run ON phase3_candidate_checks_133(run_id);
        CREATE TABLE IF NOT EXISTS phase3_field_validations_133(
          validation_id TEXT PRIMARY KEY,
          component_key TEXT NOT NULL,
          platform_key TEXT NOT NULL,
          status TEXT NOT NULL,
          evidence_fingerprint TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          validated_by TEXT NOT NULL,
          validated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_phase3_field133_component ON phase3_field_validations_133(component_key,validated_at DESC);
        CREATE TABLE IF NOT EXISTS phase3_ai_opsec_assessments_133(
          assessment_id TEXT PRIMARY KEY,
          case_id TEXT,
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          external_actions INTEGER NOT NULL DEFAULT 0,
          content_json TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS phase3_release_freezes_133(
          freeze_id TEXT PRIMARY KEY,
          case_id TEXT,
          gate_run_id TEXT NOT NULL,
          backup_id TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL DEFAULT '',
          release_profile TEXT NOT NULL,
          status TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL,
          FOREIGN KEY(gate_run_id) REFERENCES phase3_candidate_runs_133(run_id)
        );
        CREATE TABLE IF NOT EXISTS phase3_opsec_events_133(
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
        """INSERT INTO phase3_release_policy_133(policy_id,updated_at)
           VALUES('phase3',?)
           ON CONFLICT(policy_id) DO UPDATE SET
             feature_freeze=1,release_profile='production_slim',
             ai_trust_state='suggestions_only',max_external_ai_actions=0,
             remote_server_mode='disabled_loopback_only',updated_at=excluded.updated_at""",
        (ts,),
    )
    db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','133.0')")
