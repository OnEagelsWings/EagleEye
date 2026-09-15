from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping, Sequence

BUILD = "386.0"
POLICY_ID = "phase17.capability-scoped-go.v386"
CONFIRM_GO = "GO"
CONFIRM_REVOKE = "REVOKE"
MAX_TTL_MINUTES = 30
MIN_TTL_MINUTES = 1
ALLOWED_ACTION = "provider_live_enqueue"


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


@dataclass(frozen=True, slots=True)
class ExecutionGrantItem386:
    phase17_source_id: str
    canonical_source_id: str
    connector_key: str
    action: str
    request_budget: int
    requests_per_minute: int
    allowed_hosts_hash: str
    seed_urls_hash: str
    source_review_status: str
    source_enabled: bool


@dataclass(frozen=True, slots=True)
class ExecutionGrant386:
    grant_id: str
    case_id: str
    acquisition_packet_id: str
    acquisition_packet_hash: str
    workflow_id: str
    workflow_generation: int
    issued_by: str
    issued_at: str
    expires_at: str
    items: tuple[ExecutionGrantItem386, ...]
    operations_readiness_hash: str
    opsec_preflight_hash: str
    capability_scope_hash: str
    requires_explicit_go: bool = True
    go_confirmed: bool = True
    execution_authority_scope: str = "enqueue_only"
    direct_network_authority: bool = False
    automatic_execution: bool = False
    automatic_scope_expansion: bool = False
    required_execution_confirmation: str = "LIVE"
    policy_id: str = POLICY_ID

    @property
    def grant_hash(self) -> str:
        return _sha(asdict(self))


