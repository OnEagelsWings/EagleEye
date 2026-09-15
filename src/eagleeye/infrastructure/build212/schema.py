from __future__ import annotations
from typing import Any

SCHEMA_212 = r'''
CREATE TABLE IF NOT EXISTS build212_policies(
 policy_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_extensions_212(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, project_type TEXT NOT NULL, homepage TEXT NOT NULL, license_spdx TEXT NOT NULL,
 integration_mode TEXT NOT NULL, capabilities_json TEXT NOT NULL, network_capable INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 0,
 fixture_ok INTEGER NOT NULL DEFAULT 0, parser_ok INTEGER NOT NULL DEFAULT 0, live_ok INTEGER NOT NULL DEFAULT 0,
 terms_reviewed INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identity_records_212(
 record_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_ref TEXT NOT NULL, record_ref TEXT NOT NULL, fields_json TEXT NOT NULL,
 normalized_json TEXT NOT NULL, provenance_refs_json TEXT NOT NULL, source_reliability REAL NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_identity_records_212_case ON identity_records_212(case_id,created_at);
CREATE TABLE IF NOT EXISTS identity_comparisons_212(
 comparison_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, left_record_id TEXT NOT NULL, right_record_id TEXT NOT NULL,
 engine TEXT NOT NULL, model_snapshot_id TEXT NOT NULL DEFAULT '', feature_scores_json TEXT NOT NULL, contributions_json TEXT NOT NULL,
 hard_conflicts_json TEXT NOT NULL, score REAL NOT NULL, probability REAL NOT NULL, candidate_state TEXT NOT NULL,
 automatic_merge INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(left_record_id) REFERENCES identity_records_212(record_id) ON DELETE RESTRICT,
 FOREIGN KEY(right_record_id) REFERENCES identity_records_212(record_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_comparisons_212_pair ON identity_comparisons_212(case_id,left_record_id,right_record_id,model_snapshot_id);
CREATE TABLE IF NOT EXISTS identity_reviews_212(
 review_id TEXT PRIMARY KEY, comparison_id TEXT NOT NULL, case_id TEXT NOT NULL, reviewer TEXT NOT NULL, reviewer_role TEXT NOT NULL,
 decision TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(comparison_id) REFERENCES identity_comparisons_212(comparison_id) ON DELETE RESTRICT,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 CHECK(decision IN ('match','no_match','uncertain'))
);
CREATE INDEX IF NOT EXISTS idx_identity_reviews_212_comparison ON identity_reviews_212(comparison_id,created_at);
CREATE TABLE IF NOT EXISTS identity_groups_212(
 group_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, label TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS identity_membership_events_212(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, group_id TEXT NOT NULL, record_id TEXT NOT NULL, action TEXT NOT NULL,
 comparison_id TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(group_id) REFERENCES identity_groups_212(group_id) ON DELETE RESTRICT,
 FOREIGN KEY(record_id) REFERENCES identity_records_212(record_id) ON DELETE RESTRICT,
 CHECK(action IN ('attach','detach'))
);
CREATE INDEX IF NOT EXISTS idx_identity_membership_events_212_group ON identity_membership_events_212(group_id,record_id,created_at);
CREATE TABLE IF NOT EXISTS er_training_examples_212(
 example_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, comparison_id TEXT NOT NULL, label TEXT NOT NULL, source TEXT NOT NULL,
 analyst TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(comparison_id) REFERENCES identity_comparisons_212(comparison_id) ON DELETE RESTRICT,
 CHECK(label IN ('match','no_match'))
);
CREATE TABLE IF NOT EXISTS er_calibration_snapshots_212(
 snapshot_id TEXT PRIMARY KEY, name TEXT NOT NULL, example_count INTEGER NOT NULL, match_count INTEGER NOT NULL, no_match_count INTEGER NOT NULL,
 weights_json TEXT NOT NULL, metrics_json TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, approved_by TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, approved_at TEXT NOT NULL DEFAULT '', payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_translations_212(
 translation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL DEFAULT '', original_language TEXT NOT NULL,
 target_language TEXT NOT NULL, original_text TEXT NOT NULL, translated_text TEXT NOT NULL, engine TEXT NOT NULL, engine_version TEXT NOT NULL,
 glossary_json TEXT NOT NULL, uncertainties_json TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_case_translations_212_case ON case_translations_212(case_id,created_at);
CREATE TABLE IF NOT EXISTS investigator_chat_turns_212(
 turn_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, ai_run_id TEXT NOT NULL DEFAULT '', question_original TEXT NOT NULL,
 question_language TEXT NOT NULL, working_language TEXT NOT NULL, translated_question TEXT NOT NULL,
 context_json TEXT NOT NULL, response_json TEXT NOT NULL DEFAULT '{}', citations_json TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ai_feedback_212(
 feedback_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_type TEXT NOT NULL, item_id TEXT NOT NULL, verdict TEXT NOT NULL,
 dimensions_json TEXT NOT NULL, reason TEXT NOT NULL, analyst TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS opsec_profiles_212(
 profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, threat_level TEXT NOT NULL, environment TEXT NOT NULL, controls_json TEXT NOT NULL,
 safety_lock INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_opsec_profiles_212_case ON opsec_profiles_212(case_id,created_at);
CREATE TABLE IF NOT EXISTS opsec_preflights_212(
 preflight_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action_type TEXT NOT NULL, source_id TEXT NOT NULL DEFAULT '',
 requested_json TEXT NOT NULL, effective_controls_json TEXT NOT NULL, risks_json TEXT NOT NULL, decision TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS build212_events(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
 actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build212_events_case ON build212_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_identity_records_212_no_update BEFORE UPDATE ON identity_records_212 BEGIN SELECT RAISE(ABORT,'identity_records_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_records_212_no_delete BEFORE DELETE ON identity_records_212 BEGIN SELECT RAISE(ABORT,'identity_records_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_comparisons_212_no_update BEFORE UPDATE ON identity_comparisons_212 BEGIN SELECT RAISE(ABORT,'identity_comparisons_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_comparisons_212_no_delete BEFORE DELETE ON identity_comparisons_212 BEGIN SELECT RAISE(ABORT,'identity_comparisons_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_reviews_212_no_update BEFORE UPDATE ON identity_reviews_212 BEGIN SELECT RAISE(ABORT,'identity_reviews_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_reviews_212_no_delete BEFORE DELETE ON identity_reviews_212 BEGIN SELECT RAISE(ABORT,'identity_reviews_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_case_translations_212_no_update BEFORE UPDATE ON case_translations_212 BEGIN SELECT RAISE(ABORT,'case_translations_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_case_translations_212_no_delete BEFORE DELETE ON case_translations_212 BEGIN SELECT RAISE(ABORT,'case_translations_212 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build212_events_no_update BEFORE UPDATE ON build212_events BEGIN SELECT RAISE(ABORT,'build212_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build212_events_no_delete BEFORE DELETE ON build212_events BEGIN SELECT RAISE(ABORT,'build212_events is immutable'); END;
'''

def ensure_build212_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_212)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','212.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','212.0')")
    db.conn.commit()
