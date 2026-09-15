from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build329.schema import ensure_build329_schema


def ensure_build330_schema(db: Any) -> None:
    ensure_build329_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_government_legal_profiles_330(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      source_families_json TEXT NOT NULL, legal_semantics_json TEXT NOT NULL,
      identity_policy_json TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_government_legal_records_330(
      legal_record_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, record_type TEXT NOT NULL,
      legal_stage TEXT NOT NULL, record_ref TEXT NOT NULL, title TEXT NOT NULL,
      authority_name TEXT NOT NULL, jurisdiction TEXT NOT NULL, subject_name TEXT NOT NULL,
      subject_identifier_type TEXT NOT NULL, subject_identifier_value TEXT NOT NULL,
      corporate_id TEXT NOT NULL, program_or_regime TEXT NOT NULL, docket_or_case_ref TEXT NOT NULL,
      decision_or_effect TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT NOT NULL,
      publication_date TEXT NOT NULL, source_ref TEXT NOT NULL, source_uri TEXT NOT NULL,
      finality_status TEXT NOT NULL, allegation_only INTEGER NOT NULL, adverse_action INTEGER NOT NULL,
      criminality_inferred INTEGER NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_legal_subject_links_330(
      link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      legal_record_id TEXT NOT NULL, corporate_id TEXT NOT NULL, match_basis TEXT NOT NULL,
      identifier_type TEXT NOT NULL, identifier_value TEXT NOT NULL, match_class TEXT NOT NULL,
      deterministic_link INTEGER NOT NULL, automatic_identity_truth INTEGER NOT NULL,
      human_review_required INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_government_legal_comparisons_330(
      comparison_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      comparison_key TEXT NOT NULL, legal_record_ids_json TEXT NOT NULL,
      source_groups_json TEXT NOT NULL, comparison_class TEXT NOT NULL,
      explanation TEXT NOT NULL, source_echo_collapsed INTEGER NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_government_legal_plans_330(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_government_legal_attestations_330(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_330(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_330(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_330(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_legal_case_330 ON phase14_government_legal_records_330(case_id,target_id,record_type,publication_date)',
      'CREATE INDEX IF NOT EXISTS idx_legal_ref_330 ON phase14_government_legal_records_330(source_id,record_ref,docket_or_case_ref)',
      'CREATE INDEX IF NOT EXISTS idx_legal_subject_330 ON phase14_government_legal_records_330(subject_identifier_type,subject_identifier_value,subject_name)',
      'CREATE INDEX IF NOT EXISTS idx_legal_links_330 ON phase14_legal_subject_links_330(case_id,target_id,corporate_id)',
    ): db.execute(sql)

    hard=[
      ('An allegation, complaint, charge or investigation is not a final judicial or regulatory finding.', ['stage_separation'], ['allegation_equals_guilt']),
      ('A court opinion or agency decision must preserve docket/reference, authority, date and finality status.', ['decision_provenance'], ['decision_without_context']),
      ('A sanctions-list record is a designation/listing record, not an automatic identity match to a case target.', ['sanctions_identity_guard'], ['name_match_equals_designated_target']),
      ('A debarment or exclusion applies according to its recorded scope and dates and must not be generalized beyond them.', ['scope_temporal_guard'], ['debarment_equals_global_permanent_ban']),
      ('Official gazette/legal-act publication is authoritative for publication of the act, not automatically for every factual allegation quoted within it.', ['publication_fact_separation'], ['official_document_makes_all_allegations_true']),
      ('Source echoes of the same legal decision or designation must not inflate corroboration.', ['independence_group'], ['source_echo_inflation']),
      ('Corporate identity linking should prefer strong public identifiers; name-only remains candidate-only.', ['identifier_first'], ['name_only_auto_merge']),
      ('Adverse legal/regulatory records require counterevidence/finality review before dossier conclusions.', ['counterevidence_and_finality'], ['automatic_adverse_conclusion']),
    ]
    sec=[
      ('Government/legal processing remains local unless an approved public source connector is explicitly executed.', ['external_execution_false'], ['silent_remote_fetch']),
      ('Legal-source URIs must not contain credentials or private/non-global targets.', ['public_source_boundary'], ['credential_or_private_uri']),
      ('Sanctions and exclusion matches remain candidate-only until identity review.', ['candidate_only'], ['automatic_identity_truth']),
      ('Name-only sanctions/debarment matching cannot create a deterministic merge.', ['human_review'], ['name_only_merge']),
      ('Allegations, proceedings and adverse records cannot automatically create criminality/guilt labels.', ['no_criminality_inference'], ['automatic_guilt_label']),
      ('Provider failure cannot trigger direct/proxy-bypass fallback.', ['provider_gate'], ['unsafe_fallback']),
      ('API/auth requirements may be catalogued without persisting secret values in case records.', ['credential_boundary'], ['plaintext_secret']),
      ('Government/legal intelligence performs no active external reconnaissance.', ['local_processing'], ['active_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,2) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_330 VALUES(?,?,?,?,?,?,?)',(f'b330-legal-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build330-government-legal-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_330 VALUES(?,?,?,?,?,?,?)',(f'b330-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build330-security-review'))
