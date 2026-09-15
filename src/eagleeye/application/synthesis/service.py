from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8", errors="replace")).hexdigest()


class SynthesisError(ValueError):
    pass


class SynthesisConflict(SynthesisError):
    pass


class InvestigativeSynthesis131Service:
    """Source-bound, review-first case synthesis.

    The service produces conservative working drafts only. It never promotes a
    claim to fact, never exports automatically and never performs network or
    provider actions. Every substantive sentence carries internal object refs.
    """

    BUILD = "131.0"
    REVIEW_DECISIONS = {"accepted_for_working_use", "needs_revision", "rejected", "deferred"}

    def __init__(self, db: Any, audit: Any, *, cases: Any, targets: Any) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (str(case_id),))
        if not row:
            raise SynthesisError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise SynthesisError("Zielperson gehört nicht zu diesem Fall")
        return row

    def _table(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _count(self, sql: str, params: tuple[Any, ...]) -> int:
        row = self.db.one(sql, params) or {}
        return int(row.get("n") or 0)

    def _inventory(self, case_id: str, target_id: str = "") -> dict[str, Any]:
        inv: dict[str, Any] = {
            "targets": self._count("SELECT COUNT(*) AS n FROM targets WHERE case_id=?", (case_id,)),
            "intake_total": self._count("SELECT COUNT(*) AS n FROM provider_intake_120 WHERE case_id=?", (case_id,)),
            "intake_new": self._count("SELECT COUNT(*) AS n FROM provider_intake_120 WHERE case_id=? AND review_status='new'", (case_id,)),
            "evidence_packages": self._count("SELECT COUNT(*) AS n FROM evidence_packages_121 WHERE case_id=?", (case_id,)),
            "timeline_events": self._count("SELECT COUNT(*) AS n FROM timeline_events_117 WHERE case_id=?", (case_id,)),
            "open_contradictions": self._count("SELECT COUNT(*) AS n FROM contradictions_118 WHERE case_id=? AND state NOT IN ('resolved','rejected')", (case_id,)),
            "graph_relations": self._count("SELECT COUNT(*) AS n FROM graph_relations_116 WHERE case_id=?", (case_id,)),
            "hypotheses": self._count("SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=?", (case_id,)),
            "reviewed_hypotheses": self._count("SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=? AND state='reviewed'", (case_id,)),
            "pending_hypothesis_reviews": self._count("SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=? AND state='needs_review'", (case_id,)),
            "unsubstantiated_claims": 0,
            "contested_claims": 0,
            "red_team_pending": self._count("SELECT COUNT(*) AS n FROM red_team_reviews_130 WHERE case_id=? AND review_status='pending'", (case_id,)),
            "identity_hypotheses": self._count("SELECT COUNT(*) AS n FROM identity_hypotheses_129 WHERE case_id=?", (case_id,)),
            "identity_pending": self._count("SELECT COUNT(*) AS n FROM identity_hypotheses_129 WHERE case_id=? AND state='candidate'", (case_id,)),
            "captures": self._count("SELECT COUNT(*) AS n FROM browser_captures_129 WHERE case_id=?", (case_id,)),
            "source_records": self._count("SELECT COUNT(*) AS n FROM source_records_128 WHERE case_id=?", (case_id,)),
            "independent_hosts": self._count("SELECT COUNT(DISTINCT source_host) AS n FROM source_records_128 WHERE case_id=? AND source_host<>''", (case_id,)),
            "source_clusters": self._count("SELECT COUNT(*) AS n FROM source_clusters_128 WHERE case_id=?", (case_id,)),
            "orchestrator_outputs_pending": self._count("SELECT COUNT(*) AS n FROM orchestration_outputs_127 WHERE case_id=? AND review_status='pending'", (case_id,)),
        }
        if self._table("hypothesis_claims_130"):
            rows = self.db.all("SELECT hypothesis_id FROM hypotheses_130 WHERE case_id=?", (case_id,))
            for row in rows:
                claims = self.db.all("SELECT claim_id FROM hypothesis_claims_130 WHERE hypothesis_id=?", (row["hypothesis_id"],))
                for claim in claims:
                    stances = {r["stance"] for r in self.db.all("SELECT stance FROM hypothesis_evidence_130 WHERE claim_id=?", (claim["claim_id"],))}
                    if not stances:
                        inv["unsubstantiated_claims"] += 1
                    elif "supports" in stances and "contradicts" in stances:
                        inv["contested_claims"] += 1
        if target_id:
            inv["target_id"] = target_id
        return inv

    def _snapshot_material(self, case_id: str, target_id: str = "") -> dict[str, Any]:
        material: dict[str, Any] = {"case_id": case_id, "target_id": target_id, "inventory": self._inventory(case_id, target_id)}
        queries = {
            "case": ("SELECT case_id,title,purpose,legal_basis,status,updated_at FROM cases WHERE case_id=?", (case_id,)),
            "targets": ("SELECT target_id,name,updated_at FROM targets WHERE case_id=? ORDER BY target_id", (case_id,)),
            "intake": ("SELECT intake_id,review_status,content_fingerprint,updated_at FROM provider_intake_120 WHERE case_id=? ORDER BY intake_id", (case_id,)),
            "evidence": ("SELECT package_id,package_sha256,status,captured_at FROM evidence_packages_121 WHERE case_id=? ORDER BY package_id", (case_id,)),
            "sources": ("SELECT source_id,text_fingerprint,content_fingerprint,review_state,updated_at FROM source_records_128 WHERE case_id=? ORDER BY source_id", (case_id,)),
            "identity": ("SELECT hypothesis_id,state,recommendation,review_decision,created_at FROM identity_hypotheses_129 WHERE case_id=? ORDER BY hypothesis_id", (case_id,)),
            "hypotheses": ("SELECT hypothesis_id,state,review_decision,updated_at FROM hypotheses_130 WHERE case_id=? ORDER BY hypothesis_id", (case_id,)),
            "contradictions": ("SELECT contradiction_id,state,updated_at FROM contradictions_118 WHERE case_id=? ORDER BY contradiction_id", (case_id,)),
            "timeline": ("SELECT event_id,state,updated_at FROM timeline_events_117 WHERE case_id=? ORDER BY event_id", (case_id,)),
        }
        for key, (sql, params) in queries.items():
            try:
                material[key] = self.db.all(sql, params)
            except Exception:
                material[key] = []
        return material

    def current_snapshot_sha256(self, case_id: str, target_id: str = "") -> str:
        self._case(case_id)
        self._target(case_id, target_id)
        return _sha(self._snapshot_material(case_id, target_id))

    def _refs(self, case_id: str, table: str, id_col: str, object_type: str, where: str = "", params: tuple[Any, ...] = (), limit: int = 50) -> list[dict[str, str]]:
        sql = f"SELECT {id_col} AS object_id FROM {table} WHERE case_id=?"
        if where:
            sql += " AND " + where
        sql += f" ORDER BY {id_col} LIMIT {int(limit)}"
        return [{"object_type": object_type, "object_id": str(r["object_id"])} for r in self.db.all(sql, (case_id,) + params)]

    def _build_gaps(self, case_id: str, target_id: str, inventory: dict[str, Any]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        def add(kind: str, title: str, rationale: str, priority: int, action: str, refs: list[dict[str, str]] | None = None) -> None:
            gaps.append({"gap_type": kind, "title": title, "rationale": rationale, "priority": priority, "recommended_action": action, "object_refs": refs or []})
        if inventory["evidence_packages"] == 0:
            add("evidence", "Keine gesicherte Evidence", "Der Fall enthält noch kein Evidence Package.", 100, "Mindestens eine relevante öffentliche Quelle beweissicher erfassen und menschlich prüfen.")
        if inventory["independent_hosts"] < 2:
            add("source_independence", "Zu wenig unabhängige Quellen", f"Es liegen nur {inventory['independent_hosts']} unterschiedliche Quellenhosts vor.", 95, "Eine unabhängige Primär- oder Gegenquelle recherchieren.")
        if inventory["open_contradictions"]:
            add("contradiction", "Offene Widersprüche", f"{inventory['open_contradictions']} Widerspruch/Widersprüche sind nicht aufgelöst.", 90, "Widersprüche priorisieren und pro Konflikt eine Falsifikationsfrage dokumentieren.", self._refs(case_id, "contradictions_118", "contradiction_id", "contradiction", "state NOT IN ('resolved','rejected')"))
        if inventory["unsubstantiated_claims"]:
            add("claim_support", "Claims ohne Evidence", f"{inventory['unsubstantiated_claims']} Claim(s) besitzen keine fallgebundene Evidence.", 90, "Diese Claims aus Berichtsaussagen ausschließen oder gezielt belegen.")
        if inventory["contested_claims"]:
            add("contested_claim", "Umstrittene Claims", f"{inventory['contested_claims']} Claim(s) besitzen Unterstützung und Gegenbeleg.", 85, "Beide Seiten getrennt darstellen und keine eindeutige Schlussfolgerung formulieren.")
        if inventory["identity_pending"]:
            add("identity", "Offene Identitätshypothesen", f"{inventory['identity_pending']} Identitätshypothese(n) sind noch candidate-only.", 88, "Starke Identifikatoren, Zeit- und Ortskonflikte vor jeder Zuordnung prüfen.", self._refs(case_id, "identity_hypotheses_129", "hypothesis_id", "identity_hypothesis", "state='candidate'"))
        if inventory["red_team_pending"]:
            add("red_team", "Red-Team-Review offen", f"{inventory['red_team_pending']} Gegenprüfung(en) warten auf menschliches Review.", 75, "Red-Team-Ausgaben prüfen, bevor eine zentrale Hypothese im Arbeitsbericht gestützt wird.")
        if inventory["intake_new"]:
            add("intake", "Ungeprüfter Intake", f"{inventory['intake_new']} Fund/Funde sind noch nicht triagiert.", 70, "Intake vor der nächsten Synthese entscheiden.", self._refs(case_id, "provider_intake_120", "intake_id", "intake", "review_status='new'"))
        if inventory["timeline_events"] == 0:
            add("timeline", "Keine belastbare Timeline", "Es liegen keine fallgebundenen Timeline-Ereignisse vor.", 60, "Ereignis- und Veröffentlichungszeit getrennt erfassen.")
        if inventory["source_clusters"] and inventory["source_records"] > inventory["independent_hosts"]:
            add("source_copying", "Mögliche Quellenabhängigkeit", "Mehrere Quellen können auf gemeinsame Ursprünge zurückgehen.", 65, "Source-Cluster prüfen und Kopien nicht mehrfach als Bestätigung zählen.")
        return sorted(gaps, key=lambda x: (-x["priority"], x["gap_type"]))

    def create_synthesis(self, *, case_id: str, target_id: str = "", objective: str, actor: str) -> dict[str, Any]:
        case = self._case(case_id)
        target = self._target(case_id, target_id)
        objective = str(objective or "").strip()
        if len(objective) < 12:
            raise SynthesisError("Ein substantielles Analyseziel ist erforderlich")
        inventory = self._inventory(case_id, target_id)
        snapshot = self.current_snapshot_sha256(case_id, target_id)
        run_id, report_id, stamp = _id("syn131"), _id("report131"), _now()
        gaps = self._build_gaps(case_id, target_id, inventory)

        evidence_refs = self._refs(case_id, "evidence_packages_121", "package_id", "evidence")
        hypothesis_refs = self._refs(case_id, "hypotheses_130", "hypothesis_id", "hypothesis", "state='reviewed'")
        contradiction_refs = self._refs(case_id, "contradictions_118", "contradiction_id", "contradiction", "state NOT IN ('resolved','rejected')")
        identity_refs = self._refs(case_id, "identity_hypotheses_129", "hypothesis_id", "identity_hypothesis")
        timeline_refs = self._refs(case_id, "timeline_events_117", "event_id", "timeline_event")
        source_refs = self._refs(case_id, "source_records_128", "source_id", "source")

        subject = target["name"] if target else case["title"]
        sections = [
            (1, "executive_summary", "Arbeitszusammenfassung", f"Für {subject} wurde eine quellengebundene Arbeitsanalyse erzeugt. Der Bestand umfasst {inventory['evidence_packages']} Evidence Packages, {inventory['source_records']} Source Records, {inventory['hypotheses']} Hypothesen und {inventory['open_contradictions']} offene Widersprüche. Diese Zusammenfassung ist kein Tatsachen- oder Schuldurteil.", evidence_refs + source_refs[:10], "working_summary"),
            (2, "established_material", "Gesicherter Materialbestand", f"Gesichert sind die Existenz und Integrität von {inventory['evidence_packages']} fallgebundenen Evidence Packages. Der Inhalt dieser Packages wird dadurch nicht automatisch als wahr bestätigt.", evidence_refs, "source_bound" if evidence_refs else "unsubstantiated"),
            (3, "working_hypotheses", "Geprüfte Arbeitshypothesen", f"{inventory['reviewed_hypotheses']} Hypothesen wurden menschlich reviewed. Sie bleiben Arbeitshypothesen und dürfen nicht als bestätigte Tatsachen formuliert werden.", hypothesis_refs, "candidate_working_use"),
            (4, "identity_status", "Identitätsstatus", f"{inventory['identity_hypotheses']} Identitätshypothesen liegen vor; {inventory['identity_pending']} davon sind noch offen. Es erfolgt keine automatische Zusammenführung.", identity_refs, "candidate_only"),
            (5, "timeline_status", "Zeitliche Einordnung", f"Der Fall enthält {inventory['timeline_events']} Timeline-Ereignisse. Ereigniszeit, Veröffentlichungszeit und Erfassungszeit müssen getrennt bewertet werden.", timeline_refs, "candidate_only"),
            (6, "contradictions", "Widersprüche und Gegenbelege", f"{inventory['open_contradictions']} offene Widersprüche sowie {inventory['contested_claims']} umstrittene Claims verhindern eine eindeutige Schlussfolgerung ohne weitere Prüfung.", contradiction_refs, "contested" if contradiction_refs or inventory['contested_claims'] else "none_recorded"),
            (7, "intelligence_gaps", "Intelligence Gaps", f"Es wurden {len(gaps)} priorisierte Lücken identifiziert. Sie sind methodische Arbeitsaufträge, keine automatischen Rechercheaktionen.", [{"object_type": "intelligence_gap", "object_id": "generated"}], "suggestions_only"),
            (8, "limitations", "Methodische Grenzen", "Die Analyse beruht ausschließlich auf intern gespeicherten Objekten. Quellenbindung beweist Herkunft, nicht Wahrheit. AI-Ausgaben sind suggestions_only; keine externe Suche, Identitätsbestätigung, Evidence-Promotion, Schuld- oder Risikobewertung wurde ausgeführt.", [], "limitations"),
        ]

        claims: list[dict[str, Any]] = []
        for row in self.db.all("SELECT hypothesis_id,title,statement,review_decision FROM hypotheses_130 WHERE case_id=? AND state='reviewed' ORDER BY updated_at", (case_id,)):
            support = self.db.all("""SELECT he.object_type,he.object_id,he.stance,he.independence_group
                                     FROM hypothesis_evidence_130 he JOIN hypothesis_claims_130 hc ON hc.claim_id=he.claim_id
                                     WHERE hc.hypothesis_id=?""", (row["hypothesis_id"],))
            srefs = [{"object_type": r["object_type"], "object_id": r["object_id"]} for r in support if r["stance"] == "supports"]
            crefs = [{"object_type": r["object_type"], "object_id": r["object_id"]} for r in support if r["stance"] == "contradicts"]
            groups = {str(r.get("independence_group") or f"{r['object_type']}:{r['object_id']}") for r in support if r["stance"] == "supports"}
            state = "contested" if crefs else ("source_bound_working_hypothesis" if srefs else "unsubstantiated")
            claims.append({"section_key": "working_hypotheses", "claim_text": row["statement"], "claim_type": "working_hypothesis", "epistemic_state": state, "support_refs": srefs, "contradiction_refs": crefs, "independent_support_count": len(groups), "warning": "Menschlich reviewte Arbeitshypothese; keine Tatsachenpromotion."})

        limitations = [
            "Keine autonome Webrecherche oder Provideraktion.",
            "Keine automatische Identitäts-, Evidence-, Graph- oder Timeline-Promotion.",
            "Quellenbindung ist keine Wahrheitsbestätigung.",
            "Jeder Bericht benötigt menschliches Review.",
        ]
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO synthesis_runs_131 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, case_id, target_id, objective, "completed", snapshot, _json(inventory), _json(limitations), "deterministic_case_analyst_131", "131.0", "suggestions_only", 0, actor, stamp, stamp))
            self.db.execute("INSERT INTO report_drafts_131 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (report_id, run_id, case_id, target_id, f"Investigative Arbeitsanalyse – {subject}", "case_analysis", "draft", "suggestions_only", snapshot, snapshot, 0, "", 1, actor, stamp, stamp, "", "", "", ""))
            for seq, key, heading, body, refs, epistemic in sections:
                self.db.execute("INSERT INTO report_sections_131 VALUES(?,?,?,?,?,?,?,?,?,?)", (_id("sec131"), report_id, case_id, seq, key, heading, body, _json(refs), epistemic, stamp))
            for claim in claims:
                self.db.execute("INSERT INTO report_claims_131 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (_id("claim131"), report_id, case_id, claim["section_key"], claim["claim_text"], claim["claim_type"], claim["epistemic_state"], "pending_verification", _json(claim["support_refs"]), _json(claim["contradiction_refs"]), claim["independent_support_count"], claim["warning"], stamp, stamp))
            for gap in gaps:
                self.db.execute("INSERT INTO intelligence_gaps_131 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (_id("gap131"), run_id, case_id, target_id, gap["gap_type"], gap["title"], gap["rationale"], gap["priority"], gap["recommended_action"], _json(gap["object_refs"]), "open", "suggestions_only", stamp))
            brief = {"priority_gaps": [{"title": g["title"], "priority": g["priority"], "recommended_action": g["recommended_action"]} for g in gaps[:8]], "report_policy": "source_bound_review_first", "prohibited_inferences": ["Keine Schuld- oder Gefährlichkeitsbewertung", "Keine automatische Identitätsbestätigung", "Keine Kausalitätsbehauptung aus Graphnähe"], "external_actions": 0}
            self.db.execute("INSERT INTO synthesis_ai_suggestions_131 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (_id("ai131"), run_id, report_id, case_id, "case_analyst_brief", _json(brief), _json(evidence_refs + hypothesis_refs + contradiction_refs), "suggestions_only", "pending", "deterministic_case_analyst_131", "131.0", actor, stamp))
            self._opsec(case_id, "create_synthesis", "report", report_id, objective, {"objective_in_audit": False, "section_text_in_audit": False, "external_actions": 0, "automatic_export": False}, "suggestions_only", actor)
            self.audit.log("create_synthesis_131", "report_131", report_id, case_id, {"run_id": run_id, "snapshot_sha256": snapshot, "gap_count": len(gaps), "claim_count": len(claims), "external_actions": 0})
        verification = self.verify_claims(case_id=case_id, report_id=report_id, actor=actor)
        return {"run_id": run_id, "report_id": report_id, "snapshot_sha256": snapshot, "inventory": inventory, "gap_count": len(gaps), "claim_count": len(claims), "verification": verification, "trust_state": "suggestions_only", "external_actions": 0}

    def _opsec(self, case_id: str, action: str, object_type: str, object_id: str, value: str, minimization: dict[str, Any], outcome: str, actor: str) -> None:
        self.db.execute("INSERT INTO synthesis_opsec_events_131 VALUES(?,?,?,?,?,?,?,?,?,?)", (_id("op131"), case_id, action, object_type, object_id, hashlib.sha256(str(value or "").encode()).hexdigest() if value else "", _json(minimization), outcome, actor, _now()))

    def _object_exists(self, case_id: str, ref: dict[str, Any]) -> bool:
        mapping = {
            "evidence": ("evidence_packages_121", "package_id"), "source": ("source_records_128", "source_id"),
            "hypothesis": ("hypotheses_130", "hypothesis_id"), "contradiction": ("contradictions_118", "contradiction_id"),
            "identity_hypothesis": ("identity_hypotheses_129", "hypothesis_id"), "timeline_event": ("timeline_events_117", "event_id"),
            "intake": ("provider_intake_120", "intake_id"), "capture": ("browser_captures_129", "capture_id"),
            "relation": ("graph_relations_116", "relation_id"), "entity": ("resolution_entities_115", "resolution_entity_id"),
        }
        object_type = str(ref.get("object_type") or "")
        object_id = str(ref.get("object_id") or "")
        if object_type == "source":
            return bool(
                self.db.one("SELECT source_id FROM source_records_128 WHERE case_id=? AND source_id=?", (case_id, object_id))
                or self.db.one("SELECT source_id FROM graph_sources_116 WHERE case_id=? AND source_id=?", (case_id, object_id))
            )
        item = mapping.get(object_type)
        if not item:
            return False
        table, col = item
        return bool(self.db.one(f"SELECT {col} FROM {table} WHERE case_id=? AND {col}=?", (case_id, object_id)))

    def verify_claims(self, *, case_id: str, report_id: str, actor: str) -> dict[str, Any]:
        report = self.db.one("SELECT * FROM report_drafts_131 WHERE case_id=? AND report_id=?", (case_id, report_id))
        if not report:
            raise SynthesisError("Bericht nicht gefunden")
        rows = self.db.all("SELECT * FROM report_claims_131 WHERE report_id=? ORDER BY claim_id", (report_id,))
        counts = {"source_bound": 0, "contested": 0, "unsubstantiated": 0, "invalid_refs": 0}
        with self.db.transaction(immediate=True):
            for row in rows:
                support = _loads(row.get("support_refs_json"), [])
                contradiction = _loads(row.get("contradiction_refs_json"), [])
                valid_support = [ref for ref in support if self._object_exists(case_id, ref)]
                valid_contra = [ref for ref in contradiction if self._object_exists(case_id, ref)]
                invalid = len(support) + len(contradiction) - len(valid_support) - len(valid_contra)
                counts["invalid_refs"] += invalid
                if valid_contra:
                    state = "contested"
                elif valid_support:
                    state = "source_bound"
                else:
                    state = "unsubstantiated"
                counts[state] += 1
                self.db.execute("UPDATE report_claims_131 SET verification_state=?,warning=?,updated_at=? WHERE claim_id=?", (state, "Ungültige Objektverweise erkannt" if invalid else row.get("warning", ""), _now(), row["claim_id"]))
            self._opsec(case_id, "verify_report_claims", "report", report_id, "", {"claim_text_in_audit": False, "object_ref_count": sum(counts[k] for k in ("source_bound", "contested", "unsubstantiated")), "external_actions": 0}, "verified_for_draft", actor)
            self.audit.log("verify_report_claims_131", "report_131", report_id, case_id, counts | {"external_actions": 0})
        return counts

    def check_staleness(self, *, case_id: str, report_id: str, actor: str = "local-analyst") -> dict[str, Any]:
        report = self.db.one("SELECT * FROM report_drafts_131 WHERE case_id=? AND report_id=?", (case_id, report_id))
        if not report:
            raise SynthesisError("Bericht nicht gefunden")
        current = self.current_snapshot_sha256(case_id, str(report.get("target_id") or ""))
        stale = current != report["snapshot_sha256"]
        reason = "Fallobjekte oder Reviewzustände haben sich seit der Synthese verändert." if stale else ""
        state_changed = (
            str(report.get("current_snapshot_sha256") or "") != current
            or bool(report.get("stale")) != stale
            or str(report.get("stale_reason") or "") != reason
        )
        if state_changed:
            self.db.execute(
                "UPDATE report_drafts_131 SET current_snapshot_sha256=?,stale=?,stale_reason=?,updated_at=? WHERE report_id=?",
                (current, int(stale), reason, _now(), report_id),
            )
        if stale and not bool(report.get("stale")):
            self.audit.log("mark_report_stale_131", "report_131", report_id, case_id, {"previous_snapshot": report["snapshot_sha256"], "current_snapshot": current})
        return {"report_id": report_id, "stale": stale, "snapshot_sha256": report["snapshot_sha256"], "current_snapshot_sha256": current, "reason": reason}

    def request_review(self, *, case_id: str, report_id: str, actor: str) -> dict[str, Any]:
        stale = self.check_staleness(case_id=case_id, report_id=report_id, actor=actor)
        if stale["stale"]:
            raise SynthesisConflict("Veralteter Bericht muss neu erzeugt werden, bevor ein Review angefordert wird")
        unsubstantiated = self._count("SELECT COUNT(*) AS n FROM report_claims_131 WHERE report_id=? AND verification_state='unsubstantiated'", (report_id,))
        changed = self.db.execute("UPDATE report_drafts_131 SET status='needs_review',updated_at=? WHERE report_id=? AND case_id=? AND status='draft'", (_now(), report_id, case_id))
        if changed.rowcount != 1:
            raise SynthesisConflict("Bericht ist nicht mehr für Review verfügbar")
        self.audit.log("request_report_review_131", "report_131", report_id, case_id, {"unsubstantiated_claims": unsubstantiated, "stale": False})
        return {"report_id": report_id, "status": "needs_review", "unsubstantiated_claims": unsubstantiated}

    def review_report(self, *, case_id: str, report_id: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        if decision not in self.REVIEW_DECISIONS:
            raise SynthesisError("Unzulässige Reviewentscheidung")
        reason = str(reason or "").strip()
        if len(reason) < 12:
            raise SynthesisError("Substanzielle Reviewbegründung erforderlich")
        stale = self.check_staleness(case_id=case_id, report_id=report_id, actor=actor)
        if stale["stale"]:
            raise SynthesisConflict("Veralteter Bericht darf nicht reviewed werden")
        if decision == "accepted_for_working_use":
            unsubstantiated = self._count(
                "SELECT COUNT(*) AS n FROM report_claims_131 WHERE report_id=? AND verification_state='unsubstantiated'",
                (report_id,),
            )
            if unsubstantiated:
                raise SynthesisConflict(
                    "Bericht mit unbelegten Claims darf nicht als Arbeitsfassung akzeptiert werden; Claims belegen, kennzeichnen oder Bericht zurückstellen"
                )
        with self.db.transaction(immediate=True):
            changed = self.db.execute("""UPDATE report_drafts_131 SET status='reviewed',reviewed_by=?,reviewed_at=?,review_decision=?,review_reason=?,updated_at=?
                                       WHERE report_id=? AND case_id=? AND status='needs_review'""", (actor, _now(), decision, reason[:4000], _now(), report_id, case_id))
            if changed.rowcount != 1:
                raise SynthesisConflict("Bericht wurde bereits entschieden oder ist nicht im Review")
            self.db.execute("INSERT INTO report_reviews_131 VALUES(?,?,?,?,?,?,?)", (_id("review131"), report_id, case_id, decision, reason[:4000], actor, _now()))
            self._opsec(case_id, "review_report", "report", report_id, reason, {"reason_in_audit": False, "automatic_export": False, "automatic_fact_promotion": False}, decision, actor)
            self.audit.log("review_report_131", "report_131", report_id, case_id, {"decision": decision, "reason_fingerprint": hashlib.sha256(reason.encode()).hexdigest(), "automatic_export": False, "automatic_fact_promotion": False})
        return {"report_id": report_id, "status": "reviewed", "review_decision": decision, "trust_state": "suggestions_only", "automatic_export": False, "automatic_fact_promotion": False}

    def get_report(self, case_id: str, report_id: str) -> dict[str, Any]:
        report = self.db.one("SELECT * FROM report_drafts_131 WHERE case_id=? AND report_id=?", (case_id, report_id))
        if not report:
            raise SynthesisError("Bericht nicht gefunden")
        self.check_staleness(case_id=case_id, report_id=report_id)
        report = self.db.one("SELECT * FROM report_drafts_131 WHERE case_id=? AND report_id=?", (case_id, report_id))
        sections = self.db.all("SELECT * FROM report_sections_131 WHERE report_id=? ORDER BY sequence_no", (report_id,))
        for row in sections:
            row["object_refs"] = _loads(row.pop("object_refs_json", "[]"), [])
        claims = self.db.all("SELECT * FROM report_claims_131 WHERE report_id=? ORDER BY section_key,claim_id", (report_id,))
        for row in claims:
            row["support_refs"] = _loads(row.pop("support_refs_json", "[]"), [])
            row["contradiction_refs"] = _loads(row.pop("contradiction_refs_json", "[]"), [])
        return {"report": report, "sections": sections, "claims": claims, "gaps": self.db.all("SELECT * FROM intelligence_gaps_131 WHERE run_id=? ORDER BY priority DESC", (report["run_id"],))}

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        reports = self.db.all("SELECT * FROM report_drafts_131 WHERE case_id=? ORDER BY updated_at DESC LIMIT 50", (case_id,))
        stale = 0
        for row in reports:
            state = self.check_staleness(case_id=case_id, report_id=row["report_id"])
            row["stale"] = int(state["stale"])
            stale += int(state["stale"])
        return {
            "build": self.BUILD,
            "metrics": {
                "runs": self._count("SELECT COUNT(*) AS n FROM synthesis_runs_131 WHERE case_id=?", (case_id,)),
                "reports": len(reports),
                "stale_reports": stale,
                "open_gaps": self._count("SELECT COUNT(*) AS n FROM intelligence_gaps_131 WHERE case_id=? AND status='open'", (case_id,)),
                "pending_reviews": self._count("SELECT COUNT(*) AS n FROM report_drafts_131 WHERE case_id=? AND status='needs_review'", (case_id,)),
                "unsubstantiated_claims": self._count("SELECT COUNT(*) AS n FROM report_claims_131 WHERE case_id=? AND verification_state='unsubstantiated'", (case_id,)),
                "contested_claims": self._count("SELECT COUNT(*) AS n FROM report_claims_131 WHERE case_id=? AND verification_state='contested'", (case_id,)),
            },
            "reports": reports,
            "gaps": self.db.all("SELECT * FROM intelligence_gaps_131 WHERE case_id=? AND status='open' ORDER BY priority DESC,created_at DESC LIMIT 100", (case_id,)),
            "suggestions": self.db.all("SELECT * FROM synthesis_ai_suggestions_131 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "status": {"trust_state": "suggestions_only", "external_actions": 0, "automatic_fact_promotion": False, "automatic_export": False, "automatic_identity_confirmation": False, "culpability_scoring": False},
        }
