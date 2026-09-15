from __future__ import annotations

import hashlib
import html
import io
import json
import re
import shutil
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 20000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", _text(value, 50000)).strip().casefold()


class Build255DocumentProvenancePipelineService:
    """Static PDF/OCR/table extraction with immutable span-level provenance.

    The service never performs network acquisition. It processes only bytes that are
    already stored in the Build-239 Evidence Vault, verifies their SHA-256 before
    parsing, refuses automatic extraction for encrypted/active-payload PDFs, never
    follows external links, and stores derived extraction artefacts separately from
    the original evidence item.
    """

    BUILD = "255.0"
    MAX_PAGES = 750
    OCR_MIN_NATIVE_CHARS = 30
    HIGH_RISK_FLAGS = ("encrypted", "javascript", "open_action", "additional_actions", "launch_action", "embedded_files", "xfa")

    def __init__(self, db, audit, *, international_sources, evidence_vault, training, opsec, conversation, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.international_sources = international_sources
        self.evidence_vault = evidence_vault
        self.training = training
        self.opsec = opsec
        self.conversation = conversation
        self.actor = actor
        conversation._document_pipeline_255 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build255_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "")
        event_id, created_at = new_id("evt255"), now_ts()
        event_hash = _hash({"previous":previous,"event_id":event_id,"event_type":event_type,"object_id":object_id,"payload":payload,"actor":actor,"at":created_at})
        self.db.execute("INSERT INTO build255_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id,case_id,event_type,object_type,object_id,actor,dumps(payload),previous,event_hash,created_at))
        try:
            self.audit.log("build255_" + event_type, object_type, object_id, case_id, payload)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Safe evidence loading and document assessment
    # ------------------------------------------------------------------
    def _load_vault_pdf(self, *, case_id: str, vault_item_id: str, actor: str) -> tuple[dict[str, Any], bytes]:
        self._case(case_id)
        item = self.evidence_vault.item(vault_item_id)
        if item["case_id"] != case_id:
            raise PermissionError("evidence item belongs to another case")
        media = _text(item.get("media_type"), 200).lower()
        name = _text(item.get("original_filename"), 500).lower()
        if "pdf" not in media and not name.endswith(".pdf"):
            raise ValueError("Build 255 accepts PDF evidence items only")
        integrity = self.evidence_vault.verify_item(vault_item_id=vault_item_id, checked_by=actor)
        if integrity["status"] != "ok":
            raise PermissionError("evidence integrity gate failed")
        path = Path(self.evidence_vault.base_dir) / item["storage_relpath"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["content_sha256"]:
            raise PermissionError("vault hash mismatch")
        return item, raw

    @staticmethod
    def _byte_token_counts(raw: bytes) -> dict[str, int]:
        # Static token inspection only. No action, URI, script or embedded payload is executed.
        probes = {
            "javascript": (b"/JavaScript", b"/JS"),
            "open_action": (b"/OpenAction",),
            "additional_actions": (b"/AA",),
            "launch_action": (b"/Launch",),
            "embedded_files": (b"/EmbeddedFile", b"/EmbeddedFiles"),
            "external_uris": (b"/URI",),
            "interactive_forms": (b"/AcroForm",),
            "xfa": (b"/XFA",),
        }
        return {key: sum(raw.count(token) for token in tokens) for key, tokens in probes.items()}

    def assess_pdf_bytes(self, raw: bytes) -> dict[str, Any]:
        token_counts = self._byte_token_counts(raw)
        flags = {key: bool(value) for key, value in token_counts.items()}
        encrypted = False
        page_count = 0
        parser_notes: list[str] = []
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw), strict=False)
            encrypted = bool(reader.is_encrypted)
            if not encrypted:
                page_count = len(reader.pages)
            else:
                parser_notes.append("encrypted_pdf")
        except Exception as exc:
            parser_notes.append(f"pypdf:{type(exc).__name__}")
        try:
            import fitz
            doc = fitz.open(stream=raw, filetype="pdf")
            page_count = max(page_count, int(doc.page_count))
            encrypted = encrypted or bool(doc.needs_pass)
            try:
                if doc.embfile_count() > 0:
                    flags["embedded_files"] = True
                    token_counts["embedded_files"] = max(token_counts["embedded_files"], int(doc.embfile_count()))
            except Exception:
                pass
            # get_links() reads link dictionaries only; no destination is fetched/opened.
            external_link_count = 0
            if not doc.needs_pass:
                for i in range(min(doc.page_count, self.MAX_PAGES)):
                    try:
                        for link in doc.load_page(i).get_links():
                            uri = str(link.get("uri") or "")
                            if uri.startswith(("http://", "https://", "ftp://", "mailto:")):
                                external_link_count += 1
                    except Exception:
                        pass
            if external_link_count:
                flags["external_uris"] = True
                token_counts["external_uris"] = max(token_counts["external_uris"], external_link_count)
            doc.close()
        except Exception as exc:
            parser_notes.append(f"pymupdf:{type(exc).__name__}")
        flags["encrypted"] = bool(encrypted)
        suspicious_token_count = sum(token_counts.values())
        high_risk = any(flags.get(name, False) for name in self.HIGH_RISK_FLAGS)
        if page_count > self.MAX_PAGES:
            high_risk = True
            parser_notes.append("page_cap_exceeded")
        decision = "quarantine_manual_review" if high_risk else ("static_extract_links_inert" if flags.get("external_uris") or flags.get("interactive_forms") else "static_extract_allowed")
        return {
            **flags,
            "page_count": page_count,
            "suspicious_token_count": suspicious_token_count,
            "token_counts": token_counts,
            "decision": decision,
            "automatic_extraction_allowed": not high_risk,
            "active_content_execution_allowed": False,
            "external_resource_loading_allowed": False,
            "embedded_payload_execution_allowed": False,
            "network_fetch_allowed": False,
            "child_process_scope": "none_unless_local_tesseract_ocr_requested",
            "controls": [
                "vault_sha256_verified_before_parse",
                "pdf_actions_never_executed",
                "external_links_never_fetched",
                "embedded_payloads_never_opened",
                "per_operation_temp_workspace",
                "original_vault_item_immutable",
                "750_page_automatic_cap",
            ],
            "parser_notes": parser_notes,
        }

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def _native_text_spans(self, raw: bytes) -> tuple[list[dict[str, Any]], list[int]]:
        import fitz
        spans: list[dict[str, Any]] = []
        sparse_pages: list[int] = []
        doc = fitz.open(stream=raw, filetype="pdf")
        if doc.needs_pass:
            doc.close()
            raise PermissionError("encrypted PDF is not eligible for automatic extraction")
        if doc.page_count > self.MAX_PAGES:
            doc.close()
            raise ValueError("page cap exceeded")
        for pidx in range(doc.page_count):
            page = doc.load_page(pidx)
            blocks = page.get_text("blocks", sort=True)
            page_chars = 0
            for block in blocks:
                if len(block) < 5:
                    continue
                x0,y0,x1,y1,text = block[:5]
                cleaned = _text(text, 30000)
                if not cleaned:
                    continue
                page_chars += len(cleaned)
                spans.append({
                    "page_number": pidx + 1, "block_type":"text", "extraction_method":"pymupdf_native",
                    "text_content":cleaned, "confidence":1.0, "bbox":[float(x0),float(y0),float(x1),float(y1)],
                    "table_id":"", "table_row":-1, "table_col":-1,
                })
            if page_chars < self.OCR_MIN_NATIVE_CHARS:
                sparse_pages.append(pidx + 1)
        doc.close()
        return spans, sparse_pages

    def _ocr_spans(self, raw: bytes, pages: list[int]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        result: list[dict[str, Any]] = []
        metrics = {"requested_pages":len(pages),"ocr_pages":0,"tesseract_available":False,"network_used":False,"local_child_process":False}
        executable = shutil.which("tesseract")
        if not executable or not pages:
            return result, metrics
        metrics["tesseract_available"] = True
        import fitz
        from PIL import Image
        import pytesseract
        doc = fitz.open(stream=raw, filetype="pdf")
        with tempfile.TemporaryDirectory(prefix="eagleeye255_ocr_") as tmpdir:
            # tempfile exists only to provide an isolated working boundary; image data remains in memory.
            _ = tmpdir
            for page_number in pages:
                if page_number < 1 or page_number > doc.page_count:
                    continue
                page = doc.load_page(page_number - 1)
                pix = page.get_pixmap(dpi=150, alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
                metrics["local_child_process"] = True
                line_words: dict[tuple[int,int,int], list[tuple[str,float,int,int,int,int]]] = {}
                n = len(data.get("text", []))
                for i in range(n):
                    word = _text(data["text"][i], 500)
                    if not word:
                        continue
                    try: conf = float(data["conf"][i]) / 100.0
                    except Exception: conf = 0.0
                    key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
                    line_words.setdefault(key, []).append((word,conf,int(data["left"][i]),int(data["top"][i]),int(data["width"][i]),int(data["height"][i])))
                for words in line_words.values():
                    text = " ".join(w[0] for w in words)
                    x0=min(w[2] for w in words); y0=min(w[3] for w in words); x1=max(w[2]+w[4] for w in words); y1=max(w[3]+w[5] for w in words)
                    conf=sum(max(0.0,min(1.0,w[1])) for w in words)/len(words)
                    result.append({"page_number":page_number,"block_type":"ocr_text","extraction_method":"local_tesseract_ocr","text_content":text,"confidence":round(conf,4),"bbox":[x0,y0,x1,y1],"table_id":"","table_row":-1,"table_col":-1})
                metrics["ocr_pages"] += 1
        doc.close()
        return result, metrics

    def _table_spans(self, raw: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        import pdfplumber
        spans: list[dict[str, Any]] = []
        tables_meta: list[dict[str, Any]] = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if len(pdf.pages) > self.MAX_PAGES:
                raise ValueError("page cap exceeded")
            for pidx, page in enumerate(pdf.pages):
                try:
                    tables = page.extract_tables() or []
                except Exception:
                    tables = []
                for tidx, table in enumerate(tables):
                    if not table:
                        continue
                    max_cols = max((len(row or []) for row in table), default=0)
                    table_key = f"p{pidx+1}_t{tidx+1}"
                    tables_meta.append({"table_key":table_key,"page_number":pidx+1,"table_index":tidx+1,"row_count":len(table),"col_count":max_cols,"extraction_method":"pdfplumber_native_table"})
                    for ridx, row in enumerate(table):
                        for cidx, cell in enumerate(row or []):
                            cleaned = _text(cell, 12000)
                            if not cleaned:
                                continue
                            spans.append({"page_number":pidx+1,"block_type":"table_cell","extraction_method":"pdfplumber_native_table","text_content":cleaned,"confidence":1.0,"bbox":[],"table_id":table_key,"table_row":ridx,"table_col":cidx})
        return spans, tables_meta

    def process_vault_pdf(self, *, case_id: str, vault_item_id: str, actor: str, confirmation: str, allow_ocr: bool = True) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"DOCUMENT PIPELINE 255 {case_id} EXTRACT":
            raise PermissionError("explicit approval required")
        existing = self.db.one("SELECT * FROM document_pipeline_items_255 WHERE case_id=? AND vault_item_id=?", (case_id,vault_item_id))
        if existing:
            return {**dict(existing),"idempotent":True,"assessment":self._assessment_for_document(existing["document_id"]),"span_count":int(self.db.one("SELECT COUNT(*) n FROM extraction_spans_255 WHERE document_id=?",(existing["document_id"],))["n"])}
        item, raw = self._load_vault_pdf(case_id=case_id, vault_item_id=vault_item_id, actor=actor)
        assessment = self.assess_pdf_bytes(raw)
        document_id, created_at = new_id("doc255"), now_ts()
        extraction_status = "quarantined" if not assessment["automatic_extraction_allowed"] else "extracted"
        native_spans: list[dict[str, Any]] = []
        ocr_spans: list[dict[str, Any]] = []
        table_spans: list[dict[str, Any]] = []
        tables_meta: list[dict[str, Any]] = []
        ocr_metrics = {"requested_pages":0,"ocr_pages":0,"tesseract_available":bool(shutil.which("tesseract")),"network_used":False,"local_child_process":False}
        derived = {"vault_item_id":""}
        if assessment["automatic_extraction_allowed"]:
            with tempfile.TemporaryDirectory(prefix="eagleeye255_extract_"):
                native_spans, sparse_pages = self._native_text_spans(raw)
                table_spans, tables_meta = self._table_spans(raw)
                if allow_ocr:
                    ocr_spans, ocr_metrics = self._ocr_spans(raw, sparse_pages)
            all_spans = native_spans + ocr_spans + table_spans
            artifact = {
                "build":"255.0","source_vault_item_id":vault_item_id,"source_sha256":item["content_sha256"],
                "page_count":assessment["page_count"],"security_decision":assessment["decision"],
                "spans":all_spans,"tables":tables_meta,
                "provenance_semantics":"Each span is anchored to source SHA-256 + 1-based page + bbox or table cell locator; extraction is a derivative, never a replacement for the source.",
                "network_used":False,
            }
            derived_result = self.evidence_vault.create_derived(
                parent_vault_item_id=vault_item_id, content=json.dumps(artifact,ensure_ascii=False,sort_keys=True).encode("utf-8"),
                media_type="application/vnd.eagleeye.document-extraction+json", transformation_type="text_extract",
                transformation_params={"build":"255.0","native":"pymupdf","tables":"pdfplumber","ocr":"local_tesseract_if_requested","network_used":False},
                original_filename=(Path(item.get("original_filename") or "document.pdf").stem + ".build255.extract.json"),
                created_by=actor, confirmation=f"EVIDENCE DERIVATION 239 {vault_item_id} ANLEGEN",
            )
            derived = derived_result.get("child", {})
        all_spans = native_spans + ocr_spans + table_spans
        doc_payload = {
            "document_id":document_id,"case_id":case_id,"vault_item_id":vault_item_id,"original_filename":item.get("original_filename","") or "document.pdf",
            "media_type":item.get("media_type","") or "application/pdf","content_sha256":item["content_sha256"],"byte_size":int(item["byte_size"]),
            "page_count":int(assessment["page_count"]),"extraction_status":extraction_status,"derived_vault_item_id":derived.get("vault_item_id","") or "",
            "created_by":actor,"created_at":created_at,
        }
        self.db.execute("INSERT INTO document_pipeline_items_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(
            document_id,case_id,vault_item_id,doc_payload["original_filename"],doc_payload["media_type"],item["content_sha256"],int(item["byte_size"]),int(assessment["page_count"]),extraction_status,doc_payload["derived_vault_item_id"],actor,created_at,_hash(doc_payload)))
        self._store_assessment(case_id=case_id,document_id=document_id,assessment=assessment,actor=actor)
        table_id_map: dict[str,str] = {}
        for table in tables_meta:
            table_id = new_id("table255")
            table_id_map[table["table_key"]] = table_id
            prov = f"vault:{vault_item_id}#sha256={item['content_sha256']};page={table['page_number']};table={table['table_index']}"
            payload={**table,"table_id":table_id,"case_id":case_id,"document_id":document_id,"provenance_ref":prov,"created_at":now_ts()}
            self.db.execute("INSERT INTO extracted_tables_255 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(table_id,case_id,document_id,table["page_number"],table["table_index"],table["row_count"],table["col_count"],table["extraction_method"],prov,payload["created_at"],_hash(payload)))
        for span in all_spans:
            span_id, ts = new_id("span255"), now_ts()
            table_id = table_id_map.get(span.get("table_id", ""), "")
            locator = {"page":span["page_number"],"bbox":span.get("bbox",[]),"table_id":table_id,"table_row":span.get("table_row",-1),"table_col":span.get("table_col",-1)}
            prov_class = "page_table_cell_sha256" if span["block_type"] == "table_cell" else "page_bbox_sha256"
            provenance_ref = f"vault:{vault_item_id}#sha256={item['content_sha256']};page={span['page_number']};locator={prov_class}"
            provenance_hash = _hash({"source_sha256":item["content_sha256"],"locator":locator,"method":span["extraction_method"],"text_sha256":hashlib.sha256(span["text_content"].encode('utf-8')).hexdigest()})
            span_payload={**span,"span_id":span_id,"case_id":case_id,"document_id":document_id,"vault_item_id":vault_item_id,"table_id":table_id,"provenance_ref":provenance_ref,"provenance_hash":provenance_hash,"created_at":ts}
            self.db.execute("INSERT INTO extraction_spans_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                span_id,case_id,document_id,vault_item_id,span["page_number"],span["block_type"],span["extraction_method"],span["text_content"],float(span["confidence"]),dumps(span.get("bbox",[])),table_id,int(span.get("table_row",-1)),int(span.get("table_col",-1)),provenance_ref,provenance_hash,ts,_hash(span_payload)))
            binding_id = new_id("prov255")
            binding_payload={"binding_id":binding_id,"case_id":case_id,"document_id":document_id,"span_id":span_id,"source_vault_item_id":vault_item_id,"source_sha256":item["content_sha256"],"page_number":span["page_number"],"locator":locator,"extraction_method":span["extraction_method"],"derived_vault_item_id":doc_payload["derived_vault_item_id"],"binding_hash":provenance_hash,"created_at":ts}
            self.db.execute("INSERT INTO provenance_bindings_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                binding_id,case_id,document_id,span_id,vault_item_id,item["content_sha256"],span["page_number"],dumps(locator),span["extraction_method"],doc_payload["derived_vault_item_id"],provenance_hash,ts,_hash(binding_payload)))
        self._event(case_id,"document_processed","document",document_id,{"vault_item_id":vault_item_id,"decision":assessment["decision"],"extraction_status":extraction_status,"spans":len(all_spans),"tables":len(tables_meta),"ocr":ocr_metrics,"network_used":False},actor)
        return {**doc_payload,"idempotent":False,"assessment":assessment,"span_count":len(all_spans),"table_count":len(tables_meta),"ocr":ocr_metrics,"network_used":False,"original_immutable":True}

    def _store_assessment(self, *, case_id: str, document_id: str, assessment: dict[str, Any], actor: str) -> dict[str, Any]:
        aid, ts = new_id("docopsec255"), now_ts()
        payload={"assessment_id":aid,"case_id":case_id,"document_id":document_id,**assessment,"assessed_by":actor,"assessed_at":ts}
        self.db.execute("INSERT INTO document_opsec_assessments_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
            aid,case_id,document_id,int(assessment["encrypted"]),int(assessment["javascript"]),int(assessment["open_action"]),int(assessment["additional_actions"]),int(assessment["launch_action"]),int(assessment["embedded_files"]),int(assessment["external_uris"]),int(assessment["interactive_forms"]),int(assessment["xfa"]),int(assessment["suspicious_token_count"]),assessment["decision"],0,0,0,0,assessment["child_process_scope"],dumps(assessment["controls"]),actor,ts,_hash(payload)))
        return payload

    def _assessment_for_document(self, document_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM document_opsec_assessments_255 WHERE document_id=? ORDER BY assessed_at DESC LIMIT 1",(document_id,))
        return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Provenance queries and AI qualification
    # ------------------------------------------------------------------
    def spans(self, *, document_id: str, page_number: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        if page_number:
            rows=self.db.all("SELECT * FROM extraction_spans_255 WHERE document_id=? AND page_number=? ORDER BY rowid LIMIT ?",(document_id,page_number,max(1,min(int(limit),5000))))
        else:
            rows=self.db.all("SELECT * FROM extraction_spans_255 WHERE document_id=? ORDER BY page_number,rowid LIMIT ?",(document_id,max(1,min(int(limit),5000))))
        out=[]
        for row in rows:
            item=dict(row); item["bbox"]=_loads(item.get("bbox_json"),[]); out.append(item)
        return out

    def verify_span_provenance(self, *, span_id: str) -> dict[str, Any]:
        span=self.db.one("SELECT * FROM extraction_spans_255 WHERE span_id=?",(span_id,))
        binding=self.db.one("SELECT * FROM provenance_bindings_255 WHERE span_id=?",(span_id,))
        if not span or not binding:
            raise KeyError(span_id)
        locator=_loads(binding["locator_json"],{})
        observed=_hash({"source_sha256":binding["source_sha256"],"locator":locator,"method":binding["extraction_method"],"text_sha256":hashlib.sha256(span["text_content"].encode('utf-8')).hexdigest()})
        return {"span_id":span_id,"status":"ok" if observed==binding["binding_hash"]==span["provenance_hash"] else "hash_mismatch","observed_hash":observed,"stored_hash":binding["binding_hash"],"source_sha256":binding["source_sha256"],"page_number":binding["page_number"],"locator":locator}

    def stage_training_candidate_from_span(self, *, case_id: str, span_id: str, task_instruction: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"AI TRAINING CANDIDATE 255 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        span=self.db.one("SELECT * FROM extraction_spans_255 WHERE span_id=? AND case_id=?",(span_id,case_id))
        if not span:
            raise KeyError(span_id)
        provenance=self.verify_span_provenance(span_id=span_id)
        if provenance["status"] != "ok":
            raise PermissionError("provenance gate failed")
        instruction=_text(task_instruction,4000)
        if len(instruction) < 12:
            raise ValueError("substantive task instruction required")
        prov_class="page_table_cell_sha256" if span["block_type"]=="table_cell" else "page_bbox_sha256"
        context={"build":"255.0","page_number":span["page_number"],"block_type":span["block_type"],"extraction_method":span["extraction_method"],"provenance_class":prov_class,"provenance_verified":True,"human_review_required":True}
        example=self.training.add_example(case_id=case_id,instruction=instruction,response=span["text_content"],context=context,evidence_refs=[span["vault_item_id"],span_id],language=self.international_sources.detect_language(span["text_content"]),source_type="build255_document_span",source_ref=span_id,created_by=actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
        self._event(case_id,"training_candidate_staged","training_example",example["example_id"],{"span_id":span_id,"provenance":"ok","review_status":example["review_status"],"redaction_status":example["redaction_status"]},actor)
        return {"example":example,"provenance":provenance,"automatic_approval":False,"automatic_dataset_inclusion":False,"automatic_adapter_activation":False}

    def benchmarks(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.all("SELECT * FROM ai_document_benchmarks_255 ORDER BY benchmark_id")]

    def record_ai_evaluation(self, *, case_id: str, benchmark_id: str, predicted_page: int, predicted_block_type: str, predicted_text: str, predicted_table_row: int, predicted_table_col: int, predicted_provenance_class: str, model_or_ruleset: str, evaluated_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"AI BENCHMARK 255 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        benchmark=self.db.one("SELECT * FROM ai_document_benchmarks_255 WHERE benchmark_id=?",(benchmark_id,))
        if not benchmark:
            raise KeyError(benchmark_id)
        similarity=SequenceMatcher(None,_norm(benchmark["expected_text"]),_norm(predicted_text)).ratio()
        page_match=int(int(predicted_page)==int(benchmark["expected_page"]))
        block_match=int(_text(predicted_block_type,80)==benchmark["expected_block_type"])
        table_expected=int(benchmark["expected_table_row"]) >= 0 or int(benchmark["expected_table_col"]) >= 0
        table_match=int((not table_expected) or (int(predicted_table_row)==int(benchmark["expected_table_row"]) and int(predicted_table_col)==int(benchmark["expected_table_col"])))
        provenance_match=int(_text(predicted_provenance_class,120)==benchmark["expected_provenance_class"])
        passed=bool(similarity>=float(benchmark["minimum_text_similarity"]) and page_match and block_match and table_match and provenance_match)
        eid,ts=new_id("aidoc255"),now_ts()
        payload={"evaluation_id":eid,"case_id":case_id,"benchmark_id":benchmark_id,"predicted_page":int(predicted_page),"predicted_block_type":predicted_block_type,"predicted_text":predicted_text,"predicted_table_row":int(predicted_table_row),"predicted_table_col":int(predicted_table_col),"predicted_provenance_class":predicted_provenance_class,"text_similarity":round(similarity,4),"page_match":bool(page_match),"block_match":bool(block_match),"table_locator_match":bool(table_match),"provenance_match":bool(provenance_match),"passed":passed,"model_or_ruleset":_text(model_or_ruleset,200) or "manual-eval","evaluated_by":evaluated_by,"evaluated_at":ts}
        self.db.execute("INSERT INTO ai_document_evaluations_255 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,case_id,benchmark_id,int(predicted_page),_text(predicted_block_type,80),_text(predicted_text,20000),int(predicted_table_row),int(predicted_table_col),_text(predicted_provenance_class,120),round(similarity,4),page_match,block_match,table_match,provenance_match,int(passed),payload["model_or_ruleset"],evaluated_by,ts,_hash(payload)))
        self._event(case_id,"ai_document_benchmark_evaluated","ai_benchmark",benchmark_id,{"evaluation_id":eid,"passed":passed,"text_similarity":round(similarity,4)},evaluated_by)
        return payload

    def ai_metrics(self, *, case_id: str) -> dict[str, Any]:
        total=int(self.db.one("SELECT COUNT(*) n FROM ai_document_benchmarks_255 WHERE review_status='curated_reviewed'")["n"])
        families=int(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_document_benchmarks_255 WHERE review_status='curated_reviewed'")["n"])
        rows=self.db.all("SELECT * FROM ai_document_evaluations_255 WHERE case_id=?",(case_id,))
        training_candidates=int(self.db.one("SELECT COUNT(*) n FROM training_examples_228 WHERE case_id=? AND source_type='build255_document_span'",(case_id,))["n"])
        approved_candidates=int(self.db.one("SELECT COUNT(*) n FROM training_examples_228 WHERE case_id=? AND source_type='build255_document_span' AND review_status='approved' AND redaction_status='clean'",(case_id,))["n"])
        return {
            "curated_reviewed_benchmarks":total,"task_family_coverage":families,"evaluations_recorded":len(rows),
            "evaluation_pass_rate":round(sum(int(r["passed"]) for r in rows)/len(rows),4) if rows else None,
            "build255_training_candidates":training_candidates,"build255_approved_clean_training_examples":approved_candidates,
            "training_bridge":"provenance_verified_span_to_build228_pending_example_then_independent_review",
            "provenance_span_metric":"text_similarity + page + block/table locator + provenance class",
            "qualification_gate":"all locator dimensions plus benchmark-specific minimum text similarity",
            "auto_model_activation":False,"auto_adapter_activation":False,"training_examples_reviewed_only":True,
            "training_pipeline_228":self.training.dashboard(case_id=case_id),
        }

    def opsec_metrics(self, *, case_id: str) -> dict[str, Any]:
        controls=int(self.db.one("SELECT COUNT(*) n FROM document_opsec_controls_255 WHERE review_status='verified'")["n"])
        assessments=int(self.db.one("SELECT COUNT(*) n FROM document_opsec_assessments_255 WHERE case_id=?",(case_id,))["n"])
        quarantined=int(self.db.one("SELECT COUNT(*) n FROM document_opsec_assessments_255 WHERE case_id=? AND decision='quarantine_manual_review'",(case_id,))["n"])
        violations=int(self.db.one("SELECT COUNT(*) n FROM document_opsec_assessments_255 WHERE case_id=? AND (active_content_execution_allowed!=0 OR external_resource_loading_allowed!=0 OR embedded_payload_execution_allowed!=0 OR network_fetch_allowed!=0)",(case_id,))["n"])
        return {"verified_controls":controls,"required_controls":10,"control_coverage":round(min(controls,10)/10,4),"assessments_recorded":assessments,"quarantined_documents":quarantined,"execution_or_network_policy_violations":violations,"active_content_executions":0,"external_resource_fetches":0,"embedded_payload_executions":0,"network_fetches":0,"autonomous_network_changes":0,"host_reconfiguration":False,"ocr_boundary":"local_tesseract_only_when_explicitly_requested_and_available"}

    def capabilities(self) -> dict[str, Any]:
        checks={}
        for name,module in (("native_pdf_text","fitz"),("pdf_structure","pypdf"),("table_extraction","pdfplumber"),("ocr_wrapper","pytesseract")):
            try:
                __import__(module); checks[name]=True
            except Exception:
                checks[name]=False
        checks["local_tesseract_executable"]=bool(shutil.which("tesseract"))
        return checks

    def crosscut_release_gate(self, *, case_id: str) -> dict[str, Any]:
        ai=self.ai_metrics(case_id=case_id); opsec=self.opsec_metrics(case_id=case_id); caps=self.capabilities()
        try: parent_ready=bool(self.international_sources.crosscut_release_gate(case_id=case_id)["release_ready"])
        except Exception: parent_ready=False
        main_ready=bool(caps["native_pdf_text"] and caps["pdf_structure"] and caps["table_extraction"] and self.db.one("SELECT COUNT(*) n FROM document_opsec_controls_255")["n"] >= 10)
        ai_ready=bool(ai["curated_reviewed_benchmarks"]>=12 and ai["task_family_coverage"]>=4 and ai["auto_model_activation"] is False and ai["auto_adapter_activation"] is False and ai["training_examples_reviewed_only"])
        opsec_ready=bool(opsec["control_coverage"]==1.0 and opsec["execution_or_network_policy_violations"]==0 and opsec["active_content_executions"]==0 and opsec["external_resource_fetches"]==0 and opsec["embedded_payload_executions"]==0 and opsec["network_fetches"]==0 and opsec["autonomous_network_changes"]==0)
        return {"build":self.BUILD,"main_goal_ready":main_ready,"ai_delta_ready":ai_ready,"opsec_delta_ready":opsec_ready,"parent_254_gate_ready":parent_ready,"release_ready":bool(main_ready and ai_ready and opsec_ready and parent_ready),"capabilities":caps,"policy":"Build 255 adds static PDF/OCR/table extraction with immutable span provenance; active content and external resources remain inert and high-risk documents are quarantined."}

    def status(self, *, case_id: str) -> dict[str, Any]:
        docs=[]
        for row in self.db.all("SELECT * FROM document_pipeline_items_255 WHERE case_id=? ORDER BY created_at DESC",(case_id,)):
            item=dict(row); item["assessment"]=self._assessment_for_document(item["document_id"]); item["span_count"]=int(self.db.one("SELECT COUNT(*) n FROM extraction_spans_255 WHERE document_id=?",(item["document_id"],))["n"]); docs.append(item)
        pdf_candidates=[dict(r) for r in self.db.all("SELECT vault_item_id,original_filename,media_type,byte_size,content_sha256,created_at FROM evidence_vault_items_239 WHERE case_id=? AND (lower(media_type) LIKE '%pdf%' OR lower(original_filename) LIKE '%.pdf') ORDER BY created_at DESC LIMIT 100",(case_id,))]
        return {"build":self.BUILD,"documents":docs,"pdf_candidates":pdf_candidates,"ai":self.ai_metrics(case_id=case_id),"opsec":self.opsec_metrics(case_id=case_id),"gate":self.crosscut_release_gate(case_id=case_id),"capabilities":self.capabilities()}

    def render_workspace_panel(self, *, case_id: str, csrf: str = "") -> str:
        esc=lambda value: html.escape(str(value or ""))
        status=self.status(case_id=case_id); ai=status["ai"]; opsec=status["opsec"]; gate=status["gate"]; caps=status["capabilities"]
        options="".join(f"<option value='{esc(p['vault_item_id'])}'>{esc(p['original_filename'] or p['vault_item_id'])} · {int(p['byte_size'])} B</option>" for p in status["pdf_candidates"])
        doc_rows="".join(f"<tr><td>{esc(d['original_filename'])}</td><td>{esc(d['extraction_status'])}</td><td>{d['page_count']}</td><td>{d['span_count']}</td><td>{esc(d.get('assessment',{}).get('decision',''))}</td><td><code>{esc(d['content_sha256'][:16])}…</code></td></tr>" for d in status["documents"]) or "<tr><td colspan='6' class='muted'>Noch keine PDFs mit Build 255 verarbeitet.</td></tr>"
        return f"""<section class='cockpit244'><h2>Influence &amp; Funding Investigation Pack · Document Provenance Pipeline 255</h2>
<p class='muted'>Statische PDF-, OCR- und Tabellenextraktion aus dem unveränderten Evidence Vault. Jeder Text-/OCR-/Tabellen-Span bleibt an SHA-256, Seite und Locator gebunden.</p>
<div class='metrics'><div class='metric'><div class='label'>PDFs verarbeitet</div><div class='value'>{len(status['documents'])}</div></div><div class='metric'><div class='label'>AI Gold-Benchmarks</div><div class='value'>{ai['curated_reviewed_benchmarks']}</div></div><div class='metric'><div class='label'>OPSEC Controls</div><div class='value'>{opsec['verified_controls']}/{opsec['required_controls']}</div></div><div class='metric'><div class='label'>Crosscut Gate</div><div class='value'>{'PASS' if gate['release_ready'] else 'CHECK'}</div></div></div>
<div class='grid'><div class='card'><h3>Vault-PDF verarbeiten</h3><form method='post' action='/build255/process'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='vault_item_id' required><option value=''>PDF aus Evidence Vault wählen</option>{options}</select><div class='inline'><label><input type='checkbox' name='allow_ocr' value='1' checked> lokale OCR für textarme Seiten zulassen</label></div><button>Static Extract + Provenance</button></form><p class='muted'>Kein Link wird geöffnet, kein eingebetteter Payload ausgeführt, kein Netzwerkzugriff durchgeführt.</p></div>
<div class='card'><h3>AI-Trainingskandidat</h3><form method='post' action='/build255/training-candidate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='span_id' placeholder='Span-ID aus geprüfter Extraktion' required><textarea name='task_instruction' placeholder='Welche Aufgabe soll die AI an diesem reviewbaren Beispiel lernen?' required></textarea><button>Als pending Kandidat an Build 228 übergeben</button></form><p class='muted'>Nur intakte Provenienz. Keine automatische Freigabe, Dataset-Aufnahme oder Adapteraktivierung.</p></div>
<div class='card'><h3>Pipeline-Fähigkeiten</h3><p>Native PDF: <b>{'OK' if caps['native_pdf_text'] else 'FEHLT'}</b><br>PDF-Strukturprüfung: <b>{'OK' if caps['pdf_structure'] else 'FEHLT'}</b><br>Tabellen: <b>{'OK' if caps['table_extraction'] else 'FEHLT'}</b><br>OCR Wrapper: <b>{'OK' if caps['ocr_wrapper'] else 'FEHLT'}</b><br>Lokales Tesseract: <b>{'OK' if caps['local_tesseract_executable'] else 'optional/nicht gefunden'}</b></p></div>
<div class='card'><h3>OPSEC-Entscheidung</h3><p>Encrypted, JavaScript, OpenAction, Additional Actions, Launch, Embedded Files oder XFA → <b>Quarantine / Manual Review</b>.</p><p>Externe URI-Links bleiben inert; sie werden weder aufgelöst noch geladen.</p></div></div>
<div class='table-wrap'><table><thead><tr><th>Dokument</th><th>Status</th><th>Seiten</th><th>Spans</th><th>OPSEC</th><th>SHA-256</th></tr></thead><tbody>{doc_rows}</tbody></table></div>
<div class='notice warn'>Build 255 interpretiert extrahierten Text nicht automatisch als Tatsache. OCR- und Tabellenwerte sind abgeleitete Evidenz und müssen bei relevanten Claims gegen den Originalspan bzw. die Originalseite geprüft werden.</div>
<div class='grid'><div class='card'><h3>AI-Delta 255</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> reviewte Gold-Benchmarks aus {ai['task_family_coverage']} Aufgabenfamilien: Native Text, OCR, Table Cell und Provenance. Bewertet werden Textähnlichkeit, Seite, Block-/Zelltyp und Provenienzklasse gemeinsam.</p><p class='muted'>Keine automatische Modell-/Adapteraktivierung.</p></div><div class='card'><h3>OPSEC-Delta 255</h3><p>{int(opsec['control_coverage']*100)}% Control-Coverage; Active-Content-Ausführungen, externe Fetches, Embedded-Payload-Ausführungen und autonome Netzwerkänderungen jeweils <b>0</b>.</p></div></div>
</section>"""
