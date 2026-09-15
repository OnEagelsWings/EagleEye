from __future__ import annotations
import io,json,tempfile
from pathlib import Path
from PIL import Image
from eagleeye_pro.core.app_context import AppContext

def png():
    b=io.BytesIO();Image.new('RGB',(40,30),(30,80,120)).save(b,format='PNG');return b.getvalue()

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='validate377') as c:
        u=c.team_identity_359.create_initial_admin(username='validate377',display_name='Validate 377',password='Orbit-Pine-Quartz-377!');ident={**u,'session_id':'validate377'}
        cid=c.build377.team_create_case(identity=ident,title='Image Validation 377',client='QA',purpose='local deterministic image pipeline validation',legal_basis='public_data')['case_id']
        data=png();a=c.build377.image_ingest(case_id=cid,content=data,declared_media_type='image/png',filename='fixture.png');b=c.build377.image_ingest(case_id=cid,content=data,declared_media_type='image/png',filename='fixture-dup.png')
        summary=c.build377.image_case_summary(case_id=cid);pressure=c.build377.image_storage_pressure(case_id=cid)
        checks={
            'local_ingest':a['new_object_written'] is True,
            'exact_dedup':b['deduplicated'] is True and b['new_object_written'] is False,
            'same_media_on_duplicate':a['media_id']==b['media_id'],
            'handoff_network_budget_zero':a['handoff']['payload']['network_used'] is False,
            'identity_not_confirmed':summary['identity_confirmed'] is False,
            'scene_not_confirmed':summary['scene_location_confirmed'] is False,
            'storage_pressure_visible':pressure['state'] in {'normal','soft_limit','hard_limit'},
            'external_network_used_false':summary['external_network_used'] is False,
        }
        result='pass' if all(checks.values()) else 'fail'
        out={'build':'377.0','code_fingerprint':c.build377.code_fingerprint(),'result':result,'local_image_pipeline_validation':result,'checks':checks,'external_image_source_validation':'not_run','external_reverse_image_provider_validation':'not_run','external_image_analyst_validation':'not_run','external_network_used':False,'truthful_note':'Deterministic local image/media pipeline validation only; no external provider or internet image validation was performed.'}
    path=root/'LIVE_VALIDATION_BUILD_377_IMAGE_PIPELINE.json';path.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if result=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
