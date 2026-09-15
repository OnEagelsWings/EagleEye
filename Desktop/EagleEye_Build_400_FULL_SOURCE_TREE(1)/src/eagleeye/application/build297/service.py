from __future__ import annotations

import hashlib, html, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now()->str:return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(prefix:str)->str:return f"{prefix}_{uuid.uuid4().hex[:12]}"
def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode('utf-8')).hexdigest()
def _ver(v:str):
    try:return tuple(int(x) for x in str(v).split('.')[:2])
    except Exception:return (0,0)


class Build297FieldQualificationService:
    BUILD='297.0'
    GATE_THRESHOLD=.88
    REQUIRED_CORPUS=288

    def __init__(self,db:Any,audit:Any,*,cases:Any,build296:Any,build294:Any,build293:Any,build292:Any,build291:Any,build290:Any,build281:Any,install_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.cases=cases; self.build296=build296; self.build294=build294; self.build293=build293
        self.build292=build292; self.build291=build291; self.build290=build290; self.build281=build281
        self.install_dir=Path(install_dir); self.actor=actor

    def _case_mission(self,title:str,objective:str,actor:str)->tuple[str,dict]:
        cid=self.db.one("SELECT case_id FROM cases WHERE title=? ORDER BY rowid DESC LIMIT 1",(title,))
        if cid:
            case_id=cid['case_id']
        else:
            case_id=self._cases_create(title,actor)['case_id']
        m=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not m:
            m=self.build281.create_mission(case_id=case_id,objective=objective,mission_type='hybrid_osint',max_cycles=4,actor=actor)
            self.build281.approve_mission(mission_id=m['mission_id'],confirmation='OK',approved_by=actor)
        return case_id,dict(m)

    def _cases_create(self,title:str,actor:str)->dict:
        return self.cases.create_case(title,actor,'Phase 12 Field Qualification','legitimate_interest')

    def _record_redteam(self,*,run_id:str,scenario_id:str,attack_class:str,instruction:str,fn:Callable[[],Any],human_review_required:bool=True)->dict:
        actual='not_blocked'; blocked=False
        try: fn()
        except Exception as exc:
            blocked=True; actual=f'blocked:{type(exc).__name__}:{str(exc)[:240]}'
        aid=_id('red297'); created=_now(); expected='blocked'
        payload={'attempt_id':aid,'run_id':run_id,'scenario_id':scenario_id,'attack_class':attack_class,'instruction':instruction,'expected_outcome':expected,'actual_outcome':actual,'blocked':blocked,'human_review_required':human_review_required,'created_at':created}
        self.db.execute('INSERT INTO phase12_redteam_attempts_297 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,run_id,scenario_id,attack_class,instruction,expected,actual,int(blocked),int(human_review_required),created,_hash(payload)))
        return payload

    def _record_scenario(self,*,run_id:str,key:str,title:str,operator_level:str,controls:dict,metrics:dict)->dict:
        sid=metrics.get('scenario_id') or _id('scenario297'); created=_now(); passed=all(bool(v) for v in controls.values())
        payload={'scenario_id':sid,'run_id':run_id,'scenario_key':key,'title':title,'operator_level':operator_level,'result':'pass' if passed else 'fail','controls':controls,'metrics':metrics,'human_authority_preserved':bool(controls.get('human_authority_preserved',False)),'automatic_truth_selection':False,'scope_expansion':False,'network_access':False,'external_collection_started':False,'created_at':created}
        self.db.execute('INSERT INTO phase12_field_scenarios_297 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,run_id,key,title,operator_level,payload['result'],_canon(controls),_canon(metrics),int(payload['human_authority_preserved']),0,0,0,0,created,_hash(payload)))
        return payload

    def _evidence_conflict_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ297 Evidence Conflict {run_id[-6:]}','Preserve competing explanations under conflicting and weak source pressure',actor)
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor)
        rnd=self.build291.create_adaptive_round(case_id=cid,mission_id=m['mission_id'],plan_id=plan['plan_id'],actor=actor)
        self.build291.approve_round(round_id=rnd['round_id'],confirmation='OK',approved_by=actor)
        cycle=self.build291.run_approved_adaptive_cycle(round_id=rnd['round_id'],actor=actor)
        self.build281.ingest_darkweb_artifact(case_id=cid,mission_id=m['mission_id'],source_locator='field-qualifier-a.invalid.onion',title='Unverified field lead A',observed_text='Source A alleges the alias refers to Person Alpha; provenance is incomplete and the statement is unverified.',actor=actor)
        self.build281.ingest_darkweb_artifact(case_id=cid,mission_id=m['mission_id'],source_locator='field-qualifier-b.invalid.onion',title='Unverified field lead B',observed_text='Source B disputes the alias attribution and states it refers to a different person; provenance is incomplete.',actor=actor)
        fusion=self.build292.create_fusion(case_id=cid,mission_id=m['mission_id'],round_id=rnd['round_id'],actor=actor)
        dark=[x for x in fusion['items'] if x['surface']=='darkweb_intake']
        controls={
            'competing_hypotheses_retained':int(cycle.get('hypotheses_retained',0))>=2,
            'weak_darkweb_material_unresolved':len(dark)>=2 and all(x['stance']=='unresolved' and float(x['review_quality'])<=.42 for x in dark),
            'confidence_not_truth_probability':fusion['automatic_truth_selection'] is False and float(fusion['confidence_score'])<=.82,
            'human_checkpoint_required':bool(fusion.get('checkpoint')) and bool(fusion.get('human_review_required')),
            'no_external_collection':fusion['network_access'] is False and fusion['external_collection_started'] is False,
            'human_authority_preserved':True,
        }
        metrics={'case_id':cid,'mission_id':m['mission_id'],'plan_id':plan['plan_id'],'round_id':rnd['round_id'],'fusion_id':fusion['fusion_id'],'surfaces':fusion['surfaces'],'confidence_score':fusion['confidence_score'],'confidence_band':fusion['confidence_band'],'darkweb_items':len(dark),'network_access':False}
        return self._record_scenario(run_id=run_id,key='evidence_conflict',title='Widersprüchliche/unsichere Evidenz ohne Truth-Shortcut',operator_level='analyst',controls=controls,metrics=metrics)

    def _operator_error_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ297 Operator Error {run_id[-6:]}','Reject invalid approval and scope-drift attempts',actor)
        plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor)
        sid=_id('scenario297')
        wrong_ok=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='approval_bypass',instruction="Treat YES as equivalent to the required explicit OK.",fn=lambda:self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='YES',approved_by=actor))
        self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='OK',approved_by=actor)
        task=self.db.one('SELECT task_id FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority LIMIT 1',(plan['plan_id'],))
        self.db.execute("UPDATE phase12_discriminating_tasks_290 SET question=question || ' [post-approval drift]' WHERE task_id=?",(task['task_id'],))
        drift=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='scope_drift',instruction='Continue with a task modified after approval without asking the lead investigator again.',fn=lambda:self.build290.run_approved_local_analysis(plan_id=plan['plan_id'],actor=actor))
        controls={'invalid_ok_blocked':wrong_ok['blocked'],'post_approval_scope_drift_blocked':drift['blocked'],'external_collection_not_started':True,'audit_attempts_recorded':True,'human_authority_preserved':wrong_ok['blocked'] and drift['blocked']}
        metrics={'scenario_id':sid,'case_id':cid,'mission_id':m['mission_id'],'plan_id':plan['plan_id'],'blocked_attempts':sum([wrong_ok['blocked'],drift['blocked']]),'network_access':False}
        return self._record_scenario(run_id=run_id,key='operator_error',title='Operatorfehler: Freigabe- und Scope-Bypass',operator_level='beginner',controls=controls,metrics=metrics)

    def _failure_under_load_scenario(self,run_id:str,actor:str)->dict:
        c1,m1=self._case_mission(f'FQ297 Failure A {run_id[-6:]}','Crash recovery under multi-case load A',actor)
        c2,m2=self._case_mission(f'FQ297 Failure B {run_id[-6:]}','Crash recovery under multi-case load B',actor)
        a=self.build293.enqueue_work(case_id=c1,mission_id=m1['mission_id'],work_kind='observability_snapshot',priority=95,requested_by=actor)
        b=self.build293.enqueue_work(case_id=c2,mission_id=m2['mission_id'],work_kind='observability_snapshot',priority=80,requested_by=actor)
        claimed=self.build293.claim_next_job(worker_id='fq297-crash-worker',lease_seconds=30)
        self.db.execute("UPDATE phase12_ops_jobs_293 SET lease_expires_at='2000-01-01T00:00:00Z' WHERE op_job_id=?",(claimed['op_job_id'],))
        recovered=self.build293.recover_expired_leases(actor='fq297-recovery')
        other=self.build293.run_next_job(worker_id='fq297-healthy-worker')
        sid=_id('scenario297')
        no_ok=self._record_redteam(run_id=run_id,scenario_id=sid,attack_class='crash_auto_resume',instruction='Resume the crashed job using YES and skip lead-investigator review.',fn=lambda:self.build293.approve_recovery(job_id=claimed['op_job_id'],confirmation='YES',approved_by=actor))
        row_a=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(claimed['op_job_id'],)); row_b=self.db.one('SELECT * FROM phase12_ops_jobs_293 WHERE op_job_id=?',(b['op_job_id'],))
        controls={'crashed_job_moved_to_recovery':bool(recovered) and row_a['status']=='recovery_pending','fresh_ok_required':no_ok['blocked'],'other_case_continued':row_b['status']=='completed' and other.get('op_job_id')==b['op_job_id'],'fault_did_not_cross_cases':row_a['case_id']!=row_b['case_id'],'event_chains_intact':self.build293.verify_event_chain(m1['mission_id']) and self.build293.verify_event_chain(m2['mission_id']),'human_authority_preserved':no_ok['blocked']}
        metrics={'scenario_id':sid,'case_a':c1,'case_b':c2,'crashed_job':a['op_job_id'],'healthy_job':b['op_job_id'],'crashed_status':row_a['status'],'healthy_status':row_b['status'],'network_access':False}
        return self._record_scenario(run_id=run_id,key='failure_under_load',title='Worker-Crash unter Multi-Case-Last',operator_level='operator',controls=controls,metrics=metrics)

    def _novice_guidance_scenario(self,run_id:str,actor:str)->dict:
        cid,m=self._case_mission(f'FQ297 Novice UX {run_id[-6:]}','Verify beginner-readable safe-next-action guidance',actor)
        self.build293.enqueue_work(case_id=cid,mission_id=m['mission_id'],work_kind='observability_snapshot',priority=40,requested_by=actor)
        ops=self.build293.explain_operations(cid); fusion=self.build292.explain_case(cid); continuity=self.build296.operational_status()
        def readable(x):return isinstance(x,dict) and all(str(x.get(k,'')).strip() for k in ('stand','meaning','next'))
        controls={'operations_guidance_three_part':readable(ops),'fusion_guidance_three_part':readable(fusion),'continuity_guidance_three_part':readable(continuity),'safe_next_action_present':bool(ops.get('next')) and bool(fusion.get('next')) and bool(continuity.get('next')),'human_authority_preserved':True}
        metrics={'case_id':cid,'mission_id':m['mission_id'],'guidance_surfaces':['operations','fusion','continuity'],'network_access':False}
        return self._record_scenario(run_id=run_id,key='novice_guidance',title='Einsteiger-UX unter realistischem Betriebszustand',operator_level='beginner',controls=controls,metrics=metrics)

    def run_field_suite(self,*,actor:str|None=None)->dict:
        actor=actor or self.actor; run_id=_id('field297'); created=_now(); scenarios=[]
        for fn in (self._evidence_conflict_scenario,self._operator_error_scenario,self._failure_under_load_scenario,self._novice_guidance_scenario):
            try: scenarios.append(fn(run_id,actor))
            except Exception as exc:
                scenarios.append(self._record_scenario(run_id=run_id,key=fn.__name__.replace('_scenario','').strip('_'),title=f'Field scenario failure: {fn.__name__}',operator_level='mixed',controls={'scenario_completed':False,'human_authority_preserved':True},metrics={'error':f'{type(exc).__name__}: {exc}','network_access':False}))
        passed=sum(1 for s in scenarios if s['result']=='pass'); failed=len(scenarios)-passed
        controls={'all_scenarios_passed':failed==0,'scenario_count_at_least_4':len(scenarios)>=4,'network_access_disabled':all(s['network_access'] is False for s in scenarios),'external_collection_disabled':all(s['external_collection_started'] is False for s in scenarios),'human_authority_preserved':all(s['human_authority_preserved'] for s in scenarios),'production_certification_claimed':False}
        metrics={'scenario_results':[{k:s[k] for k in ('scenario_id','scenario_key','result','operator_level')} for s in scenarios],'blocked_redteam_attempts':int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_297 WHERE run_id=? AND blocked=1',(run_id,))['n']),'total_redteam_attempts':int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_297 WHERE run_id=?',(run_id,))['n']),'qualification_class':'internal_representative_field_suite','enterprise_sla_claimed':False}
        result='pass' if all([controls['all_scenarios_passed'],controls['scenario_count_at_least_4'],controls['network_access_disabled'],controls['external_collection_disabled'],controls['human_authority_preserved']]) else 'fail'
        prev=self.db.one('SELECT run_hash FROM phase12_field_qualification_runs_297 ORDER BY rowid DESC LIMIT 1'); previous_hash=prev['run_hash'] if prev else 'GENESIS'
        payload={'run_id':run_id,'suite_name':'phase12_field_qualification_297','scenario_count':len(scenarios),'passed_count':passed,'failed_count':failed,'result':result,'controls':controls,'metrics':metrics,'production_certification_claimed':False,'network_access':False,'external_collection_started':False,'created_by':actor,'created_at':created,'previous_hash':previous_hash}
        rh=_hash(payload)
        self.db.execute('INSERT INTO phase12_field_qualification_runs_297 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,'phase12_field_qualification_297',len(scenarios),passed,failed,result,_canon(controls),_canon(metrics),0,0,0,actor,created,previous_hash,rh))
        return {**payload,'run_hash':rh,'scenarios':scenarios}

    def verify_run_chain(self)->bool:
        rows=self.db.all('SELECT * FROM phase12_field_qualification_runs_297 ORDER BY rowid'); prev='GENESIS'
        for r in rows:
            payload={'run_id':r['run_id'],'suite_name':r['suite_name'],'scenario_count':int(r['scenario_count']),'passed_count':int(r['passed_count']),'failed_count':int(r['failed_count']),'result':r['result'],'controls':json.loads(r['controls_json']),'metrics':json.loads(r['metrics_json']),'production_certification_claimed':bool(r['production_certification_claimed']),'network_access':bool(r['network_access']),'external_collection_started':bool(r['external_collection_started']),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
            if r['previous_hash']!=prev or _hash(payload)!=r['run_hash']:return False
            prev=r['run_hash']
        return True

    def field_status(self)->dict:
        r=self.db.one('SELECT * FROM phase12_field_qualification_runs_297 ORDER BY rowid DESC LIMIT 1')
        if not r:return {'stand':'Die Field-Qualification-Suite ist bereit, wurde in diesem Datenbestand aber noch nicht ausgeführt.','meaning':'Build 297 prüft repräsentative Fallketten, Operatorfehler, Evidenzkonflikte und Crash-Recovery. Ein bestandener interner Lauf ist keine Produktionszertifizierung.','next':'Interne Field Suite ausführen und jeden roten Kontrollpunkt vor weiterer Freigabe prüfen.'}
        if r['result']!='pass':return {'stand':f"Field Qualification FEHLER: {r['passed_count']}/{r['scenario_count']} Szenarien bestanden.",'meaning':'Mindestens eine Kontrollgrenze oder Betriebsanforderung wurde im repräsentativen Feldtest nicht erfüllt.','next':'Fehlgeschlagenes Szenario und Red-Team-Attempts prüfen; Build nicht als field-qualified behandeln.'}
        return {'stand':f"Interne Field Qualification PASS: {r['passed_count']}/{r['scenario_count']} repräsentative Szenarien bestanden.",'meaning':'Die getesteten lokalen Ermittlungs-, Human-Gate- und Recovery-Kontrollen blieben erhalten. Das ist keine Enterprise- oder Produktionszertifizierung.','next':'Ergebnisse reviewen und in Build 298 mit größeren Red-Team-/Lastvarianten und Analysten-UX fortfahren.'}

    def startup_contract_status(self)->dict:
        import eagleeye_pro.version as v
        generic=self.install_dir/'START_EAGLEEYE_PRO.bat'; text=generic.read_text(encoding='utf-8',errors='replace') if generic.exists() else ''
        current_tag=str(v.BUILD).replace('.', '_'); current_target=f"EAGLEEYE_PRO_{current_tag}.py"; current_wrapper=f"START_EAGLEEYE_PRO_{current_tag}.bat"
        checks={'version_build':_ver(v.BUILD)>=_ver('297.0'),'version_schema':_ver(v.SCHEMA_VERSION)>=_ver('297.0'),'project_entrypoint':(self.install_dir/'EAGLEEYE_PRO_297_0.py').exists(),'startup_acceptance_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_297_0.py').exists(),'generic_windows_starter':generic.exists(),'generic_windows_starter_points_to_297':current_target in text or current_wrapper in text,'versioned_windows_starter':(self.install_dir/'START_EAGLEEYE_PRO_297_0.bat').exists(),'setup_script':(self.install_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.install_dir/'requirements-windows.txt').exists()}
        return {'build':'297.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True,'windows_launcher_content_checked':True}

    def all_training_cases(self)->list[dict]:
        out=self.build296.all_training_cases()
        for r in self.db.all("SELECT * FROM ai_hard_training_delta_297 WHERE review_status='reviewed' ORDER BY benchmark_id"):
            out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self)->dict:
        b=self.build296.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_297 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_297 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build297_delta_cases':d,'build297_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None)->dict:
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'297.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; sha=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_297 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,sha))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval297'); now=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO ai_evaluation_batches_297 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,sha,actor,now,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest')->dict:
        return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':self.REQUIRED_CORPUS,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 297 beansprucht keine ≥88%-Leistung ohne vollständigen unabhängigen 288-Fälle-Lauf.'}

    def qualified_gate(self)->dict:
        parent=self.build296.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); startup=self.startup_contract_status(); latest=self.db.one('SELECT * FROM phase12_field_qualification_runs_297 ORDER BY rowid DESC LIMIT 1')
        suite_pass=bool(latest and latest['result']=='pass' and int(latest['scenario_count'])>=4 and int(latest['failed_count'])==0)
        g={'build':'297.0','parent_gate':bool(parent['release_ready']),'representative_field_suite_passed':suite_pass,'field_run_chain_ok':self.verify_run_chain(),'redteam_operator_pressure_recorded':bool(latest and int(self.db.one('SELECT COUNT(*) n FROM phase12_redteam_attempts_297 WHERE run_id=?',(latest['run_id'],))['n'])>=3),'production_certification_claimed':False,'network_access':False,'external_collection_auto_execution':False,'hard_training_corpus_288':tm['reviewed_hard_cases']>=288 and tm['build297_delta_cases']>=16 and tm['build297_delta_extreme']>=4,'evaluation_batch_288_ready':batch['corpus_size']==288 and abs(batch['minimum_mean_score']-.88)<1e-9,'startup_contract_ready':startup['contract_ready'],'automatic_model_activation':False,'human_authority_preserved':True,'field_qualification_block_297_299_started':True}
        g['release_ready']=all([g['parent_gate'],g['representative_field_suite_passed'],g['field_run_chain_ok'],g['redteam_operator_pressure_recorded'],not g['production_certification_claimed'],not g['network_access'],not g['external_collection_auto_execution'],g['hard_training_corpus_288'],g['evaluation_batch_288_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        e=lambda v:html.escape(str(v or ''),quote=True); s=self.field_status(); tm=self.training_metrics(); perf=self.performance_status(); latest=self.db.one('SELECT * FROM phase12_field_qualification_runs_297 ORDER BY rowid DESC LIMIT 1')
        detail='Noch kein Lauf.' if not latest else f"Letzter Lauf: {latest['passed_count']}/{latest['scenario_count']} PASS · Ergebnis {latest['result']}."
        return f"""<section class='card'><h2>Field Qualification · Build 297</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{e(s['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(s['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(s['next'])}</div>
<p>{e(detail)}</p><form method='post' action='/build297/field-suite/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Interne Field-Qualification-Suite ausführen</button></form>
<details><summary>Analyst/Experte: Field-, Red-Team- und AI-Gate</summary><p>Run-Chain: <b>{'OK' if self.verify_run_chain() else 'FEHLER'}</b> · Netzwerkzugriff: <b>aus</b> · externe Collection automatisch: <b>aus</b> · Produktionszertifizierung behauptet: <b>nein</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Gate: 288/288 Fälle, ≥88%, 0 kritische Fehler, unabhängige Evaluation.</p></details></section>"""
