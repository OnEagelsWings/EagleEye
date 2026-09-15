from __future__ import annotations
import json
from typing import Any

def ensure_build321_schema(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_storage_profiles_321(
      profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, profile_name TEXT NOT NULL, mode TEXT NOT NULL,
      relational_backend TEXT NOT NULL, object_backend TEXT NOT NULL, search_backend TEXT NOT NULL, queue_backend TEXT NOT NULL,
      config_json TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_storage_capability_checks_321(
      check_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, capability TEXT NOT NULL, backend TEXT NOT NULL,
      state TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_data_access_plans_321(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, strategy_json TEXT NOT NULL,
      local_first INTEGER NOT NULL, external_execution INTEGER NOT NULL, human_approval_required INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_infrastructure_attestations_321(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_321(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_321(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_321(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    hard=[
      ('storage_independence','Investigation workflow must not depend on a single physical database.', ['logical_storage_contract','portable_mode_preserved'], ['backend_specific_truth_logic']),
      ('local_first','Existing local evidence should be queried before external acquisition.', ['local_first_plan','gap_driven_external_candidates'], ['blind_external_search']),
      ('bulk_future','Large public datasets require resumable ingestion architecture.', ['capability_contract','incremental_ready'], ['load_everything_into_sqlite']),
      ('search_future','Document retrieval must separate transactional and search workloads.', ['search_adapter_boundary'], ['fulltext_assumed_transactional']),
      ('queue_future','Long ingestion jobs need bounded worker semantics.', ['queue_adapter_boundary','job_budget'], ['unbounded_background_loop']),
      ('provenance','Storage migration must preserve source provenance and immutable hashes.', ['preserve_hashes','preserve_source_ids'], ['rewrite_provenance']),
      ('data_access','AI should select source classes by evidence gap and source independence.', ['gap_driven_sources','independence'], ['hit_count_as_quality']),
      ('migration','Portable-to-team migration requires explicit readiness assessment.', ['readiness_gate','human_migration'], ['silent_backend_switch'])]
    sec=[
      ('secrets','Backend credentials must not be persisted in investigation records.', ['secret_reference_only'], ['plaintext_secret']),
      ('network_default','Storage foundation must not create new external egress by default.', ['local_only_default'], ['auto_external_connect']),
      ('private_endpoint','Private/internal endpoints require explicit deployment configuration.', ['fail_closed_unconfigured'], ['auto_discover_private_service']),
      ('tls_policy','Future remote adapters require verified TLS policy.', ['tls_verify_required'], ['tls_disable']),
      ('least_privilege','Future backend accounts should be scoped by role.', ['least_privilege_contract'], ['admin_credentials_default']),
      ('audit','Backend selection and migration actions must be auditable.', ['audit_event'], ['silent_switch']),
      ('active_recon','Data platform work must not expand external active reconnaissance.', ['real_active_recon_disabled'], ['scan_external_target']),
      ('review','AI acquisition plan remains human-gated for external execution.', ['human_approval_required'], ['autonomous_unbounded_egress'])]
    for i,(_,sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_321 VALUES(?,?,?,?,?,?,?)',(f'b321-data-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build321-data-review'))
    for i,(_,sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_321 VALUES(?,?,?,?,?,?,?)',(f'b321-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build321-security-review'))
