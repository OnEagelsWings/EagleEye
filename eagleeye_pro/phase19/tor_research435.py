from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit
import hashlib,json,secrets,threading
from eagleeye.crawler.engine import VALID_ONION
BUILD='435.0';POLICY_ID='phase19.isolated-tor-research-worker.v435'
STATES=('planned','running','quarantined_for_review','failed','blocked','reviewed','rejected')
SAFE_MEDIA={'text/plain','text/html','application/json','application/xml','text/xml','application/xhtml+xml'}
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(v,n=1000):return ' '.join(str(v or '').split())[:n]
def _onion_url(v):
 p=urlsplit(str(v or '').strip())
 if p.scheme.lower() not in {'http','https'} or not p.hostname:raise ValueError('absolute http(s) onion URL required')
 if p.username is not None or p.password is not None:raise ValueError('credentials in onion URLs are forbidden')
 host=p.hostname.casefold().rstrip('.')
 if not VALID_ONION.fullmatch(host):raise ValueError('reviewed v3 onion hostname required')
 if p.port not in {None,80,443}:raise ValueError('non-standard onion target ports are forbidden')
 netloc=host if p.port is None else f'{host}:{p.port}'
 return urlunsplit((p.scheme.lower(),netloc,p.path or '/',p.query,''))
class IsolatedTorResearchWorker435:
 def __init__(self,db,audit,*,registry421,events422,content423,tor370,governance,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.tor370=tor370;self.governance=governance;self.actor=actor;self._live_lock=threading.Lock();self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS tor_research_task_435(task_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,source_id TEXT NOT NULL,target TEXT NOT NULL,objective TEXT NOT NULL,approval_ref TEXT NOT NULL,state TEXT NOT NULL,max_bytes INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,execution_mode TEXT NOT NULL,event_id TEXT NOT NULL,content_id TEXT NOT NULL,http_status INTEGER NOT NULL,media_type TEXT NOT NULL,response_sha256 TEXT NOT NULL,isolation_fingerprint TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT NOT NULL,reviewed_by TEXT NOT NULL,reviewed_at TEXT NOT NULL,review_decision TEXT NOT NULL,review_note TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_tr435_case ON tor_research_task_435(case_id,state,created_at);CREATE INDEX IF NOT EXISTS idx_tr435_source ON tor_research_task_435(source_id,created_at);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _identity(self,identity):
  if not isinstance(identity,dict) or not identity.get('username') or not identity.get('user_id'):raise PermissionError('canonical active identity required')
  try:user=self.governance.identity.public_user(str(identity['username']))
  except (KeyError,ValueError):raise PermissionError('canonical active identity required')
  if not user.get('active') or str(user.get('user_id'))!=str(identity.get('user_id')):raise PermissionError('canonical active identity required')
  return {**user,'session_id':str(identity.get('session_id') or 'tor435')}
 def _authorize(self,identity,case_id,object_id=''):
  ident=self._identity(identity);self.governance.authorize(ident,case_id=str(case_id),capability='research.run',object_type='tor_research_435',object_id=str(object_id or case_id));return ident
 def _source_target(self,source_id,target):
  src=self.registry421.get(source_id)
  if src['source_type']!='tor_onion' or src['access_mode']!='tor_public' or int(src.get('enabled',0))!=1:raise PermissionError('enabled tor_onion source with tor_public access required')
  base=_onion_url(src['base_url']);clean=_onion_url(target)
  if urlsplit(base).hostname.casefold()!=urlsplit(clean).hostname.casefold():raise PermissionError('target must remain on the exact reviewed onion host')
  return src,clean
 def _ensure_selftest_source(self):
  sid='src421_fixture_tor435';onion='a'*56+'.onion';base='http://'+onion+'/'
  try:
   src=self.registry421.get(sid)
   if src['source_type']!='tor_onion' or src['access_mode']!='tor_public' or src['base_url']!=base or not bool((src.get('coverage') or {}).get('fixture_only')):raise RuntimeError('reserved Build 435 fixture source has unexpected configuration')
   return src
  except KeyError:
   caps=['case_fixture','public_pages'];coverage={'fixture_only':True,'live_execution_forbidden':True};r={'source_id':sid,'name':'Build 435 Synthetic Onion Fixture','source_type':'tor_onion','access_mode':'tor_public','base_url':base,'capabilities_json':_canon(caps),'coverage_json':_canon(coverage),'terms_url':'','license_note':'Trusted internal synthetic v3-onion fixture; deterministic replay only.','enabled':1,'created_by':'system:build435_fixture','created_at':_now()};r['record_hash']=self.registry421._record_hash(r);self.db.execute('INSERT INTO acquisition_source_421 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));self.audit.log('tor435_fixture_source_seeded','acquisition_source_421',sid,'',{'fixture_only':True,'network_execution':False});return self.registry421.get(sid)
 def get(self,task_id):
  row=self.db.one('SELECT * FROM tor_research_task_435 WHERE task_id=?',(str(task_id),))
  if not row:raise KeyError('Tor research task not found')
  return dict(row)
 def _update(self,task_id,**changes):
  row=self.get(task_id);row.update(changes);row['record_hash']=self._rh(row);keys=list(changes)+['record_hash'];self.db.execute('UPDATE tor_research_task_435 SET '+','.join(k+'=?' for k in keys)+' WHERE task_id=?',tuple(row[k] for k in keys)+(task_id,));return self.get(task_id)
 def create_task(self,*,identity,case_id,source_id,target,objective,approval_ref,max_bytes=500000,timeout_seconds=20):
  ident=self._authorize(identity,case_id,source_id);case_id=str(case_id or '').strip();objective=_clean(objective,2000);approval=_clean(approval_ref,500)
  if not case_id or not objective or not approval:raise ValueError('case_id, objective and explicit approval_ref required')
  _,target=self._source_target(source_id,target);mb=int(max_bytes);to=int(timeout_seconds)
  if not 1<=mb<=2_000_000:raise ValueError('max_bytes must be between 1 and 2000000')
  if not 1<=to<=60:raise ValueError('timeout_seconds must be between 1 and 60')
  tid='tor435_'+secrets.token_hex(10);actor=str(ident['username']);r={'task_id':tid,'case_id':case_id,'source_id':source_id,'target':target,'objective':objective,'approval_ref':approval,'state':'planned','max_bytes':mb,'timeout_seconds':to,'execution_mode':'','event_id':'','content_id':'','http_status':0,'media_type':'','response_sha256':'','isolation_fingerprint':'','created_by':actor,'created_at':_now(),'completed_at':'','reviewed_by':'','reviewed_at':'','review_decision':'','review_note':''};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO tor_research_task_435 VALUES('+','.join('?' for _ in r)+')',tuple(r.values()));self.audit.log('tor_research_task_created_435','tor_research_task_435',tid,case_id,{'source_id':source_id,'approval_ref':approval,'target_host':urlsplit(target).hostname,'live_execution':False});return r
 def _record_failure(self,identity,task,error_class):
  ev=self.events422.record(identity=identity,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='failed',provenance={'build':'435.0','task_id':task['task_id'],'error_class':error_class,'read_only':True,'public_onion_only':True},usage={'no_auth':True,'no_forms':True,'no_scope_expansion':True})
  return self._update(task['task_id'],state='failed',event_id=ev['event_id'],completed_at=_now())
 def _execute(self,*,identity,task_id,transport,mode,isolation_fingerprint=''):
  task=self.get(task_id);ident=self._authorize(identity,task['case_id'],task_id)
  if task['state']!='planned':raise ValueError('Tor research task is not executable')
  self._source_target(task['source_id'],task['target']);self._update(task_id,state='running',execution_mode=mode,isolation_fingerprint=str(isolation_fingerprint or '')[:128])
  try:r=transport.fetch(task['target'],method='GET',headers={},timeout_seconds=int(task['timeout_seconds']),max_bytes=int(task['max_bytes']))
  except Exception as exc:
   self._record_failure(ident,self.get(task_id),type(exc).__name__);raise RuntimeError('Tor research retrieval failed: '+type(exc).__name__) from exc
  final=_onion_url(getattr(r,'url',task['target']))
  if urlsplit(final).hostname.casefold()!=urlsplit(task['target']).hostname.casefold():
   ev=self.events422.record(identity=ident,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='blocked',provenance={'build':'435.0','task_id':task_id,'reason':'cross_host_response','read_only':True},usage={'no_scope_expansion':True});return {'task':self._update(task_id,state='blocked',event_id=ev['event_id'],http_status=int(getattr(r,'status',0) or 0),completed_at=_now()),'event':ev,'content':None}
  body=bytes(getattr(r,'body',b'') or b'');status=int(getattr(r,'status',0) or 0);headers={str(k).casefold():str(v) for k,v in dict(getattr(r,'headers',{}) or {}).items()};media=headers.get('content-type','application/octet-stream').split(';',1)[0].strip().casefold();digest=hashlib.sha256(body).hexdigest() if body else ''
  if len(body)>int(task['max_bytes']):
   ev=self.events422.record(identity=ident,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='blocked',content_sha256=digest,media_type=media,bytes_count=len(body),provenance={'build':'435.0','task_id':task_id,'reason':'response_exceeds_budget'},usage={'downloads_blocked':True,'budget_enforced':True});return {'task':self._update(task_id,state='blocked',event_id=ev['event_id'],http_status=status,media_type=media,response_sha256=digest,completed_at=_now()),'event':ev,'content':None}
  if status<200 or status>=300:
   ev=self.events422.record(identity=ident,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='failed',content_sha256=digest,media_type=media,bytes_count=len(body),provenance={'build':'435.0','task_id':task_id,'http_status':status,'read_only':True},usage={'no_auth':True,'no_forms':True,'no_scope_expansion':True});return {'task':self._update(task_id,state='failed',event_id=ev['event_id'],http_status=status,media_type=media,response_sha256=digest,completed_at=_now()),'event':ev,'content':None}
  if media not in SAFE_MEDIA:
   ev=self.events422.record(identity=ident,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='blocked',content_sha256=digest,media_type=media,bytes_count=len(body),provenance={'build':'435.0','task_id':task_id,'reason':'unsafe_media_type','http_status':status},usage={'downloads_blocked':True,'quarantine_required':True});return {'task':self._update(task_id,state='blocked',event_id=ev['event_id'],http_status=status,media_type=media,response_sha256=digest,completed_at=_now()),'event':ev,'content':None}
  ev=self.events422.record(identity=ident,case_id=task['case_id'],source_id=task['source_id'],target=task['target'],method='tor_public',status='quarantined',content_sha256=digest,media_type=media,bytes_count=len(body),provenance={'build':'435.0','task_id':task_id,'approval_ref':task['approval_ref'],'http_status':status,'elapsed_ms':int(getattr(r,'elapsed_ms',0) or 0),'read_only':True,'public_onion_only':True},usage={'no_auth':True,'no_forms':True,'no_scope_expansion':True,'no_js':True,'quarantine_required':True})
  content=self.content423.ingest(identity=ident,event_id=ev['event_id'],content=body,media_type=media,metadata={'tor435_quarantined':True,'task_id':task_id,'review_required':True,'execution_mode':mode})
  updated=self._update(task_id,state='quarantined_for_review',event_id=ev['event_id'],content_id=content['content_id'],http_status=status,media_type=media,response_sha256=digest,completed_at=_now());self.audit.log('tor_research_retrieved_435','tor_research_task_435',task_id,task['case_id'],{'event_id':ev['event_id'],'content_id':content['content_id'],'state':'quarantined_for_review','execution_mode':mode});return {'task':updated,'event':ev,'content':content}
 def execute_live(self,*,identity,task_id,approval_ref,confirmation):
  task=self.get(task_id);self._authorize(identity,task['case_id'],task_id)
  if str(approval_ref or '').strip()!=task['approval_ref']:raise PermissionError('stored human approval_ref must be repeated exactly')
  if str(confirmation or '').strip().upper()!='TOR435_LIVE':raise PermissionError('explicit TOR435_LIVE confirmation required')
  src,_=self._source_target(task['source_id'],task['target'])
  if bool((src.get('coverage') or {}).get('fixture_only')):raise PermissionError('synthetic fixture sources cannot be used for live Tor execution')
  cfg=self.tor370.status()
  if not cfg.get('gateway_enabled'):raise PermissionError('controlled Tor gateway is disabled')
  if not self._live_lock.acquire(blocking=False):raise RuntimeError('isolated Tor live worker is busy')
  try:
   isolation=self.tor370.isolation_credentials(task_id)['fingerprint'];transport=self.tor370.make_transport(search_run_id=task_id)
   return self._execute(identity=identity,task_id=task_id,transport=transport,mode='live_tor_read_only',isolation_fingerprint=isolation)
  finally:self._live_lock.release()
 def execute_replay(self,*,identity,task_id,transport):
  return self._execute(identity=identity,task_id=task_id,transport=transport,mode='deterministic_replay',isolation_fingerprint='replay-no-network')
 def review(self,*,identity,task_id,decision,note=''):
  task=self.get(task_id);ident=self._authorize(identity,task['case_id'],task_id)
  if task['state']!='quarantined_for_review':raise ValueError('task is not awaiting review')
  dec=str(decision or '').strip().lower()
  if dec not in {'accept_for_analysis','reject'}:raise ValueError('decision must be accept_for_analysis or reject')
  state='reviewed' if dec=='accept_for_analysis' else 'rejected';updated=self._update(task_id,state=state,reviewed_by=str(ident['username']),reviewed_at=_now(),review_decision=dec,review_note=_clean(note,2000));self.audit.log('tor_research_reviewed_435','tor_research_task_435',task_id,task['case_id'],{'decision':dec,'evidence_promotion':False,'truth_determination':False});return updated
 def case_tasks(self,case_id):
  return [dict(r) for r in self.db.all('SELECT * FROM tor_research_task_435 WHERE case_id=? ORDER BY created_at,task_id',(str(case_id),))]
 def case_report(self,case_id):
  rows=self.case_tasks(case_id);counts={}
  for r in rows:counts[r['state']]=counts.get(r['state'],0)+1
  return {'build':BUILD,'case_id':str(case_id),'tasks':len(rows),'states':counts,'sources':sorted({r['source_id'] for r in rows}),'quarantined_or_reviewed':sum(1 for r in rows if r['state'] in {'quarantined_for_review','reviewed','rejected'}),'integrity_valid':self.verify_integrity()['valid'],'live_execution_requires_explicit_confirmation':True,'case_scoped':True}
 def checkpoint(self):
  tor=self.tor370.status();checks={'source_registry_integrity':self.registry421.verify_integrity()['valid'],'acquisition_event_integrity':self.events422.verify_integrity()['valid'],'content_store_integrity':self.content423.verify_integrity()['valid'],'tor_task_integrity':self.verify_integrity()['valid'],'tor_gateway_loopback_only':bool(tor.get('loopback_only')),'remote_dns_required':bool(tor.get('remote_dns_required')),'socks_auth_isolation_required':bool(tor.get('isolate_socks_auth_required')),'no_control_port_authority':not bool(tor.get('control_port_authority')),'no_destination_credentials':not bool(tor.get('destination_credentials_supported')),'no_access_control_bypass':not bool(tor.get('access_control_bypass_supported')),'no_tor_process_spawn':not bool(tor.get('tor_process_spawn')),'no_boot_external_connections':int(tor.get('automatic_external_connections_on_boot',0))==0}
  return {'build':BUILD,'hard_checkpoint':True,'checks':checks,'checkpoint_ready':all(checks.values()),'gateway_enabled':bool(tor.get('gateway_enabled')),'external_onion_validation':tor.get('external_onion_validation','not_run'),'production_release_ready':False,'truthful_note':'Checkpoint readiness validates the controlled execution boundary and deterministic replay path; it does not claim that an external onion service was contacted.'}
 def run_case_selftest(self,*,identity,case_id):
  from eagleeye.phase16.tor_gateway370 import StaticTorReplayTransport370
  from eagleeye.crawler.engine import FetchResponse
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  onion='a'*56+'.onion';base='http://'+onion+'/';source=self._ensure_selftest_source()
  token=secrets.token_hex(5);target=base+'public/'+token;task=self.create_task(identity=identity,case_id=case_id,source_id=source['source_id'],target=target,objective='Build 435 deterministic isolated-Tor case test',approval_ref='SELFTEST-'+token,max_bytes=100000,timeout_seconds=5)
  body=('Synthetic public onion page '+token).encode();transport=StaticTorReplayTransport370({target:FetchResponse(target,200,{'content-type':'text/plain'},body,2)});result=self.execute_replay(identity=identity,task_id=task['task_id'],transport=transport);reviewed=self.review(identity=identity,task_id=task['task_id'],decision='accept_for_analysis',note='Build 435 self-test review')
  ev=self.events422.get(result['event']['event_id']);checks={'case_bound':reviewed['case_id']==case_id,'source_is_tor_onion':source['source_type']=='tor_onion' and source['access_mode']=='tor_public','event_quarantined':ev['status']=='quarantined','content_bound':reviewed['content_id']==result['content']['content_id'],'deterministic_replay_no_network':reviewed['execution_mode']=='deterministic_replay' and reviewed['isolation_fingerprint']=='replay-no-network','human_review_recorded':reviewed['state']=='reviewed' and reviewed['review_decision']=='accept_for_analysis','truth_not_promoted':True,'integrity_valid':self.verify_integrity()['valid'],'checkpoint_ready':self.checkpoint()['checkpoint_ready']}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'task':reviewed,'event':ev,'content':result['content'],'checkpoint':self.checkpoint(),'note':'Synthetic v3-onion replay opens no external sockets and remains provenance-bound and quarantined until human review.'}
 def verify_integrity(self):
  bad=[]
  for row in self.db.all('SELECT * FROM tor_research_task_435'):
   d=dict(row)
   if self._rh(d)!=d['record_hash']:bad.append({'task_id':d['task_id'],'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  n=self.db.one('SELECT COUNT(*) n FROM tor_research_task_435')['n'];return {'build':BUILD,'policy':POLICY_ID,'tasks':int(n),'states':list(STATES),'safe_media_types':sorted(SAFE_MEDIA),'integrity_valid':self.verify_integrity()['valid'],'isolated_tor_worker':True,'live_network_via_controlled_tor_gateway_only':True,'live_execution_requires_approval_ref_and_confirmation':True,'read_only_get_only':True,'public_v3_onion_only':True,'destination_credentials_supported':False,'forms_or_uploads_supported':False,'access_control_bypass_supported':False,'autonomous_scope_expansion':False,'quarantine_before_review':True,'evidence_promotion':False,'truth_determination':False,'hard_checkpoint':True,'max_concurrent_live_tasks':1,'production_release_ready':False}
