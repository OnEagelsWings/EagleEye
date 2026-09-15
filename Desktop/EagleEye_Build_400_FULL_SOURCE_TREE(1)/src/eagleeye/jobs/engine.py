from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

POLICY_VERSION = "phase15.job-engine.v1"
TERMINAL = {"succeeded", "failed", "cancelled", "dead_letter"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class PersistentJobEngine:
    """SQLite-backed durable queue with explicit worker claims.

    No background threads, network clients, or shell execution live here. A worker must
    explicitly claim a job and is still subject to the Search Capsule/OPSEC gateways.
    """

    def __init__(self, db: Any, *, actor: str = "local-analyst") -> None:
        self.db = db
        self.actor = actor

    def _event(self, job_id: str, event_type: str, details: dict[str, Any] | None = None, *, actor: str | None = None) -> None:
        now = _now()
        body = {"event_id": "jev_" + uuid.uuid4().hex[:24], "job_id": job_id, "event_type": event_type, "actor": actor or self.actor, "details_json": _canon(details or {}), "created_at": now}
        self.db.execute("INSERT INTO phase15_job_events(event_id,job_id,event_type,actor,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?)", (*body.values(), _sha(body)))

    def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        case_id: str = "",
        search_run_id: str = "",
        idempotency_key: str | None = None,
        max_attempts: int = 3,
        priority: int = 100,
        available_at: str | None = None,
        resource_budget: dict[str, Any] | None = None,
        rate_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = str(idempotency_key or _sha({"job_type": job_type, "payload": payload, "case_id": case_id, "search_run_id": search_run_id}))[:128]
        existing = self.db.one("SELECT * FROM phase15_jobs WHERE idempotency_key=?", (key,))
        if existing:
            return existing | {"deduplicated": True}
        now = _now()
        rb = resource_budget or {}
        resource = {
            "max_runtime_seconds": max(1, min(int(rb.get("max_runtime_seconds", 900)), 86400)),
            "max_memory_mb": max(32, min(int(rb.get("max_memory_mb", 512)), 32768)),
            "max_output_bytes": max(1024, min(int(rb.get("max_output_bytes", 10 * 1024 * 1024)), 1024 * 1024 * 1024)),
        }
        qb = rate_budget or {}
        rate = {
            "max_requests": max(0, min(int(qb.get("max_requests", 0)), 100000)),
            "requests_per_minute": max(0, min(int(qb.get("requests_per_minute", 0)), 10000)),
            "requests_consumed": 0,
        }
        row = {
            "job_id": "job_" + uuid.uuid4().hex[:24],
            "idempotency_key": key,
            "job_type": str(job_type)[:120],
            "case_id": str(case_id or "")[:128],
            "search_run_id": str(search_run_id or "")[:128],
            "status": "queued",
            "priority": max(0, min(int(priority), 1000)),
            "attempts": 0,
            "max_attempts": max(1, min(int(max_attempts), 20)),
            "available_at": available_at or now,
            "lease_owner": "",
            "lease_expires_at": "",
            "payload_json": _canon(payload),
            "resource_budget_json": _canon(resource),
            "rate_budget_json": _canon(rate),
            "checkpoint_json": "{}",
            "result_json": "{}",
            "error_text": "",
            "created_at": now,
            "updated_at": now,
        }
        row["record_hash"] = _sha(row)
        self.db.execute(
            "INSERT INTO phase15_jobs(job_id,idempotency_key,job_type,case_id,search_run_id,status,priority,attempts,max_attempts,available_at,lease_owner,lease_expires_at,payload_json,resource_budget_json,rate_budget_json,checkpoint_json,result_json,error_text,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        self._event(row["job_id"], "enqueued", {"idempotency_key": key})
        return row | {"deduplicated": False}

    def get(self, job_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (str(job_id),))
        if not row:
            raise KeyError(job_id)
        return row

    def list(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        n = max(1, min(int(limit), 500))
        if case_id:
            return self.db.all("SELECT * FROM phase15_jobs WHERE case_id=? ORDER BY priority ASC,created_at ASC LIMIT ?", (str(case_id), n))
        return self.db.all("SELECT * FROM phase15_jobs ORDER BY created_at DESC LIMIT ?", (n,))

    def claim(self, *, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        now = _now_dt()
        now_s = now.isoformat(timespec="seconds")
        expiry = (now + timedelta(seconds=max(30, min(int(lease_seconds), 3600)))).isoformat(timespec="seconds")
        with self.db.transaction(immediate=True):
            # Recover expired leases without losing attempt history.
            self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',updated_at=? WHERE status='running' AND lease_expires_at<>'' AND lease_expires_at<?", (now_s, now_s))
            row = self.db.one("SELECT job_id FROM phase15_jobs WHERE status='queued' AND available_at<=? ORDER BY priority ASC,created_at ASC LIMIT 1", (now_s,))
            if not row:
                return None
            cur = self.db.execute("UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'", (str(worker_id)[:120], expiry, now_s, row["job_id"]))
            if cur.rowcount != 1:
                return None
            claimed = self.get(row["job_id"])
            self._event(claimed["job_id"], "claimed", {"worker_id": worker_id, "lease_expires_at": expiry}, actor=worker_id)
            return claimed

    def checkpoint(self, job_id: str, checkpoint: dict[str, Any], *, worker_id: str) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] != "running" or row["lease_owner"] != worker_id:
            raise PermissionError("active worker lease required")
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET checkpoint_json=?,updated_at=? WHERE job_id=?", (_canon(checkpoint), now, job_id))
        self._event(job_id, "checkpoint", {"checkpoint": checkpoint}, actor=worker_id)
        return self.get(job_id)

    def consume_request_budget(self, job_id: str, *, worker_id: str, units: int = 1) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] != "running" or row["lease_owner"] != worker_id:
            raise PermissionError("active worker lease required")
        amount = max(1, int(units))
        budget = json.loads(row["rate_budget_json"] or "{}")
        maximum = int(budget.get("max_requests", 0))
        consumed = int(budget.get("requests_consumed", 0))
        if maximum <= 0:
            raise PermissionError("job has no external request budget")
        if consumed + amount > maximum:
            raise PermissionError("request budget exhausted")
        budget["requests_consumed"] = consumed + amount
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET rate_budget_json=?,updated_at=? WHERE job_id=?", (_canon(budget), now, job_id))
        self._event(job_id, "rate_budget_consumed", {"units": amount, "consumed": budget["requests_consumed"], "max_requests": maximum}, actor=worker_id)
        return self.get(job_id)

    def complete(self, job_id: str, result: dict[str, Any], *, worker_id: str) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] != "running" or row["lease_owner"] != worker_id:
            raise PermissionError("active worker lease required")
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET status='succeeded',result_json=?,lease_owner='',lease_expires_at='',updated_at=? WHERE job_id=?", (_canon(result), now, job_id))
        self._event(job_id, "succeeded", {"result_hash": _sha(result)}, actor=worker_id)
        return self.get(job_id)

    def fail(self, job_id: str, error: str, *, worker_id: str, retry_delay_seconds: int = 30) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] != "running" or row["lease_owner"] != worker_id:
            raise PermissionError("active worker lease required")
        dead = int(row["attempts"]) >= int(row["max_attempts"])
        status = "dead_letter" if dead else "queued"
        available = (_now_dt() + timedelta(seconds=max(0, min(int(retry_delay_seconds), 86400)))).isoformat(timespec="seconds")
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET status=?,error_text=?,available_at=?,lease_owner='',lease_expires_at='',updated_at=? WHERE job_id=?", (status, str(error)[:4000], available, now, job_id))
        self._event(job_id, "dead_letter" if dead else "retry_scheduled", {"error": str(error)[:500], "available_at": available}, actor=worker_id)
        return self.get(job_id)

    def cancel(self, job_id: str, *, actor: str | None = None) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] in TERMINAL:
            return row
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET status='cancelled',lease_owner='',lease_expires_at='',updated_at=? WHERE job_id=?", (now, job_id))
        self._event(job_id, "cancelled", actor=actor or self.actor)
        return self.get(job_id)

    def resume(self, job_id: str, *, actor: str | None = None) -> dict[str, Any]:
        row = self.get(job_id)
        if row["status"] not in {"cancelled", "failed", "dead_letter"}:
            raise ValueError("only stopped terminal jobs can be resumed explicitly")
        now = _now()
        self.db.execute("UPDATE phase15_jobs SET status='queued',attempts=0,available_at=?,lease_owner='',lease_expires_at='',error_text='',updated_at=? WHERE job_id=?", (now, now, job_id))
        self._event(job_id, "resumed", actor=actor or self.actor)
        return self.get(job_id)

    def stats(self) -> dict[str, Any]:
        rows = self.db.all("SELECT status,COUNT(*) c FROM phase15_jobs GROUP BY status")
        return {"policy": POLICY_VERSION, "counts": {r["status"]: int(r["c"]) for r in rows}, "runtime_background_workers": 0, "network_execution": False}
