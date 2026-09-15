from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE

PW = "Orbit-Pine-Quartz-385!"


def ctx(tmp_path: Path):
    return AppContext(base_dir=tmp_path, actor="test385")


def admin(c):
    u = c.team_identity_359.create_initial_admin(username="admin385", display_name="Admin 385", password=PW)
    return {**u, "session_id": "admin-session-385"}


def case(c, identity):
    return c.build380.team_create_case(
        identity=identity,
        title="Build 385 acquisition",
        client="QA",
        purpose="authorized public-source acquisition planning",
        legal_basis="public_data",
    )


def confirmed_corporate_packet(c, identity, cid):
    for sid in ("gleif.lei", "sec.edgar"):
        c.build382.set_source_scope(case_id=cid, source_id=sid, state="approved", reviewer="admin385", confirmation="APPROVE SOURCE")
    waves = c.build384.plan_research_waves(
        case_id=cid,
        mission="corporate identifiers and official filings",
        jurisdictions=("global", "us"),
        source_classes=("corporate",),
        wave_confirmation=CONFIRM_WAVES,
    )
    packet = c.build385.compile_acquisition_packet(
        case_id=cid,
        wave_plan_id=waves["wave_plan_id"],
        identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12", "sec.edgar": "320193"},
        actor="admin385",
    )
    return waves, packet


def test_version_schema_and_capabilities(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build385.version_status() == {"runtime_build": "385.0", "schema_version": "385.0", "package_version": "385.0.0", "coherent": True}
        s = c.acquisition_orchestrator_385.status()
        assert s["capabilities"] >= 6
        assert not s["network_execution_added"]
        assert not s["arbitrary_url_execution"]
        assert not s["credential_injection"]
        assert c.build385.schema_metrics()["within_phase17_gate"]


def test_capability_matrix_maps_only_governed_connectors(tmp_path):
    with ctx(tmp_path) as c:
        caps = {x["source_id"]: x for x in c.build385.acquisition_capabilities()}
        assert caps["gleif.lei"]["connector_key"] == "gleif_lei_api_v1"
        assert caps["sec.edgar"]["connector_key"] == "sec_edgar_submissions_v1"
        assert caps["usaspending.awards"]["connector_key"] == "usaspending_award_v1"
        assert caps["eu.ted"]["plan_only"] is True
        assert caps["internet_archive.metadata"]["connector_key"] == "internet_archive_metadata_v1"
        assert all(not x["automatic_execution"] and not x["arbitrary_url_execution"] and not x["credential_injection"] for x in caps.values())


def test_packet_blocks_unapproved_phase17_scope(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        waves = c.build384.plan_research_waves(case_id=cid, mission="corporate official records", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
        packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12"})
        item = next(i for i in packet["items"] if i["source_id"] == "gleif.lei")
        assert item["ready_for_preparation"] is False
        assert "phase17_source_scope_not_approved" in item["blockers"]


def test_packet_requires_identifier(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="admin385", confirmation="APPROVE SOURCE")
        waves = c.build384.plan_research_waves(case_id=cid, mission="corporate official records", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
        packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={})
        item = next(i for i in packet["items"] if i["source_id"] == "gleif.lei")
        assert "identifier_required" in item["blockers"]


def test_invalid_identifier_is_blocked_before_preparation(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="admin385", confirmation="APPROVE SOURCE")
        waves = c.build384.plan_research_waves(case_id=cid, mission="corporate official records", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
        packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"gleif.lei": "not-a-lei"})
        item = next(i for i in packet["items"] if i["source_id"] == "gleif.lei")
        assert item["ready_for_preparation"] is False
        assert "identifier_invalid" in item["blockers"]


def test_unconfirmed_wave_plan_cannot_prepare(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="admin385", confirmation="APPROVE SOURCE")
        waves = c.build384.plan_research_waves(case_id=cid, mission="corporate official records", jurisdictions=("global",), source_classes=("corporate",))
        packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12"})
        item = next(i for i in packet["items"] if i["source_id"] == "gleif.lei")
        assert "wave_plan_not_confirmed" in item["blockers"]


def test_prepare_requires_exact_confirmation(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _, packet = confirmed_corporate_packet(c, a, cid)
        with pytest.raises(PermissionError):
            c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation="GO")


def test_prepare_creates_pending_sources_but_no_jobs_or_network(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _, packet = confirmed_corporate_packet(c, a, cid)
        before_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        out = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_PREPARE)
        after_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"])
        assert out["network_requests_created"] == 0 and out["jobs_created"] == 0
        assert before_jobs == after_jobs
        prepared = [x for x in out["outcomes"] if x.get("canonical_source_id")]
        assert len(prepared) >= 2
        for result in prepared:
            src = c.db.one("SELECT review_status FROM phase15_sources WHERE source_id=?", (result["canonical_source_id"],))
            assert src["review_status"] == "pending_review"
        assert not out["automatic_source_approval"] and not out["automatic_crawl_enqueue"] and not out["execution_authority"]


def test_prepare_is_idempotent_per_packet_source(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _, packet = confirmed_corporate_packet(c, a, cid)
        c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_PREPARE)
        again = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_PREPARE)
        assert any(x["state"] == "already_prepared" for x in again["outcomes"])
        count = int((c.db.one("SELECT COUNT(*) n FROM acquisition_preparation_385 WHERE packet_id=?", (packet["packet_id"],)) or {})["n"])
        assert count >= 2


def test_ted_search_stays_plan_only(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        c.build382.set_source_scope(case_id=cid, source_id="eu.ted", state="approved", reviewer="admin385", confirmation="APPROVE SOURCE")
        waves = c.build384.plan_research_waves(case_id=cid, mission="European procurement notices", jurisdictions=("eu",), source_classes=("procurement",), wave_confirmation=CONFIRM_WAVES)
        packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=waves["wave_plan_id"], identifiers={"eu.ted": "buyer-name = example"})
        out = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_PREPARE)
        ted = next(x for x in out["outcomes"] if x["source_id"] == "eu.ted")
        assert ted["state"] == "plan_only_method_not_qualified"
        assert ted["canonical_source_id"] is None
        assert int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {})["n"]) == 0


