from __future__ import annotations

from typing import Any


def ensure_research_strategy_schema_128(db: Any) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS connector_catalog_128(
          connector_key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          connector_version TEXT NOT NULL,
          provider_key TEXT NOT NULL DEFAULT '',
          connector_type TEXT NOT NULL,
          input_types_json TEXT NOT NULL DEFAULT '[]',
          output_types_json TEXT NOT NULL DEFAULT '[]',
          execution_mode TEXT NOT NULL,
          public_only INTEGER NOT NULL DEFAULT 1,
          network_policy TEXT NOT NULL DEFAULT 'human_approved',
          query_minimization TEXT NOT NULL DEFAULT 'required',
          allowed_hosts_json TEXT NOT NULL DEFAULT '[]',
          terms_profile TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_strategy_runs_128(
          strategy_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          profile_digest TEXT NOT NULL,
          status TEXT NOT NULL,
          query_count INTEGER NOT NULL DEFAULT 0,
          connector_count INTEGER NOT NULL DEFAULT 0,
          source_count INTEGER NOT NULL DEFAULT 0,
          cluster_count INTEGER NOT NULL DEFAULT 0,
          coverage_score INTEGER NOT NULL DEFAULT 0,
          graph_digest TEXT NOT NULL DEFAULT '',
          ai_brief_id TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_strategy128_case_target
          ON research_strategy_runs_128(case_id,target_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS query_graph_nodes_128(
          node_id TEXT PRIMARY KEY,
          strategy_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          node_type TEXT NOT NULL,
          node_key TEXT NOT NULL,
          label TEXT NOT NULL,
          trust_state TEXT NOT NULL DEFAULT 'reviewed_input',
          score REAL NOT NULL DEFAULT 0,
          properties_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          UNIQUE(strategy_id,node_type,node_key),
          FOREIGN KEY(strategy_id) REFERENCES research_strategy_runs_128(strategy_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_query_nodes128_strategy
          ON query_graph_nodes_128(strategy_id,node_type,score DESC);

        CREATE TABLE IF NOT EXISTS query_graph_edges_128(
          edge_id TEXT PRIMARY KEY,
          strategy_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          source_node_id TEXT NOT NULL,
          target_node_id TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          rationale TEXT NOT NULL DEFAULT '',
          properties_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          UNIQUE(strategy_id,source_node_id,target_node_id,relation_type),
          FOREIGN KEY(strategy_id) REFERENCES research_strategy_runs_128(strategy_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(source_node_id) REFERENCES query_graph_nodes_128(node_id) ON DELETE CASCADE,
          FOREIGN KEY(target_node_id) REFERENCES query_graph_nodes_128(node_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_query_edges128_strategy
          ON query_graph_edges_128(strategy_id,relation_type);

        CREATE TABLE IF NOT EXISTS source_records_128(
          source_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          canonical_url TEXT NOT NULL DEFAULT '',
          source_host TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL DEFAULT '',
          text_fingerprint TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL DEFAULT '',
          source_role TEXT NOT NULL,
          provider_key TEXT NOT NULL DEFAULT '',
          published_at TEXT NOT NULL DEFAULT '',
          captured_at TEXT NOT NULL DEFAULT '',
          review_state TEXT NOT NULL DEFAULT 'candidate',
          independence_cluster_id TEXT NOT NULL DEFAULT '',
          provenance_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id,object_type,object_id),
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sources128_case
          ON source_records_128(case_id,target_id,source_role,source_host);
        CREATE INDEX IF NOT EXISTS idx_sources128_cluster
          ON source_records_128(case_id,independence_cluster_id);

        CREATE TABLE IF NOT EXISTS source_clusters_128(
          cluster_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          cluster_kind TEXT NOT NULL,
          representative_source_id TEXT NOT NULL,
          member_count INTEGER NOT NULL DEFAULT 1,
          independent_count INTEGER NOT NULL DEFAULT 1,
          rationale TEXT NOT NULL,
          cluster_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(representative_source_id) REFERENCES source_records_128(source_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_clusters128_case
          ON source_clusters_128(case_id,target_id,member_count DESC);

        CREATE TABLE IF NOT EXISTS research_coverage_128(
          coverage_id TEXT PRIMARY KEY,
          strategy_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          coverage_score INTEGER NOT NULL,
          source_diversity_score INTEGER NOT NULL,
          primary_source_score INTEGER NOT NULL,
          counter_evidence_score INTEGER NOT NULL,
          temporal_coverage_score INTEGER NOT NULL,
          identity_disambiguation_score INTEGER NOT NULL,
          duplicate_penalty INTEGER NOT NULL,
          independent_hosts INTEGER NOT NULL,
          source_clusters INTEGER NOT NULL,
          open_gaps_json TEXT NOT NULL DEFAULT '[]',
          covered_dimensions_json TEXT NOT NULL DEFAULT '[]',
          metrics_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          FOREIGN KEY(strategy_id) REFERENCES research_strategy_runs_128(strategy_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_coverage128_target
          ON research_coverage_128(case_id,target_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS research_ai_suggestions_128(
          suggestion_id TEXT PRIMARY KEY,
          strategy_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          suggestion_type TEXT NOT NULL,
          content_json TEXT NOT NULL,
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          trust_state TEXT NOT NULL DEFAULT 'suggestions_only',
          review_status TEXT NOT NULL DEFAULT 'pending',
          model_key TEXT NOT NULL DEFAULT 'deterministic_research128',
          model_version TEXT NOT NULL DEFAULT '1.0',
          prompt_version TEXT NOT NULL DEFAULT '128.0',
          created_at TEXT NOT NULL,
          FOREIGN KEY(strategy_id) REFERENCES research_strategy_runs_128(strategy_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(target_id) REFERENCES targets(target_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_ai_suggestions128_case
          ON research_ai_suggestions_128(case_id,target_id,review_status,created_at DESC);

        CREATE TABLE IF NOT EXISTS research_opsec_events_128(
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          target_id TEXT NOT NULL DEFAULT '',
          strategy_id TEXT NOT NULL DEFAULT '',
          action_type TEXT NOT NULL,
          connector_key TEXT NOT NULL DEFAULT '',
          query_fingerprint TEXT NOT NULL DEFAULT '',
          data_minimization_json TEXT NOT NULL DEFAULT '{}',
          network_state TEXT NOT NULL,
          outcome TEXT NOT NULL,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_opsec128_case
          ON research_opsec_events_128(case_id,created_at DESC);
        """
    )
    db.conn.commit()
