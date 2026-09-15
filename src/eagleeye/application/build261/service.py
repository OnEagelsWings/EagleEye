from __future__ import annotations
import hashlib, html, json, time, uuid
from typing import Any

TYPES={"subquestion","known_fact","disputed_claim","hypothesis","intelligence_gap","relationship","event","source","counterevidence","open_task","analyst_assessment"}

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p): return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build261CaseIntelligenceService:
    BUILD="261.0"
    def __init__(self,db:Any,audit:Any,*,compatibility:Any,claims:Any,publication:Any,training:Any,opsec:Any,actor:str="local-analyst"):
        self.db=db; self.audit=audit; self.compatibility=compatibility; self.claims=claims; self.publication=publication; self.training=training; self.opsec=opsec; self.actor=actor

    def _case(self,case_id):
        row=self.db.one("SELECT case_id,title,status FROM cases WHERE case_id=?",(case_id,))
        if not row: raise KeyError("case not found")
        return row

    def upsert_profile(self,*,case_id,objective,research_question,confidence="medium",publication_status="internal",actor=None):
        self._case(case_id)
        if not objective.strip() or not research_question.strip(): raise ValueError("objective and research_question required")
        if confidence not in {"low","medium","high"}: raise ValueError("invalid confidence")
        now=_now(); actor=actor or self.actor
        old=self.db.one("SELECT profile_id,created_at,created_by FROM case_intelligence_profiles_261 WHERE case_id=?",(case_id,))
        pid=old["profile_id"] if old else _id("ci261")
        self.db.execute("""INSERT OR REPLACE INTO case_intelligence_profiles_261
        (profile_id,case_id,objective,research_question,confidence,publication_status,state,created_by,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",(pid,case_id,objective.strip(),research_question.strip(),confidence,publication_status,"active",
        old["created_by"] if old else actor,old["created_at"] if old else now,now))
        self._event(case_id,"profile_saved","case_intelligence_profile",pid,actor,{"objective":objective,"research_question":research_question})
        return self.db.one("SELECT * FROM case_intelligence_profiles_261 WHERE profile_id=?",(pid,))

    def add_item(self,*,case_id,item_type,title,statement,status="open",evidence_ref="",confidence="medium",actor=None):
        self._case(case_id)
        if item_type not in TYPES: raise ValueError("invalid item_type")
        if not title.strip() or not statement.strip(): raise ValueError("title and statement required")
        if item_type=="known_fact" and not evidence_ref.strip(): raise ValueError("known_fact requires evidence_ref")
        if item_type=="hypothesis" and status in {"verified","fact"}: raise ValueError("hypothesis cannot be promoted to fact")
        actor=actor or self.actor; now=_now(); iid=_id("cii261")
        payload={"item_type":item_type,"title":title.strip(),"statement":statement.strip(),"status":status,"evidence_ref":evidence_ref.strip(),"confidence":confidence}
        self.db.execute("INSERT INTO case_intelligence_items_261 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (iid,case_id,item_type,payload["title"],payload["statement"],status,payload["evidence_ref"],confidence,actor,now,_hash(payload)))
        self._event(case_id,"item_added","case_intelligence_item",iid,actor,payload)
        return self.db.one("SELECT * FROM case_intelligence_items_261 WHERE item_id=?",(iid,))

    def snapshot(self,case_id):
        case=self._case(case_id)
        profile=self.db.one("SELECT * FROM case_intelligence_profiles_261 WHERE case_id=?",(case_id,))
        rows=self.db.all("SELECT * FROM case_intelligence_items_261 WHERE case_id=? ORDER BY created_at,item_id",(case_id,))
        grouped={k:[] for k in sorted(TYPES)}
        for r in rows: grouped.setdefault(r["item_type"],[]).append(r)
        verified=int((self.db.one("SELECT COUNT(*) n FROM claims_229 WHERE case_id=? AND status='verified'",(case_id,)) or {"n":0})["n"]) if self._table("claims_229") else 0
        disputed=len(grouped.get("disputed_claim",[])); gaps=len(grouped.get("intelligence_gap",[])); tasks=len(grouped.get("open_task",[]))
        return {"case":case,"profile":profile,"items":grouped,"metrics":{"verified_claims":verified,"disputed_claims":disputed,"intelligence_gaps":gaps,"open_tasks":tasks},
                "automatic_fact_promotion":False,"automatic_external_collection":False}

    def _table(self,name):
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(name,)))

    def next_questions(self,case_id):
        s=self.snapshot(case_id); out=[]
        for x in s["items"].get("intelligence_gap",[]): out.append({"kind":"gap","question":x["statement"],"source":"analyst_recorded"})
        for x in s["items"].get("subquestion",[]):
            if x["status"]=="open": out.append({"kind":"subquestion","question":x["statement"],"source":"analyst_recorded"})
        return {"case_id":case_id,"questions":out,"generated_external_actions":[],"requires_human_selection":True}

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_case_state_benchmarks_261 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_case_state_benchmarks_261") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"automatic_model_activation":False,"automatic_adapter_activation":False}

    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_261 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"autonomous_external_collection":0,"access_control_bypass":0,"automatic_external_contact":0}

    def release_gate(self):
        caps=self.compatibility.capabilities()
        return {"build":"261.0","main_goal":self._table("case_intelligence_profiles_261") and self._table("case_intelligence_items_261"),
                "ai_delta":self.ai_metrics()["reviewed_benchmarks"]>=16 and self.ai_metrics()["task_families"]>=7,
                "opsec_delta":self.opsec_metrics()["verified_controls"]>=16,
                "capability_regression":"phase10_qualification" in caps and "test_contract_compatibility" in caps,
                "parent_build_gate":self.compatibility.compatibility_report()["sqlite_integrity"]=="ok",
                "release_ready":False} | {}
    def qualified_gate(self):
        g=self.release_gate(); g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate")); return g

    def _event(self,case_id,event_type,obj_type,obj_id,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build261_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(case_id,))
        ph=prev["event_hash"] if prev else "GENESIS"; eid=_id("evt261"); now=_now()
        eh=_hash({"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":obj_type,"object_id":obj_id,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now})
        self.db.execute("INSERT INTO build261_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,case_id,event_type,obj_type,obj_id,actor,_canon(payload),ph,eh,now))

    def verify_event_chain(self,case_id):
        rows=self.db.all("SELECT * FROM build261_events WHERE case_id=? ORDER BY rowid",(case_id,)); prev="GENESIS"
        for r in rows:
            payload=json.loads(r["payload_json"])
            exp=_hash({"event_id":r["event_id"],"case_id":r["case_id"],"event_type":r["event_type"],"object_type":r["object_type"],"object_id":r["object_id"],"actor":r["actor"],"payload":payload,"previous_hash":prev,"created_at":r["created_at"]})
            if r["previous_hash"]!=prev or r["event_hash"]!=exp: return False
            prev=r["event_hash"]
        return True

    def render_workspace_panel(self,*,case_id,csrf):
        s=self.snapshot(case_id); e=html.escape; p=s["profile"] or {}
        rows="".join(f"<tr><td>{e(k)}</td><td>{len(v)}</td></tr>" for k,v in s["items"].items() if v)
        return f"""<section class='card'><h2>Phase 11 · Case Intelligence 261</h2>
        <p>Fallzustand, Forschungsfrage, Fakten/Hypothesen, Gegenbelege und Intelligence Gaps. Keine automatische Faktenerhebung oder externe Aktion.</p>
        <form method='post' action='/build261/profile'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <label>Objective</label><input name='objective' value='{e(p.get("objective",""))}' required>
        <label>Research question</label><textarea name='research_question' required>{e(p.get("research_question",""))}</textarea><button>Case State speichern</button></form>
        <form method='post' action='/build261/item'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <select name='item_type'>{"".join(f"<option>{e(x)}</option>" for x in sorted(TYPES))}</select><input name='title' placeholder='Titel' required>
        <textarea name='statement' placeholder='Beobachtung / Frage / Hypothese' required></textarea><input name='evidence_ref' placeholder='Evidence ref (Pflicht bei known_fact)'><button>Eintrag anlegen</button></form>
        <table><tr><th>Typ</th><th>Anzahl</th></tr>{rows}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
