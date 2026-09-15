from __future__ import annotations
import hashlib, json, re
from pathlib import Path


def _read(path):
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception: return {}


class Build396CaseStateReconciliationService:
    BUILD='396.0'; PACKAGE='396.0.0'; POLICY='phase17.case-state-reconciliation-incremental-reanalysis-build.v396'
    def __init__(self,db,audit,*,build395,reconciliation396,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build395=build395; self.reconciliation396=reconciliation396; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build395,n,None)
        if v is None: raise AttributeError(n)
        return v
    def _fingerprint_paths(self):
        return ('eagleeye_pro/phase17/case_reconciliation396.py','eagleeye_pro/phase17/__init__.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build396/service.py','src/eagleeye/interfaces/web/app396.py','src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_396_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build396_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_396_0.py','tools/benchmark_build396.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); g=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); p=g(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def schema_metrics(self):
        _=self.reconciliation396.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); c={r['type']:int(r['c']) for r in rows}; integ=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); req={'reconciliation_baseline_396','reconciliation_baseline_signal_396','reconciliation_scan_396','reconciliation_scan_signal_396','reconciliation_impact_396','reanalysis_proposal_396','reanalysis_review_396'}; present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; return {'tables':c.get('table',0),'indexes':c.get('index',0),'triggers':c.get('trigger',0),'views':c.get('view',0),'integrity_check':integ,'build396_tables_present':req.issubset(present),'within_phase17_gate':c.get('table',0)<320 and c.get('index',0)<520 and integ=='ok' and req.issubset(present)}
    def _evidence(self,filename):
        v=_read(self.install_dir/filename); return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def historical_build395_receipt(self):
        r=_read(self.install_dir/'RELEASE_MANIFEST_BUILD_395_0.json'); a=_read(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_395_0.json'); valid=r.get('build')=='395.0' and r.get('production_release_ready') is False and int((r.get('regression') or {}).get('functional_regressions',-1))==0 and (r.get('acceptance') or {}).get('result')=='pass' and a.get('build')=='395.0' and a.get('result')=='pass'; return {'build':'395.0','valid':bool(valid),'code_fingerprint':r.get('code_fingerprint',''),'production_release_ready':False}
    def create_reconciliation_baseline(self,**k): return self.reconciliation396.create_baseline(**k)
    def latest_reconciliation_baseline(self,**k): return self.reconciliation396.latest_baseline(**k)
    def reconcile_case_state(self,**k): return self.reconciliation396.scan(**k)
    def reconciliation_scan(self,**k): return self.reconciliation396.scan_result(**k)
    def propose_reanalysis(self,**k): return self.reconciliation396.propose_reanalysis(**k)
    def review_reanalysis(self,**k): return self.reconciliation396.review_reanalysis(**k)
    def create_reanalysis_branch(self,**k): return self.reconciliation396.create_reanalysis_branch(**k)
    def advance_reconciliation_baseline(self,**k): return self.reconciliation396.advance_baseline(**k)
    def reanalysis_proposal(self,**k): return self.reconciliation396.proposal(**k)
    def phase17_status(self,case_id=''):
        o=dict(self.build395.phase17_status(case_id)); o.update({'build':self.BUILD,'phase17_builds_completed':16,'incremental_reconciliation':True,'explicit_delta_baseline':True,'reanalysis_branches':True,'automatic_active_state_mutation':False,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False,'reconciliation':self.reconciliation396.status()}); return o
    def qualified_gate(self):
        v=self.version_status(); s=self.schema_metrics(); pred=self.historical_build395_receipt(); st=self.reconciliation396.status(); tests=self._evidence('BUILD_396_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_396_RECONCILIATION.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_396_0.json'); checks={'version_coherent':v['coherent'],'schema_integrity':s['within_phase17_gate'],'phase17_predecessor_gate':pred['valid'],'build396_tests':bool(tests),'build396_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build396_acceptance':bool(acc),'incremental_reconciliation':st['incremental_reconciliation'],'explicit_baseline':st['explicit_baseline'],'delta_only_signal_comparison':st['delta_only_signal_comparison'],'unmatched_evidence_preserved':st['unmatched_evidence_preserved'],'dependency_propagation':st['dependency_propagation'],'review_required_reanalysis':st['review_required_reanalysis'],'controlled_reanalysis_branch':st['controlled_reanalysis_branch'],'stale_generation_protection':st['stale_generation_protection'],'append_only_history':st['append_only_history'],'no_active_state_auto_mutation':not st['active_state_auto_mutation'],'no_auto_evidence_promotion':not st['automatic_evidence_promotion'],'no_auto_go':not st['automatic_go_issuance'],'no_live_confirmation':not st['automatic_live_confirmation'],'no_truth_probability':not st['truth_probability'],'no_auto_truth':not st['automatic_truth_acceptance'],'no_direct_fetch':not st['direct_network_fetch'],'no_execution_authority':not st['execution_authority']}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':16,'production_release_ready':False,'professional_pilot_line_preserved':pred['valid']}
