from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,json,secrets
BUILD='431.0';POLICY_ID='phase19.news-provenance-syndication.v431'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _host(url):
 try:return (urlparse(str(url)).hostname or '').casefold()
 except Exception:return ''
def _claim_key(text):return ' '.join(str(text or '').casefold().split())
class NewsProvenance431:
 def __init__(self,db,audit,*,news429,events422,actor='local-analyst'):self.db=db;self.audit=audit;self.news429=news429;self.events422=events422;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS news_provenance_run_431(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,item_count INTEGER NOT NULL,distinct_source_units INTEGER NOT NULL,distinct_content_units INTEGER NOT NULL,syndication_candidate_count INTEGER NOT NULL,analysis_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_np431_case ON news_provenance_run_431(case_id,created_at);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _root_event(self,event_id):
  current=str(event_id or '');seen=set()
  for _ in range(32):
   if not current or current in seen:return current or ''
   seen.add(current);ev=self.events422.get(current);parent=str(ev.get('parent_event_id') or '')
   if not parent:return current
   current=parent
  return current
 def _latest_claims(self,news_item_id):
  row=self.db.one('SELECT claims_json FROM news_extraction_430 WHERE news_item_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(news_item_id,))
  if not row:return set()
  try:return {_claim_key(x.get('text')) for x in json.loads(row['claims_json']) if _claim_key(x.get('text'))}
  except Exception:return set()
 def analyze(self,*,identity,case_id):
  if not identity:raise PermissionError('active identity required')
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  items=self.news429.case_items(case_id);nodes=[]
  for item in items:
   obj=self.db.one('SELECT sha256 FROM content_object_423 WHERE content_id=?',(item['content_id'],))
   if not obj:raise ValueError('news item content object missing')
   ev=self.events422.get(item['event_id']);root=self._root_event(item['event_id']);claims=self._latest_claims(item['news_item_id'])
   nodes.append({'news_item_id':item['news_item_id'],'source_id':item['source_id'],'event_id':item['event_id'],'root_event_id':root,'content_id':item['content_id'],'content_sha256':obj['sha256'],'publisher':item.get('publisher') or '','canonical_host':_host(item.get('canonical_url')),'published_at':item.get('published_at') or '','source_snapshot':ev.get('source_snapshot') or {},'claims':sorted(claims)})
  def groups(field,basis):
   buckets={}
   for n in nodes:
    key=str(n.get(field) or '')
    if key:buckets.setdefault(key,[]).append(n['news_item_id'])
   return [{'group_id':basis+':'+hashlib.sha256(k.encode()).hexdigest()[:16],'basis':basis,'value':k,'news_item_ids':v,'count':len(v),'independence_signal':'not_independent' if basis in {'exact_content','event_lineage'} else 'shared_source'} for k,v in sorted(buckets.items()) if len(v)>1]
  exact=groups('content_sha256','exact_content');lineage=groups('root_event_id','event_lineage');sources=groups('source_id','same_source');hosts=groups('canonical_host','same_host')
  overlaps=[]
  for i,a in enumerate(nodes):
   ca=set(a['claims'])
   if not ca:continue
   for b in nodes[i+1:]:
    cb=set(b['claims'])
    if not cb:continue
    union=ca|cb;score=len(ca&cb)/len(union) if union else 0
    if score>=.8:overlaps.append({'left':a['news_item_id'],'right':b['news_item_id'],'jaccard':round(score,4),'signal':'high_claim_overlap','syndication_confirmed':False})
  flagged=set()
  for g in exact+lineage:
   flagged.update(g['news_item_ids'])
  analysis={'build':BUILD,'case_id':case_id,'items':nodes,'exact_content_groups':exact,'event_lineage_groups':lineage,'same_source_groups':sources,'same_host_groups':hosts,'claim_overlap_pairs':overlaps,'distinct_source_units':len({n['source_id'] for n in nodes}),'distinct_content_units':len({n['content_sha256'] for n in nodes}),'potentially_non_independent_items':sorted(flagged),'method_notes':['exact content identity is a strong non-independence signal','shared acquisition lineage is a strong non-independence signal','same source/host is a source-family signal, not proof of syndication','claim overlap is only a candidate signal and does not prove common origin'],'syndication_analysis_is_not_truth_determination':True,'publisher_claims_are_not_verified':True}
  actor=str(identity.get('user_id') or identity.get('username') or self.actor);r={'run_id':'np431_'+secrets.token_hex(10),'case_id':case_id,'item_count':len(nodes),'distinct_source_units':analysis['distinct_source_units'],'distinct_content_units':analysis['distinct_content_units'],'syndication_candidate_count':len(flagged),'analysis_json':_canon(analysis),'created_by':actor,'created_at':_now()};r['record_hash']=self._rh(r)
  self.db.execute('INSERT INTO news_provenance_run_431 VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('news_provenance_analyzed_431','case',case_id,case_id,{'run_id':r['run_id'],'items':len(nodes),'flagged':len(flagged)});return {**r,'analysis':analysis}
 def latest(self,case_id):
  row=self.db.one('SELECT * FROM news_provenance_run_431 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(case_id,))
  if not row:return None
  d=dict(row);d['analysis']=json.loads(d['analysis_json']);return d
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM news_provenance_run_431'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'run_id':d['run_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM news_provenance_run_431')['n'];return {'build':BUILD,'policy':POLICY_ID,'analysis_runs':int(n),'integrity_valid':self.verify_integrity()['valid'],'network_authority':False,'syndication_analysis_is_evidence_signal_not_truth':True,'production_release_ready':False}
