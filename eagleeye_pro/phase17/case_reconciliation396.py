from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping, Iterable

from .case_state_graph395 import CONFIRM_BRANCH as CONFIRM_CASE_STATE_BRANCH

BUILD = "396.0"
POLICY_ID = "phase17.case-state-reconciliation-incremental-reanalysis.v396"
CONFIRM_BASELINE = "CREATE RECONCILIATION BASELINE"
CONFIRM_REVIEW = "REVIEW REANALYSIS PROPOSAL"
CONFIRM_BRANCH = "CREATE REANALYSIS BRANCH"
CONFIRM_ADVANCE = "ADVANCE RECONCILIATION BASELINE"
_ALLOWED_TARGETS = {"claim", "hypothesis", "reasoning_plan"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sid(prefix: str, value: Any, n: int = 24) -> str:
    return f"{prefix}_{_sha(value)[:n]}"


def _j(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_strings(v)
    elif isinstance(value, str):
        yield value


class CaseStateReconciliation396:
    """Delta-based reconciliation of new analytical signals against active case state.

    Build 396 is deliberately advisory. It records an explicit baseline, identifies
    new upstream evidence/corroboration/claim signals, maps only conservative
    relationships into active Build-395 state, and creates review-only re-analysis
    proposals. A reviewed proposal may create a Build-395 branch, but never adopts
    or mutates active case state.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        state395: Any,
        intake389: Any,
        review390: Any,
        synthesis391: Any,
        reasoning392: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.state395 = state395
        self.intake389 = intake389
        self.review390 = review390
        self.synthesis391 = synthesis391
        self.reasoning392 = reasoning392
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_baseline_396(
              baseline_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, previous_baseline_id TEXT NOT NULL DEFAULT '',
              signal_count INTEGER NOT NULL, baseline_hash TEXT NOT NULL, created_by TEXT NOT NULL,
              created_at TEXT NOT NULL, record_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_reconciliation_baseline_396_case ON reconciliation_baseline_396(case_id,created_at);

            CREATE TABLE IF NOT EXISTS reconciliation_baseline_signal_396(
              baseline_signal_id TEXT PRIMARY KEY, baseline_id TEXT NOT NULL, case_id TEXT NOT NULL,
              signal_type TEXT NOT NULL, signal_id TEXT NOT NULL, signal_hash TEXT NOT NULL,
              proposition TEXT NOT NULL DEFAULT '', source_state TEXT NOT NULL, record_hash TEXT NOT NULL,
              UNIQUE(baseline_id,signal_type,signal_id,signal_hash));
            CREATE INDEX IF NOT EXISTS idx_reconciliation_baseline_signal_396_baseline ON reconciliation_baseline_signal_396(baseline_id,signal_type,signal_id);

            CREATE TABLE IF NOT EXISTS reconciliation_scan_396(
              scan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, baseline_id TEXT NOT NULL,
              current_signal_count INTEGER NOT NULL, delta_signal_count INTEGER NOT NULL,
              matched_signal_count INTEGER NOT NULL, unmatched_signal_count INTEGER NOT NULL,
              impact_count INTEGER NOT NULL, scan_state TEXT NOT NULL, created_by TEXT NOT NULL,
              created_at TEXT NOT NULL, scan_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_reconciliation_scan_396_case ON reconciliation_scan_396(case_id,created_at);

            CREATE TABLE IF NOT EXISTS reconciliation_scan_signal_396(
              scan_signal_id TEXT PRIMARY KEY, scan_id TEXT NOT NULL, case_id TEXT NOT NULL,
              signal_type TEXT NOT NULL, signal_id TEXT NOT NULL, signal_hash TEXT NOT NULL,
              proposition TEXT NOT NULL DEFAULT '', match_state TEXT NOT NULL, match_reason TEXT NOT NULL,
              matched_target_ids_json TEXT NOT NULL, record_hash TEXT NOT NULL,
              UNIQUE(scan_id,signal_type,signal_id,signal_hash));
            CREATE INDEX IF NOT EXISTS idx_reconciliation_scan_signal_396_scan ON reconciliation_scan_signal_396(scan_id,match_state);

            CREATE TABLE IF NOT EXISTS reconciliation_impact_396(
              impact_id TEXT PRIMARY KEY, scan_id TEXT NOT NULL, case_id TEXT NOT NULL,
              target_type TEXT NOT NULL, target_id TEXT NOT NULL, active_node_id TEXT NOT NULL,
              active_generation INTEGER NOT NULL, source_signal_type TEXT NOT NULL, source_signal_id TEXT NOT NULL,
              impact_kind TEXT NOT NULL, rationale TEXT NOT NULL, review_state TEXT NOT NULL,
              created_at TEXT NOT NULL, record_hash TEXT NOT NULL,
              UNIQUE(scan_id,target_type,target_id,source_signal_type,source_signal_id,impact_kind));
            CREATE INDEX IF NOT EXISTS idx_reconciliation_impact_396_target ON reconciliation_impact_396(case_id,target_type,target_id,review_state);

            CREATE TABLE IF NOT EXISTS reanalysis_proposal_396(
              proposal_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, scan_id TEXT NOT NULL,
              target_type TEXT NOT NULL, target_id TEXT NOT NULL, expected_active_node_id TEXT NOT NULL,
              expected_generation INTEGER NOT NULL, impact_ids_json TEXT NOT NULL, rationale TEXT NOT NULL,
              status TEXT NOT NULL, branch_id TEXT NOT NULL DEFAULT '', execution_authority INTEGER NOT NULL,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, record_hash TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_reanalysis_proposal_396_case ON reanalysis_proposal_396(case_id,target_type,target_id,status);

            CREATE TABLE IF NOT EXISTS reanalysis_review_396(
              review_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL,
              disposition TEXT NOT NULL, rationale TEXT NOT NULL, reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL, record_hash TEXT NOT NULL);
            """
        )
        self.db.conn.commit()

    def _auth(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(
            dict(identity), case_id=case_id, capability=capability,
            object_type="phase17_case_reconciliation_v396", object_id=object_id,
        )

    def _rehash(self, table: str, pk: str, value: str) -> None:
        row = self.db.one(f"SELECT * FROM {table} WHERE {pk}=?", (value,))
        if not row:
            return
        d = dict(row)
        body = {k: d[k] for k in d if k != "record_hash"}
        self.db.execute(f"UPDATE {table} SET record_hash=? WHERE {pk}=?", (_sha(body), value))

    def _inventory(self, case_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        for r in self.db.all("SELECT candidate_id,canonical_hash,normalized_json,record_hash,review_status FROM evidence_candidate_389 WHERE case_id=? ORDER BY created_at,candidate_id", (case_id,)):
            cid = str(r["candidate_id"])
            valid = bool(self.intake389.verify_candidate(case_id=case_id, candidate_id=cid).get("valid"))
            if not valid:
                continue
            normalized = _j(r.get("normalized_json"), {})
            out.append({
                "signal_type": "evidence_candidate",
                "signal_id": cid,
                "signal_hash": str(r.get("record_hash") or r.get("canonical_hash") or ""),
                "proposition": "",
                "source_state": str(r.get("review_status") or "needs_review"),
                "normalized": normalized,
            })

        for r in self.db.all("SELECT review_id,proposition,status,disposition,record_hash FROM corroboration_review_390 WHERE case_id=? AND status='finalized' ORDER BY updated_at,review_id", (case_id,)):
            rid = str(r["review_id"])
            latest = self.db.one("SELECT assessment_id,record_hash FROM corroboration_assessment_390 WHERE review_id=? ORDER BY assessment_no DESC LIMIT 1", (rid,))
            if not latest:
                continue
            if not self.review390.verify_assessment(case_id=case_id, assessment_id=str(latest["assessment_id"])).get("valid"):
                continue
            out.append({
                "signal_type": "corroboration_review",
                "signal_id": rid,
                "signal_hash": _sha({"review_hash": r.get("record_hash"), "assessment_hash": latest.get("record_hash")}),
                "proposition": str(r.get("proposition") or ""),
                "source_state": str(r.get("disposition") or "finalized"),
            })

        for r in self.db.all("SELECT claim_id,proposition,status,analyst_disposition,record_hash FROM investigation_claim_391 WHERE case_id=? AND status='reviewed_candidate' ORDER BY updated_at,claim_id", (case_id,)):
            cid = str(r["claim_id"])
            if not self.synthesis391.verify_claim(case_id=case_id, claim_id=cid).get("valid"):
                continue
            out.append({
                "signal_type": "reviewed_claim",
                "signal_id": cid,
                "signal_hash": str(r.get("record_hash") or ""),
                "proposition": str(r.get("proposition") or ""),
                "source_state": str(r.get("analyst_disposition") or "reviewed_candidate"),
            })

        return out

    def _baseline_rows(self, baseline_id: str) -> set[tuple[str, str, str]]:
        return {
            (str(r["signal_type"]), str(r["signal_id"]), str(r["signal_hash"]))
            for r in self.db.all("SELECT signal_type,signal_id,signal_hash FROM reconciliation_baseline_signal_396 WHERE baseline_id=?", (baseline_id,))
        }

    def baseline(self, *, case_id: str, baseline_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._auth(identity, case_id, "case.read", baseline_id)
        r = self.db.one("SELECT * FROM reconciliation_baseline_396 WHERE case_id=? AND baseline_id=?", (case_id, baseline_id))
        if not r:
            raise KeyError(baseline_id)
        signals = [dict(x) for x in self.db.all("SELECT * FROM reconciliation_baseline_signal_396 WHERE baseline_id=? ORDER BY signal_type,signal_id", (baseline_id,))]
        return dict(r) | {"signals": signals, "truth_determined": False, "execution_authority": False}

    def latest_baseline(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        if identity is not None:
            self._auth(identity, case_id, "case.read", case_id)
        r = self.db.one("SELECT baseline_id FROM reconciliation_baseline_396 WHERE case_id=? ORDER BY created_at DESC,baseline_id DESC LIMIT 1", (case_id,))
        return self.baseline(case_id=case_id, baseline_id=str(r["baseline_id"])) if r else None

    def create_baseline(self, *, case_id: str, identity: Mapping[str, Any], confirmation: str, previous_baseline_id: str = "") -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_BASELINE:
            raise PermissionError(f"explicit confirmation {CONFIRM_BASELINE} required")
        self._auth(identity, case_id, "dossier.write", case_id)
        signals = self._inventory(case_id)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        signals = sorted(signals, key=lambda x: (str(x.get("signal_type")), str(x.get("signal_id")), str(x.get("signal_hash"))))
        signal_digest = _sha([{k: s.get(k) for k in ("signal_type", "signal_id", "signal_hash", "proposition", "source_state")} for s in signals])
        body = {
            "baseline_id": _sid("baseline396", {"case": case_id, "previous": previous_baseline_id, "digest": signal_digest, "at": now, "nonce": secrets.token_hex(4)}),
            "case_id": case_id,
            "previous_baseline_id": previous_baseline_id,
            "signal_count": len(signals),
            "baseline_hash": signal_digest,
            "created_by": actor,
            "created_at": now,
        }
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO reconciliation_baseline_396(baseline_id,case_id,previous_baseline_id,signal_count,baseline_hash,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
            for s in signals:
                row = {
                    "baseline_signal_id": _sid("bsig396", {"baseline": body["baseline_id"], "type": s["signal_type"], "id": s["signal_id"], "hash": s["signal_hash"]}),
                    "baseline_id": body["baseline_id"], "case_id": case_id,
                    "signal_type": s["signal_type"], "signal_id": s["signal_id"], "signal_hash": s["signal_hash"],
                    "proposition": str(s.get("proposition") or ""), "source_state": str(s.get("source_state") or ""),
                }
                self.db.execute("INSERT INTO reconciliation_baseline_signal_396(baseline_signal_id,baseline_id,case_id,signal_type,signal_id,signal_hash,proposition,source_state,record_hash) VALUES(?,?,?,?,?,?,?,?,?)", (*row.values(), _sha(row)))
        self.audit.log("baseline", "reconciliation_baseline_396", body["baseline_id"], case_id, {"signal_count": len(signals), "truth_determined": False})
        return self.baseline(case_id=case_id, baseline_id=body["baseline_id"], identity=identity)

    def _active_claims(self, case_id: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self.db.all("SELECT target_id FROM case_state_active_395 WHERE case_id=? AND target_type='claim' ORDER BY target_id", (case_id,)):
            s = self.state395.active_state(case_id=case_id, target_type="claim", target_id=str(r["target_id"]))
            out[str(r["target_id"])] = s
        return out

    def _active_hypotheses(self, case_id: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self.db.all("SELECT target_id FROM case_state_active_395 WHERE case_id=? AND target_type='hypothesis' ORDER BY target_id", (case_id,)):
            s = self.state395.active_state(case_id=case_id, target_type="hypothesis", target_id=str(r["target_id"]))
            out[str(r["target_id"])] = s
        return out

    def _active_plans(self, case_id: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self.db.all("SELECT target_id FROM case_state_active_395 WHERE case_id=? AND target_type='reasoning_plan' ORDER BY target_id", (case_id,)):
            s = self.state395.active_state(case_id=case_id, target_type="reasoning_plan", target_id=str(r["target_id"]))
            out[str(r["target_id"])] = s
        return out

    @staticmethod
    def _payload_refs(payload: Mapping[str, Any]) -> set[str]:
        refs: set[str] = set()
        for action in payload.get("actions") or []:
            if not isinstance(action, Mapping):
                continue
            for ref in action.get("object_refs") or []:
                if isinstance(ref, Mapping) and ref.get("object_id"):
                    refs.add(str(ref["object_id"]))
        return refs

    def _map_signal(self, case_id: str, signal: Mapping[str, Any], active_context: tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]] | None = None) -> tuple[list[dict[str, Any]], str, str]:
        if active_context is None:
            claims = self._active_claims(case_id); hypotheses = self._active_hypotheses(case_id); plans = self._active_plans(case_id)
        else:
            claims, hypotheses, plans = active_context
        matched_claims: set[str] = set()
        proposition = _norm_text(signal.get("proposition"))

        if signal["signal_type"] == "reviewed_claim":
            if str(signal["signal_id"]) in claims:
                matched_claims.add(str(signal["signal_id"]))
        elif signal["signal_type"] == "corroboration_review" and proposition:
            for cid, state in claims.items():
                if _norm_text((state.get("payload") or {}).get("proposition")) == proposition:
                    matched_claims.add(cid)
        elif signal["signal_type"] == "evidence_candidate":
            values = {_norm_text(v) for v in _walk_strings(signal.get("normalized") or {}) if _norm_text(v)}
            for cid, state in claims.items():
                cp = _norm_text((state.get("payload") or {}).get("proposition"))
                if cp and cp in values:
                    matched_claims.add(cid)

        if not matched_claims:
            return [], "unmatched_review_material", "no conservative exact claim/proposition match"

        impacts: list[dict[str, Any]] = []
        for cid in sorted(matched_claims):
            state = claims[cid]
            impacts.append({"target_type": "claim", "target_id": cid, "state": state, "impact_kind": "direct_new_signal", "rationale": f"New {signal['signal_type']} signal maps conservatively to the active claim."})

        matched_hypotheses: set[str] = set()
        for r in self.db.all("SELECT hypothesis_id,claim_id,relation FROM hypothesis_claim_link_391 WHERE claim_id IN (%s)" % ",".join("?" for _ in matched_claims), tuple(sorted(matched_claims))):
            hid = str(r.get("hypothesis_id") or "")
            if hid in hypotheses:
                matched_hypotheses.add(hid)
                state = hypotheses[hid]
                impacts.append({"target_type": "hypothesis", "target_id": hid, "state": state, "impact_kind": "dependency_propagation", "rationale": f"Active hypothesis depends on impacted claim {r.get('claim_id')} ({r.get('relation')})."})

        affected_ids = set(matched_claims) | matched_hypotheses
        for pid, state in plans.items():
            refs = self._payload_refs(state.get("payload") or {})
            if refs & affected_ids:
                impacts.append({"target_type": "reasoning_plan", "target_id": pid, "state": state, "impact_kind": "plan_dependency_propagation", "rationale": "Active reasoning plan references a claim or hypothesis affected by the new signal."})

        return impacts, "matched_active_state", "conservative exact match with dependency propagation"

    def scan(self, *, case_id: str, baseline_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._auth(identity, case_id, "case.read", baseline_id)
        baseline = self.baseline(case_id=case_id, baseline_id=baseline_id)
        known = self._baseline_rows(baseline_id)
        inventory = self._inventory(case_id)
        delta = [s for s in inventory if (s["signal_type"], s["signal_id"], s["signal_hash"]) not in known]
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        scan_id = _sid("scan396", {"case": case_id, "baseline": baseline_id, "delta": [(s["signal_type"], s["signal_id"], s["signal_hash"]) for s in delta], "at": now, "nonce": secrets.token_hex(4)})
        signal_rows: list[dict[str, Any]] = []
        impact_rows: list[dict[str, Any]] = []
        active_context = (self._active_claims(case_id), self._active_hypotheses(case_id), self._active_plans(case_id))
        matched = 0
        unmatched = 0
        for s in delta:
            impacts, match_state, reason = self._map_signal(case_id, s, active_context)
            if impacts:
                matched += 1
            else:
                unmatched += 1
            target_ids = [f"{x['target_type']}:{x['target_id']}" for x in impacts]
            sr = {
                "scan_signal_id": _sid("ssig396", {"scan": scan_id, "type": s["signal_type"], "id": s["signal_id"], "hash": s["signal_hash"]}),
                "scan_id": scan_id, "case_id": case_id, "signal_type": s["signal_type"], "signal_id": s["signal_id"], "signal_hash": s["signal_hash"],
                "proposition": str(s.get("proposition") or ""), "match_state": match_state, "match_reason": reason,
                "matched_target_ids_json": _canon(target_ids),
            }
            signal_rows.append(sr)
            for imp in impacts:
                st = imp["state"]
                ir = {
                    "impact_id": _sid("impact396", {"scan": scan_id, "t": imp["target_type"], "id": imp["target_id"], "sig": s["signal_id"], "kind": imp["impact_kind"]}),
                    "scan_id": scan_id, "case_id": case_id, "target_type": imp["target_type"], "target_id": imp["target_id"],
                    "active_node_id": str(st.get("active_node_id") or ""), "active_generation": int(st.get("generation") or 0),
                    "source_signal_type": s["signal_type"], "source_signal_id": s["signal_id"], "impact_kind": imp["impact_kind"],
                    "rationale": imp["rationale"], "review_state": "needs_reanalysis_review", "created_at": now,
                }
                impact_rows.append(ir)
        scan_state = "reanalysis_recommended" if impact_rows else ("new_unmatched_material" if delta else "no_change")
        body = {
            "scan_id": scan_id, "case_id": case_id, "baseline_id": baseline_id,
            "current_signal_count": len(inventory), "delta_signal_count": len(delta),
            "matched_signal_count": matched, "unmatched_signal_count": unmatched,
            "impact_count": len(impact_rows), "scan_state": scan_state, "created_by": actor, "created_at": now,
            "scan_hash": _sha({"baseline": baseline.get("baseline_hash"), "signals": signal_rows, "impacts": impact_rows}),
        }
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO reconciliation_scan_396(scan_id,case_id,baseline_id,current_signal_count,delta_signal_count,matched_signal_count,unmatched_signal_count,impact_count,scan_state,created_by,created_at,scan_hash,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
            for sr in signal_rows:
                self.db.execute("INSERT INTO reconciliation_scan_signal_396(scan_signal_id,scan_id,case_id,signal_type,signal_id,signal_hash,proposition,match_state,match_reason,matched_target_ids_json,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (*sr.values(), _sha(sr)))
            for ir in impact_rows:
                self.db.execute("INSERT OR IGNORE INTO reconciliation_impact_396(impact_id,scan_id,case_id,target_type,target_id,active_node_id,active_generation,source_signal_type,source_signal_id,impact_kind,rationale,review_state,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*ir.values(), _sha(ir)))
        self.audit.log("reconcile", "reconciliation_scan_396", scan_id, case_id, {"delta_signals": len(delta), "impacts": len(impact_rows), "unmatched": unmatched, "active_state_mutated": False})
        return self.scan_result(case_id=case_id, scan_id=scan_id, identity=identity)

    def scan_result(self, *, case_id: str, scan_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._auth(identity, case_id, "case.read", scan_id)
        r = self.db.one("SELECT * FROM reconciliation_scan_396 WHERE case_id=? AND scan_id=?", (case_id, scan_id))
        if not r:
            raise KeyError(scan_id)
        signals = []
        for x in self.db.all("SELECT * FROM reconciliation_scan_signal_396 WHERE scan_id=? ORDER BY signal_type,signal_id", (scan_id,)):
            d = dict(x); d["matched_target_ids"] = _j(d.pop("matched_target_ids_json"), []); signals.append(d)
        impacts = [dict(x) for x in self.db.all("SELECT * FROM reconciliation_impact_396 WHERE scan_id=? ORDER BY target_type,target_id,source_signal_id", (scan_id,))]
        return dict(r) | {"signals": signals, "impacts": impacts, "truth_determined": False, "execution_authority": False, "active_state_mutated": False}

    def propose_reanalysis(self, *, case_id: str, scan_id: str, target_type: str, target_id: str, identity: Mapping[str, Any], rationale: str) -> dict[str, Any]:
        t = str(target_type or "").casefold()
        if t not in _ALLOWED_TARGETS:
            raise ValueError("unsupported re-analysis target type")
        self._auth(identity, case_id, "dossier.write", target_id)
        scan = self.scan_result(case_id=case_id, scan_id=scan_id)
        impacts = [x for x in scan["impacts"] if x["target_type"] == t and x["target_id"] == target_id]
        if not impacts:
            raise ValueError("scan contains no impact for target")
        active = self.state395.active_state(case_id=case_id, target_type=t, target_id=target_id)
        reason = " ".join(str(rationale or "").split())[:4000]
        if len(reason) < 12:
            raise ValueError("substantive re-analysis rationale required")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        impact_ids = sorted({str(x["impact_id"]) for x in impacts})
        body = {
            "proposal_id": _sid("rean396", {"scan": scan_id, "t": t, "id": target_id, "generation": active["generation"], "impacts": impact_ids, "reason": reason}),
            "case_id": case_id, "scan_id": scan_id, "target_type": t, "target_id": target_id,
            "expected_active_node_id": active["active_node_id"], "expected_generation": int(active["generation"]),
            "impact_ids_json": _canon(impact_ids), "rationale": reason, "status": "proposal_needs_review",
            "branch_id": "", "execution_authority": 0, "created_by": actor, "created_at": now, "updated_at": now,
        }
        existing = self.db.one("SELECT proposal_id FROM reanalysis_proposal_396 WHERE proposal_id=?", (body["proposal_id"],))
        if not existing:
            self.db.execute("INSERT INTO reanalysis_proposal_396(proposal_id,case_id,scan_id,target_type,target_id,expected_active_node_id,expected_generation,impact_ids_json,rationale,status,branch_id,execution_authority,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
        return self.proposal(case_id=case_id, proposal_id=body["proposal_id"], identity=identity)

    def proposal(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM reanalysis_proposal_396 WHERE case_id=? AND proposal_id=?", (case_id, proposal_id))
        if not r:
            raise KeyError(proposal_id)
        d = dict(r)
        if identity is not None:
            self._auth(identity, case_id, "case.read", d["target_id"])
        d["impact_ids"] = _j(d.pop("impact_ids_json"), [])
        rv = self.db.one("SELECT * FROM reanalysis_review_396 WHERE proposal_id=?", (proposal_id,))
        return d | {"review": dict(rv) if rv else None, "execution_authority": False, "active_state_mutated": False}

    def review_reanalysis(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any], disposition: str, rationale: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_REVIEW} required")
        p = self.proposal(case_id=case_id, proposal_id=proposal_id)
        self._auth(identity, case_id, "dossier.write", p["target_id"])
        if p["status"] != "proposal_needs_review":
            raise PermissionError("re-analysis proposal already reviewed")
        disp = str(disposition or "").casefold()
        if disp not in {"approve", "reject", "defer"}:
            raise ValueError("unsupported re-analysis review disposition")
        reason = " ".join(str(rationale or "").split())[:4000]
        if len(reason) < 12:
            raise ValueError("substantive review rationale required")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        review = {
            "review_id": _sid("reanrev396", {"proposal": proposal_id, "disposition": disp, "reviewer": actor}),
            "proposal_id": proposal_id, "case_id": case_id, "disposition": disp, "rationale": reason,
            "reviewed_by": actor, "reviewed_at": now,
        }
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO reanalysis_review_396(review_id,proposal_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*review.values(), _sha(review)))
            status = "reviewed_for_reanalysis" if disp == "approve" else ("rejected" if disp == "reject" else "deferred")
            self.db.execute("UPDATE reanalysis_proposal_396 SET status=?,updated_at=? WHERE proposal_id=?", (status, now, proposal_id))
            self._rehash("reanalysis_proposal_396", "proposal_id", proposal_id)
        return self.proposal(case_id=case_id, proposal_id=proposal_id, identity=identity)

    def create_reanalysis_branch(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any], confirmation: str, branch_name: str = "") -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_BRANCH:
            raise PermissionError(f"explicit confirmation {CONFIRM_BRANCH} required")
        p = self.proposal(case_id=case_id, proposal_id=proposal_id)
        self._auth(identity, case_id, "dossier.write", p["target_id"])
        rv = p.get("review") or {}
        if p["status"] != "reviewed_for_reanalysis" or rv.get("disposition") != "approve":
            raise PermissionError("only an approved re-analysis proposal may create a branch")
        if p.get("branch_id"):
            return self.state395.branch(case_id=case_id, branch_id=p["branch_id"], identity=identity) | {"reanalysis_proposal_id": proposal_id, "adopted": False}
        active = self.state395.active_state(case_id=case_id, target_type=p["target_type"], target_id=p["target_id"])
        if int(active.get("generation") or 0) != int(p["expected_generation"]) or str(active.get("active_node_id") or "") != str(p["expected_active_node_id"]):
            raise PermissionError("active case-state changed since re-analysis proposal review; create a fresh scan/proposal")
        name = " ".join(str(branch_name or "").split())[:120] or f"Reanalysis {p['target_type']} {proposal_id[-8:]}"
        branch = self.state395.create_branch(
            case_id=case_id, target_type=p["target_type"], target_id=p["target_id"], branch_name=name,
            identity=identity, confirmation=CONFIRM_CASE_STATE_BRANCH,
        )
        now = _now()
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE reanalysis_proposal_396 SET status='branch_created',branch_id=?,updated_at=? WHERE proposal_id=?", (branch["branch_id"], now, proposal_id))
            self._rehash("reanalysis_proposal_396", "proposal_id", proposal_id)
        self.audit.log("branch", "reanalysis_proposal_396", proposal_id, case_id, {"branch_id": branch["branch_id"], "active_state_mutated": False, "execution_authority": False})
        return branch | {"reanalysis_proposal_id": proposal_id, "adopted": False, "execution_authority": False}

    def advance_baseline(self, *, case_id: str, scan_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_ADVANCE:
            raise PermissionError(f"explicit confirmation {CONFIRM_ADVANCE} required")
        self._auth(identity, case_id, "dossier.write", scan_id)
        scan = self.scan_result(case_id=case_id, scan_id=scan_id)
        return self.create_baseline(case_id=case_id, identity=identity, confirmation=CONFIRM_BASELINE, previous_baseline_id=str(scan["baseline_id"]))

    def verify_baseline(self, *, case_id: str, baseline_id: str) -> dict[str, Any]:
        b = self.baseline(case_id=case_id, baseline_id=baseline_id)
        row = self.db.one("SELECT * FROM reconciliation_baseline_396 WHERE baseline_id=?", (baseline_id,))
        row_body = {k: row[k] for k in row if k != "record_hash"}
        rows_valid = str(row.get("record_hash") or "") == _sha(row_body)
        signals_valid = True
        digest_data = []
        for r in self.db.all("SELECT * FROM reconciliation_baseline_signal_396 WHERE baseline_id=? ORDER BY signal_type,signal_id", (baseline_id,)):
            body = {k: r[k] for k in r if k != "record_hash"}
            signals_valid = signals_valid and str(r.get("record_hash") or "") == _sha(body)
            digest_data.append({k: r[k] for k in ("signal_type", "signal_id", "signal_hash", "proposition", "source_state")})
        digest_valid = str(b.get("baseline_hash") or "") == _sha(digest_data)
        return {"baseline_id": baseline_id, "row_hash_valid": rows_valid, "signal_hashes_valid": signals_valid, "baseline_hash_valid": digest_valid, "valid": rows_valid and signals_valid and digest_valid}

    def verify_scan(self, *, case_id: str, scan_id: str) -> dict[str, Any]:
        r = self.db.one("SELECT * FROM reconciliation_scan_396 WHERE case_id=? AND scan_id=?", (case_id, scan_id))
        if not r:
            raise KeyError(scan_id)
        body = {k: r[k] for k in r if k != "record_hash"}
        row_valid = str(r.get("record_hash") or "") == _sha(body)
        children_valid = True
        for table in ("reconciliation_scan_signal_396", "reconciliation_impact_396"):
            for x in self.db.all(f"SELECT * FROM {table} WHERE scan_id=?", (scan_id,)):
                xb = {k: x[k] for k in x if k != "record_hash"}
                children_valid = children_valid and str(x.get("record_hash") or "") == _sha(xb)
        return {"scan_id": scan_id, "row_hash_valid": row_valid, "child_hashes_valid": children_valid, "valid": row_valid and children_valid}

    def status(self) -> dict[str, Any]:
        b = self.db.one("SELECT COUNT(*) n FROM reconciliation_baseline_396") or {}
        s = self.db.one("SELECT COUNT(*) n FROM reconciliation_scan_396") or {}
        p = self.db.one("SELECT COUNT(*) n,SUM(CASE WHEN status='branch_created' THEN 1 ELSE 0 END) branches FROM reanalysis_proposal_396") or {}
        return {
            "build": BUILD, "policy": POLICY_ID,
            "incremental_reconciliation": True, "explicit_baseline": True, "delta_only_signal_comparison": True,
            "conservative_exact_matching": True, "unmatched_evidence_preserved": True,
            "dependency_propagation": True, "review_required_reanalysis": True,
            "controlled_reanalysis_branch": True, "stale_generation_protection": True,
            "append_only_history": True, "active_state_auto_mutation": False,
            "automatic_evidence_promotion": False, "automatic_go_issuance": False,
            "automatic_live_confirmation": False, "automatic_identity_merge": False,
            "truth_probability": False, "automatic_truth_acceptance": False,
            "direct_network_fetch": False, "execution_authority": False,
            "baselines": int(b.get("n") or 0), "scans": int(s.get("n") or 0),
            "proposals": int(p.get("n") or 0), "reanalysis_branches": int(p.get("branches") or 0),
        }
