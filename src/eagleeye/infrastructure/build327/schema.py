from __future__ import annotations
import json
from typing import Any


def ensure_build327_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_pack_profiles_327(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, schema_version TEXT NOT NULL,
      supported_sources_json TEXT NOT NULL, strong_identifier_types_json TEXT NOT NULL,
      weak_match_fields_json TEXT NOT NULL, privacy_minimization_json TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_source_records_327(
      source_record_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, record_type TEXT NOT NULL,
      source_record_key TEXT NOT NULL, normalized_json TEXT NOT NULL, raw_payload_hash TEXT NOT NULL,
      observed_at TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_entities_327(
      corporate_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      canonical_name TEXT NOT NULL, jurisdiction TEXT NOT NULL, legal_form TEXT NOT NULL,
      status TEXT NOT NULL, incorporation_date TEXT NOT NULL, dissolution_date TEXT NOT NULL,
      registered_address TEXT NOT NULL, headquarters_address TEXT NOT NULL,
      website_domain TEXT NOT NULL, candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_identifiers_327(
      identifier_id TEXT PRIMARY KEY, corporate_id TEXT NOT NULL, identifier_type TEXT NOT NULL,
      identifier_value TEXT NOT NULL, jurisdiction TEXT NOT NULL, source_id TEXT NOT NULL,
      source_record_id TEXT NOT NULL, confidence_class TEXT NOT NULL, valid_from TEXT NOT NULL,
      valid_to TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_relationships_327(
      relationship_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      subject_corporate_id TEXT NOT NULL, predicate TEXT NOT NULL, object_corporate_id TEXT NOT NULL,
      subject_identifier TEXT NOT NULL, object_identifier TEXT NOT NULL, relationship_type TEXT NOT NULL,
      ownership_percent REAL NOT NULL, relationship_status TEXT NOT NULL, accounting_standard TEXT NOT NULL,
      valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, source_id TEXT NOT NULL, source_group TEXT NOT NULL,
      source_record_id TEXT NOT NULL, polarity TEXT NOT NULL, candidate_only INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_officers_327(
      officer_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, officer_name TEXT NOT NULL, role TEXT NOT NULL,
      appointed_on TEXT NOT NULL, resigned_on TEXT NOT NULL, nationality_public TEXT NOT NULL,
      occupation_public TEXT NOT NULL, service_address_public TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, source_record_id TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_control_records_327(
      control_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, controller_name TEXT NOT NULL, controller_kind TEXT NOT NULL,
      natures_of_control_json TEXT NOT NULL, notified_on TEXT NOT NULL, ceased_on TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, source_record_id TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_reporting_exceptions_327(
      exception_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      child_identifier TEXT NOT NULL, parent_scope TEXT NOT NULL, exception_reason TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, source_record_id TEXT NOT NULL,
      valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_match_candidates_327(
      match_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      left_corporate_id TEXT NOT NULL, right_corporate_id TEXT NOT NULL, match_basis TEXT NOT NULL,
      strong_identifier_match INTEGER NOT NULL, name_similarity REAL NOT NULL, address_similarity REAL NOT NULL,
      temporal_consistency INTEGER NOT NULL, source_independence INTEGER NOT NULL,
      resolution_action TEXT NOT NULL, explanation_json TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_corporate_pack_attestations_327(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_327(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_corporate_plans_327(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_327(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_327(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_corp_id_unique_327 ON phase14_corporate_identifiers_327(corporate_id,identifier_type,identifier_value,source_record_id)',
      'CREATE INDEX IF NOT EXISTS idx_corp_ident_lookup_327 ON phase14_corporate_identifiers_327(identifier_type,identifier_value,jurisdiction)',
      'CREATE INDEX IF NOT EXISTS idx_corp_entity_case_327 ON phase14_corporate_entities_327(case_id,target_id,canonical_name)',
      'CREATE INDEX IF NOT EXISTS idx_corp_rel_subject_327 ON phase14_corporate_relationships_327(subject_corporate_id,predicate)',
      'CREATE INDEX IF NOT EXISTS idx_corp_officer_name_327 ON phase14_corporate_officers_327(officer_name,corporate_id)',
      'CREATE INDEX IF NOT EXISTS idx_corp_control_name_327 ON phase14_corporate_control_records_327(controller_name,corporate_id)',
      'CREATE INDEX IF NOT EXISTS idx_corp_source_record_327 ON phase14_corporate_source_records_327(source_id,record_type,source_record_key)'
    ): db.execute(sql)

    hard=[
      ('Strong legal identifiers may support deterministic entity linking across sources.', ['LEI_or_CIK_or_jurisdiction_company_number','source_provenance'], ['name_only_auto_merge']),
      ('Names and addresses alone create match candidates rather than automatic merges.', ['candidate_match','human_review'], ['fuzzy_name_auto_identity']),
      ('GLEIF Level 1 identity and Level 2 parent relationships remain distinct record families.', ['LEI_CDF','RR_CDF'], ['flatten_relationship_into_identity']),
      ('GLEIF reporting exceptions must be represented separately from negative ownership claims.', ['reporting_exception_record'], ['exception_equals_no_parent']),
      ('Corporate relationship validity periods must be retained for temporal reasoning.', ['valid_from','valid_to'], ['timeless_current_ownership_assumption']),
      ('Companies House PSC records are statutory control records but not universal global beneficial ownership proof.', ['PSC_candidate_control','scope_caveat'], ['global_UBO_truth_claim']),
      ('Officer roles preserve appointment and resignation dates.', ['appointed_on','resigned_on'], ['current_role_from_historical_record']),
      ('Cross-source corporate packs must preserve primary/secondary source independence.', ['source_group','independence_group'], ['aggregator_echo_as_independent_confirmation']),
    ]
    sec=[
      ('Corporate pack ingestion remains local and cannot silently fetch provider data.', ['external_execution_false'], ['silent_remote_download']),
      ('Personal fields in officer/control records are minimized to investigation-relevant public fields.', ['public_field_allowlist','residential_address_excluded'], ['unbounded_personal_profile']),
      ('Provider API keys and credentials never enter corporate record payloads.', ['credential_boundary'], ['plaintext_api_key']),
      ('Unreviewed corporate source adapters cannot automatically become routing-active.', ['review_gate'], ['auto_activate_unreviewed_adapter']),
      ('Entity matching cannot auto-merge based only on fuzzy name similarity.', ['strong_identifier_gate'], ['name_only_merge']),
      ('Ownership/control data cannot be promoted to verified evidence without human review.', ['candidate_only'], ['automatic_truth_promotion']),
      ('Bulk corporate materialization remains case/target bounded.', ['case_target_binding'], ['cross_case_leakage']),
      ('Corporate pack operations do not perform active external reconnaissance.', ['local_data_processing_only'], ['active_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (1,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_327 VALUES(?,?,?,?,?,?,?)',(f'b327-corp-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build327-corporate-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (1,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_327 VALUES(?,?,?,?,?,?,?)',(f'b327-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build327-security-review'))
