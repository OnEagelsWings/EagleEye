from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='accept380') as c:
        gate=c.build380.qualified_gate(); decision=c.build380.final_decision(); slo=c.build380.final_crawler_slo_gate(); tele=c.build380.pilot_telemetry(); matrix=c.build380.external_validation_matrix(); ai=c.ai_autonomy_380.status(); opsec=c.opsec_supervisor_380.status()
        checks={
            'build_acceptance_ready':gate['build_acceptance_ready'],
            'phase16_complete':gate['phase16_complete'] and c.build380.phase16_status()['builds_completed']==20,
            'version_coherent':c.build380.version_status()['coherent'],
            'schema_within_gate':c.build380.schema_metrics()['within_gate'],
            'no_new_tables':c.build380.schema_metrics()['build380_new_tables']==0,
            'historical_379_evidence':c.build380._historical_379_ready(),
            'pilot_slo_gate':slo['pilot_slo_gate_pass'] is True,
            'production_slo_gate_false':slo['production_slo_gate_pass'] is False,
            'decision_professional_pilot_only':decision['decision']=='professional_pilot_only',
            'professional_pilot_ready':decision['professional_pilot_ready'] is True,
            'production_candidate_false':decision['production_candidate'] is False,
            'production_release_false':decision['production_release_ready'] is False and gate['production_release_ready'] is False,
            'external_qualification_not_run':decision['external_qualification_validated'] is False and matrix['build379_independent_operational_qualification']=='not_run',
            'external_gaps_visible':len(decision['remaining_external_validation_items'])>=10,
            'telemetry_no_network':tele['network_execution_by_telemetry'] is False,
            'no_auto_promotion':decision['automatic_production_promotion'] is False,
            'ai_boundary':ai['production_decision_authority'] is False and ai['release_authority'] is False,
            'opsec_boundary':opsec['system_mutations'] is False and opsec['production_override_authority'] is False,
            'crawler_increment_380':c.build380.crawler_status()['crawler_improvement_build']==380,
            'crawler_continuity':c.build380.crawler_status()['continuous_crawler_expansion_370_380'] is True,
        }
        out={'build':'380.0','code_fingerprint':c.build380.code_fingerprint(),'checks':checks,'passed':sum(bool(x) for x in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':all(checks.values()),'phase16_complete':all(checks.values()),'final_decision':decision['decision'],'professional_pilot_ready':decision['professional_pilot_ready'],'production_candidate':False,'production_release_ready':False,'external_qualification_validated':False}
    (root/'ACCEPTANCE_RESULTS_BUILD_380_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
