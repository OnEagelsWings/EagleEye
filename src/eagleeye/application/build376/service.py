from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build376DossierVNextService:
    BUILD="376.0"; PACKAGE="376.0.0"; POLICY="phase16.dossier-vnext-build.v376"
    def __init__(self,db:Any,audit:Any,*,build375:Any,dossier376:Any,ai376:Any,opsec376:Any,install_dir:Any,base_dir:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.build375=build375;self.dossier376=dossier376;self.ai376=ai376;self.opsec376=opsec376;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build375,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self):return(
        "src/eagleeye/phase16/dossier_vnext376.py","src/eagleeye/application/build376/service.py","src/eagleeye/interfaces/web/app376.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build376.py","EAGLEEYE_ACCEPTANCE_BUILD_376_0.py","tools/benchmark_build376.py","tools/live_dossier_vnext_validate_376.py","tools/generate_build376_evidence.py","CRAWLER_ROADMAP_BUILD_370_TO_380.md","PHASE_16_MASTERPLAN_BUILD_361_TO_380.md")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_376_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_376_DOSSIER_VNEXT.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=4800 and int(v.get("violations",-1))==0 else {}
    def _validation(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_376_DOSSIER_VNEXT.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,k):return self._test_evidence().get("probes",{}).get(k)=="pass"
    def schema_metrics(self):
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type");counts={r['type']:int(r['c']) for r in rows};logical=int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get('n') or 0);integrity=str((self.db.one("PRAGMA integrity_check") or {}).get('integrity_check') or 'unknown');file_bytes=self.db.path.stat().st_size if self.db.path.exists() else 0
        out={"table":counts.get('table',0),"index":counts.get('index',0),"trigger":counts.get('trigger',0),"view":counts.get('view',0),"logical_bytes":logical,"file_bytes":file_bytes,"integrity_check":integrity,"targets":{"tables_lt":180,"indexes_lt":300,"logical_bytes_lt":5*1024*1024},"dossier_vnext_new_tables":0};out['within_gate']=out['table']<180 and out['index']<300 and logical<5*1024*1024 and integrity=='ok';return out
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text();pt=(self.install_dir/'pyproject.toml').read_text()
        def g(p,t):m=re.search(p,t,re.M);return m.group(1) if m else 'unknown'
        rb=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);sv=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);pv=g(r'^version\s*=\s*["\']([^"\']+)',pt);return{"runtime_build":rb,"schema_version":sv,"package_version":pv,"coherent":rb==sv==self.BUILD and pv==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=='qualified_gate':return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,'lineno')})
        return[]
    def dossier_coverage(self,**kw):return self.dossier376.source_coverage(**kw)
    def dossier_packet(self,**kw):return self.dossier376.dossier_packet(**kw)
    def record_absence_observation(self,**kw):return self.dossier376.record_absence_observation(**kw)
    def absence_observations(self,**kw):return self.dossier376.absence_observations(**kw)
    def build_dossier_vnext(self,*,case_id:str,refresh_hypotheses:bool=True):
        base=self.build375.build_investigation_dossier(case_id=case_id,refresh_hypotheses=refresh_hypotheses);return self.dossier376.build_vnext_report(case_id=case_id,base_dossier=base,refresh_hypotheses=refresh_hypotheses)
    def run_autonomous_investigation(self,**kw):return self.ai376.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec376.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec376.protect_remote_session(**kw)
    def phase16_status(self):
        base=dict(self.build375.phase16_status());base.update({"build":self.BUILD,"builds_completed":16,"dossier_vnext":self.dossier376.status(),"ai":self.ai376.status(),"opsec":self.opsec376.status(),"crawler_improvement_build":376,"continuous_crawler_expansion_370_380":True});return base
    def crawler_status(self):
        base=dict(self.build375.crawler_status());base.update({"crawler_improvement_build":376,"dossier_source_coverage":True,"negative_evidence_semantics":True,"stale_source_metrics":True,"research_gap_register":True,"automatic_gap_closure":False,"automatic_gap_crawl":False,"continuous_crawler_expansion_370_380":True,"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0});return base
    def capabilities(self):
        bench=bool(self._benchmark());val=self._validation();local=val.get('local_dossier_vnext_validation')=='pass';specs=[('dossier_vnext_v376','dossier'),('source_coverage_register_v376','coverage'),('bounded_absence_observation_v376','absence'),('staleness_register_v376','staleness'),('research_gap_register_v376','gaps'),('crawler_gap_no_auto_execution_v376','crawler'),('opsec_gap_boundary_v376','opsec'),('local_dossier_vnext_validation_v376','local')];out=[]
        for key,probe in specs:
            tested=local if probe=='local' else self._probe(probe);states={'implemented':True,'integrated':True,'tested':tested,'benchmarked':bench,'externally_validated':False};maturity=next((k for k in reversed(DIMENSIONS) if states[k]),'declared');out.append({'key':key,'states':states,'maturity':maturity})
        return out
    def qualified_gate(self):
        s=self.schema_metrics();v=self.version_status();val=self._validation();checks={'schema_within_gate':s['within_gate'],'version_coherent':v['coherent'],'test_evidence_current':bool(self._test_evidence()),'benchmark_4800_no_violations':bool(self._benchmark()),'local_dossier_vnext_validation':val.get('local_dossier_vnext_validation')=='pass','dossier_tested':self._probe('dossier'),'coverage_tested':self._probe('coverage'),'absence_tested':self._probe('absence'),'staleness_tested':self._probe('staleness'),'gaps_tested':self._probe('gaps'),'crawler_boundary_tested':self._probe('crawler'),'opsec_tested':self._probe('opsec'),'no_literal_true_gate':self.active_gate_literal_true_lines()==[]}
        return{'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(bool(x) for x in checks.values()),'external_dossier_validation':'not_run','external_negative_evidence_validation':'not_run','production_release_ready':False,'truthful_note':'Build 376 makes coverage, bounded absence observations, staleness and research gaps explicit. Coverage is not truth probability; absence is not non-existence; no gap triggers an automatic crawl.'}
    def dashboard(self):return{'build':self.BUILD,'phase16':self.phase16_status(),'crawler':self.crawler_status(),'dossier':self.dossier376.status(),'validation':self._validation(),'capabilities':self.capabilities(),'gate':self.qualified_gate()}
