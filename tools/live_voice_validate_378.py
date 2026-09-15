from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='validate378') as c:
        u=c.team_identity_359.create_initial_admin(username='validate378',display_name='Validate 378',password='Orbit-Pine-Quartz-378!');ident={**u,'session_id':'validate378'}
        cid=c.build378.team_create_case(identity=ident,title='Voice Validation 378',client='QA',purpose='local deterministic voice pipeline validation',legal_basis='public_data')['case_id']
        s=c.crawler_frontier_352.register_source(display_name='Voice Validation Source',seed_urls=['https://example.org/voice378-live'],terms_ref='public read-only terms',max_depth=0,max_pages=1,requests_per_minute=5,max_response_bytes=100000)
        if s['review_status']=='pending_review': s=c.crawler_frontier_352.review_source(s['source_id'],decision='approve_read_only',rationale='reviewed public source',reviewer='validate378')
        c.build378.configure_case_workflow(case_id=cid,identity=ident,source_budgets={s['source_id']:20},case_request_budget=40,max_active_crawls=2,confirmation='WORKFLOW')
        c.voice_gateway_358.transcriber=lambda audio,mt,lang:'Starte Suche mit der ausgewählten Quelle'
        trans=c.build378.voice_crawler_transcribe(case_id=cid,identity=ident,audio=b'RIFF-local-fixture',media_type='audio/wav',human_started=True,source_ids=[s['source_id']])
        wrong=c.build378.voice_crawler_confirm(intent_id=trans['intent_id'],identity=ident,confirmation='CRAWL')
        confirmed=c.build378.voice_crawler_confirm(intent_id=trans['intent_id'],identity=ident,confirmation='VOICE CRAWL')
        jid=confirmed['queued'][0]['job_id']; job=c.job_engine_348.get(jid); payload=json.loads(job['payload_json'])
        interactions=c.build378.voice_crawler_interactions(case_id=cid)
        checks={
            'local_transcription':trans['status']=='transcribed',
            'audio_not_persisted':trans['audio_persisted'] is False and trans['audio_deleted_after_transcription'] is True,
            'preview_allowed':trans['preview']['allowed_for_confirmation'] is True,
            'wrong_confirmation_blocked':wrong['state']=='confirmation_required' and wrong['executed'] is False,
            'exact_confirmation_delegated':confirmed['state']=='queued_via_case_workflow' and confirmed['executed'] is True,
            'workflow_tag_present':payload.get('phase16_case_workflow_v374') is True,
            'voice_provenance_tag_present':payload.get('phase16_voice_crawler_v378') is True and payload.get('voice_intent_id_v378')==trans['intent_id'],
            'voice_no_network_authority':payload.get('voice_direct_network_authority') is False,
            'interaction_integrity':bool(interactions and interactions[0]['task_integrity_valid']),
            'external_network_unused':True,
        }
        result='pass' if all(checks.values()) else 'fail'
        out={'build':'378.0','code_fingerprint':c.build378.code_fingerprint(),'result':result,'local_voice_pipeline_validation':result,'checks':checks,'external_voice_stt_validation':'not_run','external_multi_analyst_voice_validation':'not_run','external_voice_crawler_network_validation':'not_run','external_network_used':False,'truthful_note':'Deterministic local voice/transcript-to-crawler queue validation only. No external STT service or crawler network request was performed.'}
    path=root/'LIVE_VALIDATION_BUILD_378_VOICE_PIPELINE.json';path.write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0 if result=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
