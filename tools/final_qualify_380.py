from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='final-qualify380') as c:
        slo=c.build380.final_crawler_slo_gate(); tele=c.build380.pilot_telemetry(); matrix=c.build380.external_validation_matrix(); readiness=c.professional_pilot_380.current_decision(local_ready=True)
        checks={
            'version_coherent':c.build380.version_status()['coherent'],
            'schema_within_gate':c.build380.schema_metrics()['within_gate'],
            'historical_379_evidence':c.build380._historical_379_ready(),
            'pilot_slo_pass':slo['pilot_slo_gate_pass'] is True,
            'production_slo_not_claimed':slo['production_slo_gate_pass'] is False and slo['external_slo_state']=='not_run',
            'telemetry_no_network':tele['network_execution_by_telemetry'] is False,
            'telemetry_no_workers':tele['background_workers_started_by_telemetry']==0,
            'runtime_ready':tele['runtime_ready_for_bounded_work'] is True,
            'no_cross_case_leaks':slo['local_metrics']['cross_case_leaks']==0,
            'no_evidence_loss':slo['local_metrics']['evidence_loss_events']==0,
            'no_unauthorized_network':slo['local_metrics']['unauthorized_network_escalations']==0,
            'current_decision_pilot_only':readiness['decision']=='professional_pilot_only',
            'production_false':readiness['production_candidate'] is False and readiness['production_release_ready'] is False,
            'external_receipt_not_run':matrix['build379_independent_operational_qualification']=='not_run',
            'external_gaps_visible':sum(v=='not_run' for v in matrix.values())>=10,
            'ai_no_release_authority':c.ai_autonomy_380.status()['release_authority'] is False,
            'opsec_no_system_mutation':c.opsec_supervisor_380.status()['system_mutations'] is False,
            'phase16_complete':c.professional_pilot_380.status()['phase16_builds_completed']==20,
        }
        out={'build':'380.0','code_fingerprint':c.build380.code_fingerprint(),'result':'pass' if all(checks.values()) else 'fail','checks':checks,'current_decision':'professional_pilot_only','professional_pilot_ready':all(checks.values()),'production_candidate':False,'production_release_ready':False,'external_qualification_validated':False,'network_used':False,'truthful_note':'Final local Phase-16 qualification. Controlled professional pilot is supported; general production candidacy is not claimed without independent Build-379 qualification.'}
    (root/'FINAL_QUALIFICATION_BUILD_380.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
