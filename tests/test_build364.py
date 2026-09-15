from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from eagleeye_pro.core.app_context import AppContext

ADMIN_PW="Orbit-Pine-Quartz-364!"
ANALYST_PW="Copper-Lake-Quartz-364!"
REVIEWER_PW="Velvet-River-Quartz-364!"


def ctx(tmp_path): return AppContext(base_dir=tmp_path, actor="test364")

def admin(c):
    u=c.team_identity_359.create_initial_admin(username="admin364",display_name="Admin User",password=ADMIN_PW)
    return {**u,"session_id":"test-admin-364"}

def case(c,a,title="Remote Team Case"):
    return c.build364.team_create_case(identity=a,title=title,client="QA",purpose="authorized public research",legal_basis="public_data")

def add(c,a,cid,username,display,global_role,case_role,password):
    c.build364.team_create_user(identity=a,username=username,display_name=display,global_role=global_role,password=password)
    return c.build364.assign_case_role(identity=a,case_id=cid,username=username,case_role=case_role,notes="Build 364 remote-team qualification")

def cert_pair(root: Path, host: str="eagleeye.test"):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,host)])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=2)).add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]),critical=False).sign(key,hashes.SHA256()))
    cp=root/'tls.crt'; kp=root/'tls.key'
    cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    kp.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
    try: kp.chmod(0o600)
    except OSError: pass
    return cp,kp

def set_remote(monkeypatch,tmp_path,*,host="eagleeye.test",cidr="10.23.0.0/24",bind="10.23.0.1"):
    cp,kp=cert_pair(tmp_path,host)
    monkeypatch.setenv('EAGLEEYE_REMOTE_TEAM_ENABLED','1')
    monkeypatch.setenv('EAGLEEYE_REMOTE_BIND_HOST',bind)
    monkeypatch.setenv('EAGLEEYE_REMOTE_ALLOWED_HOSTS',host)
    monkeypatch.setenv('EAGLEEYE_REMOTE_ALLOWED_CIDRS',cidr)
    monkeypatch.setenv('EAGLEEYE_REMOTE_TLS_CERT',str(cp))
    monkeypatch.setenv('EAGLEEYE_REMOTE_TLS_KEY',str(kp))
    monkeypatch.setenv('EAGLEEYE_REMOTE_PUBLIC_ORIGIN',f'https://{host}:8765')
    return cp,kp


def test_version_schema(tmp_path):
    with ctx(tmp_path) as c:
        assert c.build364.version_status()=={'runtime_build':'364.0','schema_version':'364.0','package_version':'364.0.0','coherent':True}
        m=c.build364.schema_metrics(); assert m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)


def test_default_is_local_not_external(tmp_path,monkeypatch):
    monkeypatch.delenv('EAGLEEYE_REMOTE_TEAM_ENABLED',raising=False)
    with ctx(tmp_path) as c:
        s=c.build364.remote_team_status(); assert s['mode']=='local' and not s['remote_enabled'] and not s['externally_validated']


def test_remote_config_requires_complete_tls(tmp_path,monkeypatch):
    monkeypatch.setenv('EAGLEEYE_REMOTE_TEAM_ENABLED','1'); monkeypatch.setenv('EAGLEEYE_REMOTE_BIND_HOST','10.1.2.3')
    with ctx(tmp_path) as c:
        r=c.build364.remote_config_validation(load_cert_chain=False); assert not r['valid'] and r['status']=='blocked'


def test_remote_config_validates_real_cert_pair(tmp_path,monkeypatch):
    set_remote(monkeypatch,tmp_path)
    with ctx(tmp_path) as c:
        r=c.build364.remote_config_validation(load_cert_chain=True); assert r['valid'] and r['tls_configured'] and not r['proxy_headers_trusted']


def test_wildcard_bind_is_blocked(tmp_path,monkeypatch):
    set_remote(monkeypatch,tmp_path,bind='0.0.0.0')
    with ctx(tmp_path) as c:
        r=c.build364.remote_config_validation(load_cert_chain=False); assert not r['valid'] and any('wildcard' in x for x in r['errors'])


def test_remote_request_allows_direct_https_allowlist(tmp_path,monkeypatch):
    set_remote(monkeypatch,tmp_path)
    with ctx(tmp_path) as c:
        r=c.build364.remote_request_decision(scheme='https',host_header='eagleeye.test:8765',client_ip='10.23.0.8',forwarded_headers_present=False); assert r['allowed']


