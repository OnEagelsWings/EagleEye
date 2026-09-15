from __future__ import annotations

from typing import Any


def ensure_release_schema_126(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS production_candidate_runs_126(
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
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_pc_runs126_case
          ON production_candidate_runs_126(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS production_candidate_checks_126(
          check_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          check_key TEXT NOT NULL,
          title TEXT NOT NULL,
          severity TEXT NOT NULL,
          status TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY(run_id) REFERENCES production_candidate_runs_126(run_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_pc_checks126_run
          ON production_candidate_checks_126(run_id,status,severity);

        CREATE TABLE IF NOT EXISTS phase2_release_freezes_126(
          freeze_id TEXT PRIMARY KEY,
          case_id TEXT,
          gate_run_id TEXT NOT NULL,
          backup_id TEXT NOT NULL DEFAULT '',
          manifest_sha256 TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL,
          FOREIGN KEY(gate_run_id) REFERENCES production_candidate_runs_126(run_id) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_phase2_freezes126_created
          ON phase2_release_freezes_126(created_at DESC);

        CREATE TABLE IF NOT EXISTS external_ai_launches_126(
          launch_id TEXT PRIMARY KEY,
          case_id TEXT,
          tool_key TEXT NOT NULL,
          destination_host TEXT NOT NULL,
          launch_mode TEXT NOT NULL,
          status TEXT NOT NULL,
          actor TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_external_ai126_case
          ON external_ai_launches_126(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS windows_shortcut_installs_126(
          install_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          desktop_path TEXT NOT NULL DEFAULT '',
          start_menu_path TEXT NOT NULL DEFAULT '',
          icon_path TEXT NOT NULL DEFAULT '',
          error_text TEXT NOT NULL DEFAULT '',
          requested_by TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS production_policy_126(
          policy_id TEXT PRIMARY KEY,
          feature_freeze INTEGER NOT NULL DEFAULT 1,
          canonical_interface TEXT NOT NULL DEFAULT 'firefox_browser_workspace',
          external_ai_data_transfer TEXT NOT NULL DEFAULT 'manual_only',
          shortcut_mode TEXT NOT NULL DEFAULT 'portable_installer',
          updated_at TEXT NOT NULL
        );
        """
    )
    db.conn.execute(
        """INSERT OR IGNORE INTO production_policy_126(
           policy_id,feature_freeze,canonical_interface,external_ai_data_transfer,shortcut_mode,updated_at)
           VALUES('phase2',1,'firefox_browser_workspace','manual_only','portable_installer',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"""
    )
    db.conn.commit()
