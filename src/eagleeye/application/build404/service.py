from __future__ import annotations
import re
from pathlib import Path

class Build404AIReviewGateService:
    BUILD="404.0"; PACKAGE="404.0.0"; POLICY="phase18.ai-review-release-gate.v404"
    def __init__(self,db,audit,*,build403,gate404,install_dir,actor="local-analyst"):
        self.db=db; self.audit=audit; self.build403=build403; self.gate404=gate404; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build403,name,None)
        if value is None: raise AttributeError(name)
        return value
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def review_rules(self): return self.gate404.rules()
    def review_gate_status(self): return self.gate404.gate_status()
    def review_integrity(self): return self.gate404.verify_integrity()
    def phase18_status(self,case_id=''):
        p=dict(self.build403.phase18_status(case_id)); g=self.review_gate_status(); p.update({'build':self.BUILD,'phase':18,'phase18_builds_completed':4,'ai_review_gate':True,'ai_review_gate_pass':g['ai_review_gate_pass'],'open_blocking_ai_findings':g['open_blocking_count'],'five_build_feedback_cycle':True,'next_public_feedback_build':'405.0','production_release_ready':False}); return p
    def qualified_gate(self):
        v=self.version_status(); g=self.review_gate_status(); i=self.review_integrity(); checks={'version_coherent':v['coherent'],'build403_contracts_preserved':g['checks']['build403_negative_contracts_preserved'] and g['checks']['build403_negative_runtime_preserved'] and g['checks']['build403_scenario_catalog_preserved'],'ai_review_gate_pass':g['ai_review_gate_pass'],'review_ledger_integrity':i['valid'],'production_not_released':not g['production_release_ready']}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'production_release_ready':False}
