from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile, BadZipFile
import hashlib
import json
import re
import secrets
import xml.etree.ElementTree as ET

BUILD = "458.0"
POLICY_ID = "phase20.document-intelligence-precise-anchors.v458"

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_ANCHORS = 5000
MAX_OCR_PAGES = 20
MAX_ANCHOR_TEXT = 6000

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MEDIA = "application/pdf"

CAPTION_RE = re.compile(
    r"^\s*(?:figure|fig\.?|abb\.?|abbildung|table|tabelle)\s*[A-Za-z0-9IVX.-]+",
    re.IGNORECASE,
)
FOOTNOTE_RE = re.compile(r"^\s*(?:\[?\d{1,3}\]?|[*†‡])(?:[.)\]:-]?\s+)\S+")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha_bytes(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def _sha(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _sha_bytes(value)
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _clean(value, limit=MAX_ANCHOR_TEXT):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _anchor_type(text, *, bottom=False):
    clean = _clean(text)
    if CAPTION_RE.match(clean):
        return "figure_caption"
    if bottom and FOOTNOTE_RE.match(clean):
        return "footnote_candidate"
    return "paragraph"


class DocumentIntelligence458:
    """Canonical document extraction bound to Build-447 Evidence.

    Raw document bytes are never persisted by this service. They are accepted only
    long enough to verify the Evidence content digest and derive reviewable anchors.
    OCR is bounded, optional and explicitly labelled; extraction never determines
    truth or automatically changes Evidence/Claim review state.
    """

    def __init__(self, db, audit, *, closure447, governance, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.closure447 = closure447
        self.governance = governance
        self.actor = actor
        self._schema()

    def _schema(self):
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS phase20_document_458(
              document_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              evidence_id TEXT NOT NULL,
              evidence_hash TEXT NOT NULL,
              document_sha256 TEXT NOT NULL,
              title TEXT NOT NULL,
              media_type TEXT NOT NULL,
              page_count INTEGER NOT NULL,
              extraction_mode TEXT NOT NULL,
              extracted_text_sha256 TEXT NOT NULL,
              ocr_pages INTEGER NOT NULL,
              ocr_status TEXT NOT NULL,
              anchor_count INTEGER NOT NULL,
              review_required INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(evidence_id,evidence_hash,document_sha256)
            );
            CREATE INDEX IF NOT EXISTS idx_doc458_case
              ON phase20_document_458(case_id,evidence_id,created_at);

            CREATE TABLE IF NOT EXISTS phase20_document_anchor_458(
              anchor_id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              evidence_id TEXT NOT NULL,
              evidence_hash TEXT NOT NULL,
              document_sha256 TEXT NOT NULL,
              page_number INTEGER NOT NULL,
              anchor_type TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              locator TEXT NOT NULL,
              text TEXT NOT NULL,
              text_sha256 TEXT NOT NULL,
              extraction_mode TEXT NOT NULL,
              bbox_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(document_id,page_number,anchor_type,ordinal)
            );
            CREATE INDEX IF NOT EXISTS idx_anchor458_evidence
              ON phase20_document_anchor_458(case_id,evidence_id,page_number,ordinal);

            CREATE TABLE IF NOT EXISTS phase20_claim_document_anchor_458(
              link_id TEXT PRIMARY KEY,
              claim_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              evidence_id TEXT NOT NULL,
              evidence_hash_at_link TEXT NOT NULL,
              claim_hash_at_link TEXT NOT NULL,
              anchor_id TEXT NOT NULL,
              anchor_hash_at_link TEXT NOT NULL,
              stance TEXT NOT NULL,
              note TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(claim_id,anchor_id,stance)
            );
            CREATE INDEX IF NOT EXISTS idx_claim_anchor458_claim
              ON phase20_claim_document_anchor_458(claim_id,stance,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "build458")}

    def _authorize(self, identity, case_id, capability, object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=str(capability),
            object_type="document_intelligence_458",
            object_id=str(object_id or case_id),
        )
        return ident

    def _document_row(self, document_id):
        row = self.db.one(
            "SELECT * FROM phase20_document_458 WHERE document_id=?",
            (str(document_id),),
        )
        if not row:
            raise KeyError("Build-458 document not found")
        return dict(row)

    def _anchor_row(self, anchor_id):
        row = self.db.one(
            "SELECT * FROM phase20_document_anchor_458 WHERE anchor_id=?",
            (str(anchor_id),),
        )
        if not row:
            raise KeyError("Build-458 anchor not found")
        return dict(row)

    def _decode_anchor(self, row):
        item = dict(row)
        try:
            item["bbox"] = json.loads(item.pop("bbox_json"))
        except Exception:
            item["bbox"] = {}
        return item

    def _decode_document(self, row, *, include_anchors=True):
        item = dict(row)
        item["review_required"] = bool(item["review_required"])
        if include_anchors:
            item["anchors"] = [
                self._decode_anchor(x)
                for x in self.db.all(
                    "SELECT * FROM phase20_document_anchor_458 WHERE document_id=? "
                    "ORDER BY CASE WHEN page_number=0 THEN 999999 ELSE page_number END,"
                    "ordinal,anchor_id",
                    (item["document_id"],),
                )
            ]
        return item

    def _add_anchor(self, anchors, *, page, kind, ordinal, locator, text, mode, bbox=None):
        clean = _clean(text)
        if not clean or len(anchors) >= MAX_ANCHORS:
            return
        anchors.append(
            {
                "page_number": int(page),
                "anchor_type": str(kind),
                "ordinal": int(ordinal),
                "locator": str(locator)[:500],
                "text": clean,
                "text_sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
                "extraction_mode": str(mode),
                "bbox": bbox or {},
            }
        )

    def _extract_text(self, raw):
        try:
            text = raw.decode("utf-8")
            mode = "native_text_utf8"
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
            mode = "native_text_fallback"
        parts = [x.strip() for x in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if x.strip()]
        if len(parts) <= 1:
            parts = [x.strip() for x in text.splitlines() if x.strip()]
        anchors = []
        for index, part in enumerate(parts[:MAX_ANCHORS], 1):
            self._add_anchor(
                anchors,
                page=1,
                kind=_anchor_type(part, bottom=False),
                ordinal=index,
                locator=f"page:1:paragraph:{index}",
                text=part,
                mode=mode,
            )
        return {
            "page_count": 1,
            "anchors": anchors,
            "extraction_mode": mode,
            "ocr_pages": 0,
            "ocr_status": "not_required",
        }

    def _docx_text(self, node, ns):
        return _clean("".join(x.text or "" for x in node.findall(".//w:t", ns)))

    def _extract_docx(self, raw):
        try:
            zf = ZipFile(BytesIO(raw))
        except BadZipFile as exc:
            raise ValueError("invalid DOCX archive") from exc
        with zf:
            infos = zf.infolist()
            if len(infos) > 5000:
                raise ValueError("DOCX archive has too many entries")
            if any(x.flag_bits & 0x1 for x in infos):
                raise ValueError("encrypted DOCX is not supported")
            total_uncompressed = sum(int(x.file_size) for x in infos)
            if total_uncompressed > 100 * 1024 * 1024:
                raise ValueError("DOCX expanded size exceeds limit")
            try:
                xml = zf.read("word/document.xml")
            except KeyError as exc:
                raise ValueError("DOCX word/document.xml missing") from exc
            if len(xml) > 25 * 1024 * 1024:
                raise ValueError("DOCX document.xml exceeds limit")
            root = ET.fromstring(xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            body = root.find(".//w:body", ns)
            anchors = []
            ordinal = 0
            if body is not None:
                for child in list(body):
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag == "p":
                        text = self._docx_text(child, ns)
                        if text:
                            ordinal += 1
                            self._add_anchor(
                                anchors,
                                page=0,
                                kind=_anchor_type(text),
                                ordinal=ordinal,
                                locator=f"document:paragraph:{ordinal}",
                                text=text,
                                mode="docx_xml",
                            )
                    elif tag == "tbl":
                        rows = []
                        for tr in child.findall(".//w:tr", ns):
                            cells = [self._docx_text(tc, ns) for tc in tr.findall("./w:tc", ns)]
                            if any(cells):
                                rows.append("\t".join(cells))
                        if rows:
                            ordinal += 1
                            self._add_anchor(
                                anchors,
                                page=0,
                                kind="table",
                                ordinal=ordinal,
                                locator=f"document:table:{ordinal}",
                                text="\n".join(rows),
                                mode="docx_xml",
                            )
            try:
                foot = zf.read("word/footnotes.xml")
            except KeyError:
                foot = b""
            if foot and len(foot) <= 10 * 1024 * 1024:
                foot_root = ET.fromstring(foot)
                for fn in foot_root.findall(".//w:footnote", ns):
                    fid = fn.attrib.get("{%s}id" % ns["w"], "")
                    if str(fid).startswith("-"):
                        continue
                    text = self._docx_text(fn, ns)
                    if text:
                        ordinal += 1
                        self._add_anchor(
                            anchors,
                            page=0,
                            kind="footnote",
                            ordinal=ordinal,
                            locator=f"document:footnote:{fid or ordinal}",
                            text=text,
                            mode="docx_xml",
                        )
            return {
                "page_count": 0,
                "anchors": anchors,
                "extraction_mode": "docx_xml",
                "ocr_pages": 0,
                "ocr_status": "not_applicable",
            }

    def _ocr_page(self, page):
        try:
            import fitz
            from PIL import Image
            import pytesseract
        except Exception:
            return "", "unavailable"
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image = Image.open(BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(image, lang="eng", timeout=20)
            return str(text or ""), "completed"
        except Exception:
            return "", "failed"

    def _extract_pdf(self, raw, *, allow_ocr, max_pages, max_ocr_pages):
        if not raw.startswith(b"%PDF-"):
            raise ValueError("PDF magic header missing")
        try:
            import fitz
        except Exception as exc:
            raise RuntimeError("PyMuPDF is required for Build-458 PDF extraction") from exc
        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as exc:
            raise ValueError("invalid or unsupported PDF") from exc
        with doc:
            page_count = int(doc.page_count)
            if page_count > int(max_pages):
                raise ValueError("PDF page count exceeds configured limit")
            anchors = []
            ocr_pages = 0
            ocr_states = []
            any_native = False
            any_ocr = False
            for page_index in range(page_count):
                if len(anchors) >= MAX_ANCHORS:
                    break
                page = doc.load_page(page_index)
                page_no = page_index + 1
                rect = page.rect
                page_anchor_start = len(anchors)
                native_chars = 0
                try:
                    blocks = page.get_text("blocks") or []
                except Exception:
                    blocks = []
                blocks = sorted(
                    blocks,
                    key=lambda b: (
                        round(float(b[1]) if len(b) > 1 else 0.0, 2),
                        round(float(b[0]) if len(b) > 0 else 0.0, 2),
                    ),
                )
                paragraph_ordinal = 0
                for block in blocks:
                    if len(anchors) >= MAX_ANCHORS:
                        break
                    text = _clean(block[4] if len(block) > 4 else "")
                    if len(text) < 2:
                        continue
                    native_chars += len(text)
                    paragraph_ordinal += 1
                    x0, y0, x1, y1 = [float(block[i]) for i in range(4)]
                    bottom = y0 >= float(rect.height) * 0.76
                    self._add_anchor(
                        anchors,
                        page=page_no,
                        kind=_anchor_type(text, bottom=bottom),
                        ordinal=paragraph_ordinal,
                        locator=f"page:{page_no}:block:{paragraph_ordinal}",
                        text=text,
                        mode="pdf_native_text",
                        bbox={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    )
                if native_chars >= 40:
                    any_native = True

                # Native tables are optional; failures never invalidate other anchors.
                try:
                    finder = getattr(page, "find_tables", None)
                    if callable(finder):
                        found = finder()
                        for table_index, table in enumerate(getattr(found, "tables", []) or [], 1):
                            extracted = table.extract() or []
                            rows = [
                                "\t".join(_clean(cell or "", 1000) for cell in row)
                                for row in extracted
                            ]
                            table_text = "\n".join(x for x in rows if x.strip())
                            if table_text:
                                self._add_anchor(
                                    anchors,
                                    page=page_no,
                                    kind="table",
                                    ordinal=table_index,
                                    locator=f"page:{page_no}:table:{table_index}",
                                    text=table_text,
                                    mode="pdf_native_table",
                                    bbox={
                                        "x0": float(table.bbox[0]),
                                        "y0": float(table.bbox[1]),
                                        "x1": float(table.bbox[2]),
                                        "y1": float(table.bbox[3]),
                                    } if getattr(table, "bbox", None) else {},
                                )
                except Exception:
                    pass

                if native_chars < 40:
                    if allow_ocr and ocr_pages < int(max_ocr_pages):
                        ocr_text, state = self._ocr_page(page)
                        ocr_states.append(state)
                        if ocr_text.strip():
                            ocr_pages += 1
                            any_ocr = True
                            chunks = [
                                x.strip()
                                for x in re.split(r"\n\s*\n|\r\n\s*\r\n", ocr_text)
                                if x.strip()
                            ]
                            if len(chunks) <= 1:
                                chunks = [x.strip() for x in ocr_text.splitlines() if x.strip()]
                            for idx, chunk in enumerate(chunks, 1):
                                self._add_anchor(
                                    anchors,
                                    page=page_no,
                                    kind=_anchor_type(chunk),
                                    ordinal=10000 + idx,
                                    locator=f"page:{page_no}:ocr:{idx}",
                                    text=chunk,
                                    mode="ocr_eng_tesseract",
                                )
                        elif len(anchors) == page_anchor_start:
                            ocr_states.append("no_text")
                    elif len(anchors) == page_anchor_start:
                        ocr_states.append("required_not_requested")

            if any_ocr and any_native:
                mode = "mixed_native_ocr"
            elif any_ocr:
                mode = "ocr_fallback"
            else:
                mode = "pdf_native"
            if not ocr_states:
                ocr_status = "not_required"
            elif any(x in {"unavailable", "failed"} for x in ocr_states):
                ocr_status = "partial_or_unavailable"
            elif "required_not_requested" in ocr_states:
                ocr_status = "required_not_requested"
            elif any_ocr:
                ocr_status = "completed_bounded"
            else:
                ocr_status = "no_text"
            return {
                "page_count": page_count,
                "anchors": anchors,
                "extraction_mode": mode,
                "ocr_pages": ocr_pages,
                "ocr_status": ocr_status,
            }

    def _extract(self, raw, media_type, *, allow_ocr, max_pages, max_ocr_pages):
        media = str(media_type or "").split(";", 1)[0].strip().casefold()
        if raw.startswith(b"%PDF-") or media == PDF_MEDIA:
            return self._extract_pdf(
                raw,
                allow_ocr=bool(allow_ocr),
                max_pages=max_pages,
                max_ocr_pages=max_ocr_pages,
            )
        if media == DOCX_MEDIA or (
            raw.startswith(b"PK") and b"[Content_Types].xml" in raw[:2_000_000]
        ):
            return self._extract_docx(raw)
        if media.startswith("text/") or media in {"application/json", "application/xml"}:
            return self._extract_text(raw)
        raise ValueError("unsupported document media type")

    def ingest_document(
        self,
        *,
        identity,
        evidence_id,
        expected_evidence_hash,
        content,
        title="",
        media_type="",
        allow_ocr=False,
        max_pages=MAX_PDF_PAGES,
        max_ocr_pages=MAX_OCR_PAGES,
    ):
        evidence = self.closure447.evidence(evidence_id)
        ident = self._authorize(identity, evidence["case_id"], "dossier.write", evidence_id)
        if str(expected_evidence_hash or "") != str(evidence.get("record_hash") or ""):
            raise PermissionError("Evidence changed after document import was opened")
        raw = bytes(content)
        if not raw:
            raise ValueError("document content is required")
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError("document exceeds Build-458 byte limit")
        if not 1 <= int(max_pages) <= MAX_PDF_PAGES:
            raise ValueError("max_pages outside Build-458 bounds")
        if not 0 <= int(max_ocr_pages) <= MAX_OCR_PAGES:
            raise ValueError("max_ocr_pages outside Build-458 bounds")
        digest = _sha_bytes(raw)
        if digest != str(evidence.get("content_sha256") or ""):
            raise PermissionError("document bytes do not match canonical Evidence content hash")

        media = str(media_type or evidence.get("media_type") or "application/octet-stream").split(";", 1)[0].strip().casefold()
        existing = self.db.one(
            "SELECT * FROM phase20_document_458 WHERE evidence_id=? AND evidence_hash=? "
            "AND document_sha256=?",
            (str(evidence_id), str(evidence["record_hash"]), digest),
        )
        if existing:
            return self._decode_document(existing)

        extracted = self._extract(
            raw,
            media,
            allow_ocr=bool(allow_ocr),
            max_pages=int(max_pages),
            max_ocr_pages=int(max_ocr_pages),
        )
        anchors = extracted["anchors"][:MAX_ANCHORS]
        joined = "\n".join(x["text"] for x in anchors)
        now = _now()
        document = {
            "document_id": "doc458_" + secrets.token_hex(10),
            "case_id": str(evidence["case_id"]),
            "evidence_id": str(evidence_id),
            "evidence_hash": str(evidence["record_hash"]),
            "document_sha256": digest,
            "title": _clean(title or evidence.get("title") or "Document", 1000),
            "media_type": media,
            "page_count": int(extracted["page_count"]),
            "extraction_mode": str(extracted["extraction_mode"]),
            "extracted_text_sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
            "ocr_pages": int(extracted["ocr_pages"]),
            "ocr_status": str(extracted["ocr_status"]),
            "anchor_count": len(anchors),
            "review_required": 1,
            "created_by": str(ident["username"]),
            "created_at": now,
        }
        document["record_hash"] = self._rh(document)

        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO phase20_document_458 VALUES("
                + ",".join("?" for _ in document)
                + ")",
                tuple(document.values()),
            )
            type_counts = {}
            per_type_ordinal = {}
            for anchor in anchors:
                kind = anchor["anchor_type"]
                per_type_ordinal[kind] = per_type_ordinal.get(kind, 0) + 1
                type_counts[kind] = type_counts.get(kind, 0) + 1
                row = {
                    "anchor_id": "anc458_" + secrets.token_hex(10),
                    "document_id": document["document_id"],
                    "case_id": document["case_id"],
                    "evidence_id": document["evidence_id"],
                    "evidence_hash": document["evidence_hash"],
                    "document_sha256": digest,
                    "page_number": int(anchor["page_number"]),
                    "anchor_type": kind,
                    "ordinal": int(anchor["ordinal"]),
                    "locator": anchor["locator"],
                    "text": anchor["text"],
                    "text_sha256": anchor["text_sha256"],
                    "extraction_mode": anchor["extraction_mode"],
                    "bbox_json": _canon(anchor.get("bbox") or {}),
                    "created_at": now,
                }
                row["record_hash"] = self._rh(row)
                self.db.execute(
                    "INSERT INTO phase20_document_anchor_458 VALUES("
                    + ",".join("?" for _ in row)
                    + ")",
                    tuple(row.values()),
                )

        self.audit.log(
            "document_extracted_458",
            "phase20_document_458",
            document["document_id"],
            document["case_id"],
            {
                "evidence_id": evidence_id,
                "document_sha256": digest,
                "page_count": document["page_count"],
                "anchor_count": document["anchor_count"],
                "anchor_types": type_counts,
                "extraction_mode": document["extraction_mode"],
                "ocr_status": document["ocr_status"],
                "raw_payload_persisted": False,
                "automatic_truth_determination": False,
            },
        )
        return self.document(identity=ident, document_id=document["document_id"])

    def document(self, *, identity, document_id):
        row = self._document_row(document_id)
        self._authorize(identity, row["case_id"], "case.read", document_id)
        item = self._decode_document(row)
        evidence = self.closure447.evidence(row["evidence_id"])
        item["evidence_current"] = str(evidence.get("record_hash") or "") == str(row["evidence_hash"])
        item["raw_payload_persisted"] = False
        return item

    def case_documents(self, *, identity, case_id):
        self._authorize(identity, case_id, "case.read", case_id)
        return [
            self._decode_document(row, include_anchors=False)
            for row in self.db.all(
                "SELECT * FROM phase20_document_458 WHERE case_id=? ORDER BY created_at,document_id",
                (str(case_id),),
            )
        ]

    def anchors_for_evidence(self, *, identity, evidence_id):
        evidence = self.closure447.evidence(evidence_id)
        self._authorize(identity, evidence["case_id"], "case.read", evidence_id)
        return [
            self._decode_anchor(row)
            for row in self.db.all(
                "SELECT * FROM phase20_document_anchor_458 WHERE evidence_id=? "
                "ORDER BY page_number,ordinal,anchor_id",
                (str(evidence_id),),
            )
        ]

    def link_claim_anchor(
        self,
        *,
        identity,
        claim_id,
        anchor_id,
        stance,
        note="",
        expected_claim_hash,
        expected_evidence_hash,
        expected_anchor_hash,
    ):
        claim = self.closure447.claim(claim_id)
        anchor = self._anchor_row(anchor_id)
        evidence = self.closure447.evidence(anchor["evidence_id"])
        ident = self._authorize(identity, claim["case_id"], "dossier.write", claim_id)
        if claim["case_id"] != anchor["case_id"] or claim["case_id"] != evidence["case_id"]:
            raise PermissionError("Claim, Evidence and document anchor must belong to the same case")
        if str(expected_claim_hash or "") != str(claim.get("record_hash") or ""):
            raise PermissionError("Claim changed after anchor linking was opened")
        if str(expected_evidence_hash or "") != str(evidence.get("record_hash") or ""):
            raise PermissionError("Evidence changed after anchor linking was opened")
        if str(expected_anchor_hash or "") != str(anchor.get("record_hash") or ""):
            raise PermissionError("document anchor changed after linking was opened")
        if evidence.get("review_state") != "accepted":
            raise PermissionError("only accepted Evidence may support a document-anchor Claim link")
        stance = str(stance or "").strip().lower()
        if stance not in {"support", "contradict", "context"}:
            raise ValueError("unsupported Claim anchor stance")

        claim_link = self.db.one(
            "SELECT * FROM claim_evidence_link_447 WHERE claim_id=? AND evidence_id=? AND stance=? "
            "ORDER BY rowid DESC LIMIT 1",
            (str(claim_id), str(evidence["evidence_id"]), stance),
        )
        if not claim_link:
            raise PermissionError("Claim must already contain the matching Build-447 Evidence stance")
        if str(claim_link["evidence_hash_at_link"]) != str(evidence["record_hash"]):
            raise PermissionError("Build-447 Claim/Evidence link is stale")

        existing = self.db.one(
            "SELECT * FROM phase20_claim_document_anchor_458 WHERE claim_id=? AND anchor_id=? AND stance=?",
            (str(claim_id), str(anchor_id), stance),
        )
        if existing:
            return dict(existing)
        row = {
            "link_id": "cal458_" + secrets.token_hex(10),
            "claim_id": str(claim_id),
            "case_id": str(claim["case_id"]),
            "evidence_id": str(evidence["evidence_id"]),
            "evidence_hash_at_link": str(evidence["record_hash"]),
            "claim_hash_at_link": str(claim["record_hash"]),
            "anchor_id": str(anchor_id),
            "anchor_hash_at_link": str(anchor["record_hash"]),
            "stance": stance,
            "note": _clean(note, 3000),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_claim_document_anchor_458 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "claim_document_anchor_linked_458",
            "phase20_claim_document_anchor_458",
            row["link_id"],
            row["case_id"],
            {
                "claim_id": claim_id,
                "evidence_id": evidence["evidence_id"],
                "anchor_id": anchor_id,
                "stance": stance,
                "automatic_claim_acceptance": False,
            },
        )
        return row

    def claim_anchor_citations(self, *, identity, claim_id):
        claim = self.closure447.claim(claim_id)
        self._authorize(identity, claim["case_id"], "case.read", claim_id)
        out = []
        for raw in self.db.all(
            "SELECT * FROM phase20_claim_document_anchor_458 WHERE claim_id=? "
            "ORDER BY created_at,link_id",
            (str(claim_id),),
        ):
            link = dict(raw)
            anchor = self.db.one(
                "SELECT * FROM phase20_document_anchor_458 WHERE anchor_id=?",
                (link["anchor_id"],),
            )
            evidence = self.db.one(
                "SELECT * FROM evidence_item_447 WHERE evidence_id=?",
                (link["evidence_id"],),
            )
            current_claim = str(claim.get("record_hash") or "") == str(link["claim_hash_at_link"])
            current_evidence = bool(
                evidence
                and str(evidence["record_hash"]) == str(link["evidence_hash_at_link"])
                and evidence["review_state"] == "accepted"
            )
            current_anchor = bool(
                anchor and str(anchor["record_hash"]) == str(link["anchor_hash_at_link"])
            )
            item = {
                **link,
                "current": bool(current_claim and current_evidence and current_anchor),
                "claim_current": current_claim,
                "evidence_current": current_evidence,
                "anchor_current": current_anchor,
            }
            if anchor:
                decoded = self._decode_anchor(anchor)
                item["anchor"] = {
                    k: decoded[k]
                    for k in (
                        "anchor_id", "document_id", "page_number", "anchor_type",
                        "locator", "text", "text_sha256", "extraction_mode", "record_hash",
                    )
                }
            out.append(item)
        return out

    def case_manifest(self, *, identity, case_id, anchor_limit_per_document=120):
        self._authorize(identity, case_id, "case.read", case_id)
        docs = []
        for raw in self.db.all(
            "SELECT * FROM phase20_document_458 WHERE case_id=? ORDER BY created_at,document_id",
            (str(case_id),),
        ):
            doc = self._decode_document(raw, include_anchors=False)
            evidence = self.closure447.evidence(doc["evidence_id"])
            doc["evidence_current"] = str(evidence["record_hash"]) == str(doc["evidence_hash"])
            doc["anchors"] = [
                self._decode_anchor(x)
                for x in self.db.all(
                    "SELECT * FROM phase20_document_anchor_458 WHERE document_id=? "
                    "ORDER BY page_number,ordinal,anchor_id LIMIT ?",
                    (doc["document_id"], int(anchor_limit_per_document)),
                )
            ]
            docs.append(doc)
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "documents": docs,
            "document_count": len(docs),
            "anchor_count": sum(int(x["anchor_count"]) for x in docs),
            "raw_payload_persisted": False,
            "automatic_truth_determination": False,
        }

    def dossier_anchor_manifest(self, *, identity, revision_id):
        dossier = self.closure447.dossier(revision_id)
        self._authorize(identity, dossier["case_id"], "case.read", revision_id)
        return {
            "build": BUILD,
            "revision_id": revision_id,
            "case_id": dossier["case_id"],
            "document_anchors": list((dossier.get("snapshot") or {}).get("document_anchors") or []),
            "document_anchor_warnings": list(
                (dossier.get("snapshot") or {}).get("document_anchor_warnings") or []
            ),
        }

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("phase20_document_458", "document_id"),
            ("phase20_document_anchor_458", "anchor_id"),
            ("phase20_claim_document_anchor_458", "link_id"),
        ):
            for raw in self.db.all("SELECT * FROM " + table):
                row = dict(raw)
                if self._rh(row) != row.get("record_hash"):
                    bad.append({"table": table, "id": row.get(key), "reason": "record_hash_mismatch"})

        for raw in self.db.all("SELECT * FROM phase20_document_anchor_458"):
            anchor = dict(raw)
            parent = self.db.one(
                "SELECT * FROM phase20_document_458 WHERE document_id=?",
                (anchor["document_id"],),
            )
            if not parent:
                bad.append({"table": "phase20_document_anchor_458", "id": anchor["anchor_id"], "reason": "document_missing"})
            elif (
                str(parent["document_sha256"]) != str(anchor["document_sha256"])
                or str(parent["evidence_id"]) != str(anchor["evidence_id"])
                or str(parent["evidence_hash"]) != str(anchor["evidence_hash"])
            ):
                bad.append({"table": "phase20_document_anchor_458", "id": anchor["anchor_id"], "reason": "document_binding_mismatch"})

        for raw in self.db.all("SELECT * FROM phase20_claim_document_anchor_458"):
            link = dict(raw)
            claim = self.db.one("SELECT * FROM claim_447 WHERE claim_id=?", (link["claim_id"],))
            evidence = self.db.one("SELECT * FROM evidence_item_447 WHERE evidence_id=?", (link["evidence_id"],))
            anchor = self.db.one("SELECT * FROM phase20_document_anchor_458 WHERE anchor_id=?", (link["anchor_id"],))
            if not claim or str(claim["record_hash"]) != str(link["claim_hash_at_link"]):
                bad.append({"table": "phase20_claim_document_anchor_458", "id": link["link_id"], "reason": "claim_changed_or_missing"})
            if not evidence or str(evidence["record_hash"]) != str(link["evidence_hash_at_link"]):
                bad.append({"table": "phase20_claim_document_anchor_458", "id": link["link_id"], "reason": "evidence_changed_or_missing"})
            if not anchor or str(anchor["record_hash"]) != str(link["anchor_hash_at_link"]):
                bad.append({"table": "phase20_claim_document_anchor_458", "id": link["link_id"], "reason": "anchor_changed_or_missing"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        docs = int(self.db.one("SELECT COUNT(*) n FROM phase20_document_458")["n"])
        anchors = int(self.db.one("SELECT COUNT(*) n FROM phase20_document_anchor_458")["n"])
        links = int(self.db.one("SELECT COUNT(*) n FROM phase20_claim_document_anchor_458")["n"])
        integrity = self.verify_integrity()
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "name": "Document Intelligence 2.0 / Precise Evidence Anchors",
            "documents": docs,
            "anchors": anchors,
            "claim_anchor_links": links,
            "integrity_valid": bool(integrity["valid"]),
            "pdf_native_extraction": True,
            "docx_structured_extraction": True,
            "bounded_ocr_fallback": True,
            "ocr_language_default": "eng",
            "page_paragraph_table_footnote_caption_anchors": True,
            "claim_evidence_anchor_hash_binding": True,
            "raw_payload_persisted": False,
            "automatic_truth_determination": False,
            "automatic_claim_acceptance": False,
            "focused_development_build": True,
            "next_build": "459.0",
            "next_checkpoint": "460.0",
            "production_release_ready": False,
        }
