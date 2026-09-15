from __future__ import annotations

from typing import Any


def ensure_capture_identity_schema_129(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS capture_tickets_129(
          ticket_id TEXT PRIMARY KEY,
          ticket_hash TEXT UNIQUE NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          purpose TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'issued',
          issued_by TEXT NOT NULL,
          issued_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          used_at TEXT NOT NULL DEFAULT '',
          client_origin_hash TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_capture_tickets129_case
          ON capture_tickets_129(case_id,state,expires_at);

        CREATE TABLE IF NOT EXISTS browser_captures_129(
          capture_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          ticket_id TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          source_host TEXT NOT NULL,
          title TEXT NOT NULL,
          capture_mode TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'candidate_captured',
          visible_text_sha256 TEXT NOT NULL,
          html_sha256 TEXT NOT NULL DEFAULT '',
          screenshot_sha256 TEXT NOT NULL DEFAULT '',
          manifest_sha256 TEXT NOT NULL,
          bundle_relpath TEXT NOT NULL,
          evidence_package_id TEXT NOT NULL DEFAULT '',
          previous_capture_id TEXT NOT NULL DEFAULT '',
          change_state TEXT NOT NULL DEFAULT 'first_capture',
          injection_flags_json TEXT NOT NULL DEFAULT '[]',
          artifact_count INTEGER NOT NULL DEFAULT 0,
          byte_size INTEGER NOT NULL DEFAULT 0,
          captured_by TEXT NOT NULL,
          captured_at TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_browser_captures129_case
          ON browser_captures_129(case_id,target_id,captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_browser_captures129_url
          ON browser_captures_129(case_id,canonical_url,captured_at DESC);

        CREATE TABLE IF NOT EXISTS capture_artifacts_129(
          artifact_id TEXT PRIMARY KEY,
          capture_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          filename TEXT NOT NULL,
          media_type TEXT NOT NULL,
          relpath TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          byte_size INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(capture_id,artifact_kind,filename),
          FOREIGN KEY(capture_id) REFERENCES browser_captures_129(capture_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_capture_artifacts129_capture
          ON capture_artifacts_129(capture_id,artifact_kind);

        CREATE TABLE IF NOT EXISTS capture_changes_129(
          change_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          canonical_url TEXT NOT NULL,
          previous_capture_id TEXT NOT NULL,
          current_capture_id TEXT NOT NULL,
          change_state TEXT NOT NULL,
          changed_artifacts_json TEXT NOT NULL DEFAULT '[]',
          summary_json TEXT NOT NULL DEFAULT '{}',
          review_status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(previous_capture_id) REFERENCES browser_captures_129(capture_id) ON DELETE CASCADE,
          FOREIGN KEY(current_capture_id) REFERENCES browser_captures_129(capture_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_capture_changes129_case
          ON capture_changes_129(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS identity_hypotheses_129(
          hypothesis_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          left_entity_id TEXT NOT NULL,
          right_entity_id TEXT NOT NULL,
          base_comparison_id TEXT NOT NULL DEFAULT '',
          state TEXT NOT NULL DEFAULT 'candidate',
          recommendation TEXT NOT NULL,
          precision_policy TEXT NOT NULL DEFAULT 'false_merge_averse',
          positive_component_count INTEGER NOT NULL DEFAULT 0,
          conflict_component_count INTEGER NOT NULL DEFAULT 0,
          independent_source_count INTEGER NOT NULL DEFAULT 0,
          explanation_json TEXT NOT NULL,
          ai_brief_id TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          reviewed_by TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL DEFAULT '',
          review_decision TEXT NOT NULL DEFAULT '',
          review_reason TEXT NOT NULL DEFAULT '',
          UNIQUE(case_id,left_entity_id,right_entity_id),
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_identity_hypotheses129_case
          ON identity_hypotheses_129(case_id,state,created_at DESC);

        CREATE TABLE IF NOT EXISTS identity_components_129(
          component_id TEXT PRIMARY KEY,
          hypothesis_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          component_type TEXT NOT NULL,
          direction TEXT NOT NULL,
          weight REAL NOT NULL,
          value REAL NOT NULL,
          rationale TEXT NOT NULL,
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL,
          FOREIGN KEY(hypothesis_id) REFERENCES identity_hypotheses_129(hypothesis_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_identity_components129_hypothesis
          ON identity_components_129(hypothesis_id,direction,weight DESC);

        CREATE TABLE IF NOT EXISTS identity_ai_suggestions_129(
          suggestion_id TEXT PRIMARY KEY,
          hypothesis_id TEXT NOT NULL DEFAULT '',
          capture_id TEXT NOT NULL DEFAULT '',
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          suggestion_type TEXT NOT NULL,
          content_json TEXT NOT NULL,
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          model_key TEXT NOT NULL DEFAULT 'deterministic_identity129',
          model_version TEXT NOT NULL DEFAULT '1.0',
          prompt_version TEXT NOT NULL DEFAULT '129.0',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_identity_ai129_case
          ON identity_ai_suggestions_129(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS identity_benchmark_runs_129(
          benchmark_id TEXT PRIMARY KEY,
          suite_version TEXT NOT NULL,
          case_count INTEGER NOT NULL,
          true_positive INTEGER NOT NULL,
          false_positive INTEGER NOT NULL,
          true_negative INTEGER NOT NULL,
          false_negative INTEGER NOT NULL,
          precision REAL NOT NULL,
          recall REAL NOT NULL,
          false_merge_rate REAL NOT NULL,
          result_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS opsec_events_129(
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          action_type TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL DEFAULT '',
          public_host TEXT NOT NULL DEFAULT '',
          value_fingerprint TEXT NOT NULL DEFAULT '',
          data_minimization_json TEXT NOT NULL DEFAULT '{}',
          outcome TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_opsec129_case
          ON opsec_events_129(case_id,created_at DESC);
        """
    )
    db.conn.commit()
