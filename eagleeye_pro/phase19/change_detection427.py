from __future__ import annotations
from datetime import datetime,timezone
import difflib,hashlib,json,re,secrets
BUILD='427.0';POLICY_ID='phase19.incremental-change-detection.v427'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _norm(s):return re.sub(r'\s+',' ',str(s or '')).strip()
class ChangeDetection427:
 def __init__(self,db,audit,*,events422,content423,crawler425,actor='local-analyst'):self.db=db;self.audit=audit;self.events422=events422;self.content423=content423;self.crawler425=crawler425;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS source_snapshot_427(snapshot_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,content_sha256 TEXT NOT NULL,text_normalized TEXT NOT NULL,captured_at TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_ss427_target ON source_snapshot_427(case_id,source_id,target,captured_at);CREATE TABLE IF NOT EXISTS content_change_427(change_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,previous_snapshot_id TEXT NOT NULL,current_snapshot_id TEXT NOT NULL,change_kind TEXT NOT NULL,similarity REAL NOT NULL,added_json TEXT NOT NULL,removed_json TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _record_change(self,previous,current):
  a=previous['text_normalized'];b=current['text_normalized'];ratio=difflib.SequenceMatcher(None,a,b).ratio();kind='unchanged' if previous['content_sha256']==current['content_sha256'] else ('minor' if ratio>=.95 else 'changed')
  diff=list(difflib.ndiff(a.split(),b.split()));added=[v[2:] for v in diff if v.startswith('+ ')][:100];removed=[v[2:] for v in diff if v.startswith('- ')][:100]
  ch={'change_id':'chg427_'+secrets.token_hex(10),'case_id':current['case_id'],'source_id':current['source_id'],'target':current['target'],'previous_snapshot_id':previous['snapshot_id'],'current_snapshot_id':current['snapshot_id'],'change_kind':kind,'similarity':float(ratio),'added_json':_canon(added),'removed_json':_canon(removed),'created_at':_now()};ch['record_hash']=self._rh(ch)
  self.db.execute('INSERT INTO content_change_427 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(ch.values()))
  return {**ch,'added':added,'removed':removed}
 def capture(self,*,identity,event_id,content_id,text):
  if not identity:raise PermissionError('active identity required')
  ev=self.events422.get(event_id);obj=self.db.one('SELECT * FROM content_object_423 WHERE content_id=?',(content_id,))
  if not obj:raise KeyError('content object not found')
  obs=self.db.one('SELECT * FROM content_observation_423 WHERE event_id=? AND content_id=?',(event_id,content_id))
  if not obs:raise ValueError('content_id is not linked to event_id')
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);norm=_norm(text)
  if obj['text_fingerprint'] and hashlib.sha256(norm.lower().encode()).hexdigest()!=obj['text_fingerprint']:raise ValueError('snapshot text does not match referenced content')
  sid='snap427_'+secrets.token_hex(10)
  r={'snapshot_id':sid,'case_id':ev['case_id'],'source_id':ev['source_id'],'target':ev['target'],'event_id':event_id,'content_id':content_id,'content_sha256':obj['sha256'],'text_normalized':norm,'captured_at':ev['retrieved_at'],'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r)
  prev=self.db.one("SELECT * FROM source_snapshot_427 WHERE case_id=? AND source_id=? AND target=? AND datetime(captured_at)<=datetime(?) ORDER BY datetime(captured_at) DESC,rowid DESC LIMIT 1",(ev['case_id'],ev['source_id'],ev['target'],ev['retrieved_at']))
  successor=self.db.one("SELECT * FROM source_snapshot_427 WHERE case_id=? AND source_id=? AND target=? AND datetime(captured_at)>datetime(?) ORDER BY datetime(captured_at) ASC,rowid ASC LIMIT 1",(ev['case_id'],ev['source_id'],ev['target'],ev['retrieved_at']))
  self.db.execute('INSERT INTO source_snapshot_427 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()))
  change=self._record_change(dict(prev),r) if prev else None
  successor_change=None
  if successor:
   successor=dict(successor)
   self.db.execute('DELETE FROM content_change_427 WHERE current_snapshot_id=?',(successor['snapshot_id'],))
   successor_change=self._record_change(r,successor)
  self.audit.log('source_snapshot_captured_427','acquisition_event_422',event_id,ev['case_id'],{'snapshot_id':sid,'change_kind':change['change_kind'] if change else 'baseline','successor_relinked':bool(successor_change)});return {'snapshot':r,'change':change,'successor_change':successor_change}
 def history(self,case_id,source_id,target):
  return [dict(r) for r in self.db.all('SELECT * FROM source_snapshot_427 WHERE case_id=? AND source_id=? AND target=? ORDER BY julianday(captured_at),rowid',(case_id,source_id,target))]
 def changes(self,case_id):
  return [dict(r) for r in self.db.all('SELECT * FROM content_change_427 WHERE case_id=? ORDER BY created_at DESC',(case_id,))]
 def verify_integrity(self):
  bad=[]
  for table,key in [('source_snapshot_427','snapshot_id'),('content_change_427','change_id')]:
   for row in self.db.all('SELECT * FROM '+table):
    d=dict(row)
    if self._rh(d)!=d['record_hash']:bad.append({key:d[key],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  s=self.db.one('SELECT COUNT(*) n FROM source_snapshot_427')['n'];c=self.db.one('SELECT COUNT(*) n FROM content_change_427')['n'];return {'build':BUILD,'policy':POLICY_ID,'snapshots':int(s),'changes':int(c),'integrity_valid':self.verify_integrity()['valid'],'network_authority':False,'change_detection_is_evidence_signal_not_truth':True}
