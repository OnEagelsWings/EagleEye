from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import re

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import ALLOWED_CLAIM_TYPES, FORBIDDEN_CLAIM_TYPES, classify_sensitivity, normalize_reportability, validate_claim_type

_EMAIL_RE = re.compile(r"(?i)([A-Z0-9._%+-]{1,64})@([A-Z0-9.-]+\.[A-Z]{2,})")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()./-]{6,}\d)(?!\d)")

def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

def _redact(text: str) -> str:
    text = text or ""
    text = _EMAIL_RE.sub(lambda m: (m.group(1)[:2] + "***@" + m.group(2)), text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text

class ForensicProfileEngine:
    """Build 50.0 redacted profile and source-intelligence profile engine.

    Produces a precise profile from already reviewed evidence/claims. It never confirms identity,
    guilt, dangerousness, private address, biometrics or live location.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS verified_claims (
          claim_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, claim_type TEXT NOT NULL,
          statement TEXT NOT NULL, assessment_label TEXT NOT NULL, reportability TEXT NOT NULL,
          supporting_evidence_json TEXT NOT NULL, contra_evidence_json TEXT NOT NULL,
          uncertainty_note TEXT DEFAULT '', redaction_required INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS export_profiles (
          profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, profile_type TEXT NOT NULL,
          status TEXT NOT NULL, profile_json TEXT NOT NULL, profile_markdown TEXT NOT NULL,
          content_hash TEXT NOT NULL, redaction_manifest_json TEXT NOT NULL,
          audit_digest_hash TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_verified_claims_case ON verified_claims(case_id, claim_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_export_profiles_case ON export_profiles(case_id, created_at);
        ''')
        self.db.conn.commit()

    def create_claim(self, case_id: str, claim_type: str, statement: str, *, supporting_evidence: List[str] | None = None, contra_evidence: List[str] | None = None, assessment_label: str = "plausibler öffentlicher Hinweis – menschliche Prüfung bleibt Pflicht", reportability: str = "reportable_with_uncertainty", uncertainty_note: str = "", notes: str = "") -> Dict[str, Any]:
        decision = validate_claim_type(claim_type)
        if decision.decision == "block":
            raise ValueError(decision.message)
        if not statement.strip():
            raise ValueError("Statement darf nicht leer sein.")
        sensitivity = classify_sensitivity(statement + " " + uncertainty_note)
        claim_id = new_id("claim")
        self.db.execute('''INSERT INTO verified_claims(claim_id,case_id,claim_type,statement,assessment_label,reportability,supporting_evidence_json,contra_evidence_json,uncertainty_note,redaction_required,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', [claim_id, case_id, claim_type, statement.strip(), assessment_label.strip(), normalize_reportability(reportability, has_uncertainty=bool(uncertainty_note)), dumps(supporting_evidence or []), dumps(contra_evidence or []), uncertainty_note.strip(), int(sensitivity["redaction_required"] or reportability != "internal_only"), now_ts(), notes])
        self.audit.log("create", "verified_claim", claim_id, case_id, {"claim_type": claim_type, "reportability": reportability, "sensitivity": sensitivity})
        return self.get_claim(claim_id)

    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM verified_claims WHERE claim_id=?", [claim_id])
        if not row:
            raise KeyError(claim_id)
        row["supporting_evidence"] = loads(row.get("supporting_evidence_json"), [])
        row["contra_evidence"] = loads(row.get("contra_evidence_json"), [])
        return row

    def _approved_evidence_claims(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("""SELECT evidence_id, category, title, source_url, statement, confidence, content_hash, source_reliability, review_decision, redaction_required, export_allowed, captured_at
                            FROM evidence_items WHERE case_id=? AND review_decision IN ('accepted','approved','pending') ORDER BY captured_at DESC""", [case_id])
        claims: List[Dict[str, Any]] = []
        for ev in rows:
            claim_type = "claim_public_profile_possible_match"
            category = (ev.get("category") or "").lower()
            if "firma" in category or "company" in category or "business" in category:
                claim_type = "claim_public_company_relation"
            if "timeline" in category or "event" in category:
                claim_type = "claim_public_timeline_event"
            sens = classify_sensitivity(" ".join(str(ev.get(k) or "") for k in ("title", "statement", "source_url")))
            claims.append({
                "claim_id": f"derived:{ev['evidence_id']}",
                "claim_type": claim_type,
                "statement": ev.get("statement") or ev.get("title") or "Öffentlicher Beleg vorhanden.",
                "assessment_label": "aus Evidence abgeleiteter öffentlicher Hinweis – nicht identitätsbestätigend",
                "reportability": "reportable_with_redaction" if sens["redaction_required"] else "reportable_with_uncertainty",
                "supporting_evidence": [ev["evidence_id"]],
                "contra_evidence": [],
                "uncertainty_note": "Automatisch abgeleitet aus Evidence; menschliche Einordnung bleibt erforderlich.",
                "redaction_required": int(sens["redaction_required"]),
                "source_url": ev.get("source_url") or "",
            })
        return claims

    def list_claims(self, case_id: str, include_derived: bool = True) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM verified_claims WHERE case_id=? ORDER BY created_at DESC", [case_id])
        out: List[Dict[str, Any]] = []
        for row in rows:
            row["supporting_evidence"] = loads(row.get("supporting_evidence_json"), [])
            row["contra_evidence"] = loads(row.get("contra_evidence_json"), [])
            out.append(row)
        if include_derived:
            out.extend(self._approved_evidence_claims(case_id))
        return out

    def _collect_build46_context(self, case_id: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {"search_plans": [], "planned_search_parameters": 0, "public_document_extracts": [], "review_items_pro": []}
        try:
            plans = self.db.all("SELECT plan_id,mode,source_count,parameter_count,status,generated_at FROM search_plans_46 WHERE case_id=? ORDER BY generated_at DESC", [case_id])
            context["search_plans"] = plans
            context["planned_search_parameters"] = sum(int(p.get("parameter_count") or 0) for p in plans)
        except Exception:
            pass
        try:
            extracts = self.db.all("SELECT extract_id,document_title,document_type,source_url,extraction_confidence,review_status,retrieved_at,sensitivity_json FROM public_document_extracts_46 WHERE case_id=? ORDER BY retrieved_at DESC LIMIT 25", [case_id])
            for row in extracts:
                row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
                row["document_title"] = _redact(row.get("document_title", ""))
                row["source_url"] = _redact(row.get("source_url", ""))
            context["public_document_extracts"] = extracts
        except Exception:
            pass
        try:
            review = self.db.all("SELECT review_id,title,source_url,stage,priority,reportability,source_category,updated_at,sensitivity_json FROM review_inbox_pro_46 WHERE case_id=? ORDER BY priority DESC, updated_at DESC LIMIT 40", [case_id])
            for row in review:
                row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
                row["title"] = _redact(row.get("title", ""))
                row["source_url"] = _redact(row.get("source_url", ""))
            context["review_items_pro"] = review
        except Exception:
            pass
        return context

    def build_profile(self, case_id: str, profile_type: str = "redacted_profile", outdir: str | Path | None = None) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not case:
            raise KeyError(f"Fall nicht gefunden: {case_id}")
        target_rows = self.db.all("SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC", [case_id])
        source_intel = self._collect_build46_context(case_id)
        claims = self.list_claims(case_id, include_derived=True)
        facts: List[Dict[str, Any]] = []
        hints: List[Dict[str, Any]] = []
        uncertainties: List[Dict[str, Any]] = []
        counter: List[Dict[str, Any]] = []
        blocked: List[Dict[str, Any]] = []

        for claim in claims:
            claim_type = claim.get("claim_type", "")
            if claim_type in FORBIDDEN_CLAIM_TYPES:
                blocked.append({"claim_type": claim_type, "reason": "forbidden_claim_type"})
                continue
            if claim_type not in ALLOWED_CLAIM_TYPES:
                uncertainties.append({"statement": _redact(claim.get("statement", "")), "reason": "unknown_claim_type"})
                continue
            item = {
                "claim_type": claim_type,
                "statement": _redact(claim.get("statement", "")),
                "assessment_label": claim.get("assessment_label") or "plausibler Hinweis",
                "reportability": normalize_reportability(claim.get("reportability"), has_uncertainty=True),
                "supporting_evidence": claim.get("supporting_evidence") or loads(claim.get("supporting_evidence_json"), []),
                "contra_evidence": claim.get("contra_evidence") or loads(claim.get("contra_evidence_json"), []),
                "uncertainty_note": _redact(claim.get("uncertainty_note") or ""),
            }
            if claim_type == "claim_counter_evidence":
                counter.append(item)
            elif claim_type in {"claim_uncertainty", "claim_exclusion"} or item["uncertainty_note"]:
                uncertainties.append(item)
            elif item["reportability"] == "reportable_as_verified_claim":
                facts.append(item)
            else:
                hints.append(item)

        profile = {
            "profile_type": profile_type,
            "case": {"case_id": case_id, "title": case.get("title"), "purpose": case.get("purpose"), "jurisdiction": case.get("jurisdiction"), "risk_level": case.get("risk_level")},
            "targets": [{"target_id": t["target_id"], "name": _redact(t.get("name", "")), "notes": _redact(t.get("notes", ""))} for t in target_rows],
            "profile_guardrails": [
                "Keine automatische Identitätsbestätigung.",
                "Keine Schuld-, Gefährlichkeits-, Wohnadress-, biometrische oder Live-Standort-Feststellung.",
                "Alle Aussagen bleiben als öffentliche Hinweise/Claims mit Unsicherheit und Belegreferenz markiert.",
            ],
            "facts": facts,
            "public_hints": hints,
            "uncertainties": uncertainties,
            "counter_evidence": counter,
            "blocked_claims": blocked,
            "source_intelligence": source_intel,
            "metrics": {"facts": len(facts), "public_hints": len(hints), "uncertainties": len(uncertainties), "counter_evidence": len(counter), "blocked_claims": len(blocked), "search_plans": len(source_intel.get("search_plans", [])), "planned_search_parameters": source_intel.get("planned_search_parameters", 0), "public_document_extracts": len(source_intel.get("public_document_extracts", [])), "review_items_pro": len(source_intel.get("review_items_pro", []))},
            "created_at": now_ts(),
        }
        markdown = self._to_markdown(profile)
        content_hash = _sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True) + markdown)
        audit_rows = self.db.all("SELECT event_id,timestamp,action,object_type,object_id FROM audit_events WHERE case_id=? ORDER BY timestamp ASC", [case_id])
        audit_digest_hash = _sha256(json.dumps(audit_rows, ensure_ascii=False, sort_keys=True))
        profile_id = new_id("profile")
        redaction_manifest = {"redaction": "email/phone pattern redaction plus forbidden-claim suppression", "blocked_claims": blocked}
        self.db.execute('''INSERT INTO export_profiles(profile_id,case_id,profile_type,status,profile_json,profile_markdown,content_hash,redaction_manifest_json,audit_digest_hash,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [profile_id, case_id, profile_type, "created", dumps(profile), markdown, content_hash, dumps(redaction_manifest), audit_digest_hash, profile["created_at"]])
        self.audit.log("create", "export_profile", profile_id, case_id, {"profile_type": profile_type, "content_hash": content_hash, "metrics": profile["metrics"]})
        paths: Dict[str, str] = {}
        if outdir:
            out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
            json_path = out / f"{case_id}_redacted_profile.json"
            md_path = out / f"{case_id}_redacted_profile.md"
            json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
            md_path.write_text(markdown, encoding="utf-8")
            paths = {"json": str(json_path), "markdown": str(md_path)}
        return {"profile_id": profile_id, "content_hash": content_hash, "audit_digest_hash": audit_digest_hash, "profile": profile, "markdown": markdown, "paths": paths}

    def _to_markdown(self, profile: Dict[str, Any]) -> str:
        lines = [
            f"# Redigiertes PersonenOSINT-Profil – {profile['case']['title']}",
            "",
            "## Guardrails",
        ]
        lines += [f"- {g}" for g in profile["profile_guardrails"]]
        lines += ["", "## Zielanker"]
        for t in profile["targets"]:
            lines.append(f"- {t['name']} ({t['target_id']})")
        def section(title: str, items: List[Dict[str, Any]]):
            lines.extend(["", f"## {title}"])
            if not items:
                lines.append("Keine exportfähigen Einträge.")
                return
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. **{item.get('claim_type')}** – {item.get('statement')}")
                lines.append(f"   - Bewertung: {item.get('assessment_label')}")
                lines.append(f"   - Berichtsfähigkeit: {item.get('reportability')}")
                if item.get("uncertainty_note"):
                    lines.append(f"   - Unsicherheit: {item.get('uncertainty_note')}")
                lines.append(f"   - Belege: {', '.join(item.get('supporting_evidence') or []) or 'keine'}")
                lines.append(f"   - Gegenbelege: {', '.join(item.get('contra_evidence') or []) or 'keine'}")
        section("Belastbare öffentliche Claims", profile["facts"])
        section("Öffentliche Hinweise", profile["public_hints"])
        section("Unsicherheiten / Ausschlüsse", profile["uncertainties"])
        section("Gegenbelege", profile["counter_evidence"])
        src = profile.get("source_intelligence", {})
        lines.extend(["", "## Build-46 Source Intelligence"])
        lines.append(f"- Suchpläne: {len(src.get('search_plans', []))}")
        lines.append(f"- Geplante Suchparameter: {src.get('planned_search_parameters', 0)}")
        lines.append(f"- Public-Document-Extracts: {len(src.get('public_document_extracts', []))}")
        lines.append(f"- Review-Inbox-Pro-Einträge: {len(src.get('review_items_pro', []))}")
        if src.get("search_plans"):
            lines.append("")
            lines.append("### Suchpläne")
            for plan in src.get("search_plans", [])[:10]:
                lines.append(f"- {plan.get('mode')} – {plan.get('parameter_count')} Parameter / {plan.get('source_count')} Quellen ({plan.get('status')})")
        if src.get("public_document_extracts"):
            lines.append("")
            lines.append("### Öffentliche Dokumentextrakte")
            for doc in src.get("public_document_extracts", [])[:10]:
                lines.append(f"- {doc.get('document_title')} – {doc.get('document_type')} / {doc.get('extraction_confidence')} / {doc.get('review_status')}")
        if src.get("review_items_pro"):
            lines.append("")
            lines.append("### Review Inbox Pro")
            for item in src.get("review_items_pro", [])[:10]:
                lines.append(f"- {item.get('title')} – {item.get('stage')} / {item.get('reportability')}")
        lines.extend(["", "## Metriken", json.dumps(profile["metrics"], ensure_ascii=False, indent=2), "", f"Erstellt: {profile['created_at']}"])
        return "\n".join(lines) + "\n"
