from __future__ import annotations
import re
from pathlib import Path
class Build415MultiAgentInvestigationService:
 BUILD='415.0'; PACKAGE='415.0.0'
 def __init__(self,db,audit,*,build414,multi415,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build414=build414; self.multi415=multi415; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build414,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
 def multi_agent_status(self):
  s=self.multi415.status(); checks={'version_coherent':self.version_status()['coherent'],'build414_integrity':self.build414.waves414.status()['integrity_valid'],'multi_agent_integrity':s['integrity_valid'],'human_review_required':s['human_review_required'],'case_and_plan_bound':s['case_scoped'] and s['plan_bound'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'multi_agent_gate_pass':all(checks.values()),'production_release_ready':False}
 def create_multi_agent_session(self,**kw): return self.multi415.create_session(**kw)
 def run_multi_agent_round(self,**kw): return self.multi415.run_round(**kw)
 def multi_agent_session(self,sid): return self.multi415.session(sid)
 def phase18_status(self,case_id=''):
  p=dict(self.build414.phase18_status(case_id)); s=self.multi_agent_status(); p.update({'build':self.BUILD,'phase18_builds_completed':15,'multi_agent_investigation':True,'multi_agent_gate_pass':s['multi_agent_gate_pass'],'checkpoint':'Build 415 GitHub + AI review','production_release_ready':False}); return p
