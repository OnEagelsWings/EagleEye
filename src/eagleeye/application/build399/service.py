from __future__ import annotations
import hashlib,json,re
from pathlib import Path

def _read(p):
    try:
        v=json.loads(Path(p).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
class Build399TargetEnvironmentQualificationService:
    BUILD='399.0'; PACKAGE='399.0.0'; POLICY='phase17.target-environment-soak-recovery.v399'
    def __init__(self,db,audit,*,build398,soak399,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build398=build398; self.soak399=soak399; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build398,n,None)
        if v is None: raise AttributeError(n)
        return v
    def _fingerprint_paths(self):
        return ('eagleeye_pro/phase17/target_soak399.py','eagleeye_pro/phase17/__init__.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build399/service.py','src/eagleeye/interfaces/web/app399.py','src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_399_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build399_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_399_0.py','tools/benchmark_build399.py','tools/build399_soak_bundle_template.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); g=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); p=g(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def schema_metrics(self):
        _=self.soak399.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); c={r['type']:int(r['c']) for r in rows}; integ=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); req={'soak_plan_399','soak_session_399','soak_sample_399','recovery_event_399','soak_review_399'}; present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; return {'tables':c.get('table',0),'indexes':c.get('index',0),'triggers':c.get('trigger',0),'views':c.get('view',0),'integrity_check':integ,'build399_tables_present':req.issubset(present),'within_phase17_gate':c.get('table',0)<360 and c.get('index',0)<590 and integ=='ok' and req.issubset(present)}
    def _evidence(self,f):
        v=_read(self.install_dir/f); return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def historical_build398_receipt(self):
        r=_read(self.install_dir/'RELEASE_MANIFEST_BUILD_398_0.json'); valid=bool(r.get('build')=='398.0' and r.get('production_release_ready') is False and int((r.get('regression') or {}).get('functional_regressions',-1))==0); return {'build':'398.0','valid':valid,'code_fingerprint':r.get('code_fingerprint','')}
    def phase17_status(self,case_id=''):
        o=dict(self.build398.phase17_status(case_id)); q=self.soak399.qualification_status(); h=self.build398.holdout398.qualification_status() if hasattr(self.build398,'holdout398') else {}
        o.update({'build':self.BUILD,'phase17_builds_completed':19,'target_environment_soak_framework':True,'required_soak_hours':72,'external_72h_soak_qualified':bool(q.get('external_72h_soak_qualified')),'external_soak_sessions':q.get('external_sessions',0),'real_model_human_holdout_qualified':bool(h.get('external_holdout_qualified')),'production_release_ready':False,'execution_authority':False}); return o
    def qualified_gate(self):
        v=self.version_status(); s=self.schema_metrics(); pred=self.historical_build398_receipt(); st=self.soak399.status(); tests=self._evidence('BUILD_399_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_399_SOAK_FRAMEWORK.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_399_0.json'); ext=_read(self.install_dir/'TARGET_ENVIRONMENT_QUALIFICATION_BUILD_399.json')
        checks={'version_coherent':v['coherent'],'schema_integrity':s['within_phase17_gate'],'phase17_predecessor_gate':pred['valid'],'build399_tests':bool(tests),'build399_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build399_acceptance':bool(acc),'72h_requirement':st['required_soak_hours']==72,'native_windows_required':st['native_windows_required'],'native_firefox_e2e_required':st['native_firefox_e2e_required'],'protected_profile_required':st['protected_firefox_profile_required'],'recovery_requirements':set(st['required_recovery_types'])=={'application_restart','firefox_restart'},'simulation_cannot_qualify':not st['simulation_can_qualify_external'],'no_fake_external_qualification':ext.get('external_72h_soak_qualified') is False,'no_direct_fetch':not st['direct_network_fetch'],'no_browser_launch_authority':not st['browser_launch_authority'],'no_execution_authority':not st['execution_authority'],'no_auto_go':not st['automatic_go'],'no_auto_evidence_promotion':not st['automatic_evidence_promotion']}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':19,'external_72h_soak_qualified':False,'production_release_ready':False,'professional_pilot_line_preserved':pred['valid']}
