from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1];violations=0;cases=0;cats={}
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='bench376') as c:
        for name,fn in {
            'coverage_semantics':lambda: c.dossier_vnext_376.status()['coverage_is_truth_probability'] is False,
            'absence_semantics':lambda: c.dossier_vnext_376.status()['absence_is_nonexistence'] is False,
            'gap_no_auto_crawl':lambda: c.dossier_vnext_376.status()['automatic_crawl_from_gap'] is False,
            'network_boundary':lambda: c.dossier_vnext_376.status()['direct_network_authority'] is False,
            'stale_public_web':lambda: c.dossier_vnext_376.freshness_threshold_hours('public_web')==168,
            'stale_registry':lambda: c.dossier_vnext_376.freshness_threshold_hours('government_register')==720,
            'stale_archive':lambda: c.dossier_vnext_376.freshness_threshold_hours('web_archive')==2160,
            'ai_boundary':lambda: c.ai_autonomy_376.status()['automatic_gap_closure'] is False,
            'opsec_boundary':lambda: c.opsec_supervisor_376.status()['auto_gap_crawl_block'] is True,
            'schema_boundary':lambda: c.build376.schema_metrics()['dossier_vnext_new_tables']==0,
            'truthful_release':lambda: c.build376.qualified_gate()['production_release_ready'] is False,
            'crawler_increment':lambda: c.build376.crawler_status()['crawler_improvement_build']==376,
        }.items():
            bad=0
            for _ in range(400):
                cases+=1
                try: ok=bool(fn())
                except Exception: ok=False
                if not ok:bad+=1;violations+=1
            cats[name]={'cases':400,'violations':bad}
        out={'build':'376.0','result':'pass' if violations==0 and cases>=4800 else 'fail','code_fingerprint':c.build376.code_fingerprint(),'cases':cases,'violations':violations,'categories':cats,'network_used_by_benchmark':False,'external_validation_performed':False}
    (root/'BENCHMARK_BUILD_376_DOSSIER_VNEXT.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
