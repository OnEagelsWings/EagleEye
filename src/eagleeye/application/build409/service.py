from __future__ import annotations
import re
from pathlib import Path
class Build409RetrievalQualityCoverageService:
    BUILD='409.0'; PACKAGE='409.0.0'; POLICY='phase18.retrieval-quality-coverage-service.v409'
    def __init__(self,db,audit,*,build408,quality409,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build408=build408; self.quality409=quality409; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build408,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def retrieval_quality_status(self):
        prev=self.build408.federated_search_status(); prev_checks={k:v for k,v in prev['checks'].items() if k!='version_coherent'}; st=self.quality409.status(); checks={'version_coherent':self.version_status()['coherent'],'build408_security_invariants':all(prev_checks.values()),'network_execution_disabled':st['network_execution'] is False,'truth_determination_disabled':st['truth_determined'] is False,'automatic_evidence_promotion_disabled':st['automatic_evidence_promotion'] is False,'coverage_gap_detection':st['coverage_gap_detection'] is True,'source_diversity_metrics':st['source_diversity_metrics'] is True}; return {**st,'checks':checks,'retrieval_quality_gate_pass':all(checks.values()),'production_release_ready':False,'feedback_checked_before_build':True,'next_public_feedback_build':'410.0'}
    def assess_search(self,search_id): return self.quality409.assess(search_id)
    def compare_searches(self,search_ids): return self.quality409.compare(search_ids)
    def phase18_status(self,case_id=''):
        p=dict(self.build408.phase18_status(case_id)); s=self.retrieval_quality_status(); p.update({'build':self.BUILD,'phase18_builds_completed':9,'retrieval_quality':True,'retrieval_quality_gate_pass':s['retrieval_quality_gate_pass'],'feedback_checked_before_build':True,'production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.retrieval_quality_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['retrieval_quality_gate_pass'],'production_release_ready':False}
