from pathlib import Path
import hashlib
import runpy

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app448 import render_workspace
from eagleeye.interfaces.web.app450 import create_workspace_app450

ROOT = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD = "Build450AdminPassword!2026"
REVIEWER_PASSWORD = "Build450ReviewerPassword!2026"


def setup_team(ctx, title="Build 450 Qualification"):
    admin = ctx.team_identity_359.create_initial_admin(
        username="admin450",
        display_name="Build 450 Administrator",
        password=ADMIN_PASSWORD,
    )
    reviewer = ctx.team_governance_359.create_user(
        identity=admin,
        username="reviewer450",
        display_name="Independent Build 450 Reviewer",
        global_role="reviewer",
        password=REVIEWER_PASSWORD,
    )
    case = ctx.team_governance_359.create_case(
        identity=admin,
        title=title,
        client="QA",
        purpose="Build 450 investigation workflow hard checkpoint",
        legal_basis="public_data",
    )
    ctx.team_governance_359.assign_case_role(
        identity=admin,
        case_id=case["case_id"],
        username=reviewer["username"],
        case_role="reviewer",
        notes="Independent Build 450 checkpoint reviewer",
    )
    return admin, reviewer, case


def test_build450_full_governed_workflow_engineering_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_username=reviewer["username"],
        )
        report = result["report"]

        assert result["engineering_result"] == "pass", report
        assert report["investigation_workflow_checkpoint_pass"] is True
        assert report["workflow_selftest"]["result"] == "PASS"
        assert all(report["workflow_selftest"]["checks"].values())
        assert all(report["component_checks_before"].values())
        assert all(report["component_checks_after"].values())
        assert report["authority_contract"]["pass"] is True
        assert report["release_result"] == "hold"
        assert report["production_release_ready"] is False
        assert report["truth_determined"] is False

        package_hash = report["workflow_selftest"]["package_hash"]
        assert package_hash
        exports = ctx.evidence_claims_dossier_447.exports(case["case_id"])
        assert exports
        assert exports[-1]["package_hash"] == package_hash


def test_build450_external_validation_is_not_faked_by_deterministic_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx, "External boundary 450")
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_username=reviewer["username"],
        )
        report = result["report"]
        assert report["engineering_result"] == "pass"
        assert report["release_result"] == "hold"
        assert report["release_checks"]["production_hardening_complete"] is False
        assert report["release_checks"]["external_user_validation_complete"] is False
        assert report["real_world_general_research_ready"] is False
        assert report["production_release_ready"] is False


def test_build450_rejects_same_user_as_reviewer(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case = setup_team(ctx, "Reviewer separation 450")
        with pytest.raises(PermissionError, match="independent reviewer"):
            ctx.build450.qualify_investigation_workflow_450(
                identity=admin,
                case_id=case["case_id"],
                reviewer_username=admin["username"],
            )


def test_build450_rejects_reviewer_without_required_case_capabilities(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin = ctx.team_identity_359.create_initial_admin(
            username="admin450",
            display_name="Build 450 Administrator",
            password=ADMIN_PASSWORD,
        )
        weak = ctx.team_governance_359.create_user(
            identity=admin,
            username="readonly450",
            display_name="Read Only 450",
            global_role="read_only",
            password="Build450ReadOnlyPassword!2026",
        )
        case = ctx.team_governance_359.create_case(
            identity=admin,
            title="Capability boundary 450",
            client="QA",
            purpose="Reviewer capability qualification",
            legal_basis="public_data",
        )
        ctx.team_governance_359.assign_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=weak["username"],
            case_role="read_only",
            notes="Must not qualify as reviewer",
        )
        with pytest.raises(PermissionError, match="lacks Build-450 case capabilities"):
            ctx.investigation_workflow_qualification_450.run_case_workflow(
                identity=admin,
                case_id=case["case_id"],
                reviewer_username=weak["username"],
            )


def test_build450_qualification_record_tamper_is_detected(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx, "Tamper 450")
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_username=reviewer["username"],
        )
        assert ctx.investigation_workflow_qualification_450.verify_integrity()["valid"]
        ctx.db.execute(
            "UPDATE phase20_workflow_qualification_run_450 SET release_result='pass' WHERE qualification_id=?",
            (result["qualification_id"],),
        )
        assert ctx.investigation_workflow_qualification_450.verify_integrity()["valid"] is False


