from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from eagleeye.crawler.engine import CrawlTransport

POLICY = "phase16.crawler-production.v369"
AI_POLICY = "phase16.autonomous-investigation.v369"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v369"
DEFAULT_INTERVAL_SECONDS = 3600
MIN_INTERVAL_SECONDS = 300
MAX_INTERVAL_SECONDS = 7 * 86400
DEFAULT_CASE_HIGH_WATERMARK = 8
DEFAULT_GLOBAL_HIGH_WATERMARK = 64
MAX_ENQUEUE_PER_TICK = 4
BLOCKING_HEALTH = {"offline", "authentication_required", "changed_contract", "rate_limited", "quarantined"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _dt(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class LeaseHeartbeatTransport369:
    """Transport decorator that renews only the already-claimed crawler lease.

    It adds no networking capability. Network behavior remains entirely defined by
    the injected underlying read-only transport and the existing Search Capsule /
    OPSEC crawler preflight.
    """

    def __init__(self, inner: CrawlTransport, supervisor: "ProductionCrawler369", *, job_id: str, worker_id: str, lease_seconds: int = 300) -> None:
        self.inner = inner
        self.supervisor = supervisor
        self.job_id = str(job_id)
        self.worker_id = str(worker_id)
        self.lease_seconds = max(60, min(int(lease_seconds), 1800))
        self.transport_kind = str(getattr(inner, "transport_kind", "unknown"))
        self.externally_configured = bool(getattr(inner, "externally_configured", False))

    def fetch(self, url: str, *, method: str = "GET", headers: Mapping[str, str] | None = None, timeout_seconds: int = 20, max_bytes: int = 2_000_000):
        self.supervisor.renew_lease(job_id=self.job_id, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        out = self.inner.fetch(url, method=method, headers=headers, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
        self.supervisor.renew_lease(job_id=self.job_id, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        return out


class ProductionCrawler369:
    """Production operations overlay for the existing bounded crawler.

    No per-build tables are added. Recurrence configuration is stored inside the
    existing ``phase15_crawler_policies.frontier_policy_json`` document; runtime
    truth continues to come from canonical jobs, crawl runs, fetches and source-
    health events.
    """

    def __init__(self, db: Any, audit: Any, *, build368: Any, jobs: Any, crawler: Any, connector_sdk: Any, governance: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build368 = build368
        self.jobs = jobs
        self.crawler = crawler
        self.connector_sdk = connector_sdk
        self.governance = governance
        self.actor = actor

    def _source(self, source_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
            (str(source_id),),
        )
        if not row:
            raise KeyError(source_id)
        return row

    def _production_config(self, row: Mapping[str, Any]) -> dict[str, Any]:
        policy = _json(row.get("frontier_policy_json"), {})
        cfg = dict(policy.get("production369") or {}) if isinstance(policy, dict) else {}
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "case_id": str(cfg.get("case_id") or ""),
            "interval_seconds": max(MIN_INTERVAL_SECONDS, min(int(cfg.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS), MAX_INTERVAL_SECONDS)),
            "max_backoff_seconds": max(DEFAULT_INTERVAL_SECONDS, min(int(cfg.get("max_backoff_seconds") or 86400), MAX_INTERVAL_SECONDS)),
            "failure_threshold": max(1, min(int(cfg.get("failure_threshold") or 3), 10)),
            "case_high_watermark": max(1, min(int(cfg.get("case_high_watermark") or DEFAULT_CASE_HIGH_WATERMARK), 100)),
            "global_high_watermark": max(4, min(int(cfg.get("global_high_watermark") or DEFAULT_GLOBAL_HIGH_WATERMARK), 1000)),
            "configured_at": str(cfg.get("configured_at") or ""),
            "configured_by": str(cfg.get("configured_by") or ""),
            "policy": str(cfg.get("policy") or POLICY),
        }

    def _is_connector_source(self, source_id: str) -> bool:
        return bool(self.db.one("SELECT source_id FROM phase15_connector_source_links WHERE source_id=?", (str(source_id),)))

    def configure_schedule(
        self,
        *,
        case_id: str,
        source_id: str,
        identity: dict[str, Any],
        confirmation: str,
        interval_minutes: int = 60,
        enabled: bool = True,
        failure_threshold: int = 3,
        max_backoff_minutes: int = 1440,
        case_high_watermark: int = DEFAULT_CASE_HIGH_WATERMARK,
        global_high_watermark: int = DEFAULT_GLOBAL_HIGH_WATERMARK,
    ) -> dict[str, Any]:
        self.governance.authorize(identity, case_id=case_id, capability="crawler.run", object_type="crawler_schedule", object_id=source_id)
        word = str(confirmation or "").strip().upper()
        required = "ENABLE" if enabled else "DISABLE"
        if word != required:
            raise PermissionError(f"explicit confirmation {required} required")
        row = self._source(source_id)
        if row["review_status"] != "approved_read_only" or int(row["enabled"]) != 1:
            raise PermissionError("human-reviewed approved source required")
        if str(row.get("auth_type") or "") != "none":
            raise PermissionError("production scheduler supports unauthenticated read-only sources only")
        if str(row.get("source_kind") or "") == "darknet_onion":
            raise PermissionError("Build 369 recurring scheduler does not schedule darknet sources; Build 370 gateway remains separate")
        if self._is_connector_source(source_id):
            raise PermissionError("connector sources keep their provider-specific LIVE gate and cannot be put on the generic recurring scheduler")
        outer = _json(row.get("frontier_policy_json"), {})
        if not isinstance(outer, dict):
            outer = {}
        cfg = {
            "enabled": bool(enabled),
            "case_id": str(case_id),
            "interval_seconds": max(MIN_INTERVAL_SECONDS, min(int(interval_minutes) * 60, MAX_INTERVAL_SECONDS)),
            "max_backoff_seconds": max(DEFAULT_INTERVAL_SECONDS, min(int(max_backoff_minutes) * 60, MAX_INTERVAL_SECONDS)),
            "failure_threshold": max(1, min(int(failure_threshold), 10)),
            "case_high_watermark": max(1, min(int(case_high_watermark), 100)),
            "global_high_watermark": max(4, min(int(global_high_watermark), 1000)),
            "configured_at": _now(),
            "configured_by": str(identity.get("username") or self.actor)[:160],
            "policy": POLICY,
        }
        outer["production369"] = cfg
        self.db.execute("UPDATE phase15_crawler_policies SET frontier_policy_json=?,updated_at=? WHERE source_id=?", (_canon(outer), _now(), source_id))
        self.audit.log("CRAWLER369_SCHEDULE_CONFIG", "crawler_source", source_id, case_id=case_id, details={"enabled": bool(enabled), "interval_seconds": cfg["interval_seconds"], "policy": POLICY})
        return {"source_id": source_id, "case_id": case_id, "schedule": cfg, "connector_live_gate_bypassed": False}

    def _run_rows(self, source_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.all(
            "SELECT * FROM phase15_crawl_runs WHERE source_id=? ORDER BY created_at DESC LIMIT ?",
            (str(source_id), max(1, min(int(limit), 100))),
        )

    def source_health(self, *, source_id: str) -> dict[str, Any]:
        row = self._source(source_id)
        cfg = self._production_config(row)
        runs = self._run_rows(source_id, 20)
        consecutive_failures = 0
        for r in runs:
            if str(r.get("status") or "") == "succeeded":
                break
            if str(r.get("status") or "") in {"failed", "paused"}:
                consecutive_failures += 1
        latest = runs[0] if runs else {}
        latest_success = next((r for r in runs if str(r.get("status") or "") == "succeeded"), {})
        fetch = self.db.one(
            "SELECT COUNT(f.fetch_id) c,COALESCE(AVG(f.elapsed_ms),0) avg_ms,COALESCE(MAX(f.elapsed_ms),0) max_ms,"
            "SUM(CASE WHEN f.status_code=429 THEN 1 ELSE 0 END) rate_limited,"
            "SUM(CASE WHEN f.status_code>=500 THEN 1 ELSE 0 END) server_errors,"
            "SUM(CASE WHEN f.change_state='unchanged_304' THEN 1 ELSE 0 END) not_modified,"
            "SUM(CASE WHEN f.change_state='unchanged_hash' THEN 1 ELSE 0 END) deduplicated,"
            "SUM(CASE WHEN f.change_state='changed' THEN 1 ELSE 0 END) changed_count,"
            "SUM(CASE WHEN f.change_state='new' THEN 1 ELSE 0 END) new_count "
            "FROM phase15_crawl_fetches f JOIN phase15_crawl_runs r ON r.crawl_run_id=f.crawl_run_id WHERE r.source_id=?",
            (str(source_id),),
        ) or {}
        policy_health = str(row.get("source_health") or "not_run")
        circuit_open = policy_health in BLOCKING_HEALTH or consecutive_failures >= int(cfg["failure_threshold"])
        interval = int(cfg["interval_seconds"])
        if policy_health == "degraded":
            interval = min(interval * 2, int(cfg["max_backoff_seconds"]))
        if consecutive_failures:
            interval = min(interval * (2 ** min(consecutive_failures, 6)), int(cfg["max_backoff_seconds"]))
        last_basis = _dt(str(latest.get("completed_at") or latest.get("started_at") or latest.get("created_at") or ""))
        next_due_dt = last_basis + timedelta(seconds=interval) if last_basis else None
        return {
            "policy": POLICY,
            "source_id": source_id,
            "source_health": policy_health,
            "schedule_enabled": bool(cfg["enabled"]),
            "schedule_case_id": cfg["case_id"],
            "interval_seconds_effective": interval,
            "consecutive_failed_or_paused_runs": consecutive_failures,
            "failure_threshold": int(cfg["failure_threshold"]),
            "circuit_open": circuit_open,
            "circuit_reason": policy_health if policy_health in BLOCKING_HEALTH else ("consecutive_failures" if consecutive_failures >= int(cfg["failure_threshold"]) else ""),
            "last_run_status": str(latest.get("status") or "not_run"),
            "last_run_at": str(latest.get("completed_at") or latest.get("started_at") or latest.get("created_at") or ""),
            "last_success_at": str(latest_success.get("completed_at") or latest_success.get("created_at") or ""),
            "next_due_at": next_due_dt.isoformat(timespec="seconds") if next_due_dt else "",
            "fetches": int(fetch.get("c") or 0),
            "avg_elapsed_ms": round(float(fetch.get("avg_ms") or 0), 2),
            "max_elapsed_ms": int(fetch.get("max_ms") or 0),
            "http_429": int(fetch.get("rate_limited") or 0),
            "http_5xx": int(fetch.get("server_errors") or 0),
            "delta_not_modified": int(fetch.get("not_modified") or 0),
            "delta_deduplicated": int(fetch.get("deduplicated") or 0),
            "delta_changed": int(fetch.get("changed_count") or 0),
            "delta_new": int(fetch.get("new_count") or 0),
            "automatic_identity_or_fact_promotion": False,
        }

    def backpressure(self, *, case_id: str) -> dict[str, Any]:
        global_counts = self.db.one(
            "SELECT COUNT(*) c,SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) running FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND status IN ('queued','running')"
        ) or {}
        case_counts = self.db.one(
            "SELECT COUNT(*) c,SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) running FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND case_id=? AND status IN ('queued','running')",
            (str(case_id),),
        ) or {}
        configs = []
        for row in self.db.all("SELECT frontier_policy_json FROM phase15_crawler_policies"):
            cfg = self._production_config(row)
            if cfg["enabled"] and cfg["case_id"] == case_id:
                configs.append(cfg)
        case_limit = min([int(c["case_high_watermark"]) for c in configs] or [DEFAULT_CASE_HIGH_WATERMARK])
        global_limit = min([int(c["global_high_watermark"]) for c in configs] or [DEFAULT_GLOBAL_HIGH_WATERMARK])
        global_depth = int(global_counts.get("c") or 0); case_depth = int(case_counts.get("c") or 0)
        return {
            "policy": POLICY,
            "case_id": case_id,
            "global_crawl_queue_depth": global_depth,
            "case_crawl_queue_depth": case_depth,
            "global_running": int(global_counts.get("running") or 0),
            "case_running": int(case_counts.get("running") or 0),
            "global_high_watermark": global_limit,
            "case_high_watermark": case_limit,
            "global_backpressure": global_depth >= global_limit,
            "case_backpressure": case_depth >= case_limit,
            "accept_new_scheduled_work": global_depth < global_limit and case_depth < case_limit,
        }

    def _active_source_job(self, source_id: str) -> bool:
        row = self.db.one(
            "SELECT COUNT(*) c FROM phase15_jobs j JOIN phase15_crawl_runs r ON r.search_run_id=j.search_run_id "
            "WHERE r.source_id=? AND j.job_type='governed_crawl_v1' AND j.status IN ('queued','running')",
            (str(source_id),),
        ) or {}
        return int(row.get("c") or 0) > 0

    def _enqueue_scheduled(self, *, case_id: str, source_id: str, cfg: Mapping[str, Any]) -> dict[str, Any]:
        source = self.crawler._source(source_id)
        if source["review_status"] != "approved_read_only" or int(source["enabled"]) != 1 or source["auth_type"] != "none":
            raise PermissionError("approved unauthenticated read-only source required")
        if source["source_kind"] == "darknet_onion" or self._is_connector_source(source_id):
            raise PermissionError("generic recurring scheduler cannot schedule darknet or provider-gated connector sources")
        capsule = self.crawler.build348.create_clearnet_capsule(case_id=case_id, egress_hosts=source["allowed_hosts"], max_requests=int(source["max_pages"]) + 3)
        search_run_id = capsule["search_run_id"]
        crawl_run_id = "crawl369_" + uuid.uuid4().hex[:20]
        now = _now()
        run = {"crawl_run_id": crawl_run_id, "case_id": case_id, "source_id": source_id, "search_run_id": search_run_id, "status": "queued", "pages_fetched": 0, "pages_stored": 0, "bytes_fetched": 0, "started_at": None, "completed_at": None, "created_at": now, "summary_json": "{}"}
        self.db.execute(
            "INSERT INTO phase15_crawl_runs(crawl_run_id,case_id,source_id,search_run_id,status,pages_fetched,pages_stored,bytes_fetched,started_at,completed_at,created_at,summary_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*run.values(), _sha(run)),
        )
        schedule_hash = _sha({k: cfg[k] for k in sorted(cfg) if k not in {"configured_by"}})
        job = self.jobs.enqueue(
            job_type="governed_crawl_v1",
            case_id=case_id,
            search_run_id=search_run_id,
            idempotency_key=f"crawl369:{crawl_run_id}",
            payload={"crawl_run_id": crawl_run_id, "source_id": source_id, "network_execution_by_build349_worker": True, "read_only": True, "phase16_crawler369_scheduled": True, "phase16_crawler369_schedule_hash": schedule_hash, "phase16_crawler369_case_id": case_id},
            max_attempts=3,
            priority=85,
            resource_budget={"max_runtime_seconds": 1800, "max_memory_mb": 512, "max_output_bytes": int(source["max_pages"]) * int(source["max_response_bytes"])},
            rate_budget={"max_requests": int(source["max_pages"]) + 3, "requests_per_minute": int(source["requests_per_minute"])},
        )
        self.audit.log("CRAWLER369_SCHEDULED", "crawl_run", crawl_run_id, case_id=case_id, details={"source_id": source_id, "job_id": job["job_id"], "schedule_hash": schedule_hash, "policy": POLICY})
        return {"crawl_run_id": crawl_run_id, "search_run_id": search_run_id, "job": job, "source_id": source_id, "scheduled": True}

    def scheduler_tick(self, *, case_id: str, identity: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        self.governance.authorize(identity, case_id=case_id, capability="crawler.run", object_type="crawler_scheduler", object_id=case_id)
        moment = now or _now_dt()
        pressure = self.backpressure(case_id=case_id)
        if not pressure["accept_new_scheduled_work"]:
            return {"policy": POLICY, "case_id": case_id, "state": "backpressure_hold", "scheduled": [], "skipped": [], "backpressure": pressure, "network_execution": False}
        scheduled: list[dict[str, Any]] = []; skipped: list[dict[str, Any]] = []
        rows = self.db.all(
            "SELECT s.source_id,s.review_status,s.source_kind,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE p.enabled=1 ORDER BY s.source_id"
        )
        for row in rows:
            cfg = self._production_config(row)
            if not cfg["enabled"] or cfg["case_id"] != case_id:
                continue
            sid = str(row["source_id"])
            if len(scheduled) >= MAX_ENQUEUE_PER_TICK:
                skipped.append({"source_id": sid, "reason": "tick_enqueue_cap"}); continue
            if self._is_connector_source(sid):
                skipped.append({"source_id": sid, "reason": "provider_live_gate_manual_only"}); continue
            if str(row.get("source_kind") or "") == "darknet_onion":
                skipped.append({"source_id": sid, "reason": "darknet_gateway_manual_only"}); continue
            if self._active_source_job(sid):
                skipped.append({"source_id": sid, "reason": "source_job_already_active"}); continue
            health = self.source_health(source_id=sid)
            if health["circuit_open"]:
                skipped.append({"source_id": sid, "reason": "source_health_circuit_open", "health": health["source_health"]}); continue
            due = _dt(health["next_due_at"])
            if due and due > moment:
                skipped.append({"source_id": sid, "reason": "not_due", "next_due_at": health["next_due_at"]}); continue
            pressure = self.backpressure(case_id=case_id)
            if not pressure["accept_new_scheduled_work"]:
                skipped.append({"source_id": sid, "reason": "backpressure_after_enqueue"}); break
            scheduled.append(self._enqueue_scheduled(case_id=case_id, source_id=sid, cfg=cfg))
        self.audit.log("CRAWLER369_SCHEDULER_TICK", "case", case_id, case_id=case_id, details={"scheduled": [x["crawl_run_id"] for x in scheduled], "skipped": skipped[:100], "policy": POLICY})
        return {"policy": POLICY, "case_id": case_id, "state": "ok", "scheduled": scheduled, "skipped": skipped, "backpressure": self.backpressure(case_id=case_id), "network_execution": False, "background_worker_started": False}

    def recover_expired_leases(self, *, case_id: str = "") -> dict[str, Any]:
        now = _now(); params: list[Any] = [now]
        where = "job_type='governed_crawl_v1' AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?"
        if case_id:
            where += " AND case_id=?"; params.append(case_id)
        rows = self.db.all(f"SELECT job_id,search_run_id,case_id,lease_owner,checkpoint_json FROM phase15_jobs WHERE {where}", tuple(params))
        recovered=[]
        with self.db.transaction(immediate=True):
            for row in rows:
                self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',available_at=?,updated_at=? WHERE job_id=? AND status='running'", (now, now, row["job_id"]))
                self.db.execute("UPDATE phase15_crawl_runs SET status='paused' WHERE search_run_id=? AND status='running'", (row["search_run_id"],))
                if hasattr(self.jobs, "_event"):
                    self.jobs._event(row["job_id"], "lease_recovered_369", {"previous_owner": row.get("lease_owner") or "", "checkpoint_preserved": bool(str(row.get("checkpoint_json") or "{}") != "{}")}, actor="crawler369")
                recovered.append(str(row["job_id"]))
        if recovered:
            self.audit.log("CRAWLER369_LEASE_RECOVERY", "crawler_jobs", case_id or "global", case_id=case_id, details={"jobs": recovered, "policy": POLICY})
        return {"policy": POLICY, "case_id": case_id, "recovered_jobs": recovered, "count": len(recovered), "checkpoint_preserved": True}

    def renew_lease(self, *, job_id: str, worker_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        seconds = max(60, min(int(lease_seconds), 1800)); now = _now_dt(); expiry = (now + timedelta(seconds=seconds)).isoformat(timespec="seconds")
        cur = self.db.execute("UPDATE phase15_jobs SET lease_expires_at=?,updated_at=? WHERE job_id=? AND status='running' AND lease_owner=?", (expiry, now.isoformat(timespec="seconds"), str(job_id), str(worker_id)))
        if cur.rowcount != 1:
            raise PermissionError("active crawler worker lease required")
        if hasattr(self.jobs, "_event"):
            self.jobs._event(str(job_id), "lease_heartbeat_369", {"lease_expires_at": expiry}, actor=str(worker_id))
        return self.jobs.get(str(job_id))

    def claim_next(self, *, worker_id: str, case_id: str = "", lease_seconds: int = 300) -> dict[str, Any] | None:
        self.recover_expired_leases(case_id=case_id)
        now = _now_dt(); now_s = now.isoformat(timespec="seconds"); expiry = (now + timedelta(seconds=max(60, min(int(lease_seconds), 1800)))).isoformat(timespec="seconds")
        with self.db.transaction(immediate=True):
            params: list[Any] = [now_s]
            case_clause = ""
            if case_id:
                case_clause = " AND case_id=?"; params.append(case_id)
            candidates = self.db.all(
                "SELECT job_id,payload_json,case_id FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND status='queued' AND available_at<=?" + case_clause + " ORDER BY priority ASC,created_at ASC LIMIT 20",
                tuple(params),
            )
            for row in candidates:
                payload = _json(row.get("payload_json"), {}); sid = str(payload.get("source_id") or "")
                if sid:
                    try:
                        if self.source_health(source_id=sid)["circuit_open"]:
                            continue
                    except Exception:
                        continue
                cur = self.db.execute("UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'", (str(worker_id)[:120], expiry, now_s, row["job_id"]))
                if cur.rowcount == 1:
                    claimed = self.jobs.get(row["job_id"])
                    if hasattr(self.jobs, "_event"):
                        self.jobs._event(row["job_id"], "claimed_production_369", {"worker_id": worker_id, "lease_expires_at": expiry}, actor=str(worker_id))
                    return claimed
        return None

    def record_production_health(self, *, source_id: str, crawl_run_id: str) -> dict[str, Any]:
        """Record crawler health while treating an absent robots.txt as normal.

        The legacy connector health helper counts every HTTP 404 as degraded. For
        a crawler, ``/robots.txt`` returning 404/410 simply means no robots file is
        published, so Build 369 excludes that expected discovery response from
        source availability scoring while keeping real 4xx/5xx/rate-limit/parser
        failures visible.
        """
        fetches=self.db.all("SELECT url,status_code,elapsed_ms,disposition,change_state FROM phase15_crawl_fetches WHERE crawl_run_id=? ORDER BY created_at",(str(crawl_run_id),))
        effective=[]; ignored_robots=0
        for f in fetches:
            url=str(f.get("url") or ""); code=int(f.get("status_code") or 0)
            is_robots=url.split("?",1)[0].rstrip("/").endswith("/robots.txt")
            if is_robots and code in {404,410}:
                ignored_robots+=1; continue
            effective.append(f)
        codes=[int(f.get("status_code") or 0) for f in effective if int(f.get("status_code") or 0)>0]
        dispositions=[str(f.get("disposition") or "") for f in effective]
        parses=self.db.all("SELECT status FROM phase15_parse_runs WHERE source_id=? ORDER BY created_at DESC LIMIT 100",(str(source_id),))
        parse_failures=sum(1 for p in parses if p.get("status")=="parse_failed")
        if any(c==429 for c in codes): status="rate_limited"
        elif any(c in {401,403} for c in codes): status="authentication_required"
        elif codes and all(c>=500 for c in codes): status="offline"
        elif parse_failures: status="changed_contract"
        elif any(c>=500 for c in codes) or any(x in {"fetch_error","sitemap_error","invalid_304"} for x in dispositions): status="degraded"
        elif any(c>=400 for c in codes): status="degraded"
        elif codes or ignored_robots: status="operational"
        else: status="not_run"
        detail={"crawl_run_id":crawl_run_id,"http_codes":codes[:100],"ignored_absent_robots":ignored_robots,"parse_failures":parse_failures,"samples":len(codes),"policy":POLICY}
        event={"health_id":"health369_"+uuid.uuid4().hex[:20],"source_id":source_id,"status":status,"details_json":_canon(detail),"created_at":_now()}
        self.db.execute("INSERT INTO phase15_source_health_events(health_id,source_id,status,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?)",(*event.values(),_sha(event)))
        self.db.execute("UPDATE phase15_crawler_policies SET source_health=?,updated_at=? WHERE source_id=?",(status,_now(),source_id))
        return {**event,"details":detail}

    def run_next(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], Sequence[str]] | None = None, case_id: str = "", lease_seconds: int = 300) -> dict[str, Any] | None:
        job = self.claim_next(worker_id=worker_id, case_id=case_id, lease_seconds=lease_seconds)
        if not job:
            return None
        cid = str(job.get("case_id") or "")
        # Run the inherited defensive supervisors before any network-capable work.
        if cid:
            self.build368.autonomous_opsec_protect(case_id=cid)
            job = self.jobs.get(job["job_id"])
            if job["status"] != "running" or job["lease_owner"] != worker_id:
                return {"state": "opsec_stopped", "job": job, "policy": POLICY}
        payload = _json(job.get("payload_json"), {}); source_id = str(payload.get("source_id") or "")
        wrapped = LeaseHeartbeatTransport369(transport, self, job_id=job["job_id"], worker_id=worker_id, lease_seconds=lease_seconds)
        result = self.crawler.execute_claimed_job(job_id=job["job_id"], worker_id=worker_id, transport=wrapped, resolver=resolver)
        crawl_run_id = str(payload.get("crawl_run_id") or "")
        health = self.record_production_health(source_id=source_id, crawl_run_id=crawl_run_id) if source_id and crawl_run_id else {}
        self.audit.log("CRAWLER369_WORKER_RESULT", "crawler_job", job["job_id"], case_id=cid, details={"crawl_run_id": crawl_run_id, "source_id": source_id, "status": result.get("status"), "source_health": health.get("status"), "policy": POLICY})
        return {"policy": POLICY, "job": result, "source_health_event": health, "lease_heartbeat": True, "transport_kind": wrapped.transport_kind}

    def soak_snapshot(self, *, case_id: str, limit: int = 200) -> dict[str, Any]:
        n = max(1, min(int(limit), 1000))
        rows = self.db.all("SELECT * FROM phase15_crawl_runs WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (str(case_id), n))
        succeeded = sum(1 for r in rows if r["status"] == "succeeded"); failed = sum(1 for r in rows if r["status"] == "failed"); paused = sum(1 for r in rows if r["status"] == "paused")
        resumed = errors = pages = bytes_total = 0
        for row in rows:
            summary = _json(row.get("summary_json"), {})
            resumed += int(bool(summary.get("resumed_from_checkpoint")))
            errors += int(summary.get("errors") or 0)
            pages += int(row.get("pages_fetched") or 0)
            bytes_total += int(row.get("bytes_fetched") or 0)
        stale = int((self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE case_id=? AND job_type='governed_crawl_v1' AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?", (case_id, _now())) or {}).get("c") or 0)
        lease_rec = int((self.db.one("SELECT COUNT(*) c FROM phase15_job_events e JOIN phase15_jobs j ON j.job_id=e.job_id WHERE j.case_id=? AND e.event_type='lease_recovered_369'", (case_id,)) or {}).get("c") or 0)
        scheduled_sources=[]
        for row in self.db.all("SELECT s.source_id,p.frontier_policy_json FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id"):
            cfg=self._production_config(row)
            if cfg["enabled"] and cfg["case_id"]==case_id:
                scheduled_sources.append(self.source_health(source_id=row["source_id"]))
        pressure=self.backpressure(case_id=case_id)
        return {
            "policy": POLICY, "case_id": case_id, "runs": len(rows), "succeeded": succeeded, "failed": failed, "paused": paused,
            "success_ratio": round(succeeded / len(rows), 4) if rows else 1.0, "resumed_from_checkpoint": resumed,
            "lease_recoveries": lease_rec, "stale_running_leases": stale, "pages_fetched": pages, "bytes_fetched": bytes_total,
            "crawler_errors": errors, "scheduled_sources": scheduled_sources, "open_source_circuits": sum(1 for s in scheduled_sources if s["circuit_open"]),
            "backpressure": pressure, "external_load_or_soak_validation": "not_run", "network_execution_by_snapshot": False,
        }

    def readiness(self, *, case_id: str) -> dict[str, Any]:
        soak=self.soak_snapshot(case_id=case_id)
        ready = soak["stale_running_leases"] == 0 and soak["open_source_circuits"] == 0 and not soak["backpressure"]["global_backpressure"] and not soak["backpressure"]["case_backpressure"]
        return {"policy": POLICY, "case_id": case_id, "ready_for_more_bounded_work": ready, "soak": soak, "human_review_required_for_dead_letter": True, "automatic_external_scope_expansion": False}

    def status(self) -> dict[str, Any]:
        scheduled=0
        for row in self.db.all("SELECT frontier_policy_json FROM phase15_crawler_policies"):
            scheduled += int(bool(self._production_config(row)["enabled"]))
        return {
            "policy": POLICY,
            "scheduled_sources": scheduled,
            "explicit_schedule_enable_required": True,
            "scheduler_tick_is_operator_orchestrated": True,
            "background_workers_started_on_boot": 0,
            "automatic_external_connections_on_boot": 0,
            "generic_connector_live_gate_bypass": False,
            "darknet_recurring_scheduler": False,
            "source_health_circuit_breaker": True,
            "queue_backpressure": True,
            "crawler_only_lease_recovery": True,
            "lease_heartbeat": True,
            "delta_conditional_fetch_inherited": True,
            "frontier_checkpoint_resume_inherited": True,
            "new_per_build_data_tables": 0,
            "production_release_ready": False,
        }


class AutonomousInvestigation369:
    def __init__(self, db: Any, *, base368: Any, crawler369: ProductionCrawler369):
        self.db=db; self.base368=base368; self.crawler369=crawler369

    def status(self) -> dict[str, Any]:
        base=dict(self.base368.status()); base.update({"policy_version":AI_POLICY,"crawler_production_preflight":True,"queue_backpressure_aware":True,"source_health_circuit_aware":True,"direct_scheduler_mutation_authority":False,"direct_worker_lease_mutation_authority":False}); return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        readiness=self.crawler369.readiness(case_id=case_id)
        if not readiness["ready_for_more_bounded_work"]:
            return {"state":"crawler_operations_hold","case_id":case_id,"reason":"crawler_production_backpressure_or_source_health_requires_resolution","lead_review_required":True,"dossier":{"case_id":case_id,"phase16_crawler_production_context":readiness,"lead_review_required":True,"facts":[],"hypotheses":[],"truthful_note":"No new research wave was started because Build-369 crawler production readiness was not green."}}
        out=self.base368.run_cycle(case_id=case_id,max_ticks=max_ticks); dossier=out.get("dossier")
        if isinstance(dossier,dict): dossier["phase16_crawler_production_context"]=readiness; dossier["crawler_production_requires_review"]=True; dossier["lead_review_required"]=True
        return out


class DefensiveOpsecSupervisor369:
    def __init__(self, db: Any, audit: Any, *, base368: Any, crawler369: ProductionCrawler369, jobs: Any):
        self.db=db; self.audit=audit; self.base368=base368; self.crawler369=crawler369; self.jobs=jobs

    def status(self) -> dict[str, Any]:
        base=dict(self.base368.status()); base.update({"policy_version":OPSEC_POLICY,"scheduled_job_integrity_monitor":True,"provider_live_gate_bypass_blocked":True,"darknet_recurring_scheduler_blocked":True,"source_health_circuit_breaker":True,"queue_backpressure_monitor":True,"automatic_job_resume_outside_expired_crawler_lease":False,"firewall_mutation":False,"os_mutation":False,"tor_configuration_mutation":False,"credential_mutation":False,"acl_mutation":False,"system_mutations":False}); return base

    def protect_remote_session(self, **kwargs: Any) -> dict[str, Any]: return self.base368.protect_remote_session(**kwargs)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base=self.base368.protect_case(case_id=case_id); cancelled=[]
        rows=self.db.all("SELECT job_id,payload_json FROM phase15_jobs WHERE case_id=? AND status IN ('queued','running') AND job_type='governed_crawl_v1'",(case_id,))
        for row in rows:
            payload=_json(row.get("payload_json"),{})
            if payload.get("phase16_crawler369_scheduled") is not True:
                continue
            sid=str(payload.get("source_id") or ""); invalid=False
            try:
                source=self.crawler369._source(sid); cfg=self.crawler369._production_config(source)
                invalid = not cfg["enabled"] or cfg["case_id"] != case_id or source["review_status"] != "approved_read_only" or int(source["enabled"]) != 1 or source["auth_type"] != "none" or source["source_kind"] == "darknet_onion" or self.crawler369._is_connector_source(sid)
                invalid = invalid or self.crawler369.source_health(source_id=sid)["circuit_open"]
            except Exception:
                invalid=True
            if invalid:
                self.jobs.cancel(row["job_id"],actor="opsec369"); cancelled.append(row["job_id"])
        if cancelled:
            self.audit.log("OPSEC369_SCHEDULED_CRAWL_CANCEL","case",case_id,case_id=case_id,details={"cancelled_jobs":cancelled,"policy":OPSEC_POLICY})
        return {**base,"cancelled_invalid_scheduled_crawls":cancelled,"crawler_production_readiness":self.crawler369.readiness(case_id=case_id),"policy_version":OPSEC_POLICY,"system_mutations":False}
