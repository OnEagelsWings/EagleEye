from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build336.schema import ensure_build336_schema


def ensure_build337_schema(db: Any) -> None:
    ensure_build336_schema(db)
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_profiles_337(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      planning_model TEXT NOT NULL, execution_policy_json TEXT NOT NULL, stop_policy_json TEXT NOT NULL,
      human_oversight_json TEXT NOT NULL, probability_policy TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_runs_337(
      run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, jurisdiction_hint TEXT NOT NULL, authorization_phrase_hash TEXT NOT NULL,
      max_cycles INTEGER NOT NULL, max_actions INTEGER NOT NULL, actions_used INTEGER NOT NULL,
      cycle_count INTEGER NOT NULL, status TEXT NOT NULL, stop_reason TEXT NOT NULL,
      current_phase TEXT NOT NULL, human_review_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, production_probability_output INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_hypotheses_337(
      hypothesis_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      hypothesis_type TEXT NOT NULL, statement TEXT NOT NULL, stance TEXT NOT NULL,
      status TEXT NOT NULL, priority INTEGER NOT NULL, evidence_required_json TEXT NOT NULL,
      support_count INTEGER NOT NULL, counter_count INTEGER NOT NULL,
      automatic_truth INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_requirements_337(
      requirement_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL,
      requirement_type TEXT NOT NULL, description TEXT NOT NULL, source_class TEXT NOT NULL,
      independence_required INTEGER NOT NULL, temporal_required INTEGER NOT NULL,
      status TEXT NOT NULL, coverage_score REAL NOT NULL, evidence_refs_json TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_tasks_337(
      task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      rank_no INTEGER NOT NULL, task_type TEXT NOT NULL, task_name TEXT NOT NULL,
      payload_json TEXT NOT NULL, dependencies_json TEXT NOT NULL, priority_score REAL NOT NULL,
      execution_class TEXT NOT NULL, state TEXT NOT NULL, result_json TEXT NOT NULL,
      human_gate INTEGER NOT NULL, external_execution INTEGER NOT NULL, attempts INTEGER NOT NULL,
      low_information_streak INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_cycles_337(
      cycle_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, cycle_no INTEGER NOT NULL,
      selected_tasks_json TEXT NOT NULL, completed_tasks_json TEXT NOT NULL,
      blocked_tasks_json TEXT NOT NULL, observations_json TEXT NOT NULL,
      stop_decision TEXT NOT NULL, stop_reason TEXT NOT NULL,
      action_count INTEGER NOT NULL, independent_gain INTEGER NOT NULL,
      conflict_resolution_count INTEGER NOT NULL, counterevidence_count INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_feedback_337(
      feedback_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL,
      outcome TEXT NOT NULL, new_evidence_count INTEGER NOT NULL,
      independent_source_count INTEGER NOT NULL, conflicts_resolved INTEGER NOT NULL,
      counterevidence_found INTEGER NOT NULL, notes TEXT NOT NULL,
      next_decision TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_reviews_337(
      review_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reviewer TEXT NOT NULL,
      disposition TEXT NOT NULL, notes TEXT NOT NULL, external_actions_approved INTEGER NOT NULL,
      probability_output_approved INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_supervisor_attestations_337(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_337(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_337(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_337(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_sup337_runs_case ON phase14_supervisor_runs_337(case_id,target_id,status,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_sup337_tasks_run ON phase14_supervisor_tasks_337(run_id,state,priority_score,rank_no)',
      'CREATE INDEX IF NOT EXISTS idx_sup337_req_run ON phase14_supervisor_requirements_337(run_id,status,requirement_type)',
      'CREATE INDEX IF NOT EXISTS idx_sup337_cycles_run ON phase14_supervisor_cycles_337(run_id,cycle_no)',
      'CREATE INDEX IF NOT EXISTS idx_sup337_feedback_task ON phase14_supervisor_feedback_337(task_id,created_at)',
    ): db.execute(sql)
    hard=[
      ('Supervisor decomposes an investigation into explicit hypotheses and evidence requirements rather than treating the objective as established truth.', ['hypothesis_tree','objective_not_truth'], ['objective_as_fact']),
      ('Identity verification is an upstream prerequisite for high-impact relationship conclusions.', ['identity_first','strong_id_veto'], ['fuzzy_name_overrides_identity_conflict']),
      ('Counterevidence and alternative explanations are mandatory branches, not optional cleanup steps.', ['counterhypothesis_required'], ['confirmation_only_plan']),
      ('Local data, documents, temporal states, corporate, financial, procurement and legal packs are inspected before proposing external acquisition.', ['local_first_orchestration'], ['external_search_first']),
      ('Supervisor uses bounded action/cycle budgets and explicit stop criteria.', ['bounded_cycles','bounded_actions'], ['unbounded_agent_loop']),
      ('No new independent evidence across repeated cycles must trigger stop/review rather than repeated searching.', ['low_information_stop'], ['search_forever']),
      ('Planner priority is routing utility / expected information gain, never a probability of guilt, identity or hypothesis truth.', ['utility_not_probability'], ['priority_as_probability']),
      ('Supervisor decision records expose rationale codes and evidence references without persisting hidden chain-of-thought.', ['auditable_decision_codes'], ['private_reasoning_trace_storage']),
    ]
    sec=[
      ('Every supervisor run requires exact single-run human authorization and remains case/target bound.', ['single_run_authorization','scope_bound'], ['silent_autonomous_run']),
      ('External acquisition tasks are proposals only and cannot execute network access without a separate human gate.', ['external_human_gate'], ['automatic_external_execution']),
      ('Private network, credentials, login automation and exploit actions remain prohibited.', ['private_network_fail_closed','no_credentials','no_exploits'], ['active_intrusion']),
      ('Probability calibration from Build 336 remains fail-closed and cannot be activated by the supervisor.', ['probability_gate_preserved'], ['supervisor_activates_probability']),
      ('Document/source text remains inert data and cannot become executable supervisor instructions.', ['prompt_injection_boundary'], ['source_text_as_command']),
      ('Human review is required before evidence promotion or high-impact conclusions.', ['human_review_before_promotion'], ['automatic_truth_promotion']),
      ('Source independence and counterevidence are preserved through orchestration.', ['source_independence','counterevidence_preserved'], ['source_echo_as_corroboration']),
      ('No real active external reconnaissance or automatic network reconfiguration is introduced.', ['no_active_recon','no_network_reconfiguration'], ['offensive_counteraction']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_337 VALUES(?,?,?,?,?,?,?)',(f'b337-supervisor-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build337-supervisor-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (1,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_337 VALUES(?,?,?,?,?,?,?)',(f'b337-security-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb,ensure_ascii=False),'reviewed','build337-security-review'))
