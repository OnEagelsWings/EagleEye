from __future__ import annotations
import hashlib,json,re,time,uuid
from typing import Any
from urllib.parse import urlsplit,urlunsplit

DATE_PATTERNS=[
    (re.compile(r"\b(20\d{2}|19\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b"),"day"),
    (re.compile(r"\b([0-2]?\d|3[01])\.([01]?\d)\.(20\d{2}|19\d{2})\b"),"day"),
    (re.compile(r"\b(20\d{2}|19\d{2})\b"),"year"),
]
def _now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _canon_url(url):
    try:
        p=urlsplit(url.strip())
        host=(p.hostname or "").casefold()
        path=re.sub(r"/+$","",p.path or "/")
        return urlunsplit((p.scheme.casefold(),host,path,"",""))
    except Exception:return url.strip()

class Build264TimelineExecutionService:
    BUILD="264.0"
    def __init__(self,db:Any,audit:Any,*,research263:Any,compatibility:Any,ai_search:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.research263=research263;self.compatibility=compatibility;self.ai_search=ai_search;self.training=training;self.actor=actor

    def approve_and_execute(self,*,case_id,run_id,confirmation,approved_by=None,provider="",max_queries=8,max_results_per_query=8,browser_profile_path=""):
        if str(confirmation).strip().upper()!="OK":raise PermissionError("explicit OK required")
        run=self.db.one("SELECT * FROM ai_research_runs_263 WHERE run_id=? AND case_id=?",(run_id,case_id))
        if not run:raise KeyError("research run not found")
        if self.db.one("SELECT approval_id FROM ai_execution_approvals_264 WHERE run_id=?",(run_id,)):
            raise ValueError("run already approved/executed")
        who=approved_by or self.actor
        cfg=self.ai_search.get_config()
        selected=(provider or cfg.search_provider or "browser_queue").strip()
        if selected not in {"browser_queue","searxng","brave","ollama_web"}:raise ValueError("unsupported provider")
        mq=max(1,min(int(max_queries),12));mr=max(1,min(int(max_results_per_query),20))
        if selected!="browser_queue":
            status=self.ai_search.provider_status(selected)
            if not status.get("ready"):raise RuntimeError(status.get("detail") or "provider not ready")
        aid=_id("ap264");now=_now();payload={"run_id":run_id,"provider":selected,"max_queries":mq,"max_results_per_query":mr}
        self.db.execute("INSERT INTO ai_execution_approvals_264 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (aid,run_id,case_id,selected,mq,mr,"consumed_once",who,now,_hash(payload)))
        queries=self.db.all("SELECT * FROM ai_research_queries_263 WHERE run_id=? ORDER BY rowid LIMIT ?",(run_id,mq))
        if selected=="browser_queue":
            opened=self.research263.open_run(case_id=case_id,run_id=run_id,max_tabs=min(mq,8),actor=who,profile_path=browser_profile_path)
            summary=f"{len(queries)} vorbereitete Suchanfragen; Browser-Queue geöffnet. Keine Suchresultate wurden vorgetäuscht oder automatisch importiert."
            bid=self._batch(aid,run_id,case_id,selected,"opened_waiting_import",len(queries),0,0,summary,who)
            self._event(case_id,"approved_research_execution","ai_execution_batch",bid,who,{"provider":selected,"queries":len(queries),"results":0})
            return {"approval_id":aid,"batch_id":bid,"status":"opened_waiting_import","provider":selected,"browser":opened,"result_count":0,"dossier":self.research263.dossier(run_id)}
        raw=[]
        for q in queries:
            text=q["query_text"]
            if selected=="searxng":found=self.ai_search._search_searxng(text,mr)
            elif selected=="brave":found=self.ai_search._search_brave(text,mr)
            else:found=self.ai_search._search_ollama_web(text,mr)
            for item in found[:mr]:
                raw.append((q,item))
        unique={}
        for q,item in raw:
            url=str(item.get("url") or "").strip()
            if not url:continue
            key=_canon_url(url)
            if key not in unique:unique[key]={"query":q,"item":item,"duplicates":1}
            else:unique[key]["duplicates"]+=1
        inserted=[]
        for key,b in unique.items():
            item=b["item"];q=b["query"]
            title=str(item.get("title") or key)[:500];snippet=str(item.get("snippet") or item.get("description") or "")[:5000]
            stance="context_only"
            f=self.research263.add_finding(case_id=case_id,run_id=run_id,query_id=q["query_id"],title=title,url=str(item.get("url") or ""),
                snippet=snippet,source_class=q["source_class"],evidence_ref="",stance=stance,actor=who)
            inserted.append(f)
        bid=self._batch(aid,run_id,case_id,selected,"completed",len(queries),len(raw),len(inserted),
                        f"{len(raw)} Provider-Resultate wurden auf {len(inserted)} kanonische Fundstellen dedupliziert.",who)
        clusters=self._fusion(case_id,run_id,bid)
        timeline=self.reconstruct_timeline(case_id=case_id,run_id=run_id,batch_id=bid,actor=who)
        dossier=self.research263.dossier(run_id)
        self._event(case_id,"approved_research_execution","ai_execution_batch",bid,who,{"provider":selected,"queries":len(queries),"raw_results":len(raw),"deduplicated":len(inserted)})
        return {"approval_id":aid,"batch_id":bid,"status":"completed","provider":selected,"raw_result_count":len(raw),
                "deduplicated_count":len(inserted),"fusion_clusters":len(clusters),"timeline_candidates":len(timeline["events"]),
                "timeline_conflicts":len(timeline["conflicts"]),"dossier":dossier,"bounded_execution":True}

    def _batch(self,aid,run_id,cid,provider,status,qc,rc,dc,summary,actor):
        bid=_id("batch264");now=_now();payload={"provider":provider,"status":status,"query_count":qc,"result_count":rc,"deduplicated_count":dc,"summary":summary}
        self.db.execute("INSERT INTO ai_execution_batches_264 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,aid,run_id,cid,provider,status,qc,rc,dc,summary,actor,now,_hash(payload)))
        return bid

    def _fusion(self,case_id,run_id,batch_id):
        rows=self.db.all("SELECT * FROM ai_research_findings_263 WHERE run_id=? ORDER BY created_at,finding_id",(run_id,))
        groups={}
        for r in rows:
            key=_canon_url(r["url"])
            g=groups.setdefault(key,{"rows":[],"hosts":set(),"stances":{}})
            g["rows"].append(r)
            try:g["hosts"].add(urlsplit(r["url"]).hostname or "")
            except:pass
            g["stances"][r["stance"]]=g["stances"].get(r["stance"],0)+1
        out=[]
        for key,g in groups.items():
            first=g["rows"][0];cid=_id("cluster264");now=_now()
            refs=[x["finding_id"] for x in g["rows"]];payload={"cluster_key":key,"refs":refs,"stances":g["stances"]}
            self.db.execute("INSERT INTO ai_fusion_clusters_264 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid,batch_id,run_id,case_id,key,key,first["title"],_canon(sorted(g["hosts"])),_canon(refs),_canon(g["stances"]),now,_hash(payload)))
            out.append(cid)
        return out

    def _extract_dates(self,text):
        out=[]
        for pat,precision in DATE_PATTERNS:
            for m in pat.finditer(text or ""):
                if precision=="day":
                    g=m.groups()
                    if len(g)==3 and len(g[0])==4:date=f"{g[0]}-{g[1].zfill(2)}-{g[2].zfill(2)}"
                    else:date=f"{g[2]}-{g[1].zfill(2)}-{g[0].zfill(2)}"
                else:date=f"{m.group(1)}"
                if (date,precision) not in out:out.append((date,precision))
        # If exact day exists for a year, suppress the duplicate bare year.
        years={d[:4] for d,p in out if p=="day"}
        return [(d,p) for d,p in out if not (p=="year" and d in years)]

    def reconstruct_timeline(self,*,case_id,run_id,batch_id="",actor=None):
        actor=actor or self.actor
        findings=self.db.all("SELECT * FROM ai_research_findings_263 WHERE run_id=? AND case_id=? ORDER BY created_at",(run_id,case_id))
        events=[]
        for f in findings:
            dates=self._extract_dates((f["title"] or "")+" "+(f["snippet"] or ""))
            for date,precision in dates[:6]:
                eid=_id("time264");text=((f["title"] or "")+": "+(f["snippet"] or ""))[:1200];refs=[f["evidence_ref"]]
                payload={"date":date,"precision":precision,"text":text,"evidence_refs":refs,"source_refs":[f["url"]]}
                self.db.execute("INSERT INTO temporal_events_264 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (eid,case_id,run_id,batch_id,date,precision,text,_canon(refs),_canon([f["url"]]),"candidate","unreviewed",actor,_now(),_hash(payload)))
                events.append({"event_id":eid,**payload})
        conflicts=[]
        norm=lambda s:re.sub(r"\W+"," ",s.casefold())[:160]
        for i,a in enumerate(events):
            for b in events[i+1:]:
                if a["date"]!=b["date"] and len(set(norm(a["text"]).split()) & set(norm(b["text"]).split()))>=6:
                    cid=_id("tconf264");rat="Ähnliche Ereignisbeschreibung mit unterschiedlichen Datumsangaben; manueller Abgleich erforderlich."
                    payload={"a":a["event_id"],"b":b["event_id"],"type":"date_mismatch"}
                    self.db.execute("INSERT INTO temporal_conflicts_264 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (cid,case_id,run_id,a["event_id"],b["event_id"],"date_mismatch",rat,"candidate",_now(),_hash(payload)))
                    conflicts.append({"conflict_id":cid,**payload})
        self._event(case_id,"timeline_reconstructed","research_run",run_id,actor,{"events":len(events),"conflicts":len(conflicts)})
        return {"events":events,"conflicts":conflicts,"automatic_causal_inference":False}

    def summary(self,case_id,run_id):
        batch=self.db.one("SELECT * FROM ai_execution_batches_264 WHERE run_id=? ORDER BY rowid DESC LIMIT 1",(run_id,))
        clusters=self.db.all("SELECT * FROM ai_fusion_clusters_264 WHERE run_id=? ORDER BY rowid",(run_id,))
        events=self.db.all("SELECT * FROM temporal_events_264 WHERE run_id=? ORDER BY event_date,rowid",(run_id,))
        conflicts=self.db.all("SELECT * FROM temporal_conflicts_264 WHERE run_id=? ORDER BY rowid",(run_id,))
        return {"batch":batch,"clusters":clusters,"timeline":events,"conflicts":conflicts,"dossier":self.research263.dossier(run_id),
                "automatic_causal_inference":False,"unbounded_background_search":False}


    def execute_last_pending(self,*,case_id,confirmation,approved_by=None,provider="",max_queries=8,max_results_per_query=8):
        row=self.db.one("""SELECT r.* FROM ai_research_runs_263 r
            LEFT JOIN ai_execution_approvals_264 a ON a.run_id=r.run_id
            WHERE r.case_id=? AND a.run_id IS NULL ORDER BY r.created_at DESC,r.rowid DESC LIMIT 1""",(case_id,))
        if not row:raise ValueError("Kein vorbereiteter Recherchelauf wartet auf OK")
        return self.approve_and_execute(case_id=case_id,run_id=row["run_id"],confirmation=confirmation,approved_by=approved_by,
            provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query)

    def render_workspace_panel(self,*,case_id,csrf):
        import html
        e=lambda v:html.escape(str(v or ""),quote=True)
        pending=self.db.all("""SELECT r.run_id,r.user_request,r.source_profile,r.created_at FROM ai_research_runs_263 r
            LEFT JOIN ai_execution_approvals_264 a ON a.run_id=r.run_id
            WHERE r.case_id=? AND a.run_id IS NULL ORDER BY r.created_at DESC LIMIT 10""",(case_id,))
        batches=self.db.all("SELECT * FROM ai_execution_batches_264 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        prow="".join(f"<tr><td><code>{e(r['run_id'])}</code></td><td>{e(r['user_request'][:130])}</td><td>{e(r['source_profile'])}</td><td><form method='post' action='/build264/execute'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='run_id' value='{e(r['run_id'])}'><input type='hidden' name='confirmation' value='OK'><button>OK · selbstständig abarbeiten</button></form></td></tr>" for r in pending)
        brows="".join(f"<tr><td>{e(b['provider'])}</td><td>{e(b['status'])}</td><td>{e(b['query_count'])}</td><td>{e(b['result_count'])}</td><td>{e(b['deduplicated_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in batches)
        return f"""<section class='card'><h2>AI Execution & Timeline 264</h2>
        <p><b>Vorbereiten → OK → Abarbeiten → Deduplizieren → Zusammenführen → Timeline → Dossier.</b></p>
        <p>Mit OK erhält der AI-Ermittler eine einmalige, fallgebundene Freigabe. Standardbudget: 8 Queries × 8 Resultate. Kein unbegrenzter Hintergrundlauf.</p>
        <h3>Wartet auf OK</h3><table><tr><th>Run</th><th>Auftrag</th><th>Profil</th><th>Freigabe</th></tr>{prow or "<tr><td colspan='4'>Kein offener Recherchelauf.</td></tr>"}</table>
        <h3>Execution Batches</h3><table><tr><th>Provider</th><th>Status</th><th>Queries</th><th>Rohresultate</th><th>Dedupliziert</th><th>Zusammenfassung</th></tr>{brows or "<tr><td colspan='6'>Noch kein Batch.</td></tr>"}</table>
        <p><b>Provider-Verhalten:</b> SearXNG/Brave/Ollama-Web können bei vorhandener Konfiguration Resultate selbst einlesen. Browser Queue öffnet die Suchläufe und wartet ehrlich auf Fundstellen-Import.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_timeline_benchmarks_264 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_timeline_benchmarks_264") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"bounded_execution_after_ok":True,"automatic_model_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_264 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"unbounded_background_search":0,"access_control_bypass":0,"automatic_causal_inference":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"264.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='temporal_events_264'")),
           "ai_delta":a["reviewed_benchmarks"]>=30 and a["task_families"]>=15,"opsec_delta":o["verified_controls"]>=24,
           "capability_regression":"ai_research_dossier_execution" in caps and "evidence_quality_engine" in caps,
           "parent_build_gate":self.research263.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build264_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt264");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build264_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
