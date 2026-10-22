"""Real Chromium acceptance. Requires the optional Playwright test runtime."""
import json
import socket
import threading
import time
from urllib.parse import urlencode

import pytest
import uvicorn

from eagleeye.interfaces.web.app471 import create_workspace_app471


def test_real_browser_summary_review_anchor_and_mobile(tmp_path):
    sync = pytest.importorskip('playwright.sync_api')
    app = create_workspace_app471(base_dir=tmp_path)
    ctx = app.state.context
    password = 'Acceptance!Secret_88'
    ctx.team_identity_359.create_initial_admin(username='browser471', display_name='Browser QA', password=password)
    session = ctx.team_identity_359.authenticate(username='browser471', password=password, client_fingerprint='setup')
    user = ctx.team_identity_359.validate_session(session.token, client_fingerprint='setup', touch=False)
    case = ctx.team_governance_359.create_case(identity=user, title='Browser QA Build 471', client='Synthetic',
        purpose='Synthetic browser acceptance', legal_basis='public_data')
    doc = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case['case_id'], filename='source.txt',
        raw=b'The synthetic company was founded in 2001.', title='Browser Source', source_url='https://example.org/source')
    source = app.state.assistant471.sources(user, case['case_id'], [doc['document_id']])[0]
    def model(method, path, payload=None, **kwargs):
        if path == '/api/tags': return {'models': [{'name': 'mistral:latest', 'digest': 'a'*64}]}
        if path == '/api/show': return {'capabilities': ['completion']}
        if path == '/api/chat': return {'message': {'content': json.dumps({
            'statements': [{'text': 'Die Quelle nennt das Gründungsjahr 2001.', 'citations': [
                {'anchor_id': source['anchor_id'], 'quote': 'company was founded in 2001.'}]}],
            'uncertainties': ['Die Angabe ist nicht unabhängig bestätigt.']})}}
        raise AssertionError(path)
    app.state.assistant471.request = model
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        with sync.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = f'http://127.0.0.1:{port}'
            launch_token = (tmp_path/'data/security_364/local_session_token').read_text().strip()
            response = page.goto(base + '/security/start?' + urlencode({'token': launch_token}))
            assert response.status == 200
            page.locator('input[name=username]').fill('browser471')
            page.locator('input[name=password]').fill(password)
            page.get_by_role('button', name='Anmelden', exact=True).click()
            page.goto(base + '/?case_id=' + case['case_id'])
            page.get_by_role('link', name='Lokaler KI-Ermittler', exact=True).click()
            page.locator('input[name=document_id]').first.check()
            page.get_by_role('button', name='Auswahl lokal zusammenfassen', exact=True).click()
            page.get_by_text('Die Quelle nennt das Gründungsjahr 2001.', exact=True).wait_for()
            page.locator('textarea[name=note]').fill('Im Original gelesen; Unsicherheiten bleiben bestehen.')
            page.get_by_role('button', name='Prüfentscheidung speichern', exact=True).click()
            page.get_by_text('KI-Vorschlag · acknowledged', exact=True).wait_for()
            page.reload()
            page.get_by_text('Im Original gelesen; Unsicherheiten bleiben bestehen.', exact=True).wait_for()
            page.screenshot(path=str(tmp_path/'build471-desktop.png'), full_page=True)
            page.get_by_role('link', name='Browser Source', exact=False).click()
            assert page.locator('[id="anchor-'+source['anchor_id']+'"]').count() == 1
            page.go_back()
            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
            page.screenshot(path=str(tmp_path/'build471-mobile.png'), full_page=True)
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        ctx.close()
