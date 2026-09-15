from __future__ import annotations
from typing import Any

SCHEMA_213 = r'''
CREATE TABLE IF NOT EXISTS build213_policies(
 policy_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_projects_213(
 project_id TEXT PRIMARY KEY, title TEXT NOT NULL, homepage TEXT NOT NULL, license_spdx TEXT NOT NULL,
 integration_mode TEXT NOT NULL, network_capable INTEGER NOT NULL, bundled INTEGER NOT NULL DEFAULT 0,
 fixture_ok INTEGER NOT NULL DEFAULT 0, parser_ok INTEGER NOT NULL DEFAULT 0, benchmark_ok INTEGER NOT NULL DEFAULT 0,
 live_ok INTEGER NOT NULL DEFAULT 0, terms_reviewed INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0,
 notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_definition_imports_213(
 import_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, dataset_version TEXT NOT NULL, source_hash TEXT NOT NULL,
 definition_count INTEGER NOT NULL, status TEXT NOT NULL, reviewer TEXT NOT NULL, notes TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(project_id) REFERENCES social_projects_213(project_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS social_site_definitions_213(
 definition_id TEXT PRIMARY KEY, import_id TEXT NOT NULL, project_id TEXT NOT NULL, site_key TEXT NOT NULL,
 title TEXT NOT NULL, category TEXT NOT NULL, profile_url_template TEXT NOT NULL, host TEXT NOT NULL,
 positive_rule_json TEXT NOT NULL, negative_rule_json TEXT NOT NULL, blocked_rule_json TEXT NOT NULL,
 requires_auth INTEGER NOT NULL DEFAULT 0, disabled INTEGER NOT NULL DEFAULT 0, network_risk TEXT NOT NULL,
 countries_json TEXT NOT NULL, tags_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(import_id) REFERENCES social_definition_imports_213(import_id) ON DELETE RESTRICT,
 FOREIGN KEY(project_id) REFERENCES social_projects_213(project_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_site_definitions_213_versioned ON social_site_definitions_213(import_id,site_key);
CREATE INDEX IF NOT EXISTS idx_social_site_definitions_213_project ON social_site_definitions_213(project_id,site_key);
CREATE TABLE IF NOT EXISTS social_health_checks_213(
 check_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, import_id TEXT NOT NULL, fixture_count INTEGER NOT NULL,
 true_positive INTEGER NOT NULL, false_positive INTEGER NOT NULL, true_negative INTEGER NOT NULL, false_negative INTEGER NOT NULL,
 precision REAL NOT NULL, recall REAL NOT NULL, false_positive_rate REAL NOT NULL, parser_ok INTEGER NOT NULL,
 status TEXT NOT NULL, reviewer TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(project_id) REFERENCES social_projects_213(project_id) ON DELETE RESTRICT,
 FOREIGN KEY(import_id) REFERENCES social_definition_imports_213(import_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS parallel_workspaces_213(
 workspace_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, lane_key TEXT NOT NULL, title TEXT NOT NULL,
 objective TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_parallel_workspaces_213_case_lane ON parallel_workspaces_213(case_id,lane_key);
CREATE TABLE IF NOT EXISTS social_research_plans_213(
 plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, username TEXT NOT NULL, question TEXT NOT NULL,
 definition_ids_json TEXT NOT NULL, tab_orders_json TEXT NOT NULL, task_ids_json TEXT NOT NULL,
 status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS social_tasks_213(
 task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, workspace_id TEXT NOT NULL, plan_id TEXT NOT NULL,
 definition_id TEXT NOT NULL, target_type TEXT NOT NULL, target_value TEXT NOT NULL, public_url TEXT NOT NULL,
 mode TEXT NOT NULL, status TEXT NOT NULL, candidate_only INTEGER NOT NULL DEFAULT 1, network_execution INTEGER NOT NULL DEFAULT 0,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(workspace_id) REFERENCES parallel_workspaces_213(workspace_id) ON DELETE RESTRICT,
 FOREIGN KEY(definition_id) REFERENCES social_site_definitions_213(definition_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_social_tasks_213_case ON social_tasks_213(case_id,status,created_at);
CREATE TABLE IF NOT EXISTS social_candidates_213(
 candidate_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT NOT NULL, definition_id TEXT NOT NULL,
 project_id TEXT NOT NULL, site_key TEXT NOT NULL, target_value TEXT NOT NULL, profile_url TEXT NOT NULL,
 existence_state TEXT NOT NULL, display_name TEXT NOT NULL, bio_original TEXT NOT NULL, content_language TEXT NOT NULL,
 extracted_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, collector_version TEXT NOT NULL,
 confidence REAL NOT NULL, limitations_json TEXT NOT NULL, observed_at TEXT NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(task_id) REFERENCES social_tasks_213(task_id) ON DELETE RESTRICT,
 FOREIGN KEY(definition_id) REFERENCES social_site_definitions_213(definition_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_candidates_213_unique ON social_candidates_213(case_id,definition_id,target_value,observed_at);
CREATE TABLE IF NOT EXISTS social_candidate_reviews_213(
 review_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, candidate_id TEXT NOT NULL, reviewer TEXT NOT NULL,
 decision TEXT NOT NULL, identity_relation TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(candidate_id) REFERENCES social_candidates_213(candidate_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS social_content_translations_213(
 translation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, candidate_id TEXT NOT NULL, field_name TEXT NOT NULL,
 original_language TEXT NOT NULL, target_language TEXT NOT NULL, original_text TEXT NOT NULL, translated_text TEXT NOT NULL,
 engine TEXT NOT NULL, engine_version TEXT NOT NULL, glossary_json TEXT NOT NULL, uncertainties_json TEXT NOT NULL,
 status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(candidate_id) REFERENCES social_candidates_213(candidate_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS social_chat_turns_213(
 turn_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, question_original TEXT NOT NULL, question_language TEXT NOT NULL,
 working_language TEXT NOT NULL, context_json TEXT NOT NULL, response_json TEXT NOT NULL DEFAULT '{}',
 citations_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS social_ai_feedback_213(
 feedback_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_type TEXT NOT NULL, item_id TEXT NOT NULL,
 verdict TEXT NOT NULL, dimensions_json TEXT NOT NULL, reason TEXT NOT NULL, analyst TEXT NOT NULL,
 training_eligible INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS social_platform_opsec_213(
 profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, site_key TEXT NOT NULL, threat_level TEXT NOT NULL,
 controls_json TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS social_preflights_213(
 preflight_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, task_id TEXT NOT NULL, site_key TEXT NOT NULL,
 requested_json TEXT NOT NULL, controls_json TEXT NOT NULL, risks_json TEXT NOT NULL, decision TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(task_id) REFERENCES social_tasks_213(task_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS build213_events(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
 object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build213_events_case ON build213_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_social_candidates_213_no_update BEFORE UPDATE ON social_candidates_213 BEGIN SELECT RAISE(ABORT,'social_candidates_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social_candidates_213_no_delete BEFORE DELETE ON social_candidates_213 BEGIN SELECT RAISE(ABORT,'social_candidates_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social_candidate_reviews_213_no_update BEFORE UPDATE ON social_candidate_reviews_213 BEGIN SELECT RAISE(ABORT,'social_candidate_reviews_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social_candidate_reviews_213_no_delete BEFORE DELETE ON social_candidate_reviews_213 BEGIN SELECT RAISE(ABORT,'social_candidate_reviews_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social_content_translations_213_no_update BEFORE UPDATE ON social_content_translations_213 BEGIN SELECT RAISE(ABORT,'social_content_translations_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_social_content_translations_213_no_delete BEFORE DELETE ON social_content_translations_213 BEGIN SELECT RAISE(ABORT,'social_content_translations_213 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build213_events_no_update BEFORE UPDATE ON build213_events BEGIN SELECT RAISE(ABORT,'build213_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build213_events_no_delete BEFORE DELETE ON build213_events BEGIN SELECT RAISE(ABORT,'build213_events is immutable'); END;
'''


def ensure_build213_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_213)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','213.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','213.0')")
    db.conn.commit()
