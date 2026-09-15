from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

POLICY = "phase16.operations.v365"
AI_POLICY = "phase16.autonomous-investigation.v365"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v365"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _stable_id(prefix: str, value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return prefix + hashlib.sha256(raw).hexdigest()[:24]


class OperationsTelemetry365:
    """Case-scoped operational observability over the consolidated Phase-15 ledger.

    Build 365 deliberately creates no per-build telemetry tables. The operations
    view is derived from canonical jobs, crawler, security, evidence/search and
    audit ledgers so there is one source of truth and no silent duplicate state.
    """

    def __init__(self, db: Any, audit: Any, *, jobs: Any, build364: Any, governance: Any):
        self.db = db
        self.audit = audit
        self.jobs = jobs
        self.build364 = build364
        self.governance = governance

    def _scope(self, case_id: str, column: str = "case_id") -> tuple[str, tuple[Any, ...]]:
        if case_id:
            return f" WHERE {column}=?", (case_id,)
        return "", ()

    def worker_health(self, *, case_id: str = "") -> dict[str, Any]:
        now = _now()
        where, params = self._scope(case_id)
        rows = self.db.all(
            "SELECT lease_owner,COUNT(*) AS active_jobs,MIN(lease_expires_at) AS earliest_lease,MAX(lease_expires_at) AS latest_lease "
            "FROM phase15_jobs" + where + (" AND" if where else " WHERE") + " status='running' GROUP BY lease_owner ORDER BY lease_owner",
            params,
        )
        workers = []
        for row in rows:
            expiry = str(row.get("earliest_lease") or "")
            stale = bool(expiry and expiry < now)
            workers.append({
                "worker_id": str(row.get("lease_owner") or "unassigned"),
                "active_jobs": int(row.get("active_jobs") or 0),
                "earliest_lease": expiry,
                "latest_lease": str(row.get("latest_lease") or ""),
                "state": "stale" if stale else "healthy",
            })
        stale = int((self.db.one(
            "SELECT COUNT(*) c FROM phase15_jobs" + where + (" AND" if where else " WHERE") + " status='running' AND lease_expires_at<>'' AND lease_expires_at<?",
            (*params, now),
        ) or {}).get("c") or 0)
        return {
            "policy": POLICY,
            "case_id": case_id,
            "workers": workers,
            "running_jobs": sum(int(x["active_jobs"]) for x in workers),
            "expired_worker_leases": stale,
            "healthy": stale == 0,
            "runtime_background_workers_declared": 0,
            "network_execution_by_telemetry": False,
        }

    def metrics(self, *, case_id: str = "") -> dict[str, Any]:
        where, params = self._scope(case_id)
        job_rows = self.db.all("SELECT status,COUNT(*) c FROM phase15_jobs" + where + " GROUP BY status", params)
        job_counts = {str(r["status"]): int(r["c"]) for r in job_rows}
        crawl_rows = self.db.all("SELECT status,COUNT(*) c FROM phase15_crawl_runs" + where + " GROUP BY status", params)
        crawl_counts = {str(r["status"]): int(r["c"]) for r in crawl_rows}
        fetch_sql = (
            "SELECT COUNT(f.fetch_id) c,COALESCE(AVG(f.elapsed_ms),0) avg_ms,COALESCE(MAX(f.elapsed_ms),0) max_ms,"
            "COALESCE(SUM(f.size_bytes),0) bytes FROM phase15_crawl_fetches f JOIN phase15_crawl_runs r ON r.crawl_run_id=f.crawl_run_id"
        )
        fetch_params: tuple[Any, ...] = ()
        if case_id:
            fetch_sql += " WHERE r.case_id=?"
            fetch_params = (case_id,)
        fetch = self.db.one(fetch_sql, fetch_params) or {}
        sec_rows = self.db.all("SELECT severity,COUNT(*) c FROM phase15_security_events" + where + " GROUP BY severity", params)
        security = {str(r["severity"] or "unknown").casefold(): int(r["c"]) for r in sec_rows}
        objects = int((self.db.one("SELECT COUNT(*) c FROM phase15_objects" + where, params) or {}).get("c") or 0)
        search_docs = int((self.db.one("SELECT COUNT(*) c FROM phase15_search_documents" + where, params) or {}).get("c") or 0)
        audit_where, audit_params = self._scope(case_id)
        audits = int((self.db.one("SELECT COUNT(*) c FROM audit_events" + audit_where, audit_params) or {}).get("c") or 0)
        workers = self.worker_health(case_id=case_id)
        base = self.build364.phase16_status()
        return {
            "policy": POLICY,
            "case_id": case_id,
            "job_counts": job_counts,
            "crawler_run_counts": crawl_counts,
            "fetches": {"count": int(fetch.get("c") or 0), "avg_elapsed_ms": round(float(fetch.get("avg_ms") or 0), 2), "max_elapsed_ms": int(fetch.get("max_ms") or 0), "bytes": int(fetch.get("bytes") or 0)},
            "evidence_objects": objects,
            "search_documents": search_docs,
            "security_events_by_severity": security,
            "audit_events": audits,
            "worker_health": workers,
            "inherited_remote_mode": bool((base.get("remote_team") or {}).get("remote_enabled")),
            "external_operations_validation": "not_run",
            "network_execution_by_metrics": False,
        }

    def trace(self, *, case_id: str, limit: int = 200) -> dict[str, Any]:
        n = max(1, min(int(limit), 1000))
        events: list[dict[str, Any]] = []
        for row in self.db.all(
            "SELECT e.event_id,e.event_type,e.actor,e.details_json,e.created_at,j.job_id,j.job_type,j.search_run_id "
            "FROM phase15_job_events e JOIN phase15_jobs j ON j.job_id=e.job_id WHERE j.case_id=? ORDER BY e.created_at DESC LIMIT ?",
            (case_id, n),
        ):
            events.append({"time": row["created_at"], "kind": "job", "event_id": row["event_id"], "event_type": row["event_type"], "actor": row["actor"], "job_id": row["job_id"], "job_type": row["job_type"], "search_run_id": row["search_run_id"], "details": _json(row.get("details_json"), {})})
        for row in self.db.all(
            "SELECT * FROM phase15_security_events WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, n)
        ):
            events.append({"time": row["created_at"], "kind": "security", "event_id": row["security_event_id"], "event_type": row["event_type"], "severity": row["severity"], "disposition": row["disposition"], "search_run_id": row.get("search_run_id") or "", "details": _json(row.get("evidence_json"), {})})
        for row in self.db.all(
            "SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp DESC LIMIT ?", (case_id, n)
        ):
            events.append({"time": row["timestamp"], "kind": "audit", "event_id": row["event_id"], "event_type": row["action"], "actor": row["actor"], "object_type": row["object_type"], "object_id": row.get("object_id") or "", "details": _json(row.get("details_json"), {})})
        events.sort(key=lambda e: (str(e.get("time") or ""), str(e.get("event_id") or "")), reverse=True)
        events = events[:n]
        return {
            "policy": POLICY,
            "case_id": case_id,
            "events": events,
            "event_count": len(events),
            "trace_id": _stable_id("trace_", {"case_id": case_id, "events": [(e["kind"], e["event_id"]) for e in events]}),
            "cross_case_data_included": False,
        }

    def incident_console(self, *, case_id: str) -> dict[str, Any]:
        incidents: list[dict[str, Any]] = []
        security = self.db.all(
            "SELECT * FROM phase15_security_events WHERE case_id=? ORDER BY created_at DESC LIMIT 500", (case_id,)
        )
        for row in security:
            sev = str(row.get("severity") or "unknown").casefold()
            disp = str(row.get("disposition") or "").casefold()
            if sev not in {"high", "critical"} and disp not in {"block", "blocked", "cancel", "cancelled", "pause", "paused", "quarantine", "quarantined", "isolate", "isolated"}:
                continue
            incidents.append({
                "incident_id": _stable_id("inc_", ["security", row["security_event_id"]]),
                "category": "security",
                "severity": sev,
                "state": "contained" if disp in {"block", "blocked", "cancel", "cancelled", "quarantine", "quarantined", "isolate", "isolated"} else "attention",
                "source_id": row["security_event_id"],
                "event_type": row["event_type"],
                "disposition": row["disposition"],
                "created_at": row["created_at"],
                "evidence": _json(row.get("evidence_json"), {}),
            })
        for row in self.db.all(
            "SELECT job_id,job_type,status,error_text,attempts,max_attempts,updated_at FROM phase15_jobs WHERE case_id=? AND status IN ('failed','dead_letter') ORDER BY updated_at DESC LIMIT 500", (case_id,)
        ):
            incidents.append({
                "incident_id": _stable_id("inc_", ["job", row["job_id"], row["status"]]),
                "category": "job_failure",
                "severity": "high" if row["status"] == "dead_letter" else "medium",
                "state": "attention",
                "source_id": row["job_id"],
                "event_type": row["job_type"],
                "disposition": row["status"],
                "created_at": row["updated_at"],
                "evidence": {"error": row.get("error_text") or "", "attempts": int(row.get("attempts") or 0), "max_attempts": int(row.get("max_attempts") or 0)},
            })
        now = _now()
        for row in self.db.all(
            "SELECT job_id,job_type,lease_owner,lease_expires_at,updated_at FROM phase15_jobs WHERE case_id=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<? ORDER BY lease_expires_at ASC LIMIT 500", (case_id, now)
        ):
            incidents.append({
                "incident_id": _stable_id("inc_", ["stale_lease", row["job_id"], row["lease_expires_at"]]),
                "category": "stale_worker_lease",
                "severity": "high",
                "state": "attention",
                "source_id": row["job_id"],
                "event_type": row["job_type"],
                "disposition": "recovery_required",
                "created_at": row["updated_at"],
                "evidence": {"worker_id": row.get("lease_owner") or "", "lease_expires_at": row.get("lease_expires_at") or ""},
            })
        incidents.sort(key=lambda x: (str(x.get("created_at") or ""), x["incident_id"]), reverse=True)
        counts: dict[str, int] = {}
        for incident in incidents:
            counts[incident["severity"]] = counts.get(incident["severity"], 0) + 1
        return {
            "policy": POLICY,
            "case_id": case_id,
            "incidents": incidents,
            "count": len(incidents),
            "severity_counts": counts,
            "critical_open": sum(1 for x in incidents if x["severity"] == "critical" and x["state"] != "contained"),
            "high_attention": sum(1 for x in incidents if x["severity"] == "high" and x["state"] == "attention"),
            "cross_case_data_included": False,
        }

    def readiness(self, *, case_id: str) -> dict[str, Any]:
        metrics = self.metrics(case_id=case_id)
        incidents = self.incident_console(case_id=case_id)
        audit = self.governance.verify_audit_chain()
        dead = int(metrics["job_counts"].get("dead_letter", 0))
        stale = int(metrics["worker_health"]["expired_worker_leases"])
        critical = int(incidents["severity_counts"].get("critical", 0))
        high = int(incidents["severity_counts"].get("high", 0))
        score = max(0, 100 - min(30, critical * 30) - min(20, dead * 10) - min(20, stale * 10) - min(15, high * 5) - (40 if not audit.get("chain_consistent") else 0))
        blockers = []
        if critical: blockers.append("critical_security_incident")
        if dead: blockers.append("dead_letter_jobs")
        if stale: blockers.append("expired_worker_leases")
        if not audit.get("chain_consistent"): blockers.append("audit_chain_inconsistent")
        return {
            "policy": POLICY,
            "case_id": case_id,
            "local_operational_readiness_score": score,
            "local_operational_ready": not blockers,
            "blockers": blockers,
            "audit_chain_consistent": bool(audit.get("chain_consistent")),
            "production_release_ready": False,
            "external_operations_validation": "not_run",
            "truthful_note": "This is a local operational health score, not production or external deployment validation.",
        }

    def circuit_breaker_required(self, *, case_id: str) -> bool:
        incidents = self.incident_console(case_id=case_id)
        return bool(incidents["critical_open"] or incidents["high_attention"])

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "case_scoped_metrics": True,
            "worker_lease_health": True,
            "queue_health": True,
            "crawler_metrics": True,
            "security_incident_console": True,
            "case_scoped_trace": True,
            "audit_chain_health": True,
            "operational_circuit_breaker": True,
            "new_per_build_telemetry_tables": 0,
            "local_reference_backend": "sqlite_consolidated_ledgers",
            "automatic_external_connections": False,
            "externally_validated": False,
        }


