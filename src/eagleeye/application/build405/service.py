from __future__ import annotations
import re
from pathlib import Path

class Build405SourceRegistryV2Service:
    BUILD='405.0'; PACKAGE='405.0.0'; POLICY='phase18.source-registry-v2.v405'
    def __init__(self,db,audit,*,build404,registry405,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build404=build404; self.registry405=registry405; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build404,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def source_registry_status(self): return self.registry405.status()
    def source_registry_integrity(self): return self.registry405.verify_integrity()
    def sources(self): return self.registry405.list_sources()
    def phase18_status(self,case_id=''):
        p=dict(self.build404.phase18_status(case_id)); s=self.source_registry_status(); p.update({'build':self.BUILD,'phase':18,'phase18_builds_completed':5,'source_registry_v2':True,'source_registry_sources':s['sources'],'source_registry_metadata_complete':s['metadata_complete'],'five_build_feedback_cycle_complete':True,'public_feedback_due':True,'next_public_feedback_build':'405.0','production_release_ready':False}); return p
    def qualified_gate(self):
        v=self.version_status(); s=self.source_registry_status(); i=self.source_registry_integrity(); rg=self.build404.review_gate_status(); checks={'version_coherent':v['coherent'],'source_metadata_present':s['sources']>0,'source_metadata_complete':s['metadata_complete']==s['sources'],'source_integrity':i['valid'],'ai_review_gate_pass':rg['ai_review_gate_pass'],'no_network_execution':not s['network_execution'],'no_auto_live_enablement':not s['automatic_live_enablement'],'production_not_released':not s.get('production_release_ready',False)}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'feedback_cycle_complete':True,'production_release_ready':False}
