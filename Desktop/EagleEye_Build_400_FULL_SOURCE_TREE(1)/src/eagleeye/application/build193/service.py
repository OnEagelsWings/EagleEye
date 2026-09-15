from __future__ import annotations
import hashlib, json, re
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET = re.compile(r"(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)")

class Build193SourceNativeAIInvestigatorService:
    BUILD = "193.0"
    ALLOWED_ACTIONS = {"prepare_query","open_guided_tab","run_approved_connector","capture_result","request_review"}
    PROHIBITED_ACTIONS = {"contact_person","bypass_login","solve_captcha","identify_biometrically","publish_accusation","external_media_upload","autonomous_intervention"}
    SOURCE_PROFILES = (
        ("us_congress_api","Congress.gov API","US","official_parliament","credentialed_connector","https://api.congress.gov/v3","{query}",["api_key","terms_review","live_probe"]),
        ("il_knesset_odata","Knesset Parliamentary OData","IL","official_parliament","structured_connector","https://knesset.gov.il/Odata/ParliamentInfo.svc","{query}",["terms_review","fixture","live_probe"]),
        ("un_digital_library_api","UN Digital Library Search API","global","official_documents","structured_connector","https://digitallibrary.un.org/search","p={query}&of=recjson",["terms_review","fixture","live_probe"]),
        ("us_federal_register_api","US Federal Register API","US","official_register","structured_connector","https://www.federalregister.gov/api/v1","{query}",["terms_review","fixture","live_probe"]),
        ("openalex_api_193","OpenAlex API","global","scholarly_authority","credentialed_connector","https://api.openalex.org","search={query}",["api_key","terms_review","live_probe"]),
        ("world_bank_api","World Bank Indicators API","global","official_context","structured_connector","https://api.worldbank.org/v2","{query}&format=json",["terms_review","fixture","live_probe"]),
    )
    ROUTES = {
        "birth":["matricula_online","familysearch_catalog","dnb_gnd"],
        "death":["matricula_online","grabsteine_compgen","dnb_gnd"],
        "family":["familysearch_api","compgen_gedbas","archivportal_d"],
        "company":["global_gleif_lei","us_sec_edgar","il_corporations_registry","cn_gsxt","ru_egrul_fns"],
        "parliament":["de_bundestag_dip","eu_parliament_open_data","us_congress_api","il_knesset_odata"],
        "publication":["dnb_gnd","crossref_rest","openalex_api_193","orcid_public_api"],
        "social":["bluesky_public_api","mastodon_public_api","youtube_data_api","reddit_data_api","github_public_api"],
        "official_documents":["eu_cellar_multilingual","un_digital_library_api","us_federal_register_api"],
        "location":["eu_gisco_address","govdata_source_discovery","world_bank_api"],
        "authenticity":["c2pa_trust_list_live","google_factcheck_api","nist_openmfc_live"],
        "identity":["dnb_gnd","wikidata_sparql","global_gleif_lei","familysearch_api"],
    }
    def __init__(self, db: Any, audit: Any, *, source_ops: Any, records: Any, global_sources: Any, graph: Any, identity: Any, capture: Any, ai: Any, actor: str="system"):
        self.db,self.audit,self.source_ops,self.records,self.global_sources=db,audit,source_ops,records,global_sources
        self.graph,self.identity,self.capture,self.ai,self.actor=graph,identity,capture,ai,actor

    def seed_source_profiles(self, *, confirmation: str) -> dict[str,Any]:
        if confirmation != "AI SOURCES 193 ANLEGEN": raise PermissionError("explicit approval required")
        for sid,name,country,klass,mode,endpoint,template,blockers in self.SOURCE_PROFILES:
            p={"source_id":sid,"name":name,"country":country,"source_class":klass,"access_mode":mode,"endpoint":endpoint,"query_template":template,"candidate_only":True}
            self.db.execute("INSERT OR REPLACE INTO ai_source_profiles_193 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid,name,country,klass,mode,endpoint,"DOCUMENTED",template,dumps(blockers),now_ts(),_hash(p)))
        return {"profiles":len(self.SOURCE_PROFILES),"production_active":0,"automatic_activation":False}

    def create_plan(self, *, case_id: str, question: str, subject: Mapping[str,Any], countries: Sequence[str]=(), lawful_basis: str, created_by: str="Analyst", confirmation: str) -> dict[str,Any]:
        if confirmation != f"AI PLAN 193 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        if not lawful_basis.strip(): raise ValueError("lawful_basis required")
        clean_subject=self._redact(dict(subject)); intents=self._detect_intents(question)
        pid,created=new_id("aiplan193"),now_ts()
        policy={"source_native":True,"sources_before_models":True,"automatic_action":False,"automatic_identity_confirmation":False,"human_review_required":True}
        payload={"plan_id":pid,"case_id":case_id,"question":question,"subject":clean_subject,"countries":list(countries),"intents":intents,"lawful_basis":lawful_basis,"created_at":created,"created_by":created_by,"policy":policy}
        self.db.execute("INSERT INTO ai_investigation_plans_193 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(pid,case_id,question,dumps(clean_subject),dumps(list(countries)),dumps(intents),lawful_basis,"planned",created,created_by,dumps(policy),_hash(payload)))
        tasks=self._build_tasks(pid,question,clean_subject,list(countries),intents)
        self._event("plan_created",pid,{"intents":intents,"task_count":len(tasks)})
        return payload|{"status":"planned","tasks":tasks,"next_global_step":"2_research_sources"}

    def record_result(self, *, plan_id: str, task_id: str, source_id: str, source_ref: str, claims: Sequence[Mapping[str,Any]], entities: Sequence[Mapping[str,Any]]=(), provenance: Mapping[str,Any], confirmation: str) -> dict[str,Any]:
        if confirmation != f"AI RESULT 193 {task_id} SPEICHERN": raise PermissionError("explicit approval required")
        task=self.db.one("SELECT * FROM ai_source_tasks_193 WHERE task_id=? AND plan_id=?",(task_id,plan_id))
        if not task or task["source_id"]!=source_id: raise KeyError(task_id)
        if not source_ref or not provenance: raise ValueError("source_ref and provenance required")
        rid,observed=new_id("aires193"),now_ts(); c=self._redact(list(claims)); e=self._redact(list(entities)); p=self._redact(dict(provenance))
        payload={"result_id":rid,"plan_id":plan_id,"task_id":task_id,"source_id":source_id,"source_ref":source_ref,"claims":c,"entities":e,"observed_at":observed,"provenance":p,"review_status":"candidate"}
        self.db.execute("INSERT INTO ai_source_results_193 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(rid,plan_id,task_id,source_id,source_ref,dumps(c),dumps(e),observed,dumps(p),"candidate",_hash(payload)))
        self.db.execute("UPDATE ai_source_tasks_193 SET status='completed' WHERE task_id=?",(task_id,))
        return payload

    def synthesize(self, *, plan_id: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f"AI SYNTHESIS 193 {plan_id} ERSTELLEN": raise PermissionError("explicit approval required")
        plan=self.db.one("SELECT * FROM ai_investigation_plans_193 WHERE plan_id=?",(plan_id,))
        if not plan: raise KeyError(plan_id)
        results=self.db.all("SELECT * FROM ai_source_results_193 WHERE plan_id=?",(plan_id,))
        claim_map: dict[str,list[dict[str,Any]]]={}
        for r in results:
            for c in json.loads(r["claims_json"] or "[]"):
                key=str(c.get("claim") or c.get("text") or "").strip()
                if key: claim_map.setdefault(key,[]).append({"source_id":r["source_id"],"source_ref":r["source_ref"],"direction":c.get("direction","support"),"score":float(c.get("score",.5))})
        findings=[]; contradictions=[]
        for claim,items in claim_map.items():
            support={x["source_id"] for x in items if x["direction"]=="support"}; contra={x["source_id"] for x in items if x["direction"]=="contradict"}
            if support and contra: status="contested_candidate"; contradictions.append(claim)
            elif len(support)>=2: status="corroborated_candidate"
            elif support: status="supported_candidate"
            elif contra: status="contradicted_candidate"
            else: status="inconclusive"
            findings.append({"claim":claim,"status":status,"evidence":items})
        pending=[dict(r) for r in self.db.all("SELECT source_id,intent,reason FROM ai_source_tasks_193 WHERE plan_id=? AND status!='completed' ORDER BY sequence_no",(plan_id,))]
        gaps=[f"Quelle noch nicht geprüft: {x['source_id']} ({x['intent']})" for x in pending]
        next_actions=[]
        if contradictions: next_actions.append("Widersprechende Primärquellen zeitlich und sachlich vergleichen")
        if gaps: next_actions.append("Offene priorisierte Quellenaufgaben bearbeiten")
        if not findings: next_actions.append("Mindestens eine quellengebundene Beobachtung erfassen")
        sid,created=new_id("aisyn193"),now_ts(); policy={"ai_output_is_not_fact":True,"models_do_not_replace_sources":True,"automatic_action":False,"human_review_required":True}
        payload={"synthesis_id":sid,"plan_id":plan_id,"question":plan["question"],"findings":findings,"gaps":gaps,"contradictions":contradictions,"next_actions":next_actions,"created_at":created,"policy":policy}
        self.db.execute("INSERT INTO ai_syntheses_193 VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,plan_id,plan["question"],dumps(findings),dumps(gaps),dumps(contradictions),dumps(next_actions),created,dumps(policy),_hash(payload)))
        return payload|{"next_global_step":"3_verify_candidates"}

    def approve_action(self, *, plan_id: str, action: str, approved_by: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f"AI ACTION 193 {plan_id} {action} FREIGEBEN": raise PermissionError("explicit approval required")
        if action in self.PROHIBITED_ACTIONS or action not in self.ALLOWED_ACTIONS: raise PermissionError("action prohibited")
        return {"plan_id":plan_id,"action":action,"approved_by":approved_by,"status":"approved_for_single_execution","automatic_repeat":False,"human_review_required":True}

    def dashboard(self, *, case_id: str="") -> dict[str,Any]:
        where=" WHERE case_id=?" if case_id else ""; args=(case_id,) if case_id else ()
        n=lambda q,a=(): int((self.db.one(q,a) or {"n":0})["n"])
        return {"build":self.BUILD,"plans":n("SELECT COUNT(*) AS n FROM ai_investigation_plans_193"+where,args),"open_tasks":n("SELECT COUNT(*) AS n FROM ai_source_tasks_193 WHERE status!='completed'"),"source_profiles":n("SELECT COUNT(*) AS n FROM ai_source_profiles_193"),"guided_summary":"Fragestellung → passende Quelle → belegter Fund → Prüfung","opsec":{"local_processing":True,"external_uploads":False,"automatic_action":False,"automatic_identity_confirmation":False}}

    def _detect_intents(self, question: str) -> list[str]:
        q=question.lower(); out=[]
        rules={"birth":["geburt","born","geboren"],"death":["tod","death","gestorben"],"family":["eltern","famil","ancestor","vorfahr"],"company":["firma","company","unternehmen","corporation"],"parliament":["parlament","bundestag","congress","knesset","abgeord"],"publication":["publikation","autor","paper","publication"],"social":["account","social","profil","post"],"official_documents":["gesetz","dokument","resolution","verordnung"],"location":["ort","wohnort","location"],"authenticity":["fake","deepfake","manipul","authent"],"identity":["identität","dieselbe person","same person","alias"]}
        for intent,words in rules.items():
            if any(w in q for w in words): out.append(intent)
        return out or ["identity"]

    def _build_tasks(self, plan_id: str, question: str, subject: Mapping[str,Any], countries: list[str], intents: list[str]) -> list[dict[str,Any]]:
        sources=[]
        for i in intents: sources.extend((i,s) for s in self.ROUTES.get(i,[]))
        # country-specific priority without replacing intent routing
        country_map={"US":["us_congress_api","us_sec_edgar","us_data_gov"],"IL":["il_knesset_odata","il_data_gov_ckan","il_corporations_registry"],"CN":["cn_gsxt"],"RU":["ru_egrul_fns","ru_official_legal_information"],"DE":["de_bundestag_dip","dnb_gnd","govdata_source_discovery"]}
        for c in countries:
            sources.extend(("country_context",s) for s in country_map.get(c.upper(),[]))
        seen=set(); tasks=[]; query=self._query(subject,question)
        for intent,sid in sources:
            if sid in seen: continue
            seen.add(sid); readiness,mode=self._readiness(sid)
            tid,created=new_id("aitask193"),now_ts(); reason=f"Passt zur Teilfrage '{intent}'"
            payload={"task_id":tid,"plan_id":plan_id,"sequence_no":len(tasks)+1,"source_id":sid,"intent":intent,"query_text":query,"execution_mode":mode,"readiness":readiness,"status":"pending","reason":reason,"created_at":created}
            self.db.execute("INSERT INTO ai_source_tasks_193 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(tid,plan_id,len(tasks)+1,sid,intent,query,mode,readiness,"pending",reason,created,_hash(payload)))
            tasks.append(payload)
        return tasks

    def _readiness(self, source_id: str) -> tuple[str,str]:
        own=self.db.one("SELECT status,access_mode FROM ai_source_profiles_193 WHERE source_id=?",(source_id,))
        if own: return own["status"],("structured_connector" if "connector" in own["access_mode"] else "guided_browser_tab")
        for table in ("global_source_profiles_189","production_source_profiles_1857","source_operations_profiles_187","deep_source_profiles_188"):
            try:
                r=self.db.one(f"SELECT * FROM {table} WHERE source_id=?",(source_id,))
            except Exception: r=None
            if r:
                status=r.get("status","DOCUMENTED") if hasattr(r,"get") else r["status"]
                mode="structured_connector" if status in {"PRODUCTION_ACTIVE","PRODUCTION_READY","LIVE_VALIDATED"} else "guided_browser_tab"
                return status,mode
        return "DOCUMENTED","guided_browser_tab"

    def _query(self, subject: Mapping[str,Any], question: str) -> str:
        vals=[]
        for k in ("given_name","family_name","name","birth_name","organization","place","birth_year","death_year"):
            v=subject.get(k)
            if v: vals.append(str(v))
        vals.append(question)
        return " ".join(vals).strip()[:1000]

    def _redact(self,v: Any)->Any:
        if isinstance(v,Mapping): return {k:("[REDACTED]" if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list): return [self._redact(x) for x in v]
        return v
    def _event(self,event_type: str,target: str,payload: Mapping[str,Any])->None:
        prev=self.db.one("SELECT event_sha256 FROM ai_source_events_193 ORDER BY created_at DESC,event_id DESC LIMIT 1"); ph=prev["event_sha256"] if prev else ""
        eid,created=new_id("aievt193"),now_ts(); eh=_hash({"id":eid,"type":event_type,"target":target,"payload":payload,"created":created,"prev":ph})
        self.db.execute("INSERT INTO ai_source_events_193 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,target,dumps(payload),created,self.actor,ph,eh))
