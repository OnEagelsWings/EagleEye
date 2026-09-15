from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build333.schema import ensure_build333_schema


def ensure_build334_schema(db: Any) -> None:
    ensure_build333_schema(db)
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_profiles_334(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      comparison_policy_json TEXT NOT NULL, threshold_policy_json TEXT NOT NULL,
      calibration_status TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_benchmarks_334(
      benchmark_id TEXT PRIMARY KEY, benchmark_name TEXT NOT NULL, entity_type TEXT NOT NULL,
      benchmark_kind TEXT NOT NULL, description TEXT NOT NULL, pair_count INTEGER NOT NULL,
      truth_source TEXT NOT NULL, adjudication_policy TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_ground_truth_pairs_334(
      pair_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL, entity_type TEXT NOT NULL,
      left_record_json TEXT NOT NULL, right_record_json TEXT NOT NULL,
      truth_label INTEGER NOT NULL, label_basis TEXT NOT NULL, languages_json TEXT NOT NULL,
      scripts_json TEXT NOT NULL, difficulty TEXT NOT NULL, adjudicated INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_pair_scores_334(
      score_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL, pair_id TEXT NOT NULL,
      evidence_score REAL NOT NULL, decision TEXT NOT NULL, review_required INTEGER NOT NULL,
      blocking_passed INTEGER NOT NULL, hard_veto INTEGER NOT NULL,
      features_json TEXT NOT NULL, explanation_json TEXT NOT NULL,
      truth_label INTEGER, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_benchmark_runs_334(
      run_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL,
      match_threshold REAL NOT NULL, nonmatch_threshold REAL NOT NULL,
      tp INTEGER NOT NULL, fp INTEGER NOT NULL, tn INTEGER NOT NULL, fn INTEGER NOT NULL,
      review_count INTEGER NOT NULL, precision REAL NOT NULL, recall REAL NOT NULL,
      f1 REAL NOT NULL, specificity REAL NOT NULL, fmr REAL NOT NULL, fnmr REAL NOT NULL,
      auto_coverage REAL NOT NULL, metrics_json TEXT NOT NULL,
      calibrated_probability INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_threshold_sweeps_334(
      sweep_id TEXT PRIMARY KEY, benchmark_id TEXT NOT NULL, thresholds_json TEXT NOT NULL,
      results_json TEXT NOT NULL, recommended_match_threshold REAL NOT NULL,
      recommended_nonmatch_threshold REAL NOT NULL, criterion TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_er_attestations_334(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_334(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_334(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_334(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_er334_pair_benchmark ON phase14_er_ground_truth_pairs_334(benchmark_id,truth_label,difficulty)',
      'CREATE INDEX IF NOT EXISTS idx_er334_score_benchmark ON phase14_er_pair_scores_334(benchmark_id,decision,evidence_score)',
      'CREATE INDEX IF NOT EXISTS idx_er334_run_benchmark ON phase14_er_benchmark_runs_334(benchmark_id,created_at)',
    ): db.execute(sql)
    hard=[
      ('Strong public identifiers may be high-value linkage evidence; a conflicting strong identifier must veto automatic matching.', ['strong_identifier_positive_and_conflict_veto'], ['fuzzy_name_overrides_identifier_conflict']),
      ('Name similarity alone must never auto-merge people or companies across ambiguous records.', ['name_only_review'], ['name_only_auto_merge']),
      ('Common names must carry less discriminating weight than rare names; term frequency affects linkage evidence, not truth probability.', ['term_frequency_adjustment'], ['common_name_overweight']),
      ('Multilingual/transliterated variants are comparison candidates; script conversion alone cannot establish identity.', ['multilingual_candidate_only'], ['transliteration_equals_identity']),
      ('Ground-truth evaluation must report TP FP TN FN, precision, recall, F1, specificity, FMR and FNMR.', ['ground_truth_metrics'], ['readiness_score_as_accuracy']),
      ('Thresholds must be benchmarked and ambiguous pairs must remain clerical/human review candidates.', ['review_band'], ['force_binary_all_pairs']),
      ('Missing values are absence of evidence, not disagreement.', ['missing_not_conflict'], ['missing_as_mismatch']),
      ('Temporal conflicts or mutually exclusive identifiers must remain visible as counterevidence.', ['temporal_identifier_conflict'], ['conflict_suppression']),
    ]
    sec=[
      ('Entity resolution is local-only and performs no provider calls while scoring or benchmarking.', ['offline_scoring'], ['implicit_network_lookup']),
      ('Benchmark labels and pair records are inert data and cannot execute code, SQL, shell or tool instructions.', ['benchmark_data_inert'], ['record_as_command']),
      ('No automatic identity merge is performed by Build 334.', ['no_auto_merge'], ['silent_identity_merge']),
      ('Cross-case target data must not be joined implicitly.', ['case_isolation'], ['cross_case_implicit_join']),
      ('Only lawful supplied/public fields are compared.', ['public_or_supplied_fields_only'], ['private_identifier_enrichment']),
      ('Scores are evidence weights, not calibrated probabilities.', ['score_not_probability'], ['score_rendered_as_probability']),
      ('Threshold tuning cannot silently activate a new model.', ['human_reviewed_thresholds'], ['auto_activate_threshold_model']),
      ('No active reconnaissance or external enrichment is introduced.', ['no_active_recon'], ['active_external_enrichment']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,1) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_334 VALUES(?,?,?,?,?,?,?)',(f'b334-er-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb),'reviewed','build334-entity-resolution-v2-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_334 VALUES(?,?,?,?,?,?,?)',(f'b334-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build334-security-review'))
