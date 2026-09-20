from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,json,secrets
BUILD='425.0';POLICY_ID='phase19.ai-crawler-core.v425'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class CrawlerCore425:
 def __init__(self,db,audit,*,registry421,events422,content423,health424,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.health424=health424;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS crawl_task_425(task_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,objective TEXT NOT NULL,state TEXT NOT NULL,scope_json TEXT NOT NULL,budget_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_ct425_case ON crawl_task_425(case_id,state);""");self.db.conn.commit()
 def _row_hash(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def create_task(self,*,identity,case_id,source_id,target,objective,scope=None,budget=None):
  if not identity:raise PermissionError('active identity required')
  if not case_id or not objective:raise ValueError('case_id and objective required')
  src=self.registry421.get(source_id);u=urlparse(str(target))
  if u.scheme not in {'http','https'} or not u.netloc:raise ValueError('public http(s) target required')
  if u.hostname and u.hostname.endswith('.onion'):raise ValueError('onion targets require the isolated Tor worker planned for Build 435')
  advice=self.health424.acquisition_advice(source_id)
  if advice['decision']=='avoid':raise ValueError('source currently unavailable')
  state='deferred' if advice['decision']=='defer' else 'planned';actor=str(identity.get('user_id') or identity.get('username') or self.actor)
  r={'task_id':'crawl425_'+secrets.token_hex(10),'case_id':case_id,'source_id':source_id,'target':str(target),'objective':str(objective),'state':state,'scope_json':_canon(scope or {'allowed_hosts':[u.hostname]}),'budget_json':_canon(budget or {'max_pages':1,'max_bytes':2000000}),'created_by':actor,'created_at':_now()};r['record_hash']=self._row_hash(r);self.db.execute('INSERT INTO crawl_task_425 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('crawl_task_created_425','crawl_task_425',r['task_id'],case_id,{'source_id':source_id,'state':state});return r
 def accept_retrieval(self,*,identity,task_id,status,content=None,media_type='text/plain',content_sha256=None,provenance=None,usage=None):
  task=self.get(task_id)
  if task['state'] not in {'planned','deferred'}:raise ValueError('task not ingestible')
  ev=self.events422.record(identity=identity,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='http',status=status,content_sha256=content_sha256,media_type=media_type,provenance={**(provenance or {}),'crawl_task_id':task_id,'objective':task['objective']},usage=usage or {})
  result={'task_id':task_id,'event_id':ev['event_id'],'content':None}
  if content is not None and status=='retrieved':result['content']=self.content423.ingest(identity=identity,event_id=ev['event_id'],content=content,media_type=media_type,metadata={'crawl_task_id':task_id})
  self.db.execute('UPDATE crawl_task_425 SET state=? WHERE task_id=?',('completed' if status=='retrieved' else 'failed',task_id));return result
 def get(self,task_id):
  r=self.db.one('SELECT * FROM crawl_task_425 WHERE task_id=?',(task_id,))
  if not r:raise KeyError('crawl task not found')
  return dict(r)
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM crawl_task_425'):
   d=dict(row)
   if self._row_hash(d)!=d['record_hash']:bad.append({'task_id':d['task_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM crawl_task_425')['n'];return {'build':BUILD,'policy':POLICY_ID,'tasks':int(n),'integrity_valid':self.verify_integrity()['valid'],'network_executor_implemented':False,'external_retrieval_adapter_required':True,'access_control_bypass':False,'autonomous_scope_expansion':False,'tor_execution':False}
