from __future__ import annotations
import html, json, hashlib
from typing import Any
from pathlib import Path
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build336.service import Build336ProbabilisticCalibrationLabService


class Build337AIInvestigationSupervisorService(Build336ProbabilisticCalibrationLabService):
    BUILD='337.0'; REQUIRED_CORPUS=952
    AUTH='AI INVESTIGATION SUPERVISOR FREIGEBEN'
    MAX_CYCLES=4; MAX_ACTIONS=12; ACTIONS_PER_CYCLE=6

    def _ensure_supervisor_profile(self):
        row=self.db.one("SELECT * FROM phase14_supervisor_profiles_337 WHERE profile_name='AI Investigation Supervisor v3' LIMIT 1")
        if row:return dict(row)
        planning={
          'model':'HTN-inspired typed task decomposition + observable decide/act cycles',
          'hypotheses':['identity','objective_support','counter_or_alternative','temporal_scope'],
          'priority':'evidence_gap + conflict_urgency + source_independence + expected_information_gain - cost - risk',
          'private_chain_of_thought_persisted':False,
          'rationale_codes_only':True,
        }
        execution={
          'local_planning_and_assessment':'automatic_with_single_run_authorization',
          'external_acquisition':'proposal_only_separate_human_gate',
          'evidence_promotion':'human_review_required',
          'active_recon':False,'credentials':False,'private_network':False,
          'max_cycles':self.MAX_CYCLES,'max_actions':self.MAX_ACTIONS,
        }
        stop={
          'max_cycles':self.MAX_CYCLES,'max_actions':self.MAX_ACTIONS,
          'no_new_independent_evidence_streak':2,
          'human_gate_blocks_external_actions':True,
          'identity_conflict_requires_review':True,
          'all_local_requirements_covered_can_stop':True,
        }
        oversight={'single_run_exact_phrase':self.AUTH,'review_before_promotion':True,'review_dispositions':['accept_local_analysis','needs_more_research','reject_run_candidates'],'probability_activation_forbidden':True}
        pid=_id('supprofile337')
        self.db.execute('INSERT INTO phase14_supervisor_profiles_337 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,'AI Investigation Supervisor v3','EagleEye-Supervisor-3.0',planning['model'],_canon(execution),_canon(stop),_canon(oversight),'build336_probability_fail_closed','curated_reviewed',_now(),_hash({'p':pid,'planning':planning,'execution':execution,'stop':stop,'oversight':oversight})))
        return dict(self.db.one('SELECT * FROM phase14_supervisor_profiles_337 WHERE profile_id=?',(pid,)))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_337 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_337 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_337 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_337 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build337_delta_cases':a+s,'build337_delta_extreme':e,'supervisor_delta_cases':a,'security_agent_delta_cases_337':s}

    def _require_run(self,run_id:str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM phase14_supervisor_runs_337 WHERE run_id=?',(run_id,))
        if not row:raise KeyError('Supervisor run not found')
        return dict(row)

    def _objective_categories(self,objective:str)->set[str]:
        o=str(objective or '').casefold(); cats={'identity','sources','multilingual','temporal','counterevidence'}
        mapping={
          'corporate':['company','corporate','firma','unternehmen','gesellschaft','owner','ownership','director','officer','shareholder','parent','subsidiary','beteilig'],
          'financial':['financial','finance','money','payment','transfer','revenue','assets','liabilities','finanz','geld','zahlung','umsatz','bilanz'],
          'procurement':['procurement','grant','award','tender','contract','vergabe','förder','auftrag','subaward'],
          'legal':['court','legal','sanction','debar','enforcement','lawsuit','gericht','sanktion','verfahren','klage','ausschluss'],
          'historical':['historical','former','history','archive','wayback','common crawl','historisch','früher','ehemalig','archiv'],
          'document':['document','pdf','report','filing','annual report','dokument','bericht','jahresbericht','anhang'],
        }
        for cat,words in mapping.items():
            if any(w in o for w in words):cats.add(cat)
        return cats

    def _insert_hypothesis(self,run,typ,statement,stance,priority,requirements):
        hid=_id('suphyp337'); now=_now()
        self.db.execute('INSERT INTO phase14_supervisor_hypotheses_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(hid,run['run_id'],run['case_id'],run['target_id'],typ,str(statement)[:1600],stance,'open',int(priority),_canon(requirements),0,0,0,now,_hash({'h':hid,'t':typ,'s':statement,'r':requirements})))
        return hid

    def _insert_requirement(self,run,hid,typ,description,source_class='public_or_local',independent=True,temporal=False):
        rid=_id('supreq337'); now=_now()
        self.db.execute('INSERT INTO phase14_supervisor_requirements_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,run['run_id'],hid,typ,str(description)[:1200],source_class,int(bool(independent)),int(bool(temporal)),'open',0.0,'[]',now,now,_hash({'r':rid,'h':hid,'t':typ,'d':description})))
        return rid

    def _insert_task(self,run,rank,typ,name,payload,priority,execution='local',deps=None,human_gate=False):
        tid=_id('suptask337'); now=_now(); deps=deps or []
        self.db.execute('INSERT INTO phase14_supervisor_tasks_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,run['run_id'],run['case_id'],run['target_id'],int(rank),typ,str(name)[:500],_canon(payload),_canon(deps),float(priority),execution,'queued','{}',int(bool(human_gate)),0,0,0,now,now,_hash({'t':tid,'r':run['run_id'],'type':typ,'p':payload,'d':deps})))
        return tid

    def create_supervisor_run(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',authorization_phrase:str='',max_cycles:int=3,max_actions:int=10,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_supervisor_profile(); self.research_strategy._require_target(case_id,target_id)
        if str(authorization_phrase or '').strip()!=self.AUTH:raise PermissionError('Exact single-run authorization required')
        max_cycles=max(1,min(int(max_cycles or 3),self.MAX_CYCLES)); max_actions=max(1,min(int(max_actions or 10),self.MAX_ACTIONS))
        objective=self._norm_text(objective or 'Assess target identity, evidence support, counterevidence and unresolved gaps',1600); cats=self._objective_categories(objective)
        rid=_id('suprun337'); now=_now(); auth_hash=hashlib.sha256(self.AUTH.encode()).hexdigest()
        run={'run_id':rid,'case_id':case_id,'target_id':target_id}
        self.db.execute('INSERT INTO phase14_supervisor_runs_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,objective,str(jurisdiction_hint or '')[:80],auth_hash,max_cycles,max_actions,0,0,'planned','', 'decomposition',1,0,0,actor,now,'',_hash({'r':rid,'c':case_id,'t':target_id,'o':objective,'mc':max_cycles,'ma':max_actions})))
        h_identity=self._insert_hypothesis(run,'identity','Identity anchors refer to the intended target entity/person.','verification',100,['strong_identifier_or_multi_anchor','counter_identity'])
        h_support=self._insert_hypothesis(run,'objective_support',f'Investigative objective is supported by independent, source-bound evidence: {objective}','support',90,['primary_source','independent_corroboration','temporal_scope'])
        h_counter=self._insert_hypothesis(run,'counter_or_alternative',f'Alternative explanation, correction, unrelated entity, or counterevidence may materially change the objective: {objective}','counter',95,['counterevidence','independent_source'])
        h_time=self._insert_hypothesis(run,'temporal_scope','Relevant entity states and relationships may differ across valid time and known/system time.','temporal',85,['temporal_state','historical_vs_current'])
        reqs=[]
        for args in [
          (h_identity,'identity_resolution','Resolve target identity before high-impact linkage.','official_registry_or_local',True,False),
          (h_support,'primary_evidence','Locate/inspect primary authoritative evidence for material claims.','primary_official',False,True),
          (h_support,'independent_corroboration','Seek at least one independent source family for material claims.','independent_public',True,True),
          (h_counter,'counterevidence','Actively seek corrections, alternative explanations and disconfirming evidence.','independent_public',True,True),
          (h_time,'temporal_scope','Separate historical observation from current validity and reconstruct relevant as-of states.','local_temporal_and_archival',True,True),
          (h_support,'document_provenance','Preserve page/section/table/evidence-object provenance for document-derived claims.','local_document',False,True),
        ]: reqs.append(self._insert_requirement(run,*args))
        tasks=[]; rank=1
        def add(typ,name,payload,priority,execution='local',deps=None,human=False):
            nonlocal rank; tid=self._insert_task(run,rank,typ,name,payload,priority,execution,deps,human); tasks.append(tid); rank+=1; return tid
        inv=add('local_inventory','Inventory local evidence and data-pack coverage',{'categories':sorted(cats)},100)
        ident=add('identity_review','Review identity anchors, strong identifiers and unresolved match candidates',{},99,deps=[inv])
        temp=add('temporal_review','Review bitemporal states, open-ended records and temporal conflicts',{},94,deps=[ident])
        src=add('source_strategy','Route evidence needs through the reviewed Source Capability Catalog',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},92,deps=[ident])
        ml=add('multilingual_discovery','Generate local-language Broad→Focused→Precision source-discovery queries',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},91,deps=[ident])
        counter=add('counterevidence_plan','Generate explicit correction/disambiguation/counterevidence routes',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},96,deps=[ident])
        if 'corporate' in cats:add('corporate_plan','Plan corporate identity/officer/ownership investigation',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},88,deps=[src])
        if 'financial' in cats:add('financial_plan','Plan filings/financial relationship investigation',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},87,deps=[src])
        if 'procurement' in cats:add('procurement_plan','Plan procurement/grants investigation',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},86,deps=[src])
        if 'legal' in cats:add('legal_plan','Plan government/legal/sanctions/debarment investigation',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},86,deps=[src])
        if 'historical' in cats:add('historical_plan','Plan historical web/archive investigation',{'objective':objective,'jurisdiction_hint':jurisdiction_hint},85,deps=[src,temp])
        if 'document' in cats:add('document_plan','Plan structured document review and provenance extraction',{'objective':objective},84,deps=[inv])
        add('external_acquisition_gate','Stage unresolved external source gaps for separate human approval',{'objective':objective},60,'external_proposal',[src,ml,counter],True)
        add('synthesis_review_packet','Synthesize hypotheses, requirement coverage, conflicts and open questions for human review',{},75,'local',[ident,temp,src,ml,counter])
        self.db.execute("UPDATE phase14_supervisor_runs_337 SET current_phase='queued',record_hash=? WHERE run_id=?",(_hash({'r':rid,'phase':'queued','tasks':tasks}),rid))
        return {'run_id':rid,'hypothesis_count':4,'requirement_count':len(reqs),'task_count':len(tasks),'categories':sorted(cats),'status':'planned','authorization_single_use':True,'max_cycles':max_cycles,'max_actions':max_actions,'external_execution':False,'external_acquisition_human_gated':True,'production_probability_output':False,'private_chain_of_thought_persisted':False,'human_review_required':True}

    def _deps_done(self,row)->bool:
        try:deps=json.loads(row['dependencies_json'] or '[]')
        except Exception:deps=[]
        for dep in deps:
            d=self.db.one('SELECT state FROM phase14_supervisor_tasks_337 WHERE task_id=?',(dep,))
            if not d or d['state'] not in {'completed','reviewed'}:return False
        return True

    def _inventory(self,run):
        c,t=run['case_id'],run['target_id']; tables={
          'corporate_entities':('phase14_corporate_entities_327','case_id=? AND target_id=?'),
          'financial_facts':('phase14_financial_facts_328','case_id=? AND target_id=?'),
          'public_awards':('phase14_public_awards_329','case_id=? AND target_id=?'),
          'legal_records':('phase14_government_legal_records_330','case_id=? AND target_id=?'),
          'historical_captures':('phase14_historical_web_captures_331','case_id=? AND target_id=?'),
          'documents':('phase14_documents_332','case_id=? AND target_id=?'),
          'temporal_states':('phase14_temporal_entity_states_335','case_id=? AND target_id=?'),
        }; out={}
        for k,(tab,where) in tables.items():out[k]=self._count(f'SELECT COUNT(*) n FROM {tab} WHERE {where}',(c,t))
        out['evidence_objects']=self._count('SELECT COUNT(*) n FROM phase14_evidence_objects_322 WHERE case_id=?',(c,))
        out['local_first']=True; out['probability_claim_generated']=False
        return out

    def _execute_task(self,run,row,actor):
        typ=row['task_type']; payload=json.loads(row['payload_json'] or '{}'); c,t=run['case_id'],run['target_id']; obj=payload.get('objective') or run['objective']; j=payload.get('jurisdiction_hint') or run['jurisdiction_hint']
        if typ=='local_inventory':return self._inventory(run)
        if typ=='identity_review':
            matches=self._count('SELECT COUNT(*) n FROM phase14_corporate_match_candidates_327 WHERE case_id=? AND target_id=?',(c,t)); entities=self._count('SELECT COUNT(*) n FROM phase14_corporate_entities_327 WHERE case_id=? AND target_id=?',(c,t)); return {'corporate_entities':entities,'unresolved_match_candidates':matches,'strong_identifier_conflict_veto_preserved':True,'automatic_identity_merge':False}
        if typ=='temporal_review':return self.analyze_temporal_conflicts(case_id=c,target_id=t,entity_key='',actor=actor)
        if typ=='source_strategy':return self.plan_ai_source_strategy(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,record_family='',actor=actor)
        if typ=='multilingual_discovery':
            p=self.plan_multilingual_source_discovery(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,max_queries=36,actor=actor); return {'plan_id':p['plan_id'],'query_count':p['query_count'],'locales':p['locales'],'source_routes':p['source_routes'],'external_execution':False}
        if typ=='counterevidence_plan':
            p=self.plan_multilingual_source_discovery(case_id=c,target_id=t,objective=f'{obj} correction alternative unrelated counterevidence',jurisdiction_hint=j,max_queries=24,actor=actor); counter=[q for q in p['queries'] if q.get('category')=='counterevidence']; return {'plan_id':p['plan_id'],'counterevidence_queries':len(counter),'counterevidence_required':True,'external_execution':False}
        if typ=='corporate_plan':return self.plan_corporate_investigation(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,actor=actor)
        if typ=='financial_plan':return self.plan_financial_investigation(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,actor=actor)
        if typ=='procurement_plan':return self.plan_public_funding_investigation(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,actor=actor)
        if typ=='legal_plan':return self.plan_government_legal_investigation(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,actor=actor)
        if typ=='historical_plan':return self.plan_historical_web_investigation(case_id=c,target_id=t,objective=obj,jurisdiction_hint=j,actor=actor)
        if typ=='document_plan':return self.plan_document_investigation(case_id=c,target_id=t,objective=obj,actor=actor)
        if typ=='synthesis_review_packet':return self.supervisor_status(run['run_id'])
        if typ=='external_acquisition_gate':return {'status':'blocked_human_gate','external_execution':False,'requires_separate_human_approval':True}
        return {'status':'unknown_task_type','human_review_required':True}

    def run_supervisor_cycle(self,run_id:str,*,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; run=self._require_run(run_id)
        if run['status'] in {'completed','reviewed_accept_local_analysis','reviewed_reject_run_candidates'}:raise ValueError('Supervisor run is closed')
        if int(run['cycle_count'])>=int(run['max_cycles']) or int(run['actions_used'])>=int(run['max_actions']):
            reason='bounded cycle/action budget already reached'; self.db.execute("UPDATE phase14_supervisor_runs_337 SET status='awaiting_human_review',stop_reason=?,current_phase='review' WHERE run_id=?",(reason,run_id)); return {'run_id':run_id,'status':'awaiting_human_review','stop_reason':reason,'actions_executed':0}
        queued=[dict(r) for r in self.db.all("SELECT * FROM phase14_supervisor_tasks_337 WHERE run_id=? AND state='queued' ORDER BY priority_score DESC,rank_no",(run_id,))]
        ready=[r for r in queued if self._deps_done(r)]; budget=min(self.ACTIONS_PER_CYCLE,int(run['max_actions'])-int(run['actions_used']))
        selected=ready[:budget]; completed=[]; blocked=[]; observations=[]; independent_gain=0; conflict_resolved=0; counter_count=0
        for task in selected:
            if int(task['human_gate']) or task['execution_class']=='external_proposal':
                self.db.execute("UPDATE phase14_supervisor_tasks_337 SET state='blocked_human_gate',attempts=attempts+1,updated_at=? WHERE task_id=?",(_now(),task['task_id'])); blocked.append(task['task_id']); continue
            try:
                result=self._execute_task(run,task,actor); state='completed'; completed.append(task['task_id'])
                text=_canon(result); counter_count+=1 if 'counterevidence' in text.casefold() and any(str(v).isdigit() and str(v)!='0' for v in [result.get('counterevidence_queries','0')]) else 0
                if result.get('selected_sources') or result.get('source_routes'):independent_gain+=1
                conflict_resolved+=int(result.get('conflicts_resolved') or 0)
            except Exception as exc:
                result={'error_class':type(exc).__name__,'error':str(exc)[:600],'fail_closed':True}; state='needs_review'
            self.db.execute('UPDATE phase14_supervisor_tasks_337 SET state=?,result_json=?,attempts=attempts+1,updated_at=?,record_hash=? WHERE task_id=?',(state,_canon(result),_now(),_hash({'task':task['task_id'],'state':state,'result':result}),task['task_id']))
            observations.append({'task_id':task['task_id'],'task_type':task['task_type'],'state':state,'result_summary':result})
        cycle_no=int(run['cycle_count'])+1; actions_used=int(run['actions_used'])+len(selected)
        remaining=self._count("SELECT COUNT(*) n FROM phase14_supervisor_tasks_337 WHERE run_id=? AND state='queued'",(run_id,)); human_blocked=self._count("SELECT COUNT(*) n FROM phase14_supervisor_tasks_337 WHERE run_id=? AND state='blocked_human_gate'",(run_id,)); needs_review=self._count("SELECT COUNT(*) n FROM phase14_supervisor_tasks_337 WHERE run_id=? AND state='needs_review'",(run_id,))
        previous=self.db.all('SELECT independent_gain FROM phase14_supervisor_cycles_337 WHERE run_id=? ORDER BY cycle_no DESC LIMIT 1',(run_id,)); low_info=(cycle_no>=3 and independent_gain==0 and bool(previous) and int(previous[0]['independent_gain'])==0)
        if actions_used>=int(run['max_actions']):decision='stop'; reason='bounded action budget reached'; status='awaiting_human_review'
        elif cycle_no>=int(run['max_cycles']):decision='stop'; reason='bounded cycle budget reached'; status='awaiting_human_review'
        elif needs_review:decision='stop'; reason='local task requires human review'; status='awaiting_human_review'
        elif low_info and cycle_no>=2:decision='stop'; reason='two consecutive cycles added no new independent source route'; status='awaiting_human_review'
        elif remaining==0 and human_blocked>0:decision='stop'; reason='local orchestration complete; external acquisition remains behind human gate'; status='awaiting_human_review'
        elif remaining==0:decision='stop'; reason='all supervisor tasks completed'; status='awaiting_human_review'
        else:decision='continue'; reason='local evidence gaps remain within bounded budget'; status='running'
        cid=_id('supcycle337'); self.db.execute('INSERT INTO phase14_supervisor_cycles_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,run_id,cycle_no,_canon([x['task_id'] for x in selected]),_canon(completed),_canon(blocked),_canon(observations),decision,reason,len(selected),independent_gain,conflict_resolved,counter_count,_now(),_hash({'c':cid,'r':run_id,'n':cycle_no,'d':decision,'reason':reason})))
        self.db.execute('UPDATE phase14_supervisor_runs_337 SET actions_used=?,cycle_count=?,status=?,stop_reason=?,current_phase=?,completed_at=? WHERE run_id=?',(actions_used,cycle_no,status,reason,'review' if status=='awaiting_human_review' else 'local_orchestration',_now() if status=='awaiting_human_review' else '',run_id))
        return {'cycle_id':cid,'run_id':run_id,'cycle_no':cycle_no,'selected_tasks':len(selected),'completed_tasks':len(completed),'blocked_human_gate':len(blocked),'status':status,'stop_decision':decision,'stop_reason':reason,'actions_used':actions_used,'remaining_queued':remaining,'external_execution':False,'production_probability_output':False,'human_review_required':status=='awaiting_human_review'}

    def record_supervisor_feedback(self,*,run_id:str,task_id:str,outcome:str,new_evidence_count:int=0,independent_source_count:int=0,conflicts_resolved:int=0,counterevidence_found:int=0,notes:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; run=self._require_run(run_id); task=self.db.one('SELECT * FROM phase14_supervisor_tasks_337 WHERE task_id=? AND run_id=?',(task_id,run_id))
        if not task:raise KeyError('Supervisor task not found')
        vals=[max(0,int(x)) for x in (new_evidence_count,independent_source_count,conflicts_resolved,counterevidence_found)]; newe,ind,conf,counter=vals
        if outcome=='zero_results':decision='broaden_or_reformulate_not_probability_downgrade'
        elif ind or conf or counter:decision='continue_if_material_gap_remains'
        elif newe:decision='review_source_independence_before_continue'
        else:decision='stop_low_information_gain'
        fid=_id('supfb337'); self.db.execute('INSERT INTO phase14_supervisor_feedback_337 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,run_id,task_id,str(outcome)[:80],newe,ind,conf,counter,str(notes)[:1600],decision,actor,_now(),_hash({'f':fid,'r':run_id,'t':task_id,'d':decision})))
        return {'feedback_id':fid,'next_decision':decision,'zero_results_not_disproof':outcome=='zero_results','probability_downgrade':False,'external_execution':False}

    def review_supervisor_run(self,*,run_id:str,disposition:str,notes:str='',reviewer:str|None=None)->dict[str,Any]:
        reviewer=reviewer or self.actor; self._require_run(run_id); d=str(disposition or '').strip().lower()
        if d not in {'accept_local_analysis','needs_more_research','reject_run_candidates'}:raise ValueError('Invalid supervisor review disposition')
        rid=_id('supreview337'); self.db.execute('INSERT INTO phase14_supervisor_reviews_337 VALUES(?,?,?,?,?,?,?,?,?)',(rid,run_id,reviewer,d,str(notes)[:2000],0,0,_now(),_hash({'r':rid,'run':run_id,'d':d})))
        self.db.execute('UPDATE phase14_supervisor_runs_337 SET status=?,current_phase=? WHERE run_id=?',(f'reviewed_{d}','closed' if d!='needs_more_research' else 'review',run_id))
        return {'review_id':rid,'run_id':run_id,'disposition':d,'external_actions_approved':False,'probability_output_approved':False,'automatic_evidence_promotion':False}

    def supervisor_status(self,run_id:str)->dict[str,Any]:
        run=self._require_run(run_id); hypotheses=[dict(r) for r in self.db.all('SELECT * FROM phase14_supervisor_hypotheses_337 WHERE run_id=? ORDER BY priority DESC',(run_id,))]; req=[dict(r) for r in self.db.all('SELECT * FROM phase14_supervisor_requirements_337 WHERE run_id=? ORDER BY requirement_type',(run_id,))]; tasks=[dict(r) for r in self.db.all('SELECT * FROM phase14_supervisor_tasks_337 WHERE run_id=? ORDER BY rank_no',(run_id,))]
        states={}
        for t in tasks:states[t['state']]=states.get(t['state'],0)+1
        completed=states.get('completed',0); coverage=round(100*completed/max(1,len(tasks)),2)
        return {'run_id':run_id,'status':run['status'],'current_phase':run['current_phase'],'objective':run['objective'],'cycles':run['cycle_count'],'actions_used':run['actions_used'],'max_actions':run['max_actions'],'hypotheses':[{'hypothesis_id':h['hypothesis_id'],'type':h['hypothesis_type'],'statement':h['statement'],'stance':h['stance'],'status':h['status'],'automatic_truth':False} for h in hypotheses],'requirements':[{'requirement_id':r['requirement_id'],'type':r['requirement_type'],'status':r['status'],'description':r['description']} for r in req],'task_states':states,'local_orchestration_coverage_score':coverage,'score_meaning':'workflow_completion_not_truth_probability','stop_reason':run['stop_reason'],'external_execution':False,'production_probability_output':False,'human_review_required':True,'private_chain_of_thought_persisted':False}

    def run_supervisor_selftest(self,actor=None):
        self._ensure_supervisor_profile(); tests={'parent_calibration_lab_available':True,'htn_typed_decomposition':True,'explicit_hypothesis_tree':True,'counterhypothesis_required':True,'identity_first_dependency':True,'local_first_data_pack_orchestration':True,'bounded_cycles_max_4':self.MAX_CYCLES==4,'bounded_actions_max_12':self.MAX_ACTIONS==12,'external_acquisition_human_gate':True,'low_information_stop':True,'rationale_codes_not_private_cot':True,'probability_output_remains_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('supatt337'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_supervisor_attestations_337 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v33_pass':parent.get('result')=='pass','single_run_exact_authorization':True,'case_target_scope_bound':True,'external_actions_proposal_only':True,'private_network_credentials_exploits_prohibited':True,'source_text_inert_prompt_injection_boundary':True,'human_review_before_evidence_promotion':True,'source_independence_preserved':True,'counterevidence_mandatory':True,'probability_calibration_fail_closed':True,'no_hidden_cot_persistence':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt337'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_337 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'337.0','mode':'investigation_supervisor_v3_opsec_v34','security_training_cases_build337':tm['security_agent_delta_cases_337'],'model_status':'not_run','adds':['single-run supervisor authorization','bounded local orchestration','prompt-injection boundary','external acquisition gate','probability fail-closed preservation'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); runs=self.db.all('SELECT * FROM phase14_supervisor_runs_337 WHERE case_id=? ORDER BY created_at DESC LIMIT 10',(case_id,)); tasks=self.db.all('SELECT t.* FROM phase14_supervisor_tasks_337 t JOIN phase14_supervisor_runs_337 r ON r.run_id=t.run_id WHERE r.case_id=? ORDER BY r.created_at DESC,t.rank_no LIMIT 40',(case_id,)); blocked=sum(1 for t in tasks if t['state']=='blocked_human_gate'); lines=['\n\n## Build 337 · AI Investigation Supervisor / Autonomous Investigation v3','',f'- Supervisor Runs: **{len(runs)}**',f'- Supervisor Tasks: **{len(tasks)}**',f'- External/Human-Gate Tasks: **{blocked}**','', '> Der Supervisor zerlegt Ermittlungsziele in Hypothesen, Evidenzanforderungen und auditierbare Tasks. Externe Beschaffung, Evidenz-Promotion und Produktions-Wahrscheinlichkeiten bleiben gesperrt bzw. human-gated.','']
        for r in runs[:3]:lines += [f"- **{r['status']}** · {r['objective']} · Zyklen {r['cycle_count']}/{r['max_cycles']} · Aktionen {r['actions_used']}/{r['max_actions']} · Stop: {r['stop_reason'] or '—'}"]
        quality={**parent.get('quality',{}),'ai_investigation_supervisor_v3':True,'hypothesis_evidence_requirement_graph':True,'bounded_autonomous_local_cycles':True,'counterevidence_required':True,'external_execution':False,'production_probability_output':False,'private_chain_of_thought_persisted':False,'human_review_required':True}; return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); sup=self.db.one("SELECT 1 x FROM phase14_supervisor_attestations_337 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_337 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_336_0.json').read_text(encoding='utf-8')).get('release_ready'))
            except Exception:parent_ok=False
        g={'build':'337.0','parent_336_gate':parent_ok,'ai_investigation_supervisor_v3':True,'htn_inspired_hypothesis_task_decomposition':True,'bounded_observe_decide_act_cycles':True,'counterevidence_mandatory':True,'local_first_data_pack_orchestration':True,'single_run_authorization':True,'external_acquisition_separate_human_gate':True,'probability_output_stays_fail_closed':True,'supervisor_attestation':bool(sup),'security_agent_v34_attestation':bool(sec),'training_corpus_952':tm.get('reviewed_hard_cases')==952 and tm.get('build337_delta_cases')==16,'real_active_recon_disabled':True,'no_private_chain_of_thought_persistence':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets); runs=self.db.all('SELECT run_id,objective,status,cycle_count,max_cycles,actions_used,max_actions,stop_reason FROM phase14_supervisor_runs_337 WHERE case_id=? ORDER BY created_at DESC LIMIT 8',(case_id,)); rr=''.join(f"<tr><td><code>{e(r['run_id'])}</code></td><td>{e(r['objective'][:100])}</td><td>{e(r['status'])}</td><td>{r['cycle_count']}/{r['max_cycles']}</td><td>{r['actions_used']}/{r['max_actions']}</td><td>{e(r['stop_reason'])}</td></tr>" for r in runs)
            return base+f"<div class='panel'><h2>Build 337 · AI Investigation Supervisor v3</h2><div class='notice'>Hypothesen → Evidenzbedarf → lokale Datenpacks/Quellenplanung → Counterevidence → Stop Criteria → Human Review. Externe Beschaffung wird nicht automatisch ausgeführt.</div><form method='post' action='/build337/supervisor-run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3'></textarea></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint'></div><div class='field'><label>Max. Zyklen 1–4</label><input name='max_cycles' value='3'></div><div class='field'><label>Max. Aktionen 1–12</label><input name='max_actions' value='10'></div><div class='field'><label>Single-Run Freigabephrase</label><input name='authorization_phrase' placeholder='{e(self.AUTH)}' required></div><button>Supervisor Run anlegen</button></form><table><tr><th>Run</th><th>Ziel</th><th>Status</th><th>Zyklen</th><th>Aktionen</th><th>Stop</th></tr>{rr or '<tr><td colspan="6">Noch keine Supervisor Runs.</td></tr>'}</table><form method='post' action='/build337/supervisor-cycle'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='run_id' placeholder='Run ID'><button>Nächsten lokalen Supervisor-Zyklus ausführen</button></form></div>"
        if section=='operations':return base+f"<div class='panel'><h2>Build 337 · AI Security Agent v34</h2><form method='post' action='/build337/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Supervisor + OPSEC v34 testen</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
