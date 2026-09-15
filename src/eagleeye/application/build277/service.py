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

SEVERITY_ORDER={"info":0,"low":1,"moderate":2,"high":3,"critical":4}
MATERIAL={"moderate","high","critical"}

class Build277RedTeamAnalystService:
    BUILD="277.0"
    def __init__(self,db:Any,audit:Any,*,coanalyst276:Any,reasoning275:Any,collection270:Any,compatibility:Any,training:Any,actor:str="local-analyst"):
        self.db=db;self.audit=audit;self.coanalyst276=coanalyst276;self.reasoning275=reasoning275
        self.collection270=collection270;self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,parent_run_id):
        r=self.db.one("SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?",(case_id,parent_run_id))
        if not r:raise KeyError("research run not found")
        return r

    def _latest_orchestration(self,case_id,parent_run_id,actor):
        row=self.db.one("SELECT * FROM coanalyst_runs_276 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
        if not row:
            out=self.coanalyst276.run_orchestration(case_id=case_id,parent_run_id=parent_run_id,actor=actor)
            row=self.db.one("SELECT * FROM coanalyst_runs_276 WHERE orchestration_id=?",(out["orchestration_id"],))
        return row

    def _latest_supervisor(self,case_id,parent_run_id):
        return self.db.one("SELECT * FROM supervisor_briefs_276 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))

    def _finding(self,run_id,case_id,parent_run_id,challenge,severity,statement,source_type,source_ref,countercheck,
                 assertion_effect="retain_or_lower",evidence_refs=None):
        fid=_id("rtf277")
        refs=sorted({str(x) for x in (evidence_refs or []) if str(x)})
        payload={"class":challenge,"severity":severity,"statement":statement,"source":source_ref,"countercheck":countercheck,"refs":refs}
        self.db.execute("""INSERT INTO redteam_findings_277
          (finding_id,run_id,case_id,parent_run_id,challenge_class,severity,statement,source_object_type,source_object_ref,
           evidence_refs_json,required_countercheck,assertion_effect,status,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (fid,run_id,case_id,parent_run_id,challenge,severity,statement,source_type,source_ref,_canon(refs),
           countercheck,assertion_effect,"challenge_only",_now(),_hash(payload)))
        return {"finding_id":fid,"challenge_class":challenge,"severity":severity,"statement":statement,
                "required_countercheck":countercheck,"assertion_effect":assertion_effect,"evidence_refs":refs}

    def run_red_team(self,*,case_id,parent_run_id,actor=None,max_findings=80):
        actor=actor or self.actor;self._run(case_id,parent_run_id)
        orch=self._latest_orchestration(case_id,parent_run_id,actor)
        sup=self._latest_supervisor(case_id,parent_run_id)
        if not sup:raise RuntimeError("Build276 supervisor brief required")
        existing=self.db.one("SELECT run_id FROM redteam_runs_277 WHERE case_id=? AND parent_run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(case_id,parent_run_id))
        # Each explicit run is a new immutable challenge pass; no mutation of previous output.
        rid=_id("red277")
        self.db.execute("""INSERT INTO redteam_runs_277
          (run_id,case_id,parent_run_id,orchestration_id,supervisor_brief_id,mode,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (rid,case_id,parent_run_id,orch["orchestration_id"],sup["brief_id"],"adversarial_local_only","completed",actor,_now(),
           _hash({"case":case_id,"parent":parent_run_id,"orch":orch["orchestration_id"],"sup":sup["brief_id"]})))
        f=[]

        # Reasoning epistemics.
        counts={t:(self.db.one("SELECT COUNT(*) n FROM reasoning_ledger_275 WHERE case_id=? AND parent_run_id=? AND entry_type=?",(case_id,parent_run_id,t)) or {"n":0})["n"]
                for t in ("observation","interpretation","hypothesis","assumption","contradiction")}
        if counts["contradiction"]:
            f.append(self._finding(rid,case_id,parent_run_id,"unresolved_contradictions","high",
                f"{counts['contradiction']} explicit contradiction(s) remain in the reasoning ledger.",
                "reasoning_ledger_275",parent_run_id,"Re-check each contradiction against primary evidence and state whether it remains unresolved.","lower_to_analysis_basis"))
        if counts["assumption"]:
            f.append(self._finding(rid,case_id,parent_run_id,"hidden_or_explicit_assumptions","moderate",
                f"{counts['assumption']} assumption(s) remain analytically material.",
                "reasoning_ledger_275",parent_run_id,"Seek evidence that independently tests or falsifies each material assumption.","retain_analysis_basis"))
        if counts["hypothesis"]==1:
            f.append(self._finding(rid,case_id,parent_run_id,"missing_alternative_hypothesis","high",
                "Only one hypothesis is present in the reasoning ledger; confirmation bias risk is elevated.",
                "reasoning_ledger_275",parent_run_id,"Generate at least one plausible alternative or null hypothesis and define disconfirming observations.","lower_to_analysis_basis"))

        # Supporting vs contradicting findings.
        supports=(self.db.one("SELECT COUNT(*) n FROM ai_research_findings_263 WHERE case_id=? AND stance='supports'",(case_id,)) or {"n":0})["n"]
        contra=(self.db.one("SELECT COUNT(*) n FROM ai_research_findings_263 WHERE case_id=? AND stance='contradicts'",(case_id,)) or {"n":0})["n"]
        if contra and supports>=max(3,contra*4):
            f.append(self._finding(rid,case_id,parent_run_id,"confirmation_bias","high",
                f"Supporting findings ({supports}) substantially outnumber contradicting findings ({contra}); minority counterevidence must remain visible.",
                "ai_research_findings_263",parent_run_id,"Re-summarize the case with contradiction-first ordering and verify whether supporting items are independent.","lower_to_analysis_basis"))
        elif contra:
            f.append(self._finding(rid,case_id,parent_run_id,"counterevidence_present","moderate",
                f"{contra} contradicting finding(s) are present and must be preserved in all downstream products.",
                "ai_research_findings_263",parent_run_id,"Verify every downstream summary/product retains these contradictory evidence references.","retain"))

        # Source laundering / repeated origin.
        roll=self.db.one("SELECT * FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=? ORDER BY revision_no DESC LIMIT 1",(case_id,parent_run_id))
        if roll:
            raw=int(roll["raw_source_count"]);orig=int(roll["origin_cluster_count"]);deps=int(roll["cross_wave_dependency_count"])
            if raw and orig and raw>=orig*2:
                f.append(self._finding(rid,case_id,parent_run_id,"source_laundering_or_repetition","high",
                    f"{raw} raw source observations collapse to {orig} origin candidates; repetition may inflate apparent corroboration.",
                    "source_family_rollups_271",str(roll.get("rollup_id","")), "Re-rank support by origin cluster rather than article count and seek independent primary origins.","lower_to_analysis_basis"))
            if deps:
                f.append(self._finding(rid,case_id,parent_run_id,"cross_wave_source_dependency","moderate",
                    f"{deps} cross-wave source dependencies are recorded.",
                    "source_family_rollups_271",str(roll.get("rollup_id","")), "Ensure later collection waves did not merely rediscover the same source family.","retain"))

        # Entity/network overreach.
        unreviewed=(self.db.one("""SELECT COUNT(*) n FROM relation_candidates_266 r
          LEFT JOIN relation_reviews_266 v ON v.relation_id=r.relation_id
          WHERE r.case_id=? AND v.review_id IS NULL""",(case_id,)) or {"n":0})["n"]
        if unreviewed:
            f.append(self._finding(rid,case_id,parent_run_id,"unreviewed_network_relations","moderate",
                f"{unreviewed} relation candidate(s) remain without independent review.",
                "relation_candidates_266",parent_run_id,"Independently review high-centrality edges before relying on paths or brokerage metrics.","retain_analysis_basis"))
        paths=(self.db.one("SELECT COUNT(*) n FROM network_paths_267 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        brokers=(self.db.one("SELECT COUNT(*) n FROM brokerage_metrics_267 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        if paths or brokers:
            f.append(self._finding(rid,case_id,parent_run_id,"network_semantic_overreach","moderate",
                f"Case contains {paths} network path(s) and {brokers} brokerage metric(s); topology alone cannot establish influence, control or guilt.",
                "network_paths_267",parent_run_id,"Check every network-derived statement for explicit relational evidence and remove causal/intent language unsupported by sources.","retain_analysis_basis"))

        # Temporal causality.
        tconf=(self.db.one("SELECT COUNT(*) n FROM temporal_assessments_265 WHERE case_id=? AND assessment_class LIKE '%conflict%'",(case_id,)) or {"n":0})["n"]
        if tconf:
            f.append(self._finding(rid,case_id,parent_run_id,"temporal_causality_or_sequence_risk","high",
                f"{tconf} temporal conflict assessment(s) remain; chronology should not be converted into causal sequence.",
                "temporal_assessments_265",parent_run_id,"Resolve chronology with provenance-bound dates before any causal interpretation.","lower_to_analysis_basis"))

        # ACH truth overreach.
        ach=self.db.one("SELECT * FROM ach_briefs_269 WHERE case_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",(case_id,parent_run_id))
        if ach:
            least=_loads(ach["least_inconsistent_json"],[])
            inc=_loads(ach["inconsistency_summary_json"],{})
            if least:
                f.append(self._finding(rid,case_id,parent_run_id,"ach_truth_overreach","moderate",
                    f"ACH least-inconsistent set is {least}; this is not a truth ranking or probability.",
                    "ach_briefs_269",ach["brief_id"],"Verify supervisor and publication language says 'least inconsistent' rather than 'true', 'proven' or probability.","retain_analysis_basis"))
            if isinstance(inc,dict) and sum(int(v) for v in inc.values())>0:
                f.append(self._finding(rid,case_id,parent_run_id,"ach_inconsistency","high",
                    "ACH still contains inconsistent evidence against one or more hypotheses.",
                    "ach_briefs_269",ach["brief_id"],"Prioritize discriminating evidence that could falsify surviving hypotheses.","lower_to_analysis_basis"))

        # Narrative synchrony boundary.
        ns=(self.db.one("SELECT COUNT(*) n FROM claim_diffusion_edges_272 WHERE case_id=?",(case_id,)) or {"n":0})["n"]
        if ns:
            f.append(self._finding(rid,case_id,parent_run_id,"narrative_coordination_overreach","moderate",
                f"{ns} narrative diffusion edge(s) exist; diffusion/synchrony does not establish coordination.",
                "claim_diffusion_edges_272",parent_run_id,"Seek independent evidence of coordination, tasking or common control before making coordination claims.","retain_analysis_basis"))

        # Document quarantine/sensitive records.
        sens=(self.db.one("SELECT COUNT(*) n FROM document_candidates_273 WHERE case_id=? AND sensitivity_class IN ('special_category','high_impact_sensitive','controlled_personal_record')",(case_id,)) or {"n":0})["n"]
        if sens:
            f.append(self._finding(rid,case_id,parent_run_id,"sensitive_document_overreach","high",
                f"{sens} sensitive/controlled personal document candidate(s) exist.",
                "document_candidates_273",parent_run_id,"Keep these records restricted, independently verify identity, and exclude them from public-safe summaries unless explicitly reviewed.","lower_to_internal_only"))

        # Supervisor assertion ceiling check.
        ceiling=str(sup["assertion_ceiling"])
        material=sum(1 for x in f if x["severity"] in MATERIAL)
        if material and ceiling=="evidence_summary_only":
            f.append(self._finding(rid,case_id,parent_run_id,"assertion_ceiling_overreach","critical",
                "Supervisor assertion ceiling is evidence_summary_only despite material red-team challenges.",
                "supervisor_briefs_276",sup["brief_id"],"Lower the assertion ceiling before any publication review.","lower_to_analysis_basis"))

        # Keep bounded.
        f=f[:max(1,min(int(max_findings),80))]
        # Gap proposals for material challenges, no execution.
        gaps=[]
        for x in f:
            if x["severity"] not in MATERIAL:continue
            gid=_id("rtgap277")
            query="Suche unabhängige Primärquellen und Gegenbelege zur Red-Team-Prüfung: "+x["challenge_class"].replace("_"," ")
            payload={"class":x["challenge_class"],"countercheck":x["required_countercheck"],"query":query}
            self.db.execute("""INSERT INTO redteam_gap_proposals_277
              (gap_id,brief_id,case_id,parent_run_id,challenge_class,objective,suggested_query,requires_new_ok,
               external_action_executed,status,created_at,payload_sha256)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
              (gid,"",case_id,parent_run_id,x["challenge_class"],x["required_countercheck"],query,1,0,"proposed_requires_ok",_now(),_hash(payload)))
            gaps.append({"gap_id":gid,"challenge_class":x["challenge_class"],"suggested_query":query,"requires_new_ok":True,"executed":False})

        audit=self.audit_opsec(case_id=case_id,parent_run_id=parent_run_id,orchestration_id=orch["orchestration_id"])
        critical=sum(1 for x in f if x["severity"]=="critical");high=sum(1 for x in f if x["severity"]=="high")
        recommended=ceiling
        if audit["result"]!="pass":recommended="internal_analysis_only_opsec_hold"
        elif critical or high or counts["contradiction"] or counts["assumption"]:recommended="analysis_basis_only"
        classes=sorted({x["challenge_class"] for x in f})
        checks=[x["required_countercheck"] for x in f if x["severity"] in MATERIAL]
        summary=(f"Red-Team Analyst 2.0 surfaced {len(f)} challenge(s): {critical} critical, {high} high. "
                 f"Recommended assertion ceiling: {recommended}. Findings challenge analysis only; evidence, claims and identities were not mutated.")
        bid=_id("rtbrief277")
        self.db.execute("""INSERT INTO redteam_briefs_277
          (brief_id,run_id,case_id,parent_run_id,finding_count,critical_count,high_count,challenge_classes_json,
           required_counterchecks_json,recommended_assertion_ceiling,summary,status,created_by,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (bid,rid,case_id,parent_run_id,len(f),critical,high,_canon(classes),_canon(checks),recommended,summary,
           "analysis_challenge",actor,_now(),_hash({"classes":classes,"recommended":recommended,"counts":[critical,high]})))
        # Backfill immutable proposal rows is impossible by design, so proposals deliberately remain brief_id="" and are linked by parent run/class.
        self._event(case_id,"redteam_2_completed","redteam_run",rid,actor,{"brief_id":bid,"findings":len(f),"opsec":audit["result"]})
        return {"run_id":rid,"brief_id":bid,"findings":f,"gap_proposals":gaps,"opsec_audit":audit,
                "summary":summary,"recommended_assertion_ceiling":recommended,
                "evidence_mutated":False,"claims_mutated":False,"identities_mutated":False,
                "external_actions_executed":False}

    def audit_opsec(self,*,case_id,parent_run_id,orchestration_id):
        prior=self.db.one("SELECT * FROM agent_opsec_audits_276 WHERE orchestration_id=?",(orchestration_id,))
        direct=int(prior["direct_agent_egress_count"]) if prior else 0
        private=int(prior["raw_private_identifier_count"]) if prior else 0
        secrets=int(prior["secret_pattern_count"]) if prior else 0
        scope=int(prior["cross_case_scope_violation_count"]) if prior else 0
        # Build277 itself exposes no APIs for mutation/publication/host reconfiguration.
        recursive=mutation=publication=route=prompt_auth=0
        result="pass" if not any((direct,private,secrets,scope,recursive,mutation,publication,route,prompt_auth)) else "fail"
        aid=_id("opa277");payload={"direct":direct,"private":private,"secrets":secrets,"scope":scope,"result":result}
        self.db.execute("""INSERT INTO opsec_adversarial_audits_277
          (audit_id,case_id,parent_run_id,orchestration_id,direct_agent_egress_count,recursive_spawn_count,
           raw_private_identifier_count,secret_pattern_count,cross_case_scope_violation_count,evidence_mutation_attempt_count,
           publication_attempt_count,route_reconfiguration_attempt_count,prompt_injection_authority_count,result,created_at,payload_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (aid,case_id,parent_run_id,orchestration_id,direct,recursive,private,secrets,scope,mutation,publication,route,prompt_auth,result,_now(),_hash(payload)))
        return {"audit_id":aid,"result":result,"direct_agent_egress_count":direct,"recursive_spawn_count":recursive,
                "raw_private_identifier_count":private,"secret_pattern_count":secrets,"cross_case_scope_violation_count":scope,
                "evidence_mutation_attempt_count":mutation,"publication_attempt_count":publication,
                "route_reconfiguration_attempt_count":route,"prompt_injection_authority_count":prompt_auth,
                "automatic_ip_rotation":False,"disposable_email_generation":False}

    def review_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one("SELECT * FROM redteam_briefs_277 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        if not b:raise KeyError("red-team brief")
        reviewer=reviewer or self.actor
        if reviewer==b["created_by"]:raise ValueError("independent reviewer required")
        if decision not in {"retain_challenges","needs_more_evidence","challenge_redteam","reject_redteam"}:raise ValueError("invalid decision")
        rv=_id("rtrv277")
        self.db.execute("INSERT INTO redteam_reviews_277 VALUES(?,?,?,?,?,?,?,?)",
            (rv,brief_id,case_id,decision,str(rationale)[:2000],reviewer,_now(),_hash({"d":decision,"r":rationale})))
        return {"review_id":rv,"decision":decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one("SELECT * FROM redteam_briefs_277 WHERE brief_id=? AND case_id=?",(brief_id,case_id))
        rv=self.db.one("SELECT * FROM redteam_reviews_277 WHERE brief_id=?",(brief_id,))
        audit=self.db.one("SELECT * FROM opsec_adversarial_audits_277 WHERE case_id=? AND parent_run_id=? ORDER BY rowid DESC LIMIT 1",
                          (case_id,b["parent_run_id"] if b else ""))
        if not b or not rv or rv["decision"]!="retain_challenges" or not audit or audit["result"]!="pass":
            raise PermissionError("independently retained OPSEC-clean red-team brief required")
        return self.training.add_example(case_id=case_id,
            instruction="Red-team an investigative analysis for unsupported factual language, confirmation bias, source laundering, identity mismatch, causal overreach, guilt-by-association, missing alternatives and assertion-ceiling errors. Preserve evidence and counterevidence; do not mutate facts, identities, network settings or publication state.",
            response=_canon({"summary":b["summary"],"recommended_assertion_ceiling":b["recommended_assertion_ceiling"],
                             "finding_count":b["finding_count"],"critical_count":b["critical_count"],"high_count":b["high_count"]}),
            context={"build":"277.0","red_team_2":True,"challenge_only":True,"direct_egress":False,"human_review_required":True},
            evidence_refs=[],language="de",source_type="build277_reviewed_redteam_brief",source_ref=brief_id,
            created_by=actor or self.actor,confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")

    # Preserve full AI investigator chain and add Red-Team 2.0 after supervisor synthesis.
    def execute_initial_run(self,**kwargs):
        out=self.coanalyst276.execute_initial_run(**kwargs)
        out["red_team_analyst_2_277"]=self.run_red_team(case_id=kwargs["case_id"],parent_run_id=kwargs["run_id"],actor=kwargs.get("approved_by") or self.actor)
        return out
    def approve_and_execute_wave(self,**kwargs):
        out=self.coanalyst276.approve_and_execute_wave(**kwargs)
        plan=self.collection270.plan(kwargs["plan_id"])
        out["red_team_analyst_2_277"]=self.run_red_team(case_id=kwargs["case_id"],parent_run_id=plan["parent_run_id"],actor=kwargs.get("approved_by") or self.actor)
        out["requires_new_ok_for_next_wave"]=True
        return out
    def create_person_document_run(self,**kwargs):return self.coanalyst276.create_person_document_run(**kwargs)
    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        upstream=self.coanalyst276.analyze_family(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)
        return {**upstream,"red_team_analyst_2_277":self.run_red_team(case_id=case_id,parent_run_id=parent_run_id,actor=actor or self.actor)}
    def augment_collection_plan(self,**kwargs):return self.coanalyst276.augment_collection_plan(**kwargs)

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_redteam_benchmarks_277 WHERE review_status='reviewed'") or {"n":0})["n"]
        fam=(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_redteam_benchmarks_277") or {"n":0})["n"]
        return {"reviewed_benchmarks":n,"task_families":fam,"red_team_2":True,"confirmation_bias_check":True,
                "source_laundering_check":True,"causal_overreach_check":True,"assertion_ceiling_check":True,
                "automatic_model_activation":False,"automatic_adapter_activation":False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_277 WHERE review_status='verified'") or {"n":0})["n"]
        return {"verified_controls":n,"direct_redteam_egress":0,"evidence_mutation_authority":0,"automatic_publication":0,
                "host_route_reconfiguration":0,"recursive_agent_spawning":0,"automatic_ip_rotation":0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={"build":"277.0","main_goal":bool(self.db.one("SELECT name FROM sqlite_master WHERE name='redteam_runs_277'")),
           "ai_delta":a["reviewed_benchmarks"]>=76 and a["task_families"]>=30,
           "opsec_delta":o["verified_controls"]>=76 and o["direct_redteam_egress"]==0 and o["evidence_mutation_authority"]==0,
           "capability_regression":"ai_coanalyst_orchestrator_276" in caps and "agent_egress_permission_broker_276" in caps,
           "parent_build_gate":self.coanalyst276.qualified_gate()["release_ready"]}
        g["release_ready"]=all(g[k] for k in ("main_goal","ai_delta","opsec_delta","capability_regression","parent_build_gate"));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ""),quote=True)
        briefs=self.db.all("SELECT * FROM redteam_briefs_277 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        rows="".join(f"<tr><td><code>{e(b['parent_run_id'])}</code></td><td>{e(b['finding_count'])}</td><td>{e(b['critical_count'])}</td><td>{e(b['high_count'])}</td><td>{e(b['recommended_assertion_ceiling'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all("SELECT * FROM opsec_adversarial_audits_277 WHERE case_id=? ORDER BY created_at DESC LIMIT 12",(case_id,))
        arows="".join(f"<tr><td>{e(a['parent_run_id'])}</td><td>{e(a['direct_agent_egress_count'])}</td><td>{e(a['evidence_mutation_attempt_count'])}</td><td>{e(a['publication_attempt_count'])}</td><td>{e(a['result'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Red-Team Analyst 2.0 · Build 277</h2>
        <p><b>Supervisor/Reasoning → adversarial challenge → countercheck requirements → assertion-ceiling recommendation → research gaps.</b></p>
        <p>Red-Team ist challenge-only: keine Evidence-/Claim-/Identity-Mutation, kein direkter Egress, keine Veröffentlichung und keine Host-/Proxy-Rekonfiguration.</p>
        <form method='post' action='/build277/run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='parent_run_id' placeholder='Parent Research Run ID' required><button>Red-Team 2.0 ausführen</button></form>
        <h3>Red-Team Briefs</h3><table><tr><th>Run</th><th>Findings</th><th>Critical</th><th>High</th><th>Ceiling</th><th>Summary</th></tr>{rows or '<tr><td colspan="6">Noch kein Red-Team-Lauf.</td></tr>'}</table>
        <details><summary><b>Red-Team Brief unabhängig reviewen</b></summary><form method='post' action='/build277/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Brief ID' required><select name='decision'><option>retain_challenges</option><option>needs_more_evidence</option><option>challenge_redteam</option><option>reject_redteam</option></select><textarea name='rationale' required></textarea><button>Review speichern</button></form></details>
        <h3>Adversarial OPSEC Audit</h3><table><tr><th>Run</th><th>Direct Egress</th><th>Evidence Mutation</th><th>Publication</th><th>Result</th></tr>{arows or '<tr><td colspan="5">Noch kein Audit.</td></tr>'}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one("SELECT event_hash FROM build277_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1",(cid,));ph=prev["event_hash"] if prev else "GENESIS"
        eid=_id("evt277");now=_now();data={"event_id":eid,"case_id":cid,"event_type":etype,"object_type":otype,"object_id":oid,"actor":actor,"payload":payload,"previous_hash":ph,"created_at":now}
        self.db.execute("INSERT INTO build277_events VALUES(?,?,?,?,?,?,?,?,?,?)",(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
