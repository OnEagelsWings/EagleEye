from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext

ADMIN_PW = "Orbit-Pine-Quartz-Live-365!"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_security_event(c, case_id: str) -> str:
    sid = "sec_" + uuid.uuid4().hex[:24]
    c.db.execute(
        "INSERT INTO phase15_security_events(security_event_id,case_id,search_run_id,event_type,disposition,severity,policy_version,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (sid, case_id, "", "local_operations_validation", "observe", "critical", "build365-live-validation", json.dumps({"synthetic": True}), now()),
    )
    return sid


def main() -> dict:
    root = Path(__file__).resolve().parents[1]
    receipt_path = root / "LIVE_VALIDATION_BUILD_365_OPERATIONS.json"
    with tempfile.TemporaryDirectory(prefix="ee365-ops-live-") as td:
        with AppContext(base_dir=Path(td), actor="live-validation-365") as c:
            a = c.team_identity_359.create_initial_admin(username="admin365live", display_name="Live Admin", password=ADMIN_PW)
            ident = {**a, "session_id": "live365"}
            ca = c.build365.team_create_case(identity=ident, title="Operations Live A", client="QA", purpose="authorized public research", legal_basis="public_data")
            cb = c.build365.team_create_case(identity=ident, title="Operations Live B", client="QA", purpose="authorized public research", legal_basis="public_data")
            ja = c.job_engine_348.enqueue(job_type="crawler", payload={"url": "https://example.invalid/a"}, case_id=ca["case_id"], idempotency_key="live365-a")
            jb = c.job_engine_348.enqueue(job_type="crawler", payload={"url": "https://example.invalid/b"}, case_id=cb["case_id"], idempotency_key="live365-b")
            claimed = c.job_engine_348.claim(worker_id="live-worker-365", lease_seconds=120)
            metrics_before = c.build365.operations_metrics(case_id=ca["case_id"])
            workers_before = c.build365.operations_worker_health(case_id=ca["case_id"])
            sec_id = add_security_event(c, ca["case_id"])
            c.build365.create_investigation_intake(case_id=ca["case_id"], objective="Validate operational hold", key_questions=["Does the circuit breaker stop research?"])
            c.build365.start_investigation_go(case_id=ca["case_id"], go="GO")
            ai = c.build365.run_autonomous_investigation(case_id=ca["case_id"], max_ticks=2)
            opsec = c.build365.autonomous_opsec_protect(case_id=ca["case_id"])
            trace = c.build365.operations_trace(case_id=ca["case_id"], limit=200)
            incidents = c.build365.operations_incidents(case_id=ca["case_id"])
            readiness = c.build365.operations_readiness(case_id=ca["case_id"])
            audit = c.team_governance_359.verify_audit_chain()
            ja_after = c.job_engine_348.get(ja["job_id"])
            jb_after = c.job_engine_348.get(jb["job_id"])
            trace_ids = {x.get("job_id") for x in trace["events"] if x["kind"] == "job"}
            checks = {
                "claimed_expected_case_job": bool(claimed and claimed["job_id"] == ja["job_id"]),
                "case_metrics_live": metrics_before["job_counts"].get("running") == 1,
                "worker_lease_live": workers_before["running_jobs"] == 1 and workers_before["expired_worker_leases"] == 0,
                "critical_incident_live": any(x["source_id"] == sec_id for x in incidents["incidents"]),
                "ai_incident_hold_live": ai.get("state") == "operations_hold",
                "opsec_case_containment_live": ja_after["status"] == "cancelled" and ja["job_id"] in opsec.get("cancelled_case_jobs", []),
                "other_case_unchanged": jb_after["status"] == "queued",
                "trace_case_isolation_live": ja["job_id"] in trace_ids and jb["job_id"] not in trace_ids and not trace["cross_case_data_included"],
                "audit_chain_live": bool(audit.get("chain_consistent")),
                "readiness_truthful": readiness["production_release_ready"] is False and readiness["external_operations_validation"] == "not_run",
            }
            passed = all(checks.values())
            out = {
                "build": "365.0",
                "status": "pass" if passed else "fail",
                "code_fingerprint": c.build365.code_fingerprint(),
                "checks": checks,
                "local_sqlite_operations_live_validated": passed,
                "queue_trace_incident_flow_live_validated": passed,
                "external_multi_user_operations_validated": False,
                "externally_validated": False,
                "external_network_used": False,
                "network_requests_executed": 0,
                "truthful_note": "Real local SQLite/job/audit runtime paths were exercised. No external network, remote client, load test or production environment was used.",
            }
            receipt_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
            if not passed:
                raise SystemExit(1)
            return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
