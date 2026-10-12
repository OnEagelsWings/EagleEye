from __future__ import annotations

from pathlib import Path
import json
import secrets

from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app456 import create_workspace_app456

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


def insert_evidence(ctx, *, case_id, title, url, publisher, content_sha):
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
        "descriptive_json": json.dumps({"publisher": publisher}),
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


def test_build456_source_lineage_counts_origins_not_mentions(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        identity, case = setup_case(ctx)
        case_id = case["case_id"]
        duplicate_sha = "a" * 64
        ev1 = insert_evidence(
            ctx, case_id=case_id, title="Wire copy A",
            url="https://example-one.invalid/story", publisher="Reuters",
            content_sha=duplicate_sha,
        )
        ev2 = insert_evidence(
            ctx, case_id=case_id, title="Wire copy B",
            url="https://example-two.invalid/republication", publisher="Reuters",
            content_sha=duplicate_sha,
        )
        ev3 = insert_evidence(
            ctx, case_id=case_id, title="Independent report",
            url="https://example-three.invalid/report", publisher="Associated Press",
            content_sha="b" * 64,
        )
        claim_id = insert_claim(ctx, case_id=case_id, evidence_ids=[ev1, ev2, ev3])
        report = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        support = report["summary"]["support"]
        assert support["mentions"] == 3
        assert support["unique_payloads"] == 2
        assert support["source_families"] == 2
        assert support["independent_origins"] == 2
        assert "duplicate_payloads_do_not_add_corroboration" in report["warnings"]
        assert report["source_independence_determines_truth"] is False

        ctx.build456.review_source_lineage_456(
            identity=identity,
            evidence_id=ev3,
            source_family="publisher:associated-press",
            independence_group="origin:publisher:associated-press",
            origin_key="publisher:associated-press",
            source_role="publisher",
            countable=False,
            rationale="Treat this item as non-countable for this bounded test scenario.",
            confirmation="REVIEW SOURCE LINEAGE 456",
        )
        reviewed = ctx.build456.claim_source_lineage_456(identity=identity, claim_id=claim_id)
        assert reviewed["summary"]["support"]["independent_origins"] == 1


def test_build456_integrity_and_no_automatic_authority(tmp_path):
    with AppContext(base_dir=tmp_path) as ctx:
        assert ctx.entity_lineage_456.verify_integrity()["valid"] is True
        status = ctx.entity_lineage_456.status()
        assert status["automatic_identity_confirmation"] is False
        assert status["automatic_entity_merge"] is False
        assert status["automatic_truth_determination"] is False
