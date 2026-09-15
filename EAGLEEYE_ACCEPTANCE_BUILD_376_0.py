from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='accept376') as c:
        gate=c.build376.qualified_gate();schema=c.build376.schema_metrics();checks={
            'build_acceptance_ready':gate['build_acceptance_ready'],
            'version_coherent':c.build376.version_status()['coherent'],
            'schema_within_gate':schema['within_gate'],
            'no_new_tables':schema['dossier_vnext_new_tables']==0,
            'coverage_not_truth_probability':c.dossier_vnext_376.status()['coverage_is_truth_probability'] is False,
            'absence_not_nonexistence':c.dossier_vnext_376.status()['absence_is_nonexistence'] is False,
            'absence_not_default_counterevidence':c.dossier_vnext_376.status()['absence_is_counterevidence_by_default'] is False,
            'no_automatic_gap_closure':c.dossier_vnext_376.status()['automatic_gap_closure'] is False,
            'no_automatic_gap_crawl':c.dossier_vnext_376.status()['automatic_crawl_from_gap'] is False,
            'no_direct_network_authority':c.dossier_vnext_376.status()['direct_network_authority'] is False,
            'ai_no_gap_execution':c.ai_autonomy_376.status()['automatic_gap_closure'] is False,
            'opsec_gap_monitor':c.opsec_supervisor_376.status()['auto_gap_crawl_block'] is True,
            'external_validation_not_forged':gate['external_dossier_validation']=='not_run',
            'production_false':gate['production_release_ready'] is False,
            'no_literal_true_gate':c.build376.active_gate_literal_true_lines()==[],
        }
        out={'build':'376.0','result':'pass' if all(checks.values()) else 'fail','code_fingerprint':c.build376.code_fingerprint(),'checks':checks,'passed':sum(bool(v) for v in checks.values()),'total':len(checks),'schema':schema,'build_acceptance_ready':gate['build_acceptance_ready'],'production_release_ready':False,'external_network_used':False}
    (root/'ACCEPTANCE_RESULTS_BUILD_376_0.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
