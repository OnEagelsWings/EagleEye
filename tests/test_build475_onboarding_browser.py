"""Actual first run: launcher -> bootstrap -> login -> regular case -> document."""
import socket
import threading
import time
from urllib.parse import urlencode
import pytest
import uvicorn
from eagleeye.interfaces.web.app475 import create_workspace_app475


def run_onboarding(factory,tmp_path,*,inventory=False,expert=False):
    sync=pytest.importorskip('playwright.sync_api')
    app=factory(base_dir=tmp_path);ctx=app.state.context
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        deadline=time.monotonic()+15
        while not server.started and time.monotonic()<deadline:time.sleep(.05)
        assert server.started
        with sync.sync_playwright() as runtime:
            browser=runtime.chromium.launch();page=browser.new_page(viewport={'width':1280,'height':900})
            base=f'http://127.0.0.1:{port}'
            token=(tmp_path/'data/security_364/local_session_token').read_text().strip()
            assert page.goto(base+'/security/start?'+urlencode({'token':token})).status==200
            page.locator('input[name=username]').fill('operativeqa')
            page.locator('input[name=display_name]').fill('Operational QA')
            page.locator('input[name=password]').fill('Distinct!Secure-Key-2847')
            page.get_by_role('button',name='Systemadministrator anlegen',exact=True).click()
            page.locator('input[name=username]').fill('operativeqa')
            page.locator('input[name=password]').fill('Distinct!Secure-Key-2847')
            page.get_by_role('button',name='Anmelden',exact=True).click()
            page.get_by_role('heading',name='Neuen Ermittlungsfall anlegen',exact=True).wait_for()
            page.locator('[name=title]').fill('Public operational research')
            page.locator('[name=purpose]').fill('Public example domain research with saved evidence.')
            page.locator('[name=legal_basis]').fill('Public sources, own authorized research.')
            with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/cases')) as created:
                page.get_by_role('button',name='Fall anlegen',exact=True).click()
            assert created.value.status==303
            assert created.value.request.headers.get('origin')==base
            assert '/?case_id=' in page.url
            case_url=page.url
            assert 'Legacy Workspace nicht verfügbar' not in page.locator('body').inner_text()
            page.get_by_role('link',name='Dokumente & Quellenprüfung',exact=True).click()
            source=tmp_path/'public-source.txt';source.write_text('Example domains are maintained for documentation purposes.')
            page.locator('input[type=file]').set_input_files(source)
            page.locator('input[name=title]').fill('Public documentation source')
            page.locator('input[name=source_url]').fill('https://www.iana.org/help/example-domains')
            page.locator('#upload button').click()
            page.get_by_text('Public documentation source',exact=False).first.wait_for()
            page.reload()
            page.get_by_text('Public documentation source',exact=False).first.wait_for()
            if inventory:
                page.goto(case_url)
                page.get_by_role('link',name='Geführte Recherche',exact=True).click()
                page.locator('a[href^="/workbench/sources?"]').click()
                assert 'Public documentation source' in page.locator('main').inner_text()
            if expert:
                page.goto(case_url)
                page.get_by_role('link',name='Alle Ermittlungswerkzeuge',exact=True).click()
                page.get_by_role('heading',name='Alle Ermittlungswerkzeuge – Expertenmodus').wait_for()
                page.locator('a[href*="view=dossier"]').first.click()
                page.get_by_role('heading',name='Dossier',exact=True).wait_for()
                assert 'Living-Dossier-Revision' in page.locator('main').inner_text()
                page.get_by_role('link',name='Alle Ermittlungswerkzeuge',exact=True).click()
                page.locator('a[href*="view=analysis"]').first.click()
                page.get_by_role('heading',name='Graph & Timeline',exact=True).wait_for()
                page.goto(base+'/workbench/expert?'+urlencode({'case_id':case_url.split('case_id=')[1]}))
                page.set_viewport_size({'width':390,'height':844})
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.goto(base+'/new-case');page.set_viewport_size({'width':390,'height':844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            assert page.locator('[name=title]').is_visible()
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=10);ctx.close()


def test_fresh_browser_creates_and_uses_regular_case_without_console(tmp_path):
    run_onboarding(create_workspace_app475,tmp_path)
