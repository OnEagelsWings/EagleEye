from __future__ import annotations
import json
from typing import Any


def ensure_build326_schema(db: Any) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_datasets_326(
      dataset_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, dataset_name TEXT NOT NULL,
      jurisdiction TEXT NOT NULL, record_family TEXT NOT NULL, format_class TEXT NOT NULL,
      key_fields_json TEXT NOT NULL, scope_class TEXT NOT NULL, review_status TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_ingestion_jobs_326(
      job_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      source_id TEXT NOT NULL, mode TEXT NOT NULL, state TEXT NOT NULL, input_sha256 TEXT NOT NULL,
      input_bytes INTEGER NOT NULL, row_cursor INTEGER NOT NULL, rows_seen INTEGER NOT NULL,
      rows_changed INTEGER NOT NULL, rows_quarantined INTEGER NOT NULL, checkpoint_json TEXT NOT NULL,
      external_execution INTEGER NOT NULL, human_approval_required INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_snapshots_326(
      snapshot_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, parent_snapshot_id TEXT NOT NULL,
      case_id TEXT NOT NULL, source_id TEXT NOT NULL, snapshot_mode TEXT NOT NULL,
      dataset_sha256 TEXT NOT NULL, evidence_object_id TEXT NOT NULL, size_bytes INTEGER NOT NULL,
      row_count INTEGER NOT NULL, inserted_count INTEGER NOT NULL, updated_count INTEGER NOT NULL,
      unchanged_count INTEGER NOT NULL, deleted_count INTEGER NOT NULL, quarantined_count INTEGER NOT NULL,
      cdc_algorithm TEXT NOT NULL, chunk_count INTEGER NOT NULL, reused_chunk_count INTEGER NOT NULL,
      reuse_ratio REAL NOT NULL, manifest_relpath TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_chunks_326(
      chunk_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL, byte_offset INTEGER NOT NULL, byte_length INTEGER NOT NULL,
      sha256 TEXT NOT NULL, storage_relpath TEXT NOT NULL, reused INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_record_state_326(
      dataset_id TEXT NOT NULL, record_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
      payload_json TEXT NOT NULL, active INTEGER NOT NULL, first_snapshot_id TEXT NOT NULL,
      latest_snapshot_id TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL,
      PRIMARY KEY(dataset_id,record_key)
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_record_versions_326(
      version_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, snapshot_id TEXT NOT NULL,
      record_key TEXT NOT NULL, operation TEXT NOT NULL, version INTEGER NOT NULL,
      payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, candidate_only INTEGER NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_quarantine_326(
      quarantine_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
      row_number INTEGER NOT NULL, reason TEXT NOT NULL, raw_excerpt TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_manifests_326(
      manifest_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, dataset_id TEXT NOT NULL,
      manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, parent_manifest_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_materializations_326(
      materialization_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, case_id TEXT NOT NULL,
      target_id TEXT NOT NULL, indexed_documents INTEGER NOT NULL, graph_nodes INTEGER NOT NULL,
      graph_assertions INTEGER NOT NULL, limit_applied INTEGER NOT NULL, created_by TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_bulk_plans_326(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_bulk_attestations_326(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_326(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_326(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_326(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE INDEX IF NOT EXISTS idx_bulk_ds_326_source ON phase14_bulk_datasets_326(source_id,record_family,review_status)',
      'CREATE INDEX IF NOT EXISTS idx_bulk_snap_326_dataset ON phase14_bulk_snapshots_326(dataset_id,created_at)',
      'CREATE INDEX IF NOT EXISTS idx_bulk_chunks_326_hash ON phase14_bulk_chunks_326(dataset_id,sha256)',
      'CREATE INDEX IF NOT EXISTS idx_bulk_versions_326_key ON phase14_bulk_record_versions_326(dataset_id,record_key,version)',
      'CREATE INDEX IF NOT EXISTS idx_bulk_jobs_326_case ON phase14_bulk_ingestion_jobs_326(case_id,target_id,created_at)'
    ): db.execute(sql)

    hard=[
      ('Bulk ingestion must be idempotent for identical immutable input.', ['dataset_digest','idempotency_reuse'], ['duplicate_snapshot_inflation']),
      ('Incremental full snapshots must distinguish insert, update, unchanged, and delete.', ['stable_record_key','delta_classification'], ['all_rows_as_new']),
      ('Content-defined chunking should preserve reusable chunks across small shifted changes.', ['gear_hash_chunking','chunk_digest_reuse'], ['fixed_offset_only_dedup']),
      ('Snapshot manifests must retain parent linkage and immutable file inventories.', ['parent_snapshot','manifest_sha256','chunk_inventory'], ['mutable_manifest']),
      ('Malformed records should be quarantined rather than silently becoming evidence.', ['quarantine_reason','bounded_excerpt'], ['silent_parse_coercion']),
      ('AI ingestion planning should prefer provider delta/bulk capabilities when appropriate.', ['source_registry_capabilities','incremental_preference'], ['bulk_equals_truth']),
      ('Changed bulk records may be materialized into local search/graph as candidate-only.', ['bounded_materialization','provenance_links'], ['automatic_verified_evidence']),
      ('Provider zero results and ingestion parse failures remain separate failure classes.', ['failure_taxonomy'], ['semantic_conflation']),
    ]
    sec=[
      ('Bulk ingestion is local-only unless a separate approved acquisition workflow supplies bytes.', ['external_execution_false'], ['silent_download']),
      ('Archive members with traversal or absolute paths must be rejected.', ['zip_path_guard'], ['archive_path_traversal']),
      ('Archive expansion must have member, size, and compression-ratio limits.', ['zip_bomb_guard'], ['unbounded_decompression']),
      ('Record field count and field size must be bounded.', ['row_shape_limits'], ['memory_exhaustion']),
      ('Chunk store paths derive only from validated SHA-256 digests.', ['digest_only_chunk_path'], ['filename_storage_path']),
      ('Manifest and chunks are no-overwrite immutable artifacts.', ['exclusive_create','rehash_existing'], ['overwrite_chunk']),
      ('Source credentials are not persisted in dataset or job records.', ['auth_metadata_only'], ['plaintext_secret']),
      ('Bulk materialization cannot trigger active external reconnaissance.', ['local_index_graph_only'], ['external_probe']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (2,4) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_326 VALUES(?,?,?,?,?,?,?)',(f'b326-bulk-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build326-bulk-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (1,2) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_326 VALUES(?,?,?,?,?,?,?)',(f'b326-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build326-security-review'))
