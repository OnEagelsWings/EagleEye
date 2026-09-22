from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def setup(c):
 s=c.build421.register_source(identity=ident(c),name='Source',source_type='website',base_url='https://example.org',capabilities=['pages']);t=c.build425.create_crawl_task(identity=ident(c),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='track report');return s,t
def ingest(c,t,text):
 r=c.build425.accept_retrieval(identity=ident(c),task_id=t['task_id'],status='retrieved',content=text);return r
def test_change_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s,t=setup(c);a=ingest(c,t,'alpha beta gamma');x=c.build427.capture_snapshot(identity=ident(c),event_id=a['event_id'],content_id=a['content']['content_id'],text='alpha beta gamma');assert x['change'] is None
  t2=c.build425.create_crawl_task(identity=ident(c),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='track report');b=ingest(c,t2,'alpha beta gamma delta');y=c.build427.capture_snapshot(identity=ident(c),event_id=b['event_id'],content_id=b['content']['content_id'],text='alpha beta gamma delta');assert y['change']['change_kind'] in {'minor','changed'};assert 'delta' in y['change']['added'];assert c.change_detection_427.verify_integrity()['valid']
def test_out_of_order_historical_capture_never_links_future_as_previous(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=c.build421.register_source(identity=i,name='Chronology',source_type='website',base_url='https://example.org',capabilities=['pages'])
  feb=c.build422.record_event(identity=i,case_id='chron',source_id=s['source_id'],target='https://example.org/report',method='http',retrieved_at='2026-02-01T00:00:00Z');fc=c.build423.ingest_content(identity=i,event_id=feb['event_id'],content='february version');c.build427.capture_snapshot(identity=i,event_id=feb['event_id'],content_id=fc['content_id'],text='february version')
  jan=c.build422.record_event(identity=i,case_id='chron',source_id=s['source_id'],target='https://example.org/report',method='http',retrieved_at='2026-01-01T00:00:00Z');jc=c.build423.ingest_content(identity=i,event_id=jan['event_id'],content='january version');j=c.build427.capture_snapshot(identity=i,event_id=jan['event_id'],content_id=jc['content_id'],text='january version');assert j['change'] is None
def test_event_content_link_required(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s,t=setup(c);a=ingest(c,t,'one');t2=c.build425.create_crawl_task(identity=ident(c),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='x');b=ingest(c,t2,'two')
  try:c.build427.capture_snapshot(identity=ident(c),event_id=a['event_id'],content_id=b['content']['content_id'],text='two');assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build427.change_status();assert s['version_coherent'];assert not s['network_authority'];assert s['change_detection_is_evidence_signal_not_truth'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app427.py').exists()
