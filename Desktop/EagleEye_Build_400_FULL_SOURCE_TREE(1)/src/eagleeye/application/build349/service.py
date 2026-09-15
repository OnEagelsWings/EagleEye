from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Callable, Sequence

from eagleeye.crawler.engine import POLICY_VERSION as CRAWLER_POLICY, CrawlTransport

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data=json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data,dict) else {}
    except Exception: return {}


class Build349GovernedCrawlerService:
    BUILD="349.0"

    def __init__(self, db: Any, audit: Any, *, build348: Any, crawler: Any, install_dir: str|Path, base_dir: str|Path, actor: str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build348=build348; self.crawler=crawler; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir

    def _fingerprint_paths(self) -> tuple[str,...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py","src/eagleeye/crawler/engine.py","src/eagleeye/application/build349/service.py",
            "src/eagleeye/interfaces/web/app349.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_349_0.py","EAGLEEYE_ACCEPTANCE_BUILD_349_0.py","tests/test_build349.py",
        )

    def code_fingerprint(self) -> str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self)->dict[str,Any]:
        d=_read_json(self._root/"BUILD_349_TEST_EVIDENCE.json")
        return d if d.get("build")==self.BUILD and d.get("result")=="pass" and d.get("code_fingerprint")==self.code_fingerprint() else {}

    def _probe(self,key:str)->bool: return self._test_evidence().get("probes",{}).get(key)=="pass"

    def _benchmark(self)->dict[str,Any]:
        d=_read_json(self._root/"BENCHMARK_BUILD_349_CRAWLER.json")
        if d.get("build")!=self.BUILD or d.get("code_fingerprint")!=self.code_fingerprint() or d.get("cases",0)<300 or d.get("violations")!=0 or d.get("result")!="pass": return {}
        return d

    def schema_metrics(self)->dict[str,Any]: return self.build348.schema_metrics()

    def version_status(self)->dict[str,Any]:
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text()
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="349.0.0"}

    def active_gate_literal_true_lines(self)->list[int]:
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []

    # Retained Phase-15 services by composition.
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        attr=getattr(self.build348,name,None)
        if attr is None: raise AttributeError(name)
        return attr

    def register_crawler_source(self, **kwargs: Any)->dict[str,Any]: return self.crawler.register_source(**kwargs)
    def review_crawler_source(self, source_id:str, **kwargs:Any)->dict[str,Any]: return self.crawler.review_source(source_id,**kwargs)
    def enqueue_crawl(self, **kwargs:Any)->dict[str,Any]: return self.crawler.enqueue_crawl(**kwargs)
    def run_next_crawl(self, *, worker_id:str, transport:CrawlTransport, resolver:Callable[[str],Sequence[str]]|None=None)->dict[str,Any]|None: return self.crawler.run_next(worker_id=worker_id,transport=transport,resolver=resolver)
    def crawl_runs(self, **kwargs:Any)->list[dict[str,Any]]: return self.crawler.runs(**kwargs)
    def crawl_fetches(self,crawl_run_id:str,**kwargs:Any)->list[dict[str,Any]]: return self.crawler.fetches(crawl_run_id,**kwargs)

    def crawler_sources(self, *, limit:int=200)->list[dict[str,Any]]:
        return self.db.all("SELECT s.source_id,s.source_kind,s.display_name,s.locator,s.review_status,s.risk_class,p.terms_ref,p.robots_mode,p.auth_type,p.max_depth,p.max_pages,p.requests_per_minute,p.parser_version,p.enabled,p.source_health FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id ORDER BY s.created_at DESC LIMIT ?", (max(1,min(int(limit),500)),))

    def crawler_status(self)->dict[str,Any]:
        s=self.crawler.status(); s["sources"]=len(self.crawler_sources(limit=500)); return s

    def architecture_status(self)->dict[str,Any]:
        src=(self._root/"src/eagleeye/crawler/engine.py").read_text(encoding="utf-8")
        return {
            "crawler_policy":CRAWLER_POLICY,"bounded_depth":True,"bounded_pages":True,"exact_host_allowlist":True,"robots_respected":True,
            "terms_review_required":True,"human_source_review_required":True,"read_only_methods_only":True,"forms_supported":False,"uploads_supported":False,
            "credentials_supported":False,"access_control_bypass_supported":False,"auto_background_crawler":False,"opsec_v2_preflight_per_fetch":True,
            "object_store_provenance_per_fetch":True,"darknet_direct_dns_forbidden":True,"built_in_onion_transport":False,
            "built_in_clearnet_transport":True,"system_mutation_calls_present":any(x in src for x in ("os.system(","subprocess.","Popen(")),
        }

    @staticmethod
    def _maturity(states:dict[str,bool])->str:
        last="declared"
        for k in DIMENSIONS:
            if states[k]: last=k
            else: break
        return last

    def capabilities(self)->list[dict[str,Any]]:
        m=self.schema_metrics(); v=self.version_status(); a=self.architecture_status(); bench=bool(self._benchmark()); fp=self.code_fingerprint()
        specs=[
            ("schema_baseline_v1_349","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False),
            ("governed_crawler_sdk_v1","Governed bounded crawler SDK","crawler",True,True,"crawler",bench,False),
            ("crawler_source_governance_v1","Crawler source/terms/robots governance","crawler",True,True,"source_governance",bench,False),
            ("crawler_queue_integration_v1","Crawler on persistent Job Engine","crawler",True,True,"queue",bench,False),
            ("crawler_opsec_preflight_v1","Per-fetch Capsule + OPSEC-v2 preflight","opsec",True,True,"opsec",bench,False),
            ("crawler_evidence_provenance_v1","Hash-bound Object Store crawl provenance","evidence",True,True,"provenance",bench,False),
            ("darknet_crawler_gateway_contract_v1","Onion crawler requires approved Tor transport","darknet",True,True,"darknet",bench,False),
            ("clearnet_live_transport_v1","Explicit read-only clearnet transport adapter","network",True,True,"transport",False,True),
            ("tor_live_transport_v1","Live Tor gateway transport","network",False,False,"future",False,True),
            ("canonical_versioning_349","Canonical Build 349 version contract","packaging",v["coherent"],v["coherent"],"version",False,False),
        ]
        required={"schema_baseline_v1_349","governed_crawler_sdk_v1","crawler_source_governance_v1","crawler_queue_integration_v1","crawler_opsec_preflight_v1","crawler_evidence_provenance_v1","darknet_crawler_gateway_contract_v1","canonical_versioning_349"}
        rows=[]
        for key,name,category,implemented,integrated,probe,benchmarkable,requires_external in specs:
            tested=bool(integrated and self._probe(probe)); states={"implemented":bool(implemented),"integrated":bool(implemented and integrated),"tested":tested,"benchmarked":bool(tested and benchmarkable),"externally_validated":False}
            rows.append({"capability_key":key,"display_name":name,"category":category,**states,"maturity":self._maturity(states),"required_for_build":key in required,"required_for_production":key not in {"schema_baseline_v1_349"},"external_validation_required":requires_external,"code_fingerprint":fp})
        return rows

    def qualified_gate(self)->dict[str,Any]:
        rows=self.capabilities(); req=[r for r in rows if r["required_for_build"]]
        tested=bool(req) and all(r["tested"] for r in req); crawler_bench=any(r["capability_key"]=="governed_crawler_sdk_v1" and r["benchmarked"] for r in rows)
        production=bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {"build":self.BUILD,"phase":"15","gate_authority":"build349_governed_crawler_evidence_gate","build_acceptance_ready":tested and crawler_bench and self.schema_metrics()["within_gate"],"production_release_ready":production,"release_ready":production,"baseline_tested":tested,"crawler_boundary_benchmarked":crawler_bench,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"Only human-reviewed public/authorized read-only sources may create bounded crawl jobs. Every fetch is constrained by exact egress, Job budget, Search Capsule and OPSEC v2. Build 349 contains no built-in Tor transport and no access-control bypass."}

    def dashboard(self)->dict[str,Any]:
        return {"build":self.BUILD,"phase":"15","name":"Governed Crawler SDK","schema":self.schema_metrics(),"crawler":self.crawler_status(),"architecture":self.architecture_status(),"gate":self.qualified_gate(),"version":self.version_status(),"capabilities":self.capabilities(),"crawler_improvement_commitment":"349-360"}

    def render_workspace_panel(self, *, case_id:str, csrf:str)->str:
        st=self.crawler_status(); gate=self.qualified_gate()
        return ("<section class='card'><h2>Phase 15 · Build 349 · Governed Crawler</h2>"
                f"<p><b>Quellen:</b> {st['sources']} · <b>Crawl-Runs:</b> {st['runs']} · <b>gespeicherte Seiten:</b> {st['pages_stored']} · <b>Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'offen'}.</p>"
                "<p>Bounded, read-only, review-first: exakte Host-Allowlist, robots.txt, Terms-/Lizenzreferenz, Job-Budgets, Search Capsule, OPSEC-v2 und hashgebundene Provenienz. Onion-Ziele benötigen einen separaten freigegebenen Tor-Gateway-Transport.</p>"
                f"<form method='post' action='/cases/{html.escape(case_id)}/crawler/source'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Name</label><input name='display_name' required><label>Seed URL</label><input name='seed_url' placeholder='https://example.org/' required><label>Terms/Lizenz-Referenz</label><input name='terms_ref' required><button>Quelle registrieren</button></form>"
                "<p><small>Status: <code>/api/build349</code></small></p></section>")
