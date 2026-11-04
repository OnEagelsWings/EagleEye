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
from test_build481_evidence_bridge import document_approved

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
        if link.startswith("/documents458?")
    ]
    assert len(original_links) == 1
    target = urlsplit(original_links[0])
    assert parse_qs(target.query)["case_id"] == [case_id]
    assert len(parse_qs(target.query)["document_id"]) == 1
    original = client.get(original_links[0])
    assert original.status_code == 200

    # Human review and source association do not promote claims automatically.
    assert app.state.context.evidence_claims_dossier_447.case_claims(case_id) == []
