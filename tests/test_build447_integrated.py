from pathlib import Path
from zipfile import ZipFile
import hashlib
import runpy

import pytest

from eagleeye_pro.core.app_context import AppContext

ROOT = Path(__file__).resolve().parents[1]


def ident(c):
    if c.team_identity_359.bootstrap_required():
        return c.team_identity_359.create_initial_admin(
            username="analyst",
            display_name="Analyst Fixture",
            password="SecureFixturePassword!2026",
        )
    return c.team_identity_359.public_user("analyst")


def case(c, title="Evidence Claims Dossier 447"):
    return c.build447.team_create_case(
        identity=ident(c),
        title=title,
        client="QA",
        purpose="Build 447 Evidence Claims Dossier qualification",
        legal_basis="public_data",
    )


def seed_evidence(c, identity, case_id, suffix="one"):
    source = c.build421.register_source(
        identity=identity,
        name=f"Build 447 Source {suffix}",
        source_type="website",
        access_mode="public",
        base_url=f"https://evidence447-{suffix}.example.org/",
        capabilities=["public_pages"],
        coverage={"fixture_only": True},
    )
    raw = f"Build 447 evidence payload {suffix}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    event = c.acquisition_events_422.record(
        identity=identity,
        case_id=case_id,
        source_id=source["source_id"],
        target=f"https://evidence447-{suffix}.example.org/item",
        method="manual_import",
        status="retrieved",
        content_sha256=digest,
        media_type="text/plain",
        bytes_count=len(raw),
        provenance={"build": "447-test", "fixture": True},
        usage={"public_only": True, "synthetic_test_fixture": True},
    )
    content = c.content_store_423.ingest(
        identity=identity,
        event_id=event["event_id"],
        content=raw,
        media_type="text/plain",
        metadata={"build447_test": True},
    )
    sync = c.build447.sync_case_evidence_447(identity=identity, case_id=case_id)
    ev = next(x for x in c.build447.case_evidence_447(case_id) if x["observation_id"] == content["observation_id"])
    return source, event, content, sync, ev


def review_accept(c, identity, evidence_id, note="Accepted for deterministic Build 447 qualification."):
    return c.build447.review_evidence_447(
        identity=identity,
        evidence_id=evidence_id,
        decision="accepted",
        note=note,
        confirmation="REVIEW EVIDENCE 447",
    )


def accepted_claim(c, identity, case_id, support_id, *, contra_id=None):
    claim = c.build447.propose_claim_447(
        identity=identity,
        case_id=case_id,
        statement="Synthetic proposition for Build 447 qualification.",
        support_evidence_ids=[support_id],
        contradiction_evidence_ids=[contra_id] if contra_id else [],
        uncertainty_note=(
            "A contradictory source is retained and requires human interpretation."
            if contra_id
            else ""
        ),
    )
    return c.build447.review_claim_447(
        identity=identity,
        claim_id=claim["claim_id"],
        decision="accepted_for_dossier",
        note="Accepted for deterministic dossier qualification only.",
        confirmation="REVIEW CLAIM 447",
    )


def test_build447_selftest_closes_full_chain_and_exports_package(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c)["case_id"]
        result = c.build447.run_evidence_claims_dossier_case_selftest(
            identity=i,
            case_id=cid,
        )
        assert result["result"] == "PASS"
        assert all(result["checks"].values())
        assert c.evidence_claims_dossier_447.verify_integrity()["valid"]
        exports = c.build447.case_exports_447(cid)
        assert len(exports) == 1
        package = Path(exports[0]["paths"]["case_package"])
        assert package.exists()
        with ZipFile(package) as z:
            assert set(z.namelist()) == {
                "EagleEye_Living_Dossier.json",
                "EagleEye_Living_Dossier.docx",
                "EagleEye_Living_Dossier.pdf",
                "manifest.json",
            }



