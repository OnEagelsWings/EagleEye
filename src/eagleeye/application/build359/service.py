from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
POLICY_VERSION="phase15.team-ops-release-hardening.v359"


def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}


class Build359TeamOperationsService:
    BUILD="359.0"
    def __init__(self,db:Any,audit:Any,*,build358:Any,team_ops:Any,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.build358=build358; self.team_ops=team_ops; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"):raise AttributeError(name)
        v=getattr(self.build358,name,None)
        if v is None:raise AttributeError(name)
        return v
    def _fingerprint_paths(self):return ("src/eagleeye/team/identity359.py","src/eagleeye/team/governance359.py","src/eagleeye/application/build359/service.py","src/eagleeye/interfaces/web/app359.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_359_0.py","EAGLEEYE_ACCEPTANCE_BUILD_359_0.py","tests/test_build359.py")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode());h.update(b"\0");h.update(p.read_bytes() if p.is_file() else b"<missing>");h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self._root/"BUILD_359_TEST_EVIDENCE.json");return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,k):return self._test_evidence().get("probes",{}).get(k)=="pass"
    def _benchmark(self):
        v=_read_json(self._root/"BENCHMARK_BUILD_359_TEAM_OPS.json");return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=1200 and int(v.get("violations",-1))==0 and v.get("result")=="pass" else {}
    def schema_metrics(self):return self.build358.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text();pt=(self._root/"pyproject.toml").read_text();rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M);rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M);rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M);runtime=rb.group(1) if rb else "unknown";schema=rs.group(1) if rs else "unknown";package=rp.group(1) if rp else "unknown";return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="359.0.0"}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=="qualified_gate":return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def team_status(self,case_id:str=""):return self.team_ops.team_status(case_id)
    def visible_cases(self,identity):return self.team_ops.visible_cases(identity)
    def team_create_case(self,**kwargs):return self.team_ops.create_case(**kwargs)
    def team_create_user(self,**kwargs):return self.team_ops.create_user(**kwargs)
    def assign_case_role(self,**kwargs):return self.team_ops.assign_case_role(**kwargs)
    def revoke_case_role(self,**kwargs):return self.team_ops.revoke_case_role(**kwargs)
    def authorize(self,identity:dict[str,Any]|str,*,case_id:str,capability:str,object_type:str="",object_id:str=""):return self.team_ops.authorize(identity,case_id=case_id,capability=capability,object_type=object_type,object_id=object_id)
    def request_dossier_export(self,**kwargs):return self.team_ops.request_dossier_export(**kwargs)
    def review_dossier_export(self,**kwargs):return self.team_ops.review_dossier_export(**kwargs)
    def execute_dossier_export(self,**kwargs):return self.team_ops.execute_dossier_export(**kwargs)
    def export_status(self,task_id:str):return self.team_ops.export_status(task_id)
    def team_voice_propose(self,**kwargs):return self.team_ops.voice_propose(**kwargs)
    def team_voice_transcribe(self,**kwargs):return self.team_ops.voice_transcribe(**kwargs)
    def team_voice_execute(self,**kwargs):return self.team_ops.voice_execute(**kwargs)
    def team_enqueue_crawl(self,**kwargs):return self.team_ops.enqueue_crawl(**kwargs)
    def team_review_crawler_source(self,**kwargs):return self.team_ops.review_crawler_source(**kwargs)
    def crawler_operational_snapshot(self,**kwargs):return self.team_ops.crawler_operational_snapshot(**kwargs)
    def recover_expired_crawler_leases(self,**kwargs):return self.team_ops.recover_expired_crawler_leases(**kwargs)
    def crawler_status(self):
        s=dict(self.build358.crawler_status());s.update({"crawler_improvement_build":359,"build359_case_scoped_rbac":True,"build359_role_gated_crawl_execution":True,"build359_lead_only_lease_recovery":True,"build359_dead_letter_human_attention":True,"build359_soak_recovery_qualification":True,"voice_cannot_bypass_rbac":True,"supervisor_network_execution":False});return s
    def architecture_status(self):
        return {**self.build358.architecture_status(),"team_ops_policy":POLICY_VERSION,"canonical_identity_backend":"phase15_team_identity_v359","case_scoped_rbac":True,"roles":["case_lead","investigator","analyst","reviewer","report_author","read_only"],"four_eyes_dossier_export":True,"same_actor_export_approval":False,"voice_rbac":True,"crawler_rbac":True,"audit_chain_verification":True,"multi_user_remote_server":False,"built_in_live_tor_transport":False}
    def operational_status(self):return {"team":self.team_ops.team_status(),"crawler":self.crawler_status(),"audit":self.team_ops.verify_audit_chain(),"identity":self.team_ops.identity.status()}
    @staticmethod
    def _maturity(states):
        last="declared"
        for k in DIMENSIONS:
            if states[k]:last=k
            else:break
        return last
    def capabilities(self):
        m=self.schema_metrics();bench=bool(self._benchmark());specs=[("team_rbac_v359","Case-scoped team RBAC","team",1,1,"rbac",bench,False),("four_eyes_export_v359","Four-eyes dossier export","governance",1,1,"export",bench,False),("voice_rbac_v359","Voice commands obey case RBAC","voice",1,1,"voice",bench,False),("crawler_ops_v359","RBAC crawler operations and lease recovery","crawler",1,1,"crawler",bench,False),("audit_chain_v359","Canonical auth security audit chain verification","audit",1,1,"audit",bench,False),("soak_recovery_v359","Local queue/crawler soak and recovery qualification","operations",1,1,"soak",bench,False),("schema_baseline_retained_v359","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False)];out=[]
        for key,label,cat,impl,integ,probe,bm,ext in specs:
            st={"implemented":bool(impl),"integrated":bool(integ),"tested":self._probe(probe),"benchmarked":bool(bm),"externally_validated":bool(ext)};out.append({"key":key,"label":label,"category":cat,"states":st,"maturity":self._maturity(st)})
        return out
    def qualified_gate(self):
        m=self.schema_metrics();v=self.version_status();bench=self._benchmark();tests=self._test_evidence();checks={"schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(tests),"benchmark_1200_no_violations":bool(bench),"no_literal_true_gate":self.active_gate_literal_true_lines()==[],"rbac_tested":self._probe("rbac"),"four_eyes_export_tested":self._probe("export"),"voice_rbac_tested":self._probe("voice"),"crawler_ops_tested":self._probe("crawler"),"audit_chain_tested":self._probe("audit"),"soak_tested":self._probe("soak")};ready=all(bool(x) for x in checks.values());return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":ready,"production_release_ready":False,"external_validation_complete":False,"truthful_note":"Build 359 integrates local Argon2id team sessions, case-scoped RBAC, four-eyes dossier export, role-gated voice/crawler controls and local soak/recovery qualification. Remote multi-user deployment, external pentest, external load test, live Tor and production release are not claimed."}
    def dashboard(self):return {"build":self.BUILD,"architecture":self.architecture_status(),"operations":self.operational_status(),"crawler":self.crawler_status(),"schema":self.schema_metrics(),"version":self.version_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
    def render_workspace_panel(self,*,case_id:str,csrf:str,identity:dict[str,Any]|None=None)->str:
        base=self.build358.render_workspace_panel(case_id=case_id,csrf=csrf);who=(identity or {}).get("username") or "unbekannt";roles=self.team_ops.case_roles(identity or self.actor,case_id) if identity else []
        return base+f"<div class='card'><h2>Team Operations 359</h2><p>Aktiver Benutzer: <b>{who}</b> · Fallrollen: {', '.join(roles) or 'keine'}</p><p>RBAC gilt für Voice, Research-Waves, Crawler, Source-Review und Dossier-Export. Exporte benötigen Vier-Augen-Freigabe.</p></div>"
