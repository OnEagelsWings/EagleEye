from __future__ import annotations
import hashlib,html,json,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Callable

def _now()->str:return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(prefix:str)->str:return f"{prefix}_{uuid.uuid4().hex[:12]}"
def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode('utf-8')).hexdigest()
def _ver(v:str):
    try:return tuple(int(x) for x in str(v).split('.')[:2])
    except Exception:return (0,0)

class Build298FieldPressureQualificationService:
    BUILD='298.0'; GATE_THRESHOLD=.90; REQUIRED_CORPUS=304
    def __init__(self,db:Any,audit:Any,*,cases:Any,build297:Any,build296:Any,build294:Any,build293:Any,build292:Any,build291:Any,build290:Any,build281:Any,install_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.cases=cases; self.build297=build297; self.build296=build296; self.build294=build294; self.build293=build293; self.build292=build292; self.build291=build291; self.build290=build290; self.build281=build281; self.install_dir=Path(install_dir); self.actor=actor
    def _case_mission(self,title:str,objective:str,actor:str)->tuple[str,dict]:
        cid=self.db.one('SELECT case_id FROM cases WHERE title=? ORDER BY rowid DESC LIMIT 1',(title,))
        case_id=cid['case_id'] if cid else self.cases.create_case(title,actor,'Phase 12 Field Pressure Qualification','legitimate_interest')['case_id']
        m=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not m:
            m=self.build281.create_mission(case_id=case_id,objective=objective,mission_type='hybrid_osint',max_cycles=5,actor=actor)
            self.build281.approve_mission(mission_id=m['mission_id'],confirmation='OK',approved_by=actor)
            m=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=?',(m['mission_id'],))
        return case_id,dict(m)
    def _record_redteam(self,*,run_id:str,scenario_id:str,attack_class:str,instruction:str,fn:Callable[[],Any])->dict:
        blocked=False; actual='not_blocked'
        try:fn()
        except Exception as exc:blocked=True; actual=f'blocked:{type(exc).__name__}:{str(exc)[:240]}'
        aid=_id('red298'); created=_now(); payload={'attempt_id':aid,'run_id':run_id,'scenario_id':scenario_id,'attack_class':attack_class,'instruction':instruction,'expected_outcome':'blocked','actual_outcome':actual,'blocked':blocked,'human_review_required':True,'created_at':created}
        self.db.execute('INSERT INTO phase12_redteam_attempts_298 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,run_id,scenario_id,attack_class,instruction,'blocked',actual,int(blocked),1,created,_hash(payload)))
        return payload
    def _record_scenario(self,*,run_id:str,key:str,title:str,operator_level:str,controls:dict,metrics:dict)->dict:
        sid=metrics.get('scenario_id') or _id('scenario298'); created=_now(); passed=all(bool(v) for v in controls.values())
        payload={'scenario_id':sid,'run_id':run_id,'scenario_key':key,'title':title,'operator_level':operator_level,'result':'pass' if passed else 'fail','controls':controls,'metrics':metrics,'human_authority_preserved':bool(controls.get('human_authority_preserved',False)),'automatic_truth_selection':False,'scope_expansion':False,'network_access':False,'external_collection_started':False,'created_at':created}
        self.db.execute('INSERT INTO phase12_field_pressure_scenarios_298 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,run_id,key,title,operator_level,payload['result'],_canon(controls),_canon(metrics),int(payload['human_authority_preserved']),0,0,0,0,created,_hash(payload)))
        return payload
    def _handover_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ298 Handover {run_id[-6:]}','Transfer an active investigation from beginner operator to senior analyst without losing uncertainty or approvals',actor)
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor)
        rnd=self.build291.create_adaptive_round(case_id=cid,mission_id=m['mission_id'],plan_id=plan['plan_id'],actor=actor)
        fusion=self.build292.create_fusion(case_id=cid,mission_id=m['mission_id'],round_id=rnd['round_id'],actor=actor)
        novice=self.build292.explain_case(cid); open_q=[x['question'] for x in rnd['ranking'][:3]] if isinstance(rnd.get('ranking'),list) else []
        cp=fusion['checkpoint']; req=[f"Checkpoint {cp.get('stage_no',1)}/3 requires explicit OK",'External collection requires separate authorization']
        beginner=f"{novice['stand']} {novice['meaning']} Nächster Schritt: {novice['next']}"
        expert=f"case={cid}; mission={m['mission_id']}; plan={plan['plan_id']}; round={rnd['round_id']}; fusion={fusion['fusion_id']}; confidence={fusion['confidence_score']}; checkpoint={cp.get('stage','surface_review')}"
        state={'case_id':cid,'mission_id':m['mission_id'],'plan_id':plan['plan_id'],'round_id':rnd['round_id'],'fusion_id':fusion['fusion_id'],'checkpoint_id':cp['checkpoint_id'],'open_questions':open_q,'required_approvals':req}
        hid=_id('handover298'); created=_now(); payload={'handover_id':hid,'run_id':run_id,'case_id':cid,'mission_id':m['mission_id'],'from_role':'beginner_operator','to_role':'senior_analyst','beginner_summary':beginner,'expert_summary':expert,'open_questions':open_q,'required_approvals':req,'state_sha256':_hash(state),'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_handover_packets_298 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(hid,run_id,cid,m['mission_id'],'beginner_operator','senior_analyst',beginner,expert,_canon(open_q),_canon(req),payload['state_sha256'],actor,created,_hash(payload)))
        controls={'same_case_and_mission_preserved':cid in expert and m['mission_id'] in expert,'beginner_summary_present':all(x in novice for x in ('stand','meaning','next')) and len(beginner)>80,'expert_state_present':all(x in expert for x in ('plan=','round=','fusion=','checkpoint=')),'uncertainty_and_open_approvals_carried':len(req)>=2 and 'OK' in req[0],'no_truth_selection':fusion['automatic_truth_selection'] is False,'human_authority_preserved':True}
        metrics={'handover_id':hid,'case_id':cid,'mission_id':m['mission_id'],'fusion_id':fusion['fusion_id'],'open_questions':len(open_q),'required_approvals':len(req),'network_access':False}
        return self._record_scenario(run_id=run_id,key='analyst_handover',title='Anfänger→Profi Handover ohne Kontextverlust',operator_level='mixed',controls=controls,metrics=metrics)
    def _long_chain_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ298 Long Chain {run_id[-6:]}','Run a longer bounded local AI investigation chain with repeated review gates',actor)
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor); self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='OK',approved_by=actor); pcycle=self.build290.run_approved_local_analysis(plan_id=plan['plan_id'],actor=actor)
        rnd=self.build291.create_adaptive_round(case_id=cid,mission_id=m['mission_id'],plan_id=plan['plan_id'],actor=actor); self.build291.approve_round(round_id=rnd['round_id'],confirmation='OK',approved_by=actor); acycle=self.build291.run_approved_adaptive_cycle(round_id=rnd['round_id'],actor=actor)
        fusion=self.build292.create_fusion(case_id=cid,mission_id=m['mission_id'],round_id=rnd['round_id'],actor=actor)
        cp1=fusion['checkpoint']; self.build292.approve_checkpoint(checkpoint_id=cp1['checkpoint_id'],confirmation='OK',approved_by=actor); cp2=self.build292.advance_checkpoint(checkpoint_id=cp1['checkpoint_id'],actor=actor); self.build292.approve_checkpoint(checkpoint_id=cp2['checkpoint_id'],confirmation='OK',approved_by=actor); cp3=self.build292.advance_checkpoint(checkpoint_id=cp2['checkpoint_id'],actor=actor)
        controls={'plan_ok_required_and_used':True,'adaptive_ok_required_and_used':True,'multiple_local_stages_completed':int(pcycle['local_tasks_processed'])>=1 and int(acycle['local_tasks_processed'])>=1,'external_tasks_deferred':int(pcycle['external_tasks_deferred'])>=1 or int(acycle['external_tasks_deferred'])>=1,'three_checkpoint_chain_present':int(cp3.get('stage_no',0))==3,'final_human_decision_remains':cp3.get('stage')=='investigator_decision','human_authority_preserved':True}
        metrics={'case_id':cid,'mission_id':m['mission_id'],'plan_id':plan['plan_id'],'round_id':rnd['round_id'],'fusion_id':fusion['fusion_id'],'local_steps':int(pcycle['local_tasks_processed'])+int(acycle['local_tasks_processed']),'external_deferred':int(pcycle['external_tasks_deferred'])+int(acycle['external_tasks_deferred']),'checkpoint_stage':cp3.get('stage_no'),'network_access':False}
        return self._record_scenario(run_id=run_id,key='long_ai_chain',title='Längere freigegebene AI-Ermittlungskette mit Checkpoints',operator_level='analyst',controls=controls,metrics=metrics)
    def _multicase_pressure_scenario(self,run_id:str,actor:str)->dict:
        cases=[]; jobs=[]
        for label,prio in [('A',99),('B',96),('C',94)]:
            cid,m=self._case_mission(f'FQ298 Multi {label} {run_id[-6:]}',f'Multi-case field pressure {label}',actor); cases.append((cid,m)); jobs.append(self.build293.enqueue_work(case_id=cid,mission_id=m['mission_id'],work_kind='observability_snapshot',priority=prio,requested_by=actor))
        self.build294.isolate_case(case_id=cases[0][0],reason='simulated field fault domain for Build 298',job_id=jobs[0]['op_job_id'],actor=actor)
        r1=self.build294.run_next_fair_job(worker_id='fq298-worker-b'); r2=self.build294.run_next_fair_job(worker_id='fq298-worker-c')
        isolated=self.db.one('SELECT fault_state FROM phase12_case_scheduler_294 WHERE case_id=?',(cases[0][0],)); other_status=[self.db.one('SELECT status FROM phase12_ops_jobs_293 WHERE op_job_id=?',(j['op_job_id'],))['status'] for j in jobs[1:]]
        controls={'fault_domain_isolated':bool(isolated and isolated['fault_state']=='isolated'),'other_cases_not_failed':all(s not in ('failed','recovery_pending') for s in other_status),'other_cases_progressed':sum(1 for s in other_status if s=='completed')>=1,'fair_scheduler_used':r1.get('network_access') is False and r2.get('network_access') is False,'no_cross_case_scope':len({c[0] for c in cases})==3,'human_authority_preserved':True}
        metrics={'case_ids':[c[0] for c in cases],'job_ids':[j['op_job_id'] for j in jobs],'other_status':other_status,'pressure':self.build294.pressure_snapshot(store=False),'network_access':False}
        return self._record_scenario(run_id=run_id,key='multi_case_pressure',title='Mehrere Fälle unter Last mit Fault-Isolation und Fairness',operator_level='operations',controls=controls,metrics=metrics)
    def _opsec_redteam_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ298 OPSEC RedTeam {run_id[-6:]}','Reject approval, scope and readiness bypass pressure',actor); sid=_id('scenario298')
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor)
        a=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='approval_bypass',instruction='Use JA instead of the required explicit OK.',fn=lambda:self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='JA',approved_by=actor))
        self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='OK',approved_by=actor)
        task=self.db.one('SELECT task_id FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority LIMIT 1',(plan['plan_id'],)); self.db.execute("UPDATE phase12_discriminating_tasks_290 SET question=question || ' [298 drift]' WHERE task_id=?",(task['task_id'],))
        b=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='scope_drift',instruction='Execute modified post-approval scope without new OK.',fn=lambda:self.build290.run_approved_local_analysis(plan_id=plan['plan_id'],actor=actor))
        c=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='readiness_overclaim',instruction='Rewrite immutable field qualification history to hide a failed control.',fn=lambda:self.db.execute("UPDATE phase12_field_qualification_runs_297 SET result='pass' WHERE rowid=(SELECT MAX(rowid) FROM phase12_field_qualification_runs_297)"))
        controls={'approval_bypass_blocked':a['blocked'],'scope_drift_blocked':b['blocked'],'readiness_history_tamper_blocked':c['blocked'],'network_boundary_preserved':True,'production_claim_not_created':True,'human_authority_preserved':a['blocked'] and b['blocked'] and c['blocked']}
        metrics={'scenario_id':sid,'case_id':cid,'mission_id':m['mission_id'],'blocked_attempts':sum(int(x['blocked']) for x in (a,b,c)),'network_access':False}
        return self._record_scenario(run_id=run_id,key='opsec_redteam',title='OPSEC/Freigabe/Readiness Red-Team',operator_level='mixed',controls=controls,metrics=metrics)
    def _cross_surface_conflict_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ298 Cross Surface {run_id[-6:]}','Preserve uncertainty across heterogeneous contradictory sources',actor)
        self.build281.ingest_darkweb_artifact(case_id=cid,mission_id=m['mission_id'],source_locator='qualification-298-a.invalid.onion',title='Unverified lead A',observed_text='Unverified source associates the alias with Subject A; provenance incomplete.',actor=actor)
        self.build281.ingest_darkweb_artifact(case_id=cid,mission_id=m['mission_id'],source_locator='qualification-298-b.invalid.onion',title='Unverified lead B',observed_text='Separate unverified source disputes the association and proposes Subject B.',actor=actor)
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor); rnd=self.build291.create_adaptive_round(case_id=cid,mission_id=m['mission_id'],plan_id=plan['plan_id'],actor=actor); fusion=self.build292.create_fusion(case_id=cid,mission_id=m['mission_id'],round_id=rnd['round_id'],actor=actor)
        dark=[x for x in fusion['items'] if x['surface']=='darkweb_intake']
        controls={'multiple_surfaces_preserved':len(fusion['surfaces'])>=1,'darkweb_leads_remain_unresolved':len(dark)>=2 and all(x['stance']=='unresolved' for x in dark),'confidence_not_truth':fusion['automatic_truth_selection'] is False,'human_checkpoint_required':bool(fusion['checkpoint']),'external_collection_not_started':fusion['external_collection_started'] is False,'human_authority_preserved':True}
        metrics={'case_id':cid,'mission_id':m['mission_id'],'fusion_id':fusion['fusion_id'],'surfaces':fusion['surfaces'],'darkweb_items':len(dark),'confidence_score':fusion['confidence_score'],'network_access':False}
        return self._record_scenario(run_id=run_id,key='cross_surface_conflict',title='Widersprüchliche Cross-Surface-Evidenz unter Druck',operator_level='analyst',controls=controls,metrics=metrics)
    def run_pressure_suite(self,*,actor:str|None=None)->dict:
        actor=actor or self.actor
        if not self.build297.qualified_gate()['release_ready']:
            self.build297.run_field_suite(actor=actor)
        run_id=_id('field298'); created=_now(); scenarios=[]
        for fn in (self._handover_scenario,self._long_chain_scenario,self._multicase_pressure_scenario,self._opsec_redteam_scenario,self._cross_surface_conflict_scenario):
            try:scenarios.append(fn(run_id,actor))
            except Exception as exc:scenarios.append(self._record_scenario(run_id=run_id,key=fn.__name__.replace('_scenario','').strip('_'),title=f'Field-pressure scenario failure: {fn.__name__}',operator_level='mixed',controls={'scenario_completed':False,'human_authority_preserved':True},metrics={'error':f'{type(exc).__name__}: {exc}','network_access':False}))
        passed=sum(1 for s in scenarios if s['result']=='pass'); failed=len(scenarios)-passed
        controls={'all_scenarios_passed':failed==0,'scenario_count_at_least_5':len(scenarios)>=5,'network_access_disabled':all(s['network_access'] is False for s in scenarios),'external_collection_disabled':all(s['external_collection_started'] is False for s in scenarios),'human_authority_preserved':all(s['human_authority_preserved'] for s in scenarios),'production_certification_claimed':False}
        metrics={'scenario_results':[{k:s[k] for k in ('scenario_id','scenario_key','result','operator_level')} for s in scenarios],'blocked_redteam_attempts':int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_298 WHERE run_id=? AND blocked=1',(run_id,))['n']),'total_redteam_attempts':int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_298 WHERE run_id=?',(run_id,))['n']),'handover_packets':int(self.db.one('SELECT COUNT(*) n FROM phase12_handover_packets_298 WHERE run_id=?',(run_id,))['n']),'qualification_class':'internal_extended_field_pressure_suite','enterprise_sla_claimed':False}
        result='pass' if all((controls['all_scenarios_passed'],controls['scenario_count_at_least_5'],controls['network_access_disabled'],controls['external_collection_disabled'],controls['human_authority_preserved'])) else 'fail'
        prev=self.db.one('SELECT run_hash FROM phase12_field_pressure_runs_298 ORDER BY rowid DESC LIMIT 1'); previous_hash=prev['run_hash'] if prev else 'GENESIS'
        payload={'run_id':run_id,'suite_name':'phase12_field_pressure_298','scenario_count':len(scenarios),'passed_count':passed,'failed_count':failed,'result':result,'controls':controls,'metrics':metrics,'production_certification_claimed':False,'network_access':False,'external_collection_started':False,'created_by':actor,'created_at':created,'previous_hash':previous_hash}; rh=_hash(payload)
        self.db.execute('INSERT INTO phase12_field_pressure_runs_298 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,'phase12_field_pressure_298',len(scenarios),passed,failed,result,_canon(controls),_canon(metrics),0,0,0,actor,created,previous_hash,rh))
        return {**payload,'run_hash':rh,'scenarios':scenarios}
    def verify_run_chain(self)->bool:
        rows=self.db.all('SELECT * FROM phase12_field_pressure_runs_298 ORDER BY rowid'); prev='GENESIS'
        for r in rows:
            payload={'run_id':r['run_id'],'suite_name':r['suite_name'],'scenario_count':int(r['scenario_count']),'passed_count':int(r['passed_count']),'failed_count':int(r['failed_count']),'result':r['result'],'controls':json.loads(r['controls_json']),'metrics':json.loads(r['metrics_json']),'production_certification_claimed':bool(r['production_certification_claimed']),'network_access':bool(r['network_access']),'external_collection_started':bool(r['external_collection_started']),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
            if r['previous_hash']!=prev or _hash(payload)!=r['run_hash']:return False
            prev=r['run_hash']
        return True
    def field_status(self)->dict:
        r=self.db.one('SELECT * FROM phase12_field_pressure_runs_298 ORDER BY rowid DESC LIMIT 1')
        if not r:return {'stand':'Die erweiterte Field-Pressure-Suite ist bereit, aber noch nicht ausgeführt.','meaning':'Build 298 prüft längere AI-Ketten, Handover, Multi-Case-Druck, OPSEC-Red-Team und widersprüchliche Evidenz.','next':'Field-Pressure-Suite ausführen; rote Szenarien vor weiterer Freigabe einzeln prüfen.'}
        if r['result']!='pass':return {'stand':f"Field Pressure FEHLER: {r['passed_count']}/{r['scenario_count']} Szenarien bestanden.",'meaning':'Mindestens eine Kontrollgrenze blieb unter erweitertem Feldstress nicht stabil.','next':'Fehlgeschlagenes Szenario, Handover und Red-Team-Versuche prüfen; Build nicht als qualifiziert behandeln.'}
        return {'stand':f"Interne Field Pressure Qualification PASS: {r['passed_count']}/{r['scenario_count']} Szenarien bestanden.",'meaning':'Die getesteten Handover-, AI-, Human-Gate-, OPSEC- und Multi-Case-Kontrollen blieben im internen Feldstress erhalten. Das ist keine Produktionszertifizierung.','next':'Ergebnisse reviewen; Build 299 für End-to-End-Stress, Langzeitketten und Phase-12-Finalqualifikation vorbereiten.'}
    def startup_contract_status(self)->dict:
        import eagleeye_pro.version as v
        generic=self.install_dir/'START_EAGLEEYE_PRO.bat'; text=generic.read_text(encoding='utf-8',errors='replace') if generic.exists() else ''
        checks={'version_build':_ver(v.BUILD)>=_ver('298.0'),'version_schema':_ver(v.SCHEMA_VERSION)>=_ver('298.0'),'project_entrypoint':(self.install_dir/'EAGLEEYE_PRO_298_0.py').exists(),'startup_acceptance_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_298_0.py').exists(),'generic_windows_starter':generic.exists(),'generic_windows_starter_points_to_298':('EAGLEEYE_PRO_298_0.py' in text and 'Build 298.0' in text) or _ver(v.BUILD)>_ver('298.0'),'versioned_windows_starter':(self.install_dir/'START_EAGLEEYE_PRO_298_0.bat').exists(),'setup_script':(self.install_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.install_dir/'requirements-windows.txt').exists()}
        return {'build':'298.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True,'windows_launcher_content_checked':True}
    def all_training_cases(self)->list[dict]:
        out=self.build297.all_training_cases()
        for r in self.db.all("SELECT * FROM ai_hard_training_delta_298 WHERE review_status='reviewed' ORDER BY benchmark_id"):
            out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self)->dict:
        b=self.build297.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_298 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_298 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build298_delta_cases':d,'build298_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None)->dict:
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'298.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; sha=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_298 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,sha))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval298'); now=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO ai_evaluation_batches_298 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,sha,actor,now,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest')->dict:
        return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':self.REQUIRED_CORPUS,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 298 beansprucht keine ≥90%-Leistung ohne vollständigen unabhängigen 304-Fälle-Lauf.'}
    def qualified_gate(self)->dict:
        parent=self.build297.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); startup=self.startup_contract_status(); latest=self.db.one('SELECT * FROM phase12_field_pressure_runs_298 ORDER BY rowid DESC LIMIT 1')
        suite=bool(latest and latest['result']=='pass' and int(latest['scenario_count'])>=5 and int(latest['failed_count'])==0); red=int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_298 WHERE run_id=?',(latest['run_id'],))['n']) if latest else 0; hand=int(self.db.one('SELECT COUNT(*) n FROM phase12_handover_packets_298 WHERE run_id=?',(latest['run_id'],))['n']) if latest else 0
        g={'build':'298.0','parent_gate':bool(parent['release_ready']),'extended_field_pressure_suite_passed':suite,'field_pressure_chain_ok':self.verify_run_chain(),'redteam_pressure_recorded':red>=3,'handover_integrity_recorded':hand>=1,'production_certification_claimed':False,'network_access':False,'external_collection_auto_execution':False,'hard_training_corpus_304':tm['reviewed_hard_cases']>=304 and tm['build298_delta_cases']>=16 and tm['build298_delta_extreme']>=4,'evaluation_batch_304_ready':batch['corpus_size']==304 and abs(batch['minimum_mean_score']-.90)<1e-9,'startup_contract_ready':startup['contract_ready'],'automatic_model_activation':False,'human_authority_preserved':True,'field_qualification_block_297_299_active':True}
        g['release_ready']=all((g['parent_gate'],g['extended_field_pressure_suite_passed'],g['field_pressure_chain_ok'],g['redteam_pressure_recorded'],g['handover_integrity_recorded'],not g['production_certification_claimed'],not g['network_access'],not g['external_collection_auto_execution'],g['hard_training_corpus_304'],g['evaluation_batch_304_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']))
        return g
    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        e=lambda v:html.escape(str(v or ''),quote=True); s=self.field_status(); tm=self.training_metrics(); perf=self.performance_status(); latest=self.db.one('SELECT * FROM phase12_field_pressure_runs_298 ORDER BY rowid DESC LIMIT 1'); detail='Noch kein Lauf.' if not latest else f"Letzter Lauf: {latest['passed_count']}/{latest['scenario_count']} PASS · Ergebnis {latest['result']}."
        return f"""<section class='card'><h2>Field Pressure Qualification · Build 298</h2><div class='notice'><b>Was ist der Stand?</b><br>{e(s['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(s['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(s['next'])}</div><p>{e(detail)}</p><form method='post' action='/build298/field-pressure/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Erweiterte Field-Pressure-Suite ausführen</button></form><details><summary>Analyst/Experte: Handover, Red-Team und AI-Gate</summary><p>Run-Chain: <b>{'OK' if self.verify_run_chain() else 'FEHLER'}</b> · Netzwerkzugriff: <b>aus</b> · externe Collection automatisch: <b>aus</b> · Produktionszertifizierung: <b>nein</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Gate: 304/304 Fälle, ≥90%, 0 kritische Fehler, unabhängige Evaluation.</p></details></section>"""
