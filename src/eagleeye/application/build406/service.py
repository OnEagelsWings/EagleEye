from __future__ import annotations
import re
from pathlib import Path

class Build406FeedbackRemediationService:
    BUILD='406.0'; PACKAGE='406.0.0'; POLICY='phase18.feedback-remediation-runtime-integration.v406'
    def __init__(self,db,audit,*,build405,matrix402,holdout398,soak399,gate404,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build405=build405; self.matrix402=matrix402; self.holdout398=holdout398; self.soak399=soak399; self.gate404=gate404; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build405,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def remediation_status(self):
        hs=self.holdout398.status(); audit=self.matrix402.audit(); review=self.gate404.gate_status(); integrity=self.gate404.verify_integrity(); registry_integrity=self.build405.source_registry_integrity()
        matrix_keys={r['key'] for r in self.matrix402.matrix()['rows']}
        required={'holdout.external_run.record','holdout.human_review.submit','soak.external_bundle.import','soak.external_session.review'}
        checks={
          'version_coherent':self.version_status()['coherent'],
          'governance_hard_veto_declared':hs.get('governance_compliance_hard_gate') is True,
          'quality_reviewer_diversity_declared':hs.get('quality_filtered_reviewer_diversity') is True,
          'harmful_overreach_veto_declared':hs.get('harmful_overreach_veto') is True,
          'qualification_mutations_catalogued':required <= matrix_keys,
          'authorization_audit_pass':audit['authorization_audit_pass'],
          'review_ledger_integrity':integrity['valid'],
          'review_gate_pass':review['ai_review_gate_pass'],
          'source_registry_integrity':registry_integrity['valid'],
          'production_not_released':True,
        }
        return {'build':self.BUILD,'policy':self.POLICY,'checks':checks,'p1_remediation_gate_pass':all(checks.values()),'catalogued_mutation_surfaces':self.matrix402.matrix()['mutation_surfaces'],'production_release_ready':False,'next_feedback_check':'after build 407 or 408'}
    def phase18_status(self,case_id=''):
        p=dict(self.build405.phase18_status(case_id)); r=self.remediation_status(); p.update({'build':self.BUILD,'phase18_builds_completed':6,'feedback_remediation_406':True,'p1_remediation_gate_pass':r['p1_remediation_gate_pass'],'catalogued_mutation_surfaces':r['catalogued_mutation_surfaces'],'next_public_feedback_build':'410.0','production_release_ready':False}); return p
    def qualified_gate(self):
        r=self.remediation_status(); return {'build':self.BUILD,'checks':r['checks'],'build_acceptance_ready':r['p1_remediation_gate_pass'],'production_release_ready':False}
