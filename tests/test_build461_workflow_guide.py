from __future__ import annotations

import hashlib
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app461 import create_workspace_app461
from eagleeye_pro.version import BUILD


def test_build461_authentication_and_case_scoping(tmp_path):
    assert BUILD == "461.0"
    app = create_workspace_app461(base_dir=tmp_path)
    ctx = app.state.context
    try:
        with TestClient(app) as client:
            unauthenticated = client.get("/workflow461", params={"case_id": "forged"}, follow_redirects=False)
            assert unauthenticated.status_code == 303
            assert unauthenticated.headers["location"].startswith("/security/")
        ctx.team_identity_359.create_initial_admin(
            username="admin461", display_name="QA Admin",
            password="Build461!Password_88",
        )
        fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
        issued = ctx.team_identity_359.authenticate(
            username="admin461", password="Build461!Password_88",
            client_fingerprint=fingerprint,
        )
        identity = ctx.team_identity_359.validate_session(
            issued.token, client_fingerprint=fingerprint, touch=False,
        )
        case = ctx.team_governance_359.create_case(
            identity=identity, title="Case <source> 461",
            client="Internal", purpose="Review-first UI navigation",
            legal_basis="public_data",
        )
        with TestClient(app) as client:
            client.cookies.set(COOKIE, issued.token)
            home = client.get("/", params={"case_id": case["case_id"]})
            assert home.status_code == 200
            assert "Ermittlungsweg · Anleitung" in home.text
            guide = client.get("/workflow461", params={"case_id": case["case_id"]})
            assert guide.status_code == 200
            assert guide.headers["cache-control"] == "no-store"
            assert "Case &lt;source&gt; 461" in guide.text
            assert "Case <source> 461" not in guide.text
            assert guide.text.count("case_id=") >= 5
            assert "Keine automatische Rechercheausführung" in guide.text
            forbidden = client.get("/workflow461", params={"case_id": "foreign-case"}, follow_redirects=False)
            assert forbidden.status_code == 303
            assert forbidden.headers["location"] == "/"
            health = client.get("/health").json()
            assert health["build"] == "461.0"
            assert health["production_release_ready"] is False
    finally:
        ctx.close()
