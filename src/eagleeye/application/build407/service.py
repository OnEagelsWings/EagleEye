from __future__ import annotations
import re
from pathlib import Path
class Build407ConnectorDataFabricService:
    BUILD='407.0'; PACKAGE='407.0.0'; POLICY='phase18.connector-data-fabric-service.v407'
    def __init__(self,db,audit,*,build406,fabric407,registry405,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build406=build406; self.fabric407=fabric407; self.registry405=registry405; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build406,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def data_fabric_status(self):
        prev=self.build406.remediation_status(); registry=self.registry405.verify_integrity(); fabric=self.fabric407.verify_integrity(); st=self.fabric407.status(); prev_security={k:v for k,v in prev['checks'].items() if k!='version_coherent'}; checks={'version_coherent':self.version_status()['coherent'],'build406_security_invariants':all(prev_security.values()),'source_registry_integrity':registry['valid'],'fabric_integrity':fabric['valid'],'network_execution_disabled':st['network_execution'] is False,'automatic_evidence_promotion_disabled':st['automatic_evidence_promotion'] is False,'provenance_required':st['provenance_required'] is True}; return {**st,'checks':checks,'data_fabric_gate_pass':all(checks.values()),'production_release_ready':False,'next_feedback_check':'after build 408 at latest'}
    def adapters(self): return self.fabric407.adapters()
    def plan(self,**kwargs): return self.fabric407.plan(**kwargs)
    def import_result(self,**kwargs): return self.fabric407.import_result(**kwargs)
    def phase18_status(self,case_id=''):
        p=dict(self.build406.phase18_status(case_id)); s=self.data_fabric_status(); p.update({'build':self.BUILD,'phase18_builds_completed':7,'connector_data_fabric':True,'connector_adapters':s['adapters'],'data_fabric_gate_pass':s['data_fabric_gate_pass'],'next_feedback_check':'after build 408 at latest','production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.data_fabric_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['data_fabric_gate_pass'],'production_release_ready':False}
