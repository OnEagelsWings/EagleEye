from __future__ import annotations
from typing import Any

SCHEMA_176 = r"""
CREATE TABLE IF NOT EXISTS multilingual_source_profiles_176(
 source_id TEXT PRIMARY KEY, title TEXT NOT NULL, jurisdiction TEXT NOT NULL, category TEXT NOT NULL,
 access_mode TEXT NOT NULL, base_url TEXT NOT NULL, docs_url TEXT NOT NULL, terms_url TEXT NOT NULL,
 languages_json TEXT NOT NULL, capabilities_json TEXT NOT NULL, constraints_json TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_documents_176(
 document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT, source_ref TEXT,
 original_text TEXT NOT NULL, normalized_text TEXT NOT NULL, detected_language TEXT NOT NULL,
 language_scores_json TEXT NOT NULL, script_profile_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 provenance_json TEXT NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_entities_176(
 entity_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, case_id TEXT NOT NULL, entity_type TEXT NOT NULL,
 value TEXT NOT NULL, normalized_value TEXT NOT NULL, start_offset INTEGER, end_offset INTEGER,
 confidence REAL NOT NULL, evidence_json TEXT NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_translations_176(
 translation_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, source_language TEXT NOT NULL, target_language TEXT NOT NULL,
 provider_id TEXT NOT NULL, translated_text TEXT NOT NULL, glossary_hits_json TEXT NOT NULL,
 machine_translation INTEGER NOT NULL, human_review_required INTEGER NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_analysis_176(
 analysis_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, case_id TEXT NOT NULL, summary_json TEXT NOT NULL,
 topics_json TEXT NOT NULL, temporal_refs_json TEXT NOT NULL, location_refs_json TEXT NOT NULL,
 person_refs_json TEXT NOT NULL, organization_refs_json TEXT NOT NULL, source_citations_json TEXT NOT NULL,
 ai_policy_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS multilingual_events_176(
 event_id TEXT PRIMARY KEY, case_id TEXT, event_type TEXT NOT NULL, entity_ref TEXT, details_json TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
"""

def ensure_build176_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_176)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','176.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','176.0')")
    db.conn.commit()
