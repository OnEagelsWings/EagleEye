from __future__ import annotations
import json
from typing import Any


def ensure_build311_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_connector_broker_plans_311(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective_sha256 TEXT NOT NULL,
      status TEXT NOT NULL, route_count INTEGER NOT NULL, content_json TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_connector_broker_routes_311(
      route_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      connector_key TEXT NOT NULL, provider_key TEXT NOT NULL, query_category TEXT NOT NULL, route_score REAL NOT NULL,
      trust_state TEXT NOT NULL, public_only INTEGER NOT NULL, enabled INTEGER NOT NULL, execution_state TEXT NOT NULL,
      rationale_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_connector_broker_attestations_311(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_311(
      dossier311_id TEXT PRIMARY KEY, parent_dossier_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL,
      quality_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_311(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_311(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        cid=f'b311-connector-{i+1:02d}'
        sid=f'b311-security-{i+1:02d}'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_311 VALUES(?,?,?,?,?,?,?)',(
            cid,d,'Connector broker routes a public-source investigation query to the smallest suitable trusted connector set.',
            json.dumps(['case_target_binding','public_only','trust_aware_routing','single_anchor_minimization','candidate_only','counterevidence_coverage']),
            json.dumps(['blind_connector_fanout','credential_use','automatic_evidence_promotion','identity_confirmation','hidden_scope_expansion']),
            'reviewed','build311-investigation-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_311 VALUES(?,?,?,?,?,?,?)',(
            sid,d,'Connector broker must fail closed on disabled, untrusted, private, credentialed or non-public connector paths.',
            json.dumps(['explicit_execution_approval','trusted_connector_only','public_get_only','provider_egress_gate','audit_provenance']),
            json.dumps(['silent_live_run','scope_drift','private_network_access','credential_targeting','proxy_bypass']),
            'reviewed','build311-security-review'))
