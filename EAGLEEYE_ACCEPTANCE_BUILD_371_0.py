from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor='accept371') as c:
            v=c.build371.version_status();m=c.build371.schema_metrics();g=c.build371.qualified_gate();er=c.entity_resolution_v2_371.status();cr=c.crawler_entity_link_371.status();ai=c.ai_autonomy_371.status();op=c.opsec_supervisor_371.status();crawler=c.build371.crawler_status();live=c.build371._live_validation()
            checks={
                'version_coherent':v['coherent'],'schema_gate':m['within_gate'],'activated_schema_counts':(m['table'],m['index'],m['trigger'])==(165,133,8),'no_build371_specific_tables':m['build371_specific_tables_added']==0,
                'test_evidence_current':bool(c.build371._test_evidence()),'benchmark_current':bool(c.build371._benchmark()),'local_entity_crawler_validation':live.get('local_entity_crawler_validation')=='pass',
                'conflict_veto':er['strong_identifier_conflict_veto'],'source_independence':er['source_independence_weighting'],'common_name_penalty':er['common_name_penalty'],'score_not_probability':not er['score_is_probability'],
                'no_auto_identity':not er['automatic_identity_confirmation'],'no_auto_merge':not er['automatic_merge'] and not ai['automatic_entity_merge'],'independent_review':er['independent_human_review_required'],
                'crawler_entity_provenance':crawler['entity_linked_crawl_provenance'],'source_entity_lead_queue':crawler['source_to_entity_lead_queue'],'lead_zero_network':not cr['network_execution'],'opsec_provenance_validation':op['provenance_hash_validation'],
                'no_system_mutation':not op['system_mutations'],'crawler_continuity':crawler['continuous_crawler_expansion_370_380'],'truthful_release':g['production_release_ready'] is False and g['entity_resolution_external_evaluation']=='scheduled_build_372'}
            result={'build':'371.0','checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':g['build_acceptance_ready'],'production_release_ready':False,'code_fingerprint':c.build371.code_fingerprint(),'schema':m}
    (root/'ACCEPTANCE_RESULTS_BUILD_371_0.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True));raise SystemExit(0 if result['result']=='pass' and result['build_acceptance_ready'] else 1)
if __name__=='__main__':main()
