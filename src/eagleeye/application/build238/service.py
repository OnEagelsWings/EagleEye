from __future__ import annotations
import hashlib, html, json
from collections import defaultdict, deque
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any)->str: return hashlib.sha256((v if isinstance(v,bytes) else _canon(v).encode("utf-8"))).hexdigest()
def _loads(v: str|None,d: Any)->Any:
    try: return json.loads(v) if v else d
    except Exception: return d
def _text(v: Any,n:int=20000)->str: return str(v or "").replace("\x00","").strip()[:n]
def _clamp(v: Any)->float:
    try: return max(0.0,min(1.0,float(v)))
    except Exception: return 0.0

class Build238IdentityRelationshipGraph3Service:
    """Case-local, provenance-aware analytical projection over Kernel 235.

    It does not create facts from graph proximity. New graph hypotheses remain candidates,
    need independent Build-238 review, and accepted candidates still create an unreviewed
    Kernel-235 link requiring a separate review. No network action is performed.
    """
    BUILD="238.0"
    def __init__(self,db:Any,audit:Any,*,kernel:Any,social:Any,source_fabric:Any,multilingual:Any,training:Any,conversation:Any,actor:str="local-analyst"):
        self.db,self.audit,self.kernel,self.social,self.source_fabric,self.multilingual,self.training,self.conversation,self.actor=db,audit,kernel,social,source_fabric,multilingual,training,conversation,actor
        self.conversation._identity_relationship_graph_238=self

    def graph(self,*,case_id:str,include_candidates:bool=True)->dict[str,Any]:
        self.kernel.cases.get_case(case_id)
        objects=self.db.all("SELECT * FROM canonical_objects_235 WHERE case_id=? ORDER BY created_at,object_id",(case_id,))
        nodes=[]
        for r in objects:
            obj=self.kernel.get_object(r["object_id"])
            nodes.append({"id":r["object_id"],"type":r["object_type"],"subtype":r["subtype"],"label":r["label"],"state":obj.get("state","candidate"),"confidence":round(float(obj.get("confidence",0.0)),4),"provenance":obj.get("provenance",{})})
        rows=self.db.all("""SELECT l.*,COALESCE(rv.decision,'unreviewed') review_status,rv.rationale review_rationale,a.valid_from,a.valid_to,a.first_observed_at,a.last_observed_at,a.temporal_precision,a.provenance_json annotation_provenance,a.evidence_refs_json annotation_evidence FROM canonical_links_235 l LEFT JOIN canonical_link_reviews_235 rv ON rv.link_id=l.link_id LEFT JOIN graph_edge_annotations_238 a ON a.kernel_link_id=l.link_id WHERE l.case_id=? ORDER BY l.created_at,l.link_id""",(case_id,))
        edges=[]
        for r in rows:
            state="accepted" if r["review_status"]=="accepted" else "rejected" if r["review_status"]=="rejected" else "candidate"
            if not include_candidates and state!="accepted": continue
            refs=list(dict.fromkeys(_loads(r["evidence_refs_json"],[])+_loads(r.get("annotation_evidence"),[])))
            edges.append({"id":r["link_id"],"source":r["source_object_id"],"target":r["target_object_id"],"relation":r["relation_type"],"confidence":round(float(r["confidence"]),4),"state":state,"evidence_refs":refs,"valid_from":r.get("valid_from") or "","valid_to":r.get("valid_to") or "","first_observed_at":r.get("first_observed_at") or "","last_observed_at":r.get("last_observed_at") or "","temporal_precision":r.get("temporal_precision") or "unknown","provenance":_loads(r.get("annotation_provenance"),{})})
        return {"case_id":case_id,"nodes":nodes,"edges":edges,"accepted_only":not include_candidates,"graph_is_analytical_projection":True,"proximity_is_not_relationship":True}

    def annotate_edge(self,*,link_id:str,valid_from:str="",valid_to:str="",first_observed_at:str="",last_observed_at:str="",temporal_precision:str="unknown",provenance:Mapping[str,Any]|None=None,evidence_refs:Sequence[str]=(),created_by:str,confirmation:str)->dict[str,Any]:
        link=self._link(link_id); case_id=link["case_id"]
        if confirmation!=f"GRAPH EDGE 238 {link_id} ANNOTIEREN": raise PermissionError("explicit approval required")
        if temporal_precision not in {"exact","day","month","year","range","unknown"}: raise ValueError("invalid temporal precision")
        if self.db.one("SELECT annotation_id FROM graph_edge_annotations_238 WHERE kernel_link_id=?",(link_id,)): raise ValueError("edge already annotated")
        refs=list(dict.fromkeys(_text(x,300) for x in evidence_refs if _text(x,300)))[:100]
        aid,now=new_id("graphedge238"),now_ts(); payload={"annotation_id":aid,"case_id":case_id,"kernel_link_id":link_id,"valid_from":_text(valid_from,80),"valid_to":_text(valid_to,80),"first_observed_at":_text(first_observed_at,80),"last_observed_at":_text(last_observed_at,80),"temporal_precision":temporal_precision,"provenance":dict(provenance or {}),"evidence_refs":refs,"created_by":created_by,"created_at":now}
        self.db.execute("INSERT INTO graph_edge_annotations_238 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,case_id,link_id,payload["valid_from"],payload["valid_to"],payload["first_observed_at"],payload["last_observed_at"],temporal_precision,dumps(payload["provenance"]),dumps(refs),created_by,now,_hash(payload)))
        self._event(case_id,"graph_edge_annotated","canonical_link",link_id,{"temporal_precision":temporal_precision},created_by); return payload

    def propose_relationship(self,*,case_id:str,source_object_id:str,relation_type:str,target_object_id:str,rationale:str,evidence_refs:Sequence[str],confidence:float=.5,valid_from:str="",valid_to:str="",contradiction_refs:Sequence[str]=(),created_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GRAPH HYPOTHESIS 238 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        src,dst=self.kernel.get_object(source_object_id),self.kernel.get_object(target_object_id)
        if src["case_id"]!=case_id or dst["case_id"]!=case_id or source_object_id==target_object_id: raise ValueError("case-local distinct objects required")
        rel=_text(relation_type,160).casefold(); base=rel.split(":",1)[0]
        if base not in self.kernel.RELATIONS: raise ValueError("unsupported relation type")
        note=_text(rationale,6000)
        if len(note)<15: raise ValueError("substantive rationale required")
        refs=list(dict.fromkeys(_text(x,300) for x in evidence_refs if _text(x,300)))[:100]
        contra=list(dict.fromkeys(_text(x,300) for x in contradiction_refs if _text(x,300)))[:100]
        if not refs: raise ValueError("evidence refs required")
        existing=self.db.one("SELECT * FROM graph_hypotheses_238 WHERE case_id=? AND source_object_id=? AND relation_type=? AND target_object_id=?",(case_id,source_object_id,rel,target_object_id))
        if existing: return self._hyp_payload(existing)
        hid,now=new_id("graphhyp238"),now_ts(); payload={"graph_hypothesis_id":hid,"case_id":case_id,"source_object_id":source_object_id,"relation_type":rel,"target_object_id":target_object_id,"confidence":_clamp(confidence),"rationale":note,"evidence_refs":refs,"valid_from":_text(valid_from,80),"valid_to":_text(valid_to,80),"contradiction_refs":contra,"created_by":created_by,"created_at":now}
        self.db.execute("INSERT INTO graph_hypotheses_238 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(hid,case_id,source_object_id,rel,target_object_id,payload["confidence"],note,dumps(refs),payload["valid_from"],payload["valid_to"],dumps(contra),created_by,now,_hash(payload)))
        self._event(case_id,"graph_hypothesis_created","graph_hypothesis",hid,{"relation_type":rel,"automatic_fact":False},created_by); return {**payload,"review_status":"pending","automatic_fact":False}

    def review_relationship(self,*,graph_hypothesis_id:str,decision:str,rationale:str,reviewer:str,confirmation:str)->dict[str,Any]:
        row=self._hyp(graph_hypothesis_id)
        if confirmation!=f"GRAPH HYPOTHESIS REVIEW 238 {graph_hypothesis_id} SPEICHERN": raise PermissionError("explicit approval required")
        if reviewer==row["created_by"]: raise PermissionError("independent reviewer required")
        if decision not in {"accepted_candidate","rejected","needs_more_evidence"}: raise ValueError("invalid decision")
        if len(_text(rationale,6000))<15: raise ValueError("substantive rationale required")
        if self.db.one("SELECT review_id FROM graph_hypothesis_reviews_238 WHERE graph_hypothesis_id=?",(graph_hypothesis_id,)): raise ValueError("already reviewed")
        contra=_loads(row["contradiction_refs_json"],[])
        if decision=="accepted_candidate" and contra: raise PermissionError("unresolved contradictions block acceptance")
        if decision=="accepted_candidate" and row["relation_type"].split(":",1)[0]=="same_as_candidate" and float(row["confidence"]) < .75:
            raise PermissionError("identity-candidate confidence gate blocks acceptance")
        kernel_link_id=""
        if decision=="accepted_candidate":
            link=self.kernel.create_link(case_id=row["case_id"],source_object_id=row["source_object_id"],relation_type=row["relation_type"],target_object_id=row["target_object_id"],confidence=float(row["confidence"]),evidence_refs=_loads(row["evidence_refs_json"],[]),actor=reviewer,confirmation=f"KERNEL LINK 235 {row['case_id']} ANLEGEN")
            kernel_link_id=link["link_id"]
        rid,now=new_id("graphreview238"),now_ts(); payload={"review_id":rid,"graph_hypothesis_id":graph_hypothesis_id,"case_id":row["case_id"],"decision":decision,"rationale":_text(rationale,6000),"reviewer":reviewer,"reviewed_at":now,"kernel_link_id":kernel_link_id}
        self.db.execute("INSERT INTO graph_hypothesis_reviews_238 VALUES(?,?,?,?,?,?,?,?,?)",(rid,graph_hypothesis_id,row["case_id"],decision,payload["rationale"],reviewer,now,kernel_link_id,_hash(payload)))
        self._event(row["case_id"],"graph_hypothesis_reviewed","graph_hypothesis",graph_hypothesis_id,{"decision":decision,"kernel_link_id":kernel_link_id,"kernel_review_still_required":bool(kernel_link_id)},reviewer)
        return {**payload,"kernel_review_still_required":bool(kernel_link_id),"automatic_fact":False}

    def shortest_path(self,*,case_id:str,source_object_id:str,target_object_id:str,include_candidates:bool=False,max_depth:int=6)->dict[str,Any]:
        g=self.graph(case_id=case_id,include_candidates=include_candidates); nodes={n["id"] for n in g["nodes"]}
        if source_object_id not in nodes or target_object_id not in nodes: raise KeyError("graph node not found")
        adj=defaultdict(list)
        for e in g["edges"]:
            if e["state"]=="rejected": continue
            adj[e["source"]].append((e["target"],e)); adj[e["target"]].append((e["source"],e))
        q=deque([(source_object_id,[source_object_id],[])]); seen={source_object_id}
        while q:
            cur,path,edges=q.popleft()
            if cur==target_object_id: return {"found":True,"nodes":path,"edges":edges,"candidate_edges_included":include_candidates,"path_is_not_causation":True}
            if len(edges)>=max(1,min(12,int(max_depth))): continue
            for nxt,e in adj[cur]:
                if nxt in seen: continue
                seen.add(nxt); q.append((nxt,path+[nxt],edges+[e]))
        return {"found":False,"nodes":[],"edges":[],"candidate_edges_included":include_candidates,"path_is_not_causation":True}

    def components(self,*,case_id:str,include_candidates:bool=False)->dict[str,Any]:
        g=self.graph(case_id=case_id,include_candidates=include_candidates); ids=[n["id"] for n in g["nodes"]]; adj=defaultdict(set)
        for e in g["edges"]:
            if e["state"]=="rejected": continue
            adj[e["source"]].add(e["target"]); adj[e["target"]].add(e["source"])
        seen=set(); comps=[]
        for nid in ids:
            if nid in seen: continue
            stack=[nid]; seen.add(nid); comp=[]
            while stack:
                x=stack.pop(); comp.append(x)
                for y in adj[x]:
                    if y not in seen: seen.add(y); stack.append(y)
            comps.append(sorted(comp))
        comps.sort(key=lambda x:(-len(x),x))
        return {"components":comps,"component_count":len(comps),"isolated_node_count":sum(1 for c in comps if len(c)==1),"candidate_edges_included":include_candidates}

    def create_snapshot(self,*,case_id:str,actor:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GRAPH SNAPSHOT 238 {case_id} ERSTELLEN": raise PermissionError("explicit approval required")
        g=self.graph(case_id=case_id,include_candidates=True); comp=self.components(case_id=case_id,include_candidates=False)
        accepted=sum(1 for e in g["edges"] if e["state"]=="accepted"); candidate=sum(1 for e in g["edges"] if e["state"]=="candidate"); rejected=sum(1 for e in g["edges"] if e["state"]=="rejected"); temporal=sum(1 for e in g["edges"] if e["valid_from"] or e["valid_to"] or e["first_observed_at"] or e["last_observed_at"])
        metrics={"node_types":{},"relation_types":{},"accepted_density":0.0,"graph_rule":"proximity/path does not establish relationship or causation"}
        for n in g["nodes"]: metrics["node_types"][n["type"]]=metrics["node_types"].get(n["type"],0)+1
        for e in g["edges"]: metrics["relation_types"][e["relation"]]=metrics["relation_types"].get(e["relation"],0)+1
        n=len(g["nodes"]); metrics["accepted_density"]=round(accepted/max(1,n*(n-1)),6)
        content=_hash({"nodes":g["nodes"],"edges":g["edges"]}); sid,now=new_id("graphsnap238"),now_ts(); payload={"snapshot_id":sid,"case_id":case_id,"node_count":n,"accepted_edge_count":accepted,"candidate_edge_count":candidate,"rejected_edge_count":rejected,"component_count":comp["component_count"],"isolated_node_count":comp["isolated_node_count"],"temporal_edge_count":temporal,"content_sha256":content,"metrics":metrics,"created_by":actor,"created_at":now}
        self.db.execute("INSERT INTO graph_snapshots_238 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,case_id,n,accepted,candidate,rejected,comp["component_count"],comp["isolated_node_count"],temporal,content,dumps(metrics),actor,now,_hash(payload)))
        self._event(case_id,"graph_snapshot_created","graph_snapshot",sid,{"node_count":n,"accepted_edges":accepted},actor); return payload

    def stage_training(self,*,case_id:str,actor:str,limit:int=50,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GRAPH TRAINING 238 {case_id} VORBEREITEN": raise PermissionError("explicit approval required")
        rows=self.db.all("""SELECT h.*,r.decision,r.rationale review_rationale,r.reviewer FROM graph_hypotheses_238 h JOIN graph_hypothesis_reviews_238 r ON r.graph_hypothesis_id=h.graph_hypothesis_id LEFT JOIN graph_training_links_238 t ON t.item_type='graph_hypothesis' AND t.item_id=h.graph_hypothesis_id WHERE h.case_id=? AND t.training_link_id IS NULL ORDER BY r.reviewed_at LIMIT ?""",(case_id,max(1,min(200,int(limit)))))
        created=[]
        for r in rows:
            instruction="Bewerte den vorgeschlagenen Graph-Link evidenzgebunden. Vermeide False Merges und leite aus graphischer Nähe weder Identität, Beziehung noch Kausalität ab."
            context={"source_object_id":r["source_object_id"],"relation_type":r["relation_type"],"target_object_id":r["target_object_id"],"confidence":r["confidence"],"rationale":r["rationale"],"evidence_refs":_loads(r["evidence_refs_json"],[]),"contradiction_refs":_loads(r["contradiction_refs_json"],[]),"valid_from":r["valid_from"],"valid_to":r["valid_to"]}
            response=f"Review-Entscheidung: {r['decision']}. Begründung: {r['review_rationale']}"
            try:
                ex=self.training.add_example(case_id=case_id,instruction=instruction,response=response,context=context,evidence_refs=context["evidence_refs"],language="de",source_type="identity_relationship_graph_238",source_ref=r["graph_hypothesis_id"],created_by=actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
            except ValueError as exc:
                if "duplicate" in str(exc).lower(): continue
                raise
            tid,now=new_id("graphtrain238"),now_ts(); p={"training_link_id":tid,"case_id":case_id,"item_type":"graph_hypothesis","item_id":r["graph_hypothesis_id"],"training_example_id":ex["example_id"],"created_by":actor,"created_at":now}
            self.db.execute("INSERT INTO graph_training_links_238 VALUES(?,?,?,?,?,?,?,?)",(tid,case_id,"graph_hypothesis",r["graph_hypothesis_id"],ex["example_id"],actor,now,_hash(p))); created.append(ex["example_id"])
        self._event(case_id,"graph_training_staged","case",case_id,{"created":len(created),"automatic_activation":False},actor)
        return {"case_id":case_id,"created":len(created),"training_example_ids":created,"review_status":"pending","automatic_activation":False}

    def conversation_context(self,*,case_id:str,limit:int=30)->dict[str,Any]:
        g=self.graph(case_id=case_id,include_candidates=True); lim=max(1,min(100,int(limit)))
        accepted=[e for e in g["edges"] if e["state"]=="accepted"][-lim:]; candidates=[e for e in g["edges"] if e["state"]=="candidate"][-min(lim,15):]
        return {"graph_build":self.BUILD,"nodes":g["nodes"][-lim:],"accepted_edges":accepted,"candidate_edges_not_facts":candidates,"components":self.components(case_id=case_id,include_candidates=False),"reasoning_rules":["Graph proximity is not a relationship.","A path is not causation.","Candidate edges are not facts.","same_as_candidate is not an identity merge."]}

    def dashboard(self,*,case_id:str)->dict[str,Any]:
        g=self.graph(case_id=case_id,include_candidates=True); c=self.components(case_id=case_id,include_candidates=False)
        pending=int(self.db.one("SELECT COUNT(*) n FROM training_examples_228 WHERE case_id=? AND source_type='identity_relationship_graph_238' AND review_status='pending'",(case_id,))["n"])
        return {"case_id":case_id,"nodes":len(g["nodes"]),"accepted_edges":sum(1 for e in g["edges"] if e["state"]=="accepted"),"candidate_edges":sum(1 for e in g["edges"] if e["state"]=="candidate"),"rejected_edges":sum(1 for e in g["edges"] if e["state"]=="rejected"),"components":c["component_count"],"isolated_nodes":c["isolated_node_count"],"graph_hypotheses":int(self.db.one("SELECT COUNT(*) n FROM graph_hypotheses_238 WHERE case_id=?",(case_id,))["n"]),"training_examples":int(self.db.one("SELECT COUNT(*) n FROM graph_training_links_238 WHERE case_id=?",(case_id,))["n"]),"pending_training_review":pending,"automatic_network_access":False,"automatic_identity_merge":False}

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        d=self.dashboard(case_id=case_id); e=lambda x:html.escape(str(x if x is not None else ""),quote=True)
        return f"""<section class='card' id='build238_graph'><h2>Identity &amp; Relationship Graph 3.0 + AI Training · Build 238</h2><p>Der Graph projiziert Kernel-235-Objekte und reviewte Links mit Zeit, Provenance und Confidence. Graphische Nähe, Pfade und Kandidaten sind keine Tatsachen.</p><div class='metrics'><div class='metric'><div class='label'>Nodes</div><div class='value'>{d['nodes']}</div></div><div class='metric'><div class='label'>Akzeptierte Edges</div><div class='value'>{d['accepted_edges']}</div></div><div class='metric'><div class='label'>Kandidaten</div><div class='value'>{d['candidate_edges']}</div></div><div class='metric'><div class='label'>Komponenten</div><div class='value'>{d['components']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training_examples']}</div></div></div><div class='grid'>
<div class='card'><h3>Beziehungshypothese</h3><form method='post' action='/build238/hypothesis-add'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='source_object_id' placeholder='Source Object-ID' required><input name='relation_type' value='related_to' required><input name='target_object_id' placeholder='Target Object-ID' required><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt' required><input name='contradiction_refs' placeholder='Widerspruchs-Refs optional'><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><textarea name='rationale' placeholder='Warum ist dies nur ein prüfbarer Kandidat?' required></textarea><button>Graph-Hypothese anlegen</button></form></div>
<div class='card'><h3>Hypothese unabhängig prüfen</h3><form method='post' action='/build238/hypothesis-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='graph_hypothesis_id' placeholder='Graph-Hypothesis-ID' required><select name='decision'><option>accepted_candidate</option><option>needs_more_evidence</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review speichern</button></form><p class='muted'>accepted_candidate erzeugt nur einen weiterhin separat reviewpflichtigen Kernel-Link.</p></div>
<div class='card'><h3>Zeit/Provenance eines Kernel-Links</h3><form method='post' action='/build238/edge-annotate'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='link_id' placeholder='Kernel Link-ID' required><input name='valid_from' placeholder='valid from'><input name='valid_to' placeholder='valid to'><input name='first_observed_at' placeholder='first observed'><input name='last_observed_at' placeholder='last observed'><select name='temporal_precision'><option>unknown</option><option>exact</option><option>day</option><option>month</option><option>year</option><option>range</option></select><input name='evidence_refs' placeholder='Evidence-Refs'><button>Link annotieren</button></form></div>
<div class='card'><h3>Graph-Snapshot</h3><form method='post' action='/build238/snapshot'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reproduzierbaren Graph-Snapshot erzeugen</button></form></div>
<div class='card'><h3>KI-Training fortführen</h3><form method='post' action='/build238/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='limit' type='number' min='1' max='200' value='50'><button>Reviewte Graph-Entscheidungen für Build 228 vorbereiten</button></form><p class='muted'>Pending Human Review; keine automatische Adapteraktivierung.</p></div>
</div></section>"""

    def _hyp(self,hid:str)->dict[str,Any]:
        r=self.db.one("SELECT * FROM graph_hypotheses_238 WHERE graph_hypothesis_id=?",(hid,));
        if not r: raise KeyError("graph hypothesis not found")
        return r
    def _hyp_payload(self,r:Mapping[str,Any])->dict[str,Any]:
        return {**dict(r),"evidence_refs":_loads(r.get("evidence_refs_json"),[]),"contradiction_refs":_loads(r.get("contradiction_refs_json"),[]),"review_status":"pending"}
    def _link(self,lid:str)->dict[str,Any]:
        r=self.db.one("SELECT * FROM canonical_links_235 WHERE link_id=?",(lid,));
        if not r: raise KeyError("kernel link not found")
        return r
    def _event(self,case_id:str,event_type:str,object_type:str,object_id:str,payload:Mapping[str,Any],actor:str)->None:
        prev=self.db.one("SELECT event_hash FROM build238_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(case_id,)); previous=prev["event_hash"] if prev else "GENESIS"; eid,now=new_id("evt238"),now_ts(); material={"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":object_type,"object_id":object_id,"actor":actor,"payload":dict(payload),"previous_hash":previous,"created_at":now}; h=_hash(material)
        self.db.execute("INSERT INTO build238_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,case_id,event_type,object_type,object_id,actor,dumps(dict(payload)),previous,h,now))
        try: self.audit.log(f"build238_{event_type}",object_type,object_id,case_id,dict(payload))
        except Exception: pass
