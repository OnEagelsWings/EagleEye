from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye_pro.version import BUILD
from eagleeye.interfaces.web.app460 import create_workspace_app460


def test_build460_launcher_version_and_health_contract(tmp_path):
    assert BUILD == "460.0"
    root = Path(__file__).resolve().parents[1]
    assert 'INSTALL_EAGLEEYE_460.py' in (root / 'START_EAGLEEYE_PRO.sh').read_text()
    assert 'INSTALL_EAGLEEYE_460.py' in (root / 'START_EAGLEEYE_PRO.bat').read_text()
    assert 'INSTALL_EAGLEEYE_460.py' in (root / 'INSTALL_EAGLEEYE_PRO.sh').read_text()
    assert 'INSTALL_EAGLEEYE_460.py' in (root / 'INSTALL_EAGLEEYE_PRO.bat').read_text()
    assert 'create_workspace_app460' in (root / 'src/eagleeye/interfaces/web/server.py').read_text()
    app = create_workspace_app460(base_dir=tmp_path)
    try:
        with TestClient(app) as client:
            health = client.get('/health')
            assert health.status_code == 200
            assert health.json()['build'] == BUILD
            assert 'integrity_valid' in health.json()
            assert health.json()['status'] in ('hold', 'ok')
            assert health.json()['production_release_ready'] is False
            home = client.get('/', follow_redirects=False)
            assert home.status_code == 303
    finally:
        app.state.context.close()


def test_build460_preserves_user_text_while_displaying_current_identity(tmp_path):
    import hashlib

    from eagleeye.interfaces.web.app448 import COOKIE

    app = create_workspace_app460(base_dir=tmp_path)
    ctx = app.state.context
    try:
        ctx.team_identity_359.create_initial_admin(
            username="admin460", display_name="Build 460 QA", password="Build460!Password_88"
        )
        fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
        session = ctx.team_identity_359.authenticate(
            username="admin460", password="Build460!Password_88", client_fingerprint=fingerprint
        )
        identity = ctx.team_identity_359.validate_session(
            session.token, client_fingerprint=fingerprint, touch=False
        )
        original_title = "Build 459.0 Investigator Navigation"
        case = ctx.team_governance_359.create_case(
            identity=identity, title=original_title, client="Internal",
            purpose="Verify that UI metadata never rewrites stored investigation text.",
            legal_basis="public_data",
        )
        with TestClient(app) as client:
            client.cookies.set(COOKIE, session.token)
            response = client.get("/", params={"case_id": case["case_id"]})
            assert response.status_code == 200
            assert "<small>Build 460.0 · Full Regression Checkpoint</small>" in response.text
            assert original_title in response.text
            assert "Build 460.0 Full Regression Checkpoint" not in response.text
    finally:
        ctx.close()
