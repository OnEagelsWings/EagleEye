from __future__ import annotations
import hashlib,html,json,re,time,uuid,webbrowser,os,shutil,subprocess
from typing import Any
from urllib.parse import quote_plus,urlparse
from eagleeye_pro.core.database import loads

SOURCE_LEVEL={"primary","secondary","tertiary","unknown"}
TEMPORAL={"contemporaneous","near_contemporaneous","retrospective","unknown"}
DIRECTNESS={"direct","indirect","hearsay","unknown"}
ORIGINALITY={"original","certified_copy","mirror","syndicated","excerpt","unknown"}
AUTHENTICITY={"authenticated","partially_authenticated","uncertain","disputed"}
INDEPENDENCE={"independent","partially_independent","dependent","unknown"}
CORROBORATION={"corroborated","partially_corroborated","isolated","contradicted","unknown"}
PROVENANCE={"strong_provenance","partial_provenance","weak_provenance","unknown"}
QUALITY_REVIEW={"accepted_quality_profile","needs_more_provenance","integrity_review_required","dependency_review_required","rejected_assessment"}
STANCE={"supports","contradicts","context_only","neutral"}
SEARCH_HOSTS={"www.google.com","www.google.de","www.bing.com","duckduckgo.com","search.brave.com"}
BLOCKED=re.compile(r"(?i)\b(bypass|umgeh\w*|captcha|credential|passwort|password|private account|privates konto|paywall knacken|login umgehen)\b")
RESEARCH_CMD=re.compile(r"(?i)^\s*(suche|recherchiere|finde|search|durchsuche)\b")

GERMAN_DOMAINS=[
 ("bundestag.de","parliamentary_primary"),("dip.bundestag.de","parliamentary_primary"),
 ("bundesarchiv.de","archive_primary"),("bundesregierung.de","government_primary"),
 ("bpb.de","public_context"),("fragdenstaat.de","foia_public"),
 ("deutschlandfunk.de","media"),("tagesschau.de","media"),
]

def _open_generated_search_url(url:str)->str:
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in SEARCH_HOSTS:
        return "blocked"
    candidates=[]
    env=os.environ.get("FIREFOX_PATH","").strip()
    if env:candidates.append(env)
    found=shutil.which("firefox") or shutil.which("firefox.exe")
    if found:candidates.append(found)
    if os.name=="nt":
        for base in (os.environ.get("PROGRAMFILES"),os.environ.get("PROGRAMFILES(X86)"),os.environ.get("LOCALAPPDATA")):
            if base:candidates.append(str(__import__("pathlib").Path(base)/"Mozilla Firefox"/"firefox.exe"))
    for c in candidates:
        try:
            if os.path.isfile(c):
                subprocess.Popen([c,"-new-tab",url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
                return "firefox"
        except Exception:
            pass
    try:
        return "default" if webbrowser.open_new_tab(url) else "unavailable"
    except Exception:
        return "unavailable"


def _open_generated_search_urls_ephemeral(urls,profile_path):
    safe=[]
    for url in urls:
        p=urlparse(url)
        if p.scheme=="https" and p.hostname in SEARCH_HOSTS:safe.append(url)
    if not safe:return {"mode":"blocked","opened":0}
    candidates=[]
    env=os.environ.get("FIREFOX_PATH","").strip()
    if env:candidates.append(env)
    found=shutil.which("firefox") or shutil.which("firefox.exe")
    if found:candidates.append(found)
    if os.name=="nt":
        for base in (os.environ.get("PROGRAMFILES"),os.environ.get("PROGRAMFILES(X86)"),os.environ.get("LOCALAPPDATA")):
            if base:candidates.append(str(__import__("pathlib").Path(base)/"Mozilla Firefox"/"firefox.exe"))
    for c in candidates:
        try:
            if os.path.isfile(c):
                subprocess.Popen([c,"-no-remote","-profile",str(profile_path),*safe],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
                return {"mode":"firefox_ephemeral_profile","opened":len(safe)}
        except Exception:pass
    opened=0
    for u in safe:
        try:
            if webbrowser.open_new_tab(u):opened+=1
        except Exception:pass
    return {"mode":"default_browser_fallback","opened":opened}

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p): return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _list(v):
    if v is None:return []
    if isinstance(v,(list,tuple,set)):return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";",",").split(",") if x.strip()]

