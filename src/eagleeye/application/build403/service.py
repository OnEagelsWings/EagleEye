from __future__ import annotations
import re
from pathlib import Path

class Build403NegativePathFrameworkService:
    BUILD="403.0"; PACKAGE="403.0.0"; POLICY="phase18.negative-path-abuse-framework.v403"
    def __init__(self,db,audit,*,build402,framework403,install_dir,actor="local-analyst"):
        self.db=db; self.audit=audit; self.build402=build402; self.framework403=framework403; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build402,name,None)
        if value is None: raise AttributeError(name)
        return value
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def negative_path_catalog(self): return self.framework403.catalog()
    def negative_path_audit(self): return self.framework403.contract_audit()
    def negative_path_runtime_probes(self): return self.framework403.safe_runtime_probes()
    def negative_path_status(self): return self.framework403.evaluate()
    def phase18_status(self,case_id=''):
        p=dict(self.build402.phase18_status(case_id)); n=self.negative_path_status(); p.update({'build':self.BUILD,'phase':18,'phase18_builds_completed':3,'negative_path_framework':n['negative_path_framework_ready'],'negative_path_scenarios':n['scenario_count'],'github_feedback_integrated':True,'five_build_feedback_cycle':True,'next_public_feedback_build':'405.0','production_release_ready':False}); return p
    def qualified_gate(self):
        v=self.version_status(); a=self.build402.authorization_audit(); r=self.build402.role_matrix(); n=self.negative_path_status(); checks={'version_coherent':v['coherent'],'build402_authorization_audit_preserved':a['authorization_audit_pass'],'build402_read_only_boundary_preserved':r['read_only_has_mutation_capability'] is False,'negative_contract_audit_pass':n['contract_audit_pass'],'negative_runtime_probe_pass':n['runtime_probe_pass'],'scenario_catalog_populated':n['scenario_count']>=15,'production_not_released':n['production_release_ready'] is False}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'production_release_ready':False}
