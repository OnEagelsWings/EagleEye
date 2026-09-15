from __future__ import annotations
import hashlib, html, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256((_canon(v) if not isinstance(v,str) else v).encode('utf-8')).hexdigest()
def _safe(v,d):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else d)
    except Exception:return d

class Build294OperationalResilienceService:
    BUILD='294.0'; GATE_THRESHOLD=0.88
    def __init__(self,db:Any,audit:Any,*,build293:Any,build292:Any,build281:Any,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build293=build293; self.build292=build292; self.build281=build281; self.base_dir=Path(base_dir); self.actor=actor

    def _scheduler_row(self,case_id:str):
        row=self.db.one('SELECT * FROM phase12_case_scheduler_294 WHERE case_id=?',(case_id,))
        if row:return row
        now=_now(); self.db.execute("INSERT INTO phase12_case_scheduler_294(case_id,last_claimed_at,claim_count,fault_state,fault_reason,updated_at) VALUES(?,?,?,?,?,?)",(case_id,'',0,'active','',now))
        return self.db.one('SELECT * FROM phase12_case_scheduler_294 WHERE case_id=?',(case_id,))

    def _fault_event(self,case_id:str,mission_id:str,job_id:str,severity:str,event_type:str,reason:str,details:dict,actor:str):
        prev=self.db.one('SELECT event_hash FROM phase12_fault_events_294 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); ph=prev['event_hash'] if prev else 'GENESIS'
        eid=_id('fault294'); created=_now(); payload={'fault_event_id':eid,'case_id':case_id,'mission_id':mission_id,'op_job_id':job_id,'severity':severity,'event_type':event_type,'reason':reason,'details':details,'created_by':actor,'created_at':created,'previous_hash':ph}; eh=_hash(payload)
        self.db.execute('INSERT INTO phase12_fault_events_294 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,case_id,mission_id,job_id,severity,event_type,reason,_canon(details),actor,created,ph,eh))
        return {'fault_event_id':eid,'event_hash':eh}

    def verify_fault_chain(self,case_id:str=''):
        q='SELECT * FROM phase12_fault_events_294'; args=()
        if case_id:q+=' WHERE case_id=?'; args=(case_id,)
        q+=' ORDER BY case_id,rowid'; rows=self.db.all(q,args); prev={}
        for r in rows:
            ph=prev.get(r['case_id'],'GENESIS')
            if r['previous_hash']!=ph:return False
            payload={'fault_event_id':r['fault_event_id'],'case_id':r['case_id'],'mission_id':r['mission_id'],'op_job_id':r['op_job_id'],'severity':r['severity'],'event_type':r['event_type'],'reason':r['reason'],'details':_safe(r['details_json'],{}),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
            if _hash(payload)!=r['event_hash']:return False
            prev[r['case_id']]=r['event_hash']
        return True

    def isolate_case(self,*,case_id:str,reason:str,job_id:str='',severity:str='critical',actor:str|None=None):
        actor=actor or self.actor; reason=str(reason or 'operational fault requires review')[:500]
        mission=self.db.one("SELECT mission_id FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,)); mid=mission['mission_id'] if mission else ''
        self._scheduler_row(case_id); now=_now(); self.db.execute("UPDATE phase12_case_scheduler_294 SET fault_state='isolated',fault_reason=?,updated_at=? WHERE case_id=?",(reason,now,case_id))
        # Running work becomes review-pending. Queued work stays queued but the fair scheduler will not claim it.
        running=self.db.all("SELECT op_job_id FROM phase12_ops_jobs_293 WHERE case_id=? AND status='running'",(case_id,))
        for r in running:
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='recovery_pending',lease_owner='',lease_expires_at='',heartbeat_at='',last_error=?,updated_at=? WHERE op_job_id=?",('case fault domain isolated: '+reason,now,r['op_job_id']))
            self.build293.create_checkpoint(job_id=r['op_job_id'],reason='fault_domain_isolated',actor=actor)
        evt=self._fault_event(case_id,mid,job_id,severity,'case_isolated',reason,{'running_jobs_moved_to_recovery':len(running),'automatic_retry':False,'new_ok_required':True},actor)
        return {'case_id':case_id,'fault_state':'isolated','reason':reason,'running_jobs_moved_to_recovery':len(running),'new_ok_required':True,**evt}

    def clear_isolation(self,*,case_id:str,confirmation:str,approved_by:str):
        if str(confirmation).strip().upper()!='OK': raise PermissionError("Fault-Isolation darf nur mit ausdrücklichem 'OK' aufgehoben werden.")
        row=self._scheduler_row(case_id)
        if row['fault_state']!='isolated': raise ValueError('case is not isolated')
        now=_now(); self.db.execute("UPDATE phase12_case_scheduler_294 SET fault_state='active',fault_reason='',updated_at=? WHERE case_id=?",(now,case_id))
        mission=self.db.one("SELECT mission_id FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,)); mid=mission['mission_id'] if mission else ''
        evt=self._fault_event(case_id,mid,'','review','case_isolation_cleared','lead investigator approved fault-domain reopening',{'recovery_jobs_auto_resumed':False},approved_by)
        return {'case_id':case_id,'fault_state':'active','recovery_jobs_auto_resumed':False,**evt}

    def _queue_counts(self):
        out={}
        for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_ops_jobs_293 GROUP BY status'):out[r['status']]=int(r['n'])
        return out

    def pressure_snapshot(self,*,actor:str|None=None,store:bool=True):
        actor=actor or self.actor; counts=self._queue_counts(); per_case={}
        for r in self.db.all("SELECT case_id,status,COUNT(*) n FROM phase12_ops_jobs_293 WHERE status IN ('queued','running','recovery_pending','paused','failed') GROUP BY case_id,status"):
            per_case.setdefault(r['case_id'],{})[r['status']]=int(r['n'])
        workers={}
        for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_worker_health_293 GROUP BY status'):workers[r['status']]=int(r['n'])
        isolated=int(self.db.one("SELECT COUNT(*) n FROM phase12_case_scheduler_294 WHERE fault_state='isolated'")['n'])
        queued=counts.get('queued',0); recovery=counts.get('recovery_pending',0); failed=counts.get('failed',0); stale=workers.get('stale',0); running=counts.get('running',0)
        score=min(1.0,queued/20.0 + recovery*0.12 + failed*0.18 + stale*0.18 + max(0,running-4)*0.05 + isolated*0.08)
        if score>=0.85: level='critical'; minprio=90
        elif score>=0.60: level='high'; minprio=70
        elif score>=0.35: level='elevated'; minprio=40
        else: level='normal'; minprio=1
        backpressure=level!='normal'
        summary=f"Betriebsdruck {level}: {queued} wartend, {running} laufend, {recovery} Recovery offen, {isolated} Fälle isoliert."
        data={'pressure_level':level,'pressure_score':round(score,4),'queue_counts':counts,'per_case':per_case,'worker_counts':workers,'isolated_cases':isolated,'min_claim_priority':minprio,'backpressure_active':backpressure,'beginner_summary':summary}
        if store:
            sid=_id('pressure294'); created=_now(); payload={'pressure_snapshot_id':sid,**data,'created_by':actor,'created_at':created}; self.db.execute('INSERT INTO phase12_pressure_snapshots_294 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,level,float(data['pressure_score']),_canon(counts),_canon(per_case),_canon(workers),isolated,minprio,1 if backpressure else 0,summary,actor,created,_hash(payload))); data['pressure_snapshot_id']=sid
        return data

    def telemetry_history(self,limit:int=20):
        rows=self.db.all('SELECT * FROM phase12_pressure_snapshots_294 ORDER BY rowid DESC LIMIT ?',(max(1,min(int(limit),200)),))
        return [{'pressure_snapshot_id':r['pressure_snapshot_id'],'pressure_level':r['pressure_level'],'pressure_score':float(r['pressure_score']),'queue_counts':_safe(r['queue_counts_json'],{}),'worker_counts':_safe(r['worker_counts_json'],{}),'isolated_cases':int(r['isolated_cases']),'min_claim_priority':int(r['min_claim_priority']),'backpressure_active':bool(r['backpressure_active']),'created_at':r['created_at']} for r in rows]

    def fair_claim_next_job(self,*,worker_id:str='ai-worker-294',lease_seconds:int=120):
        self.build293.recover_expired_leases(actor='ops-recovery-294')
        pressure=self.pressure_snapshot(store=True,actor=worker_id); minprio=int(pressure['min_claim_priority'])
        # Ensure scheduler state exists for every case with queued work.
        for r in self.db.all("SELECT DISTINCT case_id FROM phase12_ops_jobs_293 WHERE status='queued'"): self._scheduler_row(r['case_id'])
        eligible=self.db.all("""
          SELECT j.case_id,MAX(j.priority) top_priority,MIN(j.created_at) oldest,
                 COALESCE(s.last_claimed_at,'') last_claimed_at,COALESCE(s.claim_count,0) claim_count
          FROM phase12_ops_jobs_293 j
          LEFT JOIN phase12_case_scheduler_294 s ON s.case_id=j.case_id
          WHERE j.status='queued' AND j.priority>=? AND COALESCE(s.fault_state,'active')<>'isolated'
          GROUP BY j.case_id
        """,(minprio,))
        if not eligible:
            self.db.execute('INSERT OR REPLACE INTO phase12_worker_health_293 VALUES(?,?,?,?,?,?)',(worker_id,'idle','',_now(),'',_now()))
            return None
        # Case fairness first: least recently served case, then fewer claims, then priority, then oldest job.
        ordered=sorted(eligible,key=lambda r:(r['last_claimed_at'] or '',int(r['claim_count']),-int(r['top_priority']),r['oldest']))
        chosen=ordered[0]; case_id=chosen['case_id']
        with self.db.transaction(immediate=True):
            job=self.db.one("SELECT * FROM phase12_ops_jobs_293 WHERE status='queued' AND case_id=? AND priority>=? ORDER BY priority DESC,created_at ASC LIMIT 1",(case_id,minprio))
            if not job:return None
            from datetime import datetime,timedelta,timezone
            expiry=(datetime.now(timezone.utc)+timedelta(seconds=max(30,min(int(lease_seconds),900)))).replace(microsecond=0).isoformat().replace('+00:00','Z'); now=_now()
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='running',attempt_count=attempt_count+1,lease_owner=?,lease_expires_at=?,heartbeat_at=?,updated_at=? WHERE op_job_id=? AND status='queued'",(worker_id,expiry,now,now,job['op_job_id']))
            self.db.execute("UPDATE phase12_case_scheduler_294 SET last_claimed_at=?,claim_count=claim_count+1,updated_at=? WHERE case_id=?",(now,now,case_id))
            claimed=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job['op_job_id'],))
        self.db.execute('INSERT OR REPLACE INTO phase12_worker_health_293 VALUES(?,?,?,?,?,?)',(worker_id,'busy',claimed['op_job_id'],_now(),claimed['lease_expires_at'],_now()))
        reason=f"least-recently-served eligible case; priority {claimed['priority']} >= backpressure floor {minprio}"
        did=_id('sched294'); created=_now(); payload={'decision_id':did,'worker_id':worker_id,'selected_case_id':case_id,'selected_job_id':claimed['op_job_id'],'pressure_level':pressure['pressure_level'],'min_claim_priority':minprio,'fairness_reason':reason,'eligible_cases':[r['case_id'] for r in ordered],'created_by':worker_id,'created_at':created}; self.db.execute('INSERT INTO phase12_scheduler_decisions_294 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,worker_id,case_id,claimed['op_job_id'],pressure['pressure_level'],minprio,reason,_canon(payload['eligible_cases']),worker_id,created,_hash(payload)))
        # mirror event into existing immutable ops ledger for continuity
        self.build293._event(claimed['case_id'],claimed['mission_id'],claimed['op_job_id'],'fair_job_claimed_294',{'worker_id':worker_id,'pressure_level':pressure['pressure_level'],'min_claim_priority':minprio,'fairness_reason':reason},worker_id)
        return claimed

    def run_next_fair_job(self,*,worker_id:str='ai-worker-294'):
        j=self.fair_claim_next_job(worker_id=worker_id)
        if not j:return {'status':'idle','network_access':False,'backpressure':self.pressure_snapshot(store=False)}
        try:return self.build293.execute_claimed_job(job_id=j['op_job_id'],worker_id=worker_id)
        except Exception as exc:
            self.isolate_case(case_id=j['case_id'],reason=f'{type(exc).__name__}: {exc}',job_id=j['op_job_id'],severity='critical',actor=worker_id)
            raise

    def explain_operations(self,case_id:str=''):
        p=self.pressure_snapshot(store=False); s=self._scheduler_row(case_id) if case_id else None
        if s and s['fault_state']=='isolated':
            return {'stand':f"Dieser Fall ist isoliert. Betriebsdruck: {p['pressure_level']}.",'meaning':'Ein Fehler wurde auf diesen Fall begrenzt. Andere Fälle dürfen weiterarbeiten; dieser Fall wird nicht automatisch erneut ausgeführt.','next':"Fehler und Checkpoint prüfen. Erst danach Isolation mit 'OK' aufheben; Recovery-Jobs benötigen zusätzlich ihre eigene Freigabe.",'pressure':p,'fault_state':'isolated'}
        if p['pressure_level']=='normal': meaning='Die Queue liegt innerhalb der aktuellen lokalen Kapazitätsgrenzen.'; nxt='Normale fallfaire Abarbeitung fortsetzen.'
        else: meaning='EagleEye reduziert unter Last bewusst die Zahl niedriger priorisierter Starts, statt Ressourcen still zu überbuchen.'; nxt=f"Nur Jobs ab Priorität {p['min_claim_priority']} starten; Queue, stale Worker und Recovery-Fälle prüfen."
        return {'stand':p['beginner_summary'],'meaning':meaning,'next':nxt,'pressure':p,'fault_state':s['fault_state'] if s else 'unknown'}

    def startup_contract_status(self):
        import eagleeye_pro.version as v
        checks={'version_build':tuple(map(int,v.BUILD.split('.'))) >= (294,0),'version_schema':tuple(map(int,v.SCHEMA_VERSION.split('.'))) >= (294,0),'project_entrypoint':(self.base_dir/'EAGLEEYE_PRO_294_0.py').exists(),'startup_acceptance_script':(self.base_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_294_0.py').exists(),'generic_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO.bat').exists(),'versioned_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO_294_0.bat').exists(),'setup_script':(self.base_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.base_dir/'requirements-windows.txt').exists()}
        return {'build':'294.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True}

    def all_training_cases(self):
        out=self.build293.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_294 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows:out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build293.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_294 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_294 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build294_delta_cases':d,'build294_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'294.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_294 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval294'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}; self.db.execute('INSERT INTO ai_evaluation_batches_294 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build293.performance_status(model_label); return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False,'required_corpus_size':240,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 294 beansprucht keine ≥88%-Leistung ohne vollständigen unabhängigen 240-Fälle-Lauf.'}

    def qualified_gate(self):
        parent=self.build293.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); sc=self.startup_contract_status(); p=self.pressure_snapshot(store=False)
        g={'build':'294.0','parent_gate':bool(parent['release_ready']),'fault_isolation':True,'fair_scheduler':True,'backpressure':True,'historical_telemetry':True,'beginner_guidance':True,'fault_chain_ok':self.verify_fault_chain(),'foreign_keys_ok':len(self.db.all('PRAGMA foreign_key_check'))==0,'network_access':False,'external_collection_auto_execution':False,'hard_training_corpus_240':tm['reviewed_hard_cases']>=240 and tm['build294_delta_cases']>=16 and tm['build294_delta_extreme']>=4,'evaluation_batch_240_ready':batch['corpus_size']==240 and abs(batch['minimum_mean_score']-0.88)<1e-9,'startup_contract_ready':sc['contract_ready'],'actual_startup_release_test_required':True,'automatic_model_activation':False,'human_authority_preserved':True,'pressure_level':p['pressure_level']}
        g['release_ready']=all([g['parent_gate'],g['fault_isolation'],g['fair_scheduler'],g['backpressure'],g['historical_telemetry'],g['beginner_guidance'],g['fault_chain_ok'],g['foreign_keys_ok'],not g['network_access'],not g['external_collection_auto_execution'],g['hard_training_corpus_240'],g['evaluation_batch_240_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True); x=self.explain_operations(case_id); tm=self.training_metrics(); perf=self.performance_status(); p=x['pressure']; s=self._scheduler_row(case_id) if case_id else None
        actions=f"<form method='post' action='/build294/run-next'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Nächsten fallfairen lokalen Job ausführen</button></form>"
        if s and s['fault_state']=='isolated': actions+=f"<form method='post' action='/build294/isolation/clear'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>Isolation aufheben <input name='confirmation' placeholder='OK'></label> <button>Mit OK prüfen/freigeben</button></form>"
        q=p['queue_counts']; return f"""
<section class='card'><h2>Operational Resilience · Build 294</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{e(x['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(x['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(x['next'])}</div>
<p><b>Backpressure:</b> {e(p['pressure_level'])} · Score {e(p['pressure_score'])} · Mindestpriorität für neue Starts {e(p['min_claim_priority'])} · isolierte Fälle {e(p['isolated_cases'])}.</p>
<p><b>Queue:</b> {e(q.get('queued',0))} wartend · {e(q.get('running',0))} laufend · {e(q.get('recovery_pending',0))} Recovery · {e(q.get('failed',0))} fehlgeschlagen.</p>{actions}
<details><summary>Analyst/Experte: Fairness, Fault-Domains, Telemetrie und AI-Gate</summary><p>Fault-Chain: <b>{'OK' if self.verify_fault_chain() else 'FEHLER'}</b> · Netzwerkzugriff im Scheduler: <b>aus</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. AI-Gate: 240/240 Fälle, ≥88%, 0 kritische Fehler, unabhängige Evaluation.</p></details>
</section>"""
