from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,ipaddress,json,re,secrets
BUILD='433.0';POLICY_ID='phase19.organization-intelligence.v433'
ORG_TYPES=('company','ngo','foundation','association','government','education','religious','media','union','network','other','unknown')
ORG_STATUS=('active','inactive','dissolved','unknown')
RELATION_TYPES=('parent','subsidiary','affiliate','partner','member','funder','grantee','trade_name','predecessor','successor')
SOURCE_TYPES=('registry','ngo','government','website','news','api','dataset','archive','social')
_SENSITIVE=('token','password','secret','cookie','authorization','credential','api_key','apikey')
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _iso(v):
 d=datetime.fromisoformat(str(v).replace('Z','+00:00'));d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc);return d.isoformat(timespec='seconds')
def _public_url(v):
 s=str(v or '').strip()
 if not s:return ''
 p=urlparse(s)
 if p.scheme not in {'http','https'} or not p.hostname:raise ValueError('website must be an absolute public http(s) URL')
 if p.username or p.password:raise ValueError('URL credentials are not allowed')
 h=p.hostname.casefold()
 if h=='localhost' or h.endswith('.onion'):raise ValueError('website must be public and non-onion')
 try:
  ip=ipaddress.ip_address(h)
  if not ip.is_global:raise ValueError('website literal IP must be globally routable')
 except ValueError as e:
  if 'globally routable' in str(e):raise
 return s
def _clean_text(v,limit=500):
 return re.sub(r'\s+',' ',str(v or '')).strip()[:limit]
def _safe_json(v,*,limit=65536):
 if v is None:return {}
 if not isinstance(v,dict):raise ValueError('metadata must be a JSON object')
 def walk(x):
  if isinstance(x,dict):
   out={}
   for k,val in x.items():
    key=str(k)
    if any(s in key.casefold() for s in _SENSITIVE):raise ValueError('credential-like metadata keys are not allowed')
    out[key]=walk(val)
   return out
  if isinstance(x,list):return [walk(i) for i in x[:200]]
  if isinstance(x,(str,int,float,bool)) or x is None:return x
  return str(x)
 out=walk(v)
 if len(_canon(out).encode('utf-8'))>limit:raise ValueError('metadata too large')
 return out
def _aliases(v):
 if v is None:return []
 if not isinstance(v,(list,tuple,set)):raise ValueError('aliases must be a list')
 return sorted({_clean_text(x,300) for x in v if _clean_text(x,300)})
def _identifiers(v):
 if v is None:return []
 if not isinstance(v,list):raise ValueError('identifiers must be a list')
 out=[]
 for x in v[:100]:
  if not isinstance(x,dict):raise ValueError('identifier entries must be objects')
  typ=_clean_text(x.get('type'),80).lower();value=_clean_text(x.get('value'),300)
  if not typ or not value:raise ValueError('identifier type and value required')
  out.append({'type':typ,'value':value,'jurisdiction':_clean_text(x.get('jurisdiction'),120),'issuer':_clean_text(x.get('issuer'),200)})
 return out
def _people(v):
 if v is None:return []
 if not isinstance(v,list):raise ValueError('people must be a list')
 out=[]
 for x in v[:200]:
  if not isinstance(x,dict):raise ValueError('people entries must be objects')
  name=_clean_text(x.get('name'),300);role=_clean_text(x.get('role'),200)
  if not name or not role:raise ValueError('person name and role required')
  out.append({'name':name,'role':role,'source_claim':True})
 return out
def _attributes(v):
 if v is None:return {}
 if not isinstance(v,dict):raise ValueError('attributes must be a JSON object')
 allowed=('legal_name','organization_type','jurisdiction','registration_status','address','website','founded_at','dissolved_at','purpose','legal_form')
 out={}
 for k in allowed:
  if k not in v:continue
  val=_clean_text(v.get(k),1000)
  if k=='website' and val:val=_public_url(val)
  if k=='organization_type' and val and val.lower() not in ORG_TYPES:raise ValueError('unsupported organization_type')
  out[k]=val
 return out
