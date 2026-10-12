from __future__ import annotations

from pathlib import Path
import hashlib
import json
import secrets

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase20.news_acquisition443 import LiveNewsAcquisition443
from eagleeye.interfaces.web.app456 import create_workspace_app456
from eagleeye.interfaces.web.app448 import COOKIE

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Build456!Admin_7781"
FP = "build456-admin-fingerprint"


def setup_case(ctx):
    bootstrap = ctx.team_identity_359.create_initial_admin(
        username="admin456",
        display_name="Build 456 Admin",
        password=PASSWORD,
    )
    issued = ctx.team_identity_359.authenticate(
        username="admin456", password=PASSWORD, client_fingerprint=FP
    )
    assert issued is not None
    identity = ctx.team_identity_359.validate_session(
        issued.token, client_fingerprint=FP, touch=False
    )
    assert identity is not None
    case = ctx.team_governance_359.create_case(
        identity=identity,
        title="Build 456 multilingual lineage fixture",
        client="Internal QA",
        purpose="Validate multilingual entity candidates and source lineage.",
        legal_basis="public_data",
    )
    return identity, case


def insert_evidence(ctx, *, case_id, title, url, publisher, content_sha, publication_text):
    evidence_id = "ev456_" + secrets.token_hex(6)
    now = "2026-10-12T09:00:00+00:00"
    row = {
        "evidence_id": evidence_id,
        "case_id": case_id,
        "observation_id": "obs456_" + secrets.token_hex(6),
        "event_id": "event456_" + secrets.token_hex(6),
        "content_id": "content456_" + secrets.token_hex(6),
        "source_id": "src456_" + secrets.token_hex(4),
        "evidence_kind": "news",
        "title": title,
        "canonical_url": url,
        "observed_at": now,
        "content_sha256": content_sha,
        "media_type": "text/html",
        "duplicate_kind": "",
        "source_snapshot_json": json.dumps({"access_mode": "public"}),
        "provenance_json": json.dumps({"public_only": True}),
        "usage_json": json.dumps({}),
        "descriptive_json": json.dumps({
            "publisher": publisher,
            "metadata": {
                "publication_text_fingerprint_sha256": hashlib.sha256(
                    " ".join(publication_text.casefold().split()).encode("utf-8")
                ).hexdigest(),
                "publication_text_fingerprint_basis": "feed_summary",
            },
        }),
        "source_record_hash": "s" * 64,
        "event_record_hash": "e" * 64,
        "content_record_hash": "c" * 64,
        "observation_record_hash": "o" * 64,
        "review_state": "accepted",
        "review_note": "Build 456 fixture accepted for lineage analysis.",
        "reviewed_by": "admin456",
        "reviewed_at": now,
        "created_at": now,
        "updated_at": now,
    }
    row["record_hash"] = ctx.evidence_claims_dossier_447._rh(row)
    ctx.db.execute(
        "INSERT INTO evidence_item_447 VALUES(" + ",".join("?" for _ in row) + ")",
        tuple(row.values()),
    )
    return evidence_id


def insert_claim(ctx, *, case_id, evidence_ids):
    claim_id = "claim456_" + secrets.token_hex(6)
    now = "2026-10-12T09:05:00+00:00"
    row = {
        "claim_id": claim_id,
        "case_id": case_id,
        "statement": "The reviewed public sources describe the same bounded proposition.",
        "state": "accepted_for_dossier",
        "uncertainty_note": "Source independence is assessed separately from truth.",
        "created_by": "admin456",
        "created_at": now,
        "reviewed_by": "admin456",
        "reviewed_at": now,
        "review_note": "Fixture claim for source-lineage regression.",
        "updated_at": now,
    }
    row["record_hash"] = ctx.evidence_claims_dossier_447._rh(row)
    ctx.db.execute(
        "INSERT INTO claim_447 VALUES(" + ",".join("?" for _ in row) + ")",
        tuple(row.values()),
    )
    for evidence_id in evidence_ids:
        evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)
        link = {
            "link_id": "link456_" + secrets.token_hex(6),
            "claim_id": claim_id,
            "case_id": case_id,
            "evidence_id": evidence_id,
            "stance": "support",
            "note": "",
            "evidence_hash_at_link": evidence["record_hash"],
            "created_by": "admin456",
            "created_at": now,
        }
        link["record_hash"] = ctx.evidence_claims_dossier_447._rh(link)
        ctx.db.execute(
            "INSERT INTO claim_evidence_link_447 VALUES(" + ",".join("?" for _ in link) + ")",
            tuple(link.values()),
        )
    return claim_id


