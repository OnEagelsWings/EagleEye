from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='430.0';POLICY_ID='phase19.news-entity-event-extraction.v430'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class NewsExtraction430:
 def __init__(self,db,audit,*,news429,actor='local-analyst'):self.db=db;self.audit=audit;self.news429=news429;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS news_extraction_430(extraction_id TEXT PRIMARY KEY,news_item_id TEXT NOT NULL,case_id TEXT NOT NULL,extractor TEXT NOT NULL,extractor_version TEXT NOT NULL,entities_json TEXT NOT NULL,events_json TEXT NOT NULL,claims_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_ne430_case ON news_extraction_430(case_id,created_at);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def record(self,*,identity,news_item_id,extractor,extractor_version,entities=None,events=None,claims=None):
  if not identity:raise PermissionError('active identity required')
  n=self.db.one('SELECT * FROM news_item_429 WHERE news_item_id=?',(news_item_id,))
  if not n:raise KeyError('news item not found')
  def norm_entities(xs):
   out=[]
   for x in xs or []:
    label=str(x.get('label','')).strip();kind=str(x.get('kind','unknown')).strip().lower();conf=float(x.get('confidence',0))
    if not label or not 0<=conf<=1:raise ValueError('invalid entity')
    out.append({'label':label,'kind':kind,'confidence':conf,'source_span':str(x.get('source_span',''))[:500]})
   return out
  def norm_events(xs):
   out=[]
   for x in xs or []:
    label=str(x.get('label','')).strip();conf=float(x.get('confidence',0))
    if not label or not 0<=conf<=1:raise ValueError('invalid event')
    out.append({'label':label,'event_type':str(x.get('event_type','unknown')).lower(),'time':str(x.get('time','')),'location':str(x.get('location','')),'confidence':conf,'source_span':str(x.get('source_span',''))[:500]})
   return out
  def norm_claims(xs):
   out=[]
   for x in xs or []:
    text=str(x.get('text','')).strip();conf=float(x.get('confidence',0))
    if not text or not 0<=conf<=1:raise ValueError('invalid claim')
    out.append({'text':text,'speaker':str(x.get('speaker','')),'confidence':conf,'source_span':str(x.get('source_span',''))[:500],'corroborated':False})
   return out
  e=norm_entities(entities);v=norm_events(events);c=norm_claims(claims);actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'extraction_id':'ext430_'+secrets.token_hex(10),'news_item_id':news_item_id,'case_id':n['case_id'],'extractor':str(extractor).strip(),'extractor_version':str(extractor_version).strip(),'entities_json':_canon(e),'events_json':_canon(v),'claims_json':_canon(c),'created_by':actor,'created_at':_now()}
  if not r['extractor'] or not r['extractor_version']:raise ValueError('extractor and version required')
  r['record_hash']=self._rh(r);self.db.execute('INSERT INTO news_extraction_430 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('news_extraction_recorded_430','news_item_429',news_item_id,n['case_id'],{'extraction_id':r['extraction_id'],'entities':len(e),'events':len(v),'claims':len(c)});return {**r,'entities':e,'events':v,'claims':c}
 def case_extractions(self,case_id):
  out=[]
  for row in self.db.all('SELECT * FROM news_extraction_430 WHERE case_id=? ORDER BY created_at DESC',(case_id,)):
   d=dict(row);d['entities']=json.loads(d['entities_json']);d['events']=json.loads(d['events_json']);d['claims']=json.loads(d['claims_json']);out.append(d)
  return out
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM news_extraction_430'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'extraction_id':d['extraction_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM news_extraction_430')['n'];return {'build':BUILD,'policy':POLICY_ID,'extractions':int(n),'integrity_valid':self.verify_integrity()['valid'],'extraction_is_machine_observation_not_fact':True,'claims_default_corroborated':False,'network_authority':False,'production_release_ready':False}
