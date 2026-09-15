from __future__ import annotations
import hashlib,json,re
from typing import Any
from urllib.parse import urlparse,urlencode
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build171ConnectorExpansionFrameworkService:
 BUILD='171.0'
 LEVELS=('REGISTERED','FIXTURE_VALIDATED','SANDBOX_LIVE','PRODUCTION_READY','PRODUCTION_ACTIVE','DEGRADED','SUSPENDED','RETIRED')
 AUTH_TYPES={'none','api_key','bearer','oauth2_client_credentials','oauth2_authorization_code'}
 PAGINATION_TYPES={'none','cursor','page','offset','link_header','token'}
 def __init__(self,db:Any,audit:Any,*,runtime:Any,acceptance:Any,source_gate:Any,actor:str='system'):
  self.db,self.audit,self.runtime,self.acceptance,self.source_gate,self.actor=db,audit,runtime,acceptance,source_gate,actor
 def _validate_spec(self,s:dict)->dict:
  required={'connector_id','version','title','base_url','allowed_hosts','auth','pagination','input_schema','output_schema','normalization','provenance','limits'}
  missing=sorted(required-set(s));
  if missing: raise ValueError(f'missing connector fields: {missing}')
  cid=str(s['connector_id']).strip()
  if not re.fullmatch(r'[a-z][a-z0-9_]{2,63}',cid): raise ValueError('invalid connector_id')
  u=urlparse(str(s['base_url']))
  if u.scheme!='https' or not u.hostname or u.username or u.password: raise ValueError('base_url must be credential-free HTTPS')
  hosts=sorted({str(x).lower().strip('.') for x in s['allowed_hosts'] if str(x).strip()})
  if u.hostname.lower() not in hosts: raise ValueError('base host must be allowlisted')
  auth=dict(s['auth']); at=auth.get('type','none')
  if at not in self.AUTH_TYPES: raise ValueError('unsupported auth type')
  if at=='oauth2_authorization_code' and auth.get('pkce') is not True: raise ValueError('authorization-code connectors require PKCE')
  pag=dict(s['pagination']);
  if pag.get('type','none') not in self.PAGINATION_TYPES: raise ValueError('unsupported pagination type')
  limits=dict(s['limits'])
  for key,ceiling in [('timeout_seconds',120),('max_response_bytes',104857600),('max_pages',1000)]:
   value=int(limits.get(key,0));
   if value<1 or value>ceiling: raise ValueError(f'invalid {key}')
  for schema_name in ('input_schema','output_schema'):
   schema=s[schema_name]
   if not isinstance(schema,dict) or schema.get('type')!='object': raise ValueError(f'{schema_name} must be an object schema')
  out=dict(s); out['connector_id']=cid; out['allowed_hosts']=hosts; out['base_url']=str(s['base_url']).rstrip('/'); return out
 def register_spec(self,spec:dict,*,created_by:str|None=None,confirmation:str):
  s=self._validate_spec(spec); cid=s['connector_id']
  if confirmation!=f'CONNECTOR SDK 171 {cid} REGISTRIEREN': raise PermissionError('explicit SDK registration required')
  payload={**s,'lifecycle_status':'REGISTERED'}; sid=new_id('cspec171')
  self.db.execute('''INSERT OR REPLACE INTO connector_sdk_specs_171 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,cid,s['version'],s['title'],s['base_url'],dumps(s['allowed_hosts']),dumps(s['auth']),dumps(s['pagination']),dumps(s['input_schema']),dumps(s['output_schema']),dumps(s['normalization']),dumps(s['provenance']),dumps(s['limits']),'REGISTERED',created_by or self.actor,now_ts(),_hash(payload)))
  self.audit.log('connector_sdk_registered_171','connector',cid,'',{'version':s['version'],'status':'REGISTERED'})
  return {'spec_id':sid,'connector_id':cid,'status':'REGISTERED','payload_sha256':_hash(payload)}
 def add_fixture(self,connector_id:str,*,fixture_kind:str,payload:dict,expected:dict,confirmation:str):
  if confirmation!=f'FIXTURE 171 {connector_id} SPEICHERN': raise PermissionError('explicit fixture approval required')
  if not self.db.one('SELECT connector_id FROM connector_sdk_specs_171 WHERE connector_id=?',(connector_id,)): raise KeyError('connector not found')
  if fixture_kind not in {'success','empty','error','pagination'}: raise ValueError('invalid fixture kind')
  fid=new_id('fixture171'); item={'connector_id':connector_id,'kind':fixture_kind,'payload':payload,'expected':expected}
  self.db.execute('INSERT INTO connector_fixtures_171 VALUES(?,?,?,?,?,?,?)',(fid,connector_id,fixture_kind,dumps(payload),dumps(expected),now_ts(),_hash(item)))
  return {'fixture_id':fid,'payload_sha256':_hash(item)}
 def _schema_errors(self,value:Any,schema:dict,path:str='$')->list[str]:
  errors=[]; typ=schema.get('type')
  checks={'object':dict,'array':list,'string':str,'number':(int,float),'integer':int,'boolean':bool}
  if typ in checks and not isinstance(value,checks[typ]): return [f'{path}: expected {typ}']
  if typ=='object':
   for k in schema.get('required',[]):
    if k not in value: errors.append(f'{path}.{k}: required')
   for k,sub in schema.get('properties',{}).items():
    if k in value: errors.extend(self._schema_errors(value[k],sub,f'{path}.{k}'))
  elif typ=='array':
   for i,v in enumerate(value): errors.extend(self._schema_errors(v,schema.get('items',{}),f'{path}[{i}]'))
  return errors
 def run_contract_tests(self,connector_id:str,*,created_by:str|None=None,confirmation:str):
  if confirmation!=f'CONTRACT 171 {connector_id} PRUEFEN': raise PermissionError('explicit contract test approval required')
  row=self.db.one('SELECT * FROM connector_sdk_specs_171 WHERE connector_id=?',(connector_id,));
  if not row: raise KeyError('connector not found')
  fixtures=self.db.all('SELECT * FROM connector_fixtures_171 WHERE connector_id=? ORDER BY created_at',(connector_id,))
  failures=[]; checks={'fixture_count':len(fixtures),'https':str(row['base_url']).startswith('https://'),'host_allowlist':bool(json.loads(row['allowed_hosts_json'])),'schema_draft':'2020-12-compatible-subset','secret_free_spec':True}
  output_schema=json.loads(row['output_schema_json'])
  for f in fixtures:
   expected=json.loads(f['expected_json']); payload=json.loads(f['payload_json'])
   if f['fixture_kind']=='success': failures.extend([f"{f['fixture_id']} {e}" for e in self._schema_errors(payload,output_schema)])
   if 'record_count' in expected and expected['record_count']!=len(payload if isinstance(payload,list) else payload.get('records',[])): failures.append(f"{f['fixture_id']} record_count mismatch")
  if not fixtures: failures.append('no fixtures registered')
  status='passed' if not failures else 'failed'; rid=new_id('contract171'); result={'run_id':rid,'connector_id':connector_id,'status':status,'checks':checks,'failures':failures}
  self.db.execute('INSERT INTO connector_contract_runs_171 VALUES(?,?,?,?,?,?,?,?)',(rid,connector_id,status,dumps(checks),dumps(failures),created_by or self.actor,now_ts(),_hash(result)))
  if status=='passed': self._transition(connector_id,'FIXTURE_VALIDATED','contract tests passed',created_by or self.actor)
  return result
 def _transition(self,connector_id:str,to_status:str,reason:str,actor:str):
  row=self.db.one('SELECT lifecycle_status FROM connector_sdk_specs_171 WHERE connector_id=?',(connector_id,));
  if not row: raise KeyError('connector not found')
  old=row['lifecycle_status']; eid=new_id('life171'); payload={'connector_id':connector_id,'from':old,'to':to_status,'reason':reason}
  self.db.execute('UPDATE connector_sdk_specs_171 SET lifecycle_status=? WHERE connector_id=?',(to_status,connector_id))
  self.db.execute('INSERT INTO connector_lifecycle_events_171 VALUES(?,?,?,?,?,?,?,?)',(eid,connector_id,old,to_status,reason,actor,now_ts(),_hash(payload)))
 def promote(self,connector_id:str,to_status:str,*,reason:str,actor:str|None=None,confirmation:str):
  if to_status not in self.LEVELS: raise ValueError('invalid lifecycle status')
  if confirmation!=f'CONNECTOR SDK 171 {connector_id} {to_status}': raise PermissionError('explicit lifecycle approval required')
  row=self.db.one('SELECT lifecycle_status FROM connector_sdk_specs_171 WHERE connector_id=?',(connector_id,));
  if not row: raise KeyError('connector not found')
  current=row['lifecycle_status']; ci=self.LEVELS.index(current); ti=self.LEVELS.index(to_status)
  if to_status not in {'DEGRADED','SUSPENDED','RETIRED'} and ti>ci+1: raise RuntimeError('lifecycle stages may not be skipped')
  if to_status=='SANDBOX_LIVE' and current!='FIXTURE_VALIDATED': raise RuntimeError('fixture validation required')
  if to_status in {'PRODUCTION_READY','PRODUCTION_ACTIVE'}:
   readiness=self.acceptance.readiness(connector_id)
   if readiness.get('readiness') not in {'production_ready'}: raise RuntimeError('operational acceptance required')
  self._transition(connector_id,to_status,reason,actor or self.actor); return {'connector_id':connector_id,'from_status':current,'to_status':to_status}
 def prepare_request(self,connector_id:str,*,path:str='',params:dict|None=None):
  row=self.db.one('SELECT * FROM connector_sdk_specs_171 WHERE connector_id=?',(connector_id,));
  if not row: raise KeyError('connector not found')
  if row['lifecycle_status'] in {'SUSPENDED','RETIRED'}: raise RuntimeError('connector unavailable')
  base=row['base_url'].rstrip('/'); safe_path='/' + path.lstrip('/') if path else ''
  url=base+safe_path; host=urlparse(url).hostname.lower(); hosts=json.loads(row['allowed_hosts_json'])
  if host not in hosts: raise PermissionError('host not allowlisted')
  clean={k:v for k,v in (params or {}).items() if not any(x in k.lower() for x in ('token','secret','password','api_key','authorization','cookie'))}
  return {'connector_id':connector_id,'url':url+('?' + urlencode(clean,doseq=True) if clean else ''),'auth_reference_only':True,'timeout_seconds':json.loads(row['limits_json'])['timeout_seconds'],'review_required':True}
 def snapshot(self,*,created_by:str|None=None,confirmation:str):
  if confirmation!='CONNECTOR SDK 171 SNAPSHOT ERSTELLEN': raise PermissionError('explicit snapshot approval required')
  rows=[dict(r) for r in self.db.all('SELECT connector_id,version,title,lifecycle_status,base_url FROM connector_sdk_specs_171 ORDER BY connector_id')]
  manifest={'build':self.BUILD,'connectors':rows,'sdk_contract':{'json_schema':'2020-12-compatible','openapi':'3.1-compatible','oauth_security':'RFC9700-aligned','automatic_activation':False,'review_required':True}}
  sid=new_id('sdksnap171'); self.db.execute('INSERT INTO connector_sdk_snapshots_171 VALUES(?,?,?,?,?)',(sid,dumps(manifest),created_by or self.actor,now_ts(),_hash(manifest)))
  return {'snapshot_id':sid,'manifest':manifest,'payload_sha256':_hash(manifest)}
 def dashboard(self):
  rows=self.db.all('SELECT lifecycle_status,COUNT(*) n FROM connector_sdk_specs_171 GROUP BY lifecycle_status')
  return {'build':self.BUILD,'levels':list(self.LEVELS),'counts':{r['lifecycle_status']:r['n'] for r in rows},'core_business':'review-first person OSINT connector expansion','automatic_activation':False}
