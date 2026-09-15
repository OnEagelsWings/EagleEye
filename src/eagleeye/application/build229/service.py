from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()/.-]{6,}\d)(?!\w)")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


class Build229VerifiedResearchLoop2Service:
    """Claim-centred verified research loop for Phase 8.

    The loop deliberately separates discovery from verification. Retrieval and
    source intelligence prepare evidence and source strategies; they do not
    execute external sources. Claims can only become verified after explicit
    independent review, sufficient source-origin independence, a completed
    counter-evidence check and the configured score threshold.
    """

    BUILD = "229.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        retrieval: Any,
        source_intelligence: Any,
        conversation: Any,
        training: Any,
        workspace: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.retrieval, self.source_intelligence = retrieval, source_intelligence
        self.conversation, self.training, self.workspace = conversation, training, workspace
        self.actor = actor

    # ---------- loop lifecycle ----------
    def create_loop(
        self,
        *,
        case_id: str,
        session_id: str,
        objective: str,
        working_language: str = "de",
        max_cycles: int = 4,
        required_independent_origins: int = 2,
        min_verification_score: float = .72,
        require_counterevidence: bool = True,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        session = self.conversation.conversation._session(session_id)
        if session["case_id"] != case_id:
            raise ValueError("session and case mismatch")
        if confirmation != f"VERIFIED RESEARCH LOOP 229 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        objective = _text(objective, 20_000).strip()
        if len(objective) < 10:
            raise ValueError("substantive investigation objective required")
        lid, now = new_id("vloop229"), now_ts()
        payload = {
            "loop_id": lid, "case_id": case_id, "session_id": session_id,
            "objective": objective, "working_language": _text(working_language, 20) or "de",
            "status": "active", "current_cycle": 0, "max_cycles": max(1, min(int(max_cycles), 8)),
            "required_independent_origins": max(1, min(int(required_independent_origins), 4)),
            "min_verification_score": max(.5, min(float(min_verification_score), .95)),
            "require_counterevidence": bool(require_counterevidence), "stop_reason": "",
            "created_by": created_by, "created_at": now, "updated_at": now,
        }
        self.db.execute("INSERT INTO verified_research_loops_229 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            lid, case_id, session_id, objective, payload["working_language"], "active", 0, payload["max_cycles"],
            payload["required_independent_origins"], payload["min_verification_score"], int(payload["require_counterevidence"]),
            "", created_by, now, now, _hash(payload),
        ))
        self._event(case_id, "verified_research_loop_created", "verified_research_loop", lid, {
            "max_cycles": payload["max_cycles"], "required_independent_origins": payload["required_independent_origins"],
            "min_verification_score": payload["min_verification_score"], "counterevidence_required": payload["require_counterevidence"],
        }, created_by)
        return {**payload, "automatic_source_execution": False, "human_review_required": True}

    def start_cycle(
        self,
        *,
        loop_id: str,
        query_text: str,
        target_type: str = "unknown",
        target_value: str = "",
        countries: Sequence[str] = (),
        max_sources: int = 5,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        loop = self._loop(loop_id)
        if confirmation != f"VERIFIED RESEARCH CYCLE 229 {loop_id} STARTEN":
            raise PermissionError("explicit approval required")
        if loop["status"] not in {"active", "awaiting_next_cycle"}:
            raise ValueError("loop is not ready for another cycle")
        cycle_number = int(loop["current_cycle"]) + 1
        if cycle_number > int(loop["max_cycles"]):
            raise ValueError("maximum cycle count reached")
        query = _text(query_text, 30_000).strip()
        if len(query) < 5:
            raise ValueError("substantive cycle query required")

        retrieval = self.retrieval.retrieve(
            case_id=loop["case_id"], session_id=loop["session_id"], query_text=query,
            query_language=loop["working_language"], limit=max(3, min(int(max_sources) * 2, 18)),
        )
        source_strategy = self.source_intelligence.rank_sources(
            case_id=loop["case_id"], session_id=loop["session_id"], objective=query,
            target_type=target_type, target_value=target_value, language=loop["working_language"],
            countries=list(countries), budget_class="standard", max_sources=max(1, min(int(max_sources), 12)),
            require_independence=True, actor=actor,
            confirmation=f"SOURCE INTELLIGENCE 226 {loop['case_id']} BERECHNEN",
        )
        cid, now = new_id("vcycle229"), now_ts()
        target_redacted = self._redact_target(target_type, target_value)
        payload = {
            "cycle_id": cid, "loop_id": loop_id, "case_id": loop["case_id"], "cycle_number": cycle_number,
            "query_text": query, "target_type": target_type, "target_value_redacted": target_redacted,
            "retrieval_run_id": retrieval.get("retrieval_run_id", ""), "source_query_id": source_strategy.get("query_id", ""),
            "selected_refs": list(retrieval.get("selected_refs") or []),
            "supporting_refs": list(retrieval.get("supporting_refs") or []),
            "contradicting_refs": list(retrieval.get("contradicting_refs") or []),
            "source_strategy": {
                "selected_sources": list(source_strategy.get("selected_sources") or []),
                "stop_conditions": list(source_strategy.get("stop_conditions") or []),
                "threat_level": source_strategy.get("threat_level", "unknown"),
                "human_review_required": True, "automatic_execution": False,
            },
            "counterevidence_checked": True, "status": "evidence_ready", "created_by": actor, "created_at": now,
        }
        self.db.execute("INSERT INTO verified_research_cycles_229 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            cid, loop_id, loop["case_id"], cycle_number, query, target_type, target_redacted,
            payload["retrieval_run_id"], payload["source_query_id"], dumps(payload["selected_refs"]),
            dumps(payload["supporting_refs"]), dumps(payload["contradicting_refs"]), dumps(payload["source_strategy"]),
            "{}", 1, "evidence_ready", actor, now, "", _hash(payload),
        ))
        self.db.execute("UPDATE verified_research_loops_229 SET current_cycle=?,status='active',updated_at=? WHERE loop_id=?", (cycle_number, now, loop_id))
        self._event(loop["case_id"], "verified_research_cycle_started", "verified_research_cycle", cid, {
            "cycle_number": cycle_number, "retrieval_run_id": payload["retrieval_run_id"], "source_query_id": payload["source_query_id"],
            "selected_ref_count": len(payload["selected_refs"]), "automatic_source_execution": False,
        }, actor)
        return {**payload, "retrieval": retrieval, "source_strategy_result": source_strategy, "network_executed": False}

    # ---------- claim ledger ----------
    def add_claim(
        self,
        *,
        cycle_id: str,
        claim_text: str,
        claim_kind: str,
        confidence: float,
        supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str],
        retrieval_claim_id: str = "",
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        cycle = self._cycle(cycle_id)
        if confirmation != f"VERIFIED CLAIM 229 {cycle_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if claim_kind not in {"observation", "inference", "hypothesis", "question"}:
            raise ValueError("invalid claim kind")
        text = _text(claim_text, 20_000).strip()
        if len(text) < 5:
            raise ValueError("claim text required")
        selected = set(_loads(cycle["selected_refs_json"], []))
        support = list(dict.fromkeys(_text(x, 1000) for x in supporting_refs if _text(x, 1000)))
        contradict = list(dict.fromkeys(_text(x, 1000) for x in contradicting_refs if _text(x, 1000)))
        if not set(support + contradict).issubset(selected):
            raise ValueError("claim references must come from the cycle retrieval set")
        support_groups = self._origin_groups(cycle["case_id"], support)
        contradict_groups = self._origin_groups(cycle["case_id"], contradict)
        diversity = self._source_diversity(cycle["case_id"], support + contradict)
        score = self._verification_score(
            confidence=_clamp(confidence), support_count=len(support_groups), contradiction_count=len(contradict_groups),
            source_diversity=diversity, required_origins=int(self._loop(cycle["loop_id"])["required_independent_origins"]),
        )
        vid, now = new_id("vclaim229"), now_ts()
        payload = {
            "verified_claim_id": vid, "loop_id": cycle["loop_id"], "case_id": cycle["case_id"], "cycle_id": cycle_id,
            "retrieval_claim_id": _text(retrieval_claim_id, 200), "claim_text": text, "claim_kind": claim_kind,
            "status": "candidate", "confidence": _clamp(confidence), "supporting_refs": support, "contradicting_refs": contradict,
            "independent_support_count": len(support_groups), "independent_contradiction_count": len(contradict_groups),
            "source_diversity": diversity, "verification_score": score, "counterevidence_checked": bool(cycle["counterevidence_checked"]),
            "rationale": "", "created_by": actor, "created_at": now, "updated_at": now,
        }
        self.db.execute("INSERT INTO verified_claims_229 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            vid, cycle["loop_id"], cycle["case_id"], cycle_id, payload["retrieval_claim_id"], text, claim_kind, "candidate",
            payload["confidence"], dumps(support), dumps(contradict), payload["independent_support_count"],
            payload["independent_contradiction_count"], diversity, score, int(payload["counterevidence_checked"]), "", actor, "", now, "", now, _hash(payload),
        ))
        self._event(cycle["case_id"], "verified_claim_added", "verified_claim", vid, {
            "support_origins": len(support_groups), "contradiction_origins": len(contradict_groups), "verification_score": score,
        }, actor)
        return payload

    def review_claim(
        self,
        *,
        verified_claim_id: str,
        decision: str,
        rationale: str,
        reviewer: str,
        confirmation: str,
    ) -> dict[str, Any]:
        claim = self._claim(verified_claim_id)
        loop = self._loop(claim["loop_id"])
        if confirmation != f"VERIFIED CLAIM 229 {verified_claim_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        if reviewer == claim["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"verified", "challenged", "rejected", "unresolved"}:
            raise ValueError("invalid verification decision")
        if len(_text(rationale, 5000).strip()) < 12:
            raise ValueError("substantive review rationale required")
        if decision == "verified":
            if int(claim["independent_support_count"]) < int(loop["required_independent_origins"]):
                raise PermissionError("independent-source gate failed")
            if int(claim["independent_contradiction_count"]) > 0:
                raise PermissionError("contradiction gate failed")
            if bool(loop["require_counterevidence"]) and not bool(claim["counterevidence_checked"]):
                raise PermissionError("counter-evidence gate failed")
            if float(claim["verification_score"]) < float(loop["min_verification_score"]):
                raise PermissionError("verification-score gate failed")
            if claim["claim_kind"] in {"hypothesis", "question"}:
                raise PermissionError("hypotheses and questions cannot be marked verified observations")
        now = now_ts()
        payload = {**claim, "status": decision, "rationale": _text(rationale, 5000), "reviewed_by": reviewer, "reviewed_at": now, "updated_at": now}
        self.db.execute("UPDATE verified_claims_229 SET status=?,rationale=?,reviewed_by=?,reviewed_at=?,updated_at=?,payload_sha256=? WHERE verified_claim_id=?", (
            decision, payload["rationale"], reviewer, now, now, _hash(payload), verified_claim_id,
        ))
        self._event(claim["case_id"], "verified_claim_reviewed", "verified_claim", verified_claim_id, {
            "decision": decision, "verification_score": claim["verification_score"], "reviewer_independent": True,
        }, reviewer)
        return self._claim(verified_claim_id)

    # ---------- gaps and stop conditions ----------
    def add_gap(self, *, loop_id: str, question: str, target_type: str = "unknown", target_value: str = "", priority: int = 50,
                actor: str, confirmation: str) -> dict[str, Any]:
        loop = self._loop(loop_id)
        if confirmation != f"RESEARCH GAP 229 {loop_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        q = _text(question, 10_000).strip()
        if len(q) < 5:
            raise ValueError("gap question required")
        strategy = self.source_intelligence.rank_sources(
            case_id=loop["case_id"], session_id=loop["session_id"], objective=q, target_type=target_type,
            target_value=target_value, language=loop["working_language"], countries=(), budget_class="standard", max_sources=4,
            require_independence=True, actor=actor, confirmation=f"SOURCE INTELLIGENCE 226 {loop['case_id']} BERECHNEN",
        )
        gid, now = new_id("gap229"), now_ts(); redacted = self._redact_target(target_type, target_value)
        compact_strategy = {"query_id": strategy.get("query_id", ""), "selected_sources": strategy.get("selected_sources", []), "stop_conditions": strategy.get("stop_conditions", []), "automatic_execution": False}
        payload = {"gap_id": gid, "loop_id": loop_id, "case_id": loop["case_id"], "question": q, "target_type": target_type,
                   "target_value_redacted": redacted, "priority": max(0, min(int(priority), 100)), "status": "open", "source_strategy": compact_strategy,
                   "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO research_gaps_229 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            gid, loop_id, loop["case_id"], q, target_type, redacted, payload["priority"], "open", dumps(compact_strategy), "", actor, "", now, "", _hash(payload),
        ))
        self._event(loop["case_id"], "research_gap_added", "research_gap", gid, {"priority": payload["priority"], "source_query_id": compact_strategy["query_id"]}, actor)
        return payload

    def resolve_gap(self, *, gap_id: str, resolution_note: str, actor: str, confirmation: str) -> dict[str, Any]:
        gap = self._gap(gap_id)
        if confirmation != f"RESEARCH GAP 229 {gap_id} SCHLIESSEN":
            raise PermissionError("explicit approval required")
        note = _text(resolution_note, 5000).strip()
        if len(note) < 8:
            raise ValueError("resolution note required")
        now = now_ts(); payload = {**gap, "status": "resolved", "resolution_note": note, "resolved_by": actor, "resolved_at": now}
        self.db.execute("UPDATE research_gaps_229 SET status='resolved',resolution_note=?,resolved_by=?,resolved_at=?,payload_sha256=? WHERE gap_id=?", (note, actor, now, _hash(payload), gap_id))
        self._event(gap["case_id"], "research_gap_resolved", "research_gap", gap_id, {}, actor)
        return self._gap(gap_id)

    def assess_cycle(self, *, cycle_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        cycle = self._cycle(cycle_id); loop = self._loop(cycle["loop_id"])
        if confirmation != f"VERIFIED RESEARCH CYCLE 229 {cycle_id} BEWERTEN":
            raise PermissionError("explicit approval required")
        claims = self.db.all("SELECT * FROM verified_claims_229 WHERE cycle_id=? ORDER BY created_at", (cycle_id,))
        counts = {status: sum(1 for x in claims if x["status"] == status) for status in ("candidate", "verified", "challenged", "rejected", "unresolved")}
        open_gaps = int((self.db.one("SELECT COUNT(*) AS n FROM research_gaps_229 WHERE loop_id=? AND status='open'", (loop["loop_id"],)) or {"n": 0})["n"])
        verified = counts["verified"]
        unresolved = counts["candidate"] + counts["challenged"] + counts["unresolved"]
        if claims and verified == len(claims) and open_gaps == 0:
            loop_status, stop_reason = "ready_for_report", "all cycle claims independently verified; no open research gaps"
        elif int(loop["current_cycle"]) >= int(loop["max_cycles"]):
            loop_status, stop_reason = "insufficient_evidence", "maximum research cycles reached with unresolved verification work"
        else:
            loop_status, stop_reason = "awaiting_next_cycle", "additional independent evidence or gap resolution required"
        summary = {"claim_count": len(claims), "verified": verified, "unresolved": unresolved, "rejected": counts["rejected"], "open_gaps": open_gaps,
                   "loop_status": loop_status, "stop_reason": stop_reason}
        now = now_ts()
        self.db.execute("UPDATE verified_research_cycles_229 SET status='assessed',verification_summary_json=?,completed_at=?,payload_sha256=? WHERE cycle_id=?", (dumps(summary), now, _hash({**cycle, **summary}), cycle_id))
        self.db.execute("UPDATE verified_research_loops_229 SET status=?,stop_reason=?,updated_at=? WHERE loop_id=?", (loop_status, stop_reason, now, loop["loop_id"]))
        self._event(loop["case_id"], "verified_research_cycle_assessed", "verified_research_cycle", cycle_id, summary, actor)
        return {**summary, "cycle_id": cycle_id, "loop_id": loop["loop_id"], "automatic_source_execution": False}

    def export_verified_claim_training_candidate(self, *, verified_claim_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        claim = self._claim(verified_claim_id)
        if confirmation != f"VERIFIED CLAIM TRAINING 229 {verified_claim_id} EXPORTIEREN":
            raise PermissionError("explicit approval required")
        if claim["status"] != "verified":
            raise PermissionError("only verified claims may become training candidates")
        loop = self._loop(claim["loop_id"])
        response = f"Verifizierte Aussage: {claim['claim_text']}\nPrüfbegründung: {claim['rationale']}"
        example = self.training.add_example(
            case_id=claim["case_id"], instruction=f"Prüfe die Aussage quellenkritisch im Kontext des Ermittlungsziels: {loop['objective']}",
            response=response, context={"build": self.BUILD, "loop_id": claim["loop_id"], "verified_claim_id": verified_claim_id},
            evidence_refs=_loads(claim["supporting_refs_json"], []), language=loop["working_language"], source_type="verified_research_loop_229",
            source_ref=verified_claim_id, created_by=actor,
            confirmation=f"TRAINING EXAMPLE 228 {claim['case_id']} ANLEGEN",
        )
        self._event(claim["case_id"], "verified_claim_training_candidate_exported", "verified_claim", verified_claim_id, {"example_id": example["example_id"], "review_required": True}, actor)
        return {"verified_claim_id": verified_claim_id, "example_id": example["example_id"], "training_review_required": True, "automatic_approval": False}

    # ---------- workspace ----------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        loops = self.db.all("SELECT * FROM verified_research_loops_229 WHERE case_id=? ORDER BY updated_at DESC LIMIT 20", (case_id,))
        claims = self.db.all("SELECT * FROM verified_claims_229 WHERE case_id=? ORDER BY updated_at DESC LIMIT 50", (case_id,))
        gaps = self.db.all("SELECT * FROM research_gaps_229 WHERE case_id=? ORDER BY status,priority DESC,created_at DESC LIMIT 50", (case_id,))
        return {"build": self.BUILD, "case_id": case_id, "loops": loops, "claims": claims, "gaps": gaps,
                "verified_claims": sum(1 for x in claims if x["status"] == "verified"), "open_gaps": sum(1 for x in gaps if x["status"] == "open")}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id=case_id); esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        loops = "".join(f"<tr><td><code>{esc(x['loop_id'])}</code></td><td>{esc(x['status'])}</td><td>{esc(x['current_cycle'])}/{esc(x['max_cycles'])}</td><td>{esc(x['required_independent_origins'])}</td><td>{esc(x['stop_reason'])}</td></tr>" for x in d["loops"]) or "<tr><td colspan='5'>Noch kein verifizierter Research Loop.</td></tr>"
        return f"""<section class='card' id='build229_verified_loop'><h2>Verified Research Loop 2.0 · Build 229</h2>
<p>Claim-zentrierte Recherche mit Gegenbelegsuche, Quellenunabhängigkeit, expliziten Verifikationsgates und dokumentierten Stop-Kriterien. Quellen werden weiterhin nicht automatisch ausgeführt.</p>
<div class='grid two'><div><h3>Loop anlegen</h3><form method='post' action='/build229/loop-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216/227-Session-ID' required><input name='working_language' value='de'><input name='max_cycles' type='number' min='1' max='8' value='4'><input name='required_independent_origins' type='number' min='1' max='4' value='2'><textarea name='objective' rows='4' placeholder='Konkretes Ermittlungsziel' required></textarea><button>Verifizierten Loop anlegen</button></form></div>
<div><h3>Research-Zyklus vorbereiten</h3><form method='post' action='/build229/cycle-start'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='loop_id' placeholder='Loop-ID' required><input name='target_type' value='unknown'><input name='target_value' placeholder='Zielwert optional'><input name='countries' placeholder='DE, IL, US'><textarea name='query_text' rows='4' placeholder='Prüffrage / Evidenzlücke' required></textarea><button>Retrieval + Quellenstrategie vorbereiten</button></form></div></div>
<p><strong>Status:</strong> {len(d['loops'])} Loops · {d['verified_claims']} verifizierte Claims · {d['open_gaps']} offene Lücken</p>
<div class='table-wrap'><table><thead><tr><th>Loop</th><th>Status</th><th>Zyklus</th><th>Min. unabh. Ursprünge</th><th>Stop-Grund</th></tr></thead><tbody>{loops}</tbody></table></div></section>"""

    # ---------- helpers ----------
    def _origin_groups(self, case_id: str, refs: Sequence[str]) -> set[str]:
        groups: set[str] = set()
        for ref in refs:
            row = self.db.one("SELECT independence_group,origin_key FROM source_lineage_nodes_225 WHERE case_id=? AND source_ref=? AND status='active' ORDER BY updated_at DESC LIMIT 1", (case_id, ref))
            key = _text((row or {}).get("independence_group") or (row or {}).get("origin_key"), 1000).strip()
            if not key:
                source = self.db.one("SELECT s.source_id,s.canonical_url,s.original_url,s.collector_id FROM evidence_statements_211 st JOIN evidence_sources_211 s ON s.source_id=st.source_id WHERE st.case_id=? AND st.statement_id=?", (case_id, ref))
                if source:
                    url = _text(source.get("canonical_url") or source.get("original_url"), 4000)
                    try:
                        host = (urlsplit(url).hostname or "").casefold()
                    except Exception:
                        host = ""
                    key = host or _text(source.get("collector_id") or source.get("source_id"), 1000)
            if key:
                groups.add(key)
        return groups

    def _source_diversity(self, case_id: str, refs: Sequence[str]) -> float:
        if not refs:
            return 0.0
        types: set[str] = set()
        for ref in refs:
            row = self.db.one("SELECT source_type FROM ai_memory_chunks_216 WHERE case_id=? AND source_ref=? ORDER BY created_at DESC LIMIT 1", (case_id, ref))
            if row and row.get("source_type"):
                types.add(row["source_type"])
        return round(len(types) / max(1, len(set(refs))), 6)

    def _verification_score(self, *, confidence: float, support_count: int, contradiction_count: int, source_diversity: float, required_origins: int) -> float:
        independence = min(1.0, support_count / max(1, required_origins))
        contradiction_penalty = min(.65, contradiction_count * .35)
        score = .50 * independence + .25 * _clamp(confidence) + .25 * _clamp(source_diversity) - contradiction_penalty
        return round(_clamp(score), 6)

    def _redact_target(self, target_type: str, target_value: str) -> str:
        value = _text(target_value, 4000).strip()
        if not value:
            return ""
        if target_type in {"email", "phone"} or _EMAIL_RE.search(value) or _PHONE_RE.search(value):
            return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
        return value[:500]

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _loop(self, loop_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM verified_research_loops_229 WHERE loop_id=?", (loop_id,))
        if not row: raise KeyError(loop_id)
        return row

    def _cycle(self, cycle_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM verified_research_cycles_229 WHERE cycle_id=?", (cycle_id,))
        if not row: raise KeyError(cycle_id)
        return row

    def _claim(self, claim_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM verified_claims_229 WHERE verified_claim_id=?", (claim_id,))
        if not row: raise KeyError(claim_id)
        return row

    def _gap(self, gap_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_gaps_229 WHERE gap_id=?", (gap_id,))
        if not row: raise KeyError(gap_id)
        return row

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build229_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", ""); eid, now = new_id("evt229"), now_ts()
        event_hash = _hash({"previous": previous, "event_id": eid, "case_id": case_id, "event_type": event_type,
                            "object_type": object_type, "object_id": object_id, "payload": dict(payload), "actor": actor, "created_at": now})
        self.db.execute("INSERT INTO build229_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, dumps(dict(payload)), actor, now, previous, event_hash))
