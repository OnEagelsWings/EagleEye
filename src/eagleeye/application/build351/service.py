from __future__ import annotations
import ast, hashlib, html, json, re
from pathlib import Path
from typing import Any, Callable, Sequence
from eagleeye.crawler.engine import CrawlTransport
from eagleeye.crawler.delta_sync import DeltaSyncCrawler351, POLICY_VERSION as DELTA_POLICY

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
def _read_json(path:Path)->dict[str,Any]:
    try:
        d=json.loads(path.read_text(encoding="utf-8")); return d if isinstance(d,dict) else {}
    except Exception: return {}

class Build351DeltaSyncService:
    BUILD="351.0"
    def __init__(self,db:Any,audit:Any,*,build350:Any,delta_crawler:DeltaSyncCrawler351,connector_sdk:Any,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.build350=build350; self.delta_crawler=delta_crawler; self.connector_sdk=connector_sdk; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        a=getattr(self.build350,name,None)
        if a is None: raise AttributeError(name)
        return a
    def _fingerprint_paths(self):
        return ("src/eagleeye/infrastructure/schema_v1/schema.py","src/eagleeye/crawler/engine.py","src/eagleeye/crawler/delta_sync.py","src/eagleeye/application/build351/service.py","src/eagleeye/interfaces/web/app351.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_351_0.py","EAGLEEYE_ACCEPTANCE_BUILD_351_0.py","tests/test_build351.py")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        d=_read_json(self._root/"BUILD_351_TEST_EVIDENCE.json")
        return d if d.get("build")==self.BUILD and d.get("result")=="pass" and d.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key:str)->bool: return self._test_evidence().get("probes",{}).get(key)=="pass"
    def _benchmark(self):
        d=_read_json(self._root/"BENCHMARK_BUILD_351_DELTA_SYNC.json")
        return d if d.get("build")==self.BUILD and d.get("code_fingerprint")==self.code_fingerprint() and d.get("cases",0)>=400 and d.get("violations")==0 and d.get("result")=="pass" else {}
    def schema_metrics(self): return self.build350.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text()
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="351.0.0"}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=="qualified_gate": return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def run_next_crawl(self,*,worker_id:str,transport:CrawlTransport,resolver:Callable[[str],Sequence[str]]|None=None):
        job=self.db.one("SELECT * FROM phase15_jobs WHERE status='queued' AND job_type='governed_crawl_v1' ORDER BY priority DESC,created_at ASC LIMIT 1")
        if job:
            payload=json.loads(job["payload_json"]); sid=str(payload.get("source_id") or "")
            policy=self.connector_sdk.validate_transport_for_source(sid,transport)
            if not policy["allowed"]: raise PermissionError(policy["reason"])
        result=self.delta_crawler.run_next(worker_id=worker_id,transport=transport,resolver=resolver)
        if not result: return None
        try:
            row=self.db.one("SELECT payload_json FROM phase15_jobs WHERE job_id=?",(result["job_id"],)); payload=json.loads(row["payload_json"]) if row else {}; cr=str(payload.get("crawl_run_id") or "")
            if cr:
                run=self.db.one("SELECT source_id FROM phase15_crawl_runs WHERE crawl_run_id=?",(cr,)); parse=self.connector_sdk.parse_crawl_run(cr); health=self.connector_sdk.record_source_health(run["source_id"],crawl_run_id=cr) if run else {}
                return {**result,"build351_parse_summary":parse,"build351_source_health":health,"build351_delta_summary":json.loads(self.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?",(cr,))["summary_json"])}
        except Exception as exc: return {**result,"build351_postprocess_error":f"{type(exc).__name__}:{exc}"[:1000]}
        return result
    def delta_history(self,source_id:str,url:str,limit:int=50):
        return self.db.all("""SELECT f.* FROM phase15_crawl_fetches f JOIN phase15_crawl_runs r ON r.crawl_run_id=f.crawl_run_id WHERE r.source_id=? AND f.url=? ORDER BY f.created_at DESC LIMIT ?""",(source_id,url,max(1,min(int(limit),500))))
    def crawler_status(self):
        s=dict(self.build350.crawler_status()); s.update({"policy":DELTA_POLICY,"crawler_improvement_build":351,"delta_sync":self.delta_crawler.delta_status(),"conditional_fetch":True,"etag":True,"last_modified":True,"exact_sha256_dedup":True}); return s
    def architecture_status(self):
        b=dict(self.build350.architecture_status()); b.update({"delta_sync_policy":DELTA_POLICY,"conditional_fetch":True,"http_304_no_new_object":True,"exact_hash_no_new_object":True,"delta_provenance":True,"darknet_conditional_fetch_same_opsec_boundary":True}); return b
    @staticmethod
    def _maturity(st):
        last="declared"
        for k in DIMENSIONS:
            if st[k]: last=k
            else: break
        return last
    def capabilities(self):
        m=self.schema_metrics(); v=self.version_status(); bench=bool(self._benchmark()); fp=self.code_fingerprint()
        specs=[("schema_baseline_v1_351","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False),("crawler_delta_sync_v1","Conditional fetch and delta sync","crawler",True,True,"delta",bench,False),("etag_last_modified_v1","HTTP validators","crawler",True,True,"validators",bench,False),("exact_content_dedup_v1","Exact content deduplication","crawler",True,True,"dedup",bench,False),("delta_provenance_v1","Version/delta provenance","evidence",True,True,"provenance",bench,False),("darknet_delta_boundary_v1","Darknet delta sync retains quarantine/OPSEC","darknet",True,True,"darknet",bench,False),("canonical_versioning_351","Canonical Build 351 version","packaging",v["coherent"],v["coherent"],"version",False,False)]
        rows=[]
        for key,name,cat,imp,integ,probe,bm,ext in specs:
            tested=bool(integ and self._probe(probe)); states={"implemented":bool(imp),"integrated":bool(imp and integ),"tested":tested,"benchmarked":bool(tested and bm),"externally_validated":False}
            rows.append({"capability_key":key,"display_name":name,"category":cat,**states,"maturity":self._maturity(states),"required_for_build":True,"required_for_production":key!="schema_baseline_v1_351","external_validation_required":ext,"code_fingerprint":fp})
        return rows
    def qualified_gate(self):
        rows=self.capabilities(); tested=bool(rows) and all(r["tested"] for r in rows); bm=any(r["capability_key"]=="crawler_delta_sync_v1" and r["benchmarked"] for r in rows); prod=bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {"build":self.BUILD,"phase":"15","gate_authority":"build351_delta_sync_evidence_gate","build_acceptance_ready":tested and bm and self.schema_metrics()["within_gate"],"production_release_ready":prod,"release_ready":prod,"baseline_tested":tested,"delta_sync_benchmarked":bm,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"304 and exact-hash matches never create new evidence objects. Changed/new content retains previous-fetch provenance. Conditional requests remain bounded by Source Governance, Capsule, OPSEC-v2, rate budget and quarantine."}
    def dashboard(self): return {"build":self.BUILD,"phase":"15","name":"Delta Sync & Conditional Fetch","schema":self.schema_metrics(),"crawler":self.crawler_status(),"architecture":self.architecture_status(),"gate":self.qualified_gate(),"version":self.version_status(),"capabilities":self.capabilities(),"crawler_improvement_commitment":"349-360"}
    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        st=self.delta_crawler.delta_status(); g=self.qualified_gate()
        return f"<section class='card'><h2>Phase 15 · Build 351 · Delta Sync</h2><p><b>New:</b> {st['new']} · <b>Changed:</b> {st['changed']} · <b>304:</b> {st['not_modified']} · <b>Dedup:</b> {st['deduplicated']} · <b>Gate:</b> {'PASS' if g['build_acceptance_ready'] else 'offen'}.</p><p>ETag/Last-Modified und SHA-256 verhindern unnötige neue Evidence-Objekte. Darknet bleibt OPSEC-/Quarantäne-gebunden.</p><p><small>Status: <code>/api/build351</code></small></p></section>"
