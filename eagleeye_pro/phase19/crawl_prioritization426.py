from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='426.0';POLICY_ID='phase19.crawl-prioritization-budget.v426'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class CrawlPrioritization426:
 def __init__(self,db,audit,*,crawler425,health424,actor='local-analyst'):self.db=db;self.audit=audit;self.crawler425=crawler425;self.health424=health424;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS crawl_priority_426(priority_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,case_id TEXT NOT NULL,relevance REAL NOT NULL,source_factor REAL NOT NULL,urgency REAL NOT NULL,cost_factor REAL NOT NULL,priority_score REAL NOT NULL,decision TEXT NOT NULL,budget_json TEXT NOT NULL,reason_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_cp426_case_score ON crawl_priority_426(case_id,priority_score DESC);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def prioritize(self,*,identity,task_id,relevance,urgency=.5,budget=None):
  if not identity:raise PermissionError('active identity required')
  t=self.crawler425.get(task_id)
  for name,val in [('relevance',relevance),('urgency',urgency)]:
   if not 0<=float(val)<=1:raise ValueError(name+' must be between 0 and 1')
  health=self.health424.acquisition_advice(t['source_id']);sf={'allow':1.0,'allow_cautious':.7,'unknown':.6,'defer':.2,'avoid':0.0}.get(health['decision'],.5)
  b={'max_pages':1,'max_bytes':2000000,'max_depth':0,'max_seconds':30,**(budget or {})}
  for k in ('max_pages','max_bytes','max_depth','max_seconds'):
   if int(b[k])<0:raise ValueError(k+' must be >= 0')
  cost=min(1.0,(int(b['max_pages'])/100)+(int(b['max_bytes'])/100000000)+(int(b['max_seconds'])/3600))
  score=max(0.0,min(1.0,.55*float(relevance)+.2*float(urgency)+.2*sf+.05*(1-cost)))
  decision='defer' if health['decision']=='defer' else ('block' if health['decision']=='avoid' else ('queue_high' if score>=.75 else 'queue' if score>=.4 else 'queue_low'))
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);reason={'health':health,'weights':{'relevance':.55,'urgency':.2,'source_health':.2,'cost':.05},'advisory_only':True}
  r={'priority_id':'prio426_'+secrets.token_hex(10),'task_id':task_id,'case_id':t['case_id'],'relevance':float(relevance),'source_factor':sf,'urgency':float(urgency),'cost_factor':cost,'priority_score':score,'decision':decision,'budget_json':_canon(b),'reason_json':_canon(reason),'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO crawl_priority_426 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('crawl_priority_assessed_426','crawl_task_425',task_id,t['case_id'],{'priority_score':score,'decision':decision});return {**r,'budget':b,'reason':reason}
 def ranked_case(self,case_id):
  return [dict(r) for r in self.db.all('SELECT * FROM crawl_priority_426 WHERE case_id=? ORDER BY priority_score DESC,created_at',(case_id,))]
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM crawl_priority_426'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'priority_id':d['priority_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM crawl_priority_426')['n'];return {'build':BUILD,'policy':POLICY_ID,'assessments':int(n),'integrity_valid':self.verify_integrity()['valid'],'advisory_only':True,'network_authority':False,'autonomous_scope_expansion':False}
