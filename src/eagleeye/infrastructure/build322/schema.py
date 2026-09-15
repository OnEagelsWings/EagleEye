from __future__ import annotations
import json
from typing import Any


def ensure_build322_schema(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_evidence_objects_322(
      object_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
      media_type TEXT NOT NULL, storage_relpath TEXT NOT NULL, original_name TEXT NOT NULL, source_uri TEXT NOT NULL,
      acquisition_method TEXT NOT NULL, storage_class TEXT NOT NULL, immutable INTEGER NOT NULL, deduplicated INTEGER NOT NULL,
      chunk_size INTEGER NOT NULL, chunk_count INTEGER NOT NULL, chunk_merkle_root TEXT NOT NULL, manifest_json TEXT NOT NULL,
      first_seen_at TEXT NOT NULL, recorded_by TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_phase14_evidence_objects_322_case ON phase14_evidence_objects_322(case_id, first_seen_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_phase14_evidence_objects_322_sha ON phase14_evidence_objects_322(sha256)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_evidence_ledger_322(
      seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, object_id TEXT NOT NULL,
      event_type TEXT NOT NULL, event_json TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_merkle_checkpoints_322(
      checkpoint_id TEXT PRIMARY KEY, leaf_count INTEGER NOT NULL, merkle_root TEXT NOT NULL, last_event_hash TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_provenance_relations_322(
      relation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, subject_id TEXT NOT NULL, relation_type TEXT NOT NULL,
      object_id TEXT NOT NULL, activity_id TEXT NOT NULL, agent_id TEXT NOT NULL, attributes_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_phase14_prov_322_case ON phase14_provenance_relations_322(case_id, object_id)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_evidence_packages_322(
      package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, manifest_relpath TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
      object_count INTEGER NOT NULL, total_bytes INTEGER NOT NULL, merkle_root TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_object_store_attestations_322(
      attestation_id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, result TEXT NOT NULL,
      controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_ai_evidence_plans_322(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_322(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_322(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_322(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    hard=[
      ('cas','Raw evidence bytes should be addressed by a collision-resistant content digest.', ['sha256_content_address','deduplicate_without_rewriting'], ['filename_as_identity']),
      ('immutability','Existing content-addressed evidence must never be overwritten.', ['exclusive_create','verify_existing_digest'], ['overwrite_blob']),
      ('merkle','Large artifacts need chunk-level integrity localization and a whole-artifact Merkle root.', ['chunk_hashes','merkle_root'], ['single_unchecked_chunk']),
      ('ledger','Evidence intake history should be append-only and tamper-evident.', ['prev_hash_chain','checkpoint_root'], ['mutable_history']),
      ('provenance','Raw evidence and AI-derived artifacts must remain explicitly related but distinct.', ['wasDerivedFrom','wasGeneratedBy','agent_attribution'], ['derived_as_original']),
      ('manifest','Case evidence exports require complete digest manifests.', ['all_objects_manifested','manifest_sha256'], ['partial_unmarked_export']),
      ('local_first_ai','AI should inspect verified local originals before external acquisition.', ['verify_then_extract','gap_driven_external'], ['blind_requery']),
      ('counterevidence','AI evidence planning must retain counterevidence and provenance gaps.', ['counterevidence_action','provenance_gap_action'], ['support_only_plan'])]
    sec=[
      ('path_boundary','Blob path must be derived only from validated digest.', ['digest_only_path'], ['source_filename_path']),
      ('raw_readonly','Stored raw object is immutable-by-policy and best-effort read-only on filesystem.', ['immutable_flag','readonly_attempt'], ['rewrite_raw']),
      ('hash_verify','Existing deduplicated blob must be rehashed before reuse.', ['rehash_existing'], ['trust_filename_digest']),
      ('ledger_integrity','Ledger verification must fail on chain mismatch.', ['recompute_event_hash'], ['skip_chain_check']),
      ('checkpoint','Merkle checkpoint must be reproducible from ledger leaves.', ['recompute_root'], ['unchecked_checkpoint']),
      ('secrets','Evidence metadata must not contain backend credentials.', ['no_secret_field'], ['plaintext_secret']),
      ('external_gate','AI plan may propose external acquisition but cannot execute it automatically.', ['human_approval_required'], ['auto_external_fetch']),
      ('active_recon','Evidence-store work must not enable active external reconnaissance.', ['real_active_recon_disabled'], ['scan_external_target'])]
    for i,(_,sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_322 VALUES(?,?,?,?,?,?,?)',(f'b322-evidence-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build322-evidence-review'))
    for i,(_,sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_322 VALUES(?,?,?,?,?,?,?)',(f'b322-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build322-security-review'))
