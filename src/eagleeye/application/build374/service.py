from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any, Mapping, Sequence

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")

def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build374CaseWorkflowService:
    BUILD="374.0"; PACKAGE="374.0.0"; POLICY="phase16.case-workflow-build.v374"
    def __init__(self,db:Any,audit:Any,*,build373:Any,workflow374:Any,ai374:Any,opsec374:Any,install_dir:Any,base_dir:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.build373=build373;self.workflow374=workflow374;self.ai374=ai374;self.opsec374=opsec374;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build373,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self):return(
        "src/eagleeye/phase16/case_workflow374.py","src/eagleeye/application/build374/service.py","src/eagleeye/interfaces/web/app374.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build374.py","EAGLEEYE_ACCEPTANCE_BUILD_374_0.py","tools/benchmark_build374.py","tools/live_case_workflow_validate_374.py","tools/generate_build374_evidence.py","CRAWLER_ROADMAP_BUILD_370_TO_380.md","PHASE_16_MASTERPLAN_BUILD_361_TO_380.md")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_374_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_374_CASE_WORKFLOW.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=4400 and int(v.get("violations",-1))==0 else {}
    def _live_validation(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_374_CASE_WORKFLOW.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,k):return self._test_evidence().get("probes",{}).get(k)=="pass"
    def schema_metrics(self):
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type");counts={r['type']:int(r['c']) for r in rows};logical=int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get('n') or 0);integrity=str((self.db.one("PRAGMA integrity_check") or {}).get('integrity_check') or 'unknown');file_bytes=self.db.path.stat().st_size if self.db.path.exists() else 0
        out={"table":counts.get('table',0),"index":counts.get('index',0),"trigger":counts.get('trigger',0),"view":counts.get('view',0),"logical_bytes":logical,"file_bytes":file_bytes,"integrity_check":integrity,"targets":{"tables_lt":180,"indexes_lt":300,"logical_bytes_lt":5*1024*1024},"case_workflow_new_tables":0}
        out['within_gate']=out['table']<180 and out['index']<300 and logical<5*1024*1024 and integrity=='ok';return out
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text();pt=(self.install_dir/'pyproject.toml').read_text()
        def g(p,t):m=re.search(p,t,re.M);return m.group(1) if m else 'unknown'
        rb=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);sv=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);pv=g(r'^version\s*=\s*["\']([^"\']+)',pt);return{"runtime_build":rb,"schema_version":sv,"package_version":pv,"coherent":rb==sv==self.BUILD and pv==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=='qualified_gate':return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,'lineno')})
        return[]
    def configure_case_workflow(self,**kw):return self.workflow374.configure(**kw)
    def case_workflow_status(self,**kw):return self.workflow374.status(**kw)
    def pause_case_workflow(self,**kw):return self.workflow374.pause(**kw)
    def resume_case_workflow(self,**kw):return self.workflow374.resume(**kw)
    def handoff_case_workflow(self,**kw):return self.workflow374.handoff(**kw)
    def accept_case_handoff(self,**kw):return self.workflow374.accept_handoff(**kw)
    def complete_case_workflow(self,**kw):return self.workflow374.complete(**kw)
    def workflow_navigation_plan(self,**kw):return self.workflow374.navigation_plan(**kw)
    def workflow_navigate(self,**kw):return self.workflow374.navigate(**kw)
    def workflow_enqueue_source(self,**kw):return self.workflow374.enqueue_source(**kw)
    def run_autonomous_investigation(self,**kw):return self.ai374.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec374.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec374.protect_remote_session(**kw)
    def phase16_status(self):
        base=dict(self.build373.phase16_status());base.update({"build":self.BUILD,"builds_completed":14,"case_workflow":self.workflow374.status_capabilities(),"ai":self.ai374.status(),"opsec":self.opsec374.status(),"crawler_improvement_build":374,"continuous_crawler_expansion_370_380":True});return base
    def crawler_status(self):
        base=dict(self.build373.crawler_status());base.update({"crawler_improvement_build":374,"case_source_request_budgets":True,"case_request_budget":True,"case_pause_resume":True,"running_worker_drain_pause":True,"analyst_handoff_gate":True,"workflow_bypass_detection":True,"automatic_scope_expansion":False,"continuous_crawler_expansion_370_380":True,"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0});return base
    def capabilities(self):
        benchmarked=bool(self._benchmark());live=self._live_validation();local=live.get('local_case_workflow_validation')=='pass';specs=[('case_workflow_state_v374','state'),('case_source_budgets_v374','budgets'),('workflow_pause_resume_v374','pause_resume'),('analyst_handoff_v374','handoff'),('workflow_graph_navigation_v374','navigation'),('workflow_manual_crawl_v374','manual_crawl'),('workflow_opsec_v374','opsec'),('workflow_ai_hold_v374','ai'),('local_case_workflow_validation_v374','local')];out=[]
        for key,probe in specs:
            tested=local if probe=='local' else self._probe(probe);states={'implemented':True,'integrated':True,'tested':tested,'benchmarked':benchmarked,'externally_validated':False};maturity=next((k for k in reversed(DIMENSIONS) if states[k]),'declared');out.append({'key':key,'states':states,'maturity':maturity})
        return out
    def qualified_gate(self):
        s=self.schema_metrics();v=self.version_status();l=self._live_validation();checks={'schema_within_gate':s['within_gate'],'version_coherent':v['coherent'],'test_evidence_current':bool(self._test_evidence()),'benchmark_4400_no_violations':bool(self._benchmark()),'local_case_workflow_validation':l.get('local_case_workflow_validation')=='pass','workflow_state_tested':self._probe('state'),'budgets_tested':self._probe('budgets'),'pause_resume_tested':self._probe('pause_resume'),'handoff_tested':self._probe('handoff'),'navigation_tested':self._probe('navigation'),'manual_crawl_tested':self._probe('manual_crawl'),'opsec_tested':self._probe('opsec'),'ai_tested':self._probe('ai'),'no_literal_true_gate':self.active_gate_literal_true_lines()==[]}
        return{'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(bool(x) for x in checks.values()),'external_case_workflow_validation':'not_run','external_analyst_handoff_validation':'not_run','production_release_ready':False,'truthful_note':'Build 374 qualifies case-scoped budgets, pause/resume and two-step handoff locally. Running workers are not force-killed; external multi-analyst workflow validation remains pending.'}
    def dashboard(self):return{'build':self.BUILD,'phase16':self.phase16_status(),'crawler':self.crawler_status(),'workflow':self.workflow374.status_capabilities(),'local_validation':self._live_validation(),'capabilities':self.capabilities(),'gate':self.qualified_gate()}
