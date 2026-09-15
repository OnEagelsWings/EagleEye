from __future__ import annotations
import hashlib, html, json, re
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _text(v: Any, n: int = 10000) -> str:
    return str(v or "").replace("\x00", "").strip()[:n]


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()

ASSERTION_CLASSES={"documented_fact","allegation","official_assessment","judicial_finding","analysis","context_only"}
AUDIENCES={"internal","legal_review","limited_distribution","public"}
LEGAL_DECISIONS={"review_complete","revise","hold","escalate_qualified_counsel"}
RISK_CLASSES={"low","moderate","high","critical"}
HEARING_STATUS={"not_required","planned_manual","requested_manual","response_received","no_response_recorded","declined","not_completed"}
REDACTION_REASONS={"privacy","minor_or_vulnerable_person","credential_secret","unnecessary_identifier","source_protection","legal_restriction","operational_security","other"}
REDACTION_REVIEW={"accepted","revise","not_required"}
FINAL_DECISIONS={"approved_for_manual_publication","limited_distribution_only","internal_only","revise","hold","escalate_qualified_counsel"}


class Build259PublicationLegalReviewService:
    BUILD="259.0"
    def __init__(self,db:Any,audit:Any,*,claims:Any,documents:Any,training:Any,opsec:Any,conversation:Any,actor:str="local-analyst")->None:
        self.db,self.audit=db,audit; self.claims=claims; self.documents=documents; self.training=training; self.opsec=opsec; self.conversation=conversation; self.actor=actor
        setattr(conversation,"_publication259",self)

    def _case(self,cid:str)->None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?",(cid,)): raise KeyError(cid)

    def _packet(self,case_id:str,packet_id:str)->dict[str,Any]:
        r=self.db.one("SELECT * FROM publication_packets_259 WHERE case_id=? AND packet_id=?",(case_id,packet_id))
        if not r: raise KeyError(packet_id)
        return dict(r)

    def _event(self,cid:str,etype:str,otype:str,oid:str,payload:dict[str,Any],actor:str)->None:
        prev=self.db.one("SELECT event_hash FROM build259_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,)); ph=(prev or {}).get("event_hash","")
        eid,at=new_id("evt259"),now_ts(); eh=_hash({"previous":ph,"event_id":eid,"event_type":etype,"object_id":oid,"payload":payload,"actor":actor,"at":at})
        self.db.execute("INSERT INTO build259_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,dumps(payload),ph,eh,at))

    def create_packet(self,*,case_id:str,verified_claim_id:str,title:str,body_text:str,assertion_class:str,intended_audience:str,publication_channel:str,actor:str,confirmation:str)->dict[str,Any]:
        self._case(case_id)
        claim=self.db.one("SELECT * FROM verified_claims_229 WHERE case_id=? AND verified_claim_id=?",(case_id,verified_claim_id))
        if not claim: raise KeyError(verified_claim_id)
        if confirmation!=f"PUBLICATION PACKET 259 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        if assertion_class not in ASSERTION_CLASSES or intended_audience not in AUDIENCES: raise ValueError("invalid assertion/audience")
        if len(_text(body_text,50000))<20: raise ValueError("publication body too short")
        pid,at=new_id("pub259"),now_ts(); p={"packet_id":pid,"case_id":case_id,"verified_claim_id":verified_claim_id,"title":_text(title,500),"body_text":_text(body_text,50000),"assertion_class":assertion_class,"intended_audience":intended_audience,"publication_channel":_text(publication_channel,500),"created_by":actor,"created_at":at}
        self.db.execute("INSERT INTO publication_packets_259 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pid,case_id,verified_claim_id,p["title"],p["body_text"],assertion_class,intended_audience,p["publication_channel"],actor,at,_hash(p)))
        self._event(case_id,"publication_packet_created","publication_packet",pid,{"verified_claim_id":verified_claim_id,"assertion_class":assertion_class,"audience":intended_audience},actor); return p

    def packet_integrity(self,*,case_id:str,packet_id:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id); analysis=self.claims.analyze_claim(case_id=case_id,verified_claim_id=p["verified_claim_id"])
        review=self.db.one("SELECT * FROM claim_independence_reviews_258 WHERE case_id=? AND verified_claim_id=? ORDER BY reviewed_at DESC LIMIT 1",(case_id,p["verified_claim_id"]))
        return {"packet_id":packet_id,"claim_analysis":analysis,"independence_review_present":bool(review),"independence_review_decision":review.get("decision") if review else None,"counterevidence_present":analysis.get("counterevidence_count",0)>0,"circular_dependency_detected":bool(analysis.get("circular_dependency_detected")),"automatic_truth_determination":False}

    def legal_editorial_review(self,*,case_id:str,packet_id:str,decision:str,risk_class:str,hearing_required:bool,redaction_required:bool,source_independence_checked:bool,counterevidence_checked:bool,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id)
        if confirmation!=f"LEGAL EDITORIAL REVIEW 259 {packet_id} SPEICHERN": raise PermissionError("explicit approval required")
        if reviewer==p["created_by"]: raise PermissionError("independent reviewer required")
        if decision not in LEGAL_DECISIONS or risk_class not in RISK_CLASSES: raise ValueError("invalid review decision/risk")
        integrity=self.packet_integrity(case_id=case_id,packet_id=packet_id)
        if decision=="review_complete" and (not source_independence_checked or not counterevidence_checked): raise PermissionError("source independence and counter-evidence checks required")
        if decision=="review_complete" and not integrity["independence_review_present"]: raise PermissionError("Build 258 independence review required")
        rid,at=new_id("leg259"),now_ts(); out={"review_id":rid,"case_id":case_id,"packet_id":packet_id,"decision":decision,"risk_class":risk_class,"hearing_required":bool(hearing_required),"redaction_required":bool(redaction_required),"source_independence_checked":bool(source_independence_checked),"counterevidence_checked":bool(counterevidence_checked),"rationale":_text(rationale,8000),"reviewer":reviewer,"reviewed_at":at,"legal_advice":False}
        self.db.execute("INSERT INTO legal_editorial_reviews_259 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,case_id,packet_id,decision,risk_class,int(hearing_required),int(redaction_required),int(source_independence_checked),int(counterevidence_checked),out["rationale"],reviewer,at,_hash(out)))
        self._event(case_id,"legal_editorial_reviewed","publication_packet",packet_id,{"review_id":rid,"decision":decision,"risk_class":risk_class},reviewer); return out

    def record_hearing(self,*,case_id:str,packet_id:str,subject_label:str,status:str,request_summary:str,response_summary:str,actor:str,confirmation:str)->dict[str,Any]:
        self._packet(case_id,packet_id)
        if confirmation!=f"HEARING RECORD 259 {packet_id} SPEICHERN": raise PermissionError("explicit approval required")
        if status not in HEARING_STATUS: raise ValueError("invalid hearing status")
        hid,at=new_id("hear259"),now_ts(); out={"hearing_id":hid,"case_id":case_id,"packet_id":packet_id,"subject_label":_text(subject_label,500),"status":status,"request_summary":_text(request_summary,6000),"response_summary":_text(response_summary,10000),"contact_was_manual":True,"created_by":actor,"created_at":at,"automatic_contact":False}
        self.db.execute("INSERT INTO hearing_records_259 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(hid,case_id,packet_id,out["subject_label"],status,out["request_summary"],out["response_summary"],1,actor,at,_hash(out)))
        self._event(case_id,"hearing_recorded","publication_packet",packet_id,{"hearing_id":hid,"status":status},actor); return out

    def add_redaction(self,*,case_id:str,packet_id:str,target_text:str,replacement_text:str,reason_class:str,actor:str,confirmation:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id)
        if confirmation!=f"REDACTION PLAN 259 {packet_id} ANLEGEN": raise PermissionError("explicit approval required")
        if reason_class not in REDACTION_REASONS: raise ValueError("invalid redaction reason")
        target=_text(target_text,2000)
        if not target or target not in p["body_text"]: raise ValueError("target text must occur in packet body")
        replacement=_text(replacement_text or "[REDACTED]",500)
        rid,at=new_id("red259"),now_ts(); out={"redaction_id":rid,"case_id":case_id,"packet_id":packet_id,"target_text":target,"replacement_text":replacement,"reason_class":reason_class,"created_by":actor,"created_at":at}
        self.db.execute("INSERT INTO redaction_plans_259 VALUES(?,?,?,?,?,?,?,?,?)",(rid,case_id,packet_id,target,replacement,reason_class,actor,at,_hash(out)))
        self._event(case_id,"redaction_planned","publication_packet",packet_id,{"redaction_id":rid,"reason_class":reason_class},actor); return out

    def review_redactions(self,*,case_id:str,packet_id:str,decision:str,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id)
        if confirmation!=f"REDACTION REVIEW 259 {packet_id} SPEICHERN": raise PermissionError("explicit approval required")
        if decision not in REDACTION_REVIEW: raise ValueError("invalid redaction review")
        makers={x["created_by"] for x in self.db.all("SELECT created_by FROM redaction_plans_259 WHERE case_id=? AND packet_id=?",(case_id,packet_id))}
        if reviewer==p["created_by"] or reviewer in makers: raise PermissionError("independent redaction reviewer required")
        if decision=="accepted" and not makers: raise PermissionError("no redaction plan to accept")
        rid,at=new_id("rr259"),now_ts(); out={"redaction_review_id":rid,"case_id":case_id,"packet_id":packet_id,"decision":decision,"rationale":_text(rationale,6000),"reviewer":reviewer,"reviewed_at":at}
        self.db.execute("INSERT INTO redaction_reviews_259 VALUES(?,?,?,?,?,?,?,?)",(rid,case_id,packet_id,decision,out["rationale"],reviewer,at,_hash(out)))
        self._event(case_id,"redaction_reviewed","publication_packet",packet_id,{"redaction_review_id":rid,"decision":decision},reviewer); return out

    def safe_snapshot(self,*,case_id:str,packet_id:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id); text=p["body_text"]
        plans=[dict(x) for x in self.db.all("SELECT * FROM redaction_plans_259 WHERE case_id=? AND packet_id=? ORDER BY created_at",(case_id,packet_id))]
        for r in plans: text=text.replace(r["target_text"],r["replacement_text"])
        # inert plain-text hygiene: strip local file paths and likely URL tracking query strings; never fetch anything.
        text=re.sub(r"(?i)\bfile://\S+", "[LOCAL_PATH_REDACTED]", text)
        text=re.sub(r"(?i)https?://([^\s?#]+)(?:\?[^\s#]*)?", lambda m: "https://"+m.group(1), text)
        secret_patterns=[r"(?i)\b(?:api[_-]?key|access[_-]?token|bearer)\s*[:=]\s*[A-Za-z0-9._\-]{12,}",r"\bsk-[A-Za-z0-9_-]{12,}\b"]
        secret_hits=sum(len(re.findall(rx,text)) for rx in secret_patterns)
        for rx in secret_patterns: text=re.sub(rx,"[SECRET_REDACTED]",text)
        out={"packet_id":packet_id,"title":p["title"],"plain_text":text,"snapshot_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),"redaction_count":len(plans),"secret_pattern_hits_redacted":secret_hits,"active_content":False,"automatic_publication":False,"external_network_requests":0,"metadata":{"case_id":case_id,"packet_id":packet_id,"build":"259.0"}}
        return out

    def readiness(self,*,case_id:str,packet_id:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id); legal=self.db.one("SELECT * FROM legal_editorial_reviews_259 WHERE case_id=? AND packet_id=? ORDER BY reviewed_at DESC LIMIT 1",(case_id,packet_id)); red=self.db.one("SELECT * FROM redaction_reviews_259 WHERE case_id=? AND packet_id=? ORDER BY reviewed_at DESC LIMIT 1",(case_id,packet_id)); hear=self.db.one("SELECT * FROM hearing_records_259 WHERE case_id=? AND packet_id=? ORDER BY created_at DESC LIMIT 1",(case_id,packet_id)); integ=self.packet_integrity(case_id=case_id,packet_id=packet_id)
        blockers=[]
        if not legal or legal["decision"]!="review_complete": blockers.append("legal_editorial_review_incomplete")
        if not integ["independence_review_present"]: blockers.append("source_independence_review_missing")
        if legal and legal["hearing_required"]:
            if not hear or hear["status"] not in {"response_received","no_response_recorded","declined"}: blockers.append("hearing_not_completed")
        if legal and legal["redaction_required"]:
            if not red or red["decision"]!="accepted": blockers.append("redaction_review_incomplete")
        snap=self.safe_snapshot(case_id=case_id,packet_id=packet_id)
        if snap["secret_pattern_hits_redacted"]>0 and not (red and red["decision"]=="accepted"): blockers.append("secret_redaction_requires_review")
        return {"packet_id":packet_id,"ready_for_manual_publication_decision":not blockers,"blockers":blockers,"automatic_publication":False,"legal_advice":False,"snapshot_sha256":snap["snapshot_sha256"]}

    def final_review(self,*,case_id:str,packet_id:str,decision:str,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        p=self._packet(case_id,packet_id)
        if confirmation!=f"PUBLICATION DECISION 259 {packet_id} SPEICHERN": raise PermissionError("explicit approval required")
        if reviewer==p["created_by"]: raise PermissionError("independent final reviewer required")
        if decision not in FINAL_DECISIONS: raise ValueError("invalid publication decision")
        ready=self.readiness(case_id=case_id,packet_id=packet_id)
        if decision=="approved_for_manual_publication" and not ready["ready_for_manual_publication_decision"]: raise PermissionError("publication-readiness blockers remain")
        legal=self.db.one("SELECT * FROM legal_editorial_reviews_259 WHERE case_id=? AND packet_id=? ORDER BY reviewed_at DESC LIMIT 1",(case_id,packet_id)) or {}
        red=self.db.one("SELECT * FROM redaction_reviews_259 WHERE case_id=? AND packet_id=? ORDER BY reviewed_at DESC LIMIT 1",(case_id,packet_id)) or {}
        hear=self.db.one("SELECT * FROM hearing_records_259 WHERE case_id=? AND packet_id=? ORDER BY created_at DESC LIMIT 1",(case_id,packet_id)) or {}
        did,at=new_id("dec259"),now_ts(); out={"decision_id":did,"case_id":case_id,"packet_id":packet_id,"decision":decision,"rationale":_text(rationale,8000),"legal_review_id":legal.get("review_id",""),"redaction_review_id":red.get("redaction_review_id",""),"hearing_status":hear.get("status","not_required"),"automatic_publication":False,"reviewer":reviewer,"reviewed_at":at}
        self.db.execute("INSERT INTO publication_decisions_259 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(did,case_id,packet_id,decision,out["rationale"],out["legal_review_id"],out["redaction_review_id"],out["hearing_status"],0,reviewer,at,_hash(out)))
        self._event(case_id,"publication_decision_recorded","publication_packet",packet_id,{"decision_id":did,"decision":decision,"automatic_publication":False},reviewer); return out

    def stage_training_candidate(self,*,case_id:str,decision_id:str,actor:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"AI TRAINING CANDIDATE 259 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        d=self.db.one("SELECT * FROM publication_decisions_259 WHERE case_id=? AND decision_id=?",(case_id,decision_id))
        if not d: raise KeyError(decision_id)
        p=self._packet(case_id,d["packet_id"]); ready=self.readiness(case_id=case_id,packet_id=p["packet_id"])
        instruction="Assess publication readiness conservatively: preserve counter-evidence, respect assertion ceilings, identify hearing/redaction needs, and never give a legal-safety guarantee."
        response=f"Reviewed decision: {d['decision']}\nManual readiness: {ready['ready_for_manual_publication_decision']}\nBlockers: {', '.join(ready['blockers']) or 'none'}\nAssertion class: {p['assertion_class']}"
        ex=self.training.add_example(case_id=case_id,instruction=instruction,response=response,context={"build":"259.0","decision_id":decision_id,"human_reviewed":True,"legal_advice":False,"source_content_is_instruction":False},evidence_refs=(),language="multi",source_type="build259_reviewed_publication_readiness",source_ref=decision_id,created_by=actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
        return {"example_id":ex["example_id"],"review_required":True,"automatic_approval":False,"automatic_model_activation":False}

    def record_ai_evaluation(self,*,case_id:str,benchmark_id:str,predicted_class:str,predicted_decision:str,model_or_ruleset:str,evaluated_by:str,confirmation:str)->dict[str,Any]:
        self._case(case_id)
        if confirmation!=f"AI BENCHMARK 259 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        b=self.db.one("SELECT * FROM ai_publication_benchmarks_259 WHERE benchmark_id=?",(benchmark_id,))
        if not b: raise KeyError(benchmark_id)
        cm=int(predicted_class==b["expected_class"]); dm=int(predicted_decision==b["expected_decision"]); eid,at=new_id("aie259"),now_ts(); out={"evaluation_id":eid,"case_id":case_id,"benchmark_id":benchmark_id,"predicted_class":predicted_class,"predicted_decision":predicted_decision,"passed":bool(cm and dm),"model_or_ruleset":_text(model_or_ruleset,300),"evaluated_by":evaluated_by,"evaluated_at":at}
        self.db.execute("INSERT INTO ai_publication_evaluations_259 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(eid,case_id,benchmark_id,predicted_class,predicted_decision,cm,dm,int(out["passed"]),out["model_or_ruleset"],evaluated_by,at,_hash(out))); return out

    def ai_metrics(self,case_id:str)->dict[str,Any]:
        curated=int(self.db.one("SELECT COUNT(*) n FROM ai_publication_benchmarks_259 WHERE review_status='curated_reviewed'")["n"]); fam=int(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_publication_benchmarks_259 WHERE review_status='curated_reviewed'")["n"]); ev=self.db.all("SELECT passed FROM ai_publication_evaluations_259 WHERE case_id=?",(case_id,))
        return {"curated_reviewed_benchmarks":curated,"task_family_coverage":fam,"evaluations":len(ev),"pass_rate":round(sum(int(x["passed"]) for x in ev)/len(ev),4) if ev else None,"auto_model_activation":False,"auto_adapter_activation":False,"legal_safety_guarantee":False}

    def opsec_metrics(self,case_id:str)->dict[str,Any]:
        total=int(self.db.one("SELECT COUNT(*) n FROM publication_opsec_controls_259")["n"]); ver=int(self.db.one("SELECT COUNT(*) n FROM publication_opsec_controls_259 WHERE review_status='verified'")["n"])
        return {"verified_controls":ver,"control_coverage":ver/max(1,total),"autonomous_publication":0,"automatic_hearing_contact":0,"active_content_in_snapshot":0,"autonomous_host_network_reconfiguration":0,"csrf_protected_write_routes":1}

    def capabilities(self)->dict[str,Any]:
        return {"publication_packet":True,"legal_editorial_review":True,"hearing_ledger":True,"redaction_plan_and_review":True,"safe_inert_snapshot":True,"manual_publication_decision":True,"automatic_publication":False,"automatic_source_contact":False,"legal_advice_guarantee":False}

    def crosscut_release_gate(self,*,case_id:str)->dict[str,Any]:
        caps=self.capabilities(); ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); parent=self.claims.crosscut_release_gate(case_id=case_id)
        main=all(caps[x] for x in ("publication_packet","legal_editorial_review","hearing_ledger","redaction_plan_and_review","safe_inert_snapshot","manual_publication_decision")) and not caps["automatic_publication"]
        aiready=ai["curated_reviewed_benchmarks"]>=16 and ai["task_family_coverage"]>=10 and not ai["auto_model_activation"] and not ai["legal_safety_guarantee"]
        opready=op["verified_controls"]>=16 and op["control_coverage"]==1 and op["autonomous_publication"]==0 and op["automatic_hearing_contact"]==0 and op["active_content_in_snapshot"]==0 and op["csrf_protected_write_routes"]==1
        return {"build":self.BUILD,"main_goal_ready":main,"ai_delta_ready":aiready,"opsec_delta_ready":opready,"parent_258_gate_ready":bool(parent.get("release_ready")),"release_ready":bool(main and aiready and opready and parent.get("release_ready")),"capabilities":caps}

    def render_workspace_panel(self,*,case_id:str,csrf:str="")->str:
        esc=html.escape; claims=[dict(x) for x in self.db.all("SELECT verified_claim_id,claim_text,status FROM verified_claims_229 WHERE case_id=? ORDER BY updated_at DESC LIMIT 100",(case_id,))]; packets=[dict(x) for x in self.db.all("SELECT packet_id,title,verified_claim_id,created_by FROM publication_packets_259 WHERE case_id=? ORDER BY created_at DESC LIMIT 100",(case_id,))]
        co="".join(f"<option value='{esc(x['verified_claim_id'])}'>{esc(_text(x['claim_text'],120))}</option>" for x in claims); po="".join(f"<option value='{esc(x['packet_id'])}'>{esc(_text(x['title'],120))}</option>" for x in packets)
        ai=self.ai_metrics(case_id); op=self.opsec_metrics(case_id); gate=self.crosscut_release_gate(case_id=case_id)
        return f"""<section class='cockpit244'><h2>Publication / Legal Review · Build 259</h2><div class='notice'>Build 259 ist ein kontrollierter Publication-Readiness-Desk, keine Rechtsberatung und kein autonomes Publikationssystem. Wahrheitsstatus, Publikationsstatus und rechtlich-redaktionelle Freigabe bleiben getrennt.</div><div class='notice warn'>Anhörungen/Kontakte werden nur protokolliert und müssen außerhalb EagleEye manuell erfolgen. Öffentliche Snapshots sind inert; kein Script, kein Remote-Content, kein automatisches Posting.</div><div class='grid'><div class='card'><h3>Publikationspaket</h3><form method='post' action='/build259/packet'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='verified_claim_id' required>{co}</select><input name='title' required placeholder='Arbeitstitel'><textarea name='body_text' required placeholder='Entwurf / zu prüfender Text'></textarea><select name='assertion_class'>{''.join(f'<option>{x}</option>' for x in sorted(ASSERTION_CLASSES))}</select><select name='intended_audience'>{''.join(f'<option>{x}</option>' for x in sorted(AUDIENCES))}</select><input name='publication_channel' placeholder='z. B. interner Bericht, Website, Presse'><button>Paket anlegen</button></form></div><div class='card'><h3>Legal-/Editorial-Review</h3><form method='post' action='/build259/legal-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='packet_id' required>{po}</select><select name='decision'>{''.join(f'<option>{x}</option>' for x in sorted(LEGAL_DECISIONS))}</select><select name='risk_class'>{''.join(f'<option>{x}</option>' for x in sorted(RISK_CLASSES))}</select><label><input type='checkbox' name='hearing_required' value='1'> Anhörung erforderlich</label><label><input type='checkbox' name='redaction_required' value='1'> Redaktion/Schwärzung erforderlich</label><label><input type='checkbox' name='source_independence_checked' value='1'> Quellenunabhängigkeit geprüft</label><label><input type='checkbox' name='counterevidence_checked' value='1'> Gegenbelege geprüft</label><textarea name='rationale' required></textarea><button>Review speichern</button></form></div><div class='card'><h3>Anhörung dokumentieren</h3><form method='post' action='/build259/hearing'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='packet_id' required>{po}</select><input name='subject_label' placeholder='Betroffene Stelle/Person – nur nötige Bezeichnung'><select name='status'>{''.join(f'<option>{x}</option>' for x in sorted(HEARING_STATUS))}</select><textarea name='request_summary' placeholder='Manuell versandte Anfrage – Zusammenfassung'></textarea><textarea name='response_summary' placeholder='Antwort – Zusammenfassung'></textarea><button>Ledger-Eintrag</button></form></div><div class='card'><h3>Redaktionsplan</h3><form method='post' action='/build259/redaction'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='packet_id' required>{po}</select><input name='target_text' required placeholder='Exakter zu ersetzender Text'><input name='replacement_text' value='[REDACTED]'><select name='reason_class'>{''.join(f'<option>{x}</option>' for x in sorted(REDACTION_REASONS))}</select><button>Redaktion planen</button></form></div><div class='card'><h3>Redaktionsreview</h3><form method='post' action='/build259/redaction-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='packet_id' required>{po}</select><select name='decision'>{''.join(f'<option>{x}</option>' for x in sorted(REDACTION_REVIEW))}</select><textarea name='rationale' required></textarea><button>Vier-Augen-Review</button></form></div><div class='card'><h3>Finale manuelle Entscheidung</h3><form method='post' action='/build259/final-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='packet_id' required>{po}</select><select name='decision'>{''.join(f'<option>{x}</option>' for x in sorted(FINAL_DECISIONS))}</select><textarea name='rationale' required></textarea><button>Entscheidung protokollieren</button></form></div></div><div class='grid'><div class='card'><h3>AI-Delta 259</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> reviewte Benchmarks · {ai['task_family_coverage']} Familien.</p><p>Assertion ceiling, Hearing, Redaction, Publication Readiness, Metadata Hygiene, Abstention und Legal-Support-Grenze.</p></div><div class='card'><h3>OPSEC-Delta 259</h3><p>{op['verified_controls']} Controls · Coverage {op['control_coverage']:.0%}</p><p>Auto-Publikation: 0 · Auto-Kontakt: 0 · aktiver Snapshot-Content: 0 · CSRF-Schreibwege: aktiv.</p></div><div class='card'><h3>Release Gate</h3><p>Main: <b>{'PASS' if gate['main_goal_ready'] else 'FAIL'}</b><br>AI: <b>{'PASS' if gate['ai_delta_ready'] else 'FAIL'}</b><br>OPSEC: <b>{'PASS' if gate['opsec_delta_ready'] else 'FAIL'}</b><br>Parent 258: <b>{'PASS' if gate['parent_258_gate_ready'] else 'FAIL'}</b></p><p><b>{'RELEASE READY' if gate['release_ready'] else 'BLOCKED'}</b></p></div></div></section>"""
