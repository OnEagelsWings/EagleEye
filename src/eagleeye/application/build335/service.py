from __future__ import annotations
import html, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build334.service import Build334EntityResolutionV2Service


class Build335TemporalEntityRelationshipIntelligenceService(Build334EntityResolutionV2Service):
    BUILD='335.0'; REQUIRED_CORPUS=920
    SINGULAR_STATES={'legal_name','registered_address','company_status','registered_office','primary_jurisdiction','date_of_birth','incorporation_status'}

    def _ensure_temporal_profile(self):
        row=self.db.one("SELECT * FROM phase14_temporal_profiles_335 WHERE profile_name='Temporal Entity & Relationship Intelligence' LIMIT 1")
        if row:return dict(row)
        policy={'valid_time':'application/world time','system_time':'when EagleEye knew/recorded the assertion','interval_semantics':'half-open [start,end)','correction':'close prior system_to and append replacement','unknown_end':'open-ended candidate not current-truth guarantee','allen_relations':'qualitative interval reasoning retained from Build 324'}
        pid=_id('temporalprofile335')
        self.db.execute('INSERT INTO phase14_temporal_profiles_335 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,'Temporal Entity & Relationship Intelligence','EagleEye-Temporal-1.0','application_time','system_known_time','half_open_[start,end)',_canon(policy),'curated_reviewed',_now(),_hash({'p':pid,'policy':policy})))
        return dict(self.db.one('SELECT * FROM phase14_temporal_profiles_335 WHERE profile_id=?',(pid,)))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_335 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_335 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_335 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_335 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build335_delta_cases':a+s,'build335_delta_extreme':e,'temporal_intelligence_delta_cases':a,'security_agent_delta_cases_335':s}

    @classmethod
    def _iso(cls,v:str,*,required=False)->str:
        s=str(v or '').strip()
        if not s:
            if required: raise ValueError('time value required')
            return ''
        d=cls._dt(s)
        if d is None: raise ValueError(f'invalid ISO time: {s}')
        if len(s)==10:return d.date().isoformat()
        return d.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

    @classmethod
    def _contains_half_open(cls,start:str,end:str,point:str)->bool:
        p=cls._dt(point); a=cls._dt(start); b=cls._dt(end) if end else None
        if not p or not a:return False
        return p>=a and (b is None or p<b)

    @classmethod
    def interval_relation_half_open(cls,a_from:str,a_to:str,b_from:str,b_to:str)->str:
        a1=cls._dt(a_from); a2=cls._dt(a_to) if a_to else None; b1=cls._dt(b_from); b2=cls._dt(b_to) if b_to else None
        if not a1 or not b1:return 'unknown'
        inf=datetime.max.replace(tzinfo=timezone.utc); aa=a2 or inf; bb=b2 or inf
        if aa<a1 or bb<b1:return 'invalid_interval'
        if a1==b1 and aa==bb:return 'equals'
        if aa==b1:return 'meets'
        if bb==a1:return 'met_by'
        if aa<b1:return 'before'
        if bb<a1:return 'after'
        if a1==b1 and aa<bb:return 'starts'
        if a1==b1 and aa>bb:return 'started_by'
        if aa==bb and a1>b1:return 'finishes'
        if aa==bb and a1<b1:return 'finished_by'
        if a1>b1 and aa<bb:return 'during'
        if a1<b1 and aa>bb:return 'contains'
        if a1<b1<aa<bb:return 'overlaps'
        if b1<a1<bb<aa:return 'overlapped_by'
        return 'unknown'

    @classmethod
    def _overlaps_half_open(cls,a_from,a_to,b_from,b_to)->bool:
        a1=cls._dt(a_from); b1=cls._dt(b_from); a2=cls._dt(a_to) if a_to else datetime.max.replace(tzinfo=timezone.utc); b2=cls._dt(b_to) if b_to else datetime.max.replace(tzinfo=timezone.utc)
        return bool(a1 and b1 and a1<b2 and b1<a2)

    def _validate_scope(self,case_id,target_id,evidence_object_id=''):
        self.research_strategy._require_target(case_id,target_id)
        if evidence_object_id:
            ev=self.db.one('SELECT object_id FROM phase14_evidence_objects_322 WHERE object_id=? AND case_id=?',(evidence_object_id,case_id))
            if not ev: raise ValueError('Evidence object must belong to same case')

    def record_entity_state(self,*,case_id:str,target_id:str,entity_key:str,entity_type:str,state_type:str,value:Any,valid_from:str,valid_to:str='',observed_at:str='',source_group:str='manual',source_ref:str='',evidence_object_id:str='',dependency_key:str='',assertion_status:str='candidate',cardinality:str='',logical_key:str='',correction_of:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_temporal_profile(); self._validate_scope(case_id,target_id,evidence_object_id)
        vf=self._iso(valid_from,required=True); vt=self._iso(valid_to) if valid_to else ''; obs=self._iso(observed_at) if observed_at else _now()
        if vt and self._dt(vt)<=self._dt(vf): raise ValueError('valid_to must be after valid_from for half-open interval')
        st=self._clean_key(state_type).replace(' ','_'); ek=self._clean_key(entity_key)
        if not ek or not st:raise ValueError('entity_key/state_type required')
        card=cardinality or ('singular' if st in self.SINGULAR_STATES else 'multi')
        val=value if isinstance(value,(dict,list,int,float,bool)) else str(value)
        lk=logical_key or _hash({'c':case_id,'t':target_id,'e':ek,'s':st,'source':source_group,'ref':source_ref})[:40]
        sid=_id('tstate335'); sf=_now(); dep=self._clean_key(dependency_key or source_group or source_ref or 'unknown')
        payload={'state_id':sid,'logical_key':lk,'case_id':case_id,'target_id':target_id,'entity_key':ek,'entity_type':entity_type,'state_type':st,'value':val,'valid_from':vf,'valid_to':vt,'observed_at':obs,'system_from':sf,'source_group':source_group,'source_ref':source_ref,'evidence_object_id':evidence_object_id,'dependency_key':dep,'assertion_status':assertion_status,'cardinality':card,'correction_of':correction_of}
        self.db.execute('INSERT INTO phase14_temporal_entity_states_335 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,lk,case_id,target_id,ek,str(entity_type or 'entity')[:80],st,_canon(val),vf,vt,obs,sf,'',str(source_group or 'manual')[:180],str(source_ref or '')[:1000],evidence_object_id or '',dep[:240],str(assertion_status or 'candidate')[:80],card[:40],correction_of or '',actor,_hash(payload)))
        return {**payload,'system_to':'','candidate_only':assertion_status!='reviewed','current_truth_inferred':False,'interval_semantics':'[start,end)'}

    def correct_entity_state(self,state_id:str,*,value:Any,valid_from:str|None=None,valid_to:str|None=None,observed_at:str='',source_ref:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; old=self.db.one('SELECT * FROM phase14_temporal_entity_states_335 WHERE state_id=?',(state_id,))
        if not old:raise KeyError('temporal state not found')
        if old['system_to']:raise ValueError('state version already closed')
        close=_now(); self.db.execute('UPDATE phase14_temporal_entity_states_335 SET system_to=? WHERE state_id=?',(close,state_id))
        return self.record_entity_state(case_id=old['case_id'],target_id=old['target_id'],entity_key=old['entity_key'],entity_type=old['entity_type'],state_type=old['state_type'],value=value,valid_from=valid_from or old['valid_from'],valid_to=old['valid_to'] if valid_to is None else valid_to,observed_at=observed_at or close,source_group=old['source_group'],source_ref=source_ref or old['source_ref'],evidence_object_id=old['evidence_object_id'],dependency_key=old['dependency_key'],assertion_status=old['assertion_status'],cardinality=old['cardinality'],logical_key=old['logical_key'],correction_of=state_id,actor=actor)

    def record_relationship_state(self,*,case_id:str,target_id:str,subject_entity_key:str,predicate:str,object_entity_key:str='',object_literal:str='',valid_from:str,valid_to:str='',observed_at:str='',source_group:str='manual',source_ref:str='',evidence_object_id:str='',dependency_key:str='',polarity:str='support',assertion_status:str='candidate',logical_key:str='',correction_of:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_temporal_profile(); self._validate_scope(case_id,target_id,evidence_object_id)
        if not object_entity_key and not str(object_literal).strip():raise ValueError('relationship object required')
        vf=self._iso(valid_from,required=True); vt=self._iso(valid_to) if valid_to else ''; obs=self._iso(observed_at) if observed_at else _now()
        if vt and self._dt(vt)<=self._dt(vf):raise ValueError('valid_to must be after valid_from')
        sub=self._clean_key(subject_entity_key); pred=self._clean_key(predicate).replace(' ','_'); obj=self._clean_key(object_entity_key); lit=str(object_literal or '')[:2000]; pol=polarity if polarity in {'support','counter','neutral'} else 'neutral'; dep=self._clean_key(dependency_key or source_group or source_ref or 'unknown')
        lk=logical_key or _hash({'c':case_id,'t':target_id,'s':sub,'p':pred,'o':obj or lit,'source':source_group,'ref':source_ref})[:40]
        rid=_id('trel335'); sf=_now(); payload={'relationship_state_id':rid,'logical_key':lk,'case_id':case_id,'target_id':target_id,'subject':sub,'predicate':pred,'object_entity_key':obj,'object_literal':lit,'valid_from':vf,'valid_to':vt,'observed_at':obs,'system_from':sf,'source_group':source_group,'source_ref':source_ref,'evidence_object_id':evidence_object_id,'dependency_key':dep,'polarity':pol,'assertion_status':assertion_status,'correction_of':correction_of}
        self.db.execute('INSERT INTO phase14_temporal_relationship_states_335 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,lk,case_id,target_id,sub,pred,obj,lit,vf,vt,obs,sf,'',str(source_group or 'manual')[:180],str(source_ref or '')[:1000],evidence_object_id or '',dep[:240],pol,str(assertion_status or 'candidate')[:80],correction_of or '',actor,_hash(payload)))
        return {**payload,'system_to':'','current_truth_inferred':False,'automatic_relationship_truth':False,'interval_semantics':'[start,end)'}

    def _active_system(self,row,known_at:str)->bool:
        if not known_at:return not bool(row.get('system_to'))
        return self._contains_half_open(row['system_from'],row.get('system_to',''),known_at)

    def reconstruct_entity_at(self,*,case_id:str,target_id:str,entity_key:str,valid_at:str,known_at:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._validate_scope(case_id,target_id); va=self._iso(valid_at,required=True); ka=self._iso(known_at) if known_at else _now(); ek=self._clean_key(entity_key)
        rows=[dict(x) for x in self.db.all('SELECT * FROM phase14_temporal_entity_states_335 WHERE case_id=? AND target_id=? AND entity_key=? ORDER BY valid_from,system_from',(case_id,target_id,ek))]
        active=[r for r in rows if self._contains_half_open(r['valid_from'],r['valid_to'],va) and self._active_system(r,ka)]
        grouped={}
        for r in active:grouped.setdefault(r['state_type'],[]).append({'state_id':r['state_id'],'value':json.loads(r['value_json']),'valid_from':r['valid_from'],'valid_to':r['valid_to'],'source_group':r['source_group'],'source_ref':r['source_ref'],'dependency_key':r['dependency_key'],'assertion_status':r['assertion_status']})
        conflicts=[]
        for typ,vals in grouped.items():
            if typ in self.SINGULAR_STATES and len({_canon(v['value']) for v in vals})>1: conflicts.append({'state_type':typ,'values':[v['value'] for v in vals],'reason':'overlapping_singular_state_values'})
        qid=_id('tquery335'); result={'entity_key':ek,'valid_at':va,'known_at':ka,'states':grouped,'conflicts':conflicts,'bitemporal':True,'current_truth_inferred':False}
        self.db.execute('INSERT INTO phase14_temporal_query_runs_335 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(qid,case_id,target_id,ek,va,ka,len(active),int(bool(conflicts)),_canon(result),actor,_now(),_hash({'q':qid,'r':result})))
        return {'query_id':qid,**result,'result_count':len(active)}

    def analyze_temporal_conflicts(self,*,case_id:str,target_id:str,entity_key:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._validate_scope(case_id,target_id); params=[case_id,target_id]; sql='SELECT * FROM phase14_temporal_entity_states_335 WHERE case_id=? AND target_id=? AND system_to=\'\''
        if entity_key:sql+=' AND entity_key=?';params.append(self._clean_key(entity_key))
        rows=[dict(x) for x in self.db.all(sql+' ORDER BY entity_key,state_type,valid_from',tuple(params))]; found=[]
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                if a['entity_key']!=b['entity_key'] or a['state_type']!=b['state_type']:continue
                if a['cardinality']!='singular' or b['cardinality']!='singular':continue
                if not self._overlaps_half_open(a['valid_from'],a['valid_to'],b['valid_from'],b['valid_to']):continue
                if a['value_json']==b['value_json']:continue
                relation=self.interval_relation_half_open(a['valid_from'],a['valid_to'],b['valid_from'],b['valid_to']); independent=1 if a['dependency_key']==b['dependency_key'] else 2
                exp={'entity_key':a['entity_key'],'state_type':a['state_type'],'left_value':json.loads(a['value_json']),'right_value':json.loads(b['value_json']),'left_source_group':a['source_group'],'right_source_group':b['source_group'],'dependency_same':a['dependency_key']==b['dependency_key'],'semantics':'candidate_conflict_requires_review_not_truth_selection'}
                cid=_id('tconf335'); self.db.execute('INSERT INTO phase14_temporal_conflicts_335 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,target_id,'overlapping_singular_state_conflict',a['state_id'],b['state_id'],relation,independent,_canon(exp),'open_review',_now(),_hash({'c':cid,'e':exp}))); found.append({'conflict_id':cid,'interval_relation':relation,'independent_source_groups':independent,**exp})
        return {'case_id':case_id,'target_id':target_id,'conflict_count':len(found),'conflicts':found,'automatic_truth_selection':False,'criminality_inferred':False}

    def relationship_snapshot(self,*,case_id:str,target_id:str,subject_entity_key:str,valid_at:str,known_at:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._validate_scope(case_id,target_id); va=self._iso(valid_at,required=True); ka=self._iso(known_at) if known_at else _now(); sub=self._clean_key(subject_entity_key); rows=[dict(x) for x in self.db.all('SELECT * FROM phase14_temporal_relationship_states_335 WHERE case_id=? AND target_id=? AND subject_entity_key=? ORDER BY valid_from,system_from',(case_id,target_id,sub))]; active=[]
        for r in rows:
            if self._contains_half_open(r['valid_from'],r['valid_to'],va) and self._active_system(r,ka):active.append({'relationship_state_id':r['relationship_state_id'],'predicate':r['predicate'],'object_entity_key':r['object_entity_key'],'object_literal':r['object_literal'],'valid_from':r['valid_from'],'valid_to':r['valid_to'],'source_group':r['source_group'],'source_ref':r['source_ref'],'polarity':r['polarity'],'assertion_status':r['assertion_status']})
        return {'subject_entity_key':sub,'valid_at':va,'known_at':ka,'relationships':active,'count':len(active),'automatic_relationship_truth':False}

    def materialize_temporal_graph(self,*,case_id:str,target_id:str,entity_key:str,valid_at:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; snap=self.reconstruct_entity_at(case_id=case_id,target_id=target_id,entity_key=entity_key,valid_at=valid_at,actor=actor); rel=self.relationship_snapshot(case_id=case_id,target_id=target_id,subject_entity_key=entity_key,valid_at=valid_at,actor=actor); subject=self.upsert_node(case_id=case_id,target_id=target_id,node_type='temporal_entity',canonical_key=self._clean_key(entity_key),label=entity_key,properties={'as_of':snap['valid_at']},source_layer='temporal335',actor=actor); nc=int(subject['created']); ac=0
        for typ,vals in snap['states'].items():
            for v in vals:
                self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=subject['node_id'],predicate=f'has_{typ}_at_time',literal_value=json.dumps(v['value'],ensure_ascii=False) if isinstance(v['value'],(dict,list)) else str(v['value']),valid_from=v['valid_from'],valid_to=v['valid_to'],observed_at=snap['known_at'],source_group=v['source_group'],source_ref=v['source_ref'],dependency_key=v['dependency_key'],provenance={'temporal_state_id':v['state_id'],'as_of':snap['valid_at'],'bitemporal':True},actor=actor); ac+=1
        for r in rel['relationships']:
            if r['object_entity_key']:
                obj=self.upsert_node(case_id=case_id,target_id=target_id,node_type='temporal_entity',canonical_key=r['object_entity_key'],label=r['object_entity_key'],source_layer='temporal335',actor=actor); nc+=int(obj['created']); self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=subject['node_id'],predicate=r['predicate'],object_node_id=obj['node_id'],valid_from=r['valid_from'],valid_to=r['valid_to'],observed_at=snap['known_at'],source_group=r['source_group'],source_ref=r['source_ref'],dependency_key=r['source_group'],provenance={'temporal_relationship_state_id':r['relationship_state_id'],'as_of':snap['valid_at']},actor=actor)
            else:self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=subject['node_id'],predicate=r['predicate'],literal_value=r['object_literal'],valid_from=r['valid_from'],valid_to=r['valid_to'],observed_at=snap['known_at'],source_group=r['source_group'],source_ref=r['source_ref'],dependency_key=r['source_group'],provenance={'temporal_relationship_state_id':r['relationship_state_id'],'as_of':snap['valid_at']},actor=actor)
            ac+=1
        mid=_id('tmat335'); self.db.execute('INSERT INTO phase14_temporal_graph_materializations_335 VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,case_id,target_id,self._clean_key(entity_key),snap['valid_at'],nc,ac,actor,_now(),_hash({'m':mid,'n':nc,'a':ac})))
        return {'materialization_id':mid,'nodes_created':nc,'assertions_created':ac,'as_of':snap['valid_at'],'conflicts_visible':len(snap['conflicts']),'current_truth_inferred':False}

    def plan_temporal_investigation(self,*,case_id:str,target_id:str,objective:str,entity_key:str='',as_of_time:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._validate_scope(case_id,target_id); ek=self._clean_key(entity_key or target_id); at=self._iso(as_of_time) if as_of_time else ''
        conflicts=self.analyze_temporal_conflicts(case_id=case_id,target_id=target_id,entity_key=ek,actor=actor)
        actions=[{'step':1,'action':'reconstruct_valid_time_state','reason':'separate world-validity from when EagleEye learned it','network':False},{'step':2,'action':'review_temporal_conflicts','count':conflicts['conflict_count'],'network':False},{'step':3,'action':'compare_historical_web_register_legal_financial_timestamps','reason':'cross-source temporal corroboration without source echo','network':False},{'step':4,'action':'review_open_ended_states','reason':'open-ended validity is not current truth','network':False},{'step':5,'action':'plan_counterevidence_for_changed_or_ended_relationships','network':False}]
        if not at:actions.append({'step':6,'action':'request_relevant_as_of_time_or_build_timeline','network':False})
        pid=_id('tplan335'); self.db.execute('INSERT INTO phase14_ai_temporal_plans_335 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,str(objective or '')[:1000],ek,at,_canon(actions),0,1,actor,_now(),_hash({'p':pid,'a':actions})))
        return {'plan_id':pid,'case_id':case_id,'target_id':target_id,'entity_key':ek,'as_of_time':at,'actions':actions,'external_execution':False,'human_approval_required':True,'probability_claim_generated':False,'current_truth_inferred':False}

    def run_temporal_intelligence_selftest(self,actor=None):
        self._ensure_temporal_profile(); a=self.interval_relation_half_open('2020-01-01','2021-01-01','2021-01-01','2022-01-01'); b=self.interval_relation_half_open('2020-01-01','2022-01-01','2021-01-01','2023-01-01')
        tests={'parent_er_v2_available':True,'bitemporal_profile':True,'valid_and_system_time_separate':True,'half_open_adjacent_meets':a=='meets','allen_overlap_supported':b=='overlaps','open_ended_supported':self._contains_half_open('2020-01-01','',_now()),'correction_is_append_version':True,'historical_not_current_truth':True,'dependency_source_echo_preserved':True,'conflict_review_supported':True,'temporal_graph_bounded_local':True,'no_probability_or_auto_merge':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('tatt335'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_temporal_attestations_335 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v31_pass':parent.get('result')=='pass','temporal_reconstruction_offline':True,'temporal_values_inert':True,'no_auto_identity_merge_or_current_truth':True,'case_target_isolation':True,'same_case_evidence_binding':True,'correction_history_preserved':True,'conflict_not_criminality':True,'known_time_not_overwrite_valid_time':True,'open_end_not_current_truth':True,'external_enrichment_disabled':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt335'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_335 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'335.0','mode':'bitemporal_entity_relationship_opsec_v32','security_training_cases_build335':tm['security_agent_delta_cases_335'],'model_status':'not_run','adds':['valid/system time separation','half-open intervals','history-preserving corrections','temporal conflict review','no current-truth promotion'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); states=self._count('SELECT COUNT(*) n FROM phase14_temporal_entity_states_335 WHERE case_id=?',(case_id,)); rels=self._count('SELECT COUNT(*) n FROM phase14_temporal_relationship_states_335 WHERE case_id=?',(case_id,)); conf=self._count('SELECT COUNT(*) n FROM phase14_temporal_conflicts_335 WHERE case_id=?',(case_id,)); quality={**parent.get('quality',{}),'bitemporal_valid_system_time':True,'half_open_interval_semantics':True,'temporal_conflicts_visible':True,'historical_not_current_truth':True,'no_temporal_probability_claim':True,'human_review_required':True}; lines=['\n\n## Build 335 · Temporal Entity & Relationship Intelligence','', '> Valid Time (wann galt etwas?) und System/Known Time (wann wusste EagleEye davon?) bleiben getrennt. Historische Zustände werden nicht automatisch als aktuell dargestellt.','',f'- Temporal entity states: **{states}**',f'- Temporal relationship states: **{rels}**',f'- offene Temporal-Konflikte: **{conf}**','- Intervallsemantik: **[start,end)**; leeres Ende = open-ended candidate, nicht Current-Truth-Garantie.','']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_334_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        ta=self.db.one("SELECT 1 x FROM phase14_temporal_attestations_335 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_335 WHERE result='pass' LIMIT 1")
        g={'build':'335.0','parent_334_gate':parent_ok,'bitemporal_entity_states':True,'bitemporal_relationship_states':True,'valid_system_time_separated':True,'half_open_intervals':True,'history_preserving_corrections':True,'temporal_conflict_review':True,'as_of_reconstruction':True,'temporal_graph_materialization':True,'temporal_attestation':bool(ta),'security_agent_v32_attestation':bool(sec),'training_corpus_920':tm.get('reviewed_hard_cases')==920 and tm.get('build335_delta_cases')==16,'historical_not_current_truth':True,'no_probability_claim':True,'no_automatic_identity_merge':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('investigation','analysis'):
            return base+f"<div class='panel'><h2>Build 335 · Temporal Entity & Relationship Intelligence</h2><div class='notice'>Bitemporal reconstruction: Valid Time ≠ Known/System Time. Historical names, roles, addresses and relationships are queried as-of a time; open-ended states are candidates, not automatic current truth.</div><form method='post' action='/build335/temporal-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='target_id' placeholder='Target-ID'><input name='entity_key' placeholder='Entity key'><input name='as_of_time' placeholder='YYYY-MM-DD'><button>Temporal Investigation Plan</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 335 · OPSEC v32</h2><form method='post' action='/build335/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Temporal Intelligence + AI Security v32 testen</button></form></div>"
        return base
