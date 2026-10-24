"""Regression: expose original expert capabilities without reimplementing them.

Tests use the canonical authenticated case fixture and its existing source archive.
"""
from urllib.parse import urlencode
from html import escape, unescape

import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app477 import create_workspace_app477
from test_build471_local_ai import workspace

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app477], indirect=True)


def test_expert_tool_center_restores_existing_dossier_and_analyst_views(workspace):
    app, client, user, case_id, document_id, *_ = workspace
    center = client.get("/workbench/expert", params={"case_id": case_id})
    assert center.status_code == 200
    assert "Alle Ermittlungswerkzeuge" in center.text
    assert "Synthetic AI case" in center.text
    assert center.headers["cache-control"] == "no-store"
    assert "Vier-Augen" in center.text
    assert "kein allgemeiner Webcrawler" in center.text
    for view, visible in [
        ("research", "Recherche"),
        ("ai", "AI-Ermittlung"),
        ("evidence", "Evidence"),
        ("claims", "Claims & Hypothesen"),
        ("analysis", "Graph & Timeline"),
        ("dossier", "Dossier"),
        ("operations", "OPSEC & Team"),
    ]:
        link = "/?" + urlencode({"case_id": case_id, "view": view})
        assert 'href="' + escape(link, quote=True) + '"' in center.text
        response = client.get("/", params={"view": view, "case_id": case_id})
        assert response.status_code == 200, (view, response.text[:350])
        assert visible in unescape(response.text), view
        assert "Alle Ermittlungswerkzeuge" in response.text, view
    dossier = client.get("/", params={"case_id": case_id, "view": "dossier"})
    assert "Living-Dossier-Revision" in dossier.text
    # No accepted claim in this fixture: dossier creation must not be falsely pre-approved.
    assert "Mindestens ein akzeptierter Claim ist erforderlich" in dossier.text
    assert "Freigegebenes Dossier" not in center.text  # no endorsement/automatic release


def test_no_more_legacy_navigation_dead_end_for_real_cases(workspace):
    app, client, user, case_id, *_ = workspace
    home = client.get("/", params={"case_id": case_id})
    assert home.status_code == 200
    assert 'href="/legacy"' not in home.text
    assert 'href="/legacy?case_id=' not in home.text
    assert "/workbench/expert?case_id=" + case_id in home.text
    guided = client.get("/workbench", params={"case_id": case_id})
    assert "Erweiterte Ermittlungswerkzeuge" in guided.text
    assert "/workbench/expert?case_id=" + case_id in guided.text
    inventory = client.get("/workbench/sources", params={"case_id": case_id})
    assert 'Expertenwerkzeuge' in inventory.text


def test_expert_center_fails_closed_for_foreign_or_missing_case(workspace):
    app, client, user, case_id, *_ = workspace
    denied = client.get("/workbench/expert", params={"case_id": "case_nonexistent"})
    assert denied.status_code == 403
    with TestClient(app) as anonymous:
        without_session = anonymous.get("/workbench/expert", params={"case_id": case_id})
        assert without_session.status_code == 401


def test_visible_tools_reflect_actual_routes_not_fake_features(workspace):
    app, client, user, case_id, *_ = workspace
    page = client.get("/workbench/expert", params={"case_id": case_id})
    assert page.status_code == 200
    assert "/documents458?case_id=" + case_id in page.text
    assert "/collect469?case_id=" + case_id in page.text
    assert "DNS, RDAP .com und Crossref" in page.text
    assert "GET-Oberfläche vorhanden; Live-Funktion nicht durch die Linkprüfung belegt" in page.text
    # Build 477 does not claim the yet-to-be-merged 478/479 functionality.
    assert "In diesem Build nicht angebunden" in page.text
    assert 'href="/workbench/report?case_id=' not in page.text


def test_restoring_dossier_view_does_not_restore_unsafe_direct_approval_routes(workspace):
    app, client, user, case_id, *_ = workspace
    routes = {(route.path, method) for route in app.router.routes
              for method in (getattr(route, "methods", set()) or set())}
    assert ("/api/build449/reviews", "POST") in routes
    assert ("/api/build449/reviews/{review_id}/export", "POST") in routes
    # Build-449 intentionally deleted older direct approval/export mutation routes.
    assert ("/api/build447/dossiers/{revision_id}/export", "POST") not in routes
    assert ("/api/build447/dossiers/{revision_id}/review", "POST") not in routes
    assert client.get("/", params={"case_id": case_id, "view": "dossier"}).status_code == 200
