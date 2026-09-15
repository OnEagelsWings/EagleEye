from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from eagleeye.kernel.contracts import (
    ActionClass,
    AgentResult,
    AgentRole,
    AgentTask,
    ApprovalState,
    GatewayKind,
    ResultStatus,
)
from eagleeye.voice.gateway358 import ALLOWED_AUDIO_TYPES, MAX_AUDIO_BYTES

POLICY = "phase16.voice-live-validation.v378"
CRAWLER_POLICY = "phase16.voice-crawler-intent.v378"
AI_POLICY = "phase16.autonomous-investigation.v378"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v378"
INTENT_KIND = "voice_crawler_intent_v378"
MAX_VOICE_SOURCES = 2
MAX_VOICE_REQUESTS = 30
MAX_TRANSCRIPT_CHARS = 12000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _j(v: Any, default: Any) -> Any:
    try:
        return json.loads(v) if isinstance(v, str) else (v if v is not None else default)
    except Exception:
        return default


def _clip(v: Any, limit: int = MAX_TRANSCRIPT_CHARS) -> str:
    return " ".join(str(v or "").split())[:limit]


class VoiceCrawlerIntent378:
    """Human-confirmed voice-to-crawler intent bridge.

    The bridge has no transport and never performs network I/O. It creates a visible,
    editable proposal, validates the current case workflow and only after an exact
    second confirmation delegates to Build-374's governed manual crawl enqueue path.
    Any edit creates a new proposal and therefore requires a fresh confirmation.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        voice358: Any,
        task_repository: Any,
        workflow374: Any,
        governance359: Any,
        crawler369: Any,
        jobs: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.voice358 = voice358
        self.tasks = task_repository
        self.workflow374 = workflow374
        self.governance359 = governance359
        self.crawler369 = crawler369
        self.jobs = jobs
        self.actor = actor

    def _actor(self, identity: Mapping[str, Any]) -> str:
        return str(identity.get("username") or self.actor)[:120]

    def _authorize(self, identity: Mapping[str, Any], case_id: str, *, execute: bool = False) -> None:
        self.governance359.authorize(
            identity,
            case_id=case_id,
            capability="voice.research",
            object_type="voice_crawler_intent_v378",
            object_id=case_id,
        )
        if execute:
            self.governance359.authorize(
                identity,
                case_id=case_id,
                capability="crawler.run",
                object_type="voice_crawler_intent_v378",
                object_id=case_id,
            )

    def _source(self, source_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT s.source_id,s.source_kind,s.locator,s.display_name,s.review_status,s.risk_class,"
            "p.auth_type,p.max_pages,p.enabled,p.source_health "
            "FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
            (str(source_id),),
        )
        if not row:
            raise KeyError(source_id)
        out = dict(row)
        link = self.db.one("SELECT connector_key FROM phase15_connector_source_links WHERE source_id=?", (str(source_id),))
        out["connector_key"] = str((link or {}).get("connector_key") or "")
        return out

    def _workflow_status(self, *, case_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        return self.workflow374.status(case_id=case_id, identity=dict(identity))

    def _normal_sources(self, source_ids: Sequence[str] | None) -> list[str]:
        out: list[str] = []
        for raw in source_ids or []:
            sid = str(raw or "").strip()
            if sid and sid not in out:
                out.append(sid)
        if len(out) > MAX_VOICE_SOURCES:
            raise ValueError(f"voice crawler intent supports at most {MAX_VOICE_SOURCES} explicit sources")
        return out

    def _proposal_body(
        self,
        *,
        case_id: str,
        identity: Mapping[str, Any],
        transcript: str,
        source_ids: Sequence[str] | None,
    ) -> dict[str, Any]:
        text = _clip(transcript)
        if not text:
            raise ValueError("transcript required")
        classified = dict(self.voice358.classify(text, "command"))
        selected = self._normal_sources(source_ids)
        wf = self._workflow_status(case_id=case_id, identity=identity)
        pressure = self.crawler369.backpressure(case_id=case_id)
        reasons: list[str] = []
        warnings: list[str] = []
        packets: list[dict[str, Any]] = []

        # Voice crawler bridge only handles external crawler intents. All other voice
        # intents continue through the existing local/manual gateway.
        if classified.get("intent") not in {"start_or_continue_research", "continue_research_wave"}:
            if "crawler" not in text.casefold() and "suche" not in text.casefold() and "recherche" not in text.casefold():
                reasons.append("not_a_crawler_intent")
        if classified.get("manual_ui_required") is True:
            reasons.append("manual_ui_action_not_allowed_in_voice_crawler_bridge")
        if not selected:
            reasons.append("explicit_source_selection_required")
        if wf.get("state") != "active":
            reasons.append(f"workflow_not_active:{wf.get('state')}")
        if pressure.get("global_backpressure") or pressure.get("case_backpressure"):
            reasons.append("crawler_backpressure")

        budgets = dict(wf.get("source_budgets") or {})
        usage = dict((wf.get("usage") or {}))
        source_remaining = dict(usage.get("source_remaining_requests") or {})
        case_remaining = int(usage.get("case_remaining_requests") or 0)
        estimated_total = 0
        for sid in selected:
            try:
                src = self._source(sid)
            except KeyError:
                reasons.append(f"source_unknown:{sid}")
                continue
            estimate = int(src.get("max_pages") or 0) + 3
            estimated_total += estimate
            s_reasons: list[str] = []
            if sid not in budgets:
                s_reasons.append("source_not_in_case_workflow")
            if src.get("review_status") != "approved_read_only":
                s_reasons.append("source_not_approved_read_only")
            if int(src.get("enabled") or 0) != 1:
                s_reasons.append("source_disabled")
            if str(src.get("auth_type") or "none").casefold() != "none":
                s_reasons.append("authenticated_source_requires_separate_manual_path")
            if str(src.get("source_kind") or "").casefold() == "darknet_onion" or str(src.get("locator") or "").casefold().endswith(".onion"):
                s_reasons.append("tor_requires_separate_manual_gate")
            if src.get("connector_key"):
                s_reasons.append("provider_connector_requires_separate_live_gate")
            health = str(src.get("source_health") or "unknown").casefold()
            if health in {"offline", "authentication_required", "changed_contract", "rate_limited", "quarantined"}:
                s_reasons.append(f"source_health_block:{health}")
            remaining = int(source_remaining.get(sid, budgets.get(sid, 0)) or 0)
            if estimate > remaining:
                s_reasons.append("source_request_budget_exceeded")
            packets.append({
                "source_id": sid,
                "display_name": str(src.get("display_name") or sid),
                "source_kind": str(src.get("source_kind") or ""),
                "review_status": str(src.get("review_status") or ""),
                "source_health": health,
                "estimated_max_requests": estimate,
                "remaining_workflow_requests": remaining,
                "connector_key": str(src.get("connector_key") or ""),
                "reasons": sorted(set(s_reasons)),
            })
            reasons.extend(f"{x}:{sid}" for x in s_reasons)

        if estimated_total > MAX_VOICE_REQUESTS:
            reasons.append("voice_request_budget_exceeded")
        if estimated_total > case_remaining:
            reasons.append("case_request_budget_exceeded")
        if estimated_total > 0 and case_remaining - estimated_total <= max(5, int((wf.get("case_request_budget") or 0) * 0.10)):
            warnings.append("case_budget_low_after_voice_crawl")

        allowed = not reasons
        preview = {
            "policy": CRAWLER_POLICY,
            "case_id": case_id,
            "transcript": text,
            "classified_intent": str(classified.get("intent") or ""),
            "intent_summary": str(classified.get("summary") or ""),
            "selected_source_ids": selected,
            "source_packets": packets,
            "estimated_max_requests": estimated_total,
            "voice_request_limit": MAX_VOICE_REQUESTS,
            "workflow_id": wf.get("workflow_id"),
            "workflow_generation": int(wf.get("generation") or 0),
            "workflow_state": wf.get("state"),
            "case_remaining_requests": case_remaining,
            "backpressure": {
                "global": bool(pressure.get("global_backpressure")),
                "case": bool(pressure.get("case_backpressure")),
                "case_depth": int(pressure.get("case_crawl_queue_depth") or 0),
                "global_depth": int(pressure.get("global_crawl_queue_depth") or 0),
            },
            "allowed_for_confirmation": allowed,
            "block_reasons": sorted(set(reasons)),
            "warnings": sorted(set(warnings)),
            "required_confirmation": "VOICE CRAWL",
            "editable_transcript": True,
            "editable_source_selection": True,
            "edit_invalidates_confirmation": True,
            "source_auto_selection": False,
            "direct_network_authority": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
            "audio_persisted": False,
        }
        preview["preview_hash"] = _sha({k: v for k, v in preview.items() if k != "preview_hash"})
        return preview

    def propose(
        self,
        *,
        case_id: str,
        identity: Mapping[str, Any],
        transcript: str,
        source_ids: Sequence[str] | None = None,
        source: str = "voice378_transcript",
        parent_intent_id: str | None = None,
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, execute=False)
        preview = self._proposal_body(case_id=case_id, identity=identity, transcript=transcript, source_ids=source_ids)
        actor = self._actor(identity)
        payload = {
            "kind": INTENT_KIND,
            "policy": POLICY,
            "crawler_policy": CRAWLER_POLICY,
            "source": str(source or "voice378_transcript")[:120],
            "transcript": preview["transcript"],
            "selected_source_ids": list(preview["selected_source_ids"]),
            "preview": preview,
            "preview_hash": preview["preview_hash"],
            "requires_confirmation": True,
            "required_confirmation": "VOICE CRAWL",
            "edit_invalidates_confirmation": True,
            "direct_network_authority": False,
            "automatic_execution": False,
            "audio_persisted": False,
            "voice_biometrics": False,
            "created_by": actor,
        }
        task = AgentTask.create(
            case_id=case_id,
            actor=actor,
            agent_role=AgentRole.VOICE_GATEWAY,
            action_class=ActionClass.EXTERNAL_RESEARCH,
            requested_gateway=GatewayKind.SEARCH,
            approval_state=ApprovalState.PENDING,
            input_payload=payload,
            parent_task_id=parent_intent_id,
        )
        saved = self.tasks.create_task(task)
        self.audit.log(
            "VOICE378_CRAWLER_INTENT_PROPOSED",
            "voice_intent",
            task.task_id,
            case_id=case_id,
            details={"preview_hash": preview["preview_hash"], "source_ids": preview["selected_source_ids"], "allowed": preview["allowed_for_confirmation"], "actor": actor, "policy": POLICY},
        )
        return {
            "intent_id": task.task_id,
            "case_id": case_id,
            "state": "confirmation_available" if preview["allowed_for_confirmation"] else "blocked_preview",
            "preview": preview,
            "task": saved,
            "executed": False,
        }

    def transcribe_push_to_talk(
        self,
        *,
        case_id: str,
        identity: Mapping[str, Any],
        audio: bytes,
        media_type: str,
        language: str = "de",
        human_started: bool = False,
        source_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, execute=False)
        if not human_started:
            raise PermissionError("push_to_talk_human_start_required")
        if not audio:
            raise ValueError("audio required")
        if len(audio) > MAX_AUDIO_BYTES:
            raise ValueError("audio too large")
        mt = str(media_type or "").split(";", 1)[0].casefold()
        if mt not in ALLOWED_AUDIO_TYPES:
            raise ValueError("unsupported audio media type")
        try:
            transcript = self.voice358.transcriber(audio, mt, language) if callable(self.voice358.transcriber) else ""
        except RuntimeError as exc:
            return {
                "status": str(exc),
                "transcript": "",
                "audio_persisted": False,
                "audio_deleted_after_transcription": True,
                "requires_manual_transcript": True,
                "network_used_by_voice_gateway": False,
                "intent_created": False,
            }
        transcript = _clip(transcript)
        if not transcript:
            return {
                "status": "no_speech_recognized",
                "transcript": "",
                "audio_persisted": False,
                "audio_deleted_after_transcription": True,
                "requires_manual_transcript": True,
                "network_used_by_voice_gateway": False,
                "intent_created": False,
            }
        proposed = self.propose(case_id=case_id, identity=identity, transcript=transcript, source_ids=source_ids, source="push_to_talk_local_stt_v378")
        return {
            "status": "transcribed",
            "transcript": transcript,
            "audio_persisted": False,
            "audio_deleted_after_transcription": True,
            "requires_manual_transcript": False,
            "network_used_by_voice_gateway": False,
            "intent_created": True,
            **proposed,
        }

    def _task_row(self, intent_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        row = self.db.one("SELECT * FROM phase15_agent_tasks WHERE task_id=? AND agent_role='voice_gateway'", (str(intent_id),))
        if not row:
            raise KeyError(intent_id)
        task = _j(row.get("task_json"), {}) or {}
        if _sha(task) != row.get("record_hash"):
            raise PermissionError("voice intent task integrity mismatch")
        payload = dict(task.get("input_payload") or {})
        if payload.get("kind") != INTENT_KIND:
            raise PermissionError("not a Build-378 crawler intent")
        preview = dict(payload.get("preview") or {})
        expected = _sha({k: v for k, v in preview.items() if k != "preview_hash"})
        if expected != payload.get("preview_hash") or expected != preview.get("preview_hash"):
            raise PermissionError("voice intent preview integrity mismatch")
        return task, payload

    def _tag_job(self, *, job_id: str, intent_id: str, preview_hash: str, actor: str) -> None:
        if not hasattr(self.workflow374, "_rehash_job"):
            raise RuntimeError("workflow job tagging unavailable")
        row = self.jobs.get(job_id)
        payload = _j(row.get("payload_json"), {}) or {}
        payload.update({
            "phase16_voice_crawler_v378": True,
            "voice_intent_id_v378": intent_id,
            "voice_preview_hash_v378": preview_hash,
            "voice_confirmation_v378": "VOICE CRAWL",
            "voice_direct_network_authority": False,
            "voice_automatic_scope_expansion": False,
            "voice_authorized_by": actor,
        })
        self.workflow374._rehash_job(job_id, payload=payload)
        if hasattr(self.workflow374, "_event"):
            self.workflow374._event(job_id, "voice_crawler_tagged_v378", {"intent_id": intent_id, "preview_hash": preview_hash}, actor)

    def confirm(
        self,
        *,
        intent_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
        edited_transcript: str | None = None,
        source_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        task, payload = self._task_row(intent_id)
        case_id = str(task.get("case_id") or "")
        self._authorize(identity, case_id, execute=True)
        original_transcript = _clip(payload.get("transcript"))
        original_sources = list(payload.get("selected_source_ids") or [])
        new_transcript = _clip(edited_transcript) if edited_transcript is not None else original_transcript
        new_sources = self._normal_sources(source_ids) if source_ids is not None else original_sources
        if new_transcript != original_transcript or new_sources != original_sources:
            revised = self.propose(
                case_id=case_id,
                identity=identity,
                transcript=new_transcript,
                source_ids=new_sources,
                source="edited_voice378_intent",
                parent_intent_id=intent_id,
            )
            return {
                "state": "reconfirmation_required_after_edit",
                "executed": False,
                "original_intent_id": intent_id,
                "revised_intent": revised,
                "required_confirmation": "VOICE CRAWL",
            }
        if str(confirmation or "").strip().upper() != "VOICE CRAWL":
            return {"state": "confirmation_required", "executed": False, "intent_id": intent_id, "required_confirmation": "VOICE CRAWL"}

        fresh = self._proposal_body(case_id=case_id, identity=identity, transcript=original_transcript, source_ids=original_sources)
        if not fresh.get("allowed_for_confirmation"):
            result = AgentResult.create(
                task_id=intent_id,
                status=ResultStatus.BLOCKED,
                output_payload={"state": "blocked_on_fresh_preflight", "block_reasons": fresh.get("block_reasons") or [], "fresh_preview_hash": fresh.get("preview_hash")},
                gateway_used=GatewayKind.NONE,
                policy_reason="fresh workflow/source/backpressure preflight blocked voice crawler execution",
            )
            self.tasks.append_result(result)
            return {"state": "blocked_on_fresh_preflight", "executed": False, "intent_id": intent_id, "preview": fresh}

        actor = self._actor(identity)
        queued: list[dict[str, Any]] = []
        for sid in original_sources:
            out = self.workflow374.enqueue_source(case_id=case_id, source_id=sid, identity=dict(identity), confirmation="CRAWL")
            job = dict(out.get("job") or {})
            job_id = str(job.get("job_id") or "")
            if not job_id:
                raise RuntimeError("workflow enqueue returned no job id")
            self._tag_job(job_id=job_id, intent_id=intent_id, preview_hash=str(payload.get("preview_hash") or ""), actor=actor)
            queued.append({"source_id": sid, "job_id": job_id})

        result_payload = {
            "state": "queued_via_case_workflow",
            "intent_id": intent_id,
            "case_id": case_id,
            "queued": queued,
            "preview_hash": payload.get("preview_hash"),
            "confirmation": "VOICE CRAWL",
            "direct_network_authority": False,
            "network_request_performed_by_voice_gateway": False,
            "case_workflow_enforced": True,
            "automatic_scope_expansion": False,
        }
        self.tasks.append_result(AgentResult.create(
            task_id=intent_id,
            status=ResultStatus.COMPLETED,
            output_payload=result_payload,
            gateway_used=GatewayKind.SEARCH,
            policy_reason="human-confirmed voice intent delegated to governed case-workflow queue",
        ))
        self.audit.log(
            "VOICE378_CRAWLER_INTENT_CONFIRMED",
            "voice_intent",
            intent_id,
            case_id=case_id,
            details={"queued": queued, "preview_hash": payload.get("preview_hash"), "actor": actor, "policy": POLICY},
        )
        return {**result_payload, "executed": True}

    def interactions(self, *, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT task_id,task_json,record_hash,created_at FROM phase15_agent_tasks WHERE case_id=? AND agent_role='voice_gateway' ORDER BY created_at DESC LIMIT ?",
            (str(case_id), max(1, min(int(limit), 200))),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            task = _j(row.get("task_json"), {}) or {}
            p = dict(task.get("input_payload") or {})
            if p.get("kind") != INTENT_KIND:
                continue
            results = self.tasks.list_results(row["task_id"])
            out.append({
                "intent_id": row["task_id"],
                "created_at": row["created_at"],
                "transcript": p.get("transcript"),
                "selected_source_ids": p.get("selected_source_ids") or [],
                "preview": p.get("preview") or {},
                "task_integrity_valid": _sha(task) == row.get("record_hash"),
                "results": results,
            })
        return out

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "crawler_policy": CRAWLER_POLICY,
            "push_to_talk": True,
            "local_stt_adapter_reused": True,
            "audio_persisted": False,
            "voice_biometrics": False,
            "transcript_editable": True,
            "source_selection_editable": True,
            "edit_requires_reconfirmation": True,
            "required_confirmation": "VOICE CRAWL",
            "max_voice_sources": MAX_VOICE_SOURCES,
            "max_voice_requests": MAX_VOICE_REQUESTS,
            "source_auto_selection": False,
            "provider_connectors_via_voice": False,
            "tor_onion_via_standard_voice_path": False,
            "direct_network_authority": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
            "new_per_build_data_tables": 0,
        }


class AutonomousInvestigation378:
    def __init__(self, *, base377: Any, voice378: VoiceCrawlerIntent378) -> None:
        self.base377 = base377
        self.voice378 = voice378

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base377, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = dict(self.base377.run_cycle(case_id=case_id, max_ticks=max_ticks))
        recent = self.voice378.interactions(case_id=case_id, limit=5)
        dossier = dict(out.get("dossier") or {})
        dossier["phase16_voice_validation_v378"] = {
            "recent_intent_count": len(recent),
            "recent_intents": [
                {
                    "intent_id": x["intent_id"],
                    "selected_source_ids": x["selected_source_ids"],
                    "allowed_for_confirmation": bool((x.get("preview") or {}).get("allowed_for_confirmation")),
                    "result_states": [str((r.get("output_payload") or {}).get("state") or r.get("status") or "") for r in x.get("results") or []],
                }
                for x in recent
            ],
            "voice_direct_network_authority": False,
            "human_confirmation_required": True,
        }
        dossier.setdefault("uncertainties", [])
        dossier["uncertainties"] = list(dossier["uncertainties"]) + [
            "Voice transcripts and intent interpretation are operator-editable; crawler execution requires explicit source selection and a fresh human confirmation."
        ]
        out["dossier"] = dossier
        out["voice_validation"] = dossier["phase16_voice_validation_v378"]
        out["direct_voice_network_authority"] = False
        return out

    def status(self) -> dict[str, Any]:
        return {
            "policy": AI_POLICY,
            "voice_intent_context_in_dossier": True,
            "direct_voice_network_authority": False,
            "voice_can_auto_execute": False,
            "voice_can_auto_select_sources": False,
            "voice_can_expand_scope": False,
        }


class DefensiveOpsecSupervisor378:
    def __init__(self, db: Any, audit: Any, *, base377: Any, voice378: VoiceCrawlerIntent378, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base377 = base377
        self.voice378 = voice378
        self.jobs = jobs

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base377, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        # Classify Build-378-specific violations before inherited layers can cancel.
        violations: list[dict[str, str]] = []
        cancelled: list[str] = []
        rows = self.db.all(
            "SELECT * FROM phase15_jobs WHERE case_id=? AND job_type IN ('governed_crawl_v1','governed_tor_crawl_v370') AND status IN ('queued','workflow_paused','running') ORDER BY created_at",
            (str(case_id),),
        )
        for row in rows:
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("phase16_voice_crawler_v378") is not True:
                continue
            reasons: list[str] = []
            intent_id = str(p.get("voice_intent_id_v378") or "")
            preview_hash = str(p.get("voice_preview_hash_v378") or "")
            if not intent_id or not preview_hash:
                reasons.append("missing_voice_intent_provenance")
            else:
                try:
                    _task, payload = self.voice378._task_row(intent_id)
                    if str(payload.get("preview_hash") or "") != preview_hash:
                        reasons.append("voice_preview_hash_mismatch")
                except Exception:
                    reasons.append("voice_intent_integrity_invalid")
            if p.get("voice_direct_network_authority") is not False:
                reasons.append("voice_direct_network_authority_claim")
            if p.get("voice_automatic_scope_expansion") is not False:
                reasons.append("voice_automatic_scope_expansion_claim")
            if str(p.get("voice_confirmation_v378") or "") != "VOICE CRAWL":
                reasons.append("voice_confirmation_missing")
            if row.get("job_type") == "governed_tor_crawl_v370":
                reasons.append("voice_standard_path_must_not_queue_tor")
            if reasons:
                for reason in sorted(set(reasons)):
                    violations.append({"job_id": row["job_id"], "reason": reason})
                if row.get("status") in {"queued", "workflow_paused"}:
                    try:
                        self.jobs.cancel(row["job_id"], actor="opsec378", reason="voice378:" + ",".join(sorted(set(reasons))))
                    except TypeError:
                        self.jobs.cancel(row["job_id"], actor="opsec378")
                    cancelled.append(row["job_id"])
                self.audit.log(
                    "OPSEC378_VOICE_CRAWLER_VIOLATION",
                    "crawler_job",
                    row["job_id"],
                    case_id=case_id,
                    details={"reasons": sorted(set(reasons)), "policy": OPSEC_POLICY},
                )
        base = dict(self.base377.protect_case(case_id=case_id))
        base.update({
            "voice_crawler_violations": violations,
            "cancelled_voice_crawler_jobs": cancelled,
            "voice_direct_network_authority_blocked": True,
            "voice_automatic_scope_expansion_blocked": True,
            "voice_tor_bypass_blocked": True,
        })
        return base

    def status(self) -> dict[str, Any]:
        base = dict(self.base377.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "voice_intent_integrity_monitor": True,
            "voice_preview_hash_binding": True,
            "voice_confirmation_binding": True,
            "voice_direct_network_authority_blocked": True,
            "voice_auto_source_selection_blocked": True,
            "voice_scope_expansion_blocked": True,
            "voice_tor_bypass_blocked": True,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "credential_mutation": False,
            "acl_mutation": False,
            "system_mutations": False,
        })
        return base
