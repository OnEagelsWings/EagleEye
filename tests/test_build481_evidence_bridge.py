"""Build 481 hard boundaries: real reviewed file -> unreviewed canonical Evidence."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app481 import create_workspace_app481
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.bridge481 import _records
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session
from test_build475_ai_checkpoint import member

pytestmark = pytest.mark.parametrize(
    "workspace", [create_workspace_app481], indirect=True
)


def document_approved(workspace):
    app, client, user, case_id, document_id, *_ = workspace
    service = app.state.context.document_intelligence_458
    original = service._document(document_id)
    return service.review_extraction(
        identity=user, document_id=document_id,
        expected_document_hash=original["record_hash"],
        decision="approve",
        note="Manually compared original source and every text location.",
        confirmation="REVIEW DOCUMENT EXTRACTION 458",
    )


def form(workspace, *, document_id=None):
    app, client, user, case_id, original_id, *_ = workspace
    return {
        "csrf": csrf_session(workspace),
        "case_id": case_id,
        "document_id": document_id or original_id,
        "rationale": "I checked original public source and confirm lawful local evidence capture.",
        "confirm": "yes",
    }


def test_first_run_navigation_and_real_provenance_bridge(workspace):
    app, client, user, cid, doc_id, *_ = workspace
    ctx = app.state.context
    assert app.version == "481.0"
    assert client.get("/health").json()["build"] == "481.0"
    before = client.get("/workbench", params={"case_id": cid})
    assert before.status_code == 200
    assert "Quelle" in before.text and "Evidence" in before.text
    assert client.get("/workbench/closure", params={"case_id": cid}).status_code == 200
    bridge = client.get("/workbench/bridge481", params={"case_id": cid})
    assert bridge.status_code == 200
    assert "Erst Extraktion prüfen" in bridge.text
    data = form(workspace)
    rejected = client.post("/workbench/bridge481", data=data, follow_redirects=False)
    assert rejected.status_code == 409
    assert ctx.evidence_claims_dossier_447.case_evidence(cid) == []
    document_approved(workspace)
    accepted = client.post("/workbench/bridge481", data=data, follow_redirects=False)
    assert accepted.status_code == 303, accepted.text[:400]
    entries = _records(ctx, cid)
    assert len(entries) == 1 and entries[0]["document_id"] == doc_id
    e = ctx.evidence_claims_dossier_447.case_evidence(cid)
    assert len(e) == 1 and e[0]["review_state"] == "unreviewed"
    assert e[0]["content_sha256"] == ctx.document_intelligence_458._document(doc_id)["document_sha256"]
    assert ctx.evidence_claims_dossier_447.case_claims(cid) == []
    assert ctx.evidence_claims_dossier_447.case_dossiers(cid) == []
    assert ctx.evidence_claims_dossier_447.verify_integrity()["valid"]
    source = ctx.acquisition_events_422.get(e[0]["event_id"])
    assert source["provenance"]["network_fetch_performed"] is False
    assert source["provenance"]["document_id"] == doc_id
    assert source["provenance"]["human_rationale"]
    assert source["usage"]["truth_determined"] is False
    second = client.post("/workbench/bridge481", data=data, follow_redirects=False)
    assert second.status_code == 303
    assert len(ctx.evidence_claims_dossier_447.case_evidence(cid)) == 1
    assert len(_records(ctx, cid)) == 1
    assert "Bereits als ungeprüfte Evidence registriert" in client.get(
        "/workbench/bridge481", params={"case_id": cid}
    ).text


def test_security_approval_and_origin_fail_closed(workspace):
    app, client, admin, cid, doc_id, foreign, foreign_doc = workspace
    ctx = app.state.context
    document_approved(workspace)
    data = form(workspace)
    for changes, headers in [
        ({"csrf": "forged"}, {}),
        ({"confirm": ""}, {}),
        ({}, {"Origin": "https://attacker.example"}),
        ({"document_id": foreign_doc}, {}),
    ]:
        submitted = {**data, **changes}
        response = client.post(
            "/workbench/bridge481", data=submitted,
            headers=headers, follow_redirects=False,
        )
        assert response.status_code in (403, 422), (changes, response.status_code)
    assert ctx.evidence_claims_dossier_447.case_evidence(cid) == []
    assert client.get("/workbench/bridge481", params={"case_id": foreign_doc}).status_code == 403
    assert client.get("/workbench/bridge481", params={"case_id": "missing"}).status_code == 403
    with TestClient(app) as anonymous:
        assert anonymous.get(
            "/workbench/bridge481", params={"case_id": cid}
        ).status_code == 401


def test_stale_original_and_readonly_role_cannot_promote(workspace):
    app, client, admin, cid, doc_id, *_ = workspace
    ctx = app.state.context
    document_approved(workspace)
    data = form(workspace)
    member(workspace, "read_only")
    data["csrf"] = csrf_session(workspace, "member475", "Independent!Secret_881")
    assert client.post("/workbench/bridge481", data=data).status_code == 403
    assert not _records(ctx, cid)
    csrf_session(workspace)
    data["csrf"] = client.cookies.get(CSRF_COOKIE)
    service = ctx.document_intelligence_458
    (service.root / service._document(doc_id)["stored_relpath"]).write_bytes(b"tampered")
    assert client.post("/workbench/bridge481", data=data).status_code == 409
    assert not _records(ctx, cid)
    assert ctx.evidence_claims_dossier_447.case_evidence(cid) == []


def test_bridge_record_tampering_blocks_list(workspace):
    app, client, user, cid, doc_id, *_ = workspace
    document_approved(workspace)
    assert client.post("/workbench/bridge481", data=form(workspace)).status_code == 200
    ctx = app.state.context
    ctx.db.execute(
        "UPDATE document_evidence_bridge_481 SET content_sha256=? WHERE document_id=?",
        ("0" * 64, doc_id)
    )
    assert client.get("/workbench/bridge481", params={"case_id": cid}).status_code == 409
