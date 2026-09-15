from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from eagleeye.investigation.supervisor357 import DOSSIER_VERSION, POLICY_VERSION, WAVE_CONTRACT, MAX_WAVES, MultiWaveInvestigationSupervisor357

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding="utf-8")); return value if isinstance(value,dict) else {}
    except Exception: return {}


class Build357MultiWaveResearchService:
    BUILD="357.0"
    def __init__(self, db:Any, audit:Any, *, build356:Any, supervisor:MultiWaveInvestigationSupervisor357, install_dir:str|Path, base_dir:str|Path, actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build356=build356; self.supervisor=supervisor; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        value=getattr(self.build356,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return (
            "src/eagleeye/investigation/supervisor356.py","src/eagleeye/investigation/supervisor357.py","src/eagleeye/application/build357/service.py",
            "src/eagleeye/interfaces/web/app357.py","src/eagleeye/crawler/engine.py","src/eagleeye/crawler/frontier.py","src/eagleeye/jobs/engine.py",
            "eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_357_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_357_0.py","tests/test_build357.py",
        )
    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self._root/"BUILD_357_TEST_EVIDENCE.json")
        return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,key): return self._test_evidence().get("probes",{}).get(key)=="pass"
    def _benchmark(self):
        v=_read_json(self._root/"BENCHMARK_BUILD_357_RESEARCH_WAVES.json")
        return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=900 and int(v.get("violations",-1))==0 and v.get("result")=="pass" else {}
    def training_basis(self):
        v=_read_json(self._root/"TRAINING_BASIS_BUILD_357_AI_INVESTIGATION.json")
        return v if v.get("build")==self.BUILD else {"build":self.BUILD,"status":"not_generated","human_reviewed_training_examples":0}
    def schema_metrics(self): return self.build356.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text();
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="357.0.0"}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=="qualified_gate": return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    # supervisor API
    def create_investigation_intake(self,**kwargs): return self.supervisor.create_intake(**kwargs)
    def latest_investigation_intake(self,case_id): return self.supervisor.latest_intake(case_id)
    def start_investigation_go(self,**kwargs): return self.supervisor.start_go(**kwargs)
    def active_investigation_go(self,case_id): return self.supervisor.active_go(case_id)
    def investigation_research_waves(self,case_id): return self.supervisor.research_waves(case_id)
    def evaluate_investigation_wave(self,**kwargs): return self.supervisor.evaluate_latest_wave(**kwargs)
    def monitor_investigation_crawler(self,case_id): return self.supervisor.crawler_monitor(case_id)
    def investigation_snapshot(self,case_id): return self.supervisor.collect_case_snapshot(case_id)
    def form_initial_hypotheses(self,**kwargs): return self.supervisor.form_initial_hypotheses(**kwargs)
    def build_investigation_dossier(self,**kwargs): return self.supervisor.build_dossier(**kwargs)
    def latest_investigation_dossier(self,case_id): return self.supervisor.latest_dossier(case_id)
    def investigation_supervisor_tick(self,**kwargs): return self.supervisor.supervisor_tick(**kwargs)
    def ai_investigation_status(self):
        waves=self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE task_json LIKE '%research_wave_v357%'")
        reports=self.db.one("SELECT COUNT(*) c FROM professional_reports WHERE report_type='phase15_ai_dossier_v357'")
        return {**self.supervisor.status(),"dossier_version":DOSSIER_VERSION,"wave_count":int(waves["c"] if waves else 0),"dossier_count":int(reports["c"] if reports else 0),"training_basis":self.training_basis()}
    def crawler_status(self):
        s=dict(self.build356.crawler_status()); s.update({"crawler_improvement_build":357,"build357_research_wave_subjobs":True,"ai_prioritized_bounded_crawl_subjobs":True,"wave_terminal_evaluation_before_followup":True,"stop_on_opsec_dead_letter_or_no_delta":True,"supervisor_network_execution":False,"dossier_trace_chain":"wave->crawl_run->fetch->object_hash->parse/media/link->hypothesis->dossier"}); return s
    def architecture_status(self):
        return {"investigation_policy":POLICY_VERSION,"wave_contract":WAVE_CONTRACT,"dossier_version":DOSSIER_VERSION,"explicit_go_required":True,"multi_wave_autonomy_after_go":True,"max_waves":MAX_WAVES,"previous_wave_terminal_before_followup":True,"bounded_jobs_and_sources":True,"new_source_auto_approval":False,"supervisor_direct_network":False,"supervisor_direct_shell":False,"opsec_stop_gate":True,"dead_letter_stop_gate":True,"no_delta_stop_gate":True,"cross_modal_refusion_each_wave":True,"written_dossier":True,"speech_output":"local_browser_speech_synthesis","voice_input":False,"built_in_live_tor_transport":False}
    @staticmethod
    def _maturity(states):
        last="declared"
        for k in DIMENSIONS:
            if states[k]: last=k
            else: break
        return last
    def capabilities(self):
        m=self.schema_metrics(); bench=bool(self._benchmark()); specs=[
            ("multi_wave_orchestration_v357","GO-gated bounded multi-wave research","ai",True,True,"waves",bench,False),
            ("wave_terminal_evaluation_v357","Terminal evaluation before follow-up","ai",True,True,"terminal",bench,False),
            ("crawler_priority_subjobs_v357","AI-prioritized bounded crawler subjobs","crawler",True,True,"crawler",bench,False),
            ("wave_stop_gates_v357","OPSEC/dead-letter/no-delta stop gates","security",True,True,"stops",bench,False),
            ("dossier_refusion_v357","Dossier refusion across research waves","ai",True,True,"dossier",bench,False),
            ("schema_baseline_retained_v357","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False),
        ]; out=[]
        for key,label,cat,impl,integ,probe,benchmark,ext in specs:
            st={"implemented":bool(impl),"integrated":bool(integ),"tested":self._probe(probe),"benchmarked":bool(benchmark),"externally_validated":bool(ext)}; out.append({"key":key,"label":label,"category":cat,"states":st,"maturity":self._maturity(st)})
        return out
    def qualified_gate(self):
        m=self.schema_metrics(); v=self.version_status(); bench=self._benchmark(); tests=self._test_evidence(); cap=self.capabilities()
        checks={"schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(tests),"benchmark_900_no_violations":bool(bench),"no_literal_true_gate":self.active_gate_literal_true_lines()==[],"waves_tested":self._probe("waves"),"terminal_gate_tested":self._probe("terminal"),"crawler_subjobs_tested":self._probe("crawler"),"stop_gates_tested":self._probe("stops"),"dossier_refusion_tested":self._probe("dossier")}
        ready=all(bool(x) for x in checks.values()); external=all(c["states"]["externally_validated"] for c in cap)
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":ready,"production_release_ready":ready and external,"external_validation_complete":external,"truthful_note":"Build 357 validates bounded multi-wave orchestration after explicit GO. It does not claim live external provider validation, model-weight training, voice input, live Tor transport, automatic identity confirmation or release."}
    def dashboard(self): return {"build":self.BUILD,"architecture":self.architecture_status(),"ai_investigation":self.ai_investigation_status(),"crawler":self.crawler_status(),"schema":self.schema_metrics(),"version":self.version_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        waves=self.supervisor.research_waves(case_id); rows="".join(f"<tr><td>{w['wave_number']}</td><td>{w['terminal']}</td><td>{w['job_states']}</td><td>{len(w['source_ids'])}</td></tr>" for w in waves) or "<tr><td colspan='4'>Noch keine Research Wave.</td></tr>"
        return f"<div class='card'><h2>AI-Ermittlung 357 · Research Waves</h2><p>GO autorisiert begrenzte Folge-Wellen ausschließlich auf bereits freigegebenen Quellen. Jede Folge-Welle wartet auf terminale Auswertung der vorherigen.</p><table><tr><th>Wave</th><th>Terminal</th><th>Jobs</th><th>Quellen</th></tr>{rows}</table><form method='post' action='/cases/{case_id}/ai/tick'><input type='hidden' name='csrf' value='{csrf}'><button>Supervisor auswerten / nächste Wave</button></form></div>"
