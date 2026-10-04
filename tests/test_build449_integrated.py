from pathlib import Path
import hashlib
import runpy

import pytest
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app448 import render_workspace
from eagleeye.interfaces.web.app449 import create_workspace_app449

ROOT = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD = "Build449AdminPassword!2026"
REVIEWER_PASSWORD = "Build449ReviewerPassword!2026"


def setup_team(ctx, title="Build 449 Human Review"):
    admin = ctx.team_identity_359.create_initial_admin(
        username="admin449",
        display_name="Build 449 Administrator",
        password=ADMIN_PASSWORD,
    )
    reviewer = ctx.team_governance_359.create_user(
        identity=admin,
        username="reviewer449",
        display_name="Independent Reviewer",
        global_role="reviewer",
        password=REVIEWER_PASSWORD,
    )
    case = ctx.team_governance_359.create_case(
        identity=admin,
        title=title,
        client="QA",
        purpose="Build 449 four-eyes team workflow qualification",
        legal_basis="public_data",
    )
    ctx.team_governance_359.assign_case_role(
        identity=admin,
        case_id=case["case_id"],
        username=reviewer["username"],
        case_role="reviewer",
        notes="Independent Build 449 reviewer",
    )
    return admin, reviewer, case


def seed_unreviewed_evidence(ctx, admin, case_id):
    live = ctx.live_investigation_dispatcher_446.run_case_selftest(
        identity=admin,
        case_id=case_id,
    )
    assert live["result"] == "PASS"
    sync = ctx.evidence_claims_dossier_447.sync_case_evidence(
        identity=admin,
        case_id=case_id,
    )
    assert len(sync["evidence_ids"]) >= 1
    rows = ctx.evidence_claims_dossier_447.case_evidence(case_id)
    assert rows
    return rows


def complete_review(ctx, reviewer, request, decision, note):
    claimed = ctx.build449.claim_review_449(
        identity=reviewer,
        review_id=request["review_id"],
    )
    assert claimed["state"] == "claimed"
    confirmation = {
        "evidence": "REVIEW EVIDENCE 447",
        "claim": "REVIEW CLAIM 447",
        "dossier": "APPROVE DOSSIER 447",
        "dossier_export": "APPROVE DOSSIER EXPORT 449",
    }[request["object_type"]]
    return ctx.build449.complete_review_449(
        identity=reviewer,
        review_id=request["review_id"],
        decision=decision,
        note=note,
        confirmation=confirmation,
    )


def test_four_eyes_chain_evidence_claim_dossier_and_export(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        cid = case["case_id"]
        evidence = seed_unreviewed_evidence(ctx, admin, cid)[0]

        evidence_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Independent source and provenance review is required.",
            assigned_to=reviewer["username"],
        )
        evidence_done = complete_review(
            ctx,
            reviewer,
            evidence_request,
            "accepted",
            "Provenance is intact and the synthetic item is acceptable for qualification.",
        )
        assert evidence_done["review"]["state"] == "completed"
        assert evidence_done["object"]["reviewed_by"] == reviewer["username"]

        claim = ctx.evidence_claims_dossier_447.propose_claim(
            identity=admin,
            case_id=cid,
            statement="Build 449 qualification claim supported by independently reviewed evidence.",
            support_evidence_ids=[evidence["evidence_id"]],
            uncertainty_note="Qualification-only synthetic claim; no real-world truth assertion.",
        )
        claim_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="claim",
            object_id=claim["claim_id"],
            note="Independent claim review before dossier inclusion.",
            assigned_to=reviewer["username"],
        )
        claim_done = complete_review(
            ctx,
            reviewer,
            claim_request,
            "accepted_for_dossier",
            "The claim is bounded by its reviewed evidence and suitable for the test dossier.",
        )
        assert claim_done["object"]["state"] == "accepted_for_dossier"
        assert claim_done["object"]["reviewed_by"] == reviewer["username"]

        dossier = ctx.evidence_claims_dossier_447.build_dossier(
            identity=admin,
            case_id=cid,
            title="Build 449 Four-Eyes Dossier",
        )
        dossier_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier",
            object_id=dossier["revision_id"],
            note="Independent dossier review is required before export approval.",
            assigned_to=reviewer["username"],
        )
        dossier_done = complete_review(
            ctx,
            reviewer,
            dossier_request,
            "approved_for_export",
            "Claims, evidence references and uncertainty boundaries are preserved.",
        )
        assert dossier_done["object"]["state"] == "approved_for_export"

        export_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier_export",
            object_id=dossier["revision_id"],
            note="Request independent four-eyes release approval for dossier export.",
            assigned_to=reviewer["username"],
        )
        export_approval = complete_review(
            ctx,
            reviewer,
            export_request,
            "approve",
            "Export may proceed; reviewer is independent from requester and dossier creator.",
        )
        assert export_approval["review"]["state"] == "completed"
        assert export_approval["review"]["decision"] == "approve"

        exported = ctx.build449.execute_approved_export_449(
            identity=admin,
            review_id=export_request["review_id"],
            confirmation="EXPORT DOSSIER 447",
        )
        assert exported["execution"]["executed_by"] == admin["username"]
        assert exported["review"]["completed_by"] == reviewer["username"]
        assert exported["execution"]["package_hash"] == exported["export"]["package_hash"]
        assert Path(exported["export"]["paths"]["docx"]).exists()
        assert Path(exported["export"]["paths"]["pdf"]).exists()
        assert ctx.human_review_449.verify_integrity()["valid"]