class Build263EvidenceResearchService:
    BUILD="263.0"
    def __init__(self,db:Any,audit:Any,*,tasks:Any,case_state:Any,compatibility:Any,training:Any,opsec:Any,targets:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.tasks=tasks;self.case_state=case_state;self.compatibility=compatibility
        self.training=training;self.opsec=opsec;self.targets=targets;self.actor=actor

    def _case(self,cid):
        r=self.db.one("SELECT case_id,title FROM cases WHERE case_id=?",(cid,))
        if not r:raise KeyError("case not found")
        return r
    def _target(self,tid):
        return self.targets.get_target(tid)
    def is_research_command(self,message:str)->bool:
        return bool(RESEARCH_CMD.search(message or ""))

    def _resolve_target(self,case_id,request,target_id=""):
        if target_id:
            t=self._target(target_id)
            if t.get("case_id")!=case_id:raise ValueError("target not in active case")
            return t
        candidates=self.db.all("SELECT * FROM targets WHERE case_id=? ORDER BY created_at",(case_id,))
        lowered=(request or "").casefold()
        matched=[x for x in candidates if str(x.get("name") or "").casefold() in lowered and str(x.get("name") or "").strip()]
        if len(matched)==1:
            t=matched[0]
            for k in ("aliases_json","emails_json","usernames_json","locations_json","companies_json","domains_json"):
                t[k]=loads(t.get(k),[])
            return t
        return None

    def _urls(self,q):
        e=quote_plus(q)
        return [
          {"engine":"Google","url":"https://www.google.com/search?q="+e},
          {"engine":"Bing","url":"https://www.bing.com/search?q="+e},
          {"engine":"DuckDuckGo","url":"https://duckduckgo.com/?q="+e},
          {"engine":"Brave","url":"https://search.brave.com/search?q="+e},
        ]

    def _plan(self,request,target=None):
        r=" ".join((request or "").split())
        if BLOCKED.search(r):raise ValueError("Auftrag enthält eine unzulässige Umgehungs-/Zugriffsanforderung")
        out=[]; seen=set()
        def add(q,obj,sc):
            q=" ".join(q.split()).strip()
            if q and q.casefold() not in seen and len(out)<12:
                seen.add(q.casefold());out.append((q,obj,sc))
        german=bool(re.search(r"(?i)\b(deutsch(?:e|en|er)?|deutschland|german)\b",r))
        if target:
            name=str(target.get("name") or "").strip()
            anchors=[]
            for k in ("companies_json","locations_json","aliases_json","usernames_json","domains_json"):
                vals=target.get(k,[]) if isinstance(target.get(k),list) else loads(target.get(k),[])
                anchors += [str(x) for x in vals[:2]]
            add(f'"{name}"',"Allgemeine öffentliche Identitäts- und Kontextspuren","person_public_web")
            add(f'"{name}" filetype:pdf',"Öffentliche Dokumente, Berichte und Publikationen","documents")
            add(f'"{name}" (Interview OR Presse OR Vortrag OR Publikation)',"Medien-/Publikationskontext","media")
            add(f'"{name}" (Firma OR Geschäftsführer OR Vorstand OR Organisation)',"Öffentliche Organisations- und Berufsbezüge","corporate_public")
            for a in anchors[:4]:add(f'"{name}" "{a}"',"Disambiguierung über bereits bekannte öffentliche Anker","person_disambiguation")
            add(f'"{name}" (nicht OR anderer OR Namensvetter)',"Gegenbelege und Namensdoppler","counterevidence")
            if german:
                for dom,sc in GERMAN_DOMAINS[:4]:add(f'site:{dom} "{name}"',"Deutsche institutionelle/öffentliche Quelle",sc)
            profile="person_osint_de" if german else "person_osint_public"
        else:
            # Keep the analyst's wording as semantic anchor, but remove imperative padding.
            topic=re.sub(r"(?i)^\s*(suche|recherchiere|finde|search|durchsuche)\s*","",r).strip()
            topic=re.sub(r"(?i)^alle\s+möglichen\s+belege\s+","",topic).strip()
            topic=re.sub(r"(?i)^belege\s+","",topic).strip()
            topic=re.sub(r"(?i)^in\s+deutschen\s+quellen\s+(?:für|zu)\s+","",topic).strip()
            topic=re.sub(r"(?i)^für\s+","",topic).strip()
            add(topic,"Breite Ausgangssuche","public_web")
            add(f'"{topic}" filetype:pdf',"Dokumente und Berichte","documents")
            add(f'"{topic}" (Bericht OR Dokument OR Akte OR Untersuchung OR Untersuchungsausschuss)',"Primär-/Dokumentenspuren","documents")
            if german:
                for dom,sc in GERMAN_DOMAINS:
                    add(f'site:{dom} {topic}',f"Deutsche Quelle: {dom}",sc)
                profile="german_public_sources"
            else:
                add(f'{topic} (archive OR report OR records)',"Archive und Primärquellen","archive")
                add(f'{topic} (investigation OR evidence OR documents)',"Investigative Gegenprüfung","investigative_media")
                profile="public_sources"
        return profile,out

    def create_research_run(self,*,case_id,user_request,target_id="",auto_open=False,actor=None):
        self._case(case_id);actor=actor or self.actor
        if not self.is_research_command(user_request):raise ValueError("Rechercheauftrag muss mit Suche/Recherchiere/Finde/Durchsuche beginnen")
        target=self._resolve_target(case_id,user_request,target_id)
        profile,plan=self._plan(user_request,target)
        rid=_id("airun263");scope="person" if target else "case";now=_now()
        payload={"case_id":case_id,"target_id":target.get("target_id","") if target else "","request":user_request,"scope":scope,"source_profile":profile,"auto_open":bool(auto_open)}
        self.db.execute("INSERT INTO ai_research_runs_263 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (rid,case_id,payload["target_id"],user_request.strip(),scope,profile,"planned",int(bool(auto_open)),actor,now,_hash(payload)))
        queries=[]
        for q,obj,sc in plan:
            qid=_id("aiq263");urls=self._urls(q);qp={"query":q,"objective":obj,"source_class":sc,"urls":urls}
            self.db.execute("INSERT INTO ai_research_queries_263 VALUES(?,?,?,?,?,?,?,?,?,?)",
                (qid,rid,case_id,q,obj,sc,_canon(urls),"planned",now,_hash(qp)))
            queries.append({"query_id":qid,**qp})
        self._event(case_id,"research_run_created","ai_research_run",rid,actor,{"scope":scope,"queries":len(queries),"target_id":payload["target_id"]})
        result={"run_id":rid,"scope_type":scope,"target_id":payload["target_id"],"source_profile":profile,"queries":queries,
                "automatic_background_collection":False,"browser_open_requested":bool(auto_open)}
        if auto_open:result["browser_open"]=self.open_run(case_id=case_id,run_id=rid,max_tabs=8,actor=actor)
        self.generate_dossier(case_id=case_id,run_id=rid,actor=actor)
        return result

    def open_run(self,*,case_id,run_id,max_tabs=8,actor=None,profile_path=""):
        run=self.db.one("SELECT * FROM ai_research_runs_263 WHERE run_id=?",(run_id,))
        if not run or run["case_id"]!=case_id:raise KeyError("research run not found")
        actor=actor or self.actor;opened=[];limit=max(1,min(int(max_tabs),8))
        rows=self.db.all("SELECT query_id,urls_json FROM ai_research_queries_263 WHERE run_id=? ORDER BY rowid",(run_id,))
        selected=[]
        for row in rows[:limit]:
            urls=json.loads(row["urls_json"]);u=urls[0]["url"] if urls else "";p=urlparse(u)
            if p.scheme=="https" and p.hostname in SEARCH_HOSTS:selected.append((row["query_id"],u))
        if profile_path:
            res=_open_generated_search_urls_ephemeral([u for _,u in selected],profile_path)
            for qid,u in selected:opened.append({"query_id":qid,"url":u,"opened":res["opened"]>0,"browser":res["mode"]})
        else:
            for qid,u in selected:
                mode=_open_generated_search_url(u);opened.append({"query_id":qid,"url":u,"opened":mode not in {"blocked","unavailable"},"browser":mode})
        self._event(case_id,"research_browser_open","ai_research_run",run_id,actor,{"tabs":len(opened),"ephemeral_profile":bool(profile_path)})
        return {"tabs_requested":len(opened),"tabs":opened,"user_initiated":True,"background_collection":False,"preferred_browser":"firefox","ephemeral_profile":bool(profile_path)}

    def add_finding(self,*,case_id,run_id,query_id,title,url,snippet,source_class="public_web",evidence_ref="",stance="context_only",actor=None):
        self._case(case_id);actor=actor or self.actor
        run=self.db.one("SELECT case_id FROM ai_research_runs_263 WHERE run_id=?",(run_id,))
        q=self.db.one("SELECT case_id FROM ai_research_queries_263 WHERE query_id=? AND run_id=?",(query_id,run_id))
        if not run or not q or run["case_id"]!=case_id or q["case_id"]!=case_id:raise ValueError("run/query case mismatch")
        p=urlparse((url or "").strip())
        if p.scheme not in {"http","https"} or not p.hostname or p.hostname in {"127.0.0.1","localhost"}:raise ValueError("public http/https URL required")
        if stance not in STANCE:raise ValueError("invalid stance")
        fid=_id("aif263");ev=(evidence_ref or f"lead:{_hash(url)[:16]}").strip();now=_now()
        payload={"title":title.strip(),"url":url.strip(),"snippet":snippet.strip(),"source_class":source_class,"evidence_ref":ev,"stance":stance}
        self.db.execute("INSERT INTO ai_research_findings_263 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid,run_id,query_id,case_id,payload["title"],payload["url"],payload["snippet"],source_class,ev,stance,actor,now,_hash(payload)))
        self._event(case_id,"research_finding_added","ai_research_finding",fid,actor,{"run_id":run_id,"stance":stance,"evidence_ref":ev})
        dossier=self.generate_dossier(case_id=case_id,run_id=run_id,actor=actor)
        return {"finding_id":fid,**payload,"dossier_revision":dossier["revision_no"]}

    def generate_dossier(self,*,case_id,run_id,actor=None):
        actor=actor or self.actor
        run=self.db.one("SELECT * FROM ai_research_runs_263 WHERE run_id=?",(run_id,))
        if not run or run["case_id"]!=case_id:raise KeyError("research run not found")
        findings=self.db.all("SELECT * FROM ai_research_findings_263 WHERE run_id=? ORDER BY created_at,finding_id",(run_id,))
        queries=self.db.all("SELECT query_text,objective,source_class FROM ai_research_queries_263 WHERE run_id=? ORDER BY rowid",(run_id,))
        sup=[x for x in findings if x["stance"]=="supports"];con=[x for x in findings if x["stance"]=="contradicts"];ctx=[x for x in findings if x["stance"] in {"context_only","neutral"}]
        if findings:
            summary=(f"Recherchelauf mit {len(findings)} erfassten Fundstellen: {len(sup)} unterstützend, {len(con)} widersprechend, "
                     f"{len(ctx)} Kontext/neutral. Fundstellen sind Recherchebelege bzw. Leads entsprechend ihrer Evidence-Referenz; "
                     "die Zusammenfassung verifiziert keine Hypothese automatisch.")
        else:
            summary=(f"Rechercheplan mit {len(queries)} Suchläufen wurde vorbereitet. Noch keine Fundstellen wurden in den Fall übernommen. "
                     "Dieses Dossier ist daher zunächst eine Recherche- und Hypothesengrundlage, kein Tatsachenbericht.")
        hypothesis=[{"type":"candidate_hypothesis_basis","statement":"Die Ausgangsfrage ist anhand unabhängiger Primär- und Sekundärquellen zu prüfen.",
                     "support_refs":[x["evidence_ref"] for x in sup],"contradiction_refs":[x["evidence_ref"] for x in con],
                     "status":"unverified"}]
        gaps=[]
        if not findings:gaps.append("Suchergebnisse prüfen und relevante Fundstellen mit URL/Snippet übernehmen.")
        if not any(x["source_class"] in {"archive_primary","government_primary","parliamentary_primary"} for x in findings):
            gaps.append("Unabhängige Primärquelle bzw. amtliche/archivalische Quelle fehlt oder wurde noch nicht erfasst.")
        sources={}
        for x in findings:sources[x["source_class"]]=sources.get(x["source_class"],0)+1
        last=self.db.one("SELECT MAX(revision_no) n FROM ai_research_dossiers_263 WHERE run_id=?",(run_id,))
        revision=int((last or {"n":0}).get("n") or 0)+1
        did=_id("dos263");now=_now();title=("PersonenOSINT-Dossier" if run["scope_type"]=="person" else "Recherche-Dossier")+": "+run["user_request"][:140]
        payload={"title":title,"summary":summary,"hypothesis":hypothesis,"gaps":gaps,"sources":sources,"finding_count":len(findings)}
        self.db.execute("INSERT INTO ai_research_dossiers_263 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (did,run_id,case_id,revision,title,summary,_canon(hypothesis),_canon(gaps),_canon(sources),len(findings),
             "research_basis",actor,now,_hash({**payload,"revision":revision})))
        self._event(case_id,"research_dossier_created","ai_research_dossier",did,actor,{"run_id":run_id,"finding_count":len(findings)})
        return self.dossier(run_id)

    def dossier(self,run_id):
        d=self.db.one("SELECT * FROM ai_research_dossiers_263 WHERE run_id=? ORDER BY revision_no DESC LIMIT 1",(run_id,))
        if not d:return None
        return {**d,"hypothesis_basis":json.loads(d["hypothesis_basis_json"]),"research_gaps":json.loads(d["research_gaps_json"]),
                "source_overview":json.loads(d["source_overview_json"])}

    def refresh_dossier(self,*,case_id,run_id,actor=None):
        # Immutable dossier: create a new logical revision by removing only if no prior? Instead preserve old and return structured live view.
        run=self.db.one("SELECT * FROM ai_research_runs_263 WHERE run_id=?",(run_id,))
        if not run or run["case_id"]!=case_id:raise KeyError("run")
        findings=self.db.all("SELECT * FROM ai_research_findings_263 WHERE run_id=? ORDER BY created_at,finding_id",(run_id,))
        sup=[x for x in findings if x["stance"]=="supports"];con=[x for x in findings if x["stance"]=="contradicts"]
        return {"run_id":run_id,"finding_count":len(findings),"supports":sup,"contradicts":con,
                "context":[x for x in findings if x["stance"] not in {"supports","contradicts"}],
                "hypothesis_status":"unverified","automatic_claim_verification":False}

    def create_quality_assessment(self,*,case_id,evidence_ref,task_id="",source_level="unknown",temporal_proximity="unknown",directness="unknown",
                                  originality="unknown",authenticity="uncertain",independence="unknown",corroboration="unknown",
                                  provenance_quality="unknown",integrity_flags=None,analyst_note="",actor=None):
        self._case(case_id);actor=actor or self.actor
        vals=[(source_level,SOURCE_LEVEL),(temporal_proximity,TEMPORAL),(directness,DIRECTNESS),(originality,ORIGINALITY),
              (authenticity,AUTHENTICITY),(independence,INDEPENDENCE),(corroboration,CORROBORATION),(provenance_quality,PROVENANCE)]
        if not evidence_ref.strip() or any(v not in s for v,s in vals):raise ValueError("invalid evidence assessment")
        flags=_list(integrity_flags) or ["none"];aid=_id("eqa263");now=_now()
        payload={"source_level":source_level,"temporal":temporal_proximity,"directness":directness,"originality":originality,"authenticity":authenticity,
                 "independence":independence,"corroboration":corroboration,"provenance":provenance_quality,"flags":flags}
        self.db.execute("INSERT INTO evidence_quality_assessments_263 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid,case_id,evidence_ref,task_id,source_level,temporal_proximity,directness,originality,authenticity,independence,corroboration,
             provenance_quality,_canon(flags),analyst_note,actor,now,_hash(payload)))
        return {"assessment_id":aid,**payload,"truth_score":None,"automatic_claim_verification":False}

    def review_quality(self,*,case_id,assessment_id,decision,review_note="",reviewer=None):
        a=self.db.one("SELECT * FROM evidence_quality_assessments_263 WHERE assessment_id=?",(assessment_id,))
        if not a or a["case_id"]!=case_id:raise KeyError("assessment")
        reviewer=reviewer or self.actor
        if reviewer==a["created_by"]:raise ValueError("independent reviewer required")
        if decision not in QUALITY_REVIEW:raise ValueError("invalid review")
        rid=_id("eqr263");now=_now();payload={"decision":decision,"note":review_note}
        self.db.execute("INSERT INTO evidence_quality_reviews_263 VALUES(?,?,?,?,?,?,?,?)",
            (rid,assessment_id,case_id,decision,review_note,reviewer,now,_hash(payload)))
        return {"review_id":rid,"decision":decision}

    def stage_training_candidate(self,*,case_id,assessment_id,actor=None):
        a=self.db.one("SELECT * FROM evidence_quality_assessments_263 WHERE assessment_id=?",(assessment_id,))
        r=self.db.one("SELECT * FROM evidence_quality_reviews_263 WHERE assessment_id=?",(assessment_id,))
        if not a or a["case_id"]!=case_id or not r or r["decision"]!="accepted_quality_profile":raise PermissionError("accepted independent review required")
        return self.training.add_example(case_id=case_id,instruction="Classify reviewed evidence quality without assigning truth or automatic claim verification.",
            response=_canon({k:a[k] for k in ("source_level","temporal_proximity","directness","originality","authenticity","independence","corroboration","provenance_quality")}),
            context={"build":"263.0","quality_is_not_truth":True,"human_review_required":True},evidence_refs=[a["evidence_ref"]],
            language="de",source_type="build263_reviewed_evidence_quality",source_ref=assessment_id,created_by=actor or self.actor,
            confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_evidence_quality_benchmarks_263 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_evidence_quality_benchmarks_263") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"automatic_model_activation":False,"automatic_adapter_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_263 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"autonomous_background_collection":0,"access_control_bypass":0,"automatic_claim_verification":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"263.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='ai_research_runs_263'")),
           "ai_delta":a["reviewed_benchmarks"]>=28 and a["task_families"]>=15,"opsec_delta":o["verified_controls"]>=22,
           "capability_regression":"investigative_task_graph" in caps and "case_intelligence_model" in caps,
           "parent_build_gate":self.tasks.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build263_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt263");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build263_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda x:html.escape(str(x or ""),quote=True)
        targets=self.db.all("SELECT target_id,name FROM targets WHERE case_id=? ORDER BY name",(case_id,))
        topts="<option value=''>Fall/Thema ohne Person</option>"+"".join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
        runs=self.db.all("SELECT * FROM ai_research_runs_263 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        cards=[]
        for r in runs:
            qs=self.db.all("SELECT * FROM ai_research_queries_263 WHERE run_id=? ORDER BY rowid",(r["run_id"],))
            findings=self.db.all("SELECT * FROM ai_research_findings_263 WHERE run_id=? ORDER BY created_at",(r["run_id"],))
            d=self.dossier(r["run_id"])
            qrows=""
            for q in qs:
                urls=json.loads(q["urls_json"])
                links=" · ".join(f"<a href='{e(u['url'])}' target='_blank' rel='noopener noreferrer'>{e(u['engine'])}</a>" for u in urls)
                qrows+=f"<tr><td><code>{e(q['query_id'])}</code></td><td>{e(q['query_text'])}</td><td>{e(q['objective'])}</td><td>{links}</td></tr>"
            dossier_html=""
            if d:
                gaps="".join(f"<li>{e(g)}</li>" for g in d["research_gaps"])
                dossier_html=f"<div class='action-card'><b>Dossier Revision {e(d['revision_no'])}</b><p>{e(d['executive_summary'])}</p><b>Recherchelücken</b><ul>{gaps or '<li>Keine automatisch erkannten Lücken.</li>'}</ul></div>"
            cards.append(f"""<details class='card'><summary><b>{e(r['user_request'][:150])}</b> · {e(r['scope_type'])} · {len(qs)} Suchläufe · {len(findings)} Fundstellen</summary>
            <p><code>{e(r['run_id'])}</code></p>
            <form method='post' action='/build263/open-run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='run_id' value='{e(r['run_id'])}'><button>Bis zu 8 Suchläufe automatisch öffnen</button></form>
            <table><tr><th>Query-ID</th><th>Suchanfrage</th><th>Ziel</th><th>Direkt öffnen</th></tr>{qrows}</table>{dossier_html}</details>""")
        return f"""<section class='card'><h2>AI Research & Evidence 263</h2>
        <p><b>1. Auftrag → 2. Suchplan/Öffnen → 3. Dossier.</b> Du kannst denselben Auftrag auch im AI-Ermittler beginnen. Befehle mit „Suche…“, „Recherchiere…“, „Finde…“ oder „Durchsuche…“ werden als Rechercheauftrag erkannt.</p>
        <form method='post' action='/build263/research-command'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <label>PersonenOSINT optional</label><select name='target_id'>{topts}</select>
        <label>Auftrag an AI-Ermittler</label><textarea name='message' rows='4' placeholder='Suche alle möglichen Belege in deutschen Quellen für Operationen der CIA in Deutschland' required></textarea>
        <label><input type='checkbox' name='auto_open' value='1' checked> Suchläufe direkt automatisch öffnen (maximal 8 Tabs)</label>
        <button>Recherche ausführen</button></form>
        <p class='muted'>Es werden ausschließlich normale öffentliche Suchanfragen vorbereitet/geöffnet. Kein Login-, CAPTCHA- oder Paywall-Bypass und kein autonomer Hintergrund-Crawler.</p>
        <h3>Rechercheläufe & Dossiers</h3>{''.join(cards) or '<p>Noch kein Recherchelauf.</p>'}
        <details><summary><b>Fundstelle in ein Dossier übernehmen</b></summary>
        <form method='post' action='/build263/finding'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <input name='run_id' placeholder='Run ID' required><input name='query_id' placeholder='Query ID' required><input name='title' placeholder='Titel der Quelle' required>
        <input name='url' placeholder='https://...' required><textarea name='snippet' rows='4' placeholder='Relevanter Inhalt / deine kurze Fundstellen-Zusammenfassung'></textarea>
        <select name='stance'><option>context_only</option><option>supports</option><option>contradicts</option><option>neutral</option></select>
        <input name='source_class' value='public_web' placeholder='Source class'><input name='evidence_ref' placeholder='Evidence ref optional'>
        <button>Fundstelle übernehmen & Dossier aktualisieren</button></form></details>
        <details><summary><b>Evidence Quality</b></summary>
        <p>Keine Scheingenauigkeit: EagleEye trennt Primär/Sekundär, zeitliche Nähe, Direktheit, Original/Mirror, Authentizität, Unabhängigkeit, Corroboration und Provenienz.</p>
        <form method='post' action='/build263/quality'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <input name='evidence_ref' placeholder='Evidence ref' required>
        <select name='source_level'><option>unknown</option><option>primary</option><option>secondary</option><option>tertiary</option></select>
        <select name='originality'><option>unknown</option><option>original</option><option>certified_copy</option><option>mirror</option><option>syndicated</option><option>excerpt</option></select>
        <select name='authenticity'><option>uncertain</option><option>authenticated</option><option>partially_authenticated</option><option>disputed</option></select>
        <select name='independence'><option>unknown</option><option>independent</option><option>partially_independent</option><option>dependent</option></select>
        <select name='corroboration'><option>unknown</option><option>corroborated</option><option>partially_corroborated</option><option>isolated</option><option>contradicted</option></select>
        <select name='provenance_quality'><option>unknown</option><option>strong_provenance</option><option>partial_provenance</option><option>weak_provenance</option></select>
        <button>Evidence Quality erfassen</button></form></details>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
