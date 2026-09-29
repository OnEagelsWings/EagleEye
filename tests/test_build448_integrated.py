from pathlib import Path
import hashlib
import runpy

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app448 import create_workspace_app448, render_workspace

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "SecureFixturePassword!2026"


def admin(ctx):
    if ctx.team_identity_359.bootstrap_required():
        return ctx.team_identity_359.create_initial_admin(
            username="analyst",
            display_name="Analyst Fixture",
            password=PASSWORD,
        )
    return ctx.team_identity_359.public_user("analyst")


def make_case(ctx, identity, title="Build 448 Investigator Workspace"):
    return ctx.team_governance_359.create_case(
        identity=identity,
        title=title,
        client="QA",
        purpose="Build 448 UI and investigator-workspace qualification",
        legal_basis="public_data",
    )


def route_inventory(app):
    rows = []
    for route in app.router.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        for method in getattr(route, "methods", set()) or set():
            rows.append((str(method).upper(), str(path)))
    return rows


def test_snapshot_integrates_current_investigation_chain(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity)["case_id"]
        result = ctx.build447.run_evidence_claims_dossier_case_selftest(
            identity=identity,
            case_id=cid,
        )
        assert result["result"] == "PASS"

        snap = ctx.build448.investigator_workspace_snapshot_448(
            identity=identity,
            case_id=cid,
        )
        m = snap["metrics"]
        assert snap["case"]["case_id"] == cid
        assert m["loops"] >= 1
        assert m["evidence"] >= 2
        assert m["claims"] >= 1
        assert m["claims_accepted"] >= 1
        assert m["dossiers"] >= 1
        assert m["exports"] >= 1
        assert snap["latest_loop"]
        assert snap["matrix"] is not None
        assert snap["latest_synthesis"] is not None
        assert len(snap["primary_views"]) == 8
        assert snap["truth_determined"] is False


def test_primary_workspace_is_clear_responsive_and_current(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "Current UI 448")["case_id"]
        snap = ctx.build448.investigator_workspace_snapshot_448(
            identity=identity,
            case_id=cid,
        )
        markup = render_workspace(snap, view="overview", cases=[snap["case"]], audits=[])

        assert "<!doctype html>" in markup.lower()
        assert 'lang="de"' in markup
        assert 'name="viewport"' in markup
        assert "<main" in markup
        assert "<nav" in markup
        assert 'aria-live="polite"' in markup
        assert ":focus-visible" in markup
        assert "@media(max-width:1000px)" in markup
        assert "Build 448 · Investigator Workspace" in markup
        assert "Build 447 Evidence/Claims/Dossier integriert" in markup
        assert "Phase 13 · Simplified AI Investigation Workspace" not in markup
        assert "/legacy" in markup
        assert "keine automatische Wahrheitsfeststellung" in markup.lower()
        for key in ("overview","research","ai","evidence","claims","analysis","dossier","operations"):
            assert f"view={key}" in markup


def test_ui_route_contract_audit_passes_on_real_app(tmp_path):
    app = create_workspace_app448(base_dir=tmp_path)
    ctx = app.state.context
    try:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "Route contract 448")["case_id"]
        snap = ctx.build448.investigator_workspace_snapshot_448(
            identity=identity,
            case_id=cid,
        )
        markup = render_workspace(snap, view="overview", cases=[snap["case"]], audits=[])
        result = ctx.build448.run_ui_audit_448(
            identity=identity,
            case_id=cid,
            markup=markup,
            route_inventory=route_inventory(app),
        )
        assert result["result"] == "PASS", result
        assert all(result["checks"].values()), result
        assert result["missing_routes"] == []
        assert ctx.investigator_workspace_448.verify_integrity()["valid"]
    finally:
        ctx.close()


def test_all_primary_views_render_without_dead_view_mapping(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "View rendering 448")["case_id"]
        snap = ctx.build448.investigator_workspace_snapshot_448(
            identity=identity,
            case_id=cid,
        )
        for view in ("overview","research","ai","evidence","claims","analysis","dossier","operations"):
            markup = render_workspace(snap, view=view, cases=[snap["case"]], audits=[])
            assert "EagleEye" in markup
            assert "Build 448" in markup
            assert f"view={view}" in markup
            assert "<main" in markup
            assert 'id="workspace-status"' in markup


