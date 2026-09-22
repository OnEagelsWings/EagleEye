from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'user_id':'analyst-429','roles':['analyst']}
def test_news_ingestion(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='News Feed',source_type='news',base_url='https://news.example.org',capabilities=['rss','articles']);t=c.build425.create_crawl_task(identity=ident(),case_id='case429',source_id=s['source_id'],target='https://news.example.org/a',objective='collect public news');r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='article body')
  n=c.build429.ingest_news_item(identity=ident(),case_id='case429',source_id=s['source_id'],event_id=r['event_id'],content_id=r['content']['content_id'],canonical_url='https://news.example.org/a',title='Public report',publisher='Example News',published_at='2026-09-20T10:00:00Z',language='en',external_id='a-1',connector_kind='rss');assert n['title']=='Public report';assert len(c.build429.case_news('case429'))==1;assert c.news_connectors_429.verify_integrity()['valid']
def test_duplicate_external_id(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='API News',source_type='api',base_url='https://api.example.org',capabilities=['news']);t=c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='https://api.example.org/a',objective='x');r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='x');kw=dict(identity=ident(),case_id='c',source_id=s['source_id'],event_id=r['event_id'],content_id=r['content']['content_id'],canonical_url='https://example.org/a',title='A',published_at='2026-01-01T00:00:00Z',external_id='id1',connector_kind='api');c.build429.ingest_news_item(**kw)
  try:c.build429.ingest_news_item(**kw);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build429.news_status();assert s['version_coherent'];assert not s['network_executor_implemented'];assert s['publisher_claim_is_not_independent_corroboration'];assert not s['production_release_ready']
 assert 'app429 import create_workspace_app429' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
