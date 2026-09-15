from __future__ import annotations


def ensure_graph_hypothesis_schema_130(db) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS graph_analysis_runs_130(
          run_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          analysis_type TEXT NOT NULL,
          status TEXT NOT NULL,
          node_count INTEGER NOT NULL,
          edge_count INTEGER NOT NULL,
          filters_json TEXT NOT NULL,
          parameters_json TEXT NOT NULL,
          summary_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_graph130_runs_case
          ON graph_analysis_runs_130(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS graph_node_metrics_130(
          metric_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          node_id TEXT NOT NULL,
          node_type TEXT NOT NULL,
          label TEXT NOT NULL,
          degree INTEGER NOT NULL,
          degree_centrality REAL NOT NULL,
          betweenness REAL NOT NULL,
          component_id TEXT NOT NULL,
          community_id TEXT NOT NULL,
          candidate_only INTEGER NOT NULL DEFAULT 1,
          details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(run_id,node_id),
          FOREIGN KEY(run_id) REFERENCES graph_analysis_runs_130(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_graph130_metrics_case
          ON graph_node_metrics_130(case_id,degree DESC,betweenness DESC);

        CREATE TABLE IF NOT EXISTS graph_paths_130(
          path_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL DEFAULT '',
          case_id TEXT NOT NULL,
          source_node_id TEXT NOT NULL,
          target_node_id TEXT NOT NULL,
          path_rank INTEGER NOT NULL,
          hop_count INTEGER NOT NULL,
          path_json TEXT NOT NULL,
          edge_path_json TEXT NOT NULL,
          explanation_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_graph130_paths_case
          ON graph_paths_130(case_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS hypotheses_130(
          hypothesis_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          statement TEXT NOT NULL,
          rationale TEXT NOT NULL,
          state TEXT NOT NULL,
          candidate_only INTEGER NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          reviewed_by TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL DEFAULT '',
          review_decision TEXT NOT NULL DEFAULT '',
          review_reason TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_hyp130_case
          ON hypotheses_130(case_id,state,updated_at DESC);

        CREATE TABLE IF NOT EXISTS hypothesis_claims_130(
          claim_id TEXT PRIMARY KEY,
          hypothesis_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          claim_type TEXT NOT NULL,
          statement TEXT NOT NULL,
          epistemic_state TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(hypothesis_id) REFERENCES hypotheses_130(hypothesis_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_hyp130_claims
          ON hypothesis_claims_130(hypothesis_id,created_at);

        CREATE TABLE IF NOT EXISTS hypothesis_evidence_130(
          link_id TEXT PRIMARY KEY,
          hypothesis_id TEXT NOT NULL,
          claim_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          stance TEXT NOT NULL,
          weight REAL NOT NULL,
          independence_group TEXT NOT NULL DEFAULT '',
          summary TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(claim_id,object_type,object_id,stance),
          FOREIGN KEY(hypothesis_id) REFERENCES hypotheses_130(hypothesis_id) ON DELETE CASCADE,
          FOREIGN KEY(claim_id) REFERENCES hypothesis_claims_130(claim_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_hyp130_evidence
          ON hypothesis_evidence_130(hypothesis_id,stance);

        CREATE TABLE IF NOT EXISTS red_team_reviews_130(
          red_team_id TEXT PRIMARY KEY,
          hypothesis_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          status TEXT NOT NULL,
          counter_hypothesis TEXT NOT NULL,
          falsification_tests_json TEXT NOT NULL,
          bias_warnings_json TEXT NOT NULL,
          source_gaps_json TEXT NOT NULL,
          trust_state TEXT NOT NULL,
          model_key TEXT NOT NULL,
          model_version TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          reviewed_by TEXT NOT NULL DEFAULT '',
          reviewed_at TEXT NOT NULL DEFAULT '',
          review_status TEXT NOT NULL DEFAULT 'pending',
          review_reason TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(hypothesis_id) REFERENCES hypotheses_130(hypothesis_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_redteam130_case
          ON red_team_reviews_130(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS graph_ai_suggestions_130(
          suggestion_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          hypothesis_id TEXT NOT NULL DEFAULT '',
          run_id TEXT NOT NULL DEFAULT '',
          suggestion_type TEXT NOT NULL,
          content_json TEXT NOT NULL,
          object_refs_json TEXT NOT NULL,
          trust_state TEXT NOT NULL,
          review_status TEXT NOT NULL,
          model_key TEXT NOT NULL,
          model_version TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_graphai130_case
          ON graph_ai_suggestions_130(case_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS opsec_events_130(
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          action_type TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL DEFAULT '',
          value_fingerprint TEXT NOT NULL DEFAULT '',
          minimization_json TEXT NOT NULL DEFAULT '{}',
          outcome TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_opsec130_case
          ON opsec_events_130(case_id,created_at DESC);
        """
    )
    db.conn.commit()
