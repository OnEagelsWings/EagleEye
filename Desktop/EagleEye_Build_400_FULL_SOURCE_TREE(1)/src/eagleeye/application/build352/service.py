from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any, Callable, Sequence
from eagleeye.crawler.engine import CrawlTransport, _clean_url
from eagleeye.crawler.frontier import FrontierCrawler352, POLICY_VERSION as FRONTIER_POLICY, canonical_url

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
def _read_json(path:Path)->dict[str,Any]:
    try:
        d=json.loads(path.read_text(encoding="utf-8")); return d if isinstance(d,dict) else {}
    except Exception: return {}

def _canon(v:Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)

def _sha(v:Any)->str: return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build352FrontierResumeService:
    BUILD="352.0"
    def __init__(self,db:Any,audit:Any,*,build351:Any,frontier_crawler:FrontierCrawler352,connector_sdk:Any,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.build351=build351; self.frontier_crawler=frontier_crawler; self.connector_sdk=connector_sdk; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        a=getattr(self.build351,name,None)
        if a is None: raise AttributeError(name)
        return a
    def _fingerprint_paths(self):
        return ("src/eagleeye/infrastructure/schema_v1/schema.py","src/eagleeye/crawler/engine.py","src/eagleeye/crawler/delta_sync.py","src/eagleeye/crawler/frontier.py","src/eagleeye/application/build352/service.py","src/eagleeye/interfaces/web/app352.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_352_0.py","EAGLEEYE_ACCEPTANCE_BUILD_352_0.py","tests/test_build352.py")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        d=_read_json(self._root/"BUILD_352_TEST_EVIDENCE.json")
        return d if d.get("build")==self.BUILD and d.get("result")=="pass" and d.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key:str)->bool: return self._test_evidence().get("probes",{}).get(key)=="pass"
    def _benchmark(self):
        d=_read_json(self._root/"BENCHMARK_BUILD_352_FRONTIER.json")
        return d if d.get("build")==self.BUILD and d.get("code_fingerprint")==self.code_fingerprint() and d.get("cases",0)>=450 and d.get("violations")==0 and d.get("result")=="pass" else {}
    def schema_metrics(self): return self.build351.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text()
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="352.0.0"}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=="qualified_gate": return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def register_crawler_source(self,*,display_name:str,seed_urls:Sequence[str],terms_ref:str,jurisdiction:str="Global",source_class:str="public_web",max_depth:int=1,max_pages:int=20,requests_per_minute:int=10,max_response_bytes:int=2_000_000,parser_version:str="html-text-links-v1",sitemap_urls:Sequence[str]=(),archive_seed_urls:Sequence[str]=(),frontier_policy:dict[str,Any]|None=None):
        row=self.build351.register_crawler_source(display_name=display_name,seed_urls=seed_urls,terms_ref=terms_ref,jurisdiction=jurisdiction,source_class=source_class,max_depth=max_depth,max_pages=max_pages,requests_per_minute=requests_per_minute,max_response_bytes=max_response_bytes,parser_version=parser_version)
        allowed={str(x).lower() for x in json.loads(self.db.one("SELECT allowed_hosts_json FROM phase15_crawler_policies WHERE source_id=?",(row["source_id"],))["allowed_hosts_json"])}
        def clean(values:Sequence[str])->list[str]:
            out=[]
            for value in values:
                u=canonical_url(value); host=(__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(u).hostname or '').lower()
                if host not in allowed: raise ValueError("discovery URLs must stay within the source allowlist")
                if u not in out: out.append(u)
            return out
        sm=clean(sitemap_urls); ar=clean(archive_seed_urls)
        policy={"version":FRONTIER_POLICY,"max_frontier_items":5000,"priority":{"seed":10,"sitemap":25,"archive_seed":60,"html_link":100},"cross_host_expansion":False,**(frontier_policy or {})}
        self.db.execute("UPDATE phase15_crawler_policies SET sitemap_urls_json=?,archive_seed_urls_json=?,frontier_policy_json=?,updated_at=? WHERE source_id=?",(_canon(sm),_canon(ar),_canon(policy),self.db.one("SELECT datetime('now') t")["t"],row["source_id"]))
        return self.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",(row["source_id"],))
    def enqueue_crawl(self,*,case_id:str,source_id:str):
        out=self.build351.enqueue_crawl(case_id=case_id,source_id=source_id)
        job_id=out["job"]["job_id"]; source=self.db.one("SELECT max_pages,allowed_hosts_json,sitemap_urls_json FROM phase15_crawler_policies WHERE source_id=?",(source_id,))
        job=self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?",(job_id,)); budget=json.loads(job["rate_budget_json"] or "{}")
        hosts=len(json.loads(source["allowed_hosts_json"] or "[]")); sitemaps=len(json.loads(source["sitemap_urls_json"] or "[]"))
        budget["max_requests"]=min(100000,max(int(budget.get("max_requests",0)),int(source["max_pages"])+min(hosts,10)+min(sitemaps,20)+5))
        self.db.execute("UPDATE phase15_jobs SET rate_budget_json=? WHERE job_id=?",(_canon(budget),job_id))
        out["job"]=self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?",(job_id,)); return out

    def run_next_crawl(self,*,worker_id:str,transport:CrawlTransport,resolver:Callable[[str],Sequence[str]]|None=None):
        job=self.db.one("SELECT * FROM phase15_jobs WHERE status='queued' AND job_type='governed_crawl_v1' ORDER BY priority ASC,created_at ASC LIMIT 1")
        if job:
            payload=json.loads(job["payload_json"]); sid=str(payload.get("source_id") or ""); policy=self.connector_sdk.validate_transport_for_source(sid,transport)
            if not policy["allowed"]: raise PermissionError(policy["reason"])
        result=self.frontier_crawler.run_next(worker_id=worker_id,transport=transport,resolver=resolver)
        if not result: return None
        try:
            row=self.db.one("SELECT payload_json,status FROM phase15_jobs WHERE job_id=?",(result["job_id"],)); payload=json.loads(row["payload_json"]) if row else {}; cr=str(payload.get("crawl_run_id") or "")
            if cr and row and row["status"]=="succeeded":
                run=self.db.one("SELECT source_id FROM phase15_crawl_runs WHERE crawl_run_id=?",(cr,)); parse=self.connector_sdk.parse_crawl_run(cr); health=self.connector_sdk.record_source_health(run["source_id"],crawl_run_id=cr) if run else {}; summary=json.loads(self.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?",(cr,))["summary_json"])
                return {**result,"build352_parse_summary":parse,"build352_source_health":health,"build352_frontier_summary":summary}
            if cr:
                summary=json.loads(self.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?",(cr,))["summary_json"])
                return {**result,"build352_frontier_summary":summary}
        except Exception as exc: return {**result,"build352_postprocess_error":f"{type(exc).__name__}:{exc}"[:1000]}
        return result
    def frontier_checkpoint(self,job_id:str):
        row=self.db.one("SELECT checkpoint_json,status,attempts,lease_owner FROM phase15_jobs WHERE job_id=?",(job_id,));
        if not row: raise KeyError(job_id)
        try: cp=json.loads(row["checkpoint_json"] or "{}")
        except Exception: cp={}
        return {"job_id":job_id,"status":row["status"],"attempts":row["attempts"],"lease_owner":row["lease_owner"],"checkpoint":cp}
    def crawler_status(self):
        s=dict(self.build351.crawler_status()); s.update({"policy":FRONTIER_POLICY,"crawler_improvement_build":352,"frontier":self.frontier_crawler.frontier_status(),"crash_safe_resume":True,"sitemap_discovery":True,"archive_seed_discovery":True,"canonical_url_frontier":True}); return s
    def architecture_status(self):
        b=dict(self.build351.architecture_status()); b.update({"frontier_policy":FRONTIER_POLICY,"persistent_frontier_in_job_checkpoint":True,"new_per_build_frontier_table":False,"sitemap_traversal_bounded":True,"archive_seeds_explicit_same_host":True,"canonical_url_same_host_only":True,"resume_semantics":"at_least_once_fetch_exact_evidence_dedup","darknet_frontier_same_opsec_boundary":True}); return b
    @staticmethod
    def _maturity(st):
        last="declared"
        for k in DIMENSIONS:
            if st[k]: last=k
            else: break
        return last
    def capabilities(self):
        m=self.schema_metrics(); v=self.version_status(); bench=bool(self._benchmark()); fp=self.code_fingerprint()
        specs=[("schema_baseline_v1_352","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False),("crawler_frontier_v1","Persistent prioritized frontier","crawler",True,True,"frontier",bench,False),("crawler_resume_v1","Crash-safe crawler resume","crawler",True,True,"resume",bench,False),("sitemap_discovery_v1","Bounded sitemap discovery","crawler",True,True,"sitemap",bench,False),("archive_seed_v1","Explicit governed archive seeds","crawler",True,True,"archive",bench,False),("canonical_url_frontier_v1","Conservative canonical URL frontier","crawler",True,True,"canonical",bench,False),("darknet_frontier_boundary_v1","Darknet frontier retains OPSEC/quarantine","darknet",True,True,"darknet",bench,False),("canonical_versioning_352","Canonical Build 352 version","packaging",v["coherent"],v["coherent"],"version",False,False)]
        rows=[]
        for key,name,cat,imp,integ,probe,bm,ext in specs:
            tested=bool(integ and self._probe(probe)); states={"implemented":bool(imp),"integrated":bool(imp and integ),"tested":tested,"benchmarked":bool(tested and bm),"externally_validated":False}
            rows.append({"capability_key":key,"display_name":name,"category":cat,**states,"maturity":self._maturity(states),"required_for_build":True,"required_for_production":key!="schema_baseline_v1_352","external_validation_required":ext,"code_fingerprint":fp})
        return rows
    def qualified_gate(self):
        rows=self.capabilities(); tested=bool(rows) and all(r["tested"] for r in rows); bm=any(r["capability_key"]=="crawler_resume_v1" and r["benchmarked"] for r in rows); prod=bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {"build":self.BUILD,"phase":"15","gate_authority":"build352_frontier_resume_evidence_gate","build_acceptance_ready":tested and bm and self.schema_metrics()["within_gate"],"production_release_ready":prod,"release_ready":prod,"baseline_tested":tested,"frontier_resume_benchmarked":bm,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"Frontier state is bounded and persisted in the durable job checkpoint. Sitemap/archive expansion remains source-allowlisted; resume is at-least-once for fetches while conditional/hash dedup prevents duplicate evidence promotion."}
    def dashboard(self): return {"build":self.BUILD,"phase":"15","name":"Frontier, Sitemap & Crash-Safe Resume","schema":self.schema_metrics(),"crawler":self.crawler_status(),"architecture":self.architecture_status(),"gate":self.qualified_gate(),"version":self.version_status(),"capabilities":self.capabilities(),"crawler_improvement_commitment":"349-360"}
    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        st=self.frontier_crawler.frontier_status(); g=self.qualified_gate(); return f"<section class='card'><h2>Phase 15 · Build 352 · Frontier & Resume</h2><p><b>Persisted frontiers:</b> {st['persisted_frontiers']} · <b>Pending:</b> {st['pending_frontier_items']} · <b>Gate:</b> {'PASS' if g['build_acceptance_ready'] else 'offen'}.</p><p>Sitemaps/Archive-Seeds bleiben allowlisted; Resume ist crash-sicher. Darknet bleibt Tor-Gateway-/OPSEC-/Quarantäne-gebunden.</p><p><small>Status: <code>/api/build352</code></small></p></section>"
