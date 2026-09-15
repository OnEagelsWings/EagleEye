from __future__ import annotations

from typing import Any, Dict, List
import hashlib
import json
import re

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

_EMAIL_RE = re.compile(r"(?i)([A-Z0-9._%+-]{1,64})@([A-Z0-9.-]+\.[A-Z]{2,})")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()./-]{6,}\d)(?!\d)")


def _redact(text: str) -> str:
    text = text or ""
    text = _EMAIL_RE.sub(lambda m: m.group(1)[:2] + "***@" + m.group(2), text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text


def _hash_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class SpearheadProfileService:
    """Build 50 operational profile engine.

    Profiles are handover-oriented and distinguish facts, indicators, uncertainties,
    counter-evidence and blocked claims. They do not generate verdicts.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS spearhead_profiles_50 (
          profile_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          profile_type TEXT NOT NULL,
          status TEXT DEFAULT 'redacted',
          profile_json TEXT NOT NULL,
          markdown TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-analyst',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sprofile50_case ON spearhead_profiles_50(case_id, created_at);
        ''')
        self.db.conn.commit()

    def build(self, case_id: str, profile_type: str = "authority_handover") -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        targets = self._targets(case_id)
        claims = self._claims(case_id)
        search_plans = self._table_count("search_plans_46", case_id)
        search_params = self._table_count("search_parameters_46", case_id)
        extracts = self._rows("public_document_extracts_46", case_id)
        reviews = self._rows("review_inbox_pro_46", case_id)
        artifacts = self._rows("evidence_vault_artifacts_50", case_id)
        verification = self._latest_verification(case_id)
        missing = self._latest_missing(case_id)
        antisemitism = self._antisemitism(case_id)
        case_map = self._case_map(case_id)

        facts: List[Dict[str, Any]] = []
        indicators: List[Dict[str, Any]] = []
        uncertainties: List[str] = []
        counter_evidence: List[Dict[str, Any]] = []
        blocked_claims: List[str] = []

        for c in claims:
            entry = {"claim_type": c.get("claim_type"), "statement": _redact(c.get("statement", "")), "assessment": c.get("assessment_label", ""), "reportability": c.get("reportability", ""), "supporting_evidence": loads(c.get("supporting_evidence_json"), []), "contra_evidence": loads(c.get("contra_evidence_json"), [])}
            if c.get("claim_type") == "claim_counter_evidence":
                counter_evidence.append(entry)
            elif c.get("reportability") == "reportable_as_verified_claim":
                facts.append(entry)
            else:
                indicators.append(entry)
            if c.get("uncertainty_note"):
                uncertainties.append(c.get("uncertainty_note"))

        for r in reviews:
            if r.get("stage") == "counter_evidence":
                counter_evidence.append({"title": _redact(r.get("title", "")), "source_url": r.get("source_url", ""), "reason": r.get("decision_reason", "")})
            elif r.get("stage") in {"relevant_candidate", "needs_second_source", "evidence_item"}:
                indicators.append({"title": _redact(r.get("title", "")), "stage": r.get("stage"), "source_url": r.get("source_url", ""), "reportability": r.get("reportability", "internal_only")})

        if verification:
            uncertainties.extend(verification.get("uncertainty", []))
            blocked_claims.extend(verification.get("blocked_claims", []))

        profile = {
            "build": "50.0",
            "profile_type": profile_type,
            "case": {k: case.get(k, "") for k in ["case_id", "title", "purpose", "legal_basis", "jurisdiction", "risk_level", "status"]},
            "targets": targets,
            "metrics": {
                "targets": len(targets),
                "search_plans": search_plans,
                "planned_search_parameters": search_params,
                "public_document_extracts": len(extracts),
                "review_items": len(reviews),
                "vault_artifacts": len(artifacts),
                "timeline_events": case_map.get("metrics", {}).get("timeline_events", 0),
                "links": case_map.get("metrics", {}).get("links", 0),
                "antisemitism_incidents": len(antisemitism),
                "missing_child_records": 1 if missing else 0,
            },
            "facts": facts,
            "public_indicators": indicators,
            "counter_evidence": counter_evidence,
            "uncertainties": sorted(set(u for u in uncertainties if u)),
            "blocked_claims": sorted(set(blocked_claims)),
            "evidence_vault": [{"artifact_id": a.get("artifact_id"), "title": _redact(a.get("title", "")), "sha256": a.get("sha256"), "review_status": a.get("review_status"), "source_url": a.get("source_url", "")} for a in artifacts],
            "verification": verification or {},
            "missing_child_brief": missing or {},
            "antisemitism_incidents": antisemitism,
            "timeline": case_map.get("timeline_events", []),
            "links": case_map.get("links", []),
            "handover_guardrails": [
                "Fakten, Hinweise und Unsicherheiten getrennt halten.",
                "Keine private Adresse, Privatnummer, Live-Location oder biometrische Identifikation exportieren.",
                "Behörden/RIAS/Kinderschutzstellen erhalten redigierte Übergabefassung mit Quellen- und Hash-Anhang.",
            ],
            "created_at": now_ts(),
        }
        markdown = self._markdown(profile)
        content_hash = _hash_obj(profile)
        profile_id = new_id("sprof50")
        self.db.execute('''INSERT INTO spearhead_profiles_50(profile_id,case_id,profile_type,status,profile_json,markdown,content_hash,created_at,created_by)
        VALUES(?,?,?,?,?,?,?,?,?)''', [profile_id, case_id, profile_type, "redacted", dumps(profile), markdown, content_hash, now_ts(), "local-analyst"])
        self.audit.log("build", "spearhead_profile_50", profile_id, case_id, {"profile_type": profile_type, "content_hash": content_hash})
        return {"profile_id": profile_id, "profile": profile, "markdown": markdown, "content_hash": content_hash}

    def get(self, profile_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM spearhead_profiles_50 WHERE profile_id=?", [profile_id])
        if not row:
            raise KeyError(profile_id)
        row["profile"] = loads(row.pop("profile_json", "{}"), {})
        return row

    def _markdown(self, p: Dict[str, Any]) -> str:
        lines = [f"# EagleEye Build 50 Behörden-/Hinweisprofil", "", f"**Fall:** {_redact(p['case'].get('title',''))}", f"**Profiltyp:** {p['profile_type']}", f"**Hash:** `{_hash_obj(p)}`", "", "## Metriken"]
        for k, v in p["metrics"].items():
            lines.append(f"- {k}: {v}")
        lines += ["", "## Gesicherte öffentliche Fakten"]
        lines += [f"- {x.get('statement') or x.get('title')}" for x in p["facts"]] or ["- Keine als gesichert reportfähigen Fakten im Profilstand."]
        lines += ["", "## Öffentliche Hinweise / Kandidaten"]
        lines += [f"- {x.get('statement') or x.get('title')} ({x.get('reportability','internal_only')})" for x in p["public_indicators"][:50]] or ["- Keine Hinweise erfasst."]
        lines += ["", "## Gegenbelege"]
        lines += [f"- {x.get('statement') or x.get('title')}" for x in p["counter_evidence"]] or ["- Keine Gegenbelege dokumentiert."]
        lines += ["", "## Unsicherheiten / Pflichtprüfungen"]
        lines += [f"- {u}" for u in p["uncertainties"]] or ["- Keine zusätzlichen Unsicherheiten dokumentiert."]
        lines += ["", "## Übergabe-Leitplanken"]
        lines += [f"- {g}" for g in p["handover_guardrails"]]
        return "\n".join(lines) + "\n"

    def _targets(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM targets WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("targets") else []
        out = []
        for r in rows:
            out.append({"target_id": r.get("target_id"), "name": _redact(r.get("name", "")), "aliases": loads(r.get("aliases_json"), []), "locations": loads(r.get("locations_json"), []), "companies": loads(r.get("companies_json"), []), "domains": loads(r.get("domains_json"), [])})
        return out

    def _claims(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM verified_claims WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("verified_claims") else []

    def _rows(self, table: str, case_id: str) -> List[Dict[str, Any]]:
        if not self._table_exists(table):
            return []
        order_column = "retrieved_at" if table == "public_document_extracts_46" else "created_at"
        return self.db.all(f"SELECT * FROM {table} WHERE case_id=? ORDER BY {order_column}", [case_id])

    def _table_count(self, table: str, case_id: str) -> int:
        if not self._table_exists(table):
            return 0
        row = self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE case_id=?", [case_id])
        return int(row["n"] if row else 0)

    def _latest_verification(self, case_id: str) -> Dict[str, Any] | None:
        if not self._table_exists("verification_pro_assessments_50"):
            return None
        row = self.db.one("SELECT * FROM verification_pro_assessments_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return None
        for key in ["dimensions_json", "support_summary_json", "counter_evidence_json", "uncertainty_json", "blocked_claims_json", "required_actions_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "{}"), [])
        return row

    def _latest_missing(self, case_id: str) -> Dict[str, Any] | None:
        if not self._table_exists("missing_child_cases_50"):
            return None
        row = self.db.one("SELECT * FROM missing_child_cases_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return None
        for key in ["official_refs_json", "public_notice_urls_json", "open_questions_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [])
        return row

    def _antisemitism(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self._rows("antisemitism_incidents_50", case_id)
        out = []
        for row in rows:
            for key in ["public_urls_json", "evidence_artifacts_json", "markers_json", "recommended_handover_json"]:
                row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [])
            out.append(row)
        return out

    def _case_map(self, case_id: str) -> Dict[str, Any]:
        if not self._table_exists("timeline_events_50"):
            return {"timeline_events": [], "links": [], "metrics": {"timeline_events": 0, "links": 0}}
        timeline = self.db.all("SELECT * FROM timeline_events_50 WHERE case_id=? ORDER BY event_time, created_at", [case_id])
        links = self.db.all("SELECT * FROM link_edges_50 WHERE case_id=? ORDER BY relationship_type, created_at", [case_id]) if self._table_exists("link_edges_50") else []
        for link in links:
            link["counter_evidence"] = loads(link.pop("counter_evidence_json", "[]"), [])
        return {"timeline_events": timeline, "links": links, "metrics": {"timeline_events": len(timeline), "links": len(links)}}

    def _table_exists(self, table: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table]))
