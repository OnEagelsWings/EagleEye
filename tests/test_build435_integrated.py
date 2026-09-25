from pathlib import Path
import pytest,runpy
from eagleeye_pro.core.app_context import AppContext
from eagleeye.phase16.tor_gateway370 import StaticTorReplayTransport370
from eagleeye.crawler.engine import FetchResponse
ROOT=Path(__file__).resolve().parents[1]
ONION='a'*56+'.onion'
BASE='http://'+ONION+'/'
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def case(c,title='Tor 435 Case'):
 i=ident(c);return c.build435.team_create_case(identity=i,title=title,client='QA',purpose='authorized public-source research',legal_basis='public_data')
def source(c,name='Tor Source 435'):
 return c.build421.register_source(identity=ident(c),name=name,source_type='tor_onion',access_mode='tor_public',base_url=BASE,capabilities=['public_pages'])
def replay(target,body=b'public onion fixture',media='text/plain',status=200):
 return StaticTorReplayTransport370({target:FetchResponse(target,status,{'content-type':media},body,2)})
def test_task_requires_reviewed_v3_onion_source_and_case_auth(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];s=source(c);t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=BASE+'public/a',objective='review public page',approval_ref='APPROVAL-1')
  assert t['state']=='planned';assert t['case_id']==cid;assert t['approval_ref']=='APPROVAL-1'
  clear=c.build421.register_source(identity=i,name='Clear',source_type='website',base_url='https://example.org',capabilities=['pages'])
  with pytest.raises(PermissionError):c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=clear['source_id'],target='https://example.org',objective='x',approval_ref='A')
def test_exact_onion_host_and_standard_port_enforced(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];s=source(c)
  with pytest.raises(PermissionError):c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target='http://'+'b'*56+'.onion/x',objective='x',approval_ref='A')
  with pytest.raises(ValueError):c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=BASE[:-1]+':8080/x',objective='x',approval_ref='A')
def test_replay_quarantines_and_human_review_does_not_promote_truth(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];s=source(c);target=BASE+'public/b';t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=target,objective='read only test',approval_ref='APPROVAL-2')
  r=c.tor_research_435.execute_replay(identity=i,task_id=t['task_id'],transport=replay(target));assert r['task']['state']=='quarantined_for_review';assert r['event']['status']=='quarantined';assert r['content']['content_id']==r['task']['content_id'];assert r['task']['execution_mode']=='deterministic_replay'
  reviewed=c.build435.review_tor_research(identity=i,task_id=t['task_id'],decision='accept_for_analysis',note='reviewed');assert reviewed['state']=='reviewed';assert reviewed['review_decision']=='accept_for_analysis';assert c.build435.tor_worker_status()['evidence_promotion'] is False;assert c.build435.tor_worker_status()['truth_determination'] is False
def test_unsafe_media_is_blocked_without_content_ingest(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];s=source(c);target=BASE+'download';t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=target,objective='bounded test',approval_ref='APPROVAL-3')
  r=c.tor_research_435.execute_replay(identity=i,task_id=t['task_id'],transport=replay(target,body=b'bin',media='application/octet-stream'));assert r['task']['state']=='blocked';assert r['event']['status']=='blocked';assert r['content'] is None;assert r['task']['content_id']==''
def test_live_execution_requires_repeated_approval_and_exact_confirmation(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];s=source(c);t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=BASE+'live',objective='live boundary test',approval_ref='HUMAN-435')
  with pytest.raises(PermissionError):c.build435.execute_tor_research_live(identity=i,task_id=t['task_id'],approval_ref='WRONG',confirmation='TOR435_LIVE')
  with pytest.raises(PermissionError):c.build435.execute_tor_research_live(identity=i,task_id=t['task_id'],approval_ref='HUMAN-435',confirmation='GO')
  with pytest.raises(PermissionError):c.build435.execute_tor_research_live(identity=i,task_id=t['task_id'],approval_ref='HUMAN-435',confirmation='TOR435_LIVE')
