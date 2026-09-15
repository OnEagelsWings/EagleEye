from __future__ import annotations


def ensure_synthesis_schema_131(db) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS synthesis_runs_131(
          run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          objective TEXT NOT NULL,
          status TEXT NOT NULL,
          snapshot_sha256 TEXT NOT NULL,
          inventory_json TEXT NOT NULL,
          limitations_json TEXT NOT NULL,
          model_key TEXT NOT NULL,
          model_version TEXT NOT NULL,
          trust_state TEXT NOT NULL,
          external_actions INTEGER NOT NULL DEFAULT 0,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_runs_case
          ON synthesis_runs_131(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS intelligence_gaps_131(
          gap_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          gap_type TEXT NOT NULL,
          title TEXT NOT NULL,
          rationale TEXT NOT NULL,
          priority INTEGER NOT NULL,
          recommended_action TEXT NOT NULL,
          object_refs_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES synthesis_runs_131(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_gaps_case
          ON intelligence_gaps_131(case_id,status,priority DESC,created_at DESC);

        CREATE TABLE IF NOT EXISTS report_drafts_131(
          report_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          report_type TEXT NOT NULL,
          status TEXT NOT NULL,
          trust_state TEXT NOT NULL,
          snapshot_sha256 TEXT NOT NULL,
          current_snapshot_sha256 TEXT NOT NULL,
          stale INTEGER NOT NULL DEFAULT 0,
          stale_reason TEXT NOT NULL DEFAULT '',
          version_no INTEGER NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          reviewed_by TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL DEFAULT '',
          review_decision TEXT NOT NULL DEFAULT '',
          review_reason TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(run_id) REFERENCES synthesis_runs_131(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_reports_case
          ON report_drafts_131(case_id,status,updated_at DESC);

        CREATE TABLE IF NOT EXISTS report_sections_131(
          section_id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          sequence_no INTEGER NOT NULL,
          section_key TEXT NOT NULL,
          heading TEXT NOT NULL,
          body TEXT NOT NULL,
          object_refs_json TEXT NOT NULL,
          epistemic_state TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(report_id,section_key),
          FOREIGN KEY(report_id) REFERENCES report_drafts_131(report_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_sections_report
          ON report_sections_131(report_id,sequence_no);

        CREATE TABLE IF NOT EXISTS report_claims_131(
          claim_id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          section_key TEXT NOT NULL,
          claim_text TEXT NOT NULL,
          claim_type TEXT NOT NULL,
          epistemic_state TEXT NOT NULL,
          verification_state TEXT NOT NULL,
          support_refs_json TEXT NOT NULL,
          contradiction_refs_json TEXT NOT NULL,
          independent_support_count INTEGER NOT NULL DEFAULT 0,
          warning TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(report_id) REFERENCES report_drafts_131(report_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_claims_report
          ON report_claims_131(report_id,verification_state,section_key);

        CREATE TABLE IF NOT EXISTS synthesis_ai_suggestions_131(
          suggestion_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          report_id TEXT NOT NULL DEFAULT '',
          case_id TEXT NOT NULL,
          suggestion_type TEXT NOT NULL,
          content_json TEXT NOT NULL,
          object_refs_json TEXT NOT NULL,
          trust_state TEXT NOT NULL,
          review_status TEXT NOT NULL,
          model_key TEXT NOT NULL,
          model_version TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES synthesis_runs_131(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_ai_case
          ON synthesis_ai_suggestions_131(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS report_reviews_131(
          review_id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          reason TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(report_id) REFERENCES report_drafts_131(report_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_reviews_report
          ON report_reviews_131(report_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS synthesis_opsec_events_131(
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          action_type TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL DEFAULT '',
          content_fingerprint TEXT NOT NULL DEFAULT '',
          minimization_json TEXT NOT NULL,
          outcome TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_syn131_opsec_case
          ON synthesis_opsec_events_131(case_id,created_at DESC);
        """
    )
    db.conn.commit()
