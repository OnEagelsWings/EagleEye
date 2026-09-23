from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def test_archive_capture_timeline(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(c),name='Public Archive',source_type='archive',base_url='https://archive.example.org',capabilities=['historical_web'])
  t=c.build425.create_crawl_task(identity=ident(c),case_id='case428',source_id=s['source_id'],target='https://archive.example.org/capture',objective='retrieve historical capture');r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content='historical page')
  a=c.build428.register_archive_capture(identity=ident(c),case_id='case428',source_id=s['source_id'],original_url='https://example.org/page',archive_url='https://archive.example.org/capture',captured_at='2025-01-02T03:04:05Z',retrieved_event_id=r['event_id'],content_id=r['content']['content_id']);assert a['content_id']==r['content']['content_id'];assert len(c.build428.archive_timeline('case428','https://example.org/page'))==1;assert c.archive_history_428.verify_integrity()['valid']
def test_archive_timeline_orders_actual_instants_across_offsets(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=c.build421.register_source(identity=i,name='Offset Archive',source_type='archive',base_url='https://archive.example.org',capabilities=['historical_web'])
  e1=c.build422.record_event(identity=i,case_id='arc-offset',source_id=s['source_id'],target='https://archive.example.org/1',method='archive');o1=c.build423.ingest_content(identity=i,event_id=e1['event_id'],content='early')
  early=c.build428.register_archive_capture(identity=i,case_id='arc-offset',source_id=s['source_id'],original_url='https://example.org/page',archive_url='https://archive.example.org/1',captured_at='2026-01-01T01:00:00+02:00',retrieved_event_id=e1['event_id'],content_id=o1['content_id'])
  e2=c.build422.record_event(identity=i,case_id='arc-offset',source_id=s['source_id'],target='https://archive.example.org/2',method='archive');o2=c.build423.ingest_content(identity=i,event_id=e2['event_id'],content='late')
  late=c.build428.register_archive_capture(identity=i,case_id='arc-offset',source_id=s['source_id'],original_url='https://example.org/page',archive_url='https://archive.example.org/2',captured_at='2025-12-31T23:30:00+00:00',retrieved_event_id=e2['event_id'],content_id=o2['content_id'])
  rows=c.build428.archive_timeline('arc-offset','https://example.org/page');assert [r['archive_capture_id'] for r in rows]==[early['archive_capture_id'],late['archive_capture_id']];assert early['captured_at']=='2025-12-31T23:00:00+00:00'
def test_non_archive_source_rejected(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(c),name='Web',source_type='website',base_url='https://example.org',capabilities=['pages']);t=c.build425.create_crawl_task(identity=ident(c),case_id='c',source_id=s['source_id'],target='https://example.org',objective='x');r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content='x')
  try:c.build428.register_archive_capture(identity=ident(c),case_id='c',source_id=s['source_id'],original_url='https://example.org',archive_url='https://example.org/a',captured_at='2025-01-01T00:00:00Z',retrieved_event_id=r['event_id'],content_id=r['content']['content_id']);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build428.archive_status();assert s['version_coherent'];assert not s['network_authority'];assert s['archive_content_is_historical_observation_not_truth'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app428.py').exists()