def test_export_approval_is_reserved_before_artifact_generation(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx, "Atomic export reservation 449")
        cid = case["case_id"]
        evidence = seed_unreviewed_evidence(ctx, admin, cid)[0]
        evidence_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Independent Evidence review before atomic export regression.",
            assigned_to=reviewer["username"],
        )
        complete_review(
            ctx, reviewer, evidence_request, "accepted",
            "Evidence accepted for atomic export reservation regression."
        )
        claim = ctx.evidence_claims_dossier_447.propose_claim(
            identity=admin,
            case_id=cid,
            statement="Atomic export reservation regression claim.",
            support_evidence_ids=[evidence["evidence_id"]],
        )
        claim_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="claim",
            object_id=claim["claim_id"],
            note="Independent Claim review before atomic export regression.",
            assigned_to=reviewer["username"],
        )
        complete_review(
            ctx, reviewer, claim_request, "accepted_for_dossier",
            "Claim accepted for atomic export reservation regression."
        )
        dossier = ctx.evidence_claims_dossier_447.build_dossier(
            identity=admin, case_id=cid, title="Atomic Export Reservation Dossier"
        )
        dossier_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier",
            object_id=dossier["revision_id"],
            note="Independent dossier review before atomic export regression.",
            assigned_to=reviewer["username"],
        )
        complete_review(
            ctx, reviewer, dossier_request, "approved_for_export",
            "Dossier approved for atomic export reservation regression."
        )
        export_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="dossier_export",
            object_id=dossier["revision_id"],
            note="Independent export approval before atomic reservation regression.",
            assigned_to=reviewer["username"],
        )
        complete_review(
            ctx, reviewer, export_request, "approve",
            "Export approved for atomic reservation regression."
        )

        original = ctx.evidence_claims_dossier_447.export_dossier
        competing_checked = {"done": False}

        def guarded_export(**kwargs):
            if not competing_checked["done"]:
                competing_checked["done"] = True
                with pytest.raises(ValueError, match="reserved or executed"):
                    ctx.build449.execute_approved_export_449(
                        identity=admin,
                        review_id=export_request["review_id"],
                        confirmation="EXPORT DOSSIER 447",
                    )
            return original(**kwargs)

        ctx.evidence_claims_dossier_447.export_dossier = guarded_export
        result = ctx.build449.execute_approved_export_449(
            identity=admin,
            review_id=export_request["review_id"],
            confirmation="EXPORT DOSSIER 447",
        )
        assert competing_checked["done"] is True
        assert result["execution"]["export_id"] != "RESERVED"
        assert result["execution"]["package_hash"] != "RESERVED"
        assert len(ctx.evidence_claims_dossier_447.exports(cid)) == 1
        assert len(
            ctx.db.all(
                "SELECT * FROM review_export_execution_449 WHERE review_id=?",
                (export_request["review_id"],),
            )
        ) == 1


def test_requester_cannot_review_own_work_and_reviewer_assignment_is_enforced(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
        request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="This item requires an independent human review.",
            assigned_to=reviewer["username"],
        )
        with pytest.raises(PermissionError, match="different user"):
            ctx.build449.claim_review_449(
                identity=admin,
                review_id=request["review_id"],
            )
        claimed = ctx.build449.claim_review_449(
            identity=reviewer,
            review_id=request["review_id"],
        )
        assert claimed["claimed_by"] == reviewer["username"]
        assert claimed["assigned_to"] == reviewer["username"]


