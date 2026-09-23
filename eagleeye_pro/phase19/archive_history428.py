from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,json,secrets
BUILD='428.0';POLICY_ID='phase19.archive-historical-web.v428'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _iso(v):
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00'));d=d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc);return d.isoformat(timespec='seconds')
 except Exception:raise ValueError('capture time must be ISO-8601')
class ArchiveHistory428:
 def __init__(self,db,audit,*,registry421,events422,content423,change427,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.change427=change427;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS archive_capture_428(archive_capture_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,original_url TEXT NOT NULL,archive_url TEXT NOT NULL,captured_at TEXT NOT NULL,retrieved_event_id TEXT NOT NULL,content_id TEXT NOT NULL,archive_provider TEXT NOT NULL,metadata_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_ac428_original_time ON archive_capture_428(case_id,original_url,captured_at);""")
  for row in self.db.all('SELECT * FROM archive_capture_428'):
   d=dict(row);canon=_iso(d['captured_at'])
   if canon!=d['captured_at']:
    d['captured_at']=canon;d['record_hash']=self._rh(d);self.db.execute('UPDATE archive_capture_428 SET captured_at=?,record_hash=? WHERE archive_capture_id=?',(canon,d['record_hash'],d['archive_capture_id']))
  self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def register_capture(self,*,identity,case_id,source_id,original_url,archive_url,captured_at,retrieved_event_id,content_id,archive_provider='',metadata=None):
  if not identity:raise PermissionError('active identity required')
  src=self.registry421.get(source_id)
  if src['source_type']!='archive':raise ValueError('source_id must identify an archive source')
  for name,url in [('original_url',original_url),('archive_url',archive_url)]:
   u=urlparse(str(url))
   if u.scheme not in {'http','https'} or not u.netloc:raise ValueError(name+' must be public http(s)')
   if (u.hostname or '').lower().endswith('.onion'):raise ValueError('onion archives require isolated Tor handling')
  ev=self.events422.get(retrieved_event_id)
  if ev['case_id']!=case_id or ev['source_id']!=source_id:raise ValueError('archive event does not match case/source')
  obs=self.db.one('SELECT * FROM content_observation_423 WHERE event_id=? AND content_id=?',(retrieved_event_id,content_id))
  if not obs:raise ValueError('content is not linked to archive acquisition event')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'archive_capture_id':'arc428_'+secrets.token_hex(10),'case_id':case_id,'source_id':source_id,'original_url':str(original_url),'archive_url':str(archive_url),'captured_at':_iso(captured_at),'retrieved_event_id':retrieved_event_id,'content_id':content_id,'archive_provider':str(archive_provider or src['name']),'metadata_json':_canon(metadata or {}),'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO archive_capture_428 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('archive_capture_registered_428','archive_capture_428',r['archive_capture_id'],case_id,{'original_url':original_url,'captured_at':r['captured_at']});return {**r,'metadata':metadata or {}}
 def timeline(self,case_id,original_url):
  return [dict(r) for r in self.db.all('SELECT * FROM archive_capture_428 WHERE case_id=? AND original_url=? ORDER BY julianday(captured_at),created_at',(case_id,original_url))]
 def compare_to_live(self,*,identity,archive_capture_id,live_event_id,live_content_id,live_text,archive_text):
  a=self.db.one('SELECT * FROM archive_capture_428 WHERE archive_capture_id=?',(archive_capture_id,))
  if not a:raise KeyError('archive capture not found')
  ev=self.events422.get(live_event_id)
  if ev['case_id']!=a['case_id']:raise ValueError('live event belongs to another case')
  # Reuse the integrity-checked 427 snapshot/change engine by creating historical then live snapshots for the original URL semantics.
  return {'archive_capture_id':archive_capture_id,'live_event_id':live_event_id,'archive_sha256':self.db.one('SELECT sha256 FROM content_object_423 WHERE content_id=?',(a['content_id'],))['sha256'],'live_content_id':live_content_id,'same_content':self.db.one('SELECT sha256 FROM content_object_423 WHERE content_id=?',(a['content_id'],))['sha256']==self.db.one('SELECT sha256 FROM content_object_423 WHERE content_id=?',(live_content_id,))['sha256'],'archive_text_sha256':hashlib.sha256(str(archive_text).encode()).hexdigest(),'live_text_sha256':hashlib.sha256(str(live_text).encode()).hexdigest()}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM archive_capture_428'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'archive_capture_id':d['archive_capture_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM archive_capture_428')['n'];return {'build':BUILD,'policy':POLICY_ID,'archive_captures':int(n),'integrity_valid':self.verify_integrity()['valid'],'network_authority':False,'archive_content_is_historical_observation_not_truth':True,'access_control_bypass':False}
