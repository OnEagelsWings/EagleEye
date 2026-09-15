from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build328.schema import ensure_build328_schema


def ensure_build329_schema(db: Any) -> None:
    ensure_build328_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_procurement_grants_profiles_329(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      supported_sources_json TEXT NOT NULL, award_semantics_json TEXT NOT NULL,
      identity_policy_json TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_public_awards_329(
      public_award_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, award_type TEXT NOT NULL,
      instrument_class TEXT NOT NULL, award_ref TEXT NOT NULL, parent_award_ref TEXT NOT NULL,
      title TEXT NOT NULL, funder_name TEXT NOT NULL, recipient_name TEXT NOT NULL,
      recipient_identifier_type TEXT NOT NULL, recipient_identifier_value TEXT NOT NULL,
      recipient_corporate_id TEXT NOT NULL, awarding_agency TEXT NOT NULL,
      amount_awarded REAL, amount_obligated REAL, amount_outlay REAL,
      currency TEXT NOT NULL, award_date TEXT NOT NULL, period_start TEXT NOT NULL,
      period_end TEXT NOT NULL, program_code TEXT NOT NULL, cpv_code TEXT NOT NULL,
      jurisdiction TEXT NOT NULL, status TEXT NOT NULL, source_ref TEXT NOT NULL,
      source_uri TEXT NOT NULL, financial_semantics TEXT NOT NULL,
      opportunity_not_award INTEGER NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_funding_opportunities_329(
      opportunity_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL, opportunity_type TEXT NOT NULL,
      opportunity_ref TEXT NOT NULL, title TEXT NOT NULL, issuer_name TEXT NOT NULL,
      program_code TEXT NOT NULL, cpv_code TEXT NOT NULL, estimated_amount REAL,
      currency TEXT NOT NULL, published_at TEXT NOT NULL, deadline_at TEXT NOT NULL,
      jurisdiction TEXT NOT NULL, status TEXT NOT NULL, source_ref TEXT NOT NULL,
      source_uri TEXT NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_award_recipient_links_329(
      link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      public_award_id TEXT NOT NULL, corporate_id TEXT NOT NULL,
      match_basis TEXT NOT NULL, identifier_type TEXT NOT NULL, identifier_value TEXT NOT NULL,
      match_class TEXT NOT NULL, deterministic_merge INTEGER NOT NULL,
      human_review_required INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_public_award_comparisons_329(
      comparison_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      award_identity_key TEXT NOT NULL, award_ids_json TEXT NOT NULL,
      source_groups_json TEXT NOT NULL, comparison_class TEXT NOT NULL,
      explanation TEXT NOT NULL, source_echo_collapsed INTEGER NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_procurement_grants_attestations_329(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_329(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_public_funding_plans_329(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_329(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_329(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_pubaward_case_329 ON phase14_public_awards_329(case_id,target_id,award_type,award_date)',
      'CREATE INDEX IF NOT EXISTS idx_pubaward_recipient_329 ON phase14_public_awards_329(recipient_identifier_type,recipient_identifier_value,recipient_name)',
      'CREATE INDEX IF NOT EXISTS idx_pubaward_ref_329 ON phase14_public_awards_329(source_id,award_ref,parent_award_ref)',
      'CREATE INDEX IF NOT EXISTS idx_opportunity_case_329 ON phase14_funding_opportunities_329(case_id,target_id,opportunity_type,deadline_at)',
      'CREATE INDEX IF NOT EXISTS idx_awardlink_case_329 ON phase14_award_recipient_links_329(case_id,target_id,corporate_id)',
    ): db.execute(sql)

    hard=[
      ('A procurement or grant opportunity is not an award and must never be counted as funding received.', ['opportunity_award_separation'], ['call_equals_award']),
      ('Award amount, obligation and outlay are different financial semantics and must remain separate.', ['amount_semantics'], ['obligation_equals_payment']),
      ('Prime awards and subawards must preserve their parent/child chain.', ['prime_subaward_chain'], ['flatten_subaward']),
      ('Recipient identity should use strong public identifiers before name-only matching.', ['identifier_first'], ['name_only_auto_merge']),
      ('Source echoes in public-spending portals must not inflate independent corroboration.', ['independence_group'], ['source_echo_inflation']),
      ('A procurement award creates a documented public-award relationship, not proof of corruption or favoritism.', ['neutral_award_semantics'], ['award_equals_corruption']),
      ('A grant award records public funding/obligation semantics but not automatic cash-transfer truth unless source semantics explicitly supports outlay/payment.', ['award_semantics'], ['grant_equals_cash_payment']),
      ('Temporal validity of award, obligation, performance period and notice publication must remain distinct.', ['temporal_fields'], ['single_date_collapse']),
    ]
    sec=[
      ('Procurement and grant processing remains local unless an approved source connector is explicitly executed.', ['external_execution_false'], ['silent_remote_fetch']),
      ('Public-spending source URIs must not contain credentials or private targets.', ['public_source_boundary'], ['credential_or_private_uri']),
      ('Recipient identifiers and names remain case-bound and candidate-only until review.', ['candidate_only'], ['automatic_identity_truth']),
      ('Name-only recipient matching may create a candidate link but never a deterministic merge.', ['human_review'], ['name_only_merge']),
      ('Award, grant, procurement and subaward records cannot automatically create criminality/corruption labels.', ['no_criminality_inference'], ['automatic_corruption_label']),
      ('Provider failure cannot trigger direct/proxy-bypass fallback.', ['provider_gate'], ['unsafe_fallback']),
      ('Bulk/API metadata may be catalogued without storing API key values in case data.', ['credential_boundary'], ['plaintext_api_key']),
      ('Procurement/grant intelligence performs no active external reconnaissance.', ['local_processing'], ['active_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (1,5) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_329 VALUES(?,?,?,?,?,?,?)',(f'b329-funding-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build329-public-funding-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (3,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_329 VALUES(?,?,?,?,?,?,?)',(f'b329-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build329-security-review'))
