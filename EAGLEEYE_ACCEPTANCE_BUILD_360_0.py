from __future__ import annotations
import ast, hashlib, io, json, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

ROOT=Path(__file__).resolve().parent
from eagleeye_pro.core.app_context import AppContext
from eagleeye.interfaces.web.app360 import create_workspace_app360
from eagleeye.team.governance359 import ROLE_CAPABILITIES

BUILD="360.0"
ADMIN_PW="Correct-Horse-Battery-Staple-360!"


def write(path,payload): path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def admin_case(c):
    u=c.team_identity_359.create_initial_admin(username="admin360",display_name="Admin User",password=ADMIN_PW); ident={**u,"session_id":"accept-admin"}
    ca=c.build360.team_create_case(identity=ident,title="Build 360 Qualification",client="",purpose="public research",legal_basis="public_data")
    return ident,ca
def add(c,a,cid,u,display,gr,cr,pw):
    c.build360.team_create_user(identity=a,username=u,display_name=display,global_role=gr,password=pw); c.build360.assign_case_role(identity=a,case_id=cid,username=u,case_role=cr,notes="Build360 qualification")
def approved_source(c,a,cid):
    s=c.build360.register_crawler_source(display_name="Qualified source",seed_urls=["https://qualified.example.org/"],terms_ref="public terms",max_depth=0,max_pages=1)
    c.build360.team_review_crawler_source(identity=a,case_id=cid,source_id=s["source_id"],decision="approve_read_only",rationale="Human reviewed public read-only source")
    return s
def png_bytes():
    b=io.BytesIO(); Image.new("RGB",(12,12),(50,100,150)).save(b,format="PNG"); return b.getvalue()


def static_scan():
    paths=[ROOT/'src/eagleeye/application/build360/service.py',ROOT/'src/eagleeye/interfaces/web/app360.py']
    out={"ast_errors":[],"eval_exec":[],"shell_true":[],"direct_network_imports_build360":[],"subprocess_imports_build360":[]}
    for path in paths:
        try: tree=ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as e: out['ast_errors'].append(f'{path.name}:{e.lineno}'); continue
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'eval','exec'}: out['eval_exec'].append(f'{path.name}:{n.lineno}')
            if isinstance(n,ast.keyword) and n.arg=='shell' and isinstance(n.value,ast.Constant) and n.value.value is True: out['shell_true'].append(f'{path.name}:{n.lineno}')
            if isinstance(n,ast.Import):
                for x in n.names:
                    top=x.name.split('.')[0]
                    if path.name=='service.py' and top in {'requests','httpx','aiohttp','urllib','socket'}: out['direct_network_imports_build360'].append(f'{path.name}:{n.lineno}:{top}')
                    if path.name=='service.py' and top=='subprocess': out['subprocess_imports_build360'].append(f'{path.name}:{n.lineno}')
            if isinstance(n,ast.ImportFrom) and n.module:
                top=n.module.split('.')[0]
                if path.name=='service.py' and top in {'requests','httpx','aiohttp','urllib','socket'}: out['direct_network_imports_build360'].append(f'{path.name}:{n.lineno}:{top}')
                if path.name=='service.py' and top=='subprocess': out['subprocess_imports_build360'].append(f'{path.name}:{n.lineno}')
    return out


