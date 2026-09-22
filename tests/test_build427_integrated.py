from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'user_id':'analyst-427','roles':['analyst']}
def setup(c):
 s=c.build421.register_source(identity=ident(),name='Source',source_type='website',base_url='https://example.org',capabilities=['pages']);t=c.build425.create_crawl_task(identity=ident(),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='track report');return s,t
def ingest(c,t,text):
 r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content=text);return r
def test_change_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s,t=setup(c);a=ingest(c,t,'alpha beta gamma');x=c.build427.capture_snapshot(identity=ident(),event_id=a['event_id'],content_id=a['content']['content_id'],text='alpha beta gamma');assert x['change'] is None
  t2=c.build425.create_crawl_task(identity=ident(),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='track report');b=ingest(c,t2,'alpha beta gamma delta');y=c.build427.capture_snapshot(identity=ident(),event_id=b['event_id'],content_id=b['content']['content_id'],text='alpha beta gamma delta');assert y['change']['change_kind'] in {'minor','changed'};assert 'delta' in y['change']['added'];assert c.change_detection_427.verify_integrity()['valid']
def test_event_content_link_required(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s,t=setup(c);a=ingest(c,t,'one');t2=c.build425.create_crawl_task(identity=ident(),case_id='case427',source_id=s['source_id'],target='https://example.org/report',objective='x');b=ingest(c,t2,'two')
  try:c.build427.capture_snapshot(identity=ident(),event_id=a['event_id'],content_id=b['content']['content_id'],text='two');assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build427.change_status();assert s['version_coherent'];assert not s['network_authority'];assert s['change_detection_is_evidence_signal_not_truth'];assert not s['production_release_ready']
 assert 'app427 import create_workspace_app427' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