def test_object_creator_cannot_be_assigned_as_reviewer(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        coordinator = ctx.team_governance_359.create_user(
            identity=admin,
            username="coordinator449",
            display_name="Review Coordinator",
            global_role="investigator",
            password="Build449CoordinatorPassword!2026",
        )
        ctx.team_governance_359.assign_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=coordinator["username"],
            case_role="report_author",
            notes="Authorized independent review requester",
        )
        evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
        ev_request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Independent Evidence review before claim creation.",
            assigned_to=reviewer["username"],
        )
        complete_review(
            ctx,
            reviewer,
            ev_request,
            "accepted",
            "Evidence is acceptable for the creator-separation regression.",
        )
        claim = ctx.evidence_claims_dossier_447.propose_claim(
            identity=admin,
            case_id=case["case_id"],
            statement="Creator-separation regression claim.",
            support_evidence_ids=[evidence["evidence_id"]],
        )
        with pytest.raises(PermissionError, match="object creator"):
            ctx.build449.request_review_449(
                identity=coordinator,
                object_type="claim",
                object_id=claim["claim_id"],
                note="Attempt to assign review back to the claim creator.",
                assigned_to=admin["username"],
            )


def test_review_request_becomes_stale_when_object_changes(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
        request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Pending review that will be invalidated by an object change.",
            assigned_to=reviewer["username"],
        )

        # Simulate a legitimate lower-level compatibility review arriving before
        # the queued Build-449 task is claimed.
        ctx.evidence_claims_dossier_447.review_evidence(
            identity=reviewer,
            evidence_id=evidence["evidence_id"],
            decision="accepted",
            note="Compatibility-layer review changes the object hash.",
            confirmation="REVIEW EVIDENCE 447",
        )
        with pytest.raises(PermissionError, match="stale"):
            ctx.build449.claim_review_449(
                identity=reviewer,
                review_id=request["review_id"],
            )
        assert ctx.human_review_449.review(request["review_id"])["state"] == "stale"


def test_comments_challenges_and_counter_hypotheses_are_auditable(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
        request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Collaborative review discussion qualification.",
            assigned_to=reviewer["username"],
        )
        c1 = ctx.build449.add_review_comment_449(
            identity=admin,
            review_id=request["review_id"],
            kind="challenge",
            body="Check whether the timestamp reflects publication time or collection time.",
        )
        c2 = ctx.build449.add_review_comment_449(
            identity=reviewer,
            review_id=request["review_id"],
            kind="counter_hypothesis",
            body="The apparent discrepancy may be caused by collection latency rather than source conflict.",
        )
        rows = ctx.human_review_449.comments(request["review_id"])
        assert [x["comment_id"] for x in rows] == [c1["comment_id"], c2["comment_id"]]
        assert {x["kind"] for x in rows} == {"challenge", "counter_hypothesis"}
        assert ctx.human_review_449.verify_integrity()["valid"]


