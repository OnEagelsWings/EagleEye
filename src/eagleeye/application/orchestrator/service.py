from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

from .contracts import AnalystModelAdapter, DeterministicLocalAdapter, ModelEnvelope


class OrchestratorValidationError(ValueError):
    pass


class OrchestratorConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AgentTaskTemplate:
    agent_key: str
    task_type: str
    instruction: str


INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|system|developer)\b", re.I | re.S)),
    ("system_prompt_request", re.compile(r"\b(system prompt|developer message|hidden instructions?)\b", re.I)),
    ("secret_exfiltration", re.compile(r"\b(reveal|print|show|exfiltrate|steal)\b.{0,50}\b(secret|token|api[- ]?key|password|credential)\b", re.I | re.S)),
    ("tool_escalation", re.compile(r"\b(call|run|execute|invoke)\b.{0,40}\b(tool|shell|terminal|powershell|cmd|browser)\b", re.I | re.S)),
    ("policy_override", re.compile(r"\b(bypass|override|disable)\b.{0,40}\b(safety|policy|approval|review|guardrail)\b", re.I | re.S)),
)


class IntelligenceOrchestrator127Service:
    """Human-controlled, local-first intelligence orchestration foundation.

    Build 127 intentionally has no provider transport and no autonomous tool
    execution. It creates a bounded plan, requires explicit approval, executes
    deterministic local analyst roles, and stores every output as
    ``suggestions_only`` pending human review.
    """

    TASK_TEMPLATES: tuple[AgentTaskTemplate, ...] = (
        AgentTaskTemplate("research_planner", "research_gap_analysis", "Inventarisiere vorhandene Recherche und benenne die nächsten begrenzten Prüfschritte."),
        AgentTaskTemplate("source_analyst", "source_inventory", "Ordne vorhandene Quellen und markiere Review- und Unabhängigkeitslücken."),
        AgentTaskTemplate("verification_analyst", "verification_plan", "Formuliere Gegenprüfungen für zentrale Kandidaten und ungeprüfte Belege."),
        AgentTaskTemplate("entity_analyst", "identity_review", "Strukturiere offene Alias-, Namensdoppler- und Merge-Fragen ohne Identitätsbestätigung."),
        AgentTaskTemplate("timeline_analyst", "timeline_review", "Benenne zeitliche Lücken, unreviewte Ereignisse und mögliche Konflikte."),
        AgentTaskTemplate("contradiction_analyst", "contradiction_review", "Priorisiere offene Widersprüche und alternative Erklärungen."),
        AgentTaskTemplate("case_scribe", "case_snapshot", "Erstelle eine quellengebundene Arbeitszusammenfassung mit Unsicherheiten und Limitierungen."),
    )

    TERMINAL_PLAN_STATES = {"completed", "cancelled", "rejected", "failed"}

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        cases: Any,
        targets: Any,
        workspace: Any,
        local_ai: Any,
        clock: Callable[[], float] | None = None,
        model_adapter: AnalystModelAdapter | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets
        self.workspace = workspace
        self.local_ai = local_ai
        self._clock = clock or time.monotonic
        self.model_adapter = model_adapter or DeterministicLocalAdapter()
        self.recover_orphaned_runs(actor="system-recovery")

    @staticmethod
    def _sha(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _flags(text: str) -> list[str]:
        sample = str(text or "")[:20000]
        return [name for name, pattern in INJECTION_PATTERNS if pattern.search(sample)]

    def _policy(self) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM orchestrator_policy_127 WHERE policy_id='default'")
        if not row:
            raise RuntimeError("Build-127-Orchestrator-Policy fehlt")
        return row

    def _require_case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise OrchestratorValidationError("Fall nicht gefunden")
        return row

    def _require_target(self, case_id: str, target_id: str | None) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", (target_id, case_id))
        if not row:
            raise OrchestratorValidationError("Person/Entität gehört nicht zu diesem Fall")
        return row

    def recover_orphaned_runs(self, *, actor: str = "system-recovery") -> dict[str, int]:
        """Recover runs left in ``running`` after an unclean local shutdown."""
        rows = self.db.all("SELECT * FROM orchestration_runs_127 WHERE status='running'")
        retried = 0
        failed = 0
        with self.db.transaction(immediate=True):
            for run in rows:
                if int(run.get("attempt_no") or 1) < int(run.get("max_attempts") or 2):
                    self.db.execute(
                        "UPDATE orchestration_runs_127 SET status='interrupted',completed_at=? WHERE run_id=? AND status='running'",
                        (now_ts(), run["run_id"]),
                    )
                    self.db.execute(
                        "UPDATE orchestration_plans_127 SET status='approved',updated_at=? WHERE plan_id=? AND status='running'",
                        (now_ts(), run["plan_id"]),
                    )
                    self.db.execute(
                        "UPDATE orchestration_tasks_127 SET status='planned',started_at='',updated_at=? WHERE plan_id=? AND status='running'",
                        (now_ts(), run["plan_id"]),
                    )
                    retried += 1
                else:
                    self.db.execute(
                        "UPDATE orchestration_runs_127 SET status='failed',completed_at=? WHERE run_id=? AND status='running'",
                        (now_ts(), run["run_id"]),
                    )
                    self.db.execute(
                        "UPDATE orchestration_plans_127 SET status='failed',updated_at=? WHERE plan_id=? AND status='running'",
                        (now_ts(), run["plan_id"]),
                    )
                    failed += 1
        if retried or failed:
            self.audit.log("recover_orchestrator_runs", "intelligence_orchestrator_127", None, None, {"retried": retried, "failed": failed})
        return {"retried": retried, "failed": failed}

    def status(self) -> dict[str, Any]:
        policy = self._policy()
        return {
            "build": "127.0",
            "mode": "controlled_local_orchestrator_foundation",
            "external_network": policy["external_network_default"],
            "output_trust_state": policy["output_trust_state"],
            "plan_approval_required": bool(policy["require_plan_approval"]),
            "output_review_required": bool(policy["require_output_review"]),
            "max_tasks_hard": int(policy["max_tasks_hard"]),
            "max_runtime_seconds_hard": int(policy["max_runtime_seconds_hard"]),
            "model_key": self.model_adapter.model_key,
            "model_version": self.model_adapter.model_version,
            "may_confirm_identity": False,
            "may_promote_evidence": False,
            "may_open_network": False,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM agent_registry_127 WHERE enabled=1 ORDER BY rowid")
        for row in rows:
            row["capabilities"] = loads(row.pop("capabilities_json", "[]"), [])
            row["prohibited"] = loads(row.pop("prohibited_json", "[]"), [])
        return rows

    def create_plan(
        self,
        *,
        case_id: str,
        target_id: str | None,
        objective: str,
        max_tasks: int = 7,
        max_runtime_seconds: int = 120,
        actor: str = "local-analyst",
    ) -> dict[str, Any]:
        self._require_case(case_id)
        target = self._require_target(case_id, target_id)
        objective = " ".join(str(objective or "").split())
        if len(objective) < 10:
            raise OrchestratorValidationError("Der Analyseauftrag muss mindestens 10 Zeichen enthalten")
        if len(objective) > 2000:
            raise OrchestratorValidationError("Der Analyseauftrag ist zu lang")
        policy = self._policy()
        max_tasks = max(1, min(int(max_tasks), int(policy["max_tasks_hard"])))
        max_runtime_seconds = max(10, min(int(max_runtime_seconds), int(policy["max_runtime_seconds_hard"])))
        flags = self._flags(objective)
        plan_id = new_id("plan127")
        created = now_ts()
        status = "review_required" if flags else "draft"
        selected = self.TASK_TEMPLATES[:max_tasks]
        target_ref = target["target_id"] if target else ""
        source_refs = [{"object_type": "case", "object_id": case_id}]
        if target_ref:
            source_refs.append({"object_type": "target", "object_id": target_ref})
        with self.db.transaction(immediate=True):
            self.db.execute(
                """INSERT INTO orchestration_plans_127(
                  plan_id,case_id,target_id,objective,objective_sha256,status,max_tasks,
                  max_runtime_seconds,max_external_actions,task_count,approval_required,
                  injection_flags_json,created_by,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan_id,
                    case_id,
                    target_ref or None,
                    objective,
                    self._sha(objective),
                    status,
                    max_tasks,
                    max_runtime_seconds,
                    0,
                    len(selected),
                    1,
                    dumps(flags),
                    actor,
                    created,
                    created,
                ),
            )
            for sequence, template in enumerate(selected, start=1):
                self.db.execute(
                    """INSERT INTO orchestration_tasks_127(
                      task_id,plan_id,case_id,sequence_no,agent_key,task_type,instruction,
                      scope_json,source_refs_json,status,requires_human_approval,external_action,
                      budget_cost,created_at,updated_at)
                      VALUES(?,?,?,?,?,?,?,?,?,'planned',0,0,1,?,?)""",
                    (
                        new_id("task127"),
                        plan_id,
                        case_id,
                        sequence,
                        template.agent_key,
                        template.task_type,
                        template.instruction,
                        dumps({"objective_sha256": self._sha(objective), "target_id": target_ref}),
                        dumps(source_refs),
                        created,
                        created,
                    ),
                )
            if flags:
                self.db.execute(
                    """INSERT INTO orchestration_injection_events_127(
                      event_id,case_id,plan_id,source_kind,source_id,flags_json,action,content_sha256,created_at)
                      VALUES(?,?,?,'analyst_objective','',?,'quarantined_for_review',?,?)""",
                    (new_id("inj127"), case_id, plan_id, dumps(flags), self._sha(objective), created),
                )
        self.audit.log(
            "create_plan",
            "intelligence_orchestrator_127",
            plan_id,
            case_id,
            {"task_count": len(selected), "target_id": target_ref, "status": status, "injection_flags": flags},
        )
        return self.get_plan(case_id, plan_id)

    def approve_plan(
        self,
        *,
        case_id: str,
        plan_id: str,
        actor: str,
        confirmation: str,
        reason: str = "",
    ) -> dict[str, Any]:
        if confirmation.strip() != "PLAN FREIGEBEN":
            raise OrchestratorValidationError("Bestätigung PLAN FREIGEBEN fehlt")
        with self.db.transaction(immediate=True):
            plan = self.db.one("SELECT * FROM orchestration_plans_127 WHERE plan_id=? AND case_id=?", (plan_id, case_id))
            if not plan:
                raise OrchestratorValidationError("Plan nicht gefunden")
            if plan["status"] in self.TERMINAL_PLAN_STATES:
                raise OrchestratorConflictError("Der Plan ist bereits terminal")
            flags = loads(plan.get("injection_flags_json"), [])
            if flags:
                raise OrchestratorValidationError("Der Auftrag enthält quarantänisierte Instruktionsmuster und muss verworfen oder neu formuliert werden")
            updated = self.db.execute(
                """UPDATE orchestration_plans_127
                   SET status='approved',approved_by=?,approved_at=?,updated_at=?
                   WHERE plan_id=? AND case_id=? AND status='draft'""",
                (actor, now_ts(), now_ts(), plan_id, case_id),
            )
            if updated.rowcount != 1:
                raise OrchestratorConflictError("Der Plan wurde bereits entschieden oder verändert")
            self.db.execute(
                """INSERT INTO orchestration_approvals_127(
                   approval_id,plan_id,task_id,case_id,approval_type,decision,reason,actor,created_at)
                   VALUES(?,?,NULL,?,'plan','approved',?,?,?)""",
                (new_id("approval127"), plan_id, case_id, str(reason or "")[:1000], actor, now_ts()),
            )
        self.audit.log("approve_plan", "intelligence_orchestrator_127", plan_id, case_id, {"actor": actor})
        return self.get_plan(case_id, plan_id)

    def reject_plan(self, *, case_id: str, plan_id: str, actor: str, reason: str) -> dict[str, Any]:
        if len(str(reason or "").strip()) < 3:
            raise OrchestratorValidationError("Eine Begründung ist erforderlich")
        with self.db.transaction(immediate=True):
            changed = self.db.execute(
                """UPDATE orchestration_plans_127 SET status='rejected',updated_at=?
                   WHERE plan_id=? AND case_id=? AND status IN ('draft','review_required','approved')""",
                (now_ts(), plan_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Plan kann nicht mehr verworfen werden")
            self.db.execute(
                """INSERT INTO orchestration_approvals_127(
                   approval_id,plan_id,task_id,case_id,approval_type,decision,reason,actor,created_at)
                   VALUES(?,?,NULL,?,'plan','rejected',?,?,?)""",
                (new_id("approval127"), plan_id, case_id, str(reason)[:1000], actor, now_ts()),
            )
        self.audit.log("reject_plan", "intelligence_orchestrator_127", plan_id, case_id, {"reason": str(reason)[:200]})
        return self.get_plan(case_id, plan_id)

    def scan_untrusted_sources(self, *, case_id: str, plan_id: str) -> dict[str, Any]:
        """Scan stored intake text as data, never as executable instructions."""
        rows = self.db.all(
            "SELECT intake_id,title,snippet,raw_payload_json FROM provider_intake_120 WHERE case_id=? ORDER BY created_at DESC LIMIT 200",
            (case_id,),
        )
        events = 0
        flagged_ids: list[str] = []
        with self.db.transaction(immediate=True):
            for row in rows:
                content = "\n".join(str(row.get(key) or "") for key in ("title", "snippet", "raw_payload_json"))[:20000]
                flags = self._flags(content)
                if not flags:
                    continue
                source_id = str(row.get("intake_id") or "")
                existing = self.db.one(
                    "SELECT event_id FROM orchestration_injection_events_127 WHERE case_id=? AND plan_id=? AND source_kind='provider_intake' AND source_id=? AND content_sha256=?",
                    (case_id, plan_id, source_id, self._sha(content)),
                )
                if existing:
                    flagged_ids.append(source_id)
                    continue
                self.db.execute(
                    """INSERT INTO orchestration_injection_events_127(
                      event_id,case_id,plan_id,source_kind,source_id,flags_json,action,content_sha256,created_at)
                      VALUES(?,?,?,'provider_intake',?,?,'quarantined_as_untrusted_data',?,?)""",
                    (new_id("inj127"), case_id, plan_id, source_id, dumps(flags), self._sha(content), now_ts()),
                )
                events += 1
                flagged_ids.append(source_id)
        if events:
            self.audit.log("quarantine_injection_content", "intelligence_orchestrator_127", plan_id, case_id, {"event_count": events})
        return {"scanned": len(rows), "flagged": len(flagged_ids), "source_ids": flagged_ids}

    def pause_plan(self, *, case_id: str, plan_id: str, actor: str, reason: str = "") -> dict[str, Any]:
        with self.db.transaction(immediate=True):
            changed = self.db.execute(
                """UPDATE orchestration_plans_127 SET status='paused',updated_at=?
                   WHERE plan_id=? AND case_id=? AND status='approved'""",
                (now_ts(), plan_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Nur ein freigegebener, noch nicht gestarteter Plan kann pausiert werden")
        self.audit.log("pause_plan", "intelligence_orchestrator_127", plan_id, case_id, {"reason": str(reason or "")[:200]})
        return self.get_plan(case_id, plan_id)

    def resume_plan(self, *, case_id: str, plan_id: str, actor: str) -> dict[str, Any]:
        with self.db.transaction(immediate=True):
            changed = self.db.execute(
                """UPDATE orchestration_plans_127 SET status='approved',updated_at=?
                   WHERE plan_id=? AND case_id=? AND status='paused'""",
                (now_ts(), plan_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Nur ein pausierter Plan kann fortgesetzt werden")
        self.audit.log("resume_plan", "intelligence_orchestrator_127", plan_id, case_id, {})
        return self.get_plan(case_id, plan_id)

    def execute_plan(self, *, case_id: str, plan_id: str, actor: str = "local-analyst") -> dict[str, Any]:
        started = self._clock()
        run_id = new_id("run127")
        started_at = now_ts()
        with self.db.transaction(immediate=True):
            plan = self.db.one("SELECT * FROM orchestration_plans_127 WHERE plan_id=? AND case_id=?", (plan_id, case_id))
            if not plan:
                raise OrchestratorValidationError("Plan nicht gefunden")
            if plan["status"] != "approved":
                raise OrchestratorConflictError("Nur ausdrücklich freigegebene Pläne dürfen ausgeführt werden")
            changed = self.db.execute(
                "UPDATE orchestration_plans_127 SET status='running',updated_at=? WHERE plan_id=? AND case_id=? AND status='approved'",
                (now_ts(), plan_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Plan wurde parallel verändert")
            self.db.execute(
                """INSERT INTO orchestration_runs_127(
                  run_id,plan_id,case_id,status,task_budget,attempt_no,max_attempts,model_key,
                  model_version,prompt_bundle_sha256,started_by,started_at)
                  VALUES(?,?,?,'running',?,1,2,?,?,?,?,?)""",
                (
                    run_id, plan_id, case_id, int(plan["max_tasks"]),
                    self.model_adapter.model_key, self.model_adapter.model_version,
                    self._sha("|".join(task.agent_key + ":1.0" for task in self.TASK_TEMPLATES[: int(plan["max_tasks"])])),
                    actor, started_at,
                ),
            )

        injection_scan = self.scan_untrusted_sources(case_id=case_id, plan_id=plan_id)
        tasks = self.db.all(
            "SELECT * FROM orchestration_tasks_127 WHERE plan_id=? AND case_id=? ORDER BY sequence_no LIMIT ?",
            (plan_id, case_id, int(plan["max_tasks"])),
        )
        completed = 0
        attempted = 0
        reports: list[dict[str, Any]] = []
        final_status = "completed"
        try:
            for task in tasks:
                elapsed = self._clock() - started
                if elapsed > int(plan["max_runtime_seconds"]):
                    final_status = "budget_exhausted"
                    break
                if int(task["external_action"]):
                    self.db.execute(
                        "UPDATE orchestration_tasks_127 SET status='blocked_external',error_text='Build 127 blocks autonomous external actions',updated_at=? WHERE task_id=?",
                        (now_ts(), task["task_id"]),
                    )
                    continue
                attempted += 1
                self.db.execute(
                    "UPDATE orchestration_tasks_127 SET status='running',started_at=?,updated_at=? WHERE task_id=? AND status='planned'",
                    (now_ts(), now_ts(), task["task_id"]),
                )
                raw_result = self._execute_local_task(case_id, plan, task)
                refs = raw_result.pop("source_refs", [])
                envelope = ModelEnvelope(
                    case_id=case_id,
                    agent_key=str(task["agent_key"]),
                    prompt_version="1.0",
                    policy={"trust_state": "suggestions_only", "external_network": "blocked"},
                    input_data=raw_result,
                    source_refs=tuple(refs),
                )
                model_result = self.model_adapter.complete(envelope)
                if model_result.external_network_used:
                    raise OrchestratorValidationError("Build 127 blockiert Modelladapter mit externem Netzwerkzugriff")
                result = model_result.content
                output_id = new_id("output127")
                completed_at = now_ts()
                with self.db.transaction(immediate=True):
                    self.db.execute(
                        """UPDATE orchestration_tasks_127
                           SET status='completed',result_json=?,completed_at=?,updated_at=?
                           WHERE task_id=? AND plan_id=? AND case_id=?""",
                        (dumps(result), completed_at, completed_at, task["task_id"], plan_id, case_id),
                    )
                    self.db.execute(
                        """INSERT INTO orchestration_outputs_127(
                          output_id,run_id,task_id,plan_id,case_id,agent_key,output_type,
                          content_json,source_refs_json,trust_state,review_status,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?,'suggestions_only','pending',?)""",
                        (
                            output_id,
                            run_id,
                            task["task_id"],
                            plan_id,
                            case_id,
                            task["agent_key"],
                            task["task_type"],
                            dumps(result),
                            dumps(refs),
                            completed_at,
                        ),
                    )
                reports.append({"task_id": task["task_id"], "output_id": output_id, "agent_key": task["agent_key"]})
                completed += 1
        except Exception as exc:
            final_status = "failed"
            self.db.execute(
                "UPDATE orchestration_tasks_127 SET status='failed',error_text=?,updated_at=? WHERE plan_id=? AND case_id=? AND status='running'",
                (str(exc)[:2000], now_ts(), plan_id, case_id),
            )
            raise
        finally:
            runtime_ms = max(0, int((self._clock() - started) * 1000))
            completed_at = now_ts()
            report = {
                "mode": "local_deterministic",
                "trust_state": "suggestions_only",
                "tasks": reports,
                "external_actions": 0,
                "prompt_injection_scan": injection_scan,
                "limitations": [
                    "Keine autonome Webrecherche.",
                    "Keine Identitäts-, Schuld- oder Risikobestätigung.",
                    "Alle Ausgaben benötigen menschliches Review.",
                ],
            }
            with self.db.transaction(immediate=True):
                self.db.execute(
                    """UPDATE orchestration_runs_127
                       SET status=?,tasks_attempted=?,tasks_completed=?,external_actions=0,
                           runtime_ms=?,report_json=?,completed_at=? WHERE run_id=?""",
                    (final_status, attempted, completed, runtime_ms, dumps(report), completed_at, run_id),
                )
                self.db.execute(
                    "UPDATE orchestration_plans_127 SET status=?,updated_at=? WHERE plan_id=? AND case_id=?",
                    (final_status, completed_at, plan_id, case_id),
                )
            self.audit.log(
                "execute_plan",
                "intelligence_orchestrator_127",
                run_id,
                case_id,
                {"plan_id": plan_id, "status": final_status, "attempted": attempted, "completed": completed, "external_actions": 0},
            )
        return self.get_run(case_id, run_id)

    def _counts(self, case_id: str) -> dict[str, int]:
        queries = {
            "targets": "SELECT COUNT(*) AS n FROM targets WHERE case_id=?",
            "search_tasks": "SELECT COUNT(*) AS n FROM search_tasks WHERE case_id=?",
            "intake_new": "SELECT COUNT(*) AS n FROM provider_intake_120 WHERE case_id=? AND review_status='new'",
            "evidence_packages": "SELECT COUNT(*) AS n FROM evidence_packages_121 WHERE case_id=?",
            "entities": "SELECT COUNT(*) AS n FROM resolution_entities_115 WHERE case_id=?",
            "merge_proposals": "SELECT COUNT(*) AS n FROM resolution_merge_proposals_115 WHERE case_id=? AND state NOT IN ('confirmed','rejected')",
            "relations": "SELECT COUNT(*) AS n FROM graph_relations_116 WHERE case_id=?",
            "timeline": "SELECT COUNT(*) AS n FROM timeline_events_117 WHERE case_id=?",
            "contradictions": "SELECT COUNT(*) AS n FROM contradictions_118 WHERE case_id=? AND state NOT IN ('resolved','dismissed')",
            "research_strategies": "SELECT COUNT(*) AS n FROM research_strategy_runs_128 WHERE case_id=?",
            "source_records": "SELECT COUNT(*) AS n FROM source_records_128 WHERE case_id=?",
            "source_clusters": "SELECT COUNT(*) AS n FROM source_clusters_128 WHERE case_id=?",
            "graph_analysis_runs": "SELECT COUNT(*) AS n FROM graph_analysis_runs_130 WHERE case_id=?",
            "hypotheses": "SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=?",
            "hypotheses_review": "SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=? AND state='needs_review'",
            "red_team_pending": "SELECT COUNT(*) AS n FROM red_team_reviews_130 WHERE case_id=? AND review_status='pending'",
            "unsubstantiated_claims": "SELECT COUNT(*) AS n FROM hypothesis_claims_130 c LEFT JOIN hypothesis_evidence_130 e ON e.claim_id=c.claim_id WHERE c.case_id=? AND e.link_id IS NULL",
            "synthesis_reports": "SELECT COUNT(*) AS n FROM report_drafts_131 WHERE case_id=?",
            "synthesis_stale": "SELECT COUNT(*) AS n FROM report_drafts_131 WHERE case_id=? AND stale=1",
            "synthesis_open_gaps": "SELECT COUNT(*) AS n FROM intelligence_gaps_131 WHERE case_id=? AND status='open'",
            "report_unsubstantiated": "SELECT COUNT(*) AS n FROM report_claims_131 WHERE case_id=? AND verification_state='unsubstantiated'",
            "report_contested": "SELECT COUNT(*) AS n FROM report_claims_131 WHERE case_id=? AND verification_state='contested'",
            "governance_pending_approvals": "SELECT COUNT(*) AS n FROM governance_approval_requests_132 WHERE case_id=? AND status='pending'",
            "governance_failed_executions": "SELECT COUNT(*) AS n FROM governance_approval_requests_132 WHERE case_id=? AND execution_status='failed'",
            "governance_active_locks": "SELECT COUNT(*) AS n FROM governance_object_locks_132 WHERE case_id=? AND active=1",
            "governance_active_assignments": "SELECT COUNT(*) AS n FROM governance_case_assignments_132 WHERE case_id=? AND active=1",
            "phase4_connector_advice": "SELECT COUNT(*) AS n FROM connector_routing_advice_134 WHERE case_id=?",
            "phase4_connector_advice_pending": "SELECT COUNT(*) AS n FROM connector_routing_advice_134 WHERE case_id=? AND review_status='pending'",
        }
        result: dict[str, int] = {}
        for key, sql in queries.items():
            try:
                result[key] = int((self.db.one(sql, (case_id,)) or {}).get("n") or 0)
            except Exception:
                result[key] = 0
        return result

    def _execute_local_task(self, case_id: str, plan: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        agent = task["agent_key"]
        counts = self._counts(case_id)
        base_refs: list[dict[str, str]] = [{"object_type": "case", "object_id": case_id}]
        if plan.get("target_id"):
            base_refs.append({"object_type": "target", "object_id": str(plan["target_id"])})
        if agent == "research_planner":
            gaps: list[str] = []
            if counts["targets"] == 0:
                gaps.append("Person oder Entität erfassen")
            if counts["search_tasks"] == 0:
                gaps.append("adaptive personenspezifische Recherche erzeugen")
            if counts["intake_new"]:
                gaps.append(f"{counts['intake_new']} neue Intake-Kandidaten prüfen")
            if counts["search_tasks"] and counts["evidence_packages"] == 0:
                gaps.append("relevante Funde kontrolliert in Intake und Evidence überführen")
            if counts.get("phase4_connector_advice", 0) == 0:
                gaps.append("vertrauenswürdige Connectoren anhand Ankertyp, Zustand und Datenminimierung priorisieren")
            latest_coverage = self.db.one("SELECT coverage_score,open_gaps_json,metrics_json FROM research_coverage_128 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)) or {}
            coverage_gaps = loads(latest_coverage.get("open_gaps_json"), []) if latest_coverage else []
            for item in coverage_gaps[:6]:
                if item not in gaps:
                    gaps.append(str(item))
            return {"summary": "Begrenzter Rechercheplan", "counts": counts, "research_intelligence": {"coverage_score": int(latest_coverage.get("coverage_score") or 0), "open_gaps": coverage_gaps, "source_clusters": counts.get("source_clusters", 0)}, "recommended_next_steps": gaps[:8] or ["Bestehende Quellen gegenprüfen"], "source_refs": base_refs}
        if agent == "source_analyst":
            rows = self.db.all(
                "SELECT url,created_at FROM provider_intake_120 WHERE case_id=? ORDER BY created_at DESC LIMIT 200",
                (case_id,),
            )
            hosts = Counter((urlsplit(str(row.get("url") or "")).hostname or "unbekannt").casefold() for row in rows)
            refs = base_refs + [{"object_type": "intake", "object_id": str(row.get("intake_id"))} for row in self.db.all("SELECT intake_id FROM provider_intake_120 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))]
            dependency_clusters = self.db.all("SELECT cluster_id,cluster_kind,member_count,independent_count,rationale FROM source_clusters_128 WHERE case_id=? ORDER BY member_count DESC LIMIT 20", (case_id,))
            source_roles = self.db.all("SELECT source_role,COUNT(*) AS n FROM source_records_128 WHERE case_id=? GROUP BY source_role ORDER BY n DESC", (case_id,))
            return {"summary": "Lokales Quelleninventar", "source_count": len(rows), "host_clusters": hosts.most_common(20), "source_roles": source_roles, "dependency_clusters": dependency_clusters, "review_questions": ["Welche Quellen sind voneinander unabhängig?", "Welche Primärquelle liegt der Zitierkette zugrunde?", "Welche Angaben sind zeitlich veraltet?", "Welche Treffer sind nur Kopien derselben Ursprungsquelle?"], "source_refs": refs}
        if agent == "verification_analyst":
            intake = self.db.all("SELECT intake_id,title,url FROM provider_intake_120 WHERE case_id=? AND review_status='new' ORDER BY created_at DESC LIMIT 20", (case_id,))
            refs = base_refs + [{"object_type": "intake", "object_id": str(row["intake_id"])} for row in intake]
            hypotheses = self.db.all("SELECT hypothesis_id,title,state FROM hypotheses_130 WHERE case_id=? ORDER BY updated_at DESC LIMIT 20", (case_id,)) if counts.get("hypotheses") else []
            refs += [{"object_type": "hypothesis", "object_id": str(row["hypothesis_id"])} for row in hypotheses]
            return {"summary": "Gegenprüfungsplan", "candidates": len(intake), "hypotheses": len(hypotheses), "unsubstantiated_claims": counts.get("unsubstantiated_claims", 0), "questions": ["Welche unabhängige Quelle bestätigt denselben konkreten Claim?", "Welche alternative Person oder Organisation könnte gemeint sein?", "Welche Information würde die aktuelle Zuordnung widerlegen?", "Sind Veröffentlichungs- und Ereignisdatum getrennt?", "Welche Hypothese besitzt noch keinen dokumentierten Gegenbeleg?"], "source_refs": refs}
        if agent == "entity_analyst":
            proposals = self.db.all("SELECT proposal_id,canonical_entity_id,candidate_entity_id,state FROM resolution_merge_proposals_115 WHERE case_id=? ORDER BY requested_at DESC LIMIT 30", (case_id,))
            refs = base_refs + [{"object_type": "merge_proposal", "object_id": str(row["proposal_id"])} for row in proposals]
            return {"summary": "Identitäts-Review", "open_merge_proposals": len([p for p in proposals if p.get("state") not in {"confirmed", "rejected"}]), "review_dimensions": ["Name und Schreibvarianten", "Ort und Zeitraum", "Organisation und Rolle", "Username/E-Mail-Kontext", "Gegenbelege und Namensdoppler"], "automatic_merge": False, "source_refs": refs}
        if agent == "timeline_analyst":
            rows = self.db.all("SELECT event_id,start_date,end_date,title,state FROM timeline_events_117 WHERE case_id=? ORDER BY start_date LIMIT 100", (case_id,))
            refs = base_refs + [{"object_type": "timeline", "object_id": str(row["event_id"])} for row in rows]
            missing = sum(1 for row in rows if not row.get("start_date"))
            candidate = sum(1 for row in rows if str(row.get("state") or "").casefold() not in {"confirmed", "reviewed"})
            return {"summary": "Timeline-Review", "events": len(rows), "missing_start_dates": missing, "unreviewed_events": candidate, "questions": ["Welche Angaben sind Ereigniszeit und welche nur Veröffentlichungszeit?", "Gibt es unmögliche Überschneidungen?", "Welche Zeiträume bleiben unbelegt?"], "source_refs": refs}
        if agent == "contradiction_analyst":
            rows = self.db.all("SELECT contradiction_id,conflict_type,title,severity,state FROM contradictions_118 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))
            refs = base_refs + [{"object_type": "contradiction", "object_id": str(row["contradiction_id"])} for row in rows]
            hypothesis_rows = self.db.all("SELECT hypothesis_id,title,state FROM hypotheses_130 WHERE case_id=? ORDER BY updated_at DESC LIMIT 20", (case_id,)) if counts.get("hypotheses") else []
            refs += [{"object_type": "hypothesis", "object_id": str(row["hypothesis_id"])} for row in hypothesis_rows]
            return {"summary": "Widerspruchs- und Hypothesen-Review", "open": len([r for r in rows if r.get("state") not in {"resolved", "dismissed"}]), "hypotheses": len(hypothesis_rows), "red_team_pending": counts.get("red_team_pending", 0), "items": rows[:20], "red_team_questions": ["Welche alternative Erklärung passt ebenfalls zu den Daten?", "Ist der Widerspruch nur ein Versions- oder Datumsproblem?", "Stammen scheinbar unabhängige Quellen aus derselben Ursprungskette?", "Welche Beobachtung würde die bevorzugte Hypothese falsifizieren?", "Wird strukturelle Graphnähe fälschlich als reale Beziehung interpretiert?"], "source_refs": refs}
        snapshot = self.workspace.case_snapshot(case_id)
        refs = base_refs
        return {
            "summary": "Quellengebundener Arbeitsstand",
            "objective": str(plan.get("objective") or ""),
            "snapshot": snapshot,
            "graph_hypothesis_status": {"analysis_runs": counts.get("graph_analysis_runs", 0), "hypotheses": counts.get("hypotheses", 0), "hypotheses_review": counts.get("hypotheses_review", 0), "red_team_pending": counts.get("red_team_pending", 0), "unsubstantiated_claims": counts.get("unsubstantiated_claims", 0)},
            "investigative_synthesis_status": {"reports": counts.get("synthesis_reports", 0), "stale_reports": counts.get("synthesis_stale", 0), "open_gaps": counts.get("synthesis_open_gaps", 0), "unsubstantiated_report_claims": counts.get("report_unsubstantiated", 0), "contested_report_claims": counts.get("report_contested", 0), "automatic_export": False, "external_actions": 0},
            "collaboration_governance_status": {"pending_four_eyes_approvals": counts.get("governance_pending_approvals", 0), "failed_approval_executions": counts.get("governance_failed_executions", 0), "active_object_locks": counts.get("governance_active_locks", 0), "active_case_assignments": counts.get("governance_active_assignments", 0), "automatic_approvals": False, "automatic_permission_changes": False, "external_actions": 0},
            "phase4_operational_intelligence": {"connector_advice": counts.get("phase4_connector_advice", 0), "pending_connector_advice": counts.get("phase4_connector_advice_pending", 0), "connector_code_execution": False, "automatic_provider_runs": False, "external_actions": 0},
            "limitations": ["Gespeicherte Kandidaten sind keine unabhängig bestätigten Tatsachen.", "Graphzentralität ist keine reale Einfluss-, Schuld- oder Gefährlichkeitsbewertung.", "Identität, Kausalität und Schuld werden nicht automatisch bestätigt.", "Vor Export oder Bericht ist menschliches Review erforderlich.", "Kritische Freigaben im Teammodus benötigen eine andere autorisierte Person; AI darf sie nicht erteilen."],
            "source_refs": refs,
        }

    def review_output(
        self,
        *,
        case_id: str,
        output_id: str,
        decision: str,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        decision = decision.strip().casefold()
        if decision not in {"accepted_for_working_notes", "rejected", "needs_revision"}:
            raise OrchestratorValidationError("Ungültige Reviewentscheidung")
        if len(str(reason or "").strip()) < 3:
            raise OrchestratorValidationError("Eine Reviewbegründung ist erforderlich")
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM orchestration_outputs_127 WHERE output_id=? AND case_id=?", (output_id, case_id))
            if not row:
                raise OrchestratorValidationError("Orchestrator-Ausgabe nicht gefunden")
            changed = self.db.execute(
                """UPDATE orchestration_outputs_127
                   SET review_status=?,reviewed_by=?,reviewed_at=?,review_reason=?
                   WHERE output_id=? AND case_id=? AND review_status='pending'""",
                (decision, actor, now_ts(), str(reason)[:1000], output_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Ausgabe wurde bereits reviewed")
        self.audit.log("review_output", "intelligence_orchestrator_127", output_id, case_id, {"decision": decision})
        return self.get_output(case_id, output_id)

    def cancel_plan(self, *, case_id: str, plan_id: str, actor: str, reason: str) -> dict[str, Any]:
        with self.db.transaction(immediate=True):
            changed = self.db.execute(
                """UPDATE orchestration_plans_127 SET status='cancelled',updated_at=?
                   WHERE plan_id=? AND case_id=? AND status IN ('draft','review_required','approved')""",
                (now_ts(), plan_id, case_id),
            )
            if changed.rowcount != 1:
                raise OrchestratorConflictError("Plan kann nicht abgebrochen werden")
            self.db.execute(
                "UPDATE orchestration_tasks_127 SET status='cancelled',updated_at=? WHERE plan_id=? AND case_id=? AND status='planned'",
                (now_ts(), plan_id, case_id),
            )
        self.audit.log("cancel_plan", "intelligence_orchestrator_127", plan_id, case_id, {"reason": str(reason or "")[:200]})
        return self.get_plan(case_id, plan_id)

    def get_plan(self, case_id: str, plan_id: str) -> dict[str, Any]:
        plan = self.db.one("SELECT * FROM orchestration_plans_127 WHERE plan_id=? AND case_id=?", (plan_id, case_id))
        if not plan:
            raise OrchestratorValidationError("Plan nicht gefunden")
        plan["injection_flags"] = loads(plan.pop("injection_flags_json", "[]"), [])
        plan["tasks"] = self.db.all("SELECT * FROM orchestration_tasks_127 WHERE plan_id=? AND case_id=? ORDER BY sequence_no", (plan_id, case_id))
        return plan

    def get_run(self, case_id: str, run_id: str) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM orchestration_runs_127 WHERE run_id=? AND case_id=?", (run_id, case_id))
        if not run:
            raise OrchestratorValidationError("Lauf nicht gefunden")
        run["report"] = loads(run.pop("report_json", "{}"), {})
        run["outputs"] = self.list_outputs(case_id, run_id=run_id, limit=100)
        return run

    def get_output(self, case_id: str, output_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM orchestration_outputs_127 WHERE output_id=? AND case_id=?", (output_id, case_id))
        if not row:
            raise OrchestratorValidationError("Ausgabe nicht gefunden")
        row["content"] = loads(row.pop("content_json", "{}"), {})
        row["source_refs"] = loads(row.pop("source_refs_json", "[]"), [])
        return row

    def list_plans(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM orchestration_plans_127 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 500))))

    def list_runs(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM orchestration_runs_127 WHERE case_id=? ORDER BY started_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 500))))

    def list_outputs(self, case_id: str, *, run_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if run_id:
            return self.db.all("SELECT * FROM orchestration_outputs_127 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT ?", (case_id, run_id, max(1, min(int(limit), 500))))
        return self.db.all("SELECT * FROM orchestration_outputs_127 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 500))))

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._require_case(case_id)
        metrics = {}
        for key, sql in {
            "plans": "SELECT COUNT(*) AS n FROM orchestration_plans_127 WHERE case_id=?",
            "approved": "SELECT COUNT(*) AS n FROM orchestration_plans_127 WHERE case_id=? AND status='approved'",
            "pending_outputs": "SELECT COUNT(*) AS n FROM orchestration_outputs_127 WHERE case_id=? AND review_status='pending'",
            "completed_runs": "SELECT COUNT(*) AS n FROM orchestration_runs_127 WHERE case_id=? AND status='completed'",
            "injection_events": "SELECT COUNT(*) AS n FROM orchestration_injection_events_127 WHERE case_id=?",
        }.items():
            metrics[key] = int((self.db.one(sql, (case_id,)) or {}).get("n") or 0)
        return {"status": self.status(), "metrics": metrics, "agents": self.list_agents(), "plans": self.list_plans(case_id, 50), "runs": self.list_runs(case_id, 50), "outputs": self.list_outputs(case_id, limit=100)}
