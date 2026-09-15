from __future__ import annotations
import hashlib, json, re
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()

SECRET = re.compile(r"(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)")

class Build192EvidenceGraphService:
    BUILD = "192.0"
    NODE_TYPES = {"person","identity","account","organization","place","event","media","document","claim","evidence","source","decision"}
    EDGE_TYPES = {"supports","contradicts","derived_from","mentions","about","identifies_candidate","valid_during","reviewed_by","same_as_candidate","related_to"}
    SOURCE_PROFILES = (
        ("wikidata_sparql","Wikidata Query Service","global","structured_connector","https://query.wikidata.org/sparql"),
        ("openalex_api","OpenAlex API","global","structured_connector","https://api.openalex.org"),
        ("orcid_public_api","ORCID Public API","global","credentialed_connector","https://pub.orcid.org/v3.0"),
        ("crossref_rest","Crossref REST API","global","structured_connector","https://api.crossref.org"),
    )

    def __init__(self, db: Any, audit: Any, *, identity: Any, capture: Any, source_ops: Any, global_sources: Any, ai: Any, actor: str = "system"):
        self.db, self.audit, self.identity, self.capture = db, audit, identity, capture
        self.source_ops, self.global_sources, self.ai, self.actor = source_ops, global_sources, ai, actor

    def seed_source_profiles(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "GRAPH SOURCES 192 ANLEGEN":
            raise PermissionError("explicit approval required")
        for sid, name, country, mode, endpoint in self.SOURCE_PROFILES:
            payload = {"source_id":sid,"name":name,"country":country,"mode":mode,"endpoint":endpoint,"candidate_only":True}
            self.db.execute("INSERT OR REPLACE INTO graph_source_profiles_192 VALUES(?,?,?,?,?,?,?,?,?)",
                            (sid,name,country,mode,endpoint,"DOCUMENTED",now_ts(),dumps(["terms_review","live_probe","parser_validation"]),_hash(payload)))
        return {"profiles":len(self.SOURCE_PROFILES),"production_active":0,"candidate_only":True}

    def create_graph(self, *, case_id: str, title: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"EVIDENCE GRAPH 192 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        gid, created = new_id("egraph192"), now_ts()
        policy = {"claim_evidence_separation":True,"automatic_identity_confirmation":False,"human_review_required":True}
        payload = {"graph_id":gid,"case_id":case_id,"title":title,"created_by":created_by,"created_at":created,"policy":policy}
        self.db.execute("INSERT INTO evidence_graphs_192 VALUES(?,?,?,?,?,?,?,?,?)",
                        (gid,case_id,title,created_by,created,1,"active",dumps(policy),_hash(payload)))
        self._event("graph_created",gid,payload)
        return payload | {"revision":1,"status":"active"}

    def add_node(self, *, graph_id: str, node_type: str, label: str, external_ref: str = "", attributes: Mapping[str,Any] | None = None,
                 source_refs: Sequence[str] = (), valid_from: str = "", valid_to: str = "", confirmation: str) -> dict[str, Any]:
        if confirmation != f"GRAPH NODE 192 {graph_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if node_type not in self.NODE_TYPES:
            raise ValueError("unsupported node type")
        nid, observed = new_id("gnode192"), now_ts()
        attrs = self._redact(dict(attributes or {}))
        review = "captured_candidate" if node_type in {"source","evidence"} else "candidate"
        payload = {"node_id":nid,"graph_id":graph_id,"node_type":node_type,"label":label,"external_ref":external_ref,
                   "attributes":attrs,"source_refs":list(source_refs),"valid_from":valid_from,"valid_to":valid_to,
                   "observed_at":observed,"review_status":review}
        self.db.execute("INSERT INTO evidence_graph_nodes_192 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (nid,graph_id,node_type,label,external_ref,dumps(attrs),dumps(list(source_refs)),valid_from,valid_to,observed,review,0,_hash(payload)))
        self._bump(graph_id)
        return payload

    def add_edge(self, *, graph_id: str, source_node_id: str, target_node_id: str, edge_type: str, source_refs: Sequence[str] = (),
                 confidence: float = .5, valid_from: str = "", valid_to: str = "", confirmation: str) -> dict[str, Any]:
        if confirmation != f"GRAPH EDGE 192 {graph_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if edge_type not in self.EDGE_TYPES:
            raise ValueError("unsupported edge type")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence")
        for nid in (source_node_id,target_node_id):
            if not self.db.one("SELECT node_id FROM evidence_graph_nodes_192 WHERE graph_id=? AND node_id=?",(graph_id,nid)):
                raise KeyError(nid)
        eid, observed = new_id("gedge192"), now_ts()
        payload = {"edge_id":eid,"graph_id":graph_id,"source":source_node_id,"target":target_node_id,"edge_type":edge_type,
                   "source_refs":list(source_refs),"confidence":confidence,"valid_from":valid_from,"valid_to":valid_to,
                   "observed_at":observed,"review_status":"candidate"}
        self.db.execute("INSERT INTO evidence_graph_edges_192 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (eid,graph_id,source_node_id,target_node_id,edge_type,dumps(list(source_refs)),confidence,valid_from,valid_to,observed,"candidate",_hash(payload)))
        self._bump(graph_id)
        return payload

    def create_claim(self, *, graph_id: str, claim_text: str, subject_node_id: str = "", object_node_id: str = "",
                     predicate: str = "", valid_from: str = "", valid_to: str = "", source_refs: Sequence[str] = (), confirmation: str) -> dict[str, Any]:
        if confirmation != f"GRAPH CLAIM 192 {graph_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        node = self.add_node(graph_id=graph_id,node_type="claim",label=claim_text,
                             attributes={"predicate":predicate,"subject_node_id":subject_node_id,"object_node_id":object_node_id},
                             source_refs=source_refs,valid_from=valid_from,valid_to=valid_to,
                             confirmation=f"GRAPH NODE 192 {graph_id} SPEICHERN")
        if subject_node_id:
            self.add_edge(graph_id=graph_id,source_node_id=node["node_id"],target_node_id=subject_node_id,edge_type="about",
                          source_refs=source_refs,confidence=.7,valid_from=valid_from,valid_to=valid_to,
                          confirmation=f"GRAPH EDGE 192 {graph_id} SPEICHERN")
        if object_node_id:
            self.add_edge(graph_id=graph_id,source_node_id=node["node_id"],target_node_id=object_node_id,edge_type="related_to",
                          source_refs=source_refs,confidence=.7,valid_from=valid_from,valid_to=valid_to,
                          confirmation=f"GRAPH EDGE 192 {graph_id} SPEICHERN")
        return node | {"claim_status":"unreviewed"}

    def attach_evidence(self, *, graph_id: str, claim_node_id: str, evidence_label: str, evidence_ref: str,
                        source_id: str, direction: str, confidence: float, confirmation: str) -> dict[str, Any]:
        if confirmation != f"GRAPH EVIDENCE 192 {graph_id} VERKNUEPFEN":
            raise PermissionError("explicit approval required")
        if direction not in {"support","contradict"}:
            raise ValueError("direction")
        e = self.add_node(graph_id=graph_id,node_type="evidence",label=evidence_label,external_ref=evidence_ref,
                          attributes={"source_id":source_id},source_refs=[source_id,evidence_ref],
                          confirmation=f"GRAPH NODE 192 {graph_id} SPEICHERN")
        edge = self.add_edge(graph_id=graph_id,source_node_id=e["node_id"],target_node_id=claim_node_id,
                             edge_type="supports" if direction=="support" else "contradicts",
                             source_refs=[source_id,evidence_ref],confidence=confidence,
                             confirmation=f"GRAPH EDGE 192 {graph_id} SPEICHERN")
        return {"evidence_node":e,"edge":edge,"claim_assessment":self.assess_claim(claim_node_id=claim_node_id)}

    def assess_claim(self, *, claim_node_id: str) -> dict[str, Any]:
        claim = self.db.one("SELECT graph_id FROM evidence_graph_nodes_192 WHERE node_id=? AND node_type='claim'",(claim_node_id,))
        if not claim:
            raise KeyError(claim_node_id)
        rows = self.db.all("SELECT edge_type,confidence,source_refs_json FROM evidence_graph_edges_192 WHERE graph_id=? AND target_node_id=? AND edge_type IN ('supports','contradicts')",(claim["graph_id"],claim_node_id))
        support = [float(r["confidence"]) for r in rows if r["edge_type"]=="supports"]
        contra = [float(r["confidence"]) for r in rows if r["edge_type"]=="contradicts"]
        sources = set()
        for r in rows:
            refs = json.loads(r["source_refs_json"] or "[]")
            if refs:
                sources.add(str(refs[0]))
        if support and contra: status = "contested"
        elif len(sources)>=2 and support and sum(support)/len(support)>=.7: status = "corroborated_candidate"
        elif contra and max(contra)>=.7: status = "contradicted_candidate"
        elif support: status = "supported_candidate"
        else: status = "unreviewed"
        return {"claim_node_id":claim_node_id,"status":status,"support_count":len(support),"contradiction_count":len(contra),
                "independent_source_candidates":len(sources),"claim_is_not_fact":True,"human_review_required":True}

    def import_temporal_identity(self, *, graph_id: str, identity_id: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"GRAPH IMPORT 192 {graph_id} IDENTITY":
            raise PermissionError("explicit approval required")
        ident = self.db.one("SELECT * FROM temporal_identities_191 WHERE identity_id=?",(identity_id,))
        if not ident: raise KeyError(identity_id)
        node = self.add_node(graph_id=graph_id,node_type="identity",label=ident["display_name"],external_ref=identity_id,
                             attributes={"identity_type":ident["identity_type"],"review_status":ident["review_status"]},
                             confirmation=f"GRAPH NODE 192 {graph_id} SPEICHERN")
        fact_nodes=[]
        for f in self.db.all("SELECT * FROM temporal_identity_facts_191 WHERE identity_id=?",(identity_id,)):
            refs=json.loads(f["source_refs_json"] or "[]")
            c=self.create_claim(graph_id=graph_id,claim_text=f"{f['fact_type']}: {f['fact_value']}",subject_node_id=node["node_id"],
                                predicate=f["fact_type"],valid_from=f["valid_from"],valid_to=f["valid_to"],source_refs=refs,
                                confirmation=f"GRAPH CLAIM 192 {graph_id} ANLEGEN")
            fact_nodes.append(c["node_id"])
        return {"identity_node_id":node["node_id"],"fact_claim_nodes":fact_nodes,"candidate_only":True}

    def view(self, *, graph_id: str, mode: str = "guided", as_of: str = "") -> dict[str, Any]:
        if mode not in {"guided","expert"}: raise ValueError("mode")
        nodes=[dict(r) for r in self.db.all("SELECT * FROM evidence_graph_nodes_192 WHERE graph_id=? ORDER BY observed_at",(graph_id,))]
        edges=[dict(r) for r in self.db.all("SELECT * FROM evidence_graph_edges_192 WHERE graph_id=? ORDER BY observed_at",(graph_id,))]
        if as_of:
            valid=lambda x:(not x.get("valid_from") or x["valid_from"]<=as_of) and (not x.get("valid_to") or x["valid_to"]>=as_of)
            nodes=[x for x in nodes if valid(x)]; edges=[x for x in edges if valid(x)]
        claims=[self.assess_claim(claim_node_id=n["node_id"]) for n in nodes if n["node_type"]=="claim"]
        base={"graph_id":graph_id,"mode":mode,"as_of":as_of,"node_count":len(nodes),"edge_count":len(edges),"claims":claims,
              "next_global_step":"3_verify_candidates","candidate_only":True}
        if mode=="guided":
            return base | {"summary":{"open_claims":sum(c["status"]=="unreviewed" for c in claims),"contested_claims":sum(c["status"]=="contested" for c in claims)},
                           "recommended_action":"Widersprüche und unbelegte Claims zuerst prüfen"}
        return base | {"nodes":nodes,"edges":edges,"opsec":{"local_processing":True,"external_uploads":False,"secrets_redacted":True}}

    def ai_next_steps(self, *, graph_id: str, question: str) -> dict[str, Any]:
        v=self.view(graph_id=graph_id,mode="guided")
        contested=[c for c in v["claims"] if c["status"]=="contested"]
        open_=[c for c in v["claims"] if c["status"]=="unreviewed"]
        actions=[]
        if contested: actions.append("Widersprechende Primärquellen zeitlich und sachlich vergleichen")
        if open_: actions.append("Unbelegte Claims mit einer Primärquelle und unabhängigen Zweitquelle prüfen")
        if not actions: actions.append("Zeitliche Gültigkeit und Quellenunabhängigkeit stichprobenartig prüfen")
        return {"question":question,"actions":actions,"contested_claims":len(contested),"unreviewed_claims":len(open_),
                "ai_output_is_not_fact":True,"automatic_action":False,"human_review_required":True}

    def dashboard(self) -> dict[str, Any]:
        n=lambda t:(self.db.one(f"SELECT COUNT(*) AS n FROM {t}") or {"n":0})["n"]
        return {"build":self.BUILD,"graphs":n("evidence_graphs_192"),"nodes":n("evidence_graph_nodes_192"),"edges":n("evidence_graph_edges_192"),
                "source_profiles":n("graph_source_profiles_192"),"opsec":{"local_processing":True,"external_uploads":False,"automatic_identity_confirmation":False}}

    def _bump(self, graph_id: str) -> None:
        self.db.execute("UPDATE evidence_graphs_192 SET revision=revision+1 WHERE graph_id=?",(graph_id,))

    def _redact(self, v: Any) -> Any:
        if isinstance(v,Mapping): return {k:("[REDACTED]" if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list): return [self._redact(x) for x in v]
        return v

    def _event(self, event_type: str, target: str, payload: Mapping[str,Any]) -> None:
        prev=self.db.one("SELECT event_sha256 FROM evidence_graph_events_192 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        ph=prev["event_sha256"] if prev else ""
        eid,created=new_id("egev192"),now_ts()
        eh=_hash({"id":eid,"type":event_type,"target":target,"payload":payload,"created":created,"prev":ph})
        self.db.execute("INSERT INTO evidence_graph_events_192 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,target,dumps(payload),created,self.actor,ph,eh))
