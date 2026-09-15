from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def run():
    root=Path(__file__).resolve().parent
    live=json.loads((root/'LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json').read_text(encoding='utf-8'))
    bench=json.loads((root/'BENCHMARK_BUILD_364_REMOTE_TEAM.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='ee364-accept-') as td:
        with AppContext(base_dir=Path(td)) as c:
            st=c.build364.remote_team_status(); gate=c.build364.qualified_gate(); m=c.build364.schema_metrics()
            probes={
              'schema': bool(m['within_gate'] and (m['table'],m['index'],m['trigger'])==(141,128,8)),
              'version': c.build364.version_status()['coherent'],
              'remote_contract': c.build364._probe('remote_team'),
              'loopback_tls_live': bool(live.get('status')=='pass' and live.get('tls_handshake_verified_against_generated_ca') and live.get('clients')==2),
              'cross_case_live_denial': live.get('cross_case_denial_http_status')==403,
              'truthful_external': st['externally_validated'] is False and st['external_remote_clients_validated'] is False,
              'session_anomaly': c.opsec_supervisor_364.status()['remote_session_anomaly_monitor'],
              'ai': c.ai_autonomy_364.status()['remote_team_context_aware'],
              'opsec': c.opsec_supervisor_364.status()['session_revocation_allowed'] and not c.opsec_supervisor_364.status()['system_mutations'],
              'crawler': c.build364.crawler_status()['crawler_improvement_build']==364,
              'benchmark': bench.get('result')=='pass' and bench.get('cases')==2200 and bench.get('violations')==0,
              'gate': gate['build_acceptance_ready'],
            }
            result={'build':'364.0','result':'pass' if all(probes.values()) else 'fail','probes':probes,'gate':gate,'schema':m,'benchmark':{'cases':bench.get('cases'),'violations':bench.get('violations')},'live_transport':live,'network_used_by_acceptance':'real_loopback_tls_receipt_reused','external_network_used':False}
            return result
if __name__=='__main__': print(json.dumps(run(),indent=2,sort_keys=True))
