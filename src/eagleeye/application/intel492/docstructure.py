"""Structure and OCR anchors for Build-458 PDF documents.

Adds table, heading and OCR paragraph anchors to an *unreviewed* PDF. Existing anchors
and the document record are never changed, so a completed extraction review cannot be
bypassed. OCR output is machine-read text and stays subject to the existing review.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import statistics
from datetime import datetime, timezone

MAX_NEW_ANCHORS = 2400
OCR_DPI = 300

TABLE = """CREATE TABLE IF NOT EXISTS document_enrichment_492(
    document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_sha256 TEXT NOT NULL,
    tables INTEGER NOT NULL, headings INTEGER NOT NULL, ocr_paragraphs INTEGER NOT NULL,
    ocr_pages TEXT NOT NULL, ocr_mean_confidence REAL, ocr_engine TEXT NOT NULL,
    created_by TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL)"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(value, limit=2500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _hash(row: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.commit()


def ocr_available() -> tuple[bool, str]:
    try:
        import pytesseract
        version = str(pytesseract.get_tesseract_version())
        return True, "tesseract " + version
    except Exception:  # missing binary or wrapper
        return False, ""


def _ocr_languages() -> str:
    try:
        import pytesseract
        langs = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"
    chosen = [lang for lang in ("deu", "eng") if lang in langs]
    return "+".join(chosen) or "eng"


def tesseract_page(image) -> list[dict]:
    """Return OCR paragraphs with pixel boxes and mean word confidence."""
    import pytesseract

    data = pytesseract.image_to_data(image, lang=_ocr_languages(), config="--psm 3",
                                     output_type=pytesseract.Output.DICT)
    groups: dict[tuple, dict] = {}
    for i, word in enumerate(data["text"]):
        word = str(word or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not word or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i])
        g = groups.setdefault(key, {"words": [], "conf": [], "box": [10**9, 10**9, 0, 0]})
        g["words"].append(word)
        g["conf"].append(conf)
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        g["box"] = [min(g["box"][0], x), min(g["box"][1], y), max(g["box"][2], x + w), max(g["box"][3], y + h)]
    return [{"text": " ".join(g["words"]), "confidence": statistics.fmean(g["conf"]), "box": g["box"]}
            for _, g in sorted(groups.items())]


