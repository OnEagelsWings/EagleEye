from __future__ import annotations
import hashlib,html,json,re,time,uuid,os
from pathlib import Path
from typing import Any

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p): return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _norm_label(v):
    x=re.sub(r"\s+"," ",str(v or "").strip(" \t\r\n.,;:()[]{}"))
    return x
def _canon_key(v):
    x=_norm_label(v).casefold()
    x=re.sub(r"[^\wäöüß]+"," ",x)
    return re.sub(r"\s+"," ",x).strip()
def _type(label):
    l=label.casefold()
    if re.search(r"\b(gmbh|ag|kg|ltd|inc|llc|corp|company|stiftung|verein|e\.v\.)\b",l): return "organization"
    if re.search(r"\b(ministerium|behörde|agency|amt|regierung|bundestag|parlament)\b",l): return "public_body"
    return "entity_candidate"

REL_PATTERNS=[
    (re.compile(r"(?P<s>[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+){0,3})\s+(?:ist|war)\s+(?:Geschäftsführer(?:in)?|Direktor(?:in)?|Vorstand(?:smitglied)?|Mitglied)\s+(?:bei|der|von)\s+(?P<o>[A-ZÄÖÜ][^.;,\n]{2,100})"),"role_at"),
    (re.compile(r"(?P<s>[A-ZÄÖÜ][^.;,\n]{2,100})\s+(?:ist|war)\s+Lieferant\s+von\s+(?P<o>[A-ZÄÖÜ][^.;,\n]{2,100})"),"supplier_of"),
    (re.compile(r"(?P<s>[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+){0,3})\s+arbeitet(?:e)?\s+bei\s+(?P<o>[A-ZÄÖÜ][^.;,\n]{2,100})"),"worked_at"),
    (re.compile(r"(?P<s>[A-Z][A-Za-z0-9& .'-]{2,80})\s+(?:is|was)\s+(?:director|member|employee)\s+(?:of|at)\s+(?P<o>[A-Z][A-Za-z0-9& .'-]{2,100})",re.I),"role_at"),
]
REVIEW_DECISIONS={"supported_candidate","challenged_candidate","insufficient","reject"}

