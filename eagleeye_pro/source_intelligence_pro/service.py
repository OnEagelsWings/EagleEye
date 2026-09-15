from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


SOURCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "official_register": {"weight": 95, "label": "amtliche Registerquelle", "review": True, "redaction": True},
    "court_decision": {"weight": 90, "label": "öffentliche Gerichts-/Justizquelle", "review": True, "redaction": True},
    "gazette_notice": {"weight": 88, "label": "Amtsblatt / Bekanntmachung", "review": True, "redaction": False},
    "company_finance": {"weight": 85, "label": "öffentliche Finanz-/Unternehmensquelle", "review": True, "redaction": True},
    "public_pdf": {"weight": 75, "label": "öffentliches PDF/Dokument", "review": True, "redaction": False},
    "newspaper_archive": {"weight": 70, "label": "Presse-/Zeitungsarchiv", "review": True, "redaction": False},
    "organization_site": {"weight": 68, "label": "Organisations-/Impressumsquelle", "review": True, "redaction": False},
    "image_media": {"weight": 55, "label": "Bild-/Medienfund", "review": True, "redaction": True},
    "social_public_profile": {"weight": 45, "label": "öffentliches Profil / Social", "review": True, "redaction": True},
    "generic_web": {"weight": 40, "label": "allgemeiner Webtreffer", "review": True, "redaction": False},
    "ocr_candidate": {"weight": 35, "label": "OCR-/Extraktionskandidat", "review": True, "redaction": True},
}

DOMAIN_HINTS = [
    ("justiz", "court_decision"), ("gerichte", "court_decision"), ("bundesanzeiger", "company_finance"),
    ("unternehmensregister", "official_register"), ("handelsregister", "official_register"),
    ("insolvenz", "company_finance"), ("deutsche-digitale-bibliothek", "newspaper_archive"),
    ("zeitungsportal", "newspaper_archive"), ("bund.de", "gazette_notice"), (".de", "generic_web"),
]

class SourceIntelligenceProService:
    """Build 56.2 – Source Intelligence Pro.

    Scores sources by type/domain/document markers and records a transparent
    source-quality explanation for each imported result or finding.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS source_quality_assessments_56_2 (
          assessment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          source_type TEXT NOT NULL,
          domain TEXT DEFAULT '',
          score INTEGER NOT NULL,
          label TEXT NOT NULL,
          review_required INTEGER DEFAULT 1,
          redaction_required INTEGER DEFAULT 0,
          reasons_json TEXT NOT NULL,
          assessed_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def classify_source(self, *, url: str = "", title: str = "", source_type: str = "", snippet: str = "") -> Dict[str, Any]:
        text = " ".join([title or "", source_type or "", snippet or "", url or ""]).lower()
        domain = urlparse(url).netloc.lower().replace("www.", "") if url else ""
        detected = source_type or "generic_web"
        reasons: List[str] = []
        for needle, stype in DOMAIN_HINTS:
            if needle in domain or needle in text:
                detected = stype
                reasons.append(f"Domain-/Textmarker: {needle}")
                break
        if "filetype:pdf" in text or url.lower().endswith(".pdf") or " pdf" in text:
            detected = "public_pdf" if detected == "generic_web" else detected
            reasons.append("PDF-/Dokumentmarker erkannt")
        if re.search(r"\b(urteil|beschluss|aktenzeichen|gericht|prozess)\b", text):
            detected = "court_decision" if detected in {"generic_web", "public_pdf"} else detected
            reasons.append("Gerichts-/Verfahrensmarker erkannt")
        if re.search(r"\b(jahresabschluss|bilanz|insolvenz|förderung|vergabe|zuwendung)\b", text):
            detected = "company_finance" if detected in {"generic_web", "public_pdf"} else detected
            reasons.append("Finanz-/Registermarker erkannt")
        profile = SOURCE_PROFILES.get(detected, SOURCE_PROFILES["generic_web"])
        if not reasons:
            reasons.append("Fallback: allgemeiner öffentlicher Webtreffer")
        return {"source_type": detected, "domain": domain, "score": int(profile["weight"]), "label": profile["label"], "review_required": bool(profile["review"]), "redaction_required": bool(profile["redaction"]), "reasons": reasons}

    def assess_object(self, case_id: str, object_type: str, object_id: str, *, entity_id: str = "", url: str = "", title: str = "", source_type: str = "", snippet: str = "") -> Dict[str, Any]:
        c = self.classify_source(url=url, title=title, source_type=source_type, snippet=snippet)
        aid = new_id("sq562")
        self.db.execute(
            "INSERT INTO source_quality_assessments_56_2(assessment_id,case_id,entity_id,object_type,object_id,source_type,domain,score,label,review_required,redaction_required,reasons_json,assessed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [aid, case_id, entity_id, object_type, object_id, c["source_type"], c["domain"], c["score"], c["label"], 1 if c["review_required"] else 0, 1 if c["redaction_required"] else 0, dumps(c["reasons"]), now_ts()],
        )
        self.audit.log("assess", "source_intelligence_pro_56_2", aid, case_id, {"object_type": object_type, "object_id": object_id, "score": c["score"]})
        return {"assessment_id": aid, **c, "case_id": case_id, "entity_id": entity_id, "object_type": object_type, "object_id": object_id}

    def assess_search_results(self, case_id: str, entity_id: str = "", limit: int = 200) -> Dict[str, Any]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM search_quality_results_55_5 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        assessments = []
        for r in rows:
            assessments.append(self.assess_object(case_id, "search_quality_result", r["result_id"], entity_id=r.get("entity_id", ""), url=r.get("url", ""), title=r.get("title", ""), source_type=r.get("source_type", ""), snippet=r.get("snippet", "")))
        return {"case_id": case_id, "entity_id": entity_id, "assessed": len(assessments), "assessments": assessments}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM source_quality_assessments_56_2 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY assessed_at DESC LIMIT 300"
        rows = self.db.all(sql, params)
        for r in rows:
            r["reasons"] = loads(r.pop("reasons_json", "[]"), [])
            r["review_required"] = bool(r.get("review_required")); r["redaction_required"] = bool(r.get("redaction_required"))
        by_type: Dict[str, int] = {}; avg = 0
        for r in rows:
            by_type[r["source_type"]] = by_type.get(r["source_type"], 0) + 1
            avg += int(r.get("score") or 0)
        return {"case_id": case_id, "entity_id": entity_id, "assessment_count": len(rows), "average_score": round(avg / len(rows), 1) if rows else 0, "by_type": by_type, "assessments": rows}
