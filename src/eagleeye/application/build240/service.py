from __future__ import annotations
import hashlib, html, json
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any) -> str: return hashlib.sha256((v if isinstance(v,bytes) else _canon(v).encode("utf-8"))).hexdigest()
def _loads(v: str|None, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default
def _clamp(v: Any) -> float:
    try: return max(0.0,min(1.0,float(v)))
    except Exception: return 0.0

def _txt(v: Any,n:int=10000)->str: return str(v or "").replace("\x00","").strip()[:n]

class Build240CoAIInvestigator3CoreService:
    """Whole-case, evidence-first reasoning layer for the persistent Co-AI investigator.

    Build 240 performs no external action. It composes the canonical case state for
    Build 227, evaluates completed answers against evidence/uncertainty discipline,
    and stages only reviewed high-quality turns as pending Build-228 training data.
    """
    BUILD="240.0"
    def __init__(self,db:Any,audit:Any,*,conversation:Any,kernel:Any,verified_loop:Any,multilingual:Any,social:Any,graph:Any,evidence_vault:Any,source_fabric:Any,training:Any,actor:str="local-analyst"):
        self.db,self.audit,self.conversation,self.kernel,self.verified_loop,self.multilingual,self.social,self.graph,self.evidence_vault,self.source_fabric,self.training,self.actor=db,audit,conversation,kernel,verified_loop,multilingual,social,graph,evidence_vault,source_fabric,training,actor
        self.conversation._co_ai_investigator_240=self
        # Build 227 wraps the persistent Build-216 local chat service; attach the same read-only approved-memory hook there.
        try: self.conversation.conversation._co_ai_investigator_240=self
        except Exception: pass

    def case_state(self,*,case_id:str,limit:int=50)->dict[str,Any]:
        self.kernel.cases.get_case(case_id); lim=max(5,min(200,int(limit)))
        canonical=self.kernel.conversation_context(case_id=case_id,limit=lim)
        vault=self.evidence_vault.conversation_context(case_id=case_id,limit=lim*2)
        graph=self.graph.conversation_context(case_id=case_id,limit=lim)
        social=self.social.conversation_context(case_id=case_id,limit=lim)
        multilingual=self.multilingual.conversation_context(case_id=case_id,limit=min(30,lim))
        vd=self.verified_loop.dashboard(case_id=case_id)
        verified=[{"verified_claim_id":x["verified_claim_id"],"claim_text":x["claim_text"],"status":x["status"],"verification_score":x["verification_score"],"supporting_refs":_loads(x.get("supporting_refs_json"),[]),"contradicting_refs":_loads(x.get("contradicting_refs_json"),[])} for x in vd["claims"] if x["status"]=="verified"][:lim]
        challenged=[{"verified_claim_id":x["verified_claim_id"],"claim_text":x["claim_text"],"status":x["status"],"supporting_refs":_loads(x.get("supporting_refs_json"),[]),"contradicting_refs":_loads(x.get("contradicting_refs_json"),[])} for x in vd["claims"] if x["status"] in {"challenged","unresolved","candidate"}][:lim]
        gaps=[{"gap_id":x["gap_id"],"question":x["question"],"priority":x["priority"]} for x in vd["gaps"] if x["status"]=="open"][:lim]
        accepted_vault=list(vault.get("accepted_evidence") or [])
        integrity_ok=[]
        for ev in accepted_vault:
            try:
                check=self.evidence_vault.verify_item(vault_item_id=ev["vault_item_id"],checked_by="coai-240-readonly")
                if check["status"]=="ok": integrity_ok.append(ev)
            except Exception: pass
        tasks=[x for x in canonical.get("tasks",[]) if x.get("state") not in {"resolved","closed","done"}]
        findings=canonical.get("findings",[])
        contradictions=[]
        for x in challenged:
            if x.get("contradicting_refs"): contradictions.append({"type":"verified_claim_conflict","claim_id":x["verified_claim_id"],"claim_text":x["claim_text"],"contradicting_refs":x["contradicting_refs"]})
        for x in vault.get("pending_or_rejected_not_facts",[]):
            if x.get("decision")=="rejected": contradictions.append({"type":"rejected_evidence","vault_item_id":x["vault_item_id"],"reason":"not accepted evidence"})
        state={
            "build":self.BUILD,"case_id":case_id,
            "entities":canonical.get("entities",[])[:lim],"claims":canonical.get("claims",[])[:lim],"findings":findings[:lim],"open_tasks":tasks[:lim],
            "verified_claims":verified,"challenged_or_unresolved_claims_not_facts":challenged,
            "accepted_integrity_checked_evidence":integrity_ok[:lim],"pending_or_rejected_evidence_not_facts":vault.get("pending_or_rejected_not_facts",[])[:lim],
            "accepted_graph_edges":graph.get("accepted_edges",[])[:lim],"candidate_graph_edges_not_facts":graph.get("candidate_edges_not_facts",[])[:lim],
            "reviewed_social_context":social,"reviewed_multilingual_context":multilingual,"open_research_gaps":gaps,"contradictions":contradictions[:lim],
            "rules":[
                "State factual conclusions only when grounded in accepted/reviewed case evidence.",
                "Prefer integrity-checked Build-239 evidence when available and preserve original-vs-derived provenance.",
                "Treat hypotheses, candidate links, identity candidates and challenged claims as non-facts.",
                "Surface contradictions and evidence gaps before recommending another investigative step.",
                "Never infer causality from graph proximity or identity from transliteration/handle similarity alone.",
                "Do not execute sources, contact subjects, change source policy, merge identities or activate a model automatically.",
            ],
            "automatic_external_action":False,"human_review_required":True,
        }
        state["state_sha256"]=_hash(state)
        return state


    def approved_memory_pack(self,*,case_id:str,limit:int=24)->dict[str,Any]:
        """Return only accepted/hash-intact case evidence as citeable local memory.

        No network access occurs. Text blobs are bounded and read from the local
        content-addressed vault; binary items contribute metadata only.
        """
        state=self.case_state(case_id=case_id,limit=max(10,limit))
        items=[]; refs=[]
        for ev in state["accepted_integrity_checked_evidence"][:max(1,min(50,int(limit)))]:
            try:
                item=self.evidence_vault.item(ev["vault_item_id"])
                path=self.evidence_vault.base_dir/item["storage_relpath"]
                raw=path.read_bytes() if path.exists() else b""
                if hashlib.sha256(raw).hexdigest()!=item["content_sha256"]: continue
                text=""
                if item["media_type"].lower().startswith("text/"):
                    text=raw[:16000].decode("utf-8",errors="replace")
                row={"citation_id":item["vault_item_id"],"sha256":item["content_sha256"],"media_type":item["media_type"],"source_key":item["source_key"],"source_url":item["source_url"],"captured_at":item["captured_at"],"text":text,"canonical_evidence_object_id":ev.get("canonical_evidence_object_id","")}
                items.append(row); refs.append(item["vault_item_id"])
            except Exception: continue
        verified=[]
        for claim in state["verified_claims"][:max(1,min(50,int(limit)))]:
            verified.append(claim)
        return {"accepted_case_evidence":items,"verified_claims":verified,"allowed_citation_ids":refs,"rules":["Only these accepted case-evidence citation IDs may be used as factual approved-memory citations.","Candidate, challenged, pending or rejected records are excluded from approved memory."],"automatic_external_action":False}

    def create_snapshot(self,*,case_id:str,actor:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"COAI SNAPSHOT 240 {case_id} ERSTELLEN": raise PermissionError("explicit approval required")
        s=self.case_state(case_id=case_id); sid,now=new_id("coaisnap240"),now_ts()
        p={"snapshot_id":sid,"case_id":case_id,"state_sha256":s["state_sha256"],"entity_count":len(s["entities"]),"claim_count":len(s["claims"]),"accepted_evidence_count":len(s["accepted_integrity_checked_evidence"]),"accepted_edge_count":len(s["accepted_graph_edges"]),"verified_claim_count":len(s["verified_claims"]),"open_gap_count":len(s["open_research_gaps"]),"open_task_count":len(s["open_tasks"]),"contradiction_count":len(s["contradictions"]),"created_by":actor,"created_at":now}
        self.db.execute("INSERT INTO coai_case_snapshots_240 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,case_id,p["state_sha256"],p["entity_count"],p["claim_count"],p["accepted_evidence_count"],p["accepted_edge_count"],p["verified_claim_count"],p["open_gap_count"],p["open_task_count"],p["contradiction_count"],actor,now,_hash(p)))
        self._event(case_id,"case_snapshot_created","case",case_id,{"snapshot_id":sid,"state_sha256":s["state_sha256"]},actor); return {**p,"state":s}

    def prompt_context(self,*,case_id:str,limit:int=50)->dict[str,Any]:
        s=self.case_state(case_id=case_id,limit=limit)
        return {k:s[k] for k in ("build","case_id","entities","claims","findings","open_tasks","verified_claims","challenged_or_unresolved_claims_not_facts","accepted_integrity_checked_evidence","pending_or_rejected_evidence_not_facts","accepted_graph_edges","candidate_graph_edges_not_facts","open_research_gaps","contradictions","rules","state_sha256")}

    def assess_turn(self,*,turn_id:str,actor:str="coai-240")->dict[str,Any]:
        existing=self.db.one("SELECT * FROM coai_turn_assessments_240 WHERE turn_id=?",(turn_id,))
        if existing: return self._assessment(existing)
        turn=self.conversation.turn_status(turn_id=turn_id)
        if turn["status"]!="completed": raise ValueError("only completed turns may be assessed")
        response=turn.get("response") or {}; answer=dict(response.get("answer") or {})
        state=self.case_state(case_id=turn["case_id"])
        sidrow=self.db.one("SELECT snapshot_id FROM coai_case_snapshots_240 WHERE case_id=? AND state_sha256=? ORDER BY created_at DESC LIMIT 1",(turn["case_id"],state["state_sha256"]))
        if sidrow: sid=sidrow["snapshot_id"]
        else:
            # internal immutable snapshot: no external action and no human decision
            sid=self.create_snapshot(case_id=turn["case_id"],actor=actor,confirmation=f"COAI SNAPSHOT 240 {turn['case_id']} ERSTELLEN")["snapshot_id"]
        observations=list(answer.get("observations") or []); grounded=sum(1 for x in observations if (x or {}).get("citations"))
        used=set(str(x) for x in (response.get("citations") or []))
        accepted_ids=set()
        for e in state["accepted_integrity_checked_evidence"]: accepted_ids.update({e.get("vault_item_id",""),e.get("canonical_evidence_object_id","")})
        accepted_used=len([x for x in used if x in accepted_ids])
        candidate_ids=set(x.get("id","") or x.get("link_id","") for x in state["candidate_graph_edges_not_facts"])
        candidate_refs=sum(1 for x in used if x in candidate_ids)
        contradiction_surfaced=1 if (not state["contradictions"] or any(w in _canon(answer).casefold() for w in ("widerspruch","contradict","ungeklärt","unresolved"))) else 0
        grounding=grounded/max(1,len(observations))
        discipline_parts=[1.0 if candidate_refs==0 else 0.0, float(contradiction_surfaced), 1.0 if answer.get("open_questions") is not None else 0.0]
        discipline=sum(discipline_parts)/len(discipline_parts)
        gate="COAI_240_PASS" if grounding>=.95 and discipline>=.95 else "COAI_240_REVIEW"
        assessment={"observation_count":len(observations),"grounded_observation_count":grounded,"accepted_evidence_citation_count":accepted_used,"candidate_reference_count":candidate_refs,"contradiction_surfaced":bool(contradiction_surfaced),"open_questions_count":len(answer.get("open_questions") or []),"recommended_steps_count":len(answer.get("recommended_next_steps") or []),"grounding_score":round(grounding,4),"discipline_score":round(discipline,4),"gate":gate,"human_review_required":True}
        aid,now=new_id("coaiassess240"),now_ts(); payload={"assessment_id":aid,"case_id":turn["case_id"],"turn_id":turn_id,"snapshot_id":sid,"answer_sha256":_hash(answer),**assessment,"assessed_by":actor,"assessed_at":now}
        self.db.execute("INSERT INTO coai_turn_assessments_240 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,turn["case_id"],turn_id,sid,payload["answer_sha256"],assessment["observation_count"],grounded,accepted_used,candidate_refs,contradiction_surfaced,assessment["open_questions_count"],assessment["recommended_steps_count"],assessment["grounding_score"],assessment["discipline_score"],gate,dumps(assessment),actor,now,_hash(payload)))
        self._event(turn["case_id"],"turn_assessed","turn",turn_id,assessment,actor); return payload

    def stage_training(self,*,case_id:str,actor:str,limit:int=50,confirmation:str)->dict[str,Any]:
        if confirmation!=f"COAI TRAINING 240 {case_id} VORBEREITEN": raise PermissionError("explicit approval required")
        rows=self.db.all("""SELECT a.* FROM coai_turn_assessments_240 a LEFT JOIN coai_training_links_240 t ON t.assessment_id=a.assessment_id WHERE a.case_id=? AND a.gate='COAI_240_PASS' AND t.training_link_id IS NULL ORDER BY a.assessed_at LIMIT ?""",(case_id,max(1,min(200,int(limit)))))
        created=[]
        for r in rows:
            turn=self.conversation.turn_status(turn_id=r["turn_id"]); answer=(turn.get("response") or {}).get("answer") or {}
            context={"build":self.BUILD,"assessment_id":r["assessment_id"],"case_state_sha256":self.db.one("SELECT state_sha256 FROM coai_case_snapshots_240 WHERE snapshot_id=?",(r["snapshot_id"],))["state_sha256"],"grounding_score":r["grounding_score"],"discipline_score":r["discipline_score"],"human_review_required":True}
            ex=self.training.add_example(case_id=case_id,instruction="Beantworte eine fallbezogene Ermittlerfrage evidenzgebunden. Trenne Beobachtung, Schlussfolgerung und Hypothese; nenne Widersprüche und offene Fragen.",response=_canon(answer),context=context,evidence_refs=list((turn.get("response") or {}).get("citations") or []),language=turn.get("message_language") or "de",source_type="co_ai_investigator_240",source_ref=r["assessment_id"],created_by=actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
            tid,now=new_id("coaitrain240"),now_ts(); p={"training_link_id":tid,"case_id":case_id,"assessment_id":r["assessment_id"],"training_example_id":ex["example_id"],"created_by":actor,"created_at":now}
            self.db.execute("INSERT INTO coai_training_links_240 VALUES(?,?,?,?,?,?,?)",(tid,case_id,r["assessment_id"],ex["example_id"],actor,now,_hash(p))); created.append(ex["example_id"])
        self._event(case_id,"training_staged","case",case_id,{"count":len(created),"automatic_activation":False},actor)
        return {"case_id":case_id,"created":len(created),"training_example_ids":created,"review_status":"pending","automatic_activation":False}

    def dashboard(self,*,case_id:str)->dict[str,Any]:
        s=self.case_state(case_id=case_id,limit=40)
        one=lambda q:int((self.db.one(q,(case_id,)) or {"n":0})["n"])
        return {"build":self.BUILD,"case_id":case_id,"entities":len(s["entities"]),"verified_claims":len(s["verified_claims"]),"accepted_evidence":len(s["accepted_integrity_checked_evidence"]),"accepted_edges":len(s["accepted_graph_edges"]),"open_tasks":len(s["open_tasks"]),"gaps":len(s["open_research_gaps"]),"contradictions":len(s["contradictions"]),"assessments":one("SELECT COUNT(*) n FROM coai_turn_assessments_240 WHERE case_id=?"),"training":one("SELECT COUNT(*) n FROM coai_training_links_240 WHERE case_id=?"),"state_sha256":s["state_sha256"]}

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        e=html.escape; d=self.dashboard(case_id=case_id)
        return f"""<section class='card' id='build240_coai'><h2>Co-AI Investigator 3.0 Core + AI Training · Build 240</h2><p>Der Co-Ermittler erhält einen kanonischen, evidenzgebundenen Gesamtfallzustand. Kandidaten, Hypothesen und ungeprüfte Evidenz bleiben Nicht-Fakten; externe Aktionen bleiben menschlich kontrolliert.</p><div class='metrics'><div class='metric'><div class='label'>Entities</div><div class='value'>{d['entities']}</div></div><div class='metric'><div class='label'>Verified Claims</div><div class='value'>{d['verified_claims']}</div></div><div class='metric'><div class='label'>Accepted Evidence</div><div class='value'>{d['accepted_evidence']}</div></div><div class='metric'><div class='label'>Contradictions</div><div class='value'>{d['contradictions']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training']}</div></div></div><div class='grid'><div class='card'><h3>Gesamtfall einfrieren</h3><form method='post' action='/build240/snapshot'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Co-AI-Fallzustand snapshotten</button></form></div><div class='card'><h3>Turn prüfen</h3><form method='post' action='/build240/assess-turn'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='turn_id' placeholder='Build-227 Turn-ID' required><button>Grounding &amp; Reasoning prüfen</button></form></div><div class='card'><h3>KI-Training fortführen</h3><form method='post' action='/build240/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='limit' type='number' min='1' max='200' value='50'><button>Qualifizierte Co-AI-Turns für Build 228 vorbereiten</button></form><p class='muted'>Nur pending Human Review; keine automatische Modellaktivierung.</p></div></div><p class='muted'>State SHA-256: <code>{e(d['state_sha256'])}</code></p></section>"""

    def _assessment(self,row:Mapping[str,Any])->dict[str,Any]: return {**dict(row),"assessment":_loads(row.get("assessment_json"),{})}
    def _event(self,case_id:str,event_type:str,object_type:str,object_id:str,payload:Mapping[str,Any],actor:str)->None:
        prev=self.db.one("SELECT event_hash FROM build240_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(case_id,)); previous=prev["event_hash"] if prev else "GENESIS"; eid,now=new_id("evt240"),now_ts(); mat={"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":object_type,"object_id":object_id,"actor":actor,"payload":dict(payload),"previous_hash":previous,"created_at":now}; h=_hash(mat)
        self.db.execute("INSERT INTO build240_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,case_id,event_type,object_type,object_id,actor,dumps(dict(payload)),previous,h,now))
        try:self.audit.log(f"build240_{event_type}",object_type,object_id,case_id,dict(payload))
        except Exception:pass
