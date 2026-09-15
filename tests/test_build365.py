from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext

ADMIN_PW = "Orbit-Pine-Quartz-365!"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test365")


def admin(c):
    user = c.team_identity_359.create_initial_admin(username="admin365", display_name="Admin User", password=ADMIN_PW)
    return {**user, "session_id": "test-admin-365"}


def case(c, a, title="Operations Case"):
    return c.build365.team_create_case(identity=a, title=title, client="QA", purpose="authorized public research", legal_basis="public_data")


def security_event(c, cid, *, severity="critical", disposition="pause", event_type="ops_test"):
    import uuid
    sid = "sec_" + uuid.uuid4().hex[:24]
    c.db.execute(
        "INSERT INTO phase15_security_events(security_event_id,case_id,search_run_id,event_type,disposition,severity,policy_version,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (sid, cid, "", event_type, disposition, severity, "test365", json.dumps({"test": True}), datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    return sid


def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build365.version_status() == {"runtime_build": "365.0", "schema_version": "365.0", "package_version": "365.0.0", "coherent": True}
        m = c.build365.schema_metrics()
        assert m["within_gate"] and (m["table"], m["index"], m["trigger"]) == (141, 128, 8)


def test_operations_uses_consolidated_ledgers(tmp_path):
    with ctx(tmp_path) as c:
        s = c.operations_365.status()
        assert s["new_per_build_telemetry_tables"] == 0
        assert s["local_reference_backend"] == "sqlite_consolidated_ledgers"
        assert not s["automatic_external_connections"]


def test_case_metrics_empty_and_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "A"); cb = case(c, a, "B")
        c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=ca["case_id"])
        c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=cb["case_id"])
        m = c.build365.operations_metrics(case_id=ca["case_id"])
        assert m["job_counts"]["queued"] == 1
        assert m["evidence_objects"] == 0 and m["search_documents"] == 0
        assert m["case_id"] == ca["case_id"]


def test_worker_health_detects_healthy_running_lease(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=cid)
        claimed = c.job_engine_348.claim(worker_id="worker365", lease_seconds=120)
        assert claimed and claimed["case_id"] == cid
        w = c.build365.operations_worker_health(case_id=cid)
        assert w["running_jobs"] == 1 and w["expired_worker_leases"] == 0 and w["healthy"]
        assert w["workers"][0]["worker_id"] == "worker365"


def test_worker_health_detects_expired_lease(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        job = c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=cid)
        expired = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(timespec="seconds")
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='dead-worker',lease_expires_at=? WHERE job_id=?", (expired, job["job_id"]))
        w = c.build365.operations_worker_health(case_id=cid)
        assert w["expired_worker_leases"] == 1 and not w["healthy"] and w["workers"][0]["state"] == "stale"


def test_trace_is_strictly_case_scoped(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "Trace A"); cb = case(c, a, "Trace B")
        ja = c.job_engine_348.enqueue(job_type="a", payload={}, case_id=ca["case_id"])
        jb = c.job_engine_348.enqueue(job_type="b", payload={}, case_id=cb["case_id"])
        c.audit.log("TRACE_A", "case", ca["case_id"], case_id=ca["case_id"])
        c.audit.log("TRACE_B", "case", cb["case_id"], case_id=cb["case_id"])
        t = c.build365.operations_trace(case_id=ca["case_id"], limit=100)
        ids = {x.get("job_id") for x in t["events"] if x["kind"] == "job"}
        actions = {x["event_type"] for x in t["events"] if x["kind"] == "audit"}
        assert ja["job_id"] in ids and jb["job_id"] not in ids
        assert "TRACE_A" in actions and "TRACE_B" not in actions and not t["cross_case_data_included"]


