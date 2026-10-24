import json
from pathlib import Path
import socket
import threading
from unittest.mock import patch
import httpx
import pytest
from eagleeye.bootstrap.desktop476 import resolve_workspace,remember_workspace,diagnostics
from eagleeye.interfaces.web import server
from eagleeye_pro.version import BUILD

@pytest.fixture(autouse=True)
def isolated_settings(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_SETTINGS_DIR',str(tmp_path/'settings'))
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'global-data'))
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local-data'))
    monkeypatch.delenv('EAGLEEYE_DATA_DIR',raising=False)
    monkeypatch.delenv('EAGLEEYE_REMOTE_TEAM_ENABLED',raising=False)


def test_existing_data_directory_is_preserved_across_build_folders(tmp_path):
    old=tmp_path/'old-install';(old/'data').mkdir(parents=True)
    (old/'data/eagleeye.db').write_bytes(b'unchanged existing data')
    assert resolve_workspace(old)==old
    assert resolve_workspace(tmp_path/'new-install')==old
    assert (old/'data/eagleeye.db').read_bytes()==b'unchanged existing data'


def test_fresh_install_and_explicit_work_directory_are_stable(tmp_path,monkeypatch):
    first=resolve_workspace(tmp_path/'install-one')
    assert first==resolve_workspace(tmp_path/'install-two')
    selected=tmp_path/'selected work';monkeypatch.setenv('EAGLEEYE_DATA_DIR',str(selected))
    assert resolve_workspace(tmp_path/'install-three')==selected
    monkeypatch.delenv('EAGLEEYE_DATA_DIR')
    assert resolve_workspace(tmp_path/'install-four')==selected


def test_missing_saved_directory_never_becomes_empty_workspace(tmp_path):
    root=remember_workspace(tmp_path/'work');root.rmdir()
    with pytest.raises(ValueError,match='Arbeitsordner fehlt'):resolve_workspace(tmp_path/'new-code')
    assert not root.exists()


def test_unc_directory_is_rejected():
    with pytest.raises(ValueError):remember_workspace('\\\\server\\private')


def test_diagnostics_omit_launcher_tokens(tmp_path):
    folder=tmp_path/'data/security_364';folder.mkdir(parents=True)
    (folder/'local_session_token').write_text('secret-that-must-not-be-in-diagnostic')
    report=diagnostics(tmp_path)
    assert report['server_reachable'] is False
    assert 'secret-that-must-not-be-in-diagnostic' not in json.dumps(report)
    assert report['contains_credentials'] is False


