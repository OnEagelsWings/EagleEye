from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build337.schema import ensure_build337_schema


def ensure_build338_schema(db: Any) -> None:
    ensure_build337_schema(db)
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossier_profiles_338(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      analytic_standards_json TEXT NOT NULL, red_team_policy_json TEXT NOT NULL,
      release_policy_json TEXT NOT NULL, probability_policy TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossiers_vnext_338(
      dossier_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, supervisor_run_id TEXT NOT NULL,
      parent_dossier_id TEXT NOT NULL, revision_no INTEGER NOT NULL, title TEXT NOT NULL,
      status TEXT NOT NULL, red_team_required INTEGER NOT NULL, human_review_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, production_probability_output INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, closed_at TEXT NOT NULL,
      notes TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossier_claims_338(
      claim_id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL, case_id TEXT NOT NULL,
      claim_type TEXT NOT NULL, claim_text TEXT NOT NULL, materiality TEXT NOT NULL,
      judgment_status TEXT NOT NULL, source_refs_json TEXT NOT NULL, counter_refs_json TEXT NOT NULL,
      assumptions_json TEXT NOT NULL, uncertainty_notes TEXT NOT NULL, temporal_scope TEXT NOT NULL,
      identity_status TEXT NOT NULL, legal_status TEXT NOT NULL, source_independence_required INTEGER NOT NULL,
      automatic_truth INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_red_team_reviews_338(
      review_id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL, case_id TEXT NOT NULL,
      reviewer_role TEXT NOT NULL, verdict TEXT NOT NULL, critical_count INTEGER NOT NULL,
      major_count INTEGER NOT NULL, moderate_count INTEGER NOT NULL, source_echo_count INTEGER NOT NULL,
      unsupported_count INTEGER NOT NULL, assumption_count INTEGER NOT NULL, probability_leak_count INTEGER NOT NULL,
      metrics_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_red_team_findings_338(
      finding_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, dossier_id TEXT NOT NULL,
      claim_id TEXT NOT NULL, severity TEXT NOT NULL, finding_type TEXT NOT NULL,
      description TEXT NOT NULL, remediation TEXT NOT NULL, blocks_release INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_falsification_tests_338(
      test_id TEXT PRIMARY KEY, review_id TEXT NOT NULL, dossier_id TEXT NOT NULL,
      claim_id TEXT NOT NULL, test_type TEXT NOT NULL, description TEXT NOT NULL,
      status TEXT NOT NULL, result TEXT NOT NULL, would_weaken INTEGER NOT NULL,
      would_refute INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossier_human_reviews_338(
      human_review_id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL, red_team_review_id TEXT NOT NULL,
      reviewer TEXT NOT NULL, disposition TEXT NOT NULL, notes TEXT NOT NULL,
      red_team_findings_accepted INTEGER NOT NULL, external_actions_approved INTEGER NOT NULL,
      probability_output_approved INTEGER NOT NULL, evidence_promotion_approved INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossier_releases_338(
      release_id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL, red_team_review_id TEXT NOT NULL,
      human_review_id TEXT NOT NULL, case_id TEXT NOT NULL, release_status TEXT NOT NULL,
      markdown_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL, authorization_phrase_hash TEXT NOT NULL,
      production_probability_output INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      released_by TEXT NOT NULL, released_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_dossier_attestations_338(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_338(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_338(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_338(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_d338_case ON phase14_dossiers_vnext_338(case_id,revision_no,status)',
      'CREATE INDEX IF NOT EXISTS idx_c338_dossier ON phase14_dossier_claims_338(dossier_id,claim_type,materiality)',
      'CREATE INDEX IF NOT EXISTS idx_rt338_dossier ON phase14_red_team_reviews_338(dossier_id,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_rtf338_review ON phase14_red_team_findings_338(review_id,severity,finding_type)',
      'CREATE INDEX IF NOT EXISTS idx_fals338_review ON phase14_falsification_tests_338(review_id,claim_id)',
      'CREATE INDEX IF NOT EXISTS idx_rel338_case ON phase14_dossier_releases_338(case_id,released_at)',
    ): db.execute(sql)
    # Claims are immutable. Rework must create a new dossier revision rather than silently editing analytic history.
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_claim338_no_update BEFORE UPDATE ON phase14_dossier_claims_338 BEGIN SELECT RAISE(ABORT,'phase14_dossier_claims_338 immutable'); END")
    db.execute("CREATE TRIGGER IF NOT EXISTS trg_claim338_no_delete BEFORE DELETE ON phase14_dossier_claims_338 BEGIN SELECT RAISE(ABORT,'phase14_dossier_claims_338 immutable'); END")
    hard=[
      ('Material dossier claims distinguish underlying observations, assessments, hypotheses, counterevidence, conflicts and data gaps.', ['typed_claims','information_vs_judgment'], ['flat_untyped_conclusion']),
      ('A red-team review challenges source quality, independence, assumptions, counterevidence, identity and temporal scope before release.', ['structured_challenge','pre_release_red_team'], ['rubber_stamp_review']),
      ('Multiple citations sharing one origin do not count as independent corroboration.', ['source_echo_detection'], ['citation_count_as_independence']),
      ('High-material assessments expose assumptions and state what evidence would weaken or refute them.', ['assumption_check','falsification_tests'], ['unfalsifiable_claim']),
      ('Failure to find falsifying evidence does not confirm a claim.', ['absence_of_falsification_not_confirmation'], ['failed_falsification_as_proof']),
      ('Dossier revisions are append-only; rework creates a new revision and preserves prior claims/reviews.', ['revision_history','immutable_claims'], ['silent_claim_rewrite']),
      ('Probability-like language is blocked while Build 336 production probability remains unqualified.', ['probability_fail_closed'], ['decorative_percentage_claim']),
      ('Human release approval follows, and cannot replace, structured red-team review.', ['red_team_then_human_review'], ['human_click_bypasses_red_team']),
    ]
    sec=[
      ('Red-team processing is local and does not execute source URLs, embedded instructions or document actions.', ['local_only','source_text_inert'], ['review_causes_network_fetch']),
      ('Red-team findings never mutate original supervisor tasks, evidence objects or dossier claims.', ['review_layer_separation','append_only_findings'], ['review_rewrites_evidence']),
      ('Release requires an exact phrase and an approved human review tied to the latest red-team review.', ['release_authorization','review_binding'], ['silent_release']),
      ('Critical red-team findings block dossier release fail-closed.', ['critical_findings_block'], ['release_despite_critical']),
      ('Identity, legal-finality and temporal conflicts cannot be hidden by source volume.', ['conflict_visibility'], ['majority_vote_truth']),
      ('No dossier release can enable external execution or Build 336 probability output.', ['no_external_execution','probability_gate_preserved'], ['release_unlocks_network_or_probability']),
      ('Case isolation is enforced for dossier, review and release records.', ['case_scope_bound'], ['cross_case_dossier_leak']),
      ('No real active reconnaissance, exploit execution or automatic network reconfiguration is introduced.', ['no_active_recon','no_exploits','no_network_reconfiguration'], ['offensive_counteraction']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        difficulty='extreme' if i in (1,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_338 VALUES(?,?,?,?,?,?,?)',(f'b338-dossier-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build338-dossier-redteam-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        difficulty='extreme' if i in (2,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_338 VALUES(?,?,?,?,?,?,?)',(f'b338-security-{i+1:02d}',difficulty,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build338-security-review'))
