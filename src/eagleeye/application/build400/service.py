from __future__ import annotations
import hashlib,json,re
from pathlib import Path

def _read(p):
    try:
        v=json.loads(Path(p).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build400Phase17FinalAcceptanceService:
    BUILD='400.0'; PACKAGE='400.0.0'; POLICY='phase17.final-end-to-end-acceptance.v400'
    def __init__(self,db,audit,*,build399,acceptance400,install_dir,base_dir,actor='local-analyst'):
        self.db=db;self.audit=audit;self.build399=build399;self.acceptance400=acceptance400;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'):raise AttributeError(n)
        v=getattr(self.build399,n,None)
        if v is None:raise AttributeError(n)
        return v
    def _fingerprint_paths(self):return ('eagleeye_pro/phase17/final_acceptance400.py','eagleeye_pro/phase17/__init__.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build400/service.py','src/eagleeye/interfaces/web/app400.py','src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_400_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build400_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_400_0.py','tools/benchmark_build400.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text();pt=(self.install_dir/'pyproject.toml').read_text();g=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown');r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);p=g(r'^version\s*=\s*["\']([^"\']+)',pt);return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def schema_metrics(self):
        _=self.acceptance400.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type");c={r['type']:int(r['c']) for r in rows};integ=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown');req={'phase17_acceptance_run_400','phase17_acceptance_step_400','phase17_acceptance_review_400'};present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")};return {'tables':c.get('table',0),'indexes':c.get('index',0),'triggers':c.get('trigger',0),'views':c.get('view',0),'integrity_check':integ,'build400_tables_present':req.issubset(present),'within_phase17_gate':c.get('table',0)<370 and c.get('index',0)<610 and integ=='ok' and req.issubset(present)}
    def _evidence(self,f):
        v=_read(self.install_dir/f);return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def historical_build399_receipt(self):
        r=_read(self.install_dir/'RELEASE_MANIFEST_BUILD_399_0.json');valid=bool(r.get('build')=='399.0' and r.get('production_release_ready') is False and int((r.get('regression') or {}).get('functional_regressions',-1))==0);return {'build':'399.0','valid':valid,'code_fingerprint':r.get('code_fingerprint','')}
    def phase17_status(self,case_id=''):
        o=dict(self.build399.phase17_status(case_id));st=self.acceptance400.status();latest=self.acceptance400.latest(case_id);o.update(st);o.update({'build':self.BUILD,'phase17_builds_completed':20,'phase17_internal_acceptance':bool(latest and latest['internal_acceptance'] and latest.get('review') and latest['review']['disposition']=='accept_internal_phase17'),'phase18_entry_ready':bool(latest and latest['phase18_entry_ready'] and latest.get('review') and latest['review'].get('disposition')=='accept_internal_phase17'),'production_release_ready':False});return o
    def run_phase17_acceptance(self,**k):return self.acceptance400.run_acceptance(**k)
    def review_phase17_acceptance(self,**k):return self.acceptance400.review(**k)
    def phase17_acceptance(self,run_id):return self.acceptance400.acceptance(run_id)
    def verify_phase17_acceptance(self,run_id):return self.acceptance400.verify(run_id)
    def export_phase17_acceptance(self,*,run_id,outdir=None):return self.acceptance400.export_dossier(run_id=run_id,outdir=outdir or (self.base_dir/'reports'/'phase17_400'))
    def qualified_gate(self):
        v=self.version_status();s=self.schema_metrics();pred=self.historical_build399_receipt();tests=self._evidence('BUILD_400_TEST_EVIDENCE.json');bench=self._evidence('BENCHMARK_BUILD_400_FINAL_ACCEPTANCE.json');acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_400_0.json');final=_read(self.install_dir/'PHASE17_FINAL_ACCEPTANCE_BUILD_400.json');st=self.acceptance400.status();checks={'version_coherent':v['coherent'],'schema_integrity':s['within_phase17_gate'],'phase17_predecessor_gate':pred['valid'],'build400_tests':bool(tests),'build400_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build400_acceptance':bool(acc),'internal_phase17_acceptance':final.get('internal_phase17_complete') is True,'phase18_entry_ready':final.get('phase18_entry_ready') is True,'external_holdout_truthful':final.get('external_holdout_qualified') is False,'external_soak_truthful':final.get('external_72h_soak_qualified') is False,'production_not_falsely_released':final.get('production_release_ready') is False,'no_direct_fetch':not st['direct_network_fetch'],'no_execution_authority':not st['execution_authority'],'no_auto_go':not st['automatic_go'],'no_auto_live':not st['automatic_live_confirmation'],'no_auto_evidence_promotion':not st['automatic_evidence_promotion'],'no_auto_truth':not st['automatic_truth_acceptance']};return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':20,'phase17_internal_complete':final.get('internal_phase17_complete') is True,'phase18_entry_ready':final.get('phase18_entry_ready') is True,'external_holdout_qualified':False,'external_72h_soak_qualified':False,'professional_pilot_ready':True,'broad_live_research_ready':False,'production_release_ready':False}
