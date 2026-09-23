from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='434.0';POLICY_ID='phase19.registry-organization-integration.v434'
REGISTRY_KINDS=('company_registry','association_registry','charity_registry','ngo_registry','government_registry','lei_registry','generic_registry')
SOURCE_TYPES=('registry','government','ngo','api','dataset')
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(v,limit=1000):return ' '.join(str(v or '').split())[:limit]
def _payload(v,name):
 if v is None:return {}
 if not isinstance(v,dict):raise ValueError(name+' must be a JSON object')
 return v
class RegistryOrganizationIntegration434:
 def __init__(self,db,audit,*,registry421,events422,content423,organization433,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.organization433=organization433;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS registry_organization_record_434(integration_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,subject_id TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,registry_kind TEXT NOT NULL,registry_name TEXT NOT NULL,record_key TEXT NOT NULL,jurisdiction TEXT NOT NULL,record_status TEXT NOT NULL,normalized_json TEXT NOT NULL,relation_ids_json TEXT NOT NULL,test_fixture INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE UNIQUE INDEX IF NOT EXISTS idx_ror434_record ON registry_organization_record_434(source_id,registry_kind,record_key);CREATE INDEX IF NOT EXISTS idx_ror434_case ON registry_organization_record_434(case_id,subject_id);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _decode(self,row):
  d=dict(row);d['normalized']=json.loads(d['normalized_json']);d['relation_ids']=json.loads(d['relation_ids_json']);d['test_fixture']=bool(d['test_fixture']);return d
 def import_record(self,*,identity,case_id,source_id,event_id,content_id,registry_kind,registry_name,record_key,record,subject_id='',relations=None,test_fixture=False):
  if not identity:raise PermissionError('active identity required')
  case_id=str(case_id or '').strip();kind=str(registry_kind or '').strip().lower();key=_clean(record_key,500);name=_clean(registry_name,300);data=_payload(record,'record')
  if not case_id or not key or not name:raise ValueError('case_id, registry_name and record_key required')
  if kind not in REGISTRY_KINDS:raise ValueError('unsupported registry_kind')
  src=self.registry421.get(source_id)
  if src['source_type'] not in SOURCE_TYPES:raise ValueError('source type is not registry/organization capable')
  ev=self.events422.get(event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('registry event does not match case/source')
  if not self.db.one('SELECT 1 FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id)):raise ValueError('content is not linked to acquisition event')
  if self.db.one('SELECT 1 FROM registry_organization_record_434 WHERE source_id=? AND registry_kind=? AND record_key=?',(source_id,kind,key)):raise ValueError('registry record already imported')
  legal_name=_clean(data.get('legal_name') or data.get('name'),500)
  if not legal_name:raise ValueError('record legal_name or name required')
  org_type=_clean(data.get('organization_type') or 'unknown',80).lower();jurisdiction=_clean(data.get('jurisdiction'),200);record_status=_clean(data.get('registration_status') or data.get('status') or 'unknown',100).lower()
  aliases=data.get('aliases') or [];identifiers=data.get('identifiers') or [];people=data.get('people') or []
  if not isinstance(aliases,list) or not isinstance(identifiers,list) or not isinstance(people,list):raise ValueError('aliases, identifiers and people must be lists')
  attrs={k:data.get(k) for k in ('legal_name','organization_type','jurisdiction','registration_status','address','website','founded_at','dissolved_at','purpose','legal_form') if data.get(k) not in (None,'')}
  attrs['legal_name']=legal_name
  if org_type:attrs['organization_type']=org_type
  if jurisdiction:attrs['jurisdiction']=jurisdiction
  if record_status:attrs['registration_status']=record_status
  rels=relations or []
  if not isinstance(rels,list):raise ValueError('relations must be a list')
  checked_relations=[]
  for rel in rels:
   if not isinstance(rel,dict):raise ValueError('relation entries must be objects')
   target=str(rel.get('target_subject_id') or '').strip();typ=str(rel.get('relation_type') or '').strip().lower()
   if not target or not typ:raise ValueError('relation target_subject_id and relation_type required')
   target_sub=self.organization433._subject(target)
   if target_sub['case_id']!=case_id:raise ValueError('relation target belongs to another case')
   checked_relations.append({'target_subject_id':target,'relation_type':typ,'source_span':_clean(rel.get('source_span'),1000)})
  if subject_id:
   sub=self.organization433._subject(subject_id)
   if sub['case_id']!=case_id:raise ValueError('organization subject belongs to another case')
  else:
   sub=self.organization433.create_subject(identity=identity,case_id=case_id,display_name=legal_name,organization_type=org_type,jurisdiction=jurisdiction,status=record_status if record_status in {'active','inactive','dissolved','unknown'} else 'unknown',website=data.get('website',''),aliases=aliases,notes='Created from '+kind+' record '+key);subject_id=sub['subject_id']
  observation=self.organization433.record_observation(identity=identity,case_id=case_id,subject_id=subject_id,source_id=source_id,event_id=event_id,content_id=content_id,observed_name=legal_name,observed_at=data.get('observed_at',''),attributes=attrs,identifiers=identifiers,people=people,metadata={'registry_kind':kind,'registry_name':name,'record_key':key,'record_payload_metadata':data.get('metadata') or {},'registry_import_build':'434.0'},test_fixture=test_fixture)
  relation_ids=[]
  for rel in checked_relations:
   rr=self.organization433.record_relation(identity=identity,case_id=case_id,source_subject_id=subject_id,target_subject_id=rel['target_subject_id'],relation_type=rel['relation_type'],source_id=source_id,event_id=event_id,content_id=content_id,source_span=rel['source_span'],test_fixture=test_fixture);relation_ids.append(rr['relation_id'])
  normalized={'legal_name':legal_name,'organization_type':org_type,'jurisdiction':jurisdiction,'record_status':record_status,'aliases':aliases,'identifiers':identifiers,'people':people,'attributes':attrs,'observation_id':observation['observation_id'],'auto_created_subject':not bool(str(subject_id or '').strip() and False),'automatic_entity_resolution':False,'source_claims_are_not_verified_facts':True}
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'integration_id':'regorg434_'+secrets.token_hex(10),'case_id':case_id,'subject_id':subject_id,'source_id':source_id,'event_id':event_id,'content_id':content_id,'registry_kind':kind,'registry_name':name,'record_key':key,'jurisdiction':jurisdiction,'record_status':record_status,'normalized_json':_canon(normalized),'relation_ids_json':_canon(relation_ids),'test_fixture':1 if test_fixture else 0,'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO registry_organization_record_434 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('registry_organization_imported_434','registry_organization_record_434',r['integration_id'],case_id,{'subject_id':subject_id,'registry_kind':kind,'record_key':key,'relations':len(relation_ids),'test_fixture':bool(test_fixture)});return {**r,'normalized':normalized,'relation_ids':relation_ids,'test_fixture':bool(test_fixture),'observation':observation}
 def case_records(self,case_id):
  return [self._decode(r) for r in self.db.all('SELECT * FROM registry_organization_record_434 WHERE case_id=? ORDER BY created_at,integration_id',(str(case_id),))]
 def identifier_candidates(self,case_id,identifier_type,value):
  typ=_clean(identifier_type,80).lower();val=_clean(value,300)
  if not typ or not val:raise ValueError('identifier type and value required')
  out=[]
  for sub in self.organization433.list_subjects(case_id):
   detail=self.organization433.subject_detail(case_id,sub['subject_id']);matches=[]
   for ob in detail['observations']:
    for ident in ob['identifiers']:
     if str(ident.get('type','')).casefold()==typ.casefold() and str(ident.get('value','')).casefold()==val.casefold():matches.append({'observation_id':ob['observation_id'],'source_id':ob['source_id'],'identifier':ident})
   if matches:out.append({'subject_id':sub['subject_id'],'display_name':sub['display_name'],'matches':matches,'candidate_only':True})
  return {'build':BUILD,'case_id':str(case_id),'identifier_type':typ,'value':val,'candidates':out,'automatic_merge':False,'automatic_entity_resolution':False}
 def case_report(self,case_id):
  rows=self.case_records(case_id);return {'build':BUILD,'case_id':str(case_id),'registry_records':len(rows),'subjects':len({r['subject_id'] for r in rows}),'registries':sorted({r['registry_name'] for r in rows}),'registry_kinds':sorted({r['registry_kind'] for r in rows}),'jurisdictions':sorted({r['jurisdiction'] for r in rows if r['jurisdiction']}),'relation_claims_created':sum(len(r['relation_ids']) for r in rows),'test_fixtures':sum(1 for r in rows if r['test_fixture']),'integrity_valid':self.verify_integrity()['valid'],'automatic_entity_resolution':False,'source_claims_are_not_verified_facts':True,'case_scoped':True}
 def run_case_selftest(self,*,identity,case_id):
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  base='https://build434.example.invalid';source=next((s for s in self.registry421.list_sources(source_type='registry') if s.get('base_url')==base),None)
  if not source:source=self.registry421.register(identity=identity,name='Build 434 Synthetic Registry',source_type='registry',access_mode='public',base_url=base,capabilities=['organization_records','case_fixture'],coverage={'fixture_only':True},license_note='Synthetic Build 434 registry fixture; no network retrieval.')
  token=secrets.token_hex(5);text='Synthetic registry record '+token;raw=text.encode();digest=hashlib.sha256(raw).hexdigest();ev=self.events422.record(identity=identity,case_id=case_id,source_id=source['source_id'],target=base+'/record/'+token,method='registry',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(raw),provenance={'build':'434.0','test_fixture':True},usage={'public_only':True,'synthetic_test_fixture':True});content=self.content423.ingest(identity=identity,event_id=ev['event_id'],content=raw,media_type='text/plain',metadata={'build434_test_fixture':True})
  rec={'legal_name':'Synthetic Registry Organization '+token,'organization_type':'company','jurisdiction':'DE','registration_status':'active','legal_form':'GmbH','address':'Fixture Street 1','website':base+'/org/'+token,'aliases':['SRO '+token],'identifiers':[{'type':'registry_number','value':'HRB-'+token.upper(),'jurisdiction':'DE','issuer':'Synthetic Register'}],'people':[{'name':'Fixture Director','role':'director'}],'metadata':{'synthetic_test_fixture':True}}
  imported=self.import_record(identity=identity,case_id=case_id,source_id=source['source_id'],event_id=ev['event_id'],content_id=content['content_id'],registry_kind='company_registry',registry_name='Synthetic Company Register',record_key='record-'+token,record=rec,test_fixture=True);candidate=self.identifier_candidates(case_id,'registry_number','HRB-'+token.upper());report=self.case_report(case_id);checks={'case_bound':imported['case_id']==case_id,'event_bound':imported['event_id']==ev['event_id'],'content_bound':imported['content_id']==content['content_id'],'subject_created':bool(imported['subject_id']),'identifier_candidate_found':len(candidate['candidates'])==1 and candidate['candidates'][0]['subject_id']==imported['subject_id'],'automatic_merge_absent':candidate['automatic_merge'] is False,'automatic_resolution_absent':candidate['automatic_entity_resolution'] is False,'integrity_valid':self.verify_integrity()['valid'],'network_authority_absent':True}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'imported':imported,'identifier_lookup':candidate,'report':report,'note':'Synthetic registry data is tagged test_fixture=true. Build 434 does not perform automatic entity resolution.'}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM registry_organization_record_434'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'integration_id':d['integration_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM registry_organization_record_434')['n'];return {'build':BUILD,'policy':POLICY_ID,'registry_records':int(n),'supported_registry_kinds':list(REGISTRY_KINDS),'integrity_valid':self.verify_integrity()['valid'],'network_authority':False,'automatic_entity_resolution':False,'automatic_merge':False,'ownership_or_control_determination':False,'source_claims_are_not_verified_facts':True,'case_specific_selftest':True,'production_release_ready':False}
