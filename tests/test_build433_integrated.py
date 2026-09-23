from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def source(c,name='Org Source 433'):
 return c.build421.register_source(identity=ident(c),name=name,source_type='ngo',base_url='https://org.example.org',capabilities=['organization_profiles'])
def event_content(c,source_id,case_id,text='organization record'):
 i=ident(c);e=c.build422.record_event(identity=i,case_id=case_id,source_id=source_id,target='https://org.example.org/record',method='manual_import');o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content=text);return e,o
def test_subject_observation_and_conflict_surface(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);sub=c.build433.create_organization_subject(identity=i,case_id='case433',display_name='Example Association',organization_type='association',jurisdiction='DE',status='active',website='https://example.org',aliases=['EA'])
  e1,o1=event_content(c,s['source_id'],'case433','record one');c.build433.record_organization_observation(identity=i,case_id='case433',subject_id=sub['subject_id'],source_id=s['source_id'],event_id=e1['event_id'],content_id=o1['content_id'],attributes={'legal_name':'Example Association e.V.','jurisdiction':'DE'},identifiers=[{'type':'registry','value':'VR123','jurisdiction':'DE'}],people=[{'name':'Alice Example','role':'board member'}])
  e2,o2=event_content(c,s['source_id'],'case433','record two');c.build433.record_organization_observation(identity=i,case_id='case433',subject_id=sub['subject_id'],source_id=s['source_id'],event_id=e2['event_id'],content_id=o2['content_id'],attributes={'legal_name':'Example Association','jurisdiction':'DE'})
  d=c.build433.organization_detail('case433',sub['subject_id']);assert d['subject']['display_name']=='Example Association';assert len(d['observations'])==2;assert 'legal_name' in d['conflicts'];assert d['automatic_entity_resolution'] is False;assert d['source_claims_are_not_verified_facts'] is True
def test_relation_is_source_claim_and_case_isolated(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);a=c.build433.create_organization_subject(identity=i,case_id='case-a',display_name='Org A');b=c.build433.create_organization_subject(identity=i,case_id='case-a',display_name='Org B');other=c.build433.create_organization_subject(identity=i,case_id='case-b',display_name='Org Other')
  e,o=event_content(c,s['source_id'],'case-a')
  r=c.build433.record_organization_relation(identity=i,case_id='case-a',source_subject_id=a['subject_id'],target_subject_id=b['subject_id'],relation_type='partner',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],source_span='public partnership statement');assert r['source_claim_only'] is True
  try:c.build433.record_organization_relation(identity=i,case_id='case-a',source_subject_id=a['subject_id'],target_subject_id=other['subject_id'],relation_type='affiliate',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id']);assert False
  except ValueError:pass
  assert len(c.build433.organization_detail('case-a',a['subject_id'])['relations'])==1
def test_case_selftest_and_report(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  r=c.build433.run_organization_case_selftest(identity=ident(c),case_id='selftest433');assert r['result']=='PASS';assert all(r['checks'].values());assert r['observation']['test_fixture'] is True;assert r['relation']['test_fixture'] is True
  report=c.build433.case_organization_report('selftest433');assert report['subjects']==2;assert report['observations']==1;assert report['relation_claims']==1;assert report['case_scoped'] is True;assert report['source_claims_are_not_verified_facts'] is True
def test_tamper_detection_and_metadata_guard(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);sub=c.build433.create_organization_subject(identity=i,case_id='tamper433',display_name='Org');e,o=event_content(c,s['source_id'],'tamper433')
  try:c.build433.record_organization_observation(identity=i,case_id='tamper433',subject_id=sub['subject_id'],source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],metadata={'api_token':'secret'});assert False
  except ValueError:pass
  ob=c.build433.record_organization_observation(identity=i,case_id='tamper433',subject_id=sub['subject_id'],source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],attributes={'legal_name':'Org'})
  c.db.execute("UPDATE organization_observation_433 SET observed_name='tampered' WHERE observation_id=?",(ob['observation_id'],));assert not c.organization_intelligence_433.verify_integrity()['valid']
def test_contract_and_case_test_docs(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build433.organization_status();assert s['version_coherent'];assert s['phase19_builds_completed']==13;assert s['case_specific_selftest'];assert not s['network_authority'];assert not s['automatic_entity_resolution'];assert not s['ownership_or_control_determination'];assert s['source_claims_are_not_verified_facts'];assert not s['production_release_ready']
 assert (ROOT/'src/eagleeye/interfaces/web/app433.py').exists();assert (ROOT/'BUILD_433_CASE_TEST.md').exists()
