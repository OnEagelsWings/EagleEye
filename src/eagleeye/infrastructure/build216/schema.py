from __future__ import annotations
from typing import Any

SCHEMA_216 = r'''
CREATE TABLE IF NOT EXISTS ai_chat_sessions_216(
 session_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 title TEXT NOT NULL,
 working_language TEXT NOT NULL,
 selected_model TEXT NOT NULL DEFAULT '',
 embedding_model TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'active',
 short_memory_json TEXT NOT NULL DEFAULT '{}',
 long_memory_json TEXT NOT NULL DEFAULT '[]',
 source_policy_json TEXT NOT NULL DEFAULT '{}',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_216_case ON ai_chat_sessions_216(case_id,updated_at);

CREATE TABLE IF NOT EXISTS ai_chat_messages_216(
 message_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 parent_message_id TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL,
 content_original TEXT NOT NULL,
 content_language TEXT NOT NULL,
 content_working TEXT NOT NULL,
 evidence_refs_json TEXT NOT NULL DEFAULT '[]',
 response_sections_json TEXT NOT NULL DEFAULT '{}',
 retrieval_run_id TEXT NOT NULL DEFAULT '',
 source_grounding_score REAL NOT NULL DEFAULT 0,
 review_status TEXT NOT NULL DEFAULT 'not_required',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(session_id) REFERENCES ai_chat_sessions_216(session_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(role IN ('system','user','assistant','tool')),
 CHECK(source_grounding_score >= 0 AND source_grounding_score <= 1)
);
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_216_session ON ai_chat_messages_216(session_id,created_at);

CREATE TABLE IF NOT EXISTS ai_memory_chunks_216(
 chunk_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL,
 independence_key TEXT NOT NULL,
 title TEXT NOT NULL,
 content TEXT NOT NULL,
 language TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 quality_score REAL NOT NULL,
 contradiction_signal INTEGER NOT NULL DEFAULT 0,
 embedding_model TEXT NOT NULL DEFAULT '',
 embedding_json TEXT NOT NULL DEFAULT '[]',
 lexical_terms_json TEXT NOT NULL DEFAULT '[]',
 metadata_json TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,source_ref,source_type),
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(quality_score >= 0 AND quality_score <= 1)
);
CREATE INDEX IF NOT EXISTS idx_ai_memory_chunks_216_case ON ai_memory_chunks_216(case_id,status,source_type);

CREATE TABLE IF NOT EXISTS ai_retrieval_runs_216(
 retrieval_run_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 query_text TEXT NOT NULL,
 query_language TEXT NOT NULL,
 retrieval_mode TEXT NOT NULL,
 selected_refs_json TEXT NOT NULL,
 score_details_json TEXT NOT NULL,
 source_type_counts_json TEXT NOT NULL,
 source_diversity REAL NOT NULL,
 contradiction_included INTEGER NOT NULL DEFAULT 0,
 candidate_count INTEGER NOT NULL,
 selected_count INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(session_id) REFERENCES ai_chat_sessions_216(session_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ai_retrieval_runs_216_session ON ai_retrieval_runs_216(session_id,created_at);

CREATE TABLE IF NOT EXISTS ai_embedding_models_216(
 snapshot_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 digest TEXT NOT NULL DEFAULT '',
 details_json TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ai_embedding_models_216_case ON ai_embedding_models_216(case_id,observed_at);

CREATE TABLE IF NOT EXISTS source_quality_labels_216(
 label_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL,
 authority_score REAL NOT NULL,
 traceability_score REAL NOT NULL,
 independence_score REAL NOT NULL,
 freshness_score REAL NOT NULL,
 stability_score REAL NOT NULL,
 precision_score REAL NOT NULL,
 overall_score REAL NOT NULL,
 strengths_json TEXT NOT NULL,
 weaknesses_json TEXT NOT NULL,
 rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'reviewed',
 labelled_by TEXT NOT NULL,
 labelled_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_quality_labels_216_ref ON source_quality_labels_216(case_id,source_ref,labelled_at);

CREATE TABLE IF NOT EXISTS ai_training_examples_216(
 example_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 task_type TEXT NOT NULL,
 language TEXT NOT NULL,
 difficulty TEXT NOT NULL,
 input_json TEXT NOT NULL,
 expected_output_json TEXT NOT NULL,
 evidence_refs_json TEXT NOT NULL,
 source_quality_json TEXT NOT NULL,
 negative_constraints_json TEXT NOT NULL,
 label TEXT NOT NULL,
 rationale TEXT NOT NULL,
 split_name TEXT NOT NULL,
 status TEXT NOT NULL,
 created_by TEXT NOT NULL,
 reviewed_by TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(split_name IN ('unassigned','train','validation','holdout')),
 CHECK(status IN ('draft','reviewed','rejected','exported'))
);
CREATE INDEX IF NOT EXISTS idx_ai_training_examples_216_status ON ai_training_examples_216(status,split_name,task_type);

CREATE TABLE IF NOT EXISTS ai_benchmark_cases_216(
 benchmark_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 title TEXT NOT NULL,
 task_type TEXT NOT NULL,
 prompt_text TEXT NOT NULL,
 expected_refs_json TEXT NOT NULL,
 forbidden_claims_json TEXT NOT NULL,
 expected_behaviors_json TEXT NOT NULL,
 language TEXT NOT NULL,
 difficulty TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active',
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_benchmark_results_216(
 result_id TEXT PRIMARY KEY,
 benchmark_id TEXT NOT NULL,
 case_id TEXT NOT NULL,
 model_name TEXT NOT NULL,
 answer_message_id TEXT NOT NULL,
 citation_precision REAL NOT NULL,
 citation_recall REAL NOT NULL,
 source_grounding REAL NOT NULL,
 forbidden_claim_hits INTEGER NOT NULL,
 behavior_score REAL NOT NULL,
 passed INTEGER NOT NULL,
 metrics_json TEXT NOT NULL,
 evaluated_by TEXT NOT NULL,
 evaluated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(benchmark_id) REFERENCES ai_benchmark_cases_216(benchmark_id) ON DELETE CASCADE,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_training_exports_216(
 export_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 export_path TEXT NOT NULL,
 train_count INTEGER NOT NULL,
 validation_count INTEGER NOT NULL,
 holdout_count INTEGER NOT NULL,
 manifest_sha256 TEXT NOT NULL,
 created_by TEXT NOT NULL,
 created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS build216_events(
 event_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 object_type TEXT NOT NULL,
 object_id TEXT NOT NULL,
 actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build216_events_case ON build216_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_ai_chat_messages_216_no_update BEFORE UPDATE ON ai_chat_messages_216 BEGIN SELECT RAISE(ABORT,'ai_chat_messages_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_chat_messages_216_no_delete BEFORE DELETE ON ai_chat_messages_216 BEGIN SELECT RAISE(ABORT,'ai_chat_messages_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_retrieval_runs_216_no_update BEFORE UPDATE ON ai_retrieval_runs_216 BEGIN SELECT RAISE(ABORT,'ai_retrieval_runs_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_retrieval_runs_216_no_delete BEFORE DELETE ON ai_retrieval_runs_216 BEGIN SELECT RAISE(ABORT,'ai_retrieval_runs_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_benchmark_results_216_no_update BEFORE UPDATE ON ai_benchmark_results_216 BEGIN SELECT RAISE(ABORT,'ai_benchmark_results_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_benchmark_results_216_no_delete BEFORE DELETE ON ai_benchmark_results_216 BEGIN SELECT RAISE(ABORT,'ai_benchmark_results_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_training_exports_216_no_update BEFORE UPDATE ON ai_training_exports_216 BEGIN SELECT RAISE(ABORT,'ai_training_exports_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ai_training_exports_216_no_delete BEFORE DELETE ON ai_training_exports_216 BEGIN SELECT RAISE(ABORT,'ai_training_exports_216 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build216_events_no_update BEFORE UPDATE ON build216_events BEGIN SELECT RAISE(ABORT,'build216_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build216_events_no_delete BEFORE DELETE ON build216_events BEGIN SELECT RAISE(ABORT,'build216_events is immutable'); END;
'''


def ensure_build216_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_216)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','216.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','216.0')")
    db.conn.commit()
