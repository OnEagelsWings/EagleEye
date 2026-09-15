from __future__ import annotations
from typing import Any

SCHEMA_167 = r'''
CREATE TABLE IF NOT EXISTS crime_threat_cases_167(
 workflow_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 scope_json TEXT NOT NULL, legal_basis TEXT NOT NULL, risk_level TEXT NOT NULL,
 status TEXT NOT NULL, opened_by TEXT NOT NULL, opened_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_observations_167(
 observation_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, observation_type TEXT NOT NULL,
 occurred_at TEXT, observed_at TEXT NOT NULL, source_ref TEXT NOT NULL,
 statement_json TEXT NOT NULL, confidence REAL NOT NULL, verification_status TEXT NOT NULL,
 provenance_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_hypotheses_167(
 hypothesis_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, title TEXT NOT NULL,
 proposition TEXT NOT NULL, supporting_refs_json TEXT NOT NULL, contradicting_refs_json TEXT NOT NULL,
 assessment TEXT NOT NULL, status TEXT NOT NULL, review_status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_indicators_167(
 indicator_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, indicator_type TEXT NOT NULL,
 value_json TEXT NOT NULL, relevance REAL NOT NULL, source_refs_json TEXT NOT NULL,
 temporal_json TEXT NOT NULL, review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_entities_167(
 entity_link_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, entity_ref TEXT NOT NULL,
 role_label TEXT NOT NULL, relevance REAL NOT NULL, basis_refs_json TEXT NOT NULL,
 status TEXT NOT NULL, review_status TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_leads_167(
 lead_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, lead_type TEXT NOT NULL,
 title TEXT NOT NULL, detail_json TEXT NOT NULL, priority TEXT NOT NULL,
 source_refs_json TEXT NOT NULL, assigned_to TEXT, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_ai_assessments_167(
 assessment_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, task_type TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, output_json TEXT NOT NULL, opsec_json TEXT NOT NULL,
 model_mode TEXT NOT NULL, review_required INTEGER NOT NULL, created_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crime_threat_sitreps_167(
 sitrep_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, sequence_no INTEGER NOT NULL,
 generated_by TEXT NOT NULL, summary_json TEXT NOT NULL, classification TEXT NOT NULL,
 generated_at TEXT NOT NULL, previous_sha256 TEXT, payload_sha256 TEXT NOT NULL,
 UNIQUE(workflow_id, sequence_no)
);
CREATE TABLE IF NOT EXISTS ui_workspace_manifest_167(
 manifest_id TEXT PRIMARY KEY, version TEXT NOT NULL, sections_json TEXT NOT NULL,
 hidden_legacy_tabs_json TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
'''

def ensure_build167_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_167)
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','167.0')")
    db.conn.commit()
