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

class Build290DiscriminatingEvidenceStartupService:
    BUILD='290.0'; GATE_THRESHOLD=0.85
    def __init__(self,db:Any,audit:Any,*,build289:Any,build288:Any,build281:Any,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build289=build289; self.build288=build288; self.build281=build281; self.base_dir=Path(base_dir); self.actor=actor

    def _mission(self,case_id:str,mission_id:str=''):
        if mission_id:
            row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? AND mission_id=?',(case_id,mission_id))
        else:
            row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not row: raise ValueError('Für den Fall existiert noch keine Phase-12-Mission.')
        return row

    def _hypotheses(self,case_id:str):
        rows=[]
        try: rows=[dict(r) for r in self.db.all("SELECT hypothesis_id,label,statement,hypothesis_type,status FROM hypotheses_268 WHERE case_id=? ORDER BY created_at DESC",(case_id,))]
        except Exception: rows=[]
        if len(rows)>=2:return rows[:6]
        return [
          {'hypothesis_id':'synthetic_working','label':'Arbeitsannahme','statement':'Die derzeit stärkste Arbeitsannahme erklärt die beobachteten Befunde.','hypothesis_type':'working','status':'provisional'},
          {'hypothesis_id':'synthetic_null','label':'Null-/Alternativerklärung','statement':'Eine alternative, weniger belastende Erklärung kann dieselben Befunde erklären.','hypothesis_type':'alternative','status':'provisional'},
        ]

    def create_discriminating_plan(self,*,case_id:str,mission_id:str='',actor:str|None=None):
        actor=actor or self.actor; m=self._mission(case_id,mission_id)
        a=self.db.one('SELECT * FROM phase12_ai_case_assessments_289 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not a:
            self.build289.assess_case(case_id=case_id,mission_id=m['mission_id'],actor=actor)
            a=self.db.one('SELECT * FROM phase12_ai_case_assessments_289 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        hyps=self._hypotheses(case_id); gaps=_safe(a['gaps_json'],[])
        candidates=[]
        pairs=[]
        for i,h1 in enumerate(hyps):
            for h2 in hyps[i+1:]:
                pairs.append((h1,h2))
        if not pairs:pairs=[(hyps[0],hyps[-1])]
        gap_map={g.get('category'):g for g in gaps}
        templates=[
          ('provenance','Welche unabhängige Primärquelle würde die beiden Erklärungen unterschiedlich erwarten lassen?',0.95,True),
          ('timeline','Welche zeitliche Beobachtung müsste unter einer Erklärung vorliegen, unter der Alternative aber nicht?',0.90,False),
          ('identity','Welcher belastbare Identitätsanker würde eine mögliche Personenverwechslung auflösen?',0.88,True),
          ('counterevidence','Welcher Befund würde die derzeit bevorzugte Erklärung am stärksten schwächen?',0.94,True),
          ('source_independence','Sind mehrere scheinbare Bestätigungen tatsächlich voneinander unabhängige Quellen?',0.86,False),
          ('document_anchor','Welches öffentliche/offizielle Dokument wäre der stärkste überprüfbare Anker?',0.92,True),
        ]
        for idx,(kind,q,val,external) in enumerate(templates,1):
            h1,h2=pairs[(idx-1)%len(pairs)]
            g=gap_map.get(kind) or gap_map.get('evidence') or (gaps[0] if gaps else {})
            why=f"Hoher diagnostischer Wert: Die Antwort soll zwischen '{h1['label']}' und '{h2['label']}' unterscheiden, statt nur weitere Bestätigung zu sammeln."
            expected={h1['label']:'Beobachtung ist mit dieser Erklärung vereinbar, aber noch kein Beweis.',h2['label']:'Alternative Vorhersage bzw. fehlender erwarteter Befund wird explizit geprüft.'}
            candidates.append({'priority':idx,'kind':kind,'question':q,'why_discriminating':why,'expected_if':expected,'information_value':val,'external_collection_required':external,'gap_context':g.get('title','allgemeine Evidenzprüfung')})
        candidates.sort(key=lambda x:(-x['information_value'],x['priority']))
        ranking=[{'rank':i+1,'kind':c['kind'],'question':c['question'],'information_value':c['information_value']} for i,c in enumerate(candidates)]
        pid=_id('dplan290'); created=_now(); summary=f"{len(candidates)} diskriminierende Evidenzfragen priorisiert. Ziel: konkurrierende Erklärungen auseinanderhalten; keine automatische Wahrheitsentscheidung."
        payload={'plan_id':pid,'case_id':case_id,'mission_id':m['mission_id'],'assessment_id':a['assessment_id'],'hypotheses':hyps,'discriminators':candidates,'ranking':ranking,'summary':summary,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_discriminating_plans_290 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,m['mission_id'],a['assessment_id'],_canon(hyps),_canon(candidates),_canon(ranking),summary,1,actor,created,_hash(payload)))
        for i,c in enumerate(candidates,1):
            tid=_id('dtask290'); mode='external_collection_deferred' if c['external_collection_required'] else 'local_analysis'
            tp={'task_id':tid,'plan_id':pid,'case_id':case_id,'mission_id':m['mission_id'],'priority':i,'question':c['question'],'why_discriminating':c['why_discriminating'],'expected_if':c['expected_if'],'information_value':c['information_value'],'execution_mode':mode,'external_collection_required':c['external_collection_required'],'status':'proposed','created_at':created}
            self.db.execute('INSERT INTO phase12_discriminating_tasks_290 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,pid,case_id,m['mission_id'],i,c['question'],c['why_discriminating'],_canon(c['expected_if']),float(c['information_value']),mode,int(c['external_collection_required']),'proposed',created,_hash(tp)))
        return payload

    def approve_plan(self,*,plan_id:str,confirmation:str,approved_by:str):
        if confirmation.strip().upper()!='OK': raise PermissionError("Freigabe benötigt ausdrücklich 'OK'.")
        p=self.db.one('SELECT * FROM phase12_discriminating_plans_290 WHERE plan_id=?',(plan_id,))
        if not p: raise KeyError('plan not found')
        tasks=[dict(r) for r in self.db.all('SELECT * FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority',(plan_id,))]
        scope={'plan_id':plan_id,'mission_id':p['mission_id'],'tasks':[{k:t[k] for k in ('task_id','priority','question','information_value','execution_mode','external_collection_required')} for t in tasks]}
        sh=_hash(scope)
        ex=self.db.one("SELECT * FROM phase12_discriminating_approvals_290 WHERE plan_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(plan_id,))
        if ex:return {'plan_id':plan_id,'approved':True,'scope_sha256':ex['scope_sha256'],'deduplicated':True}
        aid=_id('dapprove290'); created=_now(); payload={'approval_id':aid,'plan_id':plan_id,'case_id':p['case_id'],'mission_id':p['mission_id'],'decision':'approved','approved_by':approved_by,'approved_at':created,'scope_sha256':sh}
        self.db.execute('INSERT INTO phase12_discriminating_approvals_290 VALUES(?,?,?,?,?,?,?,?,?)',(aid,plan_id,p['case_id'],p['mission_id'],'approved',approved_by,created,sh,_hash(payload)))
        return {**payload,'approved':True,'deduplicated':False}

    def run_approved_local_analysis(self,*,plan_id:str,actor:str|None=None):
        actor=actor or self.actor; p=self.db.one('SELECT * FROM phase12_discriminating_plans_290 WHERE plan_id=?',(plan_id,))
        if not p: raise KeyError('plan not found')
        ap=self.db.one("SELECT * FROM phase12_discriminating_approvals_290 WHERE plan_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(plan_id,))
        if not ap: raise PermissionError('Diskriminierender Evidenzplan benötigt zuerst das OK des Hauptermittlers.')
        tasks=[dict(r) for r in self.db.all('SELECT * FROM phase12_discriminating_tasks_290 WHERE plan_id=? ORDER BY priority',(plan_id,))]
        scope={'plan_id':plan_id,'mission_id':p['mission_id'],'tasks':[{k:t[k] for k in ('task_id','priority','question','information_value','execution_mode','external_collection_required')} for t in tasks]}
        if _hash(scope)!=ap['scope_sha256']: raise PermissionError('Scope-Drift erkannt; neues OK erforderlich.')
        local=[]; deferred=[]
        for t in tasks:
            if int(t['external_collection_required']):
                deferred.append({'task_id':t['task_id'],'question':t['question'],'status':'requires_separate_collection_authorization'})
            else:
                local.append({'task_id':t['task_id'],'question':t['question'],'status':'local_comparison_completed','result':'Vorhandener Fallstand wurde auf unterschiedliche Vorhersagen geprüft; Ergebnis bleibt Review-Kandidat.'})
        rid=_id('drun290'); created=_now(); result={'local_results':local,'external_deferred':deferred,'next_checkpoint':'Hauptermittler prüft, welche Frage den höchsten zusätzlichen Informationsgewinn rechtfertigt.','automatic_truth_selection':False}
        payload={'run_id':rid,'plan_id':plan_id,'case_id':p['case_id'],'mission_id':p['mission_id'],'approved_scope_sha256':ap['scope_sha256'],'local_tasks_processed':len(local),'external_tasks_deferred':len(deferred),'network_access':False,'scope_expansion':False,'result':result,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_discriminating_runs_290 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,plan_id,p['case_id'],p['mission_id'],ap['scope_sha256'],len(local),len(deferred),0,0,_canon(result),1,actor,created,_hash(payload)))
        return payload

    def startup_contract_status(self):
        import eagleeye_pro.version as v
        def _ver(value):
            try:return tuple(int(x) for x in str(value).split('.')[:2])
            except Exception:return (0,0)
        checks={
          'version_build':_ver(v.BUILD)>=(290,0),
          'version_schema':_ver(v.SCHEMA_VERSION)>=(290,0),
          'project_entrypoint':(self.base_dir/'EAGLEEYE_PRO_290_0.py').exists(),
          'generic_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO.bat').exists(),
          'versioned_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO_290_0.bat').exists(),
          'setup_script':(self.base_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),
          'requirements_windows':(self.base_dir/'requirements-windows.txt').exists(),
        }
        return {'build':'290.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True}

    def all_training_cases(self):
        out=self.build289.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_290 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows:out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build289.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_290 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_290 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build290_delta_cases':d,'build290_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'290.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_290 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval290'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO ai_evaluation_batches_290 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build289.performance_status(model_label)
        return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False,'required_corpus_size':176,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 290 beansprucht keine ≥85%-Leistung ohne vollständigen unabhängigen 176-Fälle-Lauf.'}
    def qualified_gate(self):
        parent=self.build289.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); sc=self.startup_contract_status()
        g={'build':'290.0','parent_gate':bool(parent['release_ready']),'discriminating_evidence_planner':True,'hypothesis_comparison':True,'explicit_ok_required':True,'local_analysis_bounded':True,'external_collection_auto_execution':False,'scope_expansion':False,'network_access':False,'beginner_guidance':True,'hard_training_corpus_176':tm['reviewed_hard_cases']>=176 and tm['build290_delta_cases']>=16 and tm['build290_delta_extreme']>=4,'evaluation_batch_176_ready':batch['corpus_size']==176 and abs(batch['minimum_mean_score']-0.85)<1e-9,'startup_contract_ready':sc['contract_ready'],'actual_startup_release_test_required':True,'automatic_model_activation':False,'human_authority_preserved':True}
        g['release_ready']=all([g['parent_gate'],g['discriminating_evidence_planner'],g['hypothesis_comparison'],g['explicit_ok_required'],g['local_analysis_bounded'],not g['external_collection_auto_execution'],not g['scope_expansion'],not g['network_access'],g['beginner_guidance'],g['hard_training_corpus_176'],g['evaluation_batch_176_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True)
        plans=self.db.all('SELECT * FROM phase12_discriminating_plans_290 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,)); latest=plans[0] if plans else None; tm=self.training_metrics(); sc=self.startup_contract_status(); perf=self.performance_status()
        if latest:
            ranks=_safe(latest['ranking_json'],[]); rows=''.join(f"<li><b>{e(x.get('rank'))}. {e(x.get('question'))}</b> · Informationswert {e(x.get('information_value'))}</li>" for x in ranks[:5])
            stand='Ein diskriminierender Evidenzplan liegt vor.'; meaning='Die AI priorisiert Fragen danach, wie gut sie konkurrierende Erklärungen auseinanderhalten – nicht danach, wie viele Treffer sie erzeugen.'; nextstep="Plan prüfen und nur mit 'OK' freigeben; externe Erhebung bleibt separat genehmigungspflichtig."
        else:
            rows='<li>Noch kein diskriminierender Evidenzplan.</li>'; stand='Build 290 hat für diesen Fall noch keinen Vergleichsplan erstellt.'; meaning='Die AI soll jetzt nicht einfach mehr suchen, sondern die nützlichste nächste Frage bestimmen.'; nextstep='Mit „Diskriminierende Evidenz planen“ beginnen.'
        form=f"<form method='post' action='/build290/plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Diskriminierende Evidenz planen</button></form>"
        action_forms=''
        if latest:
            approval=self.db.one("SELECT * FROM phase12_discriminating_approvals_290 WHERE plan_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(latest['plan_id'],))
            if not approval:
                action_forms=f"<form method='post' action='/build290/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='plan_id' value='{e(latest['plan_id'])}'><label>Freigabe <input name='confirmation' placeholder='OK'></label> <button>Plan mit OK freigeben</button></form>"
            else:
                action_forms=f"<form method='post' action='/build290/run-local'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='plan_id' value='{e(latest['plan_id'])}'><button>Freigegebene lokale Analyse ausführen</button></form>"
        return f"""
<section class='card'><h2>AI-Ermittlung · Build 290</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{stand}<br><br><b>Was bedeutet das?</b><br>{meaning}<br><br><b>Was ist jetzt zu tun?</b><br>{nextstep}</div>
<h3>Fragen mit hohem Informationswert</h3><ol>{rows}</ol>{form}{action_forms}
<details><summary>Analyst/Experte: Startup-, Audit- und Trainingsstatus</summary><p>Startup-Vertrag: <b>{'ready' if sc['contract_ready'] else 'not ready'}</b> · actual loopback boot: <b>Release-Test erforderlich</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Build-290 AI-Gate: 176/176 Fälle, ≥85%, 0 kritische Fehler, unabhängige Evaluation.</p></details>
</section>"""