def test_execution_readiness_preserves_phase15_review_gate(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _, packet = confirmed_corporate_packet(c, a, cid)
        c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=a, confirmation=CONFIRM_PREPARE)
        ready = c.build385.acquisition_execution_readiness(case_id=cid, packet_id=packet["packet_id"], identity=a)
        assert ready["execution_authority"] is False and ready["automatic_enqueue"] is False
        assert ready["ready_sources"] == 0
        assert all("phase15_source_review_required" in row["blockers"] for row in ready["prepared_sources"] if row["canonical_source_id"])


def test_packet_audit_and_no_plain_identifier_in_audit(tmp_path):
    with ctx(tmp_path) as c:
        a = admin(c); cid = case(c, a)["case_id"]
        _, packet = confirmed_corporate_packet(c, a, cid)
        events = c.audit.list_for_case(cid)
        event = next(x for x in events if x["action"] == "PHASE17_385_ACQUISITION_PACKET")
        text = json.dumps(event, sort_keys=True)
        assert "5493001KJTIIGC8Y1R12" not in text and "320193" not in text
        assert packet["execution_authority"] is False


def test_build385_health_and_auth_boundary(tmp_path):
    from eagleeye.interfaces.web.app385 import create_workspace_app385
    app = create_workspace_app385(base_dir=tmp_path)
    try:
        client = TestClient(app)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["build"] == "385.0"
        assert health.json()["acquisition_orchestration"] is True
        assert client.get("/api/build385/acquisition-capabilities").status_code == 401
    finally:
        app.state.context.close()


def test_current_launchers_and_server_point_to_385():
    root = Path(__file__).resolve().parents[1]
    server = (root / "src/eagleeye/interfaces/web/server.py").read_text(encoding="utf-8")
    assert "app385 import create_workspace_app385" in server
    assert "EAGLEEYE_PRO_385_0.py" in (root / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8")
    assert "EAGLEEYE_PRO_385_0.py" in (root / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8")
