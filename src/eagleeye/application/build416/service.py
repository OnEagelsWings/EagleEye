from __future__ import annotations
import re
from pathlib import Path
class Build416MultiAgentContinuityService:
 BUILD='416.0'; PACKAGE='416.0.0'
 def __init__(self,db,audit,*,build415,continuity416,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build415=build415; self.continuity416=continuity416; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build415,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
 def continuity_status(self):
  s=self.continuity416.status(); checks={'version_coherent':self.version_status()['coherent'],'continuity_integrity':s['integrity_valid'],'revalidate_every_round':s['revalidate_every_round'],'plan_and_wave_binding':s['immutable_plan_binding'] and s['wave_binding_revalidated'],'fail_closed':s['fail_closed_hold'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'continuity_gate_pass':all(checks.values()),'production_release_ready':False}
 def run_multi_agent_round(self,**kw): return self.continuity416.run_round(**kw)
 def validate_multi_agent_session(self,**kw): return self.continuity416.validate(**kw)
 def phase18_status(self,case_id=''):
  p=dict(self.build415.phase18_status(case_id)); s=self.continuity_status(); p.update({'build':self.BUILD,'phase18_builds_completed':16,'multi_agent_integrity_case_continuity':True,'continuity_gate_pass':s['continuity_gate_pass'],'production_release_ready':False}); return p
