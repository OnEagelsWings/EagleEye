from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident():return {'username':'analyst','global_role':'system_administrator','user_id':'analyst-423','roles':['analyst']}
def event(c,target):
 s=c.build421.register_source(identity=ident(),name='News '+target,source_type='news',base_url='https://example.org',capabilities=['articles']);return c.build422.record_event(identity=ident(),case_id='case423',source_id=s['source_id'],target=target,method='http')
def test_exact_dedup(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=c.build423.ingest_content(identity=ident(),event_id=event(c,'a')['event_id'],content='Same report text.');b=c.build423.ingest_content(identity=ident(),event_id=event(c,'b')['event_id'],content='Same report text.');assert a['duplicate_kind']=='unique';assert b['duplicate_kind']=='exact';assert a['content_id']==b['content_id']
def test_near_duplicate(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  c.build423.ingest_content(identity=ident(),event_id=event(c,'a')['event_id'],content='alpha beta gamma delta epsilon');b=c.build423.ingest_content(identity=ident(),event_id=event(c,'b')['event_id'],content='alpha beta gamma delta epsilon zeta',near_threshold=.8);assert b['duplicate_kind']=='near';assert b['related_content_id']
def test_integrity_and_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  x=c.build423.ingest_content(identity=ident(),event_id=event(c,'x')['event_id'],content='evidence fixture');c.db.execute("UPDATE content_object_423 SET media_type='x' WHERE content_id=?",(x['content_id'],));assert not c.content_store_423.verify_integrity()['valid'];s=c.build423.content_status();assert s['version_coherent'];assert not s['stores_raw_payload'];assert not s['direct_network_authority']
 assert 'app423 import create_workspace_app423' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text()
