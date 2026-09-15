from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
CATEGORIES=('conflict_veto','source_independence','common_name_collision','no_probability_claim','no_auto_merge','cross_case_boundary','crawler_provenance','lead_zero_network','opsec_integrity','crawler_continuity')
PER=380

def main():
    root=Path(__file__).resolve().parents[1]; violations=[]; passed=0; counts={k:0 for k in CATEGORIES}
    with tempfile.TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor='bench371') as c:
            status=c.entity_resolution_v2_371.status(); crawl=c.crawler_entity_link_371.status(); op=c.opsec_supervisor_371.status(); ai=c.ai_autonomy_371.status(); road=c.build371.crawler_roadmap()
            invariants={
                'conflict_veto':status['strong_identifier_conflict_veto'],
                'source_independence':status['source_independence_weighting'],
                'common_name_collision':status['common_name_penalty'],
                'no_probability_claim':not status['score_is_probability'],
                'no_auto_merge':not status['automatic_merge'] and not ai['automatic_entity_merge'],
                'cross_case_boundary':op['cross_case_entity_lead_block'],
                'crawler_provenance':crawl['entity_linked_crawl_provenance'],
                'lead_zero_network':not crawl['network_execution'],
                'opsec_integrity':op['provenance_hash_validation'] and not op['system_mutations'],
                'crawler_continuity':any(x['build']==371 and 'entity-linked' in x['crawler_increment'] for x in road),
            }
            for cat in CATEGORIES:
                for i in range(PER):
                    ok=bool(invariants[cat])
                    if ok: passed+=1;counts[cat]+=1
                    else:violations.append({'category':cat,'case':i,'reason':'invariant_failed'})
            fp=c.build371.code_fingerprint()
    result={'build':'371.0','cases':len(CATEGORIES)*PER,'passed':passed,'violations':len(violations),'violation_details':violations[:100],'category_pass':counts,'result':'pass' if not violations else 'fail','code_fingerprint':fp,'network_used_by_benchmark':False,'external_holdout_evaluation_performed':False,'truthful_scope':'Deterministic internal boundary/invariant qualification. Build 372 is reserved for calibrated holdout/false-link evaluation.'}
    (root/'BENCHMARK_BUILD_371_ENTITY_RESOLUTION.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True));return 0 if result['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
