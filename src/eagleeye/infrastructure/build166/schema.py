from __future__ import annotations
from typing import Any

SCHEMA_166 = r'''
CREATE TABLE IF NOT EXISTS missing_person_cases_166(
 workflow_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, subject_json TEXT NOT NULL,
 risk_profile_json TEXT NOT NULL, legal_basis TEXT NOT NULL, status TEXT NOT NULL,
 opened_by TEXT NOT NULL, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_sightings_166(
 sighting_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, observed_at TEXT NOT NULL,
 reported_at TEXT NOT NULL, location_json TEXT NOT NULL, source_ref TEXT NOT NULL,
 source_type TEXT NOT NULL, description TEXT NOT NULL, confidence REAL NOT NULL,
 verification_status TEXT NOT NULL, provenance_json TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_contacts_166(
 contact_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, person_ref TEXT,
 label TEXT NOT NULL, relationship_type TEXT NOT NULL, relevance_score REAL NOT NULL,
 last_contact_at TEXT, source_refs_json TEXT NOT NULL, risk_flags_json TEXT NOT NULL,
 review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_locations_166(
 location_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, label TEXT NOT NULL,
 location_json TEXT NOT NULL, location_type TEXT NOT NULL, relevance_score REAL NOT NULL,
 temporal_json TEXT NOT NULL, source_refs_json TEXT NOT NULL, review_status TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_leads_166(
 lead_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, lead_type TEXT NOT NULL,
 title TEXT NOT NULL, detail_json TEXT NOT NULL, priority TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, status TEXT NOT NULL, assigned_to TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_ai_assessments_166(
 assessment_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, task_type TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, output_json TEXT NOT NULL, opsec_json TEXT NOT NULL,
 model_mode TEXT NOT NULL, review_required INTEGER NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missing_person_sitreps_166(
 sitrep_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
 generated_by TEXT NOT NULL, summary_json TEXT NOT NULL, classification TEXT NOT NULL,
 generated_at TEXT NOT NULL, previous_sha256 TEXT, payload_sha256 TEXT NOT NULL,
 UNIQUE(workflow_id,sequence_no)
);
'''

def ensure_build166_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_166)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','166.0')")
    db.conn.commit()
