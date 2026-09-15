from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO

ROOT=Path(__file__).resolve().parent; OUT=ROOT/'ACCEPTANCE_RESULTS_BUILD_386_0.json'; PW='Acceptance-Orbit-Quartz-386!'

def main()->int:
    checks={}
    with tempfile.TemporaryDirectory(prefix='eagleeye386-accept-') as td:
        with AppContext(base_dir=Path(td), actor='accept386') as c:
            admin=c.team_identity_359.create_initial_admin(username='accept386',display_name='Acceptance 386',password=PW); ident={**admin,'session_id':'accept-session-386'}
            case=c.build380.team_create_case(identity=ident,title='Build386 acceptance',client='internal',purpose='authorized public-source capability grant qualification',legal_basis='public_data'); cid=case['case_id']
            checks['version_coherent']=bool(c.build386.version_status().get('coherent'))
            checks['schema_gate']=bool(c.build386.schema_metrics().get('within_phase17_gate'))
            checks['historical_build385_receipt']=bool(c.build386.historical_build385_receipt().get('valid'))
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='accept386',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='accept386')
            prepared=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE)
            sid=next(x['canonical_source_id'] for x in prepared['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='acceptance controlled read-only source',reviewer='accept386')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
            p=c.build386.execution_preflight(case_id=cid,packet_id=packet['packet_id'],identity=ident)
            checks['preflight_allowed']=p.get('allowed') is True
            checks['preflight_no_jobs_or_network']=p.get('jobs_created')==0 and p.get('network_requests_created')==0
            wrong=False
            try:c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation='YES')
            except PermissionError:wrong=True
            checks['exact_go_required']=wrong
            before=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {}).get('n') or 0)
            grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,ttl_minutes=5)
            after=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {}).get('n') or 0)
            checks['grant_creates_no_jobs']=before==after and grant.get('jobs_created')==0
            checks['grant_creates_no_network']=grant.get('network_requests_created')==0 and grant.get('direct_network_authority') is False
            row=c.db.one('SELECT token_hash,scope_json FROM execution_grant_386 WHERE grant_id=?',(grant['grant_id'],))
            checks['token_hash_only']=grant['grant_token'] not in row['scope_json'] and row['token_hash']!=grant['grant_token']
            verify=c.build386.verify_execution_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident)
            checks['grant_verifies']=verify.get('valid') is True
            checks['live_confirmation_still_required']=verify.get('required_execution_confirmation')=='LIVE'
            checks['no_automatic_execution']=verify.get('automatic_execution') is False
            checks['no_scope_expansion']=c.execution_authority_386.status().get('automatic_scope_expansion') is False
            checks['opsec_binding']=c.execution_authority_386.status().get('opsec_preflight_binding') is True
            checks['operations_binding']=c.execution_authority_386.status().get('operations_preflight_binding') is True
            checks['workflow_generation_binding']=c.execution_authority_386.status().get('workflow_generation_binding') is True
            checks['request_budget_binding']=c.execution_authority_386.status().get('request_budget_binding') is True
            code_fingerprint=c.build386.code_fingerprint()
    passed=sum(bool(v) for v in checks.values()); payload={'build':'386.0','code_fingerprint':code_fingerprint,'checks':checks,'passed':passed,'total':len(checks),'result':'pass' if passed==len(checks) else 'fail'}
    OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if payload['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
