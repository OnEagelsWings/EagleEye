from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(v: Any) -> str:
    data = v if isinstance(v, bytes) else _canon(v).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _loads(v: str | None, default: Any) -> Any:
    try:
        return json.loads(v) if v else default
    except Exception:
        return default


def _clamp(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return 0.0


def _txt(v: Any, n: int = 10000) -> str:
    return str(v or "").replace("\x00", "").strip()[:n]


_REASONING_TERMS = re.compile(r"(?i)(gegenhypothes|counter[- ]?hypothes|alternativ(?:e|en)? hypothes|alternative explanation|alternative erklär)")
_CONTRADICTION_TERMS = re.compile(r"(?i)(widerspruch|widerspricht|gegenbeleg|contradict|counter[- ]?evidence|conflict|ungeklärt|unresolved)")
_CORRECTION_TERMS = re.compile(r"(?i)(korrig|revid|berichtige|correct|revise|supersed|previous assessment|frühere einschätzung)")


class Build241InvestigativeReasoningWorkflowService:
    """Governed hypothesis/counter-hypothesis workflow for the existing Co-AI chat.

    This layer never performs an external action. It records evidence-bound reasoning
    cycles, independent review, information-gain next-step proposals and explicit
    corrections. It extends Build 227/240 instead of creating another chat engine.
    """

    BUILD = "241.0"

    def __init__(self, db: Any, audit: Any, *, conversation: Any, co_ai: Any, training: Any, actor: str = "local-analyst"):
        self.db, self.audit, self.conversation, self.co_ai, self.training, self.actor = db, audit, conversation, co_ai, training, actor
        self.conversation._reasoning_workflow_241 = self
        try:
            self.conversation.conversation._reasoning_workflow_241 = self
        except Exception:
            pass

    # ---------- canonical evidence boundary ----------
    def _accepted_refs(self, case_id: str) -> set[str]:
        state = self.co_ai.case_state(case_id=case_id, limit=150)
        refs: set[str] = set()
        for ev in state.get("accepted_integrity_checked_evidence", []):
            refs.update(str(x) for x in (ev.get("vault_item_id"), ev.get("canonical_evidence_object_id")) if x)
        for claim in state.get("verified_claims", []):
            if claim.get("verified_claim_id"):
                refs.add(str(claim["verified_claim_id"]))
        for edge in state.get("accepted_graph_edges", []):
            for key in ("id", "link_id", "edge_id"):
                if edge.get(key):
                    refs.add(str(edge[key]))
        return refs

    def _validate_refs(self, case_id: str, refs: Sequence[str]) -> list[str]:
        clean = list(dict.fromkeys(_txt(x, 300) for x in refs if _txt(x, 300)))[:100]
        allowed = self._accepted_refs(case_id)
        unknown = [x for x in clean if x not in allowed]
        if unknown:
            raise ValueError("reasoning references must resolve to accepted/reviewed case evidence: " + ", ".join(unknown[:5]))
        return clean

    # ---------- reasoning cycles ----------
    def create_cycle(
        self,
        *,
        case_id: str,
        question: str,
        primary_hypothesis: str,
        counter_hypothesis: str,
        primary_confidence: float,
        counter_confidence: float,
        supporting_refs: Sequence[str],
        counter_supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str],
        evidence_gaps: Sequence[str],
        actor: str,
        confirmation: str,
        session_id: str = "",
        turn_id: str = "",
        origin: str = "investigator",
        supersedes_cycle_id: str = "",
    ) -> dict[str, Any]:
        if confirmation != f"REASONING CYCLE 241 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self.co_ai.kernel.cases.get_case(case_id)
        question = _txt(question, 5000)
        primary = _txt(primary_hypothesis, 8000)
        counter = _txt(counter_hypothesis, 8000)
        if not question or not primary or not counter:
            raise ValueError("question, primary hypothesis and counter-hypothesis are required")
        support = self._validate_refs(case_id, supporting_refs)
        counter_support = self._validate_refs(case_id, counter_supporting_refs)
        contradict = self._validate_refs(case_id, contradicting_refs)
        gaps = list(dict.fromkeys(_txt(x, 1200) for x in evidence_gaps if _txt(x, 1200)))[:50]
        if supersedes_cycle_id:
            prior = self.cycle(supersedes_cycle_id)
            if prior["case_id"] != case_id:
                raise ValueError("cross-case supersession blocked")
        state_sha = self.co_ai.case_state(case_id=case_id, limit=80)["state_sha256"]
        cid, now = new_id("reason241"), now_ts()
        payload = {
            "cycle_id": cid, "case_id": case_id, "session_id": _txt(session_id, 200), "turn_id": _txt(turn_id, 200),
            "question": question, "primary_hypothesis": primary, "counter_hypothesis": counter,
            "primary_confidence": _clamp(primary_confidence), "counter_confidence": _clamp(counter_confidence),
            "supporting_refs": support, "counter_supporting_refs": counter_support, "contradicting_refs": contradict,
            "evidence_gaps": gaps, "origin": _txt(origin, 100) or "investigator", "supersedes_cycle_id": _txt(supersedes_cycle_id, 200),
            "state_sha256": state_sha, "created_by": actor, "created_at": now,
        }
        self.db.execute(
            "INSERT INTO reasoning_cycles_241 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, case_id, payload["session_id"], payload["turn_id"], question, primary, counter, payload["primary_confidence"], payload["counter_confidence"], dumps(support), dumps(counter_support), dumps(contradict), dumps(gaps), payload["origin"], payload["supersedes_cycle_id"], state_sha, actor, now, _hash(payload)),
        )
        self._event(case_id, "reasoning_cycle_created", "reasoning_cycle", cid, {"state_sha256": state_sha, "origin": payload["origin"]}, actor)
        return self.cycle(cid)

    def cycle(self, cycle_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM reasoning_cycles_241 WHERE cycle_id=?", (cycle_id,))
        if not row:
            raise KeyError(cycle_id)
        d = dict(row)
        for src, dst in (("supporting_refs_json", "supporting_refs"), ("counter_supporting_refs_json", "counter_supporting_refs"), ("contradicting_refs_json", "contradicting_refs"), ("evidence_gaps_json", "evidence_gaps")):
            d[dst] = _loads(d.get(src), [])
        review = self.db.one("SELECT * FROM reasoning_reviews_241 WHERE cycle_id=?", (cycle_id,))
        d["review"] = dict(review) if review else None
        return d

    def review_cycle(self, *, cycle_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        cycle = self.cycle(cycle_id)
        if confirmation != f"REASONING REVIEW 241 {cycle_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == cycle["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "revise", "rejected"}:
            raise ValueError("invalid review decision")
        rationale = _txt(rationale, 6000)
        if len(rationale) < 30:
            raise ValueError("review rationale too short")
        if cycle.get("review"):
            raise ValueError("reasoning cycle already reviewed")
        rid, now = new_id("reasonreview241"), now_ts()
        payload = {"review_id": rid, "cycle_id": cycle_id, "case_id": cycle["case_id"], "decision": decision, "rationale": rationale, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO reasoning_reviews_241 VALUES(?,?,?,?,?,?,?,?)", (rid, cycle_id, cycle["case_id"], decision, rationale, reviewer, now, _hash(payload)))
        self._event(cycle["case_id"], "reasoning_cycle_reviewed", "reasoning_cycle", cycle_id, {"decision": decision}, reviewer)
        return dict(self.db.one("SELECT * FROM reasoning_reviews_241 WHERE review_id=?", (rid,)))

    # ---------- governed next steps ----------
    def propose_next_step(
        self, *, cycle_id: str, label: str, evidence_gap: str, expected_information_gain: float, gap_reduction: float,
        opsec_risk: float, actor: str, confirmation: str,
    ) -> dict[str, Any]:
        cycle = self.cycle(cycle_id)
        if confirmation != f"REASONING STEP 241 {cycle_id} VORSCHLAGEN":
            raise PermissionError("explicit approval required")
        if not cycle.get("review") or cycle["review"]["decision"] != "accepted":
            raise PermissionError("accepted independent reasoning review required before prioritisation")
        label, gap = _txt(label, 3000), _txt(evidence_gap, 3000)
        if not label or not gap:
            raise ValueError("label and evidence gap are required")
        info, reduction, risk = _clamp(expected_information_gain), _clamp(gap_reduction), _clamp(opsec_risk)
        priority = round(max(0.0, min(1.0, .50 * info + .35 * reduction + .15 * (1.0 - risk))), 4)
        sid, now = new_id("reasonstep241"), now_ts()
        payload = {"step_id": sid, "cycle_id": cycle_id, "case_id": cycle["case_id"], "label": label, "evidence_gap": gap, "expected_information_gain": info, "gap_reduction": reduction, "opsec_risk": risk, "priority_score": priority, "proposed_by": actor, "proposed_at": now, "automatic_execution": False}
        self.db.execute("INSERT INTO reasoning_next_steps_241 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (sid, cycle_id, cycle["case_id"], label, gap, info, reduction, risk, priority, actor, now, _hash(payload)))
        self._event(cycle["case_id"], "next_step_proposed", "reasoning_step", sid, {"priority_score": priority, "automatic_execution": False}, actor)
        return payload

    # ---------- explicit correction / supersession ----------
    def record_correction(
        self, *, prior_cycle_id: str, question: str, corrected_hypothesis: str, corrected_counter_hypothesis: str,
        primary_confidence: float, counter_confidence: float, supporting_refs: Sequence[str], counter_supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str], evidence_gaps: Sequence[str], trigger_evidence_refs: Sequence[str], rationale: str,
        actor: str, confirmation: str,
    ) -> dict[str, Any]:
        prior = self.cycle(prior_cycle_id)
        if confirmation != f"REASONING CORRECTION 241 {prior_cycle_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        trigger = self._validate_refs(prior["case_id"], trigger_evidence_refs)
        if not trigger:
            raise ValueError("at least one accepted trigger evidence reference is required")
        rationale = _txt(rationale, 6000)
        if len(rationale) < 40:
            raise ValueError("correction rationale too short")
        new_cycle = self.create_cycle(
            case_id=prior["case_id"], question=question, primary_hypothesis=corrected_hypothesis,
            counter_hypothesis=corrected_counter_hypothesis, primary_confidence=primary_confidence,
            counter_confidence=counter_confidence, supporting_refs=supporting_refs, counter_supporting_refs=counter_supporting_refs,
            contradicting_refs=contradicting_refs, evidence_gaps=evidence_gaps, actor=actor,
            confirmation=f"REASONING CYCLE 241 {prior['case_id']} ANLEGEN", session_id=prior.get("session_id", ""),
            origin="explicit_correction", supersedes_cycle_id=prior_cycle_id,
        )
        corr_id, now = new_id("reasoncorr241"), now_ts()
        payload = {"correction_id": corr_id, "case_id": prior["case_id"], "prior_cycle_id": prior_cycle_id, "new_cycle_id": new_cycle["cycle_id"], "trigger_evidence_refs": trigger, "rationale": rationale, "created_by": actor, "created_at": now, "requires_independent_review_of_new_cycle": True}
        self.db.execute("INSERT INTO reasoning_corrections_241 VALUES(?,?,?,?,?,?,?,?,?)", (corr_id, prior["case_id"], prior_cycle_id, new_cycle["cycle_id"], dumps(trigger), rationale, actor, now, _hash(payload)))
        self._event(prior["case_id"], "reasoning_correction_recorded", "reasoning_correction", corr_id, {"prior_cycle_id": prior_cycle_id, "new_cycle_id": new_cycle["cycle_id"]}, actor)
        return payload

    # ---------- context for existing chat ----------
    def workflow_context(self, *, case_id: str, limit: int = 20) -> dict[str, Any]:
        self.co_ai.kernel.cases.get_case(case_id)
        lim = max(5, min(100, int(limit)))
        accepted = self.db.all(
            """SELECT c.*,r.decision,r.rationale,r.reviewer,r.reviewed_at FROM reasoning_cycles_241 c JOIN reasoning_reviews_241 r ON r.cycle_id=c.cycle_id WHERE c.case_id=? AND r.decision='accepted' ORDER BY r.reviewed_at DESC LIMIT ?""",
            (case_id, lim),
        )
        pending = self.db.all(
            """SELECT c.* FROM reasoning_cycles_241 c LEFT JOIN reasoning_reviews_241 r ON r.cycle_id=c.cycle_id WHERE c.case_id=? AND r.review_id IS NULL ORDER BY c.created_at DESC LIMIT ?""",
            (case_id, lim),
        )
        steps = self.db.all("SELECT * FROM reasoning_next_steps_241 WHERE case_id=? ORDER BY priority_score DESC,proposed_at DESC LIMIT ?", (case_id, lim))
        corrections = self.db.all("SELECT * FROM reasoning_corrections_241 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, lim))
        def compact(row: Mapping[str, Any]) -> dict[str, Any]:
            d = dict(row)
            return {
                "cycle_id": d["cycle_id"], "question": d["question"], "primary_hypothesis": d["primary_hypothesis"],
                "counter_hypothesis": d["counter_hypothesis"], "primary_confidence": d["primary_confidence"],
                "counter_confidence": d["counter_confidence"], "supporting_refs": _loads(d.get("supporting_refs_json"), []),
                "counter_supporting_refs": _loads(d.get("counter_supporting_refs_json"), []), "contradicting_refs": _loads(d.get("contradicting_refs_json"), []),
                "evidence_gaps": _loads(d.get("evidence_gaps_json"), []), "supersedes_cycle_id": d.get("supersedes_cycle_id", ""),
            }
        return {
            "build": self.BUILD, "case_id": case_id,
            "accepted_reasoning_cycles": [compact(x) for x in accepted],
            "unreviewed_reasoning_cycles_not_facts": [compact(x) for x in pending],
            "prioritized_next_steps_proposals_only": [dict(x) for x in steps],
            "explicit_corrections": [{**dict(x), "trigger_evidence_refs": _loads(x.get("trigger_evidence_refs_json"), [])} for x in corrections],
            "rules": [
                "For every material hypothesis, consider a plausible counter-hypothesis before increasing confidence.",
                "Distinguish supporting evidence from contradicting evidence and unresolved gaps.",
                "A prioritised next step is a proposal only and must never be executed automatically.",
                "When new accepted evidence changes an assessment, state the correction explicitly and preserve the superseded reasoning cycle.",
                "Do not convert unreviewed reasoning cycles into facts.",
            ],
            "automatic_external_action": False, "human_review_required": True,
        }

    # ---------- turn quality + continuous training ----------
    def assess_turn(self, *, turn_id: str, actor: str = "coai-241") -> dict[str, Any]:
        existing = self.db.one("SELECT * FROM reasoning_turn_assessments_241 WHERE turn_id=?", (turn_id,))
        if existing:
            d = dict(existing); d["assessment"] = _loads(d.get("assessment_json"), {}); return d
        turn = self.conversation.turn_status(turn_id=turn_id)
        if turn["status"] != "completed":
            raise ValueError("only completed turns may be assessed")
        base = self.co_ai.assess_turn(turn_id=turn_id, actor="coai-240")
        answer = (turn.get("response") or {}).get("answer") or {}
        text = _canon(answer)
        state = self.co_ai.case_state(case_id=turn["case_id"], limit=80)
        wf = self.workflow_context(case_id=turn["case_id"], limit=30)
        hypotheses = list(answer.get("hypotheses") or [])
        accepted_cycles = wf.get("accepted_reasoning_cycles") or []
        balance = 1.0 if not accepted_cycles else (1.0 if len(hypotheses) >= 2 or _REASONING_TERMS.search(text) else 0.0)
        contradiction = 1.0 if not state.get("contradictions") else (1.0 if _CONTRADICTION_TERMS.search(text) else 0.0)
        needs_gap_work = bool(state.get("open_research_gaps") or state.get("open_tasks") or any(x.get("evidence_gaps") for x in accepted_cycles))
        gap = 1.0 if not needs_gap_work else (1.0 if (answer.get("open_questions") and answer.get("recommended_next_steps")) else 0.0)
        correction_requested = bool((turn.get("response") or {}).get("correction_requested"))
        correction = 1.0 if not correction_requested else (1.0 if _CORRECTION_TERMS.search(text) else 0.0)
        score = round((balance + contradiction + gap + correction) / 4.0, 4)
        gate = "REASONING_241_PASS" if base.get("gate") == "COAI_240_PASS" and score >= .95 else "REASONING_241_REVIEW"
        assessment = {
            "build240_gate": base.get("gate", "COAI_240_REVIEW"), "hypothesis_balance_score": balance,
            "contradiction_score": contradiction, "gap_score": gap, "correction_score": correction,
            "workflow_score": score, "gate": gate, "accepted_reasoning_cycle_count": len(accepted_cycles),
            "human_review_required": True, "automatic_external_action": False,
        }
        aid, now = new_id("reasonassess241"), now_ts()
        payload = {"assessment_id": aid, "case_id": turn["case_id"], "turn_id": turn_id, "build240_assessment_id": base["assessment_id"], **assessment, "assessed_by": actor, "assessed_at": now}
        self.db.execute(
            "INSERT INTO reasoning_turn_assessments_241 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, turn["case_id"], turn_id, base["assessment_id"], balance, contradiction, gap, correction, score, gate, dumps(assessment), actor, now, _hash(payload)),
        )
        self._event(turn["case_id"], "reasoning_turn_assessed", "turn", turn_id, {"gate": gate, "workflow_score": score}, actor)
        return payload

    def stage_training(self, *, case_id: str, actor: str, limit: int = 50, confirmation: str) -> dict[str, Any]:
        if confirmation != f"REASONING TRAINING 241 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        rows = self.db.all(
            """SELECT a.* FROM reasoning_turn_assessments_241 a LEFT JOIN reasoning_training_links_241 t ON t.assessment_id=a.assessment_id WHERE a.case_id=? AND a.gate='REASONING_241_PASS' AND t.training_link_id IS NULL ORDER BY a.assessed_at LIMIT ?""",
            (case_id, max(1, min(200, int(limit)))),
        )
        created: list[str] = []
        for row in rows:
            turn = self.conversation.turn_status(turn_id=row["turn_id"])
            answer = (turn.get("response") or {}).get("answer") or {}
            context = {
                "build": self.BUILD, "assessment_id": row["assessment_id"], "workflow_score": row["workflow_score"],
                "hypothesis_balance_score": row["hypothesis_balance_score"], "contradiction_score": row["contradiction_score"],
                "gap_score": row["gap_score"], "correction_score": row["correction_score"],
                "reasoning_context": self.workflow_context(case_id=case_id, limit=12), "human_review_required": True,
            }
            ex = self.training.add_example(
                case_id=case_id,
                instruction="Bearbeite eine Ermittlerfrage evidenzgebunden: prüfe Hypothese und Gegenhypothese, nenne Belege und Gegenbelege, markiere Evidenzlücken, priorisiere den nächsten Prüfzug und korrigiere frühere Einschätzungen ausdrücklich, wenn neue Evidenz dies verlangt.",
                response=_canon(answer), context=context, evidence_refs=list((turn.get("response") or {}).get("citations") or []),
                language=turn.get("message_language") or "de", source_type="co_ai_reasoning_241", source_ref=row["assessment_id"], created_by=actor,
                confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN",
            )
            lid, now = new_id("reasontrain241"), now_ts()
            payload = {"training_link_id": lid, "case_id": case_id, "assessment_id": row["assessment_id"], "training_example_id": ex["example_id"], "created_by": actor, "created_at": now}
            self.db.execute("INSERT INTO reasoning_training_links_241 VALUES(?,?,?,?,?,?,?)", (lid, case_id, row["assessment_id"], ex["example_id"], actor, now, _hash(payload)))
            created.append(ex["example_id"])
        self._event(case_id, "reasoning_training_staged", "case", case_id, {"count": len(created), "automatic_activation": False}, actor)
        return {"case_id": case_id, "created": len(created), "training_example_ids": created, "review_status": "pending", "automatic_activation": False}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        wf = self.workflow_context(case_id=case_id, limit=40)
        one = lambda q: int((self.db.one(q, (case_id,)) or {"n": 0})["n"])
        return {
            "build": self.BUILD, "case_id": case_id,
            "accepted_cycles": len(wf["accepted_reasoning_cycles"]), "pending_cycles": len(wf["unreviewed_reasoning_cycles_not_facts"]),
            "next_steps": len(wf["prioritized_next_steps_proposals_only"]), "corrections": len(wf["explicit_corrections"]),
            "turn_assessments": one("SELECT COUNT(*) n FROM reasoning_turn_assessments_241 WHERE case_id=?"),
            "training": one("SELECT COUNT(*) n FROM reasoning_training_links_241 WHERE case_id=?"),
            "automatic_external_action": False,
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e = html.escape; d = self.dashboard(case_id=case_id)
        return f"""<section class='card' id='build241_reasoning'><h2>Co-AI Investigative Reasoning Workflow + AI Training · Build 241</h2><p>Hypothese und Gegenhypothese werden evidenzgebunden, reviewpflichtig und korrigierbar geführt. Priorisierte nächste Schritte bleiben reine Vorschläge und werden nie automatisch ausgeführt.</p><div class='metrics'><div class='metric'><div class='label'>Accepted cycles</div><div class='value'>{d['accepted_cycles']}</div></div><div class='metric'><div class='label'>Pending</div><div class='value'>{d['pending_cycles']}</div></div><div class='metric'><div class='label'>Next steps</div><div class='value'>{d['next_steps']}</div></div><div class='metric'><div class='label'>Corrections</div><div class='value'>{d['corrections']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training']}</div></div></div><div class='grid'><div class='card'><h3>Reasoning-Zyklus</h3><form method='post' action='/build241/cycle'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='question' placeholder='Ermittlungsfrage' required><textarea name='primary_hypothesis' placeholder='Hypothese' required></textarea><textarea name='counter_hypothesis' placeholder='Gegenhypothese' required></textarea><input name='primary_confidence' type='number' min='0' max='1' step='.05' value='.5'><input name='counter_confidence' type='number' min='0' max='1' step='.05' value='.5'><input name='supporting_refs' placeholder='Beleg-IDs, komma-getrennt'><input name='counter_supporting_refs' placeholder='Gegenhypothese-Beleg-IDs'><input name='contradicting_refs' placeholder='Gegenbeleg-IDs'><textarea name='evidence_gaps' placeholder='Evidenzlücken, eine pro Zeile'></textarea><button>Reasoning-Zyklus anlegen</button></form></div><div class='card'><h3>Unabhängig prüfen</h3><form method='post' action='/build241/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='cycle_id' placeholder='Cycle-ID' required><select name='decision'><option>accepted</option><option>revise</option><option>rejected</option></select><textarea name='rationale' placeholder='Review-Begründung' required></textarea><button>Review speichern</button></form></div><div class='card'><h3>Nächsten Prüfzug priorisieren</h3><form method='post' action='/build241/step'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='cycle_id' placeholder='reviewte Cycle-ID' required><input name='label' placeholder='Prüfschritt' required><input name='evidence_gap' placeholder='zu schließende Evidenzlücke' required><label>Information gain <input name='expected_information_gain' type='number' min='0' max='1' step='.05' value='.7'></label><label>Gap reduction <input name='gap_reduction' type='number' min='0' max='1' step='.05' value='.7'></label><label>OPSEC risk <input name='opsec_risk' type='number' min='0' max='1' step='.05' value='.2'></label><button>Nur als Vorschlag priorisieren</button></form></div><div class='card'><h3>Einschätzung korrigieren</h3><form method='post' action='/build241/correct'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='prior_cycle_id' placeholder='bisherige Cycle-ID' required><input name='question' placeholder='aktualisierte Ermittlungsfrage' required><textarea name='corrected_hypothesis' placeholder='korrigierte Hypothese' required></textarea><textarea name='corrected_counter_hypothesis' placeholder='korrigierte Gegenhypothese' required></textarea><input name='primary_confidence' type='number' min='0' max='1' step='.05' value='.5'><input name='counter_confidence' type='number' min='0' max='1' step='.05' value='.5'><input name='supporting_refs' placeholder='Beleg-IDs'><input name='counter_supporting_refs' placeholder='Gegenhypothese-Beleg-IDs'><input name='contradicting_refs' placeholder='Gegenbeleg-IDs'><input name='trigger_evidence_refs' placeholder='neue akzeptierte Trigger-Evidence-IDs' required><textarea name='evidence_gaps' placeholder='verbleibende Evidenzlücken'></textarea><textarea name='rationale' placeholder='Warum ändert neue Evidenz die frühere Einschätzung?' required></textarea><button>Explizite Revision anlegen</button></form><p class='muted'>Der Altstand bleibt unverändert; der neue Zyklus benötigt erneut unabhängiges Review.</p></div><div class='card'><h3>Turn bewerten / Training</h3><form method='post' action='/build241/assess-turn'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='turn_id' placeholder='Build-227 Turn-ID' required><button>Reasoning prüfen</button></form><form method='post' action='/build241/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='limit' type='number' min='1' max='200' value='50'><button>Qualifizierte Reasoning-Turns für Build 228 vorbereiten</button></form><p class='muted'>Nur pending Human Review; keine automatische Modellaktivierung.</p></div></div></section>"""

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build241_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "GENESIS"
        eid, now = new_id("evt241"), now_ts()
        material = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now}
        event_hash = _hash(material)
        self.db.execute("INSERT INTO build241_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, event_hash, now))
        try:
            self.audit.log(f"build241_{event_type}", object_type, object_id, case_id, dict(payload))
        except Exception:
            pass
