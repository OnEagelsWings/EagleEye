from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from eagleeye.kernel.contracts import (
    ActionClass, AgentResult, AgentRole, AgentTask, ApprovalState,
    GatewayKind, ResultStatus,
)

POLICY_VERSION = "phase15.multi-wave-investigation-supervisor.v357"
DOSSIER_VERSION = "phase15.evidence-dossier.v357"
WAVE_CONTRACT = "phase15.research-wave.v357"
MAX_WAVES = 4
MAX_SOURCES_PER_WAVE = 6
MAX_TOTAL_JOBS = 24
TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled", "dead_letter"}


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


def _clip(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


class MultiWaveInvestigationSupervisor357:
    """Bounded multi-wave orchestration layered on the Build-356 supervisor.

    GO remains the only authorization boundary for external research. After GO,
    this service may create bounded follow-up waves using only already-human-
    approved crawler sources. It does not perform network I/O itself and cannot
    approve new sources, change OPSEC/network configuration, merge identities,
    export, delete, or release findings.
    """

    def __init__(self, db: Any, *, build356: Any, task_repository: Any, cases: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.build356 = build356
        self.base = build356.supervisor
        self.task_repository = task_repository
        self.cases = cases
        self.actor = actor

    # ----- passthroughs for Build-356 investigation behavior -----
    def create_intake(self, **kwargs: Any) -> dict[str, Any]:
        return self.base.create_intake(**kwargs)

    def latest_intake(self, case_id: str) -> dict[str, Any] | None:
        return self.base.latest_intake(case_id)

    def active_go(self, case_id: str) -> dict[str, Any] | None:
        return self.base.active_go(case_id)

    def crawler_monitor(self, case_id: str) -> dict[str, Any]:
        return self.base.crawler_monitor(case_id)

    def collect_case_snapshot(self, case_id: str) -> dict[str, Any]:
        return self.base.collect_case_snapshot(case_id)

    def form_initial_hypotheses(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.base.form_initial_hypotheses(**kwargs)

    # ----- wave persistence -----
    def _wave_tasks(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT task_json,created_at FROM phase15_agent_tasks WHERE case_id=? AND agent_role='investigation_supervisor' ORDER BY created_at ASC,task_id ASC",
            (case_id,),
        )
        out=[]
        for row in rows:
            data=_json(row.get("task_json"), {})
            payload=data.get("input_payload") or {}
            if payload.get("kind") == "research_wave_v357":
                data["_created_at"] = row.get("created_at") or data.get("created_at") or ""
                out.append(data)
        return sorted(out, key=lambda x: (int((x.get("input_payload") or {}).get("wave_number") or 0), x.get("created_at") or ""))

    def _wave_results(self, task_id: str) -> list[dict[str, Any]]:
        return self.task_repository.list_results(task_id)

    def _source_rows(self) -> list[dict[str, Any]]:
        return self.db.all(
            "SELECT s.source_id,s.source_kind,s.locator,s.display_name,s.review_status,s.risk_class,p.enabled,p.source_health,p.auth_type,p.max_pages,p.requests_per_minute "
            "FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id "
            "WHERE s.review_status='approved_read_only' AND p.enabled=1 AND p.auth_type='none' ORDER BY s.created_at ASC"
        )

    def _job_rows(self, job_ids: list[str]) -> list[dict[str, Any]]:
        ids=[str(x) for x in job_ids if str(x)]
        if not ids:
            return []
        marks=",".join("?" for _ in ids)
        return self.db.all(
            f"SELECT job_id,job_type,status,attempts,max_attempts,error_text,rate_budget_json,result_json,created_at,updated_at FROM phase15_jobs WHERE job_id IN ({marks}) ORDER BY created_at ASC",
            tuple(ids),
        )

    def _wave_task(self, *, case_id: str, go_task_id: str, wave_number: int, job_rows: list[dict[str, Any]], source_ids: list[str], questions: list[str], reason: str) -> dict[str, Any]:
        task = AgentTask.create(
            case_id=case_id,
            actor=self.actor,
            agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.EXTERNAL_RESEARCH,
            requested_gateway=GatewayKind.SEARCH,
            approval_state=ApprovalState.APPROVED,
            parent_task_id=go_task_id,
            input_payload={
                "kind": "research_wave_v357",
                "wave_contract": WAVE_CONTRACT,
                "wave_number": int(wave_number),
                "go_task_id": go_task_id,
                "job_ids": [str(x.get("job_id") or "") for x in job_rows if x.get("job_id")],
                "source_ids": list(dict.fromkeys(str(x) for x in source_ids if str(x)))[:MAX_SOURCES_PER_WAVE],
                "research_questions": [_clip(x, 500) for x in questions if _clip(x, 500)][:12],
                "planning_reason": _clip(reason, 800),
                "max_waves": MAX_WAVES,
                "max_sources_per_wave": MAX_SOURCES_PER_WAVE,
                "max_total_jobs": MAX_TOTAL_JOBS,
                "new_source_approval_allowed": False,
                "network_policy_mutation_allowed": False,
                "identity_merge_allowed": False,
                "export_allowed": False,
                "release_allowed": False,
                "network_executed_by_supervisor": False,
                "policy_version": POLICY_VERSION,
            },
        )
        return self.task_repository.create_task(task)

    def ensure_initial_wave(self, *, case_id: str, go_result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        go=self.active_go(case_id)
        if not go:
            return None
        existing=self._wave_tasks(case_id)
        for wave in existing:
            if (wave.get("input_payload") or {}).get("go_task_id") == go.get("task_id") and int((wave.get("input_payload") or {}).get("wave_number") or 0) == 1:
                return wave
        enqueued=list((go_result or {}).get("enqueued") or [])
        if not enqueued:
            # Recover the initial GO jobs from the case if GO was created before Build 357.
            jobs=self.db.all("SELECT job_id,payload_json,created_at FROM phase15_jobs WHERE case_id=? ORDER BY created_at ASC LIMIT ?", (case_id, MAX_TOTAL_JOBS))
            for row in jobs:
                payload=_json(row.get("payload_json"), {})
                sid=str(payload.get("source_id") or "")
                if sid:
                    enqueued.append({"job_id": row.get("job_id"), "source_id": sid})
        job_rows=[{"job_id": x.get("job_id") or ((x.get("job") or {}).get("job_id"))} for x in enqueued]
        source_ids=[str(x.get("source_id") or "") for x in enqueued if x.get("source_id")]
        intake=self.latest_intake(case_id) or {}
        questions=(intake.get("input_payload") or {}).get("key_questions") or []
        return self._wave_task(
            case_id=case_id, go_task_id=str(go.get("task_id") or ""), wave_number=1,
            job_rows=job_rows, source_ids=source_ids, questions=questions,
            reason="Initial GO wave; created exactly once from already-approved sources.",
        )

    def start_go(self, *, case_id: str, go: str, intake_task_id: str | None = None) -> dict[str, Any]:
        result=self.base.start_go(case_id=case_id, go=go, intake_task_id=intake_task_id)
        wave=self.ensure_initial_wave(case_id=case_id, go_result=result)
        return {**result, "wave": wave, "multi_wave_policy": POLICY_VERSION}

    def research_waves(self, case_id: str) -> list[dict[str, Any]]:
        out=[]
        for wave in self._wave_tasks(case_id):
            p=wave.get("input_payload") or {}
            jobs=self._job_rows(list(p.get("job_ids") or []))
            states={}
            for job in jobs:
                states[job.get("status") or "unknown"] = states.get(job.get("status") or "unknown", 0) + 1
            terminal=bool(jobs) and all(str(j.get("status")) in TERMINAL_JOB_STATES for j in jobs)
            if not jobs:
                terminal=True
            results=self._wave_results(str(wave.get("task_id") or ""))
            out.append({
                "task_id": wave.get("task_id"), "wave_number": int(p.get("wave_number") or 0),
                "job_ids": list(p.get("job_ids") or []), "source_ids": list(p.get("source_ids") or []),
                "research_questions": list(p.get("research_questions") or []), "job_states": states,
                "terminal": terminal, "evaluation": results[-1] if results else None,
                "created_at": wave.get("created_at") or wave.get("_created_at") or "",
            })
        return out

    def _source_score(self, source: dict[str, Any], case_id: str) -> tuple[int, str]:
        sid=str(source.get("source_id") or "")
        health=str(source.get("source_health") or "not_run")
        health_score={"operational": 5, "healthy": 5, "not_run": 2, "degraded": 0, "rate_limited": -1, "offline": -3, "quarantined": -5}.get(health, 1)
        rows=self.db.all("SELECT j.status FROM phase15_jobs j WHERE j.case_id=? AND j.payload_json LIKE ? ORDER BY j.created_at DESC LIMIT 10", (case_id, f'%"source_id":"{sid}"%'))
        success=sum(1 for r in rows if r.get("status")=="succeeded")
        bad=sum(1 for r in rows if r.get("status") in {"failed","dead_letter"})
        kind_bonus=1 if str(source.get("source_kind")) in {"corporate_api","public_web","open_data"} else 0
        score=health_score + min(success,3) - 2*bad + kind_bonus
        return score, sid

    def _wave_material_delta(self, *, case_id: str, wave_created_at: str) -> dict[str, int]:
        def count(sql: str, params: tuple[Any, ...]) -> int:
            row=self.db.one(sql, params)
            return int(row.get("c") if row else 0)
        at=str(wave_created_at or "")
        return {
            "objects": count("SELECT COUNT(*) c FROM phase15_objects WHERE case_id=? AND created_at>=?", (case_id, at)),
            "evidence": count("SELECT COUNT(*) c FROM evidence_items WHERE case_id=? AND captured_at>=?", (case_id, at)),
            "search_documents": count("SELECT COUNT(*) c FROM phase15_search_documents WHERE case_id=? AND created_at>=?", (case_id, at)),
            "crawl_fetches": count("SELECT COUNT(*) c FROM phase15_crawl_fetches f JOIN phase15_crawl_runs r ON r.crawl_run_id=f.crawl_run_id WHERE r.case_id=? AND f.created_at>=?", (case_id, at)),
        }

    def evaluate_latest_wave(self, *, case_id: str, allow_followup: bool = True) -> dict[str, Any]:
        self.cases.get_case(case_id)
        go=self.active_go(case_id)
        if not go:
            return {"state":"go_required","followup_created":False,"network_executed_by_supervisor":False}
        self.ensure_initial_wave(case_id=case_id)
        waves=self.research_waves(case_id)
        if not waves:
            return {"state":"no_wave","followup_created":False,"network_executed_by_supervisor":False}
        latest=waves[-1]
        if not latest["terminal"]:
            return {"state":"waiting_for_wave_terminal","wave_number":latest["wave_number"],"job_states":latest["job_states"],"followup_created":False,"network_executed_by_supervisor":False}
        if latest.get("evaluation"):
            payload=(latest["evaluation"].get("output_payload") or {})
            return {"state":payload.get("state","evaluated"),"wave_number":latest["wave_number"],"followup_created":bool(payload.get("next_wave_task_id")),"evaluation":latest["evaluation"],"network_executed_by_supervisor":False}

        job_rows=self._job_rows(latest["job_ids"])
        dead=[j for j in job_rows if j.get("status") in {"dead_letter","failed"}]
        monitor=self.crawler_monitor(case_id)
        deltas=self._wave_material_delta(case_id=case_id, wave_created_at=latest.get("created_at") or "")
        dossier=self.base.build_dossier(case_id=case_id, refresh_hypotheses=True)
        questions=list(dossier.get("open_questions") or [])[:12]
        stop_reason=""
        if dead:
            stop_reason="worker_failures_require_human_attention"
        elif int(monitor.get("security_blocks") or 0) > 0:
            stop_reason="opsec_or_content_blocks_require_human_attention"
        elif latest["wave_number"] >= MAX_WAVES:
            stop_reason="maximum_wave_limit_reached"
        elif not allow_followup:
            stop_reason="followup_disabled_by_caller"
        elif sum(deltas.values()) == 0:
            stop_reason="no_material_delta_detected"
        elif not questions:
            stop_reason="no_open_questions"

        next_wave=None
        if not stop_reason:
            total_jobs=int(self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=?", (case_id,))["c"])
            remaining=max(0, MAX_TOTAL_JOBS-total_jobs)
            if remaining <= 0:
                stop_reason="case_job_budget_exhausted"
            else:
                ranked=sorted(self._source_rows(), key=lambda s: self._source_score(s, case_id), reverse=True)
                selected=ranked[:min(MAX_SOURCES_PER_WAVE, remaining)]
                if not selected:
                    stop_reason="no_approved_sources_available"
                else:
                    enqueued=[]; skipped=[]
                    for source in selected:
                        try:
                            item=self.build356.enqueue_crawl(case_id=case_id, source_id=source["source_id"])
                            job=item.get("job") or {}
                            enqueued.append({"source_id":source["source_id"],"job_id":job.get("job_id","")})
                        except Exception as exc:
                            skipped.append({"source_id":source.get("source_id"),"reason":_clip(exc,300)})
                    if enqueued:
                        next_wave=self._wave_task(
                            case_id=case_id, go_task_id=str(go.get("task_id") or ""),
                            wave_number=latest["wave_number"]+1, job_rows=enqueued,
                            source_ids=[x["source_id"] for x in enqueued], questions=questions,
                            reason="Follow-up wave selected after terminal evaluation of the previous wave; source ranking uses approved source health and prior job outcomes.",
                        )
                    else:
                        stop_reason="all_followup_source_enqueues_failed"

        output={
            "kind":"research_wave_evaluation_v357",
            "state":"followup_wave_created" if next_wave else "stopped_for_review",
            "wave_number":latest["wave_number"],
            "job_states":latest["job_states"],
            "material_delta":deltas,
            "open_questions":questions,
            "stop_reason":stop_reason,
            "next_wave_task_id":(next_wave or {}).get("task_id", ""),
            "network_executed_by_supervisor":False,
            "new_source_approval_changed":False,
            "policy_version":POLICY_VERSION,
        }
        result=AgentResult.create(
            task_id=str(latest["task_id"]),
            status=ResultStatus.COMPLETED if next_wave else ResultStatus.DEFERRED,
            output_payload=output,
            gateway_used=GatewayKind.NONE,
            policy_reason=stop_reason or "bounded_followup_wave_created",
        )
        saved=self.task_repository.append_result(result)
        return {**output,"followup_created":bool(next_wave),"evaluation":saved,"next_wave":next_wave}

    def build_dossier(self, *, case_id: str, refresh_hypotheses: bool = True) -> dict[str, Any]:
        base=self.base.build_dossier(case_id=case_id, refresh_hypotheses=refresh_hypotheses)
        waves=self.research_waves(case_id)
        dossier={**base}
        dossier["dossier_version"]=DOSSIER_VERSION
        dossier["research_waves"]=[{
            "wave_number":w["wave_number"],"terminal":w["terminal"],"job_states":w["job_states"],
            "source_ids":w["source_ids"],"research_questions":w["research_questions"],
            "evaluation":(w.get("evaluation") or {}).get("output_payload") if w.get("evaluation") else None,
        } for w in waves]
        dossier["metrics"]={**(base.get("metrics") or {}),"research_waves":len(waves),"max_research_waves":MAX_WAVES}
        dossier["guardrails"]={**(base.get("guardrails") or {}),"followup_without_go":False,"new_source_auto_approved":False,"unbounded_research_loop":False}
        dossier["content_hash"]=_sha({k:v for k,v in dossier.items() if k not in {"content_hash","speech_text","report_id"}})
        report_id="dossier357_"+dossier["content_hash"][:24]
        if not self.db.one("SELECT report_id FROM professional_reports WHERE report_id=?", (report_id,)):
            sections={"facts":dossier.get("facts") or [],"hypotheses":dossier.get("hypotheses") or [],"conflicts":dossier.get("counterevidence_and_conflicts") or [],"open_questions":dossier.get("open_questions") or [],"metrics":dossier.get("metrics") or {},"research_waves":dossier.get("research_waves") or []}
            self.db.execute(
                "INSERT INTO professional_reports(report_id,case_id,report_type,audience,redaction_profile,readiness_status,executive_summary,methodology,source_critique_json,uncertainty_register_json,evidence_annex_json,section_manifest_json,export_paths_json,content_hash,created_at,created_by,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (report_id,case_id,"phase15_ai_dossier_v357","investigation_team","internal_review","draft_review_required",dossier.get("executive_summary") or "","Bounded multi-wave evidence-first fusion. Follow-up waves require prior GO and terminal evaluation; only already-approved sources may be delegated.",_canon({"source_independence_not_assumed":True}),_canon(dossier.get("uncertainties") or []),_canon(dossier.get("provenance_annex") or []),_canon(sections),"[]",dossier["content_hash"],_now(),self.actor,"AI-generated draft; human review required before export/release."),
            )
        dossier["report_id"]=report_id
        dossier["speech_text"]=self.base.speech_briefing_text(dossier)
        return dossier

    def latest_dossier(self, case_id: str) -> dict[str, Any] | None:
        row=self.db.one("SELECT * FROM professional_reports WHERE case_id=? AND report_type='phase15_ai_dossier_v357' ORDER BY created_at DESC LIMIT 1", (case_id,))
        if not row:
            return None
        sections=_json(row.get("section_manifest_json"), {})
        dossier={
            "report_id":row.get("report_id"),"case_id":case_id,"dossier_version":DOSSIER_VERSION,
            "executive_summary":row.get("executive_summary") or "","facts":sections.get("facts") or [],
            "hypotheses":sections.get("hypotheses") or [],"counterevidence_and_conflicts":sections.get("conflicts") or [],
            "open_questions":sections.get("open_questions") or [],"metrics":sections.get("metrics") or {},
            "research_waves":sections.get("research_waves") or [],"provenance_annex":_json(row.get("evidence_annex_json"), []),
            "uncertainties":_json(row.get("uncertainty_register_json"), []),"content_hash":row.get("content_hash") or "",
            "generated_at":row.get("created_at") or "","readiness_status":row.get("readiness_status") or "draft_review_required",
            "guardrails":{"identity_auto_confirmed":False,"scene_location_auto_confirmed":False,"hypothesis_auto_promoted_to_fact":False,"unbounded_research_loop":False},
        }
        dossier["speech_text"]=self.base.speech_briefing_text(dossier)
        return dossier

    def supervisor_tick(self, *, case_id: str) -> dict[str, Any]:
        go=self.active_go(case_id)
        if go:
            self.ensure_initial_wave(case_id=case_id)
        wave=self.evaluate_latest_wave(case_id=case_id, allow_followup=True) if go else {"state":"go_required","followup_created":False}
        hypotheses=self.base.form_initial_hypotheses(case_id=case_id, parent_task_id=go.get("task_id") if go else None)
        dossier=self.build_dossier(case_id=case_id, refresh_hypotheses=False)
        monitor=self.crawler_monitor(case_id)
        return {
            "case_id":case_id,"go_active":bool(go),"research_wave":wave,"research_waves":len(self.research_waves(case_id)),
            "crawler":monitor,"hypotheses_refreshed":len(hypotheses),"dossier_report_id":dossier["report_id"],
            "dossier_hash":dossier["content_hash"],"network_executed_by_supervisor":False,
            "next_action":"workers_continue_current_wave" if wave.get("state")=="waiting_for_wave_terminal" else ("followup_wave_workers_may_run" if wave.get("followup_created") else "human_review_or_stop"),
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy_version":POLICY_VERSION,"wave_contract":WAVE_CONTRACT,"explicit_go_required":True,
            "multi_wave_autonomy_after_go":True,"max_waves":MAX_WAVES,"max_sources_per_wave":MAX_SOURCES_PER_WAVE,
            "max_total_jobs":MAX_TOTAL_JOBS,"wave_requires_previous_terminal":True,"stop_on_opsec_or_dead_letter":True,
            "crawler_subjobs_prioritized":True,"casewide_fusion_between_waves":True,"dossier_refusion_each_tick":True,
            "direct_network_client":False,"direct_shell":False,"auto_source_approval":False,"identity_auto_confirmation":False,
            "auto_release":False,"voice_input":False,"speech_output":"local_browser_speech_synthesis",
        }