def test_live_worker_is_single_lane_and_web_offloads_blocking_io(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Live lane')['case_id'];s=source(c);t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=BASE+'live-lane',objective='lane test',approval_ref='LANE-435')
  c.build370.configure_tor_gateway(identity=i,confirmation='ENABLE_TOR',enabled=True,socks_host='127.0.0.1',socks_port=9)
  assert c.tor_research_435._live_lock.acquire(blocking=False)
  try:
   with pytest.raises(RuntimeError):c.build435.execute_tor_research_live(identity=i,task_id=t['task_id'],approval_ref='LANE-435',confirmation='TOR435_LIVE')
  finally:c.tor_research_435._live_lock.release()
  assert c.build435.tor_worker_status()['max_concurrent_live_tasks']==1
 app=(ROOT/'src/eagleeye/interfaces/web/app435.py').read_text();assert 'run_in_threadpool' in app and 'await run_in_threadpool' in app
def test_spawn_launcher_does_not_construct_workspace(monkeypatch):
 import eagleeye.interfaces.web.app435 as app435
 calls=[]
 monkeypatch.setattr(app435,'create_workspace_app435',lambda *a,**k:calls.append((a,k)))
 ns=runpy.run_path(str(ROOT/'EAGLEEYE_PRO_435_0.py'),run_name='__mp_main__')
 assert calls==[];assert ns['app'] is None

def test_case_researcher_can_run_first_selftest_without_source_manage(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  admin=ident(c);cid=case(c,'Researcher selftest')['case_id']
  c.team_governance_359.create_user(identity=admin,username='researcher435',display_name='Case Tester',global_role='read_only',password='Pine!Quartz!Orbit!2026')
  c.team_governance_359.assign_case_role(identity=admin,case_id=cid,username='researcher435',case_role='investigator',notes='Build 435 fixture permission regression')
  researcher=c.team_identity_359.public_user('researcher435')
  with pytest.raises(PermissionError):c.build421.register_source(identity=researcher,name='Denied source',source_type='website',base_url='https://example.org',capabilities=['pages'])
  r=c.build435.run_tor_case_selftest(identity=researcher,case_id=cid);assert r['result']=='PASS';assert all(r['checks'].values())
  fixture=c.acquisition_source_registry_421.get('src421_fixture_tor435');assert fixture['coverage']['fixture_only'] is True
  t=c.build435.create_tor_research_task(identity=researcher,case_id=cid,source_id=fixture['source_id'],target=fixture['base_url']+'live-forbidden',objective='must never execute live',approval_ref='NO-LIVE-FIXTURE')
  c.build370.configure_tor_gateway(identity=admin,confirmation='ENABLE_TOR',enabled=True,socks_host='127.0.0.1',socks_port=9)
  with pytest.raises(PermissionError):c.build435.execute_tor_research_live(identity=researcher,task_id=t['task_id'],approval_ref='NO-LIVE-FIXTURE',confirmation='TOR435_LIVE')

def test_case_isolation_and_tamper_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);ca=case(c,'A')['case_id'];cb=case(c,'B')['case_id'];s=source(c);ta=c.build435.create_tor_research_task(identity=i,case_id=ca,source_id=s['source_id'],target=BASE+'a',objective='a',approval_ref='A');tb=c.build435.create_tor_research_task(identity=i,case_id=cb,source_id=s['source_id'],target=BASE+'b',objective='b',approval_ref='B')
  assert [x['task_id'] for x in c.build435.case_tor_research(ca)]==[ta['task_id']];assert [x['task_id'] for x in c.build435.case_tor_research(cb)]==[tb['task_id']]
  c.db.execute("UPDATE tor_research_task_435 SET objective='tampered' WHERE task_id=?",(ta['task_id'],));assert not c.tor_research_435.verify_integrity()['valid']
def test_case_selftest_and_hard_checkpoint(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Selftest')['case_id'];r=c.build435.run_tor_case_selftest(identity=i,case_id=cid);assert r['result']=='PASS';assert all(r['checks'].values());assert r['event']['status']=='quarantined';assert r['task']['state']=='reviewed'
  cp=c.build435.checkpoint_435();assert cp['hard_checkpoint'];assert cp['checkpoint_ready'];assert cp['version_coherent'];assert cp['phase19_builds_completed']==15;assert cp['external_onion_validation']=='not_run';assert not cp['production_release_ready']
def test_contract_and_docs(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build435.tor_worker_status();assert s['version_coherent'];assert s['hard_checkpoint'];assert s['checkpoint_ready'];assert s['public_v3_onion_only'];assert s['read_only_get_only'];assert s['live_execution_requires_approval_ref_and_confirmation'];assert not s['destination_credentials_supported'];assert not s['forms_or_uploads_supported'];assert not s['access_control_bypass_supported'];assert not s['autonomous_scope_expansion'];assert s['quarantine_before_review'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app435.py').exists();assert (ROOT/'EAGLEEYE_PRO_435_0.py').exists();assert (ROOT/'BUILD_435_CASE_TEST.md').exists()