def test_browser_opens_only_after_real_health_and_uses_authorized_entry(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HTTP_PROXY','http://127.0.0.1:1')
    monkeypatch.setenv('http_proxy','http://127.0.0.1:1')
    opened=threading.Event();urls=[];instances=[];errors=[]
    real_server=server.uvicorn.Server
    def factory(config):
        instance=real_server(config);instances.append(instance);return instance
    def open_browser(url,*args):urls.append(url);opened.set();return 'default'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    def launch():
        try:assert server.serve_workspace(base_dir=tmp_path,port=port)==0
        except BaseException as exc:errors.append(exc)
    with patch.object(server.uvicorn,'Server',side_effect=factory),patch.object(server,'open_local_browser',side_effect=open_browser):
        thread=threading.Thread(target=launch,daemon=True);thread.start()
        try:
            assert opened.wait(30),errors
            with httpx.Client(trust_env=False,follow_redirects=True) as client:
                response=client.get(urls[0])
                assert response.status_code==200 and 'Systemadministrator anlegen' in response.text
            report=diagnostics(tmp_path)
            assert report['server_reachable'] and report['build']==BUILD
            token=(tmp_path/'data/security_364/local_session_token').read_text().strip()
            assert token not in json.dumps(report) and token not in capsys.readouterr().out
        finally:
            for instance in instances:instance.should_exit=True
            thread.join(timeout=10)
    assert not thread.is_alive() and not errors
    assert diagnostics(tmp_path)['last_start']['stage']=='stopped'


def test_failed_health_does_not_open_browser(tmp_path):
    with patch.object(server,'_health_ready',return_value=False),patch.object(server,'open_local_browser') as browser:
        assert server._open_browser_when_ready(tmp_path,{'port':12345},'firefox',attempts=1,delay=.02)=='unavailable'
    browser.assert_not_called()
    assert diagnostics(tmp_path)['last_start']['stage']=='health-timeout'


def test_diagnostics_identify_an_older_running_build(tmp_path):
    from http.server import BaseHTTPRequestHandler,HTTPServer
    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.end_headers();self.wfile.write(b'{"ok":true,"build":"475.0"}')
        def log_message(self,*args):pass
    http=HTTPServer(('127.0.0.1',0),Health)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    runtime=tmp_path/'data/runtime_126_0';runtime.mkdir(parents=True)
    (runtime/'workspace.json').write_text(json.dumps({'host':'127.0.0.1','port':http.server_port,'build':'475.0'}))
    try:
        report=diagnostics(tmp_path)
        assert report['version_conflict'] and report['running_build']=='475.0'
        assert not report['server_reachable'] and server._read_running_workspace(tmp_path) is None
    finally:http.shutdown();http.server_close();thread.join(timeout=3)


def test_parallel_starts_do_not_corrupt_workspace_settings(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    root=tmp_path/'shared work'
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _:remember_workspace(root),range(16)))==[root]*16
    assert resolve_workspace(tmp_path/'another-install')==root
    assert not list((tmp_path/'settings').glob('*.tmp'))


def test_existing_workspace_reports_failed_browser_start(tmp_path):
    with patch.object(server,'_read_running_workspace',return_value={'port':12345}), \
            patch.object(server,'open_local_browser',return_value='unavailable'):
        assert not server.open_existing_workspace(base_dir=tmp_path)
    assert diagnostics(tmp_path)['last_start']['stage']=='browser-unavailable'


@pytest.mark.parametrize('location',['installation','previous_default'])
def test_legacy_database_is_discovered_without_silent_new_case_directory(tmp_path,location):
    from eagleeye.bootstrap.paths import default_runtime_root
    install=tmp_path/'install'
    old=install if location=='installation' else default_runtime_root()
    (old/'data').mkdir(parents=True)
    legacy=old/'data/eagleeye_pro_95_0.db';legacy.write_bytes(b'existing legacy source')
    assert resolve_workspace(install)==old
    assert legacy.read_bytes()==b'existing legacy source'
    assert not (old/'data/eagleeye.db').exists()  # canonical migration runs on app startup


def test_qualification_only_workspace_cannot_become_operational_default(tmp_path):
    import hashlib
    from fastapi.testclient import TestClient
    from test_build450_integrated import setup_users,ADMIN_PASSWORD
    from eagleeye.interfaces.web.app476 import create_workspace_app476
    from eagleeye.interfaces.web.app448 import COOKIE
    from eagleeye.interfaces.web.app364 import CSRF_COOKIE
    app=create_workspace_app476(base_dir=tmp_path);ctx=app.state.context
    try:
        _,_,admin,reviewer,*_=setup_users(ctx)
        qualification=ctx.build450.prepare_investigation_workflow_qualification_case_450(
            identity=admin,reviewer_username=reviewer['username'])
        session=ctx.team_identity_359.authenticate(username=admin['username'],password=ADMIN_PASSWORD,
            client_fingerprint=hashlib.sha256(b'testclient||testclient').hexdigest())
        with TestClient(app) as client:
            client.cookies.set(COOKIE,session.token);client.cookies.set(CSRF_COOKIE,session.csrf_token)
            assert client.get('/',follow_redirects=False).headers['location']=='/new-case'
            assert client.get('/workbench',follow_redirects=False).headers['location']=='/new-case'
            assert client.get('/workbench',params={'case_id':qualification['case_id']}).status_code==403
            assert client.get('/new-case').status_code==200
    finally:ctx.close()
