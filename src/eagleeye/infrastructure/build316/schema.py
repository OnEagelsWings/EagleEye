from __future__ import annotations
import json
from typing import Any

def ensure_build316_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_fabric_snapshots_316(
      snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, source_layers_json TEXT NOT NULL, status TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_fabric_items_316(
      fabric_item_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_layer TEXT NOT NULL, source_record_id TEXT NOT NULL, source_group TEXT NOT NULL,
      item_kind TEXT NOT NULL, field_name TEXT NOT NULL, normalized_value TEXT NOT NULL,
      direction TEXT NOT NULL, weight_class TEXT NOT NULL, independence_key TEXT NOT NULL,
      provenance_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_fabric_links_316(
      fabric_link_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      from_item_id TEXT NOT NULL, to_item_id TEXT NOT NULL, link_type TEXT NOT NULL,
      field_name TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_fabric_assessments_316(
      assessment_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      item_count INTEGER NOT NULL, link_count INTEGER NOT NULL, independent_groups INTEGER NOT NULL,
      support_items INTEGER NOT NULL, counter_items INTEGER NOT NULL, neutral_items INTEGER NOT NULL,
      corroboration_links INTEGER NOT NULL, conflict_links INTEGER NOT NULL, dependency_links INTEGER NOT NULL,
      open_questions_json TEXT NOT NULL, fabric_readiness_score REAL NOT NULL, probability_claim_generated INTEGER NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_security_attestations_316(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase13_dossier_revisions_316(
      dossier316_id TEXT PRIMARY KEY, parent_dossier_id TEXT NOT NULL, case_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
      title TEXT NOT NULL, status TEXT NOT NULL, file_relpath TEXT NOT NULL, content_sha256 TEXT NOT NULL,
      quality_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_316(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_316(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)''')
    for i in range(8):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_316 VALUES(?,?,?,?,?,?,?)',(
          f'b316-fabric-{i+1:02d}',d,'Intelligence Data Fabric must unify candidate records without destroying provenance, dependency, conflicts or alternative explanations.',
          json.dumps(['case_bound_snapshot','immutable_provenance','dependency_links','conflict_links','counterevidence','human_review']),
          json.dumps(['provenance_flattening','duplicate_source_double_counting','conflict_suppression','hit_count_probability','automatic_truth_promotion']),
          'reviewed','build316-fabric-review'))
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_316 VALUES(?,?,?,?,?,?,?)',(
          f'b316-security-{i+1:02d}',d,'Data-fabric automation must remain case-bound, candidate-only, provenance preserving and non-offensive.',
          json.dumps(['case_scope','candidate_only','source_lineage','dependency_retention','no_auto_promotion','review_required']),
          json.dumps(['scope_drift','provenance_loss','automatic_identity_confirmation','probability_from_volume','network_reconfiguration']),
          'reviewed','build316-security-review'))
