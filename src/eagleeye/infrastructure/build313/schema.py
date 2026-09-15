from __future__ import annotations
import json
from typing import Any

def ensure_build313_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_technical_plans_313(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective_sha256 TEXT NOT NULL,
      anchor_json TEXT NOT NULL, families_json TEXT NOT NULL, query_plan_id TEXT NOT NULL, broker_plan_id TEXT NOT NULL,
      status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_technical_candidates_313(
      candidate_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      technical_type TEXT NOT NULL, source_label TEXT NOT NULL, source_url TEXT NOT NULL, source_group TEXT NOT NULL,
      normalized_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, support_direction TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_technical_bundle_assessments_313(
      assessment_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      support_count INTEGER NOT NULL, counter_count INTEGER NOT NULL, independent_source_groups INTEGER NOT NULL,
      agreement_json TEXT NOT NULL, contradictions_json TEXT NOT NULL, readiness_score REAL NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_technical_attestations_313(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_313(
      dossier313_id TEXT PRIMARY KEY, parent_dossier_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL,
      quality_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_313(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_313(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_313 VALUES(?,?,?,?,?,?,?)',(
          f'b313-tech-{i+1:02d}',d,'Public technical intelligence must preserve provenance, distinguish passive metadata from active probing, and retain contradictions.',
          json.dumps(['public_metadata_only','passive_technical_intelligence','field_provenance','candidate_only','counterevidence','source_independence']),
          json.dumps(['port_scanning','credential_testing','exploit_attempts','private_network_targeting','hit_count_probability']),
          'reviewed','build313-tech-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_313 VALUES(?,?,?,?,?,?,?)',(
          f'b313-security-{i+1:02d}',d,'Technical intelligence remains read-only and bounded to public metadata sources.',
          json.dumps(['public_only','private_network_gate','proxy_preservation','no_active_scan','candidate_only','explicit_connector_approval']),
          json.dumps(['service_fingerprinting','login_automation','credential_use','exploit_delivery','scope_drift','automatic_identity_confirmation']),
          'reviewed','build313-security-review'))
