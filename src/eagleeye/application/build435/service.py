from __future__ import annotations
import multiprocessing,queue,threading
from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION

def _live_fetch_process(out,cfg,creds,target,timeout_seconds,max_bytes):
 try:
  from eagleeye.phase16.tor_gateway370 import Socks5TorReadOnlyTransport370
  t=Socks5TorReadOnlyTransport370(socks_host=cfg['socks_host'],socks_port=int(cfg['socks_port']),isolation_username=creds['username'],isolation_password=creds['password'])
  r=t.fetch(target,method='GET',headers={},timeout_seconds=int(timeout_seconds),max_bytes=int(max_bytes))
  out.put({'ok':True,'url':r.url,'status':int(r.status),'headers':dict(r.headers),'body':bytes(r.body),'elapsed_ms':int(r.elapsed_ms)})
 except BaseException as exc:
  out.put({'ok':False,'error':type(exc).__name__})

class Build435IsolatedTorWorkerService:
 BUILD='435.0'
 def __init__(self,db,audit,*,build434,tor435,actor='local-analyst'):self.db=db;self.audit=audit;self.build434=build434;self.tor435=tor435;self.actor=actor;self._live_process_lock=threading.Lock()
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build434,n,None)
  if v is None:raise AttributeError(n)
  return v
 def create_tor_research_task(self,**kw):return self.tor435.create_task(**kw)
 def execute_tor_research_live(self,*,identity,task_id,approval_ref,confirmation):
  task=self.tor435.get(task_id);ident=self.tor435._authorize(identity,task['case_id'],task_id)
  if task['state']!='planned':raise ValueError('Tor research task is not executable')
  if str(approval_ref or '').strip()!=task['approval_ref']:raise PermissionError('stored human approval_ref must be repeated exactly')
  if str(confirmation or '').strip().upper()!='TOR435_LIVE':raise PermissionError('explicit TOR435_LIVE confirmation required')
  self.tor435._source_target(task['source_id'],task['target']);cfg=self.tor435.tor370.config()
  if not cfg.get('enabled'):raise PermissionError('controlled Tor gateway is disabled')
  if not self._live_process_lock.acquire(blocking=False):raise RuntimeError('isolated Tor live worker is busy')
  try:
   creds=self.tor435.tor370.isolation_credentials(task_id);ctx=multiprocessing.get_context('spawn');out=ctx.Queue(maxsize=1);p=ctx.Process(target=_live_fetch_process,args=(out,{'socks_host':cfg['socks_host'],'socks_port':cfg['socks_port']},{'username':creds['username'],'password':creds['password']},task['target'],int(task['timeout_seconds']),int(task['max_bytes'])),daemon=True)
   p.start();deadline=max(1,int(task['timeout_seconds']))
   try:result=out.get(timeout=deadline)
   except queue.Empty:
    if p.is_alive():
     p.terminate();p.join(2)
     if p.is_alive():p.kill();p.join(2)
    self.tor435._record_failure(ident,self.tor435.get(task_id),'WallClockDeadlineExceeded' if p.is_alive() or p.exitcode is None else 'WorkerExitedWithoutResult');raise RuntimeError('Tor research retrieval exceeded absolute wall-clock deadline or worker exited without a result')
   p.join(2)
   if p.is_alive():
    p.terminate();p.join(2)
    if p.is_alive():p.kill();p.join(2)
   if not result.get('ok'):
    self.tor435._record_failure(ident,self.tor435.get(task_id),str(result.get('error') or 'LiveWorkerFailure'));raise RuntimeError('Tor research retrieval failed: '+str(result.get('error') or 'LiveWorkerFailure'))
   from eagleeye.crawler.engine import FetchResponse
   from eagleeye.phase16.tor_gateway370 import StaticTorReplayTransport370
   response=FetchResponse(result['url'],int(result['status']),dict(result['headers']),bytes(result['body']),int(result['elapsed_ms']));transport=StaticTorReplayTransport370({task['target']:response})
   return self.tor435._execute(identity=ident,task_id=task_id,transport=transport,mode='live_tor_read_only_deadline_process',isolation_fingerprint=creds['fingerprint'])
  finally:self._live_process_lock.release()
 def review_tor_research(self,**kw):return self.tor435.review(**kw)
 def case_tor_research(self,case_id):return self.tor435.case_tasks(case_id)
 def case_tor_report(self,case_id):return self.tor435.case_report(case_id)
 def run_tor_case_selftest(self,**kw):return self.tor435.run_case_selftest(**kw)
 def checkpoint_435(self):
  base=self.tor435.checkpoint();registry=self.build434.registry_organization_status();checks={**base['checks'],'registry_organization_integrity':bool(registry['integrity_valid']),'registry_organization_chain_coherent':bool(registry['version_coherent'])};return {**base,'checks':checks,'checkpoint_ready':all(checks.values()),'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD,'phase':19,'phase19_builds_completed':15,'production_release_ready':False}
 def tor_worker_status(self):
  s=self.tor435.status();cp=self.checkpoint_435();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD,'phase':19,'phase19_builds_completed':15,'checkpoint_ready':cp['checkpoint_ready'],'live_wall_clock_deadline_process':True,'production_release_ready':False}
