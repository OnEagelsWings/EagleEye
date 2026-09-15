from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


SCHEMA_255 = r"""
CREATE TABLE IF NOT EXISTS document_pipeline_items_255 (
  document_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  media_type TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  page_count INTEGER NOT NULL,
  extraction_status TEXT NOT NULL,
  derived_vault_item_id TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  UNIQUE(case_id,vault_item_id)
);
CREATE INDEX IF NOT EXISTS idx_doc255_case ON document_pipeline_items_255(case_id,created_at,document_id);

CREATE TABLE IF NOT EXISTS document_opsec_assessments_255 (
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  encrypted INTEGER NOT NULL,
  javascript INTEGER NOT NULL,
  open_action INTEGER NOT NULL,
  additional_actions INTEGER NOT NULL,
  launch_action INTEGER NOT NULL,
  embedded_files INTEGER NOT NULL,
  external_uris INTEGER NOT NULL,
  interactive_forms INTEGER NOT NULL,
  xfa INTEGER NOT NULL,
  suspicious_token_count INTEGER NOT NULL,
  decision TEXT NOT NULL,
  active_content_execution_allowed INTEGER NOT NULL,
  external_resource_loading_allowed INTEGER NOT NULL,
  embedded_payload_execution_allowed INTEGER NOT NULL,
  network_fetch_allowed INTEGER NOT NULL,
  child_process_scope TEXT NOT NULL,
  controls_json TEXT NOT NULL,
  assessed_by TEXT NOT NULL,
  assessed_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES document_pipeline_items_255(document_id)
);
CREATE INDEX IF NOT EXISTS idx_docopsec255_case ON document_opsec_assessments_255(case_id,assessed_at,assessment_id);

CREATE TABLE IF NOT EXISTS extraction_spans_255 (
  span_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  vault_item_id TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  block_type TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  text_content TEXT NOT NULL,
  confidence REAL NOT NULL,
  bbox_json TEXT NOT NULL,
  table_id TEXT NOT NULL DEFAULT '',
  table_row INTEGER NOT NULL DEFAULT -1,
  table_col INTEGER NOT NULL DEFAULT -1,
  provenance_ref TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES document_pipeline_items_255(document_id)
);
CREATE INDEX IF NOT EXISTS idx_span255_doc ON extraction_spans_255(document_id,page_number,span_id);
CREATE INDEX IF NOT EXISTS idx_span255_case ON extraction_spans_255(case_id,page_number,span_id);

CREATE TABLE IF NOT EXISTS extracted_tables_255 (
  table_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  table_index INTEGER NOT NULL,
  row_count INTEGER NOT NULL,
  col_count INTEGER NOT NULL,
  extraction_method TEXT NOT NULL,
  provenance_ref TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES document_pipeline_items_255(document_id)
);
CREATE INDEX IF NOT EXISTS idx_table255_doc ON extracted_tables_255(document_id,page_number,table_index);

CREATE TABLE IF NOT EXISTS provenance_bindings_255 (
  binding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  span_id TEXT NOT NULL,
  source_vault_item_id TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  locator_json TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  derived_vault_item_id TEXT NOT NULL DEFAULT '',
  binding_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(span_id) REFERENCES extraction_spans_255(span_id)
);
CREATE INDEX IF NOT EXISTS idx_prov255_doc ON provenance_bindings_255(document_id,page_number,binding_id);

CREATE TABLE IF NOT EXISTS ai_document_benchmarks_255 (
  benchmark_id TEXT PRIMARY KEY,
  task_family TEXT NOT NULL,
  fixture_description TEXT NOT NULL,
  expected_page INTEGER NOT NULL,
  expected_block_type TEXT NOT NULL,
  expected_text TEXT NOT NULL,
  expected_table_row INTEGER NOT NULL,
  expected_table_col INTEGER NOT NULL,
  expected_provenance_class TEXT NOT NULL,
  minimum_text_similarity REAL NOT NULL,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_document_evaluations_255 (
  evaluation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  benchmark_id TEXT NOT NULL,
  predicted_page INTEGER NOT NULL,
  predicted_block_type TEXT NOT NULL,
  predicted_text TEXT NOT NULL,
  predicted_table_row INTEGER NOT NULL,
  predicted_table_col INTEGER NOT NULL,
  predicted_provenance_class TEXT NOT NULL,
  text_similarity REAL NOT NULL,
  page_match INTEGER NOT NULL,
  block_match INTEGER NOT NULL,
  table_locator_match INTEGER NOT NULL,
  provenance_match INTEGER NOT NULL,
  passed INTEGER NOT NULL,
  model_or_ruleset TEXT NOT NULL,
  evaluated_by TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(benchmark_id) REFERENCES ai_document_benchmarks_255(benchmark_id)
);
CREATE INDEX IF NOT EXISTS idx_aidoc255_case ON ai_document_evaluations_255(case_id,evaluated_at,evaluation_id);

CREATE TABLE IF NOT EXISTS document_opsec_controls_255 (
  control_id TEXT PRIMARY KEY,
  control_name TEXT NOT NULL,
  enforcement TEXT NOT NULL,
  required_value TEXT NOT NULL,
  review_status TEXT NOT NULL,
  verified_by TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build255_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt255_case ON build255_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_doc255_no_update BEFORE UPDATE ON document_pipeline_items_255 BEGIN SELECT RAISE(ABORT,'document_pipeline_items_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_doc255_no_delete BEFORE DELETE ON document_pipeline_items_255 BEGIN SELECT RAISE(ABORT,'document_pipeline_items_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docopsec255_no_update BEFORE UPDATE ON document_opsec_assessments_255 BEGIN SELECT RAISE(ABORT,'document_opsec_assessments_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docopsec255_no_delete BEFORE DELETE ON document_opsec_assessments_255 BEGIN SELECT RAISE(ABORT,'document_opsec_assessments_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_span255_no_update BEFORE UPDATE ON extraction_spans_255 BEGIN SELECT RAISE(ABORT,'extraction_spans_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_span255_no_delete BEFORE DELETE ON extraction_spans_255 BEGIN SELECT RAISE(ABORT,'extraction_spans_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_table255_no_update BEFORE UPDATE ON extracted_tables_255 BEGIN SELECT RAISE(ABORT,'extracted_tables_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_table255_no_delete BEFORE DELETE ON extracted_tables_255 BEGIN SELECT RAISE(ABORT,'extracted_tables_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_prov255_no_update BEFORE UPDATE ON provenance_bindings_255 BEGIN SELECT RAISE(ABORT,'provenance_bindings_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_prov255_no_delete BEFORE DELETE ON provenance_bindings_255 BEGIN SELECT RAISE(ABORT,'provenance_bindings_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aidocbench255_no_update BEFORE UPDATE ON ai_document_benchmarks_255 BEGIN SELECT RAISE(ABORT,'ai_document_benchmarks_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aidocbench255_no_delete BEFORE DELETE ON ai_document_benchmarks_255 BEGIN SELECT RAISE(ABORT,'ai_document_benchmarks_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aidoceval255_no_update BEFORE UPDATE ON ai_document_evaluations_255 BEGIN SELECT RAISE(ABORT,'ai_document_evaluations_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aidoceval255_no_delete BEFORE DELETE ON ai_document_evaluations_255 BEGIN SELECT RAISE(ABORT,'ai_document_evaluations_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docctrl255_no_update BEFORE UPDATE ON document_opsec_controls_255 BEGIN SELECT RAISE(ABORT,'document_opsec_controls_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docctrl255_no_delete BEFORE DELETE ON document_opsec_controls_255 BEGIN SELECT RAISE(ABORT,'document_opsec_controls_255 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt255_no_update BEFORE UPDATE ON build255_events BEGIN SELECT RAISE(ABORT,'build255_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt255_no_delete BEFORE DELETE ON build255_events BEGIN SELECT RAISE(ABORT,'build255_events is immutable'); END;
"""


