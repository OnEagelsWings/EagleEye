from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-422','roles':['analyst']}
def test_event_provenance_chain(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='Public News Fixture',source_type='news',base_url='https://example.org',capabilities=['articles'])
  e=c.build422.record_event(identity=ident(),case_id='case-422',source_id=s['source_id'],target='https://example.org/a',method='http',content_sha256='a'*64,media_type='text/html',bytes_count=123,provenance={'final_url':'https://example.org/a'},usage={'terms_checked':True})
  assert e['source_id']==s['source_id'];assert e['provenance']['final_url'].endswith('/a');assert c.acquisition_events_422.verify_integrity()['valid']
def test_event_tamper_detection(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build421.register_source(identity=ident(),name='Dataset',source_type='dataset',capabilities=['records']);e=c.build422.record_event(identity=ident(),case_id='c',source_id=s['source_id'],target='fixture',method='dataset',status='observed');c.db.execute("UPDATE acquisition_event_422 SET target='tampered' WHERE event_id=?",(e['event_id'],));assert not c.acquisition_events_422.verify_integrity()['valid']
def test_build422_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build422.acquisition_event_status();assert s['version_coherent'];assert s['phase19_builds_completed']==2;assert not s['direct_network_authority'];assert not s['evidence_promotion']
 assert (ROOT/'src/eagleeye/interfaces/web/app422.py').exists()
