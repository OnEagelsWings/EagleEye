"""Current Build-500 Windows login recovery: no legacy-suite execution."""
from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app500 import create_workspace_app500


def test_current_build500_bootstrap_repeat_redirects_to_login(tmp_path: Path):
    app = create_workspace_app500(base_dir=tmp_path)
    try:
        with TestClient(app) as client:
            token = (tmp_path / "data/security_364/local_session_token").read_text().strip()
            initial = client.get("/security/start", params={"token": token}, follow_redirects=True)
            assert initial.status_code == 200
            assert "Systemadministrator anlegen" in initial.text
            form = {"username": "pilotadmin", "display_name": "Pilot Admin", "password": "a-Long-Test-Password2026!"}
            created = client.post("/security/bootstrap", data=form, follow_redirects=True)
            assert created.status_code == 200
            assert "Anmelden" in created.text
            repeated = client.post("/security/bootstrap", data=form, follow_redirects=False)
            assert repeated.status_code == 303
            assert repeated.headers["location"] == "/security/login"
            assert "Bootstrap unavailable" not in repeated.text
            assert client.get("/security/bootstrap", follow_redirects=False).headers["location"] == "/security/login"
            login = client.post("/security/login", data={"username": form["username"], "password": form["password"]}, follow_redirects=False)
            assert login.status_code == 303
            assert login.headers["location"] == "/"
    finally:
        app.state.context.close()


def test_current_build500_bootstrap_denies_missing_launcher_without_json(tmp_path: Path):
    app = create_workspace_app500(base_dir=tmp_path)
    try:
        with TestClient(app) as client:
            response = client.post("/security/bootstrap", data={"username": "test", "display_name": "Test", "password": "secret"}, follow_redirects=False)
            assert response.status_code == 403
            assert "text/html" in response.headers["content-type"]
            assert "START_EAGLEEYE_PRO.bat" in response.text
            assert not app.state.context.team_identity_359.list_users()
    finally:
        app.state.context.close()
