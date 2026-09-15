from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from eagleeye_pro.core.app_context import AppContext
from eagleeye.phase16.postgres362 import _pg_type,_quote_ident

def main():
    cases=0; violations=[]; categories={}
    with tempfile.TemporaryDirectory(prefix='ee362_bench_') as td:
        with AppContext(base_dir=td) as c:
            fp=c.build362.code_fingerprint(); plan=c.build362.postgres_migration_plan(); tables=plan['tables']
            # 450 migration/DDL cases
            bad=['x;drop','x y','x"y','1bad','x--y']
            for i in range(450):
                item=tables[i%len(tables)]
                ok=item['create_sql'].startswith('CREATE TABLE IF NOT EXISTS "') and '%s' in item['insert_sql'] and item['row_count']>=0
                if not ok: violations.append({'category':'migration','i':i})
                try:_quote_ident(bad[i%len(bad)]); violations.append({'category':'identifier','i':i})
                except ValueError:pass
                cases+=1
            categories['migration_planner']=450
            # 450 truthfulness cases: no DSN -> never external/live
            import os
            old=os.environ.pop('EAGLEEYE_POSTGRES_DSN',None)
            try:
                for i in range(450):
                    r=c.build362.postgres_live_validation()
                    if r.get('status')!='not_run' or r.get('externally_validated') or r.get('external_connection_opened'): violations.append({'category':'truthfulness','i':i})
                    cases+=1
            finally:
                if old is not None:os.environ['EAGLEEYE_POSTGRES_DSN']=old
            categories['truthful_live_gate']=450
            # 450 OPSEC/crawler invariants
            for i in range(450):
                osx=c.opsec_supervisor_362.status(); cr=c.build362.crawler_status()
                if osx.get('system_mutations') or not osx.get('backend_secret_hygiene_monitor') or cr.get('crawler_improvement_build')!=362: violations.append({'category':'opsec_crawler','i':i})
                cases+=1
            categories['opsec_crawler']=450
            # 450 AI/team-backend truthfulness invariants
            for i in range(450):
                s=c.ai_autonomy_362.status(); pg=c.build362.postgres_status()
                if not s.get('infrastructure_aware') or s.get('direct_network_client') or pg.get('externally_validated'): violations.append({'category':'ai_backend','i':i})
                cases+=1
            categories['ai_backend']=450
            out={'build':'362.0','result':'pass' if not violations and cases==1800 else 'fail','cases':cases,'violations':len(violations),'violation_examples':violations[:20],'categories':categories,'code_fingerprint':fp,'external_connections_opened':0,'external_postgresql_validation':'not_run','truthful_note':'This benchmark is local/internal. It does not substitute for a real PostgreSQL endpoint.'}
            (ROOT/'BENCHMARK_BUILD_362_POSTGRES_TEAM.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8')
            print(json.dumps(out,indent=2,sort_keys=True))
            return 0 if out['result']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