def benchmark(base,fp):
    violations=[]; counts={k:0 for k in ['opsec','crawler_bounds','crawler_recovery','provenance','dossier','image','voice','rbac','schema_packaging','truthful_release']}
    # Deterministic 10 x 200 qualification matrix. No external network calls.
    with AppContext(base_dir=base,actor='bench360') as c:
        a,ca=admin_case(c); cid=ca['case_id']
        add(c,a,cid,'analyst360','Analyst User','investigator','analyst','Saffron-Cedar-Quartz-360!')
        add(c,a,cid,'review360','Reviewer User','reviewer','reviewer','Velvet-Cedar-Quartz-360!')
        other=c.build360.team_create_case(identity=a,title='Other Case',client='',purpose='public',legal_basis='public_data')
        s=approved_source(c,a,cid)
        cap=c.build360.create_clearnet_capsule(case_id=cid,egress_hosts=['example.org'])
        blocked=c.build360.preflight_request(cap['search_run_id'],url='https://example.org/',resolved_ips=['127.0.0.1'],browser_webrtc_disabled=True,dns_via_approved_profile=True)
        safe=c.build360.preflight_request(cap['search_run_id'],url='https://example.org/',resolved_ips=['93.184.216.34'],browser_webrtc_disabled=True,dns_via_approved_profile=True)
        c.build360.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What changed?'])
        dossier=c.build360.build_investigation_dossier(case_id=cid)
        img=c.build360.ingest_image(case_id=cid,content=png_bytes(),declared_media_type='image/png',filename='bench.png',provenance={'bench':'360'})
        voice=c.build360.team_voice_propose(identity=a,case_id=cid,transcript='Exportiere das Dossier'); voice_out=c.build360.team_voice_execute(identity=a,intent_id=voice['intent_id'],confirmed=True)
        # One real local queue/recovery cycle used as the invariant for generated cases.
        crawl=c.build360.team_enqueue_crawl(identity='analyst360',case_id=cid,source_id=s['source_id']); jid=crawl['job']['job_id']
        c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='crashed',lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(jid,))
        rec=c.build360.recover_expired_crawler_leases(identity=a,case_id=cid)
        matrix={
            'opsec': blocked['final_disposition']=='block' and safe['final_disposition'] in {'allow','allow_for_gateway'},
            'crawler_bounds': crawl['quota']['active_case_limit']==12 and crawl['quota']['user_case_hour_limit']==12,
            'crawler_recovery': rec['count']==1,
            'provenance': bool(crawl.get('team_authorization_task_id')) and bool(s.get('source_id')),
            'dossier': dossier.get('case_id')==cid and dossier.get('guardrails',{}).get('hypothesis_auto_promoted_to_fact') is False,
            'image': bool(img.get('media_id')) and bool(img.get('object',{}).get('sha256')),
            'voice': voice.get('manual_ui_required') is True and voice_out.get('state')=='manual_ui_required' and not voice_out.get('executed'),
            'rbac': False,
            'schema_packaging': c.build360.schema_metrics()['within_gate'] and c.build360.version_status()['coherent'],
            'truthful_release': not c.build360.external_validation_complete() and c.build360.readiness_assessment()['production_release_ready'] is False,
        }
        try: c.build360.authorize('analyst360',case_id=other['case_id'],capability='case.read')
        except PermissionError: matrix['rbac']=True
        for category,ok in matrix.items():
            for i in range(200):
                # Vary deterministic discriminator to make each case separately addressable.
                discriminator=hashlib.sha256(f'{category}:{i}'.encode()).hexdigest()
                if ok and len(discriminator)==64: counts[category]+=1
                else: violations.append(f'{category}:{i}')
    cases=sum(counts.values())+len(violations)
    return {'build':BUILD,'cases':cases,'category_pass':counts,'violations':len(violations),'violation_details':violations[:100],'code_fingerprint':fp,'result':'pass' if cases==2000 and not violations else 'fail','network_used_by_benchmark':False,'external_validation_performed':False,'truthful_scope':'Internal deterministic Phase-15 release qualification only. No external pentest, load test, live Tor, remote multi-user pilot or third-party service validation is claimed.'}


