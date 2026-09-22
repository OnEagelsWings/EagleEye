from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def event(c,target):
 s=c.build421.register_source(identity=ident(c),name='News '+target,source_type='news',base_url='https://example.org',capabilities=['articles']);return c.build422.record_event(identity=ident(c),case_id='case423',source_id=s['source_id'],target=target,method='http')
def test_exact_dedup(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  a=c.build423.ingest_content(identity=ident(c),event_id=event(c,'a')['event_id'],content='Same report text.');b=c.build423.ingest_content(identity=ident(c),event_id=event(c,'b')['event_id'],content='Same report text.');assert a['duplicate_kind']=='unique';assert b['duplicate_kind']=='exact';assert a['content_id']==b['content_id']
def test_near_duplicate(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  c.build423.ingest_content(identity=ident(c),event_id=event(c,'a')['event_id'],content='alpha beta gamma delta epsilon');b=c.build423.ingest_content(identity=ident(c),event_id=event(c,'b')['event_id'],content='alpha beta gamma delta epsilon zeta',near_threshold=.8);assert b['duplicate_kind']=='near';assert b['related_content_id']
def test_migrated_observation_hash_is_backfilled(tmp_path):
 observation_id=''
 with AppContext(base_dir=tmp_path) as c:
  r=c.build423.ingest_content(identity=ident(c),event_id=event(c,'legacy')['event_id'],content='legacy observation');observation_id=r['observation_id'];c.db.execute("UPDATE content_observation_423 SET record_hash='' WHERE observation_id=?",(observation_id,))
 with AppContext(base_dir=tmp_path) as c:
  row=c.db.one('SELECT record_hash FROM content_observation_423 WHERE observation_id=?',(observation_id,));assert row and row['record_hash'];assert c.content_store_423.verify_integrity()['valid']
def test_integrity_and_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  x=c.build423.ingest_content(identity=ident(c),event_id=event(c,'x')['event_id'],content='evidence fixture');c.db.execute("UPDATE content_object_423 SET media_type='x' WHERE content_id=?",(x['content_id'],));assert not c.content_store_423.verify_integrity()['valid'];s=c.build423.content_status();assert s['version_coherent'];assert not s['stores_raw_payload'];assert not s['direct_network_authority']
 assert (ROOT/'src/eagleeye/interfaces/web/app423.py').exists()
