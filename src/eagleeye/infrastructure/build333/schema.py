from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build332.schema import ensure_build332_schema


def ensure_build333_schema(db: Any) -> None:
    ensure_build332_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_multilingual_profiles_333(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      normalization_policy_json TEXT NOT NULL, transliteration_policy_json TEXT NOT NULL,
      query_policy_json TEXT NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_locale_term_packs_333(
      locale_key TEXT PRIMARY KEY, language TEXT NOT NULL, script TEXT NOT NULL,
      jurisdictions_json TEXT NOT NULL, terminology_json TEXT NOT NULL,
      identifier_terms_json TEXT NOT NULL, document_terms_json TEXT NOT NULL,
      source_hints_json TEXT NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_name_variant_sets_333(
      variant_set_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      original_anchor TEXT NOT NULL, variants_json TEXT NOT NULL, scripts_json TEXT NOT NULL,
      reverse_transliteration_automatic INTEGER NOT NULL, human_review_required INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_multilingual_query_plans_333(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, jurisdiction_hint TEXT NOT NULL, locales_json TEXT NOT NULL,
      variant_set_id TEXT NOT NULL, source_routes_json TEXT NOT NULL, plan_json TEXT NOT NULL,
      query_count INTEGER NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_multilingual_queries_333(
      query_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      locale_key TEXT NOT NULL, language TEXT NOT NULL, script TEXT NOT NULL, jurisdiction TEXT NOT NULL,
      ladder TEXT NOT NULL, category TEXT NOT NULL, query_text TEXT NOT NULL,
      anchor_json TEXT NOT NULL, terminology_json TEXT NOT NULL, source_focus TEXT NOT NULL,
      stance TEXT NOT NULL, priority_score REAL NOT NULL, candidate_only INTEGER NOT NULL,
      automatic_identity_truth INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_multilingual_recovery_333(
      recovery_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, query_id TEXT NOT NULL,
      outcome TEXT NOT NULL, recovery_json TEXT NOT NULL, probability_downgrade INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_multilingual_attestations_333(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_333(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_333(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_333(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_ml333_plan_target ON phase14_multilingual_query_plans_333(case_id,target_id,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_ml333_query_plan ON phase14_multilingual_queries_333(plan_id,ladder,category,priority_score)',
      'CREATE INDEX IF NOT EXISTS idx_ml333_query_target ON phase14_multilingual_queries_333(case_id,target_id,language,category)',
      'CREATE INDEX IF NOT EXISTS idx_ml333_recovery ON phase14_multilingual_recovery_333(plan_id,query_id,outcome)',
    ): db.execute(sql)

    hard=[
      ('Multilingual discovery must preserve user-supplied identity anchors verbatim and must not translate proper names as facts.', ['verbatim_anchor_provenance'], ['translated_name_equals_identity']),
      ('A transliteration is a search variant candidate and cannot establish that two differently written names are the same person or company.', ['transliteration_candidate_only'], ['transliteration_equals_identity']),
      ('Latin-to-non-Latin reverse transliteration is ambiguous and must not be automatically invented when the local-script alias is unknown.', ['no_automatic_reverse_transliteration'], ['invent_native_script_name']),
      ('Locale terminology must be jurisdiction-aware; Brazilian Portuguese discovery should use Brazilian registry terms such as CNPJ/razão social where relevant.', ['jurisdiction_aware_terms'], ['generic_translation_only']),
      ('Local-language counterevidence queries must be generated alongside support/discovery queries.', ['counterevidence_local_language'], ['support_only_search']),
      ('Zero results must trigger controlled broadening or alternate trusted anchor variants, not a probability downgrade.', ['zero_result_broaden'], ['zero_results_equals_disproof']),
      ('Public source discovery must not imply access to private civil, subscriber, credential, or restricted records.', ['public_source_boundary'], ['private_record_access_claim']),
      ('Query priority is retrieval utility only and must never be represented as truth, guilt, identity or evidence probability.', ['retrieval_score_only'], ['query_score_equals_probability']),
    ]
    sec=[
      ('Multilingual plan generation is offline and does not execute generated searches or contact providers.', ['offline_planning'], ['implicit_network_query']),
      ('Generated query text is inert data and cannot execute shell, SQL, browser or tool commands.', ['query_text_inert'], ['query_as_command']),
      ('Credentials and private/non-global source endpoints remain forbidden in discovered source routes.', ['public_source_only'], ['credential_or_private_endpoint']),
      ('Language packs cannot overwrite strong identifiers or original identity anchors.', ['anchor_integrity'], ['language_pack_rewrites_identifier']),
      ('Unreviewed discovered sources remain candidate-only and are not automatically activated.', ['review_gate'], ['auto_activate_unknown_source']),
      ('External multilingual acquisition remains human-gated and external_execution false by default.', ['human_gate'], ['silent_external_execution']),
      ('Cross-case and cross-target multilingual query leakage is forbidden.', ['case_target_isolation'], ['cross_case_query_leakage']),
      ('No active reconnaissance, credential testing, access-control bypass or private-record enumeration is introduced by multilingual discovery.', ['no_active_recon'], ['active_or_private_recon']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,2) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_333 VALUES(?,?,?,?,?,?,?)',(f'b333-ml-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb),'reviewed','build333-multilingual-source-discovery-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (1,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_333 VALUES(?,?,?,?,?,?,?)',(f'b333-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build333-security-review'))
