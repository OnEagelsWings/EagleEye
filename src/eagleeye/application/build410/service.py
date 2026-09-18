from __future__ import annotations
import re
from pathlib import Path

class Build410FeedbackQualificationService:
    BUILD='410.0'; PACKAGE='410.0.0'; POLICY='phase18.feedback-qualification-service.v410'
    def __init__(self,db,audit,*,build409,qualification410,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build409=build409; self.qualification410=qualification410; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build409,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def feedback_qualification_status(self):
        s=self.qualification410.status(); checks={'version_coherent':self.version_status()['coherent'],**s['checks']}
        return {**s,'checks':checks,'feedback_qualification_gate_pass':all(checks.values()),'production_release_ready':False}
    def phase18_status(self,case_id=''):
        p=dict(self.build409.phase18_status(case_id)); s=self.feedback_qualification_status(); p.update({'build':self.BUILD,'phase18_builds_completed':10,'feedback_qualification':True,'feedback_qualification_gate_pass':s['feedback_qualification_gate_pass'],'public_feedback_due':True,'production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.feedback_qualification_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['feedback_qualification_gate_pass'],'public_feedback_due':True,'production_release_ready':False}
