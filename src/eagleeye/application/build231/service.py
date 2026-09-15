from __future__ import annotations

import hashlib
import html
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts


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


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _utc_parse(value: str) -> datetime:
    raw = _text(value, 64).strip()
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _latency_score(ms: int) -> float:
    ms = max(0, int(ms or 0))
    if ms == 0:
        return .55
    if ms < 1_000:
        return 1.0
    if ms < 5_000:
        return .82
    if ms < 15_000:
        return .62
    if ms < 60_000:
        return .38
    return .15


class Build231AdaptiveSourceLearningOpsecService:
    """Governed feedback layer over Builds 225/226/229/230.

    The service never executes, enables, disables or quarantines a source. It
    learns only from independently reviewed outcomes. Even accepted outcomes do
    not affect ranking until a separately reviewed policy snapshot is approved.
    """

    BUILD = "231.0"
    POLICY_ALGORITHM = "adaptive_source_policy_v1"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        source_intelligence: Any,
        retrieval: Any,
        verified_loop: Any,
        multilingual: Any,
        protection: Any,
        conversation: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.source_intelligence, self.retrieval = source_intelligence, retrieval
        self.verified_loop, self.multilingual = verified_loop, multilingual
        self.protection, self.conversation = protection, conversation
        self.actor = actor
        # Deliberate hook: Build 226 remains the canonical ranker. Build 231 may
        # only contribute a bounded adjustment from an approved policy snapshot.
        self.source_intelligence._adaptive_learning_v1 = self

    # ---------- reviewed source outcomes ----------
    def submit_outcome(
        self,
        *,
        case_id: str,
        query_id: str,
        source_key: str,
        outcome_kind: str,
        precision_signal: float,
        counterevidence_signal: float = 0.0,
        latency_ms: int = 0,
        error_signal: float = 0.0,
        opsec_incident: bool = False,
        country: str = "",
        language: str = "",
        target_type: str = "",
        evidence_refs: Sequence[str] = (),
        rationale: str,
        submitted_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        query = self._query(query_id)
        if query["case_id"] != case_id:
            raise ValueError("query and case mismatch")
        if confirmation != f"SOURCE OUTCOME 231 {query_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if outcome_kind not in {"useful", "counterevidence", "not_useful", "error", "opsec_blocked", "deferred"}:
            raise ValueError("invalid outcome kind")
        rationale = _text(rationale, 5000).strip()
        if len(rationale) < 12:
            raise ValueError("substantive rationale required")
        rankings = {x["source_key"]: x for x in self.source_intelligence.list_rankings(query_id)}
        if source_key not in rankings:
            raise ValueError("source was not part of this Build-226 ranking")
        if self.db.one("SELECT outcome_id FROM source_outcomes_231 WHERE query_id=? AND source_key=?", (query_id, source_key)):
            raise ValueError("one source outcome per query/source is allowed; create a new reviewed query for another learning observation")
        refs = list(dict.fromkeys(_text(x, 500) for x in evidence_refs if _text(x, 500)))[:50]
        domains = sorted(self._origin_domains(case_id, refs))
        oid, now = new_id("outcome231"), now_ts()
        payload = {
            "outcome_id": oid, "case_id": case_id, "query_id": query_id, "source_key": source_key,
            "country": self._norm_country(country or self._first_country(query)),
            "language": _text(language or query.get("language") or "und", 20).casefold(),
            "target_type": _text(target_type or query.get("target_type") or "unknown", 50).casefold(),
            "outcome_kind": outcome_kind, "precision_signal": _clamp(precision_signal, .5),
            "counterevidence_signal": _clamp(counterevidence_signal), "latency_ms": max(0, min(int(latency_ms or 0), 86_400_000)),
            "error_signal": _clamp(error_signal), "opsec_incident": bool(opsec_incident),
            "evidence_refs": refs, "origin_domains": domains, "rationale": rationale,
            "submitted_by": _text(submitted_by, 200), "submitted_at": now,
        }
        self.db.execute("INSERT INTO source_outcomes_231 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            oid, case_id, query_id, source_key, payload["country"], payload["language"], payload["target_type"], outcome_kind,
            payload["precision_signal"], payload["counterevidence_signal"], payload["latency_ms"], payload["error_signal"],
            int(payload["opsec_incident"]), dumps(refs), dumps(domains), rationale, payload["submitted_by"], now, _hash(payload),
        ))
        self._event(case_id, "source_outcome_submitted", "source_outcome", oid, {
            "query_id": query_id, "source_key": source_key, "outcome_kind": outcome_kind,
            "opsec_incident": bool(opsec_incident), "learning_eligible": False,
        }, submitted_by)
        return {**payload, "status": "review_required", "learning_eligible": False, "automatic_policy_update": False}

    def review_outcome(self, *, outcome_id: str, decision: str, review_note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        outcome = self._outcome(outcome_id)
        if confirmation != f"SOURCE OUTCOME REVIEW 231 {outcome_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == outcome["submitted_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "rejected"}:
            raise ValueError("invalid review decision")
        note = _text(review_note, 5000).strip()
        if len(note) < 12:
            raise ValueError("substantive review note required")
        if self.db.one("SELECT review_id FROM source_outcome_reviews_231 WHERE outcome_id=?", (outcome_id,)):
            raise ValueError("outcome already reviewed")
        rid, now = new_id("outreview231"), now_ts()
        payload = {"review_id": rid, "outcome_id": outcome_id, "case_id": outcome["case_id"], "decision": decision,
                   "review_note": note, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO source_outcome_reviews_231 VALUES(?,?,?,?,?,?,?,?)", (
            rid, outcome_id, outcome["case_id"], decision, note, reviewer, now, _hash(payload),
        ))
        self._event(outcome["case_id"], "source_outcome_reviewed", "source_outcome", outcome_id, {
            "decision": decision, "source_key": outcome["source_key"], "learning_eligible": decision == "accepted",
            "independent_reviewer": True,
        }, reviewer)
        return {**payload, "learning_eligible": decision == "accepted", "automatic_policy_update": False}

    # ---------- policy snapshots ----------
    def build_policy_snapshot(
        self,
        *,
        case_id: str,
        half_life_days: int = 120,
        min_sample: int = 5,
        max_adjustment: float = .10,
        max_domain_share: float = .55,
        max_reviewer_share: float = .60,
        exploration_rate: float = .08,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"SOURCE POLICY 231 {case_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        cfg = {
            "half_life_days": max(7, min(int(half_life_days), 730)),
            "min_sample": max(2, min(int(min_sample), 100)),
            "max_adjustment": max(0.0, min(float(max_adjustment), .20)),
            "max_domain_share": max(.20, min(float(max_domain_share), 1.0)),
            "max_reviewer_share": max(.20, min(float(max_reviewer_share), 1.0)),
            "exploration_rate": max(0.0, min(float(exploration_rate), .25)),
        }
        version = int((self.db.one("SELECT COALESCE(MAX(policy_version),0)+1 AS n FROM source_policy_snapshots_231") or {"n": 1})["n"])
        accepted = self._accepted_outcomes()
        pid, now = new_id("policy231"), now_ts()
        expected_profile_count = self._profile_scope_count(accepted)
        seed_payload = {"policy_id": pid, "policy_version": version, "status": "draft", **cfg,
                        "accepted_outcome_count": len(accepted), "profile_count": expected_profile_count, "created_case_id": case_id,
                        "created_by": created_by, "created_at": now, "algorithm": self.POLICY_ALGORITHM}
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO source_policy_snapshots_231 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                pid, version, "draft", cfg["half_life_days"], cfg["min_sample"], cfg["max_adjustment"], cfg["max_domain_share"],
                cfg["max_reviewer_share"], cfg["exploration_rate"], len(accepted), expected_profile_count, dumps(cfg), case_id, created_by, now, _hash(seed_payload),
            ))
            profiles = self._generate_profiles(pid, accepted, cfg, now)
        self._event(case_id, "source_policy_snapshot_built", "source_policy", pid, {
            "policy_version": version, "accepted_outcomes": len(accepted), "profiles": len(profiles),
            "status": "draft", "ranking_effect": False,
        }, created_by)
        return {**seed_payload, "profile_count": len(profiles), "profiles": profiles,
                "human_approval_required": True, "ranking_effect": False, "automatic_source_execution": False}

    def review_policy_snapshot(self, *, policy_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        policy = self._policy(policy_id)
        if confirmation != f"SOURCE POLICY REVIEW 231 {policy_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == policy["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid policy review decision")
        rationale = _text(rationale, 5000).strip()
        if len(rationale) < 12:
            raise ValueError("substantive policy rationale required")
        if self.db.one("SELECT policy_review_id FROM source_policy_reviews_231 WHERE policy_id=?", (policy_id,)):
            raise ValueError("policy already reviewed")
        rid, now = new_id("policyreview231"), now_ts()
        payload = {"policy_review_id": rid, "policy_id": policy_id, "decision": decision, "rationale": rationale,
                   "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO source_policy_reviews_231 VALUES(?,?,?,?,?,?,?)", (
            rid, policy_id, decision, rationale, reviewer, now, _hash(payload),
        ))
        self._event(policy["created_case_id"], "source_policy_reviewed", "source_policy", policy_id, {
            "decision": decision, "policy_version": policy["policy_version"], "ranking_effect": decision == "approved",
            "automatic_source_activation": False, "automatic_network_execution": False,
        }, reviewer)
        return {**payload, "ranking_effect": decision == "approved", "automatic_source_activation": False,
                "automatic_network_execution": False}

    def active_policy(self) -> dict[str, Any] | None:
        row = self.db.one("""
            SELECT p.*,r.policy_review_id,r.rationale AS review_rationale,r.reviewer,r.reviewed_at
            FROM source_policy_snapshots_231 p JOIN source_policy_reviews_231 r ON r.policy_id=p.policy_id
            WHERE r.decision='approved' ORDER BY p.policy_version DESC LIMIT 1
        """)
        if not row:
            return None
        row["configuration"] = _loads(row.get("configuration_json"), {})
        row["profile_count"] = int((self.db.one("SELECT COUNT(*) AS n FROM source_learning_profiles_231 WHERE policy_id=?", (row["policy_id"],)) or {"n": 0})["n"])
        return row

    def ranking_adjustment(self, *, source_key: str, target_type: str, language: str, countries: Sequence[str], threat_level: str) -> dict[str, Any]:
        """Return a bounded adjustment for Build 226; no side effects."""
        policy = self.active_policy()
        if not policy:
            return {"active": False, "score_delta": 0.0, "opsec_penalty": 0.0, "hard_block": False,
                    "reason": "no_approved_policy"}
        profiles = self.db.all("SELECT * FROM source_learning_profiles_231 WHERE policy_id=? AND source_key=?", (policy["policy_id"], source_key))
        if not profiles:
            return {"active": True, "policy_id": policy["policy_id"], "score_delta": 0.0, "opsec_penalty": 0.0,
                    "hard_block": False, "reason": "no_profile"}
        country_set = {self._norm_country(x) for x in countries if self._norm_country(x)}
        lang = _text(language or "und", 20).casefold()
        target = _text(target_type or "unknown", 50).casefold()

        def specificity(row: Mapping[str, Any]) -> tuple[int, float, int]:
            if row["country"] != "*" and row["country"] not in country_set:
                return (-1, 0.0, 0)
            if row["language"] != "*" and row["language"] != lang:
                return (-1, 0.0, 0)
            if row["target_type"] != "*" and row["target_type"] != target:
                return (-1, 0.0, 0)
            score = int(row["country"] != "*") + int(row["language"] != "*") + int(row["target_type"] != "*")
            return (score, float(row.get("confidence") or 0.0), int(row.get("sample_size") or 0))

        eligible = [(specificity(r), r) for r in profiles]
        eligible = [(s, r) for s, r in eligible if s[0] >= 0]
        if not eligible:
            return {"active": True, "policy_id": policy["policy_id"], "score_delta": 0.0, "opsec_penalty": 0.0,
                    "hard_block": False, "reason": "no_matching_scope"}
        min_sample = int(policy.get("min_sample") or 5)
        mature = [(spec, row) for spec, row in eligible if int(row.get("sample_size") or 0) >= min_sample]
        if not mature:
            return {"active": True, "policy_id": policy["policy_id"], "policy_version": policy["policy_version"],
                    "score_delta": 0.0, "opsec_penalty": 0.0, "hard_block": False, "reason": "minimum_sample_not_reached"}
        mature.sort(key=lambda item: item[0], reverse=True)
        profile = mature[0][1]
        flags = _loads(profile.get("poison_flags_json"), [])
        # OPSEC remains a separate penalty. A hard block can only come from the
        # independently approved snapshot and therefore represents a human-approved policy decision.
        opsec_rate = _clamp(profile.get("opsec_incident_rate"))
        opsec_penalty = min(.35, opsec_rate * .35)
        hard_block = bool(profile.get("hard_block_recommended"))
        return {
            "active": True, "policy_id": policy["policy_id"], "policy_version": policy["policy_version"],
            "profile_id": profile["profile_id"], "scope": {"country": profile["country"], "language": profile["language"], "target_type": profile["target_type"]},
            "sample_size": int(profile["sample_size"]), "weighted_sample": float(profile["weighted_sample"]),
            "quality_score": float(profile["quality_score"]), "confidence": float(profile["confidence"]),
            "score_delta": float(profile["score_delta"]), "opsec_penalty": opsec_penalty, "hard_block": hard_block,
            "poison_flags": flags, "reason": "approved_policy_profile",
            "automatic_source_execution": False, "automatic_source_activation": False,
        }

    # ---------- conservative exploration ----------
    def propose_exploration(self, *, query_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        query = self._query(query_id)
        if confirmation != f"SOURCE EXPLORATION 231 {query_id} VORSCHLAGEN":
            raise PermissionError("explicit approval required")
        if self.db.one("SELECT proposal_id FROM source_exploration_proposals_231 WHERE query_id=?", (query_id,)):
            return {"query_id": query_id, "proposal": None, "reason": "exploration already proposed for this query", "automatic_execution": False}
        rankings = self.source_intelligence.list_rankings(query_id)
        selected = {x["source_key"] for x in rankings if bool(x["selected"])}
        policy = self.active_policy()
        if policy and float(policy.get("exploration_rate") or 0.0) <= 0.0:
            return {"query_id": query_id, "proposal": None, "reason": "exploration disabled by approved policy", "automatic_execution": False}
        profile_samples: dict[str, int] = {}
        if policy:
            for row in self.db.all("SELECT source_key,MAX(sample_size) AS n FROM source_learning_profiles_231 WHERE policy_id=? GROUP BY source_key", (policy["policy_id"],)):
                profile_samples[row["source_key"]] = int(row.get("n") or 0)
        candidates = [r for r in rankings if bool(r["eligible"]) and r["source_key"] not in selected]
        candidates.sort(key=lambda r: (profile_samples.get(r["source_key"], 0), -float(r["final_score"]), int(r["rank_position"])))
        candidate = candidates[0] if candidates else None
        if not candidate:
            return {"query_id": query_id, "proposal": None, "reason": "no eligible unselected source", "automatic_execution": False}
        source = next((x for x in self.source_intelligence.catalog() if x["source_key"] == candidate["source_key"]), {})
        pid, now = new_id("explore231"), now_ts()
        reason = "Conservative manual exploration candidate: eligible, not selected, and under-sampled relative to current policy."
        payload = {"proposal_id": pid, "case_id": query["case_id"], "query_id": query_id, "source_key": candidate["source_key"],
                   "reason": reason, "current_rank": int(candidate["rank_position"]), "current_score": float(candidate["final_score"]),
                   "sample_size": profile_samples.get(candidate["source_key"], 0), "opsec_risk": source.get("opsec_risk", "elevated"),
                   "policy_id": (policy or {}).get("policy_id", ""), "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO source_exploration_proposals_231 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            pid, query["case_id"], query_id, candidate["source_key"], reason, payload["current_rank"], payload["current_score"], payload["sample_size"],
            payload["opsec_risk"], payload["policy_id"], created_by, now, _hash(payload),
        ))
        self._event(query["case_id"], "source_exploration_proposed", "source_exploration", pid, {
            "source_key": candidate["source_key"], "manual_trial_only": True, "network_executed": False,
        }, created_by)
        return {**payload, "manual_trial_only": True, "automatic_execution": False}

    def review_exploration(self, *, proposal_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        proposal = self._proposal(proposal_id)
        if confirmation != f"SOURCE EXPLORATION REVIEW 231 {proposal_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == proposal["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"approved_for_manual_trial", "rejected", "deferred"}:
            raise ValueError("invalid exploration review decision")
        rationale = _text(rationale, 5000).strip()
        if len(rationale) < 12:
            raise ValueError("substantive exploration rationale required")
        if self.db.one("SELECT exploration_review_id FROM source_exploration_reviews_231 WHERE proposal_id=?", (proposal_id,)):
            raise ValueError("exploration proposal already reviewed")
        rid, now = new_id("explorereview231"), now_ts()
        payload = {"exploration_review_id": rid, "proposal_id": proposal_id, "decision": decision, "rationale": rationale,
                   "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO source_exploration_reviews_231 VALUES(?,?,?,?,?,?,?)", (rid, proposal_id, decision, rationale, reviewer, now, _hash(payload)))
        self._event(proposal["case_id"], "source_exploration_reviewed", "source_exploration", proposal_id, {
            "decision": decision, "manual_trial_only": True, "source_activated": False, "network_executed": False,
        }, reviewer)
        return {**payload, "manual_trial_only": True, "source_activated": False, "network_executed": False}

    # ---------- dashboards ----------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        outcomes = self.db.all("""
            SELECT o.*,r.decision AS review_decision,r.reviewer,r.reviewed_at
            FROM source_outcomes_231 o LEFT JOIN source_outcome_reviews_231 r ON r.outcome_id=o.outcome_id
            WHERE o.case_id=? ORDER BY o.submitted_at DESC LIMIT 60
        """, (case_id,))
        policies = self.db.all("""
            SELECT p.*,r.decision AS review_decision,r.reviewer,r.reviewed_at
            FROM source_policy_snapshots_231 p LEFT JOIN source_policy_reviews_231 r ON r.policy_id=p.policy_id
            ORDER BY p.policy_version DESC LIMIT 20
        """)
        exploration = self.db.all("""
            SELECT p.*,r.decision AS review_decision FROM source_exploration_proposals_231 p
            LEFT JOIN source_exploration_reviews_231 r ON r.proposal_id=p.proposal_id
            WHERE p.case_id=? ORDER BY p.created_at DESC LIMIT 30
        """, (case_id,))
        accepted = sum(1 for x in outcomes if x.get("review_decision") == "accepted")
        pending = sum(1 for x in outcomes if not x.get("review_decision"))
        return {"build": self.BUILD, "case_id": case_id, "outcomes": outcomes, "policies": policies,
                "exploration": exploration, "accepted_outcomes": accepted, "pending_outcomes": pending,
                "active_policy": self.active_policy(), "automatic_network_execution": False}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id); esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        recent_queries = self.db.all("SELECT query_id,target_type,language,selected_sources_json FROM source_intelligence_queries_226 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        query_options = "".join(f"<option value='{esc(q['query_id'])}'>{esc(q['query_id'])} · {esc(q['target_type'])} · {esc(q['language'])}</option>" for q in recent_queries)
        pending = [x for x in data["outcomes"] if not x.get("review_decision")]
        pending_options = "".join(f"<option value='{esc(x['outcome_id'])}'>{esc(x['source_key'])} · {esc(x['outcome_kind'])} · {esc(x['outcome_id'])}</option>" for x in pending)
        drafts = [x for x in data["policies"] if not x.get("review_decision")]
        policy_options = "".join(f"<option value='{esc(x['policy_id'])}'>v{esc(x['policy_version'])} · {esc(x['policy_id'])}</option>" for x in drafts)
        pending_exploration = [x for x in data["exploration"] if not x.get("review_decision")]
        proposal_options = "".join(f"<option value='{esc(x['proposal_id'])}'>{esc(x['source_key'])} · {esc(x['proposal_id'])}</option>" for x in pending_exploration)
        active = data.get("active_policy") or {}
        outcome_rows = "".join(f"<tr><td><code>{esc(x['outcome_id'])}</code></td><td>{esc(x['source_key'])}</td><td>{esc(x['outcome_kind'])}</td><td>{esc(x.get('review_decision') or 'review_required')}</td><td>{'ja' if x['opsec_incident'] else 'nein'}</td></tr>" for x in data["outcomes"][:15]) or "<tr><td colspan='5'>Noch keine Source-Outcomes.</td></tr>"
        return f"""
<section class='card' id='build231_adaptive_source_learning'><h2>Adaptive Source Learning &amp; Investigative OPSEC · Build 231</h2>
<p>Feedbackschicht über Build 226: Lernen nur aus unabhängig reviewten Outcomes, zeitlicher Decay, Mindeststichprobe, Poisoning-/Dominanzschutz und OPSEC als eigener Ranking-Kostenfaktor. Keine automatische Quellenaktivierung oder Netzwerkausführung.</p>
<p><strong>Aktive Policy:</strong> {esc(active.get('policy_id') or 'keine')} · <strong>akzeptierte Outcomes im Fall:</strong> {data['accepted_outcomes']} · <strong>offene Reviews:</strong> {data['pending_outcomes']}</p>
<div class='grid two'>
<div><h3>Quellen-Outcome erfassen</h3><form method='post' action='/build231/outcome-submit'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><label>Build-226 Query<select name='query_id' required>{query_options}</select></label><input name='source_key' placeholder='Source-Key aus dem Ranking' required><select name='outcome_kind'><option>useful</option><option>counterevidence</option><option>not_useful</option><option>error</option><option>opsec_blocked</option><option>deferred</option></select><input name='precision_signal' type='number' min='0' max='1' step='0.05' value='0.7'><input name='counterevidence_signal' type='number' min='0' max='1' step='0.05' value='0'><input name='latency_ms' type='number' min='0' value='0'><input name='error_signal' type='number' min='0' max='1' step='0.05' value='0'><label><input name='opsec_incident' type='checkbox' value='1'> OPSEC-Vorfall / Block</label><input name='country' placeholder='Land, z. B. DE'><input name='evidence_refs' placeholder='Evidence-Statement-IDs, Komma getrennt'><textarea name='rationale' rows='4' placeholder='Warum war die Quelle nützlich, fehlerhaft oder OPSEC-kritisch?' required></textarea><button>Outcome reviewpflichtig speichern</button></form></div>
<div><h3>Outcome unabhängig prüfen</h3><form method='post' action='/build231/outcome-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='outcome_id' required>{pending_options}</select><select name='decision'><option>accepted</option><option>rejected</option></select><textarea name='review_note' rows='4' placeholder='Unabhängige Prüfbegründung' required></textarea><button>Review speichern</button></form></div>
</div>
<div class='grid two'>
<div><h3>Neue Source-Policy berechnen</h3><form method='post' action='/build231/policy-build'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><label>Half-Life Tage<input name='half_life_days' type='number' min='7' max='730' value='120'></label><label>Mindeststichprobe<input name='min_sample' type='number' min='2' max='100' value='5'></label><label>Max. Score-Anpassung<input name='max_adjustment' type='number' min='0' max='0.2' step='0.01' value='0.10'></label><label>Max. Domain-Anteil<input name='max_domain_share' type='number' min='0.2' max='1' step='0.05' value='0.55'></label><button>Draft-Policy erzeugen</button></form></div>
<div><h3>Policy unabhängig freigeben</h3><form method='post' action='/build231/policy-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='policy_id' required>{policy_options}</select><select name='decision'><option>approved</option><option>rejected</option></select><textarea name='rationale' rows='4' placeholder='Freigabebegründung / Risiken' required></textarea><button>Policy-Review speichern</button></form></div>
</div>
<div class='grid two'>
<div><h3>Konservative Exploration</h3><form method='post' action='/build231/exploration-propose'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='query_id' required>{query_options}</select><button>Unter-sampelte Quelle nur vorschlagen</button></form></div>
<div><h3>Exploration prüfen</h3><form method='post' action='/build231/exploration-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='proposal_id' required>{proposal_options}</select><select name='decision'><option>approved_for_manual_trial</option><option>deferred</option><option>rejected</option></select><textarea name='rationale' rows='3' placeholder='Begründung; Freigabe bedeutet nur manueller Versuch' required></textarea><button>Exploration-Review speichern</button></form></div>
</div>
<div class='table-wrap'><table><thead><tr><th>Outcome</th><th>Quelle</th><th>Signal</th><th>Review</th><th>OPSEC</th></tr></thead><tbody>{outcome_rows}</tbody></table></div>
</section>"""

    # ---------- profile construction ----------
    def _accepted_outcomes(self) -> list[dict[str, Any]]:
        return self.db.all("""
            SELECT o.*,r.reviewer,r.reviewed_at,r.review_note FROM source_outcomes_231 o
            JOIN source_outcome_reviews_231 r ON r.outcome_id=o.outcome_id WHERE r.decision='accepted'
            ORDER BY r.reviewed_at
        """)

    def _profile_scope_count(self, outcomes: Sequence[Mapping[str, Any]]) -> int:
        scopes: set[tuple[str, str, str, str]] = set()
        for row in outcomes:
            key = row["source_key"]; c = row.get("country") or "*"; l = row.get("language") or "*"; t = row.get("target_type") or "*"
            scopes.update({(key, "*", "*", "*"), (key, "*", l, "*"), (key, c, "*", "*"), (key, "*", "*", t), (key, c, l, "*"), (key, c, l, t)})
        return len(scopes)

    def _generate_profiles(self, policy_id: str, outcomes: Sequence[Mapping[str, Any]], cfg: Mapping[str, Any], now: str) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for row in outcomes:
            key = row["source_key"]
            c, l, t = row.get("country") or "*", row.get("language") or "*", row.get("target_type") or "*"
            scopes = {(key, "*", "*", "*"), (key, "*", l, "*"), (key, c, "*", "*"), (key, "*", "*", t),
                      (key, c, l, "*"), (key, c, l, t)}
            for scope in scopes:
                groups[scope].append(row)
        profiles: list[dict[str, Any]] = []
        for scope, rows in sorted(groups.items()):
            profile = self._profile_metrics(policy_id, scope, rows, cfg, now)
            self.db.execute("INSERT INTO source_learning_profiles_231 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                profile["profile_id"], policy_id, profile["source_key"], profile["country"], profile["language"], profile["target_type"],
                profile["sample_size"], profile["weighted_sample"], profile["precision_score"], profile["counterevidence_rate"],
                profile["evidence_yield_rate"], profile["error_rate"], profile["latency_score"], profile["opsec_incident_rate"],
                profile["quality_score"], profile["confidence"], profile["score_delta"], int(profile["hard_block_recommended"]),
                dumps(profile["poison_flags"]), dumps(profile["reviewer_distribution"]), dumps(profile["origin_distribution"]), now, _hash(profile),
            ))
            profiles.append(profile)
        return profiles

    def _profile_metrics(self, policy_id: str, scope: tuple[str, str, str, str], rows: Sequence[Mapping[str, Any]], cfg: Mapping[str, Any], now: str) -> dict[str, Any]:
        now_dt = _utc_parse(now); half_life = float(cfg["half_life_days"])
        weighted: list[tuple[Mapping[str, Any], float]] = []
        for row in rows:
            age_days = max(0.0, (now_dt - _utc_parse(row.get("reviewed_at") or row.get("submitted_at") or now)).total_seconds() / 86400.0)
            weight = math.pow(.5, age_days / max(1.0, half_life))
            weighted.append((row, weight))
        total_w = sum(w for _, w in weighted) or 1.0
        avg = lambda field, default=0.0: sum(_clamp(r.get(field), default) * w for r, w in weighted) / total_w
        precision = avg("precision_signal", .5)
        counter_rate = avg("counterevidence_signal", 0.0)
        error_rate = avg("error_signal", 0.0)
        opsec_rate = sum((1.0 if int(r.get("opsec_incident") or 0) else 0.0) * w for r, w in weighted) / total_w
        latency = sum(_latency_score(int(r.get("latency_ms") or 0)) * w for r, w in weighted) / total_w
        yield_rate = sum((1.0 if r.get("outcome_kind") in {"useful", "counterevidence"} else 0.0) * w for r, w in weighted) / total_w
        reviewer_weights: Counter[str] = Counter(); origin_weights: Counter[str] = Counter()
        for row, w in weighted:
            reviewer_weights[_text(row.get("reviewer") or "unknown", 200)] += w
            domains = _loads(row.get("origin_domains_json"), [])
            for domain in set(_text(x, 300).casefold() for x in domains if _text(x, 300)):
                origin_weights[domain] += w / max(1, len(set(domains)))
        reviewer_distribution = {k: round(v / total_w, 6) for k, v in reviewer_weights.items()}
        origin_total = sum(origin_weights.values()) or 0.0
        origin_distribution = {k: round(v / origin_total, 6) for k, v in origin_weights.items()} if origin_total else {}
        max_reviewer = max(reviewer_distribution.values(), default=0.0)
        max_domain = max(origin_distribution.values(), default=0.0)
        flags: list[str] = []
        if len(rows) < int(cfg["min_sample"]): flags.append("insufficient_sample")
        if max_reviewer > float(cfg["max_reviewer_share"]) and len(rows) >= int(cfg["min_sample"]): flags.append("reviewer_concentration")
        if origin_distribution and max_domain > float(cfg["max_domain_share"]) and len(rows) >= int(cfg["min_sample"]): flags.append("domain_dominance")
        if not origin_distribution and len(rows) >= int(cfg["min_sample"]): flags.append("lineage_sparse")
        quality = _clamp(.42 * precision + .16 * counter_rate + .12 * latency + .18 * (1.0 - error_rate) + .12 * yield_rate - .35 * opsec_rate, .5)
        sample_conf = min(1.0, total_w / max(1.0, float(cfg["min_sample"])))
        concentration_penalty = .55 if "domain_dominance" in flags else 1.0
        reviewer_penalty = .65 if "reviewer_concentration" in flags else 1.0
        lineage_penalty = .85 if "lineage_sparse" in flags else 1.0
        confidence = _clamp(sample_conf * concentration_penalty * reviewer_penalty * lineage_penalty)
        if "insufficient_sample" in flags or "domain_dominance" in flags:
            score_delta = 0.0
        else:
            raw_delta = (quality - .5) * 2.0 * float(cfg["max_adjustment"]) * confidence
            score_delta = max(-float(cfg["max_adjustment"]), min(float(cfg["max_adjustment"]), raw_delta))
        opsec_count = sum(1 for r in rows if int(r.get("opsec_incident") or 0))
        hard_block = (len(rows) >= int(cfg["min_sample"]) and opsec_count >= 2 and opsec_rate >= .25
                      and "domain_dominance" not in flags and "reviewer_concentration" not in flags)
        if hard_block:
            flags.append("opsec_block_recommended")
        return {
            "profile_id": new_id("srcprofile231"), "policy_id": policy_id,
            "source_key": scope[0], "country": scope[1] or "*", "language": scope[2] or "*", "target_type": scope[3] or "*",
            "sample_size": len(rows), "weighted_sample": round(total_w, 6), "precision_score": round(precision, 6),
            "counterevidence_rate": round(counter_rate, 6), "evidence_yield_rate": round(yield_rate, 6),
            "error_rate": round(error_rate, 6), "latency_score": round(latency, 6), "opsec_incident_rate": round(opsec_rate, 6),
            "quality_score": round(quality, 6), "confidence": round(confidence, 6), "score_delta": round(score_delta, 6),
            "hard_block_recommended": hard_block, "poison_flags": sorted(set(flags)),
            "reviewer_distribution": reviewer_distribution, "origin_distribution": origin_distribution, "created_at": now,
        }

    # ---------- helpers ----------
    def _origin_domains(self, case_id: str, refs: Sequence[str]) -> set[str]:
        domains: set[str] = set()
        for ref in refs:
            row = self.db.one("""
                SELECT s.canonical_url,s.original_url,s.collector_id,s.source_id FROM evidence_statements_211 st
                JOIN evidence_sources_211 s ON s.source_id=st.source_id WHERE st.case_id=? AND st.statement_id=?
            """, (case_id, ref))
            if not row:
                continue
            raw = _text(row.get("canonical_url") or row.get("original_url"), 4000)
            try:
                host = (urlsplit(raw).hostname or "").casefold()
            except Exception:
                host = ""
            origin = host or _text(row.get("collector_id") or row.get("source_id"), 500).casefold()
            if origin:
                domains.add(origin)
        return domains

    @staticmethod
    def _norm_country(value: str) -> str:
        raw = "".join(ch for ch in _text(value, 20).upper() if ch.isalpha())
        return raw[:3] if len(raw) in {2, 3} else "*"

    @staticmethod
    def _first_country(query: Mapping[str, Any]) -> str:
        values = _loads(query.get("countries_json"), [])
        return _text(values[0], 20) if values else ""

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _query(self, query_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_intelligence_queries_226 WHERE query_id=?", (query_id,))
        if not row: raise KeyError(query_id)
        return row

    def _outcome(self, outcome_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_outcomes_231 WHERE outcome_id=?", (outcome_id,))
        if not row: raise KeyError(outcome_id)
        return row

    def _policy(self, policy_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_policy_snapshots_231 WHERE policy_id=?", (policy_id,))
        if not row: raise KeyError(policy_id)
        return row

    def _proposal(self, proposal_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_exploration_proposals_231 WHERE proposal_id=?", (proposal_id,))
        if not row: raise KeyError(proposal_id)
        return row

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build231_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "0" * 64)
        eid, now = new_id("evt231"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"prompt", "response", "content", "messages", "target_value"}}
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id,
                "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build231_events VALUES(?,?,?,?,?,?,?,?,?,?)", (
            eid, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now,
        ))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return eid