def test_repeated_dossier_exports_use_immutable_unique_directories(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Immutable exports 447")["case_id"]
        *_x, ev = seed_evidence(c, i, cid, "immutable-export")
        ev = review_accept(c, i, ev["evidence_id"])
        accepted_claim(c, i, cid, ev["evidence_id"])
        dossier = c.build447.build_dossier_447(identity=i, case_id=cid)
        dossier = c.build447.review_dossier_447(
            identity=i,
            revision_id=dossier["revision_id"],
            decision="approved_for_export",
            note="Approved for immutable repeated-export regression.",
            confirmation="APPROVE DOSSIER 447",
        )
        first = c.build447.export_dossier_447(
            identity=i,
            revision_id=dossier["revision_id"],
            confirmation="EXPORT DOSSIER 447",
        )
        first_package = Path(first["paths"]["case_package"])
        first_bytes = first_package.read_bytes()
        second = c.build447.export_dossier_447(
            identity=i,
            revision_id=dossier["revision_id"],
            confirmation="EXPORT DOSSIER 447",
        )
        second_package = Path(second["paths"]["case_package"])
        assert first["export_id"] != second["export_id"]
        assert first_package != second_package
        assert first_package.parent.name == first["export_id"]
        assert second_package.parent.name == second["export_id"]
        assert first_package.read_bytes() == first_bytes
        assert hashlib.sha256(first_package.read_bytes()).hexdigest() == first["package_hash"]
        assert hashlib.sha256(second_package.read_bytes()).hexdigest() == second["package_hash"]


def test_evidence_sync_is_idempotent_and_does_not_break_claim_links(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Idempotent 447")["case_id"]
        _s, _e, _co, _sync, ev = seed_evidence(c, i, cid, "idem")
        ev = review_accept(c, i, ev["evidence_id"])
        claim = accepted_claim(c, i, cid, ev["evidence_id"])
        before = c.evidence_claims_dossier_447.evidence(ev["evidence_id"])
        second = c.build447.sync_case_evidence_447(identity=i, case_id=cid)
        after = c.evidence_claims_dossier_447.evidence(ev["evidence_id"])
        assert second["unchanged"] >= 1
        assert before["record_hash"] == after["record_hash"]
        assert c.evidence_claims_dossier_447.claim(claim["claim_id"])["state"] == "accepted_for_dossier"
        assert c.evidence_claims_dossier_447.verify_integrity()["valid"]


def test_unreviewed_evidence_cannot_support_claim(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Review boundary 447")["case_id"]
        _s, _e, _co, _sync, ev = seed_evidence(c, i, cid, "unreviewed")
        with pytest.raises(PermissionError, match="human-reviewed"):
            c.build447.propose_claim_447(
                identity=i,
                case_id=cid,
                statement="This must not be accepted from unreviewed evidence.",
                support_evidence_ids=[ev["evidence_id"]],
            )


def test_counterevidence_requires_uncertainty_and_is_preserved_in_dossier(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Counterevidence 447")["case_id"]
        *_a, ev1 = seed_evidence(c, i, cid, "support")
        *_b, ev2 = seed_evidence(c, i, cid, "contra")
        ev1 = review_accept(c, i, ev1["evidence_id"])
        ev2 = review_accept(c, i, ev2["evidence_id"])

        with pytest.raises(ValueError, match="uncertainty"):
            c.build447.propose_claim_447(
                identity=i,
                case_id=cid,
                statement="A proposition with unresolved contradictory evidence.",
                support_evidence_ids=[ev1["evidence_id"]],
                contradiction_evidence_ids=[ev2["evidence_id"]],
                uncertainty_note="too short",
            )

        claim = accepted_claim(c, i, cid, ev1["evidence_id"], contra_id=ev2["evidence_id"])
        dossier = c.build447.build_dossier_447(identity=i, case_id=cid)
        assert dossier["state"] == "draft_for_review"
        assert dossier["snapshot"]["counterevidence"]
        assert dossier["snapshot"]["open_uncertainties"]
        assert any(x["stance"] == "contradict" for x in claim["links"])


def test_wrong_confirmations_fail_closed_at_each_human_gate(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Confirmations 447")["case_id"]
        *_x, ev = seed_evidence(c, i, cid, "confirm")

        with pytest.raises(PermissionError):
            c.build447.review_evidence_447(
                identity=i,
                evidence_id=ev["evidence_id"],
                decision="accepted",
                note="Documented review note.",
                confirmation="GO",
            )
        ev = review_accept(c, i, ev["evidence_id"])
        claim = c.build447.propose_claim_447(
            identity=i,
            case_id=cid,
            statement="Confirmation boundary proposition.",
            support_evidence_ids=[ev["evidence_id"]],
        )
        with pytest.raises(PermissionError):
            c.build447.review_claim_447(
                identity=i,
                claim_id=claim["claim_id"],
                decision="accepted_for_dossier",
                note="Documented claim review.",
                confirmation="GO",
            )
        claim = c.build447.review_claim_447(
            identity=i,
            claim_id=claim["claim_id"],
            decision="accepted_for_dossier",
            note="Documented claim review.",
            confirmation="REVIEW CLAIM 447",
        )
        dossier = c.build447.build_dossier_447(identity=i, case_id=cid)
        with pytest.raises(PermissionError):
            c.build447.review_dossier_447(
                identity=i,
                revision_id=dossier["revision_id"],
                decision="approved_for_export",
                note="Documented dossier review.",
                confirmation="GO",
            )
        dossier = c.build447.review_dossier_447(
            identity=i,
            revision_id=dossier["revision_id"],
            decision="approved_for_export",
            note="Documented dossier review.",
            confirmation="APPROVE DOSSIER 447",
        )
        with pytest.raises(PermissionError):
            c.build447.export_dossier_447(
                identity=i,
                revision_id=dossier["revision_id"],
                confirmation="GO",
            )
        assert c.build447.case_exports_447(cid) == []


def test_dossier_requires_human_accepted_claim(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Claim gate 447")["case_id"]
        *_x, ev = seed_evidence(c, i, cid, "draftclaim")
        ev = review_accept(c, i, ev["evidence_id"])
        c.build447.propose_claim_447(
            identity=i,
            case_id=cid,
            statement="Still awaiting claim review.",
            support_evidence_ids=[ev["evidence_id"]],
        )
        with pytest.raises(ValueError, match="accepted claim"):
            c.build447.build_dossier_447(identity=i, case_id=cid)


def test_underlying_provenance_tamper_breaks_integrity_and_blocks_dossier_approval(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        cid = case(c, "Tamper 447")["case_id"]
        _src, event, _co, _sync, ev = seed_evidence(c, i, cid, "tamper")
        ev = review_accept(c, i, ev["evidence_id"])
        accepted_claim(c, i, cid, ev["evidence_id"])
        dossier = c.build447.build_dossier_447(identity=i, case_id=cid)

        c.db.execute(
            "UPDATE acquisition_event_422 SET target='https://tampered.invalid/' WHERE event_id=?",
            (event["event_id"],),
        )
        assert c.evidence_claims_dossier_447.verify_integrity()["valid"] is False
        with pytest.raises(PermissionError, match="integrity"):
            c.build447.review_dossier_447(
                identity=i,
                revision_id=dossier["revision_id"],
                decision="approved_for_export",
                note="Must be blocked due to provenance tamper.",
                confirmation="APPROVE DOSSIER 447",
            )


def test_case_isolation_for_evidence_claims_and_dossiers(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        i = ident(c)
        ca = case(c, "Case A 447")["case_id"]
        cb = case(c, "Case B 447")["case_id"]
        *_a, eva = seed_evidence(c, i, ca, "casea")
        *_b, evb = seed_evidence(c, i, cb, "caseb")
        eva = review_accept(c, i, eva["evidence_id"])
        evb = review_accept(c, i, evb["evidence_id"])

        with pytest.raises(PermissionError, match="same case"):
            c.build447.propose_claim_447(
                identity=i,
                case_id=ca,
                statement="Cross-case claim must fail.",
                support_evidence_ids=[evb["evidence_id"]],
            )

        ca_claim = accepted_claim(c, i, ca, eva["evidence_id"])
        da = c.build447.build_dossier_447(identity=i, case_id=ca)
        assert ca_claim["case_id"] == ca
        assert da["case_id"] == ca
        assert all(x["case_id"] == ca for x in c.build447.case_evidence_447(ca))
        assert all(x["case_id"] == cb for x in c.build447.case_evidence_447(cb))


def test_status_contract_and_exports_are_not_truth_certification(tmp_path):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        status = c.build447.evidence_claims_dossier_status_447()
        assert status["version_coherent"]
        assert status["phase"] == 20
        assert status["phase20_builds_completed"] == 7
        assert status["evidence_viewer"]
        assert status["source_snapshots"]
        assert status["claim_evidence_links"]
        assert status["counterevidence_preserved"]
        assert status["uncertainty_preserved"]
        assert status["living_dossier_revisions"]
        assert status["docx_export"]
        assert status["pdf_export"]
        assert status["case_package_export"]
        assert status["raw_payload_duplicated"] is False
        assert status["automatic_claim_creation"] is False
        assert status["automatic_claim_acceptance"] is False
        assert status["automatic_truth_determination"] is False
        assert status["automatic_dossier_publication"] is False
        assert status["formal_four_eyes_export_workflow_deferred_to_build449"]
        assert status["production_release_ready"] is False
        assert status["next_build"] == "448.0"
        assert status["next_hard_checkpoint"] == "450.0"


def test_contract_launcher_and_current_server(tmp_path, monkeypatch):
    with AppContext(base_dir=tmp_path) as c:
        ident(c)
        assert c.build447.evidence_claims_dossier_status_447()["version_coherent"]

    import eagleeye.interfaces.web.app447 as appmod

    calls = []
    monkeypatch.setattr(
        appmod,
        "create_workspace_app447",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    namespace = runpy.run_path(str(ROOT / "EAGLEEYE_PRO_450_0.py"), run_name="__mp_main__")
    assert calls == []
    assert namespace["app"] is None
    assert "app452 import create_workspace_app452" in (
        ROOT / "src/eagleeye/interfaces/web/server.py"
    ).read_text()
    assert (ROOT / "BUILD_447_CASE_TEST.md").exists()
    assert (ROOT / "README_BUILD_447_0.md").exists()
    readme = (ROOT / "README.md").read_text()
    assert "EAGLEEYE_PRO_450_0.py" in readme
    assert "test_build450_integrated.py" in readme
