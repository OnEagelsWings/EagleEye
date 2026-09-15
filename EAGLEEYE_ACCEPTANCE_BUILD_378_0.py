from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='accept378') as c:
        gate=c.build378.qualified_gate();schema=c.build378.schema_metrics();voice=c.voice_live_validation_378.status();crawler=c.build378.crawler_status();opsec=c.opsec_supervisor_378.status();checks={
            'build_acceptance_ready':gate['build_acceptance_ready'],
            'version_coherent':c.build378.version_status()['coherent'],
            'schema_within_gate':schema['within_gate'],
            'no_new_tables':schema['voice_validation_new_tables']==0,
            'push_to_talk':voice['push_to_talk'],
            'audio_not_persisted':voice['audio_persisted'] is False,
            'editable_reconfirmation':voice['edit_requires_reconfirmation'],
            'exact_confirmation':voice['required_confirmation']=='VOICE CRAWL',
            'explicit_sources':voice['source_auto_selection'] is False and voice['max_voice_sources']==2,
            'voice_budget_limit':voice['max_voice_requests']==30,
            'workflow_delegate':crawler['voice_case_workflow_delegation'],
            'preview_hash_provenance':crawler['voice_preview_hash_provenance'],
            'voice_no_direct_network':voice['direct_network_authority'] is False,
            'provider_gate_separate':voice['provider_connectors_via_voice'] is False,
            'tor_gate_separate':voice['tor_onion_via_standard_voice_path'] is False,
            'opsec_boundary':opsec['system_mutations'] is False and opsec['voice_confirmation_binding'],
            'external_validation_not_run':gate['external_voice_stt_validation']=='not_run' and gate['external_voice_crawler_network_validation']=='not_run',
            'production_false':gate['production_release_ready'] is False,
            'crawler_increment':crawler['crawler_improvement_build']==378,
        }
        out={'build':'378.0','code_fingerprint':c.build378.code_fingerprint(),'checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':all(checks.values()),'production_release_ready':False}
    (root/'ACCEPTANCE_RESULTS_BUILD_378_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
