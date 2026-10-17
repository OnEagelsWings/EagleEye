from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import fitz

BUILD = "458.0"
MAX_DOCUMENT_BYTES = 12 * 1024 * 1024
MAX_PAGES = 160
MAX_ANCHORS = 3200
MAX_TEXT_BYTES = 2 * 1024 * 1024
REVIEW_CONFIRMATION = "REVIEW DOCUMENT EXTRACTION 458"
ANCHOR_CONFIRMATION = "LINK DOCUMENT ANCHOR 458"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(data):
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha256(_json(data).encode("utf-8")).hexdigest()


def _clean(value, limit=2000):
    return " ".join(str(value or "").split())[:limit]


def _source_url(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url must be a public http(s) reference")
    if len(raw) > 1500:
        raise ValueError("source_url is too long")
    return raw


class DocumentIntelligence458:
    """Bounded offline document extraction and human-governed Evidence citation anchors.

    No filesystem paths or remote fetches are supplied by an API caller. An anchor
    is a reproducible document-location reference, NOT independent or accepted
    evidence. Documents and attachments never alter canonical Claim decisions.
    """

    def __init__(self, db, audit, *, closure447, governance, actor="local-analyst"):
        self.db, self.audit = db, audit
        self.closure447, self.governance = closure447, governance
        self.actor = actor
        self.root = Path(db.path).parent / "documents_458"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase20_document_458(
                document_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,
                filename TEXT NOT NULL,source_url TEXT NOT NULL,media_type TEXT NOT NULL,
                document_sha256 TEXT NOT NULL,byte_size INTEGER NOT NULL,page_count INTEGER NOT NULL,
                extraction_mode TEXT NOT NULL,ocr_required INTEGER NOT NULL,stored_relpath TEXT NOT NULL,
                state TEXT NOT NULL,review_by TEXT NOT NULL,review_at TEXT NOT NULL,
                review_note TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,
                record_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_doc458_case ON phase20_document_458(case_id,created_at);
            CREATE TABLE IF NOT EXISTS phase20_document_anchor_458(
                anchor_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,case_id TEXT NOT NULL,
                document_sha256 TEXT NOT NULL,page_number INTEGER NOT NULL,ordinal INTEGER NOT NULL,
                anchor_kind TEXT NOT NULL,text_excerpt TEXT NOT NULL,normalized_text_sha256 TEXT NOT NULL,
                bbox_json TEXT NOT NULL,extraction_method TEXT NOT NULL,created_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,UNIQUE(document_id,page_number,ordinal,anchor_kind));
            CREATE INDEX IF NOT EXISTS idx_anchor458_document ON phase20_document_anchor_458(document_id,page_number,ordinal);
            CREATE TABLE IF NOT EXISTS phase20_claim_document_citation_458(
                citation_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,claim_id TEXT NOT NULL,
                link_id TEXT NOT NULL,evidence_id TEXT NOT NULL,evidence_hash TEXT NOT NULL,
                document_id TEXT NOT NULL,document_sha256 TEXT NOT NULL,anchor_id TEXT NOT NULL,
                anchor_hash TEXT NOT NULL,note TEXT NOT NULL,created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_citation458_claim ON phase20_claim_document_citation_458(case_id,claim_id);
            """
        )
        self.db.conn.commit()

    def _rh(self, item):
        return _sha({key: value for key, value in item.items() if key != "record_hash"})

    def _identity(self, identity, case_id, capability, object_id):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (ValueError, KeyError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user["user_id"]) != str(identity["user_id"]):
            raise PermissionError("canonical active identity required")
        ident = {**user, "session_id": str(identity.get("session_id") or "build458")}
        self.governance.authorize(
            ident,case_id=str(case_id),capability=capability,
            object_type="document_intelligence_458",object_id=str(object_id),
        )
        return ident

    def _document(self, document_id):
        row = self.db.one("SELECT * FROM phase20_document_458 WHERE document_id=?", (str(document_id),))
        if not row:
            raise KeyError("Build-458 document not found")
        return dict(row)

    def _anchor(self, anchor_id):
        row = self.db.one("SELECT * FROM phase20_document_anchor_458 WHERE anchor_id=?", (str(anchor_id),))
        if not row:
            raise KeyError("Build-458 anchor not found")
        return dict(row)

    @staticmethod
    def _pdf_anchors(raw):
        if not raw.startswith(b"%PDF-"):
            raise ValueError("invalid PDF signature")
        doc = fitz.open(stream=raw, filetype="pdf")
        try:
            if doc.needs_pass:
                raise ValueError("encrypted PDF requires manual handling")
            if not 1 <= len(doc) <= MAX_PAGES:
                raise ValueError("PDF page count out of permitted bounds")
            anchors, ocr_pages = [], []
            for idx, page in enumerate(doc):
                blocks = page.get_text("blocks", sort=True)
                page_items = 0
                for blk in blocks:
                    if len(blk) < 5 or (len(blk) > 6 and blk[6] != 0):
                        continue
                    text = _clean(blk[4], 2500)
                    if len(text) < 8:
                        continue
                    y0 = float(blk[1])
                    y1 = float(blk[3])
                    kind = "caption" if re.match(r"^(table|figure|abb\.|tabelle|abbildung)\s*[0-9:.]", text, re.I) else (
                        "footnote_candidate" if y0 > page.rect.height * 0.82 else "paragraph"
                    )
                    anchors.append({
                        "page_number": idx + 1,
                        "ordinal": page_items + 1,
                        "anchor_kind": kind,
                        "text_excerpt": text,
                        "bbox": [round(float(blk[0]), 2),round(y0, 2),round(float(blk[2]), 2),round(y1, 2)],
                        "extraction_method": "native_pdf_text",
                    })
                    page_items += 1
                    if len(anchors) > MAX_ANCHORS:
                        raise ValueError("document anchor count exceeds limit")
                if page_items == 0:
                    ocr_pages.append(idx + 1)
            return anchors, len(doc), ocr_pages
        finally:
            doc.close()

    @staticmethod
    def _text_anchors(raw):
        try:
            content = raw.decode("utf-8-sig", errors="strict")
        except UnicodeError as exc:
            raise ValueError("text document must be valid UTF-8") from exc
        if len(raw) > MAX_TEXT_BYTES:
            raise ValueError("text document exceeds limit")
        chunks = [x.strip() for x in re.split(r"\n\s*\n",content) if x.strip()]
        if not chunks and content.strip():
            chunks = [content.strip()]
        if len(chunks) > MAX_ANCHORS:
            raise ValueError("text document paragraph count exceeds limit")
        return [
            {"page_number":1,"ordinal":i+1,"anchor_kind":"paragraph",
             "text_excerpt":_clean(block,2500),"bbox":None,"extraction_method":"native_utf8_text"}
            for i,block in enumerate(chunks)
        ],1,[]

    def import_bytes(self, *, identity, case_id, filename, raw, title="", source_url=""):
        ident = self._identity(identity,case_id,"research.run",case_id)
        if not isinstance(raw,(bytes,bytearray)) or not 0 < len(raw) <= MAX_DOCUMENT_BYTES:
            raise ValueError("document size exceeds bounded upload limit")
        name = Path(str(filename or "document").replace("\\","/")).name[:180]
        suffix = Path(name).suffix.casefold()
        if suffix == ".pdf":
            if not raw.startswith(b"%PDF-"):
                raise ValueError("invalid PDF signature")
            anchors,pages,ocr_pages = self._pdf_anchors(raw)
            media = "application/pdf"
        elif suffix in {".txt",".md"}:
            anchors,pages,ocr_pages = self._text_anchors(raw)
            media = "text/plain; charset=utf-8"
        else:
            raise ValueError("supported document types: PDF, TXT, MD")
        document_id = "doc458_" + secrets.token_hex(12)
        doc_digest = _sha(raw)
        rel = document_id + ".bin"
        target = self.root / rel
        temp = self.root / (rel + ".tmp")
        with temp.open("xb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(temp,0o600)
        temp.replace(target)
        try:
            row = {
                "document_id":document_id,"case_id":str(case_id),"title":_clean(title or name,300),
                "filename":name,"source_url":_source_url(source_url),"media_type":media,
                "document_sha256":doc_digest,"byte_size":len(raw),"page_count":pages,
                "extraction_mode":"native_pdf_text" if suffix==".pdf" else "native_utf8_text",
                "ocr_required":int(bool(ocr_pages)),"stored_relpath":rel,"state":"review_required",
                "review_by":"","review_at":"","review_note":"",
                "created_by":str(ident["username"]),"created_at":_now(),
            }
            row["record_hash"] = self._rh(row)
            with self.db.transaction(immediate=True):
                self.db.execute("INSERT INTO phase20_document_458 VALUES("+",".join("?" for _ in row)+")",tuple(row.values()))
                for item in anchors:
                    anchor = {
                        "anchor_id":"anchor458_"+secrets.token_hex(12),
                        "document_id":document_id,"case_id":str(case_id),
                        "document_sha256":doc_digest,"page_number":item["page_number"],
                        "ordinal":item["ordinal"],"anchor_kind":item["anchor_kind"],
                        "text_excerpt":item["text_excerpt"],
                        "normalized_text_sha256":_sha(_clean(item["text_excerpt"]).casefold().encode("utf-8")),
                        "bbox_json":_json(item["bbox"]),"extraction_method":item["extraction_method"],
                        "created_at":_now(),
                    }
                    anchor["record_hash"] = self._rh(anchor)
                    self.db.execute("INSERT INTO phase20_document_anchor_458 VALUES("+",".join("?" for _ in anchor)+")",tuple(anchor.values()))
                self.audit.log("document_imported_458","document",document_id,str(case_id),
                    {"sha256":doc_digest,"pages":pages,"anchors":len(anchors),"ocr_required":bool(ocr_pages),"human_review_required":True})
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {"document_id":document_id,"case_id":str(case_id),"document_sha256":doc_digest,
                "pages":pages,"anchors":len(anchors),"ocr_required_pages":ocr_pages,
                "state":"review_required","automatic_evidence_promotion":False}

    def documents(self, *, identity, case_id):
        self._identity(identity,case_id,"case.read",case_id)
        return [dict(row) for row in self.db.all(
            "SELECT * FROM phase20_document_458 WHERE case_id=? ORDER BY rowid DESC",(str(case_id),))]

    def anchors(self, *, identity, document_id):
        document = self._document(document_id)
        self._identity(identity,document["case_id"],"case.read",document_id)
        rows = [dict(row) for row in self.db.all(
            "SELECT * FROM phase20_document_anchor_458 WHERE document_id=? ORDER BY page_number,ordinal",(str(document_id),))]
        for row in rows:
            row["bbox"] = json.loads(row.pop("bbox_json"))
            row["locator"] = f"{document_id}:p{row['page_number']}:b{row['ordinal']}:{row['normalized_text_sha256'][:12]}"
        return {"document":document,"anchors":rows,
                "ocr_required":bool(document["ocr_required"]),"human_review_required":True}

    def review_extraction(self, *, identity, document_id, expected_document_hash, decision, note, confirmation):
        if str(confirmation or "").strip().upper() != REVIEW_CONFIRMATION:
            raise PermissionError("explicit extraction review confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in {"approve","reject"}:
            raise ValueError("invalid extraction review decision")
        if len(_clean(note,3000)) < 12:
            raise ValueError("document review rationale required")
        with self.db.transaction(immediate=True):
            row = self._document(document_id)
            ident = self._identity(identity,row["case_id"],"source.review",document_id)
            if row["record_hash"] != str(expected_document_hash or ""):
                raise PermissionError("document changed after analyst opened review")
            if row["state"] != "review_required":
                raise ValueError("document has already been reviewed")
            row["state"] = "extraction_approved" if decision=="approve" else "extraction_rejected"
            row["review_by"] = str(ident["username"])
            row["review_at"] = _now()
            row["review_note"] = _clean(note,3000)
            row["record_hash"] = self._rh(row)
            self.db.execute(
                "UPDATE phase20_document_458 SET state=?,review_by=?,review_at=?,review_note=?,record_hash=? WHERE document_id=?",
                (row["state"],row["review_by"],row["review_at"],row["review_note"],row["record_hash"],document_id))
            self.audit.log("document_extraction_reviewed_458","document",document_id,row["case_id"],
                           {"decision":decision,"document_sha256":row["document_sha256"],"truth_determined":False})
        return row

    def cite_claim_anchor(self, *, identity, claim_id, link_id, anchor_id, expected_evidence_hash,
                          expected_anchor_hash, note, confirmation):
        if str(confirmation or "").strip().upper() != ANCHOR_CONFIRMATION:
            raise PermissionError("explicit citation attachment confirmation required")
        if len(_clean(note,3000)) < 10:
            raise ValueError("citation rationale required")
        with self.db.transaction(immediate=True):
            claim = self.closure447.claim(claim_id)
            ident = self._identity(identity,claim["case_id"],"dossier.write",claim_id)
            link = self.db.one(
                "SELECT * FROM claim_evidence_link_447 WHERE link_id=? AND claim_id=? AND case_id=?",
                (str(link_id),str(claim_id),claim["case_id"]))
            if not link:
                raise KeyError("Claim link not found")
            evidence = self.closure447.evidence(link["evidence_id"])
            if evidence["case_id"] != claim["case_id"]:
                raise PermissionError("cross-case Evidence attachment blocked")
            if evidence["review_state"] not in {"accepted","context_only"}:
                raise PermissionError("Evidence requires independent review")
            if str(expected_evidence_hash or "") != evidence["record_hash"] or link["evidence_hash_at_link"] != evidence["record_hash"]:
                raise PermissionError("stale Evidence or Claim-link hash")
            anchor = self._anchor(anchor_id)
            doc = self._document(anchor["document_id"])
            if doc["case_id"] != claim["case_id"] or anchor["case_id"] != claim["case_id"]:
                raise PermissionError("cross-case document anchor blocked")
            if doc["state"] != "extraction_approved":
                raise PermissionError("document extraction must be reviewed first")
            if anchor["document_sha256"] != doc["document_sha256"] or str(expected_anchor_hash or "") != anchor["record_hash"]:
                raise PermissionError("stale document anchor")
            row = {
                "citation_id":"cite458_"+secrets.token_hex(12),
                "case_id":claim["case_id"],"claim_id":str(claim_id),"link_id":str(link_id),
                "evidence_id":evidence["evidence_id"],"evidence_hash":evidence["record_hash"],
                "document_id":doc["document_id"],"document_sha256":doc["document_sha256"],
                "anchor_id":anchor["anchor_id"],"anchor_hash":anchor["record_hash"],
                "note":_clean(note,3000),"created_by":str(ident["username"]),"created_at":_now(),
            }
            row["record_hash"] = self._rh(row)
            self.db.execute("INSERT INTO phase20_claim_document_citation_458 VALUES("+
                            ",".join("?" for _ in row)+")",tuple(row.values()))
            self.audit.log("claim_document_anchor_linked_458","citation",row["citation_id"],row["case_id"],
                {"claim_id":claim_id,"evidence_id":evidence["evidence_id"],"anchor_id":anchor_id,
                 "automatic_claim_acceptance":False})
        return row

    def claim_citations(self, *, identity, claim_id):
        claim = self.closure447.claim(claim_id)
        self._identity(identity,claim["case_id"],"case.read",claim_id)
        rows = [dict(row) for row in self.db.all(
            "SELECT * FROM phase20_claim_document_citation_458 WHERE claim_id=? AND case_id=? ORDER BY rowid",
            (str(claim_id),claim["case_id"]))]
        out=[]
        for item in rows:
            doc = self._document(item["document_id"])
            anchor = self._anchor(item["anchor_id"])
            evidence = self.closure447.evidence(item["evidence_id"])
            link = self.db.one("SELECT * FROM claim_evidence_link_447 WHERE link_id=?",(item["link_id"],))
            current = bool(
                doc["state"]=="extraction_approved" and doc["document_sha256"]==item["document_sha256"]
                and anchor["record_hash"]==item["anchor_hash"] and
                evidence["record_hash"]==item["evidence_hash"]
                and link and link["evidence_hash_at_link"]==evidence["record_hash"]
                and evidence["review_state"] in {"accepted","context_only"}
            )
            out.append({**item,"current":current,
                        "locator":f"{doc['title']} • Seite {anchor['page_number']} • Block {anchor['ordinal']}",
                        "excerpt":anchor["text_excerpt"],"extraction_method":anchor["extraction_method"],
                        "reference_ready":current})
        return {"claim_id":claim_id,"citations":out,"all_references_current":all(x["current"] for x in out),
                "automatic_truth_decision":False}

    def verify_integrity(self):
        violations=[]
        for table,key in (("phase20_document_458","document_id"),
                          ("phase20_document_anchor_458","anchor_id"),
                          ("phase20_claim_document_citation_458","citation_id")):
            for raw in self.db.all("SELECT * FROM "+table):
                row=dict(raw)
                if row["record_hash"] != self._rh(row):
                    violations.append({"table":table,"id":row[key],"reason":"record_hash_mismatch"})
        for row in self.db.all("SELECT * FROM phase20_document_458"):
            item=dict(row)
            path=self.root / item["stored_relpath"]
            if not path.is_file() or path.stat().st_size != item["byte_size"]:
                violations.append({"document_id":item["document_id"],"reason":"file_missing_or_wrong_size"})
            elif _sha(path.read_bytes()) != item["document_sha256"]:
                violations.append({"document_id":item["document_id"],"reason":"document_payload_hash_mismatch"})
        return {"build":BUILD,"valid":not violations,"violations":violations}

    def status(self):
        return {"build":BUILD,"policy":"review-first-page-anchored-document-intelligence",
                "documents":int(self.db.one("SELECT COUNT(*) AS n FROM phase20_document_458")["n"]),
                "anchors":int(self.db.one("SELECT COUNT(*) AS n FROM phase20_document_anchor_458")["n"]),
                "claim_citations":int(self.db.one("SELECT COUNT(*) AS n FROM phase20_claim_document_citation_458")["n"]),
                "integrity_valid":self.verify_integrity()["valid"],
                "automatic_evidence_promotion":False,"automatic_claim_acceptance":False,
                "ocr_without_explicit_analyst_review":False,
                "full_checkpoint_this_build":False,"next_full_checkpoint":"460.0"}
