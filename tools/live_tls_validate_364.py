from __future__ import annotations
import http.cookiejar, json, os, socket, ssl, tempfile, threading, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app364 import create_workspace_app364

ADMIN_PW='Orbit-Pine-Quartz-364!'
ANALYST_PW='Copper-Lake-Quartz-364!'


def cert_pair(root:Path):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'127.0.0.1')]); now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(__import__('ipaddress').ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
    cp=root/'cert.pem'; kp=root/'key.pem'; cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM)); kp.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption())); kp.chmod(0o600); return cp,kp

def free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p

def opener(cert:Path,ua:str):
    jar=http.cookiejar.CookieJar(); context=ssl.create_default_context(cafile=str(cert)); op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(jar)); op.addheaders=[('User-Agent',ua),('Accept-Language','de-DE')]; return op

def post_form(op,url,data):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'}); return op.open(req,timeout=4)

def main():
    root=Path(__file__).resolve().parents[1]; receipt=root/'LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json'
    with tempfile.TemporaryDirectory(prefix='ee364-tls-') as td:
        td=Path(td); base=td/'workspace'; cp,kp=cert_pair(td); port=free_port()
        with AppContext(base_dir=base) as c:
            a=c.team_identity_359.create_initial_admin(username='admin364',display_name='Admin User',password=ADMIN_PW); ident={**a,'session_id':'bootstrap-live364'}
            ca=c.build364.team_create_case(identity=ident,title='TLS A',client='QA',purpose='authorized public research',legal_basis='public_data')
            cb=c.build364.team_create_case(identity=ident,title='TLS B',client='QA',purpose='authorized public research',legal_basis='public_data')
            c.build364.team_create_user(identity=ident,username='analyst364',display_name='Analyst User',global_role='investigator',password=ANALYST_PW)
            c.build364.assign_case_role(identity=ident,case_id=ca['case_id'],username='analyst364',case_role='analyst',notes='Live TLS qualification')
        env={
            'EAGLEEYE_REMOTE_TEAM_ENABLED':'1','EAGLEEYE_REMOTE_BIND_HOST':'127.0.0.1','EAGLEEYE_REMOTE_ALLOWED_HOSTS':'127.0.0.1',
            'EAGLEEYE_REMOTE_ALLOWED_CIDRS':'127.0.0.0/8','EAGLEEYE_REMOTE_TLS_CERT':str(cp),'EAGLEEYE_REMOTE_TLS_KEY':str(kp),'EAGLEEYE_REMOTE_PUBLIC_ORIGIN':f'https://127.0.0.1:{port}'
        }
        old={k:os.environ.get(k) for k in env}; os.environ.update(env)
        server=None
        try:
            app=create_workspace_app364(base_dir=base)
            config=uvicorn.Config(app,host='127.0.0.1',port=port,log_level='critical',access_log=False,proxy_headers=False,ssl_certfile=str(cp),ssl_keyfile=str(kp))
            server=uvicorn.Server(config); thread=threading.Thread(target=server.run,daemon=True); thread.start()
            for _ in range(80):
                if server.started: break
                time.sleep(.05)
            if not server.started: raise RuntimeError('TLS server did not start')
            url=f'https://127.0.0.1:{port}'
            aop=opener(cp,'EagleEye-Live-Admin/364'); bop=opener(cp,'EagleEye-Live-Analyst/364')
            health=json.loads(aop.open(url+'/health',timeout=4).read().decode())
            post_form(aop,url+'/security/login',{'username':'admin364','password':ADMIN_PW}).read()
            post_form(bop,url+'/security/login',{'username':'analyst364','password':ANALYST_PW}).read()
            own=bop.open(url+f"/api/cases/{ca['case_id']}/team",timeout=4); own_status=own.status
            denied=0
            try: bop.open(url+f"/api/cases/{cb['case_id']}/team",timeout=4)
            except urllib.error.HTTPError as exc: denied=exc.code
            dash=json.loads(aop.open(url+'/api/build364',timeout=4).read().decode())
            passed=health.get('build')=='364.0' and health.get('remote_team_mode') is True and own_status==200 and denied==403 and dash.get('build')=='364.0'
            out={'build':'364.0','status':'pass' if passed else 'fail','transport':'real_loopback_tls','tls_handshake_verified_against_generated_ca':True,'clients':2,'users':2,'cases':2,'cross_case_denial_http_status':denied,'external_remote_clients_validated':False,'externally_validated':False,'proxy_headers_trusted':False,'truthful_note':'Real TLS transport and two independent authenticated clients were validated on loopback. This is not external remote-network validation.'}
            receipt.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2,sort_keys=True))
            if not passed: raise SystemExit(1)
        finally:
            if server is not None: server.should_exit=True; time.sleep(.15)
            for k,v in old.items():
                if v is None: os.environ.pop(k,None)
                else: os.environ[k]=v

if __name__=='__main__': main()