def test_build456_status_health_and_focused_cadence(tmp_path):
    app = create_workspace_app456(base_dir=tmp_path)
    try:
        status = app.state.context.build456.build456_status()
        assert status["build"] == "456.0"
        assert status["full_research_gate_this_build"] is False
        assert status["next_checkpoint"] == "460.0"
        assert status["automatic_entity_merge"] is False
        assert status["automatic_truth_determination"] is False
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"ok": True, "status": "ok", "build": "456.0"}
    finally:
        app.state.context.close()

    assert 'version = "456.0.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'BUILD = "456.0"' in (ROOT / "eagleeye_pro/version.py").read_text(encoding="utf-8")
    assert "app456 import create_workspace_app456" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text(encoding="utf-8")
    assert (ROOT / "INSTALL_EAGLEEYE_456.py").exists()
    assert (ROOT / "EAGLEEYE_PRO_456_0.py").exists()


def test_build456_cross_script_profiles_are_review_candidates_not_identity_proof(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        service = ctx.entity_lineage_456
        he = service.preview_name("בנימין נתניהו")
        ar = service.preview_name("محمد")
        cy = service.preview_name("Зеленський")
        assert "Hebrew" in he["scripts"]
        assert "Arabic" in ar["scripts"]
        assert "Cyrillic" in cy["scripts"]
        assert he["latin_transliteration"]
        assert ar["latin_transliteration"]
        assert cy["latin_transliteration"]
        assert service._name_pair("محمد", "Mohammed")["score"] >= 0.70
        assert service._name_pair("Зеленський", "Zelenskyy")["score"] >= 0.70


def test_build456_entity_scan_generates_candidates_without_auto_merge(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        left = ctx.entity_resolution_115.register_entity(
            case_id, "person", "محمد", "admin456", source_entity_id="build456:arabic"
        )
        right = ctx.entity_resolution_115.register_entity(
            case_id, "person", "Mohammed", "admin456", source_entity_id="build456:latin"
        )
        result = ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        assert result["entities_considered"] == 2
        assert result["alias_candidates_total"] >= 1
        assert result["pair_candidates_total"] >= 1
        assert result["automatic_merge"] is False
        links = ctx.db.one(
            "SELECT COUNT(*) AS n FROM resolution_links_115 WHERE case_id=? AND active=1",
            (case_id,),
        )
        assert int(links["n"]) == 0
        pairs = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )
        assert {pairs[0]["left_entity_id"], pairs[0]["right_entity_id"]} == {left, right}


def test_build456_source_lineage_counts_reviewed_origins_not_republication_envelopes(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        syndicated_text = "The same normalized wire text appears in two different publisher envelopes."
        ev1 = insert_evidence(
            ctx, case_id=case_id, title="Wire copy A",
            url="https://example-one.invalid/story", publisher="Reuters",
            content_sha="a" * 64, publication_text=syndicated_text,
        )
        ev2 = insert_evidence(
            ctx, case_id=case_id, title="Wire copy B",
            url="https://example-two.invalid/republication", publisher="Local Outlet",
            content_sha="b" * 64, publication_text=syndicated_text,
        )
        ev3 = insert_evidence(
            ctx, case_id=case_id, title="Independent report",
            url="https://example-three.invalid/report", publisher="Associated Press",
            content_sha="c" * 64,
            publication_text="A genuinely different publication text for the bounded test.",
        )
        claim_id = insert_claim(ctx, case_id=case_id, evidence_ids=[ev1, ev2, ev3])

        inferred = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        support = inferred["summary"]["support"]
        assert support["mentions"] == 3
        assert support["unique_publication_payloads"] == 2
        assert support["source_families"] == 3
        assert support["inferred_origin_candidates"] == 3
        assert support["reviewed_independent_origins"] == 0
        assert "unreviewed_lineage_excluded_from_independent_origin_count" in inferred["warnings"]
        assert "duplicate_publication_payloads_collapsed" in inferred["warnings"]

        for evidence_id, family, group in (
            (ev1, "publisher:reuters", "origin:wire-reuters"),
            (ev2, "publisher:local-outlet", "origin:wire-reuters"),
            (ev3, "publisher:associated-press", "origin:associated-press"),
        ):
            evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)
            ctx.build456.review_source_lineage_456(
                identity=identity,
                evidence_id=evidence_id,
                source_family=family,
                independence_group=group,
                origin_key=group.removeprefix("origin:"),
                source_role="publisher",
                countable=True,
                rationale="Human-reviewed source-lineage decision for the Build 456 regression.",
                confirmation="REVIEW SOURCE LINEAGE 456",
                expected_evidence_hash=evidence["record_hash"],
            )

        reviewed = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        assert reviewed["summary"]["support"]["mentions"] == 3
        assert reviewed["summary"]["support"]["unique_publication_payloads"] == 2
        assert reviewed["summary"]["support"]["reviewed_independent_origins"] == 2
        assert reviewed["source_independence_determines_truth"] is False

        ap = ctx.evidence_claims_dossier_447.evidence(ev3)
        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=ev3,
            source_family="publisher:associated-press",
            independence_group="origin:associated-press",
            origin_key="associated-press",
            source_role="publisher",
            countable=False,
            rationale="Analyst now marks this source non-countable for the bounded scenario.",
            confirmation="REVIEW SOURCE LINEAGE 456",
            expected_evidence_hash=ap["record_hash"],
        )
        reduced = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        assert reduced["summary"]["support"]["reviewed_independent_origins"] == 1


