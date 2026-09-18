from __future__ import annotations
from importlib.metadata import version as package_version
from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build419InvestigationSynthesisService:
 BUILD='419.0'; PACKAGE='419.0.0'
 def __init__(self,db,audit,*,build418,synthesis419,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build418=build418; self.synthesis419=synthesis419; self.install_dir=install_dir; self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build418,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  try:p=package_version('eagleeye-personosint-pro')
  except Exception:
   import re
   from pathlib import Path
   pt=Path(self.install_dir)/'pyproject.toml'; txt=pt.read_text() if pt.exists() else ''; m=re.search(r'^version\\s*=\\s*["\\\']([^"\\\']+)',txt,re.M); p=m.group(1) if m else 'unknown'
  return {'runtime_build':RUNTIME_BUILD,'schema_version':SCHEMA_VERSION,'package_version':p,'coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD and p==self.PACKAGE}
 def synthesis_status(self):
  s=self.synthesis419.status(); checks={'version_coherent':self.version_status()['coherent'],'integrity':s['integrity_valid'],'matrix_grounded':s['matrix_grounded'],'counterevidence_visible':s['counterevidence_visible'],'human_review':s['human_review_required'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'synthesis_gate_pass':all(checks.values()),'production_release_ready':False}
 def synthesize(self,**kw): return self.synthesis419.synthesize(**kw)
 def get_synthesis(self,*a,**kw): return self.synthesis419.get(*a,**kw)
 def phase18_status(self,case_id=''):
  p=dict(self.build418.phase18_status(case_id)); s=self.synthesis_status(); p.update({'build':self.BUILD,'phase18_builds_completed':19,'investigation_synthesis_argumentation':True,'synthesis_gate_pass':s['synthesis_gate_pass'],'production_release_ready':False}); return p
