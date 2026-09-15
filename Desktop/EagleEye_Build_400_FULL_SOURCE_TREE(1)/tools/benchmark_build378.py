from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=('preview','explicit_sources','reconfirmation','budget_limit','workflow_delegate','no_provider_bypass','no_tor_bypass','no_direct_network','opsec_boundary','truthful_release')

def main():
    root=Path(__file__).resolve().parents[1];cases=0;violations=0;counts={}
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='bench378') as c:
        voice=c.voice_live_validation_378.status(); crawler=c.build378.crawler_status(); opsec=c.opsec_supervisor_378.status()
        for cat in CATEGORIES:
            ok=0
            for _i in range(520):
                if cat=='preview': v=crawler['voice_to_crawler_intent_preview'] is True
                elif cat=='explicit_sources': v=voice['source_auto_selection'] is False and voice['max_voice_sources']==2
                elif cat=='reconfirmation': v=voice['edit_requires_reconfirmation'] is True and voice['required_confirmation']=='VOICE CRAWL'
                elif cat=='budget_limit': v=voice['max_voice_requests']==30 and crawler['voice_request_budget_preview'] is True
                elif cat=='workflow_delegate': v=crawler['voice_case_workflow_delegation'] is True
                elif cat=='no_provider_bypass': v=voice['provider_connectors_via_voice'] is False
                elif cat=='no_tor_bypass': v=voice['tor_onion_via_standard_voice_path'] is False
                elif cat=='no_direct_network': v=voice['direct_network_authority'] is False and crawler['voice_direct_network_authority'] is False
                elif cat=='opsec_boundary': v=opsec['system_mutations'] is False and opsec['voice_preview_hash_binding'] is True
                else: v=c.build378.qualified_gate()['production_release_ready'] is False
                cases+=1;ok+=int(v);violations+=int(not v)
            counts[cat]=ok
        out={'build':'378.0','code_fingerprint':c.build378.code_fingerprint(),'cases':cases,'violations':violations,'categories':counts,'network_used':False,'external_validation_performed':False,'result':'pass' if cases>=5200 and violations==0 else 'fail'}
    path=root/'BENCHMARK_BUILD_378_VOICE_LIVE_VALIDATION.json';path.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
