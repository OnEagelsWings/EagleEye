from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")

def _read_json(path:Path)->dict[str,Any]:
    try:
        value=json.loads(path.read_text(encoding="utf-8")); return value if isinstance(value,dict) else {}
    except Exception:return {}

class Build364RemoteTeamService:
    BUILD="364.0"; PACKAGE="364.0.0"; POLICY="phase16.remote-team-build.v364"
    def __init__(self,db,audit,*,build363,remote364,ai364,opsec364,install_dir,base_dir,actor="local-analyst"):
        self.db=db;self.audit=audit;self.build363=build363;self.remote364=remote364;self.ai364=ai364;self.opsec364=opsec364;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
    def __getattr__(self,name):
        if name.startswith("_"):raise AttributeError(name)
        value=getattr(self.build363,name,None)
        if value is None:raise AttributeError(name)
        return value
    def _fingerprint_paths(self):
        return ("src/eagleeye/phase16/remote_team364.py","src/eagleeye/application/build364/service.py","src/eagleeye/interfaces/web/app364.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","tests/test_build364.py","EAGLEEYE_ACCEPTANCE_BUILD_364_0.py","tools/live_tls_validate_364.py")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel;h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self.install_dir/"BUILD_364_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _benchmark(self):
        v=_read_json(self.install_dir/"BENCHMARK_BUILD_364_REMOTE_TEAM.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=2200 and int(v.get("violations",-1))==0 else {}
    def _probe(self,key):return self._test_evidence().get("probes",{}).get(key)=="pass"
    def schema_metrics(self):return self.build363.schema_metrics()
    def version_status(self):
        vt=(self.install_dir/"eagleeye_pro/version.py").read_text();pt=(self.install_dir/"pyproject.toml").read_text()
        def g(pattern,text):
            m=re.search(pattern,text,re.M);return m.group(1) if m else "unknown"
        r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt);s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt);p=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {"runtime_build":r,"schema_version":s,"package_version":p,"coherent":r==s==self.BUILD and p==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def remote_team_status(self):
        st=dict(self.remote364.status())
        receipt=_read_json(self.install_dir/"LIVE_VALIDATION_BUILD_364_REMOTE_TEAM.json")
        if receipt.get("build")==self.BUILD and receipt.get("status")=="pass":
            st["loopback_tls_validation_status"]="pass"
            st["loopback_tls_live_validated"]=bool(receipt.get("tls_handshake_verified_against_generated_ca"))
            st["live_tls_clients"] = int(receipt.get("clients",0))
            st["live_tls_cross_case_denial_http_status"] = int(receipt.get("cross_case_denial_http_status",0))
            st["external_remote_clients_validated"] = bool(receipt.get("external_remote_clients_validated",False))
            st["externally_validated"] = bool(receipt.get("externally_validated",False))
        return st
    def remote_config_validation(self,**kw):return self.remote364.validate_config(**kw)
    def remote_request_decision(self,**kw):return self.remote364.request_decision(**kw)
    def remote_contract_validation(self,**kw):return self.remote364.record_contract_validation(**kw)
    def loopback_tls_validation_receipt(self,**kw):return self.remote364.record_loopback_tls_validation(**kw)
    def run_autonomous_investigation(self,**kw):return self.ai364.run_cycle(**kw)
    def autonomous_opsec_protect(self,**kw):return self.opsec364.protect_case(**kw)
    def protect_remote_session(self,**kw):return self.opsec364.protect_remote_session(**kw)
    def phase16_status(self):
        base=dict(self.build363.phase16_status());base.update({"build":"364.0","builds_completed":4,"remote_team":self.remote_team_status(),"ai":self.ai364.status(),"opsec":self.opsec364.status(),"crawler_improvement_build":364});return base
    def crawler_status(self):
        base=dict(self.build363.crawler_status());base.update({"crawler_improvement_build":364,"remote_rbac_context_required":True,"remote_session_anomaly_aware":True,"cross_case_default_deny":True,"remote_client_quota_context":True,"remote_recovery_audited":True,"backend_failure_degrades_without_provenance_loss":True});return base
    @staticmethod
    def _maturity(states):
        last="declared"
        for key in DIMENSIONS:
            if states[key]:last=key
            else:break
        return last
    def capabilities(self):
        bench=bool(self._benchmark());remote=self.remote_team_status();external=remote["externally_validated"]
        specs=[("remote_multi_user_team_v364","remote_team",external),("direct_tls_profile_v364","tls",False),("cross_case_isolation_v364","cross_case",False),("session_anomaly_defense_v364","session_anomaly",False),("ai_remote_team_awareness_v364","ai",False),("opsec_remote_team_supervision_v364","opsec",False),("crawler_remote_rbac_v364","crawler",False)]
        out=[]
        for key,probe,ext in specs:
            states={"implemented":1==1,"integrated":1==1,"tested":self._probe(probe),"benchmarked":bench,"externally_validated":bool(ext)}
            out.append({"key":key,"states":states,"maturity":self._maturity(states)})
        return out
    def qualified_gate(self):
        m=self.schema_metrics();v=self.version_status();checks={"schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(self._test_evidence()),"benchmark_2200_no_violations":bool(self._benchmark()),"loopback_tls_live_validated":bool(self.remote_team_status().get("loopback_tls_live_validated")),"remote_team_contract_tested":self._probe("remote_team"),"tls_profile_tested":self._probe("tls"),"cross_case_isolation_tested":self._probe("cross_case"),"session_anomaly_tested":self._probe("session_anomaly"),"ai_improvement_tested":self._probe("ai"),"opsec_improvement_tested":self._probe("opsec"),"crawler_improvement_tested":self._probe("crawler"),"no_literal_true_gate":self.active_gate_literal_true_lines()==[]}
        st=self.remote_team_status()
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":all(bool(x) for x in checks.values()),"remote_team_externally_validated":st["externally_validated"],"external_remote_clients_validated":st["external_remote_clients_validated"],"production_release_ready":False,"truthful_note":"Build 364 validates remote-team security contracts and direct-TLS configuration locally. External remote clients and a deployed network environment are not available here, so external remote-team validation remains not_run unless separately executed."}
    def dashboard(self):return {"build":self.BUILD,"phase16":self.phase16_status(),"remote_team":self.remote_team_status(),"crawler":self.crawler_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
