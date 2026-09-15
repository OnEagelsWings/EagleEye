from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build335.schema import ensure_build335_schema


def ensure_build336_schema(db: Any) -> None:
    ensure_build335_schema(db)
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_profiles_336(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      task_type TEXT NOT NULL, calibration_method TEXT NOT NULL, holdout_policy_json TEXT NOT NULL,
      qualification_policy_json TEXT NOT NULL, probability_output_status TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_datasets_336(
      dataset_id TEXT PRIMARY KEY, dataset_name TEXT NOT NULL, task_type TEXT NOT NULL,
      entity_type TEXT NOT NULL, dataset_kind TEXT NOT NULL, truth_source TEXT NOT NULL,
      source_benchmark_id TEXT NOT NULL, sample_count INTEGER NOT NULL,
      positive_count INTEGER NOT NULL, negative_count INTEGER NOT NULL,
      independent_adjudication INTEGER NOT NULL, pii_stored INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_samples_336(
      sample_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, sample_key TEXT NOT NULL,
      raw_score REAL NOT NULL, truth_label INTEGER NOT NULL, split_name TEXT NOT NULL,
      difficulty TEXT NOT NULL, subgroup_key TEXT NOT NULL, source_pair_id TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_models_336(
      model_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, model_name TEXT NOT NULL,
      method TEXT NOT NULL, parameters_json TEXT NOT NULL, train_count INTEGER NOT NULL,
      train_positive INTEGER NOT NULL, train_negative INTEGER NOT NULL,
      holdout_count INTEGER NOT NULL, feature_profile TEXT NOT NULL,
      activation_status TEXT NOT NULL, probability_scope TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_evaluations_336(
      evaluation_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
      split_name TEXT NOT NULL, sample_count INTEGER NOT NULL,
      positive_count INTEGER NOT NULL, negative_count INTEGER NOT NULL,
      brier_score REAL NOT NULL, baseline_brier REAL NOT NULL, log_loss REAL NOT NULL,
      ece REAL NOT NULL, mce REAL NOT NULL, roc_auc REAL NOT NULL,
      metrics_json TEXT NOT NULL, probability_qualified INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_bins_336(
      bin_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, bin_index INTEGER NOT NULL,
      lower_bound REAL NOT NULL, upper_bound REAL NOT NULL, sample_count INTEGER NOT NULL,
      mean_predicted REAL NOT NULL, observed_rate REAL NOT NULL,
      wilson_low REAL NOT NULL, wilson_high REAL NOT NULL,
      absolute_gap REAL NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_qualifications_336(
      qualification_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
      status TEXT NOT NULL, reasons_json TEXT NOT NULL, gates_json TEXT NOT NULL,
      production_probability_output INTEGER NOT NULL, human_approval_required INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_calibration_attestations_336(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_336(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_336(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_336(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_cal336_samples_dataset ON phase14_calibration_samples_336(dataset_id,split_name,truth_label,raw_score)',
      'CREATE INDEX IF NOT EXISTS idx_cal336_eval_model ON phase14_calibration_evaluations_336(model_id,split_name,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_cal336_bins_eval ON phase14_calibration_bins_336(evaluation_id,bin_index)',
      'CREATE INDEX IF NOT EXISTS idx_cal336_qual_model ON phase14_calibration_qualifications_336(model_id,created_at)',
    ): db.execute(sql)
    hard=[
      ('Evidence scores must not be shown as probabilities until an independently adjudicated operational calibration passes held-out qualification.', ['probability_output_gate'], ['score_as_probability']),
      ('Calibration fitting and evaluation datasets must be disjoint and the split must be deterministic and auditable.', ['disjoint_holdout'], ['train_eval_leakage']),
      ('Brier score must be reported with a prevalence baseline because it reflects both calibration and discrimination.', ['brier_with_baseline'], ['brier_alone_equals_calibration']),
      ('Binned ECE is descriptive and bin-dependent; reliability bins and uncertainty intervals remain visible.', ['ece_descriptive'], ['ece_as_exact_truth']),
      ('Small calibration corpora must remain unqualified; ambiguous statistical evidence cannot unlock production percentages.', ['minimum_sample_gate'], ['small_fixture_probability_activation']),
      ('Isotonic calibration must not be selected on small datasets where overfitting risk is high.', ['isotonic_sample_guard'], ['small_sample_isotonic']),
      ('Calibration is task and feature-profile scoped; out-of-domain scores cannot reuse a model silently.', ['scope_binding'], ['cross_task_probability_reuse']),
      ('A good calibration metric cannot override Entity Resolution strong-ID conflict veto or human review policy.', ['er_veto_preserved'], ['probability_overrides_identifier_conflict']),
    ]
    sec=[
      ('Calibration runs are local-only and perform no network calls.', ['offline_calibration'], ['implicit_network_lookup']),
      ('Calibration artifacts store scores/labels and opaque sample IDs, not raw person/company records.', ['no_raw_pii_in_model_artifact'], ['raw_record_replication']),
      ('No model is auto-activated for production probability output.', ['human_activation_gate'], ['silent_probability_activation']),
      ('Unqualified lab probability must never appear as dossier fact probability.', ['dossier_probability_guard'], ['lab_probability_as_case_probability']),
      ('Case boundaries and source benchmark references remain explicit.', ['scope_provenance'], ['cross_case_probability_join']),
      ('Calibration inputs are inert numeric/label data and cannot execute code or tool instructions.', ['calibration_data_inert'], ['sample_as_command']),
      ('No external enrichment, active reconnaissance, or credential acquisition is introduced.', ['no_external_enrichment'], ['active_external_enrichment']),
      ('Qualification failure is fail-closed: output remains not qualified.', ['fail_closed_probability'], ['fail_open_probability']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_336 VALUES(?,?,?,?,?,?,?)',(f'b336-cal-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb),'reviewed','build336-calibration-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_336 VALUES(?,?,?,?,?,?,?)',(f'b336-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build336-security-review'))