BENCHMARKS = [
    ("bench255_native_1","native_text","Native PDF paragraph with an amount and grant identifier.",1,"text","Grant agreement GA-2026-104 awarded EUR 250000.",-1,-1,"page_bbox_sha256",0.92),
    ("bench255_native_2","native_text","Native PDF paragraph preserving a named organization.",2,"text","The beneficiary is Example Research Foundation.",-1,-1,"page_bbox_sha256",0.92),
    ("bench255_native_3","native_text","Native PDF paragraph where page provenance matters.",4,"text","Reporting period: 1 January 2026 to 31 December 2026.",-1,-1,"page_bbox_sha256",0.92),
    ("bench255_ocr_1","ocr_text","Scanned page OCR with a contract identifier.",1,"ocr_text","Contract reference CN-4471-26",-1,-1,"page_bbox_sha256",0.88),
    ("bench255_ocr_2","ocr_text","Scanned page OCR with a monetary amount.",3,"ocr_text","Total approved amount 98000 EUR",-1,-1,"page_bbox_sha256",0.88),
    ("bench255_ocr_3","ocr_text","OCR must preserve a short institutional phrase.",5,"ocr_text","Federal programme office",-1,-1,"page_bbox_sha256",0.88),
    ("bench255_table_1","table_cell","Table header extraction with cell coordinates.",1,"table_cell","Recipient",0,0,"page_table_cell_sha256",0.95),
    ("bench255_table_2","table_cell","Table amount extraction with cell coordinates.",1,"table_cell","250000",1,2,"page_table_cell_sha256",0.95),
    ("bench255_table_3","table_cell","Table programme extraction with cell coordinates.",2,"table_cell","Democracy Support",2,1,"page_table_cell_sha256",0.95),
    ("bench255_prov_1","provenance","Text span must preserve page and bbox provenance.",7,"text","Official notice published on 14 May 2026.",-1,-1,"page_bbox_sha256",0.93),
    ("bench255_prov_2","provenance","OCR span must preserve extraction method.",8,"ocr_text","Archive copy reference A-881",-1,-1,"page_bbox_sha256",0.90),
    ("bench255_prov_3","provenance","Table cell provenance must remain cell-specific.",9,"table_cell","Awarded",3,4,"page_table_cell_sha256",0.95),
]

