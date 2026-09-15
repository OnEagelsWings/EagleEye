from __future__ import annotations
import ast, hashlib, json, re
from pathlib import Path
from typing import Any

DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
POLICY_VERSION="phase15.voice-investigation-workspace.v358"

def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

class Build358VoiceInvestigationService:
    BUILD="358.0"
    def __init__(self,db:Any,audit:Any,*,build357:Any,voice:Any,install_dir:str|Path,base_dir:str|Path,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.build357=build357; self.voice=voice; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._root=self.install_dir
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build357,name,None)
        if v is None: raise AttributeError(name)
        return v
    def _fingerprint_paths(self):
        return ("src/eagleeye/voice/gateway358.py","src/eagleeye/application/build358/service.py","src/eagleeye/interfaces/web/app358.py","src/eagleeye/investigation/supervisor357.py","eagleeye_pro/core/app_context.py","src/eagleeye/interfaces/web/server.py","eagleeye_pro/version.py","pyproject.toml","EAGLEEYE_PRO_358_0.py","EAGLEEYE_ACCEPTANCE_BUILD_358_0.py","tests/test_build358.py")
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self._root/rel; h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()
    def _test_evidence(self):
        v=_read_json(self._root/"BUILD_358_TEST_EVIDENCE.json"); return v if v.get("build")==self.BUILD and v.get("result")=="pass" and v.get("code_fingerprint")==self.code_fingerprint() else {}
    def _probe(self,k):return self._test_evidence().get("probes",{}).get(k)=="pass"
    def _benchmark(self):
        v=_read_json(self._root/"BENCHMARK_BUILD_358_VOICE_WORKSPACE.json"); return v if v.get("build")==self.BUILD and v.get("code_fingerprint")==self.code_fingerprint() and int(v.get("cases",0))>=1000 and int(v.get("violations",-1))==0 and v.get("result")=="pass" else {}
    def training_basis(self):
        v=_read_json(self._root/"TRAINING_BASIS_BUILD_358_AI_INVESTIGATION.json"); return v if v.get("build")==self.BUILD else {"build":self.BUILD,"status":"not_generated","human_reviewed_training_examples":0}
    def schema_metrics(self):return self.build357.schema_metrics()
    def version_status(self):
        vt=(self._root/"eagleeye_pro/version.py").read_text(); pt=(self._root/"pyproject.toml").read_text();
        rb=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M); rs=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M); rp=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M)
        runtime=rb.group(1) if rb else "unknown"; schema=rs.group(1) if rs else "unknown"; package=rp.group(1) if rp else "unknown"
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package=="358.0.0"}
    def active_gate_literal_true_lines(self):
        tree=ast.parse(Path(__file__).read_text(encoding="utf-8"));
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name=="qualified_gate": return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,"lineno")})
        return []
    # voice API
    def voice_propose(self,**kwargs):return self.voice.propose_transcript(**kwargs)
    def voice_transcribe(self,**kwargs):return self.voice.transcribe_push_to_talk(**kwargs)
    def voice_execute(self,**kwargs):return self.voice.execute(**kwargs)
    def voice_interactions(self,case_id:str,limit:int=50):return self.voice.interactions(case_id,limit)
    def voice_status(self):return self.voice.status()
    def crawler_status(self):
        s=dict(self.build357.crawler_status()); s.update({"crawler_improvement_build":358,"build358_voice_directed_bounded_research":True,"voice_cannot_bypass_go":True,"voice_cannot_bypass_opsec":True,"voice_cannot_expand_source_allowlist":True,"voice_crawler_status_read_only":True,"supervisor_network_execution":False}); return s
    def ai_investigation_status(self):
        s=dict(self.build357.ai_investigation_status()); row=self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE agent_role='voice_gateway'"); s.update({"voice_gateway":self.voice.status(),"voice_interaction_count":int(row.get('c') if row else 0),"training_basis_358":self.training_basis()}); return s
    def architecture_status(self):
        return {**self.build357.architecture_status(),"investigation_policy":POLICY_VERSION,"voice_input":True,"voice_input_mode":"push_to_talk_local_stt_adapter","visible_editable_transcript":True,"dictation_command_separation":True,"external_research_voice_confirmation":True,"export_merge_delete_release_voice_execution":False,"audio_deleted_by_default":True,"always_on_microphone":False,"voice_biometrics":False,"local_stt_live_validated":False,"speech_output":"local_browser_speech_synthesis","built_in_live_tor_transport":False}
    @staticmethod
    def _maturity(states):
        last="declared"
        for k in DIMENSIONS:
            if states[k]:last=k
            else:break
        return last
    def capabilities(self):
        m=self.schema_metrics(); bench=bool(self._benchmark()); specs=[
            ("voice_gateway_v358","Push-to-talk voice gateway","voice",1,1,"voice",bench,False),("editable_transcript_v358","Visible editable transcript and intent summary","voice",1,1,"transcript",bench,False),("voice_confirmation_gate_v358","Confirmation gate for external research commands","security",1,1,"confirm",bench,False),("voice_manual_irreversible_gate_v358","Voice cannot execute export/merge/delete/release","security",1,1,"manual",bench,False),("voice_crawler_control_v358","Voice-directed bounded crawler/research controls","crawler",1,1,"crawler",bench,False),("schema_baseline_retained_v358","Schema baseline retained","schema",m["within_gate"],m["within_gate"],"schema",False,False)]
        out=[]
        for key,label,cat,impl,integ,probe,bm,ext in specs:
            st={"implemented":bool(impl),"integrated":bool(integ),"tested":self._probe(probe),"benchmarked":bool(bm),"externally_validated":bool(ext)}; out.append({"key":key,"label":label,"category":cat,"states":st,"maturity":self._maturity(st)})
        return out
    def qualified_gate(self):
        m=self.schema_metrics(); v=self.version_status(); bench=self._benchmark(); tests=self._test_evidence();
        checks={"schema_within_gate":m["within_gate"],"version_coherent":v["coherent"],"test_evidence_current":bool(tests),"benchmark_1000_no_violations":bool(bench),"no_literal_true_gate":self.active_gate_literal_true_lines()==[],"voice_tested":self._probe("voice"),"transcript_tested":self._probe("transcript"),"confirmation_tested":self._probe("confirm"),"manual_gate_tested":self._probe("manual"),"crawler_voice_tested":self._probe("crawler")}
        ready=all(bool(x) for x in checks.values()); external=False
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":ready,"production_release_ready":False,"external_validation_complete":external,"truthful_note":"Build 358 integrates push-to-talk, editable transcript, structured voice intent and confirmation gates. Local STT is adapter-backed and not live-validated unless an operator supplies a local model. No browser-cloud speech service, live Tor, voice biometric, voice-only export/merge/delete/release, model-weight training or automatic release is claimed."}
    def dashboard(self):return {"build":self.BUILD,"architecture":self.architecture_status(),"voice":self.voice.status(),"ai_investigation":self.ai_investigation_status(),"crawler":self.crawler_status(),"schema":self.schema_metrics(),"version":self.version_status(),"capabilities":self.capabilities(),"gate":self.qualified_gate()}
    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        base=self.build357.render_workspace_panel(case_id=case_id,csrf=csrf)
        interactions=self.voice.interactions(case_id,12); rows="".join(f"<tr><td>{x.get('mode','')}</td><td>{x.get('intent','')}</td><td>{str(x.get('transcript',''))[:180]}</td><td>{'ja' if x.get('requires_confirmation') else 'nein'}</td></tr>" for x in interactions) or "<tr><td colspan='4'>Noch keine Voice-Interaktion.</td></tr>"
        voice=f"""<div class='card'><h2>Voice Investigation Workspace 358</h2><p>Push-to-talk · sichtbares/editierbares Transkript · Diktat/Befehl getrennt. Externe Recherchebefehle benötigen eine zweite Bestätigung; Export/Merge/Delete/Release bleiben manuelle UI-Aktionen.</p><div id='eeVoiceStatus' class='muted'>Lokales STT-Modell: {'konfiguriert' if self.voice.status()['local_stt_model_configured'] else 'nicht konfiguriert – Transkript kann manuell eingegeben werden'}.</div><label>Modus</label><select id='eeVoiceMode'><option value='command'>Befehl</option><option value='dictation'>Diktat</option></select><button type='button' id='eePushToTalk'>Push-to-talk starten</button> <button type='button' id='eeStopTalk'>Aufnahme stoppen</button><label>Sichtbares/editierbares Transkript</label><textarea id='eeVoiceTranscript' rows='5'></textarea><button type='button' id='eeInterpretVoice' data-case='{case_id}' data-csrf='{csrf}'>Transkript interpretieren</button><div id='eeIntentSummary' class='card' style='display:none'></div><div id='eeVoiceConfirm' style='display:none'><button type='button' id='eeConfirmVoice'>Bestätigen & ausführen</button></div><table><tr><th>Modus</th><th>Intent</th><th>Transkript</th><th>Bestätigung</th></tr>{rows}</table><script src='/assets/build358.js'></script></div>"""
        return base+voice
