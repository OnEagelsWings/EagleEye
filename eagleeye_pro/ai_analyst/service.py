from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Dict, List

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate


FORBIDDEN_DECISION_PHRASES = [
    "sicher dieselbe person", "ist eindeutig dieselbe person", "ist der täter", "ist die täterin",
    "ist schuldig", "ist gefährlich", "wohnort ist", "private adresse", "definitiv identisch",
    "automatisch bestätigt", "face id bestätigt", "biometrisch bestätigt",
]

SAFE_ASSISTANT_NOTICE = (
    "Case Templates & Playbooks arbeitet nur assistierend: Kandidaten, Unsicherheiten, Gegenhypothesen, "
    "Zusammenfassungen und Entwürfe. Keine automatische Identitäts-, Schuld-, Gefährlichkeits- oder Wohnortentscheidung."
)


class AIAnalystAssistantService:
    """Build 29.0 local/AI-ready analyst assistant.

    This service deliberately does not call an external model. It creates structured, reproducible
    analyst-support outputs from existing case data and stores all outputs as drafts/suggestions.
    The guardrail layer blocks definitive identity, guilt, danger or private-address claims.
    Future model integrations can write into the same tables only after the same checks.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    @staticmethod
    def _hash_payload(payload: Any) -> str:
        return hashlib.sha256(dumps(payload).encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _truncate(text: str, n: int = 800) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text[:n] + ("…" if len(text) > n else "")

    def seed_templates(self) -> Dict[str, Any]:
        templates = [
            ("case_digest", "Fall-Digest", "Fasst geprüfte OSINT-Daten als Kandidaten- und Evidenzlage zusammen."),
            ("contradiction_scan", "Widerspruchsscan", "Sucht offene Konflikte, Gegenbelege und Qualitätslücken."),
            ("counter_hypotheses", "Gegenhypothesen", "Erzeugt vorsichtige alternative Erklärungen statt Identitätsbehauptungen."),
            ("timeline_draft", "Timeline-Entwurf", "Leitet Ereigniskandidaten aus Evidence und Timeline ab."),
            ("report_section_draft", "Report-Abschnittsentwurf", "Erzeugt redigierbare Berichtstexte mit Unsicherheitsmarker."),
        ]
        created = 0
        for key, title, description in templates:
            existing = self.db.one("SELECT template_id FROM ai_prompt_templates WHERE template_key=?", [key])
            if existing:
                continue
            tid = new_id("aitpl")
            self.db.execute(
                """INSERT INTO ai_prompt_templates(template_id,template_key,title,description,guardrail_profile,created_at,active)
                VALUES(?,?,?,?,?,?,1)""",
                [tid, key, title, description, "candidate_only_no_identity_guilt_or_address_decisions", now_ts()],
            )
            created += 1
        return {"templates_created": created, "templates_total": len(self.list_templates())}

    def list_templates(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_prompt_templates ORDER BY template_key")

    def guardrail_check(self, case_id: str, text: str, object_type: str = "draft", object_id: str = "") -> Dict[str, Any]:
        text = text or ""
        low = text.lower()
        blocked_terms = [p for p in FORBIDDEN_DECISION_PHRASES if p in low]
        policy = PolicyGate.evaluate_query(text)
        sensitivity = PolicyGate.classify_sensitivity(text)
        warnings = []
        if re.search(r"\b(ist|war)\s+(sicher|definitiv|eindeutig)\b", low):
            warnings.append("definitive_language_detected")
        if "wohnort" in low or "adresse" in low:
            warnings.append("address_language_requires_legal_review")
        if any(k in low for k in ["schuld", "täter", "gefährlich", "bedrohung"]):
            warnings.append("risk_or_guilt_language_requires_senior_review")
        status = "blocked" if blocked_terms or not policy.get("ok") else ("warning" if warnings or sensitivity.get("level") == "high" else "pass")
        check_id = new_id("aigc")
        payload = {
            "blocked_terms": blocked_terms,
            "warnings": warnings,
            "policy": policy,
            "sensitivity": sensitivity,
            "notice": SAFE_ASSISTANT_NOTICE,
        }
        self.db.execute(
            """INSERT INTO ai_guardrail_checks(check_id,case_id,object_type,object_id,status,blocked_terms_json,warnings_json,policy_result_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            [check_id, case_id, object_type, object_id, status, dumps(blocked_terms), dumps(warnings), dumps(payload), now_ts()],
        )
        self.audit.log("ai_guardrail_check", object_type, object_id or check_id, case_id, {"status": status, "blocked_terms": blocked_terms, "warnings": warnings})
        return {"check_id": check_id, "status": status, **payload}

    def _case_context(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        targets = self.db.all("SELECT * FROM targets WHERE case_id=? ORDER BY created_at", [case_id])
        reviews = self.db.all("SELECT * FROM review_items WHERE case_id=? ORDER BY created_at DESC", [case_id])
        evidence = self.db.all("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at DESC", [case_id])
        identities = self.db.all("SELECT * FROM identity_candidates WHERE case_id=? ORDER BY score DESC", [case_id])
        risks = self.db.all("SELECT * FROM risk_findings WHERE case_id=? ORDER BY severity DESC, created_at DESC", [case_id])
        hypotheses = self.db.all("SELECT * FROM graph_hypotheses WHERE case_id=? ORDER BY updated_at DESC", [case_id])
        contradictions = self.db.all("SELECT * FROM graph_contradictions WHERE case_id=? ORDER BY updated_at DESC", [case_id])
        timeline = self.db.all("SELECT * FROM timeline_events WHERE case_id=? ORDER BY event_date, event_id", [case_id])
        provider_results = self.db.all("SELECT * FROM provider_results WHERE case_id=? ORDER BY created_at DESC", [case_id])
        return {
            "case": case,
            "targets": targets,
            "reviews": reviews,
            "evidence": evidence,
            "identities": identities,
            "risks": risks,
            "hypotheses": hypotheses,
            "contradictions": contradictions,
            "timeline": timeline,
            "provider_results": provider_results,
        }

    def create_task(self, case_id: str, task_type: str, title: str, instructions: str = "", source_scope: List[str] | None = None) -> Dict[str, Any]:
        tid = new_id("aitask")
        ts = now_ts()
        self.db.execute(
            """INSERT INTO ai_assistant_tasks(task_id,case_id,task_type,title,instructions,source_scope_json,status,created_at,updated_at,result_hash,guardrail_status,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            [tid, case_id, task_type, title, instructions, dumps(source_scope or []), "queued", ts, ts, "", "pending", SAFE_ASSISTANT_NOTICE],
        )
        self.audit.log("create", "ai_assistant_task", tid, case_id, {"task_type": task_type, "title": title})
        return self.get_task(tid)

    def get_task(self, task_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_assistant_tasks WHERE task_id=?", [task_id])
        if not row:
            raise KeyError(f"AI task not found: {task_id}")
        row["source_scope_json"] = loads(row.get("source_scope_json"), [])
        return row

    def list_tasks(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM ai_assistant_tasks WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["source_scope_json"] = loads(r.get("source_scope_json"), [])
        return rows

    def build_case_digest(self, case_id: str, task_id: str | None = None) -> Dict[str, Any]:
        ctx = self._case_context(case_id)
        case = ctx["case"]
        reviews = ctx["reviews"]
        evidence = ctx["evidence"]
        identities = ctx["identities"]
        risks = ctx["risks"]
        contradictions = ctx["contradictions"]
        timeline = ctx["timeline"]
        review_counts = Counter((r.get("status") or "unknown") for r in reviews)
        evidence_counts = Counter((e.get("review_decision") or "pending") for e in evidence)
        sensitivity_counts = Counter((r.get("sensitivity_level") or "normal") for r in reviews)
        top_evidence = [
            {"evidence_id": e.get("evidence_id"), "title": e.get("title"), "category": e.get("category"), "decision": e.get("review_decision"), "confidence": e.get("confidence")}
            for e in evidence[:8]
        ]
        body_lines = [
            SAFE_ASSISTANT_NOTICE,
            f"Fall: {case.get('title','Unbekannt')} | Zweck: {case.get('purpose','')} | Rechtsgrundlage: {case.get('legal_basis','')}",
            f"Trefferlage: {len(reviews)} Review-Items ({dict(review_counts)}), {len(evidence)} Evidence-Items ({dict(evidence_counts)}).",
            f"Sensibilität: {dict(sensitivity_counts)}. Identity-Kandidaten: {len(identities)}. Risiken: {len(risks)}. Widersprüche/Gegenbelege: {len(contradictions)}. Timeline-Ereignisse: {len(timeline)}.",
            "Kurzbewertung: Die Datenlage ist als Kandidaten- und Evidenzlage zu behandeln; jedes Ergebnis bleibt quellenkritisch und reviewpflichtig.",
        ]
        if top_evidence:
            body_lines.append("Wichtigste Evidence-Kandidaten:")
            for e in top_evidence:
                body_lines.append(f"- {e['category']} | {e['decision']} | {e['title']} | {e['evidence_id']}")
        payload = {
            "summary_type": "case_digest",
            "body": "\n".join(body_lines),
            "metrics": {
                "review_items": len(reviews), "evidence_items": len(evidence), "identity_candidates": len(identities),
                "risk_findings": len(risks), "contradictions": len(contradictions), "timeline_events": len(timeline),
                "review_counts": dict(review_counts), "evidence_counts": dict(evidence_counts), "sensitivity_counts": dict(sensitivity_counts),
            },
            "top_evidence": top_evidence,
        }
        check = self.guardrail_check(case_id, payload["body"], "ai_summary", task_id or "")
        sid = new_id("aisum")
        self.db.execute(
            """INSERT INTO ai_summaries(summary_id,case_id,task_id,summary_type,title,body,metrics_json,source_object_ids_json,guardrail_status,created_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            [sid, case_id, task_id or "", "case_digest", "AI Case Digest", payload["body"], dumps(payload["metrics"]), dumps([e.get("evidence_id") for e in evidence[:20]]), check["status"], now_ts(), "Local deterministic digest; no external model call."],
        )
        if task_id:
            self._finish_task(task_id, payload, check["status"])
        self.audit.log("create", "ai_summary", sid, case_id, {"summary_type": "case_digest", "guardrail": check["status"]})
        return self.get_summary(sid)

    def get_summary(self, summary_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_summaries WHERE summary_id=?", [summary_id])
        if not row:
            raise KeyError("AI summary not found")
        row["metrics_json"] = loads(row.get("metrics_json"), {})
        row["source_object_ids_json"] = loads(row.get("source_object_ids_json"), [])
        return row

    def list_summaries(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM ai_summaries WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["metrics_json"] = loads(r.get("metrics_json"), {})
            r["source_object_ids_json"] = loads(r.get("source_object_ids_json"), [])
        return rows

    def suggest_contradictions(self, case_id: str, task_id: str | None = None) -> Dict[str, Any]:
        ctx = self._case_context(case_id)
        suggestions = []
        reviews = ctx["reviews"]
        evidence = ctx["evidence"]
        identities = ctx["identities"]
        # High sensitivity / export-ready mismatch
        for e in evidence:
            if int(e.get("export_allowed") or 0) and int(e.get("redaction_required") or 0):
                suggestions.append({
                    "type": "export_redaction_conflict", "severity": "high", "title": "Exportfreigabe trotz Redaction-Bedarf prüfen",
                    "description": f"Evidence {e.get('evidence_id')} ist exportiert/freigegeben, aber Redaction ist noch erforderlich.",
                    "related": [e.get("evidence_id")],
                })
        # Low quality accepted hits
        for r in reviews:
            if (r.get("status") in {"accepted_as_lead", "ready_for_evidence", "promoted_to_evidence"}) and float(r.get("quality_score") or 0) < 0.45:
                suggestions.append({
                    "type": "weak_source_accepted", "severity": "medium", "title": "Schwacher Treffer wurde akzeptiert",
                    "description": f"Review Item {r.get('item_id')} hat Qualitätswert {r.get('quality_score')} und sollte quellenkritisch nachgeprüft werden.",
                    "related": [r.get("item_id")],
                })
        # Identity candidates with notable negative markers or high score without evidence volume
        for ic in identities:
            neg = loads(ic.get("negative_markers_json"), [])
            pos = loads(ic.get("positive_markers_json"), [])
            if neg:
                suggestions.append({
                    "type": "identity_negative_markers", "severity": "medium", "title": "Identity-Kandidat enthält Gegenmarker",
                    "description": f"Kandidat {ic.get('candidate_id')} besitzt negative Marker: {', '.join(map(str, neg[:5]))}. Ergebnis bleibt Kandidat.",
                    "related": [ic.get("candidate_id")],
                })
            if float(ic.get("score") or 0) >= 0.75 and len(pos) < 2:
                suggestions.append({
                    "type": "thin_identity_basis", "severity": "medium", "title": "Hoher Identity-Score mit dünner Markerbasis",
                    "description": f"Kandidat {ic.get('candidate_id')} hat hohen Score, aber wenige positive Marker. Gegenbelegsuche empfohlen.",
                    "related": [ic.get("candidate_id")],
                })
        # Duplicate cluster leftovers
        duplicate_groups = Counter(r.get("duplicate_cluster_id") for r in reviews if r.get("duplicate_cluster_id"))
        for cluster_id, count in duplicate_groups.items():
            if count >= 2:
                suggestions.append({
                    "type": "duplicate_cluster_review", "severity": "low", "title": "Duplikatcluster im Review prüfen",
                    "description": f"Cluster {cluster_id} enthält {count} Treffer. Repräsentativen Treffer und Ausschlussliste prüfen.",
                    "related": [cluster_id],
                })
        # Persist suggestions
        created = []
        for s in suggestions[:40]:
            text = f"{s['title']} {s['description']}"
            check = self.guardrail_check(case_id, text, "ai_contradiction_suggestion", task_id or "")
            sid = new_id("aicon")
            self.db.execute(
                """INSERT INTO ai_contradiction_suggestions(suggestion_id,case_id,task_id,contradiction_type,severity,title,description,related_object_ids_json,status,guardrail_status,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                [sid, case_id, task_id or "", s["type"], s["severity"], s["title"], s["description"], dumps(s.get("related", [])), "suggested", check["status"], now_ts(), SAFE_ASSISTANT_NOTICE],
            )
            created.append(sid)
        payload = {"created": len(created), "suggestion_ids": created, "candidate_count": len(suggestions)}
        if task_id:
            self._finish_task(task_id, payload, "pass")
        self.audit.log("suggest", "ai_contradictions", case_id, case_id, payload)
        return payload

    def suggest_counter_hypotheses(self, case_id: str, task_id: str | None = None) -> Dict[str, Any]:
        ctx = self._case_context(case_id)
        hypotheses = []
        if ctx["identities"]:
            hypotheses.append({
                "type": "identity_alternative", "confidence": 0.45,
                "title": "Alternative: Namensdoppler oder mehrere Personen",
                "statement": "Die Treffer könnten teilweise zu unterschiedlichen Personen mit ähnlichem Namen, Ort oder beruflichem Kontext gehören. Namensdoppler- und Zeit-/Ort-Gegenprüfung empfohlen.",
            })
        if ctx["provider_results"] and len(ctx["evidence"]) < len(ctx["provider_results"]):
            hypotheses.append({
                "type": "source_quality_alternative", "confidence": 0.40,
                "title": "Alternative: Provider-Treffer ohne ausreichende Evidence-Basis",
                "statement": "Ein Teil der Provider-Treffer kann Suchmaschinenrauschen oder Kontextverwechslung sein, solange keine Evidence-Promotion und Quellenprüfung erfolgt ist.",
            })
        if ctx["timeline"]:
            hypotheses.append({
                "type": "timeline_alternative", "confidence": 0.42,
                "title": "Alternative: Zeitliche Reihenfolge erklärt Korrektur statt Widerspruch",
                "statement": "Abweichende Angaben können aus Aktualisierungen, alten Profilständen oder Archivständen stammen; Timeline und Webarchive sollten gegengeprüft werden.",
            })
        if not hypotheses:
            hypotheses.append({
                "type": "insufficient_data", "confidence": 0.35,
                "title": "Alternative: Datenlage noch nicht belastbar",
                "statement": "Die Fallakte enthält noch zu wenig geprüfte Evidence, um belastbare Zusammenhänge zu bilden. Zusätzliche öffentliche Quellen und Gegenbelege empfohlen.",
            })
        created=[]
        for h in hypotheses:
            check = self.guardrail_check(case_id, h["statement"], "ai_hypothesis_suggestion", task_id or "")
            sid = new_id("aihyp")
            self.db.execute(
                """INSERT INTO ai_hypothesis_suggestions(suggestion_id,case_id,task_id,hypothesis_type,title,statement,confidence,status,guardrail_status,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [sid, case_id, task_id or "", h["type"], h["title"], h["statement"], float(h["confidence"]), "suggested", check["status"], now_ts(), SAFE_ASSISTANT_NOTICE],
            )
            created.append(sid)
        payload={"created":len(created),"suggestion_ids":created}
        if task_id:
            self._finish_task(task_id, payload, "pass")
        self.audit.log("suggest", "ai_hypotheses", case_id, case_id, payload)
        return payload

    def draft_timeline_from_evidence(self, case_id: str, task_id: str | None = None) -> Dict[str, Any]:
        evidence = self._case_context(case_id)["evidence"]
        created=[]
        for e in evidence[:30]:
            title = f"Evidence-Kandidat erfasst: {self._truncate(e.get('title') or e.get('category') or 'OSINT-Fund', 120)}"
            rationale = "Zeitpunkt entspricht Capture-/Übernahmezeitpunkt, nicht zwingend Ereigniszeitpunkt der Zielperson."
            event_date = (e.get("captured_at") or now_ts())[:10]
            check = self.guardrail_check(case_id, title + " " + rationale, "ai_timeline_draft", task_id or "")
            did = new_id("aitl")
            self.db.execute(
                """INSERT INTO ai_timeline_drafts(draft_id,case_id,task_id,source_evidence_id,event_date,title,description,event_type,confidence,status,guardrail_status,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [did, case_id, task_id or "", e.get("evidence_id"), event_date, title, e.get("statement") or "", "evidence_capture_candidate", 0.5, "draft", check["status"], now_ts(), rationale],
            )
            created.append(did)
        payload={"created":len(created),"draft_ids":created}
        if task_id:
            self._finish_task(task_id, payload, "pass")
        self.audit.log("draft", "ai_timeline", case_id, case_id, payload)
        return payload

    def draft_report_sections(self, case_id: str, report_type: str = "internal_analyst", task_id: str | None = None) -> Dict[str, Any]:
        digest = self.build_case_digest(case_id, task_id=None)
        ctx = self._case_context(case_id)
        sections = {
            "executive_summary_draft": digest["body"],
            "methodology_note_draft": (
                "Die Recherche basiert auf fallbezogener, zweckgebundener OSINT-Verarbeitung aus öffentlichen oder autorisierten Quellen. "
                "Treffer werden als Review-Kandidaten behandelt, in Evidence überführt, mit Hash/Manifest dokumentiert und vor Export rechtlich/inhaltlich geprüft."
            ),
            "uncertainty_register_draft": (
                f"Offene Review-Items: {sum(1 for r in ctx['reviews'] if r.get('status') not in {'promoted_to_evidence','rejected','duplicate'})}. "
                f"Widersprüche/Gegenbelege: {len(ctx['contradictions'])}. Identity-Kandidaten: {len(ctx['identities'])}. "
                "Identitätsaussagen bleiben plausibilitätsbasiert und müssen menschlich bestätigt werden."
            ),
            "next_steps_draft": (
                "Empfohlen: offene Review-Items triagieren, Gegenbelege suchen, Redaction/Exportblocker schließen, Graph-Kanten mit Evidence belegen, "
                "Timeline auf Ereigniszeit versus Capture-Zeit prüfen und Report-Readiness erneut ausführen."
            ),
        }
        created=[]
        for section_key, body in sections.items():
            check = self.guardrail_check(case_id, body, "ai_report_draft", task_id or "")
            did = new_id("airpt")
            self.db.execute(
                """INSERT INTO ai_report_drafts(draft_id,case_id,task_id,report_type,section_key,title,body,status,guardrail_status,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [did, case_id, task_id or "", report_type, section_key, section_key.replace("_", " ").title(), body, "draft", check["status"], now_ts(), SAFE_ASSISTANT_NOTICE],
            )
            created.append(did)
        payload={"created":len(created),"draft_ids":created,"report_type":report_type}
        if task_id:
            self._finish_task(task_id, payload, "pass")
        self.audit.log("draft", "ai_report_sections", case_id, case_id, payload)
        return payload

    def run_assistant_bundle(self, case_id: str) -> Dict[str, Any]:
        task = self.create_task(case_id, "assistant_bundle", "AI Analyst Bundle", "Case Digest, Widerspruchscan, Gegenhypothesen, Timeline- und Reportentwürfe.", ["review", "evidence", "graph", "timeline", "reports"])
        task_id = task["task_id"]
        digest = self.build_case_digest(case_id, task_id=None)
        contradictions = self.suggest_contradictions(case_id, task_id=None)
        hypotheses = self.suggest_counter_hypotheses(case_id, task_id=None)
        timeline = self.draft_timeline_from_evidence(case_id, task_id=None)
        reports = self.draft_report_sections(case_id, "internal_analyst", task_id=None)
        payload = {
            "digest_id": digest["summary_id"],
            "contradictions": contradictions,
            "hypotheses": hypotheses,
            "timeline_drafts": timeline,
            "report_drafts": reports,
            "notice": SAFE_ASSISTANT_NOTICE,
        }
        check = self.guardrail_check(case_id, dumps(payload), "ai_assistant_task", task_id)
        self._finish_task(task_id, payload, check["status"])
        return {"task_id": task_id, **payload, "guardrail_status": check["status"]}

    def _finish_task(self, task_id: str, payload: Any, guardrail_status: str) -> None:
        self.db.execute(
            "UPDATE ai_assistant_tasks SET status=?, updated_at=?, result_hash=?, guardrail_status=? WHERE task_id=?",
            ["completed" if guardrail_status != "blocked" else "blocked", now_ts(), self._hash_payload(payload), guardrail_status, task_id],
        )

    def list_contradiction_suggestions(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM ai_contradiction_suggestions WHERE case_id=? ORDER BY severity DESC, created_at DESC", [case_id])
        for r in rows:
            r["related_object_ids_json"] = loads(r.get("related_object_ids_json"), [])
        return rows

    def list_hypothesis_suggestions(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_hypothesis_suggestions WHERE case_id=? ORDER BY confidence DESC, created_at DESC", [case_id])

    def list_timeline_drafts(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_timeline_drafts WHERE case_id=? ORDER BY event_date, event_id", [case_id])

    def list_report_drafts(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM ai_report_drafts WHERE case_id=? ORDER BY created_at DESC", [case_id])

    def dashboard(self, case_id: str) -> Dict[str, Any]:
        task_counts = self.db.all("SELECT status, COUNT(*) AS n FROM ai_assistant_tasks WHERE case_id=? GROUP BY status", [case_id])
        guard_counts = self.db.all("SELECT status, COUNT(*) AS n FROM ai_guardrail_checks WHERE case_id=? GROUP BY status", [case_id])
        return {
            "status": "ai_assistant_ready",
            "notice": SAFE_ASSISTANT_NOTICE,
            "tasks": {r["status"]: r["n"] for r in task_counts},
            "guardrails": {r["status"]: r["n"] for r in guard_counts},
            "summaries": self.db.one("SELECT COUNT(*) AS n FROM ai_summaries WHERE case_id=?", [case_id]).get("n", 0),
            "contradiction_suggestions": self.db.one("SELECT COUNT(*) AS n FROM ai_contradiction_suggestions WHERE case_id=?", [case_id]).get("n", 0),
            "hypothesis_suggestions": self.db.one("SELECT COUNT(*) AS n FROM ai_hypothesis_suggestions WHERE case_id=?", [case_id]).get("n", 0),
            "timeline_drafts": self.db.one("SELECT COUNT(*) AS n FROM ai_timeline_drafts WHERE case_id=?", [case_id]).get("n", 0),
            "report_drafts": self.db.one("SELECT COUNT(*) AS n FROM ai_report_drafts WHERE case_id=?", [case_id]).get("n", 0),
        }
