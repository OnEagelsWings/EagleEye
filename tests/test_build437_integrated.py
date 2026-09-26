from pathlib import Path
import runpy
import pytest
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def case(c,title='Entity 437'):
 return c.build437.team_create_case(identity=ident(c),title=title,client='QA',purpose='authorized cross-source entity resolution',legal_basis='public_data')
def selftest(c,title='Entity 437 selftest'):
 i=ident(c);cid=case(c,title)['case_id'];r=c.build437.run_entity_resolution_case_selftest(identity=i,case_id=cid);return i,cid,r
def test_case_selftest_creates_review_candidate_not_merge(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i,cid,r=selftest(c);assert r['result']=='PASS';assert all(r['checks'].values())
  q=c.build437.entity_resolution_review_queue(cid);assert q;assert all(x['human_review_required'] for x in q);assert all(x['score_is_probability'] is False for x in q)
  report=c.build437.entity_resolution_report(cid);assert report['approved_non_destructive_links']==0;assert report['resolution_entities']==2;assert report['resolution_event_chain_valid']
def test_independent_reviewer_creates_non_destructive_link(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  admin,cid,r=selftest(c,'Independent review');packet=c.build437.entity_resolution_review_queue(cid)[0];cmp=packet['comparison'];canonical=cmp['left_entity_id']
  p=c.build437.propose_same_entity_437(identity=admin,case_id=cid,comparison_id=cmp['comparison_id'],canonical_entity_id=canonical);assert p['state']=='pending';assert p['automatic_merge'] is False
  c.team_governance_359.create_user(identity=admin,username='reviewer437',display_name='Reviewer 437',global_role='reviewer',password='Cedar!Orbit!Quartz!437')
  c.team_governance_359.assign_case_role(identity=admin,case_id=cid,username='reviewer437',case_role='reviewer',notes='independent Build 437 review')
  reviewer=c.team_identity_359.public_user('reviewer437')
  out=c.build437.review_same_entity_437(identity=reviewer,case_id=cid,proposal_id=p['proposal_id'],approve=True,reason='Independent provenance review supports a non-destructive same-entity link')
  assert out['state']=='approved';assert out['automatic_merge'] is False;assert out['destructive_merge'] is False
  report=c.build437.entity_resolution_report(cid);assert report['approved_non_destructive_links']==1;assert report['resolution_entities']==2
def test_requester_cannot_review_own_proposal(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  admin,cid,r=selftest(c,'Separation of duties');packet=c.build437.entity_resolution_review_queue(cid)[0];cmp=packet['comparison'];p=c.build437.propose_same_entity_437(identity=admin,case_id=cid,comparison_id=cmp['comparison_id'],canonical_entity_id=cmp['left_entity_id'])
  with pytest.raises(PermissionError):c.build437.review_same_entity_437(identity=admin,case_id=cid,proposal_id=p['proposal_id'],approve=True,reason='Requester must not approve their own entity-resolution proposal')
def test_case_isolation(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  _,ca,ra=selftest(c,'Case A 437');_,cb,rb=selftest(c,'Case B 437')
  ba=c.build437.entity_resolution_bindings(ca);bb=c.build437.entity_resolution_bindings(cb);assert ba and bb;assert {x['case_id'] for x in ba}=={ca};assert {x['case_id'] for x in bb}=={cb};assert not ({x['binding_id'] for x in ba}&{x['binding_id'] for x in bb})
def test_binding_tamper_fails_integrity(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  _,cid,r=selftest(c,'Tamper 437');b=c.build437.entity_resolution_bindings(cid)[0];c.db.execute("UPDATE phase19_entity_binding_437 SET source_ref='tampered' WHERE binding_id=?",(b['binding_id'],));assert not c.entity_resolution_437.verify_integrity()['valid']
def test_news_machine_mentions_remain_candidates(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);cid=case(c,'News candidates')['case_id'];s=c.build421.register_source(identity=i,name='News 437',source_type='news',base_url='https://news437.example.org',capabilities=['articles']);e=c.build422.record_event(identity=i,case_id=cid,source_id=s['source_id'],target='https://news437.example.org/a',method='http');o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content='Alice Example appeared in the report.');n=c.build429.ingest_news_item(identity=i,case_id=cid,source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],canonical_url='https://news437.example.org/a',title='Report',published_at='2026-09-25T10:00:00Z',external_id='n437',connector_kind='rss');c.build430.record_news_extraction(identity=i,news_item_id=n['news_item_id'],extractor='fixture',extractor_version='1',entities=[{'label':'Alice Example','kind':'person','confidence':.8,'source_span':'Alice Example'}])
  run=c.build437.sync_cross_source_entities(identity=i,case_id=cid);bindings=c.build437.entity_resolution_bindings(cid);news=[x for x in bindings if x['source_kind']=='news_entity_mention'];assert len(news)==1
  ent=c.db.one('SELECT * FROM resolution_entities_115 WHERE resolution_entity_id=?',(news[0]['resolution_entity_id'],));assert ent['candidate_only']==1;assert run['result']['automatic_identity_confirmation'] is False
def test_surface_onion_context_is_not_identity_evidence(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i,cid,r=selftest(c,'Context-only 437');packet=c.build437.entity_resolution_review_queue(cid)[0];assert packet['content_correlation_is_identity_evidence'] is False;assert all(x.get('identity_evidence') is False for x in packet['surface_onion_context'])
def test_contract_and_launcher(tmp_path,monkeypatch):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build437.entity_resolution_status_437();assert s['version_coherent'];assert s['phase19_builds_completed']==17;assert s['cross_source_entity_resolution'];assert s['uses_canonical_resolution_ledger_115'];assert s['uses_evidence_weighted_review_371'];assert not s['score_is_probability'];assert not s['automatic_identity_confirmation'];assert not s['automatic_merge'];assert not s['destructive_merge'];assert s['independent_human_review_required'];assert not s['network_execution'];assert not s['production_release_ready']
 import eagleeye.interfaces.web.app437 as appmod
 calls=[];monkeypatch.setattr(appmod,'create_workspace_app437',lambda *a,**k:calls.append((a,k)));ns=runpy.run_path(str(ROOT/'EAGLEEYE_PRO_437_0.py'),run_name='__mp_main__');assert calls==[];assert ns['app'] is None
 assert (ROOT/'src/eagleeye/interfaces/web/app437.py').exists();assert (ROOT/'EAGLEEYE_PRO_437_0.py').exists();assert (ROOT/'BUILD_437_CASE_TEST.md').exists();assert (ROOT/'README_BUILD_437_0.md').exists()
