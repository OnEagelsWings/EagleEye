from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-428','roles':['analyst']}
def test_archive_capture_timeline(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='Public Archive',source_type='archive',base_url='https://archive.example.org',capabilities=['historical_web'])
  t=c.build425.create_crawl_task(identity=ident(),case_id='case428',source_id=s['source_id'],target='https://archive.example.org/capture',objective='retrieve historical capture');r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='historical page')
  a=c.build428.register_archive_capture(identity=ident(),case_id='case428',source_id=s['source_id'],original_url='https://example.org/page',archive_url='https://archive.example.org/capture',captured_at='2025-01-02T03:04:05Z',retrieved_event_id=r['event_id'],content_id=r['content']['content_id']);assert a['content_id']==r['content']['content_id'];assert len(c.build428.archive_timeline('case428','https://example.org/page'))==1;assert c.archive_history_428.verify_integrity()['valid']
def test_non_archive_source_rejected(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='Web',source_type='website',base_url='https://example.org',capabilities=['pages']);t=c.build425.create_crawl_task(identity=ident(),case_id='c',source_id=s['source_id'],target='https://example.org',objective='x');r=c.build425.accept_retrieval(identity=ident(),task_id=t['task_id'],status='retrieved',content='x')
  try:c.build428.register_archive_capture(identity=ident(),case_id='c',source_id=s['source_id'],original_url='https://example.org',archive_url='https://example.org/a',captured_at='2025-01-01T00:00:00Z',retrieved_event_id=r['event_id'],content_id=r['content']['content_id']);assert False
  except ValueError:pass
def test_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build428.archive_status();assert s['version_coherent'];assert not s['network_authority'];assert s['archive_content_is_historical_observation_not_truth'];assert not s['production_release_ready']
 assert 'app428 import create_workspace_app428' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
