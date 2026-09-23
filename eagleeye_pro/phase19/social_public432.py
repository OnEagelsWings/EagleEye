from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,ipaddress,json,secrets
BUILD='432.0';POLICY_ID='phase19.social-public-adapters.v432'
ADAPTERS=('mastodon_public','bluesky_public','generic_public')
OBJECT_TYPES=('post','profile','thread','account')
VISIBILITY=('public','unlisted','unknown')
_SENSITIVE=('token','password','secret','cookie','authorization','credential','api_key','apikey')
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _iso_utc(v):
 d=datetime.fromisoformat(str(v).replace('Z','+00:00'));d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc);return d.isoformat(timespec='seconds')
def _public_url(v):
 u=str(v or '').strip();p=urlparse(u)
 if p.scheme not in {'http','https'} or not p.hostname:raise ValueError('canonical_url must be an absolute public http(s) URL')
 if p.username or p.password:raise ValueError('URL credentials are not allowed')
 h=p.hostname.casefold()
 if h=='localhost' or h.endswith('.onion'):raise ValueError('canonical_url must be public and non-onion')
 try:
  ip=ipaddress.ip_address(h)
  if not ip.is_global:raise ValueError('canonical_url literal IP must be globally routable')
 except ValueError as e:
  if 'globally routable' in str(e):raise
 return u
def _safe_metadata(v):
 def walk(x):
  if isinstance(x,dict):
   out={}
   for k,val in x.items():
    key=str(k)
    if any(s in key.casefold() for s in _SENSITIVE):raise ValueError('credential-like metadata keys are not allowed')
    out[key]=walk(val)
   return out
  if isinstance(x,list):return [walk(i) for i in x[:100]]
  if isinstance(x,(str,int,float,bool)) or x is None:return x
  return str(x)
 out=walk(v or {})
 if len(_canon(out).encode('utf-8'))>65536:raise ValueError('metadata too large')
 return out
def _metrics(v):
 out={}
 for k,val in (v or {}).items():
  key=str(k).strip().lower()
  if not key or len(key)>64:raise ValueError('invalid metric name')
  try:n=int(val)
  except Exception:raise ValueError('social metrics must be integers')
  if n<0:raise ValueError('social metrics must be >= 0')
  out[key]=n
 return dict(sorted(out.items()))