CONTROLS = [
    ("ctrl255_original_immutable","Original evidence immutability","Build 255 reads only the Build-239 content-addressed vault copy and writes derivatives separately.","true"),
    ("ctrl255_hash_verify","Pre-extraction integrity verification","SHA-256 integrity must pass before parsing.","required"),
    ("ctrl255_no_active_exec","Active PDF content execution","JavaScript, Launch, OpenAction and additional actions are never executed.","false"),
    ("ctrl255_no_external_fetch","External resource loading","URI targets and remote resources are never fetched during extraction.","false"),
    ("ctrl255_no_embedded_exec","Embedded payload execution","Embedded files are never opened or executed by the pipeline.","false"),
    ("ctrl255_quarantine","High-risk document quarantine","Encrypted or active-payload PDFs require manual review and are not extracted automatically.","required"),
    ("ctrl255_size_cap","Document size cap","Single-document processing is capped at 100 MiB inherited from Build 239.","104857600"),
    ("ctrl255_page_cap","Page processing cap","Automatic extraction is capped at 750 pages per document.","750"),
    ("ctrl255_ocr_local","OCR execution boundary","OCR is local-only, optional, and may invoke only the local tesseract executable; no network access.","local_only"),
    ("ctrl255_temp_isolation","Temporary workspace isolation","Rendering/extraction uses per-operation temporary directories and removes them after use.","required"),
]


def ensure_build255_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_255)
    for bid, family, desc, page, block, text, row, col, prov, threshold in BENCHMARKS:
        payload = {
            "benchmark_id": bid, "task_family": family, "fixture_description": desc, "expected_page": page,
            "expected_block_type": block, "expected_text": text, "expected_table_row": row, "expected_table_col": col,
            "expected_provenance_class": prov, "minimum_text_similarity": threshold,
            "review_status": "curated_reviewed", "reviewed_by": "build255-curation",
        }
        db.conn.execute(
            "INSERT OR IGNORE INTO ai_document_benchmarks_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,family,desc,page,block,text,row,col,prov,threshold,"curated_reviewed","build255-curation",_hash(payload)),
        )
    for cid, name, enforcement, required in CONTROLS:
        payload = {"control_id":cid,"control_name":name,"enforcement":enforcement,"required_value":required,"review_status":"verified","verified_by":"build255-opsec-review"}
        db.conn.execute(
            "INSERT OR IGNORE INTO document_opsec_controls_255 VALUES(?,?,?,?,?,?,?)",
            (cid,name,enforcement,required,"verified","build255-opsec-review",_hash(payload)),
        )
    for key, value in (
        ("schema_version","255.0"),("application_build","255.0"),
        ("phase10_pack","influence_funding_investigation"),("phase10_module","pdf_ocr_table_provenance_pipeline"),
        ("ai_crosscut_gate","required_every_build"),("opsec_crosscut_gate","required_every_build"),
        ("build255_ai_delta","reviewed_pdf_ocr_table_provenance_goldset_span_accuracy"),
        ("build255_opsec_delta","active_content_link_embedded_payload_quarantine_and_local_extraction_boundary"),
    ):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(key,value))
    db.conn.commit()
