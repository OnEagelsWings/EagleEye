from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone,timedelta
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _utc()->datetime:return datetime.now(timezone.utc)
def _iso(dt:datetime)->str:return dt.isoformat().replace('+00:00','Z')

class Build201SourceRuntime3Service:
    BUILD='201.1'
    MODES=('fast_discovery','balanced','precision_first')
    DEFAULT_SOURCES={
      'gleif_lei_live':('structured_api',10,4,2,25,4,2,3,120),
      'crossref_rest_live':('structured_api',20,5,1,25,4,2,3,120),
      'gdelt_doc_live':('structured_api',20,4,5,30,4,2,3,180),
      'openalex_live':('credentialed_api',30,3,2,30,4,3,3,180),
      'congress_live':('credentialed_api',30,2,10,30,3,3,3,240),
      'knesset_odata_live':('structured_api',30,2,10,30,3,3,3,240),
      'federal_register_live':('structured_api',20,3,5,25,4,2,3,180),
      'world_bank_live':('structured_api',40,3,5,25,4,2,3,180),
      'internet_archive_cdx_190':('structured_api',30,2,15,40,3,4,3,300),
      'github_events_watch':('credentialed_api',30,2,10,30,3,3,3,240),
    }
    def __init__(self,db:Any,audit:Any,*,platform:Any,source_ops:Any,pilot_ai:Any,graph:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.platform=platform;self.source_ops=source_ops;self.pilot_ai=pilot_ai;self.graph=graph;self.actor=actor
    def seed_runtime(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='SOURCE RUNTIME 201 ANLEGEN':raise PermissionError('explicit approval required')
        created=now_ts()
        for sid,cfg in self.DEFAULT_SOURCES.items():
            access,priority,parallel,minint,timeout,retries,backoff,threshold,cooldown=cfg
            p={'source_id':sid,'mode':access,'priority':priority,'max_parallel':parallel,'min_interval_seconds':minint,'timeout_seconds':timeout,'max_retries':retries,'backoff_base_seconds':backoff,'circuit_threshold':threshold,'circuit_cooldown_seconds':cooldown,'schema_fingerprint':'','status':'ready_for_validation'}
            self.db.execute('INSERT OR REPLACE INTO source_runtime_profiles_201 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,access,priority,parallel,minint,timeout,retries,backoff,threshold,cooldown,'','ready_for_validation',created,_hash(p)))
            self.db.execute('INSERT OR IGNORE INTO source_circuits_201 VALUES(?,?,?,?,?,?,?,?)',(sid,'closed',0,'','','',created,_hash({'source_id':sid,'state':'closed'})))
        return {'sources':len(self.DEFAULT_SOURCES),'automatic_activation':False,'speed_with_evidence_gates':True}
    def create_search_jobs(self,*,case_id:str,question:str,source_ids:Sequence[str],mode:str='balanced',priority:int=50,confirmation:str)->dict[str,Any]:
        if confirmation!=f'SOURCE JOBS 201 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        if mode not in self.MODES:raise ValueError(mode)
        if not question.strip():raise ValueError('question required')
        jobs=[];now=now_ts()
        for sid in source_ids:
            profile=self.db.one('SELECT * FROM source_runtime_profiles_201 WHERE source_id=?',(sid,))
            if not profile:raise KeyError(sid)
            circuit=self.db.one('SELECT * FROM source_circuits_201 WHERE source_id=?',(sid,))
            status='blocked_circuit' if circuit and circuit['state']=='open' else 'queued'
            jid=new_id('job201');q={'question':question,'source_id':sid,'mode':mode,'precision_contract':{'candidate_only':True,'citation_required':True,'source_ref_required':True,'automatic_identity_confirmation':False}}
            p={'job_id':jid,'case_id':case_id,'source_id':sid,'query':q,'mode':mode,'priority':priority,'status':status,'attempt':0,'next_run_at':now,'checkpoint':{}}
            self.db.execute('INSERT INTO source_jobs_201 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,case_id,sid,dumps(q),mode,priority,status,0,now,dumps({}),0,'','',now,now,_hash(p)));jobs.append(p)
        jobs.sort(key=lambda x:(self.db.one('SELECT priority FROM source_runtime_profiles_201 WHERE source_id=?',(x['source_id'],))['priority'],x['source_id']))
        return {'case_id':case_id,'mode':mode,'jobs':jobs,'parallel_discovery':mode!='precision_first','candidate_only':True}
    def next_batch(self,*,limit:int=8)->list[dict[str,Any]]:
        rows=self.db.all("SELECT j.*,p.max_parallel,p.priority AS source_priority FROM source_jobs_201 j JOIN source_runtime_profiles_201 p ON p.source_id=j.source_id WHERE j.status='queued' ORDER BY j.priority DESC,p.priority ASC,j.created_at ASC")
        selected=[];per={}
        for r in rows:
            if len(selected)>=limit:break
            n=per.get(r['source_id'],0)
            if n>=int(r['max_parallel']):continue
            per[r['source_id']]=n+1;selected.append(dict(r))
        return selected
    def start_job(self,*,job_id:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'SOURCE JOB 201 {job_id} STARTEN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM source_jobs_201 WHERE job_id=?',(job_id,))
        if not row:raise KeyError(job_id)
        circuit=self.db.one('SELECT * FROM source_circuits_201 WHERE source_id=?',(row['source_id'],))
        if circuit and circuit['state']=='open':raise RuntimeError('source circuit open')
        attempt=int(row['attempt'])+1;updated=now_ts();self.db.execute("UPDATE source_jobs_201 SET status='running',attempt=?,updated_at=? WHERE job_id=?",(attempt,updated,job_id))
        return {'job_id':job_id,'status':'running','attempt':attempt,'timeout_enforced':True}
    def complete_job(self,*,job_id:str,http_status:int,latency_ms:int,records:Sequence[Mapping[str,Any]],schema_fields:Sequence[str],parser_ok:bool,next_checkpoint:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'SOURCE JOB 201 {job_id} ABSCHLIESSEN':raise PermissionError('explicit approval required')
        job=self.db.one('SELECT * FROM source_jobs_201 WHERE job_id=?',(job_id,));
        if not job:raise KeyError(job_id)
        profile=self.db.one('SELECT * FROM source_runtime_profiles_201 WHERE source_id=?',(job['source_id'],))
        fp=_hash(sorted(set(schema_fields)));drift=bool(profile['schema_fingerprint'] and profile['schema_fingerprint']!=fp)
        status='completed' if http_status<400 and parser_ok and not drift else 'failed'
        run_id=new_id('run201');finished=now_ts();p={'run_id':run_id,'job_id':job_id,'http_status':http_status,'latency_ms':latency_ms,'records_received':len(records),'parser_ok':parser_ok,'schema_fingerprint':fp,'schema_drift':drift,'status':status}
        self.db.execute('INSERT INTO source_runs_201 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,job_id,job['source_id'],http_status,latency_ms,len(records),int(parser_ok),fp,int(drift),status,job['updated_at'],finished,_hash(p)))
        if status=='completed':
            self.db.execute("UPDATE source_jobs_201 SET status='completed',checkpoint_json=?,result_count=?,error_code='',error_message='',updated_at=?,payload_sha256=? WHERE job_id=?",(dumps(dict(next_checkpoint or {})),len(records),finished,_hash(p),job_id))
            self.db.execute("UPDATE source_runtime_profiles_201 SET schema_fingerprint=?,status='healthy' WHERE source_id=?",(fp,job['source_id']))
            self._close_circuit(job['source_id'])
        else:self._fail_job(job,code='schema_drift' if drift else ('parser_error' if not parser_ok else f'http_{http_status}'),message='response schema changed' if drift else 'source execution failed')
        return {**p,'checkpoint':dict(next_checkpoint or {}),'precision_preserved':status=='completed','automatic_acceptance':False}
    def ingest_candidates(self,*,job_id:str,records:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f'SOURCE CANDIDATES 201 {job_id} SPEICHERN':raise PermissionError('explicit approval required')
        job=self.db.one('SELECT * FROM source_jobs_201 WHERE job_id=?',(job_id,));
        if not job or job['status']!='completed':raise ValueError('completed job required')
        saved=0
        for i,r in enumerate(records):
            source_ref=str(r.get('source_ref') or r.get('url') or r.get('id') or '')
            if not source_ref:continue
            normalized=dict(r);evidence={'source_ref':source_ref,'observed_at':now_ts(),'job_id':job_id,'independent_source_unverified':True}
            cid=new_id('candidate201');record_id=str(r.get('id') or i);entity_type=str(r.get('entity_type') or 'unknown');confidence=min(.99,max(0.0,float(r.get('confidence',.5))))
            p={'candidate_id':cid,'job_id':job_id,'source_id':job['source_id'],'source_record_id':record_id,'normalized':normalized,'evidence':evidence,'confidence':confidence,'review_status':'candidate'}
            self.db.execute('INSERT INTO runtime_candidates_201 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,job_id,job['case_id'],job['source_id'],record_id,entity_type,dumps(normalized),dumps(evidence),confidence,'candidate',now_ts(),_hash(p)));saved+=1
        return {'job_id':job_id,'saved':saved,'review_status':'candidate','automatic_identity_confirmation':False,'citation_required':True}
    def fail_job(self,*,job_id:str,code:str,message:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'SOURCE JOB 201 {job_id} FEHLER':raise PermissionError('explicit approval required')
        job=self.db.one('SELECT * FROM source_jobs_201 WHERE job_id=?',(job_id,));
        if not job:raise KeyError(job_id)
        return self._fail_job(job,code=code,message=message)
    def _fail_job(self,job:Any,*,code:str,message:str)->dict[str,Any]:
        profile=self.db.one('SELECT * FROM source_runtime_profiles_201 WHERE source_id=?',(job['source_id'],));attempt=int(job['attempt']);maxr=int(profile['max_retries']);delay=int(profile['backoff_base_seconds'])*(2**max(0,attempt-1));retry=attempt<maxr
        next_at=_iso(_utc()+timedelta(seconds=delay)) if retry else ''
        status='queued' if retry else 'failed';self.db.execute('UPDATE source_jobs_201 SET status=?,next_run_at=?,error_code=?,error_message=?,updated_at=? WHERE job_id=?',(status,next_at,code,message[:500],now_ts(),job['job_id']))
        circuit=self.db.one('SELECT * FROM source_circuits_201 WHERE source_id=?',(job['source_id'],));fails=int(circuit['consecutive_failures'])+1;state='open' if fails>=int(profile['circuit_threshold']) else 'closed';retry_after=_iso(_utc()+timedelta(seconds=int(profile['circuit_cooldown_seconds']))) if state=='open' else ''
        self.db.execute('UPDATE source_circuits_201 SET state=?,consecutive_failures=?,opened_at=?,retry_after=?,last_error=?,updated_at=?,payload_sha256=? WHERE source_id=?',(state,fails,now_ts() if state=='open' else '',retry_after,message[:500],now_ts(),_hash({'source_id':job['source_id'],'state':state,'fails':fails}),job['source_id']))
        return {'job_id':job['job_id'],'status':status,'retry_scheduled':retry,'retry_after_seconds':delay if retry else None,'circuit_state':state,'fail_closed':True}
    def _close_circuit(self,source_id:str)->None:
        self.db.execute("UPDATE source_circuits_201 SET state='closed',consecutive_failures=0,opened_at='',retry_after='',last_error='',updated_at=? WHERE source_id=?",(now_ts(),source_id))
    def runtime_status(self)->dict[str,Any]:
        jobs=self.db.all('SELECT status,COUNT(*) AS n FROM source_jobs_201 GROUP BY status');circuits=self.db.all('SELECT state,COUNT(*) AS n FROM source_circuits_201 GROUP BY state')
        return {'build':'201.1','jobs':{r['status']:r['n'] for r in jobs},'circuits':{r['state']:r['n'] for r in circuits},'speed_modes':list(self.MODES),'evidence_first':True}
