from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from eagleeye_pro.core.app_context import AppContext

def main():
    with tempfile.TemporaryDirectory(prefix='ee361_accept_') as td:
        with AppContext(base_dir=td) as c:
            m=c.build361.schema_metrics(); v=c.build361.version_status(); p=c.build361.phase16_status(); g=c.build361.qualified_gate()
            checks={
              'schema':bool(m['within_gate']), 'version':bool(v['coherent']), 'phase16':p['phase']=='16',
              'ai':c.ai_autonomy_361.status()['autonomous_after_go'], 'opsec':c.opsec_supervisor_361.status()['autonomous_defensive_supervision'],
              'osint':len(c.build361.validation_matrix())>=13, 'crawler':c.build361.crawler_status()['crawler_improvement_build']==361,
              'truthfulness':not g['production_release_ready'] and not g['external_validation_complete'], 'gate':bool(g['build_acceptance_ready'])}
            out={'build':'361.0','result':'pass' if all(checks.values()) else 'fail','checks':checks,'schema':m,'version':v,'gate':g,'external_connections_opened':0}
            (ROOT/'ACCEPTANCE_RESULTS_BUILD_361_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8')
            print(json.dumps(out,indent=2,sort_keys=True)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
