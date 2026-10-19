from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app459 import create_workspace_app459
from eagleeye.interfaces.web.app448 import COOKIE


def test_build459_navigation_resolves_authorized_case(tmp_path):
    app = create_workspace_app459(base_dir=tmp_path)
    ctx = app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="admin459", display_name="Navigation QA", password="Build459!Password_88"
        )
        fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
        issued = ctx.team_identity_359.authenticate(
            username="admin459", password="Build459!Password_88",
            client_fingerprint=fingerprint
        )
        identity = ctx.team_identity_359.validate_session(
            issued.token, client_fingerprint=fingerprint, touch=False
        )
        case = ctx.team_governance_359.create_case(
            identity=identity, title="Navigation QA", client="Internal",
            purpose="Verify document navigation remains case-scoped.",
            legal_basis="public_data"
        )
        with TestClient(app) as client:
            client.cookies.set(COOKIE, issued.token)
            response = client.get("/", params={"case_id": case["case_id"]})
            assert response.status_code == 200
            assert "Build 459.0" in response.text
            assert response.text.count("Dokumente &amp; Quellenprüfung") == 1
            assert "/documents458?case_id=" in response.text
            assert case["case_id"] in response.text
            # UI links must use the actual authorized case, not a forged case ID.
            forged = client.get("/", params={"case_id": "unknown-case"})
            assert forged.status_code == 200
            assert "/documents458?case_id=" in forged.text
            assert "unknown-case" not in forged.text
    finally:
        ctx.close()
