from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='424.0';POLICY_ID='phase19.source-health.v424'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _iso_utc(value):
 d=datetime.fromisoformat(str(value).replace('Z','+00:00'));d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc);return d.isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class SourceHealth424:
 def __init__(self,db,audit,*,registry421,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS source_health_event_424(health_event_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,observed_at TEXT NOT NULL,state TEXT NOT NULL,http_status INTEGER,latency_ms INTEGER,quota_remaining INTEGER,quota_limit INTEGER,retry_after_seconds INTEGER,freshness_at TEXT,error_class TEXT NOT NULL,metadata_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_sh424_source_time ON source_health_event_424(source_id,observed_at);""");self.db.conn.commit()
 def _row_hash(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def record(self,*,identity,source_id,state,http_status=None,latency_ms=None,quota_remaining=None,quota_limit=None,retry_after_seconds=None,freshness_at=None,error_class='',metadata=None,observed_at=None):
  if not identity:raise PermissionError('active identity required')
  self.registry421.get(source_id)
  if state not in {'healthy','degraded','rate_limited','unavailable','unknown'}:raise ValueError('invalid source health state')
  for name,v in [('latency_ms',latency_ms),('quota_remaining',quota_remaining),('quota_limit',quota_limit),('retry_after_seconds',retry_after_seconds)]:
   if v is not None and int(v)<0:raise ValueError(name+' must be >= 0')
  if quota_remaining is not None and quota_limit is not None and int(quota_remaining)>int(quota_limit):raise ValueError('quota_remaining exceeds quota_limit')
  try:observed=_iso_utc(observed_at or _now())
  except Exception:raise ValueError('observed_at must be ISO-8601')
  if freshness_at:
   try:freshness_at=_iso_utc(freshness_at)
   except Exception:raise ValueError('freshness_at must be ISO-8601')
  if http_status is not None and not 100<=int(http_status)<=599:raise ValueError('http_status must be between 100 and 599')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'health_event_id':'sh424_'+secrets.token_hex(10),'source_id':source_id,'observed_at':observed,'state':state,'http_status':http_status,'latency_ms':latency_ms,'quota_remaining':quota_remaining,'quota_limit':quota_limit,'retry_after_seconds':retry_after_seconds,'freshness_at':freshness_at,'error_class':str(error_class or ''),'metadata_json':_canon(metadata or {}),'created_by':actor,'created_at':_now()};r['record_hash']=self._row_hash(r);self.db.execute('INSERT INTO source_health_event_424 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('source_health_recorded_424','acquisition_source_421',source_id,None,{'health_event_id':r['health_event_id'],'state':state});return r
 def latest(self,source_id):
  self.registry421.get(source_id);r=self.db.one('SELECT * FROM source_health_event_424 WHERE source_id=? ORDER BY julianday(observed_at) DESC,created_at DESC LIMIT 1',(source_id,));return dict(r) if r else None
 def acquisition_advice(self,source_id):
  r=self.latest(source_id)
  if not r:return {'source_id':source_id,'decision':'unknown','reason':'no_health_observation','retry_after_seconds':None}
  decision='allow'
  if r['state']=='rate_limited':decision='defer'
  elif r['state']=='unavailable':decision='avoid'
  elif r['state']=='degraded':decision='allow_cautious'
  return {'source_id':source_id,'decision':decision,'reason':r['state'],'retry_after_seconds':r['retry_after_seconds'],'quota_remaining':r['quota_remaining'],'freshness_at':r['freshness_at']}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM source_health_event_424'):
   d=dict(row)
   if self._row_hash(d)!=d['record_hash']:bad.append({'health_event_id':d['health_event_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM source_health_event_424')['n'];return {'build':BUILD,'policy':POLICY_ID,'health_events':int(n),'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'autonomous_scope_expansion':False,'capabilities':['availability','latency','quota','retry_after','freshness','error_state']}
