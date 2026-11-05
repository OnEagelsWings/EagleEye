"""Build 490 synthetic journey, phase 1: persisted source and review -> UI drill-down.

This is intentionally a partial acceptance slice, NOT the full 490 E2E gate.
It exercises real storage and authenticated routes without external networks.
"""
import html
import re
from urllib.parse import urlsplit, parse_qs
import pytest
from eagleeye.interfaces.web.app489 import create_workspace_app489
from test_build471_local_ai import workspace
from test_build488_integration import entities, form as review_form
from test_build487_sources import lead, form as source_form
from test_build481_evidence_bridge import document_approved, form as evidence_form

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app489], indirect=True)


def test_synthetic_case_review_source_and_original_navigation(workspace, tmp_path):
    app, client, user, case_id, *_ = workspace
    left, right = entities(workspace, tmp_path)
    response = client.post(
        "/workbench/entities488",
        data=review_form(workspace, left, right),
        follow_redirects=False,
    )
    assert response.status_code == 303

    lead_id = lead(workspace)
    document_approved(workspace)
    response = client.post(
        "/workbench/sources487",
        data=source_form(workspace, lead_id),
        follow_redirects=False,
    )
    assert response.status_code == 303

    checkpoint = client.get("/workbench/checkpoint489", params={"case_id": case_id})
    assert checkpoint.status_code == 200
    assert "Auditierte Entitätsentscheidungen (1)" in checkpoint.text
    assert "Integritätsgeprüfte Quellenzuordnungen (1)" in checkpoint.text

    links = re.findall(r'href="([^"]+)"', checkpoint.text)
    original_links = [
        html.unescape(link) for link in links
        if link.startswith("/documents458?") and "document_id=" in html.unescape(link)
    ]
    assert len(original_links) == 1
    target = urlsplit(original_links[0])
    assert parse_qs(target.query)["case_id"] == [case_id]
    assert len(parse_qs(target.query)["document_id"]) == 1
    original = client.get(original_links[0])
    assert original.status_code == 200

    # Source links and entity decisions never auto-promote evidence or claims.
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_evidence(case_id) == []
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    # A second, explicit authenticated action promotes the reviewed original
    # into *unreviewed* canonical Evidence, not into an accepted claim.
    handoff = client.post(
        "/workbench/bridge481", data=evidence_form(workspace),
        follow_redirects=False,
    )
    assert handoff.status_code == 303, handoff.text[:400]
    evidence = store.case_evidence(case_id)
    assert len(evidence) == 1
    assert evidence[0]["review_state"] == "unreviewed"
    document = app.state.context.document_intelligence_458._document(workspace[4])
    assert evidence[0]["content_sha256"] == document["document_sha256"]
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []
    assert store.verify_integrity()["valid"]

    # Retrying a valid handoff must not duplicate canonical Evidence.
    again = client.post(
        "/workbench/bridge481", data=evidence_form(workspace),
        follow_redirects=False,
    )
    assert again.status_code == 303
    assert len(store.case_evidence(case_id)) == 1

    # The canonical record must retain an honest, auditable local-capture
    # provenance. A manually entered research lead is NOT a network capture.
    source_event = app.state.context.acquisition_events_422.get(evidence[0]["event_id"])
    assert source_event["provenance"]["network_fetch_performed"] is False
    assert source_event["provenance"]["document_id"] == workspace[4]
    assert source_event["provenance"]["human_rationale"]
    assert source_event["usage"]["truth_determined"] is False
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []


    # The existing authenticated graph workspace must remain reachable from
    # the same synthetic case after source/evidence handoff. This is a UI
    # navigation gate, NOT proof that unreviewed candidate links are facts.
    graph = client.get("/graph464", params={"case_id": case_id})
    assert graph.status_code == 200, graph.text[:400]
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []



def test_synthetic_source_bound_ai_requires_human_review(workspace):
    """Run the existing local assistant against the real imported original.

    No network model is needed: only the Ollama transport is simulated, while
    extraction, source anchors, persistence, and authenticated routes stay real.
    """
    from unittest.mock import patch
    from test_build471_local_ai import csrf as assistant_csrf, reply, provider

    app, client, user, case_id, doc_id, foreign_case, foreign_doc = workspace
    service = app.state.assistant471
    token = assistant_csrf(client, case_id)
    calls = []
    answer = reply(service, user, case_id, doc_id)
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    with patch.object(service, "request", side_effect=provider(answer, calls)):
        generated = client.post(
            "/assistant471/generate",
            data={"case_id": case_id, "csrf_token": token,
                  "document_id": doc_id, "model": "mistral:latest"},
            follow_redirects=False,
        )
    assert generated.status_code == 303, generated.text[:400]
    assert any(path == "/api/chat" for _, path, _ in calls)
    run = service.history(user, case_id)[0]
    assert run["status"] == "review_required"
    assert run["truth_determined"] is False
    assert run["claims_created"] == 0
    assert run["sources"][0]["anchor_id"] == answer["statements"][0]["citations"][0]["anchor_id"]
    assert client.get("/assistant471", params={"case_id": case_id}).status_code == 200
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []

    # Build 474's existing review contract requires a verdict and a distinct
    # explanation for EVERY statement, hypothesis and uncertainty. Use the
    # actual item identifiers, not a bypass or a blanket acknowledgment.
    from eagleeye.application.review474 import review_items
    items = review_items(run)
    assert items
    assessment_form = {
        "case_id": case_id, "csrf_token": token,
        "run_id": run["run_id"], "decision": "acknowledged",
        "note": "Originalquelle und alle Einzelbewertungen selbst geprüft.",
    }
    for item in items:
        key = item["item_id"]
        assessment_form["verdict_" + key] = "unclear"
        assessment_form["item_note_" + key] = (
            "Nur die vorliegende Quelle; unabhängige Bestätigung fehlt."
        )
    reviewed = client.post(
        "/assistant471/review", data=assessment_form, follow_redirects=False,
    )
    assert reviewed.status_code == 303, reviewed.text[:400]
    stored = type(service)(app.state.context).history(user, case_id)[0]
    assert stored["status"] == "acknowledged"
    assert stored["truth_determined"] is False
    assert set(stored["review"]["assessments"]) == {
        item["item_id"] for item in items
    }
    assert all(
        entry["verdict"] == "unclear"
        for entry in stored["review"]["assessments"].values()
    )
    assert stored["sources"] == run["sources"]
    assert stored["claims_created"] == 0
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []
    assert service.history(user, foreign_case) == []



def test_synthetic_ai_review_rejects_incomplete_assessment_without_promotion(workspace):
    """A summary cannot be acknowledged with a bare note instead of item reviews.

    This is a fail-closed regression for the stricter review contract introduced
    by the stacked workspace. The successful fully assessed review remains an
    open Build-490 integration gate and is not simulated here.
    """
    from unittest.mock import patch
    from test_build471_local_ai import csrf as assistant_csrf, reply, provider

    app, client, user, case_id, doc_id, *_ = workspace
    service = app.state.assistant471
    token = assistant_csrf(client, case_id)
    with patch.object(service, "request", side_effect=provider(
        reply(service, user, case_id, doc_id), []
    )):
        generated = client.post(
            "/assistant471/generate",
            data={"case_id": case_id, "csrf_token": token,
                  "document_id": doc_id, "model": "mistral:latest"},
            follow_redirects=False,
        )
    assert generated.status_code == 303
    run = service.history(user, case_id)[0]
    rejected = client.post(
        "/assistant471/review",
        data={"case_id": case_id, "csrf_token": token,
              "run_id": run["run_id"], "decision": "acknowledged",
              "note": "Only a generic note; no individual assessment."},
        follow_redirects=False,
    )
    assert rejected.status_code == 422
    persisted = type(service)(app.state.context).history(user, case_id)[0]
    assert persisted["status"] == "review_required"
    assert persisted["truth_determined"] is False
    # A rejected review must not discard or rewrite the cited source anchors.
    assert persisted["sources"] == run["sources"]
    assert persisted["run_id"] == run["run_id"]
    assert persisted["claims_created"] == 0
    store = app.state.context.evidence_claims_dossier_447
    assert store.case_claims(case_id) == []
    assert store.case_dossiers(case_id) == []


def test_synthetic_graph_and_original_are_case_scoped(workspace):
    """Graph and original navigation must not bypass case access control."""
    from fastapi.testclient import TestClient

    app, client, user, case_id, document_id, foreign_case, foreign_doc = workspace
    # The fixture creates both cases under the SAME administrator. Access to
    # either case is authorized; a 403 here would incorrectly test ownership.
    assert client.get("/graph464", params={"case_id": foreign_case}).status_code == 200
    # A document from one case must never be resolved under another case.
    assert client.get(
        "/documents458", params={"case_id": case_id, "document_id": foreign_doc}
    ).status_code in {403, 404}
    with TestClient(app) as anonymous:
        assert anonymous.get("/graph464", params={"case_id": case_id}).status_code == 401
        assert anonymous.get(
            "/documents458", params={"case_id": case_id, "document_id": document_id}
        ).status_code == 401