class OrganizationIntelligence433:
 def __init__(self,db,audit,*,registry421,events422,content423,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS organization_subject_433(subject_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,display_name TEXT NOT NULL,organization_type TEXT NOT NULL,jurisdiction TEXT NOT NULL,status TEXT NOT NULL,website TEXT NOT NULL,aliases_json TEXT NOT NULL,notes TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_os433_case ON organization_subject_433(case_id,display_name);
CREATE TABLE IF NOT EXISTS organization_observation_433(observation_id TEXT PRIMARY KEY,subject_id TEXT NOT NULL,case_id TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,observed_name TEXT NOT NULL,observed_at TEXT NOT NULL,attributes_json TEXT NOT NULL,identifiers_json TEXT NOT NULL,people_json TEXT NOT NULL,metadata_json TEXT NOT NULL,test_fixture INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_oo433_subject ON organization_observation_433(subject_id,observed_at);CREATE INDEX IF NOT EXISTS idx_oo433_case ON organization_observation_433(case_id,observed_at);
CREATE TABLE IF NOT EXISTS organization_relation_claim_433(relation_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_subject_id TEXT NOT NULL,target_subject_id TEXT NOT NULL,relation_type TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,source_span TEXT NOT NULL,test_fixture INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_or433_case ON organization_relation_claim_433(case_id,source_subject_id,target_subject_id);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _subject(self,subject_id):
  row=self.db.one('SELECT * FROM organization_subject_433 WHERE subject_id=?',(str(subject_id),))
  if not row:raise KeyError('organization subject not found')
  d=dict(row);d['aliases']=json.loads(d['aliases_json']);return d
 def create_subject(self,*,identity,case_id,display_name,organization_type='unknown',jurisdiction='',status='unknown',website='',aliases=None,notes=''):
  if not identity:raise PermissionError('active identity required')
  case_id=str(case_id or '').strip();name=_clean_text(display_name,500);typ=str(organization_type or 'unknown').strip().lower();status=str(status or 'unknown').strip().lower()
  if not case_id or not name:raise ValueError('case_id and display_name required')
  if typ not in ORG_TYPES:raise ValueError('unsupported organization_type')
  if status not in ORG_STATUS:raise ValueError('unsupported organization status')
  sid='org433_'+secrets.token_hex(10);actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'subject_id':sid,'case_id':case_id,'display_name':name,'organization_type':typ,'jurisdiction':_clean_text(jurisdiction,200),'status':status,'website':_public_url(website) if website else '','aliases_json':_canon(_aliases(aliases)),'notes':_clean_text(notes,2000),'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO organization_subject_433 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('organization_subject_created_433','organization_subject_433',sid,case_id,{'display_name':name,'organization_type':typ});return {**r,'aliases':json.loads(r['aliases_json'])}
 def record_observation(self,*,identity,case_id,subject_id,source_id,event_id,content_id,observed_name='',observed_at='',attributes=None,identifiers=None,people=None,metadata=None,test_fixture=False):
  if not identity:raise PermissionError('active identity required')
  sub=self._subject(subject_id);case_id=str(case_id or '').strip()
  if sub['case_id']!=case_id:raise ValueError('organization subject belongs to another case')
  src=self.registry421.get(source_id)
  if src['source_type'] not in SOURCE_TYPES:raise ValueError('source type is not supported for organization intelligence')
  ev=self.events422.get(event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('organization event does not match case/source')
  if not self.db.one('SELECT 1 FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id)):raise ValueError('content is not linked to acquisition event')
  try:ts=_iso(observed_at or ev['retrieved_at'])
  except Exception:raise ValueError('observed_at must be ISO-8601')
  attrs=_attributes(attributes);ids=_identifiers(identifiers);persons=_people(people);meta=_safe_json(metadata);actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'observation_id':'oob433_'+secrets.token_hex(10),'subject_id':subject_id,'case_id':case_id,'source_id':source_id,'event_id':event_id,'content_id':content_id,'observed_name':_clean_text(observed_name or sub['display_name'],500),'observed_at':ts,'attributes_json':_canon(attrs),'identifiers_json':_canon(ids),'people_json':_canon(persons),'metadata_json':_canon(meta),'test_fixture':1 if test_fixture else 0,'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO organization_observation_433 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('organization_observation_recorded_433','organization_observation_433',r['observation_id'],case_id,{'subject_id':subject_id,'source_id':source_id,'test_fixture':bool(test_fixture)});return {**r,'attributes':attrs,'identifiers':ids,'people':persons,'metadata':meta,'test_fixture':bool(test_fixture)}
 def record_relation(self,*,identity,case_id,source_subject_id,target_subject_id,relation_type,source_id,event_id,content_id,source_span='',test_fixture=False):
  if not identity:raise PermissionError('active identity required')
  a=self._subject(source_subject_id);b=self._subject(target_subject_id);case_id=str(case_id or '').strip();typ=str(relation_type or '').strip().lower()
  if a['case_id']!=case_id or b['case_id']!=case_id:raise ValueError('both organization subjects must belong to the same case')
  if source_subject_id==target_subject_id:raise ValueError('self relation is not allowed')
  if typ not in RELATION_TYPES:raise ValueError('unsupported organization relation type')
  ev=self.events422.get(event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('relation event does not match case/source')
  if not self.db.one('SELECT 1 FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id)):raise ValueError('content is not linked to acquisition event')
  rid='orel433_'+secrets.token_hex(10);actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'relation_id':rid,'case_id':case_id,'source_subject_id':source_subject_id,'target_subject_id':target_subject_id,'relation_type':typ,'source_id':source_id,'event_id':event_id,'content_id':content_id,'source_span':_clean_text(source_span,1000),'test_fixture':1 if test_fixture else 0,'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO organization_relation_claim_433 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('organization_relation_claim_recorded_433','organization_relation_claim_433',rid,case_id,{'relation_type':typ,'source_subject_id':source_subject_id,'target_subject_id':target_subject_id,'source_claim_only':True});return {**r,'test_fixture':bool(test_fixture),'source_claim_only':True}
 def list_subjects(self,case_id):
  out=[]
  for row in self.db.all('SELECT * FROM organization_subject_433 WHERE case_id=? ORDER BY display_name,subject_id',(str(case_id),)):
   d=dict(row);d['aliases']=json.loads(d['aliases_json']);out.append(d)
  return out
 def subject_detail(self,case_id,subject_id):
  sub=self._subject(subject_id)
  if sub['case_id']!=str(case_id):raise KeyError('organization subject not found in case')
  obs=[]
  for row in self.db.all('SELECT * FROM organization_observation_433 WHERE subject_id=? ORDER BY julianday(observed_at),created_at',(subject_id,)):
   d=dict(row);d['attributes']=json.loads(d['attributes_json']);d['identifiers']=json.loads(d['identifiers_json']);d['people']=json.loads(d['people_json']);d['metadata']=json.loads(d['metadata_json']);d['test_fixture']=bool(d['test_fixture']);obs.append(d)
  rel=[dict(r) for r in self.db.all('SELECT * FROM organization_relation_claim_433 WHERE case_id=? AND (source_subject_id=? OR target_subject_id=?) ORDER BY created_at',(str(case_id),subject_id,subject_id))]
  for r in rel:r['test_fixture']=bool(r['test_fixture']);r['source_claim_only']=True
  values={}
  for o in obs:
   for k,v in o['attributes'].items():
    if v:values.setdefault(k,[]).append({'value':v,'source_id':o['source_id'],'observation_id':o['observation_id']})
  conflicts={k:v for k,v in values.items() if len({x['value'] for x in v})>1}
  return {'build':BUILD,'subject':sub,'observations':obs,'relations':rel,'attribute_values':values,'conflicts':conflicts,'automatic_entity_resolution':False,'source_claims_are_not_verified_facts':True}
 def case_report(self,case_id):
  subjects=self.list_subjects(case_id);obs=[dict(r) for r in self.db.all('SELECT * FROM organization_observation_433 WHERE case_id=?',(str(case_id),))];rels=[dict(r) for r in self.db.all('SELECT * FROM organization_relation_claim_433 WHERE case_id=?',(str(case_id),))];conflicts=0
  for s in subjects:conflicts+=len(self.subject_detail(case_id,s['subject_id'])['conflicts'])
  return {'build':BUILD,'case_id':str(case_id),'subjects':len(subjects),'observations':len(obs),'relation_claims':len(rels),'test_fixtures':sum(int(r['test_fixture']) for r in obs)+sum(int(r['test_fixture']) for r in rels),'distinct_sources':len({r['source_id'] for r in obs}|{r['source_id'] for r in rels}),'attribute_conflicts':conflicts,'integrity_valid':self.verify_integrity()['valid'],'source_claims_are_not_verified_facts':True,'automatic_entity_resolution':False,'case_scoped':True}
 def run_case_selftest(self,*,identity,case_id):
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  base='https://build433.example.invalid';source=next((s for s in self.registry421.list_sources(source_type='ngo') if s.get('base_url')==base),None)
  if not source:source=self.registry421.register(identity=identity,name='Build 433 Synthetic Organization Fixture',source_type='ngo',access_mode='public',base_url=base,capabilities=['organization_profiles','case_fixture'],coverage={'fixture_only':True},license_note='Synthetic Build 433 case test source; no network retrieval.')
  token=secrets.token_hex(5);a=self.create_subject(identity=identity,case_id=case_id,display_name='Synthetic Association '+token,organization_type='association',jurisdiction='DE',status='active',website=base+'/association/'+token,aliases=['Synthetic Assoc '+token]);b=self.create_subject(identity=identity,case_id=case_id,display_name='Synthetic Foundation '+token,organization_type='foundation',jurisdiction='DE',status='active',website=base+'/foundation/'+token)
  text='Synthetic organization record for case self-test '+token;raw=text.encode();digest=hashlib.sha256(raw).hexdigest();ev=self.events422.record(identity=identity,case_id=case_id,source_id=source['source_id'],target=base+'/record/'+token,method='manual_import',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(raw),provenance={'build':'433.0','test_fixture':True},usage={'public_only':True,'synthetic_test_fixture':True});content=self.content423.ingest(identity=identity,event_id=ev['event_id'],content=raw,media_type='text/plain',metadata={'build433_test_fixture':True})
  ob=self.record_observation(identity=identity,case_id=case_id,subject_id=a['subject_id'],source_id=source['source_id'],event_id=ev['event_id'],content_id=content['content_id'],observed_name=a['display_name'],attributes={'legal_name':a['display_name'],'organization_type':'association','jurisdiction':'DE','registration_status':'active','website':a['website']},identifiers=[{'type':'fixture_registry_id','value':'FIX-'+token,'jurisdiction':'DE','issuer':'Synthetic Registry'}],people=[{'name':'Fixture Person','role':'board member'}],metadata={'synthetic_test_fixture':True},test_fixture=True)
  rel=self.record_relation(identity=identity,case_id=case_id,source_subject_id=a['subject_id'],target_subject_id=b['subject_id'],relation_type='partner',source_id=source['source_id'],event_id=ev['event_id'],content_id=content['content_id'],source_span='Synthetic partnership claim',test_fixture=True)
  detail=self.subject_detail(case_id,a['subject_id']);report=self.case_report(case_id);checks={'case_bound':a['case_id']==case_id and b['case_id']==case_id and ob['case_id']==case_id and rel['case_id']==case_id,'event_bound':ob['event_id']==ev['event_id'] and rel['event_id']==ev['event_id'],'content_bound':ob['content_id']==content['content_id'] and rel['content_id']==content['content_id'],'identifier_preserved':ob['identifiers'][0]['value']=='FIX-'+token,'relation_is_source_claim':rel['source_claim_only'] is True,'subject_visible_in_case':any(x['subject_id']==a['subject_id'] for x in self.list_subjects(case_id)),'automatic_resolution_absent':detail['automatic_entity_resolution'] is False,'integrity_valid':self.verify_integrity()['valid'],'network_authority_absent':True}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'subjects':[a,b],'observation':ob,'relation':rel,'report':report,'note':'Synthetic records are tagged as fixtures; use a dedicated test case when possible.'}
 def verify_integrity(self):
  bad=[]
  for table,key in [('organization_subject_433','subject_id'),('organization_observation_433','observation_id'),('organization_relation_claim_433','relation_id')]:
   for row in self.db.all('SELECT * FROM '+table):
    d=dict(row)
    if self._rh(d)!=d['record_hash']:bad.append({key:d[key],'table':table,'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  s=self.db.one('SELECT COUNT(*) n FROM organization_subject_433')['n'];o=self.db.one('SELECT COUNT(*) n FROM organization_observation_433')['n'];r=self.db.one('SELECT COUNT(*) n FROM organization_relation_claim_433')['n'];return {'build':BUILD,'policy':POLICY_ID,'subjects':int(s),'observations':int(o),'relation_claims':int(r),'supported_organization_types':list(ORG_TYPES),'supported_relation_types':list(RELATION_TYPES),'integrity_valid':self.verify_integrity()['valid'],'network_authority':False,'automatic_entity_resolution':False,'ownership_or_control_determination':False,'source_claims_are_not_verified_facts':True,'case_specific_selftest':True,'production_release_ready':False}
