from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build327.schema import ensure_build327_schema


def ensure_build328_schema(db: Any) -> None:
    ensure_build327_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_pack_profiles_328(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      supported_models_json TEXT NOT NULL, fact_identity_json TEXT NOT NULL,
      flow_semantics_json TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_filings_328(
      filing_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, source_id TEXT NOT NULL, source_group TEXT NOT NULL,
      filing_kind TEXT NOT NULL, accession_or_filing_ref TEXT NOT NULL, form_type TEXT NOT NULL,
      filing_date TEXT NOT NULL, period_end TEXT NOT NULL, fiscal_year TEXT NOT NULL,
      fiscal_period TEXT NOT NULL, taxonomy_family TEXT NOT NULL, source_uri TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_facts_328(
      fact_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, filing_id TEXT NOT NULL, source_id TEXT NOT NULL,
      source_group TEXT NOT NULL, taxonomy TEXT NOT NULL, concept TEXT NOT NULL,
      label TEXT NOT NULL, unit TEXT NOT NULL, value_text TEXT NOT NULL,
      numeric_value REAL, period_start TEXT NOT NULL, period_end TEXT NOT NULL,
      instant_date TEXT NOT NULL, fiscal_year TEXT NOT NULL, fiscal_period TEXT NOT NULL,
      form_type TEXT NOT NULL, filed_at TEXT NOT NULL, accession TEXT NOT NULL,
      frame TEXT NOT NULL, dimensions_json TEXT NOT NULL, decimals_text TEXT NOT NULL,
      coordinate_hash TEXT NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_fact_comparisons_328(
      comparison_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, coordinate_hash TEXT NOT NULL,
      fact_ids_json TEXT NOT NULL, version_count INTEGER NOT NULL,
      distinct_values INTEGER NOT NULL, latest_filed_at TEXT NOT NULL,
      comparison_class TEXT NOT NULL, explanation TEXT NOT NULL,
      probability_claim_generated INTEGER NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_relation_indicators_328(
      indicator_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      subject_corporate_id TEXT NOT NULL, predicate TEXT NOT NULL,
      object_corporate_id TEXT NOT NULL, subject_label TEXT NOT NULL, object_label TEXT NOT NULL,
      amount_value REAL, currency TEXT NOT NULL, ownership_percent REAL,
      valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, source_id TEXT NOT NULL,
      source_group TEXT NOT NULL, source_ref TEXT NOT NULL, indicator_class TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_documented_financial_flows_328(
      flow_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      payer_corporate_id TEXT NOT NULL, payee_corporate_id TEXT NOT NULL,
      payer_label TEXT NOT NULL, payee_label TEXT NOT NULL, amount_value REAL NOT NULL,
      currency TEXT NOT NULL, transaction_type TEXT NOT NULL, transaction_date TEXT NOT NULL,
      period_start TEXT NOT NULL, period_end TEXT NOT NULL, source_id TEXT NOT NULL,
      source_group TEXT NOT NULL, source_ref TEXT NOT NULL, evidence_basis TEXT NOT NULL,
      explicit_transfer_claim INTEGER NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_indicators_328(
      indicator_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      corporate_id TEXT NOT NULL, period_key TEXT NOT NULL, metric_key TEXT NOT NULL,
      metric_value REAL NOT NULL, inputs_json TEXT NOT NULL, interpretation TEXT NOT NULL,
      fraud_or_illegality_inferred INTEGER NOT NULL, probability_claim_generated INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_financial_pack_attestations_328(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_328(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_financial_plans_328(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_328(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_328(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_fin_filing_case_328 ON phase14_financial_filings_328(case_id,target_id,corporate_id,filing_date)',
      'CREATE INDEX IF NOT EXISTS idx_fin_fact_coord_328 ON phase14_financial_facts_328(case_id,target_id,corporate_id,coordinate_hash,filed_at)',
      'CREATE INDEX IF NOT EXISTS idx_fin_fact_concept_328 ON phase14_financial_facts_328(case_id,target_id,concept,period_end)',
      'CREATE INDEX IF NOT EXISTS idx_fin_rel_subject_328 ON phase14_financial_relation_indicators_328(subject_corporate_id,predicate,valid_from)',
      'CREATE INDEX IF NOT EXISTS idx_fin_flow_party_328 ON phase14_documented_financial_flows_328(payer_corporate_id,payee_corporate_id,transaction_date)',
    ): db.execute(sql)

    hard=[
      ('XBRL fact identity must retain concept, unit, period and dimensions rather than concept alone.', ['coordinate_preserved','dimensions_preserved'], ['concept_only_fact_identity']),
      ('Multiple filings may report different values for the same economic coordinate and must remain versioned.', ['fact_versions','restatement_review'], ['overwrite_older_fact']),
      ('A later filing is not automatically more truthful; it is only the latest reported version.', ['latest_reported_version'], ['latest_equals_truth']),
      ('Financial flow requires explicit payer, payee, amount/currency and temporal/source basis.', ['explicit_flow_fields'], ['ownership_implies_cash_transfer']),
      ('Related-party, ownership and supplier relations remain indicators unless a transfer is documented.', ['relation_indicator'], ['relationship_as_money_flow']),
      ('Financial ratios are analytical descriptors and cannot imply fraud or illegality.', ['ratio_context'], ['ratio_equals_fraud']),
      ('Fiscal periods and instant facts must not be mixed without period-aware normalization.', ['period_type_review'], ['instant_duration_mix']),
      ('Source independence and filing provenance remain attached to every financial fact.', ['source_group','filing_ref'], ['detached_numeric_fact']),
    ]
    sec=[
      ('Financial pack processing remains local unless a reviewed connector is explicitly approved.', ['external_execution_false'], ['silent_remote_financial_fetch']),
      ('Financial source URIs and payloads must not contain credentials.', ['credential_boundary'], ['plaintext_api_key']),
      ('Candidate financial facts cannot auto-promote to verified evidence.', ['candidate_only'], ['automatic_truth_promotion']),
      ('High-impact ownership and money-flow claims require human review.', ['human_review'], ['automatic_accusation']),
      ('Financial analytics cannot create fraud, corruption or criminality labels from ratios alone.', ['no_illegality_inference'], ['automated_criminal_label']),
      ('Case and target boundaries are preserved for facts, relations and flows.', ['case_target_binding'], ['cross_case_leakage']),
      ('Provider failure does not trigger unsafe direct network fallback.', ['provider_gate'], ['direct_fallback']),
      ('Financial pack operations perform no active external reconnaissance.', ['local_processing'], ['active_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (1,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_328 VALUES(?,?,?,?,?,?,?)',(f'b328-fin-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build328-financial-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (3,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_328 VALUES(?,?,?,?,?,?,?)',(f'b328-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build328-security-review'))