def test_build456_lineage_review_is_bound_to_visible_evidence_hash_and_boolean(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        evidence_id = insert_evidence(
            ctx,
            case_id=case["case_id"],
            title="Evidence version binding",
            url="https://binding.invalid/item",
            publisher="Binding Publisher",
            content_sha="d" * 64,
            publication_text="Stable publication text for expected Evidence hash validation.",
        )
        evidence = ctx.evidence_claims_dossier_447.evidence(evidence_id)

        try:
            ctx.build456.review_source_lineage_456(
                identity=identity,
                evidence_id=evidence_id,
                source_family="publisher:binding",
                independence_group="origin:binding",
                origin_key="binding",
                source_role="publisher",
                countable="false",
                rationale="String booleans must never become reviewer decisions.",
                confirmation="REVIEW SOURCE LINEAGE 456",
                expected_evidence_hash=evidence["record_hash"],
            )
            assert False, "non-boolean countable must fail"
        except ValueError:
            pass

        try:
            ctx.build456.review_source_lineage_456(
                identity=identity,
                evidence_id=evidence_id,
                source_family="publisher:binding",
                independence_group="origin:binding",
                origin_key="binding",
                source_role="publisher",
                countable=False,
                rationale="Stale UI state must never create a current lineage override.",
                confirmation="REVIEW SOURCE LINEAGE 456",
                expected_evidence_hash="0" * 64,
            )
            assert False, "stale expected Evidence hash must fail"
        except PermissionError:
            pass

def test_build456_integrity_and_no_automatic_authority(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        assert ctx.entity_lineage_456.verify_integrity()["valid"] is True
        status = ctx.entity_lineage_456.status()
        assert status["automatic_identity_confirmation"] is False
        assert status["automatic_entity_merge"] is False
        assert status["automatic_truth_determination"] is False


def test_build456_news_publication_fingerprint_uses_substantive_text_not_title():
    service = object.__new__(LiveNewsAcquisition443)
    left = {
        "title": "Outlet-specific headline",
        "summary": "The same substantive wire summary is republished by two outlets.",
    }
    right = {
        "title": "Completely different headline",
        "summary": "The same substantive wire summary is republished by two outlets.",
    }
    assert service._publication_text_fingerprint(left)
    assert service._publication_text_fingerprint(left) == service._publication_text_fingerprint(right)
    assert service._publication_text_fingerprint(
        {"title": "Live updates", "summary": ""}
    ) == ""
    assert service._publication_text_fingerprint(
        {"title": "Different article", "summary": "Read more"}
    ) == ""
    assert service._publication_text_fingerprint(
        {"title": "Different article", "summary": "Click here to continue reading."}
    ) == ""


def test_build456_reviewed_pair_inputs_are_immutable_after_terminal_decision(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        left = ctx.entity_resolution_115.register_entity(
            case_id, "person", "محمد", "admin456", source_entity_id="build456:pair-left"
        )
        right = ctx.entity_resolution_115.register_entity(
            case_id, "person", "Mohammed", "admin456", source_entity_id="build456:pair-right"
        )
        ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        pair = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )[0]
        before = dict(
            ctx.db.one(
                "SELECT * FROM phase20_entity_pair_candidate_456 WHERE pair_id=?",
                (pair["pair_id"],),
            )
        )
        reviewed = ctx.build456.review_multilingual_pair_456(
            identity=identity,
            pair_id=pair["pair_id"],
            decision="likely_distinct",
            rationale="Keep these records distinct until stronger identity evidence exists.",
            confirmation="REVIEW ENTITY PAIR 456",
            expected_pair_hash=pair["record_hash"],
        )
        assert reviewed["state"] == "analyst_marked_distinct"

        ctx.entity_resolution_115.add_alias(
            right, "محمد", "manual", "admin456", "build456:post-review-alias"
        )
        ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        after = dict(
            ctx.db.one(
                "SELECT * FROM phase20_entity_pair_candidate_456 WHERE pair_id=?",
                (pair["pair_id"],),
            )
        )
        assert after["state"] == "analyst_marked_distinct"
        assert after["similarity_score"] == reviewed["similarity_score"]
        assert after["signals_json"] == reviewed["signals_json"]
        assert after["reviewed_by"] == reviewed["reviewed_by"]
        assert before["pair_id"] == after["pair_id"]


def test_build456_stale_or_rejected_claim_evidence_never_counts_as_independent(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        evidence_id = insert_evidence(
            ctx,
            case_id=case["case_id"],
            title="Accepted then changed",
            url="https://stale.invalid/item",
            publisher="Reviewed Publisher",
            content_sha="e" * 64,
            publication_text="Substantive publication text used for a reviewed lineage record.",
        )
        claim_id = insert_claim(ctx, case_id=case["case_id"], evidence_ids=[evidence_id])
        original = ctx.evidence_claims_dossier_447.evidence(evidence_id)
        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=evidence_id,
            source_family="publisher:reviewed",
            independence_group="origin:reviewed",
            origin_key="reviewed",
            source_role="publisher",
            countable=True,
            rationale="Initial lineage review while the Claim link is current.",
            confirmation="REVIEW SOURCE LINEAGE 456",
            expected_evidence_hash=original["record_hash"],
        )
        assert (
            ctx.build456.claim_source_lineage_456(
                identity=identity, claim_id=claim_id
            )["summary"]["support"]["reviewed_independent_origins"]
            == 1
        )

        raw = dict(
            ctx.db.one(
                "SELECT * FROM evidence_item_447 WHERE evidence_id=?", (evidence_id,)
            )
        )
        raw["review_state"] = "rejected"
        raw["review_note"] = "Rejected after the Claim linked the prior Evidence version."
        raw["reviewed_at"] = "2026-10-12T10:00:00+00:00"
        raw["updated_at"] = raw["reviewed_at"]
        raw["record_hash"] = ctx.evidence_claims_dossier_447._rh(raw)
        ctx.db.execute(
            "UPDATE evidence_item_447 SET review_state=?,review_note=?,reviewed_at=?,"
            "updated_at=?,record_hash=? WHERE evidence_id=?",
            (
                raw["review_state"], raw["review_note"], raw["reviewed_at"],
                raw["updated_at"], raw["record_hash"], evidence_id,
            ),
        )
        changed = ctx.evidence_claims_dossier_447.evidence(evidence_id)
        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=evidence_id,
            source_family="publisher:reviewed",
            independence_group="origin:reviewed",
            origin_key="reviewed",
            source_role="publisher",
            countable=True,
            rationale="Lineage itself is reviewed again, but Claim link is now stale.",
            confirmation="REVIEW SOURCE LINEAGE 456",
            expected_evidence_hash=changed["record_hash"],
        )
        report = ctx.build456.claim_source_lineage_456(
            identity=identity, claim_id=claim_id
        )
        assert report["summary"]["support"]["reviewed_independent_origins"] == 0
        assert "nonaccepted_evidence_excluded_from_independent_origin_count" in report["warnings"]
        assert "stale_claim_evidence_link_excluded_from_independent_origin_count" in report["warnings"]


def test_build456_mutation_api_audit_actor_is_authenticated_user(tmp_path):
    app = create_workspace_app456(base_dir=tmp_path)
    try:
        ctx = app.state.context
        ctx.team_identity_359.create_initial_admin(
            username="webadmin456",
            display_name="Build 456 Web Admin",
            password="Build456!WebAdmin_8821",
        )
        ua = "build456-web-audit-test"
        lang = "en"
        fingerprint = hashlib.sha256(f"{ua}|{lang}|testclient".encode()).hexdigest()
        issued = ctx.team_identity_359.authenticate(
            username="webadmin456",
            password="Build456!WebAdmin_8821",
            client_fingerprint=fingerprint,
        )
        identity = ctx.team_identity_359.validate_session(
            issued.token, client_fingerprint=fingerprint, touch=False
        )
        case = ctx.team_governance_359.create_case(
            identity=identity,
            title="Build 456 audit actor",
            client="Internal QA",
            purpose="Verify authenticated mutation audit attribution.",
            legal_basis="public_data",
        )
        with TestClient(
            app, headers={"user-agent": ua, "accept-language": lang}
        ) as client:
            client.cookies.set(COOKIE, issued.token)
            response = client.post(
                f"/api/build456/cases/{case['case_id']}/entity-scan",
                json={"min_pair_score": 0.72},
            )
            assert response.status_code == 200
            event = ctx.entity_lineage_456.db.one(
                "SELECT * FROM audit_events WHERE case_id=? AND action=? "
                "ORDER BY rowid DESC LIMIT 1",
                (case["case_id"], "multilingual_entity_scan_456"),
            )
            assert event is not None
            assert event["actor"] == "webadmin456"
    finally:
        app.state.context.close()


def test_build456_invalid_cross_stance_link_cannot_suppress_valid_origin(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        text_payload = "Shared publication text for cross-stance eligibility regression."
        support_id = insert_evidence(
            ctx, case_id=case_id, title="Valid support",
            url="https://valid-support.invalid/item", publisher="Valid Publisher",
            content_sha="1" * 64, publication_text=text_payload,
        )
        stale_id = insert_evidence(
            ctx, case_id=case_id, title="Stale contradiction",
            url="https://stale-contradict.invalid/item", publisher="Stale Publisher",
            content_sha="2" * 64, publication_text=text_payload,
        )
        claim_id = "claim456_crossstance"
        now = "2026-10-12T11:00:00+00:00"
        claim = {
            "claim_id": claim_id,
            "case_id": case_id,
            "statement": "A stale contradicting link must not suppress a valid reviewed origin.",
            "state": "accepted_for_dossier",
            "uncertainty_note": "Regression fixture.",
            "created_by": "admin456",
            "created_at": now,
            "reviewed_by": "admin456",
            "reviewed_at": now,
            "review_note": "Regression fixture.",
            "updated_at": now,
        }
        claim["record_hash"] = ctx.evidence_claims_dossier_447._rh(claim)
        ctx.entity_lineage_456.db.execute(
            "INSERT INTO claim_447 VALUES(" + ",".join("?" for _ in claim) + ")",
            tuple(claim.values()),
        )
        for evidence_id, stance in ((support_id, "support"), (stale_id, "contradict")):
            ev = ctx.evidence_claims_dossier_447.evidence(evidence_id)
            link = {
                "link_id": "link456_" + secrets.token_hex(5),
                "claim_id": claim_id,
                "case_id": case_id,
                "evidence_id": evidence_id,
                "stance": stance,
                "note": "",
                "evidence_hash_at_link": ev["record_hash"],
                "created_by": "admin456",
                "created_at": now,
            }
            link["record_hash"] = ctx.evidence_claims_dossier_447._rh(link)
            ctx.entity_lineage_456.db.execute(
                "INSERT INTO claim_evidence_link_447 VALUES(" + ",".join("?" for _ in link) + ")",
                tuple(link.values()),
            )

        support = ctx.evidence_claims_dossier_447.evidence(support_id)
        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=support_id,
            source_family="publisher:valid",
            independence_group="origin:valid",
            origin_key="valid",
            source_role="publisher",
            countable=True,
            rationale="Valid supporting Evidence is reviewed and current.",
            confirmation="REVIEW SOURCE LINEAGE 456",
            expected_evidence_hash=support["record_hash"],
        )
        stale = dict(
            ctx.entity_lineage_456.db.one(
                "SELECT * FROM evidence_item_447 WHERE evidence_id=?", (stale_id,)
            )
        )
        stale["review_state"] = "rejected"
        stale["updated_at"] = "2026-10-12T11:05:00+00:00"
        stale["record_hash"] = ctx.evidence_claims_dossier_447._rh(stale)
        ctx.entity_lineage_456.db.execute(
            "UPDATE evidence_item_447 SET review_state=?,updated_at=?,record_hash=? WHERE evidence_id=?",
            (stale["review_state"], stale["updated_at"], stale["record_hash"], stale_id),
        )
        stale_current = ctx.evidence_claims_dossier_447.evidence(stale_id)
        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=stale_id,
            source_family="publisher:stale",
            independence_group="origin:conflicting-stale",
            origin_key="conflicting-stale",
            source_role="publisher",
            countable=True,
            rationale="Rejected Evidence may have reviewed lineage but cannot affect corroboration.",
            confirmation="REVIEW SOURCE LINEAGE 456",
            expected_evidence_hash=stale_current["record_hash"],
        )

        report = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        assert report["summary"]["support"]["reviewed_independent_origins"] == 1
        assert "same_publication_payload_crosses_claim_stances" not in report["warnings"]


