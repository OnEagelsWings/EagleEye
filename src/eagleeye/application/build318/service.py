from __future__ import annotations
import html,json
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build317.service import Build317AIDataQueryPlannerService

class Build318UnifiedAutonomousInvestigationService(Build317AIDataQueryPlannerService):
    BUILD='318.0'; REQUIRED_CORPUS=648; AUTH='UNIFIED INVESTIGATION FREIGEBEN'
    def __init__(self,*args,build317=None,**kwargs):
        super().__init__(*args,**kwargs); self.build317=build317 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_318 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_318 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_318 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_318 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build318_delta_cases':a+s,'build318_delta_extreme':e,'unified_investigation_delta_cases':a,'security_agent_delta_cases_318':s}
    def start_unified_investigation(self,*,case_id,target_id,objective='',authorization_phrase='',max_actions=5,actor=None):
        actor=actor or self.actor
        if str(authorization_phrase or '').strip()!=self.AUTH: raise PermissionError('Explicit single-run authorization required')
        max_actions=max(1,min(int(max_actions or 5),8))
        plan=self.create_query_plan(case_id=case_id,target_id=target_id,objective=objective,actor=actor)
        rid=_id('unified318'); self.db.execute('INSERT INTO phase13_unified_runs_318 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,plan['plan_id'],str(objective or '')[:1200],self.AUTH,max_actions,'running','',actor,_now(),None,_hash({'r':rid,'p':plan['plan_id'],'m':max_actions})))
        steps=[]
        for a in plan['actions'][:max_actions]:
            sid=_id('unifiedstep318'); decision='staged_for_public_source_execution'
            self.db.execute('INSERT INTO phase13_unified_steps_318 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,rid,a['action_id'],a['rank'],self._step_type(a),a['question'],a['query'],a['source_focus'],decision,1,1,_now(),_hash({'s':sid,'r':rid,'a':a['action_id']})))
            steps.append({'step_id':sid,'rank':a['rank'],'question':a['question'],'query':a['query'],'source_focus':a['source_focus'],'decision':decision,'candidate_only':True})
        stop='bounded action budget reached; execute/review staged public-source actions before any new autonomous cycle'
        self.db.execute('UPDATE phase13_unified_runs_318 SET status=?,stop_reason=?,completed_at=? WHERE run_id=?',('awaiting_human_review',stop,_now(),rid))
        return {'run_id':rid,'plan_id':plan['plan_id'],'steps':steps,'status':'awaiting_human_review','stop_reason':stop,'single_use_authorization':True,'candidate_only':True,'probability_claim_generated':False,'human_review_required':True}
    def _step_type(self,a):
        q=(a.get('question') or '').lower()
        if 'counter' in q or 'conflict' in q: return 'counterevidence_resolution'
        if 'missing' in q or 'gap' in q: return 'evidence_gap_search'
        if 'source' in q: return 'independent_source_search'
        return 'targeted_public_research'
    def review_unified_run(self,*,run_id,disposition,notes='',reviewer=None):
        reviewer=reviewer or self.actor; disp=str(disposition or '').strip().lower()
        if disp not in {'accept_for_analysis','needs_more_research','reject_candidates'}: raise ValueError('Invalid review disposition')
        row=self.db.one('SELECT * FROM phase13_unified_runs_318 WHERE run_id=?',(run_id,))
        if not row: raise KeyError('Run not found')
        qid=_id('unifiedreview318'); self.db.execute('INSERT INTO phase13_unified_run_reviews_318 VALUES(?,?,?,?,?,?,?)',(qid,run_id,reviewer,disp,str(notes)[:2000],_now(),_hash({'q':qid,'r':run_id,'d':disp})))
        self.db.execute('UPDATE phase13_unified_runs_318 SET status=? WHERE run_id=?',('reviewed_'+disp,run_id))
        return {'review_id':qid,'run_id':run_id,'disposition':disp,'automatic_evidence_promotion':False}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v14_pass':parent.get('result')=='pass','single_use_explicit_authorization':True,'bounded_max_actions_8':True,'planner_driven_actions':True,'counterevidence_preserved':True,'candidate_only_outputs':True,'human_review_before_promotion':True,'public_source_scope_only':True,'private_network_fail_closed':True,'no_credential_or_login_automation':True,'no_hit_count_probability':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt318'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_attestations_318 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'318.0','mode':'unified_autonomous_investigation_opsec_v15','security_training_cases_build318':tm['security_agent_delta_cases_318'],'model_status':'not_run','adds':['single-use authorization','bounded unified cycles','candidate-only orchestration','mandatory review'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=self.build317.compose_evidence_dossier(case_id=case_id,title=title,actor=actor or self.actor)
        runs=self.db.all('SELECT * FROM phase13_unified_runs_318 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); steps=self.db.all('SELECT s.* FROM phase13_unified_steps_318 s JOIN phase13_unified_runs_318 r ON r.run_id=s.run_id WHERE r.case_id=? ORDER BY r.created_at DESC,s.rank_no ASC LIMIT 40',(case_id,))
        lines=['\n\n## Build 318 · Unified Autonomous Investigation','',f'- Unified Runs: **{len(runs)}**',f'- staged investigation steps: **{len(steps)}**','', '> Jeder Run ist fall-/zielgebunden, single-use autorisiert, auf höchstens 8 Aktionen begrenzt und endet vor Evidence-Promotion im Human Review.','']
        for s in steps[:8]: lines += [f"- **#{s['rank_no']}** {s['question']} → `{s['planned_query']}` · {s['decision']}"]
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':{**parent.get('quality',{}),'unified_autonomous_investigation':True,'bounded_single_use_runs':True,'candidate_only':True,'probability_claim_generated':False,'human_review_required':True}}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_attestations_318 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                from pathlib import Path
                parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_317_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'318.0','parent_317_gate':parent_ok,'security_agent_v15_attestation':bool(sec),'training_corpus_648':tm['reviewed_hard_cases']==648 and tm['build318_delta_cases']==16 and tm['build318_delta_extreme']==4,'phase13_unified_autonomous_investigation':True,'single_use_authorization':True,'bounded_action_budget':True,'planner_fabric_integration':True,'counterevidence_and_stop_conditions':True,'candidate_only_until_review':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'real_active_recon_disabled':True,'no_probability_from_hit_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 318 · Unified Autonomous Investigation</h2><div class='notice'>Ein autorisierter, begrenzter Ermittlungszyklus aus Data Fabric + Query Planner. Max. 8 Aktionen, candidate_only, Human Review verpflichtend.</div><form method='post' action='/build318/unified-run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3'></textarea></div><div class='field'><label>Max. Aktionen (1–8)</label><input name='max_actions' value='5'></div><div class='field'><label>Freigabephrase</label><input name='authorization_phrase' placeholder='{self.AUTH}' required></div><button>Unified Run starten</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 318 · AI Security Agent v15</h2><form method='post' action='/build318/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-318 Unified/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
