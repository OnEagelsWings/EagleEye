from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO, CONFIRM_REVOKE

PW = "Orbit-Pine-Quartz-386!"


def ctx(tmp_path: Path):
    return AppContext(base_dir=tmp_path, actor="test386")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin386", display_name="Admin 386", password=PW)
    return {**u, "session_id": "admin-session-386"}


def case(c, identity):
    return c.build380.team_create_case(identity=identity, title="Build 386 GO", client="QA", purpose="authorized public-source execution authorization", legal_basis="public_data")


def prepared_source(c, identity, cid):
    c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="admin386", confirmation="APPROVE SOURCE")
    waves = c.build384.plan_research_waves(case_id=cid, mission="official corporate identifier verification", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
    packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12"}, actor="admin386")
    out = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=identity, confirmation=CONFIRM_PREPARE)
    source_id = next(x["canonical_source_id"] for x in out["outcomes"] if x.get("canonical_source_id"))
    return packet, source_id


def approve_and_workflow(c, identity, cid, source_id, *, budget=20):
    c.crawler_engine_349.review_source(source_id, decision="approve_read_only", rationale="Build 386 controlled public-source qualification", reviewer="admin386")
    c.case_workflow_374.configure(case_id=cid, identity=identity, source_budgets={source_id: budget}, case_request_budget=budget, max_active_crawls=2, confirmation="WORKFLOW")


def grant_ready(c, identity, cid):
    packet, source_id = prepared_source(c, identity, cid)
    approve_and_workflow(c, identity, cid, source_id)
    return packet, source_id


def test_version_schema_and_status(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build386.version_status() == {"runtime_build": "386.0", "schema_version": "386.0", "package_version": "386.0.0", "coherent": True}
        s = c.execution_authority_386.status()
        assert s["capability_scoped_go"] and s["token_hash_only_persistence"]
        assert not s["direct_network_authority"] and not s["automatic_execution"]
        assert c.build386.schema_metrics()["within_phase17_gate"]


def test_preflight_blocks_unreviewed_source(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, source_id = prepared_source(c, a, cid)
        c.case_workflow_374.configure(case_id=cid, identity=a, source_budgets={source_id: 20}, case_request_budget=20, max_active_crawls=2, confirmation="WORKFLOW")
        p = c.build386.execution_preflight(case_id=cid, packet_id=packet["packet_id"], identity=a)
        assert not p["allowed"]
        assert "one_or_more_sources_not_execution_ready" in p["blockers"]
        assert "phase15_source_review_required" in p["selected_sources"][0]["blockers"]


def test_preflight_requires_workflow_budget(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, source_id = prepared_source(c, a, cid)
        c.crawler_engine_349.review_source(source_id, decision="approve_read_only", rationale="review", reviewer="admin386")
        with pytest.raises(KeyError):
            c.build386.execution_preflight(case_id=cid, packet_id=packet["packet_id"], identity=a)


def test_preflight_allows_reviewed_budgeted_source(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, source_id = grant_ready(c, a, cid)
        p = c.build386.execution_preflight(case_id=cid, packet_id=packet["packet_id"], identity=a)
        assert p["allowed"] and not p["blockers"]
        assert p["selected_sources"][0]["canonical_source_id"] == source_id
        assert p["selected_sources"][0]["request_budget"] == 4
        assert p["network_requests_created"] == 0 and p["jobs_created"] == 0


def test_go_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        with pytest.raises(PermissionError):
            c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation="YES")


def test_go_issues_short_lived_hash_bound_token_without_job(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        before = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        grant = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO, ttl_minutes=7)
        after = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        assert before == after
        assert grant["grant_token"].startswith("go386_")
        assert grant["direct_network_authority"] is False and grant["automatic_execution"] is False
        assert grant["execution_authority_scope"] == "enqueue_only"
        assert grant["network_requests_created"] == 0 and grant["jobs_created"] == 0
        row = c.db.one("SELECT token_hash,scope_json FROM execution_grant_386 WHERE grant_id=?", (grant["grant_id"],))
        assert grant["grant_token"] not in row["scope_json"]
        assert row["token_hash"] != grant["grant_token"]


def test_grant_verifies_with_correct_token(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a)
        assert v["valid"] and not v["blockers"]
        assert v["required_execution_confirmation"] == "LIVE"


def test_wrong_token_is_rejected(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token="go386_wrong", identity=a)
        assert not v["valid"] and "invalid_grant_token" in v["blockers"]


def test_source_state_change_invalidates_grant(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, source_id = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        c.db.execute("UPDATE phase15_crawler_policies SET enabled=0 WHERE source_id=?", (source_id,))
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a)
        assert not v["valid"]
        assert "current_preflight_failed" in v["blockers"]


def test_workflow_generation_change_invalidates_grant(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, source_id = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        c.case_workflow_374.configure(case_id=cid, identity=a, source_budgets={source_id: 20}, case_request_budget=20, max_active_crawls=2, confirmation="WORKFLOW")
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a)
        assert not v["valid"] and "workflow_generation_changed" in v["blockers"]


def test_expired_grant_invalid(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        c.db.execute("UPDATE execution_grant_386 SET expires_at='2000-01-01T00:00:00+00:00' WHERE grant_id=?", (g["grant_id"],))
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a)
        assert not v["valid"] and "grant_expired" in v["blockers"]


def test_revoke_requires_confirmation_and_invalidates(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        with pytest.raises(PermissionError):
            c.build386.revoke_execution_grant(case_id=cid, grant_id=g["grant_id"], identity=a, confirmation="STOP")
        r = c.build386.revoke_execution_grant(case_id=cid, grant_id=g["grant_id"], identity=a, confirmation=CONFIRM_REVOKE)
        assert r["state"] == "revoked"
        v = c.build386.verify_execution_grant(case_id=cid, grant_id=g["grant_id"], grant_token=g["grant_token"], identity=a)
        assert not v["valid"] and "grant_not_active" in v["blockers"]


def test_operations_hold_blocks_go(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        c.execution_authority_386.operations365.circuit_breaker_required = lambda *, case_id: True
        p = c.build386.execution_preflight(case_id=cid, packet_id=packet["packet_id"], identity=a)
        assert not p["allowed"] and "operations_preflight_hold" in p["blockers"]


def test_go_audit_contains_no_token(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        packet, _ = grant_ready(c, a, cid)
        g = c.build386.issue_execution_grant(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_GO)
        events = [e for e in c.audit.list_for_case(cid) if e.get("object_type") == "execution_grant" and e.get("object_id") == g["grant_id"]]
        text = str(events)
        assert g["grant_token"] not in text
        assert "capability_scope_hash" in text


def test_web_health_and_auth(tmp_path):
    from eagleeye.interfaces.web.app386 import create_workspace_app386
    app = create_workspace_app386(base_dir=tmp_path)
    try:
        client = TestClient(app)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["build"] == "386.0"
        assert health.json()["capability_scoped_go"] is True
        assert client.get("/api/build386/phase17-status").status_code == 401
    finally:
        app.state.context.close()


def test_current_launchers_and_server_point_to_386():
    root = Path(__file__).resolve().parents[1]
    server = (root / "src/eagleeye/interfaces/web/server.py").read_text(encoding="utf-8")
    assert "app386 import create_workspace_app386" in server
    assert "EAGLEEYE_PRO_386_0.py" in (root / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8")
    assert "EAGLEEYE_PRO_386_0.py" in (root / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8")