def test_remote_request_rejects_http_host_cidr_and_forwarded(tmp_path,monkeypatch):
    set_remote(monkeypatch,tmp_path)
    with ctx(tmp_path) as c:
        assert c.build364.remote_request_decision(scheme='http',host_header='eagleeye.test',client_ip='10.23.0.8')['reason']=='https_required'
        assert c.build364.remote_request_decision(scheme='https',host_header='evil.test',client_ip='10.23.0.8')['reason']=='host_not_allowlisted'
        assert c.build364.remote_request_decision(scheme='https',host_header='eagleeye.test',client_ip='10.99.0.8')['reason']=='client_network_not_allowlisted'
        assert c.build364.remote_request_decision(scheme='https',host_header='eagleeye.test',client_ip='10.23.0.8',forwarded_headers_present=True)['reason']=='untrusted_forwarding_headers'


def test_remote_contract_does_not_claim_external(tmp_path):
    with ctx(tmp_path) as c:
        r=c.build364.remote_contract_validation(clients=3,cases=2,violations=0); assert r['contract_validated'] and not r['externally_validated']


def test_loopback_tls_receipt_not_external(tmp_path):
    with ctx(tmp_path) as c:
        r=c.build364.loopback_tls_validation_receipt(passed=True,external_remote_clients=False); assert r['loopback_tls_live_validated'] and not r['externally_validated']


def test_cross_case_rbac_isolation(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,'A'); cb=case(c,a,'B')
        add(c,a,ca['case_id'],'analyst364','Analyst User','investigator','analyst',ANALYST_PW)
        c.build364.authorize('analyst364',case_id=ca['case_id'],capability='case.read')
        with pytest.raises(PermissionError): c.build364.authorize('analyst364',case_id=cb['case_id'],capability='case.read')


def test_visible_cases_filtered(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,'A'); case(c,a,'B')
        add(c,a,ca['case_id'],'analyst364','Analyst User','investigator','analyst',ANALYST_PW)
        visible=c.build364.visible_cases('analyst364'); assert [x['case_id'] for x in visible]==[ca['case_id']]


def test_session_fingerprint_mismatch_revokes(tmp_path):
    with ctx(tmp_path) as c:
        admin(c); issued=c.team_identity_359.authenticate(username='admin364',password=ADMIN_PW,client_fingerprint='client-a')
        assert c.team_identity_359.validate_session(issued.token,client_fingerprint='client-a',touch=False)
        r=c.build364.protect_remote_session(token=issued.token,observed_fingerprint='client-b',observed_ip='10.23.0.9')
        assert r['blocked'] and r['state']=='revoked'
        assert c.team_identity_359.validate_session(issued.token,client_fingerprint='client-a',touch=False) is None


def test_session_same_fingerprint_survives(tmp_path):
    with ctx(tmp_path) as c:
        admin(c); issued=c.team_identity_359.authenticate(username='admin364',password=ADMIN_PW,client_fingerprint='client-a')
        r=c.build364.protect_remote_session(token=issued.token,observed_fingerprint='client-a'); assert not r['blocked'] and r['state']=='consistent'


def test_opsec_denial_burst_revokes_session(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); ca=case(c,a,'A'); cb=case(c,a,'B')
        add(c,a,ca['case_id'],'analyst364','Analyst User','investigator','analyst',ANALYST_PW)
        issued=c.team_identity_359.authenticate(username='analyst364',password=ANALYST_PW,client_fingerprint='remote-a')
        ident=c.team_identity_359.validate_session(issued.token,client_fingerprint='remote-a',touch=False); assert ident
        for _ in range(5):
            with pytest.raises(PermissionError): c.build364.authorize(ident,case_id=cb['case_id'],capability='case.read')
        out=c.build364.autonomous_opsec_protect(case_id=cb['case_id']); assert issued.session_id in out['remote_sessions_revoked']
        assert c.team_identity_359.validate_session(issued.token,client_fingerprint='remote-a',touch=False) is None


