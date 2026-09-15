from __future__ import annotations
import hashlib,html,json,re,time,uuid
from typing import Any

AGENT_ROLES=(
 "evidence_analyst","source_analyst","temporal_analyst","financial_analyst","network_analyst",
 "hypothesis_analyst","counterevidence_analyst","opsec_analyst","publication_analyst","red_team_analyst"
)
SECRET_PATTERNS=[
 re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b'),
 re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}'),
 re.compile(r'(?i)\b(?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*[^\s,;]{6,}')
]
EMAIL_RE=re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I)
PHONE_RE=re.compile(r'(?<!\w)(?:\+?\d{1,3}[\s()/.-])(?:[\d\s()/.-]{6,}\d)(?!\w)')

def _now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()

def _loads(v,default=None):
    try:return json.loads(v)
    except Exception:return [] if default is None else default

class Build276CoAnalystOrchestratorService:
    BUILD="276.0"
    def __init__(self,db:Any,audit:Any,*,reasoning275:Any,collection270:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.reasoning275=reasoning275;self.collection270=collection270
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,parent_run_id):
        row=self.db.one("SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?",(case_id,parent_run_id))
        if not row:raise KeyError("research run not found")
        return row

    def _safe_text(self,text):
        # Reuse Build275 derived-text redaction and add a local fallback.
        try:return self.reasoning275._redact(text)
        except Exception:
            s=str(text or "")
            s=EMAIL_RE.sub("[EMAIL_REDACTED]",s);s=PHONE_RE.sub("[PHONE_REDACTED]",s)
            for p in SECRET_PATTERNS:s=p.sub("[SECRET_REDACTED]",s)
            return re.sub(r"\s+"," ",s).strip()[:4000]

    def _safe_obj(self,obj):
        if isinstance(obj,str):return self._safe_text(obj)
        if isinstance(obj,list):return [self._safe_obj(x) for x in obj]
        if isinstance(obj,tuple):return [self._safe_obj(x) for x in obj]
        if isinstance(obj,dict):return {str(k):self._safe_obj(v) for k,v in obj.items()}
        return obj

    def _latest_reasoning_brief(self,case_id,parent_run_id,actor):
        b=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        if not b:
            self.reasoning275.synthesize(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            b=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        return b

    def run_orchestration(self,*,case_id,parent_run_id,actor=None,max_agents=10,token_budget_per_agent=2500):
        actor=actor or self.actor;self._run(case_id,parent_run_id)
        brief=self._latest_reasoning_brief(case_id,parent_run_id,actor)
        roles=list(AGENT_ROLES)[:max(1,min(int(max_agents),len(AGENT_ROLES)))]
        token_budget=max(500,min(int(token_budget_per_agent),8000))
        oid=_id("orch276")
        results=[]
        for role in roles:
            task_id=_id("atask276")
            goal=self._goal(role)
            input_refs=[brief["brief_id"]]
            self.db.execute("""INSERT INTO coanalyst_tasks_276
              (task_id,orchestration_id,case_id,parent_run_id,agent_role,task_goal,input_refs_json,egress_class,token_budget,status,created_at,payload_sha256)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (task_id,oid,case_id,parent_run_id,role,goal,_canon(input_refs),"local_only",token_budget,"completed",_now(),
               _hash({"role":role,"goal":goal,"refs":input_refs,"egress":"local_only","budget":token_budget})))
            data=self._run_agent(role,case_id,parent_run_id,brief)
            data=self._safe_obj(data)
            rid=_id("ares276")
            self.db.execute("""INSERT INTO coanalyst_results_276
              (result_id,task_id,orchestration_id,case_id,parent_run_id,agent_role,summary,findings_json,evidence_refs_json,caveats_json,external_actions_json,status,created_at,payload_sha256)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (rid,task_id,oid,case_id,parent_run_id,role,data["summary"],_canon(data["findings"]),_canon(data["evidence_refs"]),
               _canon(data["caveats"]),_canon([]),data.get("status","analysis_basis"),_now(),_hash({"role":role,"data":data})))
            results.append({"result_id":rid,"agent_role":role,**data})
        self.db.execute("""INSERT INTO coanalyst_runs_276
          (orchestration_id,case_id,parent_run_id,reasoning_brief_id,mode,agent_count,external_egress_policy,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (oid,case_id,parent_run_id,brief["brief_id"],"supervisor_local_multiagent",len(roles),"deny_by_default_broker_only","completed",actor,_now(),
           _hash({"case":case_id,"run":parent_run_id,"brief":brief["brief_id"],"roles":roles})))
        audit=self.audit_agent_opsec(case_id=case_id,parent_run_id=parent_run_id,orchestration_id=oid)
        supervisor=self._supervisor_brief(case_id,parent_run_id,oid,brief,results,audit,actor)
        self._event(case_id,"coanalyst_orchestration_completed","coanalyst_run",oid,actor,{"agents":len(roles),"opsec":audit["result"],"brief":supervisor["brief_id"]})
        return {"orchestration_id":oid,"agent_count":len(roles),"results":results,"opsec_audit":audit,"supervisor_brief":supervisor,
                "direct_agent_egress":False,"external_collection_requires_new_ok":True,"recursive_agent_spawning":False}

    def _goal(self,role):
        goals={
          "evidence_analyst":"Assess evidence coverage, provenance and unsupported observations.",
          "source_analyst":"Assess source independence, dependency and origin concentration.",
          "temporal_analyst":"Assess chronology, temporal conflicts and unresolved ordering.",
          "financial_analyst":"Assess evidence-bound financial-flow candidates without inferring illegality.",
          "network_analyst":"Assess relation/path topology without inferring intent, influence or guilt.",
          "hypothesis_analyst":"Assess competing hypotheses and ACH inconsistency without truth scoring.",
          "counterevidence_analyst":"Surface counterevidence, contradictions and disconfirming observations.",
          "opsec_analyst":"Assess local privacy/compartmentation, browser/gateway and egress control state.",
          "publication_analyst":"Assess whether assertion ceiling and reviews permit only internal analysis or manual publication review.",
          "red_team_analyst":"Challenge overreach, source laundering, confirmation bias, causality and hidden assumptions."
        }
        return goals[role]

    def _family_runs(self,case_id,parent_run_id):
        rows=self.db.all("SELECT child_run_id FROM collection_wave_tasks_270 WHERE child_run_id<>'' AND wave_id IN (SELECT wave_id FROM collection_waves_270 WHERE case_id=? AND parent_run_id=?)",(case_id,parent_run_id))
        return [parent_run_id]+[r["child_run_id"] for r in rows if r["child_run_id"]!=parent_run_id]

    def _run_agent(self,role,case_id,parent_run_id,reasoning_brief):
        runs=self._family_runs(case_id,parent_run_id)
        if role=="evidence_analyst":return self._evidence_agent(case_id,parent_run_id,runs)
        if role=="source_analyst":return self._source_agent(case_id,parent_run_id,runs)
        if role=="temporal_analyst":return self._temporal_agent(case_id,parent_run_id,runs)
        if role=="financial_analyst":return self._financial_agent(case_id,parent_run_id)
        if role=="network_analyst":return self._network_agent(case_id,parent_run_id,runs)
        if role=="hypothesis_analyst":return self._hypothesis_agent(case_id,parent_run_id,runs)
        if role=="counterevidence_analyst":return self._counterevidence_agent(case_id,parent_run_id,runs)
        if role=="opsec_analyst":return self._opsec_agent(case_id,parent_run_id,runs)
        if role=="publication_analyst":return self._publication_agent(case_id,parent_run_id,reasoning_brief)
        return self._red_team_agent(case_id,parent_run_id,runs,reasoning_brief)

    def _evidence_agent(self,case_id,parent_run_id,runs):
        obs=self.db.all("SELECT evidence_refs_json FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='observation'",(case_id,parent_run_id))
        refs=sorted({x for r in obs for x in _loads(r["evidence_refs_json"],[])})
        all_entries=(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id)) or {"n":0})["n"]
        findings=[{"class":"evidence_coverage","observations":len(obs),"unique_evidence_refs":len(refs),"reasoning_entries":all_entries,"severity":"info"}]
        caveats=[] if obs else ["No evidence-backed observations are present in the reasoning ledger."]
        return {"summary":f"Evidence analyst: {len(obs)} evidence-backed observations reference {len(refs)} unique evidence objects across {all_entries} reasoning entries.","findings":findings,"evidence_refs":refs[:100],"caveats":caveats}

    def _source_agent(self,case_id,parent_run_id,runs):
        roll=self.db.one("SELECT * FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        if roll:
            dep=roll["cross_wave_dependency_count"]
            finding={"class":"source_independence","raw_sources":roll["raw_source_count"],"origin_clusters":roll["origin_cluster_count"],"cross_wave_dependencies":dep,"severity":"high" if dep>5 else "moderate" if dep else "info"}
            return {"summary":f"Source analyst: {roll['raw_source_count']} raw source observations collapse to {roll['origin_cluster_count']} origin candidates; {dep} cross-wave dependencies are recorded.","findings":[finding],"evidence_refs":[],"caveats":["Origin candidates are not automatically verified independent sources."]}
        briefs=self.db.all("SELECT raw_source_count,independent_origin_candidate_count,dependent_source_count FROM source_independence_briefs_271 WHERE case_id=?",(case_id,))
        return {"summary":f"Source analyst: no family rollup exists; {len(briefs)} run-level source-independence briefs are available.","findings":[],"evidence_refs":[],"caveats":["Cross-wave source independence is incomplete."]}

    def _temporal_agent(self,case_id,parent_run_id,runs):
        ph=','.join('?' for _ in runs)
        rows=self.db.all(f"SELECT assessment_id,assessment_class,severity FROM temporal_assessments_265 WHERE case_id=? AND run_id IN ({ph})",tuple([case_id]+runs)) if runs else []
        conflicts=[r for r in rows if "conflict" in r["assessment_class"]]
        return {"summary":f"Temporal analyst: {len(rows)} temporal assessments; {len(conflicts)} conflict-class assessments remain in the case family.",
                "findings":[{"class":"temporal_conflicts","count":len(conflicts),"severity":"high" if conflicts else "info"}],"evidence_refs":[],
                "caveats":["A temporal conflict does not by itself establish which source is correct."] if conflicts else []}

    def _financial_agent(self,case_id,parent_run_id):
        flows=self.db.all("SELECT flow_id,assertion_class,evidence_refs_json,source_quality FROM financial_flows_252 WHERE case_id=?",(case_id,))
        reviewed=0;refs=[]
        for f in flows:
            refs+=_loads(f["evidence_refs_json"],[])
            if self.db.one("SELECT 1 x FROM financial_flow_reviews_252 WHERE flow_id=?",(f["flow_id"],)):reviewed+=1
        return {"summary":f"Financial analyst: {len(flows)} evidence-bound financial-flow candidates; {reviewed} have a Build252 review.",
                "findings":[{"class":"financial_flow_candidates","count":len(flows),"reviewed":reviewed,"severity":"moderate" if flows and reviewed<len(flows) else "info"}],
                "evidence_refs":sorted(set(refs))[:100],"caveats":["Financial relation does not establish illegality, influence or intent."] if flows else []}

    def _network_agent(self,case_id,parent_run_id,runs):
        ph=','.join('?' for _ in runs)
        args=tuple([case_id]+runs)
        nodes=(self.db.one(f"SELECT COUNT(*) n FROM network_nodes_266 WHERE case_id=? AND run_id IN ({ph})",args) or {"n":0})["n"] if runs else 0
        edges=(self.db.one(f"SELECT COUNT(*) n FROM network_edges_266 WHERE case_id=? AND run_id IN ({ph})",args) or {"n":0})["n"] if runs else 0
        paths=(self.db.one(f"SELECT COUNT(*) n FROM network_paths_267 WHERE case_id=? AND run_id IN ({ph})",args) or {"n":0})["n"] if runs else 0
        brokers=(self.db.one(f"SELECT COUNT(*) n FROM brokerage_metrics_267 WHERE case_id=? AND run_id IN ({ph})",args) or {"n":0})["n"] if runs else 0
        unreviewed=(self.db.one("SELECT COUNT(*) n FROM relation_candidates_266 r LEFT JOIN relation_reviews_266 v ON v.relation_id=r.relation_id WHERE r.case_id=? AND v.review_id IS NULL",(case_id,)) or {"n":0})["n"]
        return {"summary":f"Network analyst: {nodes} candidate nodes, {edges} evidence-bound edges, {paths} multi-hop paths and {brokers} brokerage observations; {unreviewed} relation candidates remain unreviewed.",
                "findings":[{"class":"unreviewed_relations","count":unreviewed,"severity":"moderate" if unreviewed else "info"}],"evidence_refs":[],
                "caveats":["Path proximity and brokerage are topology only; they do not establish coordination, influence, intent or guilt."]}

    def _hypothesis_agent(self,case_id,parent_run_id,runs):
        hypotheses=(self.db.one("SELECT COUNT(*) n FROM hypotheses_268 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        ach=self.db.one("SELECT * FROM ach_briefs_269 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,parent_run_id))
        least=_loads(ach["least_inconsistent_json"],[]) if ach else []
        inc=_loads(ach["inconsistency_summary_json"],{}) if ach else {}
        inc_total=sum(int(v) for v in inc.values()) if isinstance(inc,dict) else 0
        return {"summary":f"Hypothesis analyst: {hypotheses} hypothesis records; ACH least-inconsistent set contains {len(least)} hypothesis label(s) with {inc_total} recorded inconsistencies.",
                "findings":[{"class":"ach_inconsistency","count":inc_total,"least_inconsistent":least,"severity":"high" if inc_total else "info"}],"evidence_refs":[],
                "caveats":["Least-inconsistent is not a truth probability and no automatic winner is selected."]}

    def _counterevidence_agent(self,case_id,parent_run_id,runs):
        ph=','.join('?' for _ in runs);args=tuple([case_id]+runs)
        contra=(self.db.one(f"SELECT COUNT(*) n FROM ai_research_findings_263 WHERE case_id=? AND run_id IN ({ph}) AND stance='contradicts'",args) or {"n":0})["n"] if runs else 0
        contradictions=(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='contradiction'",(case_id,parent_run_id)) or {"n":0})["n"]
        refs=[r["evidence_ref"] for r in self.db.all(f"SELECT evidence_ref FROM ai_research_findings_263 WHERE case_id=? AND run_id IN ({ph}) AND stance='contradicts'",args)] if runs else []
        return {"summary":f"Counter-evidence analyst: {contra} contradicting findings and {contradictions} explicit reasoning contradictions are preserved.",
                "findings":[{"class":"counterevidence","contradicting_findings":contra,"reasoning_contradictions":contradictions,"severity":"high" if contra or contradictions else "info"}],"evidence_refs":sorted(set(refs))[:100],
                "caveats":["Minority counterevidence is retained and must not be hidden by result compression."]}

    def _opsec_agent(self,case_id,parent_run_id,runs):
        comp=self.db.one("SELECT * FROM compartment_audits_275 WHERE case_id=? AND parent_run_id=? ORDER BY rowid DESC LIMIT 1",(case_id,parent_run_id))
        leak=self.db.one("SELECT * FROM opsec_leak_preflight_269 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1",(case_id,parent_run_id))
        hard=self.db.one("SELECT * FROM browser_hardening_audits_274 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1",(case_id,parent_run_id))
        failures=[]
        if comp and comp["result"]!="pass":failures.append("compartment_audit")
        if leak and leak["result"]=="blocked":failures.append("leak_preflight")
        if hard and hard["result"]!="pass":failures.append("browser_hardening")
        return {"summary":f"OPSEC analyst: {len(failures)} critical local protection failure(s) detected. Agent egress remains deny-by-default and broker-only.",
                "findings":[{"class":"opsec_failures","items":failures,"severity":"critical" if failures else "info"}],"evidence_refs":[],
                "caveats":["Local configuration checks do not prove network anonymity or DNS-leak-free operation."]}

    def _publication_agent(self,case_id,parent_run_id,reasoning_brief):
        packets=(self.db.one("SELECT COUNT(*) n FROM publication_packets_259 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        reviews=(self.db.one("SELECT COUNT(*) n FROM legal_editorial_reviews_259 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        ceiling=reasoning_brief["assertion_ceiling"]
        hold=ceiling!="evidence_summary_only" or packets>reviews
        return {"summary":f"Publication analyst: {packets} publication packet(s), {reviews} legal/editorial review(s), assertion ceiling={ceiling}. {'Manual publication hold recommended.' if hold else 'No automatic publication is permitted.'}",
                "findings":[{"class":"publication_readiness","hold":hold,"assertion_ceiling":ceiling,"severity":"high" if hold else "moderate"}],"evidence_refs":[],
                "caveats":["This agent is advisory only and cannot publish, contact subjects or approve release."]}

    def _red_team_agent(self,case_id,parent_run_id,runs,reasoning_brief):
        contradictions=reasoning_brief["contradiction_count"];assumptions=reasoning_brief["assumption_count"]
        unreviewed=(self.db.one("SELECT COUNT(*) n FROM relation_candidates_266 r LEFT JOIN relation_reviews_266 v ON v.relation_id=r.relation_id WHERE r.case_id=? AND v.review_id IS NULL",(case_id,)) or {"n":0})["n"]
        roll=self.db.one("SELECT * FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        deps=roll["cross_wave_dependency_count"] if roll else 0
        issues=[]
        if contradictions:issues.append({"class":"unresolved_contradictions","count":contradictions,"severity":"high"})
        if assumptions:issues.append({"class":"explicit_assumptions","count":assumptions,"severity":"moderate"})
        if unreviewed:issues.append({"class":"unreviewed_network_relations","count":unreviewed,"severity":"moderate"})
        if deps:issues.append({"class":"source_dependency","count":deps,"severity":"moderate"})
        if not issues:issues=[{"class":"no_major_structural_issue_detected","count":0,"severity":"info"}]
        return {"summary":f"Red-team analyst: {len([x for x in issues if x['severity']!='info'])} material challenge class(es) surfaced. Correlation, topology, temporal sequence, source repetition and narrative synchrony must not be promoted into causality or coordination without independent evidence.",
                "findings":issues,"evidence_refs":[],"caveats":["Red-team findings challenge analysis; they do not alter or delete evidence."]}

    def request_external_collection(self,*,case_id,parent_run_id,orchestration_id,agent_role,objective,suggested_query,source_classes=None,actor=None):
        self._run(case_id,parent_run_id)
        if agent_role not in AGENT_ROLES:raise ValueError("agent role not allowed")
        orch=self.db.one("SELECT * FROM coanalyst_runs_276 WHERE orchestration_id=? AND case_id=? AND parent_run_id=?",(orchestration_id,case_id,parent_run_id))
        if not orch:raise KeyError("orchestration")
        query=self._safe_text(suggested_query);obj=self._safe_text(objective)
        if not query.lower().startswith(("suche ","recherchiere ","finde ","durchsuche ")):query="Suche "+query
        if re.search(r"(?i)\b(?:passwort|password|captcha|paywall|login umgehen|bypass)\b",query):raise PermissionError("access-control bypass request rejected")
        rid=_id("egress276")
        payload={"agent":agent_role,"objective":obj,"query":query,"source_classes":source_classes or []}
        self.db.execute("""INSERT INTO agent_egress_requests_276
          (request_id,orchestration_id,case_id,parent_run_id,agent_role,objective,suggested_query,source_classes_json,egress_decision,requires_new_ok,collection_task_id,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (rid,orchestration_id,case_id,parent_run_id,agent_role,obj,query,_canon(source_classes or []),"deny_direct_route_to_central_collection",1,"","proposed_requires_ok",actor or self.actor,_now(),_hash(payload)))
        self._event(case_id,"agent_egress_request","agent_egress_request",rid,actor or self.actor,{"agent":agent_role,"requires_new_ok":True})
        return {"request_id":rid,"egress_decision":"deny_direct_route_to_central_collection","requires_new_ok":True,"executed":False,"suggested_query":query}

    def audit_agent_opsec(self,*,case_id,parent_run_id,orchestration_id):
        tasks=self.db.all("SELECT * FROM coanalyst_tasks_276 WHERE orchestration_id=?",(orchestration_id,))
        results=self.db.all("SELECT * FROM coanalyst_results_276 WHERE orchestration_id=?",(orchestration_id,))
        local=sum(1 for t in tasks if t["egress_class"]=="local_only")
        direct=sum(1 for t in tasks if t["egress_class"]!="local_only")
        blob="\n".join([t["task_goal"]+" "+t["input_refs_json"] for t in tasks]+[r["summary"]+" "+r["findings_json"]+" "+r["caveats_json"] for r in results])
        secrets=sum(len(p.findall(blob)) for p in SECRET_PATTERNS)
        private=len(EMAIL_RE.findall(blob))+len(PHONE_RE.findall(blob))
        cross_scope=sum(1 for t in tasks if t["case_id"]!=case_id or t["parent_run_id"]!=parent_run_id)
        comp=self.db.one("SELECT * FROM compartment_audits_275 WHERE case_id=? AND parent_run_id=? ORDER BY rowid DESC LIMIT 1",(case_id,parent_run_id))
        comp_fail=0 if comp and comp["result"]=="pass" else 1
        result="pass" if len(tasks)==local and not (direct or secrets or private or cross_scope or comp_fail) else "fail"
        aid=_id("aopsec276");payload={"tasks":len(tasks),"local":local,"direct":direct,"secret":secrets,"private":private,"scope":cross_scope,"comp":comp_fail,"result":result}
        self.db.execute("""INSERT INTO agent_opsec_audits_276
          (audit_id,orchestration_id,case_id,parent_run_id,task_count,local_only_task_count,direct_agent_egress_count,secret_pattern_count,
           raw_private_identifier_count,cross_case_scope_violation_count,compartment_failure_count,result,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (aid,orchestration_id,case_id,parent_run_id,len(tasks),local,direct,secrets,private,cross_scope,comp_fail,result,_now(),_hash(payload)))
        return {"audit_id":aid,"result":result,"task_count":len(tasks),"local_only_task_count":local,"direct_agent_egress_count":direct,
                "secret_pattern_count":secrets,"raw_private_identifier_count":private,"cross_case_scope_violation_count":cross_scope,
                "compartment_failure_count":comp_fail}

    def _supervisor_brief(self,case_id,parent_run_id,orchestration_id,reasoning_brief,results,audit,actor):
        critical=[];counter=[];unresolved=[];next_steps=[];restricted=reasoning_brief["restricted_entry_count"]
        for r in results:
            for f in r["findings"]:
                if f.get("severity") in {"critical","high"}:critical.append({"agent":r["agent_role"],**f})
                if r["agent_role"]=="counterevidence_analyst" and f.get("severity")!="info":counter.append(f)
            unresolved.extend([{"agent":r["agent_role"],"caveat":c} for c in r["caveats"][:3]])
        questions=(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='question'",(case_id,parent_run_id)) or {"n":0})["n"]
        nxt=self.db.all("SELECT statement FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='next_step' ORDER BY created_at LIMIT 12",(case_id,parent_run_id))
        next_steps=[{"statement":self._safe_text(x["statement"]),"requires_new_ok":"new OK" in x["statement"]} for x in nxt]
        judgments=[]
        for r in results:
            judgments.append({"agent":r["agent_role"],"assessment":r["summary"],"status":"specialist_analysis_not_fact"})
        ceiling=reasoning_brief["assertion_ceiling"]
        if audit["result"]!="pass":ceiling="internal_analysis_only_opsec_hold"
        summary=(f"Supervisor fused {len(results)} specialist analyses. {len(critical)} high/critical issue(s), {questions} open question(s), "
                 f"{restricted} restricted reasoning entry/entries. Assertion ceiling: {ceiling}. Specialist disagreement and counterevidence remain explicit; no direct agent egress is permitted.")
        bid=_id("sup276");payload={"critical":critical,"counter":counter,"unresolved":unresolved,"next":next_steps,"ceiling":ceiling}
        self.db.execute("""INSERT INTO supervisor_briefs_276
          (brief_id,orchestration_id,case_id,parent_run_id,agent_result_count,critical_issue_count,open_gap_count,restricted_issue_count,
           summary,key_judgments_json,counterevidence_json,unresolved_json,next_steps_json,assertion_ceiling,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (bid,orchestration_id,case_id,parent_run_id,len(results),len(critical),questions,restricted,summary,_canon(judgments),_canon(counter),
           _canon(unresolved),_canon(next_steps),ceiling,"analysis_basis",actor,_now(),_hash(payload)))
        return {"brief_id":bid,"summary":summary,"critical_issues":critical,"open_gap_count":questions,"restricted_issue_count":restricted,
                "key_judgments":judgments,"counterevidence":counter,"unresolved":unresolved,"next_steps":next_steps,"assertion_ceiling":ceiling,
                "automatic_publication":False,"direct_agent_egress":False}

    def review_supervisor_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one("SELECT * FROM supervisor_briefs_276 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        if not b:raise KeyError("supervisor brief")
        reviewer=reviewer or self.actor
        if reviewer==b["created_by"]:raise ValueError("independent reviewer required")
        if decision not in {"retain_analysis","needs_more_evidence","challenge_analysis","reject_analysis"}:raise ValueError("invalid decision")
        rid=_id("srev276")
        self.db.execute("INSERT INTO supervisor_reviews_276 VALUES(?,?,?,?,?,?,?,?)",(rid,brief_id,case_id,decision,self._safe_text(rationale),reviewer,_now(),_hash({"d":decision,"r":rationale})))
        return {"review_id":rid,"decision":decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one("SELECT * FROM supervisor_briefs_276 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        rv=self.db.one("SELECT * FROM supervisor_reviews_276 WHERE brief_id=?",(brief_id,))
        audit=self.db.one("SELECT * FROM agent_opsec_audits_276 WHERE orchestration_id=?",(b["orchestration_id"] if b else "",))
        if not b or not rv or rv["decision"]!="retain_analysis" or not audit or audit["result"]!="pass":raise PermissionError("independently retained OPSEC-clean supervisor brief required")
        return self.training.add_example(case_id=case_id,
            instruction="Supervise specialized local co-analysts. Preserve evidence provenance, source dependency, counterevidence, disagreements and assertion ceilings. Never give specialist agents direct network authority; route external research requests through the central human-approved collection broker.",
            response=_canon({"summary":b["summary"],"assertion_ceiling":b["assertion_ceiling"],"critical_issue_count":b["critical_issue_count"],"agent_count":b["agent_result_count"]}),
            context={"build":"276.0","multiagent":True,"agent_egress":"broker_only","human_review_required":True,"automatic_publication":False},
            evidence_refs=[],language="de",source_type="build276_reviewed_supervisor_brief",source_ref=brief_id,created_by=actor or self.actor,
            confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    # Wrappers keep the existing OK-driven investigator chain and add local multi-agent synthesis.
    def execute_initial_run(self,**kwargs):
        out=self.reasoning275.execute_initial_run(**kwargs)
        case_id=kwargs["case_id"];run_id=kwargs["run_id"]
        out["coanalyst_orchestrator_276"]=self.run_orchestration(case_id=case_id,parent_run_id=run_id,actor=kwargs.get("approved_by") or self.actor)
        return out

    def approve_and_execute_wave(self,**kwargs):
        out=self.reasoning275.approve_and_execute_wave(**kwargs)
        plan=self.collection270.plan(kwargs["plan_id"])
        out["coanalyst_orchestrator_276"]=self.run_orchestration(case_id=kwargs["case_id"],parent_run_id=plan["parent_run_id"],actor=kwargs.get("approved_by") or self.actor)
        out["requires_new_ok_for_next_wave"]=True
        return out

    def create_person_document_run(self,**kwargs):return self.reasoning275.create_person_document_run(**kwargs)
    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        upstream=self.reasoning275.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)
        return {**upstream,"coanalyst_orchestrator_276":self.run_orchestration(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)}
    def augment_collection_plan(self,**kwargs):return self.reasoning275.augment_collection_plan(**kwargs)

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_agent_benchmarks_276 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_agent_benchmarks_276") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"specialist_agents":len(AGENT_ROLES),"supervisor_fusion":True,
                "agent_disagreement_preserved":True,"automatic_model_activation":False,"automatic_adapter_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_276 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"agent_egress_broker":1,"direct_agent_egress":0,"recursive_agent_spawning":0,
                "case_scope_inheritance":1,"pii_secret_redaction":1,"automatic_ip_rotation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"276.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='coanalyst_runs_276'")),
           "ai_delta":a["reviewed_benchmarks"]>=72 and a["specialist_agents"]==10,
           "opsec_delta":o["verified_controls"]>=68 and o["direct_agent_egress"]==0,
           "capability_regression":"analyst_notebook_reasoning_ledger_275" in caps and "pii_secret_compartmentation_275" in caps,
           "parent_build_gate":self.reasoning275.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM supervisor_briefs_276 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['parent_run_id'])}</code></td><td>{e(b['agent_result_count'])}</td><td>{e(b['critical_issue_count'])}</td><td>{e(b['open_gap_count'])}</td><td>{e(b['assertion_ceiling'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all("SELECT * FROM agent_opsec_audits_276 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        arows="".join(f"<tr><td>{e(a['parent_run_id'])}</td><td>{e(a['task_count'])}</td><td>{e(a['local_only_task_count'])}</td><td>{e(a['direct_agent_egress_count'])}</td><td>{e(a['result'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>AI Co-Analyst Orchestrator · Build 276</h2>
        <p><b>Supervisor → Evidence / Source / Temporal / Financial / Network / Hypothesis / Counter-Evidence / OPSEC / Publication / Red-Team.</b></p>
        <p>Alle Spezialagenten arbeiten standardmäßig lokal und fallgebunden. Externe Recherchevorschläge gehen ausschließlich über den Agent Egress Permission Broker und benötigen ein neues OK.</p>
        <form method='post' action='/build276/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='parent_run_id' placeholder='Parent Research Run ID' required><button>Co-Analyst Orchestrator ausführen</button></form>
        <h3>Supervisor Briefs</h3><table><tr><th>Run</th><th>Agents</th><th>Critical</th><th>Gaps</th><th>Ceiling</th><th>Summary</th></tr>{rows or '<tr><td colspan="6">Noch kein Orchestrator-Lauf.</td></tr>'}</table>
        <details><summary><b>Supervisor Brief unabhängig reviewen</b></summary><form method='post' action='/build276/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Supervisor Brief ID' required><select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select><textarea name='rationale' required></textarea><button>Review speichern</button></form></details>
        <h3>Agent OPSEC Audit</h3><table><tr><th>Run</th><th>Tasks</th><th>Local-only</th><th>Direct Egress</th><th>Result</th></tr>{arows or '<tr><td colspan="5">Noch kein Audit.</td></tr>'}</table>
        <p><b>Invariant:</b> Agenten dürfen keine Provider direkt aufrufen, keine Accounts anlegen, keine Schutzmechanismen umgehen, nicht veröffentlichen und keine weiteren Agenten rekursiv starten.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build276_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt276");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build276_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
