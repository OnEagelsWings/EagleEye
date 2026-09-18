from __future__ import annotations
import re
from pathlib import Path
class Build414AutonomousResearchWavesService:
 BUILD='414.0'; PACKAGE='414.0.0'
 def __init__(self,db,audit,*,build413,waves414,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build413=build413; self.waves414=waves414; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build413,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
 def wave_status(self):
  s=self.waves414.status(); checks={'version_coherent':self.version_status()['coherent'],'build413_integrity':self.build413.planner413.status()['integrity_valid'],'wave_integrity':s['integrity_valid'],'explicit_human_authorization':s['explicit_human_authorization_required'],'bounded_plan_envelope':s['immutable_plan_envelope'] and s['budget_bounded'],'no_direct_network_authority':not s['direct_network_authority'],'no_auto_go_promotion_scope_or_truth':not any(s[k] for k in ('automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'autonomous_research_wave_gate_pass':all(checks.values()),'production_release_ready':False}
 def create_research_wave_run(self,**kw): return self.waves414.create_run(**kw)
 def authorize_research_wave_run(self,**kw): return self.waves414.authorize(**kw)
 def advance_research_wave_run(self,**kw): return self.waves414.advance(**kw)
 def research_wave_run(self,run_id): return self.waves414.run(run_id)
 def phase18_status(self,case_id=''):
  p=dict(self.build413.phase18_status(case_id)); s=self.wave_status(); p.update({'build':self.BUILD,'phase18_builds_completed':14,'autonomous_research_waves':True,'autonomous_research_wave_gate_pass':s['autonomous_research_wave_gate_pass'],'next_checkpoint':'Build 415 GitHub + AI review','production_release_ready':False}); return p
