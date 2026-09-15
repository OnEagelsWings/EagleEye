from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from eagleeye.kernel.contracts import ActionClass, AgentRole, AgentTask, ApprovalState, GatewayKind

POLICY_VERSION = "phase15.investigation-supervisor.v356"
DOSSIER_VERSION = "phase15.evidence-dossier.v356"
GO_TOKEN = "GO"
MAX_ROWS_PER_DOMAIN = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value not in (None, "") else default
    except Exception:
        return default


def _clip(text: Any, limit: int = 1200) -> str:
    return " ".join(str(text or "").split())[:limit]


def _speech_text(text: str) -> str:
    # Local browser speech output should not read URLs, hashes or opaque IDs aloud.
    value = re.sub(r"https?://\S+", " Quelle ", str(text or ""), flags=re.I)
    value = re.sub(r"\b[a-f0-9]{32,64}\b", " Prüfsumme ", value, flags=re.I)
    value = re.sub(r"\b(?:obj|src|job|crawl|search|agt|agr|media|case)_[A-Za-z0-9_-]+\b", " Referenz ", value)
    return re.sub(r"\s+", " ", value).strip()[:7000]


class InvestigationSupervisor356:
    """Evidence-first case supervisor for Phase 15.

    The supervisor has read access to case-scoped stores and may enqueue already
    approved research after an explicit GO. It cannot execute network requests,
    mutate proxy/Tor/firewall/OS state, approve sources, merge identities, export,
    delete or release findings.
    """

    def __init__(self, db: Any, *, build355: Any, task_repository: Any, cases: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.build355 = build355
        self.task_repository = task_repository
        self.cases = cases
        self.actor = actor
        self._ensure_prompt_template()

    def _ensure_prompt_template(self) -> None:
        key = "phase15_investigation_supervisor_356"
        if self.db.one("SELECT template_id FROM ai_prompt_templates WHERE template_key=?", (key,)):
            return
        self.db.execute(
            "INSERT INTO ai_prompt_templates(template_id,template_key,title,description,guardrail_profile,created_at,active) VALUES(?,?,?,?,?,?,1)",
            (
                "prompt356_" + uuid.uuid4().hex[:16], key,
                "Phase 15 Investigation Supervisor 356",
                "Fuse reviewed evidence, sources, crawler/parser/media/graph/timeline state into a dossier. Separate facts, observations, hypotheses, counterevidence, uncertainty and open questions. Never auto-confirm identity, location or guilt. External research may be delegated only after explicit GO and only to already-approved governed sources.",
                "evidence_first_go_gated_candidate_only_no_identity_or_scene_confirmation",
                _now(),
            ),
        )

    def _table(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            return self.db.all(sql, params)
        except Exception:
            return []

    def create_intake(
        self,
        *,
        case_id: str,
        objective: str,
        key_questions: list[str] | None = None,
        scope_notes: str = "",
        source_constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        self.cases.get_case(case_id)
        objective = _clip(objective, 2000)
        if not objective:
            raise ValueError("objective is required")
        questions = [_clip(x, 600) for x in (key_questions or []) if _clip(x, 600)][:20]
        constraints = [_clip(x, 400) for x in (source_constraints or []) if _clip(x, 400)][:20]
        task = AgentTask.create(
            case_id=case_id,
            actor=self.actor,
            agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.LOCAL_ANALYSIS,
            requested_gateway=GatewayKind.NONE,
            approval_state=ApprovalState.NOT_REQUIRED,
            input_payload={
                "kind": "case_intake_v356",
                "objective": objective,
                "key_questions": questions,
                "scope_notes": _clip(scope_notes, 2000),
                "source_constraints": constraints,
                "external_research_authorized": False,
                "policy_version": POLICY_VERSION,
            },
        )
        self.task_repository.create_task(task)
        self.db.execute(
            "INSERT INTO ai_summaries(summary_id,case_id,task_id,summary_type,title,body,metrics_json,source_object_ids_json,guardrail_status,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                "sum356_" + uuid.uuid4().hex[:18], case_id, task.task_id, "intake", "Investigation Intake",
                objective, _canon({"question_count": len(questions), "go_required": True}), "[]", "passed", _now(),
                "External research remains disabled until explicit GO.",
            ),
        )
        return task.to_dict()

    def latest_intake(self, case_id: str) -> dict[str, Any] | None:
        rows = self._rows("SELECT task_json FROM phase15_agent_tasks WHERE case_id=? AND agent_role='investigation_supervisor' AND action_class='local_analysis' ORDER BY created_at DESC LIMIT 50", (case_id,))
        for row in rows:
            data = _json(row.get("task_json"), {})
            if data.get("input_payload", {}).get("kind") == "case_intake_v356":
                return data
        return None

    def _approved_crawler_sources(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT s.source_id,s.source_kind,s.locator,s.display_name,s.review_status,s.risk_class,p.enabled,p.source_health,p.auth_type,p.allowed_hosts_json "
            "FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id "
            "WHERE s.review_status='approved_read_only' AND p.enabled=1 AND p.auth_type='none' ORDER BY s.created_at ASC"
        )

    def start_go(self, *, case_id: str, go: str, intake_task_id: str | None = None) -> dict[str, Any]:
        self.cases.get_case(case_id)
        if str(go or "").strip().upper() != GO_TOKEN:
            raise PermissionError("exact GO approval required")
        intake = self.latest_intake(case_id)
        if not intake:
            raise ValueError("case intake required before GO")
        if intake_task_id and intake.get("task_id") != intake_task_id:
            raise ValueError("intake task mismatch")
        existing_go = self.active_go(case_id)
        if existing_go and existing_go.get("input_payload", {}).get("intake_task_id") == intake.get("task_id"):
            return {"go_task_id": existing_go.get("task_id"), "state": "research_wave_already_active", "enqueued": [], "skipped": [], "network_executed_by_supervisor": False, "worker_gateway_required": True, "source_approval_changed": False}
        task = AgentTask.create(
            case_id=case_id,
            actor=self.actor,
            agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.EXTERNAL_RESEARCH,
            requested_gateway=GatewayKind.SEARCH,
            approval_state=ApprovalState.APPROVED,
            input_payload={
                "kind": "research_wave_go_v356",
                "intake_task_id": intake.get("task_id"),
                "objective": intake.get("input_payload", {}).get("objective", ""),
                "explicit_go": True,
                "allowed_scope": "already_human_reviewed_governed_sources_only",
                "new_source_approval_allowed": False,
                "identity_merge_allowed": False,
                "export_allowed": False,
                "release_allowed": False,
                "policy_version": POLICY_VERSION,
            },
        )
        self.task_repository.create_task(task)
        enqueued: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        explicit_source_ids = {str(x).split(":",1)[1].strip() for x in intake.get("input_payload", {}).get("source_constraints", []) if str(x).startswith("source_id:") and ":" in str(x)}
        for source in self._approved_crawler_sources():
            if explicit_source_ids and source["source_id"] not in explicit_source_ids:
                continue
            try:
                result = self.build355.enqueue_crawl(case_id=case_id, source_id=source["source_id"])
                job = result.get("job") or {}
                enqueued.append({"source_id": source["source_id"], "job_id": job.get("job_id", ""), "crawl_run_id": result.get("crawl_run_id", ""), "search_run_id": result.get("search_run_id", ""), "source_kind": source.get("source_kind", "")})
            except Exception as exc:
                skipped.append({"source_id": source["source_id"], "reason": _clip(exc, 400)})
        return {
            "go_task_id": task.task_id,
            "state": "research_wave_started",
            "enqueued": enqueued,
            "skipped": skipped,
            "network_executed_by_supervisor": False,
            "worker_gateway_required": True,
            "source_approval_changed": False,
        }

    def active_go(self, case_id: str) -> dict[str, Any] | None:
        rows = self._rows("SELECT task_json FROM phase15_agent_tasks WHERE case_id=? AND action_class='external_research' AND approval_state='approved' ORDER BY created_at DESC LIMIT 50", (case_id,))
        for row in rows:
            data = _json(row.get("task_json"), {})
            if data.get("input_payload", {}).get("kind") == "research_wave_go_v356" and data.get("input_payload", {}).get("explicit_go") is True:
                return data
        return None

    def crawler_monitor(self, case_id: str) -> dict[str, Any]:
        jobs = self._rows("SELECT job_id,job_type,status,attempts,max_attempts,error_text,updated_at,result_json FROM phase15_jobs WHERE case_id=? ORDER BY created_at DESC LIMIT 250", (case_id,))
        runs = self._rows("SELECT crawl_run_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,summary_json,created_at,completed_at FROM phase15_crawl_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 250", (case_id,))
        security = self._rows("SELECT security_event_id,search_run_id,event_type,disposition,severity,evidence_json,created_at FROM phase15_security_events WHERE case_id=? ORDER BY created_at DESC LIMIT 250", (case_id,))
        parse = self._rows("SELECT p.parse_run_id,p.object_id,p.source_id,p.status,p.record_count,p.warnings_json,p.error_text,p.created_at FROM phase15_parse_runs p JOIN phase15_objects o ON o.object_id=p.object_id WHERE o.case_id=? ORDER BY p.created_at DESC LIMIT 250", (case_id,))
        state_counts: dict[str, int] = {}
        for j in jobs: state_counts[j.get("status", "unknown")] = state_counts.get(j.get("status", "unknown"), 0) + 1
        blocked = [x for x in security if x.get("disposition") in {"block", "quarantine", "deny"}]
        parser_errors = [x for x in parse if x.get("status") not in {"ok", "parsed", "completed", "succeeded"}]
        attention = []
        if state_counts.get("dead_letter", 0): attention.append("dead_letter_jobs")
        if state_counts.get("failed", 0): attention.append("failed_jobs")
        if blocked: attention.append("opsec_or_content_blocks")
        if parser_errors: attention.append("parser_errors_or_warnings")
        return {
            "job_states": state_counts,
            "jobs_total": len(jobs),
            "crawl_runs": len(runs),
            "pages_fetched": sum(int(r.get("pages_fetched") or 0) for r in runs),
            "pages_stored": sum(int(r.get("pages_stored") or 0) for r in runs),
            "bytes_fetched": sum(int(r.get("bytes_fetched") or 0) for r in runs),
            "security_blocks": len(blocked),
            "parse_problem_count": len(parser_errors),
            "attention": attention,
            "supervisor_may_change_network_configuration": False,
        }

    def collect_case_snapshot(self, case_id: str) -> dict[str, Any]:
        case = self.cases.get_case(case_id)
        targets = self._rows("SELECT * FROM targets WHERE case_id=? ORDER BY created_at", (case_id,))
        evidence = self._rows("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        review = self._rows("SELECT * FROM review_items WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        nodes = self._rows("SELECT * FROM graph_nodes WHERE case_id=? LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        edges = self._rows("SELECT * FROM graph_edges WHERE case_id=? LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        timeline = self._rows("SELECT * FROM timeline_events WHERE case_id=? ORDER BY event_date LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        hypotheses = self._rows("SELECT * FROM graph_hypotheses WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        contradictions = self._rows("SELECT * FROM graph_contradictions WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        objects = self._rows("SELECT object_id,search_run_id,source_id,sha256,size_bytes,media_type,security_state,provenance_json,created_at FROM phase15_objects WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        media = self._rows("SELECT media_id,evidence_id,media_kind,object_ref,sha256,metadata_json,review_status,created_at FROM phase15_media_assets WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        links = self._rows("SELECT * FROM phase15_object_links WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        search_runs = self._rows("SELECT * FROM phase15_search_runs WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        crawl_runs = self._rows("SELECT * FROM phase15_crawl_runs WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        jobs = self._rows("SELECT job_id,job_type,search_run_id,status,attempts,max_attempts,checkpoint_json,result_json,error_text,created_at,updated_at FROM phase15_jobs WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        parse_runs = self._rows("SELECT p.* FROM phase15_parse_runs p JOIN phase15_objects o ON o.object_id=p.object_id WHERE o.case_id=? ORDER BY p.created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        search_docs = self._rows("SELECT doc_id,object_id,source_id,title,body_sha256,security_state,provenance_json,created_at,updated_at FROM phase15_search_documents WHERE case_id=? ORDER BY updated_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        agent_tasks = self._rows("SELECT task_id,agent_role,action_class,approval_state,task_json,created_at FROM phase15_agent_tasks WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        ai_hyp = self._rows("SELECT * FROM ai_hypothesis_suggestions WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        ai_contra = self._rows("SELECT * FROM ai_contradiction_suggestions WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, MAX_ROWS_PER_DOMAIN))
        source_ids = sorted({str(x.get("source_id")) for x in objects + crawl_runs if x.get("source_id")})
        sources = []
        if source_ids:
            marks = ",".join("?" for _ in source_ids)
            sources = self._rows(f"SELECT source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_at FROM phase15_sources WHERE source_id IN ({marks})", tuple(source_ids))
        return {
            "case": case, "targets": targets, "evidence": evidence, "review_items": review,
            "graph_nodes": nodes, "graph_edges": edges, "timeline": timeline,
            "graph_hypotheses": hypotheses, "contradictions": contradictions,
            "objects": objects, "media": media, "object_links": links, "sources": sources,
            "search_runs": search_runs, "crawl_runs": crawl_runs, "jobs": jobs,
            "parse_runs": parse_runs, "search_documents": search_docs,
            "agent_tasks": agent_tasks, "ai_hypotheses": ai_hyp, "ai_contradictions": ai_contra,
            "crawler_monitor": self.crawler_monitor(case_id),
        }

    def _persist_hypothesis(self, *, case_id: str, task_id: str, hypothesis_type: str, title: str, statement: str, confidence: float, refs: list[str], notes: str) -> dict[str, Any]:
        key = _sha({"case_id": case_id, "type": hypothesis_type, "statement": statement, "refs": sorted(refs)})[:24]
        existing = self.db.one("SELECT * FROM ai_hypothesis_suggestions WHERE suggestion_id=?", ("aih356_" + key,))
        if existing:
            return existing
        row = {
            "suggestion_id": "aih356_" + key,
            "case_id": case_id,
            "task_id": task_id,
            "hypothesis_type": hypothesis_type,
            "title": _clip(title, 240),
            "statement": _clip(statement, 2000),
            "confidence": max(0.05, min(float(confidence), 0.85)),
            "status": "suggested",
            "guardrail_status": "passed_candidate_only",
            "created_at": _now(),
            "notes": _clip(notes + " | refs=" + ",".join(refs[:12]), 2500),
        }
        self.db.execute("INSERT INTO ai_hypothesis_suggestions(suggestion_id,case_id,task_id,hypothesis_type,title,statement,confidence,status,guardrail_status,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)", tuple(row[k] for k in ("suggestion_id","case_id","task_id","hypothesis_type","title","statement","confidence","status","guardrail_status","created_at","notes")))
        return row

    def form_initial_hypotheses(self, *, case_id: str, parent_task_id: str | None = None) -> list[dict[str, Any]]:
        self.cases.get_case(case_id)
        task = AgentTask.create(
            case_id=case_id, actor=self.actor, agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.LOCAL_ANALYSIS, requested_gateway=GatewayKind.NONE,
            approval_state=ApprovalState.NOT_REQUIRED,
            input_payload={"kind": "hypothesis_wave_v356", "candidate_only": True, "parent_go_task_id": parent_task_id or "", "policy_version": POLICY_VERSION},
            parent_task_id=parent_task_id,
        )
        self.task_repository.create_task(task)
        out: list[dict[str, Any]] = []
        # Cross-source structured record correlation remains a lead, never an identity merge.
        try:
            leads = self.build355.correlation_candidates(case_id=case_id)
        except Exception:
            leads = []
        for lead in leads[:60]:
            basis = str(lead.get("basis") or "cross_source_candidate")
            left, right = lead.get("left") or {}, lead.get("right") or {}
            strong = "identifier" in basis or "lei" in basis or "cik" in basis
            conf = 0.68 if strong else 0.42
            refs = [x for x in [left.get("parse_run_id"), right.get("parse_run_id"), left.get("object_id"), right.get("object_id")] if x]
            out.append(self._persist_hypothesis(case_id=case_id, task_id=task.task_id, hypothesis_type="cross_source_entity_candidate", title="Cross-source entity candidate", statement=f"Records from {left.get('source_id','source A')} and {right.get('source_id','source B')} may refer to the same entity; human review is required.", confidence=conf, refs=[str(x) for x in refs], notes=f"basis={basis}; identity_confirmed=false"))
        for link in self._rows("SELECT * FROM phase15_object_links WHERE case_id=? AND relation IN ('geolocation_hypothesis_v1','exact_duplicate_candidate','near_duplicate_candidate','visual_variant_candidate') ORDER BY created_at DESC LIMIT 100", (case_id,)):
            prov = _json(link.get("provenance_json"), {})
            relation = link.get("relation", "candidate")
            if relation == "geolocation_hypothesis_v1":
                h = prov.get("hypothesis") or prov
                label = h.get("label") or h.get("city") or h.get("country") or "unknown location"
                conf = min(float(h.get("confidence") or 0.35), 0.75)
                statement = f"Media item {link.get('from_id')} may be associated with {label}; this is a visual geolocation hypothesis, not a scene-location fact."
                htype = "visual_geolocation_candidate"
            else:
                conf = min(float(prov.get("confidence") or prov.get("similarity") or 0.45), 0.8)
                statement = f"Media items {link.get('from_id')} and {link.get('to_id')} may be duplicate/variant assets ({relation}); this does not establish identity, place or source ownership."
                htype = "media_similarity_candidate"
            out.append(self._persist_hypothesis(case_id=case_id, task_id=task.task_id, hypothesis_type=htype, title=relation.replace("_", " ").title(), statement=statement, confidence=conf, refs=[str(link.get("link_id") or "")], notes="candidate_only; human review required"))
        return out

    def _fact_rows(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        facts = []
        for e in snapshot["evidence"]:
            decision = str(e.get("review_decision") or "").lower()
            rank = str(e.get("evidence_rank") or "").lower()
            if decision in {"approved", "accepted", "promoted", "verified"} or rank in {"verified", "primary", "corroborated"}:
                facts.append({"statement": _clip(e.get("statement"), 1200), "ref": e.get("evidence_id"), "source_url": e.get("source_url") or "", "classification": "reviewed_evidence_fact"})
        return facts[:120]

    def _open_questions(self, snapshot: dict[str, Any]) -> list[str]:
        intake = self.latest_intake(snapshot["case"]["case_id"]) or {}
        questions = list(intake.get("input_payload", {}).get("key_questions") or [])
        mon = snapshot["crawler_monitor"]
        if mon.get("security_blocks"): questions.append("Welche gesperrten/isolierten Quellen oder Inhalte benötigen Security-Review?")
        if mon.get("parse_problem_count"): questions.append("Welche Parserfehler verändern die Quellenabdeckung oder Evidenzqualität?")
        if not snapshot["evidence"]: questions.append("Welche Beobachtungen können nach menschlichem Review zu Evidence-Facts promoviert werden?")
        if snapshot["ai_hypotheses"]: questions.append("Welche Gegenbelege falsifizieren oder schwächen die aktuellen AI-Hypothesen?")
        return list(dict.fromkeys(_clip(q, 600) for q in questions if _clip(q, 600)))[:30]

    def build_dossier(self, *, case_id: str, refresh_hypotheses: bool = True) -> dict[str, Any]:
        go = self.active_go(case_id)
        if refresh_hypotheses:
            self.form_initial_hypotheses(case_id=case_id, parent_task_id=go.get("task_id") if go else None)
        snap = self.collect_case_snapshot(case_id)
        facts = self._fact_rows(snap)
        hyps = self._rows("SELECT suggestion_id,hypothesis_type,title,statement,confidence,status,guardrail_status,created_at,notes FROM ai_hypothesis_suggestions WHERE case_id=? ORDER BY created_at DESC LIMIT 160", (case_id,))
        contradictions = [{"id": x.get("contradiction_id"), "title": x.get("title"), "description": _clip(x.get("description"), 1200), "status": x.get("status")} for x in snap["contradictions"]]
        contradictions += [{"id": x.get("suggestion_id"), "title": x.get("title"), "description": _clip(x.get("description"), 1200), "status": x.get("status")} for x in snap["ai_contradictions"]]
        annex = [{"object_id": x.get("object_id"), "sha256": x.get("sha256"), "source_id": x.get("source_id"), "search_run_id": x.get("search_run_id"), "media_type": x.get("media_type"), "security_state": x.get("security_state")} for x in snap["objects"][:200]]
        objective = (self.latest_intake(case_id) or {}).get("input_payload", {}).get("objective") or snap["case"].get("purpose") or ""
        metrics = {
            "sources": len(snap["sources"]), "objects": len(snap["objects"]), "reviewed_facts": len(facts), "hypotheses": len(hyps),
            "contradictions": len(contradictions), "timeline_events": len(snap["timeline"]), "graph_nodes": len(snap["graph_nodes"]),
            "graph_edges": len(snap["graph_edges"]), "media": len(snap["media"]), "parse_runs": len(snap["parse_runs"]),
            "search_runs": len(snap["search_runs"]), "crawl_runs": len(snap["crawl_runs"]), "go_active": bool(go),
        }
        dossier = {
            "dossier_version": DOSSIER_VERSION,
            "case_id": case_id,
            "objective": objective,
            "executive_summary": f"Evidence-first case synthesis for '{snap['case'].get('title','case')}'. {len(facts)} reviewed evidence facts, {len(hyps)} candidate hypotheses, {len(snap['sources'])} referenced governed sources and {len(snap['objects'])} stored objects are currently represented. Hypotheses remain review-required.",
            "facts": facts,
            "observations": {
                "sources": [{"source_id": x.get("source_id"), "display_name": x.get("display_name"), "source_kind": x.get("source_kind"), "review_status": x.get("review_status"), "risk_class": x.get("risk_class")} for x in snap["sources"]],
                "crawler": snap["crawler_monitor"],
                "timeline": snap["timeline"][:80],
                "graph_nodes": snap["graph_nodes"][:80],
                "graph_edges": snap["graph_edges"][:80],
                "media_count": len(snap["media"]),
            },
            "hypotheses": [{**h, "classification": "ai_hypothesis_candidate", "requires_human_review": True} for h in hyps],
            "counterevidence_and_conflicts": contradictions[:100],
            "uncertainties": ["Absence of evidence is not evidence of absence.", "Source independence must be reviewed before corroboration claims.", "Visual geolocation, similarity and cross-source matches remain candidate-level unless separately verified."],
            "open_questions": self._open_questions(snap),
            "provenance_annex": annex,
            "metrics": metrics,
            "guardrails": {"identity_auto_confirmed": False, "scene_location_auto_confirmed": False, "hypothesis_auto_promoted_to_fact": False, "external_action_without_go": False, "source_auto_approved": False},
            "generated_at": _now(),
        }
        content_hash = _sha(dossier)
        report_id = "dossier356_" + content_hash[:24]
        if not self.db.one("SELECT report_id FROM professional_reports WHERE report_id=?", (report_id,)):
            self.db.execute(
                "INSERT INTO professional_reports(report_id,case_id,report_type,audience,redaction_profile,readiness_status,executive_summary,methodology,source_critique_json,uncertainty_register_json,evidence_annex_json,section_manifest_json,export_paths_json,content_hash,created_at,created_by,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    report_id, case_id, "phase15_ai_dossier_v356", "investigation_team", "internal_review", "draft_review_required",
                    dossier["executive_summary"], "Evidence-first fusion of case-scoped stores. Facts require prior review; AI hypotheses remain candidates; crawler/network actions are Go-gated and OPSEC-mediated.",
                    _canon({"source_count": len(snap["sources"]), "independence_not_assumed": True}), _canon(dossier["uncertainties"]), _canon(annex),
                    _canon({"facts": facts, "hypotheses": dossier["hypotheses"], "conflicts": dossier["counterevidence_and_conflicts"], "open_questions": dossier["open_questions"], "metrics": metrics}),
                    "[]", content_hash, dossier["generated_at"], self.actor, "AI-generated draft; human review required before export/release.",
                ),
            )
        dossier["report_id"] = report_id
        dossier["content_hash"] = content_hash
        dossier["speech_text"] = self.speech_briefing_text(dossier)
        return dossier

    def latest_dossier(self, case_id: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT * FROM professional_reports WHERE case_id=? AND report_type='phase15_ai_dossier_v356' ORDER BY created_at DESC LIMIT 1", (case_id,))
        if not row:
            return None
        sections = _json(row.get("section_manifest_json"), {})
        dossier = {
            "report_id": row.get("report_id"), "case_id": case_id, "dossier_version": DOSSIER_VERSION,
            "executive_summary": row.get("executive_summary") or "",
            "facts": sections.get("facts") or [], "hypotheses": sections.get("hypotheses") or [],
            "counterevidence_and_conflicts": sections.get("conflicts") or [],
            "open_questions": sections.get("open_questions") or [], "metrics": sections.get("metrics") or {},
            "provenance_annex": _json(row.get("evidence_annex_json"), []),
            "uncertainties": _json(row.get("uncertainty_register_json"), []),
            "content_hash": row.get("content_hash") or "", "generated_at": row.get("created_at") or "",
            "readiness_status": row.get("readiness_status") or "draft_review_required",
            "guardrails": {"identity_auto_confirmed": False, "scene_location_auto_confirmed": False, "hypothesis_auto_promoted_to_fact": False},
        }
        dossier["speech_text"] = self.speech_briefing_text(dossier)
        return dossier

    def speech_briefing_text(self, dossier: dict[str, Any]) -> str:
        metrics = dossier.get("metrics") or {}
        hyps = dossier.get("hypotheses") or []
        questions = dossier.get("open_questions") or []
        parts = [
            "EagleEye Ermittlungsbriefing.",
            _clip(dossier.get("executive_summary"), 1800),
            f"Aktuell liegen {metrics.get('reviewed_facts',0)} reviewte Fakten und {metrics.get('hypotheses',0)} Hypothesen vor.",
        ]
        if hyps:
            parts.append("Erste Hypothesen: " + " ".join(_clip(h.get("statement"), 450) for h in hyps[:5]))
        if questions:
            parts.append("Offene Fragen: " + " ".join(_clip(q, 350) for q in questions[:5]))
        parts.append("Alle Hypothesen sind prüfpflichtig. Identität, Ort und Kausalität werden nicht automatisch bestätigt.")
        return _speech_text(" ".join(parts))

    def supervisor_tick(self, *, case_id: str) -> dict[str, Any]:
        go = self.active_go(case_id)
        monitor = self.crawler_monitor(case_id)
        hypotheses = self.form_initial_hypotheses(case_id=case_id, parent_task_id=go.get("task_id") if go else None)
        dossier = self.build_dossier(case_id=case_id, refresh_hypotheses=False)
        return {
            "case_id": case_id,
            "go_active": bool(go),
            "crawler": monitor,
            "hypotheses_refreshed": len(hypotheses),
            "dossier_report_id": dossier["report_id"],
            "dossier_hash": dossier["content_hash"],
            "network_executed_by_supervisor": False,
            "next_action": "workers_continue_governed_jobs" if go and any(k in monitor["job_states"] for k in ("queued", "ready", "retry_wait", "leased", "running")) else "human_review_or_new_governed_sources",
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy_version": POLICY_VERSION,
            "intake": True,
            "explicit_go_required": True,
            "approved_source_auto_delegation_after_go": True,
            "case_wide_read_fusion": True,
            "crawler_monitoring_and_evaluation": True,
            "initial_hypotheses": True,
            "evidence_dossier_v356": True,
            "speech_output": "browser_local_speech_synthesis",
            "voice_input": False,
            "direct_network_client": False,
            "direct_shell": False,
            "direct_database_handle_exposed_to_model": False,
            "auto_identity_confirmation": False,
            "auto_scene_location_confirmation": False,
            "auto_source_approval": False,
            "external_action_without_go": False,
        }
