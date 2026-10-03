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
FP_ADMIN = "build450-admin-fingerprint"
FP_REVIEWER = "build450-reviewer-fingerprint"


def login(ctx, username, password, fingerprint):
    issued = ctx.team_identity_359.authenticate(
        username=username,
        password=password,
        client_fingerprint=fingerprint,
    )
    assert issued is not None
    identity = ctx.team_identity_359.validate_session(
        issued.token,
        client_fingerprint=fingerprint,
        touch=False,
    )
    assert identity is not None
    return identity, issued


def setup_users(ctx):
    bootstrap_admin = ctx.team_identity_359.create_initial_admin(
        username="admin450",
        display_name="Build 450 Administrator",
        password=ADMIN_PASSWORD,
    )
    reviewer_user = ctx.team_governance_359.create_user(
        identity=bootstrap_admin,
        username="reviewer450",
        display_name="Independent Build 450 Reviewer",
        global_role="reviewer",
        password=REVIEWER_PASSWORD,
    )
    admin, admin_session = login(ctx, "admin450", ADMIN_PASSWORD, FP_ADMIN)
    reviewer, reviewer_session = login(ctx, "reviewer450", REVIEWER_PASSWORD, FP_REVIEWER)
    return bootstrap_admin, reviewer_user, admin, reviewer, admin_session, reviewer_session


