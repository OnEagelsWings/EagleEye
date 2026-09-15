from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build334.schema import ensure_build334_schema


def ensure_build335_schema(db: Any) -> None:
    ensure_build334_schema(db)
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_profiles_335(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      valid_time_model TEXT NOT NULL, system_time_model TEXT NOT NULL, interval_semantics TEXT NOT NULL,
      correction_policy_json TEXT NOT NULL, review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_entity_states_335(
      state_id TEXT PRIMARY KEY, logical_key TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      entity_key TEXT NOT NULL, entity_type TEXT NOT NULL, state_type TEXT NOT NULL, value_json TEXT NOT NULL,
      valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, observed_at TEXT NOT NULL,
      system_from TEXT NOT NULL, system_to TEXT NOT NULL,
      source_group TEXT NOT NULL, source_ref TEXT NOT NULL, evidence_object_id TEXT NOT NULL,
      dependency_key TEXT NOT NULL, assertion_status TEXT NOT NULL, cardinality TEXT NOT NULL,
      correction_of TEXT NOT NULL, created_by TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_relationship_states_335(
      relationship_state_id TEXT PRIMARY KEY, logical_key TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      subject_entity_key TEXT NOT NULL, predicate TEXT NOT NULL, object_entity_key TEXT NOT NULL, object_literal TEXT NOT NULL,
      valid_from TEXT NOT NULL, valid_to TEXT NOT NULL, observed_at TEXT NOT NULL,
      system_from TEXT NOT NULL, system_to TEXT NOT NULL,
      source_group TEXT NOT NULL, source_ref TEXT NOT NULL, evidence_object_id TEXT NOT NULL,
      dependency_key TEXT NOT NULL, polarity TEXT NOT NULL, assertion_status TEXT NOT NULL,
      correction_of TEXT NOT NULL, created_by TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_conflicts_335(
      conflict_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, conflict_type TEXT NOT NULL,
      left_ref TEXT NOT NULL, right_ref TEXT NOT NULL, interval_relation TEXT NOT NULL,
      independent_source_groups INTEGER NOT NULL, explanation_json TEXT NOT NULL,
      review_status TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_query_runs_335(
      query_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, entity_key TEXT NOT NULL,
      valid_at TEXT NOT NULL, known_at TEXT NOT NULL, result_count INTEGER NOT NULL,
      conflicts_visible INTEGER NOT NULL, result_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_graph_materializations_335(
      materialization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, entity_key TEXT NOT NULL,
      valid_at TEXT NOT NULL, nodes_created INTEGER NOT NULL, assertions_created INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_ai_temporal_plans_335(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      entity_key TEXT NOT NULL, as_of_time TEXT NOT NULL, actions_json TEXT NOT NULL,
      external_execution INTEGER NOT NULL, human_approval_required INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_temporal_attestations_335(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_335(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_335(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_335(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )""")
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_temporal335_entity ON phase14_temporal_entity_states_335(case_id,target_id,entity_key,state_type,valid_from,valid_to)',
      'CREATE INDEX IF NOT EXISTS idx_temporal335_entity_system ON phase14_temporal_entity_states_335(logical_key,system_from,system_to)',
      'CREATE INDEX IF NOT EXISTS idx_temporal335_rel ON phase14_temporal_relationship_states_335(case_id,target_id,subject_entity_key,predicate,valid_from,valid_to)',
      'CREATE INDEX IF NOT EXISTS idx_temporal335_rel_system ON phase14_temporal_relationship_states_335(logical_key,system_from,system_to)',
      'CREATE INDEX IF NOT EXISTS idx_temporal335_conflict ON phase14_temporal_conflicts_335(case_id,target_id,conflict_type,created_at)',
    ): db.execute(sql)
    hard=[
      ('Valid time and system/known time must remain separate; a later discovery must not rewrite when a fact allegedly applied.', ['bitemporal_valid_and_system_time'], ['collapse_valid_and_known_time']),
      ('Adjacent states use half-open [start,end) intervals so a handover at the same timestamp does not create a false overlap.', ['half_open_intervals'], ['closed_interval_false_overlap']),
      ('A historical address, role or owner must not be rendered as current without an as-of query.', ['as_of_required'], ['historical_promoted_to_current']),
      ('Conflicting overlapping singular states remain visible and require human review.', ['temporal_conflict_visible'], ['conflict_suppression']),
      ('Same-value observations from dependent source copies must not count as independent temporal corroboration.', ['dependency_preserved'], ['source_echo_temporal_confirmation']),
      ('Corrections close system time and append a replacement version; they do not erase the prior knowledge state.', ['bitemporal_correction'], ['destructive_history_rewrite']),
      ('Unknown valid_to means open-ended candidate validity, not certainty that the state remains current.', ['open_end_candidate'], ['open_end_equals_current_truth']),
      ('Temporal entity resolution may use time compatibility as evidence but may not auto-merge identities.', ['temporal_er_candidate_only'], ['temporal_overlap_auto_merge']),
    ]
    sec=[
      ('Temporal reconstruction is local-only and performs no provider calls.', ['offline_temporal_reconstruction'], ['implicit_network_lookup']),
      ('Temporal values and source strings are inert data.', ['temporal_data_inert'], ['temporal_value_as_command']),
      ('No automatic identity merge or current-truth promotion occurs.', ['no_auto_merge_or_current_truth'], ['silent_identity_merge']),
      ('Case and target boundaries are enforced for temporal states and graph materialization.', ['case_target_isolation'], ['cross_case_temporal_join']),
      ('Evidence references must belong to the same case when supplied.', ['same_case_evidence'], ['cross_case_evidence_binding']),
      ('Corrections preserve audit history and cannot delete previous system-time versions.', ['audit_history_preserved'], ['history_delete']),
      ('Temporal conflicts are review signals, not guilt or fraud labels.', ['conflict_not_criminality'], ['temporal_conflict_criminality']),
      ('No active reconnaissance, credential lookup, or external enrichment is introduced.', ['no_active_recon'], ['active_external_enrichment']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (2,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_335 VALUES(?,?,?,?,?,?,?)',(f'b335-temporal-{i+1:02d}',d,sc,json.dumps(exp,ensure_ascii=False),json.dumps(forb),'reviewed','build335-temporal-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_335 VALUES(?,?,?,?,?,?,?)',(f'b335-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build335-security-review'))
