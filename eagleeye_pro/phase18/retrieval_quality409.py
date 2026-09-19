from __future__ import annotations
from collections import Counter
import hashlib, json

BUILD='409.0'
POLICY_ID='phase18.retrieval-quality-coverage.v409'


def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class RetrievalQualityCoverage409:
    """Read-only quality/coverage analysis for Build-408 federated search.

    This module never determines truth, never promotes evidence and never performs
    network execution. It measures retrieval diversity and explicit coverage gaps.
    """
    def __init__(self,db,audit,*,search408,fabric407,registry405,actor='local-analyst'):
        self.db=db; self.audit=audit; self.search408=search408; self.fabric407=fabric407; self.registry405=registry405; self.actor=actor
    def _source_meta(self):
        out={}
        for a in self.fabric407.adapters():
            try: src=self.registry405.get(a['source_id'])
            except Exception: continue
            out[a['source_id']]={
                'adapter_kind':a['adapter_kind'],
                'remote':bool(a['remote']),
                'provenance_class':src.get('provenance_class','unknown'),
                'health_state':src.get('health_state','unknown'),
            }
        return out
    def assess(self,search_id):
        sess=self.search408.session(search_id); results=self.search408.merged_results(search_id); meta=self._source_meta()
        planned=[p['source_id'] for p in sess['source_plan']]
        observed=sorted({r['source_id'] for r in results})
        adapter_kinds=sorted({meta.get(s,{}).get('adapter_kind','unknown') for s in observed})
        provenance_classes=sorted({meta.get(s,{}).get('provenance_class','unknown') for s in observed})
        remote_states={bool(meta.get(s,{}).get('remote')) for s in observed}
        refs=[str(r.get('canonical_ref') or '').strip() for r in results if str(r.get('canonical_ref') or '').strip()]
        ref_hosts=[]
        for ref in refs:
            host=ref.split('://',1)[-1].split('/',1)[0].casefold()
            if host: ref_hosts.append(host)
        host_counts=Counter(ref_hosts)
        duplicate_host_pressure=max(host_counts.values())/len(ref_hosts) if ref_hosts else 0.0
        coverage={
            'planned_sources':len(planned),
            'observed_sources':len(observed),
            'source_coverage_ratio':round(len(observed)/len(planned),6) if planned else 0.0,
            'adapter_kind_count':len(adapter_kinds),
            'provenance_class_count':len(provenance_classes),
            'remote_local_mix':remote_states=={False,True},
            'canonical_host_count':len(host_counts),
            'duplicate_host_pressure':round(duplicate_host_pressure,6),
        }
        gaps=[]
        if not results: gaps.append('no_results_imported')
        if len(observed)<min(2,len(planned)): gaps.append('insufficient_source_diversity')
        if len(adapter_kinds)<min(2,len(set(p['adapter_kind'] for p in sess['source_plan']))): gaps.append('insufficient_adapter_diversity')
        if len(provenance_classes)<2 and len(observed)>=2: gaps.append('single_provenance_class')
        if refs and len(host_counts)<2 and len(observed)>=2: gaps.append('single_canonical_host')
        if duplicate_host_pressure>0.75 and len(ref_hosts)>=4: gaps.append('host_concentration_high')
        quality={
            'coverage':coverage,
            'observed_source_ids':observed,
            'adapter_kinds':adapter_kinds,
            'provenance_classes':provenance_classes,
            'gaps':gaps,
            'coverage_sufficient_for_analysis':not gaps,
            'truth_determined':False,
            'truth_probability':None,
            'evidence_promoted':False,
            'network_execution':False,
        }
        quality['assessment_hash']=_sha({'search_id':search_id,'quality':quality})
        return quality
    def compare(self,search_ids):
        rows=[{'search_id':sid,**self.assess(sid)} for sid in search_ids]
        return {'build':BUILD,'assessments':rows,'best_effort_only':True,'truth_ranking':False,'network_execution':False}
    def verify_integrity(self):
        s=self.status()
        forbidden=('truth_determined','execution_authority','automatic_evidence_promotion','network_execution','automatic_go')
        violations=[k for k in forbidden if s.get(k) is True]
        return {'build': BUILD, 'valid': not violations, 'violations': violations, 'contract':'static_capability_integrity'}

    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'retrieval_quality':True,'coverage_gap_detection':True,'source_diversity_metrics':True,'adapter_diversity_metrics':True,'provenance_diversity_metrics':True,'host_concentration_metric':True,'truth_determined':False,'execution_authority':False,'automatic_evidence_promotion':False,'network_execution':False}
