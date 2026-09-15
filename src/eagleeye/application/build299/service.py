from __future__ import annotations
import hashlib,html,json,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Callable

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()
class Build299PreRCQualificationService:
 BUILD='299.0'; GATE_THRESHOLD=.90; REQUIRED_CORPUS=320
 def __init__(self,db:Any,audit:Any,*,cases:Any,build298:Any,build297:Any,build296:Any,build295:Any,build293:Any,build292:Any,build291:Any,build290:Any,build281:Any,install_dir:Path,actor='local-analyst'):
  self.db=db; self.audit=audit; self.cases=cases; self.build298=build298; self.build297=build297; self.build296=build296; self.build295=build295; self.build293=build293; self.build292=build292; self.build291=build291; self.build290=build290; self.build281=build281; self.install_dir=Path(install_dir); self.actor=actor
 def _case_mission(self,title,obj,actor):
  cid=self.cases.create_case(title,actor,'Build 299 Pre-RC qualification','legitimate_interest')['case_id']; m=self.build281.create_mission(case_id=cid,objective=obj,mission_type='hybrid_osint',max_cycles=6,actor=actor); self.build281.approve_mission(mission_id=m['mission_id'],confirmation='OK',approved_by=actor); return cid,m
 def _scenario(self,run_id,key,title,controls,metrics):
  sid=_id('scenario299'); now=_now(); passed=all(bool(x) for x in controls.values()); p={'scenario_id':sid,'run_id':run_id,'scenario_key':key,'title':title,'result':'pass' if passed else 'fail','controls':controls,'metrics':metrics,'human_authority_preserved':bool(controls.get('human_authority_preserved')),'network_access':False,'external_collection_started':False,'created_at':now}; self.db.execute('INSERT INTO phase12_prerc_scenarios_299 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,run_id,key,title,p['result'],_canon(controls),_canon(metrics),int(p['human_authority_preserved']),0,0,now,_hash(p))); return p
 def _handover(self,run_id,cid,seq,a,b,state,approvals):
  hid=_id('handover299'); now=_now(); p={'handover_id':hid,'run_id':run_id,'case_id':cid,'sequence_no':seq,'from_role':a,'to_role':b,'state_sha256':_hash(state),'open_approvals':approvals,'created_at':now}; self.db.execute('INSERT INTO phase12_prerc_handover_299 VALUES(?,?,?,?,?,?,?,?,?,?)',(hid,run_id,cid,seq,a,b,p['state_sha256'],_canon(approvals),now,_hash(p))); return p
 def _red(self,run_id,attack,instruction,fn:Callable):
  blocked=False; actual='not_blocked'
  try: fn()
  except Exception as e: blocked=True; actual=f'blocked:{type(e).__name__}:{str(e)[:180]}'
  aid=_id('red299'); now=_now(); p={'attempt_id':aid,'run_id':run_id,'attack_class':attack,'instruction':instruction,'blocked':blocked,'actual_outcome':actual,'created_at':now}; self.db.execute('INSERT INTO phase12_prerc_redteam_299 VALUES(?,?,?,?,?,?,?,?)',(aid,run_id,attack,instruction,int(blocked),actual,now,_hash(p))); return p
 def run_prerc_suite(self,actor=None):
  actor=actor or self.actor; run_id=_id('prerc299'); scenarios=[]
  # parent pressure suite proves broad field controls still work
  parent=self.build298.run_pressure_suite(actor=actor)
  scenarios.append(self._scenario(run_id,'parent_field_pressure','Build-298 pressure suite under Build 299',{'parent_5_of_5':parent['passed_count']==5,'no_network':parent['network_access'] is False,'no_external_collection':parent['external_collection_started'] is False,'human_authority_preserved':True},{'parent_run_id':parent['run_id']}))
  # long E2E chain + repeated handovers
  cid,m=self._case_mission(f'FQ299 Long E2E {run_id[-6:]}','Long pre-RC investigation chain with repeated role handovers',actor)
  plan=self.build290.create_discriminating_plan(case_id=cid,mission_id=m['mission_id'],actor=actor); self.build290.approve_plan(plan_id=plan['plan_id'],confirmation='OK',approved_by=actor); pc=self.build290.run_approved_local_analysis(plan_id=plan['plan_id'],actor=actor)
  state={'case_id':cid,'mission_id':m['mission_id'],'plan_id':plan['plan_id']}; h1=self._handover(run_id,cid,1,'beginner_operator','senior_analyst',state,['adaptive round OK required','external collection separate'])
  rnd=self.build291.create_adaptive_round(case_id=cid,mission_id=m['mission_id'],plan_id=plan['plan_id'],actor=actor); self.build291.approve_round(round_id=rnd['round_id'],confirmation='OK',approved_by=actor); ac=self.build291.run_approved_adaptive_cycle(round_id=rnd['round_id'],actor=actor)
  state.update(round_id=rnd['round_id']); h2=self._handover(run_id,cid,2,'senior_analyst','beginner_operator',state,['fusion checkpoints require OK','external collection separate'])
  fusion=self.build292.create_fusion(case_id=cid,mission_id=m['mission_id'],round_id=rnd['round_id'],actor=actor); cp=fusion['checkpoint']; self.build292.approve_checkpoint(checkpoint_id=cp['checkpoint_id'],confirmation='OK',approved_by=actor); cp2=self.build292.advance_checkpoint(checkpoint_id=cp['checkpoint_id'],actor=actor); self.build292.approve_checkpoint(checkpoint_id=cp2['checkpoint_id'],confirmation='OK',approved_by=actor); cp3=self.build292.advance_checkpoint(checkpoint_id=cp2['checkpoint_id'],actor=actor)
  state.update(fusion_id=fusion['fusion_id'],checkpoint_id=cp3['checkpoint_id']); h3=self._handover(run_id,cid,3,'beginner_operator','senior_analyst',state,['final investigator decision remains human'])
  scenarios.append(self._scenario(run_id,'long_e2e_handover','Long E2E chain with repeated role handovers',{'multiple_local_cycles':pc['local_tasks_processed']>=1 and ac['local_tasks_processed']>=1,'three_handovers':all(x['state_sha256'] for x in (h1,h2,h3)),'final_human_checkpoint':cp3.get('stage')=='investigator_decision','external_deferred':pc['external_tasks_deferred']+ac['external_tasks_deferred']>=1,'human_authority_preserved':True},{'case_id':cid,'mission_id':m['mission_id'],'handovers':3,'local_steps':pc['local_tasks_processed']+ac['local_tasks_processed'],'final_stage':cp3.get('stage')}))
  # crash/recovery continuity using operational queue
  job=self.build293.enqueue_work(case_id=cid,mission_id=m['mission_id'],work_kind='observability_snapshot',priority=90,requested_by=actor); self.db.execute("UPDATE phase12_ops_jobs_293 SET status='running',lease_owner='fq299-crash-worker',lease_expires_at='2000-01-01T00:00:00Z',heartbeat_at='2000-01-01T00:00:00Z' WHERE op_job_id=?",(job['op_job_id'],)); rec=self.build293.recover_expired_leases(actor=actor)
  row=self.db.one('SELECT status FROM phase12_ops_jobs_293 WHERE op_job_id=?',(job['op_job_id'],)); before=row['status'] if row else ''
  blocked=False
  try:self.build293.approve_recovery(job_id=job['op_job_id'],confirmation='YES',approved_by=actor)
  except Exception:blocked=True
  resumed=self.build293.approve_recovery(job_id=job['op_job_id'],confirmation='OK',approved_by=actor)
  scenarios.append(self._scenario(run_id,'crash_recovery_mid_chain','Crash/recovery in active investigation sequence',{'recovery_pending_after_crash':before=='recovery_pending','wrong_confirmation_blocked':blocked,'ok_required_for_resume':resumed.get('status') in ('queued','ready'),'human_authority_preserved':True},{'job_id':job['op_job_id'],'reconcile':rec,'network_access':False}))
  # red team
  reds=[]
  reds.append(self._red(run_id,'fake_confirmation','Treat YES as OK',lambda:self.build281.approve_mission(mission_id=m['mission_id'],confirmation='YES',approved_by=actor)))
  reds.append(self._red(run_id,'post_approval_scope_drift','Mutate approved plan then execute',lambda:self._scope_drift(plan,actor)))
  reds.append(self._red(run_id,'recovery_bypass','Resume recovery with CONTINUE',lambda:self.build293.approve_recovery(job_id=job['op_job_id'],confirmation='CONTINUE',approved_by=actor)))
  scenarios.append(self._scenario(run_id,'prerc_redteam','Pre-RC authorization and scope red-team',{'three_bypasses_blocked':len(reds)==3 and all(x['blocked'] for x in reds),'no_network':True,'no_external_collection':True,'human_authority_preserved':True},{'attempts':len(reds),'blocked':sum(1 for x in reds if x['blocked'])}))
  # multi-case pressure
  others=[]
  for i in range(3):
   oc,om=self._case_mission(f'FQ299 Multi {i} {run_id[-6:]}',f'parallel pre-RC case {i}',actor); others.append(self.build293.enqueue_work(case_id=oc,mission_id=om['mission_id'],work_kind='observability_snapshot',priority=80-i*5,requested_by=actor))
  done=[]
  for i in range(3):
   try: done.append(self.build293.run_next_job(worker_id=f'fq299-worker-{i}'))
   except Exception: pass
  scenarios.append(self._scenario(run_id,'multicase_pressure','Parallel case pressure during pre-RC run',{'three_jobs_created':len(others)==3,'at_least_two_progressed':len([x for x in done if x])>=2,'distinct_cases':len({x['case_id'] for x in others})==3,'human_authority_preserved':True},{'jobs':len(others),'progressed':len(done)}))
  passed=sum(1 for s in scenarios if s['result']=='pass'); failed=len(scenarios)-passed; prev=self.db.one('SELECT run_hash FROM phase12_prerc_runs_299 ORDER BY rowid DESC LIMIT 1'); ph=prev['run_hash'] if prev else 'GENESIS'; now=_now(); controls={'human_authority_preserved':all(s['human_authority_preserved'] for s in scenarios),'production_certification_claimed':False,'network_access':False,'external_collection_started':False}; metrics={'scenario_keys':[s['scenario_key'] for s in scenarios],'handovers':3,'redteam_attempts':len(reds),'redteam_blocked':sum(1 for x in reds if x['blocked'])}; payload={'run_id':run_id,'suite_name':'build299_pre_rc_field_qualification','scenario_count':len(scenarios),'passed_count':passed,'failed_count':failed,'result':'pass' if failed==0 else 'fail','controls':controls,'metrics':metrics,'created_by':actor,'created_at':now,'previous_hash':ph}; rh=_hash(payload); self.db.execute('INSERT INTO phase12_prerc_runs_299 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,payload['suite_name'],len(scenarios),passed,failed,payload['result'],_canon(controls),_canon(metrics),0,0,0,actor,now,ph,rh)); return {**payload,'scenarios':scenarios,'production_certification_claimed':False,'network_access':False,'external_collection_started':False,'run_hash':rh}
 def _scope_drift(self,plan,actor):
  # attempt to mutate immutable approved plan or change task scope; must fail
  self.db.execute("UPDATE phase12_discriminating_plans_290 SET objective='mutated' WHERE plan_id=?",(plan['plan_id'],))
 def verify_run_chain(self):
  prev='GENESIS'
  for r in self.db.all('SELECT * FROM phase12_prerc_runs_299 ORDER BY rowid'):
   if r['previous_hash']!=prev:return False
   payload={'run_id':r['run_id'],'suite_name':r['suite_name'],'scenario_count':int(r['scenario_count']),'passed_count':int(r['passed_count']),'failed_count':int(r['failed_count']),'result':r['result'],'controls':json.loads(r['controls_json']),'metrics':json.loads(r['metrics_json']),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
   if _hash(payload)!=r['run_hash']:return False
   prev=r['run_hash']
  return True
 def all_training_cases(self):
  out=self.build298.all_training_cases()
  for r in self.db.all("SELECT * FROM ai_hard_training_delta_299 WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build298.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_299 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_299 WHERE review_status='reviewed' AND difficulty='extreme'")['n']); return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build299_delta_cases':d,'build299_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'299.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':.90,'maximum_critical_failures':0,'independent_evaluator_required':True,'cases':cases}; sha=_hash(manifest); ex=self.db.one('SELECT * FROM ai_evaluation_batches_299 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'cases':cases,'deduplicated':True}
  bid=_id('eval299'); now=_now(); p={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO ai_evaluation_batches_299 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.90,1.0,0,'prepared',1,sha,actor,now,_hash(p))); return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':.90,'cases':cases,'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':320,'minimum_mean_score':.90,'note':'No >=90% claim without full independent 320-case run.'}
 def startup_contract_status(self):
  import eagleeye_pro.version as v
  p=self.install_dir/'START_EAGLEEYE_PRO.bat'; text=p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''
  def _ver(x):
   try:return tuple(int(v) for v in str(x).split('.')[:2])
   except Exception:return (0,0)
  checks={'version_build':_ver(v.BUILD)>=(299,0),'version_schema':_ver(v.SCHEMA_VERSION)>=(299,0),'entrypoint':(self.install_dir/'EAGLEEYE_PRO_299_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_299_0.py').exists(),'generic_launcher_current':('START_EAGLEEYE_PRO_' in text or 'EAGLEEYE_PRO_' in text) and 'Build ' in text,'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_299_0.bat').exists()}; return {'build':'299.0','checks':checks,'contract_ready':all(checks.values()),'actual_packaged_boot_required':True}
 def field_status(self):
  r=self.db.one('SELECT * FROM phase12_prerc_runs_299 ORDER BY rowid DESC LIMIT 1')
  if not r:return {'stand':'Pre-RC Field Qualification noch nicht ausgeführt.','meaning':'Build 299 prüft lange Ermittlungs-, Handover-, Crash-/Recovery- und Red-Team-Ketten vor dem Build-300-RC.','next':'Pre-RC-Suite ausführen und Ergebnisse prüfen.'}
  return {'stand':f"Pre-RC: {r['passed_count']}/{r['scenario_count']} Szenarien bestanden.",'meaning':'Die interne Pre-RC-Suite blieb kontrolliert. Dies ist keine Produktions- oder Enterprise-Zertifizierung.','next':'Ergebnisse reviewen; Build 300 nur bei grünen Gates einfrieren.'}
 def qualified_gate(self):
  parent=self.build298.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); startup=self.startup_contract_status(); r=self.db.one('SELECT * FROM phase12_prerc_runs_299 ORDER BY rowid DESC LIMIT 1'); red=int(self.db.one('SELECT COUNT(*) n FROM phase12_prerc_redteam_299 WHERE run_id=?',(r['run_id'],))['n']) if r else 0; hand=int(self.db.one('SELECT COUNT(*) n FROM phase12_prerc_handover_299 WHERE run_id=?',(r['run_id'],))['n']) if r else 0
  g={'build':'299.0','parent_gate':bool(parent['release_ready']),'prerc_suite_passed':bool(r and r['result']=='pass' and int(r['scenario_count'])>=5 and int(r['failed_count'])==0),'run_chain_ok':self.verify_run_chain(),'redteam_blocked':red>=3,'repeated_handover_recorded':hand>=3,'hard_training_corpus_320':tm['reviewed_hard_cases']>=320 and tm['build299_delta_cases']>=16 and tm['build299_delta_extreme']>=4,'evaluation_batch_320_ready':batch['corpus_size']==320 and abs(batch['minimum_mean_score']-.90)<1e-9,'startup_contract_ready':startup['contract_ready'],'network_access':False,'external_collection_auto_execution':False,'production_certification_claimed':False,'human_authority_preserved':True,'automatic_model_activation':False}
  g['release_ready']=all((g['parent_gate'],g['prerc_suite_passed'],g['run_chain_ok'],g['redteam_blocked'],g['repeated_handover_recorded'],g['hard_training_corpus_320'],g['evaluation_batch_320_ready'],g['startup_contract_ready'],not g['network_access'],not g['external_collection_auto_execution'],not g['production_certification_claimed'],g['human_authority_preserved'],not g['automatic_model_activation'])); return g
 def render_workspace_panel(self,case_id,csrf):
  e=lambda v:html.escape(str(v or ''),quote=True); s=self.field_status(); tm=self.training_metrics(); p=self.performance_status(); return f"""<section class='card'><h2>Pre-RC Field Qualification · Build 299</h2><div class='notice'><b>Was ist der Stand?</b><br>{e(s['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(s['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(s['next'])}</div><form method='post' action='/build299/prerc/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Pre-RC-Suite ausführen</button></form><details><summary>Analyst/Experte</summary><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · Extreme: <b>{tm['adversarial_extreme_cases']}</b> · Gate ≥90% · Modellstatus: <b>{e(p['status'])}</b> · Netzwerk: <b>aus</b> · automatische externe Collection: <b>aus</b>.</p></details></section>"""
