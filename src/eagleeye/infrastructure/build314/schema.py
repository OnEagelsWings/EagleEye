from __future__ import annotations
import json
from typing import Any

def ensure_build314_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_govlegal_plans_314(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective_sha256 TEXT NOT NULL,
      jurisdictions_json TEXT NOT NULL, families_json TEXT NOT NULL, query_plan_id TEXT NOT NULL, broker_plan_id TEXT NOT NULL,
      status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_govlegal_candidates_314(
      candidate_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      record_type TEXT NOT NULL, jurisdiction TEXT NOT NULL, authority TEXT NOT NULL, source_url TEXT NOT NULL,
      source_group TEXT NOT NULL, normalized_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, support_direction TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_govlegal_assessments_314(
      assessment_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      support_count INTEGER NOT NULL, counter_count INTEGER NOT NULL, independent_source_groups INTEGER NOT NULL,
      agreement_json TEXT NOT NULL, contradictions_json TEXT NOT NULL, readiness_score REAL NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_recon_lab_runs_314(
      run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, authorization_id TEXT NOT NULL,
      scope_json TEXT NOT NULL, plan_json TEXT NOT NULL, simulation_only INTEGER NOT NULL, network_calls INTEGER NOT NULL,
      status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_security_attestations_314(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_314(
      dossier314_id TEXT PRIMARY KEY, parent_dossier_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL,
      quality_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_314(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_314(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_314 VALUES(?,?,?,?,?,?,?)',(
          f'b314-govlegal-{i+1:02d}',d,'Government and legal research must preserve jurisdiction, authority, provenance, counterevidence and review status.',
          json.dumps(['public_official_sources','jurisdiction_awareness','authority_provenance','candidate_only','counterevidence','source_independence']),
          json.dumps(['private_database_access','login_bypass','automatic_guilt_inference','record_count_probability','unreviewed_identity_confirmation']),
          'reviewed','build314-govlegal-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_314 VALUES(?,?,?,?,?,?,?)',(
          f'b314-security-{i+1:02d}',d,'Active reconnaissance logic is permitted only as a no-network lab simulation; real external probing remains disabled.',
          json.dumps(['explicit_authorization','simulation_only','network_calls_zero','scope_audit','fail_closed','public_passive_research']),
          json.dumps(['external_port_scan','service_fingerprinting','credential_testing','packet_probing','exploit_attempts','scope_drift']),
          'reviewed','build314-security-review'))
