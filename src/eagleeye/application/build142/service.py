from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

REPORT_TYPES = {
    "executive_summary",
    "person_profile",
    "full_investigation",
    "chronology",
    "contradiction_report",
    "source_register",
    "hypothesis_assessment",
    "handover",
}
AUDIENCES = {"internal", "supervisor", "legal_review", "client", "handover", "public"}
REDACTION_PROFILES = {"internal_full", "external_redacted", "handover_minimized", "public_summary"}
REVIEW_DECISIONS = {"approved", "needs_revision", "rejected", "deferred"}
RELEASE_CONFIRMATION = "BERICHT ZUR VERÖFFENTLICHUNG FREIGEBEN"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canonical(value).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _safe_name(value: str, fallback: str = "report") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return text[:80] or fallback


def _masked_email(value: str) -> str:
    text = str(value or "")
    if "@" not in text:
        return "[REDACTED EMAIL]"
    local, domain = text.rsplit("@", 1)
    return (local[:1] + "***@" + domain) if domain else "[REDACTED EMAIL]"


def _pdf_text(value: Any) -> str:
    # Base-14 Helvetica uses WinAnsi. Keep German text readable and replace
    # unsupported punctuation deterministically instead of emitting black boxes.
    text = str(value or "").replace("–", "-").replace("—", "-").replace("…", "...")
    return text.encode("cp1252", errors="replace").decode("cp1252")


