from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app455 import create_workspace_app455

ROOT = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD = "Quartz!Harbor_7621_Admin"
REVIEWER_PASSWORD = "Cedar!Orbit_5834_Review"
FP_ADMIN = "build455-test-admin"
FP_REVIEWER = "build455-test-reviewer"


def login(ctx, username, password, fingerprint):
    issued = ctx.team_identity_359.authenticate(
        username=username, password=password, client_fingerprint=fingerprint
    )
    assert issued is not None
    identity = ctx.team_identity_359.validate_session(
        issued.token, client_fingerprint=fingerprint, touch=False
    )
    assert identity is not None
    return identity, issued


def setup_users(ctx):
    bootstrap = ctx.team_identity_359.create_initial_admin(
        username="admin455test",
        display_name="Build 455 Test Admin",
        password=ADMIN_PASSWORD,
    )
    ctx.team_governance_359.create_user(
        identity=bootstrap,
        username="reviewer455test",
        display_name="Build 455 Test Reviewer",
        global_role="reviewer",
        password=REVIEWER_PASSWORD,
    )
    admin, admin_session = login(ctx, "admin455test", ADMIN_PASSWORD, FP_ADMIN)
    reviewer, reviewer_session = login(ctx, "reviewer455test", REVIEWER_PASSWORD, FP_REVIEWER)
    return admin, reviewer, admin_session, reviewer_session


def run_retained_450(ctx):
    admin, reviewer, admin_session, reviewer_session = setup_users(ctx)
    case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
        identity=admin, reviewer_username=reviewer["username"]
    )
    ctx.build450.consent_investigation_workflow_qualification_case_450(
        case_id=case["case_id"],
        confirmation="CONSENT BUILD 450 QUALIFICATION",
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    result = ctx.build450.qualify_investigation_workflow_450(
        identity=admin,
        case_id=case["case_id"],
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    assert result["engineering_result"] == "pass"
    return admin, reviewer


def test_build455_retains_450_and_preflight_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        run_retained_450(ctx)
        checks = ctx.operational_qualification_455._engineering_checks()
        assert checks["build450_checkpoint_pass"] is True
        assert checks["build450_integrity_valid"] is True
        assert checks["surface_retrieval_integrity"] is True
        assert checks["surface_hardening_integrity"] is True
        assert checks["retrieval_process_isolation"] is True
        assert checks["retrieval_content_risk_gate"] is True
        assert checks["retrieval_unsupported_profile_fails_closed"] is True
        assert checks["infrastructure_integrity"] is True
        assert checks["infrastructure_active_scanning_false"] is True
        assert checks["xref_integrity"] is True
        assert checks["xref_automatic_ownership_false"] is True
        assert checks["five_build_checkpoint"] is True
        assert all(checks.values())


def test_build455_fixture_source_cannot_satisfy_real_source_boundary(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer = run_retained_450(ctx)
        source = ctx.build421.register_source(
            identity=admin,
            name="Build 455 fixture must not qualify",
            source_type="website",
            access_mode="public",
            base_url="https://fixture455.example.org/",
            capabilities=["public_pages"],
            coverage={"fixture_only": True, "live_execution_forbidden": True},
        )
        _source, checks = ctx.operational_qualification_455._source_real_public(source["source_id"])
        assert checks["non_fixture"] is False
        assert checks["not_live_forbidden"] is False


def test_build455_status_health_version_and_full_test_contract(tmp_path):
    app = create_workspace_app455(base_dir=tmp_path)
    try:
        status = app.state.context.build455.build455_status()
        assert status["build"] == "455.0"
        assert status["hard_checkpoint"] is True
        assert status["full_research_gate_this_build"] is True
        assert status["next_checkpoint"] == "460.0"
        assert status["production_release_ready"] is False
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True, "status": "ok", "build": "455.0"}
    finally:
        app.state.context.close()

    assert 'version = "455.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "455.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert "app455 import create_workspace_app455" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "EAGLEEYE_PRO_455_0.py").exists()
    assert (ROOT / "INSTALL_EAGLEEYE_455.py").exists()
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "build_number % 5 == 0" in ci
    assert "test_build455_operational_checkpoint.py" in ci


def test_build455_surface441_tamper_breaks_engineering_preflight(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer = run_retained_450(ctx)
        case = ctx.team_governance_359.create_case(
            identity=admin,
            title="Build 455 provenance tamper fixture",
            client="Internal QA",
            purpose="Verify Build-441 provenance tamper closes the 455 gate.",
            legal_basis="public_data",
        )
        result = ctx.build441.run_surface_retrieval_case_selftest(
            identity=admin, case_id=case["case_id"]
        )
        run_id = result["run"]["run_id"]
        ctx.db.execute(
            "UPDATE surface_retrieval_run_441 SET event_id='forged_event' WHERE run_id=?",
            (run_id,),
        )
        checks = ctx.operational_qualification_455._engineering_checks()
        assert checks["surface_retrieval_integrity"] is False


def test_build455_appcontext_lifecycle_requires_actual_close(tmp_path):
    first = AppContext(base_dir=tmp_path)
    second = None
    try:
        first_service = first.operational_qualification_455
        first_id = first_service.context_instance_id
        second = AppContext(base_dir=tmp_path)
        second_service = second.operational_qualification_455
        before = second_service._context_lifecycle_checks(first_id)
        assert before["context_instance_changed"] is True
        assert before["qualification_context_record_present"] is True
        assert before["qualification_context_closed"] is False
        assert all(
            bool(v) for k, v in before.items()
            if k != "qualification_context_closed"
        )

        first.close()
        after = second_service._context_lifecycle_checks(first_id)
        assert all(after.values())
    finally:
        first.close()
        if second is not None:
            second.close()
