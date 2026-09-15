from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Callable, Sequence

from eagleeye.connectors.sdk import ConnectorParserSDK, OFFICIAL_CONNECTORS, PARSER_POLICY_VERSION
from eagleeye.crawler.engine import POLICY_VERSION as CRAWLER_POLICY, CrawlTransport

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")


def _read_json(path: Path)->dict[str,Any]:
    try:
        data=json.loads(path.read_text(encoding="utf-8")); return data if isinstance(data,dict) else {}
    except Exception: return {}


class Build350ConnectorParserService:
    BUILD="350.0"

    def __init__(self,db:Any,audit:Any,*,build349:Any,connector_sdk:ConnectorParserSDK,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build349=build349; self.connector_sdk=connector_sdk; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir

    def _fingerprint_paths(self)->tuple[str,...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py","src/eagleeye/crawler/engine.py","src/eagleeye/connectors/sdk.py",
            "src/eagleeye/application/build350/service.py","src/eagleeye/interfaces/web/app350.py","eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_350_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_350_0.py","tests/test_build350.py",
        )

    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self)->dict[str,Any]:
        d=_read_json(self._root/"BUILD_350_TEST_EVIDENCE.json")
        return d if d.get("build")==self.BUILD and d.get("result")=="pass" and d.get("code_fingerprint")==self.code_fingerprint() else {}

    def _probe(self,key:str)->bool: return self._test_evidence().get("probes",{}).get(key)=="pass"

    def _benchmark(self)->dict[str,Any]:
        d=_read_json(self._root/"BENCHMARK_BUILD_350_CONNECTORS.json")
        if d.get("build")!=self.BUILD or d.get("code_fingerprint")!=self.code_fingerprint() or d.get("cases",0)<350 or d.get("violations")!=0 or d.get("result")!="pass": return {}
        return d

    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        attr=getattr(self.build349,name,None)
        if attr is None: raise AttributeError(name)
        return attr

    def schema_metrics(self)->dict[str,Any]: return self.build349.schema_metrics()

    def version_status(self)->dict[str,Any]:
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text()
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="350.0.0"}

    def active_gate_literal_true_lines(self)->list[int]:
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []

    # Connector/parser SDK
    def connector_manifests(self)->list[dict[str,Any]]: return self.connector_sdk.manifests()
    def connector_source_plan(self,connector_key:str,identifier:str)->dict[str,Any]: return self.connector_sdk.source_plan(connector_key,identifier)
    def register_official_source(self,connector_key:str,identifier:str)->dict[str,Any]: return self.connector_sdk.register_official_source(connector_key,identifier)
    def parse_artifact(self,object_id:str,*,parser_version:str|None=None)->dict[str,Any]: return self.connector_sdk.parse_object(object_id,parser_version=parser_version)
    def parse_runs(self,**kwargs:Any)->list[dict[str,Any]]: return self.connector_sdk.parse_runs(**kwargs)
    def source_health(self,source_id:str,*,crawl_run_id:str="")->dict[str,Any]: return self.connector_sdk.record_source_health(source_id,crawl_run_id=crawl_run_id)
    def correlation_candidates(self,*,case_id:str)->list[dict[str,Any]]: return self.connector_sdk.correlation_candidates(case_id=case_id)

    def run_next_crawl(self,*,worker_id:str,transport:CrawlTransport,resolver:Callable[[str],Sequence[str]]|None=None)->dict[str,Any]|None:
        # If the next job belongs to an official connector, enforce connector-specific transport policy.
        job=self.db.one("SELECT * FROM phase15_jobs WHERE status='queued' AND job_type='governed_crawl_v1' ORDER BY priority DESC,created_at ASC LIMIT 1")
        if job:
            payload=json.loads(job["payload_json"]); source_id=str(payload.get("source_id") or "")
            policy=self.connector_sdk.validate_transport_for_source(source_id,transport)
            if not policy["allowed"]: raise PermissionError(policy["reason"])
        result=self.build349.run_next_crawl(worker_id=worker_id,transport=transport,resolver=resolver)
        if not result: return None
        try:
            payload=json.loads(result.get("payload_json") or "{}"); crawl_run_id=str(payload.get("crawl_run_id") or "")
            if not crawl_run_id:
                # completed Job payload is still persisted; read it by id.
                row=self.db.one("SELECT payload_json FROM phase15_jobs WHERE job_id=?",(result["job_id"],)); payload=json.loads(row["payload_json"]) if row else {}; crawl_run_id=str(payload.get("crawl_run_id") or "")
            if crawl_run_id:
                run=self.db.one("SELECT source_id FROM phase15_crawl_runs WHERE crawl_run_id=?",(crawl_run_id,))
                parse_summary=self.connector_sdk.parse_crawl_run(crawl_run_id)
                health=self.connector_sdk.record_source_health(run["source_id"],crawl_run_id=crawl_run_id) if run else {}
                return {**result,"build350_parse_summary":parse_summary,"build350_source_health":health}
        except Exception as exc:
            return {**result,"build350_postprocess_error":f"{type(exc).__name__}:{exc}"[:1000]}
        return result

    def crawler_status(self)->dict[str,Any]:
        s=dict(self.build349.crawler_status()); s.update({"policy":CRAWLER_POLICY,"connector_parser_policy":PARSER_POLICY_VERSION,"parser_sdk":self.connector_sdk.status(),"crawler_improvement_build":350})
        return s

    def architecture_status(self)->dict[str,Any]:
        base=dict(self.build349.architecture_status())
        base.update({"crawler_policy":CRAWLER_POLICY,"parser_policy":PARSER_POLICY_VERSION,"html_parser":True,"json_parser":True,"xml_parser":True,"xml_dtd_entities_allowed":False,"content_type_sniffing":True,"canonical_url_extraction":True,"source_health_taxonomy":True,"official_connector_manifests":sorted(OFFICIAL_CONNECTORS),"companies_house_live_enabled":False,"authenticated_scraping_supported":False,"automatic_connector_live_fetch":False})
        return base

    @staticmethod
    def _maturity(states:dict[str,bool])->str:
        last="declared"
        for k in DIMENSIONS:
            if states[k]: last=k
            else: break
        return last

    def capabilities(self)->list[dict[str,Any]]:
        m=self.schema_metrics(); v=self.version_status(); bench=bool(self._benchmark()); fp=self.code_fingerprint()
        specs=[
            ("schema_baseline_v1_350","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False),
            ("crawler_v2_350","Governed crawler v2 retained and improved","crawler",True,True,"crawler",bench,False),
            ("connector_parser_sdk_v1","Connector/Parser SDK","data",True,True,"parsers",bench,False),
            ("source_health_v1","Source health and parser-contract status","data",True,True,"health",bench,False),
            ("gleif_connector_plan_v1","GLEIF official connector plan","corporate",True,True,"gleif",bench,True),
            ("sec_edgar_connector_plan_v1","SEC EDGAR official connector plan","corporate",True,True,"sec",bench,True),
            ("companies_house_plan_v1","Companies House authenticated connector plan","corporate",True,False,"companies_house",False,True),
            ("darknet_parser_quarantine_boundary_v1","Darknet/quarantine parser boundary","darknet",True,True,"darknet",bench,False),
            ("cross_source_correlation_leads_v1","Cross-source entity correlation leads without auto-merge","investigation",True,True,"correlation",bench,False),
            ("canonical_versioning_350","Canonical Build 350 version contract","packaging",v["coherent"],v["coherent"],"version",False,False),
        ]
        required={"schema_baseline_v1_350","crawler_v2_350","connector_parser_sdk_v1","source_health_v1","gleif_connector_plan_v1","sec_edgar_connector_plan_v1","darknet_parser_quarantine_boundary_v1","cross_source_correlation_leads_v1","canonical_versioning_350"}
        rows=[]
        for key,name,category,implemented,integrated,probe,benchmarkable,requires_external in specs:
            tested=bool(integrated and self._probe(probe)); states={"implemented":bool(implemented),"integrated":bool(implemented and integrated),"tested":tested,"benchmarked":bool(tested and benchmarkable),"externally_validated":False}
            rows.append({"capability_key":key,"display_name":name,"category":category,**states,"maturity":self._maturity(states),"required_for_build":key in required,"required_for_production":key not in {"schema_baseline_v1_350","companies_house_plan_v1"},"external_validation_required":requires_external,"code_fingerprint":fp})
        return rows

    def qualified_gate(self)->dict[str,Any]:
        rows=self.capabilities(); req=[r for r in rows if r["required_for_build"]]; tested=bool(req) and all(r["tested"] for r in req); parser_bench=any(r["capability_key"]=="connector_parser_sdk_v1" and r["benchmarked"] for r in rows); production=bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {"build":self.BUILD,"phase":"15","gate_authority":"build350_connector_parser_evidence_gate","build_acceptance_ready":tested and parser_bench and self.schema_metrics()["within_gate"],"production_release_ready":production,"release_ready":production,"baseline_tested":tested,"connector_parser_benchmarked":parser_bench,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"Crawler improvements remain bounded and review-first. Parsed output is a deterministic derivative, not a fact claim. Quarantined content is never auto-parsed. Official connectors remain subject to each provider's auth, rate, User-Agent and terms requirements."}

    def dashboard(self)->dict[str,Any]:
        return {"build":self.BUILD,"phase":"15","name":"Connector & Parser SDK","schema":self.schema_metrics(),"crawler":self.crawler_status(),"architecture":self.architecture_status(),"gate":self.qualified_gate(),"version":self.version_status(),"capabilities":self.capabilities(),"connectors":self.connector_manifests(),"crawler_improvement_commitment":"349-360"}

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        st=self.connector_sdk.status(); gate=self.qualified_gate()
        return ("<section class='card'><h2>Phase 15 · Build 350 · Connector & Parser SDK</h2>"
                f"<p><b>Parser Runs:</b> {st['parse_runs']} · <b>Official Manifests:</b> {st['official_manifests']} · <b>Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'offen'}.</p>"
                "<p>HTML/JSON/XML/Text werden versioniert und hashgebunden normalisiert. Quarantäne bleibt vor Parser und Index. GLEIF/SEC sind öffentliche Connector-Pläne; Companies House bleibt wegen API-Authentisierung plan-only.</p>"
                f"<form method='post' action='/cases/{html.escape(case_id)}/connectors/official'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Connector</label><select name='connector_key'><option value='gleif_lei_api_v1'>GLEIF LEI</option><option value='sec_edgar_submissions_v1'>SEC EDGAR</option><option value='companies_house_company_v1'>Companies House (plan-only)</option></select><label>LEI / CIK / Company Number</label><input name='identifier' required><button>Quellenplan anlegen</button></form>"
                "<p><small>Status: <code>/api/build350</code></small></p></section>")
