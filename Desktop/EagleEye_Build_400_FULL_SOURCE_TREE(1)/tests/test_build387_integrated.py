from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE

PW = "Build387-Test-Orbit!"


def ctx(tmp_path):
    return AppContext(base_dir=tmp_path, actor="test387")


def admin(c):
    a = c.team_identity_359.create_initial_admin(username="admin387", display_name="Admin 387", password=PW)
    return {**a, "session_id": "test-session-387"}


def case(c, identity):
    return c.build380.team_create_case(identity=identity, title="Build387 test", client="internal", purpose="authorized public-source controlled executor test", legal_basis="public_data")


def grant_ready(c, identity, cid):
    c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="admin387", confirmation="APPROVE SOURCE")
    waves = c.build384.plan_research_waves(case_id=cid, mission="official corporate identifier verification", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
    packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12"}, actor="admin387")
    prepared = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=identity, confirmation=CONFIRM_PREPARE)
    sid = next(x["canonical_source_id"] for x in prepared["outcomes"] if x.get("canonical_source_id"))
    c.crawler_engine_349.review_source(sid, decision="approve_read_only", rationale="Build 387 controlled read-only source", reviewer="admin387")
    c.case_workflow_374.configure(case_id=cid, identity=identity, source_budgets={sid: 20}, case_request_budget=20, max_active_crawls=2, confirmation="WORKFLOW")
    grant = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=identity, confirmation=CONFIRM_GO, ttl_minutes=5)
    return packet, sid, grant


def test_version_schema_and_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build387.version_status() == {"runtime_build": "387.0", "schema_version": "387.0", "package_version": "387.0.0", "coherent": True}
        s = c.controlled_executor_387.status()
        assert s["one_time_grant_consumption"] and s["post_reservation_revalidation"]
        assert not s["direct_network_fetch_by_executor"] and not s["worker_claim_by_executor"]
        assert c.build387.schema_metrics()["within_phase17_gate"]


def test_exact_live_confirmation_required(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        with pytest.raises(PermissionError):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation="EXECUTE")
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_valid_grant_enqueues_exactly_one_unclaimed_job(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, sid, g = grant_ready(c, a, cid)
        before = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        out = c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        after = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        assert after == before + 1
        assert out["jobs_enqueued"] == 1 and out["network_fetches_executed"] == 0
        assert out["grant_consumed"] is True and out["direct_network_fetch_by_executor"] is False
        job = c.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (out["job_ids"][0],))
        payload = json.loads(job["payload_json"])
        assert job["status"] == "queued" and int(job["attempts"]) == 0
        assert not job["lease_owner"] and not job["lease_expires_at"]
        assert payload["phase17_executor_v387"] is True
        assert payload["phase17_grant_id"] == g["grant_id"]
        assert payload["phase17_acquisition_packet_id"] == packet["packet_id"]
        assert payload["phase16_case_workflow_v374"] is True
        assert payload["source_id"] == sid
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "consumed_387"


def test_replay_does_not_create_second_job(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        out = c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        count1 = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        with pytest.raises(PermissionError):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        count2 = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        assert count1 == count2
        assert int((c.db.one("SELECT COUNT(*) n FROM execution_dispatch_387 WHERE grant_id=?", (g["grant_id"],)) or {})["n"]) == 1
        assert out["job_ids"]


def test_wrong_token_creates_no_job_and_grant_remains_active(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        before = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        with pytest.raises(PermissionError):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token="go386_wrong", identity=a, confirmation=CONFIRM_EXECUTE)
        after = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"])
        assert before == after
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_source_state_change_blocks_dispatch(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, sid, g = grant_ready(c, a, cid)
        c.db.execute("UPDATE phase15_crawler_policies SET enabled=0 WHERE source_id=?", (sid,))
        with pytest.raises(PermissionError):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        assert int((c.db.one("SELECT COUNT(*) n FROM execution_dispatch_387") or {})["n"]) == 0
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_workflow_generation_change_blocks_dispatch(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, sid, g = grant_ready(c, a, cid)
        c.case_workflow_374.configure(case_id=cid, identity=a, source_budgets={sid: 20}, case_request_budget=20, max_active_crawls=2, confirmation="WORKFLOW")
        with pytest.raises(PermissionError):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_workflow_active_crawl_limit_is_enforced(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, sid, g = grant_ready(c, a, cid)
        # Occupy both workflow slots with properly tagged canonical jobs.
        for _ in range(2):
            c.case_workflow_374.enqueue_source(case_id=cid, source_id=sid, identity=a, confirmation="CRAWL")
        with pytest.raises(PermissionError, match="workflow_active_crawl_limit"):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_enqueue_failure_rolls_back_jobs_dispatch_and_reservation(tmp_path, monkeypatch):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        before_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        original = c.controlled_executor_387._enqueue_live
        def broken(**kwargs):
            out = original(**kwargs)
            raise RuntimeError("simulated post-enqueue failure")
        monkeypatch.setattr(c.controlled_executor_387, "_enqueue_live", broken)
        with pytest.raises(RuntimeError, match="simulated post-enqueue failure"):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        after_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        assert before_jobs == after_jobs
        assert int((c.db.one("SELECT COUNT(*) n FROM execution_dispatch_387") or {})["n"]) == 0
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"


def test_dispatch_record_hash_and_job_provenance_verify(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        out = c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        v = c.build387.verify_execution_dispatch(case_id=cid, dispatch_id=out["dispatch_id"])
        assert v == {"dispatch_id": out["dispatch_id"], "record_hash_valid": True, "jobs_present": True, "all_jobs_workflow_tagged": True, "all_jobs_unclaimed": True, "job_count": 1}


def test_dispatch_audit_contains_no_grant_token(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        out = c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        events = [e for e in c.audit.list_for_case(cid) if e.get("object_type") == "execution_dispatch" and e.get("object_id") == out["dispatch_id"]]
        assert events
        assert g["grant_token"] not in str(events)



def test_post_reservation_preflight_failure_rolls_back_reservation(tmp_path, monkeypatch):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _p, _sid, g = grant_ready(c, a, cid)
        original = c.execution_authority_386.preflight
        calls = {"n": 0}
        def changing_preflight(**kwargs):
            calls["n"] += 1
            out = original(**kwargs)
            if calls["n"] >= 2:
                out = dict(out); out["allowed"] = False; out["blockers"] = ["simulated_post_reservation_state_change"]
            return out
        monkeypatch.setattr(c.execution_authority_386, "preflight", changing_preflight)
        with pytest.raises(PermissionError, match="post-reservation preflight failed"):
            c.build387.execute_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a, confirmation=CONFIRM_EXECUTE)
        assert c.execution_authority_386.grant(case_id=cid, grant_id=g["grant_id"])["state"] == "active"
        assert int((c.db.one("SELECT COUNT(*) n FROM execution_dispatch_387") or {})["n"]) == 0
        assert int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {})["n"]) == 0

def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app387 import create_workspace_app387
    app = create_workspace_app387(base_dir=tmp_path)
    try:
        client = TestClient(app)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["build"] == "387.0"
        assert health.json()["controlled_executor"] is True
        assert client.get("/api/build387/phase17-status").status_code == 401
    finally:
        app.state.context.close()


def test_current_launchers_and_server_point_to_387():
    root = Path(__file__).resolve().parents[1]
    server = (root / "src/eagleeye/interfaces/web/server.py").read_text(encoding="utf-8")
    assert "app387 import create_workspace_app387" in server
    assert "EAGLEEYE_PRO_387_0.py" in (root / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8")
    assert "EAGLEEYE_PRO_387_0.py" in (root / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8")
