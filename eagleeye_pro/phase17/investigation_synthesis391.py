from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping

BUILD = "391.0"
POLICY_ID = "phase17.ai-investigation-synthesis.v391"
CONFIRM_CLAIM_REVIEW = "REVIEW SYNTHESIZED CLAIM"
CONFIRM_HYPOTHESIS_REVIEW = "REVIEW HYPOTHESIS"
CONFIRM_KERNEL_ADMISSION = "ADMIT TO INVESTIGATION KERNEL"
CONFIRM_SNAPSHOT = "SNAPSHOT SYNTHESIS"

_ALLOWED_CLAIM_DISPOSITIONS = {
    "retain_candidate",
    "needs_more_evidence",
    "contested_requires_analysis",
    "ready_for_hypothesis_work",
    "discard_not_supported",
}
_ALLOWED_HYPOTHESIS_DISPOSITIONS = {
    "retain_for_testing",
    "needs_more_evidence",
    "revise_requested",
    "rejected",
}
_ALLOWED_HYPOTHESIS_RELATIONS = {
    "supports_hypothesis",
    "contradicts_hypothesis",
    "context",
    "test_target",
}


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


def _claim_state(assessment_state: str) -> str:
    mapping = {
        "multi_group_support": "multi_source_support_structure",
        "single_independence_group": "single_source_group",
        "contested_multi_source": "contested_multi_source",
        "contested_single_support_group": "contested_single_support_group",
        "contradiction_only": "contradiction_only",
        "context_only": "context_only",
        "independence_unresolved": "source_independence_unresolved",
        "insufficient_review_material": "insufficient_review_material",
        "integrity_review_required": "integrity_review_required",
    }
    return mapping.get(str(assessment_state or ""), "needs_analysis")


