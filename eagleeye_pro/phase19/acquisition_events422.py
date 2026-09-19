from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='422.0';POLICY_ID='phase19.acquisition-event-provenance.v422'
METHODS=('http','api','rss','search','dataset','archive','social_api','registry','tor_public','manual_import')
STATUSES=('observed','retrieved','failed','blocked','quarantined')
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class AcquisitionEvents422:
 def __init__(self,db,audit,*,registry421,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS acquisition_event_422(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,method TEXT NOT NULL,status TEXT NOT NULL,retrieved_at TEXT NOT NULL,content_sha256 TEXT NOT NULL,media_type TEXT NOT NULL,bytes_count INTEGER NOT NULL,provenance_json TEXT NOT NULL,usage_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_ae422_case ON acquisition_event_422(case_id,retrieved_at);CREATE INDEX IF NOT EXISTS idx_ae422_source ON acquisition_event_422(source_id,retrieved_at);""");self.db.conn.commit()
 def _hash(self,r):return _sha({k:r[k] for k in r if k!='record_hash'})
 def record(self,*,identity,case_id,source_id,target,method,status='retrieved',content_sha256='',media_type='',bytes_count=0,provenance=None,usage=None,retrieved_at=''):
  if not identity:raise PermissionError('active identity required')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);case_id=str(case_id or '').strip();source_id=str(source_id or '').strip();target=str(target or '').strip();method=str(method or '').strip().lower();status=str(status or '').strip().lower()
  if not case_id:raise ValueError('case_id required')
  if not target:raise ValueError('target required')
  if method not in METHODS:raise ValueError('unsupported acquisition method')
  if status not in STATUSES:raise ValueError('unsupported acquisition status')
  sources=self.registry421.list_sources(enabled_only=False)
  if source_id not in {x['source_id'] for x in sources}:raise ValueError('unknown source_id')
  digest=str(content_sha256 or '').lower().strip()
  if digest and (len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)):raise ValueError('content_sha256 must be a SHA-256 hex digest')
  eid='acq422_'+secrets.token_hex(10);r={'event_id':eid,'case_id':case_id,'source_id':source_id,'target':target,'method':method,'status':status,'retrieved_at':retrieved_at or _now(),'content_sha256':digest,'media_type':str(media_type or ''),'bytes_count':max(0,int(bytes_count or 0)),'provenance_json':_canon(provenance or {}),'usage_json':_canon(usage or {}),'created_by':actor,'created_at':_now()};r['record_hash']=self._hash(r)
  self.db.execute('INSERT INTO acquisition_event_422 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('acquisition_event_recorded_422','acquisition_event_422',eid,case_id,{'source_id':source_id,'method':method,'status':status,'content_sha256':digest});return self.get(eid)
 def get(self,event_id):
  row=self.db.one('SELECT * FROM acquisition_event_422 WHERE event_id=?',(event_id,))
  if not row:raise KeyError(event_id)
  d=dict(row);d['provenance']=json.loads(d.pop('provenance_json'));d['usage']=json.loads(d.pop('usage_json'));return d
 def list_case(self,case_id):return [self.get(r['event_id']) for r in self.db.all('SELECT event_id FROM acquisition_event_422 WHERE case_id=? ORDER BY retrieved_at,event_id',(case_id,))]
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM acquisition_event_422'):
   d=dict(row)
   if self._hash(d)!=d['record_hash']:bad.append({'event_id':d['event_id'],'reason':'event_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM acquisition_event_422')['n'];return {'build':BUILD,'policy':POLICY_ID,'events':int(n),'integrity_valid':self.verify_integrity()['valid'],'methods':list(METHODS),'direct_network_authority':False,'evidence_promotion':False,'truth_determination':False}
