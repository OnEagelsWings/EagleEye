from __future__ import annotations
import hashlib,json,re
from pathlib import Path

def _read(p):
    try:
        v=json.loads(Path(p).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
class Build398ModelHoldoutService:
    BUILD='398.0'; PACKAGE='398.0.0'; POLICY='phase17.model-holdout-human-eval.v398'
    def __init__(self,db,audit,*,build397,holdout398,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build397=build397; self.holdout398=holdout398; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build397,n,None)
        if v is None: raise AttributeError(n)
        return v
    def _fingerprint_paths(self):
        return ('eagleeye_pro/phase17/model_holdout398.py','eagleeye_pro/phase17/fixtures/holdout398_cases.json','eagleeye_pro/phase17/__init__.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build398/service.py','src/eagleeye/interfaces/web/app398.py','src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_398_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build398_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_398_0.py','tools/benchmark_build398.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); g=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); p=g(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def schema_metrics(self):
        _=self.holdout398.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); c={r['type']:int(r['c']) for r in rows}; integ=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); req={'holdout_suite_398','holdout_case_398','holdout_run_398','holdout_review_398','holdout_baseline_398'}; present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; return {'tables':c.get('table',0),'indexes':c.get('index',0),'triggers':c.get('trigger',0),'views':c.get('view',0),'integrity_check':integ,'build398_tables_present':req.issubset(present),'within_phase17_gate':c.get('table',0)<350 and c.get('index',0)<570 and integ=='ok' and req.issubset(present)}
    def _evidence(self,f):
        v=_read(self.install_dir/f); return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def historical_build397_receipt(self):
        r=_read(self.install_dir/'RELEASE_MANIFEST_BUILD_397_0.json'); return {'build':'397.0','valid':bool(r.get('build')=='397.0' and r.get('production_release_ready') is False and int(((r.get('regression') or {}).get('phase15_16') or {}).get('functional_regressions',-1))==0),'code_fingerprint':r.get('code_fingerprint','')}
    def phase17_status(self,case_id=''):
        o=dict(self.build397.phase17_status(case_id)); q=self.holdout398.qualification_status(); o.update({'build':self.BUILD,'phase17_builds_completed':18,'model_holdout_framework':True,'bundled_holdout_cases':60,'internal_structural_baseline':True,'real_model_human_holdout_qualified':bool(q.get('external_holdout_qualified')),'real_model_runs':q.get('real_model_runs',0),'human_reviewed_cases':q.get('human_reviewed_cases',0),'production_release_ready':False,'execution_authority':False}); return o
    def qualified_gate(self):
        v=self.version_status(); s=self.schema_metrics(); pred=self.historical_build397_receipt(); st=self.holdout398.status(); tests=self._evidence('BUILD_398_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_398_HOLDOUT.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_398_0.json'); ext=_read(self.install_dir/'MODEL_HOLDOUT_QUALIFICATION_BUILD_398.json'); checks={'version_coherent':v['coherent'],'schema_integrity':s['within_phase17_gate'],'phase17_predecessor_gate':pred['valid'],'build398_tests':bool(tests),'build398_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build398_acceptance':bool(acc),'minimum_50_case_framework':st['bundled_fixture_cases']>=50,'frozen_suite_supported':st['frozen_suite_supported'],'human_review_required':st['human_review_required_for_qualification'],'external_model_required':st['external_real_model_required_for_qualification'],'no_fake_external_qualification':ext.get('external_holdout_qualified') is False,'no_direct_fetch':not st['direct_network_fetch'],'no_execution_authority':not st['execution_authority'],'no_auto_go':not st['automatic_go'],'no_auto_evidence_promotion':not st['automatic_evidence_promotion'],'no_truth_probability_training':not st['truth_probability_training']}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':18,'external_holdout_qualified':False,'production_release_ready':False,'professional_pilot_line_preserved':pred['valid']}
