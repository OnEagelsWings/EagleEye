from __future__ import annotations

from typing import Any


def ensure_scale_schema_123(db: Any) -> None:
    db.conn.executescript(
"""
            CREATE TABLE IF NOT EXISTS research_anchors_123(
              anchor_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
              anchor_type TEXT NOT NULL, anchor_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
              reliability REAL NOT NULL, source_kind TEXT NOT NULL, source_id TEXT DEFAULT '',
              review_status TEXT NOT NULL DEFAULT 'reviewed', created_by TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(case_id,target_id,anchor_type,normalized_value),
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
              FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_research_anchors123_target
              ON research_anchors_123(case_id,target_id,review_status,anchor_type);
            CREATE TABLE IF NOT EXISTS research_profiles_123(
              profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
              profile_digest TEXT NOT NULL, completeness INTEGER NOT NULL,
              anchor_count INTEGER NOT NULL, type_count INTEGER NOT NULL,
              profile_json TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(case_id,target_id,profile_digest),
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
              FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_research_profiles123_target
              ON research_profiles_123(case_id,target_id,created_at DESC);
            CREATE TABLE IF NOT EXISTS adaptive_search_tasks_123(
              adaptive_id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
              target_id TEXT NOT NULL, profile_digest TEXT NOT NULL, precision_score INTEGER NOT NULL,
              anchor_count INTEGER NOT NULL, rationale TEXT NOT NULL, novelty_key TEXT NOT NULL,
              source_kind TEXT NOT NULL DEFAULT 'adaptive_profile', created_at TEXT NOT NULL,
              UNIQUE(case_id,target_id,novelty_key),
              FOREIGN KEY(task_id) REFERENCES search_tasks(task_id) ON DELETE CASCADE,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
              FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_adaptive_tasks123_case
              ON adaptive_search_tasks_123(case_id,target_id,precision_score DESC,created_at DESC);
            CREATE TABLE IF NOT EXISTS background_jobs_123(
              job_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
              job_type TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 2,
              result_json TEXT NOT NULL DEFAULT '{}', error_text TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT DEFAULT '',
              completed_at TEXT DEFAULT '', updated_at TEXT NOT NULL,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_jobs123_case
              ON background_jobs_123(case_id,status,created_at DESC);
            CREATE TABLE IF NOT EXISTS provider_diagnostics_123(
              diagnostic_id TEXT PRIMARY KEY, case_id TEXT, provider TEXT NOT NULL,
              ready INTEGER NOT NULL, detail TEXT NOT NULL, checked_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_provider_diag123
              ON provider_diagnostics_123(provider,checked_at DESC);
            CREATE TABLE IF NOT EXISTS performance_samples_123(
              sample_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, operation TEXT NOT NULL,
              elapsed_ms REAL NOT NULL, budget_ms REAL NOT NULL, within_budget INTEGER NOT NULL,
              item_count INTEGER NOT NULL DEFAULT 0, details_json TEXT NOT NULL DEFAULT '{}',
              measured_at TEXT NOT NULL,
              FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_perf_samples123_case
              ON performance_samples_123(case_id,operation,measured_at DESC);
            """
    )
    db.conn.commit()