class AutonomousInvestigation365:
    def __init__(self, db: Any, *, base364: Any, operations365: OperationsTelemetry365):
        self.db = db
        self.base364 = base364
        self.operations365 = operations365

    def status(self) -> dict[str, Any]:
        base = dict(self.base364.status())
        base.update({
            "policy_version": AI_POLICY,
            "operations_context_aware": True,
            "incident_aware_research_hold": True,
            "dossier_records_operational_health": True,
            "direct_operations_mutation_authority": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        # Local, read-only operational preflight. It does not grant the AI any
        # additional network/system authority and cannot recover jobs itself.
        if self.operations365.circuit_breaker_required(case_id=case_id):
            readiness = self.operations365.readiness(case_id=case_id)
            return {
                "state": "operations_hold",
                "case_id": case_id,
                "reason": "operational_incident_requires_human_or_opsec_resolution",
                "lead_review_required": True,
                "dossier": {
                    "case_id": case_id,
                    "phase16_operations_context": readiness,
                    "lead_review_required": True,
                    "facts": [],
                    "hypotheses": [],
                    "truthful_note": "No research wave was started because the Build-365 operational circuit breaker was open.",
                },
            }
        out = self.base364.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            dossier["phase16_operations_context"] = {
                **self.operations365.readiness(case_id=case_id),
                "incident_count": self.operations365.incident_console(case_id=case_id)["count"],
                "worker_health": self.operations365.worker_health(case_id=case_id),
                "lead_review_required": True,
            }
            dossier["lead_review_required"] = True
        return out


class DefensiveOpsecSupervisor365:
    def __init__(self, db: Any, audit: Any, *, jobs: Any, base364: Any, operations365: OperationsTelemetry365):
        self.db = db
        self.audit = audit
        self.jobs = jobs
        self.base364 = base364
        self.operations365 = operations365

    def status(self) -> dict[str, Any]:
        base = dict(self.base364.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "queue_failure_monitor": True,
            "stale_worker_monitor": True,
            "incident_console_monitor": True,
            "operational_circuit_breaker": True,
            "case_job_cancel_allowed": True,
            "automatic_job_resume": False,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "credential_mutation": False,
            "acl_mutation": False,
            "system_mutations": False,
        })
        return base

    def protect_remote_session(self, **kwargs: Any) -> dict[str, Any]:
        return self.base364.protect_remote_session(**kwargs)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base364.protect_case(case_id=case_id)
        cancelled: list[str] = []
        if self.operations365.circuit_breaker_required(case_id=case_id):
            rows = self.db.all("SELECT job_id FROM phase15_jobs WHERE case_id=? AND status IN ('queued','running') ORDER BY created_at ASC", (case_id,))
            for row in rows:
                self.jobs.cancel(str(row["job_id"]), actor="opsec365")
                cancelled.append(str(row["job_id"]))
            if cancelled:
                self.audit.log(
                    "OPSEC365_OPERATIONAL_CIRCUIT_BREAKER",
                    "case",
                    case_id,
                    case_id=case_id,
                    details={"cancelled_jobs": cancelled, "policy": OPSEC_POLICY},
                )
        return {
            **base,
            "operations_circuit_breaker_open": self.operations365.circuit_breaker_required(case_id=case_id),
            "cancelled_case_jobs": cancelled,
            "incident_console": self.operations365.incident_console(case_id=case_id),
            "system_mutations": False,
            "policy_version": OPSEC_POLICY,
        }
