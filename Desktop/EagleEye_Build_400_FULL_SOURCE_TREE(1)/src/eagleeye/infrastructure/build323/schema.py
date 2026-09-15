from __future__ import annotations
import json
from typing import Any


def ensure_build323_schema(db: Any) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_backend_profiles_323(
      profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, backend TEXT NOT NULL, mode TEXT NOT NULL,
      semantic_backend TEXT NOT NULL, config_json TEXT NOT NULL, connected INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_documents_323(
      document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, object_id TEXT NOT NULL,
      title TEXT NOT NULL, source_uri TEXT NOT NULL, source_group TEXT NOT NULL, media_type TEXT NOT NULL,
      provenance_status TEXT NOT NULL, body_sha256 TEXT NOT NULL, passage_count INTEGER NOT NULL,
      indexed_at TEXT NOT NULL, indexed_by TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_search_docs_323_case ON phase14_search_documents_323(case_id,target_id,indexed_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_search_docs_323_object ON phase14_search_documents_323(object_id)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_passages_323(
      passage_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL, title TEXT NOT NULL,
      anchors TEXT NOT NULL, body TEXT NOT NULL, source_uri TEXT NOT NULL, source_group TEXT NOT NULL,
      provenance_status TEXT NOT NULL, passage_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
      integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_search_passages_323_case ON phase14_search_passages_323(case_id,target_id,document_id)")
    # Standalone FTS table keeps portable mode self-contained. User text is compiled into a quoted token query.
    db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS phase14_search_fts_323 USING fts5(
      passage_id UNINDEXED, case_id UNINDEXED, target_id UNINDEXED, title, anchors, body,
      tokenize='unicode61 remove_diacritics 2')""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_runs_323(
      run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, query_text TEXT NOT NULL,
      compiled_query TEXT NOT NULL, result_count INTEGER NOT NULL, source_group_count INTEGER NOT NULL,
      fusion_method TEXT NOT NULL, semantic_backend_used INTEGER NOT NULL, zero_result_action TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_ai_index_plans_323(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, objective TEXT NOT NULL,
      plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL, external_execution INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_judgments_323(
      judgment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, query_text TEXT NOT NULL,
      document_id TEXT NOT NULL, relevance_grade INTEGER NOT NULL, judged_by TEXT NOT NULL, created_at TEXT NOT NULL,
      integrity_hash TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_search_judgments_323_query ON phase14_search_judgments_323(case_id,target_id,query_text)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_evaluations_323(
      evaluation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, query_text TEXT NOT NULL,
      k INTEGER NOT NULL, metrics_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_search_attestations_323(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS phase14_security_attestations_323(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
      created_at TEXT NOT NULL, integrity_hash TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_hard_training_delta_323(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_security_training_delta_323(
      case_id TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL, expected_json TEXT NOT NULL,
      forbidden_json TEXT NOT NULL, review_status TEXT NOT NULL, reviewer TEXT NOT NULL)""")
    hard=[
      ('bm25','Investigation search should rank exact domain terms with BM25 instead of raw hit counts.', ['bm25_rank','field_weights'], ['count_equals_truth']),
      ('field_aware','Identity anchors and titles should receive higher retrieval weight than generic body text.', ['title_anchor_weighting'], ['body_only_rank']),
      ('passages','Long evidence documents should be indexed as bounded overlapping passages with stable offsets.', ['passage_offsets','overlap'], ['whole_document_only']),
      ('rrf','Independent retrieval channels may be fused by rank without pretending their raw scores share a scale.', ['rrf_rank_fusion'], ['raw_score_addition']),
      ('provenance','Search results must retain object/source/provenance linkage.', ['source_group','object_link'], ['orphan_result']),
      ('evidence_boundary','Retrieval relevance must not be presented as evidential weight or probability.', ['relevance_only_label'], ['relevance_as_truth']),
      ('zero_result','Zero local results should trigger broadening or source-gap planning, not confidence collapse.', ['broaden_on_zero'], ['zero_means_false']),
      ('counterevidence','AI local search should explicitly retrieve counterevidence perspectives before external acquisition.', ['counter_query','source_diversity'], ['support_only_retrieval'])]
    sec=[
      ('fts_input','User search strings must be token-limited and quoted before FTS MATCH execution.', ['safe_query_compiler'], ['raw_fts_operator_passthrough']),
      ('local_default','Portable investigation search must remain local by default.', ['local_fts5'], ['automatic_remote_search']),
      ('semantic_boundary','Semantic/vector backend is declared but not connected automatically.', ['semantic_declared_not_connected'], ['silent_embedding_egress']),
      ('source_uri','Indexed source URIs are metadata and must not be fetched as a search side effect.', ['no_search_side_fetch'], ['implicit_fetch']),
      ('provenance','Search result provenance must not be dropped during fusion.', ['provenance_preserved'], ['fused_orphan']),
      ('score_boundary','RRF/BM25 scores must not become probability or evidence-strength claims.', ['score_not_probability'], ['score_as_probability']),
      ('external_gate','External source-gap acquisition remains human-approved.', ['human_gate'], ['autonomous_external_execution']),
      ('active_recon','Search-index work must not activate external reconnaissance.', ['real_active_recon_disabled'], ['scan_from_search'])]
    for i,(_,sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_323 VALUES(?,?,?,?,?,?,?)',(f'b323-search-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build323-search-review'))
    for i,(_,sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (6,7) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_323 VALUES(?,?,?,?,?,?,?)',(f'b323-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build323-security-review'))
