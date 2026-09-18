from __future__ import annotations
import re
from pathlib import Path

class Build413InvestigationPlannerService:
    BUILD='413.0'; PACKAGE='413.0.0'; POLICY='phase18.investigation-planner-service.v413'
    def __init__(self,db,audit,*,build412,planner413,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build412=build412; self.planner413=planner413; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build412,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def planner_status(self):
        prev=self.build412.relationship_status(); prev_checks={k:v for k,v in prev['checks'].items() if k!='version_coherent'}; p=self.planner413.status()
        checks={'version_coherent':self.version_status()['coherent'],'build412_security_invariants':all(prev_checks.values()),'planner_integrity':p['integrity_valid'],'case_scoped_authorization':p['case_scoped_authorization'],'objective_subquestions_strategy_stops_risks':all(p[k] for k in ('objective_and_subquestions','source_strategy','stop_conditions','risk_constraints')),'no_execution_or_go':not p['network_execution'] and not p['execution_authority'] and not p['automatic_go'],'no_truth_promotion_or_scope_expansion':not p['truth_determined'] and not p['automatic_evidence_promotion'] and not p['autonomous_scope_expansion']}
        return {'build':self.BUILD,'checks':checks,'investigation_planner_gate_pass':all(checks.values()),'production_release_ready':False}
    def create_investigation_plan(self,**kwargs): return self.planner413.create_plan(**kwargs)
    def investigation_plan(self,plan_id): return self.planner413.get_plan(plan_id)
    def investigation_plans(self,case_id): return self.planner413.list_plans(case_id)
    def phase18_status(self,case_id=''):
        p=dict(self.build412.phase18_status(case_id)); s=self.planner_status(); p.update({'build':self.BUILD,'phase18_builds_completed':13,'investigation_planner':True,'investigation_planner_gate_pass':s['investigation_planner_gate_pass'],'feedback_checked_before_build':True,'next_feedback_check':'before build 414','production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.planner_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['investigation_planner_gate_pass'],'production_release_ready':False}
