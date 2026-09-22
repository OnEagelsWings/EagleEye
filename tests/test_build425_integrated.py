from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-425','roles':['analyst']}
def src(c):
 return c.build421.register_source(identity=ident(),name='Public source',source_type='website',base_url='https://example.org',capabilities=['pages'])
def test_end_to_end_acquisition_chain(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=src(c);c.build424.record_source_health(identity=ident(),source_id=s['source_id'],state='healthy',latency_ms=10)
  t=c.build425.create_crawl_task(identity=ident(),case_id='case425',source_id=s['source_id'],target='https://example.org/report',objective='Collect public report')
  r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='public report alpha beta',media_type='text/plain')
  assert r['event_id'];assert r['content']['duplicate_kind']=='unique';ev=c.acquisition_events_422.get(r['event_id']);assert ev['content_sha256']==r['content']['sha256'];assert ev['bytes_count']==len(b'public report alpha beta');assert ev['source_snapshot']['source_id']==s['source_id'];assert c.build425.crawler_status()['integrity_valid'];assert c.content_store_423.verify_integrity()['valid']
def test_health_gate_and_onion_boundary(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=src(c);c.build424.record_source_health(identity=ident(),source_id=s['source_id'],state='rate_limited',retry_after_seconds=60)
  t=c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='https://example.org/x',objective='x');assert t['state']=='deferred'
  try:c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='http://abc.onion/x',objective='x');assert False
  except ValueError:pass
  try:c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='http://127.0.0.1/admin',objective='x');assert False
  except ValueError:pass
def test_digest_mismatch_rejected(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=src(c);t=c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='https://example.org/x',objective='x')
  try:c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='abc',content_sha256='0'*64);assert False
  except ValueError:pass
def test_build425_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build425.crawler_status();assert s['version_coherent'];assert not s['network_executor_implemented'];assert not s['access_control_bypass'];assert s['phase19_builds_completed']==5
 assert 'app425 import create_workspace_app425' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
