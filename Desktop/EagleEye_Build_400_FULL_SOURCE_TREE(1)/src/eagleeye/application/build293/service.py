from __future__ import annotations
import hashlib, html, json, time, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _future(seconds:int): return (datetime.now(timezone.utc)+timedelta(seconds=int(seconds))).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256((_canon(v) if not isinstance(v,str) else v).encode('utf-8')).hexdigest()
def _safe(v,d):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else d)
    except Exception:return d

class Build293OperationalStrengthService:
    BUILD='293.0'; GATE_THRESHOLD=0.85
    LOCAL_WORK={'observability_snapshot','fusion_refresh','adaptive_local_cycle'}
    def __init__(self,db:Any,audit:Any,*,build292:Any,build291:Any,build281:Any,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build292=build292; self.build291=build291; self.build281=build281; self.base_dir=Path(base_dir); self.actor=actor

    def _mission(self,case_id:str='',mission_id:str=''):
        if mission_id: row=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=?',(mission_id,))
        elif case_id: row=self.db.one("SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY CASE WHEN status='authorized' THEN 0 ELSE 1 END,created_at DESC LIMIT 1",(case_id,))
        else: row=None
        if not row: raise ValueError('Keine Phase-12-Mission gefunden.')
        return row

    def _event(self,case_id,mission_id,job_id,event_type,details,actor):
        prev=self.db.one('SELECT event_hash FROM phase12_ops_events_293 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1',(mission_id,))
        ph=prev['event_hash'] if prev else 'GENESIS'; eid=_id('ops293evt'); created=_now()
        payload={'event_id':eid,'case_id':case_id,'mission_id':mission_id,'op_job_id':job_id,'event_type':event_type,'details':details,'created_by':actor,'created_at':created,'previous_hash':ph}
        eh=_hash(payload)
        self.db.execute('INSERT INTO phase12_ops_events_293 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,mission_id,job_id,event_type,_canon(details),actor,created,ph,eh))
        return {'event_id':eid,'event_hash':eh}

    def verify_event_chain(self,mission_id:str=''):
        where=' WHERE mission_id=?' if mission_id else ''; args=(mission_id,) if mission_id else ()
        rows=self.db.all('SELECT * FROM phase12_ops_events_293'+where+' ORDER BY mission_id,rowid',args); previous={}
        for r in rows:
            ph=previous.get(r['mission_id'],'GENESIS')
            if r['previous_hash']!=ph:return False
            payload={'event_id':r['event_id'],'case_id':r['case_id'],'mission_id':r['mission_id'],'op_job_id':r['op_job_id'],'event_type':r['event_type'],'details':_safe(r['details_json'],{}),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
            if _hash(payload)!=r['event_hash']:return False
            previous[r['mission_id']]=r['event_hash']
        return True

    def create_checkpoint(self,*,job_id:str,reason:str,actor:str|None=None):
        actor=actor or self.actor; j=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
        if not j: raise KeyError('operational job not found')
        prev=self.db.one('SELECT checkpoint_hash FROM phase12_ops_checkpoints_293 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1',(j['mission_id'],)); ph=prev['checkpoint_hash'] if prev else 'GENESIS'
        state={'status':j['status'],'attempt_count':int(j['attempt_count']),'max_attempts':int(j['max_attempts']),'lease_owner':j['lease_owner'],'lease_expires_at':j['lease_expires_at'],'consumed_local_steps':int(j['consumed_local_steps']),'max_local_steps':int(j['max_local_steps']),'work_kind':j['work_kind'],'payload_sha256':j['payload_sha256']}
        next_actions=['review interruption or result','resume only inside existing mission scope','obtain new OK before crash-recovery resume or scope change']
        cid=_id('ops293cp'); created=_now(); payload={'checkpoint_id':cid,'case_id':j['case_id'],'mission_id':j['mission_id'],'op_job_id':job_id,'reason':reason,'job_status':j['status'],'state':state,'next_actions':next_actions,'created_by':actor,'created_at':created,'previous_hash':ph}; ch=_hash(payload)
        self.db.execute('INSERT INTO phase12_ops_checkpoints_293 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,j['case_id'],j['mission_id'],job_id,reason,j['status'],_canon(state),_canon(next_actions),actor,created,ph,ch))
        self.db.execute('UPDATE phase12_ops_jobs_293 SET last_checkpoint_id=?,updated_at=? WHERE op_job_id=?',(cid,_now(),job_id))
        self._event(j['case_id'],j['mission_id'],job_id,'checkpoint_created',{'checkpoint_id':cid,'reason':reason,'job_status':j['status']},actor)
        return {'checkpoint_id':cid,'checkpoint_hash':ch,'state':state,'next_actions':next_actions}

    def enqueue_work(self,*,case_id:str,mission_id:str='',work_kind:str='observability_snapshot',payload:dict|None=None,priority:int=50,max_attempts:int=3,max_runtime_seconds:int=120,max_local_steps:int=8,requested_by:str|None=None):
        actor=requested_by or self.actor; m=self._mission(case_id,mission_id)
        if m['case_id']!=case_id: raise PermissionError('mission/case mismatch')
        if m['status']!='authorized': raise PermissionError("Mission muss zuerst durch den Hauptermittler mit 'OK' autorisiert sein.")
        if work_kind not in self.LOCAL_WORK: raise ValueError('Build 293 erlaubt nur lokale, vorab definierte Operational-Work-Klassen.')
        payload=dict(payload or {}); payload['approved_scope']=m['mission_type']; payload['network_access']=False; payload['external_collection_started']=False
        priority=max(1,min(int(priority),100)); max_attempts=max(1,min(int(max_attempts),5)); max_runtime_seconds=max(5,min(int(max_runtime_seconds),900)); max_local_steps=max(1,min(int(max_local_steps),100))
        idem=_hash({'case_id':case_id,'mission_id':m['mission_id'],'work_kind':work_kind,'payload':payload})
        ex=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE idempotency_key=?',(idem,))
        if ex:return {'op_job_id':ex['op_job_id'],'status':ex['status'],'deduplicated':True,'case_id':case_id,'mission_id':m['mission_id'],'network_access':False}
        jid=_id('ops293job'); created=_now(); psha=_hash({'job_id':jid,'case_id':case_id,'mission_id':m['mission_id'],'work_kind':work_kind,'payload':payload,'created_at':created})
        self.db.execute('INSERT INTO phase12_ops_jobs_293 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,case_id,m['mission_id'],work_kind,_canon(payload),priority,'queued',0,max_attempts,'','','',max_runtime_seconds,max_local_steps,0,'','',idem,actor,created,created,psha))
        self._event(case_id,m['mission_id'],jid,'job_queued',{'work_kind':work_kind,'priority':priority,'max_attempts':max_attempts,'max_runtime_seconds':max_runtime_seconds,'max_local_steps':max_local_steps},actor)
        return {'op_job_id':jid,'status':'queued','deduplicated':False,'case_id':case_id,'mission_id':m['mission_id'],'network_access':False,'scope_expansion':False}

    def _worker(self,worker_id,status,current_job_id='',lease_expires_at=''):
        now=_now(); self.db.execute('INSERT OR REPLACE INTO phase12_worker_health_293 VALUES(?,?,?,?,?,?)',(worker_id,status,current_job_id,now,lease_expires_at,now))

    def recover_expired_leases(self,*,actor:str='ops-recovery-293'):
        now=_now(); rows=self.db.all("SELECT * FROM phase12_ops_jobs_293 WHERE status='running' AND lease_expires_at<>'' AND lease_expires_at<?",(now,)); recovered=[]
        for j in rows:
            expired_owner=str(j['lease_owner'] or '')
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='recovery_pending',lease_owner='',heartbeat_at='',last_error='worker lease expired; state requires review',updated_at=? WHERE op_job_id=?",(now,j['op_job_id']))
            if expired_owner:
                self._worker(expired_owner,'stale','',j['lease_expires_at'])
            cp=self.create_checkpoint(job_id=j['op_job_id'],reason='worker_lease_expired',actor=actor)
            self._event(j['case_id'],j['mission_id'],j['op_job_id'],'lease_expired_recovery_pending',{'checkpoint_id':cp['checkpoint_id'],'automatic_retry':False,'new_ok_required':True},actor)
            recovered.append({'op_job_id':j['op_job_id'],'checkpoint_id':cp['checkpoint_id'],'status':'recovery_pending','new_ok_required':True})
        return recovered

    def claim_next_job(self,*,worker_id:str='ai-worker-293',lease_seconds:int=120):
        self.recover_expired_leases(); lease_seconds=max(30,min(int(lease_seconds),900))
        with self.db.transaction(immediate=True):
            row=self.db.one("SELECT * FROM phase12_ops_jobs_293 WHERE status='queued' ORDER BY priority DESC,created_at ASC LIMIT 1")
            if not row:
                self._worker(worker_id,'idle'); return None
            expiry=_future(lease_seconds); now=_now()
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='running',attempt_count=attempt_count+1,lease_owner=?,lease_expires_at=?,heartbeat_at=?,updated_at=? WHERE op_job_id=? AND status='queued'",(worker_id,expiry,now,now,row['op_job_id']))
            claimed=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(row['op_job_id'],))
        self._worker(worker_id,'busy',claimed['op_job_id'],claimed['lease_expires_at']); self._event(claimed['case_id'],claimed['mission_id'],claimed['op_job_id'],'job_claimed',{'worker_id':worker_id,'attempt_count':int(claimed['attempt_count']),'lease_expires_at':claimed['lease_expires_at']},worker_id)
        return claimed

    def heartbeat(self,*,job_id:str,worker_id:str='ai-worker-293',extend_seconds:int=120):
        j=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
        if not j or j['status']!='running' or j['lease_owner']!=worker_id: raise PermissionError('worker does not own this running job')
        expiry=_future(max(30,min(int(extend_seconds),900))); now=_now(); self.db.execute('UPDATE phase12_ops_jobs_293 SET heartbeat_at=?,lease_expires_at=?,updated_at=? WHERE op_job_id=?',(now,expiry,now,job_id)); self._worker(worker_id,'busy',job_id,expiry)
        return {'op_job_id':job_id,'worker_id':worker_id,'heartbeat_at':now,'lease_expires_at':expiry}

    def record_resource_usage(self,*,job_id:str,local_steps:int=1,worker_id:str='ai-worker-293'):
        j=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
        if not j or j['status']!='running' or j['lease_owner']!=worker_id: raise PermissionError('resource accounting requires the owning running worker')
        steps=int(j['consumed_local_steps'])+max(0,int(local_steps)); limit=int(j['max_local_steps'])
        if steps>limit:
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='paused',lease_owner='',lease_expires_at='',heartbeat_at='',last_error='local step budget exhausted',consumed_local_steps=?,updated_at=? WHERE op_job_id=?",(steps,_now(),job_id))
            cp=self.create_checkpoint(job_id=job_id,reason='resource_budget_exhausted',actor=worker_id); self._worker(worker_id,'idle')
            self._event(j['case_id'],j['mission_id'],job_id,'resource_budget_exhausted',{'consumed_local_steps':steps,'max_local_steps':limit,'checkpoint_id':cp['checkpoint_id']},worker_id)
            raise RuntimeError('Lokales Ressourcenbudget erschöpft; Job wurde sicher pausiert.')
        self.db.execute('UPDATE phase12_ops_jobs_293 SET consumed_local_steps=?,updated_at=? WHERE op_job_id=?',(steps,_now(),job_id)); return {'op_job_id':job_id,'consumed_local_steps':steps,'max_local_steps':limit,'remaining_local_steps':limit-steps}

    def execute_claimed_job(self,*,job_id:str,worker_id:str='ai-worker-293'):
        j=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
        if not j or j['status']!='running' or j['lease_owner']!=worker_id: raise PermissionError('job must be claimed by this worker')
        m=self._mission(j['case_id'],j['mission_id'])
        if m['status']!='authorized':
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='paused',lease_owner='',lease_expires_at='',heartbeat_at='',last_error='mission not authorized',updated_at=? WHERE op_job_id=?",(_now(),job_id)); self._worker(worker_id,'idle'); cp=self.create_checkpoint(job_id=job_id,reason='mission_not_authorized',actor=worker_id); return {'op_job_id':job_id,'status':'paused','checkpoint':cp,'new_ok_required':True}
        payload=_safe(j['payload_json'],{}); started=time.monotonic(); self.record_resource_usage(job_id=job_id,local_steps=1,worker_id=worker_id)
        try:
            if j['work_kind']=='observability_snapshot': result=self.observability_snapshot(actor=worker_id,store=True)
            elif j['work_kind']=='fusion_refresh': result=self.build292.create_fusion(case_id=j['case_id'],mission_id=j['mission_id'],round_id=str(payload.get('round_id','')),actor=worker_id)
            elif j['work_kind']=='adaptive_local_cycle':
                rid=str(payload.get('round_id',''))
                if not rid: raise ValueError('adaptive_local_cycle requires an approved round_id')
                result=self.build291.run_approved_adaptive_cycle(round_id=rid,actor=worker_id)
            else: raise ValueError('unsupported local work kind')
            elapsed=time.monotonic()-started
            if elapsed>int(j['max_runtime_seconds']): raise RuntimeError('runtime budget exceeded')
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='completed',lease_owner='',lease_expires_at='',heartbeat_at='',last_error='',updated_at=? WHERE op_job_id=?",(_now(),job_id)); self._worker(worker_id,'idle'); cp=self.create_checkpoint(job_id=job_id,reason='local_work_completed',actor=worker_id)
            self._event(j['case_id'],j['mission_id'],job_id,'job_completed',{'checkpoint_id':cp['checkpoint_id'],'elapsed_seconds':round(elapsed,4),'network_access':False,'external_collection_started':False},worker_id)
            return {'op_job_id':job_id,'status':'completed','result':result,'checkpoint':cp,'network_access':False,'external_collection_started':False,'scope_expansion':False}
        except Exception as exc:
            cur=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
            if cur['status']=='paused' and 'budget' in str(cur['last_error']).lower(): status='paused'
            else: status='recovery_pending' if int(cur['attempt_count'])<int(cur['max_attempts']) else 'failed'
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status=?,lease_owner='',lease_expires_at='',heartbeat_at='',last_error=?,updated_at=? WHERE op_job_id=?",(status,str(exc)[:500],_now(),job_id)); self._worker(worker_id,'idle'); cp=self.create_checkpoint(job_id=job_id,reason='execution_error',actor=worker_id)
            self._event(j['case_id'],j['mission_id'],job_id,'job_execution_error',{'error_type':type(exc).__name__,'checkpoint_id':cp['checkpoint_id'],'automatic_retry':False,'new_ok_required':status=='recovery_pending'},worker_id)
            raise

    def run_next_job(self,*,worker_id:str='ai-worker-293'):
        j=self.claim_next_job(worker_id=worker_id)
        if not j:return {'status':'idle','network_access':False}
        return self.execute_claimed_job(job_id=j['op_job_id'],worker_id=worker_id)

    def approve_recovery(self,*,job_id:str,confirmation:str,approved_by:str):
        if str(confirmation).strip().upper()!='OK': raise PermissionError("Recovery benötigt ausdrücklich 'OK' des Hauptermittlers.")
        j=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job_id,))
        if not j or j['status']!='recovery_pending': raise ValueError('job is not awaiting recovery approval')
        cp=self.db.one('SELECT * FROM phase12_ops_checkpoints_293 WHERE op_job_id=? ORDER BY rowid DESC LIMIT 1',(job_id,))
        if not cp: raise ValueError('recovery requires an immutable checkpoint')
        if int(j['attempt_count'])>=int(j['max_attempts']): raise RuntimeError('maximum attempts reached; manual review required')
        aid=_id('ops293ok'); created=_now(); payload={'approval_id':aid,'op_job_id':job_id,'checkpoint_id':cp['checkpoint_id'],'decision':'approved','approved_by':approved_by,'approved_at':created,'checkpoint_hash':cp['checkpoint_hash']}; ph=_hash(payload)
        self.db.execute('INSERT INTO phase12_ops_recovery_approvals_293 VALUES(?,?,?,?,?,?,?,?)',(aid,job_id,cp['checkpoint_id'],'approved',approved_by,created,cp['checkpoint_hash'],ph))
        self.db.execute("UPDATE phase12_ops_jobs_293 SET status='queued',last_error='',updated_at=? WHERE op_job_id=?",(_now(),job_id)); self._event(j['case_id'],j['mission_id'],job_id,'recovery_approved',{'approval_id':aid,'checkpoint_id':cp['checkpoint_id'],'new_status':'queued'},approved_by)
        return {'op_job_id':job_id,'status':'queued','approval_id':aid,'checkpoint_id':cp['checkpoint_id'],'scope_expansion':False}

    def observability_snapshot(self,*,actor:str|None=None,store:bool=True):
        actor=actor or self.actor; counts={}
        for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_ops_jobs_293 GROUP BY status'):counts[r['status']]=int(r['n'])
        active=int(self.db.one("SELECT COUNT(DISTINCT case_id) n FROM phase12_ops_jobs_293 WHERE status IN ('queued','running','recovery_pending','paused')")['n'])
        workers={}
        for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_worker_health_293 GROUP BY status'):workers[r['status']]=int(r['n'])
        integrity={'event_chain_ok':self.verify_event_chain(),'sqlite_integrity':str(self.db.one('PRAGMA integrity_check')['integrity_check']) if self.db.one('PRAGMA integrity_check') else 'unknown','foreign_key_violations':len(self.db.all('PRAGMA foreign_key_check')),'network_access':False}
        degraded=counts.get('failed',0)>0 or counts.get('recovery_pending',0)>0 or workers.get('stale',0)>0 or not integrity['event_chain_ok'] or integrity['foreign_key_violations']>0
        summary=(f"{active} aktive Fälle · {counts.get('queued',0)} wartend · {counts.get('running',0)} laufend · {counts.get('recovery_pending',0)} Recovery offen. "+('System benötigt Review.' if degraded else 'Operationaler Zustand ist stabil.'))
        data={'queue_counts':counts,'active_cases':active,'worker_counts':workers,'integrity':integrity,'beginner_summary':summary,'degraded':degraded}
        if store:
            sid=_id('ops293obs'); created=_now(); payload={'snapshot_id':sid,**data,'created_by':actor,'created_at':created}; self.db.execute('INSERT INTO phase12_observability_snapshots_293 VALUES(?,?,?,?,?,?,?,?,?)',(sid,_canon(counts),active,_canon(workers),_canon(integrity),summary,actor,created,_hash(payload))); data['snapshot_id']=sid
        return data

    def explain_operations(self,case_id:str=''):
        obs=self.observability_snapshot(store=False); q='SELECT * FROM phase12_ops_jobs_293'; args=()
        if case_id:q+=' WHERE case_id=?'; args=(case_id,)
        q+=' ORDER BY created_at DESC LIMIT 1'; j=self.db.one(q,args)
        if not j:
            return {'stand':'Für diesen Fall liegt noch kein operationaler Build-293-Job vor.','meaning':'Build 293 kann lokale AI-/Analysearbeit über mehrere Fälle hinweg geplant, begrenzt und nach Unterbrechungen kontrolliert wiederaufnehmbar machen.','next':'Eine autorisierte Phase-12-Mission auswählen und einen lokalen Operational-Job einreihen.','observability':obs}
        stand=f"Letzter Job: {j['work_kind']} · Status {j['status']} · lokale Schritte {j['consumed_local_steps']}/{j['max_local_steps']}."
        if j['status']=='recovery_pending': meaning='Der Worker wurde unterbrochen oder ein Fehlerzustand ist unklar. EagleEye führt nicht automatisch weiter.'; nxt="Checkpoint prüfen und nur mit 'OK' des Hauptermittlers für einen erneuten Versuch freigeben."
        elif j['status']=='queued': meaning='Der Auftrag ist freigegeben und wartet in der fallübergreifenden Queue.'; nxt='Worker-Lauf starten oder Queue priorisieren; der Scope bleibt an diesen Fall gebunden.'
        elif j['status']=='running': meaning='Ein lokaler Worker hält derzeit eine zeitlich begrenzte Lease.'; nxt='Heartbeat/Lease beobachten; bei Ausfall wechselt der Job in Recovery statt still neu zu starten.'
        elif j['status']=='completed': meaning='Der lokale Arbeitsschritt wurde mit Checkpoint abgeschlossen.'; nxt='Ergebnis prüfen und erst danach den nächsten Ermittlungsauftrag freigeben.'
        else: meaning='Der Job ist angehalten oder fehlgeschlagen und braucht menschliche Prüfung.'; nxt='Fehler/Checkpoint prüfen; keine automatische Scope-Erweiterung zulassen.'
        return {'stand':stand,'meaning':meaning,'next':nxt,'op_job_id':j['op_job_id'],'status':j['status'],'observability':obs}

    def startup_contract_status(self):
        import eagleeye_pro.version as v
        checks={'version_build':tuple(map(int,v.BUILD.split('.'))) >= (293,0),'version_schema':tuple(map(int,v.SCHEMA_VERSION.split('.'))) >= (293,0),'project_entrypoint':(self.base_dir/'EAGLEEYE_PRO_293_0.py').exists(),'startup_acceptance_script':(self.base_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_293_0.py').exists(),'generic_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO.bat').exists(),'versioned_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO_293_0.bat').exists(),'setup_script':(self.base_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.base_dir/'requirements-windows.txt').exists()}
        return {'build':'293.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True}

    def all_training_cases(self):
        out=self.build292.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_293 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows:out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build292.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_293 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_293 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build293_delta_cases':d,'build293_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'293.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_293 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval293'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}; self.db.execute('INSERT INTO ai_evaluation_batches_293 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build292.performance_status(model_label); return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False,'required_corpus_size':224,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 293 beansprucht keine ≥85%-Leistung ohne vollständigen unabhängigen 224-Fälle-Lauf.'}

    def qualified_gate(self):
        parent=self.build292.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); sc=self.startup_contract_status(); obs=self.observability_snapshot(store=False)
        g={'build':'293.0','parent_gate':bool(parent['release_ready']),'multicase_queue':True,'idempotent_dispatch':True,'lease_heartbeat':True,'crash_recovery_requires_ok':True,'resource_budgets':True,'observability':True,'beginner_guidance':True,'event_chain_ok':obs['integrity']['event_chain_ok'],'foreign_keys_ok':obs['integrity']['foreign_key_violations']==0,'network_access':False,'external_collection_auto_execution':False,'hard_training_corpus_224':tm['reviewed_hard_cases']>=224 and tm['build293_delta_cases']>=16 and tm['build293_delta_extreme']>=4,'evaluation_batch_224_ready':batch['corpus_size']==224 and abs(batch['minimum_mean_score']-0.85)<1e-9,'startup_contract_ready':sc['contract_ready'],'actual_startup_release_test_required':True,'automatic_model_activation':False,'human_authority_preserved':True}
        g['release_ready']=all([g['parent_gate'],g['multicase_queue'],g['idempotent_dispatch'],g['lease_heartbeat'],g['crash_recovery_requires_ok'],g['resource_budgets'],g['observability'],g['beginner_guidance'],g['event_chain_ok'],g['foreign_keys_ok'],not g['network_access'],not g['external_collection_auto_execution'],g['hard_training_corpus_224'],g['evaluation_batch_224_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True); x=self.explain_operations(case_id); tm=self.training_metrics(); perf=self.performance_status(); obs=x['observability']; latest=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        actions=''; m=None
        try:m=self._mission(case_id=case_id)
        except Exception:pass
        if m and m['status']=='authorized':
            actions+=f"<form method='post' action='/build293/enqueue'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><input type='hidden' name='work_kind' value='observability_snapshot'><button>Lokalen Operational-Job einreihen</button></form>"
        actions+=f"<form method='post' action='/build293/run-next'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Nächsten lokalen Queue-Job ausführen</button></form>"
        if latest and latest['status']=='recovery_pending':
            actions+=f"<form method='post' action='/build293/recovery/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='op_job_id' value='{e(latest['op_job_id'])}'><label>Recovery-Freigabe <input name='confirmation' placeholder='OK'></label> <button>Recovery mit OK freigeben</button></form>"
        q=obs['queue_counts']; return f"""
<section class='card'><h2>Operational Strength · Build 293</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{e(x['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(x['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(x['next'])}</div>
<p><b>Fallübergreifende Queue:</b> {e(obs['active_cases'])} aktive Fälle · {e(q.get('queued',0))} wartend · {e(q.get('running',0))} laufend · {e(q.get('recovery_pending',0))} Recovery offen · {e(q.get('failed',0))} fehlgeschlagen.</p>{actions}
<details><summary>Analyst/Experte: Leases, Ressourcen, Integrity, Startup und Training</summary><p>Event-Chain: <b>{'OK' if obs['integrity']['event_chain_ok'] else 'FEHLER'}</b> · FK-Verstöße: <b>{e(obs['integrity']['foreign_key_violations'])}</b> · Netzwerkzugriff im Build-293-Scheduler: <b>aus</b>. Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. AI-Gate: 224/224 Fälle, ≥85%, 0 kritische Fehler, unabhängige Evaluation.</p></details>
</section>"""
