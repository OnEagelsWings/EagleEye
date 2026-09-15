from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")

def _read_json(path: Path) -> dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:
        return {}

class Build370ControlledTorCrawlerService:
    BUILD="370.0"; PACKAGE="370.0.0"; POLICY="phase16.controlled-tor-crawler-build.v370"
    def __init__(self, db: Any, audit: Any, *, build369: Any, tor370: Any, ai370: Any, opsec370: Any, install_dir: Any, base_dir: Any, actor: str="local-analyst"):
        self.db=db; self.audit=audit; self.build369=build369; self.tor370=tor370; self.ai370=ai370; self.opsec370=opsec370; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build369,name,None)
        if v is None: raise AttributeError(name)
        return v
    def _fingerprint_paths(self)->tuple[str,...]:
        return (
            "src/eagleeye/phase16/tor_gateway370.py","src/eagleeye/crawler/frontier.py","src/eagleeye/security/search_capsule.py","src/eagleeye/application/build370/service.py","src/eagleeye/interfaces/web/app370.py",
            "eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml",
            "tests/test_build370.py","EAGLEEYE_ACCEPTANCE_BUILD_370_0.py","tools/live_tor_gateway_validate_370.py","tools/benchmark_build370.py",
            "PHASE_16_MASTERPLAN_BUILD_361_TO_380.md",
        )
    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_370_TEST_EVIDENCE.json"); return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_370_TOR_CRAWLER.json"); return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=3600 and int(v.get("violations",-1))==0 else {}
    def _live_validation(self):
        v=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_370_TOR_GATEWAY.json"); return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key): return self._test_evidence().get("probes",{}).get(key)=="pass"
    def schema_metrics(self): return self.build369.schema_metrics()
    def version_status(self):
        vt=(self.install_dir/"eagleeye_pro/version.py").read_text(); pt=(self.install_dir/"pyproject.toml").read_text()
        def g(p,t):
            m=re.search(p,t,re.M); return m.group(1) if m else "unknown"
        runtime=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate": return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def configure_tor_gateway(self,**kw): return self.tor370.configure(**kw)
    def tor_gateway_status(self): return self.tor370.status()
    def tor_local_probe(self,**kw): return self.tor370.local_socks_probe(**kw)
    def enqueue_tor_crawl(self,**kw): return self.tor370.enqueue_darknet_crawl(**kw)
    def tor_run_next(self,**kw): return self.tor370.run_next(**kw)
    def tor_recover_expired_leases(self,**kw): return self.tor370.recover_expired_leases(**kw)
    def tor_case_status(self,**kw): return self.tor370.case_status(**kw)
    def crawler_roadmap(self): return self.tor370.crawler_roadmap_370_380()
    def run_autonomous_investigation(self,**kw): return self.ai370.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw): return self.opsec370.protect_case(**kw)
    def protect_remote_session(self,**kw): return self.opsec370.protect_remote_session(**kw)
    def phase16_status(self):
        b=dict(self.build369.phase16_status()); b.update({"build":self.BUILD,"builds_completed":10,"controlled_tor_gateway":self.tor370.status(),"ai":self.ai370.status(),"opsec":self.opsec370.status(),"crawler_improvement_build":370,"continuous_crawler_expansion_370_380":True,"crawler_roadmap_370_380":self.crawler_roadmap()}); return b
    def crawler_status(self):
        b=dict(self.build369.crawler_status()); b.update({"crawler_improvement_build":370,"tor_specific_job_queue":True,"clearnet_tor_worker_separation":True,"tor_case_backpressure":True,"tor_lease_recovery":True,"tor_capsule_socks_auth_isolation":True,"tor_remote_dns_required":True,"darknet_recurring_schedule_disabled":True,"continuous_crawler_expansion_370_380":True,"crawler_roadmap_370_380":self.crawler_roadmap(),"automatic_external_connections_on_boot":0,"background_workers_started_on_boot":0}); return b
    def capabilities(self):
        bench=bool(self._benchmark()); live=self._live_validation(); local=live.get("local_socks_contract_validation")=="pass"; specs=[("controlled_tor_gateway_v370","gateway",False),("tor_remote_dns_v370","dns",False),("tor_socks_auth_isolation_v370","isolation",False),("tor_queue_separation_v370","queue",False),("tor_backpressure_v370","backpressure",False),("tor_lease_recovery_v370","lease",False),("crawler_continuity_370_380","roadmap",False),("crawler_ai_boundary_v370","ai",False),("crawler_opsec_boundary_v370","opsec",False),("local_socks_contract_v370","local",local)]
        out=[]
        for key,probe,ext in specs:
            tested=self._probe(probe) if probe!="local" else local; st={"implemented":True,"integrated":True,"tested":tested,"benchmarked":bench,"externally_validated":bool(ext)}; out.append({"key":key,"states":st,"maturity":next((k for k in reversed(DIMENSIONS) if st[k]),"declared")})
        return out
    def qualified_gate(self):
        m=self.schema_metrics(); v=self.version_status(); live=self._live_validation(); checks={
            "schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(self._test_evidence()),"benchmark_3600_no_violations":bool(self._benchmark()),
            "local_socks_contract_validation":live.get("local_socks_contract_validation")=="pass","local_tor_http_fixture_validation":live.get("local_tor_transport_http_validation")=="pass",
            "gateway_tested":self._probe("gateway"),"dns_isolation_tested":self._probe("dns"),"socks_auth_isolation_tested":self._probe("isolation"),"queue_separation_tested":self._probe("queue"),"backpressure_tested":self._probe("backpressure"),"lease_tested":self._probe("lease"),"crawler_roadmap_tested":self._probe("roadmap"),"ai_tested":self._probe("ai"),"opsec_tested":self._probe("opsec"),"no_literal_true_gate":self.active_gate_literal_true_lines()==[]}
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":all(bool(x) for x in checks.values()),"local_socks_contract_validated":live.get("local_socks_contract_validation")=="pass","local_tor_daemon_validated":live.get("local_tor_daemon_validation")=="pass","external_onion_validated":live.get("external_onion_validation")=="pass","production_release_ready":False,"truthful_note":"Build 370 validates the Tor SOCKS5 contract and Tor-labelled crawler path against a local fixture. It does not claim that a real Tor daemon or an external onion service was contacted."}
    def dashboard(self): return {"build":self.BUILD,"phase16":self.phase16_status(),"tor":self.tor370.status(),"crawler":self.crawler_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
