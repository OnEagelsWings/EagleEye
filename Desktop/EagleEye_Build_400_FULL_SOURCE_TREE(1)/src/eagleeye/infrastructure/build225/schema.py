from __future__ import annotations

from typing import Any

SCHEMA_225 = r'''
CREATE TABLE IF NOT EXISTS retrieval_claims_225(
 claim_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 source_statement_id TEXT NOT NULL DEFAULT '',
 subject_ref TEXT NOT NULL,
 predicate TEXT NOT NULL,
 canonical_text TEXT NOT NULL,
 normalized_value_json TEXT NOT NULL DEFAULT '{}',
 language TEXT NOT NULL DEFAULT 'und',
 claim_kind TEXT NOT NULL,
 confidence REAL NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'candidate',
 first_seen TEXT NOT NULL DEFAULT '',
 last_seen TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(claim_kind IN ('observation','inference','hypothesis','question')),
 CHECK(confidence >= 0 AND confidence <= 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_claims_225_source ON retrieval_claims_225(case_id,source_statement_id) WHERE source_statement_id <> '';
CREATE INDEX IF NOT EXISTS idx_retrieval_claims_225_case ON retrieval_claims_225(case_id,review_status,predicate,updated_at);

CREATE TABLE IF NOT EXISTS source_lineage_nodes_225(
 node_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL,
 origin_key TEXT NOT NULL,
 independence_group TEXT NOT NULL,
 canonical_url TEXT NOT NULL DEFAULT '',
 title TEXT NOT NULL DEFAULT '',
 content_sha256 TEXT NOT NULL DEFAULT '',
 observed_at TEXT NOT NULL DEFAULT '',
 source_quality REAL NOT NULL DEFAULT 0.5,
 status TEXT NOT NULL DEFAULT 'active',
 metadata_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(source_quality >= 0 AND source_quality <= 1),
 UNIQUE(case_id,source_ref,source_type)
);
CREATE INDEX IF NOT EXISTS idx_source_lineage_nodes_225_case ON source_lineage_nodes_225(case_id,independence_group,status);

CREATE TABLE IF NOT EXISTS source_lineage_edges_225(
 edge_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 parent_node_id TEXT NOT NULL,
 child_node_id TEXT NOT NULL,
 relation_type TEXT NOT NULL,
 confidence REAL NOT NULL,
 basis TEXT NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'candidate',
 reviewed_by TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(parent_node_id) REFERENCES source_lineage_nodes_225(node_id) ON DELETE CASCADE,
 FOREIGN KEY(child_node_id) REFERENCES source_lineage_nodes_225(node_id) ON DELETE CASCADE,
 CHECK(parent_node_id <> child_node_id),
 CHECK(relation_type IN ('direct_copy','quotation','summary','derived','same_origin','independent','unknown')),
 CHECK(confidence >= 0 AND confidence <= 1),
 UNIQUE(case_id,parent_node_id,child_node_id,relation_type)
);
CREATE INDEX IF NOT EXISTS idx_source_lineage_edges_225_case ON source_lineage_edges_225(case_id,relation_type,review_status);

CREATE TABLE IF NOT EXISTS claim_evidence_links_225(
 link_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 claim_id TEXT NOT NULL,
 source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL,
 lineage_node_id TEXT NOT NULL DEFAULT '',
 stance TEXT NOT NULL,
 strength REAL NOT NULL,
 temporal_relation TEXT NOT NULL DEFAULT 'unknown',
 rationale TEXT NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'candidate',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(claim_id) REFERENCES retrieval_claims_225(claim_id) ON DELETE CASCADE,
 CHECK(stance IN ('supports','contradicts','context','unknown')),
 CHECK(temporal_relation IN ('current','historical','superseded','unknown')),
 CHECK(strength >= 0 AND strength <= 1),
 UNIQUE(case_id,claim_id,source_ref,stance)
);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_links_225_claim ON claim_evidence_links_225(case_id,claim_id,stance,review_status);

CREATE TABLE IF NOT EXISTS retrieval_runs_225(
 retrieval_run_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 target_claim_id TEXT NOT NULL DEFAULT '',
 query_text TEXT NOT NULL,
 query_language TEXT NOT NULL,
 retrieval_mode TEXT NOT NULL,
 selected_refs_json TEXT NOT NULL,
 supporting_refs_json TEXT NOT NULL,
 contradicting_refs_json TEXT NOT NULL,
 context_refs_json TEXT NOT NULL,
 score_details_json TEXT NOT NULL,
 source_diversity REAL NOT NULL,
 lineage_diversity REAL NOT NULL,
 counterevidence_included INTEGER NOT NULL DEFAULT 0,
 candidate_count INTEGER NOT NULL,
 selected_count INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(session_id) REFERENCES ai_chat_sessions_216(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_retrieval_runs_225_session ON retrieval_runs_225(session_id,created_at);

CREATE TABLE IF NOT EXISTS retrieval_results_225(
 result_id TEXT PRIMARY KEY,
 retrieval_run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL,
 stance TEXT NOT NULL,
 final_score REAL NOT NULL,
 lexical_score REAL NOT NULL,
 semantic_score REAL,
 entity_score REAL NOT NULL,
 temporal_score REAL NOT NULL,
 quality_score REAL NOT NULL,
 independence_score REAL NOT NULL,
 lineage_penalty REAL NOT NULL,
 contradiction_bonus REAL NOT NULL,
 rank_position INTEGER NOT NULL,
 selected INTEGER NOT NULL DEFAULT 0,
 explanation_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(retrieval_run_id) REFERENCES retrieval_runs_225(retrieval_run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(final_score >= 0),
 CHECK(selected IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_retrieval_results_225_run ON retrieval_results_225(retrieval_run_id,selected,rank_position);

CREATE TABLE IF NOT EXISTS retrieval_reviews_225(
 review_id TEXT PRIMARY KEY,
 retrieval_run_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 decision TEXT NOT NULL,
 correct_refs_json TEXT NOT NULL,
 missing_refs_json TEXT NOT NULL,
 wrongly_ranked_refs_json TEXT NOT NULL,
 rationale TEXT NOT NULL,
 training_example_id TEXT NOT NULL DEFAULT '',
 reviewer TEXT NOT NULL,
 reviewed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(retrieval_run_id) REFERENCES retrieval_runs_225(retrieval_run_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('useful','partially_useful','misleading','insufficient'))
);
CREATE INDEX IF NOT EXISTS idx_retrieval_reviews_225_run ON retrieval_reviews_225(retrieval_run_id,reviewed_at);

CREATE TABLE IF NOT EXISTS build225_events(
 event_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 object_type TEXT NOT NULL,
 object_id TEXT NOT NULL,
 actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build225_events_case ON build225_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_retrieval_runs_225_no_update BEFORE UPDATE ON retrieval_runs_225 BEGIN SELECT RAISE(ABORT,'retrieval_runs_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_retrieval_runs_225_no_delete BEFORE DELETE ON retrieval_runs_225 BEGIN SELECT RAISE(ABORT,'retrieval_runs_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_retrieval_results_225_no_update BEFORE UPDATE ON retrieval_results_225 BEGIN SELECT RAISE(ABORT,'retrieval_results_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_retrieval_results_225_no_delete BEFORE DELETE ON retrieval_results_225 BEGIN SELECT RAISE(ABORT,'retrieval_results_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_retrieval_reviews_225_no_update BEFORE UPDATE ON retrieval_reviews_225 BEGIN SELECT RAISE(ABORT,'retrieval_reviews_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_retrieval_reviews_225_no_delete BEFORE DELETE ON retrieval_reviews_225 BEGIN SELECT RAISE(ABORT,'retrieval_reviews_225 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build225_events_no_update BEFORE UPDATE ON build225_events BEGIN SELECT RAISE(ABORT,'build225_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build225_events_no_delete BEFORE DELETE ON build225_events BEGIN SELECT RAISE(ABORT,'build225_events is immutable'); END;
'''


def ensure_build225_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_225)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','225.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','225.0')")
    db.conn.commit()
