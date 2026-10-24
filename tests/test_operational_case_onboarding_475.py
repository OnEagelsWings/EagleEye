"""Regression: a fresh real user must be able to create an operational case via UI."""
from __future__ import annotations

import hashlib
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app475 import create_workspace_app475
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE


def test_first_operational_case_flow_in_build475(tmp_path):
    app = create_workspace_app475(base_dir=tmp_path)
    ctx = app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="firstcase475",
            display_name="First Case QA",
            password="Distinct!Secure-Key-2847",
        )
        fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
        session = ctx.team_identity_359.authenticate(
            username="firstcase475",
            password="Distinct!Secure-Key-2847",
            client_fingerprint=fingerprint,
        )
        with TestClient(app) as client:
            # No logged-in access? No case metadata or CSRF token should leak.
            anonymous = client.get("/new-case", follow_redirects=False)
            assert anonymous.status_code == 303
            assert anonymous.headers["location"] == "/security/login"

            client.cookies.set(COOKIE, session.token)
            client.cookies.set(CSRF_COOKIE, session.csrf_token)
            home = client.get("/", follow_redirects=False)
            assert home.status_code == 303
            assert home.headers["location"] == "/new-case"

            create_page = client.get("/new-case")
            assert create_page.status_code == 200
            assert 'action="/cases"' in create_page.text
            assert "Neuen Ermittlungsfall anlegen" in create_page.text
            assert "keine Produktivfreigabe" in create_page.text
            assert session.csrf_token in create_page.text
            assert create_page.headers.get("cache-control") == "no-store"

            attempted = client.post("/cases", data={
                "title": "Unauthorized first case",
                "client": "",
                "purpose": "Denied CSRF",
                "legal_basis": "public_data",
                "csrf": "forged",
            }, follow_redirects=False)
            assert attempted.status_code == 403
            ident = ctx.team_identity_359.validate_session(
                session.token, client_fingerprint=fingerprint, touch=False)
            assert ctx.team_governance_359.visible_cases(ident) == []

            posted = client.post("/cases", data={
                "title": "First operational public case",
                "client": "Own research",
                "purpose": "Public source analysis, no sensitive data",
                "legal_basis": "public_data",
                "csrf": session.csrf_token,
            }, follow_redirects=False)
            assert posted.status_code == 303
            assert posted.headers["location"].startswith("/cases/")

            cases = ctx.team_governance_359.visible_cases(ident)
            assert len(cases) == 1
            case_id = cases[0]["case_id"]
            assert cases[0]["title"] == "First operational public case"
            assert posted.headers["location"] == "/cases/" + case_id

            primary = client.get("/")
            assert primary.status_code == 200
            assert "First operational public case" in primary.text
            assert "Neuen Fall anlegen" in primary.text
            assert "/documents458?case_id=" in primary.text
            assert "/collect469?case_id=" in primary.text
            # Creation stays available for a second distinct operational case.
            assert client.get("/new-case").status_code == 200
    finally:
        ctx.close()