def setup_qualification_case(ctx):
    _bootstrap, _reviewer_user, admin, reviewer, admin_session, reviewer_session = setup_users(ctx)
    case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
        identity=admin,
        reviewer_username=reviewer["username"],
    )
    consent = ctx.build450.consent_investigation_workflow_qualification_case_450(
        case_id=case["case_id"],
        confirmation="CONSENT BUILD 450 QUALIFICATION",
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    assert consent["reviewer_username"] == reviewer["username"]
    return admin, reviewer, case, admin_session, reviewer_session


def test_build450_full_governed_workflow_engineering_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        report = result["report"]

        assert result["engineering_result"] == "pass", report
        assert report["investigation_workflow_checkpoint_pass"] is True
        assert report["engineering_checks"]["isolated_qualification_case"] is True
        assert report["engineering_checks"]["authenticated_independent_reviewer"] is True
        assert report["workflow_selftest"]["result"] == "PASS"
        assert all(report["workflow_selftest"]["checks"].values())
        assert all(report["component_checks_before"].values())
        assert all(report["component_checks_after"].values())
        assert report["authority_contract"]["pass"] is True
        assert report["release_result"] == "hold"
        assert report["production_release_ready"] is False
        assert report["truth_determined"] is False
        assert report["qualification_case"]["reviewer_username"] == reviewer["username"]

        package_hash = report["workflow_selftest"]["package_hash"]
        exports = ctx.evidence_claims_dossier_447.exports(case["case_id"])
        assert package_hash
        assert exports[-1]["package_hash"] == package_hash


def test_build450_external_validation_is_not_faked_by_deterministic_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        report = result["report"]
        assert report["engineering_result"] == "pass"
        assert report["release_result"] == "hold"
        assert report["release_checks"]["production_hardening_complete"] is False
        assert report["release_checks"]["external_user_validation_complete"] is False
        assert report["real_world_general_research_ready"] is False
        assert report["production_release_ready"] is False


def test_build450_requires_two_distinct_authenticated_sessions(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, admin, reviewer, _a, reviewer_session = setup_users(ctx)
        with pytest.raises(PermissionError, match="independent reviewer"):
            ctx.build450.prepare_investigation_workflow_qualification_case_450(
                identity=admin,
                reviewer_username=admin["username"],
            )

        case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
            identity=admin,
            reviewer_username=reviewer["username"],
        )
        ctx.build450.consent_investigation_workflow_qualification_case_450(
            case_id=case["case_id"],
            confirmation="CONSENT BUILD 450 QUALIFICATION",
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        ctx.team_identity_359.revoke_session(
            reviewer_session.token,
            reason="Build 450 revoked-reviewer regression",
        )
        with pytest.raises(PermissionError, match="reviewer authentication failed"):
            ctx.build450.qualify_investigation_workflow_450(
                identity=admin,
                case_id=case["case_id"],
                reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
            )


def test_build450_rejects_unmarked_operational_case_without_mutation(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, admin, reviewer, _a, _r = setup_users(ctx)
        case = ctx.team_governance_359.create_case(
            identity=admin,
            title="Ordinary operational case",
            client="QA",
            purpose="Normal investigation case; must never receive qualification fixtures.",
            legal_basis="public_data",
        )
        ctx.team_governance_359.assign_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=reviewer["username"],
            case_role="reviewer",
            notes="Ordinary case reviewer",
        )
        before = {
            "evidence": len(ctx.evidence_claims_dossier_447.case_evidence(case["case_id"])),
            "claims": len(ctx.evidence_claims_dossier_447.case_claims(case["case_id"])),
            "dossiers": len(ctx.evidence_claims_dossier_447.case_dossiers(case["case_id"])),
            "exports": len(ctx.evidence_claims_dossier_447.exports(case["case_id"])),
        }
        with pytest.raises(PermissionError, match="isolated qualification case"):
            ctx.build450.qualify_investigation_workflow_450(
                identity=admin,
                case_id=case["case_id"],
                reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
            )
        after = {
            "evidence": len(ctx.evidence_claims_dossier_447.case_evidence(case["case_id"])),
            "claims": len(ctx.evidence_claims_dossier_447.case_claims(case["case_id"])),
            "dossiers": len(ctx.evidence_claims_dossier_447.case_dossiers(case["case_id"])),
            "exports": len(ctx.evidence_claims_dossier_447.exports(case["case_id"])),
        }
        assert after == before


def test_build450_preflight_integrity_failure_aborts_before_workflow_mutation(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        source = ctx.build421.register_source(
            identity=admin,
            name="Build 450 tamper source",
            source_type="website",
            access_mode="public",
            base_url="https://tamper450.example.org/",
            capabilities=["public_pages"],
            coverage={"fixture_only": True},
        )
        ctx.db.execute(
            "UPDATE acquisition_source_421 SET record_hash='tampered' WHERE source_id=?",
            (source["source_id"],),
        )
        before_events = int(
            (ctx.db.one(
                "SELECT COUNT(*) n FROM acquisition_event_422 WHERE case_id=?",
                (case["case_id"],),
            ) or {}).get("n") or 0
        )
        with pytest.raises(RuntimeError, match="preflight integrity failed"):
            ctx.investigation_workflow_qualification_450.run_case_workflow(
                identity=admin,
                case_id=case["case_id"],
                reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
            )
        after_events = int(
            (ctx.db.one(
                "SELECT COUNT(*) n FROM acquisition_event_422 WHERE case_id=?",
                (case["case_id"],),
            ) or {}).get("n") or 0
        )
        assert after_events == before_events
        assert ctx.build450.investigation_workflow_latest_450(case["case_id"]) is None


def test_build450_rejects_reviewer_after_case_capability_revocation(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        ctx.team_governance_359.revoke_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=reviewer["username"],
            case_role="reviewer",
            reason="Build 450 capability-revocation regression.",
        )
        with pytest.raises(PermissionError, match="lacks Build-450 case capabilities"):
            ctx.build450.qualify_investigation_workflow_450(
                identity=admin,
                case_id=case["case_id"],
                reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
            )


def test_build450_requires_explicit_reviewer_consent(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, admin, reviewer, _a, _r = setup_users(ctx)
        case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
            identity=admin,
            reviewer_username=reviewer["username"],
        )
        with pytest.raises(PermissionError, match="explicit reviewer consent"):
            ctx.build450.qualify_investigation_workflow_450(
                identity=admin,
                case_id=case["case_id"],
                reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
            )
        with pytest.raises(PermissionError, match="explicit CONSENT BUILD 450 QUALIFICATION"):
            ctx.build450.consent_investigation_workflow_qualification_case_450(
                case_id=case["case_id"],
                confirmation="GO",
                reviewer_session_token=_r.token,
                reviewer_client_fingerprint=FP_REVIEWER,
            )
        consent = ctx.build450.consent_investigation_workflow_qualification_case_450(
            case_id=case["case_id"],
            confirmation="CONSENT BUILD 450 QUALIFICATION",
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert consent["confirmation"] == "CONSENT BUILD 450 QUALIFICATION"

def test_build450_qualification_record_tamper_disables_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert ctx.investigation_workflow_qualification_450.verify_integrity()["valid"]
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is True
        ctx.db.execute(
            "UPDATE phase20_workflow_qualification_run_450 SET release_result='pass' WHERE qualification_id=?",
            (result["qualification_id"],),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["integrity_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False



def test_build450_corrupt_export_artifact_invalidates_checkpoint_status(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        workflow = result["report"]["workflow_selftest"]
        assert workflow["artifact_verification"]["valid"] is True
        package = Path(workflow["artifact_paths"]["case_package"])
        package.write_bytes(b"corrupted-build450-package")
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_artifacts_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False


def test_build450_required_component_tamper_invalidates_existing_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, _r = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=_r.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert result["engineering_result"] == "pass"
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is True

        evidence_id = result["report"]["workflow_selftest"]["evidence_id"]
        ctx.db.execute(
            "UPDATE evidence_item_447 SET review_note='tampered-after-qualification' WHERE evidence_id=?",
            (evidence_id,),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["current_component_integrity_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False


def test_build450_current_app_is_read_only_for_checkpoint_and_keeps_review_bypass_closed(tmp_path):
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
        assert ("POST", "/api/build450/cases/{case_id}/qualify") not in paths
        assert ("POST", "/api/build449/reviews") in paths
    finally:
        app.state.context.close()


def test_build450_http_workspace_shows_read_only_checkpoint_status(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    _bootstrap, _reviewer_user, admin, _reviewer, admin_session, _r = setup_users(ctx)
    case = ctx.team_governance_359.create_case(
        identity=admin,
        title="HTTP operational Build 450",
        client="QA",
        purpose="Operational workspace must not launch qualification mutation.",
        legal_basis="public_data",
    )

    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", admin_session.token)
        # TestClient's expected fingerprint is generated from these headers.
        # Re-authenticate with the same fingerprint used by the app.
        client.cookies.clear()
        fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
        issued = ctx.team_identity_359.authenticate(
            username=admin["username"],
            password=ADMIN_PASSWORD,
            client_fingerprint=fp,
        )
        client.cookies.set("ee_auth_session", issued.token)
        root = client.get("/", params={"view": "operations", "case_id": case["case_id"]})
        assert root.status_code == 200
        assert "Build 450" in root.text
        assert "Investigation Workflow Hard Checkpoint" in root.text
        assert "read-only Checkpoint-Status" in root.text
        assert "/api/build450/cases/" not in root.text or "/qualify" not in root.text

        status = client.get("/api/build450/status")
        assert status.status_code == 200
        assert status.json()["hard_checkpoint"] is True
        assert status.json()["interactive_http_qualification_disabled"] is True
        assert status.json()["production_release_ready"] is False


def test_build450_workspace_render_retains_team_review_and_checkpoint_boundaries(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, admin, reviewer, _a, _r = setup_users(ctx)
        case = ctx.team_governance_359.create_case(
            identity=admin,
            title="Rendered operational 450",
            client="QA",
            purpose="Read-only rendered checkpoint status",
            legal_basis="public_data",
        )
        ctx.team_governance_359.assign_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=reviewer["username"],
            case_role="reviewer",
            notes="Rendered workspace reviewer",
        )
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
        assert "CI-/Test-/Admin-intern" in markup
        assert "/api/build450/cases/" not in markup or "/qualify" not in markup


def test_build450_status_launcher_manifest_and_checkpoint_contract(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, _admin, _reviewer, _a, _r = setup_users(ctx)
        status = ctx.build450.investigation_workflow_status_450()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 10
        assert status["hard_checkpoint"]
        assert status["qualification_fail_closed"]
        assert status["independent_reviewer_required"]
        assert status["authenticated_reviewer_session_required"]
        assert status["explicit_reviewer_consent_required"]
        assert status["isolated_qualification_case_required"]
        assert status["interactive_http_qualification_disabled"]
        assert status["component_integrity_required"]
        assert status["current_component_integrity_valid"]
        assert status["current_authority_contract_valid"]
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
