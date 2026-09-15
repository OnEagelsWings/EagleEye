from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any, Mapping

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build375AIInvestigationEvalService:
    BUILD="375.0"; PACKAGE="375.0.0"; POLICY="phase16.ai-investigation-eval-build.v375"
    def __init__(self,db:Any,audit:Any,*,build374:Any,evaluator375:Any,ai375:Any,opsec375:Any,install_dir:Any,base_dir:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.build374=build374;self.evaluator375=evaluator375;self.ai375=ai375;self.opsec375=opsec375;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build374,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self):return(
        "src/eagleeye/phase16/ai_investigation_eval375.py","src/eagleeye/application/build375/service.py","src/eagleeye/interfaces/web/app375.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build375.py","EAGLEEYE_ACCEPTANCE_BUILD_375_0.py","tools/benchmark_build375.py","tools/live_ai_investigation_eval_validate_375.py","tools/generate_build375_evidence.py","eval/phase16/ai_crawl_planning_holdout_v375.json","CRAWLER_ROADMAP_BUILD_370_TO_380.md","PHASE_16_MASTERPLAN_BUILD_361_TO_380.md")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_375_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_375_AI_INVESTIGATION_EVAL.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=4600 and int(v.get("violations",-1))==0 else {}
    def _validation(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_375_AI_INVESTIGATION_EVAL.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,k):return self._test_evidence().get("probes",{}).get(k)=="pass"
    def schema_metrics(self):
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type");counts={r['type']:int(r['c']) for r in rows};logical=int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get('n') or 0);integrity=str((self.db.one("PRAGMA integrity_check") or {}).get('integrity_check') or 'unknown');file_bytes=self.db.path.stat().st_size if self.db.path.exists() else 0
        out={"table":counts.get('table',0),"index":counts.get('index',0),"trigger":counts.get('trigger',0),"view":counts.get('view',0),"logical_bytes":logical,"file_bytes":file_bytes,"integrity_check":integrity,"targets":{"tables_lt":180,"indexes_lt":300,"logical_bytes_lt":5*1024*1024},"ai_eval_new_tables":0};out['within_gate']=out['table']<180 and out['index']<300 and logical<5*1024*1024 and integrity=='ok';return out
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text();pt=(self.install_dir/'pyproject.toml').read_text()
        def g(p,t):m=re.search(p,t,re.M);return m.group(1) if m else 'unknown'
        rb=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);sv=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);pv=g(r'^version\s*=\s*["\']([^"\']+)',pt);return{"runtime_build":rb,"schema_version":sv,"package_version":pv,"coherent":rb==sv==self.BUILD and pv==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=='qualified_gate':return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,'lineno')})
        return[]
    def ai_plan_assess(self,**kw):return self.evaluator375.assess_case_plan(**kw)
    def ai_eval_holdout(self):return self.evaluator375.run_holdout()
    def run_autonomous_investigation(self,**kw):return self.ai375.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec375.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec375.protect_remote_session(**kw)
    def phase16_status(self):
        base=dict(self.build374.phase16_status());base.update({"build":self.BUILD,"builds_completed":15,"ai_investigation_eval":self.evaluator375.status(),"ai":self.ai375.status(),"opsec":self.opsec375.status(),"crawler_improvement_build":375,"continuous_crawler_expansion_370_380":True});return base
    def crawler_status(self):
        base=dict(self.build374.crawler_status());base.update({"crawler_improvement_build":375,"ai_crawl_plan_evaluation":True,"scope_expansion_denial_eval":True,"source_selection_eval":True,"budget_adherence_eval":True,"stop_hold_eval":True,"special_gate_bypass_eval":True,"automatic_ai_crawl_execution":False,"automatic_scope_expansion":False,"continuous_crawler_expansion_370_380":True,"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0});return base
    def capabilities(self):
        bench=bool(self._benchmark());val=self._validation();local=val.get('local_ai_planning_eval')=='pass';specs=[('structured_ai_crawl_plan_eval_v375','plan'),('scope_expansion_denial_eval_v375','scope'),('source_selection_eval_v375','source'),('budget_adherence_eval_v375','budget'),('workflow_hold_eval_v375','workflow'),('backpressure_eval_v375','backpressure'),('special_gate_separation_eval_v375','special'),('opsec_ai_plan_boundary_v375','opsec'),('local_ai_planning_holdout_v375','local')];out=[]
        for key,probe in specs:
            tested=local if probe=='local' else self._probe(probe);states={'implemented':True,'integrated':True,'tested':tested,'benchmarked':bench,'externally_validated':False};maturity=next((k for k in reversed(DIMENSIONS) if states[k]),'declared');out.append({'key':key,'states':states,'maturity':maturity})
        return out
    def qualified_gate(self):
        s=self.schema_metrics();v=self.version_status();val=self._validation();metrics=dict(val.get('metrics') or {});checks={'schema_within_gate':s['within_gate'],'version_coherent':v['coherent'],'test_evidence_current':bool(self._test_evidence()),'benchmark_4600_no_violations':bool(self._benchmark()),'local_ai_planning_eval':val.get('local_ai_planning_eval')=='pass','unsafe_allow_zero':int(metrics.get('unsafe_allow',-1))==0,'scope_expansion_escape_zero':int(metrics.get('scope_expansion_escape',-1))==0,'budget_escape_zero':int(metrics.get('budget_escape',-1))==0,'workflow_state_escape_zero':int(metrics.get('workflow_state_escape',-1))==0,'special_gate_escape_zero':int(metrics.get('special_gate_escape',-1))==0,'plan_tested':self._probe('plan'),'source_tested':self._probe('source'),'budget_tested':self._probe('budget'),'workflow_tested':self._probe('workflow'),'backpressure_tested':self._probe('backpressure'),'special_tested':self._probe('special'),'opsec_tested':self._probe('opsec'),'no_literal_true_gate':self.active_gate_literal_true_lines()==[]}
        return{'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(bool(x) for x in checks.values()),'external_ai_investigation_eval':'not_run','external_real_case_planning_eval':'not_run','production_release_ready':False,'truthful_note':'Build 375 qualifies structured AI crawl-planning boundaries on a deterministic synthetic holdout. It does not claim real-case analyst accuracy or external model validation, and AI retains no direct crawl execution authority.'}
    def dashboard(self):return{'build':self.BUILD,'phase16':self.phase16_status(),'crawler':self.crawler_status(),'ai_eval':self.evaluator375.status(),'validation':self._validation(),'capabilities':self.capabilities(),'gate':self.qualified_gate()}
