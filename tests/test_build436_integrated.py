from pathlib import Path
import json,runpy
import pytest
from eagleeye_pro.core.app_context import AppContext
from eagleeye.phase16.tor_gateway370 import StaticTorReplayTransport370
from eagleeye.crawler.engine import FetchResponse
ROOT=Path(__file__).resolve().parents[1]
ONION='a'*56+'.onion'
BASE='http://'+ONION+'/'
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def case(c,title='Surface Onion 436'):
 return c.build436.team_create_case(identity=ident(c),title=title,client='QA',purpose='authorized public-source correlation',legal_basis='public_data')
def surface_source(c):
 i=ident(c)
 existing=[s for s in c.acquisition_source_registry_421.list_sources(source_type='website') if s.get('base_url')=='https://surface436.example.org']
 return existing[0] if existing else c.build421.register_source(identity=i,name='Surface 436',source_type='website',base_url='https://surface436.example.org',capabilities=['public_pages'])
def surface_content(c,case_id,body,target='https://surface436.example.org/page'):
 i=ident(c);s=surface_source(c);raw=body.encode() if isinstance(body,str) else bytes(body);import hashlib;digest=hashlib.sha256(raw).hexdigest()
 e=c.build422.record_event(identity=i,case_id=case_id,source_id=s['source_id'],target=target,method='manual_import',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(raw),provenance={'test':True},usage={'public_only':True})
 o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content=raw,media_type='text/plain');return s,e,o
def reviewed_onion(c,case_id,body,path='public/test'):
 i=ident(c);s=c.tor_research_435._ensure_selftest_source();target=s['base_url']+path;t=c.build435.create_tor_research_task(identity=i,case_id=case_id,source_id=s['source_id'],target=target,objective='Build436 test onion',approval_ref='TEST-436')
 raw=body.encode() if isinstance(body,str) else bytes(body);transport=StaticTorReplayTransport370({target:FetchResponse(target,200,{'content-type':'text/plain'},raw,2)})
 r=c.tor_research_435.execute_replay(identity=i,task_id=t['task_id'],transport=transport);rv=c.build435.review_tor_research(identity=i,task_id=t['task_id'],decision='accept_for_analysis',note='Build436 fixture review');return s,r,rv
def test_exact_surface_onion_candidate_is_not_identity_claim(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c)['case_id'];body='same public research content 436';s,e,o=surface_content(c,cid,body);os,orr,rv=reviewed_onion(c,cid,body)
  run=c.build436.analyze_surface_onion(identity=i,case_id=cid,min_jaccard=.75);res=run['result'];assert res['candidate_count']>=1
  exact=[x for x in res['candidates'] if x['surface_content_id']==o['content_id'] and x['onion_task_id']==rv['task_id'] and any(y['kind']=='exact_sha256' for y in x['signals'])]
  assert len(exact)==1;assert exact[0]['candidate_only'];assert exact[0]['entity_identity_determined'] is False
  assert res['identity_determination'] is False;assert res['truth_determination'] is False;assert res['operational_followup_allowed'] is False;assert res['analysis_review_allowed'] is True
