from __future__ import annotations
from typing import Any, Dict, List
import hashlib, re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate

ALLOWED_STATUS = [
    "new", "in_review", "accepted_as_lead", "promoted_to_evidence", "rejected",
    "conflicting", "sensitive", "export_blocked", "duplicate", "needs_source_review",
    "needs_redaction", "ready_for_evidence"
]

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid"}

class ReviewService:
    """Build 22.0 Review Inbox Pro.

    The service treats every hit as a review candidate, never as a confirmed identity.
    It adds deterministic fingerprints, quality checks, duplicate clustering and
    conservative triage so analysts can work faster without weakening evidentiary standards.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def normalize_url(url: str) -> str:
        if not url:
            return ""
        try:
            p = urlparse(url.strip())
            scheme = (p.scheme or "https").lower()
            netloc = p.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            query_pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
            query = urlencode(query_pairs, doseq=True)
            path = p.path.rstrip("/") or "/"
            return urlunparse((scheme, netloc, path, "", query, ""))
        except Exception:
            return url.strip().lower()

    @classmethod
    def fingerprint(cls, title: str, url: str, snippet: str) -> str:
        normalized = cls.normalize_url(url)
        if normalized:
            return cls.sha256_text("url|" + normalized)
        text = re.sub(r"\s+", " ", " ".join([title or "", snippet or ""]).lower()).strip()[:500]
        return cls.sha256_text("text|" + text)

    @staticmethod
    def extract_markers(text: str) -> List[str]:
        markers=[]; t=text or ""
        if re.search(r"https?://", t): markers.append("url")
        if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", t): markers.append("email_like")
        if re.search(r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\b", t): markers.append("person_name_like")
        for kw in ["linkedin", "xing", "github", "pdf", "presse", "register", "impressum", "archive", "wayback", "firma", "domain", "profil"]:
            if kw in t.lower(): markers.append(kw)
        return sorted(set(markers))

    def quality_check(self, title: str, url: str, snippet: str, score: float = 0.0) -> Dict[str, Any]:
        issues: List[str] = []
        q = 0.0
        if title and len(title.strip()) >= 4:
            q += 0.15
        else:
            issues.append("Titel fehlt oder ist zu kurz.")
        normalized = self.normalize_url(url)
        if normalized.startswith("http") and "." in urlparse(normalized).netloc:
            q += 0.25
        else:
            issues.append("URL fehlt oder ist nicht plausibel.")
        if snippet and len(snippet.strip()) >= 20:
            q += 0.20
        else:
            issues.append("Snippet/Zusammenfassung ist zu dünn.")
        markers = self.extract_markers(" ".join([title or "", url or "", snippet or ""]))
        q += min(0.20, len(markers) * 0.04)
        q += min(0.20, max(0.0, min(1.0, float(score or 0))) * 0.20)
        if any(k in (url or "").lower() for k in ["example.org", "example.com"]):
            # Demo/test URLs remain valid but lower evidentiary quality.
            issues.append("Demo-/Beispiel-URL: nur für Test- oder Platzhalterzwecke geeignet.")
        return {"quality_score": round(min(1.0, q), 3), "issues": issues, "markers": markers, "normalized_url": normalized}

    def add_manual_hit(self, case_id: str, title: str, url: str, snippet: str, source_type: str="web", provider: str="manual", query: str="", score: float=0.5, notes: str="") -> Dict[str, Any]:
        text = " ".join([title or "", url or "", snippet or "", query or ""])
        policy = PolicyGate.evaluate_query(text)
        if not policy.get("ok"):
            raise ValueError("Review-Import blockiert: Guardrails erlauben keine Privatquellen-/Bypass-/Doxxing-Workflows.")
        sens = PolicyGate.classify_sensitivity(text)
        qc = self.quality_check(title, url, snippet, score)
        item_id = new_id("rev")
        ts = now_ts()
        fp = self.fingerprint(title, url, snippet)
        self.db.execute("""INSERT INTO review_items(item_id,case_id,source_type,provider,title,url,snippet,query,score,status,sensitivity_level,markers_json,normalized_url,fingerprint,duplicate_cluster_id,quality_score,triage_reason,reviewer,notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            item_id,case_id,source_type,provider,title,url,snippet,query,float(score),"new",sens["level"],
            dumps(sorted(set(qc["markers"]+sens["markers"]))),qc["normalized_url"],fp,"",qc["quality_score"],"; ".join(qc["issues"]),"local-analyst",notes,ts,ts
        ])
        self.db.execute("""INSERT INTO review_quality_checks(check_id,case_id,item_id,quality_score,issues_json,created_at)
        VALUES(?,?,?,?,?,?)""", [new_id("rqc"), case_id, item_id, qc["quality_score"], dumps(qc["issues"]), ts])
        self.audit.log("create", "review_item", item_id, case_id, {"title": title, "sensitivity": sens, "quality": qc})
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM review_items WHERE item_id=?", [item_id])
        if not row:
            raise KeyError(f"Review-Item nicht gefunden: {item_id}")
        row["markers_json"] = loads(row.get("markers_json"), [])
        return row

    def update_status(self, item_id: str, status: str, notes: str="") -> Dict[str, Any]:
        if status not in ALLOWED_STATUS:
            raise ValueError("Unbekannter Review-Status.")
        item = self.get_item(item_id)
        new_notes = notes or item.get("notes") or ""
        self.db.execute("UPDATE review_items SET status=?, notes=?, updated_at=? WHERE item_id=?", [status, new_notes, now_ts(), item_id])
        self.audit.log("status_update", "review_item", item_id, item["case_id"], {"status": status})
        return self.get_item(item_id)

    def list_items(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM review_items WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["markers_json"] = loads(r.get("markers_json"), [])
        return rows

    def find_duplicates(self, case_id: str, min_cluster_size: int = 2) -> Dict[str, Any]:
        rows = self.db.all("SELECT * FROM review_items WHERE case_id=? AND fingerprint<>'' ORDER BY created_at", [case_id])
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(r.get("fingerprint") or "", []).append(r)
        clusters=[]
        ts=now_ts()
        for fp, items in groups.items():
            if len(items) < min_cluster_size:
                continue
            ids=[i["item_id"] for i in items]
            existing=self.db.one("SELECT * FROM duplicate_clusters WHERE case_id=? AND fingerprint=?", [case_id, fp])
            representative=max(items, key=lambda x: float(x.get("quality_score") or 0))
            if existing:
                cid=existing["cluster_id"]
                self.db.execute("UPDATE duplicate_clusters SET item_ids_json=?, representative_item_id=?, updated_at=? WHERE cluster_id=?", [dumps(ids), representative["item_id"], ts, cid])
            else:
                cid=new_id("dup")
                self.db.execute("""INSERT INTO duplicate_clusters(cluster_id,case_id,fingerprint,normalized_url,item_ids_json,status,representative_item_id,created_at,updated_at,analyst_decision)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [cid, case_id, fp, representative.get("normalized_url") or "", dumps(ids), "candidate_duplicate", representative["item_id"], ts, ts, ""])
            for i in items:
                if i["item_id"] != representative["item_id"] and i.get("status") not in ("promoted_to_evidence", "rejected"):
                    self.db.execute("UPDATE review_items SET duplicate_cluster_id=?, status=?, updated_at=? WHERE item_id=?", [cid, "duplicate", ts, i["item_id"]])
                else:
                    self.db.execute("UPDATE review_items SET duplicate_cluster_id=?, updated_at=? WHERE item_id=?", [cid, ts, i["item_id"]])
            clusters.append({"cluster_id": cid, "fingerprint": fp, "items": len(items), "representative_item_id": representative["item_id"]})
        self.audit.log("analyze", "duplicate_clusters", case_id, case_id, {"clusters": clusters})
        return {"clusters": clusters, "cluster_count": len(clusters)}

    def triage_item(self, item_id: str) -> Dict[str, Any]:
        item = self.get_item(item_id)
        score = float(item.get("score") or 0)
        quality = float(item.get("quality_score") or 0)
        sens = item.get("sensitivity_level") or "normal"
        if sens == "high":
            status = "sensitive"; reason = "Hohe Sensibilität: Senior-/Legal-Review vor Evidence/Export erforderlich."
        elif item.get("duplicate_cluster_id") and item.get("status") == "duplicate":
            status = "duplicate"; reason = "Duplikatcluster erkannt; repräsentativen Treffer prüfen."
        elif quality < 0.35:
            status = "needs_source_review"; reason = "Quellenqualität zu niedrig; weitere Prüfung oder Nachcapture nötig."
        elif score >= 0.75 and quality >= 0.55:
            status = "ready_for_evidence"; reason = "Gute Treffer- und Quellenqualität; kann als Evidence Candidate geprüft werden."
        elif score < 0.30:
            status = "rejected"; reason = "Niedriger Score; eher Namensdoppler/irrelevanter Treffer."
        else:
            status = "in_review"; reason = "Manuelle Analystenprüfung erforderlich."
        self.db.execute("UPDATE review_items SET status=?, triage_reason=?, updated_at=? WHERE item_id=?", [status, reason, now_ts(), item_id])
        self.audit.log("triage", "review_item", item_id, item["case_id"], {"status": status, "reason": reason, "quality": quality, "score": score})
        return self.get_item(item_id)

    def bulk_triage(self, case_id: str) -> Dict[str, Any]:
        self.find_duplicates(case_id)
        items=self.list_items(case_id)
        summary: Dict[str, int] = {}
        for i in items:
            updated=self.triage_item(i["item_id"])
            summary[updated["status"]]=summary.get(updated["status"],0)+1
        return {"case_id": case_id, "triaged": len(items), "summary": summary}

    def review_dashboard(self, case_id: str) -> Dict[str, Any]:
        rows=self.db.all("SELECT status, COUNT(*) AS n FROM review_items WHERE case_id=? GROUP BY status", [case_id])
        sens=self.db.all("SELECT sensitivity_level, COUNT(*) AS n FROM review_items WHERE case_id=? GROUP BY sensitivity_level", [case_id])
        quality=self.db.one("SELECT AVG(quality_score) AS avg_quality, COUNT(*) AS n FROM review_items WHERE case_id=?", [case_id]) or {}
        dup=self.db.one("SELECT COUNT(*) AS n FROM duplicate_clusters WHERE case_id=?", [case_id]) or {"n":0}
        return {
            "status_counts": {r["status"]: r["n"] for r in rows},
            "sensitivity_counts": {r["sensitivity_level"]: r["n"] for r in sens},
            "avg_quality": round(float(quality.get("avg_quality") or 0), 3),
            "review_items": int(quality.get("n") or 0),
            "duplicate_clusters": int(dup.get("n") or 0),
        }
