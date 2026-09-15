from __future__ import annotations
from typing import Any

SCHEMA_214 = r'''
CREATE TABLE IF NOT EXISTS build214_policies(
 policy_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consolidated_workspaces_214(
 workspace_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, lane_key TEXT NOT NULL, title TEXT NOT NULL,
 objective TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_consolidated_workspaces_214_case_lane ON consolidated_workspaces_214(case_id,lane_key);

CREATE TABLE IF NOT EXISTS ontology_entities_214(
 entity_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_type TEXT NOT NULL, label TEXT NOT NULL,
 properties_json TEXT NOT NULL, source_refs_json TEXT NOT NULL, language TEXT NOT NULL,
 confidence REAL NOT NULL, review_status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ontology_entities_214_case_type ON ontology_entities_214(case_id,entity_type,created_at);
CREATE TABLE IF NOT EXISTS ontology_relations_214(
 relation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_entity_id TEXT NOT NULL, target_entity_id TEXT NOT NULL,
 relation_type TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, observed_at TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, confidence REAL NOT NULL, review_status TEXT NOT NULL,
 contradiction_status TEXT NOT NULL, notes TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(source_entity_id) REFERENCES ontology_entities_214(entity_id) ON DELETE RESTRICT,
 FOREIGN KEY(target_entity_id) REFERENCES ontology_entities_214(entity_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_ontology_relations_214_case ON ontology_relations_214(case_id,relation_type,observed_at);

CREATE TABLE IF NOT EXISTS document_records_214(
 document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, evidence_ref TEXT NOT NULL, original_name TEXT NOT NULL,
 safe_name TEXT NOT NULL, extension TEXT NOT NULL, media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 content_sha256 TEXT NOT NULL, language TEXT NOT NULL, source_kind TEXT NOT NULL, parser_mode TEXT NOT NULL,
 active_content_state TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_document_records_214_case ON document_records_214(case_id,created_at);
CREATE TABLE IF NOT EXISTS document_extractions_214(
 extraction_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL, extractor TEXT NOT NULL,
 extractor_version TEXT NOT NULL, text_original TEXT NOT NULL, text_sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL,
 warnings_json TEXT NOT NULL, language TEXT NOT NULL, page_count INTEGER NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(document_id) REFERENCES document_records_214(document_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS document_mentions_214(
 mention_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL, extraction_id TEXT NOT NULL,
 entity_type TEXT NOT NULL, text_original TEXT NOT NULL, normalized_text TEXT NOT NULL,
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, context_text TEXT NOT NULL,
 confidence REAL NOT NULL, review_status TEXT NOT NULL, linked_entity_id TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(document_id) REFERENCES document_records_214(document_id) ON DELETE RESTRICT,
 FOREIGN KEY(extraction_id) REFERENCES document_extractions_214(extraction_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_document_mentions_214_case ON document_mentions_214(case_id,entity_type,created_at);
CREATE TABLE IF NOT EXISTS document_translations_214(
 translation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL, extraction_id TEXT NOT NULL,
 original_language TEXT NOT NULL, target_language TEXT NOT NULL, original_text TEXT NOT NULL,
 translated_text TEXT NOT NULL, engine TEXT NOT NULL, engine_version TEXT NOT NULL,
 glossary_json TEXT NOT NULL, uncertainties_json TEXT NOT NULL, status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(document_id) REFERENCES document_records_214(document_id) ON DELETE RESTRICT,
 FOREIGN KEY(extraction_id) REFERENCES document_extractions_214(extraction_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS investigation_chat_turns_214(
 turn_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, question_original TEXT NOT NULL, question_language TEXT NOT NULL,
 working_language TEXT NOT NULL, focus TEXT NOT NULL, context_json TEXT NOT NULL, response_json TEXT NOT NULL DEFAULT '{}',
 citations_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS investigation_ai_feedback_214(
 feedback_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, item_type TEXT NOT NULL, item_id TEXT NOT NULL,
 verdict TEXT NOT NULL, dimensions_json TEXT NOT NULL, reason TEXT NOT NULL, analyst TEXT NOT NULL,
 training_eligible INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS document_opsec_profiles_214(
 profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, threat_level TEXT NOT NULL, document_class TEXT NOT NULL,
 controls_json TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS document_preflights_214(
 preflight_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL, requested_json TEXT NOT NULL,
 controls_json TEXT NOT NULL, risks_json TEXT NOT NULL, decision TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
 FOREIGN KEY(document_id) REFERENCES document_records_214(document_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS build214_events(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
 object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
 FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_build214_events_case ON build214_events(case_id,created_at);

CREATE TRIGGER IF NOT EXISTS trg_ontology_entities_214_no_update BEFORE UPDATE ON ontology_entities_214 BEGIN SELECT RAISE(ABORT,'ontology_entities_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ontology_entities_214_no_delete BEFORE DELETE ON ontology_entities_214 BEGIN SELECT RAISE(ABORT,'ontology_entities_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ontology_relations_214_no_update BEFORE UPDATE ON ontology_relations_214 BEGIN SELECT RAISE(ABORT,'ontology_relations_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_ontology_relations_214_no_delete BEFORE DELETE ON ontology_relations_214 BEGIN SELECT RAISE(ABORT,'ontology_relations_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_records_214_no_update BEFORE UPDATE ON document_records_214 BEGIN SELECT RAISE(ABORT,'document_records_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_records_214_no_delete BEFORE DELETE ON document_records_214 BEGIN SELECT RAISE(ABORT,'document_records_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_extractions_214_no_update BEFORE UPDATE ON document_extractions_214 BEGIN SELECT RAISE(ABORT,'document_extractions_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_extractions_214_no_delete BEFORE DELETE ON document_extractions_214 BEGIN SELECT RAISE(ABORT,'document_extractions_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_mentions_214_no_update BEFORE UPDATE ON document_mentions_214 BEGIN SELECT RAISE(ABORT,'document_mentions_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_mentions_214_no_delete BEFORE DELETE ON document_mentions_214 BEGIN SELECT RAISE(ABORT,'document_mentions_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_translations_214_no_update BEFORE UPDATE ON document_translations_214 BEGIN SELECT RAISE(ABORT,'document_translations_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_translations_214_no_delete BEFORE DELETE ON document_translations_214 BEGIN SELECT RAISE(ABORT,'document_translations_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_preflights_214_no_update BEFORE UPDATE ON document_preflights_214 BEGIN SELECT RAISE(ABORT,'document_preflights_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_preflights_214_no_delete BEFORE DELETE ON document_preflights_214 BEGIN SELECT RAISE(ABORT,'document_preflights_214 is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_build214_events_no_update BEFORE UPDATE ON build214_events BEGIN SELECT RAISE(ABORT,'build214_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_build214_events_no_delete BEFORE DELETE ON build214_events BEGIN SELECT RAISE(ABORT,'build214_events is immutable'); END;
'''


def ensure_build214_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_214)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','214.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','214.0')")
    db.conn.commit()
