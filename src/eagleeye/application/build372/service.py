from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")

def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build372EntityResolutionEvaluationService:
    BUILD="372.0"; PACKAGE="372.0.0"; POLICY="phase16.entity-resolution-evaluation-build.v372"
    def __init__(self,db:Any,audit:Any,*,build371:Any,eval372:Any,source_quality372:Any,ai372:Any,opsec372:Any,install_dir:Any,base_dir:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.build371=build371;self.eval372=eval372;self.source_quality372=source_quality372;self.ai372=ai372;self.opsec372=opsec372;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build371,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self)->tuple[str,...]:return(
        "src/eagleeye/phase16/entity_resolution_eval372.py","src/eagleeye/application/build372/service.py","src/eagleeye/interfaces/web/app372.py",
        "eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build372.py",
        "EAGLEEYE_ACCEPTANCE_BUILD_372_0.py","tools/benchmark_build372.py","tools/live_entity_eval_validate_372.py","tools/generate_build372_evidence.py",
        "eval/phase16/entity_resolution_holdout_v372.json","CRAWLER_ROADMAP_BUILD_370_TO_380.md","PHASE_16_MASTERPLAN_BUILD_361_TO_380.md")
    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_372_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_372_ENTITY_EVAL.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=4000 and int(v.get("violations",-1))==0 else {}
    def _holdout(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_372_ENTITY_EVAL.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key):return self._test_evidence().get("probes",{}).get(key)=="pass"
    def schema_metrics(self):
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts={r['type']:int(r['c']) for r in rows};logical=int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get('n') or 0)
        integrity=str((self.db.one("PRAGMA integrity_check") or {}).get('integrity_check') or 'unknown');file_bytes=self.db.path.stat().st_size if self.db.path.exists() else 0
        out={'table':counts.get('table',0),'index':counts.get('index',0),'trigger':counts.get('trigger',0),'view':counts.get('view',0),'logical_bytes':logical,'file_bytes':file_bytes,'integrity_check':integrity,'targets':{'tables_lt':180,'indexes_lt':300,'logical_bytes_lt':5*1024*1024},'canonical_entity_ledger_activated':True,'build372_specific_tables_added':0,'evaluation_results_persisted_in_case_tables':False}
        out['within_gate']=out['table']<180 and out['index']<300 and logical<5*1024*1024 and integrity=='ok';return out
    def version_status(self):
        vt=(self.install_dir/"eagleeye_pro/version.py").read_text();pt=(self.install_dir/"pyproject.toml").read_text()
        def g(p,t):
            m=re.search(p,t,re.M);return m.group(1) if m else "unknown"
        runtime=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);schema=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);package=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate":return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def evaluate_labeled_entity_comparisons(self,**kw):return self.eval372.evaluate_labeled(**kw)
    def comparison_eval_record(self,**kw):return self.eval372.comparison_record(**kw)
    def crawler_source_quality(self,**kw):return self.source_quality372.provenance_quality(**kw)
    def crawler_lead_quality(self,**kw):return self.source_quality372.lead_quality_packet(**kw)
    def crawler_source_quality_case(self,**kw):return self.source_quality372.case_summary(**kw)
    def source_quality_calibration_contract(self):return self.source_quality372.calibration_contract()
    def run_autonomous_investigation(self,**kw):return self.ai372.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec372.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec372.protect_remote_session(**kw)
    def phase16_status(self):
        b=dict(self.build371.phase16_status());b.update({"build":self.BUILD,"builds_completed":12,"entity_resolution_evaluation":self.eval372.status(),"crawler_source_quality":self.source_quality372.status(),"ai":self.ai372.status(),"opsec":self.opsec372.status(),"crawler_improvement_build":372,"continuous_crawler_expansion_370_380":True});return b
    def crawler_status(self):
        b=dict(self.build371.crawler_status());b.update({"crawler_improvement_build":372,"crawler_entity_eval_corpus":True,"false_link_calibration":True,"source_quality_calibration":True,"lead_source_quality_annotation":True,"source_quality_is_identity_probability":False,"source_quality_can_skip_review":False,"entity_lead_auto_merge":False,"continuous_crawler_expansion_370_380":True,"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0});return b
    def capabilities(self):
        bench=bool(self._benchmark());hold=self._holdout();local=hold.get("synthetic_holdout_validation")=="pass";specs=[
            ("entity_resolution_holdout_eval_v372","holdout_eval",False),("false_link_metrics_v372","false_link",False),("conflict_escape_gate_v372","conflict_escape",False),
            ("common_name_eval_v372","common_name",False),("crawler_source_quality_v372","source_quality",False),("lead_quality_packet_v372","lead_quality",False),
            ("entity_eval_ai_boundary_v372","ai",False),("entity_eval_opsec_boundary_v372","opsec",False),("synthetic_holdout_validation_v372","local",False)]
        out=[]
        for key,probe,ext in specs:
            tested=self._probe(probe) if probe!="local" else local;st={"implemented":True,"integrated":True,"tested":tested,"benchmarked":bench,"externally_validated":bool(ext)};out.append({"key":key,"states":st,"maturity":next((k for k in reversed(DIMENSIONS) if st[k]),"declared")})
        return out
    def qualified_gate(self):
        m=self.schema_metrics();v=self.version_status();hold=self._holdout();metrics=dict(hold.get("metrics") or {});checks={
            "schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(self._test_evidence()),"benchmark_4000_no_violations":bool(self._benchmark()),
            "synthetic_holdout_validation":hold.get("synthetic_holdout_validation")=="pass","unsafe_false_link_rate_le_005":float(metrics.get("unsafe_false_link_rate",1.0))<=0.05,
            "strong_identifier_conflict_escape_zero":int(metrics.get("strong_identifier_conflict_escape_count",1))==0,"review_positive_precision_ge_090":float(metrics.get("review_positive_precision",0.0))>=0.90,
            "same_entity_candidate_recall_ge_080":float(metrics.get("same_entity_candidate_recall",0.0))>=0.80,"holdout_eval_tested":self._probe("holdout_eval"),"false_link_tested":self._probe("false_link"),
            "common_name_tested":self._probe("common_name"),"source_quality_tested":self._probe("source_quality"),"lead_quality_tested":self._probe("lead_quality"),"ai_tested":self._probe("ai"),"opsec_tested":self._probe("opsec"),
            "no_literal_true_gate":self.active_gate_literal_true_lines()==[]}
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":all(bool(x) for x in checks.values()),"synthetic_holdout_validated":hold.get("synthetic_holdout_validation")=="pass","external_real_world_holdout_validation":"not_run","production_release_ready":False,"truthful_note":"Build 372 calibrates Entity Resolution v2 on a deterministic synthetic holdout and adds source-quality annotations. Synthetic evaluation is not an external real-world false-link validation and never authorizes automatic merging or threshold changes."}
    def dashboard(self):return {"build":self.BUILD,"phase16":self.phase16_status(),"crawler":self.crawler_status(),"entity_evaluation":self.eval372.status(),"source_quality":self.source_quality372.status(),"holdout_validation":self._holdout(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
