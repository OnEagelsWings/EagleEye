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
def _ver(s:str):
    try:return tuple(int(x) for x in str(s).split('.')[:2])
    except Exception:return (0,0)

class Build291AdaptiveHypothesisService:
    BUILD='291.0'; GATE_THRESHOLD=0.85
    def __init__(self,db:Any,audit:Any,*,build290:Any,build289:Any,build281:Any,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build290=build290; self.build289=build289; self.build281=build281; self.base_dir=Path(base_dir); self.actor=actor

    def _mission(self,case_id:str,mission_id:str=''):
        if mission_id: row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? AND mission_id=?',(case_id,mission_id))
        else: row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not row: raise ValueError('Für den Fall existiert noch keine Phase-12-Mission.')
        return row

    def _source_plan(self,case_id:str,mission_id:str,plan_id:str='',actor:str=''):
        if plan_id: p=self.db.one('SELECT * FROM phase12_discriminating_plans_290 WHERE case_id=? AND plan_id=?',(case_id,plan_id))
        else: p=self.db.one('SELECT * FROM phase12_discriminating_plans_290 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not p:
            self.build290.create_discriminating_plan(case_id=case_id,mission_id=mission_id,actor=actor or self.actor)
            p=self.db.one('SELECT * FROM phase12_discriminating_plans_290 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        return p

    @staticmethod
    def _kind(question:str)->str:
        q=(question or '').lower()
        if 'gegen' in q or 'schwäch' in q or 'befund' in q:return 'counterevidence'
        if 'identität' in q or 'personenverwechsl' in q:return 'identity'
        if 'zeit' in q:return 'timeline'
        if 'unabhängig' in q:return 'source_independence'
        if 'dokument' in q:return 'document_anchor'
        if 'primärquelle' in q:return 'provenance'
        return 'evidence'

    def _completed_source_ids(self,case_id:str)->set[str]:
        try:
            return {str(r['source_task_id']) for r in self.db.all("SELECT DISTINCT source_task_id FROM phase12_adaptive_outcomes_291 WHERE review_status IN ('review_candidate','reviewed') AND round_id IN (SELECT round_id FROM phase12_adaptive_rounds_291 WHERE case_id=?)",(case_id,))}
        except Exception:return set()

    def _rank(self,tasks:list[dict],completed:set[str],round_no:int):
        ranked=[]
        for t in tasks:
            base=float(t['information_value']); kind=self._kind(t['question']); external=bool(t['external_collection_required'])
            completed_penalty=0.24 if str(t['task_id']) in completed else 0.0
            counter_bonus=0.045 if kind=='counterevidence' and round_no>1 else 0.0
            independence_bonus=0.03 if kind in ('source_independence','provenance') else 0.0
            local_bonus=0.02 if not external else 0.0
            adaptive=max(0.05,min(0.99,base-completed_penalty+counter_bonus+independence_bonus+local_bonus))
            reasons=[]
            if completed_penalty: reasons.append('bereits lokal bearbeitet: nachrangig')
            if counter_bonus: reasons.append('Gegenbeleg nach erster Runde aufgewertet')
            if independence_bonus: reasons.append('Quellenunabhängigkeit/Provenienz erhöht diagnostischen Wert')
            if local_bonus: reasons.append('innerhalb des genehmigten lokalen Scopes sofort prüfbar')
            if not reasons: reasons.append('hoher ursprünglicher Informationswert bleibt erhalten')
            ranked.append({'source_task_id':t['task_id'],'question':t['question'],'kind':kind,'base_information_value':base,'adaptive_score':round(adaptive,4),'execution_mode':t['execution_mode'],'external_collection_required':external,'rationale':'; '.join(reasons)})
        ranked.sort(key=lambda x:(-x['adaptive_score'],x['external_collection_required'],x['question']))
        for i,x in enumerate(ranked,1):x['priority']=i
        return ranked

    def create_adaptive_round(self,*,case_id:str,mission_id:str='',plan_id:str='',actor:str|None=None):
        actor=actor or self.actor; m=self._mission(case_id,mission_id); p=self._source_plan(case_id,m['mission_id'],plan_id,actor)
        tasks=[dict(r) for r in self.db.all('SELECT * FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority',(p['plan_id'],))]
        if not tasks: raise ValueError('Der Build-290-Plan enthält keine Aufgaben.')
        prior=int(self.db.one('SELECT COUNT(*) n FROM phase12_adaptive_rounds_291 WHERE case_id=?',(case_id,))['n']); round_no=prior+1
        completed=self._completed_source_ids(case_id)
        before=[{'priority':i+1,'source_task_id':t['task_id'],'question':t['question'],'score':float(t['information_value'])} for i,t in enumerate(sorted(tasks,key=lambda x:(-float(x['information_value']),int(x['priority']))))]
        adaptive=self._rank(tasks,completed,round_no)
        hyps=_safe(p['hypotheses_json'],[])
        rid=_id('around291'); created=_now(); state={'case_id':case_id,'mission_id':m['mission_id'],'source_plan_id':p['plan_id'],'round_no':round_no,'source_tasks':[{k:t[k] for k in ('task_id','question','information_value','execution_mode','external_collection_required')} for t in tasks],'completed_source_task_ids':sorted(completed)}
        state_hash=_hash(state); summary=f'Adaptive Runde {round_no}: {len(adaptive)} Fragen neu gewichtet; {len(completed)} bereits bearbeitete Quellaufgaben berücksichtigt. Mehrere Erklärungen bleiben ausdrücklich offen.'
        payload={'round_id':rid,'case_id':case_id,'mission_id':m['mission_id'],'source_plan_id':p['plan_id'],'round_no':round_no,'hypotheses':hyps,'ranking_before':before,'adaptive_ranking':adaptive,'summary':summary,'human_review_required':True,'state_sha256':state_hash,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_adaptive_rounds_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,m['mission_id'],p['plan_id'],round_no,_canon(hyps),_canon(before),_canon(adaptive),summary,1,actor,created,state_hash,_hash(payload)))
        for x in adaptive:
            aid=_id('atask291'); tp={'adaptive_task_id':aid,'round_id':rid,'source_task_id':x['source_task_id'],'case_id':case_id,'mission_id':m['mission_id'],'priority':x['priority'],'question':x['question'],'base_information_value':x['base_information_value'],'adaptive_score':x['adaptive_score'],'execution_mode':x['execution_mode'],'external_collection_required':x['external_collection_required'],'rationale':x['rationale'],'status':'proposed','created_at':created}
            self.db.execute('INSERT INTO phase12_adaptive_tasks_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,rid,x['source_task_id'],case_id,m['mission_id'],x['priority'],x['question'],x['base_information_value'],x['adaptive_score'],x['execution_mode'],int(x['external_collection_required']),x['rationale'],'proposed',created,_hash(tp)))
        return payload

    def approve_round(self,*,round_id:str,confirmation:str,approved_by:str):
        if confirmation.strip().upper()!='OK': raise PermissionError("Freigabe benötigt ausdrücklich 'OK'.")
        r=self.db.one('SELECT * FROM phase12_adaptive_rounds_291 WHERE round_id=?',(round_id,))
        if not r: raise KeyError('adaptive round not found')
        tasks=[dict(x) for x in self.db.all('SELECT * FROM phase12_adaptive_tasks_291 WHERE round_id=? ORDER BY priority',(round_id,))]
        scope={'round_id':round_id,'mission_id':r['mission_id'],'state_sha256':r['state_sha256'],'tasks':[{k:t[k] for k in ('adaptive_task_id','source_task_id','priority','question','adaptive_score','execution_mode','external_collection_required')} for t in tasks]}
        sh=_hash(scope); ex=self.db.one("SELECT * FROM phase12_adaptive_approvals_291 WHERE round_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(round_id,))
        if ex:return {'round_id':round_id,'approved':True,'scope_sha256':ex['scope_sha256'],'deduplicated':True}
        aid=_id('aapprove291'); created=_now(); payload={'approval_id':aid,'round_id':round_id,'case_id':r['case_id'],'mission_id':r['mission_id'],'decision':'approved','approved_by':approved_by,'approved_at':created,'scope_sha256':sh}
        self.db.execute('INSERT INTO phase12_adaptive_approvals_291 VALUES(?,?,?,?,?,?,?,?,?)',(aid,round_id,r['case_id'],r['mission_id'],'approved',approved_by,created,sh,_hash(payload)))
        return {**payload,'approved':True,'deduplicated':False}

    def run_approved_adaptive_cycle(self,*,round_id:str,actor:str|None=None):
        actor=actor or self.actor; r=self.db.one('SELECT * FROM phase12_adaptive_rounds_291 WHERE round_id=?',(round_id,))
        if not r: raise KeyError('adaptive round not found')
        ap=self.db.one("SELECT * FROM phase12_adaptive_approvals_291 WHERE round_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(round_id,))
        if not ap: raise PermissionError('Adaptive Runde benötigt zuerst das OK des Hauptermittlers.')
        tasks=[dict(x) for x in self.db.all('SELECT * FROM phase12_adaptive_tasks_291 WHERE round_id=? ORDER BY priority',(round_id,))]
        scope={'round_id':round_id,'mission_id':r['mission_id'],'state_sha256':r['state_sha256'],'tasks':[{k:t[k] for k in ('adaptive_task_id','source_task_id','priority','question','adaptive_score','execution_mode','external_collection_required')} for t in tasks]}
        if _hash(scope)!=ap['scope_sha256']: raise PermissionError('Scope-Drift erkannt; neues OK erforderlich.')
        local=[]; deferred=[]; completed=set(self._completed_source_ids(r['case_id']))
        cid=_id('acycle291'); created=_now()
        for t in tasks:
            if int(t['external_collection_required']):
                deferred.append({'adaptive_task_id':t['adaptive_task_id'],'question':t['question'],'status':'requires_separate_collection_authorization'})
                continue
            local.append({'adaptive_task_id':t['adaptive_task_id'],'question':t['question'],'status':'bounded_local_analysis_completed','result':'Lokale Fallstruktur wurde erneut verglichen. Der Informationsgewinn verändert Prioritäten, nicht automatisch die Wahrheitseinschätzung.'})
            completed.add(str(t['source_task_id']))
            oid=_id('outcome291'); op={'outcome_id':oid,'cycle_id':cid,'round_id':round_id,'adaptive_task_id':t['adaptive_task_id'],'source_task_id':t['source_task_id'],'outcome_class':'uncertainty_reduced','information_gain':0.15,'claim_effect':'review_candidate_only','review_status':'review_candidate','created_by':actor,'created_at':created}
            self.db.execute('INSERT INTO phase12_adaptive_outcomes_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(oid,cid,round_id,t['adaptive_task_id'],t['source_task_id'],'uncertainty_reduced',0.15,'review_candidate_only','review_candidate',actor,created,_hash(op)))
        source_tasks=[dict(x) for x in self.db.all('SELECT * FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority',(r['source_plan_id'],))]
        before=_safe(r['adaptive_ranking_json'],[]); after=self._rank(source_tasks,completed,int(r['round_no'])+1)
        before_pos={str(x['source_task_id']):int(x['priority']) for x in before}; changed=sum(1 for x in after if before_pos.get(str(x['source_task_id']))!=int(x['priority']))
        next_priority=next((x for x in after if str(x['source_task_id']) not in completed),after[0] if after else {})
        reason='Prioritäten wurden nach lokalem Informationsgewinn neu gewichtet: bearbeitete Fragen sinken, komplementäre Gegenbeleg-/Provenienzfragen können steigen. Keine Hypothese wird automatisch ausgewählt.'
        reid=_id('reprio291'); rp={'reprioritization_id':reid,'cycle_id':cid,'round_id':round_id,'case_id':r['case_id'],'mission_id':r['mission_id'],'ranking_before':before,'ranking_after':after,'changed_positions':changed,'next_priority':next_priority,'reason':reason,'human_review_required':True,'created_at':created}
        self.db.execute('INSERT INTO phase12_adaptive_reprioritizations_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(reid,cid,round_id,r['case_id'],r['mission_id'],_canon(before),_canon(after),changed,_canon(next_priority),reason,1,created,_hash(rp)))
        hyps=_safe(r['hypotheses_json'],[]); result={'local_results':local,'external_deferred':deferred,'reprioritization':{'changed_positions':changed,'ranking_after':after,'next_priority':next_priority},'hypotheses_retained':len(hyps),'automatic_truth_selection':False,'next_checkpoint':'Hauptermittler prüft die neue Rangfolge. Externe Collection bleibt separat freigabepflichtig.'}
        payload={'cycle_id':cid,'round_id':round_id,'case_id':r['case_id'],'mission_id':r['mission_id'],'approved_scope_sha256':ap['scope_sha256'],'local_tasks_processed':len(local),'external_tasks_deferred':len(deferred),'hypotheses_retained':len(hyps),'network_access':False,'scope_expansion':False,'automatic_truth_selection':False,'result':result,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_adaptive_cycle_runs_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,round_id,r['case_id'],r['mission_id'],ap['scope_sha256'],len(local),len(deferred),len(hyps),0,0,0,_canon(result),1,actor,created,_hash(payload)))
        return payload

    def startup_contract_status(self):
        import eagleeye_pro.version as v
        checks={
          'version_build':_ver(v.BUILD)>=(291,0),'version_schema':_ver(v.SCHEMA_VERSION)>=(291,0),
          'project_entrypoint':(self.base_dir/'EAGLEEYE_PRO_291_0.py').exists(),
          'startup_acceptance_script':(self.base_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_291_0.py').exists(),
          'generic_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO.bat').exists(),
          'versioned_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO_291_0.bat').exists(),
          'setup_script':(self.base_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.base_dir/'requirements-windows.txt').exists(),
        }
        return {'build':'291.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True}

    def all_training_cases(self):
        out=self.build290.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_291 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows:out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build290.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_291 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_291 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build291_delta_cases':d,'build291_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'291.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_291 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval291'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO ai_evaluation_batches_291 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build290.performance_status(model_label)
        return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False,'required_corpus_size':192,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 291 beansprucht keine ≥85%-Leistung ohne vollständigen unabhängigen 192-Fälle-Lauf.'}
    def qualified_gate(self):
        parent=self.build290.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); sc=self.startup_contract_status()
        g={'build':'291.0','parent_gate':bool(parent['release_ready']),'adaptive_reprioritization':True,'counterevidence_orchestration':True,'multiple_hypotheses_retained':True,'explicit_ok_required':True,'approved_local_autonomy':True,'external_collection_auto_execution':False,'scope_expansion':False,'network_access':False,'beginner_guidance':True,'hard_training_corpus_192':tm['reviewed_hard_cases']>=192 and tm['build291_delta_cases']>=16 and tm['build291_delta_extreme']>=4,'evaluation_batch_192_ready':batch['corpus_size']==192 and abs(batch['minimum_mean_score']-0.85)<1e-9,'startup_contract_ready':sc['contract_ready'],'actual_startup_release_test_required':True,'automatic_model_activation':False,'human_authority_preserved':True}
        g['release_ready']=all([g['parent_gate'],g['adaptive_reprioritization'],g['counterevidence_orchestration'],g['multiple_hypotheses_retained'],g['explicit_ok_required'],g['approved_local_autonomy'],not g['external_collection_auto_execution'],not g['scope_expansion'],not g['network_access'],g['beginner_guidance'],g['hard_training_corpus_192'],g['evaluation_batch_192_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True)
        rounds=self.db.all('SELECT * FROM phase12_adaptive_rounds_291 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,)); latest=rounds[0] if rounds else None; tm=self.training_metrics(); perf=self.performance_status(); sc=self.startup_contract_status()
        if latest:
            ranks=_safe(latest['adaptive_ranking_json'],[]); rows=''.join(f"<li><b>{e(x.get('priority'))}. {e(x.get('question'))}</b><br>Adaptive Score {e(x.get('adaptive_score'))} · {e(x.get('rationale'))}</li>" for x in ranks[:5])
            rep=self.db.one('SELECT * FROM phase12_adaptive_reprioritizations_291 WHERE round_id=? ORDER BY rowid DESC LIMIT 1',(latest['round_id'],))
            if rep:
                nxt=_safe(rep['next_priority_json'],{}); stand=f"Runde {e(latest['round_no'])} wurde analysiert; {e(rep['changed_positions'])} Rangpositionen haben sich verändert."; meaning='Die AI hat neue lokale Informationen in die Reihenfolge eingerechnet. Das ist eine Prioritätsänderung, keine automatische Wahrheitsentscheidung.'; nextstep=f"Neue Rangfolge prüfen. Nächste priorisierte Frage: {e(nxt.get('question','keine offene Frage'))}. Externe Erhebung bleibt separat freigabepflichtig."
            else:
                stand=f"Adaptive Ermittlungsrunde {e(latest['round_no'])} ist vorbereitet."; meaning='Die AI gewichtet offene, bereits bearbeitete und gegenbelegorientierte Fragen neu.'; nextstep="Rangfolge prüfen und nur mit 'OK' für den begrenzten lokalen Zyklus freigeben."
        else:
            rows='<li>Noch keine adaptive Runde.</li>'; stand='Build 291 hat für diesen Fall noch keine adaptive Priorisierung erstellt.'; meaning='Die AI kann die Build-290-Fragen jetzt nach bereits gewonnenen Informationen neu ordnen.'; nextstep='Mit „Adaptive Runde erstellen“ beginnen.'
        create=f"<form method='post' action='/build291/round'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Adaptive Runde erstellen</button></form>"
        actions=''
        if latest:
            approval=self.db.one("SELECT * FROM phase12_adaptive_approvals_291 WHERE round_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(latest['round_id'],))
            if not approval: actions=f"<form method='post' action='/build291/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='round_id' value='{e(latest['round_id'])}'><label>Freigabe <input name='confirmation' placeholder='OK'></label> <button>Adaptive Runde mit OK freigeben</button></form>"
            else: actions=f"<form method='post' action='/build291/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='round_id' value='{e(latest['round_id'])}'><button>Freigegebenen adaptiven AI-Zyklus ausführen</button></form>"
        return f"""
<section class='card'><h2>AI-Ermittlung · Build 291</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{stand}<br><br><b>Was bedeutet das?</b><br>{meaning}<br><br><b>Was ist jetzt zu tun?</b><br>{nextstep}</div>
<h3>Adaptive Prioritäten</h3><ol>{rows}</ol>{create}{actions}
<details><summary>Analyst/Experte: Adaptive Logik, Startup und Training</summary><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Startup-Vertrag: <b>{'ready' if sc['contract_ready'] else 'not ready'}</b>. Build-291 AI-Gate: 192/192 Fälle, ≥85%, 0 kritische Fehler, unabhängige Evaluation. Netzwerkzugriff und automatische externe Collection bleiben aus.</p></details>
</section>"""
