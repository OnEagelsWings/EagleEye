from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from urllib.parse import urlsplit
BUILD='421.0'; POLICY_ID='phase19.acquisition-source-registry.v421'
SOURCE_TYPES=('api','rss','website','search','dataset','archive','social','registry','ngo','government','news','tor_onion')
ACCESS_MODES=('public','api_key','oauth','licensed','local_dataset','tor_public')
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class AcquisitionSourceRegistry421:
 def __init__(self,db,audit,*,source_registry405,governance,actor='local-analyst'): self.db=db; self.audit=audit; self.source_registry405=source_registry405; self.governance=governance; self.actor=actor; self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS acquisition_source_421(source_id TEXT PRIMARY KEY,name TEXT NOT NULL,source_type TEXT NOT NULL,access_mode TEXT NOT NULL,base_url TEXT NOT NULL,capabilities_json TEXT NOT NULL,coverage_json TEXT NOT NULL,terms_url TEXT NOT NULL,license_note TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_as421_type ON acquisition_source_421(source_type,enabled);"""); self.db.conn.commit()
 def _record_hash(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
 def _identity(self,identity):
  if not isinstance(identity,dict) or not identity.get('username') or not identity.get('user_id'):raise PermissionError('canonical active identity required')
  try:user=self.governance.identity.public_user(identity['username'])
  except (KeyError,ValueError):raise PermissionError('canonical active identity required')
  if not user.get('active') or str(user.get('user_id'))!=str(identity.get('user_id')):raise PermissionError('canonical active identity required')
  return {**user,'session_id':str(identity.get('session_id') or 'service421')}
 def _validate_url(self,url,*,onion=False):
  u=str(url or '').strip()
  if not u:return ''
  p=urlsplit(u)
  if p.scheme not in {'http','https'} or not p.hostname:raise ValueError('base_url must be an absolute http(s) URL')
  if onion and not p.hostname.lower().endswith('.onion'):raise ValueError('tor_onion source requires an .onion hostname')
  if not onion and p.hostname.lower().endswith('.onion'):raise ValueError('.onion sources must use source_type=tor_onion')
  return u
 def register(self,*,identity,name,source_type,access_mode='public',base_url='',capabilities=(),coverage=None,terms_url='',license_note=''):
  ident=self._identity(identity); self.governance.identity.require_global(ident,'source.manage'); actor=str(ident['username']); name=str(name or '').strip(); st=str(source_type or '').strip().lower(); am=str(access_mode or '').strip().lower()
  if not name:raise ValueError('name required')
  if st not in SOURCE_TYPES:raise ValueError('unsupported source_type')
  if am not in ACCESS_MODES:raise ValueError('unsupported access_mode')
  base=self._validate_url(base_url,onion=st=='tor_onion'); terms=self._validate_url(terms_url) if terms_url else ''; caps=sorted({str(x).strip().lower() for x in capabilities if str(x).strip()})
  if not caps:raise ValueError('at least one capability required')
  sid='src421_'+secrets.token_hex(10); r={'source_id':sid,'name':name,'source_type':st,'access_mode':am,'base_url':base,'capabilities_json':_canon(caps),'coverage_json':_canon(coverage or {}),'terms_url':terms,'license_note':str(license_note or '').strip(),'enabled':1,'created_by':actor,'created_at':_now()}; r['record_hash']=self._record_hash(r)
  self.db.execute('INSERT INTO acquisition_source_421 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('acquisition_source_registered_421','acquisition_source_421',sid,'',{'source_type':st,'access_mode':am,'capabilities':caps}); return {**r,'capabilities':caps,'coverage':coverage or {}}
 def get(self,source_id):
  row=self.db.one('SELECT * FROM acquisition_source_421 WHERE source_id=?',(str(source_id),))
  if not row:raise KeyError('source not found')
  d=dict(row);d['capabilities']=json.loads(d.pop('capabilities_json'));d['coverage']=json.loads(d.pop('coverage_json'));return d
 def list_sources(self,*,source_type='',capability='',enabled_only=True):
  sql='SELECT * FROM acquisition_source_421'; args=[]; where=[]
  if source_type:where.append('source_type=?');args.append(str(source_type).lower())
  if enabled_only:where.append('enabled=1')
  if where:sql+=' WHERE '+' AND '.join(where)
  sql+=' ORDER BY name,source_id'; out=[]
  for row in self.db.all(sql,tuple(args)):
   d=dict(row);d['capabilities']=json.loads(d.pop('capabilities_json'));d['coverage']=json.loads(d.pop('coverage_json'))
   if capability and str(capability).lower() not in d['capabilities']:continue
   out.append(d)
  return out
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM acquisition_source_421'):
   d=dict(row)
   if self._record_hash(d)!=d['record_hash']:bad.append({'source_id':d['source_id'],'reason':'source_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  rows=self.db.all('SELECT source_type,COUNT(*) n FROM acquisition_source_421 WHERE enabled=1 GROUP BY source_type')
  return {'build':BUILD,'policy':POLICY_ID,'registered_sources':sum(int(r['n']) for r in rows),'by_type':{r['source_type']:int(r['n']) for r in rows},'supported_source_types':list(SOURCE_TYPES),'supported_access_modes':list(ACCESS_MODES),'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'credential_collection':False,'access_control_bypass':False,'autonomous_scope_expansion':False}
