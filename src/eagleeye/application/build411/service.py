from __future__ import annotations
import re
from pathlib import Path

class Build411TemporalIntelligenceService:
    BUILD='411.0'; PACKAGE='411.0.0'; POLICY='phase18.temporal-intelligence-service.v411'
    def __init__(self,db,audit,*,build410,temporal411,holdout398,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build410=build410; self.temporal411=temporal411; self.holdout398=holdout398; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build410,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def remediation_status(self):
        s=self.holdout398.qualification_status(); p=self.holdout398.status()
        checks={
            'governance_hard_veto': p.get('governance_compliance_hard_gate') is True,
            'quality_filtered_reviewer_diversity': p.get('quality_filtered_reviewer_diversity') is True,
            'harmful_overreach_veto': p.get('harmful_overreach_veto') is True,
            'authoritative_status_fields': all(k in p for k in ('governance_compliance_hard_gate','quality_filtered_reviewer_diversity','harmful_overreach_veto')),
            'build410_security_invariants': all(v for k,v in self.build410.feedback_qualification_status()['checks'].items() if k != 'version_coherent'),
        }
        return {'build':self.BUILD,'checks':checks,'remediation_gate_pass':all(checks.values()),'external_holdout_qualified':bool(s.get('external_holdout_qualified',False)),'production_release_ready':False}
    def temporal_status(self):
        t=self.temporal411.status(); r=self.remediation_status(); checks={'version_coherent':self.version_status()['coherent'],'remediation_gate_pass':r['remediation_gate_pass'],'temporal_nonexecuting':t['network_execution'] is False and t['execution_authority'] is False,'no_truth_or_causality':t['truth_determined'] is False and t['causality_inferred'] is False,'no_automatic_evidence_promotion':t['automatic_evidence_promotion'] is False}
        return {'build':self.BUILD,'checks':checks,'temporal_intelligence_gate_pass':all(checks.values()),'production_release_ready':False}
    def timeline(self,search_id): return self.temporal411.timeline(search_id)
    def temporal_conflicts(self,search_id): return self.temporal411.conflicts(search_id)
    def temporal_coverage(self,search_id): return self.temporal411.coverage(search_id)
    def phase18_status(self,case_id=''):
        p=dict(self.build410.phase18_status(case_id)); s=self.temporal_status(); p.update({'build':self.BUILD,'phase18_builds_completed':11,'temporal_intelligence':True,'temporal_intelligence_gate_pass':s['temporal_intelligence_gate_pass'],'feedback_checked_before_build':True,'next_feedback_check':'before build 412','production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.temporal_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['temporal_intelligence_gate_pass'],'production_release_ready':False}