def test_build456_forwarding_preserves_terminal_canonical_comparison(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        left = ctx.entity_resolution_115.register_entity(
            case_id, "person", "محمد", "admin456", source_entity_id="build456:terminal-left"
        )
        right = ctx.entity_resolution_115.register_entity(
            case_id, "person", "Mohammed", "admin456", source_entity_id="build456:terminal-right"
        )
        comparison = ctx.entity_resolution_115.compare(left, right, "admin456")
        ctx.entity_lineage_456.db.execute(
            "UPDATE resolution_comparisons_115 SET state='approved_distinct',reviewed_by=?,"
            "reviewed_at=?,review_reason=? WHERE comparison_id=?",
            ("canonical-reviewer", "2026-10-12T11:10:00+00:00",
             "Previously reviewed canonical distinct decision.", comparison["comparison_id"]),
        )
        before = dict(
            ctx.entity_lineage_456.db.one(
                "SELECT * FROM resolution_comparisons_115 WHERE comparison_id=?",
                (comparison["comparison_id"],),
            )
        )
        ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        pair = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )[0]
        reviewed = ctx.build456.review_multilingual_pair_456(
            identity=identity,
            pair_id=pair["pair_id"],
            decision="investigate_same",
            rationale="Forward only if canonical resolution is still unresolved.",
            confirmation="REVIEW ENTITY PAIR 456",
            expected_pair_hash=pair["record_hash"],
        )
        after = dict(
            ctx.entity_lineage_456.db.one(
                "SELECT * FROM resolution_comparisons_115 WHERE comparison_id=?",
                (comparison["comparison_id"],),
            )
        )
        assert reviewed["state"] == "canonical_resolution_already_reviewed"
        assert reviewed["resolution_comparison_id"] == comparison["comparison_id"]
        assert after["state"] == "approved_distinct"
        assert after["reviewed_by"] == before["reviewed_by"]
        assert after["reviewed_at"] == before["reviewed_at"]
        assert after["review_reason"] == before["review_reason"]


