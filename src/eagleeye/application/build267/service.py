from __future__ import annotations
import hashlib,html,json,re,time,uuid
from collections import defaultdict,deque
from typing import Any
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit

def _now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _canon_path(nodes):
    a=tuple(nodes);b=tuple(reversed(nodes));return min(a,b)
def _strip_tracking_from_urls(text):
    # Only normalizes URLs embedded in a query; does not remove substantive search terms.
    def repl(m):
        u=m.group(0)
        try:
            p=urlsplit(u)
            kept=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                  if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid","fbclid","mc_cid","mc_eid","ref","ref_src"}]
            return urlunsplit((p.scheme,p.netloc,p.path,urlencode(kept),p.fragment))
        except Exception:return u
    out=re.sub(r"https?://[^\s\"')]+",repl,str(text or ""))
    return re.sub(r"\s+"," ",out).strip()
def _risk_class(points):
    return "high" if points>=6 else "moderate" if points>=3 else "low"

class Build267PathBrokerageService:
    BUILD="267.0"
    def __init__(self,db:Any,audit:Any,*,network266:Any,research263:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.network266=network266;self.research263=research263;self.compatibility=compatibility;self.training=training;self.actor=actor

    def analyze_paths(self,*,case_id,run_id,actor=None,max_hops=4,max_paths=200):
        actor=actor or self.actor
        nodes=self.db.all("SELECT * FROM network_nodes_266 WHERE case_id=? AND run_id=? ORDER BY node_id",(case_id,run_id))
        edges=self.db.all("SELECT * FROM network_edges_266 WHERE case_id=? AND run_id=? ORDER BY edge_id",(case_id,run_id))
        labels={n["node_id"]:n["label"] for n in nodes}
        adj=defaultdict(list)
        for e in edges:
            adj[e["source_node_id"]].append((e["target_node_id"],e))
            adj[e["target_node_id"]].append((e["source_node_id"],e))
        paths=[];seen=set();limit=max(1,min(int(max_paths),500));hops=max(2,min(int(max_hops),5))
        for start in sorted(labels):
            dq=deque([(start,[start],[])])
            while dq and len(paths)<limit:
                cur,npath,epath=dq.popleft()
                if len(epath)>=hops:continue
                for nxt,e in adj.get(cur,[]):
                    if nxt in npath:continue
                    nn=npath+[nxt];ee=epath+[e]
                    if len(ee)>=2:
                        key=_canon_path(nn)
                        if key not in seen:
                            seen.add(key)
                            refs=[];preds=[];unreviewed=0
                            for edge in ee:
                                preds.append(edge["predicate"])
                                refs.extend(json.loads(edge["evidence_refs_json"]))
                                relrefs=json.loads(edge["relation_refs_json"])
                                supported=False
                                for rr in relrefs:
                                    rv=self.db.one("SELECT decision FROM relation_reviews_266 WHERE relation_id=?",(rr,))
                                    if rv and rv["decision"]=="supported_candidate":supported=True
                                if not supported:unreviewed+=1
                            pid=_id("path267");pc="reviewed_path" if unreviewed==0 else "qualified_candidate_path"
                            payload={"nodes":nn,"edges":[x["edge_id"] for x in ee],"predicates":preds,"refs":refs,"unreviewed":unreviewed}
                            self.db.execute("INSERT INTO network_paths_267 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (pid,case_id,run_id,nn[0],nn[-1],_canon(nn),_canon([x["edge_id"] for x in ee]),_canon(preds),
                                 _canon(sorted(set(refs))),len(ee),unreviewed,pc,"analysis_basis",_now(),_hash(payload)))
                            paths.append({"path_id":pid,"nodes":nn,"labels":[labels.get(x,x) for x in nn],"predicates":preds,
                                          "hop_count":len(ee),"unreviewed_edge_count":unreviewed,"evidence_refs":sorted(set(refs))})
                    dq.append((nxt,nn,ee))
        metrics=self._brokerage(case_id,run_id,paths,labels,edges)
        brief=self._brief(case_id,run_id,paths,metrics,actor)
        self._event(case_id,"path_brokerage_analysis","research_run",run_id,actor,{"paths":len(paths),"brokers":len(metrics),"brief_id":brief["brief_id"]})
        return {"paths":paths,"brokerage":metrics,"brief":brief,"guilt_by_association":False,
                "coordination_inference":False,"intent_inference":False,"path_budget":limit}

    def _brokerage(self,case_id,run_id,paths,labels,edges):
        degree=defaultdict(int)
        for e in edges:
            degree[e["source_node_id"]]+=1;degree[e["target_node_id"]]+=1
        inter=defaultdict(int);total=len(paths)
        for p in paths:
            for n in p["nodes"][1:-1]:inter[n]+=1
        out=[]
        for nid,count in sorted(inter.items(),key=lambda kv:(-kv[1],labels.get(kv[0],""))):
            ratio=(count/total) if total else 0.0
            klass="high_bridge" if ratio>=0.5 and count>=2 else "moderate_bridge" if ratio>=0.25 else "observed_bridge"
            mid=_id("broker267");payload={"node":nid,"degree":degree[nid],"intermediate":count,"total":total,"ratio":round(ratio,6)}
            self.db.execute("INSERT INTO brokerage_metrics_267 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid,case_id,run_id,nid,labels.get(nid,nid),degree[nid],count,total,ratio,klass,"topology_only",_now(),_hash(payload)))
            out.append({"metric_id":mid,"node_id":nid,"label":labels.get(nid,nid),"degree":degree[nid],
                        "intermediate_path_count":count,"brokerage_ratio":ratio,"metric_class":klass,
                        "interpretation":"topological_bridge_only"})
        return out

    def _brief(self,case_id,run_id,paths,metrics,actor):
        ranked=sorted(paths,key=lambda p:(p["unreviewed_edge_count"],p["hop_count"],p["labels"]))
        top=[{"path_id":p["path_id"],"labels":p["labels"],"predicates":p["predicates"],"unreviewed_edges":p["unreviewed_edge_count"],
              "evidence_refs":p["evidence_refs"]} for p in ranked[:12]]
        brokers=[{"label":m["label"],"degree":m["degree"],"intermediate_path_count":m["intermediate_path_count"],
                  "brokerage_ratio":round(m["brokerage_ratio"],3),"meaning":"graph intermediary only"} for m in metrics[:10]]
        gaps=[];follow=[]
        for p in ranked[:8]:
            if p["unreviewed_edge_count"]:
                desc=" → ".join(p["labels"])
                gaps.append(f"Pfad {desc} enthält {p['unreviewed_edge_count']} nicht unabhängig reviewte Kante(n).")
                follow.append({"query":f'Prüfe unabhängige Primärquellen für den Netzwerkpfad "{desc}".',"requires_new_ok":True})
        summary=(f"{len(paths)} mehrstufige evidenzgebundene Pfadkandidaten wurden aus dem Build-266-Netzwerk verdichtet. "
                 f"{len(metrics)} Knoten erscheinen als Vermittler in mindestens einem Pfad. Brokerage ist ausschließlich eine graphische Strukturmetrik; "
                 "weder Koordination, Einfluss, Absicht noch Schuld werden daraus abgeleitet.")
        bid=_id("brief267");payload={"paths":top,"brokers":brokers,"gaps":gaps,"follow":follow}
        self.db.execute("INSERT INTO ai_path_briefs_267 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,case_id,run_id,len(paths),len(metrics),summary,_canon(top),_canon(brokers),_canon(gaps),_canon(follow),
             "analysis_basis",actor,_now(),_hash(payload)))
        return {"brief_id":bid,"summary":summary,"top_paths":top,"broker_candidates":brokers,
                "research_gaps":gaps,"followup_queries":follow}

    def analyze_query_risk(self,*,case_id,run_id,route_mode=''):
        rows=self.db.all("SELECT * FROM ai_research_queries_263 WHERE case_id=? AND run_id=? ORDER BY rowid",(case_id,run_id))
        allq=self.db.all("SELECT query_text FROM ai_research_queries_263 WHERE case_id=?",(case_id,))
        hashes=[_hash(_strip_tracking_from_urls(x["query_text"]).casefold()) for x in allq]
        risks=[]
        for q in rows:
            raw=str(q["query_text"]);minq=_strip_tracking_from_urls(raw);qh=_hash(minq.casefold())
            token_count=len(re.findall(r"\S+",minq))
            quoted=len(re.findall(r'"[^"]{8,}"',minq))
            sensitive=0
            sensitive+=len(re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",minq,re.I))*3
            sensitive+=len(re.findall(r"(?<!\d)(?:\+?\d[\d ()/-]{7,}\d)(?!\d)",minq))*2
            repeat=max(0,hashes.count(qh)-1)
            points=(1 if token_count>14 else 0)+(2 if quoted else 0)+sensitive+(2 if repeat>=2 else 1 if repeat else 0)
            rc=_risk_class(points);rid=_id("risk267")
            notes=[]
            if quoted:notes.append("long_exact_phrase")
            if sensitive:notes.append("sensitive_identifier_pattern")
            if repeat:notes.append("repeated_query_fingerprint")
            if raw!=minq:notes.append("tracking_parameters_removed_for_comparison")
            payload={"query_hash":qh,"tokens":token_count,"quoted":quoted,"sensitive":sensitive,"repeat":repeat,"points":points,"class":rc}
            self.db.execute("INSERT INTO opsec_query_risk_267 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid,case_id,run_id,q["query_id"],qh,token_count,quoted,sensitive,repeat,points,rc,_hash(minq),
                 ",".join(notes),_now(),_hash(payload)))
            risks.append({"query_id":q["query_id"],"risk_class":rc,"risk_points":points,"token_count":token_count,
                          "quoted_phrase_count":quoted,"sensitive_pattern_count":sensitive,"repeated_query_count":repeat,
                          "raw_query_stored_in_risk_record":False})
        direct=self.db.one("SELECT proxy_mode FROM opsec_sessions_265 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,run_id))
        effective_route=(route_mode or (direct["proxy_mode"] if direct else "direct"))
        direct_warning=int(effective_route=="direct")
        high=sum(1 for r in risks if r["risk_class"]=="high");moderate=sum(1 for r in risks if r["risk_class"]=="moderate")
        rec=[]
        if high:rec.append("Hoch korrelierbare Suchanfragen prüfen und, wo sachlich möglich, weniger einzigartige Identifikatoren gleichzeitig verwenden.")
        if direct_warning:rec.append("Direkte Route: öffentliche IP ist sichtbar; App beansprucht keine Netzwerkanonymität.")
        rec.append("Ephemeres Firefox-Profil verwendet Referrer-Minimierung, sofern Firefox-Profilmodus aktiv ist.")
        summary=f"{len(risks)} Queries analysiert: {high} hoch, {moderate} moderat korrelierbar. Der Report speichert Query-Hashes und Merkmale, nicht den sensitiven Query-Text."
        bid=_id("riskbrief267");payload={"count":len(risks),"high":high,"moderate":moderate,"direct":direct_warning,"rec":rec}
        self.db.execute("INSERT INTO opsec_run_risk_briefs_267 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,case_id,run_id,len(risks),high,moderate,direct_warning,1,summary,_canon(rec),"defensive_opsec",_now(),_hash(payload)))
        self._event(case_id,"query_correlation_risk","research_run",run_id,self.actor,{"high":high,"moderate":moderate,"direct_warning":bool(direct_warning)})
        return {"brief_id":bid,"summary":summary,"queries":risks,"recommendations":rec,
                "direct_ip_exposure_warning":bool(direct_warning),"referrer_minimization_expected":True,
                "automatic_ip_rotation":False}

    def execute_enhanced(self,*,case_id,run_id,confirmation,approved_by=None,provider="",max_queries=8,max_results_per_query=8,proxy_mode="direct",proxy_label=""):
        pre=self.analyze_query_risk(case_id=case_id,run_id=run_id,route_mode=proxy_mode)
        out=self.network266.execute_enhanced(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label)
        paths=self.analyze_paths(case_id=case_id,run_id=run_id,actor=approved_by or self.actor)
        out["path_brokerage_267"]=paths;out["query_correlation_risk_267"]=pre
        return out


    def stage_training_candidate(self,*,case_id,path_id,actor=None):
        row=self.db.one("SELECT * FROM network_paths_267 WHERE path_id=? AND case_id=?",(path_id,case_id))
        if not row:raise KeyError("path")
        if row["path_class"]!="reviewed_path" or row["unreviewed_edge_count"]!=0:
            raise PermissionError("only paths whose underlying relation edges were independently supported may stage training")
        return self.training.add_example(case_id=case_id,
            instruction="Explain an evidence-bound multi-hop network path without inferring intent, coordination, influence or guilt from topology alone.",
            response=_canon({"node_ids":json.loads(row["node_ids_json"]),"predicates":json.loads(row["predicates_json"]),
                             "hop_count":row["hop_count"],"interpretation":"observed_path_only"}),
            context={"build":"267.0","topology_not_intent":True,"guilt_by_association":False,"human_review_required":True},
            evidence_refs=json.loads(row["evidence_refs_json"]),language="de",source_type="build267_reviewed_network_path",
            source_ref=path_id,created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_path_benchmarks_267 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_path_benchmarks_267") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"multi_hop_path_fusion":True,"brokerage_topology_only":True,
                "large_data_path_summary":True,"automatic_model_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_267 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"query_correlation_risk":1,"referrer_minimization":1,"raw_query_copy_in_risk_table":0,
                "automatic_ip_rotation":0,"ip_spoofing":0,"disposable_email_generation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"267.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='network_paths_267'")),
           "ai_delta":a["reviewed_benchmarks"]>=36 and a["task_families"]>=18,
           "opsec_delta":o["verified_controls"]>=32 and o["query_correlation_risk"]==1,
           "capability_regression":"relationship_network_analysis_2" in caps and "opsec_cross_run_isolation_audit" in caps,
           "parent_build_gate":self.network266.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM ai_path_briefs_267 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['run_id'])}</code></td><td>{e(b['path_count'])}</td><td>{e(b['broker_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        risks=self.db.all("SELECT * FROM opsec_run_risk_briefs_267 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rrows="".join(f"<tr><td>{e(r['run_id'])}</td><td>{e(r['query_count'])}</td><td>{e(r['high_risk_queries'])}</td><td>{e(r['moderate_risk_queries'])}</td><td>{e(r['summary'])}</td></tr>" for r in risks)
        return f"""<section class='card'><h2>Network Paths & Brokerage · Build 267</h2>
        <p><b>Network → mehrstufige Pfade → graphische Vermittlerpositionen → Path Brief → gezielte Research Gaps.</b></p>
        <p>Ein Broker ist ausschließlich eine Strukturposition im Kandidatengraphen. Daraus wird keine Absicht, Steuerung, Kooperation oder Schuld abgeleitet.</p>
        <h3>AI Path Briefs</h3><table><tr><th>Run</th><th>Pfade</th><th>Broker-Kandidaten</th><th>Zusammenfassung</th></tr>{rows or "<tr><td colspan='4'>Noch keine Pfadanalyse.</td></tr>"}</table>
        <h3>Correlation-Risk Reports</h3><p>OPSEC-Audit speichert nur Query-Hashes/Merkmale. Trackingparameter werden für Vergleichszwecke entfernt. Ephemere Firefox-Profile minimieren Referrer; bei Fallback-Browsern wird dieser Schutz nicht behauptet.</p>
        <table><tr><th>Run</th><th>Queries</th><th>High</th><th>Moderate</th><th>Bewertung</th></tr>{rrows or "<tr><td colspan='5'>Noch kein Report.</td></tr>"}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build267_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt267");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build267_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
