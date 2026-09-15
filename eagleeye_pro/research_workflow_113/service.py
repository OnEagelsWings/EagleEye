from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class ResearchWorkflow113Service:
    """Build 113 research workflow engine.

    The service structures research without autonomously confirming identities,
    converting candidates into facts, or expanding beyond the approved scope.
    """

    WORKFLOW_STATES = {
        "draft", "planned", "approved", "running", "paused", "review",
        "completed", "cancelled", "blocked",
    }
    STEP_STATES = {
        "pending", "ready", "running", "paused", "review", "completed",
        "skipped", "blocked", "failed",
    }
    STEP_TYPES = {
        "scope", "identity_baseline", "research_question", "search",
        "capture", "normalize", "deduplicate", "source_review", "correlate",
        "timeline", "hypothesis", "counter_hypothesis", "contradiction_review",
        "gap_review", "lead_review", "closeout",
    }
    TRANSITIONS = {
        "draft": {"planned", "cancelled"},
        "planned": {"approved", "draft", "cancelled", "blocked"},
        "approved": {"running", "cancelled", "blocked"},
        "running": {"paused", "review", "completed", "cancelled", "blocked"},
        "paused": {"running", "cancelled", "blocked"},
        "review": {"running", "completed", "paused", "blocked"},
        "blocked": {"planned", "approved", "running", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    REQUIRED_GATES = ("scope", "identity", "source_quality", "contradiction", "lead_review")

    def __init__(self, db: Any, audit: Any = None, kernel: Any = None) -> None:
        self.db = db
        self.audit = audit
        self.kernel = kernel
        self.ensure_schema()
        self.seed_templates()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_templates_113(
                template_id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                version INTEGER NOT NULL,
                steps_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_workflows_113(
                workflow_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                target_id TEXT,
                template_id TEXT,
                title TEXT NOT NULL,
                objective TEXT NOT NULL,
                approved_scope_json TEXT NOT NULL,
                assumptions_json TEXT NOT NULL,
                constraints_json TEXT NOT NULL,
                state TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL,
                approved_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_workflows113_case_state
                ON research_workflows_113(case_id,state,updated_at);
            CREATE TABLE IF NOT EXISTS workflow_steps_113(
                step_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                step_type TEXT NOT NULL,
                title TEXT NOT NULL,
                purpose TEXT NOT NULL,
                acceptance_criteria_json TEXT NOT NULL,
                dependencies_json TEXT NOT NULL,
                assigned_agent TEXT,
                state TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_text TEXT,
                UNIQUE(workflow_id,sequence_no)
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_steps113_state
                ON workflow_steps_113(workflow_id,state,sequence_no);
            CREATE TABLE IF NOT EXISTS workflow_gates_113(
                gate_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                gate_type TEXT NOT NULL,
                status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                checked_by TEXT,
                checked_at TEXT,
                UNIQUE(workflow_id,gate_type)
            );
            CREATE TABLE IF NOT EXISTS workflow_decisions_113(
                decision_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                step_id TEXT,
                actor TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                rationale TEXT NOT NULL,
                alternatives_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_metrics_113(
                metric_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                step_id TEXT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_events_113(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                workflow_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.conn.commit()

    def seed_templates(self) -> None:
        steps = [
            ("scope", "Mandat und Umfang", "Legitimen Zweck, Zielperson und Grenzen festhalten", ["Zweck dokumentiert", "Umfang freigegeben"]),
            ("identity_baseline", "Identitätsbasis", "Ausgangsidentität und Verwechslungsrisiken erfassen", ["Mindestens zwei Identitätsanker oder Unsicherheit dokumentiert"]),
            ("research_question", "Leitfragen", "Präzise, prüfbare Recherchefragen definieren", ["Fragen sind eng, neutral und prüfbar"]),
            ("search", "Gezielte Suche", "Nur freigegebene öffentliche Quellen anhand des Plans durchsuchen", ["Suchzweck und Query dokumentiert"]),
            ("capture", "Quellensicherung", "Relevante Treffer mit Herkunft und Zeitpunkt sichern", ["URL, Zeitpunkt und Kontext vorhanden"]),
            ("normalize", "Normalisierung", "Namen, Daten, Orte und Organisationen vereinheitlichen", ["Originalwert bleibt erhalten"]),
            ("deduplicate", "Dublettenprüfung", "Abhängige oder identische Treffer zusammenführen", ["Unabhängigkeit der Quellen bewertet"]),
            ("source_review", "Quellenprüfung", "Autorität, Aktualität, Nähe und Unabhängigkeit bewerten", ["Jede belastende Aussage besitzt Quellenbewertung"]),
            ("correlate", "Korrelation", "Befunde anhand gemeinsamer Anker verbinden", ["Korrelation ist von Kausalität getrennt"]),
            ("timeline", "Zeitliche Einordnung", "Ereignisse und Gültigkeitszeiträume ordnen", ["Zeitkonflikte markiert"]),
            ("hypothesis", "Hypothesen", "Mehrere konkurrierende Erklärungen formulieren", ["Hypothesen als vorläufig gekennzeichnet"]),
            ("counter_hypothesis", "Gegenhypothesen", "Alternative Erklärungen und Widerlegungsversuche dokumentieren", ["Mindestens eine Alternative geprüft"]),
            ("contradiction_review", "Widerspruchsprüfung", "Konflikte, Lücken und abweichende Identitäten prüfen", ["Offene Konflikte benannt"]),
            ("gap_review", "Informationslücken", "Fehlende Informationen priorisieren", ["Nächste Schritte nach Nutzen und Risiko priorisiert"]),
            ("lead_review", "Lead Review", "Menschliche Qualitäts- und Verhältnismäßigkeitsprüfung", ["Lead-Entscheidung dokumentiert"]),
            ("closeout", "Abschluss", "Ergebnis, Grenzen und Reproduzierbarkeit festhalten", ["Keine Hypothese als Fakt ausgegeben"]),
        ]
        payload = [
            {"sequence_no": i + 1, "step_type": t, "title": title, "purpose": purpose, "acceptance_criteria": criteria}
            for i, (t, title, purpose, criteria) in enumerate(steps)
        ]
        self.db.execute(
            "INSERT INTO workflow_templates_113(template_id,name,description,version,steps_json,created_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET description=excluded.description,version=excluded.version,steps_json=excluded.steps_json,active=1",
            ("tpl_person_research_v1", "Person Research – Quality Cycle", "Reproduzierbarer, hypothesengeleiteter OSINT-Qualitätszyklus", 1, _json(payload), _now()),
        )

    def _event(self, workflow_id: str, actor: str, event_type: str, payload: dict[str, Any] | None = None) -> str:
        event_id, ts = _id("wfe"), _now()
        with self.db.conn:
            row = self.db.conn.execute(
                "SELECT event_hash FROM workflow_events_113 WHERE workflow_id=? ORDER BY sequence DESC LIMIT 1",
                (workflow_id,),
            ).fetchone()
            previous = row[0] if row else "GENESIS"
            material = _json([event_id, workflow_id, actor, event_type, payload or {}, previous, ts])
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            self.db.conn.execute(
                "INSERT INTO workflow_events_113(event_id,workflow_id,actor,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, workflow_id, actor, event_type, _json(payload or {}), previous, digest, ts),
            )
        if self.kernel:
            wf = self.db.one("SELECT case_id FROM research_workflows_113 WHERE workflow_id=?", (workflow_id,))
            if wf:
                self.kernel.event(wf["case_id"], actor, event_type, "research_workflow", workflow_id, payload or {})
        return event_id

    def create_workflow(
        self, case_id: str, title: str, objective: str, created_by: str,
        target_id: str | None = None, approved_scope: dict[str, Any] | None = None,
        assumptions: Iterable[str] | None = None, constraints: Iterable[str] | None = None,
        template_name: str = "Person Research – Quality Cycle",
    ) -> str:
        if not case_id or not objective.strip():
            raise ValueError("case_id and objective are required")
        template = self.db.one("SELECT * FROM workflow_templates_113 WHERE name=? AND active=1", (template_name,))
        if not template:
            raise ValueError("workflow template unavailable")
        workflow_id, ts = _id("wf"), _now()
        scope = approved_scope or {"public_sources_only": True, "identity_confirmation": "human_review", "autonomous_scope_expansion": False}
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO research_workflows_113(workflow_id,case_id,target_id,template_id,title,objective,approved_scope_json,assumptions_json,constraints_json,state,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (workflow_id, case_id, target_id, template["template_id"], title[:300], objective[:5000], _json(scope), _json(list(assumptions or [])), _json(list(constraints or [])), "draft", created_by, ts, ts),
            )
            for spec in json.loads(template["steps_json"]):
                self.db.conn.execute(
                    "INSERT INTO workflow_steps_113(step_id,workflow_id,sequence_no,step_type,title,purpose,acceptance_criteria_json,dependencies_json,state,input_json,output_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (_id("wfs"), workflow_id, spec["sequence_no"], spec["step_type"], spec["title"], spec["purpose"], _json(spec["acceptance_criteria"]), _json([] if spec["sequence_no"] == 1 else [spec["sequence_no"] - 1]), "ready" if spec["sequence_no"] == 1 else "pending", _json({}), _json({})),
                )
            for gate in self.REQUIRED_GATES:
                self.db.conn.execute(
                    "INSERT INTO workflow_gates_113(gate_id,workflow_id,gate_type,status,rationale) VALUES(?,?,?,?,?)",
                    (_id("wfg"), workflow_id, gate, "pending", ""),
                )
        self._event(workflow_id, created_by, "WorkflowCreated", {"objective": objective[:500]})
        return workflow_id

    def transition(self, workflow_id: str, new_state: str, actor: str, rationale: str = "") -> None:
        if new_state not in self.WORKFLOW_STATES:
            raise ValueError("invalid workflow state")
        workflow = self.db.one("SELECT * FROM research_workflows_113 WHERE workflow_id=?", (workflow_id,))
        if not workflow:
            raise ValueError("workflow not found")
        if new_state not in self.TRANSITIONS[workflow["state"]]:
            raise ValueError(f"invalid transition {workflow['state']} -> {new_state}")
        if new_state == "approved":
            gate = self.db.one("SELECT status FROM workflow_gates_113 WHERE workflow_id=? AND gate_type='scope'", (workflow_id,))
            if not gate or gate["status"] != "passed":
                raise ValueError("scope gate must pass before approval")
        if new_state == "completed":
            pending = self.db.one("SELECT COUNT(*) n FROM workflow_steps_113 WHERE workflow_id=? AND state NOT IN ('completed','skipped')", (workflow_id,))["n"]
            gates = self.db.one("SELECT COUNT(*) n FROM workflow_gates_113 WHERE workflow_id=? AND status!='passed'", (workflow_id,))["n"]
            if pending or gates:
                raise ValueError("workflow cannot complete with open steps or gates")
        ts = _now()
        self.db.execute(
            "UPDATE research_workflows_113 SET state=?,updated_at=?,completed_at=CASE WHEN ?='completed' THEN ? ELSE completed_at END WHERE workflow_id=?",
            (new_state, ts, new_state, ts, workflow_id),
        )
        self.decision(workflow_id, None, actor, "state_transition", rationale or f"Transition to {new_state}", [workflow["state"]])
        self._event(workflow_id, actor, "WorkflowStateChanged", {"from": workflow["state"], "to": new_state})

    def set_gate(self, workflow_id: str, gate_type: str, passed: bool, actor: str, rationale: str) -> None:
        if gate_type not in self.REQUIRED_GATES:
            raise ValueError("invalid gate")
        if not rationale.strip():
            raise ValueError("gate rationale required")
        self.db.execute(
            "UPDATE workflow_gates_113 SET status=?,rationale=?,checked_by=?,checked_at=? WHERE workflow_id=? AND gate_type=?",
            ("passed" if passed else "failed", rationale[:3000], actor, _now(), workflow_id, gate_type),
        )
        self._event(workflow_id, actor, "WorkflowGateChecked", {"gate": gate_type, "passed": passed})

    def start_step(self, step_id: str, actor: str, input_data: dict[str, Any] | None = None) -> None:
        step = self.db.one("SELECT * FROM workflow_steps_113 WHERE step_id=?", (step_id,))
        if not step or step["state"] != "ready":
            raise ValueError("step not ready")
        dependencies = json.loads(step["dependencies_json"])
        for sequence in dependencies:
            dependency = self.db.one("SELECT state FROM workflow_steps_113 WHERE workflow_id=? AND sequence_no=?", (step["workflow_id"], sequence))
            if not dependency or dependency["state"] not in {"completed", "skipped"}:
                raise ValueError("step dependency incomplete")
        self.db.execute(
            "UPDATE workflow_steps_113 SET state='running',input_json=?,started_at=?,error_text=NULL WHERE step_id=?",
            (_json(input_data or {}), _now(), step_id),
        )
        self._event(step["workflow_id"], actor, "WorkflowStepStarted", {"step_id": step_id, "type": step["step_type"]})

    def complete_step(self, step_id: str, actor: str, output: dict[str, Any], quality_note: str) -> None:
        step = self.db.one("SELECT * FROM workflow_steps_113 WHERE step_id=?", (step_id,))
        if not step or step["state"] not in {"running", "review"}:
            raise ValueError("step is not active")
        if not quality_note.strip():
            raise ValueError("quality note required")
        result = dict(output or {})
        result["quality_note"] = quality_note[:3000]
        with self.db.conn:
            self.db.conn.execute("UPDATE workflow_steps_113 SET state='completed',output_json=?,completed_at=? WHERE step_id=?", (_json(result), _now(), step_id))
            nxt = self.db.conn.execute("SELECT step_id FROM workflow_steps_113 WHERE workflow_id=? AND sequence_no>? AND state='pending' ORDER BY sequence_no LIMIT 1", (step["workflow_id"], step["sequence_no"])).fetchone()
            if nxt:
                self.db.conn.execute("UPDATE workflow_steps_113 SET state='ready' WHERE step_id=?", (nxt[0],))
        self._event(step["workflow_id"], actor, "WorkflowStepCompleted", {"step_id": step_id, "type": step["step_type"]})

    def fail_step(self, step_id: str, actor: str, error: str, blocked: bool = False) -> None:
        step = self.db.one("SELECT * FROM workflow_steps_113 WHERE step_id=?", (step_id,))
        if not step:
            raise ValueError("step not found")
        state = "blocked" if blocked else "failed"
        self.db.execute("UPDATE workflow_steps_113 SET state=?,error_text=? WHERE step_id=?", (state, error[:4000], step_id))
        self._event(step["workflow_id"], actor, "WorkflowStepFailed", {"step_id": step_id, "state": state})

    def resume_step(self, step_id: str, actor: str, rationale: str) -> None:
        step = self.db.one("SELECT * FROM workflow_steps_113 WHERE step_id=?", (step_id,))
        if not step or step["state"] not in {"paused", "failed", "blocked"}:
            raise ValueError("step cannot be resumed")
        self.db.execute("UPDATE workflow_steps_113 SET state='ready',error_text=NULL WHERE step_id=?", (step_id,))
        self.decision(step["workflow_id"], step_id, actor, "resume", rationale, [])
        self._event(step["workflow_id"], actor, "WorkflowStepResumed", {"step_id": step_id})

    def decision(self, workflow_id: str, step_id: str | None, actor: str, decision_type: str, rationale: str, alternatives: Iterable[str]) -> str:
        if not rationale.strip():
            raise ValueError("decision rationale required")
        decision_id = _id("wfd")
        self.db.execute(
            "INSERT INTO workflow_decisions_113 VALUES(?,?,?,?,?,?,?,?)",
            (decision_id, workflow_id, step_id, actor, decision_type[:120], rationale[:5000], _json(list(alternatives)), _now()),
        )
        return decision_id

    def metric(self, workflow_id: str, name: str, value: float, step_id: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        metric_id = _id("wfm")
        self.db.execute("INSERT INTO workflow_metrics_113 VALUES(?,?,?,?,?,?,?)", (metric_id, workflow_id, step_id, name[:120], float(value), _json(metadata or {}), _now()))
        return metric_id

    def next_actions(self, workflow_id: str) -> list[dict[str, Any]]:
        workflow = self.db.one("SELECT * FROM research_workflows_113 WHERE workflow_id=?", (workflow_id,))
        if not workflow:
            return []
        actions: list[dict[str, Any]] = []
        failed_gates = self.db.all("SELECT gate_type,status,rationale FROM workflow_gates_113 WHERE workflow_id=? AND status!='passed' ORDER BY gate_type", (workflow_id,))
        for gate in failed_gates:
            actions.append({"priority": 10, "action": "review_gate", "gate": gate["gate_type"], "status": gate["status"]})
        ready = self.db.all("SELECT step_id,sequence_no,step_type,title,state FROM workflow_steps_113 WHERE workflow_id=? AND state IN ('ready','failed','blocked') ORDER BY sequence_no", (workflow_id,))
        for step in ready:
            actions.append({"priority": 20 if step["state"] == "ready" else 5, "action": "execute_or_resolve_step", **step})
        return sorted(actions, key=lambda item: (item["priority"], item.get("sequence_no", 0)))

    def summary(self, workflow_id: str) -> dict[str, Any]:
        workflow = self.db.one("SELECT * FROM research_workflows_113 WHERE workflow_id=?", (workflow_id,))
        if not workflow:
            raise ValueError("workflow not found")
        steps = self.db.all("SELECT * FROM workflow_steps_113 WHERE workflow_id=? ORDER BY sequence_no", (workflow_id,))
        gates = self.db.all("SELECT * FROM workflow_gates_113 WHERE workflow_id=? ORDER BY gate_type", (workflow_id,))
        decisions = self.db.all("SELECT * FROM workflow_decisions_113 WHERE workflow_id=? ORDER BY created_at", (workflow_id,))
        completed = sum(1 for step in steps if step["state"] in {"completed", "skipped"})
        return {
            "workflow": workflow,
            "progress": round(completed / len(steps), 4) if steps else 0.0,
            "steps": steps,
            "gates": gates,
            "decisions": decisions,
            "next_actions": self.next_actions(workflow_id),
            "human_control": {
                "identity_confirmation": "required",
                "scope_expansion": "requires explicit approval",
                "candidate_to_fact": "not automatic",
            },
        }

    def verify_event_chain(self, workflow_id: str) -> dict[str, Any]:
        previous, errors = "GENESIS", []
        rows = self.db.all("SELECT * FROM workflow_events_113 WHERE workflow_id=? ORDER BY sequence", (workflow_id,))
        for row in rows:
            payload = json.loads(row["payload_json"])
            material = _json([row["event_id"], workflow_id, row["actor"], row["event_type"], payload, previous, row["created_at"]])
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                errors.append(row["event_id"])
            previous = row["event_hash"]
        return {"valid": not errors, "events": len(rows), "errors": errors}
