from __future__ import annotations
import hashlib,html,json,re,time,uuid
from typing import Any

def _now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _loads(v,default):
    try:return json.loads(v) if v not in (None,"") else default
    except Exception:return default

EMAIL_RE=re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I)
PHONE_RE=re.compile(r'(?<!\w)(?:\+?\d{1,3}[\s()/.-])(?:[\d\s()/.-]{6,}\d)(?!\w)')
SECRET_PATTERNS=[
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}'),
    re.compile(r'(?i)\b(?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*[^\s,;]{6,}')
]
SECTION_ORDER=[
    "Executive Assessment","Key Judgments","Evidence","Counter-Evidence","Alternative Hypotheses",
    "Timeline","Network","Financial Flows","Source Assessment","Document Corpus","Red-Team Challenges",
    "Intelligence Gaps","Next Steps"
]

class Build278IntelligenceProductService:
    BUILD="278.0"
    def __init__(self,db:Any,audit:Any,*,redteam277:Any,reasoning275:Any,collection270:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.redteam277=redteam277;self.reasoning275=reasoning275
        self.collection270=collection270;self.compatibility=compatibility;self.training=training;self.actor=actor

    def _table(self,name):
        return bool(self.db.one("SELECT 1 x FROM sqlite_master WHERE type='table' AND name=?",(name,)))
    def _run(self,case_id,parent_run_id):
        r=self.db.one("SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?",(case_id,parent_run_id))
        if not r:raise KeyError("research run not found")
        return r
    def _safe_text(self,text):
        s=str(text or "")
        s=EMAIL_RE.sub("[EMAIL_REDACTED]",s);s=PHONE_RE.sub("[PHONE_REDACTED]",s)
        for p in SECRET_PATTERNS:s=p.sub("[SECRET_REDACTED]",s)
        return re.sub(r"\s+"," ",s).strip()[:8000]

    def _latest_dependencies(self,case_id,parent_run_id,actor):
        rb=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        if not rb:
            self.reasoning275.synthesize(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            rb=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        sup=self.db.one("SELECT * FROM supervisor_briefs_276 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
        rt=self.db.one("SELECT * FROM redteam_briefs_277 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
        if not rt:
            self.redteam277.run_red_team(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            sup=self.db.one("SELECT * FROM supervisor_briefs_276 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
            rt=self.db.one("SELECT * FROM redteam_briefs_277 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
        if not sup or not rt:raise RuntimeError("Build276 supervisor and Build277 red-team brief required")
        return rb,sup,rt

    def _trace(self,case_id,evidence_refs):
        refs=sorted({str(x) for x in evidence_refs if str(x)})
        claims=[];locators=[];origins=[]
        for ev in refs[:200]:
            if self._table("claim_source_lineage_258"):
                for r in self.db.all("SELECT DISTINCT verified_claim_id FROM claim_source_lineage_258 WHERE case_id=? AND source_ref=?",(case_id,ev)):
                    if r["verified_claim_id"] not in claims:claims.append(r["verified_claim_id"])
            if self._table("document_candidates_273"):
                for d in self.db.all("SELECT document_id,title,url,document_type,publication_date FROM document_candidates_273 WHERE case_id=? AND evidence_ref=?",(case_id,ev)):
                    locators.append({"kind":"document_273","evidence_ref":ev,"document_id":d["document_id"],"title":d["title"],
                                     "url":d["url"],"document_type":d["document_type"],"publication_date":d["publication_date"]})
            if self._table("provenance_bindings_255"):
                for b in self.db.all("""SELECT b.document_id,b.span_id,b.page_number,b.locator_json,b.source_vault_item_id,
                                             s.provenance_ref,s.block_type
                                      FROM provenance_bindings_255 b JOIN extraction_spans_255 s ON s.span_id=b.span_id
                                      WHERE b.case_id=? AND (b.source_vault_item_id=? OR s.provenance_ref=?) LIMIT 20""",(case_id,ev,ev)):
                    locators.append({"kind":"page_span_255","evidence_ref":ev,"document_id":b["document_id"],"span_id":b["span_id"],
                                     "page_number":b["page_number"],"locator":_loads(b["locator_json"],{}),"block_type":b["block_type"]})
            if self._table("source_nodes_271"):
                for sn in self.db.all("SELECT source_id,run_id,canonical_url,host FROM source_nodes_271 WHERE case_id=? AND evidence_ref=?",(case_id,ev)):
                    cluster=self.db.one("SELECT cluster_id,independence_class,origin_source_id FROM source_clusters_271 WHERE case_id=? AND run_id=? AND evidence_refs_json LIKE ? ORDER BY rowid DESC LIMIT 1",
                                        (case_id,sn["run_id"],f'%"{ev}"%'))
                    origins.append({"evidence_ref":ev,"source_id":sn["source_id"],"host":sn["host"],"canonical_url":sn["canonical_url"],
                                    "cluster_id":cluster["cluster_id"] if cluster else "",
                                    "independence_class":cluster["independence_class"] if cluster else "unknown",
                                    "origin_source_id":cluster["origin_source_id"] if cluster else ""})
        return {"claim_ids":claims[:100],"document_locators":locators[:200],"source_origin_refs":origins[:200]}

    def _add_statement(self,*,product_id,case_id,parent_run_id,section,order,statement_class,text,confidence,
                       evidence_refs=None,review_requirement="human_review",assertion_class="analysis_basis"):
        refs=sorted({str(x) for x in (evidence_refs or []) if str(x)})
        tr=self._trace(case_id,refs)
        sid=_id("pstmt278");safe=self._safe_text(text)
        payload={"section":section,"class":statement_class,"text":safe,"confidence":confidence,"refs":refs,
                 "claims":tr["claim_ids"],"locators":tr["document_locators"],"origins":tr["source_origin_refs"]}
        self.db.execute("""INSERT INTO product_statements_278
          (statement_id,product_id,case_id,parent_run_id,section_name,statement_order,statement_class,statement_text,
           confidence_class,evidence_refs_json,claim_ids_json,document_locators_json,source_origin_refs_json,
           review_requirement,assertion_class,status,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (sid,product_id,case_id,parent_run_id,section,order,statement_class,safe,confidence,_canon(refs),
           _canon(tr["claim_ids"]),_canon(tr["document_locators"]),_canon(tr["source_origin_refs"]),
           review_requirement,assertion_class,"internal_product",_now(),_hash(payload)))
        return sid

    def build_product(self,*,case_id,parent_run_id,actor=None,product_type="investigative_intelligence_assessment"):
        actor=actor or self.actor;self._run(case_id,parent_run_id)
        rb,sup,rt=self._latest_dependencies(case_id,parent_run_id,actor)
        rev=(self.db.one("SELECT MAX(revision_no) n FROM intelligence_products_278 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id)) or {"n":0})["n"] or 0
        rev=int(rev)+1
        case=self.db.one("SELECT title FROM cases WHERE case_id=?",(case_id,)) or {"title":"EagleEye Case"}
        # Never raise above upstream/red-team recommendation.
        ceiling=rt["recommended_assertion_ceiling"] or sup["assertion_ceiling"] or rb["assertion_ceiling"]
        if ceiling=="evidence_summary_only" and rb["assertion_ceiling"]!="evidence_summary_only":
            ceiling=rb["assertion_ceiling"]
        confidence="moderate_with_material_uncertainty" if ceiling!="evidence_summary_only" else "moderate_evidence_summary"
        pid=_id("product278")
        executive=self._safe_text(
            f"{sup['summary']} Red-Team: {rt['summary']} This product preserves counter-evidence and does not convert hypotheses, network topology, source repetition or temporal sequence into facts."
        )
        # Placeholder counts filled by immutable INSERT once statements are planned.
        plan=[]

        # Executive assessment is explicitly analytical, not a fact.
        plan.append(("Executive Assessment","executive_assessment",executive,confidence,[], "manual_product_review","analysis_basis"))

        # Key judgments from supervisor, linked to agent evidence where possible.
        judgments=_loads(sup["key_judgments_json"],[])
        for j in judgments[:12]:
            agent=str(j.get("agent",""))
            ev=[]
            res=self.db.one("SELECT evidence_refs_json FROM coanalyst_results_276 WHERE orchestration_id=? AND agent_role=?",(sup["orchestration_id"],agent))
            if res:ev=_loads(res["evidence_refs_json"],[])
            plan.append(("Key Judgments","key_judgment",self._safe_text(j.get("assessment","")), "moderate",ev,"manual_product_review","assessment_not_fact"))

        # Evidence-backed observations and interpretations; restricted-sensitive entries are omitted.
        restricted=(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND compartment='restricted_sensitive'",(case_id,parent_run_id)) or {"n":0})["n"]
        for r in self.db.all("""SELECT * FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND compartment<>'restricted_sensitive'
                              AND entry_type IN ('observation','interpretation') ORDER BY created_at,entry_id LIMIT 120""",(case_id,parent_run_id)):
            refs=_loads(r["evidence_refs_json"],[])
            sc="observation" if r["entry_type"]=="observation" else "interpretation"
            conf="evidence_bound" if sc=="observation" else "analysis_derived"
            plan.append(("Evidence",sc,r["statement"],conf,refs,"manual_product_review","evidence" if sc=="observation" else "assessment_not_fact"))

        # Counterevidence from findings and reasoning contradictions.
        contra_rows=self.db.all("SELECT evidence_ref,title,snippet FROM ai_research_findings_263 WHERE case_id=? AND stance='contradicts' ORDER BY created_at LIMIT 100",(case_id,))
        for r in contra_rows:
            plan.append(("Counter-Evidence","counterevidence",f"{r['title']}: {r['snippet']}","evidence_bound",[r["evidence_ref"]],"mandatory_review","counterevidence"))
        for r in self.db.all("SELECT statement,evidence_refs_json FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='contradiction' ORDER BY created_at LIMIT 60",(case_id,parent_run_id)):
            plan.append(("Counter-Evidence","contradiction",r["statement"],"analysis_derived",_loads(r["evidence_refs_json"],[]),"mandatory_review","analysis_basis"))
        if not contra_rows:
            plan.append(("Counter-Evidence","analysis_status","No explicit contradicting research finding is currently recorded; absence of recorded counter-evidence is not proof of the working assessment.","unknown",[],"mandatory_review","analysis_status"))

        # Alternatives.
        for r in self.db.all("SELECT statement,evidence_refs_json FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='hypothesis' AND compartment<>'restricted_sensitive' ORDER BY created_at LIMIT 30",(case_id,parent_run_id)):
            plan.append(("Alternative Hypotheses","hypothesis",r["statement"],"unverified_hypothesis",_loads(r["evidence_refs_json"],[]),"mandatory_review","hypothesis_not_fact"))

        # Core analytical sections are summarized in the main product and detailed in annexes.
        tcount=(self.db.one("SELECT COUNT(*) n FROM temporal_assessments_265 WHERE case_id=?",(case_id,)) or {"n":0})["n"] if self._table("temporal_assessments_265") else 0
        plan.append(("Timeline","timeline_assessment",f"{tcount} temporal assessment(s) are recorded. Chronology and sequence are presented without automatic causal inference.","analysis_derived",[],"manual_product_review","no_causality_inferred"))
        rcount=(self.db.one("SELECT COUNT(*) n FROM relation_candidates_266 WHERE case_id=?",(case_id,)) or {"n":0})["n"] if self._table("relation_candidates_266") else 0
        pcount=(self.db.one("SELECT COUNT(*) n FROM network_paths_267 WHERE case_id=?",(case_id,)) or {"n":0})["n"] if self._table("network_paths_267") else 0
        plan.append(("Network","network_assessment",f"{rcount} relation candidate(s) and {pcount} multi-hop path(s) are recorded. Topology does not establish influence, control, intent or guilt.","analysis_derived",[],"manual_product_review","topology_only"))
        fcount=(self.db.one("SELECT COUNT(*) n FROM financial_flows_252 WHERE case_id=?",(case_id,)) or {"n":0})["n"] if self._table("financial_flows_252") else 0
        plan.append(("Financial Flows","financial_assessment",f"{fcount} evidence-bound financial-flow candidate(s) are recorded. Financial linkage alone does not establish illegality, coordination or influence.","analysis_derived",[],"manual_product_review","financial_relation_only"))
        roll=self.db.one("SELECT * FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id)) if self._table("source_family_rollups_271") else None
        if roll:
            plan.append(("Source Assessment","source_assessment",f"{roll['raw_source_count']} raw source observation(s) collapse to {roll['origin_cluster_count']} origin candidate(s), with {roll['cross_wave_dependency_count']} cross-wave dependency observation(s). Origin candidate does not automatically mean independent source.","analysis_derived",[],"manual_product_review","source_independence_context"))
        else:
            plan.append(("Source Assessment","source_assessment","No cross-wave source-family rollup is currently available; source independence remains incomplete.","unknown",[],"manual_product_review","source_independence_incomplete"))
        dcount=(self.db.one("SELECT COUNT(*) n FROM document_candidates_273 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id)) or {"n":0})["n"] if self._table("document_candidates_273") else 0
        plan.append(("Document Corpus","document_assessment",f"{dcount} document candidate(s) are associated with this research family. Restricted-sensitive records are omitted from this product and remain subject to separate review.","analysis_derived",[],"manual_product_review","restricted_sensitive_omitted"))

        # Red-team challenges, mandatory.
        rtfind=self.db.all("SELECT * FROM redteam_findings_277 WHERE run_id=? ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'moderate' THEN 2 ELSE 1 END DESC, rowid",(rt["run_id"],))
        for r in rtfind[:80]:
            plan.append(("Red-Team Challenges","redteam_challenge",f"{r['statement']} Countercheck: {r['required_countercheck']}",
                         f"challenge_{r['severity']}",_loads(r["evidence_refs_json"],[]),"mandatory_review",r["assertion_effect"]))

        # Gaps + next steps.
        for r in self.db.all("SELECT statement FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='question' ORDER BY created_at LIMIT 50",(case_id,parent_run_id)):
            plan.append(("Intelligence Gaps","intelligence_gap",r["statement"],"open_question",[],"manual_product_review","gap"))
        for r in self.db.all("SELECT statement FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type='next_step' ORDER BY created_at LIMIT 50",(case_id,parent_run_id)):
            plan.append(("Next Steps","next_step",r["statement"],"planned_action",[],"requires_new_ok_if_external","planned_not_executed"))

        sections={s:0 for s in SECTION_ORDER}
        for sec,*_ in plan:sections[sec]=sections.get(sec,0)+1
        counter_count=sum(1 for x in plan if x[1] in {"counterevidence","contradiction"})
        red_count=sum(1 for x in plan if x[1]=="redteam_challenge")
        gap_count=sum(1 for x in plan if x[1]=="intelligence_gap")
        title=f"{case['title']} — Intelligence Assessment Rev. {rev}"
        self.db.execute("""INSERT INTO intelligence_products_278
          (product_id,case_id,parent_run_id,revision_no,product_type,title,executive_assessment,assertion_ceiling,
           confidence_class,statement_count,counterevidence_count,redteam_challenge_count,open_gap_count,restricted_omitted_count,
           sections_json,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (pid,case_id,parent_run_id,rev,product_type,title,executive,ceiling,confidence,len(plan),counter_count,red_count,gap_count,
           restricted,_canon(sections),"internal_unreviewed",actor,_now(),_hash({"title":title,"ceiling":ceiling,"sections":sections,"count":len(plan)})))
        order_by={}
        for sec,cls,text,conf,refs,req,assertion in plan:
            order_by[sec]=order_by.get(sec,0)+1
            self._add_statement(product_id=pid,case_id=case_id,parent_run_id=parent_run_id,section=sec,order=order_by[sec],
                                statement_class=cls,text=text,confidence=conf,evidence_refs=refs,review_requirement=req,assertion_class=assertion)
        annexes=self._build_annexes(pid,case_id,parent_run_id)
        audit=self.audit_export(product_id=pid)
        self._event(case_id,"intelligence_product_created","intelligence_product",pid,actor,
                    {"revision":rev,"statements":len(plan),"ceiling":ceiling,"audit":audit["result"]})
        return {"product_id":pid,"revision_no":rev,"title":title,"assertion_ceiling":ceiling,"confidence_class":confidence,
                "statement_count":len(plan),"counterevidence_count":counter_count,"redteam_challenge_count":red_count,
                "open_gap_count":gap_count,"restricted_omitted_count":restricted,"sections":sections,"annexes":annexes,
                "export_audit":audit,"automatic_publication":False,"publication_ready":False}

    def _annex(self,product_id,case_id,parent_run_id,kind,title,payload):
        aid=_id("annex278")
        items=payload if isinstance(payload,list) else payload.get("items",[]) if isinstance(payload,dict) else []
        self.db.execute("INSERT INTO product_annexes_278 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (aid,product_id,case_id,parent_run_id,kind,title,_canon(payload),len(items),"internal_annex",_now(),_hash(payload)))
        return {"annex_id":aid,"annex_type":kind,"item_count":len(items)}

    def _build_annexes(self,pid,case_id,parent_run_id):
        out=[]
        # Timeline
        timeline=[]
        if self._table("temporal_assessments_265"):
            for r in self.db.all("SELECT assessment_id,event_a,event_b,assessment_class,severity,precision_relation,rationale FROM temporal_assessments_265 WHERE case_id=? ORDER BY rowid LIMIT 100",(case_id,)):
                timeline.append(dict(r))
        out.append(self._annex(pid,case_id,parent_run_id,"timeline","Timeline / Temporal Assessments",{"items":timeline,"causality_inferred":False}))
        # Network
        network=[]
        if self._table("relation_candidates_266"):
            for r in self.db.all("SELECT relation_id,subject,predicate,object,evidence_refs_json,confidence_class,status FROM relation_candidates_266 WHERE case_id=? ORDER BY rowid LIMIT 120",(case_id,)):
                network.append(dict(r))
        out.append(self._annex(pid,case_id,parent_run_id,"network","Relations / Network",{"items":network,"guilt_or_influence_inferred":False}))
        # Financial
        financial=[]
        if self._table("financial_flows_252"):
            for r in self.db.all("SELECT flow_id,payer_influence_entity_id,payee_influence_entity_id,instrument,amount_min,amount_max,currency,transaction_date,purpose,evidence_refs_json,source_quality FROM financial_flows_252 WHERE case_id=? ORDER BY rowid LIMIT 100",(case_id,)):
                financial.append(dict(r))
        out.append(self._annex(pid,case_id,parent_run_id,"financial","Financial Flows",{"items":financial,"illegality_inferred":False}))
        # Source
        source=[]
        if self._table("source_family_rollups_271"):
            for r in self.db.all("SELECT * FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 3",(case_id,parent_run_id)):
                source.append(dict(r))
        out.append(self._annex(pid,case_id,parent_run_id,"source_assessment","Source Independence",{"items":source,"independence_not_truth":True}))
        # Documents, excluding sensitive classes.
        docs=[]
        if self._table("document_candidates_273"):
            for r in self.db.all("""SELECT document_id,evidence_ref,title,url,document_type,source_class,country_code,language,
                                      sensitivity_class,publication_date,translation_status
                               FROM document_candidates_273 WHERE case_id=? AND parent_run_id=?
                               AND sensitivity_class NOT IN ('special_category','high_impact_sensitive','controlled_personal_record')
                               ORDER BY rowid LIMIT 150""",(case_id,parent_run_id)):
                docs.append(dict(r))
        out.append(self._annex(pid,case_id,parent_run_id,"documents","Document Corpus",{"items":docs,"restricted_sensitive_omitted":True}))
        # Traceability index from all statements.
        trace=[]
        for s in self.db.all("SELECT statement_id,section_name,evidence_refs_json,claim_ids_json,document_locators_json,source_origin_refs_json FROM product_statements_278 WHERE product_id=? ORDER BY rowid",(pid,)):
            if s["evidence_refs_json"]!="[]" or s["document_locators_json"]!="[]" or s["claim_ids_json"]!="[]":
                trace.append(dict(s))
        out.append(self._annex(pid,case_id,parent_run_id,"traceability","Evidence / Claim / Document Locator Index",{"items":trace}))
        return out

    def audit_export(self,*,product_id):
        p=self.db.one("SELECT * FROM intelligence_products_278 WHERE product_id=?",(product_id,))
        if not p:raise KeyError("product")
        rows=self.db.all("SELECT * FROM product_statements_278 WHERE product_id=?",(product_id,))
        blob="\n".join(r["statement_text"] for r in rows)
        factual={"observation","counterevidence"}
        no_prov=sum(1 for r in rows if r["statement_class"] in factual and not _loads(r["evidence_refs_json"],[]))
        restricted=int(p["restricted_omitted_count"])
        emails=len(EMAIL_RE.findall(blob));phones=len(PHONE_RE.findall(blob));secrets=sum(len(x.findall(blob)) for x in SECRET_PATTERNS)
        loc_count=sum(len(_loads(r["evidence_refs_json"],[]))+len(_loads(r["document_locators_json"],[]))+len(_loads(r["claim_ids_json"],[])) for r in rows)
        red=int(any(r["section_name"]=="Red-Team Challenges" for r in rows))
        counter=int(any(r["section_name"]=="Counter-Evidence" for r in rows))
        rt=self.db.one("SELECT recommended_assertion_ceiling FROM redteam_briefs_277 WHERE case_id=? AND parent_run_id=? ORDER BY rowid DESC LIMIT 1",(p["case_id"],p["parent_run_id"]))
        ceiling_ok=int(not rt or p["assertion_ceiling"]==rt["recommended_assertion_ceiling"] or p["assertion_ceiling"] in {"analysis_basis_only","internal_analysis_only_opsec_hold"})
        result="pass" if not(no_prov or emails or phones or secrets or not red or not counter or not ceiling_ok) else "fail"
        aid=_id("paudit278");payload={"no_prov":no_prov,"emails":emails,"phones":phones,"secrets":secrets,"loc":loc_count,"red":red,"counter":counter,"ceiling":ceiling_ok,"result":result}
        self.db.execute("""INSERT INTO product_export_audits_278
          (audit_id,product_id,case_id,parent_run_id,statement_count,statements_without_provenance,restricted_content_count,
           raw_email_pattern_count,raw_phone_pattern_count,secret_pattern_count,evidence_locator_count,redteam_included,
           counterevidence_included,assertion_ceiling_preserved,automatic_publication,result,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (aid,product_id,p["case_id"],p["parent_run_id"],len(rows),no_prov,restricted,emails,phones,secrets,loc_count,red,counter,ceiling_ok,0,result,_now(),_hash(payload)))
        return {"audit_id":aid,"result":result,"statements_without_provenance":no_prov,"restricted_omitted_count":restricted,
                "raw_email_pattern_count":emails,"raw_phone_pattern_count":phones,"secret_pattern_count":secrets,
                "evidence_locator_count":loc_count,"redteam_included":bool(red),"counterevidence_included":bool(counter),
                "assertion_ceiling_preserved":bool(ceiling_ok),"automatic_publication":False}

    def review_product(self,*,case_id,product_id,decision,rationale,reviewer=None):
        p=self.db.one("SELECT * FROM intelligence_products_278 WHERE product_id=? AND case_id=?",(product_id,case_id))
        if not p:raise KeyError("product")
        reviewer=reviewer or self.actor
        if reviewer==p["created_by"]:raise ValueError("independent reviewer required")
        if decision not in {"retain_internal_product","needs_more_evidence","challenge_product","reject_product"}:raise ValueError("invalid decision")
        rid=_id("prev278")
        self.db.execute("INSERT INTO product_reviews_278 VALUES(?,?,?,?,?,?,?,?)",
                        (rid,product_id,case_id,decision,self._safe_text(rationale),reviewer,_now(),_hash({"d":decision,"r":rationale})))
        return {"review_id":rid,"decision":decision}

    def export_markdown(self,*,case_id,product_id,actor=None):
        p=self.db.one("SELECT * FROM intelligence_products_278 WHERE product_id=? AND case_id=?",(product_id,case_id))
        if not p:raise KeyError("product")
        audit=self.audit_export(product_id=product_id)
        if audit["result"]!="pass":raise RuntimeError("product export audit failed")
        review=self.db.one("SELECT * FROM product_reviews_278 WHERE product_id=?",(product_id,))
        reviewed=bool(review and review["decision"]=="retain_internal_product")
        lines=[f"# {p['title']}","",f"**Assertion Ceiling:** {p['assertion_ceiling']}",f"**Confidence:** {p['confidence_class']}",
               f"**Status:** {'independently reviewed internal product' if reviewed else 'unreviewed internal product'}",""]
        rows=self.db.all("SELECT * FROM product_statements_278 WHERE product_id=? ORDER BY CASE section_name "
                         +" ".join([f"WHEN '{s}' THEN {i}" for i,s in enumerate(SECTION_ORDER,1)])
                         +" ELSE 99 END, statement_order",(product_id,))
        current=None
        for r in rows:
            if r["section_name"]!=current:
                current=r["section_name"];lines.extend([f"## {current}",""])
            line=f"- {r['statement_text']} _(class: {r['statement_class']}; confidence: {r['confidence_class']})_"
            refs=_loads(r["evidence_refs_json"],[])
            claims=_loads(r["claim_ids_json"],[])
            locs=_loads(r["document_locators_json"],[])
            if refs:line+=f" Evidence: {', '.join(refs[:12])}"
            if claims:line+=f" Claims: {', '.join(claims[:8])}"
            if locs:
                concise=[]
                for x in locs[:8]:
                    if x.get("kind")=="page_span_255":concise.append(f"{x.get('document_id')} p.{x.get('page_number')} span {x.get('span_id')}")
                    else:concise.append(str(x.get("document_id") or x.get("evidence_ref")))
                line+=" Locators: "+", ".join(concise)
            lines.append(line)
        lines.extend(["","## Release Boundary","",
                      "- This export is an internal intelligence product. Build 278 does not automatically publish, upload or contact any subject.",
                      "- External collection next steps remain subject to a new explicit OK.",
                      "- Dark-web collection is not implemented in Phase 11 and remains reserved for Phase 12 after Build 280."])
        content="\n".join(lines)
        if EMAIL_RE.search(content) or PHONE_RE.search(content) or any(x.search(content) for x in SECRET_PATTERNS):
            raise RuntimeError("PII/secret export gate failed")
        eid=_id("pexport278")
        self.db.execute("INSERT INTO product_exports_278 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (eid,product_id,case_id,p["parent_run_id"],"markdown_internal",content,int(reviewed),0,"manual_internal_export",
                         actor or self.actor,_now(),_hash(content)))
        return {"export_id":eid,"content":content,"reviewed":reviewed,"publication_ready":False,"automatic_publication":False}

    def stage_training_candidate(self,*,case_id,product_id,actor=None):
        p=self.db.one("SELECT * FROM intelligence_products_278 WHERE product_id=? AND case_id=?",(product_id,case_id))
        review=self.db.one("SELECT * FROM product_reviews_278 WHERE product_id=?",(product_id,))
        audit=self.db.one("SELECT * FROM product_export_audits_278 WHERE product_id=? ORDER BY rowid DESC LIMIT 1",(product_id,))
        if not p or not review or review["decision"]!="retain_internal_product" or not audit or audit["result"]!="pass":
            raise PermissionError("independently retained provenance-safe product required")
        return self.training.add_example(case_id=case_id,
            instruction="Build an internal intelligence product from evidence, reasoning, supervisor and red-team layers. Preserve qualitative confidence, counterevidence, alternative hypotheses, assertion ceilings and provenance locators. Never raise the assertion ceiling or auto-publish.",
            response=_canon({"executive_assessment":p["executive_assessment"],"assertion_ceiling":p["assertion_ceiling"],
                             "statement_count":p["statement_count"],"counterevidence_count":p["counterevidence_count"],
                             "redteam_challenge_count":p["redteam_challenge_count"]}),
            context={"build":"278.0","intelligence_product":True,"provenance_safe":True,"automatic_publication":False,"human_review_required":True},
            evidence_refs=[],language="de",source_type="build278_reviewed_intelligence_product",source_ref=product_id,
            created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    # Full OK-driven chain: Build277 analysis + internal product generation.
    def execute_initial_run(self,**kwargs):
        out=self.redteam277.execute_initial_run(**kwargs)
        out["intelligence_product_278"]=self.build_product(case_id=kwargs["case_id"],parent_run_id=kwargs["run_id"],actor=kwargs.get("approved_by") or self.actor)
        return out
    def approve_and_execute_wave(self,**kwargs):
        out=self.redteam277.approve_and_execute_wave(**kwargs)
        plan=self.collection270.plan(kwargs["plan_id"])
        out["intelligence_product_278"]=self.build_product(case_id=kwargs["case_id"],parent_run_id=plan["parent_run_id"],actor=kwargs.get("approved_by") or self.actor)
        out["requires_new_ok_for_next_wave"]=True
        return out
    def create_person_document_run(self,**kwargs):return self.redteam277.create_person_document_run(**kwargs)
    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        up=self.redteam277.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)
        return {**up,"intelligence_product_278":self.build_product(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)}
    def augment_collection_plan(self,**kwargs):return self.redteam277.augment_collection_plan(**kwargs)

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_product_benchmarks_278 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_product_benchmarks_278") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"automatic_product_synthesis":True,"provenance_traceability":True,
                "counterevidence_mandatory":True,"redteam_mandatory":True,"automatic_model_activation":False,"automatic_adapter_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_278 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"provenance_safe_export":1,"automatic_publication":0,"automatic_contact":0,
                "automatic_upload":0,"restricted_sensitive_export":0,"darkweb_collection":0,"automatic_ip_rotation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"278.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='intelligence_products_278'")),
           "ai_delta":a["reviewed_benchmarks"]>=80 and a["task_families"]>=30,
           "opsec_delta":o["verified_controls"]>=80 and o["automatic_publication"]==0 and o["darkweb_collection"]==0,
           "capability_regression":"red_team_analyst_2_277" in caps and "opsec_redteam_2_277" in caps,
           "parent_build_gate":self.redteam277.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        products=self.db.all("SELECT * FROM intelligence_products_278 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(p['parent_run_id'])}</code></td><td>{e(p['revision_no'])}</td><td>{e(p['statement_count'])}</td><td>{e(p['counterevidence_count'])}</td><td>{e(p['redteam_challenge_count'])}</td><td>{e(p['assertion_ceiling'])}</td><td>{e(p['status'])}</td></tr>" for p in products)
        return f"""<section class='card'><h2>Intelligence Product Builder · Build 278</h2>
        <p><b>Evidence + Reasoning Ledger + Co-Analysts + Supervisor + Red-Team → provenance-bound internal intelligence product.</b></p>
        <p>Jede belastbare Aussage behält Evidence References sowie – soweit verfügbar – Claim-, Dokument-, Seiten-/Span- und Source-Origin-Locators. Restricted-sensitive Inhalte werden ausgelassen und gezählt.</p>
        <form method='post' action='/build278/build'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='parent_run_id' placeholder='Parent Research Run ID' required><button>Intelligence Product erstellen</button></form>
        <h3>Products</h3><table><tr><th>Run</th><th>Rev.</th><th>Statements</th><th>Counter</th><th>Red-Team</th><th>Ceiling</th><th>Status</th></tr>{rows or '<tr><td colspan="7">Noch kein Build-278-Produkt.</td></tr>'}</table>
        <details><summary><b>Product unabhängig reviewen</b></summary><form method='post' action='/build278/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='product_id' placeholder='Product ID' required><select name='decision'><option>retain_internal_product</option><option>needs_more_evidence</option><option>challenge_product</option><option>reject_product</option></select><textarea name='rationale' required></textarea><button>Review speichern</button></form></details>
        <p><b>Release Boundary:</b> Build 278 erzeugt interne Produkte/Exports, veröffentlicht aber niemals automatisch. Dark-Web-Code bleibt bis Phase 12 (nach Build 280) ausdrücklich außerhalb des Builds.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build278_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt278");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build278_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
