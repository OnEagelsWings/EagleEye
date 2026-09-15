from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eagleeye.kernel.contracts import (
    ActionClass, AgentResult, AgentRole, AgentTask, ApprovalState,
    GatewayKind, ResultStatus,
)

POLICY_VERSION = "phase15.team-operations.v359"
EXPORT_CONTRACT = "phase15.dossier-export.v359"

ROLE_CAPABILITIES: dict[str, set[str]] = {
    "case_lead": {
        "case.read", "case.manage", "research.run", "crawler.run", "crawler.recover", "crawler.monitor",
        "source.review", "voice.read", "voice.research", "dossier.read", "dossier.write",
        "dossier.review", "dossier.export.request", "dossier.export.execute", "audit.read",
    },
    "investigator": {
        "case.read", "research.run", "crawler.run", "crawler.monitor", "voice.read", "voice.research",
        "dossier.read", "dossier.write",
    },
    "analyst": {
        "case.read", "research.run", "crawler.run", "crawler.monitor", "voice.read", "dossier.read", "dossier.write",
    },
    "reviewer": {
        "case.read", "crawler.monitor", "source.review", "voice.read", "dossier.read",
        "dossier.review", "dossier.export.approve", "audit.read",
    },
    "report_author": {"case.read", "voice.read", "dossier.read", "dossier.write"},
    "read_only": {"case.read", "voice.read", "dossier.read"},
}

CAPABILITY_TO_CANONICAL = {
    "case.read": "case.read",
    "case.manage": "case.assign",
    "research.run": "research.execute",
    "crawler.run": "research.execute",
    "crawler.recover": "research.execute",
    "crawler.monitor": "case.read",
    "source.review": "egress.approve",
    "voice.read": "case.read",
    "voice.research": "ai.execute",
    "dossier.read": "case.read",
    "dossier.write": "report.write",
    "dossier.review": "report.review",
    "dossier.export.request": "export.request",
    # execution/approval use the explicit v359 role matrix plus report review/request;
    # legacy governance does not expose a clean export.execute permission.
    "dossier.export.approve": "report.review",
    "dossier.export.execute": "export.request",
    "audit.read": "audit.read",
}

ROLE_RANK = {"case_lead": 100, "reviewer": 80, "investigator": 70, "analyst": 60, "report_author": 50, "read_only": 10}
MAX_ACTIVE_CRAWL_JOBS_PER_CASE = 12
MAX_CRAWL_AUTHORIZATIONS_PER_USER_CASE_HOUR = 12


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _j(v: Any, default: Any) -> Any:
    try:
        out = json.loads(str(v or ""))
        return out
    except Exception:
        return default