def test_build449_snapshot_and_ui_surface_review_queue_without_direct_review_buttons(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        admin, reviewer, case = setup_team(ctx)
        evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
        request = ctx.build449.request_review_449(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="UI review queue qualification.",
            assigned_to=reviewer["username"],
        )
        snap = ctx.build449.team_review_snapshot_449(
            identity=admin,
            case_id=case["case_id"],
        )
        assert snap["build"] == "449.0"
        assert snap["team_review449"]["four_eyes_required"] is True
        assert snap["team_review449"]["metrics"]["pending"] == 1
        assert request["review_id"] in {x["review_id"] for x in snap["team_review449"]["queue"]}

        evidence_html = render_workspace(
            snap,
            view="evidence",
            cases=[snap["case"]],
            audits=[],
        )
        assert "Build 449 · Human Review & Team Workflow" in evidence_html
        assert "/api/build449/reviews" in evidence_html
        assert f"/api/build447/evidence/{evidence['evidence_id']}/review" not in evidence_html

        operations_html = render_workspace(
            snap,
            view="operations",
            cases=[snap["case"]],
            audits=[],
        )
        assert "Team Review · Build 449" in operations_html
        assert reviewer["username"] in operations_html
        assert request["review_id"] in operations_html


def test_current_app_removes_direct_build447_review_mutations_and_registers_449_routes(tmp_path):
    app = create_workspace_app449(base_dir=tmp_path)
    try:
        paths = {
            (method, getattr(route, "path", ""))
            for route in app.router.routes
            for method in (getattr(route, "methods", set()) or set())
        }
        assert ("POST", "/api/build447/evidence/{evidence_id}/review") not in paths
        assert ("POST", "/api/build447/claims/{claim_id}/review") not in paths
        assert ("POST", "/api/build447/dossiers/{revision_id}/review") not in paths
        assert ("POST", "/api/build447/dossiers/{revision_id}/export") not in paths
        assert ("POST", "/api/build447/cases/{case_id}/selftest") not in paths
        for path in (
            "/api/build449/reviews",
            "/api/build449/reviews/{review_id}/claim",
            "/api/build449/reviews/{review_id}/complete",
            "/api/build449/reviews/{review_id}/comments",
            "/api/build449/reviews/{review_id}/export",
        ):
            assert ("POST", path) in paths
    finally:
        app.state.context.close()


def test_http_workspace_uses_build449_snapshot_and_review_queue(tmp_path):
    app = create_workspace_app449(base_dir=tmp_path)
    ctx = app.state.context
    admin, reviewer, case = setup_team(ctx, "HTTP Build 449")
    evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
    ctx.build449.request_review_449(
        identity=admin,
        object_type="evidence",
        object_id=evidence["evidence_id"],
        note="HTTP current workspace review qualification.",
        assigned_to=reviewer["username"],
    )
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
        assert "Build 449" in root.text
        assert "Team Review · Build 449" in root.text
        status = client.get("/api/build449/status")
        assert status.status_code == 200
        assert status.json()["dossier_export_four_eyes"] is True


def test_current_ui_audit_checks_449_routes_and_bypass_absence(tmp_path):
    app = create_workspace_app449(base_dir=tmp_path)
    ctx = app.state.context
    admin, reviewer, case = setup_team(ctx, "UI audit Build 449")
    evidence = seed_unreviewed_evidence(ctx, admin, case["case_id"])[0]
    ctx.build449.request_review_449(
        identity=admin,
        object_type="evidence",
        object_id=evidence["evidence_id"],
        note="UI audit needs a visible team-review task.",
        assigned_to=reviewer["username"],
    )
    fingerprint = hashlib.sha256("testclient||testclient".encode()).hexdigest()
    session = ctx.team_identity_359.authenticate(
        username=admin["username"],
        password=ADMIN_PASSWORD,
        client_fingerprint=fingerprint,
    )
    assert session is not None

    with TestClient(app) as client:
        client.cookies.set("ee_auth_session", session.token)
        response = client.post(
            f"/api/build449/cases/{case['case_id']}/ui-audit",
            headers={"sec-fetch-site": "same-origin"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["result"] == "PASS"
        assert result["checks"]["required_build449_routes"] is True
        assert result["checks"]["direct_build447_review_bypass_absent"] is True
        assert result["bypass_routes"] == []
        history = client.get(f"/api/build449/cases/{case['case_id']}/ui-audits")
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1


def test_status_launcher_and_checkpoint_contract(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as ctx:
        setup_team(ctx)
        status = ctx.build449.human_review_status_449()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 9
        assert status["case_scoped_review_queue"]
        assert status["reviewer_assignment"]
        assert status["creator_reviewer_separation"]
        assert status["requester_reviewer_separation"]
        assert status["stale_object_detection"]
        assert status["comments_challenges_agreement_counter_hypothesis"]
        assert status["dossier_export_four_eyes"]
        assert status["current_ui_route_contract_audited"]
        assert status["direct_build447_review_bypass_forbidden"]
        assert status["automatic_truth_determination"] is False
        assert status["production_release_ready"] is False
        assert status["next_build"] == "450.0"
        assert status["next_hard_checkpoint"] == "450.0"

    import eagleeye.interfaces.web.app449 as appmod
    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app449",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_450_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app450 import create_workspace_app450" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert "EAGLEEYE_PRO_450_0.py" in (ROOT / "START_EAGLEEYE_PRO.sh").read_text()
    assert (ROOT / "README_BUILD_449_0.md").exists()
    assert (ROOT / "BUILD_449_CASE_TEST.md").exists()
