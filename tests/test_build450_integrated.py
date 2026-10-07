from pathlib import Path
import hashlib
import json
import runpy

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app448 import render_workspace
from eagleeye.interfaces.web.app450 import (
    JSON_PAYLOAD_GUARD_MAX_BYTES,
    QUALIFICATION_IDENTIFIER_TOKEN_LIMIT,
    _route_body_requires_payload_guard,
    create_workspace_app450,
)

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
                reviewer_session_token=reviewer_session.token,
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



def test_build450_artifact_read_errors_fail_closed_without_status_exception(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        workflow = result["report"]["workflow_selftest"]
        docx_path = Path(workflow["artifact_paths"]["docx"])
        package_path = Path(workflow["artifact_paths"]["case_package"])
        original_read_bytes = Path.read_bytes
        blocked = {docx_path}

        def guarded_read_bytes(path):
            if Path(path) in blocked:
                raise OSError("synthetic Build-450 artifact read failure")
            return original_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_artifacts_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False

        blocked.clear()
        blocked.add(package_path)
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_artifacts_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False



def test_build450_malformed_artifact_path_values_fail_closed_without_status_500(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        original_report = result["report"]

        for key, malformed in (
            ("docx", ["not", "a", "path"]),
            ("case_package", {"not": "a path"}),
        ):
            report = json.loads(json.dumps(original_report))
            report["workflow_selftest"]["artifact_paths"][key] = malformed
            ctx.db.execute(
                "UPDATE phase20_workflow_qualification_run_450 SET report_json=? WHERE qualification_id=?",
                (json.dumps(report), result["qualification_id"]),
            )
            status = ctx.build450.investigation_workflow_status_450()
            assert status["integrity_valid"] is False
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



def test_build450_reviewer_proof_requires_real_session_token_and_fingerprint(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        _bootstrap, _reviewer_user, admin, reviewer, admin_session, reviewer_session = setup_users(ctx)
        case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
            identity=admin,
            reviewer_username=reviewer["username"],
        )
        with pytest.raises(PermissionError, match="reviewer authentication failed"):
            ctx.build450.consent_investigation_workflow_qualification_case_450(
                case_id=case["case_id"],
                confirmation="CONSENT BUILD 450 QUALIFICATION",
                reviewer_session_token=reviewer_session.token,
                reviewer_client_fingerprint="copied-or-wrong-fingerprint",
            )
        with pytest.raises(PermissionError, match="only the designated reviewer"):
            ctx.build450.consent_investigation_workflow_qualification_case_450(
                case_id=case["case_id"],
                confirmation="CONSENT BUILD 450 QUALIFICATION",
                reviewer_session_token=admin_session.token,
                reviewer_client_fingerprint=FP_ADMIN,
            )


def test_build450_deleted_consent_retracts_existing_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert result["engineering_result"] == "pass"
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is True
        ctx.db.execute(
            "DELETE FROM phase20_qualification_consent_450 WHERE case_id=?",
            (case["case_id"],),
        )
        integrity = ctx.investigation_workflow_qualification_450.verify_integrity()
        assert integrity["valid"] is False
        assert any(x["reason"] == "reviewer_consent_missing" for x in integrity["violations"])
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is False


def test_build450_deleted_case_marker_retracts_existing_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _a, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert result["engineering_result"] == "pass"
        ctx.db.execute(
            "DELETE FROM phase20_qualification_case_450 WHERE case_id=?",
            (case["case_id"],),
        )
        integrity = ctx.investigation_workflow_qualification_450.verify_integrity()
        assert integrity["valid"] is False
        assert any(x["reason"] == "qualification_case_marker_missing" for x in integrity["violations"])
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is False


def test_build450_qualification_cases_are_hidden_from_operational_workspace(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    _bootstrap, _reviewer_user, admin, reviewer, _admin_session, _reviewer_session = setup_users(ctx)
    qualification_case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
        identity=admin,
        reviewer_username=reviewer["username"],
    )
    operational_case = ctx.team_governance_359.create_case(
        identity=admin,
        title="Operational Build 450 Case",
        client="QA",
        purpose="Normal operational case visible in the current workspace.",
        legal_basis="public_data",
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        blocked = client.get(
            "/",
            params={"view": "overview", "case_id": qualification_case["case_id"]},
        )
        assert blocked.status_code == 403
        assert "Qualifikationsfall isoliert" in blocked.text
        root = client.get("/", params={"view": "overview"})
        assert root.status_code == 200
        assert "Operational Build 450 Case" in root.text
        assert "Build 450 Isolated Qualification" not in root.text
        assert qualification_case["case_id"] not in root.text
        assert operational_case["case_id"] in root.text



def test_build450_reconsent_preserves_prior_qualification_integrity(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        first = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        assert first["engineering_result"] == "pass"
        first_consent_id = first["report"]["qualification_case"]["consent_id"]

        ctx.team_identity_359.revoke_session(
            reviewer_session.token,
            reason="Build 450 re-consent history regression.",
        )
        reviewer2, reviewer_session2 = login(
            ctx,
            reviewer["username"],
            REVIEWER_PASSWORD,
            "build450-reviewer-fingerprint-2",
        )
        second_consent = ctx.build450.consent_investigation_workflow_qualification_case_450(
            case_id=case["case_id"],
            confirmation="CONSENT BUILD 450 QUALIFICATION",
            reviewer_session_token=reviewer_session2.token,
            reviewer_client_fingerprint="build450-reviewer-fingerprint-2",
        )
        assert second_consent["consent_id"] != first_consent_id

        second = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session2.token,
            reviewer_client_fingerprint="build450-reviewer-fingerprint-2",
        )
        assert second["engineering_result"] == "pass"
        assert ctx.investigation_workflow_qualification_450.verify_integrity()["valid"] is True
        assert ctx.build450.investigation_workflow_status_450()["investigation_workflow_checkpoint_pass"] is True
        consent_count = int(
            (ctx.db.one(
                "SELECT COUNT(*) n FROM phase20_qualification_consent_450 WHERE case_id=?",
                (case["case_id"],),
            ) or {}).get("n") or 0
        )
        assert consent_count == 2


def test_build450_only_qualification_case_renders_safe_empty_state_and_blocks_legacy_exposure(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    _bootstrap, _reviewer_user, admin, reviewer, _admin_session, _reviewer_session = setup_users(ctx)
    qualification_case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
        identity=admin,
        reviewer_username=reviewer["username"],
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        blocked_root = client.get("/", params={"case_id": qualification_case["case_id"]})
        assert blocked_root.status_code == 403
        assert "Qualifikationsfall isoliert" in blocked_root.text

        root = client.get("/")
        assert root.status_code == 200
        assert "Kein operativer Fall verfügbar" in root.text
        assert qualification_case["case_id"] not in root.text
        assert "Build 450 Isolated Qualification" not in root.text

        legacy = client.get("/legacy", params={"case_id": qualification_case["case_id"]})
        assert legacy.status_code == 403
        assert "Qualifikationsfall isoliert" in legacy.text
        assert qualification_case["case_id"] not in legacy.text
        assert "Build 450 Isolated Qualification" not in legacy.text


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



def test_build450_deleting_bound_export_row_retracts_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _a, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        workflow = result["report"]["workflow_selftest"]
        status = ctx.build450.investigation_workflow_status_450()
        assert status["investigation_workflow_checkpoint_pass"] is True
        assert status["qualified_workflow_rows_valid"] is True
        ctx.db.execute(
            "DELETE FROM dossier_export_447 WHERE export_id=?",
            (workflow["export_id"],),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_workflow_rows_valid"] is False
        assert any(x["reason"] == "export_row_missing" for x in status["qualified_workflow_row_violations"])
        assert status["investigation_workflow_checkpoint_pass"] is False


def test_build450_deleting_bound_acquisition_execution_retracts_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _a, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        workflow = result["report"]["workflow_selftest"]
        acquisition = workflow["acquisition"]
        assert acquisition["executions"]
        execution_id = acquisition["executions"][0]["execution_id"]

        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_workflow_rows_valid"] is True
        assert status["investigation_workflow_checkpoint_pass"] is True

        ctx.db.execute(
            "DELETE FROM live_ai_execution_446 WHERE execution_id=?",
            (execution_id,),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_workflow_rows_valid"] is False
        assert any(
            x["reason"] == "acquisition_execution_row_missing"
            and x.get("id") == execution_id
            for x in status["qualified_workflow_row_violations"]
        )
        assert status["investigation_workflow_checkpoint_pass"] is False


def test_build450_deleting_bound_review_row_retracts_checkpoint_pass(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _a, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        workflow = result["report"]["workflow_selftest"]
        ctx.db.execute(
            "DELETE FROM review_request_449 WHERE review_id=?",
            (workflow["export_review_id"],),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["qualified_workflow_rows_valid"] is False
        assert any(x["reason"] == "export_review_row_missing" for x in status["qualified_workflow_row_violations"])
        assert status["investigation_workflow_checkpoint_pass"] is False


def test_build450_qualification_case_is_blocked_on_inherited_case_routes(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    _bootstrap, _reviewer_user, admin, reviewer, _admin_session, _reviewer_session = setup_users(ctx)
    qualification_case = ctx.build450.prepare_investigation_workflow_qualification_case_450(
        identity=admin,
        reviewer_username=reviewer["username"],
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        legacy_case = client.get(f"/cases/{qualification_case['case_id']}")
        assert legacy_case.status_code == 403
        assert "Qualifikationsfall isoliert" in legacy_case.text

        inherited_mutation = client.post(
            f"/api/build447/cases/{qualification_case['case_id']}/claims",
            headers={"sec-fetch-site": "same-origin"},
            json={"statement": "qualification isolation regression", "support_evidence_ids": []},
        )
        assert inherited_mutation.status_code == 403
        assert "isolated" in inherited_mutation.json()["detail"].lower()


def test_build450_qualification_review_object_is_blocked_on_inherited_review_route(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
    result = ctx.build450.qualify_investigation_workflow_450(
        identity=admin,
        case_id=case["case_id"],
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    review_id = result["report"]["workflow_selftest"]["export_review_id"]
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            f"/api/build449/reviews/{review_id}/comments",
            headers={"sec-fetch-site": "same-origin"},
            json={"kind": "comment", "body": "qualification isolation regression"},
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()


def test_build450_payload_bound_review_request_cannot_target_qualification_case(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
    result = ctx.build450.qualify_investigation_workflow_450(
        identity=admin,
        case_id=case["case_id"],
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    revision_id = result["report"]["workflow_selftest"]["revision_id"]
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            "/api/build449/reviews",
            headers={"sec-fetch-site": "same-origin"},
            json={
                "object_type": "dossier_export",
                "object_id": revision_id,
                "note": "payload isolation regression",
                "assigned_to": "",
            },
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()



def test_build450_schema_driven_isolation_blocks_inherited_case_bound_primary_key_resources(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, _reviewer_session = setup_qualification_case(ctx)
    ctx.db.conn.executescript(
        """CREATE TABLE IF NOT EXISTS qualification_asset_regression_450(
        asset_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        payload TEXT NOT NULL
        );"""
    )
    asset_id = "media450_schema_bound_asset"
    ctx.db.execute(
        "INSERT INTO qualification_asset_regression_450(asset_id,case_id,payload) VALUES(?,?,?)",
        (asset_id, case["case_id"], "synthetic inherited-resource isolation regression"),
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.get(f"/api/images/{asset_id}")
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()




def test_build450_schema_derived_plan_id_is_blocked_in_body_only_inherited_route(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, _reviewer_session = setup_qualification_case(ctx)
    plan = ctx.build413.create_investigation_plan(
        case_id=case["case_id"],
        objective="Qualification case plan must stay isolated from inherited body-only routes.",
        subquestions=["Can a schema-derived plan_id bypass the Build-450 body guard?"],
        identity=admin,
    )
    before = int(
        (ctx.db.one(
            "SELECT COUNT(*) n FROM autonomous_wave_run_414 WHERE case_id=?",
            (case["case_id"],),
        ) or {}).get("n") or 0
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            "/api/build414/waves",
            headers={"sec-fetch-site": "same-origin"},
            json={
                "plan_id": plan["plan_id"],
                "max_waves": 2,
                "max_searches_per_wave": 2,
            },
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()
        after = int(
            (app.state.context.db.one(
                "SELECT COUNT(*) n FROM autonomous_wave_run_414 WHERE case_id=?",
                (case["case_id"],),
            ) or {}).get("n") or 0
        )
        assert after == before




def test_build450_schema_isolation_token_extraction_is_bounded_before_auth_amplification(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    try:
        payload = {
            "items": [
                {"plan_id": f"untrusted-plan-token-{idx}"}
                for idx in range(QUALIFICATION_IDENTIFIER_TOKEN_LIMIT + 1)
            ]
        }
        with TestClient(app) as client:
            response = client.post(
                "/api/build414/waves",
                headers={"sec-fetch-site": "same-origin"},
                json=payload,
            )
            assert response.status_code == 413
            assert "identifier token limit" in response.json()["detail"].lower()
    finally:
        app.state.context.close()


def test_build450_composite_case_key_is_not_treated_as_globally_unique_resource_id(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, reviewer, qualification_case, _admin_session, _reviewer_session = setup_qualification_case(ctx)
    normal_case = ctx.team_governance_359.create_case(
        identity=admin,
        title="Normal shared-resource case",
        client="QA",
        purpose="Ensure composite case-scoped shared IDs do not over-block normal resources.",
        legal_basis="public_data",
    )
    shared_id = "shared-composite-id-450"
    ctx.db.conn.executescript(
        """CREATE TABLE IF NOT EXISTS composite_scope_regression_450(
        case_id TEXT NOT NULL,
        shared_id TEXT NOT NULL,
        note TEXT NOT NULL,
        PRIMARY KEY(case_id, shared_id)
        );"""
    )
    ctx.db.execute(
        "INSERT INTO composite_scope_regression_450(case_id,shared_id,note) VALUES(?,?,?)",
        (qualification_case["case_id"], shared_id, "qualification association"),
    )
    ctx.db.execute(
        "INSERT INTO composite_scope_regression_450(case_id,shared_id,note) VALUES(?,?,?)",
        (normal_case["case_id"], shared_id, "normal association"),
    )
    # The schema-derived isolation layer must skip shared_id because it is only
    # one component of a composite PK. A nonexistent route therefore remains a
    # normal 404 instead of being falsely converted into a qualification 403.
    with TestClient(app) as client:
        response = client.get(f"/api/nonexistent-shared-resource/{shared_id}")
        assert response.status_code == 404



def test_build450_malformed_report_json_fails_closed_without_status_exception(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        ctx.db.execute(
            "UPDATE phase20_workflow_qualification_run_450 SET report_json=? WHERE qualification_id=?",
            ("not-valid-json", result["qualification_id"]),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["integrity_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False
        integrity = ctx.investigation_workflow_qualification_450.verify_integrity()
        reasons = {x["reason"] for x in integrity["violations"]}
        assert "report_json_invalid" in reasons


def test_build450_non_object_report_json_fails_closed_without_status_exception(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        ctx.db.execute(
            "UPDATE phase20_workflow_qualification_run_450 SET report_json=? WHERE qualification_id=?",
            ("null", result["qualification_id"]),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["integrity_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False
        integrity = ctx.investigation_workflow_qualification_450.verify_integrity()
        assert any(x["reason"] == "report_json_not_object" for x in integrity["violations"])


def test_build450_payload_isolation_does_not_trust_content_type(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
    result = ctx.build450.qualify_investigation_workflow_450(
        identity=admin,
        case_id=case["case_id"],
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    revision_id = result["report"]["workflow_selftest"]["revision_id"]
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    body = (
        '{"object_type":"dossier_export","object_id":"'
        + revision_id
        + '","note":"media type isolation regression","assigned_to":""}'
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            "/api/build449/reviews",
            headers={
                "sec-fetch-site": "same-origin",
                "content-type": "text/plain",
            },
            content=body,
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()



def test_build450_manual_request_json_route_cannot_mutate_qualification_case(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, _reviewer_session = setup_qualification_case(ctx)
    source = ctx.build421.register_source(
        identity=admin,
        name="Build 450 manual-json guard source",
        source_type="website",
        access_mode="public",
        base_url="https://manual-json-guard450.example.org/",
        capabilities=["public_pages"],
        coverage={"fixture_only": True},
    )
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    before = int(
        (ctx.db.one(
            "SELECT COUNT(*) n FROM crawl_task_425 WHERE case_id=?",
            (case["case_id"],),
        ) or {}).get("n") or 0
    )
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            "/api/build425/crawler/tasks",
            headers={"sec-fetch-site": "same-origin"},
            json={
                "case_id": case["case_id"],
                "source_id": source["source_id"],
                "target": "https://manual-json-guard450.example.org/item",
                "objective": "This must be blocked before the inherited manual JSON handler.",
                "scope": {"allowed_hosts": ["manual-json-guard450.example.org"]},
                "budget": {"max_pages": 1, "max_bytes": 100000},
            },
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()
        after = int(
            (ctx.db.one(
                "SELECT COUNT(*) n FROM crawl_task_425 WHERE case_id=?",
                (case["case_id"],),
            ) or {}).get("n") or 0
        )
        assert after == before


def test_build450_utf16_json_payload_cannot_bypass_qualification_isolation(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    ctx = app.state.context
    admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
    result = ctx.build450.qualify_investigation_workflow_450(
        identity=admin,
        case_id=case["case_id"],
        reviewer_session_token=reviewer_session.token,
        reviewer_client_fingerprint=FP_REVIEWER,
    )
    revision_id = result["report"]["workflow_selftest"]["revision_id"]
    fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    issued = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fp,
    )
    body = json.dumps(
        {
            "object_type": "dossier_export",
            "object_id": revision_id,
            "note": "utf16 qualification isolation regression",
            "assigned_to": "",
        }
    ).encode("utf-16")
    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", issued.token)
        response = client.post(
            "/api/build449/reviews",
            headers={
                "sec-fetch-site": "same-origin",
                "content-type": "application/json",
            },
            content=body,
        )
        assert response.status_code == 403
        assert "isolated" in response.json()["detail"].lower()


def test_build450_json_guard_is_bounded_but_does_not_classify_multipart_routes(tmp_path):
    app = create_workspace_app450(base_dir=tmp_path)
    try:
        multipart_routes = []
        for route in app.router.routes:
            body_field = getattr(route, "body_field", None)
            field_info = getattr(body_field, "field_info", None) if body_field is not None else None
            media_type = str(getattr(field_info, "media_type", "") or "").split(";", 1)[0].strip().lower()
            if media_type in {"multipart/form-data", "application/x-www-form-urlencoded"}:
                multipart_routes.append(route)
        assert multipart_routes, "expected at least one inherited form/multipart route"
        assert all(not _route_body_requires_payload_guard(route) for route in multipart_routes)

        # Guarded JSON routes are intentionally bounded; large binary/form
        # uploads are not passed through this JSON buffer.
        fp = hashlib.sha256("testclient||testclient".encode()).hexdigest()
        bootstrap = app.state.context.team_identity_359.create_initial_admin(
            username="guard450",
            display_name="Guard Regression Admin",
            password="Build450GuardPassword!2026",
        )
        issued = app.state.context.team_identity_359.authenticate(
            username=bootstrap["username"],
            password="Build450GuardPassword!2026",
            client_fingerprint=fp,
        )
        with TestClient(app) as client:
            client.cookies.set("ee_auth_session", issued.token)
            response = client.post(
                "/api/build449/reviews",
                headers={"sec-fetch-site": "same-origin", "content-type": "application/json"},
                content=b"{" + b'"note":"' + (b"x" * JSON_PAYLOAD_GUARD_MAX_BYTES) + b'"}',
            )
            assert response.status_code == 413
            assert "guard limit" in response.json()["detail"].lower()
    finally:
        app.state.context.close()


def test_build450_nested_workflow_report_shape_fails_closed_without_status_500(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, _reviewer, case, _admin_session, reviewer_session = setup_qualification_case(ctx)
        result = ctx.build450.qualify_investigation_workflow_450(
            identity=admin,
            case_id=case["case_id"],
            reviewer_session_token=reviewer_session.token,
            reviewer_client_fingerprint=FP_REVIEWER,
        )
        report = dict(result["report"])
        report["workflow_selftest"] = [1]
        ctx.db.execute(
            "UPDATE phase20_workflow_qualification_run_450 SET report_json=? WHERE qualification_id=?",
            (json.dumps(report), result["qualification_id"]),
        )
        status = ctx.build450.investigation_workflow_status_450()
        assert status["integrity_valid"] is False
        assert status["qualified_artifacts_valid"] is False
        assert status["qualified_workflow_rows_valid"] is False
        assert status["investigation_workflow_checkpoint_pass"] is False
        integrity = ctx.investigation_workflow_qualification_450.verify_integrity()
        assert any(
            x["reason"] == "workflow_selftest_report_not_object"
            for x in integrity["violations"]
        )

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
    assert "app452 import create_workspace_app452" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert "INSTALL_EAGLEEYE_452.py" in (ROOT / "START_EAGLEEYE_PRO.sh").read_text()
    assert (ROOT / "README_BUILD_450_0.md").exists()
    assert (ROOT / "BUILD_450_CASE_TEST.md").exists()
    assert (ROOT / "RELEASE_MANIFEST_BUILD_450_0.json").exists()
