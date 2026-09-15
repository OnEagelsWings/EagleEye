from __future__ import annotations
from pathlib import Path
from dataclasses import asdict
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.source_planner383 import CONFIRM_INFERRED_SELECTORS
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES

def _ctx(tmp_path:Path): return AppContext(base_dir=tmp_path)
def _case(c): return c.cases.create_case(title="Phase17 integration",client="internal",purpose="OSINT research",legal_basis="legitimate_interest",jurisdiction="DE/EU")

def test_integrated_version_and_registry(tmp_path):
    with _ctx(tmp_path) as c:
        assert c.build384.version_status()=={"runtime_build":"384.0","schema_version":"384.0","package_version":"384.0.0","coherent":True}
        s=c.phase17_runtime_384.status(); assert s["integrated_with_build380"] and s["canonical_database"]
        assert s["registry"]["source_count"] >= 6

def test_control_plane_uses_real_case_and_phase16_health(tmp_path):
    with _ctx(tmp_path) as c:
        case=_case(c); snap=c.build381.snapshot(case["case_id"])
        assert snap["case_id"]==case["case_id"]; assert snap["research_ready"] is True; assert snap["network_requests_created"]==0

def test_missing_case_holds_control_plane(tmp_path):
    with _ctx(tmp_path) as c:
        snap=c.build381.snapshot("missing-case"); assert snap["research_ready"] is False

def test_persistence_is_in_canonical_database(tmp_path):
    with _ctx(tmp_path) as c:
        _=c.phase17_runtime_384
        tables={r["name"] for r in c.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"source_registry_sources","research_plan_ledger","source_coverage_ledger","jurisdiction_profile_384","research_wave_plan_384"}.issubset(tables)

def test_build383_plan_is_review_first_and_audited(tmp_path):
    with _ctx(tmp_path) as c:
        case=_case(c); cid=case["case_id"]
        p=c.build383.plan_acquisition(case_id=cid,mission="company procurement records",jurisdictions=("us",),entity_types=("organization",),confirmation=CONFIRM_INFERRED_SELECTORS)
        assert p["execution_authority"] is False and p["scope_expansion_authority"] is False and p["network_requests_created"]==0
        assert any(e["action"]=="PHASE17_383_ACQUISITION_PLAN" for e in c.audit.list_for_case(cid))

def test_build384_waves_integrated_and_nonexecuting(tmp_path):
    with _ctx(tmp_path) as c:
        case=_case(c); cid=case["case_id"]
        p=c.build384.plan_research_waves(case_id=cid,mission="company procurement regulatory archive",source_classes=("corporate","procurement","regulatory","archive"),jurisdictions=("us",),wave_confirmation=CONFIRM_WAVES)
        assert p["confirmation_state"]=="confirmed"; assert p["execution_authority"] is False; assert p["scope_expansion_authority"] is False; assert p["network_requests_created"]==0
        assert all(w["requires_go"] and not w["execution_authority"] for w in p["waves"])

def test_source_approval_does_not_grant_execution(tmp_path):
    with _ctx(tmp_path) as c:
        case=_case(c); cid=case["case_id"]
        c.build382.set_source_scope(case_id=cid,source_id="gleif.lei",state="approved",reviewer="analyst",confirmation="APPROVE SOURCE")
        row=c.db.one("SELECT state FROM case_source_scope WHERE case_id=? AND source_id=?",(cid,"gleif.lei")); assert row["state"]=="approved"
        assert c.build384.phase17_status(cid)["execution_authority"] is False


def test_app384_health_and_auth_boundary(tmp_path):
    from fastapi.testclient import TestClient
    from eagleeye.interfaces.web.app384 import create_workspace_app384
    app=create_workspace_app384(base_dir=tmp_path)
    try:
        client=TestClient(app)
        h=client.get('/health')
        assert h.status_code==200 and h.json()['build']=='384.0' and h.json()['phase17_integrated'] is True
        assert client.get('/api/build384/phase17-status').status_code==401
    finally:
        app.state.context.close()


def test_current_launchers_and_server_point_to_384():
    root=Path(__file__).resolve().parents[1]
    server=(root/'src/eagleeye/interfaces/web/server.py').read_text(encoding='utf-8')
    assert 'app384 import create_workspace_app384' in server
    assert 'EAGLEEYE_PRO_384_0.py' in (root/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8')
    assert 'EAGLEEYE_PRO_384_0.py' in (root/'START_EAGLEEYE_PRO.sh').read_text(encoding='utf-8')
