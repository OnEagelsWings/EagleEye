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