class ExecutionAuthority386:
    """Issue short-lived, case-scoped GO grants without executing network work.

    The grant binds the exact Build-385 acquisition packet, current canonical source review
    state, case-workflow generation and request budgets, local Operations readiness and
    defensive OPSEC boundary state. Only a token hash is persisted. Build 386 does not enqueue
    a crawler job and does not perform network I/O; execution remains a separate explicit gate.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        acquisition385: Any,
        workflow374: Any,
        operations365: Any,
        opsec380: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.acquisition385 = acquisition385
        self.workflow374 = workflow374
        self.operations365 = operations365
        self.opsec380 = opsec380
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS execution_grant_386 (
                grant_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                acquisition_packet_id TEXT NOT NULL,
                acquisition_packet_hash TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                scope_json TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                workflow_generation INTEGER NOT NULL,
                operations_readiness_hash TEXT NOT NULL,
                opsec_preflight_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                issued_by TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT NOT NULL DEFAULT '',
                record_hash TEXT NOT NULL,
                FOREIGN KEY(acquisition_packet_id) REFERENCES acquisition_packet_385(packet_id)
            );
            CREATE INDEX IF NOT EXISTS idx_execution_grant_386_case
                ON execution_grant_386(case_id, issued_at);
            CREATE INDEX IF NOT EXISTS idx_execution_grant_386_packet
                ON execution_grant_386(acquisition_packet_id, state, expires_at);
            """
        )
        self.db.conn.commit()

    def _packet_row(self, case_id: str, packet_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT packet_id,case_id,packet_hash,packet_json FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?",
            (packet_id, case_id),
        )
        if not row:
            raise KeyError(packet_id)
        return row

    def _workflow_status(self, *, case_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        return dict(self.workflow374.status(case_id=case_id, identity=dict(identity)))

    def _operations_preflight(self, case_id: str) -> dict[str, Any]:
        readiness = dict(self.operations365.readiness(case_id=case_id))
        breaker = bool(self.operations365.circuit_breaker_required(case_id=case_id))
        incidents = dict(self.operations365.incident_console(case_id=case_id))
        return {
            "local_operational_ready": bool(readiness.get("local_operational_ready")),
            "blockers": list(readiness.get("blockers") or []),
            "circuit_breaker_required": breaker,
            "critical_open": bool(incidents.get("critical_open")),
            "high_attention": bool(incidents.get("high_attention")),
            "audit_chain_consistent": bool(readiness.get("audit_chain_consistent")),
        }

    def _opsec_preflight(self, case_id: str) -> dict[str, Any]:
        status = dict(self.opsec380.status())
        invalid_jobs = list(self.workflow374.invalid_jobs(case_id=case_id))
        override_jobs = []
        checker = getattr(self.opsec380, "_override_jobs", None)
        if callable(checker):
            override_jobs = list(checker(case_id))
        return {
            "workflow_invalid_jobs": invalid_jobs,
            "production_override_jobs": override_jobs,
            "system_mutations": bool(status.get("system_mutations")),
            "firewall_mutation": bool(status.get("firewall_mutation")),
            "credential_mutation": bool(status.get("credential_mutation")),
            "automatic_release_authority": bool(status.get("automatic_release_authority")),
        }

    def preflight(
        self,
        *,
        case_id: str,
        packet_id: str,
        identity: Mapping[str, Any],
        source_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        self.governance.authorize(
            dict(identity), case_id=case_id, capability="crawler.run",
            object_type="phase17_execution_grant_v386", object_id=packet_id,
        )
        packet_row = self._packet_row(case_id, packet_id)
        packet = dict(_j(packet_row["packet_json"], {}))
        readiness = self.acquisition385.execution_readiness(case_id=case_id, packet_id=packet_id, identity=dict(identity))
        workflow = self._workflow_status(case_id=case_id, identity=identity)
        operations = self._operations_preflight(case_id)
        opsec = self._opsec_preflight(case_id)

        requested = {str(v) for v in (source_ids or ()) if str(v)}
        prep_by_phase17 = {str(p.get("source_id")): p for p in packet.get("preparations") or self.acquisition385.preparations(case_id=case_id, packet_id=packet_id)}
        ready_by_phase17 = {str(r.get("phase17_source_id")): r for r in readiness.get("prepared_sources") or []}
        packet_items = {str(i.get("source_id")): i for i in packet.get("items") or []}
        available = sorted(set(prep_by_phase17) & set(ready_by_phase17))
        selected = sorted(requested or set(available))
        blockers: list[str] = []
        rows: list[dict[str, Any]] = []

        if not selected:
            blockers.append("no_prepared_sources_selected")
        if requested - set(available):
            blockers.append("selected_source_not_prepared_in_packet")
        if workflow.get("state") != "active":
            blockers.append("case_workflow_not_active")
        if not operations.get("local_operational_ready") or operations.get("circuit_breaker_required"):
            blockers.append("operations_preflight_hold")
        if opsec.get("workflow_invalid_jobs") or opsec.get("production_override_jobs"):
            blockers.append("opsec_case_boundary_hold")
        if any(opsec.get(k) for k in ("system_mutations", "firewall_mutation", "credential_mutation", "automatic_release_authority")):
            blockers.append("opsec_policy_boundary_invalid")

        source_budgets = dict(workflow.get("source_budgets") or {})
        usage = dict(workflow.get("usage") or {})
        remaining_by_source = dict(usage.get("source_remaining_requests") or {})
        case_remaining = int(usage.get("case_remaining_requests") or 0)
        total_budget = 0

        for phase17_id in selected:
            prep = prep_by_phase17.get(phase17_id) or {}
            ready = ready_by_phase17.get(phase17_id) or {}
            item = packet_items.get(phase17_id) or {}
            canonical = str(prep.get("canonical_source_id") or "")
            row_blockers = list(ready.get("blockers") or [])
            source = self.db.one(
                "SELECT s.source_id,s.review_status,s.source_kind,p.enabled,p.max_pages,p.requests_per_minute,p.allowed_hosts_json,p.seed_urls_json "
                "FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
                (canonical,),
            ) if canonical else None
            if not source:
                row_blockers.append("canonical_source_missing")
                estimate = 0
            else:
                estimate = int(source.get("max_pages") or 0) + 3
                if str(source.get("review_status")) != "approved_read_only":
                    row_blockers.append("source_review_not_approved")
                if int(source.get("enabled") or 0) != 1:
                    row_blockers.append("source_not_enabled")
                if str(source.get("source_kind") or "") not in {"corporate_api", "public_money_api", "reference_api"}:
                    row_blockers.append("source_kind_not_provider_live")
                if canonical not in source_budgets:
                    row_blockers.append("source_not_in_workflow_budget")
                elif estimate > int(remaining_by_source.get(canonical, source_budgets.get(canonical, 0)) or 0):
                    row_blockers.append("source_request_budget_exceeded")
            total_budget += estimate
            if bool(item.get("plan_only")):
                row_blockers.append("phase17_source_plan_only")
            if not bool(item.get("phase16_live_eligible")):
                row_blockers.append("source_not_live_eligible")
            rows.append({
                "phase17_source_id": phase17_id,
                "canonical_source_id": canonical or None,
                "connector_key": prep.get("connector_key"),
                "action": ALLOWED_ACTION,
                "request_budget": estimate,
                "requests_per_minute": int((source or {}).get("requests_per_minute") or 0),
                "ready": not row_blockers,
                "blockers": sorted(set(row_blockers)),
                "source_review_status": (source or {}).get("review_status"),
                "source_enabled": bool(int((source or {}).get("enabled") or 0)),
                "allowed_hosts_hash": _sha(_j((source or {}).get("allowed_hosts_json"), [])),
                "seed_urls_hash": _sha(_j((source or {}).get("seed_urls_json"), [])),
            })
        if total_budget > case_remaining:
            blockers.append("case_request_budget_exceeded")
        if any(not r["ready"] for r in rows):
            blockers.append("one_or_more_sources_not_execution_ready")

        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "case_id": case_id,
            "packet_id": packet_id,
            "packet_hash": str(packet_row["packet_hash"]),
            "selected_sources": rows,
            "workflow": {
                "workflow_id": workflow.get("workflow_id"),
                "generation": int(workflow.get("generation") or 0),
                "state": workflow.get("state"),
                "case_remaining_requests": case_remaining,
                "total_requested_budget": total_budget,
            },
            "operations": operations,
            "opsec": opsec,
            "allowed": not blockers,
            "blockers": sorted(set(blockers)),
            "required_confirmation": CONFIRM_GO,
            "direct_network_authority": False,
            "automatic_execution": False,
            "network_requests_created": 0,
            "jobs_created": 0,
        }

    def issue_grant(
        self,
        *,
        case_id: str,
        packet_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
        source_ids: Sequence[str] | None = None,
        ttl_minutes: int = 10,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_GO:
            raise PermissionError(f"explicit confirmation {CONFIRM_GO} required")
        preflight = self.preflight(case_id=case_id, packet_id=packet_id, identity=identity, source_ids=source_ids)
        if not preflight["allowed"]:
            raise PermissionError("execution grant blocked: " + ",".join(preflight["blockers"]))
        ttl = max(MIN_TTL_MINUTES, min(int(ttl_minutes), MAX_TTL_MINUTES))
        issued = _now_dt()
        expires = issued + timedelta(minutes=ttl)
        actor = str(identity.get("username") or self.actor)[:120]
        items = tuple(
            ExecutionGrantItem386(
                phase17_source_id=str(r["phase17_source_id"]),
                canonical_source_id=str(r["canonical_source_id"]),
                connector_key=str(r.get("connector_key") or ""),
                action=ALLOWED_ACTION,
                request_budget=int(r["request_budget"]),
                requests_per_minute=int(r["requests_per_minute"]),
                allowed_hosts_hash=str(r["allowed_hosts_hash"]),
                seed_urls_hash=str(r["seed_urls_hash"]),
                source_review_status=str(r.get("source_review_status") or ""),
                source_enabled=bool(r.get("source_enabled")),
            )
            for r in preflight["selected_sources"]
        )
        operations_hash = _sha(preflight["operations"])
        opsec_hash = _sha(preflight["opsec"])
        scope_seed = {
            "case_id": case_id,
            "packet_id": packet_id,
            "packet_hash": preflight["packet_hash"],
            "workflow_id": preflight["workflow"]["workflow_id"],
            "workflow_generation": preflight["workflow"]["generation"],
            "items": [asdict(i) for i in items],
            "operations_hash": operations_hash,
            "opsec_hash": opsec_hash,
            "policy": POLICY_ID,
        }
        scope_hash = _sha(scope_seed)
        token = "go386_" + secrets.token_urlsafe(32)
        token_hash = _sha(token)
        grant_id = "grant386_" + secrets.token_hex(12)
        grant = ExecutionGrant386(
            grant_id=grant_id,
            case_id=case_id,
            acquisition_packet_id=packet_id,
            acquisition_packet_hash=str(preflight["packet_hash"]),
            workflow_id=str(preflight["workflow"]["workflow_id"]),
            workflow_generation=int(preflight["workflow"]["generation"]),
            issued_by=actor,
            issued_at=issued.isoformat(timespec="seconds"),
            expires_at=expires.isoformat(timespec="seconds"),
            items=items,
            operations_readiness_hash=operations_hash,
            opsec_preflight_hash=opsec_hash,
            capability_scope_hash=scope_hash,
        )
        scope_json = _canon(asdict(grant) | {"grant_hash": grant.grant_hash})
        record = {
            "grant_id": grant_id,
            "case_id": case_id,
            "acquisition_packet_id": packet_id,
            "acquisition_packet_hash": grant.acquisition_packet_hash,
            "token_hash": token_hash,
            "scope_json": scope_json,
            "workflow_id": grant.workflow_id,
            "workflow_generation": grant.workflow_generation,
            "operations_readiness_hash": operations_hash,
            "opsec_preflight_hash": opsec_hash,
            "state": "active",
            "issued_by": actor,
            "issued_at": grant.issued_at,
            "expires_at": grant.expires_at,
            "revoked_at": "",
        }
        record_hash = _sha(record)
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO execution_grant_386(grant_id,case_id,acquisition_packet_id,acquisition_packet_hash,token_hash,scope_json,workflow_id,workflow_generation,operations_readiness_hash,opsec_preflight_hash,state,issued_by,issued_at,expires_at,revoked_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*record.values(), record_hash),
            )
        self.audit.log(
            "PHASE17_386_GO_GRANTED", "execution_grant", grant_id, case_id=case_id,
            details={
                "packet_id": packet_id,
                "capability_scope_hash": scope_hash,
                "source_count": len(items),
                "request_budget": sum(i.request_budget for i in items),
                "expires_at": grant.expires_at,
                "direct_network_authority": False,
                "token_persisted_in_plaintext": False,
                "policy": POLICY_ID,
            },
        )
        return asdict(grant) | {
            "grant_hash": grant.grant_hash,
            "grant_token": token,
            "token_returned_once": True,
            "token_persisted_in_plaintext": False,
            "network_requests_created": 0,
            "jobs_created": 0,
        }

    def grant(self, *, case_id: str, grant_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM execution_grant_386 WHERE grant_id=? AND case_id=?", (grant_id, case_id))
        if not row:
            raise KeyError(grant_id)
        body = dict(_j(row["scope_json"], {}))
        body.update({
            "state": row["state"],
            "expires_at": row["expires_at"],
            "revoked_at": row["revoked_at"],
            "grant_token": None,
            "token_persisted_in_plaintext": False,
        })
        return body

    def verify_grant(
        self,
        *,
        case_id: str,
        grant_id: str,
        grant_token: str,
        identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.governance.authorize(
            dict(identity), case_id=case_id, capability="crawler.run",
            object_type="phase17_execution_grant_v386", object_id=grant_id,
        )
        row = self.db.one("SELECT * FROM execution_grant_386 WHERE grant_id=? AND case_id=?", (grant_id, case_id))
        if not row:
            raise KeyError(grant_id)
        blockers: list[str] = []
        if not secrets.compare_digest(str(row["token_hash"]), _sha(str(grant_token or ""))):
            blockers.append("invalid_grant_token")
        if str(row["state"]) != "active":
            blockers.append("grant_not_active")
        if _parse_dt(str(row["expires_at"])) <= _now_dt():
            blockers.append("grant_expired")
        scope = dict(_j(row["scope_json"], {}))
        packet = self._packet_row(case_id, str(row["acquisition_packet_id"]))
        if str(packet["packet_hash"]) != str(row["acquisition_packet_hash"]):
            blockers.append("acquisition_packet_hash_changed")
        try:
            current = self.preflight(
                case_id=case_id,
                packet_id=str(row["acquisition_packet_id"]),
                identity=identity,
                source_ids=[str(i.get("phase17_source_id")) for i in scope.get("items") or []],
            )
        except (PermissionError, KeyError) as exc:
            current = {"allowed": False, "blockers": [str(exc)], "workflow": {}, "operations": {}, "opsec": {}}
        if not current.get("allowed"):
            blockers.extend(["current_preflight_failed", *list(current.get("blockers") or [])])
        if str(current.get("workflow", {}).get("workflow_id") or "") != str(row["workflow_id"]):
            blockers.append("workflow_id_changed")
        if int(current.get("workflow", {}).get("generation") or 0) != int(row["workflow_generation"]):
            blockers.append("workflow_generation_changed")
        if _sha(current.get("operations") or {}) != str(row["operations_readiness_hash"]):
            blockers.append("operations_state_changed")
        if _sha(current.get("opsec") or {}) != str(row["opsec_preflight_hash"]):
            blockers.append("opsec_state_changed")
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "case_id": case_id,
            "grant_id": grant_id,
            "valid": not blockers,
            "blockers": sorted(set(blockers)),
            "capability_scope_hash": scope.get("capability_scope_hash"),
            "execution_authority_scope": scope.get("execution_authority_scope", "enqueue_only"),
            "direct_network_authority": False,
            "automatic_execution": False,
            "required_execution_confirmation": "LIVE",
            "network_requests_created": 0,
            "jobs_created": 0,
        }

    def revoke_grant(
        self,
        *,
        case_id: str,
        grant_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_REVOKE:
            raise PermissionError(f"explicit confirmation {CONFIRM_REVOKE} required")
        self.governance.authorize(
            dict(identity), case_id=case_id, capability="crawler.run",
            object_type="phase17_execution_grant_v386", object_id=grant_id,
        )
        row = self.db.one("SELECT state FROM execution_grant_386 WHERE grant_id=? AND case_id=?", (grant_id, case_id))
        if not row:
            raise KeyError(grant_id)
        now = _now()
        with self.db.conn:
            self.db.conn.execute(
                "UPDATE execution_grant_386 SET state='revoked',revoked_at=? WHERE grant_id=? AND case_id=? AND state='active'",
                (now, grant_id, case_id),
            )
        self.audit.log(
            "PHASE17_386_GO_REVOKED", "execution_grant", grant_id, case_id=case_id,
            details={"revoked_at": now, "policy": POLICY_ID},
        )
        return self.grant(case_id=case_id, grant_id=grant_id)

    def status(self) -> dict[str, Any]:
        row = self.db.one("SELECT COUNT(*) n FROM execution_grant_386") or {}
        active = self.db.one("SELECT COUNT(*) n FROM execution_grant_386 WHERE state='active' AND expires_at>?", (_now(),)) or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "grants": int(row.get("n") or 0),
            "active_unexpired_grants": int(active.get("n") or 0),
            "capability_scoped_go": True,
            "token_hash_only_persistence": True,
            "packet_hash_binding": True,
            "workflow_generation_binding": True,
            "operations_preflight_binding": True,
            "opsec_preflight_binding": True,
            "request_budget_binding": True,
            "grant_ttl_max_minutes": MAX_TTL_MINUTES,
            "direct_network_authority": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
            "host_security_mutation": False,
        }
