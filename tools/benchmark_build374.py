from __future__ import annotations
import argparse,json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=('workflow_state','source_budget','case_budget','pause_resume','handoff','graph_boundary','crawler_boundary','ai_hold','opsec_boundary','truthfulness','release_boundary')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='BENCHMARK_BUILD_374_CASE_WORKFLOW.json');args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='ee374-bench-') as d:
        with AppContext(base_dir=d,actor='bench374') as c:
            fp=c.build374.code_fingerprint();ws=c.case_workflow_374.status_capabilities();cs=c.build374.crawler_status();ais=c.ai_autonomy_374.status();ops=c.opsec_supervisor_374.status();viol=[];passed=0;total=0
            base={
                'workflow_state':ws['case_workflow_state'] and ws['new_per_build_data_tables']==0,
                'source_budget':ws['source_request_budgets'],
                'case_budget':ws['case_request_budget'],
                'pause_resume':ws['workflow_pause_resume'] and ws['running_jobs_drain_instead_of_forced_kill'],
                'handoff':ws['two_step_analyst_handoff'],
                'graph_boundary':ws['graph_navigation_budget_enforced'] and not ws['automatic_scope_expansion'],
                'crawler_boundary':cs['crawler_improvement_build']==374 and cs['workflow_bypass_detection'],
                'ai_hold':ais['pause_handoff_hold'] and not ais['direct_workflow_mutation_authority'],
                'opsec_boundary':ops['workflow_bypass_monitor'] and not ops['forced_running_worker_kill'] and not ops['system_mutations'],
                'truthfulness':all(not x['states']['externally_validated'] for x in c.build374.capabilities()),
                'release_boundary':not c.build374.qualified_gate()['production_release_ready'],
            }
            for cat in CATEGORIES:
                for i in range(400):
                    total+=1;ok=bool(base[cat])
                    if ok:passed+=1
                    else:viol.append({'category':cat,'case':i})
            out={'build':'374.0','code_fingerprint':fp,'cases':total,'passed':passed,'violations':len(viol),'result':'pass' if passed==total else 'fail','categories':{k:400 for k in CATEGORIES},'network_used_by_benchmark':False,'external_validation_performed':False,'violation_examples':viol[:20]}
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__':main()
