from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='accept377') as c:
        gate=c.build377.qualified_gate();schema=c.build377.schema_metrics();status=c.image_live_validation_377.status();checks={
            'build_acceptance_ready':gate['build_acceptance_ready'],
            'version_coherent':c.build377.version_status()['coherent'],
            'schema_within_gate':schema['within_gate'],
            'no_new_tables':schema['image_validation_new_tables']==0,
            'exact_dedup':status['exact_dedup_pre_ingest'],
            'media_provenance':status['media_crawl_provenance'],
            'pressure_control':status['object_store_pressure_control'],
            'image_agent_no_network':status['image_agent_network_authority'] is False,
            'no_auto_reverse':status['automatic_reverse_image_search'] is False,
            'no_face_identity':status['automatic_face_identity'] is False,
            'no_scene_confirmation':status['automatic_scene_location_confirmation'] is False,
            'handoff_no_raw_bytes':status['raw_image_bytes_in_handoff_job'] is False,
            'ai_no_direct_network':c.ai_autonomy_377.status()['direct_image_network_authority'] is False,
            'opsec_boundary':c.opsec_supervisor_377.status()['system_mutations'] is False,
            'external_validation_not_run':gate['external_image_source_validation']=='not_run',
            'production_false':gate['production_release_ready'] is False,
            'crawler_increment':c.build377.crawler_status()['crawler_improvement_build']==377,
        }
        out={'build':'377.0','code_fingerprint':c.build377.code_fingerprint(),'checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':all(checks.values()),'production_release_ready':False}
    (root/'ACCEPTANCE_RESULTS_BUILD_377_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