def analyse_pdf(raw: bytes, *, ocr_pages: list[int], ocr_engine=None) -> dict:
    """Pure analysis: table, heading and OCR candidates per page (no persistence)."""
    import fitz

    doc = fitz.open(stream=raw, filetype="pdf")
    items, confidences, ocr_done = [], [], []
    try:
        sizes = []
        for page in doc:
            for block in page.get_text("dict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            sizes.append(round(float(span.get("size", 0)), 1))
        body = statistics.median(sizes) if sizes else 0
        for index, page in enumerate(doc):
            number = index + 1
            try:
                tables = page.find_tables().tables
            except Exception:
                tables = []
            for table in tables:
                rows = [" | ".join(_clean(c, 300) for c in row if c is not None) for row in (table.extract() or [])]
                text = _clean(" ; ".join(r for r in rows if r.strip()))
                if len(text) >= 8:
                    items.append({"page_number": number, "anchor_kind": "table", "text_excerpt": text,
                                  "bbox": [round(float(v), 2) for v in table.bbox],
                                  "extraction_method": "pymupdf_table"})
            if body:
                for block in page.get_text("dict").get("blocks", []):
                    for line in block.get("lines", []):
                        spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                        if not spans:
                            continue
                        text = _clean("".join(s["text"] for s in spans), 300)
                        size = max(float(s.get("size", 0)) for s in spans)
                        bold = any(int(s.get("flags", 0)) & 16 for s in spans)
                        if 3 <= len(text) <= 200 and (size >= body * 1.25 or (bold and size >= body * 1.1)) \
                                and not re.fullmatch(r"[\d\s.,/-]+", text):
                            items.append({"page_number": number, "anchor_kind": "heading", "text_excerpt": text,
                                          "bbox": [round(float(v), 2) for v in line["bbox"]],
                                          "extraction_method": "pymupdf_font_heading"})
            if number in ocr_pages and ocr_engine is not None:
                from PIL import Image
                pix = page.get_pixmap(dpi=OCR_DPI)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                scale = 72.0 / OCR_DPI
                for para in ocr_engine(image):
                    text = _clean(para["text"])
                    if len(text) < 8:
                        continue
                    confidences.append(para["confidence"])
                    items.append({"page_number": number, "anchor_kind": "ocr_paragraph", "text_excerpt": text,
                                  "bbox": [round(v * scale, 2) for v in para["box"]],
                                  "extraction_method": "ocr_tesseract"})
                ocr_done.append(number)
            if len(items) > MAX_NEW_ANCHORS:
                raise ValueError("Zu viele neue Anker für eine automatische Ergänzung.")
    finally:
        doc.close()
    return {"items": items, "ocr_pages": ocr_done,
            "ocr_mean_confidence": round(statistics.fmean(confidences), 1) if confidences else None}


def enrich_document(ctx, *, identity: dict, document_id: str, ocr_engine=None, engine_name: str = "") -> dict:
    service = ctx.document_intelligence_458
    doc = service._document(document_id)
    service._identity(identity, doc["case_id"], "research.run", document_id)
    if doc["media_type"] != "application/pdf":
        raise ValueError("Struktur- und OCR-Anker gibt es nur für PDF-Dokumente.")
    if doc["state"] != "review_required":
        raise ValueError("Das Dokument wurde bereits geprüft. Anker lassen sich nur vor der Extraktionsprüfung ergänzen.")
    if doc["record_hash"] != service._rh(doc) or not service._payload_current(doc):
        raise ValueError("Originalbeleg wurde verändert oder ist nicht verfügbar.")
    if ctx.db.one("SELECT 1 FROM document_enrichment_492 WHERE document_id=?", (document_id,)):
        raise ValueError("Für dieses Dokument wurden die Anker bereits ergänzt.")
    raw = (service.root / doc["stored_relpath"]).read_bytes()
    existing = service.anchors(identity=identity, document_id=document_id)["anchors"]
    text_pages = {a["page_number"] for a in existing if a["extraction_method"] == "native_pdf_text"}
    ocr_pages = [p for p in range(1, int(doc["page_count"]) + 1) if p not in text_pages]
    result = analyse_pdf(raw, ocr_pages=ocr_pages, ocr_engine=ocr_engine)
    counts = {"table": 0, "heading": 0, "ocr_paragraph": 0}
    with ctx.db.transaction(immediate=True):
        current = service._document(document_id)
        if current != doc:
            raise ValueError("Dokument wurde während der Ergänzung verändert.")
        ordinals: dict[tuple, int] = {}
        for item in result["items"]:
            key = (item["page_number"], item["anchor_kind"])
            ordinals[key] = ordinals.get(key, 0) + 1
            anchor = {
                "anchor_id": "anchor458_" + secrets.token_hex(12), "document_id": document_id,
                "case_id": doc["case_id"], "document_sha256": doc["document_sha256"],
                "page_number": item["page_number"], "ordinal": ordinals[key],
                "anchor_kind": item["anchor_kind"], "text_excerpt": item["text_excerpt"],
                "normalized_text_sha256": hashlib.sha256(_clean(item["text_excerpt"]).casefold().encode("utf-8")).hexdigest(),
                "bbox_json": json.dumps(item["bbox"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "extraction_method": item["extraction_method"], "created_at": _now(),
            }
            anchor["record_hash"] = service._rh(anchor)
            ctx.db.execute("INSERT INTO phase20_document_anchor_458 VALUES(" + ",".join("?" for _ in anchor) + ")",
                           tuple(anchor.values()))
            counts[item["anchor_kind"]] += 1
        row = {"document_id": document_id, "case_id": doc["case_id"], "document_sha256": doc["document_sha256"],
               "tables": counts["table"], "headings": counts["heading"], "ocr_paragraphs": counts["ocr_paragraph"],
               "ocr_pages": json.dumps(result["ocr_pages"]), "ocr_mean_confidence": result["ocr_mean_confidence"],
               "ocr_engine": engine_name if ocr_engine is not None else "",
               "created_by": str(identity["username"]), "created_at": _now()}
        row["record_hash"] = _hash(row)
        ctx.db.execute("INSERT INTO document_enrichment_492 VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        ctx.audit.log("document_structure_enriched_492", "document", document_id, doc["case_id"],
                      {**counts, "ocr_pages": result["ocr_pages"], "review_still_required": True})
    return {**row, "pages_without_text": ocr_pages, "ocr_skipped": bool(ocr_pages) and ocr_engine is None}


def enrichment_for(ctx, document_id: str) -> dict | None:
    row = ctx.db.one("SELECT * FROM document_enrichment_492 WHERE document_id=?", (document_id,))
    return dict(row) if row else None
