from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
POLICY_VERSION="phase15.final-qualification-and-truthful-release.v360"


def _read_json(path:Path)->dict[str,Any]:
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}


class Build360FinalQualificationService:
    BUILD="360.0"
    PACKAGE="360.0.0"
    def __init__(self,db:Any,audit:Any,*,build359:Any,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.build359=build359; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        value=getattr(self.build359,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self):
        return (
            "src/eagleeye/application/build360/service.py","src/eagleeye/interfaces/web/app360.py",
            "eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py",
            "pyproject.toml","EAGLEEYE_PRO_360_0.py","EAGLEEYE_ACCEPTANCE_BUILD_360_0.py","tests/test_build360.py"
        )
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            path=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(path.read_bytes() if path.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        value=_read_json(self._root/"BUILD_360_TEST_EVIDENCE.json")
        return value if value.get("build")==self.BUILD and value.get("result")=="pass" and value.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key:str)->bool:
        return self._test_evidence().get("probes",{}).get(key)=="pass"
    def _benchmark(self):
        value=_read_json(self._root/"BENCHMARK_BUILD_360_FINAL_QUALIFICATION.json")
        return value if value.get("build")==self.BUILD and value.get("code_fingerprint")==self.code_fingerprint() and int(value.get("cases",0))>=2000 and int(value.get("violations",-1))==0 and value.get("result")=="pass" else {}
    def schema_metrics(self): return self.build359.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text()
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package==self.PACKAGE}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name=="qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    def external_validation_matrix(self):
        return {
            "external_pentest":{"status":"not_run","blocking":True},
            "external_red_team":{"status":"not_run","blocking":True},
            "external_load_failure_test":{"status":"not_run","blocking":True},
            "remote_multi_user_deployment":{"status":"not_validated","blocking":True},
            "live_postgresql":{"status":"not_run","blocking":False},
            "live_s3_minio":{"status":"not_run","blocking":False},
            "live_team_search_backend":{"status":"not_run","blocking":False},
            "live_local_stt_model":{"status":"not_run","blocking":False},
            "live_reverse_image_provider":{"status":"not_run","blocking":False},
            "live_tor_gateway":{"status":"not_run","blocking":False},
            "professional_pilot":{"status":"not_run","blocking":True},
        }
    def external_validation_complete(self):
        return all(v.get("status") in {"pass","validated"} for v in self.external_validation_matrix().values() if v.get("blocking"))
    def readiness_assessment(self):
        bench=bool(self._benchmark()); tests=bool(self._test_evidence()); qualified=bench and tests
        rows=[
            ("architecture_schema_packaging",10,9 if qualified else 7,"Consolidated schema, deterministic packages, no per-build schema explosion."),
            ("evidence_ai_dossier",10,9 if qualified else 7,"Evidence-first dossier, provenance, hypotheses/counterevidence and multi-wave supervisor."),
            ("crawler_data_acquisition",10,8 if qualified else 6,"Bounded crawler, delta/frontier/resume/media/connectors; limited live external connector validation."),
            ("opsec_security",10,9 if qualified else 7,"Per-search capsule and OPSEC-v2 internally qualified; external pentest/red-team outstanding."),
            ("image_intelligence",10,8 if qualified else 6,"Secure ingest, metadata/OCR/similarity/geo hypotheses; no external reverse-image live validation."),
            ("voice_workspace",10,7 if qualified else 5,"Push-to-talk contract and local TTS; local Whisper model not live-validated in build environment."),
            ("team_rbac_governance",10,9 if qualified else 7,"Argon2id local team identity, case RBAC and four-eyes export; remote team deployment not validated."),
            ("data_platform_backends",10,7 if qualified else 5,"SQLite/local CAS live; PostgreSQL/S3/team-search adapters contract-tested but not externally live-validated."),
            ("reliability_recovery",10,9 if qualified else 7,"Persistent jobs, leases, retry/DLQ, crash resume, local soak/failure qualification."),
            ("external_validation_pilot",10,0,"Independent pentest/load/pilot validation has not been performed in this build environment."),
        ]
        total=sum(score for _,_,score,_ in rows); internal=sum(score for key,_,score,_ in rows if key!="external_validation_pilot"); internal_max=90
        return {
            "classification":"controlled_local_pilot_candidate" if qualified else "engineering_candidate",
            "internal_engineering_readiness_percent":round(100*internal/internal_max),
            "operative_production_readiness_score":total,
            "score_max":100,
            "production_release_ready":False,
            "rows":[{"area":k,"max":mx,"score":sc,"basis":basis} for k,mx,sc,basis in rows],
            "blocking_gaps":["independent external pentest/red-team","external load/failure qualification","remote multi-user deployment validation","professional pilot with reviewed cases"],
            "important_nonblocking_gaps":["live PostgreSQL/S3/team-search validation","live local STT model validation","live reverse-image provider validation","live Tor gateway validation"],
            "truthful_summary":"Build 360 is internally qualified as a controlled local pilot candidate, not a production release. Internal benchmarks cannot substitute for independent external validation."
        }
    def crawler_release_qualification(self):
        base=dict(self.build359.crawler_status()); bench=bool(self._benchmark())
        return {**base,"crawler_improvement_build":360,"build360_boundedness_qualified":bench,"build360_failure_recovery_qualified":self._probe("crawler_failure"),"build360_delta_frontier_provenance_qualified":self._probe("crawler_provenance"),"build360_media_crawler_qualified":self._probe("image"),"build360_rbac_quota_recovery_qualified":self._probe("rbac"),"external_crawler_load_test":"not_run","live_tor_gateway":"not_run"}
    def architecture_status(self):
        return {**self.build359.architecture_status(),"final_qualification_policy":POLICY_VERSION,"phase15_builds_completed":20,"final_internal_qualification":bool(self._benchmark()) and bool(self._test_evidence()),"external_validation_complete":self.external_validation_complete(),"release_classification":self.readiness_assessment()["classification"]}
    @staticmethod
    def _maturity(states):
        last="declared"
        for key in DIMENSIONS:
            if states[key]: last=key
            else: break
        return last
    def capabilities(self):
        specs=[
            ("final_e2e_qualification_v360","End-to-end Phase-15 qualification","release","e2e"),
            ("opsec_redteam_internal_v360","Internal OPSEC/red-team matrix","security","opsec"),
            ("crawler_release_qualification_v360","Crawler failure/provenance qualification","crawler","crawler_failure"),
            ("ai_dossier_release_qualification_v360","AI investigation/dossier qualification","ai","dossier"),
            ("image_release_qualification_v360","Image-intelligence qualification","image","image"),
            ("voice_release_qualification_v360","Voice/intent qualification","voice","voice"),
            ("team_rbac_release_qualification_v360","RBAC/cross-case qualification","team","rbac"),
            ("recovery_soak_internal_v360","Local recovery/soak qualification","operations","recovery"),
            ("truthful_release_assessment_v360","Truthful readiness assessment","release","truthfulness"),
        ]; bench=bool(self._benchmark()); out=[]
        for key,label,cat,probe in specs:
            states={"implemented":True,"integrated":True,"tested":self._probe(probe),"benchmarked":bench,"externally_validated":False}
            out.append({"key":key,"label":label,"category":cat,"states":states,"maturity":self._maturity(states)})
        return out
    def qualified_gate(self):
        metrics=self.schema_metrics(); version=self.version_status(); tests=self._test_evidence(); bench=self._benchmark()
        checks={
            "schema_within_gate":metrics["within_gate"],"version_coherent":version["coherent"],"test_evidence_current":bool(tests),
            "benchmark_2000_no_violations":bool(bench),"no_literal_true_gate":self.active_gate_literal_true_lines()==[],
            "e2e_tested":self._probe("e2e"),"opsec_tested":self._probe("opsec"),"crawler_failure_tested":self._probe("crawler_failure"),
            "crawler_provenance_tested":self._probe("crawler_provenance"),"dossier_tested":self._probe("dossier"),"image_tested":self._probe("image"),
            "voice_tested":self._probe("voice"),"rbac_tested":self._probe("rbac"),"recovery_tested":self._probe("recovery"),"truthfulness_tested":self._probe("truthfulness")
        }
        ready=all(bool(v) for v in checks.values()); ext=self.external_validation_complete()
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":ready,"controlled_pilot_candidate_ready":ready,"production_release_ready":ready and ext,"external_validation_complete":ext,"truthful_note":"Build 360 completes internal Phase-15 qualification. Production remains blocked until independent external security/load validation and a professional pilot are actually completed."}
    def final_status(self):
        return {"build":self.BUILD,"phase15_builds_completed":20,"gate":self.qualified_gate(),"readiness":self.readiness_assessment(),"external_validation":self.external_validation_matrix(),"crawler":self.crawler_release_qualification(),"schema":self.schema_metrics(),"version":self.version_status()}
    def dashboard(self):
        return {"build":self.BUILD,"architecture":self.architecture_status(),"final_status":self.final_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
    def render_workspace_panel(self,*,case_id:str,csrf:str,identity:dict[str,Any]|None=None)->str:
        base=self.build359.render_workspace_panel(case_id=case_id,csrf=csrf,identity=identity); r=self.readiness_assessment()
        return base+f"<div class='card'><h2>Phase 15 Abschluss · Build 360</h2><p><b>{r['classification']}</b> · interne Engineering-Reife {r['internal_engineering_readiness_percent']}% · operative Production-Readiness {r['operative_production_readiness_score']}/100.</p><p>Production bleibt blockiert, bis unabhängige externe Security-/Load-Tests und ein professioneller Pilot tatsächlich durchgeführt wurden.</p></div>"
