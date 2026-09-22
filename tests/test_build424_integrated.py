from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def source(c):
 return c.build421.register_source(identity=ident(c),name='Source 424',source_type='news',base_url='https://example.org',capabilities=['articles'])
def test_health_and_advice(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=source(c);c.build424.record_source_health(identity=ident(c),source_id=s['source_id'],state='rate_limited',http_status=429,latency_ms=250,quota_remaining=0,quota_limit=100,retry_after_seconds=60);a=c.build424.acquisition_advice(s['source_id']);assert a['decision']=='defer';assert a['retry_after_seconds']==60
def test_health_validation_and_integrity(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=source(c)
  try:c.build424.record_source_health(identity=ident(c),source_id=s['source_id'],state='healthy',quota_remaining=11,quota_limit=10);assert False
  except ValueError:pass
  x=c.build424.record_source_health(identity=ident(c),source_id=s['source_id'],state='healthy',latency_ms=12);c.db.execute("UPDATE source_health_event_424 SET state='unavailable' WHERE health_event_id=?",(x['health_event_id'],));assert not c.source_health_424.verify_integrity()['valid']
def test_build424_contract(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build424.source_health_status();assert s['version_coherent'];assert s['phase19_builds_completed']==4;assert not s['direct_network_authority'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app424.py').exists()