def test_incident_console_collects_security_event(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        sid = security_event(c, cid, severity="critical", disposition="pause")
        incidents = c.build365.operations_incidents(case_id=cid)
        assert incidents["count"] == 1 and incidents["incidents"][0]["source_id"] == sid
        assert incidents["severity_counts"]["critical"] == 1


def test_incident_console_collects_dead_letter(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        job = c.job_engine_348.enqueue(job_type="document_parse", payload={}, case_id=cid, max_attempts=1)
        claimed = c.job_engine_348.claim(worker_id="w365", lease_seconds=60)
        assert claimed and claimed["job_id"] == job["job_id"]
        c.job_engine_348.fail(job["job_id"], "synthetic failure", worker_id="w365")
        incidents = c.build365.operations_incidents(case_id=cid)
        assert any(x["category"] == "job_failure" and x["disposition"] == "dead_letter" for x in incidents["incidents"])


def test_readiness_is_local_not_production(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        r = c.build365.operations_readiness(case_id=cid)
        assert r["local_operational_ready"] and r["local_operational_readiness_score"] == 100
        assert r["production_release_ready"] is False and r["external_operations_validation"] == "not_run"


def test_readiness_degrades_on_critical_incident(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        security_event(c, cid, severity="critical", disposition="observe")
        r = c.build365.operations_readiness(case_id=cid)
        assert not r["local_operational_ready"] and "critical_security_incident" in r["blockers"] and r["local_operational_readiness_score"] < 100


def test_ai_still_requires_explicit_go(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        assert c.build365.run_autonomous_investigation(case_id=cid)["state"] == "go_required"


def test_ai_dossier_contains_operations_context_after_go(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.build365.create_investigation_intake(case_id=cid, objective="Research public facts", key_questions=["What is supported?"])
        c.build365.start_investigation_go(case_id=cid, go="GO")
        out = c.build365.run_autonomous_investigation(case_id=cid, max_ticks=1)
        assert out["dossier"]["lead_review_required"]
        assert "phase16_operations_context" in out["dossier"]
        assert out["dossier"]["phase16_operations_context"]["production_release_ready"] is False


def test_ai_operations_hold_prevents_research_wave(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        security_event(c, cid, severity="critical", disposition="observe")
        c.build365.create_investigation_intake(case_id=cid, objective="Research public facts", key_questions=["What is supported?"])
        c.build365.start_investigation_go(case_id=cid, go="GO")
        out = c.build365.run_autonomous_investigation(case_id=cid, max_ticks=3)
        assert out["state"] == "operations_hold"
        assert "No research wave was started" in out["dossier"]["truthful_note"]


def test_opsec_circuit_breaker_cancels_only_case_jobs(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); ca = case(c, a, "Protected"); cb = case(c, a, "Other")
        ja = c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=ca["case_id"])
        jb = c.job_engine_348.enqueue(job_type="crawler", payload={}, case_id=cb["case_id"])
        security_event(c, ca["case_id"], severity="critical", disposition="observe")
        out = c.build365.autonomous_opsec_protect(case_id=ca["case_id"])
        assert out["operations_circuit_breaker_open"] and ja["job_id"] in out["cancelled_case_jobs"]
        assert c.job_engine_348.get(ja["job_id"])["status"] == "cancelled"
        assert c.job_engine_348.get(jb["job_id"])["status"] == "queued"


def test_opsec_never_mutates_system_controls(tmp_path):
    with ctx(tmp_path) as c:
        s = c.opsec_supervisor_365.status()
        assert s["operational_circuit_breaker"] and s["case_job_cancel_allowed"]
        assert not s["system_mutations"] and not s["firewall_mutation"] and not s["os_mutation"] and not s["tor_configuration_mutation"] and not s["credential_mutation"] and not s["acl_mutation"]


def test_crawler_improvement_is_operational(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build365.crawler_status()
        assert s["crawler_improvement_build"] == 365
        assert s["case_queue_metrics"] and s["worker_lease_health"] and s["incident_console_aware"]
        assert not s["automatic_stale_lease_recovery"] and s["dead_letter_human_review_required"]


def test_phase16_status_is_five_of_twenty(tmp_path):
    with ctx(tmp_path) as c:
        s = c.build365.phase16_status()
        assert s["phase"] == "16" and s["build"] == "365.0" and s["builds_completed"] == 5
        assert s["operations"]["case_scoped_metrics"]


def test_capabilities_do_not_claim_external_operations(tmp_path):
    with ctx(tmp_path) as c:
        caps = {x["key"]: x for x in c.build365.capabilities()}
        assert not caps["operations_console_v365"]["states"]["externally_validated"]
        assert c.build365.qualified_gate()["production_release_ready"] is False


def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build365.active_gate_literal_true_lines() == []


def test_new_modules_have_no_direct_network_or_subprocess_imports():
    names = set()
    for p in [Path("src/eagleeye/phase16/operations365.py"), Path("src/eagleeye/application/build365/service.py"), Path("src/eagleeye/interfaces/web/app365.py")]:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
    assert not names.intersection({"requests", "httpx", "aiohttp", "urllib", "socket", "subprocess"})


def test_local_web_operations_are_authenticated_and_case_scoped(tmp_path, monkeypatch):
    monkeypatch.delenv("EAGLEEYE_REMOTE_TEAM_ENABLED", raising=False)
    from eagleeye.interfaces.web.app365 import create_workspace_app365
    root = tmp_path / "web365"
    app = create_workspace_app365(base_dir=root)
    app.state.context.team_identity_359.create_initial_admin(username="admin365", display_name="Admin User", password=ADMIN_PW)
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200 and h.json()["build"] == "365.0"
        assert client.get("/api/build365/phase16-status").status_code == 401
        token = (root / "data/security_364/local_session_token").read_text().strip()
        start = client.get("/security/start", params={"token": token}, follow_redirects=False)
        assert start.status_code == 303
        login = client.post("/security/login", data={"username": "admin365", "password": ADMIN_PW}, follow_redirects=False)
        assert login.status_code == 303
        c = app.state.context
        ident = c.team_identity_359.public_user("admin365") | {"session_id": "web-test"}
        cid = c.build365.team_create_case(identity=ident, title="Web Ops", client="QA", purpose="authorized public research", legal_basis="public_data")["case_id"]
        assert client.get(f"/api/cases/{cid}/operations/metrics").status_code == 200
        assert client.get(f"/cases/{cid}/operations").status_code == 200


def test_build365_registry_is_lazy_and_resolvable(tmp_path):
    with ctx(tmp_path) as c:
        assert c.service_registry.is_registered("operations_365")
        assert c.service_registry.is_registered("build365")
        assert c.build365.BUILD == "365.0"
