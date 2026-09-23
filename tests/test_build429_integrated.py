from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def test_news_ingestion(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(c),name='News Feed',source_type='news',base_url='https://news.example.org',capabilities=['rss','articles']);t=c.build425.create_crawl_task(identity=ident(c),case_id='case429',source_id=s['source_id'],target='https://news.example.org/a',objective='collect public news');r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content='article body')
  n=c.build429.ingest_news_item(identity=ident(c),case_id='case429',source_id=s['source_id'],event_id=r['event_id'],content_id=r['content']['content_id'],canonical_url='https://news.example.org/a',title='Public report',publisher='Example News',published_at='2026-09-20T10:00:00Z',language='en',external_id='a-1',connector_kind='rss');assert n['title']=='Public report';assert len(c.build429.case_news('case429'))==1;assert c.news_connectors_429.verify_integrity()['valid']
def test_news_order_uses_actual_publication_instants_across_offsets(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=c.build421.register_source(identity=i,name='Offset News',source_type='news',base_url='https://news.example.org',capabilities=['articles'])
  e1=c.build422.record_event(identity=i,case_id='news-offset',source_id=s['source_id'],target='https://news.example.org/early',method='http');o1=c.build423.ingest_content(identity=i,event_id=e1['event_id'],content='early article')
  early=c.build429.ingest_news_item(identity=i,case_id='news-offset',source_id=s['source_id'],event_id=e1['event_id'],content_id=o1['content_id'],canonical_url='https://news.example.org/early',title='Early',published_at='2026-01-01T01:00:00+02:00',external_id='early',connector_kind='rss')
  e2=c.build422.record_event(identity=i,case_id='news-offset',source_id=s['source_id'],target='https://news.example.org/late',method='http');o2=c.build423.ingest_content(identity=i,event_id=e2['event_id'],content='late article')
  late=c.build429.ingest_news_item(identity=i,case_id='news-offset',source_id=s['source_id'],event_id=e2['event_id'],content_id=o2['content_id'],canonical_url='https://news.example.org/late',title='Late',published_at='2025-12-31T23:30:00+00:00',external_id='late',connector_kind='rss')
  rows=c.build429.case_news('news-offset');assert [r['news_item_id'] for r in rows]==[late['news_item_id'],early['news_item_id']];assert early['published_at']=='2025-12-31T23:00:00+00:00'
def test_duplicate_external_id(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(c),name='API News',source_type='api',base_url='https://api.example.org',capabilities=['news']);t=c.build425.create_crawl_task(identity=ident(c),case_id='c',source_id=s['source_id'],target='https://api.example.org/a',objective='x');r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content='x');kw=dict(identity=ident(c),case_id='c',source_id=s['source_id'],event_id=r['event_id'],content_id=r['content']['content_id'],canonical_url='https://example.org/a',title='A',published_at='2026-01-01T00:00:00Z',external_id='id1',connector_kind='api');c.build429.ingest_news_item(**kw)
  try:c.build429.ingest_news_item(**kw);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build429.news_status();assert s['version_coherent'];assert not s['network_executor_implemented'];assert s['publisher_claim_is_not_independent_corroboration'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app429.py').exists()
