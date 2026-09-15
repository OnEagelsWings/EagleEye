from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any
DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}
class Build371EntityResolutionV2Service:
    BUILD="371.0"; PACKAGE="371.0.0"; POLICY="phase16.entity-resolution-v2-build.v371"
    def __init__(self,db:Any,audit:Any,*,build370:Any,entity371:Any,crawler371:Any,ai371:Any,opsec371:Any,install_dir:Any,base_dir:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.build370=build370;self.entity371=entity371;self.crawler371=crawler371;self.ai371=ai371;self.opsec371=opsec371;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build370,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self)->tuple[str,...]:return("src/eagleeye/phase16/entity_resolution371.py","src/eagleeye/application/build371/service.py","src/eagleeye/interfaces/web/app371.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build371.py","EAGLEEYE_ACCEPTANCE_BUILD_371_0.py","tools/benchmark_build371.py","tools/live_entity_crawler_validate_371.py","CRAWLER_ROADMAP_BUILD_370_TO_380.md","PHASE_16_MASTERPLAN_BUILD_361_TO_380.md")
    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_371_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_371_ENTITY_RESOLUTION.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=3800 and int(v.get("violations",-1))==0 else {}
    def _live_validation(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_371_ENTITY_CRAWLER.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key):return self._test_evidence().get("probes",{}).get(key)=="pass"
    def schema_metrics(self):
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts={r['type']:int(r['c']) for r in rows}; logical=int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get('n') or 0)
        integrity=str((self.db.one("PRAGMA integrity_check") or {}).get('integrity_check') or 'unknown'); file_bytes=self.db.path.stat().st_size if self.db.path.exists() else 0
        out={'table':counts.get('table',0),'index':counts.get('index',0),'trigger':counts.get('trigger',0),'view':counts.get('view',0),'logical_bytes':logical,'file_bytes':file_bytes,'integrity_check':integrity,'targets':{'tables_lt':180,'indexes_lt':300,'logical_bytes_lt':5*1024*1024},'canonical_entity_ledger_activated':True,'build371_specific_tables_added':0}
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
    def register_entity_candidate(self,**kw):return self.entity371.register_candidate(**kw)
    def compare_entities_v2(self,**kw):return self.entity371.compare(**kw)
    def propose_same_entity(self,**kw):return self.entity371.propose_same_entity(**kw)
    def review_same_entity(self,**kw):return self.entity371.review_same_entity(**kw)
    def entity_case_status(self,**kw):return self.entity371.case_status(**kw)
    def crawl_entity_provenance(self,**kw):return self.crawler371.provenance(**kw)
    def enqueue_entity_link_lead(self,**kw):return self.crawler371.enqueue_lead(**kw)
    def entity_lead_run_next(self,**kw):return self.crawler371.run_next(**kw)
    def entity_lead_recover_expired_leases(self,**kw):return self.crawler371.recover_expired_leases(**kw)
    def entity_lead_case_status(self,**kw):return self.crawler371.case_status(**kw)
    def run_autonomous_investigation(self,**kw):return self.ai371.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec371.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec371.protect_remote_session(**kw)
    def phase16_status(self):
        b=dict(self.build370.phase16_status());b.update({"build":self.BUILD,"builds_completed":11,"entity_resolution_v2":self.entity371.status(),"crawler_entity_linkage":self.crawler371.status(),"ai":self.ai371.status(),"opsec":self.opsec371.status(),"crawler_improvement_build":371,"continuous_crawler_expansion_370_380":True});return b
    def crawler_status(self):
        b=dict(self.build370.crawler_status());b.update({"crawler_improvement_build":371,"entity_linked_crawl_provenance":True,"source_to_entity_lead_queue":True,"lead_queue_uses_canonical_job_ledger":True,"entity_lead_network_execution":False,"entity_lead_auto_merge":False,"continuous_crawler_expansion_370_380":True,"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0});return b
    def capabilities(self):
        bench=bool(self._benchmark());live=self._live_validation();local=live.get("local_entity_crawler_validation")=="pass";specs=[("entity_resolution_v2_v371","entity_v2",False),("strong_identifier_conflict_veto_v371","conflict_veto",False),("source_independence_weighting_v371","source_independence",False),("common_name_penalty_v371","common_name",False),("crawler_entity_provenance_v371","crawler_provenance",False),("source_entity_lead_queue_v371","lead_queue",False),("non_destructive_review_link_v371","review_link",False),("entity_ai_boundary_v371","ai",False),("entity_opsec_boundary_v371","opsec",False),("local_entity_crawler_validation_v371","local",local)]
        out=[]
        for key,probe,ext in specs:
            tested=self._probe(probe) if probe!="local" else local;st={"implemented":True,"integrated":True,"tested":tested,"benchmarked":bench,"externally_validated":bool(ext)};out.append({"key":key,"states":st,"maturity":next((k for k in reversed(DIMENSIONS) if st[k]),"declared")})
        return out
    def qualified_gate(self):
        m=self.schema_metrics();v=self.version_status();live=self._live_validation();checks={"schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(self._test_evidence()),"benchmark_3800_no_violations":bool(self._benchmark()),"local_entity_crawler_validation":live.get("local_entity_crawler_validation")=="pass","entity_v2_tested":self._probe("entity_v2"),"conflict_veto_tested":self._probe("conflict_veto"),"source_independence_tested":self._probe("source_independence"),"crawler_provenance_tested":self._probe("crawler_provenance"),"lead_queue_tested":self._probe("lead_queue"),"review_link_tested":self._probe("review_link"),"ai_tested":self._probe("ai"),"opsec_tested":self._probe("opsec"),"no_literal_true_gate":self.active_gate_literal_true_lines()==[]}
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":all(bool(x) for x in checks.values()),"entity_resolution_external_evaluation":"scheduled_build_372","production_release_ready":False,"truthful_note":"Build 371 internally qualifies evidence-weighted, review-gated Entity Resolution v2 and crawler-linked provenance. Calibrated external/holdout entity-resolution evaluation is intentionally deferred to Build 372."}
    def dashboard(self):return {"build":self.BUILD,"phase16":self.phase16_status(),"crawler":self.crawler_status(),"entity_resolution":self.entity371.status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
