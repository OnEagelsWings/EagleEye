from __future__ import annotations
import re
from pathlib import Path
class Build418EvidenceHypothesisMatrixService:
 BUILD='418.0'; PACKAGE='418.0.0'
 def __init__(self,db,audit,*,build417,matrix418,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build417=build417; self.matrix418=matrix418; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build417,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  from eagleeye_pro.version import BUILD as runtime, SCHEMA_VERSION as schema
  try:
   from importlib.metadata import version as package_version
   package=package_version('eagleeye-personosint-pro')
  except Exception:
   pt=(self.install_dir/'pyproject.toml').read_text() if (self.install_dir/'pyproject.toml').exists() else ''
   m=re.search(r'^version\\s*=\\s*["\\\']([^"\\\']+)',pt,re.M); package=m.group(1) if m else 'unknown'
  return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
 def matrix_status(self):
  s=self.matrix418.status(); checks={'version_coherent':self.version_status()['coherent'],'integrity':s['integrity_valid'],'continuity_guarded':s['continuity_guarded'],'conflict_and_gap_detection':s['conflict_detection'] and s['coverage_gap_detection'],'human_review':s['human_review_required'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'matrix_gate_pass':all(checks.values()),'production_release_ready':False}
 def link_evidence(self,**kw): return self.matrix418.link(**kw)
 def reasoning_matrix(self,**kw): return self.matrix418.matrix(**kw)
 def phase18_status(self,case_id=''):
  p=dict(self.build417.phase18_status(case_id)); s=self.matrix_status(); p.update({'build':self.BUILD,'phase18_builds_completed':18,'evidence_hypothesis_reasoning_matrix':True,'matrix_gate_pass':s['matrix_gate_pass'],'production_release_ready':False}); return p