class InvestigationSynthesis391:
    """Phase-17 epistemic synthesis without automatic truth or probability assignment.

    Build 391 converts finalized Build-390 corroboration reviews into candidate claims,
    preserves supporting and contradicting observations separately, permits review-only
    hypothesis proposals, and bridges reviewed analytical work into Investigation Kernel
    notebook entries. It deliberately does not call the legacy probabilistic hypothesis
    recalculation path and does not create verified facts or evidence automatically.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        review390: Any,
        intake389: Any,
        kernel112: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.review390 = review390
        self.intake389 = intake389
        self.kernel112 = kernel112
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS investigation_claim_391 (
              claim_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              corroboration_review_id TEXT NOT NULL UNIQUE,
              proposition TEXT NOT NULL,
              epistemic_status TEXT NOT NULL,
              structural_state TEXT NOT NULL,
              support_groups INTEGER NOT NULL,
              contradiction_groups INTEGER NOT NULL,
              context_groups INTEGER NOT NULL,
              unresolved_observations INTEGER NOT NULL,
              corroboration_disposition TEXT NOT NULL,
              status TEXT NOT NULL,
              analyst_disposition TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              source_review_hash TEXT NOT NULL,
              record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_investigation_claim_391_case ON investigation_claim_391(case_id,status,updated_at);

            CREATE TABLE IF NOT EXISTS investigation_claim_candidate_391 (
              link_id TEXT PRIMARY KEY,
              claim_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              candidate_id TEXT NOT NULL,
              stance TEXT NOT NULL,
              independence_group TEXT NOT NULL,
              counted_as_independent INTEGER NOT NULL,
              candidate_hash TEXT NOT NULL,
              candidate_record_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(claim_id,candidate_id,stance),
              FOREIGN KEY(claim_id) REFERENCES investigation_claim_391(claim_id)
            );
            CREATE INDEX IF NOT EXISTS idx_claim_candidate_391_claim ON investigation_claim_candidate_391(claim_id,stance);

            CREATE TABLE IF NOT EXISTS investigation_claim_review_391 (
              claim_review_id TEXT PRIMARY KEY,
              claim_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              disposition TEXT NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(claim_id) REFERENCES investigation_claim_391(claim_id)
            );

            CREATE TABLE IF NOT EXISTS investigation_hypothesis_391 (
              hypothesis_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              title TEXT NOT NULL,
              statement TEXT NOT NULL,
              test_plan TEXT NOT NULL,
              epistemic_status TEXT NOT NULL,
              status TEXT NOT NULL,
              origin TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_investigation_hypothesis_391_case ON investigation_hypothesis_391(case_id,status,updated_at);

            CREATE TABLE IF NOT EXISTS hypothesis_claim_link_391 (
              link_id TEXT PRIMARY KEY,
              hypothesis_id TEXT NOT NULL,
              claim_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              relation TEXT NOT NULL,
              claim_record_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(hypothesis_id,claim_id,relation),
              FOREIGN KEY(hypothesis_id) REFERENCES investigation_hypothesis_391(hypothesis_id),
              FOREIGN KEY(claim_id) REFERENCES investigation_claim_391(claim_id)
            );

            CREATE TABLE IF NOT EXISTS investigation_hypothesis_review_391 (
              hypothesis_review_id TEXT PRIMARY KEY,
              hypothesis_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              disposition TEXT NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(hypothesis_id) REFERENCES investigation_hypothesis_391(hypothesis_id)
            );

            CREATE TABLE IF NOT EXISTS kernel_synthesis_bridge_391 (
              bridge_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT NOT NULL,
              kernel_entry_id TEXT NOT NULL,
              bridge_state TEXT NOT NULL,
              source_record_hash TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,object_type,object_id)
            );

            CREATE TABLE IF NOT EXISTS synthesis_snapshot_391 (
              snapshot_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              snapshot_hash TEXT NOT NULL,
              record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_synthesis_snapshot_391_case ON synthesis_snapshot_391(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(dict(identity), case_id=case_id, capability=capability, object_type="phase17_synthesis_v391", object_id=object_id)

    def _claim_row(self, case_id: str, claim_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_claim_391 WHERE claim_id=? AND case_id=?", (claim_id, case_id))
        if not row:
            raise KeyError(claim_id)
        return dict(row)

    def _hypothesis_row(self, case_id: str, hypothesis_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_hypothesis_391 WHERE hypothesis_id=? AND case_id=?", (hypothesis_id, case_id))
        if not row:
            raise KeyError(hypothesis_id)
        return dict(row)

    def _latest_assessment_row(self, case_id: str, review_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM corroboration_assessment_390 WHERE case_id=? AND review_id=? ORDER BY assessment_no DESC LIMIT 1",
            (case_id, review_id),
        )
        if not row:
            raise PermissionError("corroboration review has no assessment")
        verify = self.review390.verify_assessment(case_id=case_id, assessment_id=str(row["assessment_id"]))
        if not bool(verify.get("valid")):
            raise PermissionError("corroboration assessment integrity invalid")
        return dict(row)

    def synthesize_review(self, *, case_id: str, review_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "source.review", review_id)
        existing = self.db.one("SELECT claim_id FROM investigation_claim_391 WHERE case_id=? AND corroboration_review_id=?", (case_id, review_id))
        if existing:
            return self.claim(case_id=case_id, claim_id=str(existing["claim_id"]), identity=identity)
        review = self.review390.review(case_id=case_id, review_id=review_id, identity=identity)
        if str(review.get("status") or "") != "finalized":
            raise PermissionError("corroboration review must be finalized before claim synthesis")
        latest = self._latest_assessment_row(case_id, review_id)
        assessment = _j(latest.get("assessment_json"), {}) or {}
        if int(assessment.get("invalid_candidates") or 0) > 0:
            raise PermissionError("invalid candidate integrity blocks synthesis")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        source_review_hash = _sha({
            "review_record_hash": str(review.get("record_hash") or ""),
            "assessment_record_hash": str(latest.get("record_hash") or ""),
            "assessment_id": str(latest.get("assessment_id") or ""),
        })
        body = {
            "claim_id": "claim391_" + secrets.token_hex(12),
            "case_id": case_id,
            "corroboration_review_id": review_id,
            "proposition": str(review.get("proposition") or "")[:12000],
            "epistemic_status": "candidate_claim_not_fact",
            "structural_state": _claim_state(str(assessment.get("assessment_state") or "")),
            "support_groups": int(assessment.get("support_groups") or 0),
            "contradiction_groups": int(assessment.get("contradiction_groups") or 0),
            "context_groups": int(assessment.get("context_groups") or 0),
            "unresolved_observations": int(assessment.get("unresolved_observations") or 0),
            "corroboration_disposition": str(review.get("disposition") or ""),
            "status": "candidate_claim_needs_review",
            "analyst_disposition": "",
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
            "source_review_hash": source_review_hash,
        }
        observations = {str(o.get("candidate_id") or ""): o for o in (assessment.get("observations") or []) if isinstance(o, Mapping)}
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO investigation_claim_391(claim_id,case_id,corroboration_review_id,proposition,epistemic_status,structural_state,support_groups,contradiction_groups,context_groups,unresolved_observations,corroboration_disposition,status,analyst_disposition,created_by,created_at,updated_at,source_review_hash,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*body.values(), _sha(body)),
            )
            for link in review.get("links") or []:
                candidate_id = str(link.get("candidate_id") or "")
                cand = self.db.one("SELECT * FROM evidence_candidate_389 WHERE candidate_id=? AND case_id=?", (candidate_id, case_id))
                if not cand:
                    raise PermissionError("linked candidate missing")
                integrity = self.intake389.verify_candidate(case_id=case_id, candidate_id=candidate_id)
                if not bool(integrity.get("valid")):
                    raise PermissionError("linked candidate integrity invalid")
                obs = observations.get(candidate_id, {})
                lbody = {
                    "link_id": "clink391_" + secrets.token_hex(10),
                    "claim_id": body["claim_id"],
                    "case_id": case_id,
                    "candidate_id": candidate_id,
                    "stance": str(link.get("stance") or "context"),
                    "independence_group": str(obs.get("independence_group") or "unresolved"),
                    "counted_as_independent": int(bool(obs.get("counted_as_independent"))),
                    "candidate_hash": str(cand.get("canonical_hash") or ""),
                    "candidate_record_hash": str(cand.get("record_hash") or ""),
                    "created_at": now,
                }
                self.db.execute(
                    "INSERT INTO investigation_claim_candidate_391(link_id,claim_id,case_id,candidate_id,stance,independence_group,counted_as_independent,candidate_hash,candidate_record_hash,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (*lbody.values(), _sha(lbody)),
                )
        self.audit.log("synthesize", "investigation_claim_391", body["claim_id"], case_id, {"review_id": review_id, "truth_determined": False, "probability_assigned": False})
        return self.claim(case_id=case_id, claim_id=body["claim_id"], identity=identity)

    def synthesize_case(self, *, case_id: str, identity: Mapping[str, Any], limit: int = 100) -> dict[str, Any]:
        self._authorize(identity, case_id, "source.review", case_id)
        rows = self.db.all(
            "SELECT review_id FROM corroboration_review_390 r WHERE case_id=? AND status='finalized' AND NOT EXISTS (SELECT 1 FROM investigation_claim_391 c WHERE c.corroboration_review_id=r.review_id) ORDER BY updated_at LIMIT ?",
            (case_id, max(1, min(int(limit), 500))),
        )
        claims = [self.synthesize_review(case_id=case_id, review_id=str(r["review_id"]), identity=identity) for r in rows]
        return {"case_id": case_id, "created": len(claims), "claims": claims, "truth_determined": False, "automatic_claim_acceptance": False}

    def claim(self, *, case_id: str, claim_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", claim_id)
        row = self._claim_row(case_id, claim_id)
        links = [dict(r) for r in self.db.all("SELECT * FROM investigation_claim_candidate_391 WHERE claim_id=? ORDER BY created_at,link_id", (claim_id,))]
        review = self.db.one("SELECT * FROM investigation_claim_review_391 WHERE claim_id=?", (claim_id,))
        return {
            **row,
            "candidate_links": links,
            "review": dict(review) if review else None,
            "support_candidate_ids": [x["candidate_id"] for x in links if x["stance"] == "supports"],
            "counterevidence_candidate_ids": [x["candidate_id"] for x in links if x["stance"] == "contradicts"],
            "context_candidate_ids": [x["candidate_id"] for x in links if x["stance"] == "context"],
            "truth_determined": False,
            "probability_assigned": False,
            "verified_fact": False,
        }

    def review_claim(self, *, case_id: str, claim_id: str, identity: Mapping[str, Any], disposition: str, rationale: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_CLAIM_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_CLAIM_REVIEW} required")
        self._authorize(identity, case_id, "source.review", claim_id)
        disp = str(disposition or "").strip().lower()
        if disp not in _ALLOWED_CLAIM_DISPOSITIONS:
            raise ValueError("unsupported claim disposition")
        if len(str(rationale or "").strip()) < 12:
            raise ValueError("substantive claim review rationale required")
        claim = self._claim_row(case_id, claim_id)
        if str(claim.get("status") or "") != "candidate_claim_needs_review":
            raise PermissionError("claim already reviewed or not reviewable")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        review = {
            "claim_review_id": "claimrev391_" + secrets.token_hex(10),
            "claim_id": claim_id,
            "case_id": case_id,
            "disposition": disp,
            "rationale": str(rationale).strip()[:4000],
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        updated = {k: claim[k] for k in claim if k != "record_hash"}
        updated.update({"status": "reviewed_candidate", "analyst_disposition": disp, "updated_at": now})
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO investigation_claim_review_391(claim_review_id,claim_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*review.values(), _sha(review)))
            self.db.execute("UPDATE investigation_claim_391 SET status=?,analyst_disposition=?,updated_at=?,record_hash=? WHERE claim_id=?", ("reviewed_candidate", disp, now, _sha(updated), claim_id))
        self.audit.log("review", "investigation_claim_391", claim_id, case_id, {"disposition": disp, "truth_determined": False})
        return self.claim(case_id=case_id, claim_id=claim_id, identity=identity)

    def propose_hypothesis(
        self,
        *,
        case_id: str,
        title: str,
        statement: str,
        test_plan: str,
        claim_relations: Mapping[str, str],
        identity: Mapping[str, Any],
        origin: str = "ai_proposed_for_review",
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", case_id)
        title_clean = " ".join(str(title or "").split())[:500]
        statement_clean = " ".join(str(statement or "").split())[:12000]
        test_clean = " ".join(str(test_plan or "").split())[:12000]
        if len(title_clean) < 3 or len(statement_clean) < 8 or len(test_clean) < 8:
            raise ValueError("title, statement and test plan are required")
        if not claim_relations or len(claim_relations) > 100:
            raise ValueError("1..100 reviewed claim relations required")
        claims: list[tuple[dict[str, Any], str]] = []
        for claim_id, relation_raw in claim_relations.items():
            relation = str(relation_raw or "").strip().lower()
            if relation not in _ALLOWED_HYPOTHESIS_RELATIONS:
                raise ValueError(f"unsupported hypothesis relation: {relation}")
            claim = self._claim_row(case_id, str(claim_id))
            if str(claim.get("status") or "") != "reviewed_candidate":
                raise PermissionError("hypothesis may only bind reviewed candidate claims")
            claims.append((claim, relation))
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        body = {
            "hypothesis_id": "hyp391_" + secrets.token_hex(12),
            "case_id": case_id,
            "title": title_clean,
            "statement": statement_clean,
            "test_plan": test_clean,
            "epistemic_status": "hypothesis_not_fact",
            "status": "proposal_needs_review",
            "origin": str(origin or "ai_proposed_for_review")[:120],
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO investigation_hypothesis_391(hypothesis_id,case_id,title,statement,test_plan,epistemic_status,status,origin,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
            for claim, relation in claims:
                lbody = {
                    "link_id": "hcl391_" + secrets.token_hex(10),
                    "hypothesis_id": body["hypothesis_id"],
                    "claim_id": str(claim["claim_id"]),
                    "case_id": case_id,
                    "relation": relation,
                    "claim_record_hash": str(claim.get("record_hash") or ""),
                    "created_at": now,
                }
                self.db.execute("INSERT INTO hypothesis_claim_link_391(link_id,hypothesis_id,claim_id,case_id,relation,claim_record_hash,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*lbody.values(), _sha(lbody)))
        self.audit.log("propose", "investigation_hypothesis_391", body["hypothesis_id"], case_id, {"claim_count": len(claims), "truth_determined": False, "probability_assigned": False})
        return self.hypothesis(case_id=case_id, hypothesis_id=body["hypothesis_id"], identity=identity)

    def hypothesis(self, *, case_id: str, hypothesis_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", hypothesis_id)
        row = self._hypothesis_row(case_id, hypothesis_id)
        links = [dict(r) for r in self.db.all("SELECT * FROM hypothesis_claim_link_391 WHERE hypothesis_id=? ORDER BY created_at,link_id", (hypothesis_id,))]
        review = self.db.one("SELECT * FROM investigation_hypothesis_review_391 WHERE hypothesis_id=?", (hypothesis_id,))
        bridge = self.db.one("SELECT * FROM kernel_synthesis_bridge_391 WHERE case_id=? AND object_type='hypothesis' AND object_id=?", (case_id, hypothesis_id))
        return {**row, "claim_links": links, "review": dict(review) if review else None, "kernel_bridge": dict(bridge) if bridge else None, "truth_determined": False, "probability_assigned": False, "legacy_kernel_confidence_used": False}

    def review_hypothesis(self, *, case_id: str, hypothesis_id: str, identity: Mapping[str, Any], disposition: str, rationale: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_HYPOTHESIS_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_HYPOTHESIS_REVIEW} required")
        self._authorize(identity, case_id, "dossier.write", hypothesis_id)
        disp = str(disposition or "").strip().lower()
        if disp not in _ALLOWED_HYPOTHESIS_DISPOSITIONS:
            raise ValueError("unsupported hypothesis disposition")
        if len(str(rationale or "").strip()) < 12:
            raise ValueError("substantive hypothesis review rationale required")
        hypothesis = self._hypothesis_row(case_id, hypothesis_id)
        if str(hypothesis.get("status") or "") != "proposal_needs_review":
            raise PermissionError("hypothesis already reviewed or not reviewable")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        rev = {
            "hypothesis_review_id": "hyprev391_" + secrets.token_hex(10),
            "hypothesis_id": hypothesis_id,
            "case_id": case_id,
            "disposition": disp,
            "rationale": str(rationale).strip()[:4000],
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        updated = {k: hypothesis[k] for k in hypothesis if k != "record_hash"}
        updated.update({"status": disp, "updated_at": now})
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO investigation_hypothesis_review_391(hypothesis_review_id,hypothesis_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*rev.values(), _sha(rev)))
            self.db.execute("UPDATE investigation_hypothesis_391 SET status=?,updated_at=?,record_hash=? WHERE hypothesis_id=?", (disp, now, _sha(updated), hypothesis_id))
        self.audit.log("review", "investigation_hypothesis_391", hypothesis_id, case_id, {"disposition": disp, "truth_determined": False})
        return self.hypothesis(case_id=case_id, hypothesis_id=hypothesis_id, identity=identity)

    def _bridge(self, *, case_id: str, object_type: str, object_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_KERNEL_ADMISSION:
            raise PermissionError(f"explicit confirmation {CONFIRM_KERNEL_ADMISSION} required")
        self._authorize(identity, case_id, "dossier.write", object_id)
        existing = self.db.one("SELECT * FROM kernel_synthesis_bridge_391 WHERE case_id=? AND object_type=? AND object_id=?", (case_id, object_type, object_id))
        if existing:
            return dict(existing)
        actor = str(identity.get("username") or self.actor)[:120]
        if object_type == "claim":
            obj = self._claim_row(case_id, object_id)
            if str(obj.get("status") or "") != "reviewed_candidate":
                raise PermissionError("claim must be reviewed before kernel admission")
            title = "Phase-17 candidate claim"
            body = _canon({"epistemic_status": obj["epistemic_status"], "proposition": obj["proposition"], "structural_state": obj["structural_state"], "analyst_disposition": obj["analyst_disposition"], "truth_determined": False})
            related = [object_id, str(obj.get("corroboration_review_id") or "")]
            source_hash = str(obj.get("record_hash") or "")
        elif object_type == "hypothesis":
            obj = self._hypothesis_row(case_id, object_id)
            if str(obj.get("status") or "") != "retain_for_testing":
                raise PermissionError("only retained-for-testing hypotheses may enter the kernel")
            title = "Phase-17 hypothesis for testing"
            body = _canon({"epistemic_status": "hypothesis_not_fact", "title": obj["title"], "statement": obj["statement"], "test_plan": obj["test_plan"], "truth_determined": False, "probability_assigned": False})
            related = [object_id] + [str(r["claim_id"]) for r in self.db.all("SELECT claim_id FROM hypothesis_claim_link_391 WHERE hypothesis_id=? ORDER BY created_at", (object_id,))]
            source_hash = str(obj.get("record_hash") or "")
        else:
            raise ValueError("object_type must be claim or hypothesis")
        # Intentional: notebook/event bridge only. Do not call kernel112.hypothesis(),
        # whose legacy implementation carries numerical prior/confidence fields.
        kernel_entry_id = self.kernel112.note(case_id, actor, f"phase17_{object_type}_candidate", title, body, related)
        now = _now()
        bridge = {
            "bridge_id": "kbridge391_" + secrets.token_hex(10),
            "case_id": case_id,
            "object_type": object_type,
            "object_id": object_id,
            "kernel_entry_id": kernel_entry_id,
            "bridge_state": "kernel_notebook_candidate",
            "source_record_hash": source_hash,
            "created_by": actor,
            "created_at": now,
        }
        self.db.execute("INSERT INTO kernel_synthesis_bridge_391(bridge_id,case_id,object_type,object_id,kernel_entry_id,bridge_state,source_record_hash,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)", (*bridge.values(), _sha(bridge)))
        self.audit.log("bridge", "kernel_synthesis_bridge_391", bridge["bridge_id"], case_id, {"object_type": object_type, "object_id": object_id, "legacy_kernel_confidence_used": False})
        return {**bridge, "record_hash": _sha(bridge), "legacy_kernel_confidence_used": False, "truth_determined": False}

    def admit_claim_to_kernel(self, *, case_id: str, claim_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        return self._bridge(case_id=case_id, object_type="claim", object_id=claim_id, identity=identity, confirmation=confirmation)

    def admit_hypothesis_to_kernel(self, *, case_id: str, hypothesis_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        return self._bridge(case_id=case_id, object_type="hypothesis", object_id=hypothesis_id, identity=identity, confirmation=confirmation)

    def _feed(self, case_id: str) -> dict[str, Any]:
        claims = [self.claim(case_id=case_id, claim_id=str(r["claim_id"])) for r in self.db.all("SELECT claim_id FROM investigation_claim_391 WHERE case_id=? ORDER BY updated_at DESC,claim_id", (case_id,))]
        hypotheses = [self.hypothesis(case_id=case_id, hypothesis_id=str(r["hypothesis_id"])) for r in self.db.all("SELECT hypothesis_id FROM investigation_hypothesis_391 WHERE case_id=? ORDER BY updated_at DESC,hypothesis_id", (case_id,))]
        counterevidence = []
        for claim in claims:
            for link in claim.get("candidate_links") or []:
                if link.get("stance") == "contradicts":
                    counterevidence.append({"claim_id": claim["claim_id"], "candidate_id": link["candidate_id"], "independence_group": link["independence_group"], "counted_as_independent": bool(link["counted_as_independent"])})
        open_questions: list[str] = []
        for claim in claims:
            if int(claim.get("unresolved_observations") or 0) > 0:
                open_questions.append(f"Resolve source independence for claim {claim['claim_id']} before stronger analytical use.")
            if int(claim.get("support_groups") or 0) < 2 and claim.get("analyst_disposition") != "discard_not_supported":
                open_questions.append(f"Seek an additional independent source group for claim {claim['claim_id']}.")
            if int(claim.get("contradiction_groups") or 0) > 0:
                open_questions.append(f"Investigate preserved counterevidence for claim {claim['claim_id']}.")
            if claim.get("analyst_disposition") == "needs_more_evidence":
                open_questions.append(f"Close the evidence gap documented for claim {claim['claim_id']}.")
        for hyp in hypotheses:
            if hyp.get("status") in {"proposal_needs_review", "retain_for_testing", "needs_more_evidence", "revise_requested"}:
                open_questions.append(f"Test/review hypothesis {hyp['hypothesis_id']}: {hyp['test_plan'][:240]}")
        return {
            "case_id": case_id,
            "build": BUILD,
            "claims": claims,
            "hypotheses": hypotheses,
            "counterevidence": counterevidence,
            "open_questions": list(dict.fromkeys(open_questions))[:500],
            "epistemic_contract": {
                "observation": "Build-389 normalized candidate observation",
                "corroboration": "Build-390 source-independence structure",
                "claim": "Build-391 analyst-reviewable proposition; not a verified fact",
                "hypothesis": "Build-391 explanatory/testable proposition; not a fact",
            },
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_claim_acceptance": False,
            "automatic_evidence_promotion": False,
            "legacy_kernel_confidence_used": False,
            "network_requests_created": 0,
        }

    def ai_synthesis_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        return self._feed(case_id)

    def create_snapshot(self, *, case_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_SNAPSHOT:
            raise PermissionError(f"explicit confirmation {CONFIRM_SNAPSHOT} required")
        self._authorize(identity, case_id, "dossier.write", case_id)
        actor = str(identity.get("username") or self.actor)[:120]
        payload = self._feed(case_id)
        created = _now()
        snapshot_hash = _sha(payload)
        body = {"snapshot_id": "snap391_" + secrets.token_hex(12), "case_id": case_id, "payload_json": _canon(payload), "created_by": actor, "created_at": created, "snapshot_hash": snapshot_hash}
        self.db.execute("INSERT INTO synthesis_snapshot_391(snapshot_id,case_id,payload_json,created_by,created_at,snapshot_hash,record_hash) VALUES(?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
        self.audit.log("snapshot", "synthesis_snapshot_391", body["snapshot_id"], case_id, {"snapshot_hash": snapshot_hash, "truth_determined": False})
        return {"snapshot_id": body["snapshot_id"], "case_id": case_id, "snapshot_hash": snapshot_hash, "created_at": created, "payload": payload}

    def verify_claim(self, *, case_id: str, claim_id: str) -> dict[str, Any]:
        row = self._claim_row(case_id, claim_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        links_ok = True
        for link in self.db.all("SELECT * FROM investigation_claim_candidate_391 WHERE claim_id=?", (claim_id,)):
            lbody = {k: link[k] for k in link if k != "record_hash"}
            links_ok = links_ok and str(link.get("record_hash") or "") == _sha(lbody)
        return {"claim_id": claim_id, "valid": str(row.get("record_hash") or "") == _sha(body) and links_ok}

    def verify_hypothesis(self, *, case_id: str, hypothesis_id: str) -> dict[str, Any]:
        row = self._hypothesis_row(case_id, hypothesis_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        links_ok = True
        for link in self.db.all("SELECT * FROM hypothesis_claim_link_391 WHERE hypothesis_id=?", (hypothesis_id,)):
            lbody = {k: link[k] for k in link if k != "record_hash"}
            links_ok = links_ok and str(link.get("record_hash") or "") == _sha(lbody)
        return {"hypothesis_id": hypothesis_id, "valid": str(row.get("record_hash") or "") == _sha(body) and links_ok}

    def status(self) -> dict[str, Any]:
        c = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN status='reviewed_candidate' THEN 1 ELSE 0 END) reviewed FROM investigation_claim_391") or {}
        h = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN status='retain_for_testing' THEN 1 ELSE 0 END) retained FROM investigation_hypothesis_391") or {}
        b = self.db.one("SELECT COUNT(*) total FROM kernel_synthesis_bridge_391") or {}
        s = self.db.one("SELECT COUNT(*) total FROM synthesis_snapshot_391") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "candidate_claim_synthesis": True,
            "counterevidence_preserved": True,
            "hypothesis_proposals": True,
            "investigation_kernel_notebook_bridge": True,
            "legacy_kernel_probability_path_used": False,
            "automatic_truth_acceptance": False,
            "truth_probability": False,
            "automatic_claim_acceptance": False,
            "automatic_evidence_promotion": False,
            "automatic_identity_merge": False,
            "direct_network_fetch": False,
            "claims": int(c.get("total") or 0),
            "reviewed_claims": int(c.get("reviewed") or 0),
            "hypotheses": int(h.get("total") or 0),
            "retained_hypotheses": int(h.get("retained") or 0),
            "kernel_bridges": int(b.get("total") or 0),
            "snapshots": int(s.get("total") or 0),
        }
