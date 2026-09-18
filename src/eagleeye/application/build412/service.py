from __future__ import annotations
import re
from pathlib import Path

class Build412RelationshipIntelligenceService:
    BUILD='412.0'; PACKAGE='412.0.0'; POLICY='phase18.relationship-intelligence-service.v412'
    def __init__(self,db,audit,*,build411,relationship412,registry405,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build411=build411; self.relationship412=relationship412; self.registry405=registry405; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build411,n,None)
        if v is None: raise AttributeError(n)
        return v
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); pick=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown')
        runtime=pick(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=pick(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def registry_remediation_status(self):
        st=self.registry405.status(); integ=self.registry405.verify_integrity()
        checks={
            'active_identity_required': st.get('active_identity_required') is True,
            'registry_reconciliation_required': st.get('registry_reconciliation_required') is True,
            'registry_integrity': integ.get('valid') is True,
            'registry_reconciled': integ.get('registry_reconciled') is True,
            'health_history_integrity': integ.get('health_history_valid') is True,
        }
        return {'build':self.BUILD,'checks':checks,'registry_remediation_gate_pass':all(checks.values()),'production_release_ready':False}
    def relationship_status(self):
        prev=self.build411.temporal_status(); prev_checks={k:v for k,v in prev['checks'].items() if k!='version_coherent'}; r=self.relationship412.status(); reg=self.registry_remediation_status()
        checks={
            'version_coherent':self.version_status()['coherent'],
            'build411_security_invariants':all(prev_checks.values()),
            'registry_remediation_gate_pass':reg['registry_remediation_gate_pass'],
            'explicit_relationships_only':r['explicit_structured_relationships_only'] and r['text_cooccurrence_relationships'] is False,
            'provenance_preserved':r['provenance_preserved'] is True,
            'no_entity_or_relationship_inference':r['entity_resolution_performed'] is False and r['relationship_inference_performed'] is False,
            'no_truth_or_execution':r['truth_determined'] is False and r['network_execution'] is False and r['execution_authority'] is False,
            'no_automatic_go_or_promotion':r['automatic_go'] is False and r['automatic_evidence_promotion'] is False,
        }
        return {'build':self.BUILD,'checks':checks,'relationship_intelligence_gate_pass':all(checks.values()),'production_release_ready':False}
    def relationship_graph(self,search_id): return self.relationship412.graph(search_id)
    def neighborhood(self,search_id,entity_id): return self.relationship412.neighborhood(search_id,entity_id)
    def relationship_paths(self,search_id,start_entity_id,end_entity_id,max_depth=4): return self.relationship412.paths(search_id,start_entity_id,end_entity_id,max_depth)
    def phase18_status(self,case_id=''):
        p=dict(self.build411.phase18_status(case_id)); s=self.relationship_status(); p.update({'build':self.BUILD,'phase18_builds_completed':12,'relationship_intelligence_graph':True,'relationship_intelligence_gate_pass':s['relationship_intelligence_gate_pass'],'feedback_checked_before_build':True,'next_feedback_check':'before build 413','production_release_ready':False}); return p
    def qualified_gate(self):
        s=self.relationship_status(); return {'build':self.BUILD,'checks':s['checks'],'build_acceptance_ready':s['relationship_intelligence_gate_pass'],'production_release_ready':False}
