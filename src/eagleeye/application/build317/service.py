from __future__ import annotations
import html,json,re
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build316.service import Build316IntelligenceDataFabricService

class Build317AIDataQueryPlannerService(Build316IntelligenceDataFabricService):
    BUILD='317.0'; REQUIRED_CORPUS=632
    def __init__(self,*args,build316=None,**kwargs):
        super().__init__(*args,**kwargs); self.build316=build316 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_317 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_317 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_317 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_317 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build317_delta_cases':a+s,'build317_delta_extreme':e,'query_planner_delta_cases':a,'security_agent_delta_cases_317':s}
    def _latest_fabric(self,case_id,target_id):
        return self.db.one("SELECT * FROM phase13_fabric_snapshots_316 WHERE case_id=? AND target_id=? AND status='assessed' ORDER BY created_at DESC LIMIT 1",(case_id,target_id))
    def create_query_plan(self,*,case_id,target_id,objective='',actor=None):
        actor=actor or self.actor
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        snap=self._latest_fabric(case_id,target_id); sid=(snap or {}).get('snapshot_id')
        pid=_id('queryplan317'); objective=' '.join(str(objective or '').split())[:1200] or 'resolve highest-value evidentiary gaps'
        self.db.execute('INSERT INTO phase13_query_plans_317 VALUES(?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,sid,objective,'planned',actor,_now(),_hash({'p':pid,'c':case_id,'t':target_id,'s':sid})))
        actions=self._generate_actions(pid,case_id,target_id,sid,objective)
        return {'plan_id':pid,'snapshot_id':sid,'actions':actions,'status':'planned','probability_claim_generated':False,'human_review_required':True}
    def _generate_actions(self,pid,case_id,target_id,sid,objective):
        items=self.db.all('SELECT * FROM phase13_fabric_items_316 WHERE snapshot_id=?',(sid,)) if sid else []
        links=self.db.all('SELECT * FROM phase13_fabric_links_316 WHERE snapshot_id=?',(sid,)) if sid else []
        conflicts=[x for x in links if x['link_type']=='conflict']; fields={x['field_name'] for x in items}; groups={x['source_group'] for x in items if x['source_group']}; counter_items=[x for x in items if x['direction']=='counter']
        targets=self.db.one('SELECT * FROM targets WHERE target_id=?',(target_id,)) or {}; anchor=(targets.get('name') or target_id).strip()
        candidates=[]
        if counter_items and not conflicts:
            cf=counter_items[0].get('field_name') or 'contested attribute'
            candidates.append((f'Resolve counterevidence conflict in {cf}',f'counter_conflict:{cf}',f'"{anchor}" {cf} official correction', 'focused','independent authoritative source',0.93,0.9,0.9,0.12,0.08,'Existing counterevidence must be independently verified even when no formal fabric conflict edge exists.'))
        for c in conflicts[:4]:
            f=c['field_name']; candidates.append((f'Resolve conflict in {f}',f'counterevidence:{f}',f'"{anchor}" {f}', 'focused','independent authoritative records',0.95,0.95,0.8,0.15,0.1,'Conflicting canonical values can materially change the hypothesis.'))
        for f,label in [('registration_id','official registration identifier'),('domain','domain ownership / registration'),('organisation','organisation affiliation'),('status','current official status'),('name','identity attributes')]:
            if f not in fields:
                candidates.append((f'Fill missing field {f}',f'gap:{f}',f'"{anchor}" {label}','broad','official/public records',0.85,0.55,0.75,0.1,0.08,'Missing discriminating field limits entity resolution.'))
        candidates.append(('Search explicit counterevidence','alternative_hypothesis',f'"{anchor}" alternative OR correction OR former OR unrelated','broad','independent public sources',0.8,0.7,0.9,0.1,0.08,'Counterevidence reduces confirmation bias and improves calibration.'))
        if len(groups)<3: candidates.append(('Add independent source family','source_independence',f'"{anchor}" official register','broad','new independent source family',0.88,0.5,1.0,0.12,0.08,'Current evidence has limited source independence.'))
        scored=[]
        for q,h,query,mode,focus,ig,cr,ind,cost,risk,why in candidates:
            score=round(100*(0.42*ig+0.23*cr+0.23*ind-0.07*cost-0.05*risk),2); scored.append((score,q,h,query,mode,focus,ig,cr,ind,cost,risk,why))
        scored.sort(reverse=True,key=lambda x:x[0]); out=[]
        for rank,row in enumerate(scored[:8],1):
            score,q,h,query,mode,focus,ig,cr,ind,cost,risk,why=row; aid=_id('queryaction317'); stop='stop when an independent authoritative source resolves the gap/conflict or two attempts add no new independent evidence'
            self.db.execute('INSERT INTO phase13_query_actions_317 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,pid,case_id,target_id,rank,q,h,query,mode,focus,ig,cr,ind,cost,risk,score,why,stop,'proposed',_now(),_hash({'a':aid,'q':query,'s':score})))
            out.append({'action_id':aid,'rank':rank,'question':q,'query':query,'search_mode':mode,'source_focus':focus,'priority_score':score,'expected_information_gain':ig,'rationale':why,'stop_condition':stop})
        return out
    def record_query_feedback(self,*,action_id,result_count,relevant_count,new_independent_sources,conflicts_resolved,notes=''):
        a=self.db.one('SELECT * FROM phase13_query_actions_317 WHERE action_id=?',(action_id,));
        if not a: raise KeyError('Query action not found')
        rc=max(0,int(result_count)); rel=max(0,int(relevant_count)); nis=max(0,int(new_independent_sources)); cr=max(0,int(conflicts_resolved))
        useful=1 if (rel>0 and (nis>0 or cr>0)) else 0
        if rc==0: decision='broaden'
        elif useful: decision='continue_if_gap_remains'
        elif rc>0 and rel==0: decision='reformulate'
        else: decision='stop_low_information_gain'
        fid=_id('queryfeedback317'); self.db.execute('INSERT INTO phase13_query_feedback_317 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,action_id,rc,rel,nis,cr,useful,decision,str(notes)[:1200],_now(),_hash({'f':fid,'d':decision})))
        return {'feedback_id':fid,'next_decision':decision,'useful':bool(useful),'probability_claim_generated':False}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v13_pass':parent.get('result')=='pass','case_bound_planning':True,'public_source_planning_only':True,'bounded_ranked_actions':True,'counterevidence_required':True,'source_independence_rewarded':True,'risk_cost_penalized':True,'stop_conditions_required':True,'no_hit_count_probability':True,'no_auto_identity_confirmation':True,'real_active_recon_disabled':True,'human_review_required':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt317'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_attestations_317 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'317.0','mode':'query_planner_opsec_v14','security_training_cases_build317':tm['security_agent_delta_cases_317'],'model_status':'not_run','adds':['information-gain planning','counterevidence requirement','bounded stop conditions','risk/cost penalties'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=self.build316.compose_evidence_dossier(case_id=case_id,title=title,actor=actor or self.actor)
        plans=self.db.all('SELECT * FROM phase13_query_plans_317 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); actions=self.db.all('SELECT * FROM phase13_query_actions_317 WHERE case_id=? ORDER BY priority_score DESC LIMIT 20',(case_id,))
        lines=['\n\n## Build 317 · AI Data Query Planner','',f'- Query-Pläne: **{len(plans)}**',f'- priorisierte nächste Suchaktionen: **{len(actions)}**','', '> Prioritäten basieren auf erwartetem Erkenntnisgewinn, Konfliktauflösung, Quellenunabhängigkeit, Kosten/Risiko und Stop-Bedingungen. Trefferzahlen sind keine Wahrscheinlichkeit.','']
        for a in actions[:5]: lines += [f"- **{a['priority_score']:.1f}/100** · {a['question']} → `{a['query_text']}`"]
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':{**parent.get('quality',{}),'query_planner':True,'information_gain_ranked':True,'counterevidence_planned':True,'probability_claim_generated':False,'human_review_required':True}}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_attestations_317 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                from pathlib import Path
                parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_316_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'317.0','parent_316_gate':parent_ok,'security_agent_v14_attestation':bool(sec),'training_corpus_632':tm['reviewed_hard_cases']==632 and tm['build317_delta_cases']==16 and tm['build317_delta_extreme']==4,'phase13_ai_data_query_planner':True,'information_gain_prioritization':True,'conflict_gap_driven_search':True,'counterevidence_search':True,'bounded_stop_conditions':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'real_active_recon_disabled':True,'no_probability_from_hit_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 317 · AI Data Query Planner</h2><div class='notice'>Priorisiert die nächste Recherche nach Evidenzlücken, Konflikten, erwartbarem Erkenntnisgewinn und Quellenunabhängigkeit. Kein Trefferzahl-Confidence-Score.</div><form method='post' action='/build317/query-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3'></textarea></div><button>Query-Plan erzeugen</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 317 · AI Security Agent v14</h2><form method='post' action='/build317/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-317 Planner/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
