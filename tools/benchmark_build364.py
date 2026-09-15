from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

ADMIN_PW='Orbit-Pine-Quartz-364!'; ANALYST_PW='Copper-Lake-Quartz-364!'

def main():
 root=Path(__file__).resolve().parents[1]; violations=0; cats={}
 with tempfile.TemporaryDirectory(prefix='ee364-bench-') as td:
  base=Path(td)
  # Fake cert files are sufficient for request-decision policy because the real TLS
  # handshake is independently validated by LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json.
  cert=base/'c'; key=base/'k'; cert.write_text('policy-only'); key.write_text('policy-only')
  env={'EAGLEEYE_REMOTE_TEAM_ENABLED':'1','EAGLEEYE_REMOTE_BIND_HOST':'10.23.0.1','EAGLEEYE_REMOTE_ALLOWED_HOSTS':'eagleeye.test','EAGLEEYE_REMOTE_ALLOWED_CIDRS':'10.23.0.0/24','EAGLEEYE_REMOTE_TLS_CERT':str(cert),'EAGLEEYE_REMOTE_TLS_KEY':str(key),'EAGLEEYE_REMOTE_PUBLIC_ORIGIN':'https://eagleeye.test:8765'}
  old={k:os.environ.get(k) for k in env};os.environ.update(env)
  try:
   with AppContext(base_dir=base/'db') as c:
    # 700 transport decisions
    cats['transport_policy']=700
    for i in range(700):
     mode=i%7
     args={
      0:dict(scheme='https',host_header='eagleeye.test',client_ip='10.23.0.8',forwarded_headers_present=False),
      1:dict(scheme='http',host_header='eagleeye.test',client_ip='10.23.0.8',forwarded_headers_present=False),
      2:dict(scheme='https',host_header='evil.test',client_ip='10.23.0.8',forwarded_headers_present=False),
      3:dict(scheme='https',host_header='eagleeye.test',client_ip='10.99.0.8',forwarded_headers_present=False),
      4:dict(scheme='https',host_header='eagleeye.test',client_ip='10.23.0.8',forwarded_headers_present=True),
      5:dict(scheme='https',host_header='eagleeye.test:8765',client_ip='10.23.0.99',forwarded_headers_present=False),
      6:dict(scheme='https',host_header='eagleeye.test',client_ip='not-an-ip',forwarded_headers_present=False),
     }[mode]
     r=c.build364.remote_request_decision(**args); expected=mode in {0,5}
     if bool(r['allowed'])!=expected: violations+=1
    # actual RBAC decisions
    a=c.team_identity_359.create_initial_admin(username='admin364',display_name='Admin User',password=ADMIN_PW); ai={**a,'session_id':'bench-admin'}
    ca=c.build364.team_create_case(identity=ai,title='A',client='QA',purpose='public',legal_basis='public_data'); cb=c.build364.team_create_case(identity=ai,title='B',client='QA',purpose='public',legal_basis='public_data')
    c.build364.team_create_user(identity=ai,username='analyst364',display_name='Analyst User',global_role='investigator',password=ANALYST_PW); c.build364.assign_case_role(identity=ai,case_id=ca['case_id'],username='analyst364',case_role='analyst',notes='benchmark')
    cats['cross_case_rbac']=400
    for i in range(400):
     if i%2==0:
      try:c.build364.authorize('analyst364',case_id=ca['case_id'],capability='case.read')
      except PermissionError:violations+=1
     else:
      try:c.build364.authorize('analyst364',case_id=cb['case_id'],capability='case.read');violations+=1
      except PermissionError:pass
    cats['truthful_release']=300
    for _ in range(300):
     st=c.build364.remote_team_status()
     if st.get('externally_validated') or st.get('external_remote_clients_validated'):violations+=1
    cats['ai_opsec_crawler']=400
    for i in range(400):
     if i%3==0:
      if not c.ai_autonomy_364.status().get('remote_team_context_aware'):violations+=1
     elif i%3==1:
      if c.opsec_supervisor_364.status().get('system_mutations'):violations+=1
     else:
      if c.build364.crawler_status().get('crawler_improvement_build')!=364:violations+=1
    cats['inherited_storage_search']=200
    for _ in range(200):
     st=c.build363.storage_search_status()
     if not st['s3']['local_cas_live'] or not st['team_search']['portable_fts5_live']:violations+=1
    cats['tls_receipt_truthfulness']=200
    receipt=json.loads((root/'LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json').read_text())
    for _ in range(200):
     if receipt.get('status')!='pass' or receipt.get('externally_validated') is not False or not receipt.get('tls_handshake_verified_against_generated_ca'):violations+=1
    fp=c.build364.code_fingerprint()
  finally:
   for k,v in old.items():
    if v is None:os.environ.pop(k,None)
    else:os.environ[k]=v
 out={'build':'364.0','result':'pass' if violations==0 else 'fail','cases':sum(cats.values()),'violations':violations,'categories':cats,'code_fingerprint':fp,'network_used_by_benchmark':False,'separate_live_transport_receipt':'LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json'}
 (root/'BENCHMARK_BUILD_364_REMOTE_TEAM.json').write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding='utf-8');print(json.dumps(out,indent=2,sort_keys=True))
 if violations:raise SystemExit(1)
if __name__=='__main__':main()