class Build142Service:
    BUILD = "142.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: Any,
        install_dir: Any,
        *,
        build141: Any,
        build140: Any,
        build138: Any,
        build136: Any,
        build135: Any,
        synthesis: Any,
        protection: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.reports_root = (self.base_dir / "reports" / "build142").resolve()
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.build141 = build141
        self.build140 = build140
        self.build138 = build138
        self.build136 = build136
        self.build135 = build135
        self.synthesis = synthesis
        self.protection = protection

    def _table(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson gehört nicht zu diesem Fall")
        for key in ("aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"):
            row[key.removesuffix("_json")] = loads(row.get(key), [])
        return row

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build142_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        stamp = now_ts()
        body = {"case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": dict(payload or {}), "previous_hash": previous_hash, "created_by": actor, "created_at": stamp}
        event_hash = _sha(body)
        self.db.execute(
            "INSERT INTO build142_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (new_id("evt142"), case_id, event_type, object_type, object_id, dumps(dict(payload or {})), previous_hash, event_hash, actor, stamp),
        )

    def _profile(self, case_id: str, target_id: str) -> list[dict[str, Any]]:
        if not target_id or not self._table("person_profile_attributes_135"):
            return []
        rows = self.db.all("SELECT * FROM person_profile_attributes_135 WHERE case_id=? AND target_id=? ORDER BY attribute_key", (case_id, target_id))
        out = []
        for row in rows:
            out.append({
                "attribute_id": row["attribute_id"],
                "key": row["attribute_key"],
                "value": loads(row.get("value_json"), None),
                "known": bool(row.get("known")),
                "approximate": bool(row.get("approximate")),
                "review_status": row.get("review_status"),
                "confidence": float(row.get("confidence") or 0),
                "source_id": row.get("source_id") or "",
                "note": row.get("investigator_note") or "",
            })
        return out

    def _assertions(self, case_id: str, target_id: str = "") -> list[dict[str, Any]]:
        sql = "SELECT a.*,sn.label AS subject_label,onode.label AS object_label FROM evidence_assertions_138 a JOIN evidence_nodes_138 sn ON sn.node_id=a.subject_node_id JOIN evidence_nodes_138 onode ON onode.node_id=a.object_node_id WHERE a.case_id=?"
        params: list[Any] = [case_id]
        if target_id:
            sql += " AND (a.target_id=? OR a.target_id IS NULL)"
            params.append(target_id)
        sql += " ORDER BY a.epistemic_state DESC,a.confidence DESC,a.updated_at DESC"
        rows = self.db.all(sql, tuple(params)) if self._table("evidence_assertions_138") else []
        result: list[dict[str, Any]] = []
        for row in rows:
            links = self.db.all(
                "SELECT l.*,s.title,s.canonical_url,s.publisher,s.source_type,s.reliability,q.overall_score,q.quality_band FROM evidence_assertion_sources_138 l JOIN evidence_sources_138 s ON s.source_id=l.source_id LEFT JOIN source_quality_assessments_141 q ON q.case_id=l.case_id AND q.source_id=l.source_id WHERE l.assertion_id=? ORDER BY l.stance,s.title",
                (row["assertion_id"],),
            )
            supports = [self._source_ref(link) for link in links if link.get("stance") == "supports"]
            contradicts = [self._source_ref(link) for link in links if link.get("stance") != "supports"]
            result.append({
                "assertion_id": row["assertion_id"],
                "text": row["assertion_text"],
                "subject": row.get("subject_label") or "",
                "predicate": row.get("predicate") or "",
                "object": row.get("object_label") or "",
                "epistemic_state": row.get("epistemic_state") or "lead",
                "confidence": float(row.get("confidence") or 0),
                "valid_from": row.get("valid_from") or "",
                "valid_to": row.get("valid_to") or "",
                "candidate_only": bool(row.get("candidate_only")),
                "independent_support_count": int(row.get("independence_count") or 0),
                "supporting_sources": supports,
                "contradicting_sources": contradicts,
                "review_note": row.get("review_note") or "",
            })
        return result

    @staticmethod
    def _source_ref(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "source_id": row.get("source_id") or "",
            "title": row.get("title") or "",
            "url": row.get("canonical_url") or "",
            "publisher": row.get("publisher") or "",
            "source_type": row.get("source_type") or "unknown",
            "stance": row.get("stance") or "supports",
            "excerpt": row.get("excerpt") or "",
            "quality_score": float(row.get("overall_score") if row.get("overall_score") is not None else row.get("reliability") or 0.5),
            "quality_band": row.get("quality_band") or "unassessed",
        }

    def _sources(self, case_id: str) -> list[dict[str, Any]]:
        if not self._table("evidence_sources_138"):
            return []
        rows = self.db.all(
            "SELECT s.*,q.classification,q.overall_score,q.quality_band,q.strengths_json,q.weaknesses_json FROM evidence_sources_138 s LEFT JOIN source_quality_assessments_141 q ON q.case_id=s.case_id AND q.source_id=s.source_id WHERE s.case_id=? ORDER BY COALESCE(q.overall_score,s.reliability) DESC,s.title",
            (case_id,),
        )
        for row in rows:
            row["strengths"] = loads(row.pop("strengths_json", "[]"), [])
            row["weaknesses"] = loads(row.pop("weaknesses_json", "[]"), [])
        return rows

    def _contradictions(self, case_id: str, target_id: str = "") -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if self._table("attribute_contradictions_135"):
            sql = "SELECT * FROM attribute_contradictions_135 WHERE case_id=?"
            params: list[Any] = [case_id]
            if target_id:
                sql += " AND target_id=?"
                params.append(target_id)
            for row in self.db.all(sql + " ORDER BY created_at DESC", tuple(params)):
                out.append({"id": row.get("contradiction_id") or "", "type": row.get("contradiction_type") or "profile", "severity": row.get("severity") or "medium", "summary": row.get("summary") or row.get("details") or "Profilwiderspruch", "status": row.get("status") or "open"})
        if self._table("evidence_warnings_138"):
            for row in self.db.all("SELECT * FROM evidence_warnings_138 WHERE case_id=? ORDER BY created_at DESC", (case_id,)):
                out.append({"id": row.get("warning_id") or "", "type": row.get("warning_type") or "evidence", "severity": row.get("severity") or "medium", "summary": row.get("summary") or row.get("title") or "Evidence-Warnung", "status": row.get("status") or "open"})
        if self._table("source_change_events_141"):
            for row in self.db.all("SELECT c.*,s.title FROM source_change_events_141 c JOIN evidence_sources_138 s ON s.source_id=c.source_id WHERE c.case_id=? AND c.status IN ('open','acknowledged') ORDER BY c.created_at DESC", (case_id,)):
                out.append({"id": row["change_id"], "type": "source_change", "severity": row["severity"], "summary": f"Geänderte Quelle: {row['title']} - {row['summary']}", "status": row["status"]})
        return out

    def _timeline(self, case_id: str, target_id: str = "") -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for claim in self._assertions(case_id, target_id):
            if claim["valid_from"] or claim["valid_to"]:
                events.append({"date_from": claim["valid_from"], "date_to": claim["valid_to"], "title": claim["text"], "state": claim["epistemic_state"], "refs": [s["source_id"] for s in claim["supporting_sources"]]})
        return sorted(events, key=lambda r: (r["date_from"] or "9999", r["date_to"] or "9999"))

    def _photos(self, case_id: str, target_id: str = "") -> list[dict[str, Any]]:
        if not self._table("photo_assets_136"):
            return []
        sql = "SELECT p.*,i.quality_band AS image_quality_band,i.content_profile AS research_suitability FROM photo_assets_136 p LEFT JOIN image_analyses_140 i ON i.case_id=p.case_id AND i.asset_id=p.asset_id WHERE p.case_id=?"
        params: list[Any] = [case_id]
        if target_id:
            sql += " AND (p.target_id=? OR p.target_id IS NULL)"
            params.append(target_id)
        rows = self.db.all(sql + " ORDER BY p.created_at DESC", tuple(params))
        return [{
            "asset_id": r["asset_id"], "title": r.get("title") or r.get("original_filename") or "Foto", "source_kind": r.get("source_kind"), "source_label": r.get("source_label") or "", "source_page_url": r.get("source_page_url") or "", "sha256": r.get("sha256") or "", "dimensions": f"{r.get('width_px') or 0}x{r.get('height_px') or 0}", "candidate_only": bool(r.get("candidate_only")), "review_status": r.get("review_status") or "unreviewed", "quality_band": r.get("image_quality_band") or "unassessed", "research_suitability": r.get("research_suitability") or "", "notes": r.get("notes") or ""} for r in rows]

    def _source_report(self, case_id: str, source_report131_id: str) -> dict[str, Any] | None:
        if not source_report131_id:
            return None
        data = self.synthesis.get_report(case_id, source_report131_id)
        report = data["report"]
        if report.get("stale"):
            raise ValueError("Der Build-131-Quellbericht ist veraltet")
        return data

    def _inventory(self, case_id: str, target_id: str = "", source_report131_id: str = "") -> dict[str, Any]:
        case = self._case(case_id)
        target = self._target(case_id, target_id)
        profile = self._profile(case_id, target_id)
        assertions = self._assertions(case_id, target_id)
        sources = self._sources(case_id)
        contradictions = self._contradictions(case_id, target_id)
        timeline = self._timeline(case_id, target_id)
        photos = self._photos(case_id, target_id)
        source_report = self._source_report(case_id, source_report131_id)
        source_changes = self.db.all("SELECT change_id,source_id,change_type,severity,summary,status,created_at FROM source_change_events_141 WHERE case_id=? ORDER BY created_at DESC", (case_id,)) if self._table("source_change_events_141") else []
        return {"case": case, "target": target, "profile": profile, "assertions": assertions, "sources": sources, "contradictions": contradictions, "timeline": timeline, "photos": photos, "source_changes": source_changes, "source_report131": source_report}

    def _snapshot_sha(self, inventory: Mapping[str, Any]) -> str:
        return _sha(inventory)

    @staticmethod
    def _citation_coverage(assertions: Iterable[Mapping[str, Any]]) -> tuple[float, int, int, int]:
        rows = list(assertions)
        substantive = [r for r in rows if r.get("epistemic_state") in {"supported", "confirmed", "contradictory", "refuted"}]
        supported = sum(bool(r.get("supporting_sources")) for r in substantive)
        unresolved = sum(not bool(r.get("supporting_sources")) for r in substantive)
        contested = sum(bool(r.get("contradicting_sources")) or r.get("epistemic_state") == "contradictory" for r in rows)
        return (supported / len(substantive) if substantive else 1.0), supported, contested, unresolved

    def _build_sections(self, inventory: Mapping[str, Any], report_type: str) -> list[dict[str, Any]]:
        case, target = inventory["case"], inventory.get("target")
        assertions = inventory["assertions"]
        confirmed = [a for a in assertions if a["epistemic_state"] in {"confirmed", "supported"} and a["supporting_sources"]]
        hypotheses = [a for a in assertions if a["epistemic_state"] in {"lead", "hypothesis"}]
        contested = [a for a in assertions if a["contradicting_sources"] or a["epistemic_state"] in {"contradictory", "refuted"}]
        sections: list[dict[str, Any]] = []

        def add(key: str, heading: str, summary: str, items: Any) -> None:
            sections.append({"key": key, "heading": heading, "summary": summary, "items": items})

        add("mandate", "Auftrag und Prüfrahmen", "Zweck, Rechtsgrundlage und Grenzen der Untersuchung.", [{"label": "Fall", "value": case["title"]}, {"label": "Zweck", "value": case["purpose"]}, {"label": "Rechtsgrundlage", "value": case["legal_basis"]}, {"label": "Jurisdiktion", "value": case.get("jurisdiction") or "DE/EU"}, {"label": "Zielperson", "value": (target or {}).get("name") or "Gesamter Fall"}])
        if report_type in {"executive_summary", "full_investigation", "handover"}:
            add("executive", "Executive Summary", "Nur beleggebundene Kernaussagen; Hypothesen sind getrennt ausgewiesen.", confirmed[:12])
        if report_type in {"person_profile", "full_investigation", "handover"}:
            base_identity = []
            if target:
                base_identity.append({"label": "Name", "value": target.get("name") or ""})
                base_identity.append({"label": "Aliasse", "value": target.get("aliases", [])})
                base_identity.append({"label": "E-Mails", "value": target.get("emails", [])})
                base_identity.append({"label": "Benutzernamen", "value": target.get("usernames", [])})
                base_identity.append({"label": "Orte", "value": target.get("locations", [])})
                base_identity.append({"label": "Organisationen", "value": target.get("companies", [])})
                base_identity.append({"label": "Domains", "value": target.get("domains", [])})
                base_identity.append({"label": "Notizen", "value": target.get("notes") or ""})
            add("profile", "Personenprofil", "Strukturierte Attribute mit Prüfstatus, Konfidenz und Quellenbezug.", base_identity + inventory["profile"])
        if report_type in {"chronology", "full_investigation", "handover"}:
            add("chronology", "Chronologie", "Zeitlich geordnete belegte oder gekennzeichnete Ereignisse.", inventory["timeline"])
        if report_type in {"hypothesis_assessment", "full_investigation", "handover", "executive_summary"}:
            add("hypotheses", "Hypothesen und offene Fragen", "Unbestätigte Hinweise werden nicht als Tatsachen dargestellt.", hypotheses[:30])
        if report_type in {"contradiction_report", "full_investigation", "handover", "executive_summary"}:
            add("contradictions", "Widersprüche und Risiken", "Konflikte, Quellenänderungen und Gegenbelege.", inventory["contradictions"] + contested)
        if report_type in {"source_register", "full_investigation", "handover"}:
            add("sources", "Quellenregister", "Quellenqualität, Abrufstatus und Unabhängigkeit.", inventory["sources"])
        if report_type in {"full_investigation", "handover", "person_profile"}:
            add("photos", "Foto- und Medienregister", "Technische Bildinformationen und Provenienz; keine biometrische Identitätsaussage.", inventory["photos"])
        if report_type == "handover":
            add("handover", "Übergabe und nächste Schritte", "Offene Aufgaben, Reviewbedarf und OPSEC-Grenzen.", [{"label": "Offene Widersprüche", "value": len(inventory["contradictions"])}, {"label": "Kandidaten/Hypothesen", "value": len(hypotheses)}, {"label": "Quellenänderungen", "value": len(inventory["source_changes"])}, {"label": "Automatische Außenaktionen", "value": 0}])
        return sections

    def _redact(self, content: dict[str, Any], profile: str, rules: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        result = copy.deepcopy(content)
        count = 0
        sensitive_keys = {"emails", "notes", "source_page_url", "url", "canonical_url", "observed_url", "excerpt"}
        profile_keys = {"birth_date", "children_count", "children_state", "marital_status", "life_status"}

        def walk(value: Any, path: str = "") -> Any:
            nonlocal count
            if isinstance(value, dict):
                out: dict[str, Any] = {}
                for key, item in value.items():
                    current = f"{path}.{key}" if path else key
                    if profile != "internal_full" and key in sensitive_keys:
                        count += 1
                        if key == "emails" and isinstance(item, list):
                            out[key] = [_masked_email(str(v)) for v in item]
                        elif key in {"url", "canonical_url", "source_page_url", "observed_url"}:
                            try:
                                host = urlsplit(str(item)).hostname or ""
                                out[key] = f"[REDACTED URL: {host}]" if host else "[REDACTED URL]"
                            except Exception:
                                out[key] = "[REDACTED URL]"
                        else:
                            out[key] = "[REDACTED]"
                    elif profile in {"handover_minimized", "public_summary"} and key in profile_keys:
                        count += 1
                        out[key] = "[REDACTED]"
                    else:
                        out[key] = walk(item, current)
                return out
            if isinstance(value, list):
                return [walk(item, f"{path}[{index}]") for index, item in enumerate(value)]
            if isinstance(value, str):
                text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[REDACTED EMAIL]", value) if profile != "internal_full" else value
                if text != value:
                    count += 1
                text2 = re.sub(r"\b(?:\+?\d[\d\s()/-]{7,}\d)\b", "[REDACTED PHONE]", text) if profile != "internal_full" else text
                if text2 != text:
                    count += 1
                return text2
            return value

        result = walk(result)
        for rule in rules:
            if rule.get("action") != "replace":
                continue
            parts = [p for p in str(rule.get("field_path") or "").split(".") if p]
            node: Any = result
            try:
                for part in parts[:-1]:
                    node = node[part]
                if parts and isinstance(node, dict) and parts[-1] in node:
                    node[parts[-1]] = rule.get("replacement") or "[REDACTED]"
                    count += 1
            except (KeyError, TypeError, IndexError):
                continue
        if profile == "public_summary":
            result["sections"] = [s for s in result.get("sections", []) if s.get("key") in {"mandate", "executive", "chronology", "sources"}]
        return result, count

    def create_report(self, *, case_id: str, target_id: str = "", source_report131_id: str = "", report_type: str, title: str, audience: str, redaction_profile: str, actor: str) -> dict[str, Any]:
        if report_type not in REPORT_TYPES:
            raise ValueError("Unbekannter Berichtstyp")
        if audience not in AUDIENCES or redaction_profile not in REDACTION_PROFILES:
            raise ValueError("Unzulässige Zielgruppe oder Redaktionsprofil")
        inventory = self._inventory(case_id, target_id, source_report131_id)
        snapshot = self._snapshot_sha(inventory)
        coverage, supported, contested, unresolved = self._citation_coverage(inventory["assertions"])
        report_id = new_id("report142")
        content = {
            "schema": "eagleeye.report.142",
            "report_id": report_id,
            "report_type": report_type,
            "title": str(title or "").strip() or f"{report_type.replace('_', ' ').title()} - {inventory['case']['title']}",
            "case_id": case_id,
            "target_id": target_id,
            "audience": audience,
            "redaction_profile": redaction_profile,
            "generated_at": now_ts(),
            "generated_by": actor,
            "epistemic_notice": "Tatsachen, Hypothesen, Widersprüche und offene Fragen sind getrennt zu würdigen. Bildähnlichkeit ist keine Personenidentität.",
            "method": {"external_ai_calls": 0, "autonomous_actions": 0, "automatic_identity_claims": 0, "automatic_image_uploads": 0},
            "sections": self._build_sections(inventory, report_type),
            "citation_index": [{"source_id": s["source_id"], "title": s["title"], "url": s.get("canonical_url") or "", "publisher": s.get("publisher") or "", "quality_band": s.get("quality_band") or "unassessed", "retrieved_at": s.get("retrieved_at") or ""} for s in inventory["sources"]],
            "metrics": {"citation_coverage": coverage, "supported_claims": supported, "contested_claims": contested, "unresolved_claims": unresolved, "source_count": len(inventory["sources"]), "photo_count": len(inventory["photos"]), "contradiction_count": len(inventory["contradictions"])},
        }
        rules: list[dict[str, Any]] = []
        redacted, sensitive = self._redact(content, redaction_profile, rules)
        content_hash = _sha(redacted)
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO professional_reports_142(report142_id,case_id,target_id,source_report131_id,report_type,title,audience,redaction_profile,status,version_no,snapshot_sha256,content_sha256,content_json,citation_coverage,supported_claims,contested_claims,unresolved_claims,sensitive_items,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (report_id, case_id, target_id or None, source_report131_id or None, report_type, redacted["title"], audience, redaction_profile, "draft", 1, snapshot, content_hash, dumps(redacted), coverage, supported, contested, unresolved, sensitive, actor, stamp, stamp),
            )
            self._event(case_id=case_id, event_type="report_created", object_type="professional_report", object_id=report_id, actor=actor, payload={"report_type": report_type, "audience": audience, "redaction_profile": redaction_profile, "content_sha256": content_hash, "citation_coverage": coverage})
            self.audit.log("create_professional_report_142", "professional_report_142", report_id, case_id, {"report_type": report_type, "audience": audience, "content_sha256": content_hash, "external_actions": 0})
        return self.get_report(case_id=case_id, report_id=report_id)

    def add_redaction_rule(self, *, case_id: str, report_id: str, field_path: str, reason: str, replacement: str, actor: str) -> dict[str, Any]:
        report = self._report(case_id, report_id)
        if report["status"] != "draft":
            raise PermissionError("Redaktionsregeln können nur im Entwurf geändert werden")
        if len(str(reason or "").strip()) < 8:
            raise ValueError("Begründung der Schwärzung erforderlich")
        rule_id = new_id("red142")
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO report_redaction_rules_142(rule_id,report142_id,case_id,field_path,action,reason,replacement,automatic,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (rule_id, report_id, case_id, field_path.strip(), "replace", reason.strip(), replacement or "[REDACTED]", 0, actor, now_ts()))
            self._rebuild_redacted_content(report_id, actor)
            self._event(case_id=case_id, event_type="redaction_rule_added", object_type="professional_report", object_id=report_id, actor=actor, payload={"rule_id": rule_id, "field_path": field_path, "reason_sha256": _sha(reason)})
        return {"rule_id": rule_id, "report_id": report_id, "field_path": field_path}

    def _rebuild_redacted_content(self, report_id: str, actor: str) -> None:
        report = self.db.one("SELECT * FROM professional_reports_142 WHERE report142_id=?", (report_id,))
        if not report:
            raise KeyError("Bericht nicht gefunden")
        # Rebuild from a fresh case snapshot, then reapply rules. This avoids
        # cumulative redaction artifacts and detects staleness transparently.
        inventory = self._inventory(report["case_id"], report.get("target_id") or "", report.get("source_report131_id") or "")
        content = loads(report["content_json"], {})
        content["sections"] = self._build_sections(inventory, report["report_type"])
        content["citation_index"] = [{"source_id": s["source_id"], "title": s["title"], "url": s.get("canonical_url") or "", "publisher": s.get("publisher") or "", "quality_band": s.get("quality_band") or "unassessed", "retrieved_at": s.get("retrieved_at") or ""} for s in inventory["sources"]]
        rules = self.db.all("SELECT * FROM report_redaction_rules_142 WHERE report142_id=? ORDER BY created_at", (report_id,))
        redacted, sensitive = self._redact(content, report["redaction_profile"], rules)
        coverage, supported, contested, unresolved = self._citation_coverage(inventory["assertions"])
        self.db.execute("UPDATE professional_reports_142 SET content_json=?,content_sha256=?,snapshot_sha256=?,citation_coverage=?,supported_claims=?,contested_claims=?,unresolved_claims=?,sensitive_items=?,version_no=version_no+1,updated_at=? WHERE report142_id=?", (dumps(redacted), _sha(redacted), self._snapshot_sha(inventory), coverage, supported, contested, unresolved, sensitive, now_ts(), report_id))

    def _report(self, case_id: str, report_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM professional_reports_142 WHERE case_id=? AND report142_id=?", (case_id, report_id))
        if not row:
            raise KeyError("Bericht nicht gefunden")
        return row

    def check_staleness(self, *, case_id: str, report_id: str) -> dict[str, Any]:
        report = self._report(case_id, report_id)
        inventory = self._inventory(case_id, report.get("target_id") or "", report.get("source_report131_id") or "")
        current = self._snapshot_sha(inventory)
        stale = current != report["snapshot_sha256"]
        reason = "Fall-, Beleg-, Quellenqualitäts- oder Fotodaten haben sich seit dem Berichtssnapshot verändert." if stale else ""
        if bool(report.get("stale")) != stale or str(report.get("stale_reason") or "") != reason:
            self.db.execute("UPDATE professional_reports_142 SET stale=?,stale_reason=?,updated_at=? WHERE report142_id=?", (int(stale), reason, now_ts(), report_id))
        return {"report_id": report_id, "stale": stale, "snapshot_sha256": report["snapshot_sha256"], "current_snapshot_sha256": current, "reason": reason}

    def request_review(self, *, case_id: str, report_id: str, actor: str) -> dict[str, Any]:
        report = self._report(case_id, report_id)
        stale = self.check_staleness(case_id=case_id, report_id=report_id)
        if stale["stale"]:
            raise PermissionError("Veralteten Bericht neu erzeugen oder aktualisieren")
        if report["status"] != "draft":
            raise PermissionError("Nur ein Entwurf kann zur Prüfung eingereicht werden")
        if float(report["citation_coverage"]) < 1.0 or int(report["unresolved_claims"]) > 0:
            raise PermissionError("Alle als belastbar dargestellten Aussagen benötigen gültige Quellenreferenzen")
        stamp = now_ts()
        self.db.execute("UPDATE professional_reports_142 SET status='review_ready',review_requested_by=?,review_requested_at=?,updated_at=? WHERE report142_id=?", (actor, stamp, stamp, report_id))
        self._event(case_id=case_id, event_type="review_requested", object_type="professional_report", object_id=report_id, actor=actor, payload={"content_sha256": report["content_sha256"]})
        return self.get_report(case_id=case_id, report_id=report_id)

    def review_report(self, *, case_id: str, report_id: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        if decision not in REVIEW_DECISIONS:
            raise ValueError("Unzulässige Reviewentscheidung")
        reason = str(reason or "").strip()
        if len(reason) < 12:
            raise ValueError("Substanzielle Reviewbegründung erforderlich")
        report = self._report(case_id, report_id)
        if report["status"] != "review_ready":
            raise PermissionError("Bericht ist nicht im Review")
        if actor == report["created_by"] and report["audience"] in {"client", "handover", "public", "legal_review"}:
            raise PermissionError("Externe oder übergabefähige Berichte benötigen Vier-Augen-Prüfung")
        if self.check_staleness(case_id=case_id, report_id=report_id)["stale"]:
            raise PermissionError("Veralteter Bericht darf nicht freigegeben werden")
        status = "reviewed" if decision == "approved" else "draft" if decision == "needs_revision" else "closed"
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE professional_reports_142 SET status=?,reviewed_by=?,reviewed_at=?,review_decision=?,review_reason=?,updated_at=? WHERE report142_id=?", (status, actor, stamp, decision, reason[:4000], stamp, report_id))
            self.db.execute("INSERT INTO report_reviews_142(review142_id,report142_id,case_id,decision,reason,findings_json,actor,created_at) VALUES(?,?,?,?,?,?,?,?)", (new_id("review142"), report_id, case_id, decision, reason[:4000], "[]", actor, stamp))
            self._event(case_id=case_id, event_type="report_reviewed", object_type="professional_report", object_id=report_id, actor=actor, payload={"decision": decision, "reason_sha256": _sha(reason)})
        return self.get_report(case_id=case_id, report_id=report_id)

    def _render_html(self, report: Mapping[str, Any], content: Mapping[str, Any], watermark: str) -> bytes:
        sections = []
        for section in content.get("sections", []):
            items_html = self._items_html(section.get("items", []))
            sections.append(f"<section><h2>{html.escape(str(section.get('heading') or ''))}</h2><p class='summary'>{html.escape(str(section.get('summary') or ''))}</p>{items_html}</section>")
        citations = "".join(f"<li id='src-{html.escape(str(s.get('source_id') or ''))}'><b>{html.escape(str(s.get('title') or 'Quelle'))}</b> - {html.escape(str(s.get('publisher') or ''))} - {html.escape(str(s.get('quality_band') or 'unassessed'))}<br><code>{html.escape(str(s.get('url') or ''))}</code></li>" for s in content.get("citation_index", []))
        css = """body{font-family:Arial,sans-serif;margin:38px;color:#17202a;line-height:1.45}header{border-bottom:3px solid #243b53;margin-bottom:28px}.watermark{position:fixed;top:45%;left:12%;font-size:54px;opacity:.07;transform:rotate(-28deg);z-index:-1}h1{font-size:26px}h2{margin-top:28px;border-bottom:1px solid #ccd6df;padding-bottom:5px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccd6df;padding:6px;vertical-align:top}th{background:#eef3f7}.claim{border-left:4px solid #58799b;padding:9px 12px;margin:8px 0;background:#f7f9fb}.record{margin:10px 0 16px}.record h3{font-size:13px;margin:0 0 5px;color:#243b53}.state{font-size:10px;text-transform:uppercase}.summary{color:#52606d}.footer{margin-top:40px;border-top:1px solid #ccd6df;padding-top:10px;font-size:10px;color:#52606d}code{overflow-wrap:anywhere}@media print{body{margin:18mm}.watermark{position:fixed}}"""
        body = f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><title>{html.escape(str(content.get('title') or 'EagleEye Bericht'))}</title><style>{css}</style></head><body><div class='watermark'>{html.escape(watermark)}</div><header><h1>{html.escape(str(content.get('title') or ''))}</h1><p><b>Berichtstyp:</b> {html.escape(str(content.get('report_type') or ''))}<br><b>Zielgruppe:</b> {html.escape(str(content.get('audience') or ''))}<br><b>Erstellt:</b> {html.escape(str(content.get('generated_at') or ''))}<br><b>Content SHA-256:</b> <code>{html.escape(str(report.get('content_sha256') or ''))}</code></p><p><i>{html.escape(str(content.get('epistemic_notice') or ''))}</i></p></header>{''.join(sections)}<section><h2>Quellenverzeichnis</h2><ol>{citations or '<li>Keine Quellen im Register.</li>'}</ol></section><div class='footer'>EagleEye Build 142.0 - unveränderliche Releasefassung - {html.escape(watermark)}</div></body></html>"""
        return body.encode("utf-8")

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, bool):
            return "Ja" if value else "Nein"
        if isinstance(value, (list, tuple, set)):
            values = [Build142Service._display_value(v) for v in value if v not in (None, "")]
            return ", ".join(values) if values else "—"
        if isinstance(value, Mapping):
            preferred = []
            labels = {
                "date_from": "Von", "date_to": "Bis", "title": "Titel", "name": "Name",
                "status": "Status", "review_status": "Prüfstatus", "confidence": "Konfidenz",
                "quality_band": "Qualität", "publisher": "Herausgeber", "url": "URL",
            }
            for key, item in value.items():
                if item in (None, "", [], {}):
                    continue
                preferred.append(f"{labels.get(str(key), str(key).replace('_', ' ').title())}: {Build142Service._display_value(item)}")
            return "; ".join(preferred) if preferred else "—"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    @staticmethod
    def _item_title(item: Mapping[str, Any]) -> str:
        for key in ("title", "name", "heading", "event", "attribute_key", "predicate", "source_title"):
            value = item.get(key)
            if value not in (None, ""):
                return Build142Service._display_value(value)
        return "Eintrag"

    def _items_html(self, items: Any) -> str:
        if not items:
            return "<p>Keine Einträge.</p>"
        if isinstance(items, list) and all(isinstance(i, Mapping) and "text" in i for i in items):
            chunks = []
            for item in items:
                refs = [s.get("source_id") for s in item.get("supporting_sources", []) if s.get("source_id")]
                chunks.append(f"<div class='claim'><div class='state'>{html.escape(str(item.get('epistemic_state') or ''))} – Konfidenz {float(item.get('confidence') or 0):.2f}</div><p>{html.escape(str(item.get('text') or ''))}</p><small>Quellen: {html.escape(', '.join(refs) or 'keine')} | Gegenbelege: {len(item.get('contradicting_sources', []))}</small></div>")
            return "".join(chunks)
        if isinstance(items, list) and all(isinstance(i, Mapping) and "label" in i and "value" in i for i in items):
            return "<table><tbody>" + "".join(f"<tr><th>{html.escape(str(i.get('label') or ''))}</th><td>{html.escape(self._display_value(i.get('value')))}</td></tr>" for i in items) + "</tbody></table>"
        cards = []
        for item in items if isinstance(items, list) else [items]:
            if not isinstance(item, Mapping):
                cards.append(f"<div class='claim'><p>{html.escape(self._display_value(item))}</p></div>")
                continue
            title = html.escape(self._item_title(item))
            rows = []
            for key, value in list(item.items())[:14]:
                if key in {"title", "name", "heading"} or value in (None, "", [], {}):
                    continue
                label = str(key).replace("_", " ").title()
                rows.append(f"<tr><th>{html.escape(label)}</th><td>{html.escape(self._display_value(value))}</td></tr>")
            cards.append(f"<div class='record'><h3>{title}</h3><table><tbody>{''.join(rows)}</tbody></table></div>")
        return "".join(cards)

    def _render_pdf(self, content: Mapping[str, Any], watermark: str, path: Path) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, KeepTogether
        except Exception as exc:  # pragma: no cover - runtime dependency contract
            raise RuntimeError("PDF-Export benötigt reportlab>=4,<5") from exc

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="EE142Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=14))
        styles.add(ParagraphStyle(name="EE142H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor("#243B53")))
        styles.add(ParagraphStyle(name="EE142Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=6))
        styles.add(ParagraphStyle(name="EE142Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=colors.HexColor("#52606D")))
        styles.add(ParagraphStyle(name="EE142Center", parent=styles["BodyText"], alignment=TA_CENTER, fontSize=8))

        class NumberedDoc(BaseDocTemplate):
            pass

        doc = NumberedDoc(str(path), pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=18*mm, title=_pdf_text(content.get("title")))
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")

        def page(canvas: Any, document: Any) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#6B7C93"))
            canvas.drawString(20*mm, 10*mm, _pdf_text(f"EagleEye Build 142.0 | {watermark}"))
            canvas.drawRightString(A4[0]-20*mm, 10*mm, _pdf_text(f"Seite {document.page}"))
            canvas.setFillColor(colors.Color(0.3, 0.3, 0.3, alpha=0.07))
            canvas.setFont("Helvetica-Bold", 34)
            canvas.translate(A4[0]/2, A4[1]/2)
            canvas.rotate(32)
            canvas.drawCentredString(0, 0, _pdf_text(watermark)[:55])
            canvas.restoreState()

        doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page)])
        story: list[Any] = [Paragraph(html.escape(_pdf_text(content.get("title"))), styles["EE142Title"]), Paragraph(html.escape(_pdf_text(content.get("epistemic_notice"))), styles["EE142Body"]), Spacer(1, 6)]
        metadata = [f"Berichtstyp: {content.get('report_type','')}", f"Zielgruppe: {content.get('audience','')}", f"Erstellt: {content.get('generated_at','')}"]
        story.extend(Paragraph(html.escape(_pdf_text(line)), styles["EE142Small"]) for line in metadata)
        story.append(Spacer(1, 10))
        for section in content.get("sections", []):
            story.append(Paragraph(html.escape(_pdf_text(section.get("heading"))), styles["EE142H2"]))
            story.append(Paragraph(html.escape(_pdf_text(section.get("summary"))), styles["EE142Small"]))
            items = section.get("items", [])
            if not items:
                story.append(Paragraph("Keine Eintraege.", styles["EE142Body"]))
                continue
            for item in items[:120]:
                if isinstance(item, Mapping) and "text" in item:
                    refs = ", ".join(str(s.get("source_id")) for s in item.get("supporting_sources", []) if s.get("source_id")) or "keine"
                    block = [Paragraph(f"<b>{html.escape(_pdf_text(item.get('epistemic_state','')).upper())}</b> - {html.escape(_pdf_text(item.get('text','')))}", styles["EE142Body"]), Paragraph(html.escape(_pdf_text(f"Quellen: {refs}; Gegenbelege: {len(item.get('contradicting_sources', []))}")), styles["EE142Small"])]
                    story.append(KeepTogether(block))
                elif isinstance(item, Mapping):
                    if "label" in item and "value" in item:
                        label = html.escape(_pdf_text(item.get("label")))
                        value = html.escape(_pdf_text(self._display_value(item.get("value"))))
                        story.append(Paragraph(f"<b>{label}:</b> {value}", styles["EE142Body"]))
                    else:
                        title = html.escape(_pdf_text(self._item_title(item)))
                        lines = [Paragraph(f"<b>{title}</b>", styles["EE142Body"])]
                        for key, value in list(item.items())[:14]:
                            if key in {"title", "name", "heading"} or value in (None, "", [], {}):
                                continue
                            label = html.escape(_pdf_text(str(key).replace("_", " ").title()))
                            shown = html.escape(_pdf_text(self._display_value(value)))
                            lines.append(Paragraph(f"<b>{label}:</b> {shown}", styles["EE142Small"]))
                        lines.append(Spacer(1, 4))
                        story.append(KeepTogether(lines))
                else:
                    story.append(Paragraph(html.escape(_pdf_text(item)), styles["EE142Body"]))
        story.append(PageBreak())
        story.append(Paragraph("Quellenverzeichnis", styles["EE142H2"]))
        for index, source in enumerate(content.get("citation_index", []), start=1):
            story.append(Paragraph(html.escape(_pdf_text(f"[{index}] {source.get('title','Quelle')} | {source.get('publisher','')} | {source.get('quality_band','unassessed')} | {source.get('url','')}")), styles["EE142Small"]))
        doc.build(story)

    def release_report(self, *, case_id: str, report_id: str, release_label: str, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != RELEASE_CONFIRMATION:
            raise PermissionError("Exakte Freigabephrase erforderlich")
        report = self._report(case_id, report_id)
        if report["status"] != "reviewed" or report["review_decision"] != "approved":
            raise PermissionError("Nur geprüfte und genehmigte Berichte dürfen veröffentlicht werden")
        if actor == report["created_by"] and report["audience"] in {"client", "handover", "public", "legal_review"}:
            raise PermissionError("Ersteller darf externe Releasefassung nicht allein freigeben")
        if self.check_staleness(case_id=case_id, report_id=report_id)["stale"]:
            raise PermissionError("Bericht ist veraltet")
        content = loads(report["content_json"], {})
        if _sha(content) != report["content_sha256"]:
            raise PermissionError("Berichtsinhalt besteht Integritätsprüfung nicht")
        next_no = int((self.db.one("SELECT COALESCE(MAX(release_no),0)+1 AS n FROM report_releases_142 WHERE report142_id=?", (report_id,)) or {}).get("n") or 1)
        release_id = new_id("release142")
        rel_dir = Path(_safe_name(case_id)) / _safe_name(report_id) / f"release_{next_no:03d}_{_safe_name(release_id)}"
        out_dir = (self.reports_root / rel_dir).resolve()
        if self.reports_root not in out_dir.parents:
            raise PermissionError("Ungültiger Exportpfad")
        out_dir.mkdir(parents=True, exist_ok=False)
        watermark = f"{report['audience'].upper()} | {release_id} | {report['content_sha256'][:12]}"
        json_path = out_dir / "report.json"
        html_path = out_dir / "report.html"
        pdf_path = out_dir / "report.pdf"
        manifest_path = out_dir / "manifest.json"
        json_bytes = (_canonical({"release_id": release_id, "release_no": next_no, "report": content, "content_sha256": report["content_sha256"], "snapshot_sha256": report["snapshot_sha256"]}) + "\n").encode("utf-8")
        html_bytes = self._render_html(report, content, watermark)
        json_path.write_bytes(json_bytes)
        html_path.write_bytes(html_bytes)
        self._render_pdf(content, watermark, pdf_path)
        file_entries = []
        for role, path, mime in (("json", json_path, "application/json"), ("html", html_path, "text/html; charset=utf-8"), ("pdf", pdf_path, "application/pdf")):
            raw = path.read_bytes()
            file_entries.append({"role": role, "filename": path.name, "byte_size": len(raw), "sha256": _sha(raw), "mime_type": mime})
        manifest = {"schema": "eagleeye.release-manifest.142", "build": self.BUILD, "release_id": release_id, "report142_id": report_id, "case_id": case_id, "release_no": next_no, "release_label": release_label.strip() or f"Release {next_no}", "created_at": now_ts(), "created_by": actor, "audience": report["audience"], "redaction_profile": report["redaction_profile"], "watermark": watermark, "content_sha256": report["content_sha256"], "snapshot_sha256": report["snapshot_sha256"], "files": file_entries, "claims": {"immutable_release": True, "automatic_export": False, "external_ai_calls": 0, "automatic_identity_claims": 0}}
        manifest_bytes = (_canonical(manifest) + "\n").encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        manifest_hash = _sha(manifest_bytes)
        all_entries = file_entries + [{"role": "manifest", "filename": manifest_path.name, "byte_size": len(manifest_bytes), "sha256": manifest_hash, "mime_type": "application/json"}]
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO report_releases_142(release_id,report142_id,case_id,release_no,release_label,status,audience,redaction_profile,content_sha256,manifest_sha256,export_dir_relpath,html_relpath,pdf_relpath,json_relpath,manifest_relpath,watermark_text,file_count,immutable,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (release_id, report_id, case_id, next_no, manifest["release_label"], "released", report["audience"], report["redaction_profile"], report["content_sha256"], manifest_hash, rel_dir.as_posix(), (rel_dir / html_path.name).as_posix(), (rel_dir / pdf_path.name).as_posix(), (rel_dir / json_path.name).as_posix(), (rel_dir / manifest_path.name).as_posix(), watermark, len(all_entries), 1, actor, stamp))
            for entry in all_entries:
                self.db.execute("INSERT INTO report_export_files_142(export_file_id,release_id,case_id,file_role,relpath,byte_size,sha256,mime_type,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (new_id("file142"), release_id, case_id, entry["role"], (rel_dir / entry["filename"]).as_posix(), entry["byte_size"], entry["sha256"], entry["mime_type"], stamp))
            self.db.execute("UPDATE professional_reports_142 SET status='released',released=1,released_by=?,released_at=?,updated_at=? WHERE report142_id=?", (actor, stamp, stamp, report_id))
            self._event(case_id=case_id, event_type="report_released", object_type="report_release", object_id=release_id, actor=actor, payload={"report142_id": report_id, "release_no": next_no, "manifest_sha256": manifest_hash, "file_count": len(all_entries)})
            self.audit.log("release_professional_report_142", "report_release_142", release_id, case_id, {"report_id": report_id, "manifest_sha256": manifest_hash, "file_count": len(all_entries), "automatic_export": False})
        return self.get_release(case_id=case_id, release_id=release_id)

    def _release_path(self, relpath: str) -> Path:
        path = (self.reports_root / str(relpath)).resolve()
        if self.reports_root != path and self.reports_root not in path.parents:
            raise PermissionError("Exportpfad verlässt Berichtstresor")
        return path

    def verify_release(self, *, case_id: str, release_id: str, actor: str) -> dict[str, Any]:
        release = self.db.one("SELECT * FROM report_releases_142 WHERE case_id=? AND release_id=?", (case_id, release_id))
        if not release:
            raise KeyError("Release nicht gefunden")
        files = self.db.all("SELECT * FROM report_export_files_142 WHERE release_id=? ORDER BY file_role", (release_id,))
        details = []
        failed = 0
        for row in files:
            path = self._release_path(row["relpath"])
            exists = path.is_file()
            actual = _sha(path.read_bytes()) if exists else ""
            ok = exists and actual == row["sha256"]
            failed += int(not ok)
            details.append({"role": row["file_role"], "relpath": row["relpath"], "exists": exists, "expected_sha256": row["sha256"], "actual_sha256": actual, "ok": ok})
        status = "pass" if failed == 0 and len(files) == int(release["file_count"]) else "fail"
        check_id = new_id("check142")
        self.db.execute("INSERT INTO report_integrity_checks_142(check_id,release_id,case_id,status,checked_files,failed_files,details_json,checked_by,checked_at) VALUES(?,?,?,?,?,?,?,?,?)", (check_id, release_id, case_id, status, len(files), failed, dumps(details), actor, now_ts()))
        self._event(case_id=case_id, event_type="release_integrity_checked", object_type="report_release", object_id=release_id, actor=actor, payload={"status": status, "checked_files": len(files), "failed_files": failed})
        return {"check_id": check_id, "release_id": release_id, "status": status, "checked_files": len(files), "failed_files": failed, "details": details}

    def get_report(self, *, case_id: str, report_id: str) -> dict[str, Any]:
        report = self._report(case_id, report_id)
        content = loads(report["content_json"], {})
        rules = self.db.all("SELECT * FROM report_redaction_rules_142 WHERE report142_id=? ORDER BY created_at", (report_id,))
        reviews = self.db.all("SELECT * FROM report_reviews_142 WHERE report142_id=? ORDER BY created_at DESC", (report_id,))
        releases = self.db.all("SELECT * FROM report_releases_142 WHERE report142_id=? ORDER BY release_no DESC", (report_id,))
        return {"report": report, "content": content, "redaction_rules": rules, "reviews": reviews, "releases": releases}

    def get_release(self, *, case_id: str, release_id: str) -> dict[str, Any]:
        release = self.db.one("SELECT * FROM report_releases_142 WHERE case_id=? AND release_id=?", (case_id, release_id))
        if not release:
            raise KeyError("Release nicht gefunden")
        files = self.db.all("SELECT * FROM report_export_files_142 WHERE release_id=? ORDER BY file_role", (release_id,))
        return {"release": release, "files": files}

    def export_file(self, *, case_id: str, release_id: str, file_role: str) -> tuple[Path, str]:
        row = self.db.one("SELECT f.* FROM report_export_files_142 f JOIN report_releases_142 r ON r.release_id=f.release_id WHERE r.case_id=? AND r.release_id=? AND f.file_role=?", (case_id, release_id, file_role))
        if not row:
            raise KeyError("Exportdatei nicht gefunden")
        path = self._release_path(row["relpath"])
        if not path.is_file() or _sha(path.read_bytes()) != row["sha256"]:
            raise PermissionError("Exportdatei fehlt oder wurde verändert")
        return path, row["mime_type"]

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        if not case_id:
            return {"build": self.BUILD, "metrics": {"reports": 0, "releases": 0, "integrity_failures": 0}, "reports": [], "releases": [], "status": self._status()}
        self._case(case_id)
        reports = self.db.all("SELECT * FROM professional_reports_142 WHERE case_id=? ORDER BY updated_at DESC", (case_id,))
        stale = 0
        for row in reports:
            state = self.check_staleness(case_id=case_id, report_id=row["report142_id"])
            row["stale"] = int(state["stale"])
            stale += int(state["stale"])
        releases = self.db.all("SELECT * FROM report_releases_142 WHERE case_id=? ORDER BY created_at DESC", (case_id,))
        return {
            "build": self.BUILD,
            "metrics": {
                "reports": len(reports),
                "review_ready": sum(r["status"] == "review_ready" for r in reports),
                "released": len(releases),
                "stale": stale,
                "integrity_failures": int((self.db.one("SELECT COUNT(*) AS n FROM report_integrity_checks_142 WHERE case_id=? AND status='fail'", (case_id,)) or {}).get("n") or 0),
            },
            "reports": reports,
            "releases": releases,
            "status": self._status(),
        }

    @staticmethod
    def _status() -> dict[str, Any]:
        return {"report_types": sorted(REPORT_TYPES), "formats": ["html", "pdf", "json", "manifest"], "automatic_export": False, "external_ai_calls": 0, "automatic_identity_claims": 0, "automatic_image_uploads": 0, "immutable_releases": True, "four_eyes_for_external": True, "redaction_profiles": sorted(REDACTION_PROFILES)}
