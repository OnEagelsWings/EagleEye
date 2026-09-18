from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import hashlib, json
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

DEFAULT_CATEGORIES = [
    ("identity_anchor", "Identitätsanker", "Belegbarer Anker für Name/Alias/Profilkontext; nie automatische Identitätsbestätigung.", 0, 1, "medium"),
    ("professional_context", "Beruflicher Kontext", "Öffentlicher Berufs-, Publikations-, Firmen- oder Rollenhinweis.", 0, 1, "medium"),
    ("registry_business", "Register-/Firmenbezug", "Öffentliche Register-, Impressums-, Domain- oder Firmenverbindung.", 0, 1, "medium"),
    ("media_press", "Presse/Medien", "Öffentlicher Medien-, Presse-, Interview- oder Archivhinweis.", 0, 1, "medium"),
    ("counter_evidence", "Gegenbeleg/Ausschluss", "Hinweis, der eine Zuordnung relativiert, widerspricht oder ausschließt.", 1, 0, "low"),
    ("sensitive_indicator", "Sensibler Hinweis", "Potentiell sensible Information; Export nur nach Redaction/Legal Review.", 0, 1, "high"),
]

class EvidenceService:
    """Build 22.0 Evidence Vault Pro.

    Provides category seeding, reliability scoring, redaction review records,
    tamper checks and export package manifests. Evidence remains candidate-grade
    until reviewed; the vault records provenance and chain events.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.seed_categories()

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    def _chain_event(self, case_id: str, object_type: str, object_id: str, event_type: str, details: Dict[str, Any], actor: str = "local-analyst") -> None:
        self.db.execute("""INSERT INTO chain_events(chain_event_id,case_id,object_type,object_id,event_type,timestamp,actor,details_json)
        VALUES(?,?,?,?,?,?,?,?)""", [new_id("chain"), case_id, object_type, object_id, event_type, now_ts(), actor, dumps(details)])

    def seed_categories(self) -> None:
        for cid, name, desc, export_allowed, redact, risk in DEFAULT_CATEGORIES:
            self.db.execute("""INSERT OR IGNORE INTO evidence_categories(category_id,name,description,default_export_allowed,default_redaction_required,risk_level,notes)
            VALUES(?,?,?,?,?,?,?)""", [cid, name, desc, export_allowed, redact, risk, "Build 22.0 default category"])

    def list_categories(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM evidence_categories ORDER BY risk_level DESC, name")

    def _category_defaults(self, category: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_categories WHERE name=? OR category_id=?", [category, category])
        if not row:
            return {"name": category, "default_export_allowed": 0, "default_redaction_required": 1, "risk_level": "medium"}
        return row

    @staticmethod
    def _source_reliability(provider: str, url: str) -> tuple[str, float]:
        u=(url or "").lower(); p=(provider or "").lower()
        if any(x in u for x in ["bundesanzeiger", "handelsregister", ".gov", ".gouv", ".bund.de", ".europa.eu"]):
            return "official_or_register", 0.90
        if any(x in u for x in ["linkedin", "xing", "github", "researchgate", "orcid"]):
            return "public_profile", 0.65
        if any(x in u for x in ["archive.org", "webcache", "wayback"]):
            return "archive", 0.60
        if "search_workbench" in p:
            return "manual_public_capture", 0.55
        if u:
            return "public_web", 0.50
        return "unknown", 0.25

    def promote_review_item(self, item_id: str, category: str="Identitätsanker", confidence: str="candidate", export_allowed: bool|None=False, notes: str="") -> Dict[str, Any]:
        item = self.db.one("SELECT * FROM review_items WHERE item_id=?", [item_id])
        if not item:
            raise KeyError("Review-Item nicht gefunden.")
        statement = item.get("snippet") or item.get("title") or "OSINT-Hinweis ohne Snippet"
        evidence_id = new_id("ev")
        captured = now_ts()
        cat = self._category_defaults(category)
        source_rel, rel_score = self._source_reliability(item.get("provider") or "", item.get("url") or "")
        item_quality = float(item.get("quality_score") or 0)
        reliability = round(min(1.0, rel_score * 0.55 + item_quality * 0.45), 3)
        export_value = int(cat.get("default_export_allowed") if export_allowed is None else bool(export_allowed))
        redaction_required = int(cat.get("default_redaction_required", 1))
        if item.get("sensitivity_level") == "high":
            redaction_required = 1
            export_value = 0
        metadata = {"case_id": item["case_id"], "review_item_id": item_id, "source_url": item.get("url"), "captured_at": captured, "category": cat.get("name", category), "reliability_score": reliability}
        content_hash = self.sha256_text("|".join([item.get("title") or "", item.get("url") or "", statement]))
        metadata_hash = self.sha256_text(json.dumps(metadata, sort_keys=True, ensure_ascii=False))
        self.db.execute("""INSERT INTO evidence_items(evidence_id,case_id,review_item_id,category,title,source_url,statement,confidence,content_hash,metadata_hash,captured_at,captured_by,custody_status,export_allowed,redaction_required,evidence_rank,reliability_score,source_reliability,review_decision,redaction_profile,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            evidence_id,item["case_id"],item_id,cat.get("name", category),item.get("title") or "Evidence",item.get("url"),statement,confidence,content_hash,metadata_hash,captured,"local-analyst","captured",export_value,redaction_required,"candidate",reliability,source_rel,"pending","client_safe",notes
        ])
        self.db.execute("UPDATE review_items SET status=?, updated_at=? WHERE item_id=?", ["promoted_to_evidence", now_ts(), item_id])
        self._chain_event(item["case_id"], "evidence_item", evidence_id, "promoted_from_review", {"from_review_item": item_id, "confidence": confidence, "category": cat.get("name", category), "reliability_score": reliability})
        self.audit.log("promote", "evidence_item", evidence_id, item["case_id"], {"from_review_item": item_id, "confidence": confidence, "reliability_score": reliability})
        return self.get_evidence(evidence_id)

    def get_evidence(self, evidence_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_items WHERE evidence_id=?", [evidence_id])
        if not row:
            raise KeyError("Evidence nicht gefunden.")
        return row

    def list_evidence(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at DESC", [case_id])

    def decide_evidence(self, evidence_id: str, decision: str, export_allowed: bool|None=None, redaction_required: bool|None=None, notes: str="") -> Dict[str, Any]:
        if decision not in {"accepted", "candidate", "rejected", "needs_redaction", "export_blocked", "internal_only"}:
            raise ValueError("Unbekannte Evidence-Entscheidung.")
        ev=self.get_evidence(evidence_id)
        updates=[]; params=[]
        updates.append("review_decision=?"); params.append(decision)
        if export_allowed is not None:
            updates.append("export_allowed=?"); params.append(int(bool(export_allowed)))
        if redaction_required is not None:
            updates.append("redaction_required=?"); params.append(int(bool(redaction_required)))
        if notes:
            updates.append("notes=?"); params.append(notes)
        updates.append("custody_status=?"); params.append("reviewed")
        params.append(evidence_id)
        self.db.execute(f"UPDATE evidence_items SET {', '.join(updates)} WHERE evidence_id=?", params)
        self._chain_event(ev["case_id"], "evidence_item", evidence_id, "evidence_decision", {"decision": decision, "export_allowed": export_allowed, "redaction_required": redaction_required, "notes": notes})
        self.audit.log("decide", "evidence_item", evidence_id, ev["case_id"], {"decision": decision})
        return self.get_evidence(evidence_id)

    def create_redaction_review(self, evidence_id: str, profile: str="client_safe", decision: str="redacted", reviewer: str="local-analyst", notes: str="") -> Dict[str, Any]:
        ev=self.get_evidence(evidence_id)
        # Local redaction implementation; mirrors RedactionService without import cycle.
        import re
        text=ev.get("statement") or ""
        summary={
            "emails": len(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)),
            "phones": len(re.findall(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)", text)),
            "ips": len(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)),
        }
        redacted=re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[E-MAIL REDACTED]", text)
        redacted=re.sub(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)", "[PHONE REDACTED]", redacted)
        if profile in ("client_safe", "public"):
            redacted=re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP REDACTED]", redacted)
        rid=new_id("redact")
        self.db.execute("""INSERT INTO redaction_reviews(redaction_id,case_id,evidence_id,profile,decision,summary_json,redacted_statement,reviewer,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [rid, ev["case_id"], evidence_id, profile, decision, dumps(summary), redacted, reviewer, now_ts(), notes])
        if decision in {"redacted", "cleared"}:
            self.db.execute("UPDATE evidence_items SET redaction_required=0, redaction_profile=?, custody_status=? WHERE evidence_id=?", [profile, "redaction_reviewed", evidence_id])
        self._chain_event(ev["case_id"], "evidence_item", evidence_id, "redaction_review", {"redaction_id": rid, "profile": profile, "decision": decision, "summary": summary})
        self.audit.log("redaction_review", "evidence_item", evidence_id, ev["case_id"], {"redaction_id": rid, "decision": decision})
        return self.db.one("SELECT * FROM redaction_reviews WHERE redaction_id=?", [rid])

    def list_redaction_reviews(self, case_id: str) -> List[Dict[str, Any]]:
        rows=self.db.all("SELECT * FROM redaction_reviews WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["summary_json"]=loads(r.get("summary_json"), {})
        return rows

    def chain_of_custody(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM chain_events WHERE case_id=? ORDER BY timestamp ASC", [case_id])

    def verify_manifest(self, case_id: str) -> Dict[str, Any]:
        items = self.list_evidence(case_id)
        issues=[]
        for ev in items:
            for key in ["evidence_id","case_id","title","statement","content_hash","metadata_hash","captured_at"]:
                if not ev.get(key):
                    issues.append({"evidence_id": ev.get("evidence_id"), "missing": key})
            recomputed_content=self.sha256_text("|".join([ev.get("title") or "", ev.get("source_url") or "", ev.get("statement") or ""]))
            if ev.get("content_hash") and recomputed_content != ev.get("content_hash"):
                issues.append({"evidence_id": ev.get("evidence_id"), "issue": "content_hash_mismatch"})
            if ev.get("redaction_required") and ev.get("export_allowed"):
                issues.append({"evidence_id": ev.get("evidence_id"), "issue": "export_allowed_while_redaction_required"})
        return {"ok": not issues, "gate": "EVIDENCE_MANIFEST_PASS" if not issues else "EVIDENCE_MANIFEST_REVIEW", "items": len(items), "issues": issues}

    def evidence_dashboard(self, case_id: str) -> Dict[str, Any]:
        counts=self.db.all("SELECT review_decision, COUNT(*) AS n FROM evidence_items WHERE case_id=? GROUP BY review_decision", [case_id])
        cats=self.db.all("SELECT category, COUNT(*) AS n FROM evidence_items WHERE case_id=? GROUP BY category", [case_id])
        blocks=self.db.one("SELECT SUM(CASE WHEN redaction_required=1 THEN 1 ELSE 0 END) AS redact, SUM(CASE WHEN export_allowed=1 THEN 1 ELSE 0 END) AS exportable, AVG(reliability_score) AS avg_rel FROM evidence_items WHERE case_id=?", [case_id]) or {}
        return {
            "decision_counts": {r["review_decision"]: r["n"] for r in counts},
            "category_counts": {r["category"]: r["n"] for r in cats},
            "redaction_required": int(blocks.get("redact") or 0),
            "exportable": int(blocks.get("exportable") or 0),
            "avg_reliability": round(float(blocks.get("avg_rel") or 0), 3),
        }

    def create_package_manifest(self, case_id: str, outdir: str|Path|None=None, notes: str="") -> Dict[str, Any]:
        items=self.list_evidence(case_id)
        exportable=[i for i in items if i.get("export_allowed") and not i.get("redaction_required")]
        redaction_blocked=[i for i in items if i.get("redaction_required")]
        payload={
            "case_id": case_id,
            "created_at": now_ts(),
            "item_count": len(items),
            "exportable_count": len(exportable),
            "redaction_blocked_count": len(redaction_blocked),
            "items": [{k:i.get(k) for k in ["evidence_id","category","title","source_url","content_hash","metadata_hash","captured_at","review_decision","export_allowed","redaction_required","reliability_score"]} for i in items],
        }
        raw=json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        mh=self.sha256_text(raw)
        mid=new_id("manifest")
        storage_path=""
        if outdir:
            out=Path(outdir); out.mkdir(parents=True, exist_ok=True)
            path=out / f"evidence_package_manifest_{case_id}_{mid}.json"
            path.write_text(raw, encoding="utf-8")
            storage_path=str(path)
        self.db.execute("""INSERT INTO evidence_package_manifests(manifest_id,case_id,manifest_hash,item_count,exportable_count,redaction_blocked_count,created_at,storage_path,notes)
        VALUES(?,?,?,?,?,?,?,?,?)""", [mid, case_id, mh, len(items), len(exportable), len(redaction_blocked), payload["created_at"], storage_path, notes])
        self._chain_event(case_id, "evidence_package_manifest", mid, "manifest_created", {"manifest_hash": mh, "items": len(items), "exportable": len(exportable), "redaction_blocked": len(redaction_blocked)})
        return {"manifest_id": mid, "manifest_hash": mh, "item_count": len(items), "exportable_count": len(exportable), "redaction_blocked_count": len(redaction_blocked), "storage_path": storage_path}
