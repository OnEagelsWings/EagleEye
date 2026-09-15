from __future__ import annotations
import hashlib, html, json, time, uuid
from typing import Any

TASK_TYPES={"gap_resolution","corroboration","verify_claim","resolve_entity","source_independence","timeline","financial_trace","document_review","counterevidence","legal_publication_review"}
PRIORITIES={"low","normal","high","critical"}
SOURCE_CLASSES={"public_registry","public_web","manual_document_review","legal_database","media_archive","corporate_registry","public_procurement","foia_archive","case_evidence"}
STATES={"proposed","approved","in_progress","blocked","completed","rejected"}

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p): return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

def _list(v):
    if v is None: return []
    if isinstance(v,(list,tuple,set)): return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";",",").split(",") if x.strip()]

class Build262InvestigativeTaskGraphService:
    BUILD="262.0"
    def __init__(self,db:Any,audit:Any,*,case_state:Any,compatibility:Any,training:Any,opsec:Any,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.case_state=case_state; self.compatibility=compatibility; self.training=training; self.opsec=opsec; self.actor=actor

    def _case(self,case_id):
        row=self.db.one("SELECT case_id,title FROM cases WHERE case_id=?",(case_id,))
        if not row: raise KeyError("case not found")
        return row

    def _task(self,task_id):
        row=self.db.one("SELECT * FROM investigative_tasks_262 WHERE task_id=?",(task_id,))
        if not row: raise KeyError("task not found")
        return row

    def current_state(self,task_id):
        row=self.db.one("SELECT * FROM investigative_task_state_events_262 WHERE task_id=? ORDER BY rowid DESC LIMIT 1",(task_id,))
        return row or {"state":"proposed","reviewer":"","result_summary":"","evidence_refs_json":"[]"}

    def create_task(self,*,case_id,task_type,title,question,priority="normal",evidence_requirements=None,source_classes=None,origin_kind="manual",origin_ref="",actor=None):
        self._case(case_id)
        if task_type not in TASK_TYPES: raise ValueError("invalid task_type")
        if priority not in PRIORITIES: raise ValueError("invalid priority")
        if not title.strip() or not question.strip(): raise ValueError("title and question required")
        src=_list(source_classes) or ["case_evidence"]
        bad=[x for x in src if x not in SOURCE_CLASSES]
        if bad: raise ValueError("unapproved source class")
        req=_list(evidence_requirements)
        actor=actor or self.actor; tid=_id("task262"); now=_now()
        payload={"origin_kind":origin_kind,"origin_ref":origin_ref,"task_type":task_type,"title":title.strip(),"question":question.strip(),"priority":priority,"evidence_requirements":req,"source_classes":src}
        self.db.execute("INSERT INTO investigative_tasks_262 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (tid,case_id,origin_kind,origin_ref,task_type,payload["title"],payload["question"],priority,_canon(req),_canon(src),actor,now,_hash(payload)))
        self._state_event(case_id,tid,"proposed","Task created","",[],actor)
        self._event(case_id,"task_created","investigative_task",tid,actor,payload)
        return self.task_view(tid)

    def propose_from_case_state(self,case_id,actor=None):
        self._case(case_id); actor=actor or self.actor; created=[]
        snap=self.case_state.snapshot(case_id)
        mapping=[("intelligence_gap","gap_resolution","high"),("subquestion","corroboration","normal"),("disputed_claim","verify_claim","high")]
        existing={(r["origin_kind"],r["origin_ref"]) for r in self.db.all("SELECT origin_kind,origin_ref FROM investigative_tasks_262 WHERE case_id=?",(case_id,))}
        for item_type,task_type,priority in mapping:
            for item in snap["items"].get(item_type,[]):
                key=(item_type,item["item_id"])
                if key in existing: continue
                created.append(self.create_task(case_id=case_id,task_type=task_type,title=item["title"],question=item["statement"],priority=priority,
                    evidence_requirements=["provenance_bound_evidence"],source_classes=["case_evidence","public_registry","manual_document_review"],origin_kind=item_type,origin_ref=item["item_id"],actor=actor))
        return {"case_id":case_id,"created_count":len(created),"tasks":created,"automatic_approval":False,"automatic_execution":False}

    def add_dependency(self,*,case_id,task_id,depends_on_task_id,actor=None):
        if task_id==depends_on_task_id: raise ValueError("self dependency")
        a=self._task(task_id); b=self._task(depends_on_task_id)
        if a["case_id"]!=case_id or b["case_id"]!=case_id: raise ValueError("cross-case dependency forbidden")
        if self._would_cycle(task_id,depends_on_task_id): raise ValueError("dependency cycle")
        actor=actor or self.actor; did=_id("dep262"); now=_now(); payload={"task_id":task_id,"depends_on_task_id":depends_on_task_id}
        self.db.execute("INSERT INTO investigative_task_dependencies_262 VALUES(?,?,?,?,?,?,?)",(did,case_id,task_id,depends_on_task_id,actor,now,_hash(payload)))
        self._event(case_id,"dependency_added","investigative_task_dependency",did,actor,payload)
        return {"dependency_id":did,**payload}

    def _would_cycle(self,task_id,depends_on):
        # proposed edge task -> depends_on creates cycle if depends_on already reaches task
        stack=[depends_on]; seen=set()
        while stack:
            cur=stack.pop()
            if cur==task_id: return True
            if cur in seen: continue
            seen.add(cur)
            rows=self.db.all("SELECT depends_on_task_id FROM investigative_task_dependencies_262 WHERE task_id=?",(cur,))
            stack.extend(r["depends_on_task_id"] for r in rows)
        return False

    def transition(self,*,case_id,task_id,state,rationale="",result_summary="",evidence_refs=None,reviewer=None):
        task=self._task(task_id)
        if task["case_id"]!=case_id: raise ValueError("case mismatch")
        if state not in STATES: raise ValueError("invalid state")
        cur=self.current_state(task_id)["state"]
        allowed={"proposed":{"approved","rejected"},"approved":{"in_progress","blocked","rejected"},"in_progress":{"completed","blocked"},"blocked":{"approved","in_progress","rejected"},"completed":set(),"rejected":set()}
        if state not in allowed.get(cur,set()): raise ValueError(f"invalid transition {cur}->{state}")
        refs=_list(evidence_refs)
        if state=="approved" and (reviewer or self.actor)==task["created_by"]: raise ValueError("approval requires independent reviewer")
        if state=="completed" and (not result_summary.strip() or not refs): raise ValueError("completion requires result summary and evidence refs")
        reviewer=reviewer or self.actor
        self._state_event(case_id,task_id,state,rationale,result_summary,refs,reviewer)
        self._event(case_id,"task_state_changed","investigative_task",task_id,reviewer,{"from":cur,"to":state,"evidence_refs":refs})
        return self.task_view(task_id)

    def task_view(self,task_id):
        task=self._task(task_id); state=self.current_state(task_id)
        deps=self.db.all("SELECT depends_on_task_id FROM investigative_task_dependencies_262 WHERE task_id=? ORDER BY rowid",(task_id,))
        dep_ids=[x["depends_on_task_id"] for x in deps]
        dep_states={d:self.current_state(d)["state"] for d in dep_ids}
        ready=state["state"]=="approved" and all(v=="completed" for v in dep_states.values())
        return {**task,"state":state["state"],"state_reviewer":state.get("reviewer",""),"dependencies":dep_ids,"dependency_states":dep_states,"ready":ready,"automatic_execution":False}

    def graph(self,case_id):
        self._case(case_id)
        tasks=[self.task_view(r["task_id"]) for r in self.db.all("SELECT task_id FROM investigative_tasks_262 WHERE case_id=? ORDER BY created_at,task_id",(case_id,))]
        edges=self.db.all("SELECT task_id,depends_on_task_id FROM investigative_task_dependencies_262 WHERE case_id=? ORDER BY rowid",(case_id,))
        return {"case_id":case_id,"tasks":tasks,"edges":edges,"ready_task_ids":[t["task_id"] for t in tasks if t["ready"]],"automatic_external_actions":[]}

    def stage_training_candidate(self,*,case_id,task_id,actor=None):
        task=self._task(task_id); state=self.current_state(task_id)
        if task["case_id"]!=case_id: raise ValueError("case mismatch")
        if state["state"]!="completed": raise PermissionError("only completed evidence-bound tasks may stage training candidates")
        refs=json.loads(state.get("evidence_refs_json") or "[]")
        actor=actor or self.actor
        return self.training.add_example(case_id=case_id,
            instruction="Given this reviewed investigative task, state the evidence-bounded outcome and preserve uncertainty.",
            response=state.get("result_summary") or "",
            context={"build":"262.0","task_type":task["task_type"],"task_title":task["title"],"task_question":task["question"],"source_classes":json.loads(task["source_classes_json"]),"human_review_required":True,"source_content_is_instruction":False},
            evidence_refs=refs,language="de",source_type="build262_completed_task",source_ref=task_id,created_by=actor,
            confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_task_graph_benchmarks_262 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_task_graph_benchmarks_262") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"automatic_model_activation":False,"automatic_adapter_activation":False}

    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_262 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"autonomous_external_collection":0,"automatic_browser_execution":0,"automatic_external_contact":0,"access_control_bypass":0}

    def qualified_gate(self):
        caps=self.compatibility.capabilities(); ai=self.ai_metrics(); op=self.opsec_metrics()
        g={"build":"262.0","main_goal":all(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(x,)) for x in ("investigative_tasks_262","investigative_task_dependencies_262","investigative_task_state_events_262")),
           "ai_delta":ai["reviewed_benchmarks"]>=20 and ai["task_families"]>=10,"opsec_delta":op["verified_controls"]>=18,
           "capability_regression":"case_intelligence_model" in caps and "phase10_qualification" in caps,
           "parent_build_gate":self.case_state.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate")); return g

    def _state_event(self,case_id,task_id,state,rationale,result_summary,evidence_refs,reviewer):
        payload={"state":state,"rationale":rationale,"result_summary":result_summary,"evidence_refs":evidence_refs}
        self.db.execute("INSERT INTO investigative_task_state_events_262 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (_id("state262"),case_id,task_id,state,rationale,result_summary,_canon(evidence_refs),reviewer,_now(),_hash(payload)))

    def _event(self,case_id,event_type,obj_type,obj_id,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build262_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(case_id,)); ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt262"); now=_now(); data={"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":obj_type,"object_id":obj_id,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}; eh=_hash(data)
        self.db.execute("INSERT INTO build262_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,case_id,event_type,obj_type,obj_id,actor,_canon(payload),ph,eh,now))

    def verify_event_chain(self,case_id):
        prev="GENESIS"
        for r in self.db.all("SELECT * FROM build262_events WHERE case_id=? ORDER BY rowid",(case_id,)):
            payload=json.loads(r["payload_json"]); data={"event_id":r["event_id"],"case_id":r["case_id"],"event_type":r["event_type"],"object_type":r["object_type"],"object_id":r["object_id"],"actor":r["actor"],"payload":payload,"previous_hash":prev,"created_at":r["created_at"]}
            if r["previous_hash"]!=prev or r["event_hash"]!=_hash(data): return False
            prev=r["event_hash"]
        return True

    def render_workspace_panel(self,*,case_id,csrf):
        e=html.escape; graph=self.graph(case_id); rows="".join(f"<tr><td>{e(t['title'])}</td><td>{e(t['task_type'])}</td><td>{e(t['priority'])}</td><td>{e(t['state'])}</td><td>{'ready' if t['ready'] else ''}</td></tr>" for t in graph["tasks"])
        return f"""<section class='card'><h2>Phase 11 · Investigative Task Graph 262</h2><p>Tasks sind Planungsobjekte. Ready bedeutet niemals automatische Ausführung.</p>
        <form method='post' action='/build262/from-case-state'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Tasks aus Case State vorschlagen</button></form>
        <form method='post' action='/build262/task'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <select name='task_type'>{''.join(f'<option>{e(x)}</option>' for x in sorted(TASK_TYPES))}</select><select name='priority'>{''.join(f'<option>{e(x)}</option>' for x in ('normal','high','critical','low'))}</select>
        <input name='title' placeholder='Task' required><textarea name='question' placeholder='Überprüfbare Frage' required></textarea><input name='source_classes' value='case_evidence,public_registry,manual_document_review'><button>Task anlegen</button></form>
        <form method='post' action='/build262/dependency'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='task_id' placeholder='Task ID' required><input name='depends_on_task_id' placeholder='Depends on Task ID' required><button>Abhängigkeit anlegen</button></form>
        <form method='post' action='/build262/state'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='task_id' placeholder='Task ID' required><select name='state'>{''.join(f'<option>{e(x)}</option>' for x in ('approved','in_progress','blocked','completed','rejected'))}</select><input name='rationale' placeholder='Begründung'><input name='result_summary' placeholder='Result Summary'><input name='evidence_refs' placeholder='Evidence refs, comma-separated'><button>Status speichern</button></form>
        <table><tr><th>Task</th><th>Typ</th><th>Priorität</th><th>Status</th><th>Ready</th></tr>{rows}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
