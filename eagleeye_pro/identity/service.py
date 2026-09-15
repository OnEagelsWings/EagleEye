from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class IdentityResolutionService:
    """Candidate-based identity resolution. It never confirms identity automatically."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    @staticmethod
    def _contains(text: str, value: str) -> bool:
        return bool(value) and value.lower() in (text or "").lower()

    def generate_candidates(self, case_id: str) -> List[Dict[str, Any]]:
        targets = self.db.all("SELECT * FROM targets WHERE case_id=?", [case_id])
        review_items = self.db.all("SELECT * FROM review_items WHERE case_id=?", [case_id])
        evidence = self.db.all("SELECT * FROM evidence_items WHERE case_id=?", [case_id])
        created=[]
        for t in targets:
            aliases = loads(t.get("aliases_json"), []) or []
            emails = loads(t.get("emails_json"), []) or []
            usernames = loads(t.get("usernames_json"), []) or []
            locations = loads(t.get("locations_json"), []) or []
            companies = loads(t.get("companies_json"), []) or []
            domains = loads(t.get("domains_json"), []) or []
            markers=[]; negative=[]; ev_ids=[]; score=0.0
            haystacks=[]
            for r in review_items:
                haystacks.append(" ".join([r.get("title") or "", r.get("url") or "", r.get("snippet") or "", r.get("query") or ""]))
            for ev in evidence:
                haystacks.append(" ".join([ev.get("title") or "", ev.get("source_url") or "", ev.get("statement") or ""]))
            combined="\n".join(haystacks)
            if self._contains(combined, t.get("name", "")):
                markers.append("name_match"); score += 0.25
            for label, values, weight in [("alias_match", aliases, 0.12), ("email_match", emails, 0.18), ("username_match", usernames, 0.14), ("location_match", locations, 0.08), ("company_match", companies, 0.16), ("domain_match", domains, 0.12)]:
                hits=[v for v in values if self._contains(combined, v)]
                if hits:
                    markers.append(f"{label}:{', '.join(hits[:3])}"); score += weight
            name_tokens=(t.get("name") or "").split()
            if len(name_tokens) < 2:
                negative.append("weak_name_anchor")
            if not evidence:
                negative.append("no_promoted_evidence")
            else:
                ev_ids=[ev["evidence_id"] for ev in evidence[:10]]
            score=max(0.0, min(score, 0.95))
            label=f"Kandidat für {t.get('name')}"
            existing=self.db.one("SELECT * FROM identity_candidates WHERE case_id=? AND target_id=? AND label=?", [case_id, t["target_id"], label])
            if existing:
                self.db.execute("""UPDATE identity_candidates SET score=?, positive_markers_json=?, negative_markers_json=?, evidence_ids_json=?, updated_at=? WHERE candidate_id=?""",
                                [score, dumps(markers), dumps(negative), dumps(ev_ids), now_ts(), existing["candidate_id"]])
                cid=existing["candidate_id"]
            else:
                cid=new_id("ident")
                self.db.execute("""INSERT INTO identity_candidates(candidate_id,case_id,target_id,label,score,positive_markers_json,negative_markers_json,evidence_ids_json,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [cid,case_id,t["target_id"],label,score,dumps(markers),dumps(negative),dumps(ev_ids),"candidate",now_ts(),now_ts()])
            self.audit.log("generate", "identity_candidate", cid, case_id, {"score": score, "markers": markers, "negative": negative})
            created.append(self.get_candidate(cid))
        return created

    def get_candidate(self, candidate_id: str) -> Dict[str, Any]:
        row=self.db.one("SELECT * FROM identity_candidates WHERE candidate_id=?", [candidate_id])
        if not row:
            raise KeyError("Identity Candidate nicht gefunden.")
        for k in ["positive_markers_json", "negative_markers_json", "evidence_ids_json"]:
            row[k]=loads(row.get(k), [])
        return row

    def decide_candidate(self, candidate_id: str, status: str, analyst_decision: str) -> Dict[str, Any]:
        if status not in ("candidate", "accepted_as_probable", "rejected", "conflicting", "needs_more_evidence"):
            raise ValueError("Ungültiger Identity-Status.")
        row=self.get_candidate(candidate_id)
        self.db.execute("UPDATE identity_candidates SET status=?, analyst_decision=?, updated_at=? WHERE candidate_id=?", [status, analyst_decision, now_ts(), candidate_id])
        self.audit.log("decision", "identity_candidate", candidate_id, row["case_id"], {"status": status, "analyst_decision": analyst_decision})
        return self.get_candidate(candidate_id)

    def list_candidates(self, case_id: str) -> List[Dict[str, Any]]:
        rows=self.db.all("SELECT * FROM identity_candidates WHERE case_id=? ORDER BY score DESC", [case_id])
        for r in rows:
            for k in ["positive_markers_json", "negative_markers_json", "evidence_ids_json"]:
                r[k]=loads(r.get(k), [])
        return rows