def test_workspace_http_root_and_views_work_with_authenticated_session(tmp_path):
    app = create_workspace_app448(base_dir=tmp_path)
    ctx = app.state.context
    identity = admin(ctx)
    cid = make_case(ctx, identity, "HTTP workspace 448")["case_id"]

    fingerprint = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    session = ctx.team_identity_359.authenticate(
        username="analyst",
        password=PASSWORD,
        client_fingerprint=fingerprint,
    )
    assert session is not None

    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", session.token)
        for view in ("overview","research","ai","evidence","claims","analysis","dossier","operations"):
            response = client.get("/", params={"view": view, "case_id": cid})
            assert response.status_code == 200, (view, response.text[:500])
            assert "Build 448" in response.text
            assert "Phase 13 · Simplified AI Investigation Workspace" not in response.text

        legacy = client.get("/legacy", params={"tab": "cockpit302", "case_id": cid})
        assert legacy.status_code == 200
        assert "EagleEye" in legacy.text


def test_ui_audit_endpoint_executes_and_persists(tmp_path):
    app = create_workspace_app448(base_dir=tmp_path)
    ctx = app.state.context
    identity = admin(ctx)
    cid = make_case(ctx, identity, "HTTP audit 448")["case_id"]
    fingerprint = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    session = ctx.team_identity_359.authenticate(
        username="analyst",
        password=PASSWORD,
        client_fingerprint=fingerprint,
    )
    assert session is not None

    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", session.token)
        response = client.post(
            f"/api/build448/cases/{cid}/ui-audit",
            headers={"sec-fetch-site": "same-origin"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["result"] == "PASS"
        history = client.get(f"/api/build448/cases/{cid}/ui-audits")
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1


def test_ui_audit_record_tamper_is_detected(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity = admin(ctx)
        cid = make_case(ctx, identity, "Audit tamper 448")["case_id"]
        snap = ctx.build448.investigator_workspace_snapshot_448(identity=identity, case_id=cid)
        markup = render_workspace(snap, view="overview", cases=[snap["case"]], audits=[])
        # Route inventory can be supplied from the app contract without executing network I/O.
        from eagleeye.interfaces.web.app448 import REQUIRED_MUTATION_ROUTES if False else render_workspace
        # Use an actual app so every inherited route is included.
        app = create_workspace_app448(base_dir=tmp_path / "route-app")
        try:
            route_identity = admin(app.state.context)
            route_case = make_case(app.state.context, route_identity, "route inventory")["case_id"]
            route_snap = app.state.context.build448.investigator_workspace_snapshot_448(identity=route_identity, case_id=route_case)
            route_markup = render_workspace(route_snap, view="overview", cases=[route_snap["case"]], audits=[])
            result = app.state.context.build448.run_ui_audit_448(
                identity=route_identity,
                case_id=route_case,
                markup=route_markup,
                route_inventory=route_inventory(app),
            )
            assert result["result"] == "PASS"
            app.state.context.db.execute(
                "UPDATE ui_audit_448 SET result='FAIL' WHERE audit_id=?",
                (result["audit_id"],),
            )
            assert app.state.context.investigator_workspace_448.verify_integrity()["valid"] is False
        finally:
            app.state.context.close()


def test_status_and_launcher_contract(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as ctx:
        admin(ctx)
        status = ctx.build448.investigator_workspace_status_448()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 8
        assert status["case_first_workspace"]
        assert status["responsive_workspace"]
        assert status["evidence_claim_dossier_flow_visible"]
        assert status["ui_route_contract_audited"]
        assert status["legacy_workspace_available"]
        assert status["scheduled_ui_audit_supported"]
        assert status["automatic_truth_determination"] is False
        assert status["production_release_ready"] is False
        assert status["next_build"] == "449.0"
        assert status["next_hard_checkpoint"] == "450.0"

    import eagleeye.interfaces.web.app448 as appmod
    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app448",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_448_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app448 import create_workspace_app448" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert "EAGLEEYE_PRO_448_0.py" in (ROOT / "START_EAGLEEYE_PRO.sh").read_text()
    assert (ROOT / "BUILD_448_UI_AUDIT.md").exists()
    assert (ROOT / "README_BUILD_448_0.md").exists()
