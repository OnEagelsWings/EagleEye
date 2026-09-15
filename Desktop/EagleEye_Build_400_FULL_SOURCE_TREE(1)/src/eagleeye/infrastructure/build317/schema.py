from __future__ import annotations
import json
from typing import Any

def ensure_build317_schema(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS phase13_query_plans_317(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, snapshot_id TEXT,
      objective TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase13_query_actions_317(
      action_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      rank_no INTEGER NOT NULL, question TEXT NOT NULL, hypothesis_link TEXT NOT NULL, query_text TEXT NOT NULL,
      search_mode TEXT NOT NULL, source_focus TEXT NOT NULL, expected_information_gain REAL NOT NULL,
      conflict_resolution_value REAL NOT NULL, independence_value REAL NOT NULL, cost_penalty REAL NOT NULL,
      risk_penalty REAL NOT NULL, priority_score REAL NOT NULL, rationale TEXT NOT NULL, stop_condition TEXT NOT NULL,
      status TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase13_query_feedback_317(
      feedback_id TEXT PRIMARY KEY, action_id TEXT NOT NULL, result_count INTEGER NOT NULL, relevant_count INTEGER NOT NULL,
      new_independent_sources INTEGER NOT NULL, conflicts_resolved INTEGER NOT NULL, useful INTEGER NOT NULL,
      next_decision TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase13_security_attestations_317(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_317(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_317(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_317 VALUES(?,?,?,?,?,?,?)',(f'b317-planner-{i+1:02d}',d,'Planner must choose the next query by expected information gain, conflicts, independence and evidentiary gaps.',json.dumps(['gap_driven_queries','counterevidence','independence','stop_conditions','human_review']),json.dumps(['query_volume_as_quality','hit_count_probability','confirmation_only_search','unbounded_search']), 'reviewed','build317-planner-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_317 VALUES(?,?,?,?,?,?,?)',(f'b317-security-{i+1:02d}',d,'Planner automation remains public-source, bounded, reviewable and non-offensive.',json.dumps(['public_sources','bounded_plan','risk_penalty','review_required']),json.dumps(['scope_drift','active_intrusion','credential_use','automatic_truth_promotion']), 'reviewed','build317-security-review'))