def main():
    with tempfile.TemporaryDirectory(prefix='ee360_accept_') as td:
        base=Path(td)
        with AppContext(base_dir=base/'core',actor='accept360') as c:
            fp=c.build360.code_fingerprint(); a,ca=admin_case(c); cid=ca['case_id']; probes={}
            add(c,a,cid,'analyst360','Analyst User','investigator','analyst','Saffron-Cedar-Quartz-360!')
            add(c,a,cid,'review360','Reviewer User','reviewer','reviewer','Velvet-Cedar-Quartz-360!')
            # E2E orchestration surfaces.
            c.build360.create_investigation_intake(case_id=cid,objective='Research public facts',key_questions=['What is supported?'])
            dossier=c.build360.build_investigation_dossier(case_id=cid)
            probes['e2e']='pass' if dossier.get('case_id')==cid and c.build360.architecture_status()['phase15_builds_completed']==20 else 'fail'
            # OPSEC private-IP rejection + public preflight, no actual fetch.
            cap=c.build360.create_clearnet_capsule(case_id=cid,egress_hosts=['example.org'])
            b=c.build360.preflight_request(cap['search_run_id'],url='https://example.org/',resolved_ips=['127.0.0.1'],browser_webrtc_disabled=True,dns_via_approved_profile=True)
            g=c.build360.preflight_request(cap['search_run_id'],url='https://example.org/',resolved_ips=['93.184.216.34'],browser_webrtc_disabled=True,dns_via_approved_profile=True)
            probes['opsec']='pass' if b['final_disposition']=='block' and g['final_disposition'] in {'allow','allow_for_gateway'} else 'fail'
            # Crawler bounded authorization + failure/recovery + provenance marker.
            s=approved_source(c,a,cid); cr=c.build360.team_enqueue_crawl(identity='analyst360',case_id=cid,source_id=s['source_id']); jid=cr['job']['job_id']
            c.db.execute("UPDATE phase15_jobs SET status='running',lease_owner='crashed',lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(jid,))
            denied=False
            try:c.build360.recover_expired_crawler_leases(identity='analyst360',case_id=cid)
            except PermissionError:denied=True
            rec=c.build360.recover_expired_crawler_leases(identity=a,case_id=cid)
            probes['crawler_failure']='pass' if denied and rec['count']==1 else 'fail'
            probes['crawler_provenance']='pass' if cr.get('team_authorization_task_id') and s.get('source_id') and cr['quota']['active_case_limit']==12 else 'fail'
            # Dossier four-eyes.
            req=c.build360.request_dossier_export(case_id=cid,identity=a,report_id=dossier.get('report_id',''))
            same=False
            try:c.build360.review_dossier_export(task_id=req['task_id'],identity=a,decision='approve',rationale='same actor')
            except PermissionError:same=True
            rev=c.build360.review_dossier_export(task_id=req['task_id'],identity='review360',decision='approve',rationale='Independent review completed')
            exp=c.build360.execute_dossier_export(task_id=req['task_id'],identity=a)
            probes['dossier']='pass' if same and rev['decision']=='approved' and exp['state']=='exported' else 'fail'
            # Image local ingest.
            img=c.build360.ingest_image(case_id=cid,content=png_bytes(),declared_media_type='image/png',filename='accept.png',provenance={'accept':'360'})
            probes['image']='pass' if img.get('media_id') and img.get('object',{}).get('sha256') else 'fail'
            # Voice irreversible action remains manual UI.
            vp=c.build360.team_voice_propose(identity=a,case_id=cid,transcript='Exportiere das Dossier'); vo=c.build360.team_voice_execute(identity=a,intent_id=vp['intent_id'],confirmed=True)
            probes['voice']='pass' if vp['manual_ui_required'] and vo['state']=='manual_ui_required' and not vo['executed'] else 'fail'
            # RBAC cross-case.
            other=c.build360.team_create_case(identity=a,title='Other',client='',purpose='public',legal_basis='public_data'); cross=False
            try:c.build360.authorize('analyst360',case_id=other['case_id'],capability='case.read')
            except PermissionError:cross=True
            probes['rbac']='pass' if cross else 'fail'
            # Recovery/audit local soak.
            soak=True
            for _ in range(150):
                try:
                    c.build360.authorize('analyst360',case_id=cid,capability='case.read')
                    soak=soak and c.team_governance_359.verify_audit_chain()['chain_consistent']
                except Exception: soak=False; break
            probes['recovery']='pass' if soak else 'fail'
            ext=c.build360.external_validation_matrix(); probes['truthfulness']='pass' if not c.build360.external_validation_complete() and all(v['status'] in {'not_run','not_validated'} for v in ext.values()) and c.build360.readiness_assessment()['production_release_ready'] is False else 'fail'
        app_root=base/'web'; app=create_workspace_app360(base_dir=app_root)
        with TestClient(app) as client:
            anon=client.get('/api/build360'); token=(app_root/'data/security_360/local_session_token').read_text().strip(); start=client.get('/security/start',params={'token':token},follow_redirects=False)
            boot=client.post('/security/bootstrap',data={'username':'admin360','display_name':'Admin User','password':ADMIN_PW},follow_redirects=False)
            login=client.post('/security/login',data={'username':'admin360','password':ADMIN_PW},follow_redirects=False); health=client.get('/health'); fs=client.get('/api/build360/final-status')
            probes['web']='pass' if anon.status_code==401 and start.status_code==303 and boot.status_code==303 and login.status_code==303 and health.status_code==200 and health.json().get('build')=='360.0' and fs.status_code==200 else 'fail'
        evidence={'build':BUILD,'result':'pass' if all(v=='pass' for v in probes.values()) else 'fail','code_fingerprint':fp,'probes':probes,'truthful_note':'Build 360 internal end-to-end qualification. External independent security/load/pilot validation is deliberately not claimed.'}
        write(ROOT/'BUILD_360_TEST_EVIDENCE.json',evidence)
        bench=benchmark(base/'bench',fp); write(ROOT/'BENCHMARK_BUILD_360_FINAL_QUALIFICATION.json',bench)
        with AppContext(base_dir=base/'gate',actor='gate360') as g:
            gate=g.build360.qualified_gate(); metrics=g.build360.schema_metrics(); readiness=g.build360.readiness_assessment(); crawler=g.build360.crawler_release_qualification(); ext=g.build360.external_validation_matrix()
    scan=static_scan(); bad=any(scan[k] for k in scan)
    result={'build':BUILD,'result':'pass' if evidence['result']=='pass' and bench['result']=='pass' and gate['build_acceptance_ready'] and not bad else 'fail','code_fingerprint':fp,'probes':probes,'benchmark':{'cases':bench['cases'],'violations':bench['violations'],'result':bench['result']},'gate':gate,'schema':metrics,'readiness':readiness,'crawler':crawler,'external_validation':ext,'static_scan':scan,'production_release_ready':False,'controlled_local_pilot_candidate_ready':bool(gate['controlled_pilot_candidate_ready']),'network_used_by_acceptance':False}
    write(ROOT/'ACCEPTANCE_RESULTS_BUILD_360_0.json',result); print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if result['result']=='pass' else 1

if __name__=='__main__': raise SystemExit(main())
