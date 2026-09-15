from __future__ import annotations

from typing import Any


def ensure_reliability_schema_125(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reliability_startup_sessions_125(
          session_id TEXT PRIMARY KEY,
          process_id INTEGER NOT NULL,
          started_at TEXT NOT NULL,
          heartbeat_at TEXT NOT NULL,
          clean_shutdown INTEGER NOT NULL DEFAULT 0,
          recovered_at TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_reliability_startup125_state
          ON reliability_startup_sessions_125(clean_shutdown,heartbeat_at DESC);

        CREATE TABLE IF NOT EXISTS reliability_operations_125(
          operation_id TEXT PRIMARY KEY,
          case_id TEXT,
          operation_type TEXT NOT NULL,
          idempotency_key TEXT NOT NULL DEFAULT '',
          state TEXT NOT NULL,
          attempt INTEGER NOT NULL DEFAULT 1,
          started_at TEXT NOT NULL,
          heartbeat_at TEXT NOT NULL,
          completed_at TEXT NOT NULL DEFAULT '',
          error_text TEXT NOT NULL DEFAULT '',
          result_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_reliability_operation125_idempotency
          ON reliability_operations_125(case_id,operation_type,idempotency_key)
          WHERE idempotency_key <> '';
        CREATE INDEX IF NOT EXISTS idx_reliability_operations125_state
          ON reliability_operations_125(state,heartbeat_at);

        CREATE TABLE IF NOT EXISTS reliability_backups_125(
          backup_id TEXT PRIMARY KEY,
          case_id TEXT,
          file_name TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL,
          encrypted INTEGER NOT NULL DEFAULT 1,
          includes_evidence INTEGER NOT NULL DEFAULT 1,
          package_sha256 TEXT NOT NULL,
          plaintext_sha256 TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          schema_version TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          verified_at TEXT NOT NULL DEFAULT '',
          verification_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reliability_backups125_created
          ON reliability_backups_125(created_at DESC);

        CREATE TABLE IF NOT EXISTS reliability_integrity_runs_125(
          run_id TEXT PRIMARY KEY,
          case_id TEXT,
          status TEXT NOT NULL,
          score INTEGER NOT NULL,
          issue_count INTEGER NOT NULL,
          report_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_reliability_integrity125_case
          ON reliability_integrity_runs_125(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS reliability_restore_stages_125(
          stage_id TEXT PRIMARY KEY,
          backup_id TEXT NOT NULL,
          stage_relpath TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL,
          database_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          verified_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(backup_id) REFERENCES reliability_backups_125(backup_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reliability_fault_events_125(
          fault_id TEXT PRIMARY KEY,
          case_id TEXT,
          fault_type TEXT NOT NULL,
          severity TEXT NOT NULL,
          component TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          resolved INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          resolved_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_reliability_faults125_case
          ON reliability_fault_events_125(case_id,resolved,created_at DESC);

        CREATE TABLE IF NOT EXISTS reliability_performance_gates_125(
          gate_id TEXT PRIMARY KEY,
          operation TEXT NOT NULL,
          budget_ms REAL NOT NULL,
          observed_ms REAL NOT NULL,
          within_budget INTEGER NOT NULL,
          sample_count INTEGER NOT NULL DEFAULT 1,
          details_json TEXT NOT NULL DEFAULT '{}',
          measured_at TEXT NOT NULL
        );
        """
    )
    db.conn.commit()
