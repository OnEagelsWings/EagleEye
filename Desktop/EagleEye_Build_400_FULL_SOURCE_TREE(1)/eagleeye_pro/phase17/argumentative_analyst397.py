from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping

BUILD = "397.0"
POLICY_ID = "phase17.argumentative-ai-analyst.v397"
CONFIRM_REVIEW = "REVIEW ANALYST RECOMMENDATION"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


def _sid(prefix: str) -> str:
    return prefix + "_" + secrets.token_hex(12)


class ArgumentativeAIAnalyst397:
    """Evidence-grounded argument review without truth scoring or execution authority."""

    def __init__(self, db: Any, audit: Any, *, state395: Any, reconciliation396: Any, intake389: Any, review390: Any, synthesis391: Any, governance: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.state395 = state395
        self.reconciliation396 = reconciliation396
        self.intake389 = intake389
        self.review390 = review390
        self.synthesis391 = synthesis391
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analyst_assessment_397(
              assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
              target_type TEXT NOT NULL, target_id TEXT NOT NULL,
              active_node_id TEXT NOT NULL, active_generation INTEGER NOT NULL,
              proposition TEXT NOT NULL, support_groups INTEGER NOT NULL,
              contradiction_groups INTEGER NOT NULL, context_groups INTEGER NOT NULL,
              unresolved_observations INTEGER NOT NULL, delta_signal_count INTEGER NOT NULL,
              stop_decision TEXT NOT NULL, decision_rationale TEXT NOT NULL,
              discriminating_questions_json TEXT NOT NULL, scan_id TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL, created_at TEXT NOT NULL,
              assessment_hash TEXT NOT NULL, record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_analyst_assessment_397_case ON analyst_assessment_397(case_id,target_type,target_id,created_at);

            CREATE TABLE IF NOT EXISTS analyst_citation_397(
              citation_id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, case_id TEXT NOT NULL,
              candidate_id TEXT NOT NULL, stance TEXT NOT NULL, independence_group TEXT NOT NULL,
              counted_as_independent INTEGER NOT NULL, phase17_source_id TEXT NOT NULL,
              canonical_source_id TEXT NOT NULL, object_id TEXT NOT NULL, object_sha256 TEXT NOT NULL,
              parse_run_id TEXT NOT NULL, record_index INTEGER NOT NULL, canonical_hash TEXT NOT NULL,
              candidate_record_hash TEXT NOT NULL, created_at TEXT NOT NULL, record_hash TEXT NOT NULL,
              UNIQUE(assessment_id,candidate_id,stance)
            );
            CREATE INDEX IF NOT EXISTS idx_analyst_citation_397_assessment ON analyst_citation_397(assessment_id,stance,independence_group);

            CREATE TABLE IF NOT EXISTS analyst_recommendation_397(
              recommendation_id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL, case_id TEXT NOT NULL,
              target_type TEXT NOT NULL, target_id TEXT NOT NULL, recommendation_type TEXT NOT NULL,
              proposal_json TEXT NOT NULL, rationale TEXT NOT NULL, status TEXT NOT NULL,
              execution_authority INTEGER NOT NULL, created_by TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_analyst_recommendation_397_case ON analyst_recommendation_397(case_id,target_type,target_id,status);

            CREATE TABLE IF NOT EXISTS analyst_recommendation_review_397(
              review_id TEXT PRIMARY KEY, recommendation_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
              disposition TEXT NOT NULL, rationale TEXT NOT NULL, reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL, record_hash TEXT NOT NULL
            );
            """
        )
        self.db.conn.commit()

    def _auth(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(dict(identity), case_id=case_id, capability=capability, object_type="phase17_argumentative_analyst_v397", object_id=object_id)

    def _active(self, case_id: str, target_type: str, target_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        if target_type not in {"claim", "hypothesis"}:
            raise ValueError("target_type must be claim or hypothesis")
        return self.state395.active_state(case_id=case_id, target_type=target_type, target_id=target_id, identity=identity)

    def _claim_ids_for_target(self, case_id: str, target_type: str, target_id: str) -> list[tuple[str, str]]:
        if target_type == "claim":
            return [(target_id, "test_target")]
        rows = self.db.all("SELECT claim_id,relation FROM hypothesis_claim_link_391 WHERE case_id=? AND hypothesis_id=? ORDER BY claim_id,relation", (case_id, target_id))
        return [(str(r["claim_id"]), str(r["relation"])) for r in rows]

    def _candidate_rows(self, case_id: str, claim_id: str, relation: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in self.db.all(
            "SELECT l.*,c.phase17_source_id,c.canonical_source_id,c.object_id,c.object_sha256,c.parse_run_id,c.record_index,c.canonical_hash,c.record_hash AS candidate_record_hash "
            "FROM investigation_claim_candidate_391 l JOIN evidence_candidate_389 c ON c.candidate_id=l.candidate_id "
            "WHERE l.case_id=? AND l.claim_id=? ORDER BY l.stance,l.independence_group,l.candidate_id",
            (case_id, claim_id),
        ):
            d = dict(r)
            stance = str(d.get("stance") or "context")
            if relation == "contradicts_hypothesis":
                stance = "contradicts" if stance == "supports" else ("supports" if stance == "contradicts" else stance)
            elif relation == "context":
                stance = "context"
            d["effective_stance"] = stance
            out.append(d)
        return out

    def _latest_scan_delta(self, case_id: str) -> tuple[str, int]:
        r = self.db.one("SELECT scan_id,delta_signal_count FROM reconciliation_scan_396 WHERE case_id=? ORDER BY created_at DESC,scan_id DESC LIMIT 1", (case_id,))
        return (str(r["scan_id"]), int(r["delta_signal_count"])) if r else ("", 0)

    def _decision(self, *, support: int, contradiction: int, unresolved: int, delta: int) -> tuple[str, str, list[str]]:
        questions: list[str] = []
        if contradiction > 0:
            questions.append("Which independently sourced observation best discriminates between the competing explanations?")
        if support < 2:
            questions.append("Can the proposition be tested against a second genuinely independent source family?")
        if unresolved > 0:
            questions.append("Which unresolved source-origin relationships must be reviewed before counting corroboration?")
        if delta > 0:
            questions.append("Do the newest delta signals materially change the active working state or merely add context?")
        if contradiction > 0:
            return "continue_discriminating_research", "Independent counterevidence remains material; continue only with discriminating evidence rather than more same-direction duplication.", questions
        if support >= 2 and unresolved == 0 and delta == 0:
            return "stop_current_question_for_human_review", "At least two countable independent support groups are present with no counted contradiction or unresolved observation; stop this question for human review, not truth acceptance.", questions
        if delta > 0:
            return "pause_and_review_revision", "New reconciliation signals exist; pause expansion and review whether the active working state needs a revision branch.", questions
        return "pause_insufficient_evidence", "The present evidence structure is insufficient for a stronger analytical conclusion; preserve uncertainty and seek a discriminating source.", questions

    def assess(self, *, case_id: str, target_type: str, target_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        target_type = str(target_type).strip().casefold()
        self._auth(identity, case_id, "case.read", target_id)
        active = self._active(case_id, target_type, target_id, identity)
        payload = dict(active.get("payload") or {})
        proposition = str(payload.get("proposition") or payload.get("statement") or "")
        claim_refs = self._claim_ids_for_target(case_id, target_type, target_id)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for claim_id, relation in claim_refs:
            for row in self._candidate_rows(case_id, claim_id, relation):
                key = (str(row["candidate_id"]), str(row["effective_stance"]))
                if key not in seen:
                    seen.add(key); rows.append(row)

        groups = {"supports": set(), "contradicts": set(), "context": set()}
        unresolved = 0
        for row in rows:
            stance = str(row.get("effective_stance") or "context")
            group = str(row.get("independence_group") or "unresolved")
            if not bool(row.get("counted_as_independent")) or group in {"", "unresolved"}:
                unresolved += 1
                continue
            groups.setdefault(stance, set()).add(group)
        scan_id, delta = self._latest_scan_delta(case_id)
        decision, rationale, questions = self._decision(support=len(groups["supports"]), contradiction=len(groups["contradicts"]), unresolved=unresolved, delta=delta)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now(); aid = _sid("aa397")
        assessment_body = {
            "assessment_id": aid, "case_id": case_id, "target_type": target_type, "target_id": target_id,
            "active_node_id": str(active.get("active_node_id") or ""), "active_generation": int(active.get("generation") or 0),
            "proposition": proposition, "support_groups": len(groups["supports"]), "contradiction_groups": len(groups["contradicts"]),
            "context_groups": len(groups["context"]), "unresolved_observations": unresolved, "delta_signal_count": delta,
            "stop_decision": decision, "decision_rationale": rationale, "discriminating_questions_json": _canon(questions),
            "scan_id": scan_id, "created_by": actor, "created_at": now,
        }
        assessment_hash = _sha(assessment_body)
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO analyst_assessment_397(assessment_id,case_id,target_type,target_id,active_node_id,active_generation,proposition,support_groups,contradiction_groups,context_groups,unresolved_observations,delta_signal_count,stop_decision,decision_rationale,discriminating_questions_json,scan_id,created_by,created_at,assessment_hash,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*assessment_body.values(), assessment_hash, _sha({**assessment_body, "assessment_hash": assessment_hash})))
            citations=[]
            for row in rows:
                cid = _sid("cite397")
                cbody = {
                    "citation_id": cid, "assessment_id": aid, "case_id": case_id, "candidate_id": str(row["candidate_id"]),
                    "stance": str(row.get("effective_stance") or "context"), "independence_group": str(row.get("independence_group") or "unresolved"),
                    "counted_as_independent": int(bool(row.get("counted_as_independent"))), "phase17_source_id": str(row.get("phase17_source_id") or ""),
                    "canonical_source_id": str(row.get("canonical_source_id") or ""), "object_id": str(row.get("object_id") or ""),
                    "object_sha256": str(row.get("object_sha256") or ""), "parse_run_id": str(row.get("parse_run_id") or ""),
                    "record_index": int(row.get("record_index") or 0), "canonical_hash": str(row.get("canonical_hash") or ""),
                    "candidate_record_hash": str(row.get("candidate_record_hash") or ""), "created_at": now,
                }
                self.db.execute("INSERT INTO analyst_citation_397(citation_id,assessment_id,case_id,candidate_id,stance,independence_group,counted_as_independent,phase17_source_id,canonical_source_id,object_id,object_sha256,parse_run_id,record_index,canonical_hash,candidate_record_hash,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*cbody.values(), _sha(cbody)))
                citations.append(cbody)
        self.audit.log("assess", "analyst_assessment_397", aid, case_id, {"target_type": target_type, "target_id": target_id, "stop_decision": decision, "truth_determined": False})
        return self.assessment(case_id=case_id, assessment_id=aid, identity=identity)

    def assessment(self, *, case_id: str, assessment_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None: self._auth(identity, case_id, "case.read", assessment_id)
        r = self.db.one("SELECT * FROM analyst_assessment_397 WHERE case_id=? AND assessment_id=?", (case_id, assessment_id))
        if not r: raise KeyError(assessment_id)
        out = dict(r); out["discriminating_questions"] = _j(out.pop("discriminating_questions_json", "[]"), [])
        out["citations"] = [dict(x) for x in self.db.all("SELECT * FROM analyst_citation_397 WHERE assessment_id=? ORDER BY stance,independence_group,citation_id", (assessment_id,))]
        out.update({"truth_determined": False, "probability_assigned": False, "execution_authority": False})
        return out

    def propose_recommendation(self, *, case_id: str, assessment_id: str, identity: Mapping[str, Any], recommendation_type: str, proposal: Mapping[str, Any], rationale: str) -> dict[str, Any]:
        self._auth(identity, case_id, "dossier.write", assessment_id)
        a = self.assessment(case_id=case_id, assessment_id=assessment_id)
        if recommendation_type not in {"claim_revision", "hypothesis_revision", "reasoning_plan_revision", "additional_discriminating_research", "human_review_only"}:
            raise ValueError("unsupported recommendation_type")
        if len(str(rationale).strip()) < 12: raise ValueError("rationale required")
        now=_now(); rid=_sid("rec397"); actor=str(identity.get("username") or self.actor)[:120]
        body={"recommendation_id":rid,"assessment_id":assessment_id,"case_id":case_id,"target_type":a["target_type"],"target_id":a["target_id"],"recommendation_type":recommendation_type,"proposal_json":_canon(dict(proposal)),"rationale":str(rationale)[:4000],"status":"proposal_needs_review","execution_authority":0,"created_by":actor,"created_at":now,"updated_at":now}
        self.db.execute("INSERT INTO analyst_recommendation_397(recommendation_id,assessment_id,case_id,target_type,target_id,recommendation_type,proposal_json,rationale,status,execution_authority,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(*body.values(),_sha(body)))
        return self.recommendation(case_id=case_id,recommendation_id=rid,identity=identity)

    def review_recommendation(self, *, case_id: str, recommendation_id: str, identity: Mapping[str, Any], disposition: str, rationale: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation).strip().upper()!=CONFIRM_REVIEW: raise PermissionError(f"explicit confirmation {CONFIRM_REVIEW} required")
        self._auth(identity, case_id, "dossier.write", recommendation_id)
        r=self.db.one("SELECT * FROM analyst_recommendation_397 WHERE case_id=? AND recommendation_id=?",(case_id,recommendation_id))
        if not r: raise KeyError(recommendation_id)
        if r["status"]!="proposal_needs_review": raise PermissionError("recommendation already reviewed")
        disp=str(disposition).strip().casefold()
        if disp not in {"approve_for_manual_revision","reject","needs_more_analysis"}: raise ValueError("invalid disposition")
        now=_now(); actor=str(identity.get("username") or self.actor)[:120]; rev={"review_id":_sid("rrev397"),"recommendation_id":recommendation_id,"case_id":case_id,"disposition":disp,"rationale":str(rationale)[:4000],"reviewed_by":actor,"reviewed_at":now}
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO analyst_recommendation_review_397(review_id,recommendation_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",(*rev.values(),_sha(rev)))
            new_status="reviewed_for_manual_revision" if disp=="approve_for_manual_revision" else ("rejected" if disp=="reject" else "needs_more_analysis")
            d=dict(r); body={k:d[k] for k in d if k!="record_hash"}; body["status"]=new_status; body["updated_at"]=now
            self.db.execute("UPDATE analyst_recommendation_397 SET status=?,updated_at=?,record_hash=? WHERE recommendation_id=?",(new_status,now,_sha(body),recommendation_id))
        return self.recommendation(case_id=case_id,recommendation_id=recommendation_id,identity=identity)

    def recommendation(self, *, case_id: str, recommendation_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:self._auth(identity,case_id,"case.read",recommendation_id)
        r=self.db.one("SELECT * FROM analyst_recommendation_397 WHERE case_id=? AND recommendation_id=?",(case_id,recommendation_id))
        if not r:raise KeyError(recommendation_id)
        d=dict(r); d["proposal"]=_j(d.pop("proposal_json","{}"),{}); d["execution_authority"]=bool(d["execution_authority"]); d["automatic_upstream_mutation"]=False; d["truth_determined"]=False; return d

    def verify_assessment(self, *, case_id: str, assessment_id: str) -> dict[str, Any]:
        r=self.db.one("SELECT * FROM analyst_assessment_397 WHERE case_id=? AND assessment_id=?",(case_id,assessment_id))
        if not r:return {"valid":False,"reason":"missing"}
        d=dict(r); rec=d.pop("record_hash"); expected=_sha(d); valid=rec==expected
        for c in self.db.all("SELECT * FROM analyst_citation_397 WHERE assessment_id=?",(assessment_id,)):
            cd=dict(c); cr=cd.pop("record_hash"); valid=valid and cr==_sha(cd)
            cand=self.db.one("SELECT record_hash FROM evidence_candidate_389 WHERE candidate_id=?",(c["candidate_id"],)); valid=valid and bool(cand) and str(cand["record_hash"])==str(c["candidate_record_hash"])
        return {"valid":bool(valid),"assessment_id":assessment_id}

    def status(self) -> dict[str, Any]:
        return {"build":BUILD,"policy":POLICY_ID,"precise_evidence_citations":True,"source_independence_aware":True,"support_counterevidence_separated":True,"discriminating_questions":True,"explicit_stop_decisions":True,"reconciliation_delta_aware":True,"review_required_recommendations":True,"automatic_upstream_mutation":False,"automatic_truth_acceptance":False,"truth_probability":False,"automatic_evidence_promotion":False,"automatic_go_issuance":False,"automatic_live_confirmation":False,"direct_network_fetch":False,"execution_authority":False}
