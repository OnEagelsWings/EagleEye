from __future__ import annotations

from pathlib import Path
import json

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase20.operational_qualification455 import OperationalResearchQualification455
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


def test_build455_checkpoint_regression_exclusions_are_exact_and_never_exclude_current_build():
    manifest = json.loads(
        (ROOT / "tools" / "CHECKPOINT_REGRESSION_EXCLUSIONS_455.json").read_text(encoding="utf-8")
    )
    exclusions = manifest["exclusions"]
    assert manifest["excluded_count"] == len(exclusions) == 114
    nodeids = [item["nodeid"] for item in exclusions]
    assert len(nodeids) == len(set(nodeids))
    assert all(nodeid.startswith("tests/test_build") and "::" in nodeid for nodeid in nodeids)
    assert not any("test_build455" in nodeid for nodeid in nodeids)
    assert all(item["reason"].startswith("superseded_") for item in exclusions)
    runner = (ROOT / "tools" / "run_checkpoint_regression455.py").read_text(encoding="utf-8")
    assert "--deselect" in runner
    assert "current_build_tests_excluded" in runner


def test_build455_case_qualification_api_requires_case_read_authorization():
    text = (
        ROOT / "src" / "eagleeye" / "interfaces" / "web" / "app455.py"
    ).read_text(encoding="utf-8")
    assert 'capability="case.read"' in text
    assert 'HTTPException(403' in text
    assert "operational_research_latest_455(case_id)" in text


def test_build455_restart_and_status_revalidate_current_prerequisites():
    text = (
        ROOT / "eagleeye_pro" / "phase20" / "operational_qualification455.py"
    ).read_text(encoding="utf-8")
    assert "restart_engineering_checks = self._engineering_checks()" in text
    assert '"build450_checkpoint_still_valid"' in text
    assert "def _current_gate_revalidation" in text
    assert '"physical_export_current"' in text
    assert '"recovery_state_binding_current"' in text
    assert "current_live_case = self._current_gate_revalidation(run)" in text
    assert '"current_live_case_revalidation"' in text


def test_build455_completed_review_must_match_current_artifact_reviewer_and_decision():
    review = {
        "state": "completed",
        "completed_by": "independent-reviewer",
        "decision": "accepted",
    }
    current = {
        "reviewed_by": "independent-reviewer",
        "review_state": "accepted",
    }
    assert OperationalResearchQualification455._review_matches_current_artifact(
        review, "evidence", current
    )
    changed_reviewer = {**current, "reviewed_by": "creator"}
    assert not OperationalResearchQualification455._review_matches_current_artifact(
        review, "evidence", changed_reviewer
    )
    changed_decision = {**current, "review_state": "context_only"}
    assert not OperationalResearchQualification455._review_matches_current_artifact(
        review, "evidence", changed_decision
    )


def test_build455_counterevidence_requires_distinct_content_payload():
    support = {"content_id": "content-a", "content_sha256": "a" * 64}
    duplicate = {"content_id": "content-a", "content_sha256": "a" * 64}
    distinct = {"content_id": "content-b", "content_sha256": "b" * 64}
    assert not OperationalResearchQualification455._distinct_evidence_payloads(
        support, duplicate
    )
    assert OperationalResearchQualification455._distinct_evidence_payloads(
        support, distinct
    )


def test_build455_evidence_review_must_be_independent_from_acquisition_actor():
    qualifier = object.__new__(OperationalResearchQualification455)

    class Identity:
        @staticmethod
        def public_user(username):
            assert username == "reviewer"
            return {"username": "reviewer", "user_id": "user-reviewer"}

    class Governance:
        identity = Identity()

    qualifier.governance = Governance()
    review = {"completed_by": "reviewer"}
    assert not qualifier._reviewer_independent_from_acquisition(
        review, {"created_by": "user-reviewer"}
    )
    assert not qualifier._reviewer_independent_from_acquisition(
        review, {"created_by": "reviewer"}
    )
    assert qualifier._reviewer_independent_from_acquisition(
        review, {"created_by": "user-acquirer"}
    )


def test_build455_latest_review_denial_supersedes_older_approval(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        base = {
            "case_id": "case-review-currency-455",
            "object_type": "dossier_export",
            "object_id": "revision-review-currency-455",
            "object_hash_at_request": "hash-review-currency-455",
            "requested_by": "requester455",
            "assigned_to": "reviewer455",
            "request_note": "Build 455 review currency regression",
            "claimed_by": "reviewer455",
            "claimed_at": "2026-10-11T18:00:00+00:00",
            "completed_by": "reviewer455",
            "review_note": "Build 455 review currency regression",
        }
        rows = [
            {
                **base,
                "review_id": "review455_old_approve",
                "state": "completed",
                "requested_at": "2026-10-11T18:00:00+00:00",
                "decision": "approve",
                "completed_at": "2026-10-11T18:01:00+00:00",
                "updated_at": "2026-10-11T18:01:00+00:00",
            },
            {
                **base,
                "review_id": "review455_new_deny",
                "state": "denied",
                "requested_at": "2026-10-11T18:02:00+00:00",
                "decision": "deny",
                "completed_at": "2026-10-11T18:03:00+00:00",
                "updated_at": "2026-10-11T18:03:00+00:00",
            },
        ]
        columns = [
            "review_id", "case_id", "object_type", "object_id", "object_hash_at_request",
            "requested_by", "assigned_to", "state", "request_note", "requested_at",
            "claimed_by", "claimed_at", "decision", "completed_by", "completed_at",
            "review_note", "updated_at", "record_hash",
        ]
        for row in rows:
            row["record_hash"] = ctx.human_review_449._rh(row)
            ctx.db.execute(
                "INSERT INTO review_request_449("
                + ",".join(columns)
                + ") VALUES("
                + ",".join("?" for _ in columns)
                + ")",
                tuple(row[name] for name in columns),
            )
        latest = ctx.operational_qualification_455._latest_review(
            base["case_id"], base["object_type"], base["object_id"]
        )
        assert latest["review_id"] == "review455_new_deny"
        assert latest["state"] == "denied"
        assert latest["decision"] == "deny"
