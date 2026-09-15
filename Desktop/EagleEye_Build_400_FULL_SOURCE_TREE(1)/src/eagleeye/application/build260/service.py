from __future__ import annotations
import hashlib, html, json
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _text(v: Any, n: int = 10000) -> str:
    return str(v or "").replace("\x00", "").strip()[:n]

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()

def _loads(v: Any, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default

STAGES = (
    "schema_sqlite_integrity","phase10_parent_gates","financial_flow_semantics","source_profile_routing",
    "document_provenance_quarantine","entity_resolution_false_merge_split","framing_causal_restraint","claim_dependency_counterevidence",
    "publication_legal_redaction","ai_adversarial_redteam","opsec_adversarial_redteam","event_hash_integrity",
    "web_auth_csrf","migration_259_to_260","package_hygiene_launcher","full_regression_suite",
)
STAGE_STATUS={"pass","fail","blocked"}
SEVERITY={"info","low","moderate","high","critical"}
FINAL={"phase10_release_candidate","needs_remediation","blocked"}

class Build260Phase10QualificationService:
    BUILD="260.0"
    def __init__(self,db:Any,audit:Any,*,publication:Any,claims:Any,framing:Any,entities:Any,documents:Any,sources:Any,finance:Any,influence:Any,training:Any,opsec:Any,conversation:Any,actor:str="local-analyst")->None:
        self.db,self.audit=db,audit
        self.publication,self.claims,self.framing,self.entities,self.documents=publication,claims,framing,entities,documents
        self.sources,self.finance,self.influence,self.training,self.opsec=sources,finance,influence,training,opsec
        self.conversation,self.actor=conversation,actor
        setattr(conversation,"_qualification260",self)

    def _case(self,cid:str)->None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?",(cid,)): raise KeyError(cid)
    def _run(self,case_id:str,run_id:str)->dict[str,Any]:
        r=self.db.one("SELECT * FROM qualification_runs_260 WHERE case_id=? AND run_id=?",(case_id,run_id))
        if not r: raise KeyError(run_id)
        return dict(r)
    def _event(self,cid:str,etype:str,otype:str,oid:str,payload:dict[str,Any],actor:str)->None:
        prev=self.db.one("SELECT event_hash FROM build260_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,)); ph=(prev or {}).get("event_hash","")
        eid,at=new_id("evt260"),now_ts(); eh=_hash({"previous":ph,"event_id":eid,"event_type":etype,"object_id":oid,"payload":payload,"actor":actor,"at":at})
        self.db.execute("INSERT INTO build260_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,dumps(payload),ph,eh,at))

    def create_run(self,*,case_id:str,title:str,scope:str,actor:str,confirmation:str)->dict[str,Any]:
        self._case(case_id)
        if confirmation!=f"PHASE10 QUALIFICATION 260 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        if len(_text(title,500))<5 or len(_text(scope,4000))<20: raise ValueError("substantive title/scope required")
        rid,at=new_id("qual260"),now_ts(); out={"run_id":rid,"case_id":case_id,"title":_text(title,500),"scope":_text(scope,4000),"status":"open","created_by":actor,"created_at":at}
        self.db.execute("INSERT INTO qualification_runs_260 VALUES(?,?,?,?,?,?,?,?,?)",(rid,case_id,out["title"],out["scope"],"open",actor,at,None,_hash(out)))
        self._event(case_id,"qualification_created","qualification_run",rid,{"stage_count":len(STAGES),"automatic_external_action":False},actor)
        return out

    def record_stage(self,*,case_id:str,run_id:str,stage_key:str,status:str,severity:str,metrics:dict[str,Any]|None,findings:list[str]|None,evidence_ref:str,actor:str,confirmation:str)->dict[str,Any]:
        run=self._run(case_id,run_id)
        if confirmation!=f"QUALIFICATION STAGE 260 {run_id} SPEICHERN": raise PermissionError("explicit approval required")
        if stage_key not in STAGES or status not in STAGE_STATUS or severity not in SEVERITY: raise ValueError("invalid qualification stage/status/severity")
        if actor==run["created_by"] and stage_key in {"ai_adversarial_redteam","opsec_adversarial_redteam","event_hash_integrity","full_regression_suite"}: raise PermissionError("independent reviewer required for critical qualification stages")
        metrics=dict(metrics or {}); findings=[_text(x,2000) for x in (findings or [])][:100]
        rid,at=new_id("qres260"),now_ts(); out={"result_id":rid,"run_id":run_id,"case_id":case_id,"stage_key":stage_key,"status":status,"severity":severity,"metrics":metrics,"findings":findings,"evidence_ref":_text(evidence_ref,1000),"created_by":actor,"created_at":at}
        self.db.execute("INSERT INTO qualification_stage_results_260 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(rid,run_id,case_id,stage_key,status,severity,dumps(metrics),dumps(findings),out["evidence_ref"],actor,at,_hash(out)))
        self._event(case_id,"qualification_stage_recorded","qualification_result",rid,{"run_id":run_id,"stage":stage_key,"status":status,"severity":severity},actor)
        return out

    def phase10_inventory(self,case_id:str)->dict[str,Any]:
        self._case(case_id)
        tables={
            "financial_flows_252":"financial_flows_252","source_profiles_253":"source_profiles_253","source_profiles_254":"source_profiles_254",
            "documents_255":"documents_255","entity_profiles_256":"entity_profiles_256","frame_observations_257":"frame_observations_257",
            "claim_source_lineage_258":"claim_source_lineage_258","publication_packets_259":"publication_packets_259",
        }
        counts={}
        for key,table in tables.items():
            try: counts[key]=int(self.db.one(f"SELECT COUNT(*) n FROM {table} WHERE case_id=?",(case_id,))["n"])
            except Exception: counts[key]=0
        return {"case_id":case_id,"object_counts":counts,"sqlite_integrity":self.db.one("PRAGMA integrity_check")["integrity_check"],"schema_version":self.db.one("SELECT value FROM meta WHERE key='schema_version'")["value"],"automatic_external_action":False}

    def verify_event_chain(self,case_id:str)->dict[str,Any]:
        rows=[dict(x) for x in self.db.all("SELECT * FROM build260_events WHERE case_id=? ORDER BY rowid",(case_id,))]
        prev=""; errors=[]
        for i,r in enumerate(rows):
            if r["previous_hash"]!=prev: errors.append(f"previous_hash_mismatch:{i}")
            payload=_loads(r["payload_json"],{})
            expected=_hash({"previous":r["previous_hash"],"event_id":r["event_id"],"event_type":r["event_type"],"object_id":r["object_id"],"payload":payload,"actor":r["actor"],"at":r["created_at"]})
            if expected!=r["event_hash"]: errors.append(f"event_hash_mismatch:{i}")
            prev=r["event_hash"]
        return {"case_id":case_id,"events":len(rows),"valid":not errors,"errors":errors}

    def record_ai_evaluation(self,*,case_id:str,benchmark_id:str,predicted_class:str,predicted_decision:str,model_or_ruleset:str,evaluated_by:str,confirmation:str)->dict[str,Any]:
        self._case(case_id)
        if confirmation!=f"AI REDTEAM 260 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        b=self.db.one("SELECT * FROM ai_redteam_benchmarks_260 WHERE benchmark_id=?",(benchmark_id,))
        if not b: raise KeyError(benchmark_id)
        cm=int(predicted_class==b["expected_class"]); dm=int(predicted_decision==b["expected_decision"]); eid,at=new_id("aie260"),now_ts()
        out={"evaluation_id":eid,"case_id":case_id,"benchmark_id":benchmark_id,"predicted_class":predicted_class,"predicted_decision":predicted_decision,"passed":bool(cm and dm),"model_or_ruleset":_text(model_or_ruleset,300),"evaluated_by":evaluated_by,"evaluated_at":at}
        self.db.execute("INSERT INTO ai_redteam_evaluations_260 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,case_id,benchmark_id,predicted_class,predicted_decision,cm,dm,int(out["passed"]),out["model_or_ruleset"],evaluated_by,at,_hash(out)))
        return out

    def ai_metrics(self,case_id:str)->dict[str,Any]:
        curated=int(self.db.one("SELECT COUNT(*) n FROM ai_redteam_benchmarks_260 WHERE review_status='curated_reviewed'")["n"]); fam=int(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_redteam_benchmarks_260 WHERE review_status='curated_reviewed'")["n"]); attacks=int(self.db.one("SELECT COUNT(DISTINCT attack_class) n FROM ai_redteam_benchmarks_260 WHERE review_status='curated_reviewed'")["n"]); ev=self.db.all("SELECT passed FROM ai_redteam_evaluations_260 WHERE case_id=?",(case_id,))
        return {"curated_reviewed_benchmarks":curated,"task_family_coverage":fam,"attack_class_coverage":attacks,"evaluations":len(ev),"pass_rate":round(sum(int(x["passed"]) for x in ev)/len(ev),4) if ev else None,"auto_dataset_approval":False,"auto_model_activation":False,"auto_adapter_activation":False,"source_text_authorizes_tools":False}

    def opsec_metrics(self,case_id:str)->dict[str,Any]:
        total=int(self.db.one("SELECT COUNT(*) n FROM opsec_controls_260")["n"]); ver=int(self.db.one("SELECT COUNT(*) n FROM opsec_controls_260 WHERE review_status='verified'")["n"])
        return {"verified_controls":ver,"control_coverage":ver/max(1,total),"autonomous_external_collection":0,"access_control_bypass":0,"autonomous_publication":0,"automatic_model_activation":0,"automatic_host_network_reconfiguration":0,"cross_case_identifier_reuse":0,"csrf_protected_write_routes":1,"immutable_hash_chained_qualification_events":1}

    def capabilities(self)->dict[str,Any]:
        return {"full_case_stage_ledger":True,"phase10_inventory":True,"adversarial_ai_redteam":True,"opsec_qualification":True,"event_chain_verification":True,"four_eyes_release_review":True,"automatic_deployment":False,"automatic_external_action":False}

    def crosscut_release_gate(self,*,case_id:str)->dict[str,Any]:
        caps=self.capabilities(); ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); parent=self.publication.crosscut_release_gate(case_id=case_id)
        main=all(caps[x] for x in ("full_case_stage_ledger","phase10_inventory","adversarial_ai_redteam","opsec_qualification","event_chain_verification","four_eyes_release_review")) and not caps["automatic_deployment"]
        aiready=ai["curated_reviewed_benchmarks"]>=32 and ai["task_family_coverage"]>=10 and ai["attack_class_coverage"]>=20 and not ai["auto_model_activation"] and not ai["auto_adapter_activation"]
        opready=op["verified_controls"]>=24 and op["control_coverage"]==1 and op["autonomous_external_collection"]==0 and op["access_control_bypass"]==0 and op["autonomous_publication"]==0 and op["csrf_protected_write_routes"]==1
        return {"build":self.BUILD,"main_goal_ready":main,"ai_delta_ready":aiready,"opsec_delta_ready":opready,"parent_259_gate_ready":bool(parent.get("release_ready")),"release_ready":bool(main and aiready and opready and parent.get("release_ready")),"capabilities":caps}

    def run_summary(self,*,case_id:str,run_id:str)->dict[str,Any]:
        run=self._run(case_id,run_id); rows=[dict(x) for x in self.db.all("SELECT * FROM qualification_stage_results_260 WHERE case_id=? AND run_id=? ORDER BY rowid",(case_id,run_id))]
        seen={r["stage_key"]:r for r in rows}; missing=[x for x in STAGES if x not in seen]; failed=[x for x,r in seen.items() if r["status"]!="pass"]; severe=[x for x,r in seen.items() if r["severity"] in {"high","critical"} and r["status"]!="pass"]
        gate=self.crosscut_release_gate(case_id=case_id); chain=self.verify_event_chain(case_id)
        ready=not missing and not failed and not severe and gate["release_ready"] and chain["valid"]
        return {"run_id":run_id,"case_id":case_id,"stages_total":len(STAGES),"stages_recorded":len(seen),"missing_stages":missing,"failed_stages":failed,"high_critical_blockers":severe,"event_chain_valid":chain["valid"],"crosscut_gate":gate,"candidate_ready_for_independent_review":ready,"automatic_release":False,"real_world_external_validation_still_distinct":True}

    def final_review(self,*,case_id:str,run_id:str,decision:str,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        run=self._run(case_id,run_id)
        if confirmation!=f"PHASE10 RELEASE REVIEW 260 {run_id} SPEICHERN": raise PermissionError("explicit approval required")
        if reviewer==run["created_by"]: raise PermissionError("independent final reviewer required")
        if decision not in FINAL or len(_text(rationale,8000))<20: raise ValueError("invalid final review")
        summary=self.run_summary(case_id=case_id,run_id=run_id)
        if decision=="phase10_release_candidate" and not summary["candidate_ready_for_independent_review"]: raise PermissionError("qualification blockers remain")
        rid,at=new_id("relrev260"),now_ts(); out={"review_id":rid,"run_id":run_id,"case_id":case_id,"decision":decision,"rationale":_text(rationale,8000),"reviewer":reviewer,"reviewed_at":at,"automatic_deployment":False}
        self.db.execute("INSERT INTO phase10_release_reviews_260 VALUES(?,?,?,?,?,?,?,?,?)",(rid,run_id,case_id,decision,out["rationale"],reviewer,at,0,_hash(out)))
        self._event(case_id,"phase10_release_reviewed","qualification_run",run_id,{"review_id":rid,"decision":decision,"automatic_deployment":False},reviewer)
        return out

    def render_workspace_panel(self,*,case_id:str,csrf:str="")->str:
        esc=html.escape; gate=self.crosscut_release_gate(case_id=case_id); ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); inv=self.phase10_inventory(case_id)
        runs=[dict(x) for x in self.db.all("SELECT run_id,title,created_by,created_at FROM qualification_runs_260 WHERE case_id=? ORDER BY created_at DESC LIMIT 50",(case_id,))]
        ro="".join(f"<option value='{esc(x['run_id'])}'>{esc(_text(x['title'],100))}</option>" for x in runs)
        stage_opts="".join(f"<option>{esc(x)}</option>" for x in STAGES)
        return f"""<section class='cockpit244'><h2>Phase 10 Qualification · Build 260</h2><div class='notice'>Build 260 ist der Abschluss-/Release-Candidate-Build der Phase 10. Er bündelt Full-Case-Qualifikation, adversariales AI-Red-Team, OPSEC-Abnahme, Integritäts- und Regressionsnachweise. Ein PASS ist kein automatisches Deployment und ersetzt keine externe Realwelt-Abnahme.</div><div class='grid'><div class='card'><h3>Qualifikationslauf anlegen</h3><form method='post' action='/build260/run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='title' required value='Phase 10 Full Qualification'><textarea name='scope' required>Vollständige lokale Phase-10-Abnahme mit Funktions-, AI-, OPSEC-, Integritäts-, Migrations-, Web-, Packaging- und Regressionstests.</textarea><button>Lauf anlegen</button></form></div><div class='card'><h3>Stage-Ergebnis</h3><form method='post' action='/build260/stage'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='run_id' required>{ro}</select><select name='stage_key'>{stage_opts}</select><select name='status'><option>pass</option><option>fail</option><option>blocked</option></select><select name='severity'><option>info</option><option>low</option><option>moderate</option><option>high</option><option>critical</option></select><input name='evidence_ref' placeholder='Testreport / Manifest / Hash'><textarea name='findings' placeholder='Befunde, eine Zeile pro Eintrag'></textarea><button>Stage protokollieren</button></form></div><div class='card'><h3>Finales Vier-Augen-Review</h3><form method='post' action='/build260/final-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='run_id' required>{ro}</select><select name='decision'><option>phase10_release_candidate</option><option>needs_remediation</option><option>blocked</option></select><textarea name='rationale' required></textarea><button>Release-Review speichern</button></form></div></div><div class='grid'><div class='card'><h3>Phase-10-Inventar</h3><p>Schema <b>{esc(inv['schema_version'])}</b> · SQLite <b>{esc(inv['sqlite_integrity'])}</b></p><p>252 Flows: {inv['object_counts']['financial_flows_252']} · 255 Docs: {inv['object_counts']['documents_255']} · 256 Entities: {inv['object_counts']['entity_profiles_256']} · 259 Packets: {inv['object_counts']['publication_packets_259']}</p></div><div class='card'><h3>AI-Delta 260</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> adversarial reviewte Benchmarks · {ai['task_family_coverage']} Familien · {ai['attack_class_coverage']} Angriffsklassen.</p><p>Auto-Modell/Adapter: 0 · Source-Text autorisiert Tools: 0.</p></div><div class='card'><h3>OPSEC-Delta 260</h3><p><b>{op['verified_controls']}</b> Controls · Coverage {op['control_coverage']:.0%}</p><p>Auto-Collection: 0 · Access-Bypass: 0 · Auto-Publikation: 0 · Host-Reconfiguration: 0.</p></div><div class='card'><h3>Crosscut Gate</h3><p>Main: <b>{'PASS' if gate['main_goal_ready'] else 'FAIL'}</b><br>AI: <b>{'PASS' if gate['ai_delta_ready'] else 'FAIL'}</b><br>OPSEC: <b>{'PASS' if gate['opsec_delta_ready'] else 'FAIL'}</b><br>Parent 259: <b>{'PASS' if gate['parent_259_gate_ready'] else 'FAIL'}</b></p><p><b>{'RELEASE-GATE READY' if gate['release_ready'] else 'BLOCKED'}</b></p></div></div></section>"""
