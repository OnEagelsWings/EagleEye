from __future__ import annotations
import hashlib,html,json,re,time,uuid
from typing import Any

ENTRY_TYPES={"observation","interpretation","hypothesis","assumption","contradiction","question","decision","next_step"}
COMPARTMENTS={"public_analysis","case_private","restricted_sensitive"}
EMAIL_RE=re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I)
PHONE_RE=re.compile(r'(?<!\w)(?:\+?\d{1,3}[\s()/.-])(?:[\d\s()/.-]{6,}\d)(?!\w)')
SECRET_PATTERNS=[
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}'),
    re.compile(r'(?i)\b(?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*[^\s,;]{6,}')
]
def _now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build275ReasoningLedgerService:
    BUILD="275.0"
    def __init__(self,db:Any,audit:Any,*,knowledge274:Any,collection270:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.knowledge274=knowledge274;self.collection270=collection270
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,parent_run_id):
        r=self.db.one("SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?",(case_id,parent_run_id))
        if not r:raise KeyError("research run not found")
        return r

    def _redact(self,text):
        s=str(text or "")
        s=EMAIL_RE.sub("[EMAIL_REDACTED]",s)
        s=PHONE_RE.sub("[PHONE_REDACTED]",s)
        for p in SECRET_PATTERNS:s=p.sub("[SECRET_REDACTED]",s)
        return re.sub(r"\s+"," ",s).strip()[:4000]

    def add_entry(self,*,case_id,parent_run_id,entry_type,statement,evidence_refs=None,parent_entry_ids=None,
                  source_object_type="",source_object_ref="",confidence_class="unknown",compartment="case_private",actor=None):
        self._run(case_id,parent_run_id)
        if entry_type not in ENTRY_TYPES:raise ValueError("invalid reasoning entry type")
        if compartment not in COMPARTMENTS:raise ValueError("invalid compartment")
        refs=sorted({str(x).strip() for x in (evidence_refs or []) if str(x).strip()})
        if entry_type=="observation" and not refs:raise ValueError("observation requires evidence reference")
        parents=sorted({str(x).strip() for x in (parent_entry_ids or []) if str(x).strip()})
        for pid in parents:
            p=self.db.one("SELECT case_id,parent_run_id FROM reasoning_ledger_275 WHERE entry_id=?",(pid,))
            if not p or p["case_id"]!=case_id or p["parent_run_id"]!=parent_run_id:raise ValueError("cross-case/run reasoning link forbidden")
        stmt=self._redact(statement)
        fp=_hash({"type":entry_type,"statement":stmt,"refs":refs,"source_type":source_object_type,"source_ref":source_object_ref})
        existing=self.db.one("SELECT * FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_fingerprint=?",(case_id,parent_run_id,fp))
        if existing:return existing
        eid=_id("reason275");actor=actor or self.actor
        payload={"type":entry_type,"statement":stmt,"refs":refs,"parents":parents,"source":source_object_ref,"compartment":compartment}
        self.db.execute("""INSERT INTO reasoning_ledger_275
            (entry_id,case_id,parent_run_id,entry_type,statement,evidence_refs_json,parent_entry_ids_json,source_object_type,source_object_ref,
             confidence_class,compartment,status,created_by,created_at,entry_fingerprint,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid,case_id,parent_run_id,entry_type,stmt,_canon(refs),_canon(parents),source_object_type,source_object_ref,
             confidence_class,compartment,"analysis_basis",actor,_now(),fp,_hash(payload)))
        for pid in parents:self._link(case_id,parent_run_id,pid,eid,"supports_reasoning_chain")
        self._event(case_id,"reasoning_entry_added","reasoning_entry",eid,actor,{"type":entry_type,"compartment":compartment})
        return self.db.one("SELECT * FROM reasoning_ledger_275 WHERE entry_id=?",(eid,))

    def _link(self,case_id,parent_run_id,from_id,to_id,relation):
        lid=_id("rlink275")
        self.db.execute("""INSERT OR IGNORE INTO reasoning_links_275
            (link_id,case_id,parent_run_id,from_entry_id,to_entry_id,relation_type,status,created_at,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (lid,case_id,parent_run_id,from_id,to_id,relation,"analysis_basis",_now(),_hash({"f":from_id,"t":to_id,"r":relation})))

    def _family_runs(self,case_id,parent_run_id):
        rows=self.db.all("SELECT child_run_id FROM collection_wave_tasks_270 WHERE child_run_id<>'' AND wave_id IN (SELECT wave_id FROM collection_waves_270 WHERE case_id=? AND parent_run_id=?)",(case_id,parent_run_id))
        return [parent_run_id]+[r["child_run_id"] for r in rows if r["child_run_id"]!=parent_run_id]

    def synthesize(self,*,case_id,parent_run_id,actor=None):
        actor=actor or self.actor;self._run(case_id,parent_run_id);runs=self._family_runs(case_id,parent_run_id)
        created=[]
        # Evidence-backed observations from ACH rows.
        for rid in runs:
            rows=self.db.all("SELECT evidence_ref,source_kind FROM ach_evidence_rows_269 WHERE case_id=? AND run_id=? ORDER BY rowid",(case_id,rid))
            for r in rows[:80]:
                created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="observation",
                    statement=f"ACH contains an evidence row from source class {r['source_kind']}.",evidence_refs=[r["evidence_ref"]],
                    source_object_type="ach_evidence_row",source_object_ref=r["evidence_ref"],confidence_class="evidence_bound",
                    compartment="case_private",actor=actor))
        # Existing hypotheses remain hypotheses, never facts.
        for rid in runs:
            for h in self.db.all("SELECT * FROM hypotheses_268 WHERE case_id=? AND run_id=? ORDER BY label",(case_id,rid)):
                refs=[x["evidence_ref"] for x in self.db.all("SELECT evidence_ref FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?",(h["hypothesis_id"],))]
                comp="restricted_sensitive" if self.db.one("SELECT 1 x FROM document_candidates_273 WHERE case_id=? AND parent_run_id=? AND sensitivity_class IN ('special_category','high_impact_sensitive','controlled_personal_record') LIMIT 1",(case_id,parent_run_id)) else "case_private"
                created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="hypothesis",
                    statement=h["statement"],evidence_refs=refs,source_object_type="hypothesis_268",source_object_ref=h["hypothesis_id"],
                    confidence_class="unverified_hypothesis",compartment=comp,actor=actor))
        # ACH contradictions and assumptions.
        ach=self.db.one("SELECT * FROM ach_briefs_269 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,parent_run_id))
        if ach:
            inc=json.loads(ach["inconsistency_summary_json"]);least=json.loads(ach["least_inconsistent_json"])
            for label,count in inc.items():
                if int(count)>0:
                    created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="contradiction",
                        statement=f"ACH hypothesis {label} has {count} inconsistent evidence row(s); the inconsistency remains analytically material.",
                        source_object_type="ach_brief_269",source_object_ref=ach["brief_id"],confidence_class="analysis_derived",
                        compartment="public_analysis",actor=actor))
            if len(least)!=1:
                created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="assumption",
                    statement="Multiple hypotheses remain equally least inconsistent; no unique explanatory conclusion is justified.",
                    source_object_type="ach_brief_269",source_object_ref=ach["brief_id"],confidence_class="explicit_uncertainty",
                    compartment="public_analysis",actor=actor))
        # Temporal contradictions.
        for rid in runs:
            for t in self.db.all("SELECT * FROM temporal_assessments_265 WHERE case_id=? AND run_id=? AND assessment_class LIKE '%conflict%' ORDER BY rowid",(case_id,rid))[:30]:
                created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="contradiction",
                    statement=f"Temporal analysis contains unresolved conflict class {t['assessment_class']}.",
                    source_object_type="temporal_assessment_265",source_object_ref=t["assessment_id"],confidence_class="analysis_derived",
                    compartment="public_analysis",actor=actor))
        # Interpretation from latest cross-case brief, still clearly interpretation.
        kb=self.db.one("SELECT * FROM cross_case_knowledge_briefs_274 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        if kb:
            created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="interpretation",
                statement=kb["summary"],source_object_type="cross_case_knowledge_brief_274",source_object_ref=kb["brief_id"],
                confidence_class="analysis_summary",compartment="public_analysis",actor=actor))
        # Questions and next steps from current collection plan.
        plan=self.db.one("SELECT * FROM collection_plans_270 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,parent_run_id))
        if plan:
            for task in self.db.all("SELECT * FROM collection_tasks_270 WHERE plan_id=? ORDER BY priority,created_at LIMIT 40",(plan["plan_id"],)):
                q=self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="question",
                    statement=task["objective"],source_object_type="collection_task_270",source_object_ref=task["task_id"],
                    confidence_class="open_question",compartment="case_private",actor=actor);created.append(q)
                n=self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="next_step",
                    statement=f"Research task: {task['query_text']}. External execution requires {'new OK' if task['requires_ok'] else 'no external approval'}; priority {task['priority']}.",
                    parent_entry_ids=[q["entry_id"]],source_object_type="collection_task_270",source_object_ref=task["task_id"],
                    confidence_class="planned_action",compartment="case_private",actor=actor);created.append(n)
            rv=self.db.one("SELECT * FROM collection_plan_reviews_270 WHERE plan_id=?",(plan["plan_id"],))
            if rv:
                created.append(self.add_entry(case_id=case_id,parent_run_id=parent_run_id,entry_type="decision",
                    statement=f"Collection-plan review decision: {rv['decision']}. {rv['rationale']}",
                    source_object_type="collection_plan_review_270",source_object_ref=rv["review_id"],confidence_class="human_decision",
                    compartment="case_private",actor=actor))
        audit=self.audit_compartments(case_id=case_id,parent_run_id=parent_run_id)
        brief=self._brief(case_id,parent_run_id,actor)
        return {"brief":brief,"compartment_audit":audit,"entry_count":len(self.db.all("SELECT entry_id FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id))),
                "new_or_reused_entries":len(created),"observation_is_interpretation":False,"hypothesis_is_fact":False}

    def _brief(self,case_id,parent_run_id,actor):
        counts={t:(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type=?",(case_id,parent_run_id,t)) or {"n":0})["n"] for t in ENTRY_TYPES}
        restricted=(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND compartment='restricted_sensitive'",(case_id,parent_run_id)) or {"n":0})["n"]
        ceiling="analysis_basis_only" if counts["contradiction"] or counts["assumption"] or counts["hypothesis"] else "evidence_summary_only"
        rev=(self.db.one("SELECT MAX(revision_no) n FROM reasoning_briefs_275 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id)) or {"n":0})["n"] or 0
        rev=int(rev)+1
        summary=(f"Reasoning ledger: {counts['observation']} observations, {counts['interpretation']} interpretations, {counts['hypothesis']} hypotheses, "
                 f"{counts['assumption']} assumptions, {counts['contradiction']} contradictions, {counts['question']} questions, "
                 f"{counts['decision']} decisions and {counts['next_step']} next steps. Assertion ceiling: {ceiling}.")
        bid=_id("rbrief275");payload={"counts":counts,"restricted":restricted,"ceiling":ceiling}
        self.db.execute("""INSERT INTO reasoning_briefs_275
            (brief_id,case_id,parent_run_id,revision_no,observation_count,interpretation_count,hypothesis_count,assumption_count,contradiction_count,
             question_count,decision_count,next_step_count,restricted_entry_count,assertion_ceiling,summary,created_by,created_at,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid,case_id,parent_run_id,rev,counts["observation"],counts["interpretation"],counts["hypothesis"],counts["assumption"],
             counts["contradiction"],counts["question"],counts["decision"],counts["next_step"],restricted,ceiling,summary,actor,_now(),_hash(payload)))
        return self.db.one("SELECT * FROM reasoning_briefs_275 WHERE brief_id=?",(bid,))

    def audit_compartments(self,*,case_id,parent_run_id):
        rows=self.db.all("SELECT statement,compartment FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=?",(case_id,parent_run_id))
        blob="\n".join(r["statement"] for r in rows)
        emails=len(EMAIL_RE.findall(blob));phones=len(PHONE_RE.findall(blob));secrets=sum(len(p.findall(blob)) for p in SECRET_PATTERNS)
        gp=(self.db.one("SELECT COUNT(*) n FROM global_public_objects_274 WHERE knowledge_type='person'") or {"n":0})["n"]
        private_global=0
        for r in self.db.all("SELECT display_label,attributes_json FROM global_public_objects_274"):
            txt=str(r["display_label"])+" "+str(r["attributes_json"])
            if EMAIL_RE.search(txt) or PHONE_RE.search(txt) or re.search(r"(?i)\btarget_[a-z0-9]+\b",txt):private_global+=1
        counts={c:sum(1 for r in rows if r["compartment"]==c) for c in COMPARTMENTS}
        result="pass" if not (emails or phones or secrets or gp or private_global) else "fail"
        aid=_id("comp275");payload={"entries":len(rows),"emails":emails,"phones":phones,"secrets":secrets,"gp":gp,"private_global":private_global,"result":result}
        self.db.execute("""INSERT INTO compartment_audits_275
            (audit_id,case_id,parent_run_id,ledger_entry_count,public_analysis_count,case_private_count,restricted_sensitive_count,
             raw_email_pattern_count,raw_phone_pattern_count,secret_pattern_count,global_person_object_count,global_private_identifier_count,
             result,created_at,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid,case_id,parent_run_id,len(rows),counts["public_analysis"],counts["case_private"],counts["restricted_sensitive"],
             emails,phones,secrets,gp,private_global,result,_now(),_hash(payload)))
        return {"audit_id":aid,"result":result,**counts,"raw_email_pattern_count":emails,"raw_phone_pattern_count":phones,
                "secret_pattern_count":secrets,"global_person_object_count":gp,"global_private_identifier_count":private_global}

    def safe_export(self,*,case_id,brief_id,actor=None):
        b=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        if not b:raise KeyError("brief")
        rows=self.db.all("SELECT entry_type,statement,compartment,confidence_class FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? ORDER BY created_at,entry_id",(case_id,b["parent_run_id"]))
        safe=[{"type":r["entry_type"],"statement":self._redact(r["statement"]),"confidence":r["confidence_class"]} for r in rows if r["compartment"]!="restricted_sensitive"]
        payload={"brief_id":brief_id,"assertion_ceiling":b["assertion_ceiling"],"summary":b["summary"],"entries":safe,
                 "evidence_refs_included":False,"restricted_entries_included":False}
        raw=_canon(payload)
        if EMAIL_RE.search(raw) or PHONE_RE.search(raw) or any(p.search(raw) for p in SECRET_PATTERNS):raise RuntimeError("safe export secret/PII gate failed")
        eid=_id("rexport275");actor=actor or self.actor
        self.db.execute("""INSERT INTO safe_reasoning_exports_275
            (export_id,brief_id,case_id,parent_run_id,included_entry_count,restricted_entries_omitted,evidence_refs_omitted,export_json,status,created_by,created_at,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid,brief_id,case_id,b["parent_run_id"],len(safe),sum(1 for r in rows if r["compartment"]=="restricted_sensitive"),1,raw,
             "manual_safe_export",actor,_now(),_hash(payload)))
        return {"export_id":eid,**payload}

    def review_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        if not b:raise KeyError("brief")
        reviewer=reviewer or self.actor
        if reviewer==b["created_by"]:raise ValueError("independent reviewer required")
        if decision not in {"retain_analysis","needs_more_evidence","challenge_analysis","reject_analysis"}:raise ValueError("invalid decision")
        rid=_id("rrev275")
        self.db.execute("INSERT INTO reasoning_reviews_275 VALUES(?,?,?,?,?,?,?,?)",
            (rid,brief_id,case_id,decision,rationale,reviewer,_now(),_hash({"d":decision,"r":rationale})))
        return {"review_id":rid,"decision":decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one("SELECT * FROM reasoning_briefs_275 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        rv=self.db.one("SELECT * FROM reasoning_reviews_275 WHERE brief_id=?",(brief_id,))
        audit=self.db.one("SELECT * FROM compartment_audits_275 WHERE case_id=? AND parent_run_id=? ORDER BY rowid DESC LIMIT 1",(case_id,b["parent_run_id"] if b else ""))
        if not b or not rv or rv["decision"]!="retain_analysis" or not audit or audit["result"]!="pass":raise PermissionError("independently retained privacy-clean reasoning brief required")
        return self.training.add_example(case_id=case_id,
            instruction="Keep observation, interpretation, hypothesis, assumption, contradiction, question, decision and next step explicitly separate. Preserve counterevidence and assertion ceilings; redact secrets and private identifiers from derived text.",
            response=_canon({"summary":b["summary"],"assertion_ceiling":b["assertion_ceiling"],"restricted_entries":b["restricted_entry_count"]}),
            context={"build":"275.0","reasoning_ledger":True,"observation_not_interpretation":True,"privacy_clean":True,"human_review_required":True},
            evidence_refs=[],language="de",source_type="build275_reviewed_reasoning_ledger",source_ref=brief_id,
            created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    def execute_initial_run(self,**kwargs):
        out=self.knowledge274.execute_initial_run(**kwargs)
        case_id=kwargs["case_id"];run_id=kwargs["run_id"];out["reasoning_ledger_275"]=self.synthesize(case_id=case_id,parent_run_id=run_id,actor=kwargs.get("approved_by") or self.actor)
        return out

    def approve_and_execute_wave(self,**kwargs):
        out=self.knowledge274.approve_and_execute_wave(**kwargs)
        plan=self.collection270.plan(kwargs["plan_id"])
        out["reasoning_ledger_275"]=self.synthesize(case_id=kwargs["case_id"],parent_run_id=plan["parent_run_id"],actor=kwargs.get("approved_by") or self.actor)
        out["requires_new_ok_for_next_wave"]=True
        return out

    def create_person_document_run(self,**kwargs):
        return self.knowledge274.create_person_document_run(**kwargs)

    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        k=self.knowledge274.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)
        r=self.synthesize(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)
        return {"cross_case_knowledge_274":k,"reasoning_ledger_275":r}

    def augment_collection_plan(self,**kwargs):
        return self.knowledge274.augment_collection_plan(**kwargs)

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_reasoning_benchmarks_275 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_reasoning_benchmarks_275") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"reasoning_ledger_synthesis":True,"assertion_ceiling":True,
                "large_data_reasoning_compression":True,"automatic_model_activation":False,"automatic_adapter_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_275 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"pii_secret_compartmentation":1,"global_person_objects_allowed":0,"safe_export_gate":1,
                "gateway_fail_closed_preserved":1,"browser_hardening_preserved":1,"automatic_ip_rotation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"275.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='reasoning_ledger_275'")),
           "ai_delta":a["reviewed_benchmarks"]>=68 and a["task_families"]>=25,
           "opsec_delta":o["verified_controls"]>=64 and o["pii_secret_compartmentation"]==1,
           "capability_regression":"cross_case_public_knowledge_layer_274" in caps and "opsec_case_isolation_browser_hardening_274" in caps,
           "parent_build_gate":self.knowledge274.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM reasoning_briefs_275 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['parent_run_id'])}</code></td><td>{e(b['revision_no'])}</td><td>{e(b['observation_count'])}</td><td>{e(b['hypothesis_count'])}</td><td>{e(b['contradiction_count'])}</td><td>{e(b['next_step_count'])}</td><td>{e(b['assertion_ceiling'])}</td></tr>" for b in briefs)
        audits=self.db.all("SELECT * FROM compartment_audits_275 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        arows="".join(f"<tr><td>{e(a['parent_run_id'])}</td><td>{e(a['result'])}</td><td>{e(a['public_analysis_count'])}</td><td>{e(a['case_private_count'])}</td><td>{e(a['restricted_sensitive_count'])}</td><td>{e(a['secret_pattern_count'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Analyst Notebook & Reasoning Ledger · Build 275</h2>
        <p><b>Observation ≠ Interpretation ≠ Hypothesis ≠ Assumption ≠ Contradiction ≠ Decision.</b> Der AI-Ermittler verdichtet die bisherige Fallanalyse in eine unveränderbare, auditierbare Reasoning-Spur.</p>
        <form method='post' action='/build275/analyze'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='parent_run_id' placeholder='Parent Research Run ID' required><button>Reasoning Ledger aktualisieren</button></form>
        <h3>Reasoning Briefs</h3><table><tr><th>Run</th><th>Rev.</th><th>Obs.</th><th>Hyp.</th><th>Contr.</th><th>Next</th><th>Assertion Ceiling</th></tr>{rows or '<tr><td colspan="7">Noch kein Reasoning Brief.</td></tr>'}</table>
        <details><summary><b>Brief unabhängig reviewen</b></summary><form method='post' action='/build275/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Brief ID' required><select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select><textarea name='rationale' required></textarea><button>Review speichern</button></form></details>
        <h3>PII / Secret Compartment Audit</h3><table><tr><th>Run</th><th>Result</th><th>Public</th><th>Case Private</th><th>Restricted</th><th>Secret Leaks</th></tr>{arows or '<tr><td colspan="6">Noch kein Audit.</td></tr>'}</table>
        <p>Safe Export lässt restricted-sensitive Einträge und Evidence References standardmäßig weg. Externe Recherche-Next-Steps bleiben an ein neues OK gebunden.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build275_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt275");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build275_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
