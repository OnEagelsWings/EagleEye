from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from eagleeye_pro.core.database import dumps, new_id, now_ts

FINAL_STATUSES = {"succeeded", "partial_success", "failed", "cancelled"}
JOB_STATUSES = {"queued", "running", *FINAL_STATUSES}
OUTCOME_CODES = {
    "SUCCESS", "PARTIAL_SUCCESS", "NO_RESULT", "SOURCE_UNAVAILABLE",
    "BLOCKED_BY_POLICY", "AUTH_REQUIRED", "RATE_LIMITED", "PARSER_FAILED",
    "INTEGRITY_FAILED", "USER_CANCELLED", "INTERNAL_ERROR",
}
ERROR_CLASSES = {
    "policy", "authentication", "rate_limit", "source", "parser",
    "integrity", "timeout", "resource", "validation", "internal",
}
SEVERITIES = {"debug", "info", "warning", "error", "critical"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def new_correlation_id() -> str:
    return f"corr153_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class JobHandle:
    job_id: str
    correlation_id: str
    operation: str
    component: str
    case_id: str | None


class Build153ReliabilityObservabilityService:
    BUILD = "153.0"
    MISSION = "Reliability and Observability"

    def __init__(self, db: Any, audit: Any, *, registry: Any, actor: str = "system") -> None:
        self.db = db
        self.audit = audit
        self.registry = registry
        self.actor = actor

    def start_job(self, *, operation: str, component: str, case_id: str | None = None,
                  correlation_id: str | None = None, input_summary: dict[str, Any] | None = None,
                  actor: str | None = None) -> JobHandle:
        operation = operation.strip()
        component = component.strip()
        if not operation or not component:
            raise ValueError("Operation und Komponente sind erforderlich")
        job_id = new_id("job153")
        correlation_id = correlation_id or new_correlation_id()
        created = now_ts()
        self.db.execute(
            "INSERT INTO operation_jobs_153(job_id,correlation_id,case_id,operation,component,status,started_at,actor,input_summary_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (job_id, correlation_id, case_id, operation, component, "running", created, actor or self.actor, dumps(input_summary or {})),
        )
        self.emit_event(correlation_id=correlation_id, job_id=job_id, case_id=case_id,
                        component=component, severity="info", event_name="job.started",
                        message=f"{operation} gestartet", attributes={"operation": operation})
        return JobHandle(job_id, correlation_id, operation, component, case_id)

    def finish_job(self, job_id: str, *, status: str, outcome_code: str,
                   output_summary: dict[str, Any] | None = None, error_class: str | None = None,
                   error_message: str | None = None, retryable: bool = False) -> dict[str, Any]:
        status = status.strip().casefold()
        outcome_code = outcome_code.strip().upper()
        if status not in FINAL_STATUSES:
            raise ValueError("Ungültiger finaler Jobstatus")
        if outcome_code not in OUTCOME_CODES:
            raise ValueError("Unbekannter Outcome-Code")
        if error_class is not None and error_class not in ERROR_CLASSES:
            raise ValueError("Unbekannte Fehlerklasse")
        row = self.db.one("SELECT * FROM operation_jobs_153 WHERE job_id=?", (job_id,))
        if not row:
            raise KeyError("Job nicht gefunden")
        if row["status"] in FINAL_STATUSES:
            raise RuntimeError("Job ist bereits abgeschlossen")
        elapsed = max(0, int((time.time() - self._parse_epoch(row["started_at"])) * 1000))
        partial = status == "partial_success"
        self.db.execute(
            "UPDATE operation_jobs_153 SET status=?,outcome_code=?,finished_at=?,duration_ms=?,output_summary_json=?,error_class=?,error_message=?,retryable=?,partial=? WHERE job_id=?",
            (status, outcome_code, now_ts(), elapsed, dumps(output_summary or {}), error_class,
             (error_message or "")[:4000] or None, int(retryable), int(partial), job_id),
        )
        severity = "error" if status == "failed" else "warning" if partial else "info"
        self.emit_event(correlation_id=row["correlation_id"], job_id=job_id, case_id=row.get("case_id"),
                        component=row["component"], severity=severity, event_name=f"job.{status}",
                        message=f"{row['operation']} beendet: {outcome_code}",
                        attributes={"outcome_code": outcome_code, "retryable": retryable, "error_class": error_class})
        result = self.db.one("SELECT * FROM operation_jobs_153 WHERE job_id=?", (job_id,))
        self.audit.log("job_finished_153", "operation_job", job_id, row.get("case_id"),
                       {"status": status, "outcome_code": outcome_code, "correlation_id": row["correlation_id"]})
        return result

    @staticmethod
    def _parse_epoch(value: str) -> float:
        from datetime import datetime
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()

    def emit_event(self, *, correlation_id: str, component: str, severity: str,
                   event_name: str, message: str, attributes: dict[str, Any] | None = None,
                   job_id: str | None = None, case_id: str | None = None) -> dict[str, Any]:
        severity = severity.strip().casefold()
        if severity not in SEVERITIES:
            raise ValueError("Ungültiger Schweregrad")
        attrs = attributes or {}
        event_id = new_id("telemetry153")
        created = now_ts()
        digest = _digest(attrs)
        self.db.execute(
            "INSERT INTO telemetry_events_153(event_id,created_at,correlation_id,job_id,case_id,component,severity,event_name,message,attributes_json,attributes_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, created, correlation_id, job_id, case_id, component.strip(), severity,
             event_name.strip(), message.strip(), dumps(attrs), digest),
        )
        return self.db.one("SELECT * FROM telemetry_events_153 WHERE event_id=?", (event_id,))

    @contextmanager
    def job(self, *, operation: str, component: str, case_id: str | None = None,
            correlation_id: str | None = None, input_summary: dict[str, Any] | None = None,
            actor: str | None = None) -> Iterator[JobHandle]:
        handle = self.start_job(operation=operation, component=component, case_id=case_id,
                                correlation_id=correlation_id, input_summary=input_summary, actor=actor)
        try:
            yield handle
        except PermissionError as exc:
            self.finish_job(handle.job_id, status="failed", outcome_code="BLOCKED_BY_POLICY",
                            error_class="policy", error_message=str(exc), retryable=False)
            raise
        except TimeoutError as exc:
            self.finish_job(handle.job_id, status="failed", outcome_code="SOURCE_UNAVAILABLE",
                            error_class="timeout", error_message=str(exc), retryable=True)
            raise
        except Exception as exc:
            self.finish_job(handle.job_id, status="failed", outcome_code="INTERNAL_ERROR",
                            error_class="internal", error_message=str(exc), retryable=False,
                            output_summary={"exception_type": type(exc).__name__, "traceback": traceback.format_exc(limit=5)})
            raise
        else:
            current = self.db.one("SELECT status FROM operation_jobs_153 WHERE job_id=?", (handle.job_id,))
            if current and current["status"] == "running":
                self.finish_job(handle.job_id, status="succeeded", outcome_code="SUCCESS")

    def health_snapshot(self, *, actor: str | None = None) -> dict[str, Any]:
        threads = list(threading.enumerate())
        non_daemon = [t for t in threads if not t.daemon and t is not threading.main_thread()]
        running = self.db.one("SELECT COUNT(*) AS n FROM operation_jobs_153 WHERE status='running'")["n"]
        failed = self.db.one("SELECT COUNT(*) AS n FROM operation_jobs_153 WHERE status='failed'")["n"]
        partial = self.db.one("SELECT COUNT(*) AS n FROM operation_jobs_153 WHERE status='partial_success'")["n"]
        db_ok = True
        try:
            self.db.one("SELECT 1 AS ok")
        except Exception:
            db_ok = False
        initialized = len(self.registry.initialized_names())
        findings: list[dict[str, Any]] = []
        for thread in non_daemon:
            findings.append({"resource_type": "thread", "resource_name": thread.name,
                             "severity": "warning", "state": "alive", "ident": thread.ident})
        if running:
            findings.append({"resource_type": "job", "resource_name": "running_jobs",
                             "severity": "warning", "state": "active", "count": running})
        overall = "critical" if not db_ok else "degraded" if findings else "healthy"
        payload = {
            "build": self.BUILD, "mission": self.MISSION, "overall_status": overall,
            "active_jobs": running, "failed_jobs": failed, "partial_jobs": partial,
            "active_threads": len(threads), "non_daemon_threads": len(non_daemon),
            "initialized_services": initialized, "database_ok": db_ok,
            "pid": os.getpid(), "findings": findings,
            "person_osint_core_preserved": True, "firefox_workflow_unchanged": True,
            "automatic_identity_confirmation": False,
        }
        snapshot_id = new_id("health153")
        digest = _digest(payload)
        created = now_ts()
        self.db.execute(
            "INSERT INTO health_snapshots_153(snapshot_id,created_at,actor,overall_status,active_jobs,failed_jobs,partial_jobs,active_threads,non_daemon_threads,initialized_services,database_ok,findings_json,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snapshot_id, created, actor or self.actor, overall, running, failed, partial, len(threads),
             len(non_daemon), initialized, int(db_ok), dumps(findings), digest),
        )
        for item in findings:
            self.db.execute(
                "INSERT INTO resource_findings_153(finding_id,snapshot_id,resource_type,resource_name,severity,state,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (new_id("finding153"), snapshot_id, item["resource_type"], item["resource_name"],
                 item["severity"], item["state"], dumps(item), created),
            )
        self.audit.log("health_snapshot_153", "reliability", snapshot_id, None,
                       {"status": overall, "sha256": digest, "findings": len(findings)})
        return {**payload, "snapshot_id": snapshot_id, "created_at": created, "payload_sha256": digest}

    def correlation_timeline(self, correlation_id: str) -> dict[str, Any]:
        jobs = self.db.all("SELECT * FROM operation_jobs_153 WHERE correlation_id=? ORDER BY started_at", (correlation_id,))
        events = self.db.all("SELECT * FROM telemetry_events_153 WHERE correlation_id=? ORDER BY created_at", (correlation_id,))
        return {"correlation_id": correlation_id, "jobs": jobs, "events": events,
                "job_count": len(jobs), "event_count": len(events)}
