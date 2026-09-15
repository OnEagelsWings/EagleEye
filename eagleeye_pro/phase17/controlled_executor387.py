from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping

BUILD = "387.0"
POLICY_ID = "phase17.controlled-executor.v387"
CONFIRM_EXECUTE = "LIVE"
RESERVED_STATE = "reserved_387"
CONSUMED_STATE = "consumed_387"


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
class DispatchItem387:
    phase17_source_id: str
    canonical_source_id: str
    connector_key: str
    source_kind: str
    request_budget: int
    job_id: str
    crawl_run_id: str
    search_run_id: str


class ControlledExecutor387:
    """Consume one Build-386 GO grant exactly once and enqueue reviewed read-only work.

    Build 387 does *not* fetch any external resource itself. It converts a valid, unexpired,
    capability-scoped Build-386 grant into canonical Phase-16 crawler jobs only after an
    exact ``LIVE`` confirmation and a last-moment revalidation. Reservation, revalidation,
    enqueue, workflow tagging, dispatch receipt and grant consumption happen inside one
    SQLite IMMEDIATE transaction; an exception rolls the complete dispatch back.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        authority386: Any,
        workflow374: Any,
        build366: Any,
        build367: Any,
        build368: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.authority386 = authority386
        self.workflow374 = workflow374
        self.build366 = build366
        self.build367 = build367
        self.build368 = build368
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS execution_dispatch_387 (
                dispatch_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                grant_id TEXT NOT NULL UNIQUE,
                acquisition_packet_id TEXT NOT NULL,
                capability_scope_hash TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                workflow_generation INTEGER NOT NULL,
                source_ids_json TEXT NOT NULL,
                connector_keys_json TEXT NOT NULL,
                job_ids_json TEXT NOT NULL,
                dispatch_json TEXT NOT NULL,
                state TEXT NOT NULL,
                actor TEXT NOT NULL,
                reserved_at TEXT NOT NULL,
                enqueued_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                FOREIGN KEY(grant_id) REFERENCES execution_grant_386(grant_id),
                FOREIGN KEY(acquisition_packet_id) REFERENCES acquisition_packet_385(packet_id)
            );
            CREATE INDEX IF NOT EXISTS idx_execution_dispatch_387_case
                ON execution_dispatch_387(case_id, enqueued_at);
            CREATE INDEX IF NOT EXISTS idx_execution_dispatch_387_packet
                ON execution_dispatch_387(acquisition_packet_id, enqueued_at);
            """
        )
        self.db.conn.commit()

    def _grant_row(self, case_id: str, grant_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM execution_grant_386 WHERE grant_id=? AND case_id=?", (grant_id, case_id))
        if not row:
            raise KeyError(grant_id)
        return row

    def _validate_token_and_state(self, row: Mapping[str, Any], grant_token: str) -> None:
        if not secrets.compare_digest(str(row.get("token_hash") or ""), _sha(str(grant_token or ""))):
            raise PermissionError("invalid grant token")
        if str(row.get("state") or "") != "active":
            raise PermissionError("execution grant is not active")
        if _parse_dt(str(row.get("expires_at") or "1970-01-01T00:00:00+00:00")) <= _now_dt():
            raise PermissionError("execution grant expired")

    def _current_preflight(self, *, row: Mapping[str, Any], scope: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
        source_ids = [str(i.get("phase17_source_id") or "") for i in scope.get("items") or []]
        current = self.authority386.preflight(
            case_id=str(row["case_id"]),
            packet_id=str(row["acquisition_packet_id"]),
            identity=identity,
            source_ids=source_ids,
        )
        blockers: list[str] = []
        if not current.get("allowed"):
            blockers.extend(["current_preflight_failed", *list(current.get("blockers") or [])])
        packet = self.db.one(
            "SELECT packet_hash FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?",
            (row["acquisition_packet_id"], row["case_id"]),
        )
        if not packet or str(packet.get("packet_hash") or "") != str(row.get("acquisition_packet_hash") or ""):
            blockers.append("acquisition_packet_hash_changed")
        workflow = current.get("workflow") or {}
        if str(workflow.get("workflow_id") or "") != str(row.get("workflow_id") or ""):
            blockers.append("workflow_id_changed")
        if int(workflow.get("generation") or 0) != int(row.get("workflow_generation") or 0):
            blockers.append("workflow_generation_changed")
        if _sha(current.get("operations") or {}) != str(row.get("operations_readiness_hash") or ""):
            blockers.append("operations_state_changed")
        if _sha(current.get("opsec") or {}) != str(row.get("opsec_preflight_hash") or ""):
            blockers.append("opsec_state_changed")
        if _parse_dt(str(row.get("expires_at") or "1970-01-01T00:00:00+00:00")) <= _now_dt():
            blockers.append("grant_expired")
        if blockers:
            raise PermissionError("dispatch preflight blocked: " + ",".join(sorted(set(blockers))))
        return current

    def _workflow_budget_recheck(self, *, case_id: str, scope: Mapping[str, Any], identity: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        _row, workflow = self.workflow374._workflow(case_id)
        if str(workflow.get("state") or "") != "active":
            raise PermissionError("workflow_not_active")
        allocations: dict[str, int] = {}
        for item in scope.get("items") or []:
            sid = str(item.get("canonical_source_id") or "")
            if not sid:
                raise PermissionError("canonical_source_missing")
            allocations[sid] = allocations.get(sid, 0) + int(item.get("request_budget") or 0)
        check = self.workflow374._budget_check(case_id=case_id, payload=workflow, allocations=allocations)
        if not check.get("allowed"):
            raise PermissionError("workflow budget blocked: " + ",".join(check.get("reasons") or []))
        usage = check.get("usage") or {}
        if int(usage.get("active_crawls") or 0) + len(scope.get("items") or []) > int(workflow.get("max_active_crawls") or 1):
            raise PermissionError("workflow_active_crawl_limit")
        return workflow, allocations

    def _source_kind(self, source_id: str, connector_key: str) -> str:
        row = self.db.one(
            "SELECT s.source_kind,l.connector_key FROM phase15_sources s "
            "JOIN phase15_connector_source_links l ON l.source_id=s.source_id WHERE s.source_id=?",
            (source_id,),
        )
        if not row:
            raise KeyError(source_id)
        if str(row.get("connector_key") or "") != str(connector_key or ""):
            raise PermissionError("connector/source mismatch")
        return str(row.get("source_kind") or "")

    def _enqueue_live(self, *, case_id: str, source_id: str, source_kind: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        kwargs = {"case_id": case_id, "source_id": source_id, "identity": dict(identity), "confirmation": CONFIRM_EXECUTE}
        if source_kind == "corporate_api":
            return dict(self.build366.enqueue_corporate_live(**kwargs))
        if source_kind == "public_money_api":
            return dict(self.build367.enqueue_public_money_live(**kwargs))
        if source_kind == "reference_api":
            return dict(self.build368.enqueue_reference_live(**kwargs))
        raise PermissionError("source kind is not eligible for Build-387 controlled execution")

    def _tag_phase17_job(
        self,
        *,
        job_id: str,
        workflow: Mapping[str, Any],
        request_budget: int,
        actor: str,
        grant_id: str,
        dispatch_id: str,
        packet_id: str,
        capability_scope_hash: str,
    ) -> dict[str, Any]:
        tagged = self.workflow374._tag_crawl_job(
            job_id=job_id,
            workflow=workflow,
            reserved_requests=request_budget,
            actor=actor,
            origin="phase17_controlled_executor_v387",
        )
        payload = dict(_j(tagged.get("payload_json"), {}) or {})
        payload.update({
            "phase17_executor_v387": True,
            "phase17_grant_id": grant_id,
            "phase17_dispatch_id": dispatch_id,
            "phase17_acquisition_packet_id": packet_id,
            "phase17_capability_scope_hash": capability_scope_hash,
            "phase17_one_time_execution": True,
            "phase17_direct_fetch_by_executor": False,
            "automatic_scope_expansion": False,
        })
        return self.workflow374._rehash_job(job_id, payload=payload)

    def execute_grant(
        self,
        *,
        case_id: str,
        grant_id: str,
        grant_token: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_EXECUTE:
            raise PermissionError(f"explicit confirmation {CONFIRM_EXECUTE} required")
        self.governance.authorize(
            dict(identity), case_id=case_id, capability="crawler.run",
            object_type="phase17_controlled_execution_v387", object_id=grant_id,
        )
        actor = str(identity.get("username") or self.actor)[:120]
        reserved_at = _now()
        dispatch_id = "dispatch387_" + _sha({"case_id": case_id, "grant_id": grant_id, "reserved_at": reserved_at})[:24]

        with self.db.transaction(immediate=True):
            row = self._grant_row(case_id, grant_id)
            self._validate_token_and_state(row, grant_token)
            if self.db.one("SELECT dispatch_id FROM execution_dispatch_387 WHERE grant_id=?", (grant_id,)):
                raise PermissionError("grant already dispatched")
            scope = dict(_j(row.get("scope_json"), {}) or {})
            if not scope.get("items"):
                raise PermissionError("grant has no executable items")

            # Pre-reservation validation establishes the expected current state.
            self._current_preflight(row=row, scope=scope, identity=identity)
            workflow, allocations = self._workflow_budget_recheck(case_id=case_id, scope=scope, identity=identity)

            cur = self.db.execute(
                "UPDATE execution_grant_386 SET state=? WHERE grant_id=? AND case_id=? AND state='active' AND expires_at>?",
                (RESERVED_STATE, grant_id, case_id, _now()),
            )
            if cur.rowcount != 1:
                raise PermissionError("grant reservation race")

            # Last-moment post-reservation check closes the TOCTOU window before enqueue.
            reserved = self._grant_row(case_id, grant_id)
            if str(reserved.get("state")) != RESERVED_STATE:
                raise PermissionError("grant reservation lost")
            if _parse_dt(str(reserved.get("expires_at"))) <= _now_dt():
                raise PermissionError("grant expired after reservation")
            post = self.authority386.preflight(
                case_id=case_id,
                packet_id=str(reserved["acquisition_packet_id"]),
                identity=identity,
                source_ids=[str(i.get("phase17_source_id") or "") for i in scope.get("items") or []],
            )
            if not post.get("allowed"):
                raise PermissionError("post-reservation preflight failed: " + ",".join(post.get("blockers") or []))
            if str(post.get("packet_hash") or "") != str(reserved.get("acquisition_packet_hash") or ""):
                raise PermissionError("packet hash changed after reservation")
            if str(post.get("workflow", {}).get("workflow_id") or "") != str(reserved.get("workflow_id") or ""):
                raise PermissionError("workflow id changed after reservation")
            if int(post.get("workflow", {}).get("generation") or 0) != int(reserved.get("workflow_generation") or 0):
                raise PermissionError("workflow generation changed after reservation")
            if _sha(post.get("operations") or {}) != str(reserved.get("operations_readiness_hash") or ""):
                raise PermissionError("operations state changed after reservation")
            if _sha(post.get("opsec") or {}) != str(reserved.get("opsec_preflight_hash") or ""):
                raise PermissionError("opsec state changed after reservation")
            workflow, allocations = self._workflow_budget_recheck(case_id=case_id, scope=scope, identity=identity)

            dispatched: list[DispatchItem387] = []
            for item in scope.get("items") or []:
                source_id = str(item.get("canonical_source_id") or "")
                connector_key = str(item.get("connector_key") or "")
                request_budget = int(item.get("request_budget") or allocations.get(source_id, 0))
                source_kind = self._source_kind(source_id, connector_key)
                out = self._enqueue_live(case_id=case_id, source_id=source_id, source_kind=source_kind, identity=identity)
                job = dict(out.get("job") or {})
                job_id = str(job.get("job_id") or "")
                if not job_id:
                    raise RuntimeError("connector enqueue returned no job id")
                tagged = self._tag_phase17_job(
                    job_id=job_id,
                    workflow=workflow,
                    request_budget=request_budget,
                    actor=actor,
                    grant_id=grant_id,
                    dispatch_id=dispatch_id,
                    packet_id=str(reserved["acquisition_packet_id"]),
                    capability_scope_hash=str(scope.get("capability_scope_hash") or ""),
                )
                if str(tagged.get("status") or "") != "queued":
                    raise RuntimeError("Build-387 executor may only leave a queued job")
                if int(tagged.get("attempts") or 0) != 0:
                    raise RuntimeError("Build-387 executor must not claim/execute a job")
                dispatched.append(DispatchItem387(
                    phase17_source_id=str(item.get("phase17_source_id") or ""),
                    canonical_source_id=source_id,
                    connector_key=connector_key,
                    source_kind=source_kind,
                    request_budget=request_budget,
                    job_id=job_id,
                    crawl_run_id=str(out.get("crawl_run_id") or ""),
                    search_run_id=str(out.get("search_run_id") or ""),
                ))

            enqueued_at = _now()
            body = {
                "build": BUILD,
                "policy": POLICY_ID,
                "dispatch_id": dispatch_id,
                "case_id": case_id,
                "grant_id": grant_id,
                "acquisition_packet_id": str(reserved["acquisition_packet_id"]),
                "capability_scope_hash": str(scope.get("capability_scope_hash") or ""),
                "workflow_id": str(reserved["workflow_id"]),
                "workflow_generation": int(reserved["workflow_generation"]),
                "items": [asdict(i) for i in dispatched],
                "actor": actor,
                "reserved_at": reserved_at,
                "enqueued_at": enqueued_at,
                "grant_consumed": True,
                "direct_network_fetch_by_executor": False,
                "worker_execution_started": False,
                "automatic_scope_expansion": False,
            }
            record = {
                "dispatch_id": dispatch_id,
                "case_id": case_id,
                "grant_id": grant_id,
                "acquisition_packet_id": str(reserved["acquisition_packet_id"]),
                "capability_scope_hash": str(scope.get("capability_scope_hash") or ""),
                "workflow_id": str(reserved["workflow_id"]),
                "workflow_generation": int(reserved["workflow_generation"]),
                "source_ids_json": _canon([i.canonical_source_id for i in dispatched]),
                "connector_keys_json": _canon([i.connector_key for i in dispatched]),
                "job_ids_json": _canon([i.job_id for i in dispatched]),
                "dispatch_json": _canon(body),
                "state": "enqueued",
                "actor": actor,
                "reserved_at": reserved_at,
                "enqueued_at": enqueued_at,
            }
            self.db.execute(
                "INSERT INTO execution_dispatch_387(dispatch_id,case_id,grant_id,acquisition_packet_id,capability_scope_hash,workflow_id,workflow_generation,source_ids_json,connector_keys_json,job_ids_json,dispatch_json,state,actor,reserved_at,enqueued_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*record.values(), _sha(record)),
            )
            cur = self.db.execute(
                "UPDATE execution_grant_386 SET state=? WHERE grant_id=? AND case_id=? AND state=?",
                (CONSUMED_STATE, grant_id, case_id, RESERVED_STATE),
            )
            if cur.rowcount != 1:
                raise RuntimeError("grant consumption race")
            self.audit.log(
                "PHASE17_387_GRANT_EXECUTED", "execution_dispatch", dispatch_id, case_id=case_id,
                details={
                    "grant_id": grant_id,
                    "packet_id": reserved["acquisition_packet_id"],
                    "capability_scope_hash": scope.get("capability_scope_hash"),
                    "job_ids": [i.job_id for i in dispatched],
                    "source_count": len(dispatched),
                    "request_budget": sum(i.request_budget for i in dispatched),
                    "direct_network_fetch_by_executor": False,
                    "grant_token_persisted": False,
                    "policy": POLICY_ID,
                },
            )

        return body | {
            "jobs_enqueued": len(dispatched),
            "job_ids": [i.job_id for i in dispatched],
            "network_fetches_executed": 0,
            "grant_token_persisted": False,
        }

    def dispatch(self, *, case_id: str, dispatch_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM execution_dispatch_387 WHERE dispatch_id=? AND case_id=?", (dispatch_id, case_id))
        if not row:
            raise KeyError(dispatch_id)
        body = dict(_j(row.get("dispatch_json"), {}) or {})
        body.update({"state": row.get("state"), "record_hash": row.get("record_hash")})
        return body

    def verify_dispatch_record(self, *, case_id: str, dispatch_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM execution_dispatch_387 WHERE dispatch_id=? AND case_id=?", (dispatch_id, case_id))
        if not row:
            raise KeyError(dispatch_id)
        expected = _sha({k: row[k] for k in row if k != "record_hash"})
        jobs = list(_j(row.get("job_ids_json"), []) or [])
        job_rows = [self.db.one("SELECT job_id,status,attempts,payload_json FROM phase15_jobs WHERE job_id=?", (jid,)) for jid in jobs]
        return {
            "dispatch_id": dispatch_id,
            "record_hash_valid": secrets.compare_digest(str(row.get("record_hash") or ""), expected),
            "jobs_present": all(bool(v) for v in job_rows),
            "all_jobs_workflow_tagged": all((_j((v or {}).get("payload_json"), {}) or {}).get("phase17_executor_v387") is True for v in job_rows),
            "all_jobs_unclaimed": all(str((v or {}).get("status") or "") == "queued" and int((v or {}).get("attempts") or 0) == 0 for v in job_rows),
            "job_count": len(jobs),
        }

    def status(self) -> dict[str, Any]:
        total = int((self.db.one("SELECT COUNT(*) n FROM execution_dispatch_387") or {}).get("n") or 0)
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "dispatches": total,
            "one_time_grant_consumption": True,
            "atomic_reserve_revalidate_enqueue_consume": True,
            "post_reservation_revalidation": True,
            "workflow_budget_recheck": True,
            "phase16_connector_gate_reuse": True,
            "direct_network_fetch_by_executor": False,
            "worker_claim_by_executor": False,
            "automatic_scope_expansion": False,
            "host_security_mutation": False,
        }
