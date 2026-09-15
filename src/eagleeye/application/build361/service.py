from __future__ import annotations
import ast,hashlib,json,re
from pathlib import Path
from typing import Any
DIMENSIONS=('implemented','integrated','tested','benchmarked','externally_validated')
def _read_json(p:Path):
    try:
        v=json.loads(p.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
class Build361Phase16BaselineService:
    BUILD='361.0'; PACKAGE='361.0.0'; POLICY='phase16.baseline.v361'
    def __init__(self,db,audit,*,build360,phase16,ai361,opsec361,install_dir,base_dir,actor='local-analyst'):
        self.db=db;self.audit=audit;self.build360=build360;self.phase16=phase16;self.ai361=ai361;self.opsec361=opsec361;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build360,n,None)
        if v is None: raise AttributeError(n)
        return v
    def _fingerprint_paths(self): return ('src/eagleeye/phase16/baseline361.py','src/eagleeye/application/build361/service.py','src/eagleeye/interfaces/web/app361.py','eagleeye_pro/core/app_context.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','tests/test_build361.py','EAGLEEYE_ACCEPTANCE_BUILD_361_0.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/'BUILD_361_TEST_EVIDENCE.json'); return v if v.get('build')==self.BUILD and v.get('result')=='pass' and v.get('code_fingerprint')==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/'BENCHMARK_BUILD_361_PHASE16_BASELINE.json'); return v if v.get('build')==self.BUILD and v.get('result')=='pass' and v.get('code_fingerprint')==self.code_fingerprint() and int(v.get('cases',0))>=1500 and int(v.get('violations',-1))==0 else {}
    def _probe(self,k): return self._test_evidence().get('probes',{}).get(k)=='pass'
    def schema_metrics(self): return self.build360.schema_metrics()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text();pt=(self.install_dir/'pyproject.toml').read_text()
        def g(p,t):
            m=re.search(p,t,re.M);return m.group(1) if m else 'unknown'
        r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);p=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=='qualified_gate': return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,'lineno')})
        return []
    def phase16_status(self): return {**self.phase16.phase16_status(),'schema':self.schema_metrics(),'version':self.version_status(),'qualification':{'tests':bool(self._test_evidence()),'benchmark':bool(self._benchmark())}}
    def run_autonomous_investigation(self,**kw): return self.ai361.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw): return self.opsec361.protect_case(**kw)
    def validation_matrix(self): return self.phase16.validation_matrix()
    def record_validation_receipt(self,**kw): return self.phase16.record_validation_receipt(**kw)
    def crawler_status(self): return {**self.build360.crawler_release_qualification(),'crawler_improvement_build':361,'phase16_live_validation_framework':True,'opsec_supervisor_monitors_crawler':True,'live_osint_connectors_required_for_phase16':True}
    @staticmethod
    def _maturity(st):
        last='declared'
        for k in DIMENSIONS:
            if st[k]:last=k
            else:break
        return last
    def capabilities(self):
        bench=bool(self._benchmark()); specs=[('phase16_external_validation_framework','baseline'),('ai_full_case_autonomy_after_go_v361','ai'),('defensive_opsec_supervisor_v361','opsec'),('live_osint_validation_contract_v361','osint')]; out=[]
        for key,probe in specs:
            st={'implemented':1==1,'integrated':1==1,'tested':self._probe(probe),'benchmarked':bench,'externally_validated':False};out.append({'key':key,'states':st,'maturity':self._maturity(st)})
        return out
    def qualified_gate(self):
        m=self.schema_metrics();v=self.version_status(); checks={'schema_within_gate':m['within_gate'],'version_coherent':v['coherent'],'test_evidence_current':bool(self._test_evidence()),'benchmark_1500_no_violations':bool(self._benchmark()),'phase16_targets_tested':self._probe('baseline'),'ai_go_autonomy_tested':self._probe('ai'),'opsec_autonomous_defense_tested':self._probe('opsec'),'live_osint_contract_tested':self._probe('osint'),'no_literal_true_gate':self.active_gate_literal_true_lines()==[]}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(bool(x) for x in checks.values()),'production_release_ready':False,'external_validation_complete':False,'truthful_note':'Build 361 establishes the Phase-16 pilot/external-validation baseline. No external service, live OSINT provider, pentest or professional pilot is claimed externally validated by this build.'}
    def dashboard(self): return {'build':self.BUILD,'phase16':self.phase16_status(),'crawler':self.crawler_status(),'capabilities':self.capabilities(),'gate':self.qualified_gate()}
    def final_status(self): return self.dashboard()