def test_build450_current_app_keeps_review_bypass_closed_and_adds_checkpoint_routes(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    try:
        paths = {
            (method, getattr(route, "path", ""))
            for route in app.router.routes
            for method in (getattr(route, "methods", set()) or set())
        }
        for path in (
            "/api/build447/evidence/{evidence_id}/review",
            "/api/build447/claims/{claim_id}/review",
            "/api/build447/dossiers/{revision_id}/review",
            "/api/build447/dossiers/{revision_id}/export",
        ):
            assert ("POST", path) not in paths

        assert ("GET", "/api/build450/status") in paths
        assert ("GET", "/api/build450/cases/{case_id}/latest") in paths
        assert ("POST", "/api/build450/cases/{case_id}/qualify") in paths
        assert ("POST", "/api/build449/reviews") in paths
    finally:
        app.state.context.close()


def test_build450_http_workspace_shows_checkpoint_and_can_qualify(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, reviewer, case = setup_team(ctx, "HTTP Build 450")
    fingerprint = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    session = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fingerprint,
    )
    assert session is not None

    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", session.token)
        root = client.get("/", params={"view": "operations", "case_id": case["case_id"]})
        assert root.status_code == 200
        assert "Build 450" in root.text
        assert "Investigation Workflow Hard Checkpoint" in root.text
        assert "/api/build450/cases/" in root.text

        status = client.get("/api/build450/status")
        assert status.status_code == 200
        assert status.json()["hard_checkpoint"] is True
        assert status.json()["production_release_ready"] is False

        response = client.post(
            f"/api/build450/cases/{case['case_id']}/qualify",
            json={"reviewer_username": reviewer["username"]},
            headers={"sec-fetch-site": "same-origin"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["engineering_result"] == "pass"
        assert body["release_result"] == "hold"

        latest = client.get(f"/api/build450/cases/{case['case_id']}/latest")
        assert latest.status_code == 200
        assert latest.json()["item"]["engineering_result"] == "pass"


def test_build450_workspace_render_retains_team_review_and_checkpoint_boundaries(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx, "Rendered 450")
        snap = ctx.build449.team_review_snapshot_449(
            identity=admin,
            case_id=case["case_id"],
        )
        snap["checkpoint450"] = {
            **ctx.build450.investigation_workflow_status_450(),
            "latest": None,
        }
        markup = render_workspace(
            snap,
            view="operations",
            cases=[snap["case"]],
            audits=[],
        )
        assert "Build 450 · Investigation Workflow Hard Checkpoint" in markup
        assert "Engineering-PASS ist keine Production-Freigabe" in markup
        assert "Team Review · Build 449" in markup
        assert reviewer["username"] in markup
        assert "/api/build450/cases/" in markup


def test_build450_status_launcher_manifest_and_checkpoint_contract(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as ctx:
        setup_team(ctx)
        status = ctx.build450.investigation_workflow_status_450()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 10
        assert status["hard_checkpoint"]
        assert status["qualification_fail_closed"]
        assert status["independent_reviewer_required"]
        assert status["component_integrity_required"]
        assert status["full_governed_case_workflow_required"]
        assert status["github_ci_required"]
        assert status["full_repository_regression_required"]
        assert status["ui_regression_required"]
        assert status["codex_review_required_for_current_head"]
        assert status["release_gate_pass"] is False
        assert status["production_release_ready"] is False
        assert status["automatic_truth_determination"] is False

    import eagleeye.interfaces.web.app450 as appmod
    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app450",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_450_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app450 import create_workspace_app450" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert "EAGLEEYE_PRO_450_0.py" in (ROOT / "START_EAGLEEYE_PRO.sh").read_text()
    assert (ROOT / "README_BUILD_450_0.md").exists()
    assert (ROOT / "BUILD_450_CASE_TEST.md").exists()
    assert (ROOT / "RELEASE_MANIFEST_BUILD_450_0.json").exists()
