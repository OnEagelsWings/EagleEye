from __future__ import annotations
import json,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from eagleeye_pro.core.app_context import AppContext

def main():
    with tempfile.TemporaryDirectory(prefix='ee362_accept_') as td:
        with AppContext(base_dir=td) as c:
            m=c.build362.schema_metrics();v=c.build362.version_status();pg=c.build362.postgres_status();g=c.build362.qualified_gate();rollback=c.build362.local_rollback_drill()
            checks={'schema':bool(m['within_gate']),'version':bool(v['coherent']),'postgres_contract':c.build362._probe('postgres'),'migration':c.build362._probe('migration'),'rollback':rollback['status']=='pass','ai':c.build362._probe('ai'),'opsec':c.build362._probe('opsec'),'crawler':c.build362._probe('crawler'),'benchmark':bool(c.build362._benchmark()),'truthfulness':not pg['externally_validated'] and not g['production_release_ready'],'gate':bool(g['build_acceptance_ready'])}
            out={'build':'362.0','result':'pass' if all(checks.values()) else 'fail','checks':checks,'schema':m,'version':v,'postgres':pg,'gate':g,'external_connections_opened':0,'external_postgresql_validation':'not_run'}
            (ROOT/'ACCEPTANCE_RESULTS_BUILD_362_0.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2,sort_keys=True));return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
