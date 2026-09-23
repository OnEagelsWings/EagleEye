from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def source(c):
 return c.build421.register_source(identity=ident(c),name='Social 432',source_type='social',base_url='https://social.example.org',capabilities=['public_posts','profiles'])
def test_case_scoped_fixture_and_isolation(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c)
  a=c.build432.ingest_social_fixture(identity=i,case_id='case-a',source_id=s['source_id'],adapter='mastodon_public',canonical_url='https://social.example.org/@alice/1',text='public fixture A',external_object_id='1',account_handle='@alice',published_at='2026-09-22T10:00:00+02:00',language='de',metrics={'likes':2,'replies':1})
  b=c.build432.ingest_social_fixture(identity=i,case_id='case-b',source_id=s['source_id'],adapter='mastodon_public',canonical_url='https://social.example.org/@alice/2',text='public fixture B',external_object_id='2',account_handle='@alice',published_at='2026-09-22T08:30:00Z',language='de')
  aa=c.build432.case_social('case-a');bb=c.build432.case_social('case-b')
  assert [x['observation_id'] for x in aa]==[a['observation']['observation_id']];assert [x['observation_id'] for x in bb]==[b['observation']['observation_id']]
  assert aa[0]['platform']=='mastodon';assert aa[0]['published_at']=='2026-09-22T08:00:00+00:00';assert aa[0]['test_fixture'] is True
def test_adapter_contract_rejects_private_and_credentials(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);e=c.build422.record_event(identity=i,case_id='case432',source_id=s['source_id'],target='https://social.example.org/post/1',method='social_api');o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content='public post')
  try:c.build432.record_social_observation(identity=i,case_id='case432',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],adapter='bluesky_public',platform='bluesky',canonical_url='https://bsky.app/profile/example/post/1',external_object_id='p1',visibility='direct');assert False
  except ValueError:pass
  try:c.build432.record_social_observation(identity=i,case_id='case432',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],adapter='generic_public',canonical_url='https://social.example.org/post/1',external_object_id='p2',metadata={'api_token':'secret'});assert False
  except ValueError:pass
def test_case_selftest_one_step(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  r=c.build432.run_case_selftest(identity=ident(c),case_id='case-selftest-432');assert r['result']=='PASS';assert all(r['checks'].values());assert r['fixture']['observation']['test_fixture'] is True
  report=c.build432.case_social_report('case-selftest-432');assert report['observations']==1;assert report['test_fixtures']==1;assert report['case_scoped'] is True
def test_integrity_and_duplicate_guard(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);a=c.build432.ingest_social_fixture(identity=i,case_id='dup432',source_id=s['source_id'],adapter='generic_public',canonical_url='https://social.example.org/posts/dup',text='fixture',external_object_id='dup')
  try:c.build432.ingest_social_fixture(identity=i,case_id='dup432',source_id=s['source_id'],adapter='generic_public',canonical_url='https://social.example.org/posts/dup2',text='fixture2',external_object_id='dup');assert False
  except ValueError:pass
  c.db.execute("UPDATE social_observation_432 SET account_handle='tampered' WHERE observation_id=?",(a['observation']['observation_id'],));assert not c.social_public_432.verify_integrity()['valid']
def test_contract_and_case_test_docs(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build432.social_status();assert s['version_coherent'];assert s['phase19_builds_completed']==12;assert s['case_specific_selftest'];assert s['public_only'];assert not s['network_executor_implemented'];assert not s['credential_collection'];assert not s['private_or_direct_content_supported'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app432.py').exists();assert (ROOT/'BUILD_432_CASE_TEST.md').exists()
