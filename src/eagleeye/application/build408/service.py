from __future__ import annotations
import re
from pathlib import Path

class Build408FederatedSearchService:
    BUILD='408.0'; PACKAGE='408.0.0'; POLICY='phase18.federated-search-service.v408'
    def __init__(self,db,audit,*,build407,search408,registry405,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build407=build407; self.search408=search408; self.registry405=registry405; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build407,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def federated_search_status(self):
        prev=self.build407.data_fabric_status(); prev_checks={k:v for k,v in prev['checks'].items() if k!='version_coherent'}
        reg=self.registry405.verify_integrity(); integ=self.search408.verify_integrity(); st=self.search408.status()
        checks={'version_coherent':self.version_status()['coherent'],'build407_security_invariants':all(prev_checks.values()),'source_registry_integrity':reg['valid'],'source_health_history_integrity':reg.get('health_history_valid') is True,'federated_search_integrity':integ['valid'],'network_execution_disabled':st['network_execution'] is False,'automatic_go_disabled':st['automatic_go'] is False,'automatic_evidence_promotion_disabled':st['automatic_evidence_promotion'] is False,'provenance_required':st['provenance_required'] is True}
        return {**st,'checks':checks,'federated_search_gate_pass':all(checks.values()),'production_release_ready':False,'feedback_checked_before_build':True,'next_public_feedback_build':'410.0'}
    def create_search(self,**kwargs): return self.search408.create_search(**kwargs)
    def import_results(self,**kwargs): return self.search408.import_results(**kwargs)
    def merged_results(self,search_id): return self.search408.merged_results(search_id)
    def phase18_status(self,case_id=''):
        p=dict(self.build407.phase18_status(case_id)); s=self.federated_search_status(); p.update({'build':self.BUILD,'phase18_builds_completed':8,'federated_search':True,'federated_search_gate_pass':s['federated_search_gate_pass'],'feedback_checked_before_build':True,'production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.federated_search_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['federated_search_gate_pass'],'production_release_ready':False}