def test_only_reviewed_onion_material_is_correlated(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Reviewed only')['case_id'];body='unreviewed onion content';surface_content(c,cid,body)
  s=c.tor_research_435._ensure_selftest_source();target=s['base_url']+'public/unreviewed';t=c.build435.create_tor_research_task(identity=i,case_id=cid,source_id=s['source_id'],target=target,objective='unreviewed',approval_ref='U436');transport=StaticTorReplayTransport370({target:FetchResponse(target,200,{'content-type':'text/plain'},body.encode(),2)});c.tor_research_435.execute_replay(identity=i,task_id=t['task_id'],transport=transport)
  run=c.build436.analyze_surface_onion(identity=i,case_id=cid);assert run['result']['reviewed_onion_tasks']==0;assert run['result']['candidate_count']==0
def test_high_lexical_overlap_is_candidate_signal_only(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Jaccard')['case_id'];surface_content(c,cid,'alpha beta gamma delta epsilon surface');reviewed_onion(c,cid,'alpha beta gamma delta epsilon onion','public/jaccard')
  run=c.build436.analyze_surface_onion(identity=i,case_id=cid,min_jaccard=.7);pairs=[p for p in run['result']['candidates'] if any(s['kind']=='token_jaccard' for s in p['signals'])];assert pairs;assert all(p['candidate_only'] and not p['entity_identity_determined'] for p in pairs)
def test_opsec_failure_blocks_analysis_review_not_active_followup(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'OPSEC')['case_id'];surface_content(c,cid,'opsec shared text');_,r,rv=reviewed_onion(c,cid,'opsec shared text','public/opsec')
  ev=c.acquisition_events_422.get(rv['event_id']);row=c.db.one('SELECT * FROM acquisition_event_422 WHERE event_id=?',(rv['event_id'],));d=dict(row);d['usage_json']='{}';d['record_hash']=c.acquisition_events_422._hash(d);c.db.execute('UPDATE acquisition_event_422 SET usage_json=?,record_hash=? WHERE event_id=?',(d['usage_json'],d['record_hash'],rv['event_id']))
  run=c.build436.analyze_surface_onion(identity=i,case_id=cid);res=run['result'];assert res['opsec_blocker_count']==1;assert res['analysis_review_allowed'] is False;assert res['operational_followup_allowed'] is False
def test_relevant_provenance_tamper_fails_closed(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Integrity preflight')['case_id'];_,e,o=surface_content(c,cid,'integrity bound text');reviewed_onion(c,cid,'integrity bound text','public/integrity')
  c.db.execute("UPDATE content_observation_423 SET target='https://tampered.invalid' WHERE observation_id=?",(o['observation_id'],))
  with pytest.raises(RuntimeError):c.build436.analyze_surface_onion(identity=i,case_id=cid)

def test_case_selftest_and_fixture_seeding_are_repeatable(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Selftest436')['case_id'];a=c.build436.run_surface_onion_case_selftest(identity=i,case_id=cid);b=c.build436.run_surface_onion_case_selftest(identity=i,case_id=cid);assert a['result']=='PASS' and b['result']=='PASS';assert all(a['checks'].values());assert all(b['checks'].values())
  assert c.acquisition_source_registry_421.get('src421_fixture_surface436')['coverage']['fixture_only'];assert c.acquisition_source_registry_421.get('src421_fixture_tor435')['coverage']['fixture_only']
def test_carried_forward_build435_review_is_terminal(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'Atomic review')['case_id'];_,r,rv=reviewed_onion(c,cid,'atomic terminal review','public/atomic')
  with pytest.raises(ValueError):c.build435.review_tor_research(identity=i,task_id=rv['task_id'],decision='reject',note='conflicting second decision')
def test_case_isolation_and_integrity(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);ca=case(c,'A436')['case_id'];cb=case(c,'B436')['case_id'];surface_content(c,ca,'case a shared');reviewed_onion(c,ca,'case a shared','public/a436');surface_content(c,cb,'case b only')
  ra=c.build436.analyze_surface_onion(identity=i,case_id=ca);rb=c.build436.analyze_surface_onion(identity=i,case_id=cb);assert ra['result']['candidate_count']>=1;assert rb['result']['candidate_count']==0
  c.db.execute("UPDATE surface_onion_run_436 SET candidate_count=999 WHERE run_id=?",(ra['run_id'],));assert not c.surface_onion_436.verify_integrity()['valid']
def test_contract_opsec_web_and_spawn_guard(tmp_path,monkeypatch):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build436.surface_onion_status();assert s['version_coherent'];assert s['phase19_builds_completed']==16;assert s['reviewed_onion_only'];assert s['candidate_only'];assert not s['network_execution'];assert not s['cross_surface_contact'];assert not s['operational_followup_authority'];assert not s['automatic_entity_resolution'];assert not s['identity_determination'];assert not s['truth_determination'];assert not s['production_release_ready']
 app435=(ROOT/'src/eagleeye/interfaces/web/app435.py').read_text();app436=(ROOT/'src/eagleeye/interfaces/web/app436.py').read_text();assert 'Cross-origin mutation blocked' in app435 and 'Cross-origin mutation blocked' in app436
 import eagleeye.interfaces.web.app436 as appmod
 calls=[];monkeypatch.setattr(appmod,'create_workspace_app436',lambda *a,**k:calls.append((a,k)));ns=runpy.run_path(str(ROOT/'EAGLEEYE_PRO_436_0.py'),run_name='__mp_main__');assert calls==[];assert ns['app'] is None
 assert 'app436 import create_workspace_app436' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text();assert (ROOT/'BUILD_436_CASE_TEST.md').exists();readme=(ROOT/'README.md').read_text();assert 'EAGLEEYE_PRO_436_0.py' in readme and 'test_build436_integrated.py' in readme
