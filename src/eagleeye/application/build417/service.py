from __future__ import annotations
import re
from pathlib import Path
class Build417HypothesisCoordinationService:
 BUILD='417.0'; PACKAGE='417.0.0'
 def __init__(self,db,audit,*,build416,hypothesis417,install_dir,actor='local-analyst'): self.db=db; self.audit=audit; self.build416=build416; self.hypothesis417=hypothesis417; self.install_dir=Path(install_dir); self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'): raise AttributeError(n)
  v=getattr(self.build416,n,None)
  if v is None: raise AttributeError(n)
  return v
 def version_status(self):
  vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\\s*=\\s*["\\\']([^"\\\']+)',vt); schema=pick(r'^SCHEMA_VERSION\\s*=\\s*["\\\']([^"\\\']+)',vt); package=pick(r'^version\\s*=\\s*["\\\']([^"\\\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
 def hypothesis_status(self):
  s=self.hypothesis417.status(); checks={'version_coherent':self.version_status()['coherent'],'integrity':s['integrity_valid'],'continuity_guarded':s['continuity_guarded'],'counterevidence_and_alternatives':s['counterevidence_first_class'] and s['alternatives_supported'],'human_review':s['human_review_required'],'no_forbidden_authority':not any(s[k] for k in ('direct_network_authority','automatic_go_issuance','automatic_evidence_promotion','autonomous_scope_expansion','truth_determined'))}; return {'build':self.BUILD,'checks':checks,'hypothesis_gate_pass':all(checks.values()),'production_release_ready':False}
 def create_hypothesis(self,**kw): return self.hypothesis417.create(**kw)
 def add_hypothesis_item(self,**kw): return self.hypothesis417.add_item(**kw)
 def review_hypothesis(self,**kw): return self.hypothesis417.review(**kw)
 def set_hypothesis_state(self,**kw): return self.hypothesis417.set_human_state(**kw)
 def phase18_status(self,case_id=''):
  p=dict(self.build416.phase18_status(case_id)); s=self.hypothesis_status(); p.update({'build':self.BUILD,'phase18_builds_completed':17,'hypothesis_counterevidence_coordination':True,'hypothesis_gate_pass':s['hypothesis_gate_pass'],'production_release_ready':False}); return p
