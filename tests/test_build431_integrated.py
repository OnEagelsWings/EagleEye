from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def add_news(c,*,case_id,name,url,text,external_id,published_at='2026-09-20T10:00:00Z'):
 i=ident(c);s=c.build421.register_source(identity=i,name=name,source_type='news',base_url=url,capabilities=['articles'])
 e=c.build422.record_event(identity=i,case_id=case_id,source_id=s['source_id'],target=url+'/article',method='http')
 o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content=text)
 n=c.build429.ingest_news_item(identity=i,case_id=case_id,source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],canonical_url=url+'/article',title=name+' report',publisher=name,published_at=published_at,external_id=external_id,connector_kind='rss')
 return s,e,o,n
def test_exact_content_non_independence(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=add_news(c,case_id='case431',name='Outlet A',url='https://a.example.org',text='same wire copy',external_id='a')
  b=add_news(c,case_id='case431',name='Outlet B',url='https://b.example.org',text='same wire copy',external_id='b')
  r=c.build431.analyze_news_provenance(identity=ident(c),case_id='case431');analysis=r['analysis']
  assert analysis['distinct_source_units']==2;assert analysis['distinct_content_units']==1;assert len(analysis['exact_content_groups'])==1;assert set(analysis['exact_content_groups'][0]['news_item_ids'])=={a[3]['news_item_id'],b[3]['news_item_id']};assert analysis['syndication_analysis_is_not_truth_determination'];assert c.news_provenance_431.verify_integrity()['valid']
def test_claim_overlap_is_candidate_not_confirmation(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=add_news(c,case_id='claims431',name='Outlet C',url='https://c.example.org',text='Alice met Example Org in Berlin.',external_id='c')
  b=add_news(c,case_id='claims431',name='Outlet D',url='https://d.example.org',text='A separate article with different wording.',external_id='d')
  for n in (a[3],b[3]):c.build430.record_news_extraction(identity=ident(c),news_item_id=n['news_item_id'],extractor='fixture',extractor_version='1',claims=[{'text':'Alice met Example Org','confidence':.8}])
  r=c.build431.analyze_news_provenance(identity=ident(c),case_id='claims431');pairs=r['analysis']['claim_overlap_pairs'];assert len(pairs)==1;assert pairs[0]['jaccard']==1.0;assert pairs[0]['syndication_confirmed'] is False
def test_provenance_tamper_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  add_news(c,case_id='tamper431',name='Outlet E',url='https://e.example.org',text='article',external_id='e')
  r=c.build431.analyze_news_provenance(identity=ident(c),case_id='tamper431');c.db.execute('UPDATE news_provenance_run_431 SET item_count=99 WHERE run_id=?',(r['run_id'],));assert not c.news_provenance_431.verify_integrity()['valid']
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build431.provenance_status();assert s['version_coherent'];assert s['phase19_builds_completed']==11;assert s['syndication_analysis_is_evidence_signal_not_truth'];assert not s['network_authority'];assert not s['production_release_ready']
 assert 'app431 import create_workspace_app431' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text();readme=(ROOT/'README.md').read_text();assert 'EAGLEEYE_PRO_431_0.py' in readme and 'build `431.0`' in readme and 'test_build431_integrated.py' in readme
