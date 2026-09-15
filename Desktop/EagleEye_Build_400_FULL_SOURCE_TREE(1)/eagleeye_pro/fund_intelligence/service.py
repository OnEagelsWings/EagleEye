from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

SENSITIVE_TERMS = {
    "adresse": "private_address", "anschrift": "private_address", "wohnort": "location_review",
    "telefon": "private_phone", "handy": "private_phone", "email": "email_review", "e-mail": "email_review",
    "geburtsdatum": "birth_data", "geburtsort": "birth_data", "sterbedatum": "death_data",
    "urteil": "legal_proceeding", "anklage": "legal_proceeding", "insolvenz": "financial_review",
    "minderjähr": "minor_data", "kind": "minor_data", "opfer": "victim_data", "zeuge": "witness_data",
}

HIGH_VALUE_TYPES = {
    "court_or_justice": (85, "court"),
    "registry": (82, "registry"),
    "official_public_record": (80, "registry"),
    "public_pdf": (70, "pdf"),
    "newspaper_press": (62, "web"),
    "archival_source": (65, "registry"),
    "image_media": (45, "image"),
    "public_web": (50, "web"),
}


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _hay(*parts: str) -> str:
    return " ".join(str(p or "") for p in parts).lower()


class FundImportIntelligenceService:
    """Build 60.2: turns captured results into structured person findings.

    Imported hits receive source type, sensitivity flags, initial relevance,
    suggested status/evidence level and provenance metadata before entering the
    person file. No imported hit becomes a verified fact automatically.
    """

    def __init__(self, db: Database, audit: AuditService, *, capture_pro=None, person_detail=None):
        self.db = db
        self.audit = audit
        self.capture_pro = capture_pro
        self.person_detail = person_detail
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS fund_intelligence_60_2 (
          intelligence_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          capture_result_id TEXT DEFAULT '',
          person_finding_id TEXT DEFAULT '',
          source_type TEXT NOT NULL,
          finding_type TEXT NOT NULL,
          relevance_score INTEGER DEFAULT 0,
          evidence_level TEXT DEFAULT 'candidate',
          suggested_status TEXT DEFAULT 'candidate',
          sensitivity_flags_json TEXT NOT NULL,
          export_caution TEXT DEFAULT 'review_required',
          chain_origin_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, capture_result_id)
        );
        CREATE INDEX IF NOT EXISTS idx_fund602_entity ON fund_intelligence_60_2(case_id, entity_id, relevance_score DESC);
        ''')
        self.db.conn.commit()

    def analyze_capture_result(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        source_type = capture.get("source_guess") or "public_web"
        base, finding_type = HIGH_VALUE_TYPES.get(source_type, (50, "web"))
        text = _hay(capture.get("title"), capture.get("url"), capture.get("snippet"), capture.get("category_key"))
        flags: List[str] = []
        for term, flag in SENSITIVE_TERMS.items():
            if term in text and flag not in flags:
                flags.append(flag)
        if capture.get("domain"):
            base += 4
        if capture.get("snippet"):
            base += 5
        if flags:
            base -= 5
        relevance = max(0, min(100, base))
        evidence_level = "strong_indicator" if relevance >= 78 and not flags else ("weak_indicator" if relevance >= 55 else "candidate")
        suggested_status = "needs_review" if flags or source_type in {"court_or_justice", "image_media"} else ("candidate" if relevance < 80 else "included")
        export_caution = "redaction_required" if flags else "standard_review"
        return {"source_type": source_type, "finding_type": finding_type, "relevance_score": relevance, "evidence_level": evidence_level, "suggested_status": suggested_status, "sensitivity_flags": flags, "export_caution": export_caution}

    def import_capture_to_person_file(self, capture_result_id: str, *, analyst_note: str = "", auto_create_finding: bool = True) -> Dict[str, Any]:
        if not self.capture_pro:
            raise RuntimeError("capture_pro service not attached")
        cap = self.capture_pro.get_result(capture_result_id)
        analysis = self.analyze_capture_result(cap)
        person_finding_id = ""
        if auto_create_finding and self.person_detail:
            meta = {"build": "60.2", "capture_result_id": capture_result_id, "source_type": analysis["source_type"], "relevance_score": analysis["relevance_score"], "sensitivity_flags": analysis["sensitivity_flags"], "query": cap.get("query", ""), "engine": cap.get("engine", ""), "category_key": cap.get("category_key", "")}
            finding = self.person_detail.add_finding_note(
                cap["case_id"], cap["entity_id"],
                title=cap.get("title", "Fund"),
                summary=cap.get("snippet") or cap.get("url", ""),
                finding_type=analysis["finding_type"],
                source_url=cap.get("url", ""),
                category=cap.get("category_key", "") or analysis["source_type"],
                status=analysis["suggested_status"],
                analyst_note=analyst_note or f"Automatisch aus Capture importiert. Relevanzvorschlag: {analysis['relevance_score']}/100.",
                evidence_level=analysis["evidence_level"],
                redaction_required=bool(analysis["sensitivity_flags"]),
                metadata=meta,
            )
            person_finding_id = finding.get("finding_note_id", "")
        intelligence_id = self._upsert_intelligence(cap, analysis, person_finding_id)
        self.audit.log("create", "fund_intelligence_60_2", intelligence_id, cap["case_id"], {"entity_id": cap["entity_id"], "capture_result_id": capture_result_id, "finding": person_finding_id})
        row = self.get_intelligence(intelligence_id)
        row["capture"] = cap
        return row

    def bulk_import_captures(self, case_id: str, entity_id: str, *, limit: int = 50) -> Dict[str, Any]:
        if not self.capture_pro:
            raise RuntimeError("capture_pro service not attached")
        rows = self.capture_pro.list_results(case_id, entity_id, limit=limit)
        imported = [self.import_capture_to_person_file(r["capture_result_id"]) for r in rows]
        return {"case_id": case_id, "entity_id": entity_id, "count": len(imported), "items": imported}

    def list_intelligence(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM fund_intelligence_60_2 WHERE case_id=? AND entity_id=? ORDER BY relevance_score DESC, created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])
        for r in rows:
            r["sensitivity_flags"] = loads(r.pop("sensitivity_flags_json", "[]"), [])
            r["chain_origin"] = loads(r.pop("chain_origin_json", "{}"), {})
        return rows

    def get_intelligence(self, intelligence_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM fund_intelligence_60_2 WHERE intelligence_id=?", [intelligence_id])
        if not row:
            raise KeyError(intelligence_id)
        row["sensitivity_flags"] = loads(row.pop("sensitivity_flags_json", "[]"), [])
        row["chain_origin"] = loads(row.pop("chain_origin_json", "{}"), {})
        return row

    def _upsert_intelligence(self, cap: Dict[str, Any], analysis: Dict[str, Any], person_finding_id: str) -> str:
        existing = self.db.one("SELECT intelligence_id FROM fund_intelligence_60_2 WHERE case_id=? AND entity_id=? AND capture_result_id=?", [cap["case_id"], cap["entity_id"], cap["capture_result_id"]])
        origin = {"capture_result_id": cap["capture_result_id"], "batch_id": cap.get("batch_id", ""), "query": cap.get("query", ""), "engine": cap.get("engine", ""), "category_key": cap.get("category_key", "")}
        now = now_ts()
        if existing:
            iid = existing["intelligence_id"]
            self.db.execute('''UPDATE fund_intelligence_60_2 SET person_finding_id=?,source_type=?,finding_type=?,relevance_score=?,evidence_level=?,suggested_status=?,sensitivity_flags_json=?,export_caution=?,chain_origin_json=?,updated_at=? WHERE intelligence_id=?''', [person_finding_id, analysis["source_type"], analysis["finding_type"], analysis["relevance_score"], analysis["evidence_level"], analysis["suggested_status"], dumps(analysis["sensitivity_flags"]), analysis["export_caution"], dumps(origin), now, iid])
        else:
            iid = new_id("fi602")
            self.db.execute('''INSERT INTO fund_intelligence_60_2(intelligence_id,case_id,entity_id,capture_result_id,person_finding_id,source_type,finding_type,relevance_score,evidence_level,suggested_status,sensitivity_flags_json,export_caution,chain_origin_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [iid, cap["case_id"], cap["entity_id"], cap["capture_result_id"], person_finding_id, analysis["source_type"], analysis["finding_type"], analysis["relevance_score"], analysis["evidence_level"], analysis["suggested_status"], dumps(analysis["sensitivity_flags"]), analysis["export_caution"], dumps(origin), now, now])
        return iid