class SocialPublicAdapters432:
 def __init__(self,db,audit,*,registry421,events422,content423,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS social_observation_432(observation_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,adapter TEXT NOT NULL,platform TEXT NOT NULL,object_type TEXT NOT NULL,external_object_id TEXT NOT NULL,account_id TEXT NOT NULL,account_handle TEXT NOT NULL,canonical_url TEXT NOT NULL,published_at TEXT NOT NULL,visibility TEXT NOT NULL,language TEXT NOT NULL,reply_to_external_id TEXT NOT NULL,reshare_of_external_id TEXT NOT NULL,metrics_json TEXT NOT NULL,metadata_json TEXT NOT NULL,test_fixture INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE UNIQUE INDEX IF NOT EXISTS idx_so432_external ON social_observation_432(source_id,adapter,object_type,external_object_id);CREATE INDEX IF NOT EXISTS idx_so432_case_time ON social_observation_432(case_id,published_at);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def record(self,*,identity,case_id,source_id,event_id,content_id,adapter,canonical_url,external_object_id,platform='',object_type='post',account_id='',account_handle='',published_at='',visibility='public',language='',reply_to_external_id='',reshare_of_external_id='',metrics=None,metadata=None,test_fixture=False):
  if not identity:raise PermissionError('active identity required')
  case_id=str(case_id or '').strip();source_id=str(source_id or '').strip();adapter=str(adapter or '').strip().lower();object_type=str(object_type or '').strip().lower();visibility=str(visibility or '').strip().lower()
  if not case_id:raise ValueError('case_id required')
  if adapter not in ADAPTERS:raise ValueError('unsupported social adapter')
  if object_type not in OBJECT_TYPES:raise ValueError('unsupported social object_type')
  if visibility not in VISIBILITY:raise ValueError('only public/unlisted/unknown public-source visibility is accepted')
  src=self.registry421.get(source_id)
  if src['source_type']!='social':raise ValueError('source_id must identify a social source')
  ev=self.events422.get(event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('social event does not match case/source')
  if ev['method'] not in {'social_api','api','http','manual_import'}:raise ValueError('acquisition method is not compatible with public social data')
  obs=self.db.one('SELECT 1 FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id))
  if not obs:raise ValueError('content is not linked to acquisition event')
  ext=str(external_object_id or '').strip()
  if not ext:raise ValueError('external_object_id required')
  if len(ext)>500:raise ValueError('external_object_id too long')
  url=_public_url(canonical_url)
  try:ts=_iso_utc(published_at or ev['retrieved_at'])
  except Exception:raise ValueError('published_at must be ISO-8601')
  expected={'mastodon_public':'mastodon','bluesky_public':'bluesky'}.get(adapter,'')
  platform=str(platform or expected or 'generic').strip().lower()
  if expected and platform!=expected:raise ValueError('platform does not match adapter')
  m=_metrics(metrics);meta=_safe_metadata(metadata)
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'observation_id':'soc432_'+secrets.token_hex(10),'case_id':case_id,'source_id':source_id,'event_id':event_id,'content_id':content_id,'adapter':adapter,'platform':platform,'object_type':object_type,'external_object_id':ext,'account_id':str(account_id or '')[:300],'account_handle':str(account_handle or '')[:200],'canonical_url':url,'published_at':ts,'visibility':visibility,'language':str(language or '').lower().strip()[:32],'reply_to_external_id':str(reply_to_external_id or '')[:500],'reshare_of_external_id':str(reshare_of_external_id or '')[:500],'metrics_json':_canon(m),'metadata_json':_canon(meta),'test_fixture':1 if test_fixture else 0,'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r)
  try:self.db.execute('INSERT INTO social_observation_432 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()))
  except Exception as e:
   if 'UNIQUE' in str(e).upper():raise ValueError('duplicate social object for this source/adapter')
   raise
  self.audit.log('social_public_observation_recorded_432','social_observation_432',r['observation_id'],case_id,{'adapter':adapter,'platform':platform,'object_type':object_type,'test_fixture':bool(test_fixture)});return {**r,'metrics':m,'metadata':meta,'test_fixture':bool(test_fixture)}
 def ingest_fixture(self,*,identity,case_id,source_id,adapter,canonical_url,text,external_object_id,platform='',object_type='post',account_id='',account_handle='',published_at='',language='',metrics=None,metadata=None):
  raw=str(text or '').encode('utf-8')
  if not raw:raise ValueError('fixture text required')
  digest=hashlib.sha256(raw).hexdigest()
  event=self.events422.record(identity=identity,case_id=case_id,source_id=source_id,target=canonical_url,method='manual_import',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(raw),provenance={'build':'432.0','adapter':adapter,'test_fixture':True,'canonical_url':canonical_url},usage={'public_only':True,'synthetic_test_fixture':True})
  content=self.content423.ingest(identity=identity,event_id=event['event_id'],content=raw,media_type='text/plain',metadata={'build432_test_fixture':True,'adapter':adapter})
  item=self.record(identity=identity,case_id=case_id,source_id=source_id,event_id=event['event_id'],content_id=content['content_id'],adapter=adapter,canonical_url=canonical_url,external_object_id=external_object_id,platform=platform,object_type=object_type,account_id=account_id,account_handle=account_handle,published_at=published_at or event['retrieved_at'],visibility='public',language=language,metrics=metrics,metadata={**(metadata or {}),'synthetic_test_fixture':True},test_fixture=True)
  return {'event':event,'content':content,'observation':item}
 def case_items(self,case_id,*,platform='',adapter='',include_fixtures=True):
  sql='SELECT * FROM social_observation_432 WHERE case_id=?';args=[str(case_id)]
  if platform:sql+=' AND platform=?';args.append(str(platform).lower())
  if adapter:sql+=' AND adapter=?';args.append(str(adapter).lower())
  if not include_fixtures:sql+=' AND test_fixture=0'
  sql+=' ORDER BY julianday(published_at) DESC,created_at DESC';out=[]
  for row in self.db.all(sql,tuple(args)):
   d=dict(row);d['metrics']=json.loads(d['metrics_json']);d['metadata']=json.loads(d['metadata_json']);d['test_fixture']=bool(d['test_fixture']);out.append(d)
  return out
 def case_report(self,case_id):
  rows=self.case_items(case_id);by_platform={};by_adapter={};by_type={}
  for r in rows:
   by_platform[r['platform']]=by_platform.get(r['platform'],0)+1;by_adapter[r['adapter']]=by_adapter.get(r['adapter'],0)+1;by_type[r['object_type']]=by_type.get(r['object_type'],0)+1
  return {'build':BUILD,'case_id':str(case_id),'observations':len(rows),'test_fixtures':sum(1 for r in rows if r['test_fixture']),'by_platform':by_platform,'by_adapter':by_adapter,'by_object_type':by_type,'source_ids':sorted({r['source_id'] for r in rows}),'integrity_valid':self.verify_integrity()['valid'],'case_scoped':True}
 def run_case_selftest(self,*,identity,case_id):
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  fixture_base='https://build432.example.invalid'
  source=next((s for s in self.registry421.list_sources(source_type='social') if s.get('base_url')==fixture_base),None)
  if not source:source=self.registry421.register(identity=identity,name='Build 432 Synthetic Social Fixture',source_type='social',access_mode='public',base_url=fixture_base,capabilities=['public_posts','case_fixture'],coverage={'fixture_only':True},license_note='Synthetic Build 432 case test source; no network retrieval.')
  token=secrets.token_hex(6);url=fixture_base+'/posts/'+token
  result=self.ingest_fixture(identity=identity,case_id=case_id,source_id=source['source_id'],adapter='generic_public',canonical_url=url,text='Synthetic Build 432 public-social case fixture '+token,external_object_id='fixture-'+token,platform='generic',account_id='fixture-account',account_handle='@fixture',language='en',metrics={'likes':0,'replies':0},metadata={'case_selftest':True})
  oid=result['observation']['observation_id'];items=self.case_items(case_id)
  checks={'case_bound':result['observation']['case_id']==case_id,'event_bound':result['observation']['event_id']==result['event']['event_id'],'content_bound':result['observation']['content_id']==result['content']['content_id'],'fixture_visible_in_case':any(x['observation_id']==oid for x in items),'integrity_valid':self.verify_integrity()['valid'],'network_authority_absent':True}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'fixture':result,'note':'Synthetic fixture remains tagged test_fixture=true; use a dedicated test case when possible.'}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM social_observation_432'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'observation_id':d['observation_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM social_observation_432')['n'];f=self.db.one('SELECT COUNT(*) n FROM social_observation_432 WHERE test_fixture=1')['n'];return {'build':BUILD,'policy':POLICY_ID,'observations':int(n),'test_fixtures':int(f),'supported_adapters':list(ADAPTERS),'supported_object_types':list(OBJECT_TYPES),'integrity_valid':self.verify_integrity()['valid'],'network_executor_implemented':False,'public_only':True,'credential_collection':False,'private_or_direct_content_supported':False,'production_release_ready':False}
