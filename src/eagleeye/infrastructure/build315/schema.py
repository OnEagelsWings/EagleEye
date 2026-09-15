from __future__ import annotations
import json
from typing import Any

def ensure_build315_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_entity_resolution_runs_315(
      resolution_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, hypothesis_type TEXT NOT NULL,
      hypothesis_text TEXT NOT NULL, source_layers_json TEXT NOT NULL, status TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_entity_resolution_signals_315(
      signal_id TEXT PRIMARY KEY, resolution_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_layer TEXT NOT NULL, source_record_id TEXT NOT NULL, source_group TEXT NOT NULL, field_name TEXT NOT NULL,
      normalized_value TEXT NOT NULL, direction TEXT NOT NULL, weight_class TEXT NOT NULL, independence_key TEXT NOT NULL,
      rationale TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_entity_resolution_assessments_315(
      assessment_id TEXT PRIMARY KEY, resolution_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      support_signals INTEGER NOT NULL, counter_signals INTEGER NOT NULL, neutral_signals INTEGER NOT NULL,
      independent_groups INTEGER NOT NULL, duplicate_dependency_groups INTEGER NOT NULL,
      matched_fields_json TEXT NOT NULL, conflicts_json TEXT NOT NULL, alternative_hypotheses_json TEXT NOT NULL,
      resolution_readiness_score REAL NOT NULL, probability_claim_generated INTEGER NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_security_attestations_315(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_315(
      dossier315_id TEXT PRIMARY KEY, parent_dossier_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL,
      quality_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_315(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_315(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_315 VALUES(?,?,?,?,?,?,?)',(
          f'b315-resolution-{i+1:02d}',d,'Cross-database entity resolution must distinguish corroboration from source duplication and retain alternative hypotheses.',
          json.dumps(['cross_layer_resolution','source_independence','field_level_matching','counterevidence','alternative_hypotheses','human_review']),
          json.dumps(['single_record_identity_confirmation','duplicate_source_double_counting','hit_count_probability','counterevidence_suppression']),
          'reviewed','build315-resolution-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_315 VALUES(?,?,?,?,?,?,?)',(
          f'b315-security-{i+1:02d}',d,'Entity-resolution automation must stay case-bound, candidate-only and must not infer sensitive identity from unsupported correlations.',
          json.dumps(['case_scope','candidate_only','dependency_penalty','provenance_preservation','no_auto_promotion','review_required']),
          json.dumps(['scope_drift','sensitive_inference','automatic_identity_confirmation','probability_from_record_count','provenance_loss']),
          'reviewed','build315-security-review'))