class TeamOperationsGovernance359:
    """Phase-15 team security boundary built on the canonical Phase-15 team identity layer.

    Users, password sessions, case memberships and access decisions use the small canonical Phase-15 team schema. Workflow decisions remain immutable AgentTask/AgentResult records.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        identity359: Any,
        build358: Any,
        task_repository: Any,
        job_engine: Any,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.identity = identity359
        self.build358 = build358
        self.tasks = task_repository
        self.jobs = job_engine
        self.base_dir = Path(base_dir)
        self.actor = actor

    def _identity(self, identity_or_username: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(identity_or_username, dict):
            identity = dict(identity_or_username)
            if not identity.get("username") or not identity.get("user_id"):
                raise PermissionError("authenticated identity required")
            return identity
        user = self.identity.public_user(str(identity_or_username))
        return {
            "user_id": user["user_id"], "username": user["username"], "display_name": user["display_name"],
            "global_role": user["global_role"], "session_id": "service359", "role_key": "",
        }

    def case_roles(self, identity_or_username: dict[str, Any] | str, case_id: str) -> list[str]:
        return self.identity.case_roles(self._identity(identity_or_username), case_id)

    def effective_capabilities(self, identity_or_username: dict[str, Any] | str, case_id: str) -> list[str]:
        identity = self._identity(identity_or_username)
        if identity.get("global_role") == "system_administrator":
            return sorted(set().union(*ROLE_CAPABILITIES.values()))
        caps: set[str] = set()
        for role in self.case_roles(identity, case_id):
            caps.update(ROLE_CAPABILITIES.get(role, set()))
        return sorted(caps)

    def authorize(self, identity_or_username: dict[str, Any] | str, *, case_id: str, capability: str, object_type: str = "", object_id: str = "") -> dict[str, Any]:
        identity = self._identity(identity_or_username); capability = str(capability)
        if capability not in CAPABILITY_TO_CANONICAL:
            raise PermissionError("unknown phase15 team capability")
        allowed = capability in set(self.effective_capabilities(identity, case_id))
        reason = "phase15_role_matrix" if allowed else "role_or_case_membership_denied"
        self.identity.record_access(user_id=identity["user_id"], username=identity["username"], session_id=identity.get("session_id", ""), case_id=case_id, capability=capability, allowed=allowed, reason=reason, object_type=object_type, object_id=object_id, details={"case_roles": self.case_roles(identity, case_id)})
        if not allowed:
            raise PermissionError(f"RBAC denied: {capability}")
        return {"allowed": True, "username": identity["username"], "case_id": case_id, "capability": capability, "case_roles": self.case_roles(identity, case_id)}

    def visible_cases(self, identity_or_username: dict[str, Any] | str) -> list[dict[str, Any]]:
        return self.identity.visible_cases(self._identity(identity_or_username))

    def create_case(self, *, identity: dict[str, Any] | str, title: str, client: str, purpose: str, legal_basis: str) -> dict[str, Any]:
        ident=self._identity(identity)
        self.identity.require_global(ident,"case.create")
        row=self.identity.cases.create_case(title,client,purpose,legal_basis)
        case_role="case_lead" if ident.get("global_role")=="system_administrator" else "investigator"
        self.identity.assign_case(identity=ident,case_id=row["case_id"],username=ident["username"],case_role=case_role,notes="Build 359 creator membership",bootstrap=True)
        return row

    def team_status(self, case_id: str = "") -> dict[str, Any]:
        memberships = self.identity.list_case_memberships(case_id)
        active = [m for m in memberships if bool(m.get("active"))]
        return {
            "policy_version": POLICY_VERSION, "canonical_identity_backend": "phase15_team_identity_v359",
            "identity_status": self.identity.status(), "default_deny": True, "case_scoped_rbac": True,
            "roles": {k: sorted(v) for k, v in ROLE_CAPABILITIES.items()}, "active_memberships": len(active),
            "membership_rows": active[:200], "anonymous_case_access": False, "voice_permission_boundary": True,
            "crawler_permission_boundary": True, "four_eyes_dossier_export": True,
        }

    def assign_case_role(self, *, identity: dict[str, Any] | str, case_id: str, username: str, case_role: str, notes: str = "") -> dict[str, Any]:
        if case_role not in ROLE_CAPABILITIES: raise ValueError("unsupported phase15 case role")
        ident=self._identity(identity)
        self.authorize(ident,case_id=case_id,capability="case.manage",object_type="membership",object_id=username)
        return self.identity.assign_case(identity=ident,case_id=case_id,username=username,case_role=case_role,notes=notes)

    def create_user(self, *, identity: dict[str, Any] | str, username: str, display_name: str, global_role: str, password: str) -> dict[str, Any]:
        ident=self._identity(identity)
        return self.identity.create_user(identity=ident,username=username,display_name=display_name,global_role=global_role,password=password)

    def revoke_case_role(self, *, identity: dict[str, Any] | str, case_id: str, username: str, case_role: str, reason: str) -> dict[str, Any]:
        ident=self._identity(identity)
        self.authorize(ident,case_id=case_id,capability="case.manage",object_type="membership",object_id=username)
        return self.identity.revoke_case_membership(identity=ident,case_id=case_id,username=username,case_role=case_role,reason=reason)

    def _task(self, task_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_agent_tasks WHERE task_id=?", (task_id,))
        if not row:
            raise KeyError(task_id)
        payload = _j(row.get("task_json"), {})
        return {**row, "task": payload, "input_payload": payload.get("input_payload") or {}}

    def _task_results(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM phase15_agent_results WHERE task_id=? ORDER BY created_at ASC", (task_id,))
        out=[]
        for r in rows:
            body=_j(r.get("result_json"), {})
            out.append({**r, "result": body, "output_payload": body.get("output_payload") or {}})
        return out

    def request_dossier_export(self, *, case_id: str, identity: dict[str, Any] | str, export_format: str = "json", report_id: str = "") -> dict[str, Any]:
        ident=self._identity(identity)
        self.authorize(ident, case_id=case_id, capability="dossier.export.request", object_type="dossier", object_id=report_id)
        fmt=str(export_format).lower().strip()
        if fmt not in {"json", "md"}:
            raise ValueError("export format must be json or md")
        dossier=self.build358.latest_investigation_dossier(case_id) or self.build358.build_investigation_dossier(case_id=case_id)
        requested_report=str(report_id or dossier.get("report_id") or "")
        task=AgentTask.create(
            case_id=case_id, actor=ident["username"], agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.EXPORT, requested_gateway=GatewayKind.EXPORT, approval_state=ApprovalState.PENDING,
            input_payload={"kind":"dossier_export_request_v359","contract":EXPORT_CONTRACT,"report_id":requested_report,"format":fmt,"dossier_hash":dossier.get("content_hash") or "","requested_by":ident["username"],"four_eyes_required":True},
        )
        saved=self.tasks.create_task(task)
        self.audit.log("TEAM359_EXPORT_REQUESTED", "dossier", requested_report or case_id, details={"case_id":case_id,"task_id":task.task_id,"actor":ident["username"],"format":fmt})
        return {"state":"pending_reviewer","task_id":task.task_id,"case_id":case_id,"report_id":requested_report,"format":fmt,"task":saved}

    def review_dossier_export(self, *, task_id: str, identity: dict[str, Any] | str, decision: str, rationale: str) -> dict[str, Any]:
        ident=self._identity(identity); row=self._task(task_id); case_id=str(row["case_id"]); inp=row["input_payload"]
        if inp.get("kind") != "dossier_export_request_v359":
            raise ValueError("not a build359 dossier export request")
        self.authorize(ident, case_id=case_id, capability="dossier.export.approve", object_type="dossier_export", object_id=task_id)
        if ident["username"].casefold() == str(inp.get("requested_by") or "").casefold():
            raise PermissionError("four-eyes review requires a different user")
        dec=str(decision).lower().strip()
        if dec not in {"approve", "deny"}:
            raise ValueError("decision must be approve or deny")
        if len(str(rationale or "").strip()) < 8:
            raise ValueError("review rationale must be documented")
        prior=[r for r in self._task_results(task_id) if (r.get("output_payload") or {}).get("kind")=="dossier_export_review_v359"]
        if prior:
            raise ValueError("export request already reviewed")
        output={"kind":"dossier_export_review_v359","decision":"approved" if dec=="approve" else "denied","reviewer":ident["username"],"rationale":str(rationale)[:1200],"reviewed_at":_now(),"same_actor_as_requester":False}
        result=AgentResult.create(task_id=task_id,status=ResultStatus.COMPLETED if dec=="approve" else ResultStatus.BLOCKED,output_payload=output,gateway_used=GatewayKind.NONE,policy_reason="four_eyes_review")
        saved=self.tasks.append_result(result)
        self.audit.log("TEAM359_EXPORT_REVIEWED", "dossier_export", task_id, details={"case_id":case_id,"reviewer":ident["username"],"decision":output["decision"]})
        return {**output,"result":saved}

    def export_status(self, task_id: str) -> dict[str, Any]:
        row=self._task(task_id); results=self._task_results(task_id); review=next(((x.get("output_payload") or {}) for x in results if (x.get("output_payload") or {}).get("kind")=="dossier_export_review_v359"), None); executed=next(((x.get("output_payload") or {}) for x in results if (x.get("output_payload") or {}).get("kind")=="dossier_export_execution_v359"), None)
        return {"task_id":task_id,"case_id":row["case_id"],"request":row["input_payload"],"review":review,"execution":executed,"ready_to_execute":bool(review and review.get("decision")=="approved" and not executed)}

    def execute_dossier_export(self, *, task_id: str, identity: dict[str, Any] | str) -> dict[str, Any]:
        ident=self._identity(identity); status=self.export_status(task_id); case_id=str(status["case_id"]); req=status["request"]
        self.authorize(ident, case_id=case_id, capability="dossier.export.execute", object_type="dossier_export", object_id=task_id)
        if not status["ready_to_execute"]:
            raise PermissionError("approved four-eyes review required before export")
        dossier=self.build358.latest_investigation_dossier(case_id) or self.build358.build_investigation_dossier(case_id=case_id)
        if str(req.get("dossier_hash") or "") and str(dossier.get("content_hash") or "") != str(req.get("dossier_hash")):
            raise PermissionError("dossier changed after export request; request a new review")
        fmt=req.get("format") or "json"; root=(self.base_dir/"exports"/"build359"/case_id)
        root.mkdir(parents=True,exist_ok=True)
        final=root/f"{task_id}.{fmt}"
        if fmt=="json":
            content=json.dumps(dossier,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8")
        else:
            lines=[f"# EagleEye Dossier {case_id}","",str(dossier.get("executive_summary") or ""),"","## Reviewed facts"]
            lines += [f"- {x.get('claim') or x.get('text') or x}" for x in dossier.get("facts") or []]
            lines += ["","## Hypotheses"] + [f"- {x.get('hypothesis') or x.get('text') or x}" for x in dossier.get("hypotheses") or []]
            lines += ["","## Open questions"] + [f"- {x}" for x in dossier.get("open_questions") or []]
            content=("\n".join(lines)+"\n").encode("utf-8")
        temp=final.with_suffix(final.suffix+".tmp")
        temp.write_bytes(content)
        try: temp.chmod(0o600)
        except OSError: pass
        os.replace(temp,final)
        digest=hashlib.sha256(content).hexdigest()
        out={"kind":"dossier_export_execution_v359","state":"exported","path":str(final.relative_to(self.base_dir)),"sha256":digest,"bytes":len(content),"format":fmt,"executed_by":ident["username"],"reviewed_by":status["review"].get("reviewer"),"dossier_hash":dossier.get("content_hash") or "","exported_at":_now()}
        result=AgentResult.create(task_id=task_id,status=ResultStatus.COMPLETED,output_payload=out,gateway_used=GatewayKind.EXPORT,policy_reason="four_eyes_export_executed")
        self.tasks.append_result(result)
        self.audit.log("TEAM359_EXPORT_EXECUTED", "dossier_export", task_id, details={"case_id":case_id,"actor":ident["username"],"sha256":digest,"path":out["path"]})
        return out

    def _voice_intent(self, intent_id: str) -> tuple[str, str]:
        row=self._task(intent_id); inp=row["input_payload"]
        if inp.get("kind") != "voice_interaction_v358":
            # gateway stores contract fields that may differ by exact kind; fall back to intent.
            pass
        return str(row["case_id"]), str(inp.get("intent") or "unknown")

    def voice_propose(self, *, identity: dict[str, Any] | str, case_id: str, transcript: str, mode: str = "command", source: str = "workspace_transcript") -> dict[str, Any]:
        self.authorize(identity, case_id=case_id, capability="voice.read", object_type="voice", object_id=case_id)
        return self.build358.voice_propose(case_id=case_id, transcript=transcript, mode=mode, source=source)

    def voice_transcribe(self, *, identity: dict[str, Any] | str, case_id: str, **kwargs: Any) -> dict[str, Any]:
        self.authorize(identity, case_id=case_id, capability="voice.read", object_type="voice", object_id=case_id)
        return self.build358.voice_transcribe(case_id=case_id, **kwargs)

    def voice_execute(self, *, identity: dict[str, Any] | str, intent_id: str, confirmed: bool = False, edited_transcript: str | None = None) -> dict[str, Any]:
        case_id,intent=self._voice_intent(intent_id)
        cap="voice.research" if intent in {"start_go","start_or_continue_research","continue_research_wave"} else "voice.read"
        if intent in {"refresh_dossier"}: cap="dossier.write"
        self.authorize(identity, case_id=case_id, capability=cap, object_type="voice_intent", object_id=intent_id)
        return self.build358.voice_execute(intent_id=intent_id,confirmed=confirmed,edited_transcript=edited_transcript)

    def enqueue_crawl(self, *, identity: dict[str, Any] | str, case_id: str, source_id: str) -> dict[str, Any]:
        ident=self._identity(identity)
        self.authorize(ident, case_id=case_id, capability="crawler.run", object_type="crawler_source", object_id=source_id)
        active=int((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type LIKE '%crawl%' AND status IN ('queued','running','retry_wait')",(case_id,)) or {}).get("c") or 0)
        if active >= MAX_ACTIVE_CRAWL_JOBS_PER_CASE:
            raise PermissionError("case crawl active-job quota reached")
        from datetime import timedelta
        cutoff=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec="seconds")
        recent=int((self.db.one("""SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=? AND created_at>=? AND json_extract(task_json,'$.input_payload.kind')='team_crawl_authorization_v359' AND json_extract(task_json,'$.input_payload.authorized_by')=?""",(case_id,cutoff,ident["username"])) or {}).get("c") or 0)
        if recent >= MAX_CRAWL_AUTHORIZATIONS_PER_USER_CASE_HOUR:
            raise PermissionError("user/case crawl authorization quota reached")
        # Persist an immutable authorization marker before delegating the actual bounded job.
        marker=AgentTask.create(case_id=case_id,actor=ident["username"],agent_role=AgentRole.INVESTIGATION_SUPERVISOR,action_class=ActionClass.EXTERNAL_RESEARCH,requested_gateway=GatewayKind.SEARCH,approval_state=ApprovalState.APPROVED,input_payload={"kind":"team_crawl_authorization_v359","source_id":source_id,"authorized_by":ident["username"],"policy":POLICY_VERSION,"quota":{"active_case_limit":MAX_ACTIVE_CRAWL_JOBS_PER_CASE,"user_case_hour_limit":MAX_CRAWL_AUTHORIZATIONS_PER_USER_CASE_HOUR}})
        self.tasks.create_task(marker)
        out=self.build358.enqueue_crawl(case_id=case_id,source_id=source_id)
        return {**out,"team_authorization_task_id":marker.task_id,"quota":{"active_case_limit":MAX_ACTIVE_CRAWL_JOBS_PER_CASE,"user_case_hour_limit":MAX_CRAWL_AUTHORIZATIONS_PER_USER_CASE_HOUR}}

    def review_crawler_source(self, *, identity: dict[str, Any] | str, case_id: str, source_id: str, decision: str, rationale: str) -> dict[str, Any]:
        ident=self._identity(identity)
        self.authorize(ident, case_id=case_id, capability="source.review", object_type="crawler_source", object_id=source_id)
        return self.build358.review_crawler_source(source_id,decision=decision,rationale=rationale,reviewer=ident["username"])

    def crawler_operational_snapshot(self, *, identity: dict[str, Any] | str, case_id: str) -> dict[str, Any]:
        self.authorize(identity, case_id=case_id, capability="crawler.monitor", object_type="crawler", object_id=case_id)
        rows=self.db.all("SELECT status,COUNT(*) c FROM phase15_jobs WHERE case_id=? GROUP BY status",(case_id,))
        counts={str(r["status"]):int(r["c"]) for r in rows}
        stale=int((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?",(case_id,_now())) or {}).get("c") or 0)
        authz=int((self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=? AND task_json LIKE '%team_crawl_authorization_v359%'",(case_id,)) or {}).get("c") or 0)
        base=dict(self.build358.crawler_status())
        return {**base,"crawler_improvement_build":359,"build359_rbac_crawl_permissions":True,"case_job_counts":counts,"expired_worker_leases":stale,"team_authorized_manual_crawls":authz,"recovery_requires_case_lead":True,"dead_letter_requires_human_attention":True,"soak_ready":True,"active_case_crawl_job_limit":MAX_ACTIVE_CRAWL_JOBS_PER_CASE,"user_case_crawl_authorizations_per_hour_limit":MAX_CRAWL_AUTHORIZATIONS_PER_USER_CASE_HOUR}

    def recover_expired_crawler_leases(self, *, identity: dict[str, Any] | str, case_id: str) -> dict[str, Any]:
        ident=self._identity(identity)
        self.authorize(ident, case_id=case_id, capability="crawler.recover", object_type="crawler", object_id=case_id)
        now=_now(); recovered=[]
        with self.db.transaction(immediate=True):
            rows=self.db.all("SELECT job_id,lease_owner,lease_expires_at FROM phase15_jobs WHERE case_id=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?",(case_id,now))
            for row in rows:
                self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',updated_at=? WHERE job_id=? AND status='running'",(now,row["job_id"]))
                event={"event_id":"jev_"+uuid.uuid4().hex[:24],"job_id":row["job_id"],"event_type":"lease_recovered_by_lead_v359","actor":ident["username"],"details_json":_canon({"expired_owner":row.get("lease_owner") or "","expired_at":row.get("lease_expires_at") or "","case_id":case_id}),"created_at":now}
                self.db.execute("INSERT INTO phase15_job_events(event_id,job_id,event_type,actor,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?)",(*event.values(),_sha(event)))
                recovered.append(row["job_id"])
        self.audit.log("TEAM359_CRAWLER_LEASE_RECOVERY","case",case_id,details={"actor":ident["username"],"recovered":len(recovered)})
        return {"case_id":case_id,"recovered_job_ids":recovered,"count":len(recovered),"actor":ident["username"]}

    def verify_audit_chain(self) -> dict[str, Any]:
        result=self.identity.verify_access_chain()
        return {"events":result.get("events",0),"chain_consistent":bool(result.get("ok")),"head_hash":result.get("head_hash","") ,"append_only_security_events":True}
