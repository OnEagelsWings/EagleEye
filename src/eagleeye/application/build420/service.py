from __future__ import annotations
import re
from importlib.metadata import version as package_version
from pathlib import Path
from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build420Phase18QualificationService:
 BUILD='420.0'; PACKAGE='420.0.0'
 def __init__(self,db,audit,*,build419,qualification420,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build419=build419; self.qualification420=qualification420; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build419,n,None)
  if v is None:raise AttributeError(n)
  return v
 def version_status(self):
  try:p=package_version('eagleeye-personosint-pro')
  except Exception:
   pt=self.install_dir/'pyproject.toml'; txt=pt.read_text() if pt.exists() else ''; m=re.search(r'^version\\s*=\\s*["\\\']([^"\\\']+)',txt,re.M); p=m.group(1) if m else 'unknown'
  return {'runtime_build':RUNTIME_BUILD,'schema_version':SCHEMA_VERSION,'package_version':p,'coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD and p==self.PACKAGE}
 def qualification_status(self):
  s=self.qualification420.status(); last=self.db.one('SELECT qualification_id,result,created_at FROM phase18_qualification_run_420 ORDER BY created_at DESC,qualification_id DESC LIMIT 1'); last=dict(last) if last else None; checks={'version_coherent':self.version_status()['coherent'],'qualification_integrity':s['integrity_valid'],'passing_qualification_run':bool(last and last['result']=='pass'),'fail_closed':s['qualification_fail_closed'],'deep_review_required':s['full_regression_required'] and s['codex_review_required'] and s['github_ci_required'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'last_qualification':last,'phase18_gate_pass':all(checks.values()),'production_release_ready':False}
 def qualify_phase18(self,**kw): return self.qualification420.qualify(**kw)
 def phase18_status(self,case_id=''):
  p=dict(self.build419.phase18_status(case_id)); s=self.qualification_status(); p.update({'build':self.BUILD,'phase18_builds_completed':20,'phase18_complete':True,'qualification_framework':True,'phase18_gate_pass':s['phase18_gate_pass'],'production_release_ready':False}); return p