class Build266RelationshipNetworkService:
    BUILD="266.0"
    def __init__(self,db:Any,audit:Any,*,temporal265:Any,research263:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.temporal265=temporal265;self.research263=research263
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def analyze_run(self,*,case_id,run_id,actor=None):
        actor=actor or self.actor
        findings=self.db.all("SELECT * FROM ai_research_findings_263 WHERE case_id=? AND run_id=? ORDER BY created_at,finding_id",(case_id,run_id))
        existing={(r["subject"],r["predicate"],r["object"],tuple(json.loads(r["evidence_refs_json"]))) for r in self.db.all("SELECT * FROM relation_candidates_266 WHERE case_id=? AND run_id=?",(case_id,run_id))}
        created=[]
        for f in findings:
            text=f"{f['title']}. {f['snippet']}"
            for pat,predicate in REL_PATTERNS:
                for m in pat.finditer(text):
                    s=_norm_label(m.group("s"));o=_norm_label(m.group("o"))
                    if len(s)<2 or len(o)<2 or _canon_key(s)==_canon_key(o): continue
                    ev=[f["evidence_ref"]]; key=(s,predicate,o,tuple(ev))
                    if key in existing: continue
                    rid=_id("rel266");payload={"subject":s,"predicate":predicate,"object":o,"evidence_refs":ev,"source_urls":[f["url"]]}
                    self.db.execute("INSERT INTO relation_candidates_266 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (rid,case_id,run_id,s,predicate,o,_type(s),_type(o),_canon(ev),_canon([f["url"]]),"candidate","unreviewed",actor,_now(),_hash(payload)))
                    created.append(rid);existing.add(key)
        self._build_graph(case_id,run_id)
        brief=self._brief(case_id,run_id,actor)
        self._event(case_id,"relationship_analysis","research_run",run_id,actor,{"findings":len(findings),"new_relations":len(created),"brief_id":brief["brief_id"]})
        return {"finding_count":len(findings),"new_relation_candidates":len(created),"relations":self.list_relations(case_id,run_id),
                "network":self.network(case_id,run_id),"brief":brief,"automatic_verification":False,"coordination_inference":False}

    def add_relation_candidate(self,*,case_id,run_id,subject,predicate,object,evidence_refs,source_urls=None,actor=None):
        actor=actor or self.actor
        refs=[str(x).strip() for x in evidence_refs if str(x).strip()]
        if not refs: raise ValueError("evidence refs required")
        s,o=_norm_label(subject),_norm_label(object)
        if not s or not o or not predicate.strip():raise ValueError("subject predicate object required")
        rid=_id("rel266");payload={"subject":s,"predicate":predicate.strip(),"object":o,"evidence_refs":refs,"source_urls":source_urls or []}
        self.db.execute("INSERT INTO relation_candidates_266 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid,case_id,run_id,s,predicate.strip(),o,_type(s),_type(o),_canon(refs),_canon(source_urls or []),"candidate","unreviewed",actor,_now(),_hash(payload)))
        self._build_graph(case_id,run_id)
        return self.db.one("SELECT * FROM relation_candidates_266 WHERE relation_id=?",(rid,))

    def review_relation(self,*,case_id,relation_id,decision,rationale,reviewer=None):
        r=self.db.one("SELECT * FROM relation_candidates_266 WHERE relation_id=?",(relation_id,))
        if not r or r["case_id"]!=case_id:raise KeyError("relation")
        reviewer=reviewer or self.actor
        if reviewer==r["created_by"]:raise ValueError("independent reviewer required")
        if decision not in REVIEW_DECISIONS:raise ValueError("invalid decision")
        if self.db.one("SELECT review_id FROM relation_reviews_266 WHERE relation_id=?",(relation_id,)):raise ValueError("already reviewed")
        rid=_id("rr266");payload={"relation_id":relation_id,"decision":decision,"rationale":rationale}
        self.db.execute("INSERT INTO relation_reviews_266 VALUES(?,?,?,?,?,?,?,?)",(rid,relation_id,case_id,decision,rationale,reviewer,_now(),_hash(payload)))
        return {"review_id":rid,"decision":decision}

    def stage_training_candidate(self,*,case_id,relation_id,actor=None):
        r=self.db.one("SELECT * FROM relation_candidates_266 WHERE relation_id=?",(relation_id,))
        rv=self.db.one("SELECT * FROM relation_reviews_266 WHERE relation_id=?",(relation_id,))
        if not r or r["case_id"]!=case_id or not rv or rv["decision"]!="supported_candidate":raise PermissionError("supported independent review required")
        return self.training.add_example(case_id=case_id,
            instruction="Extract an explicit evidence-bound relationship candidate without inferring coordination, guilt, influence or identity beyond the source.",
            response=_canon({"subject":r["subject"],"predicate":r["predicate"],"object":r["object"],"status":"candidate"}),
            context={"build":"266.0","guilt_by_association":False,"automatic_verification":False},
            evidence_refs=json.loads(r["evidence_refs_json"]),language="de",source_type="build266_reviewed_relation",
            source_ref=relation_id,created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def list_relations(self,case_id,run_id):
        rows=self.db.all("SELECT * FROM relation_candidates_266 WHERE case_id=? AND run_id=? ORDER BY created_at,relation_id",(case_id,run_id))
        for r in rows:
            r["evidence_refs"]=json.loads(r["evidence_refs_json"]);r["source_urls"]=json.loads(r["source_urls_json"])
            r["review"]=self.db.one("SELECT decision,rationale,reviewer FROM relation_reviews_266 WHERE relation_id=?",(r["relation_id"],))
        return rows

    def _node(self,case_id,run_id,label,node_type):
        key=_canon_key(label)
        row=self.db.one("SELECT * FROM network_nodes_266 WHERE case_id=? AND run_id=? AND canonical_key=? AND node_type=?",(case_id,run_id,key,node_type))
        if row:return row["node_id"]
        nid=_id("node266");payload={"label":label,"type":node_type,"key":key}
        self.db.execute("INSERT INTO network_nodes_266 VALUES(?,?,?,?,?,?,?,?,?)",(nid,case_id,run_id,label,node_type,key,"candidate",_now(),_hash(payload)))
        return nid

    def _build_graph(self,case_id,run_id):
        relations=self.db.all("SELECT * FROM relation_candidates_266 WHERE case_id=? AND run_id=? ORDER BY rowid",(case_id,run_id))
        for r in relations:
            if self.db.one("SELECT edge_id FROM network_edges_266 WHERE relation_refs_json=?",( _canon([r["relation_id"]]),)):continue
            s=self._node(case_id,run_id,r["subject"],r["subject_type"]);o=self._node(case_id,run_id,r["object"],r["object_type"])
            eid=_id("edge266");payload={"source":s,"target":o,"predicate":r["predicate"],"refs":[r["relation_id"]]}
            self.db.execute("INSERT INTO network_edges_266 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (eid,case_id,run_id,s,o,r["predicate"],r["evidence_refs_json"],_canon([r["relation_id"]]),"candidate",_now(),_hash(payload)))

    def network(self,case_id,run_id):
        nodes=self.db.all("SELECT * FROM network_nodes_266 WHERE case_id=? AND run_id=? ORDER BY label",(case_id,run_id))
        edges=self.db.all("SELECT * FROM network_edges_266 WHERE case_id=? AND run_id=? ORDER BY rowid",(case_id,run_id))
        return {"nodes":nodes,"edges":edges,"guilt_by_association":False,"coordination_inference":False}

    def _brief(self,case_id,run_id,actor):
        net=self.network(case_id,run_id);rels=self.list_relations(case_id,run_id)
        degree={}
        labels={n["node_id"]:n["label"] for n in net["nodes"]}
        for e in net["edges"]:
            degree[e["source_node_id"]]=degree.get(e["source_node_id"],0)+1;degree[e["target_node_id"]]=degree.get(e["target_node_id"],0)+1
        top=[{"label":labels[k],"degree":v} for k,v in sorted(degree.items(),key=lambda kv:(-kv[1],labels.get(kv[0],"")))[:10]]
        unresolved=sum(1 for r in rels if not r["review"])
        follow=[]
        for r in rels[:6]:
            if not r["review"]:follow.append({"query":f'Prüfe unabhängige Primärquellen für die Beziehung "{r["subject"]}" — {r["predicate"]} — "{r["object"]}".',"requires_new_ok":True})
        summary=f"{len(net['nodes'])} Netzwerkknoten und {len(net['edges'])} evidenzgebundene Kandidatenkanten; {unresolved} Beziehungen sind noch nicht unabhängig reviewt. Netzwerk-Nähe wird nicht als Koordination, Einfluss oder Schuld interpretiert."
        bid=_id("brief266");payload={"nodes":len(net["nodes"]),"edges":len(net["edges"]),"unresolved":unresolved,"top":top,"followup":follow}
        self.db.execute("INSERT INTO ai_network_briefs_266 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,case_id,run_id,len(net["nodes"]),len(net["edges"]),unresolved,summary,_canon(top),_canon(follow),"analysis_basis",actor,_now(),_hash(payload)))
        return {"brief_id":bid,"summary":summary,"top_entities":top,"followup_queries":follow,"unresolved_relations":unresolved}

    def audit_opsec_isolation(self,*,case_id,run_id):
        row=self.db.one("SELECT * FROM opsec_sessions_265 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,run_id))
        if not row:return {"status":"no_opsec_session","direct_ip_exposure_warning":True}
        base=Path(self.db.path).parent
        profile=base/row["ephemeral_profile_relpath"];ph=_hash(str(profile))
        reuse=(self.db.one("SELECT COUNT(*) n FROM opsec_isolation_audits_266 WHERE profile_path_hash=? AND run_id<>?",(ph,run_id)) or {"n":0})["n"]
        def any_name(parts):
            if not profile.exists():return 0
            for p in profile.rglob("*"):
                if p.is_file() and any(x in p.name.casefold() for x in parts):return 1
            return 0
        cookies=any_name(("cookie",));cache=any_name(("cache",));history=any_name(("history","places.sqlite"))
        configured_proxy=bool(os.environ.get("EAGLEEYE_OUTBOUND_PROXY","").strip())
        direct=int(row["proxy_mode"]=="direct" or (row["proxy_mode"]=="user_configured_proxy" and not configured_proxy))
        status="pass" if not reuse and not (row["status"]=="cleaned" and (cookies or cache or history)) and not (row["proxy_mode"]=="user_configured_proxy" and not configured_proxy) else "fail"
        aid=_id("iso266");payload={"session_id":row["session_id"],"profile_hash":ph,"reuse":reuse,"cookies":cookies,"cache":cache,"history":history,"route":row["proxy_mode"],"direct_warning":direct}
        self.db.execute("INSERT INTO opsec_isolation_audits_266 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid,case_id,run_id,row["session_id"],ph,int(bool(reuse)),cookies,cache,history,row["proxy_mode"],direct,status,_now(),_hash(payload)))
        self._event(case_id,"opsec_isolation_audit","research_run",run_id,self.actor,{"status":status,"direct_route_warning":bool(direct),"profile_reuse":bool(reuse)})
        return {"audit_id":aid,"status":status,"cross_run_profile_reuse":bool(reuse),"cookie_files_present":cookies,
                "cache_files_present":cache,"history_files_present":history,"configured_route_mode":row["proxy_mode"],
                "direct_ip_exposure_warning":bool(direct),"automatic_ip_rotation":False,"synthetic_email_creation":False}

    def execute_enhanced(self,*,case_id,run_id,confirmation,approved_by=None,provider="",max_queries=8,max_results_per_query=8,proxy_mode="direct",proxy_label=""):
        if proxy_mode=="user_configured_proxy" and not os.environ.get("EAGLEEYE_OUTBOUND_PROXY","").strip():
            raise RuntimeError("user_configured_proxy selected, but EAGLEEYE_OUTBOUND_PROXY is not configured; refusing direct fallback")
        out=self.temporal265.execute_enhanced(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label)
        rel=self.analyze_run(case_id=case_id,run_id=run_id,actor=approved_by or self.actor)
        iso=self.audit_opsec_isolation(case_id=case_id,run_id=run_id)
        out["relationship_analysis_266"]=rel;out["opsec_isolation_266"]=iso
        return out

    def finalize_browser_context(self,*,case_id,run_id):
        cleaned=self.temporal265.finalize_browser_context(case_id=case_id,run_id=run_id)
        audit=self.audit_opsec_isolation(case_id=case_id,run_id=run_id)
        return {"cleanup":cleaned,"isolation_audit":audit}

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_relationship_benchmarks_266 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_relationship_benchmarks_266") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"relationship_fusion":True,"large_data_network_summary":True,"automatic_model_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_266 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"cross_run_isolation_audit":1,"direct_route_exposure_warning":1,
                "automatic_ip_rotation":0,"ip_spoofing":0,"disposable_email_generation":0,"user_configured_proxy_supported":1}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"266.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='relation_candidates_266'")),
           "ai_delta":a["reviewed_benchmarks"]>=34 and a["task_families"]>=17,
           "opsec_delta":o["verified_controls"]>=30 and o["cross_run_isolation_audit"]==1,
           "capability_regression":"temporal_contradiction_engine" in caps and "ephemeral_research_privacy" in caps,
           "parent_build_gate":self.temporal265.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM ai_network_briefs_266 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['run_id'])}</code></td><td>{e(b['node_count'])}</td><td>{e(b['edge_count'])}</td><td>{e(b['unresolved_relations'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all("SELECT * FROM opsec_isolation_audits_266 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        arows="".join(f"<tr><td>{e(a['run_id'])}</td><td>{e(a['configured_route_mode'])}</td><td>{'⚠ öffentliche IP sichtbar' if a['direct_ip_exposure_warning'] else 'konfigurierter Route-Kontext'}</td><td>{e(a['status'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Relationship & Network Analysis 2.0 · Build 266</h2>
        <p><b>Findings → explizite Beziehungskandidaten → deduplizierte Knoten → Kandidatenkanten → Network Brief.</b> Keine Beziehung aus bloßer Ko-Nennung; keine Schuld- oder Koordinationsschlussfolgerung.</p>
        <h3>AI Network Briefs</h3><table><tr><th>Run</th><th>Knoten</th><th>Kanten</th><th>Unreviewt</th><th>Zusammenfassung</th></tr>{rows or "<tr><td colspan='5'>Noch keine Netzwerkanalyse.</td></tr>"}</table>
        <h3>OPSEC Isolation Audit</h3><p>Jeder Run soll einen eigenen lokalen Browserkontext verwenden. Direkte Verbindung wird ausdrücklich als öffentlich IP-sichtbar markiert. Ein bereits von dir konfigurierter Proxy/VPN-Routing-Kontext kann genutzt werden; EagleEye erzeugt oder rotiert keine IP.</p>
        <table><tr><th>Run</th><th>Route</th><th>Exposure</th><th>Audit</th></tr>{arows or "<tr><td colspan='4'>Noch kein Isolation Audit.</td></tr>"}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build266_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt266");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build266_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
