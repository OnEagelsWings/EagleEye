from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

POLICY = "phase16.case-workflow.v374"
CRAWLER_POLICY = "phase16.case-workflow-crawler.v374"
AI_POLICY = "phase16.autonomous-investigation.v374"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v374"
STATE_JOB = "case_workflow_state_v374"
CRAWL_TYPES = {"governed_crawl_v1", "governed_tor_crawl_v370"}
MAX_CASE_REQUEST_BUDGET = 5000
MAX_SOURCE_REQUEST_BUDGET = 1000
MAX_ACTIVE_WORKFLOW_CRAWLS = 8
MAX_SOURCE_BUDGETS = 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _j(v: Any, default: Any) -> Any:
    try:
        return json.loads(v) if isinstance(v, str) else (v if v is not None else default)
    except Exception:
        return default


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _job_hash(row: Mapping[str, Any]) -> str:
    body = {k: row[k] for k in row if k not in {"record_hash", "deduplicated"}}
    return _sha(body)


class CaseWorkflow374:
    """Case-scoped research workflow layered on canonical ledgers.

    Build 374 deliberately adds no workflow table. A non-claimable state record lives
    in the durable Phase-15 job ledger and transitions are mirrored to job events and
    the audit ledger. Crawler jobs remain canonical crawler jobs.
    """

    def __init__(self, db: Any, audit: Any, *, governance: Any, identity: Any, jobs: Any, graph373: Any, navigation373: Any, crawler369: Any, crawler352: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.governance = governance
        self.identity = identity
        self.jobs = jobs
        self.graph373 = graph373
        self.navigation373 = navigation373
        self.crawler369 = crawler369
        self.crawler352 = crawler352
        self.actor = actor

    def _actor(self, identity: Mapping[str, Any]) -> str:
        return str(identity.get("username") or self.actor)[:120]

    def _authorize_manage(self, identity: Mapping[str, Any], case_id: str) -> None:
        self.governance.authorize(identity, case_id=case_id, capability="case.manage", object_type="case_workflow_v374", object_id=case_id)

    def _authorize_monitor(self, identity: Mapping[str, Any], case_id: str) -> None:
        self.governance.authorize(identity, case_id=case_id, capability="crawler.monitor", object_type="case_workflow_v374", object_id=case_id)

    def _authorize_crawl(self, identity: Mapping[str, Any], case_id: str) -> None:
        self.governance.authorize(identity, case_id=case_id, capability="crawler.run", object_type="case_workflow_v374", object_id=case_id)

    def _state_row(self, case_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM phase15_jobs WHERE job_type=? AND case_id=? ORDER BY created_at DESC LIMIT 1", (STATE_JOB, str(case_id)))

    def _payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return dict(_j(row.get("payload_json"), {}) or {})

    def _rehash_job(self, job_id: str, *, payload: Mapping[str, Any] | None = None, status: str | None = None, available_at: str | None = None, clear_lease: bool = False) -> dict[str, Any]:
        row = self.jobs.get(job_id)
        now = _now()
        new = dict(row)
        if payload is not None:
            new["payload_json"] = _canon(dict(payload))
        if status is not None:
            new["status"] = str(status)
        if available_at is not None:
            new["available_at"] = available_at
        if clear_lease:
            new["lease_owner"] = ""; new["lease_expires_at"] = ""
        new["updated_at"] = now
        new["record_hash"] = _job_hash(new)
        self.db.execute(
            "UPDATE phase15_jobs SET payload_json=?,status=?,available_at=?,lease_owner=?,lease_expires_at=?,updated_at=?,record_hash=? WHERE job_id=?",
            (new["payload_json"], new["status"], new["available_at"], new["lease_owner"], new["lease_expires_at"], new["updated_at"], new["record_hash"], job_id),
        )
        return self.jobs.get(job_id)

    def _event(self, job_id: str, event_type: str, details: Mapping[str, Any], actor: str) -> None:
        if hasattr(self.jobs, "_event"):
            self.jobs._event(job_id, event_type, dict(details), actor=actor)

    def _normal_source_budgets(self, source_budgets: Mapping[str, Any]) -> dict[str, int]:
        if not isinstance(source_budgets, Mapping) or not source_budgets:
            raise ValueError("at least one source budget is required")
        if len(source_budgets) > MAX_SOURCE_BUDGETS:
            raise ValueError("too many source budgets")
        out: dict[str, int] = {}
        for sid, raw in source_budgets.items():
            source_id = str(sid or "").strip()
            if not source_id:
                raise ValueError("source budget contains empty source id")
            if not self.db.one("SELECT source_id FROM phase15_sources WHERE source_id=?", (source_id,)):
                raise KeyError(source_id)
            amount = max(1, min(int(raw), MAX_SOURCE_REQUEST_BUDGET))
            out[source_id] = amount
        return dict(sorted(out.items()))

    def configure(self, *, case_id: str, identity: Mapping[str, Any], source_budgets: Mapping[str, Any], case_request_budget: int = 100, max_active_crawls: int = 3, confirmation: str) -> dict[str, Any]:
        self._authorize_manage(identity, case_id)
        if str(confirmation or "").strip().upper() != "WORKFLOW":
            raise PermissionError("explicit confirmation WORKFLOW required")
        active = int((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type IN ('governed_crawl_v1','governed_tor_crawl_v370') AND status IN ('queued','running')", (case_id,)) or {}).get("c") or 0)
        if active:
            raise PermissionError("configure workflow only when no crawler jobs are queued/running")
        budgets = self._normal_source_budgets(source_budgets)
        case_budget = max(1, min(int(case_request_budget), MAX_CASE_REQUEST_BUDGET))
        if sum(budgets.values()) < 1:
            raise ValueError("invalid source budgets")
        actor = self._actor(identity); now = _now()
        old = self._state_row(case_id)
        generation = int((self._payload(old).get("generation") if old else 0) or 0) + 1
        workflow_id = str((self._payload(old).get("workflow_id") if old else "") or ("wf374_" + uuid.uuid4().hex[:24]))
        payload = {
            "policy": POLICY,
            "workflow_id": workflow_id,
            "case_id": case_id,
            "state": "active",
            "generation": generation,
            "source_budgets": budgets,
            "case_request_budget": case_budget,
            "max_active_crawls": max(1, min(int(max_active_crawls), MAX_ACTIVE_WORKFLOW_CRAWLS)),
            "configured_by": actor,
            "configured_at": now,
            "updated_by": actor,
            "updated_at": now,
            "current_owner": actor,
            "handoff": {},
            "automatic_scope_expansion": False,
            "direct_network_authority": False,
        }
        if old:
            row = self._rehash_job(old["job_id"], payload=payload, status="workflow_active", clear_lease=True)
            jid = row["job_id"]
        else:
            row = self.jobs.enqueue(job_type=STATE_JOB, case_id=case_id, idempotency_key=f"case-workflow-v374:{case_id}", payload=payload, priority=1000, max_attempts=1, resource_budget={"max_runtime_seconds": 1, "max_memory_mb": 32, "max_output_bytes": 1024}, rate_budget={"max_requests": 0, "requests_per_minute": 0})
            row = self._rehash_job(row["job_id"], payload=payload, status="workflow_active", clear_lease=True); jid = row["job_id"]
        self._event(jid, "workflow_configured_v374", {"generation": generation, "source_budgets": budgets, "case_request_budget": case_budget}, actor)
        self.audit.log("WORKFLOW374_CONFIGURED", "case", case_id, case_id=case_id, details={"workflow_id": workflow_id, "generation": generation, "source_budget_count": len(budgets), "case_request_budget": case_budget, "actor": actor, "policy": POLICY})
        return self.status(case_id=case_id, identity=identity)

    def _workflow(self, case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        row = self._state_row(case_id)
        if not row:
            raise KeyError("case workflow is not configured")
        return row, self._payload(row)

    def _crawler_rows(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase15_jobs WHERE case_id=? AND job_type IN ('governed_crawl_v1','governed_tor_crawl_v370') ORDER BY created_at", (case_id,))

    def _usage(self, case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        by_source: dict[str, dict[str, int]] = {str(s): {"reserved": 0, "consumed": 0, "jobs": 0} for s in (payload.get("source_budgets") or {})}
        case_reserved = 0; case_consumed = 0; active = 0; workflow_jobs = 0
        for row in self._crawler_rows(case_id):
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("phase16_case_workflow_v374") is not True or p.get("workflow_id") != payload.get("workflow_id"):
                continue
            workflow_jobs += 1
            sid = str(p.get("source_id") or "")
            rb = _j(row.get("rate_budget_json"), {}) or {}
            reserved = int(p.get("workflow_reserved_requests") or rb.get("max_requests") or 0)
            consumed = int(rb.get("requests_consumed") or 0)
            if row.get("status") in {"queued", "running", "workflow_paused"}:
                effective = max(reserved, consumed)
            else:
                effective = consumed
            case_reserved += effective; case_consumed += consumed
            if row.get("status") in {"queued", "running"}:
                active += 1
            if sid:
                item = by_source.setdefault(sid, {"reserved": 0, "consumed": 0, "jobs": 0})
                item["reserved"] += effective; item["consumed"] += consumed; item["jobs"] += 1
        source_limits = {str(k): int(v) for k, v in (payload.get("source_budgets") or {}).items()}
        source_remaining = {sid: max(0, source_limits.get(sid, 0) - data["reserved"]) for sid, data in by_source.items()}
        return {
            "workflow_jobs": workflow_jobs,
            "active_crawls": active,
            "case_reserved_requests": case_reserved,
            "case_consumed_requests": case_consumed,
            "case_remaining_requests": max(0, int(payload.get("case_request_budget") or 0) - case_reserved),
            "by_source": by_source,
            "source_remaining_requests": source_remaining,
        }

    def _budget_check(self, *, case_id: str, payload: Mapping[str, Any], allocations: Mapping[str, int]) -> dict[str, Any]:
        usage = self._usage(case_id, payload)
        reasons: list[str] = []
        total = sum(max(0, int(v)) for v in allocations.values())
        if payload.get("state") != "active": reasons.append("workflow_not_active")
        if usage["active_crawls"] >= int(payload.get("max_active_crawls") or 1): reasons.append("workflow_active_crawl_limit")
        if total > usage["case_remaining_requests"]: reasons.append("case_request_budget_exceeded")
        configured = payload.get("source_budgets") or {}
        for sid, units in allocations.items():
            if sid not in configured: reasons.append(f"source_not_budgeted:{sid}"); continue
            remaining = int(usage["source_remaining_requests"].get(sid, int(configured[sid])))
            if int(units) > remaining: reasons.append(f"source_request_budget_exceeded:{sid}")
        return {"allowed": not reasons, "reasons": sorted(set(reasons)), "allocations": {str(k): int(v) for k, v in allocations.items()}, "usage": usage}

    def _tag_crawl_job(self, *, job_id: str, workflow: Mapping[str, Any], reserved_requests: int, actor: str, origin: str) -> dict[str, Any]:
        row = self.jobs.get(job_id); p = _j(row.get("payload_json"), {}) or {}
        p.update({
            "phase16_case_workflow_v374": True,
            "workflow_policy_v374": CRAWLER_POLICY,
            "workflow_id": workflow.get("workflow_id"),
            "workflow_generation": int(workflow.get("generation") or 0),
            "workflow_reserved_requests": int(reserved_requests),
            "workflow_origin": origin,
            "workflow_authorized_by": actor,
            "workflow_pause_requested_v374": False,
            "automatic_scope_expansion": False,
        })
        tagged = self._rehash_job(job_id, payload=p)
        self._event(job_id, "workflow_tagged_v374", {"workflow_id": workflow.get("workflow_id"), "reserved_requests": reserved_requests, "origin": origin}, actor)
        return tagged

    def navigation_plan(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize_crawl(identity, case_id)
        _, wf = self._workflow(case_id)
        base = self.navigation373.plan(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=dict(identity))
        allocations = {str(p["source_id"]): int(p["estimated_max_requests"]) for p in base.get("source_packets") or []}
        budget = self._budget_check(case_id=case_id, payload=wf, allocations=allocations)
        allowed = bool(base.get("allowed")) and bool(budget["allowed"])
        reasons = sorted(set(list(base.get("reasons") or []) + list(budget["reasons"])))
        return {**base, "policy": CRAWLER_POLICY, "workflow_id": wf["workflow_id"], "workflow_state": wf["state"], "workflow_budget": budget, "allowed": allowed, "reasons": reasons, "required_confirmation": "NAVIGATE", "case_workflow_enforced": True}

    def navigate(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != "NAVIGATE":
            raise PermissionError("explicit confirmation NAVIGATE required")
        actor = self._actor(identity); _, wf = self._workflow(case_id)
        plan = self.navigation_plan(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=identity)
        if not plan["allowed"]:
            raise PermissionError("workflow graph navigation blocked: " + ",".join(plan["reasons"]))
        out = self.navigation373.navigate(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=dict(identity), confirmation="NAVIGATE")
        reservations = {str(p["source_id"]): int(p["estimated_max_requests"]) for p in plan.get("source_packets") or []}
        for q in out.get("queued") or []:
            self._tag_crawl_job(job_id=q["job_id"], workflow=wf, reserved_requests=reservations.get(q["source_id"], 0), actor=actor, origin="graph_navigation_v373")
        self.audit.log("WORKFLOW374_GRAPH_NAVIGATION", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], "root_entity_id": root_entity_id, "job_ids": [q["job_id"] for q in out.get("queued") or []], "actor": actor, "policy": CRAWLER_POLICY})
        return {**out, "workflow_id": wf["workflow_id"], "workflow_budget_after": self._usage(case_id, wf), "case_workflow_enforced": True}

    def enqueue_source(self, *, case_id: str, source_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        self._authorize_crawl(identity, case_id)
        if str(confirmation or "").strip().upper() != "CRAWL":
            raise PermissionError("explicit confirmation CRAWL required")
        actor = self._actor(identity); _, wf = self._workflow(case_id)
        src = self.db.one("SELECT s.source_id,s.review_status,p.enabled,p.max_pages FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (source_id,))
        if not src: raise KeyError(source_id)
        if src.get("review_status") != "approved_read_only" or int(src.get("enabled") or 0) != 1: raise PermissionError("source not approved")
        estimate = int(src.get("max_pages") or 0) + 3
        budget = self._budget_check(case_id=case_id, payload=wf, allocations={source_id: estimate})
        if not budget["allowed"]: raise PermissionError("workflow crawl blocked: " + ",".join(budget["reasons"]))
        out = self.governance.enqueue_crawl(identity=dict(identity), case_id=case_id, source_id=source_id)
        self._tag_crawl_job(job_id=out["job"]["job_id"], workflow=wf, reserved_requests=estimate, actor=actor, origin="workflow_manual_crawl")
        self.audit.log("WORKFLOW374_CRAWL_ENQUEUED", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], "source_id": source_id, "job_id": out["job"]["job_id"], "actor": actor, "policy": CRAWLER_POLICY})
        return {**out, "workflow_id": wf["workflow_id"], "case_workflow_enforced": True}

    def _pause_jobs(self, *, case_id: str, wf: Mapping[str, Any], actor: str, reason: str) -> dict[str, Any]:
        paused: list[str] = []; draining: list[str] = []
        for row in self._crawler_rows(case_id):
            if row.get("status") not in {"queued", "running"}: continue
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("phase16_case_workflow_v374") is not True or p.get("workflow_id") != wf.get("workflow_id"): continue
            p["workflow_pause_requested_v374"] = True; p["workflow_pause_reason_v374"] = reason
            if row["status"] == "queued":
                p["workflow_pause_previous_status_v374"] = "queued"
                self._rehash_job(row["job_id"], payload=p, status="workflow_paused", clear_lease=True); paused.append(row["job_id"])
            else:
                self._rehash_job(row["job_id"], payload=p); draining.append(row["job_id"])
        return {"paused_queued_jobs": paused, "draining_running_jobs": draining}

    def pause(self, *, case_id: str, identity: Mapping[str, Any], reason: str, confirmation: str) -> dict[str, Any]:
        self._authorize_manage(identity, case_id)
        if str(confirmation or "").strip().upper() != "PAUSE": raise PermissionError("explicit confirmation PAUSE required")
        if len(str(reason or "").strip()) < 4: raise ValueError("pause reason required")
        row, wf = self._workflow(case_id); actor = self._actor(identity)
        if wf.get("state") == "completed": raise PermissionError("completed workflow cannot be paused")
        jobs = self._pause_jobs(case_id=case_id, wf=wf, actor=actor, reason=str(reason)[:500])
        wf.update({"state": "paused", "pause_reason": str(reason)[:1000], "paused_by": actor, "paused_at": _now(), "updated_by": actor, "updated_at": _now()})
        self._rehash_job(row["job_id"], payload=wf, status="workflow_paused_state", clear_lease=True)
        self._event(row["job_id"], "workflow_paused_v374", jobs | {"reason": str(reason)[:500]}, actor)
        self.audit.log("WORKFLOW374_PAUSED", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], **jobs, "reason": str(reason)[:500], "actor": actor, "policy": POLICY})
        return self.status(case_id=case_id, identity=identity)

    def _resume_paused_jobs(self, *, case_id: str, wf: Mapping[str, Any], actor: str) -> list[str]:
        resumed: list[str] = []
        for row in self._crawler_rows(case_id):
            if row.get("status") != "workflow_paused": continue
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("workflow_id") != wf.get("workflow_id") or p.get("phase16_case_workflow_v374") is not True: continue
            p["workflow_pause_requested_v374"] = False; p.pop("workflow_pause_previous_status_v374", None)
            self._rehash_job(row["job_id"], payload=p, status="queued", available_at=_now(), clear_lease=True); resumed.append(row["job_id"])
        return resumed

    def resume(self, *, case_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        self._authorize_manage(identity, case_id)
        if str(confirmation or "").strip().upper() != "RESUME": raise PermissionError("explicit confirmation RESUME required")
        row, wf = self._workflow(case_id); actor = self._actor(identity)
        if wf.get("state") != "paused": raise PermissionError("workflow is not paused")
        resumed = self._resume_paused_jobs(case_id=case_id, wf=wf, actor=actor)
        wf.update({"state": "active", "updated_by": actor, "updated_at": _now(), "resumed_by": actor, "resumed_at": _now()})
        self._rehash_job(row["job_id"], payload=wf, status="workflow_active", clear_lease=True)
        self._event(row["job_id"], "workflow_resumed_v374", {"resumed_jobs": resumed}, actor)
        self.audit.log("WORKFLOW374_RESUMED", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], "resumed_jobs": resumed, "actor": actor, "policy": POLICY})
        return self.status(case_id=case_id, identity=identity)

    def handoff(self, *, case_id: str, identity: Mapping[str, Any], to_username: str, note: str, confirmation: str) -> dict[str, Any]:
        self._authorize_manage(identity, case_id)
        if str(confirmation or "").strip().upper() != "HANDOFF": raise PermissionError("explicit confirmation HANDOFF required")
        if len(str(note or "").strip()) < 8: raise ValueError("handoff note must document context")
        row, wf = self._workflow(case_id); actor = self._actor(identity); target = str(to_username or "").strip().casefold()
        memberships = [m for m in self.identity.list_case_memberships(case_id) if bool(m.get("active")) and str(m.get("username") or "").casefold() == target and m.get("case_role") in {"case_lead", "investigator", "analyst"}]
        if not memberships: raise PermissionError("handoff target needs an active analyst/investigator/case_lead membership")
        if target == actor.casefold(): raise ValueError("handoff target must be another analyst")
        jobs = self._pause_jobs(case_id=case_id, wf=wf, actor=actor, reason="handoff_pending")
        graph_metrics = self.graph373.snapshot(case_id=case_id, identity=dict(identity), max_nodes=120, max_edges=240).get("metrics") or {}
        packet = {
            "from": actor, "to": target, "note": str(note)[:2000], "created_at": _now(), "status": "pending_acceptance",
            "budget": self._usage(case_id, wf), "graph_metrics": graph_metrics, "paused_queued_jobs": jobs["paused_queued_jobs"], "draining_running_jobs": jobs["draining_running_jobs"],
        }
        packet["packet_hash"] = _sha(packet)
        wf.update({"state": "handoff_pending", "handoff": packet, "updated_by": actor, "updated_at": _now()})
        self._rehash_job(row["job_id"], payload=wf, status="workflow_handoff_pending", clear_lease=True)
        self._event(row["job_id"], "workflow_handoff_proposed_v374", {"to": target, "packet_hash": packet["packet_hash"]}, actor)
        self.audit.log("WORKFLOW374_HANDOFF_PROPOSED", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], "from": actor, "to": target, "packet_hash": packet["packet_hash"], "policy": POLICY})
        return self.status(case_id=case_id, identity=identity)

    def accept_handoff(self, *, case_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        self._authorize_crawl(identity, case_id)
        if str(confirmation or "").strip().upper() != "ACCEPT": raise PermissionError("explicit confirmation ACCEPT required")
        row, wf = self._workflow(case_id); actor = self._actor(identity); handoff = dict(wf.get("handoff") or {})
        if wf.get("state") != "handoff_pending" or handoff.get("status") != "pending_acceptance": raise PermissionError("no pending handoff")
        if actor.casefold() != str(handoff.get("to") or "").casefold(): raise PermissionError("only designated handoff target can accept")
        handoff.update({"status": "accepted", "accepted_at": _now(), "accepted_by": actor})
        wf.update({"state": "active", "current_owner": actor, "handoff": handoff, "updated_by": actor, "updated_at": _now()})
        resumed = self._resume_paused_jobs(case_id=case_id, wf=wf, actor=actor)
        self._rehash_job(row["job_id"], payload=wf, status="workflow_active", clear_lease=True)
        self._event(row["job_id"], "workflow_handoff_accepted_v374", {"from": handoff.get("from"), "to": actor, "resumed_jobs": resumed}, actor)
        self.audit.log("WORKFLOW374_HANDOFF_ACCEPTED", "case", case_id, case_id=case_id, details={"workflow_id": wf["workflow_id"], "from": handoff.get("from"), "to": actor, "resumed_jobs": resumed, "policy": POLICY})
        return self.status(case_id=case_id, identity=identity)

    def complete(self, *, case_id: str, identity: Mapping[str, Any], note: str, confirmation: str) -> dict[str, Any]:
        self._authorize_manage(identity, case_id)
        if str(confirmation or "").strip().upper() != "COMPLETE": raise PermissionError("explicit confirmation COMPLETE required")
        row, wf = self._workflow(case_id); actor = self._actor(identity)
        jobs = self._pause_jobs(case_id=case_id, wf=wf, actor=actor, reason="workflow_completed")
        wf.update({"state": "completed", "completion_note": str(note or "")[:2000], "completed_by": actor, "completed_at": _now(), "updated_by": actor, "updated_at": _now()})
        self._rehash_job(row["job_id"], payload=wf, status="workflow_completed", clear_lease=True)
        self._event(row["job_id"], "workflow_completed_v374", jobs, actor)
        return self.status(case_id=case_id, identity=identity)

    def status(self, *, case_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize_monitor(identity, case_id)
        row, wf = self._workflow(case_id)
        usage = self._usage(case_id, wf)
        paused = [r["job_id"] for r in self._crawler_rows(case_id) if r.get("status") == "workflow_paused" and (_j(r.get("payload_json"), {}) or {}).get("workflow_id") == wf.get("workflow_id")]
        running_drain = [r["job_id"] for r in self._crawler_rows(case_id) if r.get("status") == "running" and (_j(r.get("payload_json"), {}) or {}).get("workflow_pause_requested_v374") is True]
        return {
            "policy": POLICY, "case_id": case_id, "workflow_id": wf.get("workflow_id"), "state": wf.get("state"), "generation": int(wf.get("generation") or 0),
            "current_owner": wf.get("current_owner"), "source_budgets": dict(wf.get("source_budgets") or {}), "case_request_budget": int(wf.get("case_request_budget") or 0),
            "max_active_crawls": int(wf.get("max_active_crawls") or 0), "usage": usage, "paused_job_ids": paused, "draining_job_ids": running_drain,
            "handoff": dict(wf.get("handoff") or {}), "configured_at": wf.get("configured_at"), "updated_at": wf.get("updated_at"),
            "automatic_scope_expansion": False, "automatic_network_authority": False, "new_per_build_data_tables": 0,
        }

    def invalid_jobs(self, *, case_id: str) -> list[dict[str, str]]:
        row = self._state_row(case_id)
        if not row: return []
        wf = self._payload(row); configured_at = str(wf.get("configured_at") or "")
        invalid: list[dict[str, str]] = []
        for job in self._crawler_rows(case_id):
            if str(job.get("created_at") or "") < configured_at: continue
            if job.get("status") not in {"queued", "running", "workflow_paused"}: continue
            p = _j(job.get("payload_json"), {}) or {}
            if p.get("phase16_case_workflow_v374") is not True:
                invalid.append({"job_id": job["job_id"], "reason": "workflow_bypass_untagged_crawl"}); continue
            if p.get("workflow_id") != wf.get("workflow_id") or int(p.get("workflow_generation") or 0) != int(wf.get("generation") or 0):
                invalid.append({"job_id": job["job_id"], "reason": "workflow_identity_mismatch"}); continue
            sid = str(p.get("source_id") or ""); reserved = int(p.get("workflow_reserved_requests") or 0)
            if sid not in (wf.get("source_budgets") or {}): invalid.append({"job_id": job["job_id"], "reason": "source_not_budgeted"}); continue
            if reserved <= 0 or reserved > int((wf.get("source_budgets") or {}).get(sid) or 0): invalid.append({"job_id": job["job_id"], "reason": "invalid_source_reservation"}); continue
            if p.get("automatic_scope_expansion") is not False: invalid.append({"job_id": job["job_id"], "reason": "scope_expansion_flag"}); continue
            if wf.get("state") in {"paused", "handoff_pending", "completed"} and job.get("status") == "queued": invalid.append({"job_id": job["job_id"], "reason": "queued_while_workflow_not_active"})
        return invalid

    def status_capabilities(self) -> dict[str, Any]:
        return {
            "policy": POLICY, "case_workflow_state": True, "source_request_budgets": True, "case_request_budget": True,
            "workflow_pause_resume": True, "running_jobs_drain_instead_of_forced_kill": True, "two_step_analyst_handoff": True,
            "graph_navigation_budget_enforced": True, "manual_crawl_budget_enforced": True, "workflow_bypass_detection": True,
            "automatic_scope_expansion": False, "automatic_network_authority": False, "new_per_build_data_tables": 0,
        }


class AutonomousInvestigation374:
    def __init__(self, *, base373: Any, workflow374: CaseWorkflow374) -> None:
        self.base373 = base373; self.workflow374 = workflow374

    def status(self) -> dict[str, Any]:
        base = dict(self.base373.status())
        base.update({"policy_version": AI_POLICY, "case_workflow_awareness": True, "pause_handoff_hold": True, "workflow_budget_awareness": True, "direct_workflow_mutation_authority": False, "direct_network_authority": False, "automatic_scope_expansion": False})
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        row = self.workflow374._state_row(case_id)
        if row:
            wf = self.workflow374._payload(row)
            if wf.get("state") != "active":
                return {"case_id": case_id, "state": "case_workflow_hold", "hold_reason": f"workflow_{wf.get('state')}", "workflow": {"workflow_id": wf.get("workflow_id"), "state": wf.get("state"), "current_owner": wf.get("current_owner")}, "dossier": {"phase16_case_workflow_v374": {"state": wf.get("state"), "research_execution_held": True, "automatic_scope_expansion": False}}}
        out = self.base373.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict) and row:
            wf = self.workflow374._payload(row); usage = self.workflow374._usage(case_id, wf)
            dossier["phase16_case_workflow_v374"] = {"workflow_id": wf.get("workflow_id"), "state": wf.get("state"), "current_owner": wf.get("current_owner"), "case_remaining_requests": usage.get("case_remaining_requests"), "active_crawls": usage.get("active_crawls"), "direct_workflow_mutation_authority": False, "automatic_scope_expansion": False}
        return out


class DefensiveOpsecSupervisor374:
    def __init__(self, db: Any, audit: Any, *, base373: Any, workflow374: CaseWorkflow374, jobs: Any) -> None:
        self.db=db; self.audit=audit; self.base373=base373; self.workflow374=workflow374; self.jobs=jobs

    def status(self) -> dict[str, Any]:
        base = dict(self.base373.status())
        base.update({"policy_version": OPSEC_POLICY, "workflow_bypass_monitor": True, "workflow_budget_integrity_monitor": True, "paused_case_queue_monitor": True, "handoff_integrity_monitor": True, "forced_running_worker_kill": False, "system_mutations": False})
        return base

    def protect_remote_session(self, **kw: Any) -> dict[str, Any]: return self.base373.protect_remote_session(**kw)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base373.protect_case(case_id=case_id)
        invalid = self.workflow374.invalid_jobs(case_id=case_id)
        cancelled: list[str] = []
        for item in invalid:
            row = self.jobs.get(item["job_id"])
            if row.get("status") == "running":
                p = _j(row.get("payload_json"), {}) or {}; p["workflow_pause_requested_v374"] = True; p["opsec374_reason"] = item["reason"]
                self.workflow374._rehash_job(row["job_id"], payload=p)
            elif row.get("status") in {"queued", "workflow_paused"}:
                self.jobs.cancel(row["job_id"], actor="opsec374"); cancelled.append(row["job_id"])
        if invalid:
            self.audit.log("OPSEC374_WORKFLOW_BOUNDARY", "case", case_id, case_id=case_id, details={"invalid_jobs": invalid, "cancelled_jobs": cancelled, "policy": OPSEC_POLICY})
        return {**base, "workflow_invalid_jobs": invalid, "cancelled_workflow_jobs": cancelled, "policy_version": OPSEC_POLICY, "system_mutations": False}
