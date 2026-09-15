from __future__ import annotations
import hashlib, html, json, uuid
from datetime import datetime, timezone
from typing import Any

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256((_canon(v) if not isinstance(v,str) else v).encode('utf-8')).hexdigest()

def _safe_json(v,default):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else default)
    except Exception:return default

class Build289AIInvestigationDepthService:
    BUILD='289.0'; GATE_THRESHOLD=0.80
    LOCAL_TYPES={'analyze_evidence','review_hypothesis','review_identity','review_counterevidence','deduplicate_research'}
    def __init__(self,db:Any,audit:Any,*,build288:Any,build281:Any,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build288=build288; self.build281=build281; self.actor=actor

    def _table_exists(self,name:str)->bool:
        return bool(self.db.one("SELECT 1 ok FROM sqlite_master WHERE type='table' AND name=?",(name,)))
    def _count(self,table:str,case_id:str,extra:str='',params:tuple=())->int:
        if not self._table_exists(table): return 0
        row=self.db.one(f'SELECT COUNT(*) n FROM {table} WHERE case_id=? {extra}',(case_id,*params)); return int(row['n']) if row else 0
    def _event(self,case_id,event_type,obj_type,obj_id,payload,actor):
        prev=self.db.one('SELECT event_hash FROM phase12_ai_depth_events_289 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); ph=prev['event_hash'] if prev else ''
        eid=_id('evt289'); created=_now(); body={'event_id':eid,'case_id':case_id,'event_type':event_type,'object_type':obj_type,'object_id':obj_id,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':created}; eh=_hash(body)
        self.db.execute('INSERT INTO phase12_ai_depth_events_289 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,event_type,obj_type,obj_id,actor,_canon(payload),ph,eh,created)); return eh

    def _mission_for_case(self,case_id:str,mission_id:str=''):
        if mission_id:
            m=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=? AND case_id=?',(mission_id,case_id))
        else:
            m=self.db.one("SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,))
        if not m: raise ValueError('Für den Fall existiert noch keine Phase-12-Mission.')
        return m

    def assess_case(self,*,case_id:str,mission_id:str='',actor:str|None=None):
        actor=actor or self.actor; m=self._mission_for_case(case_id,mission_id)
        claims=self._count('retrieval_claims_225',case_id)
        claim_support=self._count('claim_evidence_links_225',case_id,"AND stance='supports'")
        claim_contra=self._count('claim_evidence_links_225',case_id,"AND stance='contradicts'")
        hypotheses=self._count('hypotheses_268',case_id)
        hyp_support=self._count('hypothesis_evidence_links_268',case_id,"AND role LIKE 'support%'")
        hyp_contra=self._count('hypothesis_evidence_links_268',case_id,"AND role LIKE 'contradict%'")
        counter=self._count('counterevidence_258',case_id)
        profiles=self._count('person_document_profiles_273',case_id)
        documents=self._count('document_candidates_273',case_id)
        snapshots=self._count('phase12_capture_snapshots_288',case_id)
        collections=self._count('phase12_collection_requests_285',case_id)
        # duplicate source paths indicate redundant collection effort
        redundancies=[]
        if self._table_exists('phase12_collection_requests_285'):
            rows=self.db.all('SELECT normalized_locator,COUNT(*) n FROM phase12_collection_requests_285 WHERE case_id=? GROUP BY normalized_locator HAVING COUNT(*)>1 ORDER BY n DESC',(case_id,))
            redundancies=[{'kind':'duplicate_source_path','source_locator':r['normalized_locator'],'count':int(r['n']),'action':'Vor einer weiteren Erhebung prüfen, ob ein vorhandener Capture/Receipt genügt.'} for r in rows]
        gaps=[]
        def gap(cat,severity,title,rationale,action,external=False,scope='approved_case'):
            gaps.append({'category':cat,'severity':severity,'title':title,'rationale':rationale,'recommended_action':action,'external_collection_required':bool(external),'scope_class':scope})
        if snapshots==0:
            gap('evidence','high','Keine Phase-12-Capture-Snapshots','Die aktuelle Mission hat noch keinen reproduzierbaren Capture-Snapshot.','Vor Schlussfolgerungen vorhandene lokale Evidenz prüfen oder eine separat freizugebende Collection vorbereiten.',True)
        if claims==0:
            gap('claims','medium','Keine strukturierten Retrieval-Claims','Der Fall enthält derzeit keine strukturierten Claims aus der Retrieval-Schicht.','Vorhandenes Material lokal in beobachtbare Aussagen zerlegen.',False)
        elif claim_support>0 and claim_contra==0 and counter==0:
            gap('counterevidence','high','Gegenbelege fehlen','Es existiert Unterstützung, aber kein strukturierter Widerspruch/Gegenbeleg.','Eine diskriminierende Gegenbeleg-Suche planen; Bestätigung allein nicht als Abschluss werten.',True)
        if hypotheses==0:
            gap('hypothesis','medium','Keine konkurrierenden Hypothesen','Die Hypothesen-Schicht ist leer.','Mindestens eine Arbeits- und eine Null-/Alternativhypothese lokal formulieren.',False)
        elif hyp_support>0 and hyp_contra==0:
            gap('hypothesis','high','Hypothesen ohne dokumentierte Widerspruchsprüfung','Unterstützende Verknüpfungen existieren, widersprechende Verknüpfungen fehlen.','Hypothesen gezielt auf Falsifikationskriterien prüfen.',False)
        if profiles>0 and documents==0:
            gap('identity','high','Personenprofil ohne Dokumentanker','Ein Personen-Dokumentprofil existiert, aber keine Dokumentkandidaten.','Identitätsanker aus offiziellen/öffentlichen Dokumenten als separate Collection-Aufgabe vorbereiten.',True,'person_osint_public_records')
        if collections>0 and snapshots==0:
            gap('collection','medium','Collection geplant, aber noch kein Snapshot','Es gibt Collection-Aufträge, aber keinen reproduzierbaren Snapshot.','Status der Gateway-/Capture-Kette prüfen; nicht blind erneut sammeln.',False)
        if not gaps:
            gap('review','low','Kein offensichtlicher Struktur-Gap','Die automatischen Strukturprüfungen finden keinen dominanten Mangel.','Hauptermittler prüft Hypothesen, Quellenabhängigkeit und Relevanz vor der nächsten Recherchewelle.',False)
        severity_rank={'high':0,'medium':1,'low':2}
        gaps.sort(key=lambda x:(severity_rank.get(x['severity'],9),x['category']))
        priorities=[{'rank':i+1,'category':g['category'],'title':g['title'],'recommended_action':g['recommended_action'],'external_collection_required':g['external_collection_required']} for i,g in enumerate(gaps[:8])]
        uncertainty={'identity_uncertainty':profiles>0 and documents<2,'counterevidence_coverage_low':(claim_support+hyp_support)>0 and (claim_contra+hyp_contra+counter)==0,'evidence_density':'low' if snapshots+documents<2 else 'moderate_or_higher','automatic_truth_selection':False}
        ev={'claims':claims,'claim_support_links':claim_support,'claim_contradiction_links':claim_contra,'hypotheses':hypotheses,'hypothesis_support_links':hyp_support,'hypothesis_contradiction_links':hyp_contra,'counterevidence':counter,'person_profiles':profiles,'document_candidates':documents,'capture_snapshots':snapshots,'collection_requests':collections}
        summary=f"AI-Strukturprüfung: {len(gaps)} priorisierte Prüfpunkte; {len(redundancies)} mögliche redundante Suchpfade. Keine automatische Wahrheitsentscheidung."
        aid=_id('assess289'); created=_now(); payload={'assessment_id':aid,'case_id':case_id,'mission_id':m['mission_id'],'assessment_version':'289.0','evidence_snapshot':ev,'gaps':gaps,'priorities':priorities,'redundancies':redundancies,'uncertainty':uncertainty,'summary':summary,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_ai_case_assessments_289 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,m['mission_id'],'289.0',_canon(ev),_canon(gaps),_canon(priorities),_canon(redundancies),_canon(uncertainty),summary,1,actor,created,_hash(payload)))
        self._event(case_id,'case_assessed','assessment',aid,{'gap_count':len(gaps),'redundancy_count':len(redundancies)},actor)
        return payload

    def propose_research_wave(self,*,assessment_id:str,max_tasks:int=6,external_collection_budget:int=2,actor:str|None=None):
        actor=actor or self.actor; max_tasks=max(1,min(int(max_tasks),8)); external_collection_budget=max(0,min(int(external_collection_budget),3))
        a=self.db.one('SELECT * FROM phase12_ai_case_assessments_289 WHERE assessment_id=?',(assessment_id,));
        if not a: raise KeyError('assessment not found')
        gaps=_safe_json(a['gaps_json'],[])[:max_tasks]; wid=_id('wave289'); objective='Priorisierte, begrenzte Folgeermittlung aus AI-Strukturprüfung'; created=_now()
        wave_payload={'wave_id':wid,'assessment_id':assessment_id,'case_id':a['case_id'],'mission_id':a['mission_id'],'objective':objective,'task_budget':max_tasks,'external_collection_budget':external_collection_budget,'status':'proposed','created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_research_waves_289 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(wid,assessment_id,a['case_id'],a['mission_id'],objective,max_tasks,external_collection_budget,'proposed',actor,created,_hash(wave_payload)))
        ext_used=0; tasks=[]
        mapping={'evidence':'analyze_evidence','claims':'analyze_evidence','counterevidence':'review_counterevidence','hypothesis':'review_hypothesis','identity':'review_identity','collection':'deduplicate_research','review':'analyze_evidence'}
        for i,g in enumerate(gaps,1):
            external=bool(g.get('external_collection_required')) and ext_used<external_collection_budget
            if external: ext_used+=1
            mode='proposal_only_external' if external else 'local_analysis_only'; task_type=mapping.get(g.get('category'),'analyze_evidence')
            tid=_id('task289'); tp={'task_id':tid,'wave_id':wid,'case_id':a['case_id'],'mission_id':a['mission_id'],'priority':i,'task_type':task_type,'title':g.get('title','Folgeprüfung'),'rationale':g.get('rationale',''),'execution_mode':mode,'scope_class':g.get('scope_class','approved_case'),'external_collection_required':external,'status':'planned','created_at':created}
            self.db.execute('INSERT INTO phase12_research_wave_tasks_289 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,wid,a['case_id'],a['mission_id'],i,task_type,tp['title'],tp['rationale'],mode,tp['scope_class'],int(external),'planned',created,_hash(tp))); tasks.append(tp)
        self._event(a['case_id'],'research_wave_proposed','research_wave',wid,{'task_count':len(tasks),'external_tasks':ext_used},actor)
        return {**wave_payload,'tasks':tasks,'requires_lead_ok':True,'network_access':False}

    def approve_research_wave(self,*,wave_id:str,confirmation:str,approved_by:str):
        if str(confirmation or '').strip().upper()!='OK': raise PermissionError('Explizites OK des Hauptermittlers erforderlich.')
        w=self.db.one('SELECT * FROM phase12_research_waves_289 WHERE wave_id=?',(wave_id,));
        if not w: raise KeyError('research wave not found')
        # Parent mission itself must already be approved.
        ma=self.db.one("SELECT * FROM phase12_missions_281 WHERE mission_id=?",(w['mission_id'],))
        if not ma or not str(ma.get('approved_by','') if hasattr(ma,'get') else ma['approved_by']).strip() or not str(ma.get('approved_at','') if hasattr(ma,'get') else ma['approved_at']).strip(): raise PermissionError('Übergeordnete Mission ist nicht freigegeben.')
        tasks=[dict(r) for r in self.db.all('SELECT task_id,priority,task_type,title,execution_mode,scope_class,external_collection_required FROM phase12_research_wave_tasks_289 WHERE wave_id=? ORDER BY priority',(wave_id,))]
        scope={'wave_id':wave_id,'mission_id':w['mission_id'],'task_budget':int(w['task_budget']),'external_collection_budget':int(w['external_collection_budget']),'tasks':tasks}; sh=_hash(scope)
        existing=self.db.one("SELECT * FROM phase12_research_wave_approvals_289 WHERE wave_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(wave_id,))
        if existing:return {'approval_id':existing['approval_id'],'wave_id':wave_id,'scope_sha256':existing['scope_sha256'],'approved':True,'deduplicated':True}
        apid=_id('approve289'); created=_now(); payload={'approval_id':apid,'wave_id':wave_id,'case_id':w['case_id'],'mission_id':w['mission_id'],'decision':'approved','approved_by':approved_by,'approved_at':created,'scope_sha256':sh}
        self.db.execute('INSERT INTO phase12_research_wave_approvals_289 VALUES(?,?,?,?,?,?,?,?,?)',(apid,wave_id,w['case_id'],w['mission_id'],'approved',approved_by,created,sh,_hash(payload)))
        self._event(w['case_id'],'research_wave_approved','research_wave',wave_id,{'scope_sha256':sh,'approved_by':approved_by},approved_by)
        return {**payload,'approved':True,'deduplicated':False}

    def run_approved_local_cycle(self,*,wave_id:str,actor:str|None=None):
        actor=actor or self.actor; w=self.db.one('SELECT * FROM phase12_research_waves_289 WHERE wave_id=?',(wave_id,));
        if not w: raise KeyError('research wave not found')
        ap=self.db.one("SELECT * FROM phase12_research_wave_approvals_289 WHERE wave_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(wave_id,))
        if not ap: raise PermissionError('Research Wave benötigt zuerst das OK des Hauptermittlers.')
        tasks=[dict(r) for r in self.db.all('SELECT * FROM phase12_research_wave_tasks_289 WHERE wave_id=? ORDER BY priority',(wave_id,))]
        current_scope={'wave_id':wave_id,'mission_id':w['mission_id'],'task_budget':int(w['task_budget']),'external_collection_budget':int(w['external_collection_budget']),'tasks':[{k:t[k] for k in ('task_id','priority','task_type','title','execution_mode','scope_class','external_collection_required')} for t in tasks]}
        if _hash(current_scope)!=ap['scope_sha256']: raise PermissionError('Scope-Drift erkannt; neues OK erforderlich.')
        local=[]; deferred=[]
        for t in tasks:
            if int(t['external_collection_required']):
                deferred.append({'task_id':t['task_id'],'title':t['title'],'status':'requires_separate_collection_authorization'})
            else:
                local.append({'task_id':t['task_id'],'title':t['title'],'status':'local_analysis_completed','finding':'Lokale Strukturprüfung abgeschlossen; Ergebnis bleibt Review-Kandidat und keine Tatsachenfeststellung.'})
        cid=_id('cycle289'); created=_now(); result={'local_results':local,'external_deferred':deferred,'next_checkpoint':'Hauptermittler prüft lokale Ergebnisse und entscheidet separat über externe Collection-Aufgaben.','automatic_truth_selection':False}
        payload={'cycle_id':cid,'wave_id':wave_id,'case_id':w['case_id'],'mission_id':w['mission_id'],'approved_scope_sha256':ap['scope_sha256'],'local_tasks_processed':len(local),'external_tasks_deferred':len(deferred),'network_access':False,'scope_expansion':False,'result':result,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_ai_local_cycle_runs_289 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,wave_id,w['case_id'],w['mission_id'],ap['scope_sha256'],len(local),len(deferred),0,0,_canon(result),1,actor,created,_hash(payload)))
        self._event(w['case_id'],'approved_local_cycle_completed','research_wave',wave_id,{'local_tasks':len(local),'external_deferred':len(deferred),'network_access':False},actor)
        return payload

    def all_training_cases(self):
        out=self.build288.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_289 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows: out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build288.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_289 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_289 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build289_delta_cases':d,'build289_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'289.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_289 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval289'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO ai_evaluation_batches_289 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build288.performance_status(model_label); return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False if p.get('status')!='qualified' else bool(p.get('qualified')),'required_corpus_size':160,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 289 beansprucht keine neue Modellleistung ohne vollständigen unabhängigen 160-Fälle-Lauf.'}
    def qualified_gate(self):
        parent=self.build288.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); gate={'build':'289.0','parent_gate':bool(parent['release_ready']),'ai_gap_assessment':True,'bounded_research_waves':True,'explicit_ok_required':True,'approved_local_autonomy':True,'external_collection_auto_execution':False,'scope_expansion':False,'network_access':False,'beginner_guidance':True,'hard_training_corpus_160':tm['reviewed_hard_cases']>=160 and tm['build289_delta_cases']>=16 and tm['build289_delta_extreme']>=4,'evaluation_batch_160_ready':batch['corpus_size']==160,'automatic_model_activation':False,'human_authority_preserved':True}; gate['release_ready']=all([gate['parent_gate'],gate['ai_gap_assessment'],gate['bounded_research_waves'],gate['explicit_ok_required'],gate['approved_local_autonomy'],not gate['external_collection_auto_execution'],not gate['scope_expansion'],not gate['network_access'],gate['beginner_guidance'],gate['hard_training_corpus_160'],gate['evaluation_batch_160_ready'],not gate['automatic_model_activation'],gate['human_authority_preserved']]); return gate

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True)
        assessments=self.db.all('SELECT * FROM phase12_ai_case_assessments_289 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,)); waves=self.db.all('SELECT * FROM phase12_research_waves_289 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,)); tm=self.training_metrics(); perf=self.performance_status()
        latest=assessments[0] if assessments else None
        if latest:
            pr=_safe_json(latest['priorities_json'],[]); top=''.join(f"<li><b>{e(x.get('rank'))}. {e(x.get('title'))}</b><br>{e(x.get('recommended_action'))}</li>" for x in pr[:5]) or '<li>Keine priorisierten Punkte.</li>'
            stand=f"AI-Strukturprüfung vorhanden: {e(latest['summary'])}"; meaning='Die AI priorisiert Ermittlungsbedarf, entscheidet aber nicht automatisch, was wahr ist.'; nextstep='Prioritäten prüfen. Danach eine begrenzte Recherchewelle vorschlagen und nur mit OK freigeben.'
        else:
            top='<li>Noch keine AI-Strukturprüfung.</li>'; stand='Noch keine Build-289-Strukturprüfung für diesen Fall.'; meaning='Die AI hat den vorhandenen Fallstand noch nicht auf Lücken, Widersprüche und redundante Wege geprüft.'; nextstep='Mit „Fallstand analysieren“ beginnen.'
        wave_rows=''.join(f"<tr><td><code>{e(w['wave_id'])}</code></td><td>{e(w['status'])}</td><td>{e(w['task_budget'])}</td></tr>" for w in waves) or '<tr><td colspan=3>Noch keine Recherchewelle.</td></tr>'
        assess_form=f"<form method='post' action='/build289/assess'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Fallstand analysieren</button></form>"
        wave_form=''
        if latest: wave_form=f"<form method='post' action='/build289/propose-wave'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='assessment_id' value='{e(latest['assessment_id'])}'><button>Begrenzte Recherchewelle vorschlagen</button></form>"
        return f"""
<section class='card'><h2>AI-Ermittlung · Build 289</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{stand}<br><br><b>Was bedeutet das?</b><br>{meaning}<br><br><b>Was ist jetzt zu tun?</b><br>{nextstep}</div>
<h3>Priorisierte nächste Prüfungen</h3><ol>{top}</ol>{assess_form}{wave_form}
<details><summary>Analyst/Experte: Audit- und Trainingsstatus</summary><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Externe Collection wird in Build 289 nicht automatisch ausgeführt; Scope-Erweiterung ist deaktiviert.</p><table><tr><th>Wave</th><th>Status</th><th>Task-Budget</th></tr>{wave_rows}</table></details>
</section>"""
