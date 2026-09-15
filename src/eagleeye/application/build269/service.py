from __future__ import annotations
import hashlib,html,json,os,re,time,uuid
from pathlib import Path
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p): return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

ASSESSMENTS={"consistent","inconsistent","neutral","unknown"}

class Build269ACHLeakPreflightService:
    BUILD="269.0"
    def __init__(self,db:Any,audit:Any,*,hypothesis268:Any,temporal265:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.hypothesis268=hypothesis268;self.temporal265=temporal265
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _case_run(self,case_id,run_id):
        run=self.db.one("SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?",(case_id,run_id))
        if not run: raise KeyError("research run not found")
        return run

    def preflight_leaks(self,*,case_id,run_id,mode="standard",route_mode="direct",proxy_label=""):
        self._case_run(case_id,run_id)
        mode=mode if mode in {"standard","high_risk"} else "standard"
        notes=[]
        route_fail_closed=True
        if mode=="high_risk" and route_mode=="direct":
            notes.append("high-risk mode forbids direct route")
        proxy=os.environ.get("EAGLEEYE_OUTBOUND_PROXY","").strip()
        if route_mode=="user_configured_proxy":
            p=urlsplit(proxy) if proxy else None
            route_ok=bool(p and p.scheme in {"http","https"} and p.hostname and not p.username and not p.password)
            if not route_ok: notes.append("configured route missing or unsafe")
        else:
            route_ok=(route_mode=="direct")

        probe=None
        try:
            probe=self.temporal265.create_opsec_context(case_id=case_id,run_id=run_id,proxy_mode=route_mode,proxy_label=proxy_label,mode="preflight_probe")
            profile=Path(probe["profile_path"])
            userjs=profile/"user.js"
            txt=userjs.read_text(encoding="utf-8") if userjs.exists() else ""
            profile_present=int(profile.exists() and userjs.exists())
            webrtc=int('user_pref("media.peerconnection.enabled", false);' in txt)
            dns_prefetch=int('user_pref("network.dns.disablePrefetch", true);' in txt)
            speculative=int(
                'user_pref("network.http.speculative-parallel-limit", 0);' in txt and
                'user_pref("browser.urlbar.speculativeConnect.enabled", false);' in txt and
                'user_pref("network.prefetch-next", false);' in txt
            )
            referrer=int('user_pref("network.http.sendRefererHeader", 0);' in txt)
            cookies=int(any(p.is_file() and "cookie" in p.name.casefold() for p in profile.rglob("*")))
            history=int(any(p.is_file() and p.name.casefold() in {"places.sqlite","history.sqlite"} for p in profile.rglob("*")))
            rel=str(profile.relative_to(Path(self.db.path).parent))
            reused=(self.db.one("SELECT COUNT(*) n FROM opsec_sessions_265 WHERE ephemeral_profile_relpath=?",(rel,)) or {"n":0})["n"]>1
            profile_unique=int(not reused)
        except Exception as exc:
            profile_present=webrtc=dns_prefetch=speculative=referrer=profile_unique=0
            cookies=history=0
            notes.append(f"profile preflight failed: {type(exc).__name__}")
        finally:
            if probe:
                try:self.temporal265.cleanup_context(probe["session_id"],notes="Build269 preflight probe cleanup")
                except Exception:pass

        if route_mode=="direct":
            dns_path_status="direct_route_unprotected"
        elif route_mode=="user_configured_proxy" and route_ok:
            dns_path_status="configured_route_network_dns_unverified"
        else:
            dns_path_status="route_unavailable"

        critical=[]
        if mode=="high_risk":
            if route_mode=="direct":critical.append("direct_route")
            if route_mode=="user_configured_proxy" and not route_ok:critical.append("route_missing")
            if not profile_present:critical.append("profile_missing")
            if not profile_unique:critical.append("profile_reuse")
            if not webrtc:critical.append("webrtc_enabled_or_unverified")
            if not dns_prefetch:critical.append("dns_prefetch_enabled_or_unverified")
            if not speculative:critical.append("speculative_connections_enabled_or_unverified")
            if not referrer:critical.append("referrer_policy_missing")
            if cookies:critical.append("cookie_residue")
            if history:critical.append("history_residue")
        result="blocked" if critical else ("pass_with_warning" if dns_path_status.endswith("unverified") or mode=="standard" and route_mode=="direct" else "pass")
        notes.extend(critical)
        if dns_path_status.endswith("unverified"):
            notes.append("DNS network path cannot be verified by EagleEye; no anonymity or DNS-leak-free claim is made")
        if mode=="standard" and route_mode=="direct":
            notes.append("standard direct route: public IP visible")

        pid=_id("leakpf269")
        payload={"mode":mode,"route_mode":route_mode,"profile":profile_present,"unique":profile_unique,"webrtc":webrtc,
                 "dns_prefetch":dns_prefetch,"speculative":speculative,"referrer":referrer,"cookies":cookies,"history":history,
                 "dns_path_status":dns_path_status,"result":result}
        self.db.execute("INSERT INTO opsec_leak_preflight_269 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid,case_id,run_id,mode,route_mode,profile_present,profile_unique,webrtc,dns_prefetch,speculative,referrer,
             cookies,history,int(route_fail_closed),dns_path_status,result,_canon(notes),_now(),_hash(payload)))
        self._event(case_id,"defensive_leak_preflight","research_run",run_id,self.actor,{"result":result,"mode":mode,"critical":critical})
        return {"preflight_id":pid,"result":result,"mode":mode,"route_mode":route_mode,
                "profile_present":bool(profile_present),"profile_unique":bool(profile_unique),
                "webrtc_disabled":bool(webrtc),"dns_prefetch_disabled":bool(dns_prefetch),
                "speculative_connections_disabled":bool(speculative),"referrer_disabled":bool(referrer),
                "cookie_residue":bool(cookies),"history_residue":bool(history),
                "dns_path_status":dns_path_status,"notes":notes,
                "network_anonymity_verified":False,"dns_leak_free_verified":False,
                "automatic_ip_rotation":False}

    def build_ach(self,*,case_id,run_id,actor=None):
        actor=actor or self.actor
        self._case_run(case_id,run_id)
        hs=self.db.all("SELECT * FROM hypotheses_268 WHERE case_id=? AND run_id=? ORDER BY label",(case_id,run_id))
        if not hs: raise RuntimeError("Build268 hypothesis set required")
        old=self.db.one("SELECT matrix_id FROM ach_matrices_269 WHERE case_id=? AND run_id=?",(case_id,run_id))
        if old:return self.ach_brief(old["matrix_id"])
        hset=self.db.one("SELECT * FROM hypothesis_sets_268 WHERE case_id=? AND run_id=?",(case_id,run_id))
        mid=_id("ach269")
        self.db.execute("INSERT INTO ach_matrices_269 VALUES(?,?,?,?,?,?,?,?,?)",
            (mid,hset["set_id"],case_id,run_id,hset["research_question"],"analysis_basis",actor,_now(),_hash({"set":hset["set_id"],"q":hset["research_question"]})))
        refs={}
        for h in hs:
            links=self.db.all("SELECT * FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?",(h["hypothesis_id"],))
            for l in links:
                refs.setdefault(l["evidence_ref"],{"source_kind":l["source_kind"],"links":defaultdict(list)})
                refs[l["evidence_ref"]]["links"][h["hypothesis_id"]].append(l["role"])
        # Also preserve findings not linked by Build268 as evidence rows with unknown cells.
        findings=self.db.all("SELECT evidence_ref,title,snippet FROM ai_research_findings_263 WHERE case_id=? AND run_id=?",(case_id,run_id))
        finding_note={f["evidence_ref"]:(f"{f['title']}: {f['snippet']}")[:500] for f in findings}
        for f in findings:
            refs.setdefault(f["evidence_ref"],{"source_kind":"finding","links":defaultdict(list)})

        rows=[]
        for ev,data in sorted(refs.items()):
            assessments={}
            rationales={}
            for h in hs:
                roles=data["links"].get(h["hypothesis_id"],[])
                if any(r.startswith("contradict") for r in roles):
                    a="inconsistent";rat="Evidence link contradicts this hypothesis."
                elif any(r.startswith("support") for r in roles):
                    a="consistent";rat="Evidence link is consistent with this hypothesis; consistency does not prove it."
                elif roles:
                    a="neutral";rat="Evidence is contextual/non-discriminating for this hypothesis."
                else:
                    a="unknown";rat="No explicit Build268 evidence link to this hypothesis."
                assessments[h["hypothesis_id"]]=a;rationales[h["hypothesis_id"]]=rat
            vals=set(assessments.values())
            discr=int("inconsistent" in vals and len(vals-{"unknown","neutral"})>1 or ("inconsistent" in vals and any(v!="inconsistent" for v in vals)))
            rid=_id("achrow269")
            self.db.execute("INSERT INTO ach_evidence_rows_269 VALUES(?,?,?,?,?,?,?,?,?,?)",
                (rid,mid,case_id,run_id,ev,data["source_kind"],finding_note.get(ev,"Evidence reference from hypothesis set."),discr,_now(),_hash({"ev":ev,"d":discr})))
            for h in hs:
                cid=_id("achcell269")
                self.db.execute("INSERT INTO ach_cells_269 VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (cid,rid,h["hypothesis_id"],case_id,assessments[h["hypothesis_id"]],rationales[h["hypothesis_id"]],discr,
                     "analysis_basis",_now(),_hash({"r":rid,"h":h["hypothesis_id"],"a":assessments[h["hypothesis_id"]]})))
            rows.append({"row_id":rid,"evidence_ref":ev,"discriminating":bool(discr),"assessments":assessments})

        brief=self._build_brief(mid,case_id,run_id,hs,actor)
        self._event(case_id,"ach_matrix_created","ach_matrix",mid,actor,{"hypotheses":len(hs),"evidence_rows":len(rows)})
        return brief

    def _build_brief(self,matrix_id,case_id,run_id,hs,actor):
        rows=self.db.all("SELECT * FROM ach_evidence_rows_269 WHERE matrix_id=? ORDER BY rowid",(matrix_id,))
        inc={};unk={}
        for h in hs:
            cells=self.db.all("SELECT assessment,discriminating FROM ach_cells_269 WHERE hypothesis_id=? AND row_id IN (SELECT row_id FROM ach_evidence_rows_269 WHERE matrix_id=?)",(h["hypothesis_id"],matrix_id))
            inc[h["label"]]=sum(1 for c in cells if c["assessment"]=="inconsistent")
            unk[h["label"]]=sum(1 for c in cells if c["assessment"]=="unknown")
        min_inc=min(inc.values()) if inc else 0
        least=sorted([label for label,val in inc.items() if val==min_inc])
        discriminating=sum(1 for r in rows if r["discriminating"])
        gaps=[]
        if discriminating==0:gaps.append("No strongly discriminating evidence row is currently available.")
        tied=len(least)>1
        if tied:gaps.append("Multiple hypotheses remain equally least inconsistent; seek discriminating primary evidence.")
        follow=[]
        if gaps:
            follow.append({"query":"Suche gezielt nach unabhängiger Primärevidenz, die die verbleibenden Hypothesen unterschiedlich vorhersagen oder falsifizieren würde.","requires_new_ok":True})
        summary=(f"ACH matrix: {len(hs)} hypotheses × {len(rows)} unique evidence rows; {discriminating} discriminating rows. "
                 f"Least-inconsistent set: {', '.join(least) if least else 'none'}. This is an inconsistency comparison, not a truth ranking or probability.")
        bid=_id("achbrief269")
        self.db.execute("INSERT INTO ach_briefs_269 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,matrix_id,case_id,run_id,len(hs),len(rows),discriminating,_canon(inc),_canon(unk),_canon(least),
             _canon(gaps),_canon(follow),summary,"analysis_basis",actor,_now(),_hash({"inc":inc,"least":least,"gaps":gaps})))
        return {"brief_id":bid,"matrix_id":matrix_id,"summary":summary,"inconsistency_summary":inc,"unknown_summary":unk,
                "least_inconsistent":least,"research_gaps":gaps,"followup_queries":follow,
                "automatic_winner_selection":False,"truth_probability":None}

    def ach_brief(self,matrix_id):
        b=self.db.one("SELECT * FROM ach_briefs_269 WHERE matrix_id=? ORDER BY rowid DESC LIMIT 1",(matrix_id,))
        if not b:return None
        return {**b,"inconsistency_summary":json.loads(b["inconsistency_summary_json"]),"unknown_summary":json.loads(b["unknown_summary_json"]),
                "least_inconsistent":json.loads(b["least_inconsistent_json"]),"research_gaps":json.loads(b["research_gaps_json"]),
                "followup_queries":json.loads(b["followup_queries_json"]),"automatic_winner_selection":False,"truth_probability":None}

    def review_ach(self,*,case_id,matrix_id,decision,rationale,reviewer=None):
        m=self.db.one("SELECT * FROM ach_matrices_269 WHERE matrix_id=?",(matrix_id,))
        if not m or m["case_id"]!=case_id:raise KeyError("matrix")
        reviewer=reviewer or self.actor
        if reviewer==m["created_by"]:raise ValueError("independent reviewer required")
        if decision not in {"retain_analysis","challenge_analysis","needs_more_evidence","reject_analysis"}:raise ValueError("invalid decision")
        rid=_id("achrev269")
        self.db.execute("INSERT INTO ach_reviews_269 VALUES(?,?,?,?,?,?,?,?)",
            (rid,matrix_id,case_id,decision,rationale,reviewer,_now(),_hash({"d":decision,"r":rationale})))
        return {"review_id":rid,"decision":decision}

    def stage_training_candidate(self,*,case_id,matrix_id,actor=None):
        m=self.db.one("SELECT * FROM ach_matrices_269 WHERE matrix_id=? AND case_id=?",(matrix_id,case_id))
        rv=self.db.one("SELECT * FROM ach_reviews_269 WHERE matrix_id=? ORDER BY rowid DESC LIMIT 1",(matrix_id,))
        if not m or not rv or rv["decision"]!="retain_analysis":raise PermissionError("independently retained ACH analysis required")
        brief=self.ach_brief(matrix_id)
        refs=[r["evidence_ref"] for r in self.db.all("SELECT evidence_ref FROM ach_evidence_rows_269 WHERE matrix_id=?",(matrix_id,))]
        return self.training.add_example(case_id=case_id,
            instruction="Build and summarize an ACH matrix by emphasizing inconsistencies and discriminating evidence; never convert least-inconsistent into truth probability.",
            response=_canon({"inconsistency_summary":brief["inconsistency_summary"],"least_inconsistent":brief["least_inconsistent"],"truth_probability":None}),
            context={"build":"269.0","ach":True,"automatic_winner_selection":False,"human_review_required":True},
            evidence_refs=refs,language="de",source_type="build269_reviewed_ach",source_ref=matrix_id,
            created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def execute_enhanced(self,*,case_id,run_id,confirmation,approved_by=None,provider="",max_queries=8,max_results_per_query=8,
                         proxy_mode="direct",proxy_label="",opsec_mode="standard"):
        leak=self.preflight_leaks(case_id=case_id,run_id=run_id,mode=opsec_mode,route_mode=proxy_mode,proxy_label=proxy_label)
        if leak["result"]=="blocked":
            raise RuntimeError("Build269 defensive leak preflight blocked this run: "+"; ".join(leak["notes"]))
        upstream_mode="strict" if opsec_mode=="high_risk" else "standard"
        out=self.hypothesis268.execute_enhanced(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,
            proxy_label=proxy_label,opsec_mode=upstream_mode)
        ach=self.build_ach(case_id=case_id,run_id=run_id,actor=approved_by or self.actor)
        out["ach_269"]=ach;out["leak_preflight_269"]=leak
        return out

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_ach_benchmarks_269 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_ach_benchmarks_269") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"ach_automation":True,"discriminating_evidence":True,
                "automatic_winner_selection":False,"truth_probability":False,"automatic_model_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_269 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"defensive_leak_preflight":1,"webrtc_block":1,"dns_prefetch_block":1,"profile_residue_gate":1,
                "network_anonymity_claim":0,"dns_leak_free_claim":0,"automatic_ip_rotation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"269.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='ach_matrices_269'")),
           "ai_delta":a["reviewed_benchmarks"]>=42 and a["task_families"]>=20,
           "opsec_delta":o["verified_controls"]>=40 and o["defensive_leak_preflight"]==1,
           "capability_regression":"hypothesis_lab_2" in caps and "strict_egress_policy" in caps,
           "parent_build_gate":self.hypothesis268.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"))
        return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM ach_briefs_269 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['run_id'])}</code></td><td>{e(b['hypothesis_count'])}</td><td>{e(b['evidence_row_count'])}</td><td>{e(b['discriminating_row_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        pfs=self.db.all("SELECT * FROM opsec_leak_preflight_269 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        prows="".join(f"<tr><td>{e(p['run_id'])}</td><td>{e(p['mode'])}</td><td>{e(p['result'])}</td><td>{e(p['dns_path_status'])}</td><td>{e(p['notes_json'])}</td></tr>" for p in pfs)
        return f"""<section class='card'><h2>ACH & Leak Preflight · Build 269</h2>
        <p><b>Hypothesen → eindeutige Evidence Rows → Consistent / Inconsistent / Neutral / Unknown → discriminating evidence → least-inconsistent set.</b></p>
        <p>Least-inconsistent ist keine Wahrheitswahrscheinlichkeit und kein automatischer Gewinner.</p>
        <h3>ACH Briefs</h3><table><tr><th>Run</th><th>Hypothesen</th><th>Evidence Rows</th><th>Discriminating</th><th>Brief</th></tr>{rows or "<tr><td colspan='5'>Noch keine ACH-Matrix.</td></tr>"}</table>
        <details><summary><b>ACH unabhängig reviewen</b></summary>
        <form method='post' action='/build269/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'>
        <input name='matrix_id' placeholder='ACH Matrix ID' required>
        <select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select>
        <textarea name='rationale' placeholder='Review-Begründung' required></textarea><button>ACH Review speichern</button></form></details>
        <h3>Defensive Leak Preflight</h3><p>High-Risk Mode blockiert Direct Route, fehlendes ephemeres Profil, WebRTC, DNS-Prefetch/Speculation, Referrer-Leakage und Browser-Residuen. DNS-Netzwerkpfade werden nicht als leak-free behauptet, wenn EagleEye sie nicht beobachten kann.</p>
        <table><tr><th>Run</th><th>Mode</th><th>Result</th><th>DNS Path</th><th>Notes</th></tr>{prows or "<tr><td colspan='5'>Noch kein Preflight.</td></tr>"}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build269_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,))
        ph=prev["event_hash"] if prev else "GENESIS";eid=_id("evt269");now=_now()
        data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build269_events VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
