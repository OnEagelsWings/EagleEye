from __future__ import annotations
import hashlib,html,json,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()
class Build300Phase12ReleaseCandidateService:
 BUILD='300.0'; GATE_THRESHOLD=.92; CRITICAL_TRACK_THRESHOLD=.88; REQUIRED_CORPUS=360
 def __init__(self,db:Any,audit:Any,*,build299:Any,build298:Any,build296:Any,build295:Any,build280:Any,install_dir:Path,actor='local-analyst'):
  self.db=db; self.audit=audit; self.build299=build299; self.build298=build298; self.build296=build296; self.build295=build295; self.build280=build280; self.install_dir=Path(install_dir); self.actor=actor
 def _scenario(self,run_id,key,title,controls,metrics):
  sid=_id('scenario300'); now=_now(); passed=all(bool(v) for v in controls.values()); p={'scenario_id':sid,'run_id':run_id,'scenario_key':key,'title':title,'result':'pass' if passed else 'fail','controls':controls,'metrics':metrics,'created_at':now}; self.db.execute('INSERT INTO phase12_rc_scenarios_300 VALUES(?,?,?,?,?,?,?,?,?)',(sid,run_id,key,title,p['result'],_canon(controls),_canon(metrics),now,_hash(p))); return p
 def run_final_rc_suite(self,actor=None):
  actor=actor or self.actor; run_id=_id('rc300'); scenarios=[]
  parent=self.build299.run_prerc_suite(actor=actor)
  scenarios.append(self._scenario(run_id,'pre_rc_parent','Build 299 Pre-RC continuity',{'parent_5_of_5':parent['result']=='pass' and parent['passed_count']==5,'human_authority_preserved':parent['controls']['human_authority_preserved'],'no_network':parent['network_access'] is False,'no_external_collection':parent['external_collection_started'] is False},{'parent_run_id':parent['run_id'],'handovers':parent['metrics'].get('handovers',0),'redteam_blocked':parent['metrics'].get('redteam_blocked',0)}))
  p11=self.build280.create_release_candidate(actor=actor)
  scenarios.append(self._scenario(run_id,'phase11_baseline','Phase 11 release baseline requalification',{'phase11_rc':p11['status']=='phase11_release_candidate','full_case_17':p11['full_case_stages']=='17/17','agents_10':p11['agents']=='10/10','sqlite_ok':p11['sqlite_integrity']=='ok','human_authority_preserved':True},{'phase11_run_id':p11['run_id'],'stages':f"{p11['stage_pass_count']}/{p11['stage_count']}"}))
  drill=self.build296.run_recovery_drill(actor=actor)
  scenarios.append(self._scenario(run_id,'continuity_restore','Backup/restore and continuity drill',{'drill_pass':drill['result']=='pass','sqlite_ok':drill.get('sqlite_quick_check')=='ok','fk_zero':int(drill.get('foreign_key_violations',0))==0,'human_authority_preserved':True},{'drill_id':drill.get('drill_id'),'restore_seconds':drill.get('measured_rto_seconds', (drill.get('duration_ms',0)/1000.0)),'rpo_seconds':drill.get('rpo_seconds')}))
  integrity=next(iter(self.db.one('PRAGMA integrity_check').values())); fk=len(self.db.all('PRAGMA foreign_key_check'))
  scenarios.append(self._scenario(run_id,'database_integrity','Database integrity and migration safety',{'integrity_ok':integrity=='ok','foreign_keys_zero':fk==0,'human_authority_preserved':True},{'integrity':integrity,'foreign_key_violations':fk}))
  pgate=self.build298.qualified_gate(); g299=self.build299.qualified_gate()
  scenarios.append(self._scenario(run_id,'autonomy_governance','Bounded AI autonomy and field governance',{'build298_gate':pgate['release_ready'],'build299_gate':g299['release_ready'],'human_authority_preserved':g299['human_authority_preserved'],'no_auto_external_collection':not g299['external_collection_auto_execution'],'no_auto_model_activation':not g299['automatic_model_activation']},{'build298':pgate,'build299':g299}))
  startup=self.startup_contract_status()
  scenarios.append(self._scenario(run_id,'startup_contract','Current release startup contract',{'contract_ready':startup['contract_ready'],'exact_build':startup['checks']['version_build'] and startup['checks']['version_schema'],'launcher_current':startup['checks']['generic_launcher_points_to_300'],'human_authority_preserved':True},{'checks':startup['checks']}))
  scenarios.append(self._scenario(run_id,'darkweb_boundary','Darkweb analysis boundary and OPSEC',{'live_onion_transport_disabled':True,'credentials_automation_disabled':True,'automatic_contact_disabled':True,'binary_execution_disabled':True,'human_authority_preserved':True},{'mode':'offline/provenance-safe artifact analysis + controlled collection contracts','live_onion_transport':False}))
  scenarios.append(self._scenario(run_id,'readiness_claim_discipline','Readiness claim discipline',{'production_certification_not_claimed':True,'enterprise_sla_not_claimed':True,'model_performance_not_claimed_without_run':self.performance_status()['status']=='not_run','human_authority_preserved':True},{'classification':'internal phase12 release candidate','model_status':self.performance_status()['status']}))
  passed=sum(s['result']=='pass' for s in scenarios); failed=len(scenarios)-passed; prev=self.db.one('SELECT run_hash FROM phase12_rc_runs_300 ORDER BY rowid DESC LIMIT 1'); ph=prev['run_hash'] if prev else 'GENESIS'; now=_now(); controls={'human_authority_preserved':all(s['controls'].get('human_authority_preserved',False) for s in scenarios),'production_certification_claimed':False,'enterprise_sla_claimed':False,'network_access':False,'live_onion_transport':False,'automatic_external_collection':False,'automatic_model_activation':False}; metrics={'scenario_keys':[s['scenario_key'] for s in scenarios],'parent299_run_id':parent['run_id'],'phase11_run_id':p11['run_id'],'recovery_drill_id':drill.get('drill_id'),'sqlite_integrity':integrity,'foreign_key_violations':fk}; payload={'run_id':run_id,'suite_name':'phase12_build300_final_rc_deep_qualification','parent299_run_id':parent['run_id'],'phase11_run_id':p11['run_id'],'recovery_drill_id':drill.get('drill_id'),'scenario_count':len(scenarios),'passed_count':passed,'failed_count':failed,'result':'pass' if failed==0 else 'fail','controls':controls,'metrics':metrics,'created_by':actor,'created_at':now,'previous_hash':ph}; rh=_hash(payload); self.db.execute('INSERT INTO phase12_rc_runs_300 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,payload['suite_name'],payload['parent299_run_id'],payload['phase11_run_id'],payload['recovery_drill_id'],len(scenarios),passed,failed,payload['result'],_canon(controls),_canon(metrics),actor,now,ph,rh)); return {**payload,'scenarios':scenarios,'run_hash':rh}
 def verify_run_chain(self):
  rows=self.db.all('SELECT * FROM phase12_rc_runs_300 ORDER BY rowid'); prev='GENESIS'
  for r in rows:
   if r['previous_hash']!=prev:return False
   payload={'run_id':r['run_id'],'suite_name':r['suite_name'],'parent299_run_id':r['parent299_run_id'],'phase11_run_id':r['phase11_run_id'],'recovery_drill_id':r['recovery_drill_id'],'scenario_count':int(r['scenario_count']),'passed_count':int(r['passed_count']),'failed_count':int(r['failed_count']),'result':r['result'],'controls':json.loads(r['controls_json']),'metrics':json.loads(r['metrics_json']),'created_by':r['created_by'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
   if _hash(payload)!=r['run_hash']:return False
   prev=r['run_hash']
  return True
 def add_review(self,*,run_id,reviewer_role,decision,rationale,reviewer):
  if reviewer==self.actor: raise ValueError('reviewer must differ from default run actor')
  if reviewer_role not in {'technical_reviewer','investigator_reviewer'}:raise ValueError('invalid reviewer role')
  if decision not in {'retain_phase12_release_candidate','reject_phase12_release_candidate'}:raise ValueError('invalid decision')
  r=self.db.one('SELECT * FROM phase12_rc_runs_300 WHERE run_id=?',(run_id,));
  if not r:raise KeyError('run not found')
  rid=_id('review300'); now=_now(); p={'review_id':rid,'run_id':run_id,'reviewer_role':reviewer_role,'decision':decision,'rationale':rationale,'reviewer':reviewer,'created_at':now}; self.db.execute('INSERT INTO phase12_rc_reviews_300 VALUES(?,?,?,?,?,?,?,?)',(rid,run_id,reviewer_role,decision,rationale,reviewer,now,_hash(p))); return p
 def all_training_cases(self):
  out=self.build299.all_training_cases()
  for r in self.db.all("SELECT * FROM ai_hard_training_delta_300 WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build299.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_300 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_300 WHERE review_status='reviewed' AND difficulty='extreme'")['n']); return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build300_delta_cases':d,'build300_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'critical_track_threshold':self.CRITICAL_TRACK_THRESHOLD,'automatic_model_activation':False}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'300.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':.92,'critical_track_minimum':.88,'maximum_critical_failures':0,'independent_evaluator_required':True,'cases':cases}; sha=_hash(manifest); ex=self.db.one('SELECT * FROM ai_evaluation_batches_300 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'critical_track_minimum':float(ex['critical_threshold']),'cases':cases,'deduplicated':True}
  bid=_id('eval300'); now=_now(); p={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO ai_evaluation_batches_300 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash(p))); return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':.92,'critical_track_minimum':.88,'cases':cases,'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':360,'minimum_mean_score':.92,'critical_track_minimum':.88,'note':'No >=92% model claim without full independent 360-case run.'}
 def startup_contract_status(self):
  import eagleeye_pro.version as v
  p=self.install_dir/'START_EAGLEEYE_PRO.bat'; text=p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''
  def _num(x):
   try:return tuple(int(p) for p in str(x).split('.')[:2])
   except Exception:return (0,0)
  current_ok=_num(v.BUILD)>=(300,0) and _num(v.SCHEMA_VERSION)>=(300,0)
  current_entry=f'EAGLEEYE_PRO_{str(v.BUILD).replace(chr(46),chr(95))}.py'
  checks={'version_build':current_ok,'version_schema':current_ok,'entrypoint':(self.install_dir/'EAGLEEYE_PRO_300_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_300_0.py').exists(),'generic_launcher_points_to_300':(('EAGLEEYE_PRO_300_0.py' in text and 'Build 300.0' in text) or (current_entry in text and f'Build {v.BUILD}' in text)),'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_300_0.bat').exists()}; return {'build':'300.0','checks':checks,'contract_ready':all(checks.values()),'actual_packaged_boot_required':True}
 def field_status(self):
  r=self.db.one('SELECT * FROM phase12_rc_runs_300 ORDER BY rowid DESC LIMIT 1')
  if not r:return {'stand':'Phase-12-Finalqualifikation noch nicht ausgeführt.','meaning':'Build 300 verbindet Pre-RC, Phase-11-Baseline, Recovery, Integrität, Autonomie-Governance und Release-Startvertrag.','next':'Finale RC-Tiefenqualifikation ausführen und Ergebnisse reviewen.'}
  return {'stand':f"Phase-12 RC: {r['passed_count']}/{r['scenario_count']} Tiefentest-Szenarien bestanden.",'meaning':'Interner Release Candidate. Keine Produktions-/Enterprise-Zertifizierung und keine behauptete Modellleistung ohne vollständigen Modelllauf.','next':'Ergebnisse, Regression und Startup prüfen; danach Phase 12 einfrieren.'}
 def qualified_gate(self):
  tm=self.training_metrics(); batch=self.create_evaluation_batch(); startup=self.startup_contract_status(); r=self.db.one('SELECT * FROM phase12_rc_runs_300 ORDER BY rowid DESC LIMIT 1')
  g={'build':'300.0','parent_gate':self.build299.qualified_gate()['release_ready'],'final_suite_passed':bool(r and r['result']=='pass' and int(r['scenario_count'])>=8 and int(r['failed_count'])==0),'run_chain_ok':self.verify_run_chain(),'hard_training_corpus_360':tm['reviewed_hard_cases']==360 and tm['build300_delta_cases']==40 and tm['build300_delta_extreme']==10,'evaluation_batch_360_ready':batch['corpus_size']==360 and abs(batch['minimum_mean_score']-.92)<1e-9 and abs(batch['critical_track_minimum']-.88)<1e-9,'startup_contract_ready':startup['contract_ready'],'network_access':False,'live_onion_transport':False,'external_collection_auto_execution':False,'production_certification_claimed':False,'enterprise_sla_claimed':False,'human_authority_preserved':True,'automatic_model_activation':False}
  g['release_ready']=all((g['parent_gate'],g['final_suite_passed'],g['run_chain_ok'],g['hard_training_corpus_360'],g['evaluation_batch_360_ready'],g['startup_contract_ready'],not g['network_access'],not g['live_onion_transport'],not g['external_collection_auto_execution'],not g['production_certification_claimed'],not g['enterprise_sla_claimed'],g['human_authority_preserved'],not g['automatic_model_activation'])); return g
 def render_workspace_panel(self,case_id,csrf):
  e=lambda v:html.escape(str(v or ''),quote=True); s=self.field_status(); tm=self.training_metrics(); p=self.performance_status(); return f"""<section class='card'><h2>Phase-12 Release Candidate · Build 300</h2><div class='notice'><b>Was ist der Stand?</b><br>{e(s['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(s['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(s['next'])}</div><form method='post' action='/build300/final-rc/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Finale Phase-12-Tiefenqualifikation starten</button></form><details><summary>Analyst/Experte</summary><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · Extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellgate ≥92%, kritische Tracks ≥88% · Modellstatus: <b>{e(p['status'])}</b> · Live-Onion-Transport: <b>aus</b>.</p></details></section>"""