def test_ai_requires_go(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; assert c.build364.run_autonomous_investigation(case_id=cid)['state']=='go_required'


def test_ai_dossier_contains_remote_context(tmp_path):
    with ctx(tmp_path) as c:
        a=admin(c); cid=case(c,a)['case_id']; c.build364.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What is supported?']); c.build364.start_investigation_go(case_id=cid,go='GO')
        out=c.build364.run_autonomous_investigation(case_id=cid,max_ticks=1); d=out['dossier']; assert d['lead_review_required'] and d['phase16_remote_team_context']['cross_case_default_deny']


def test_opsec_status_has_no_system_mutation(tmp_path):
    with ctx(tmp_path) as c:
        s=c.opsec_supervisor_364.status(); assert s['remote_session_anomaly_monitor'] and s['session_revocation_allowed'] and not s['system_mutations'] and not s['firewall_mutation']


def test_crawler_improvement(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build364.crawler_status(); assert s['crawler_improvement_build']==364 and s['remote_rbac_context_required'] and s['cross_case_default_deny']


def test_phase16_status(tmp_path):
    with ctx(tmp_path) as c:
        s=c.build364.phase16_status(); assert s['phase']=='16' and s['build']=='364.0' and s['builds_completed']==4


def test_capabilities_do_not_claim_external(tmp_path):
    with ctx(tmp_path) as c:
        caps={x['key']:x for x in c.build364.capabilities()}; assert not caps['remote_multi_user_team_v364']['states']['externally_validated']


def test_production_false(tmp_path):
    with ctx(tmp_path) as c: assert c.build364.qualified_gate()['production_release_ready'] is False


def test_no_literal_true_gate(tmp_path):
    with ctx(tmp_path) as c: assert c.build364.active_gate_literal_true_lines()==[]


def test_new_modules_no_direct_http_or_subprocess_imports():
    names=set()
    for p in [Path('src/eagleeye/phase16/remote_team364.py'),Path('src/eagleeye/application/build364/service.py')]:
        tree=ast.parse(p.read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): names.update(x.name.split('.')[0] for x in n.names)
            elif isinstance(n,ast.ImportFrom) and n.module:names.add(n.module.split('.')[0])
    assert not names.intersection({'requests','httpx','aiohttp','urllib','socket','subprocess'})


def test_local_web_health_and_auth(tmp_path,monkeypatch):
    monkeypatch.delenv('EAGLEEYE_REMOTE_TEAM_ENABLED',raising=False)
    from eagleeye.interfaces.web.app364 import create_workspace_app364
    root=tmp_path/'localweb'; app=create_workspace_app364(base_dir=root)
    with TestClient(app) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()['build']=='364.0' and not h.json()['remote_team_mode']
        assert client.get('/api/build364').status_code==401
        token=(root/'data/security_364/local_session_token').read_text().strip()
        assert client.get('/security/start',params={'token':token},follow_redirects=False).status_code==303


def test_remote_web_requires_https_and_allows_direct_login(tmp_path,monkeypatch):
    # Bootstrap locally before remote mode is enabled.
    root=tmp_path/'remoteweb'
    with AppContext(base_dir=root) as c: c.team_identity_359.create_initial_admin(username='admin364',display_name='Admin User',password=ADMIN_PW)
    set_remote(monkeypatch,tmp_path,host='eagleeye.test',cidr='10.23.0.0/24')
    from eagleeye.interfaces.web.app364 import create_workspace_app364
    app=create_workspace_app364(base_dir=root)
    with TestClient(app,base_url='https://eagleeye.test',client=('10.23.0.9',50000)) as client:
        h=client.get('/health'); assert h.status_code==200 and h.json()['remote_team_mode']
        assert h.headers.get('strict-transport-security')
        assert client.get('/security/start',params={'token':'x'}).status_code==403
        assert client.get('/security/login').status_code==200
        r=client.post('/security/login',data={'username':'admin364','password':ADMIN_PW},follow_redirects=False); assert r.status_code==303
        assert 'Secure' in r.headers.get('set-cookie','')
        assert client.get('/api/build364').status_code==200


def test_remote_web_blocks_forwarded_headers(tmp_path,monkeypatch):
    root=tmp_path/'remoteweb2'
    with AppContext(base_dir=root) as c: c.team_identity_359.create_initial_admin(username='admin364',display_name='Admin User',password=ADMIN_PW)
    set_remote(monkeypatch,tmp_path,host='eagleeye.test',cidr='10.23.0.0/24')
    from eagleeye.interfaces.web.app364 import create_workspace_app364
    app=create_workspace_app364(base_dir=root)
    with TestClient(app,base_url='https://eagleeye.test',client=('10.23.0.9',50000),headers={'X-Forwarded-For':'1.2.3.4'}) as client:
        r=client.get('/health'); assert r.status_code==403 and r.json()['reason']=='untrusted_forwarding_headers'
