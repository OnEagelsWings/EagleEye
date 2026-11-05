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
