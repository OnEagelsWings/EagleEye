from __future__ import annotations
import hashlib
import html
import json
from typing import Any, Iterable
from urllib.parse import urlsplit
from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()

def _loads(v: str, default: Any):
    try: return json.loads(v) if v else default
    except Exception: return default

def _text(v: Any, n: int = 5000) -> str:
    return str(v or "").replace("\x00", "").strip()[:n]


class Build253GermanSourceProfilesService:
    BUILD = "253.0"
    OBS_ASSERTION_CLASSES = ("direct_source_observation", "source_reports_statement", "metadata_only")
    KEYWORDS = {
        "de_handelsregister": ("handelsregister","registergericht","registernummer","vertretungsberechtigt","gmbh","vorstand","geschäftsführer"),
        "de_unternehmensregister": ("jahresabschluss","bilanz","unternehmensbericht","rechnungslegung","euid","finanzbericht"),
        "de_bundesanzeiger": ("bundesanzeiger","bekanntmachung","amtlicher teil","veröffentlichung","verkündung"),
        "de_transparenzregister": ("wirtschaftlich berechtigt","beneficial owner","transparenzregister","wirtschaftliches interesse"),
        "de_lobbyregister": ("lobby","interessenvertretung","regelungsvorhaben","auftraggeber","zuwendung","schenkung","lobbyregister"),
        "de_bundeshaushalt": ("bundeshaushalt","einzelplan","kapitel","haushaltstitel","soll","ist","haushaltsjahr"),
        "de_bundestag_dip": ("drucksache","plenarprotokoll","dip","gesetzgebung","beratungsvorgang","bundestag","bundesrat"),
    }

    def __init__(self, db, audit, *, finance, influence, training, opsec, evidence_vault, conversation, actor="local-analyst"):
        self.db, self.audit, self.finance, self.influence = db, audit, finance, influence
        self.training, self.opsec, self.evidence_vault, self.conversation, self.actor = training, opsec, evidence_vault, conversation, actor
        conversation._german_sources_253 = self

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str,Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build253_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "")
        eid, now = new_id("evt253"), now_ts()
        event_hash = _hash({"previous":previous,"event_id":eid,"event_type":event_type,"object_id":object_id,"payload":payload,"actor":actor,"at":now})
        self.db.execute("INSERT INTO build253_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid,case_id,event_type,object_type,object_id,actor,dumps(payload),previous,event_hash,now))
        try: self.audit.log("build253_"+event_type, object_type, object_id, case_id, payload)
        except Exception: pass

    def profiles(self) -> list[dict[str,Any]]:
        rows = self.db.all("SELECT * FROM german_source_profiles_253 ORDER BY source_kind,display_name")
        out=[]
        for r in rows:
            d=dict(r)
            for key in ("key_fields_json","limitations_json","opsec_controls_json"):
                d[key[:-5] if key.endswith("_json") else key] = _loads(d[key], [])
            d["machine_readable"] = bool(d["machine_readable"])
            out.append(d)
        return out

    def profile(self, source_id: str) -> dict[str,Any]:
        r=self.db.one("SELECT * FROM german_source_profiles_253 WHERE source_id=?",(source_id,))
        if not r: raise KeyError(source_id)
        d=dict(r); d["key_fields"]=_loads(d["key_fields_json"],[]); d["limitations"]=_loads(d["limitations_json"],[]); d["opsec_controls"]=_loads(d["opsec_controls_json"],[]); d["machine_readable"]=bool(d["machine_readable"]); return d

    def source_preflight(self, *, case_id: str, source_id: str, actor: str, record: bool=True) -> dict[str,Any]:
        self._case(case_id); p=self.profile(source_id)
        domain=urlsplit(p["root_url"]).netloc or p["official_domain"]
        try: eg=self.opsec.egress_decision(case_id=case_id,destination_class="official_public_source",destination_ref=domain)
        except Exception: eg={"decision":"review","rule_id":"","automatic_network_change":False}
        restricted=p["access_class"] in {"account_and_request_required","session_or_login_may_apply","mixed_open_account_for_some_documents"}
        automation_allowed=bool(p["machine_readable"] and not restricted and eg.get("decision") == "allow")
        credential_handling="none_expected" if not restricted else "user_enters_credentials_in_official_source_ui_only; EagleEye stores no credential value"
        result={"case_id":case_id,"source_id":source_id,"destination_ref":domain,"access_class":p["access_class"],"egress_decision":eg.get("decision","review"),"egress_rule_id":eg.get("rule_id",""),"automation_allowed":automation_allowed,"credential_handling":credential_handling,"required_controls":p["opsec_controls"],"autonomous_network_change":False,"manual_review_required":eg.get("decision") != "allow" or restricted}
        if record:
            pid,now=new_id("preflight253"),now_ts(); payload=dict(result,preflight_id=pid)
            self.db.execute("INSERT INTO opsec_source_preflights_253 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,case_id,source_id,domain,p["access_class"],result["egress_decision"],int(automation_allowed),credential_handling,dumps(p["opsec_controls"]),0,actor,now,_hash(payload)))
            self._event(case_id,"source_preflight","source_profile",source_id,{"preflight_id":pid,"egress":result["egress_decision"],"automation_allowed":automation_allowed,"restricted":restricted},actor)
            result["preflight_id"]=pid
        return result

    def recommend_sources(self, *, case_id: str, research_question: str, top_k: int=5) -> dict[str,Any]:
        self._case(case_id); q=_text(research_question,4000).lower()
        scored=[]
        for p in self.profiles():
            hits=[kw for kw in self.KEYWORDS.get(p["source_id"],()) if kw in q]
            score=len(hits)
            if p["evidence_value"].startswith("primary_official"): score += 0.25
            scored.append((score,p,hits))
        scored.sort(key=lambda x:(-x[0],x[1]["display_name"]))
        selected=[]
        for score,p,hits in scored[:max(1,min(7,int(top_k)) )]:
            selected.append({"source_id":p["source_id"],"display_name":p["display_name"],"score":score,"matched_terms":hits,"assertion_ceiling":p["assertion_ceiling"],"access_class":p["access_class"],"advisory_only":True})
        return {"build":self.BUILD,"question":research_question,"recommendations":selected,"grounding_required":True,"no_autonomous_browsing":True,"method":"controlled source-routing heuristic; candidate for reviewed AI training/evaluation"}

    def create_lookup_plan(self, *, case_id: str, source_id: str, research_question: str, query_terms: Iterable[str], expected_artifacts: Iterable[str], purpose: str, actor: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id); p=self.profile(source_id)
        if confirmation != f"SOURCE PLAN 253 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        if len(_text(research_question)) < 12 or len(_text(purpose)) < 8: raise ValueError("research question/purpose too short")
        terms=[_text(x,300) for x in query_terms if _text(x,300)][:30]
        if not terms: raise ValueError("at least one query term required")
        pre=self.source_preflight(case_id=case_id,source_id=source_id,actor=actor,record=True)
        pid,now=new_id("srcplan253"),now_ts()
        payload={"plan_id":pid,"case_id":case_id,"source_id":source_id,"research_question":_text(research_question,4000),"query_terms":terms,"expected_artifacts":[_text(x,300) for x in expected_artifacts if _text(x,300)][:20],"purpose":_text(purpose,2000),"access_class":p["access_class"],"egress_decision":pre["egress_decision"],"opsec_review_required":pre["manual_review_required"],"execution_mode":"manual_or_reviewed_only","created_by":actor,"created_at":now}
        self.db.execute("INSERT INTO source_lookup_plans_253 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,case_id,source_id,payload["research_question"],dumps(terms),dumps(payload["expected_artifacts"]),payload["purpose"],p["access_class"],pre["egress_decision"],int(pre["manual_review_required"]),"manual_or_reviewed_only",actor,now,_hash(payload)))
        self._event(case_id,"lookup_plan_created","source_lookup_plan",pid,{"source_id":source_id,"preflight_id":pre.get("preflight_id",""),"execution_mode":"manual_or_reviewed_only"},actor)
        return payload

    def record_observation(self, *, case_id: str, source_id: str, plan_id: str, external_record_ref: str, document_date: str, observed_fields: dict[str,Any], evidence_refs: Iterable[str], assertion_class: str, notes: str, actor: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id); p=self.profile(source_id)
        if confirmation != f"SOURCE OBSERVATION 253 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        if assertion_class not in self.OBS_ASSERTION_CLASSES: raise ValueError("invalid assertion class")
        refs=[_text(x,500) for x in evidence_refs if _text(x,500)]
        if assertion_class == "direct_source_observation" and not refs: raise ValueError("direct source observations require evidence refs")
        if plan_id:
            plan=self.db.one("SELECT * FROM source_lookup_plans_253 WHERE plan_id=? AND case_id=?",(plan_id,case_id))
            if not plan: raise KeyError(plan_id)
            if plan["source_id"] != source_id: raise ValueError("plan/source mismatch")
        oid,now=new_id("srcobs253"),now_ts(); fields=dict(observed_fields or {})
        payload={"observation_id":oid,"case_id":case_id,"source_id":source_id,"plan_id":plan_id,"external_record_ref":_text(external_record_ref,1000),"document_date":_text(document_date,80),"observed_fields":fields,"evidence_refs":refs,"assertion_class":assertion_class,"assertion_ceiling":p["assertion_ceiling"],"notes":_text(notes,4000),"created_by":actor,"created_at":now,"creates_claim_automatically":False,"creates_financial_flow_automatically":False}
        self.db.execute("INSERT INTO source_observations_253 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,case_id,source_id,plan_id,_text(external_record_ref,1000),_text(document_date,80),dumps(fields),dumps(refs),assertion_class,_text(notes,4000),actor,now,_hash(payload)))
        self._event(case_id,"source_observation_recorded","source_observation",oid,{"source_id":source_id,"evidence_count":len(refs),"no_auto_claim":True,"no_auto_flow":True},actor)
        return payload

    def benchmarks(self) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.all("SELECT * FROM ai_source_benchmarks_253 ORDER BY benchmark_id")]

    def record_ai_evaluation(self, *, case_id: str, benchmark_id: str, predicted_source_id: str, predicted_assertion_ceiling: str, predicted_access_class: str, model_or_ruleset: str, evaluated_by: str, confirmation: str) -> dict[str,Any]:
        self._case(case_id)
        if confirmation != f"AI BENCHMARK 253 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        b=self.db.one("SELECT * FROM ai_source_benchmarks_253 WHERE benchmark_id=?",(benchmark_id,))
        if not b: raise KeyError(benchmark_id)
        sm=predicted_source_id==b["expected_source_id"]; am=predicted_assertion_ceiling==b["expected_assertion_ceiling"]; xm=predicted_access_class==b["expected_access_class"]; passed=sm and am and xm
        eid,now=new_id("aie253"),now_ts(); payload={"evaluation_id":eid,"case_id":case_id,"benchmark_id":benchmark_id,"source_match":sm,"assertion_match":am,"access_match":xm,"passed":passed,"model_or_ruleset":_text(model_or_ruleset,300),"evaluated_by":evaluated_by,"evaluated_at":now}
        self.db.execute("INSERT INTO ai_source_evaluations_253 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,case_id,benchmark_id,_text(predicted_source_id,200),_text(predicted_assertion_ceiling,200),_text(predicted_access_class,200),int(sm),int(am),int(xm),int(passed),_text(model_or_ruleset,300),evaluated_by,now,_hash(payload)))
        self._event(case_id,"ai_source_benchmark_evaluated","ai_benchmark",benchmark_id,{"evaluation_id":eid,"passed":passed,"three_dimension_gate":True},evaluated_by)
        return payload

    def ai_metrics(self, *, case_id: str) -> dict[str,Any]:
        total=int(self.db.one("SELECT COUNT(*) n FROM ai_source_benchmarks_253 WHERE review_status='curated_reviewed'")["n"])
        rows=self.db.all("SELECT * FROM ai_source_evaluations_253 WHERE case_id=?",(case_id,))
        passed=sum(1 for r in rows if r["passed"])
        return {"curated_reviewed_benchmarks":total,"evaluations":len(rows),"passed":passed,"pass_rate":round(passed/len(rows),4) if rows else None,"dimensions":["source_selection","assertion_ceiling","access_class"],"qualification_gate":"all_three_dimensions_per_benchmark","auto_model_activation":False,"training_pipeline_228":self.training.dashboard(case_id=case_id)}

    def opsec_metrics(self, *, case_id: str) -> dict[str,Any]:
        profiles=self.profiles(); controlled=sum(1 for p in profiles if len(p["opsec_controls"])>=3)
        pre=int(self.db.one("SELECT COUNT(*) n FROM opsec_source_preflights_253 WHERE case_id=?",(case_id,))["n"])
        restricted=sum(1 for p in profiles if p["access_class"] in {"account_and_request_required","session_or_login_may_apply","mixed_open_account_for_some_documents"})
        return {"source_profiles":len(profiles),"profiles_with_control_set":controlled,"control_coverage":round(controlled/len(profiles),4) if profiles else 0.0,"restricted_sources":restricted,"preflights_recorded":pre,"autonomous_network_changes":0,"credential_values_stored":0,"host_reconfiguration":False}

    def crosscut_release_gate(self, *, case_id: str) -> dict[str,Any]:
        ai=self.ai_metrics(case_id=case_id); op=self.opsec_metrics(case_id=case_id)
        ai_ready=ai["curated_reviewed_benchmarks"]>=7 and ai["auto_model_activation"] is False
        op_ready=op["source_profiles"]>=7 and op["control_coverage"]==1.0 and op["autonomous_network_changes"]==0
        return {"build":self.BUILD,"main_goal_ready":len(self.profiles())>=7,"ai_delta_ready":ai_ready,"opsec_delta_ready":op_ready,"release_ready":bool(len(self.profiles())>=7 and ai_ready and op_ready),"policy":"Every remaining build must show a measurable AI delta and a measurable defensive OPSEC delta; neither may regress."}

    def status(self, *, case_id: str) -> dict[str,Any]:
        return {"build":self.BUILD,"profiles":self.profiles(),"plans":[dict(r) for r in self.db.all("SELECT * FROM source_lookup_plans_253 WHERE case_id=? ORDER BY created_at DESC",(case_id,))],"observations":[dict(r) for r in self.db.all("SELECT * FROM source_observations_253 WHERE case_id=? ORDER BY created_at DESC",(case_id,))],"ai":self.ai_metrics(case_id=case_id),"opsec":self.opsec_metrics(case_id=case_id),"gate":self.crosscut_release_gate(case_id=case_id)}

    def render_workspace_panel(self, *, case_id: str, csrf: str="") -> str:
        e=lambda x: html.escape(str(x or "")); s=self.status(case_id=case_id); prof=s["profiles"]
        options="".join(f"<option value='{e(p['source_id'])}'>{e(p['display_name'])}</option>" for p in prof)
        cards="".join(f"<div class='card'><h3>{e(p['display_name'])}</h3><p><span class='badge'>{e(p['source_kind'])}</span> <span class='badge candidate'>{e(p['access_class'])}</span></p><p>{e(p['evidence_value'])} · Aussagegrenze: <b>{e(p['assertion_ceiling'])}</b></p><p class='muted'>{e(p['root_url'])}</p><p class='muted'>OPSEC: {e(', '.join(p['opsec_controls']))}</p></div>" for p in prof)
        gate=s["gate"]; ai=s["ai"]; op=s["opsec"]
        return f"""<section class='cockpit244'><h2>Influence &amp; Funding Investigation Pack · German Sources 253</h2><p class='muted'>Kontrollierte deutsche Register-, Haushalts-, Lobby- und Parlamentsquellen. Quellenprofile definieren Beweiswert und Aussagegrenze; sie starten keine autonome Recherche.</p><div class='metrics'><div class='metric'><div class='label'>Quellenprofile</div><div class='value'>{len(prof)}</div></div><div class='metric'><div class='label'>AI-Benchmarks reviewed</div><div class='value'>{ai['curated_reviewed_benchmarks']}</div></div><div class='metric'><div class='label'>OPSEC control coverage</div><div class='value'>{int(op['control_coverage']*100)}%</div></div><div class='metric'><div class='label'>Crosscut Gate</div><div class='value'>{'PASS' if gate['release_ready'] else 'CHECK'}</div></div></div><div class='grid'><div class='card'><h3>Quellenempfehlung / AI-Routing</h3><form method='post' action='/build253/recommend'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><textarea name='research_question' placeholder='Welche öffentliche Tatsache soll geklärt werden?' required></textarea><button>Quellenkandidaten bestimmen</button></form><p class='muted'>Advisory only: keine autonome Browsersuche, keine automatische Tatsachenbehauptung.</p></div><div class='card'><h3>Lookup-Plan</h3><form method='post' action='/build253/plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='source_id'>{options}</select><textarea name='research_question' placeholder='Recherchefrage' required></textarea><input name='query_terms' placeholder='Suchbegriffe, komma-getrennt' required><input name='expected_artifacts' placeholder='Erwartete Dokumente/Felder, komma-getrennt'><textarea name='purpose' placeholder='Zweck und Abgrenzung' required></textarea><button>Plan + OPSEC-Preflight anlegen</button></form></div><div class='card'><h3>Quellenbeobachtung</h3><form method='post' action='/build253/observation'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><select name='source_id'>{options}</select><input name='plan_id' placeholder='Plan-ID'><input name='external_record_ref' placeholder='Externe Register-/Dokumentreferenz'><input name='document_date' placeholder='Dokumentdatum'><select name='assertion_class'>{''.join(f'<option>{e(x)}</option>' for x in self.OBS_ASSERTION_CLASSES)}</select><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt'><textarea name='observed_fields' placeholder='Felder als key=value; key=value'></textarea><textarea name='notes' placeholder='Notiz'></textarea><button>Beobachtung quellennah speichern</button></form></div></div><h3>Deutsche Quellenprofile</h3><div class='grid'>{cards}</div><div class='notice warn'>Build 253 speichert keine Passwörter und umgeht keine Zugangskontrollen. Transparenzregister, Login-/Session-Portale und andere beschränkte Quellen bleiben manuell und rechtlich kontrolliert. Haushaltsansätze, Lobbyregisterangaben und Registerdaten werden nicht automatisch zu Einfluss-, Korruptions- oder Geheimdienstbehauptungen hochgestuft.</div><div class='card'><h3>Verbindliche Querschnittsgates ab 253</h3><p><b>AI:</b> {e(ai['curated_reviewed_benchmarks'])} reviewte Gold-Benchmarks; Qualifikation über Quelle + Aussagegrenze + Zugriffsklasse; keine automatische Adapteraktivierung.</p><p><b>OPSEC:</b> {int(op['control_coverage']*100)}% der Quellenprofile mit explizitem Kontrollsatz; {op['restricted_sources']} eingeschränkte Quellen separat markiert; keine autonome Host-/Netzwerkänderung.</p></div></section>"""