def test_build456_pair_cap_preflight_is_atomic(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        for idx, name in enumerate(("محمد", "محمود", "احمد", "خالد")):
            ctx.entity_resolution_115.register_entity(
                case_id,
                "person",
                name,
                "admin456",
                source_entity_id=f"build456:cap-{idx}",
            )
        try:
            ctx.build456.scan_multilingual_entities_456(
                identity=identity,
                case_id=case_id,
                min_pair_score=0.55,
                max_pairs=2,
            )
            assert False, "pair-cap preflight must reject before mutation"
        except ValueError as exc:
            assert "max_pairs" in str(exc)

        db = ctx.entity_lineage_456.db
        aliases = db.one(
            "SELECT COUNT(*) AS n FROM phase20_alias_candidate_456 WHERE case_id=?",
            (case_id,),
        )
        pairs = db.one(
            "SELECT COUNT(*) AS n FROM phase20_entity_pair_candidate_456 WHERE case_id=?",
            (case_id,),
        )
        runs = db.one(
            "SELECT COUNT(*) AS n FROM phase20_entity_lineage_run_456 WHERE case_id=?",
            (case_id,),
        )
        assert int(aliases["n"]) == 0
        assert int(pairs["n"]) == 0
        assert int(runs["n"]) == 0


def test_build456_pair_review_rejects_stale_display_hash(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        left = ctx.entity_resolution_115.register_entity(
            case_id, "person", "محمد", "admin456", source_entity_id="build456:stale-pair-left"
        )
        right = ctx.entity_resolution_115.register_entity(
            case_id, "person", "Mohammed", "admin456", source_entity_id="build456:stale-pair-right"
        )
        ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        pair = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )[0]
        displayed_hash = pair["record_hash"]

        ctx.entity_resolution_115.add_alias(
            right, "محمد", "manual", "admin456", "build456:stale-pair-alias"
        )
        ctx.build456.scan_multilingual_entities_456(
            identity=identity, case_id=case_id, min_pair_score=0.65
        )
        current = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )[0]
        assert current["record_hash"] != displayed_hash

        try:
            ctx.build456.review_multilingual_pair_456(
                identity=identity,
                pair_id=pair["pair_id"],
                decision="likely_distinct",
                rationale="A stale analyst view must never authorize the changed candidate.",
                confirmation="REVIEW ENTITY PAIR 456",
                expected_pair_hash=displayed_hash,
            )
            assert False, "stale pair review must fail"
        except PermissionError:
            pass

        unchanged = ctx.build456.multilingual_pair_candidates_456(
            identity=identity, case_id=case_id
        )[0]
        assert unchanged["state"] == "review_required"
        assert unchanged["reviewed_by"] == ""
