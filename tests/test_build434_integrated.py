from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
ROOT=Path(__file__).resolve().parents[1]
def ident(c):
 if c.team_identity_359.bootstrap_required():return c.team_identity_359.create_initial_admin(username='analyst',display_name='Analyst Fixture',password='SecureFixturePassword!2026')
 return c.team_identity_359.public_user('analyst')
def source(c):
 return c.build421.register_source(identity=ident(c),name='Registry 434',source_type='registry',base_url='https://registry.example.org',capabilities=['organization_records'])
def event_content(c,source_id,case_id,key,text='registry record'):
 i=ident(c);e=c.build422.record_event(identity=i,case_id=case_id,source_id=source_id,target='https://registry.example.org/record/'+key,method='registry');o=c.build423.ingest_content(identity=i,event_id=e['event_id'],content=text);return e,o
def record_payload(name='Example GmbH',number='HRB-123'):
 return {'legal_name':name,'organization_type':'company','jurisdiction':'DE','registration_status':'active','legal_form':'GmbH','address':'Example Street 1','website':'https://example.org','aliases':['Example'],'identifiers':[{'type':'registry_number','value':number,'jurisdiction':'DE','issuer':'Example Register'}],'people':[{'name':'Alice Example','role':'director'}]}
def test_registry_import_creates_provenance_bound_subject(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);e,o=event_content(c,s['source_id'],'case434','1')
  r=c.build434.import_registry_organization(identity=i,case_id='case434',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],registry_kind='company_registry',registry_name='Example Register',record_key='HRB-123',record=record_payload())
  assert r['case_id']=='case434';assert r['event_id']==e['event_id'];assert r['content_id']==o['content_id'];assert r['normalized']['auto_created_subject'] is True;assert r['normalized']['automatic_entity_resolution'] is False
  d=c.build433.organization_detail('case434',r['subject_id']);assert len(d['observations'])==1;assert d['observations'][0]['identifiers'][0]['value']=='HRB-123'
  cand=c.build434.registry_identifier_candidates('case434','registry_number','HRB-123');assert len(cand['candidates'])==1;assert cand['automatic_merge'] is False;assert cand['automatic_entity_resolution'] is False
def test_attach_existing_subject_and_relation_claim(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);a=c.build433.create_organization_subject(identity=i,case_id='attach434',display_name='Existing Org',organization_type='company');b=c.build433.create_organization_subject(identity=i,case_id='attach434',display_name='Parent Org',organization_type='company')
  e,o=event_content(c,s['source_id'],'attach434','2')
  r=c.build434.import_registry_organization(identity=i,case_id='attach434',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],registry_kind='company_registry',registry_name='Example Register',record_key='HRB-200',record=record_payload('Existing Org','HRB-200'),subject_id=a['subject_id'],relations=[{'target_subject_id':b['subject_id'],'relation_type':'parent','source_span':'Registry lists Parent Org'}])
  assert r['subject_id']==a['subject_id'];assert r['normalized']['auto_created_subject'] is False;assert len(r['relation_ids'])==1
  detail=c.build433.organization_detail('attach434',a['subject_id']);assert detail['relations'][0]['source_claim_only'] is True
def test_registry_record_dedup_is_case_scoped(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c)
  for case_id in ('case-one','case-two'):
   e,o=event_content(c,s['source_id'],case_id,case_id)
   c.build434.import_registry_organization(identity=i,case_id=case_id,source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],registry_kind='company_registry',registry_name='Example Register',record_key='SAME-1',record=record_payload('Same Company','SAME-1'))
  e,o=event_content(c,s['source_id'],'case-one','duplicate')
  try:c.build434.import_registry_organization(identity=i,case_id='case-one',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],registry_kind='company_registry',registry_name='Example Register',record_key='SAME-1',record=record_payload('Same Company','SAME-1'));assert False
  except ValueError:pass
  assert len(c.build434.case_registry_records('case-one'))==1;assert len(c.build434.case_registry_records('case-two'))==1
def test_invalid_relation_rejected_before_subject_creation(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  i=ident(c);s=source(c);target=c.build433.create_organization_subject(identity=i,case_id='guard434',display_name='Target');e,o=event_content(c,s['source_id'],'guard434','3')
  before=len(c.build433.case_organizations('guard434'))
  try:c.build434.import_registry_organization(identity=i,case_id='guard434',source_id=s['source_id'],event_id=e['event_id'],content_id=o['content_id'],registry_kind='company_registry',registry_name='Example Register',record_key='BAD-REL',record=record_payload('New Org','BAD-REL'),relations=[{'target_subject_id':target['subject_id'],'relation_type':'controls'}]);assert False
  except ValueError:pass
  assert len(c.build433.case_organizations('guard434'))==before
def test_case_selftest_and_integrity(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  r=c.build434.run_registry_case_selftest(identity=ident(c),case_id='selftest434');assert r['result']=='PASS';assert all(r['checks'].values());assert r['imported']['test_fixture'] is True
  report=c.build434.case_registry_report('selftest434');assert report['registry_records']==1;assert report['subjects']==1;assert report['automatic_entity_resolution'] is False;assert report['case_scoped'] is True
  c.db.execute("UPDATE registry_organization_record_434 SET registry_name='tampered' WHERE integration_id=?",(r['imported']['integration_id'],));assert not c.registry_organization_434.verify_integrity()['valid']
def test_contract_and_case_test_docs(tmp_path):
 with AppContext(base_dir=tmp_path) as c:
  s=c.build434.registry_organization_status();assert s['version_coherent'];assert s['phase19_builds_completed']==14;assert s['case_specific_selftest'];assert not s['network_authority'];assert not s['automatic_entity_resolution'];assert not s['automatic_merge'];assert not s['ownership_or_control_determination'];assert s['source_claims_are_not_verified_facts'];assert not s['production_release_ready']
 assert 'app434 import create_workspace_app434' in (ROOT/'src/eagleeye/interfaces/web/server.py').read_text();assert (ROOT/'BUILD_434_CASE_TEST.md').exists();readme=(ROOT/'README.md').read_text();assert 'EAGLEEYE_PRO_434_0.py' in readme and 'test_build434_integrated.py' in readme
