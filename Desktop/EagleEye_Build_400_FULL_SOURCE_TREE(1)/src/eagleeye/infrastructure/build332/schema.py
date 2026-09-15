from __future__ import annotations
import json
from typing import Any
from eagleeye.infrastructure.build331.schema import ensure_build331_schema


def ensure_build332_schema(db: Any) -> None:
    ensure_build331_schema(db)
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_profiles_332(
      profile_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL, profile_version TEXT NOT NULL,
      parser_engine TEXT NOT NULL, structure_policy_json TEXT NOT NULL,
      provenance_policy_json TEXT NOT NULL, review_status TEXT NOT NULL,
      created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_documents_332(
      document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      evidence_object_id TEXT NOT NULL, original_name TEXT NOT NULL, media_type TEXT NOT NULL,
      source_uri TEXT NOT NULL, source_group TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
      page_count INTEGER NOT NULL, extraction_engine TEXT NOT NULL, text_layer_present INTEGER NOT NULL,
      ocr_status TEXT NOT NULL, needs_ocr_review INTEGER NOT NULL, candidate_only INTEGER NOT NULL,
      review_status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_pages_332(
      page_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      page_number INTEGER NOT NULL, width REAL NOT NULL, height REAL NOT NULL,
      text_chars INTEGER NOT NULL, block_count INTEGER NOT NULL, table_count INTEGER NOT NULL,
      image_block_count INTEGER NOT NULL, needs_ocr_review INTEGER NOT NULL,
      page_text_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_blocks_332(
      block_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, page_id TEXT NOT NULL,
      case_id TEXT NOT NULL, target_id TEXT NOT NULL, page_number INTEGER NOT NULL,
      reading_order INTEGER NOT NULL, block_type TEXT NOT NULL, heading_level INTEGER NOT NULL,
      section_path TEXT NOT NULL, bbox_json TEXT NOT NULL, text_content TEXT NOT NULL,
      text_sha256 TEXT NOT NULL, extraction_confidence TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_tables_332(
      table_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, page_id TEXT NOT NULL,
      case_id TEXT NOT NULL, target_id TEXT NOT NULL, page_number INTEGER NOT NULL,
      table_index INTEGER NOT NULL, bbox_json TEXT NOT NULL, row_count INTEGER NOT NULL,
      column_count INTEGER NOT NULL, header_json TEXT NOT NULL, cells_json TEXT NOT NULL,
      markdown_text TEXT NOT NULL, extraction_method TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_observations_332(
      observation_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, block_id TEXT NOT NULL,
      case_id TEXT NOT NULL, target_id TEXT NOT NULL, page_number INTEGER NOT NULL,
      observation_type TEXT NOT NULL, observation_value TEXT NOT NULL,
      normalized_json TEXT NOT NULL, context_excerpt TEXT NOT NULL,
      source_locator TEXT NOT NULL, extraction_method TEXT NOT NULL,
      candidate_only INTEGER NOT NULL, automatic_fact_promotion INTEGER NOT NULL,
      human_review_required INTEGER NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_materializations_332(
      materialization_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      document_id TEXT NOT NULL, search_documents_created INTEGER NOT NULL,
      graph_nodes_created INTEGER NOT NULL, graph_assertions_created INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_ai_document_plans_332(
      plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
      objective TEXT NOT NULL, plan_json TEXT NOT NULL, human_approval_required INTEGER NOT NULL,
      external_execution INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_document_attestations_332(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS phase14_security_attestations_332(
      attestation_id TEXT PRIMARY KEY, result TEXT NOT NULL, controls_json TEXT NOT NULL,
      metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_hard_training_delta_332(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS ai_security_training_delta_332(
      case_key TEXT PRIMARY KEY, difficulty TEXT NOT NULL, scenario TEXT NOT NULL,
      expected_json TEXT NOT NULL, forbidden_json TEXT NOT NULL,
      review_status TEXT NOT NULL, review_note TEXT NOT NULL
    )''')
    for sql in (
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_doc332_unique_object ON phase14_documents_332(case_id,target_id,evidence_object_id)',
      'CREATE INDEX IF NOT EXISTS idx_doc332_pages ON phase14_document_pages_332(document_id,page_number)',
      'CREATE INDEX IF NOT EXISTS idx_doc332_blocks ON phase14_document_blocks_332(document_id,page_number,reading_order)',
      'CREATE INDEX IF NOT EXISTS idx_doc332_tables ON phase14_document_tables_332(document_id,page_number,table_index)',
      'CREATE INDEX IF NOT EXISTS idx_doc332_obs ON phase14_document_observations_332(case_id,target_id,observation_type,page_number)',
    ): db.execute(sql)

    hard=[
      ('Document intelligence must preserve page and region provenance instead of flattening every source into unlocated text.', ['page_region_provenance'], ['text_dump_without_locator']),
      ('Reading order is a derived layout interpretation and must remain separate from the immutable original evidence bytes.', ['derived_reading_order'], ['rewrite_original']),
      ('Tables must retain row/column structure and page/bounding-box provenance; whitespace-flattened text is not equivalent.', ['table_structure'], ['flatten_table_semantics']),
      ('A monetary string extracted from a document is an observation candidate, not a documented financial flow unless payer, payee, amount, currency and temporal/source context are explicitly established.', ['amount_candidate_only'], ['amount_equals_flow']),
      ('A role mention such as Director: Alice is a document observation candidate and must not auto-update current corporate truth.', ['role_candidate_only'], ['role_auto_truth']),
      ('Sparse-text or scanned pages should be flagged for OCR review; absence of extracted text is not absence of content.', ['ocr_gap_semantics'], ['no_text_equals_blank_page']),
      ('Section hierarchy and heading detection are heuristic document-structure aids and not evidential claims.', ['heading_heuristic'], ['heading_equals_fact']),
      ('Derived search/graph materialization must point back to evidence object, document, page and block/table locator.', ['provenance_chain'], ['derived_without_source_locator']),
    ]
    sec=[
      ('Document parsing is local-first and must not upload documents to external OCR or extraction services by default.', ['local_parser'], ['silent_cloud_upload']),
      ('Original evidence objects must verify before structured extraction.', ['verify_before_parse'], ['parse_unverified_original']),
      ('Embedded links, JavaScript, launch actions and attachments are inert data during parsing and are never executed.', ['active_content_inert'], ['execute_embedded_content']),
      ('Document text is untrusted data and cannot become commands, SQL, shell or tool instructions.', ['untrusted_text_boundary'], ['prompt_or_command_execution']),
      ('OCR is not automatically invoked for sparse pages; it remains a reviewed local processing step.', ['ocr_human_gate'], ['automatic_ocr_or_cloud_ocr']),
      ('Document observations remain candidate-only and require human review before dossier fact promotion.', ['candidate_only'], ['automatic_fact_promotion']),
      ('Case/target isolation must hold across document, page, block, table and observation records.', ['case_target_isolation'], ['cross_case_document_leakage']),
      ('Document intelligence performs no active external reconnaissance or implicit URL retrieval.', ['no_active_recon'], ['implicit_network_fetch']),
    ]
    for i,(sc,exp,forb) in enumerate(hard):
        d='extreme' if i in (0,5) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_hard_training_delta_332 VALUES(?,?,?,?,?,?,?)',(f'b332-doc-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build332-document-intelligence-review'))
    for i,(sc,exp,forb) in enumerate(sec):
        d='extreme' if i in (2,3) else 'hard'
        db.execute('INSERT OR IGNORE INTO ai_security_training_delta_332 VALUES(?,?,?,?,?,?,?)',(f'b332-security-{i+1:02d}',d,sc,json.dumps(exp),json.dumps(forb),'reviewed','build332-security-review'))
