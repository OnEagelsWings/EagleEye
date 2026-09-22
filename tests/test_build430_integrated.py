from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def news(c):
 s=c.build421.register_source(identity=ident(c),name='News',source_type='news',base_url='https://news.example.org',capabilities=['rss']);t=c.build425.create_crawl_task(identity=ident(c),case_id='case430',source_id=s['source_id'],target='https://news.example.org/a',objective='news');r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content='Alice met Example Org in Berlin.');return c.build429.ingest_news_item(identity=ident(c),case_id='case430',source_id=s['source_id'],event_id=r['event_id'],content_id=r['content']['content_id'],canonical_url='https://news.example.org/a',title='Meeting',published_at='2026-09-20T10:00:00Z',external_id='1')
def test_extraction(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  n=news(c);x=c.build430.record_news_extraction(identity=ident(c),news_item_id=n['news_item_id'],extractor='local-test-model',extractor_version='1',entities=[{'label':'Alice','kind':'person','confidence':.9,'source_span':'Alice'}],events=[{'label':'meeting','event_type':'meeting','location':'Berlin','confidence':.8}],claims=[{'text':'Alice met Example Org','confidence':.7}]);assert x['claims'][0]['corroborated'] is False;assert c.news_extraction_430.verify_integrity()['valid']
def test_confidence_bounds(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  n=news(c)
  try:c.build430.record_news_extraction(identity=ident(c),news_item_id=n['news_item_id'],extractor='x',extractor_version='1',entities=[{'label':'x','confidence':1.2}]);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build430.extraction_status();assert s['version_coherent'];assert s['hard_checkpoint'];assert s['extraction_is_machine_observation_not_fact'];assert not s['production_release_ready']
 assert 'app430 import create_workspace_app430' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
