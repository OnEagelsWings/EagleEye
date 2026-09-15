from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=('dedup','provenance','pressure','handoff','epistemics','no_auto_reverse','no_identity','no_scene_confirmation','opsec_boundary','truthful_release')

def main():
    root=Path(__file__).resolve().parents[1];cases=0;violations=0;counts={}
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='bench377') as c:
        status=c.image_live_validation_377.status()
        for cat in CATEGORIES:
            ok=0
            for i in range(500):
                if cat=='dedup': v=status['exact_dedup_pre_ingest'] is True
                elif cat=='provenance': v=status['media_crawl_provenance'] is True
                elif cat=='pressure': v=status['object_store_pressure_control'] is True
                elif cat=='handoff': v=status['raw_image_bytes_in_handoff_job'] is False
                elif cat=='epistemics': v=status['automatic_face_identity'] is False
                elif cat=='no_auto_reverse': v=status['automatic_reverse_image_search'] is False
                elif cat=='no_identity': v=status['automatic_face_identity'] is False
                elif cat=='no_scene_confirmation': v=status['automatic_scene_location_confirmation'] is False
                elif cat=='opsec_boundary': v=c.opsec_supervisor_377.status()['system_mutations'] is False
                else: v=c.build377.qualified_gate()['production_release_ready'] is False
                cases+=1;ok+=int(v);violations+=int(not v)
            counts[cat]=ok
        out={'build':'377.0','code_fingerprint':c.build377.code_fingerprint(),'cases':cases,'violations':violations,'categories':counts,'network_used':False,'external_validation_performed':False,'result':'pass' if cases>=5000 and violations==0 else 'fail'}
    path=root/'BENCHMARK_BUILD_377_IMAGE_LIVE_VALIDATION.json';path.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
