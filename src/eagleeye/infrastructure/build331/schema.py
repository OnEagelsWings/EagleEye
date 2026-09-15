from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build330.schema import ensure_build330_schema


def ensure_build331_schema(db: Any) -> None:
    ensure_build330_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_historical_web_profiles_331(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      source_families_json TEXT NOT NULL, capture_semantics_json TEXT NOT NULL,
      change_policy_json TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_historical_web_captures_331(
      capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, source_group TEXT NOT NULL,
      original_url TEXT NOT NULL, canonical_url TEXT NOT NULL, capture_at TEXT NOT NULL,
      observed_at TEXT NOT NULL, source_locator TEXT NOT NULL, archive_record_id TEXT NOT NULL,
      http_status INTEGER NOT NULL, mime_type TEXT NOT NULL,
      warc_filename TEXT NOT NULL, warc_offset TEXT NOT NULL, warc_length TEXT NOT NULL,
      warc_payload_digest TEXT NOT NULL, payload_sha256 TEXT NOT NULL, simhash64 TEXT NOT NULL,
      title TEXT NOT NULL, text_excerpt TEXT NOT NULL, evidence_object_id TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, archive_capture_truth INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_historical_web_diffs_331(
      diff_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      canonical_url TEXT NOT NULL, older_capture_id TEXT NOT NULL, newer_capture_id TEXT NOT NULL,
      change_class TEXT NOT NULL, exact_same INTEGER NOT NULL, near_duplicate INTEGER NOT NULL,
      simhash_hamming INTEGER NOT NULL, sequence_similarity REAL NOT NULL,
      added_excerpt TEXT NOT NULL, removed_excerpt TEXT NOT NULL,
      material_change_candidate INTEGER NOT NULL, automatic_fact_revision INTEGER NOT NULL,
      human_review_required INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_historical_web_mentions_331(
      mention_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      capture_id TEXT NOT NULL, mention_type TEXT NOT NULL, mention_value TEXT NOT NULL,
      normalized_value TEXT NOT NULL, context_excerpt TEXT NOT NULL,
      valid_at_capture_time INTEGER NOT NULL, current_truth_inferred INTEGER NOT NULL,
      candidate_only INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_historical_web_plans_331(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_historical_web_attestations_331(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_331(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_331(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_331(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_histweb_url_time_331 ON phase14_historical_web_captures_331(case_id,target_id,canonical_url,capture_at)',
      'CREATE INDEX IF NOT EXISTS idx_histweb_digest_331 ON phase14_historical_web_captures_331(payload_sha256,simhash64)',
      'CREATE INDEX IF NOT EXISTS idx_histweb_source_331 ON phase14_historical_web_captures_331(source_id,archive_record_id)',
      'CREATE INDEX IF NOT EXISTS idx_histweb_diff_331 ON phase14_historical_web_diffs_331(case_id,target_id,canonical_url,change_class)',
      'CREATE INDEX IF NOT EXISTS idx_histweb_mentions_331 ON phase14_historical_web_mentions_331(case_id,target_id,mention_type,normalized_value)',
    ): db.execute(sql)

    hard=[
      ('An archived capture proves an archive observed a representation at a capture time; it does not by itself prove every statement on the page was true.', ['archive_observation_semantics'], ['archive_equals_truth']),
      ('Historical and current web states must remain temporally separate; old contact/role text cannot be silently promoted to current truth.', ['temporal_truth_guard'], ['historical_equals_current']),
      ('Near-duplicate detection may suppress redundant captures but must preserve materially changed states.', ['simhash_near_duplicate'], ['near_duplicate_drops_material_change']),
      ('Exact payload digest and near-duplicate fingerprint serve different purposes and must not be conflated.', ['digest_vs_similarity'], ['simhash_equals_integrity_hash']),
      ('Common Crawl capture gaps are coverage gaps, not evidence that a page did not exist.', ['coverage_gap_semantics'], ['missing_capture_equals_nonexistence']),
      ('WARC payload/block digests and archive locators must be retained as capture provenance when available.', ['warc_provenance'], ['drop_archive_locator']),
      ('Archive banners, URI rewriting and preservation transformations can alter bytes without changing the historical information represented.', ['memento_representation_caveat'], ['byte_difference_equals_historical_change']),
      ('Historical web changes should generate reviewable change candidates, not automatic fact replacement in the case graph.', ['change_candidate_only'], ['automatic_fact_revision']),
    ]
    sec=[
      ('Historical-web analysis is local-first and does not fetch archive URLs unless a reviewed public connector is explicitly executed.', ['external_execution_false'], ['silent_archive_fetch']),
      ('Original and archive URLs must reject credentials and private/non-global IP targets.', ['public_url_boundary'], ['credential_or_private_url']),
      ('Archive locators are data, not executable commands or shell fragments.', ['locator_data_only'], ['execute_locator']),
      ('Historical capture text remains candidate-only and cannot auto-promote identity, guilt or ownership claims.', ['candidate_only'], ['automatic_truth_promotion']),
      ('Stored capture URLs are never automatically revisited during search, graph or diff operations.', ['no_implicit_network'], ['implicit_url_fetch']),
      ('Source failure or archive gap cannot trigger a direct/proxy-bypass fallback.', ['provider_gate'], ['unsafe_fallback']),
      ('Historical-person mentions require minimization and review before dossier use.', ['privacy_minimization'], ['bulk_person_profile_promotion']),
      ('Historical-web intelligence performs no active external reconnaissance.', ['no_active_recon'], ['active_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_331 VALUES(?,?,?,?,?,?,?)',(f'b331-histweb-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build331-historical-web-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (1,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_331 VALUES(?,?,?,?,?,?,?)',(f'b331-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build331-security-review'))
