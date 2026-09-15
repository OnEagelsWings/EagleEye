from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def run():
    with tempfile.TemporaryDirectory(prefix='ee363-accept-') as td:
        with AppContext(base_dir=Path(td)) as c:
            st=c.build363.storage_search_status(); gate=c.build363.qualified_gate(); m=c.build363.schema_metrics()
            probes={
              'schema': bool(m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)),
              'local_store': bool(st['s3']['local_cas_live']),
              'local_search': bool(st['team_search']['portable_fts5_live']),
              'truthful_s3': st['s3']['externally_validated'] is False,
              'truthful_team_search': st['team_search']['externally_validated'] is False,
              'ai': c.ai_autonomy_363.status()['storage_search_health_aware'],
              'opsec': c.opsec_supervisor_363.status()['storage_search_health_monitor'],
              'crawler': c.build363.crawler_status()['crawler_improvement_build']==363,
              'version': c.build363.version_status()['coherent'],
              'gate': gate['build_acceptance_ready'],
            }
            result={'build':'363.0','result':'pass' if all(probes.values()) else 'fail','probes':probes,'gate':gate,'schema':m,'network_used':False}
            return result
if __name__=='__main__': print(json.dumps(run(),indent=2,sort_keys=True))
