from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

BUILD = "394.0"
POLICY_ID = "phase17.investigator-discussion-versioned-revision.v394"
CONFIRM_REVISION_REVIEW = "REVIEW VERSIONED REVISION"
CONFIRM_APPLY_REVISION = "APPLY VERSIONED REVISION"
CONFIRM_KERNEL_ADMISSION = "ADMIT DISCUSSION REVISION TO KERNEL"

_ALLOWED_TURN_TYPES = {
    "argument",
    "counterargument",
    "clarification",
    "hypothesis_comparison",
    "revision_discussion",
    "synthesis",
}
_ALLOWED_REVISION_TARGETS = {"claim", "hypothesis", "reasoning_plan"}
_ALLOWED_REVISION_DISPOSITIONS = {
    "approve_versioned_revision",
    "revise_requested",
    "rejected",
    "deferred",
}
_ALLOWED_PATCH_FIELDS = {
    "claim": {"proposition", "scope_note", "analyst_note"},
    "hypothesis": {"title", "statement", "test_plan", "analyst_note"},
    "reasoning_plan": {"analyst_note", "sequence_note", "rationale_note", "action_order", "action_notes"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _stable_id(prefix: str, value: Any, n: int = 24) -> str:
    return f"{prefix}_{_sha(value)[:n]}"


def _clean_text(value: Any, limit: int = 12000) -> str:
    return " ".join(str(value or "").split())[:limit]


class InvestigatorDiscussionRevision394:
    """Multi-turn discussion and versioned revision workspace for Phase 17.

    Build 394 deliberately stores revisions as new immutable working versions rather
    than overwriting Build-391 claims/hypotheses or Build-392 reasoning plans.
    Evidence-derived support/contradiction metrics are never editable here. Human
    review is required before a revision may be materialized, and materialization
    grants no GO/LIVE/network/evidence-promotion authority.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        dialogue393: Any,
        synthesis391: Any,
        reasoning392: Any,
        kernel112: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.dialogue393 = dialogue393
        self.synthesis391 = synthesis391
        self.reasoning392 = reasoning392
        self.kernel112 = kernel112
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS investigator_discussion_session_394 (
              discussion_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              dialogue_session_id TEXT NOT NULL,
              source_dialogue_hash TEXT NOT NULL,
              state TEXT NOT NULL,
              turn_count INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,dialogue_session_id,source_dialogue_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_investigator_discussion_session_394_case
              ON investigator_discussion_session_394(case_id,updated_at);

            CREATE TABLE IF NOT EXISTS investigator_discussion_turn_394 (
              turn_id TEXT PRIMARY KEY,
              discussion_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              parent_turn_id TEXT NOT NULL DEFAULT '',
              turn_type TEXT NOT NULL,
              speaker_role TEXT NOT NULL,
              prompt_text TEXT NOT NULL,
              response_json TEXT NOT NULL,
              object_refs_json TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(discussion_id,ordinal),
              FOREIGN KEY(discussion_id) REFERENCES investigator_discussion_session_394(discussion_id)
            );
            CREATE INDEX IF NOT EXISTS idx_investigator_discussion_turn_394_discussion
              ON investigator_discussion_turn_394(discussion_id,ordinal);

            CREATE TABLE IF NOT EXISTS hypothesis_comparison_394 (
              comparison_id TEXT PRIMARY KEY,
              discussion_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              hypothesis_ids_json TEXT NOT NULL,
              comparison_json TEXT NOT NULL,
              comparison_state TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(discussion_id) REFERENCES investigator_discussion_session_394(discussion_id)
            );
            CREATE INDEX IF NOT EXISTS idx_hypothesis_comparison_394_case
              ON hypothesis_comparison_394(case_id,created_at);

            CREATE TABLE IF NOT EXISTS discussion_revision_proposal_394 (
              proposal_id TEXT PRIMARY KEY,
              discussion_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              source_turn_id TEXT NOT NULL DEFAULT '',
              source_challenge_proposal_id TEXT NOT NULL DEFAULT '',
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              source_object_hash TEXT NOT NULL,
              base_version_id TEXT NOT NULL DEFAULT '',
              base_payload_hash TEXT NOT NULL,
              patch_json TEXT NOT NULL,
              rationale TEXT NOT NULL,
              status TEXT NOT NULL,
              requires_human_review INTEGER NOT NULL,
              execution_authority INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(discussion_id) REFERENCES investigator_discussion_session_394(discussion_id)
            );
            CREATE INDEX IF NOT EXISTS idx_discussion_revision_proposal_394_case
              ON discussion_revision_proposal_394(case_id,target_type,target_id,status,created_at);

            CREATE TABLE IF NOT EXISTS discussion_revision_review_394 (
              review_id TEXT PRIMARY KEY,
              proposal_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              disposition TEXT NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(proposal_id) REFERENCES discussion_revision_proposal_394(proposal_id)
            );

            CREATE TABLE IF NOT EXISTS versioned_revision_394 (
              version_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              version_number INTEGER NOT NULL,
              parent_version_id TEXT NOT NULL DEFAULT '',
              proposal_id TEXT NOT NULL UNIQUE,
              source_object_hash TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              epistemic_status TEXT NOT NULL,
              execution_authority INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,target_type,target_id,version_number),
              FOREIGN KEY(proposal_id) REFERENCES discussion_revision_proposal_394(proposal_id)
            );
            CREATE INDEX IF NOT EXISTS idx_versioned_revision_394_target
              ON versioned_revision_394(case_id,target_type,target_id,version_number);

            CREATE TABLE IF NOT EXISTS discussion_kernel_bridge_394 (
              bridge_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              version_id TEXT NOT NULL UNIQUE,
              kernel_entry_id TEXT NOT NULL,
              source_version_hash TEXT NOT NULL,
              bridge_state TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(version_id) REFERENCES versioned_revision_394(version_id)
            );
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(
            dict(identity),
            case_id=case_id,
            capability=capability,
            object_type="phase17_investigator_discussion_v394",
            object_id=object_id,
        )

    @staticmethod
    def _dialogue_hash(session: Mapping[str, Any]) -> str:
        return _sha({
            "session_id": session.get("session_id"),
            "workspace_id": session.get("workspace_id"),
            "source_workspace_hash": session.get("source_workspace_hash"),
            "turn_count": session.get("turn_count"),
            "record_hash": session.get("record_hash"),
            "turn_hashes": [str(x.get("record_hash") or "") for x in session.get("turns") or []],
        })

    def _discussion_row(self, case_id: str, discussion_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT * FROM investigator_discussion_session_394 WHERE case_id=? AND discussion_id=?",
            (case_id, discussion_id),
        )
        if not row:
            raise KeyError(discussion_id)
        return dict(row)

    def _turn_row(self, case_id: str, turn_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigator_discussion_turn_394 WHERE case_id=? AND turn_id=?", (case_id, turn_id))
        if not row:
            raise KeyError(turn_id)
        return dict(row)

    def _proposal_row(self, case_id: str, proposal_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM discussion_revision_proposal_394 WHERE case_id=? AND proposal_id=?", (case_id, proposal_id))
        if not row:
            raise KeyError(proposal_id)
        return dict(row)

    def _version_row(self, case_id: str, version_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM versioned_revision_394 WHERE case_id=? AND version_id=?", (case_id, version_id))
        if not row:
            raise KeyError(version_id)
        return dict(row)

    def create_session(self, *, case_id: str, dialogue_session_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", dialogue_session_id)
        verify = self.dialogue393.verify_session(case_id=case_id, session_id=dialogue_session_id)
        if not bool(verify.get("valid")):
            raise ValueError("Build-393 dialogue session integrity verification failed or source workspace is stale")
        source = self.dialogue393.session(case_id=case_id, session_id=dialogue_session_id)
        dhash = self._dialogue_hash(source)
        existing = self.db.one(
            "SELECT discussion_id FROM investigator_discussion_session_394 WHERE case_id=? AND dialogue_session_id=? AND source_dialogue_hash=?",
            (case_id, dialogue_session_id, dhash),
        )
        if existing:
            return self.session(case_id=case_id, discussion_id=str(existing["discussion_id"]), identity=identity)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        body = {
            "discussion_id": _stable_id("discuss394", {"case_id": case_id, "dialogue_session_id": dialogue_session_id, "source_dialogue_hash": dhash}),
            "case_id": case_id,
            "dialogue_session_id": dialogue_session_id,
            "source_dialogue_hash": dhash,
            "state": "active_versioned_discussion",
            "turn_count": 0,
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO investigator_discussion_session_394(discussion_id,case_id,dialogue_session_id,source_dialogue_hash,state,turn_count,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (*body.values(), _sha(body)),
        )
        self.audit.log("discussion_session", "investigator_discussion_session_394", body["discussion_id"], case_id, {
            "dialogue_session_id": dialogue_session_id,
            "truth_determined": False,
            "execution_authority": False,
        })
        return self.session(case_id=case_id, discussion_id=body["discussion_id"], identity=identity)

    def session(self, *, case_id: str, discussion_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", discussion_id)
        row = self._discussion_row(case_id, discussion_id)
        turns: list[dict[str, Any]] = []
        for item in self.db.all("SELECT * FROM investigator_discussion_turn_394 WHERE discussion_id=? ORDER BY ordinal", (discussion_id,)):
            t = dict(item)
            turns.append({**t, "response": dict(_j(t.get("response_json"), {}) or {}), "object_refs": list(_j(t.get("object_refs_json"), []) or [])})
        comparisons = []
        for item in self.db.all("SELECT * FROM hypothesis_comparison_394 WHERE discussion_id=? ORDER BY created_at,comparison_id", (discussion_id,)):
            c = dict(item)
            comparisons.append({**c, "hypothesis_ids": list(_j(c.get("hypothesis_ids_json"), []) or []), "comparison": dict(_j(c.get("comparison_json"), {}) or {})})
        return {
            **row,
            "turns": turns,
            "comparisons": comparisons,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "execution_authority": False,
        }

    def _source_workspace(self, case_id: str, discussion: Mapping[str, Any]) -> dict[str, Any]:
        source = self.dialogue393.session(case_id=case_id, session_id=str(discussion["dialogue_session_id"]))
        return self.reasoning392.workspace(case_id=case_id, workspace_id=str(source["workspace_id"]))

    def discuss(
        self,
        *,
        case_id: str,
        discussion_id: str,
        prompt: str,
        identity: Mapping[str, Any],
        turn_type: str = "argument",
        parent_turn_id: str = "",
        object_refs: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", discussion_id)
        ttype = str(turn_type or "argument").strip().casefold()
        if ttype not in _ALLOWED_TURN_TYPES:
            raise ValueError("unsupported discussion turn type")
        text = _clean_text(prompt, 8000)
        if len(text) < 3:
            raise ValueError("discussion prompt required")
        discussion = self._discussion_row(case_id, discussion_id)
        verify = self.verify_session(case_id=case_id, discussion_id=discussion_id)
        if not bool(verify.get("valid")):
            raise ValueError("discussion source is stale or integrity verification failed")
        if parent_turn_id:
            parent = self._turn_row(case_id, parent_turn_id)
            if str(parent.get("discussion_id")) != discussion_id:
                raise ValueError("parent turn belongs to a different discussion")
        workspace = self._source_workspace(case_id, discussion)
        issues = [dict(x) for x in workspace.get("issues") or []]
        arguments = [dict(x) for x in workspace.get("arguments") or []]
        refs = [dict(x) for x in object_refs][:50]
        if not refs:
            refs = [{"object_type": "workspace", "object_id": str(workspace.get("workspace_id") or "")}]
        response = {
            "turn_type": ttype,
            "discussion_prompt": text,
            "argument_context": [
                {"argument_type": a.get("argument_type"), "statement": a.get("statement"), "object_refs": a.get("object_refs") or []}
                for a in arguments[:12]
            ],
            "counterevidence_context": [
                {"issue_type": i.get("issue_type"), "severity": i.get("severity"), "title": i.get("title"), "rationale": i.get("rationale"), "object_refs": i.get("object_refs") or []}
                for i in issues if str(i.get("issue_type") or "") in {"counterevidence_conflict", "contested_claim", "source_independence_gap", "independent_support_gap", "hypothesis_test_gap"}
            ][:12],
            "discussion_guidance": self._guidance(ttype),
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_upstream_mutation": False,
            "execution_authority": False,
        }
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        ordinal = int(discussion.get("turn_count") or 0) + 1
        body = {
            "turn_id": _stable_id("dturn394", {"discussion_id": discussion_id, "ordinal": ordinal, "prompt": text, "turn_type": ttype, "parent": parent_turn_id}),
            "discussion_id": discussion_id,
            "case_id": case_id,
            "ordinal": ordinal,
            "parent_turn_id": str(parent_turn_id or ""),
            "turn_type": ttype,
            "speaker_role": "investigator_ai_discussion",
            "prompt_text": text,
            "response_json": _canon(response),
            "object_refs_json": _canon(refs),
            "created_by": actor,
            "created_at": now,
        }
        updated = {k: discussion[k] for k in discussion if k != "record_hash"}
        updated.update({"turn_count": ordinal, "updated_at": now})
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO investigator_discussion_turn_394(turn_id,discussion_id,case_id,ordinal,parent_turn_id,turn_type,speaker_role,prompt_text,response_json,object_refs_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*body.values(), _sha(body)),
            )
            self.db.execute(
                "UPDATE investigator_discussion_session_394 SET turn_count=?,updated_at=?,record_hash=? WHERE discussion_id=?",
                (ordinal, now, _sha(updated), discussion_id),
            )
        self.audit.log("discussion_turn", "investigator_discussion_turn_394", body["turn_id"], case_id, {
            "turn_type": ttype,
            "parent_turn_id": parent_turn_id,
            "truth_determined": False,
            "execution_authority": False,
        })
        return self.turn(case_id=case_id, turn_id=body["turn_id"], identity=identity)

    @staticmethod
    def _guidance(turn_type: str) -> list[str]:
        guides = {
            "argument": ["State the claim being defended.", "Identify the evidence and independence groups supporting it.", "Name the strongest known counterevidence."],
            "counterargument": ["Attack the inference rather than the person/source.", "Preserve contradictory observations.", "Identify what evidence would change the assessment."],
            "clarification": ["Separate observation, claim and hypothesis.", "Clarify scope, date and jurisdiction.", "Do not infer absence from no-result observations."],
            "hypothesis_comparison": ["Compare explanatory scope and testability.", "Keep shared supporting claims from being double-counted.", "Prefer discriminating tests over generic additional collection."],
            "revision_discussion": ["Describe the exact proposed text/plan change.", "Preserve immutable evidence-derived metrics.", "Record why the prior version remains historically relevant."],
            "synthesis": ["Summarize agreement and disagreement.", "List unresolved gaps.", "Keep proposed next actions review-only and capability-scoped."],
        }
        return guides[turn_type]

    def turn(self, *, case_id: str, turn_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", turn_id)
        row = self._turn_row(case_id, turn_id)
        return {
            **row,
            "response": dict(_j(row.get("response_json"), {}) or {}),
            "object_refs": list(_j(row.get("object_refs_json"), []) or []),
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
        }

    def compare_hypotheses(
        self,
        *,
        case_id: str,
        discussion_id: str,
        hypothesis_ids: Sequence[str],
        identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, "case.read", discussion_id)
        discussion = self._discussion_row(case_id, discussion_id)
        if not self.verify_session(case_id=case_id, discussion_id=discussion_id).get("valid"):
            raise ValueError("discussion source is stale or invalid")
        ids = list(dict.fromkeys(str(x) for x in hypothesis_ids if str(x)))
        if len(ids) < 2 or len(ids) > 8:
            raise ValueError("compare 2..8 hypotheses")
        workspace = self._source_workspace(case_id, discussion)
        workspace_hyp_ids = {str(x.get("hypothesis_id") or "") for x in (workspace.get("source_snapshot") or {}).get("hypotheses") or []}
        if any(h not in workspace_hyp_ids for h in ids):
            raise ValueError("all hypotheses must belong to the source reasoning workspace")
        rows = [self.synthesis391.hypothesis(case_id=case_id, hypothesis_id=h) for h in ids]
        claim_map = {str(x.get("claim_id") or ""): dict(x) for x in (workspace.get("source_snapshot") or {}).get("claims") or []}
        issues = [dict(x) for x in workspace.get("issues") or []]
        items: list[dict[str, Any]] = []
        for hyp in rows:
            hid = str(hyp["hypothesis_id"])
            links = [dict(x) for x in hyp.get("claim_links") or []]
            support = [x for x in links if str(x.get("relation") or "") in {"supports", "basis", "consistent_with"}]
            test_targets = [x for x in links if str(x.get("relation") or "") == "test_target"]
            contrary = [x for x in links if str(x.get("relation") or "") in {"contradicts", "tension", "counterevidence"}]
            linked_claims = [claim_map.get(str(x.get("claim_id") or ""), {}) for x in links]
            linked_issues = [i for i in issues if any(str(r.get("object_id") or "") == hid for r in i.get("object_refs") or [])]
            items.append({
                "hypothesis_id": hid,
                "title": hyp.get("title"),
                "statement": hyp.get("statement"),
                "test_plan": hyp.get("test_plan"),
                "status": hyp.get("status"),
                "epistemic_status": "hypothesis_not_fact",
                "linked_claims": [{"claim_id": c.get("claim_id"), "proposition": c.get("proposition"), "analyst_disposition": c.get("analyst_disposition")} for c in linked_claims if c],
                "support_link_count": len(support),
                "test_target_count": len(test_targets),
                "counter_relation_count": len(contrary),
                "open_issue_types": sorted({str(i.get("issue_type") or "") for i in linked_issues if i.get("issue_type")}),
                "probability_assigned": False,
            })
        shared_claims: dict[str, list[str]] = {}
        for item, hyp in zip(items, rows):
            for link in hyp.get("claim_links") or []:
                cid = str(link.get("claim_id") or "")
                if cid:
                    shared_claims.setdefault(cid, []).append(str(item["hypothesis_id"]))
        comparison = {
            "hypotheses": items,
            "shared_claims": [{"claim_id": cid, "hypothesis_ids": hs} for cid, hs in sorted(shared_claims.items()) if len(hs) > 1],
            "comparison_guidance": [
                "Shared claims are not independent evidence for choosing between hypotheses.",
                "Prefer tests whose possible outcomes discriminate between competing explanations.",
                "Retain counterevidence and unresolved source-independence issues explicitly.",
            ],
            "winner_selected": False,
            "truth_determined": False,
            "probability_assigned": False,
        }
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        body = {
            "comparison_id": _stable_id("hcmp394", {"discussion_id": discussion_id, "hypothesis_ids": ids, "comparison": comparison}),
            "discussion_id": discussion_id,
            "case_id": case_id,
            "hypothesis_ids_json": _canon(ids),
            "comparison_json": _canon(comparison),
            "comparison_state": "side_by_side_review_not_ranking",
            "created_by": actor,
            "created_at": now,
        }
        existing = self.db.one("SELECT * FROM hypothesis_comparison_394 WHERE comparison_id=?", (body["comparison_id"],))
        if not existing:
            self.db.execute(
                "INSERT INTO hypothesis_comparison_394(comparison_id,discussion_id,case_id,hypothesis_ids_json,comparison_json,comparison_state,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (*body.values(), _sha(body)),
            )
        return {**body, "record_hash": _sha(body), "hypothesis_ids": ids, "comparison": comparison}

    def _source_object(self, case_id: str, target_type: str, target_id: str) -> tuple[dict[str, Any], str]:
        if target_type == "claim":
            obj = self.synthesis391.claim(case_id=case_id, claim_id=target_id)
            source_hash = str(obj.get("record_hash") or "")
            payload = {
                "target_type": "claim",
                "target_id": target_id,
                "proposition": obj.get("proposition"),
                "epistemic_status": obj.get("epistemic_status"),
                "structural_state": obj.get("structural_state"),
                "support_groups": obj.get("support_groups"),
                "contradiction_groups": obj.get("contradiction_groups"),
                "context_groups": obj.get("context_groups"),
                "unresolved_observations": obj.get("unresolved_observations"),
                "analyst_disposition": obj.get("analyst_disposition"),
                "scope_note": "",
                "analyst_note": "",
            }
        elif target_type == "hypothesis":
            obj = self.synthesis391.hypothesis(case_id=case_id, hypothesis_id=target_id)
            source_hash = str(obj.get("record_hash") or "")
            payload = {
                "target_type": "hypothesis",
                "target_id": target_id,
                "title": obj.get("title"),
                "statement": obj.get("statement"),
                "test_plan": obj.get("test_plan"),
                "epistemic_status": "hypothesis_not_fact",
                "status": obj.get("status"),
                "claim_links": [
                    {"claim_id": x.get("claim_id"), "relation": x.get("relation"), "claim_record_hash": x.get("claim_record_hash")}
                    for x in obj.get("claim_links") or []
                ],
                "analyst_note": "",
            }
        elif target_type == "reasoning_plan":
            obj = self.reasoning392.plan(case_id=case_id, plan_id=target_id)
            source_hash = str(obj.get("plan_hash") or obj.get("record_hash") or "")
            payload = {
                "target_type": "reasoning_plan",
                "target_id": target_id,
                "workspace_id": obj.get("workspace_id"),
                "plan_status": obj.get("plan_status"),
                "requires_go": bool(obj.get("requires_go")),
                "execution_authority": False,
                "actions": [
                    {
                        "action_id": x.get("action_id"), "ordinal": x.get("ordinal"), "action_type": x.get("action_type"),
                        "priority": x.get("priority"), "title": x.get("title"), "rationale": x.get("rationale"),
                        "requires_go": bool(x.get("requires_go")), "execution_authority": False,
                    }
                    for x in obj.get("actions") or []
                ],
                "analyst_note": "",
                "sequence_note": "",
                "rationale_note": "",
                "action_notes": {},
            }
        else:
            raise ValueError("target_type must be claim, hypothesis or reasoning_plan")
        if not source_hash:
            raise ValueError("source object lacks integrity hash")
        return payload, source_hash

    def _latest_version(self, case_id: str, target_type: str, target_id: str) -> dict[str, Any] | None:
        row = self.db.one(
            "SELECT * FROM versioned_revision_394 WHERE case_id=? AND target_type=? AND target_id=? ORDER BY version_number DESC LIMIT 1",
            (case_id, target_type, target_id),
        )
        if not row:
            return None
        out = dict(row)
        out["payload"] = dict(_j(out.get("payload_json"), {}) or {})
        return out

    def _validate_patch(self, target_type: str, patch: Mapping[str, Any], base_payload: Mapping[str, Any]) -> dict[str, Any]:
        allowed = _ALLOWED_PATCH_FIELDS[target_type]
        unknown = set(patch) - allowed
        if unknown:
            raise ValueError("unsupported or immutable revision fields: " + ",".join(sorted(unknown)))
        if not patch:
            raise ValueError("non-empty revision patch required")
        clean: dict[str, Any] = {}
        for key, value in patch.items():
            if key in {"proposition", "title", "statement", "test_plan", "scope_note", "analyst_note", "sequence_note", "rationale_note"}:
                limit = 12000 if key in {"statement", "test_plan"} else 4000
                text = _clean_text(value, limit)
                if key in {"proposition", "title", "statement", "test_plan"} and len(text) < 3:
                    raise ValueError(f"{key} cannot be empty")
                clean[key] = text
            elif key == "action_order":
                if target_type != "reasoning_plan":
                    raise ValueError("action_order is valid only for reasoning plans")
                ids = [str(x) for x in value] if isinstance(value, (list, tuple)) else []
                existing = [str(x.get("action_id") or "") for x in base_payload.get("actions") or []]
                if sorted(ids) != sorted(existing) or len(ids) != len(set(ids)):
                    raise ValueError("action_order must contain each existing action exactly once")
                clean[key] = ids
            elif key == "action_notes":
                if target_type != "reasoning_plan" or not isinstance(value, Mapping):
                    raise ValueError("action_notes must be a mapping for reasoning plans")
                existing = {str(x.get("action_id") or "") for x in base_payload.get("actions") or []}
                if any(str(k) not in existing for k in value):
                    raise ValueError("action_notes may reference existing actions only")
                clean[key] = {str(k): _clean_text(v, 2000) for k, v in value.items()}
        return clean

    def create_revision_proposal(
        self,
        *,
        case_id: str,
        discussion_id: str,
        target_type: str,
        target_id: str,
        patch: Mapping[str, Any],
        rationale: str,
        identity: Mapping[str, Any],
        source_turn_id: str = "",
        source_challenge_proposal_id: str = "",
    ) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", target_id)
        ttype = str(target_type or "").strip().casefold()
        if ttype not in _ALLOWED_REVISION_TARGETS:
            raise ValueError("unsupported revision target type")
        reason = _clean_text(rationale, 4000)
        if len(reason) < 12:
            raise ValueError("substantive revision rationale required")
        if not self.verify_session(case_id=case_id, discussion_id=discussion_id).get("valid"):
            raise ValueError("discussion source is stale or invalid")
        if source_turn_id:
            turn = self._turn_row(case_id, source_turn_id)
            if str(turn.get("discussion_id")) != discussion_id:
                raise ValueError("source turn belongs to a different discussion")
        if source_challenge_proposal_id:
            pverify = self.dialogue393.verify_proposal(case_id=case_id, proposal_id=source_challenge_proposal_id)
            if not bool(pverify.get("valid")):
                raise ValueError("source Build-393 proposal integrity failed")
            p393 = self.dialogue393.proposal(case_id=case_id, proposal_id=source_challenge_proposal_id)
            if str(p393.get("status") or "") != "reviewed_for_manual_revision":
                raise PermissionError("Build-393 proposal must be reviewed for manual revision")
            ptype = str(p393.get("target_type") or "")
            pid = str(p393.get("target_id") or "")
            if ptype in _ALLOWED_REVISION_TARGETS and (ptype != ttype or pid != target_id):
                raise ValueError("revision target does not match reviewed Build-393 proposal")
        elif not source_turn_id:
            raise ValueError("revision proposal requires a discussion turn or reviewed Build-393 challenge proposal")

        source_payload, source_hash = self._source_object(case_id, ttype, target_id)
        latest = self._latest_version(case_id, ttype, target_id)
        base_payload = dict(latest["payload"] if latest else source_payload)
        base_version_id = str(latest.get("version_id") or "") if latest else ""
        clean_patch = self._validate_patch(ttype, dict(patch), base_payload)
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        body = {
            "proposal_id": _stable_id("revprop394", {"discussion_id": discussion_id, "target_type": ttype, "target_id": target_id, "base_version_id": base_version_id, "patch": clean_patch, "rationale": reason}),
            "discussion_id": discussion_id,
            "case_id": case_id,
            "source_turn_id": str(source_turn_id or ""),
            "source_challenge_proposal_id": str(source_challenge_proposal_id or ""),
            "target_type": ttype,
            "target_id": target_id,
            "source_object_hash": source_hash,
            "base_version_id": base_version_id,
            "base_payload_hash": _sha(base_payload),
            "patch_json": _canon(clean_patch),
            "rationale": reason,
            "status": "proposal_needs_review",
            "requires_human_review": 1,
            "execution_authority": 0,
            "created_by": actor,
            "created_at": now,
        }
        existing = self.db.one("SELECT proposal_id FROM discussion_revision_proposal_394 WHERE proposal_id=?", (body["proposal_id"],))
        if not existing:
            self.db.execute(
                "INSERT INTO discussion_revision_proposal_394(proposal_id,discussion_id,case_id,source_turn_id,source_challenge_proposal_id,target_type,target_id,source_object_hash,base_version_id,base_payload_hash,patch_json,rationale,status,requires_human_review,execution_authority,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*body.values(), _sha(body)),
            )
            self.audit.log("revision_proposal", "discussion_revision_proposal_394", body["proposal_id"], case_id, {
                "target_type": ttype, "target_id": target_id, "versioned_only": True, "execution_authority": False,
            })
        return self.revision_proposal(case_id=case_id, proposal_id=body["proposal_id"], identity=identity)

    def revision_proposal(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", proposal_id)
        row = self._proposal_row(case_id, proposal_id)
        review = self.db.one("SELECT * FROM discussion_revision_review_394 WHERE proposal_id=?", (proposal_id,))
        version = self.db.one("SELECT version_id FROM versioned_revision_394 WHERE proposal_id=?", (proposal_id,))
        return {
            **row,
            "patch": dict(_j(row.get("patch_json"), {}) or {}),
            "requires_human_review": bool(row.get("requires_human_review")),
            "execution_authority": False,
            "review": dict(review) if review else None,
            "applied_version_id": str(version.get("version_id") or "") if version else "",
            "automatic_upstream_mutation": False,
        }

    def review_revision(
        self,
        *,
        case_id: str,
        proposal_id: str,
        identity: Mapping[str, Any],
        disposition: str,
        rationale: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_REVISION_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_REVISION_REVIEW} required")
        self._authorize(identity, case_id, "dossier.write", proposal_id)
        disp = str(disposition or "").strip().casefold()
        if disp not in _ALLOWED_REVISION_DISPOSITIONS:
            raise ValueError("unsupported revision disposition")
        reason = _clean_text(rationale, 4000)
        if len(reason) < 12:
            raise ValueError("substantive revision review rationale required")
        row = self._proposal_row(case_id, proposal_id)
        if str(row.get("status") or "") != "proposal_needs_review":
            raise PermissionError("revision proposal already reviewed or not reviewable")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        review = {
            "review_id": _stable_id("revreview394", {"proposal_id": proposal_id, "disposition": disp, "reviewer": actor}),
            "proposal_id": proposal_id,
            "case_id": case_id,
            "disposition": disp,
            "rationale": reason,
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        status = "reviewed_for_versioning" if disp == "approve_versioned_revision" else disp
        updated = {k: row[k] for k in row if k != "record_hash"}
        updated["status"] = status
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO discussion_revision_review_394(review_id,proposal_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",
                (*review.values(), _sha(review)),
            )
            self.db.execute("UPDATE discussion_revision_proposal_394 SET status=?,record_hash=? WHERE proposal_id=?", (status, _sha(updated), proposal_id))
        self.audit.log("revision_review", "discussion_revision_proposal_394", proposal_id, case_id, {"disposition": disp, "execution_authority": False})
        return self.revision_proposal(case_id=case_id, proposal_id=proposal_id, identity=identity)

    def _materialize_payload(self, target_type: str, base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
        out = json.loads(_canon(base))
        for key, value in patch.items():
            if key == "action_order":
                by_id = {str(x.get("action_id") or ""): dict(x) for x in out.get("actions") or []}
                out["actions"] = [{**by_id[aid], "ordinal": i} for i, aid in enumerate(value, start=1)]
            elif key == "action_notes":
                notes = dict(out.get("action_notes") or {})
                notes.update(dict(value))
                out["action_notes"] = notes
            else:
                out[key] = value
        out["revision_metadata"] = {
            "versioned_working_copy": True,
            "source_target_type": target_type,
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
        }
        if target_type == "reasoning_plan":
            out["execution_authority"] = False
            for action in out.get("actions") or []:
                action["execution_authority"] = False
        return out

    def apply_revision(self, *, case_id: str, proposal_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_APPLY_REVISION:
            raise PermissionError(f"explicit confirmation {CONFIRM_APPLY_REVISION} required")
        self._authorize(identity, case_id, "dossier.write", proposal_id)
        proposal = self._proposal_row(case_id, proposal_id)
        if str(proposal.get("status") or "") != "reviewed_for_versioning":
            raise PermissionError("only approved reviewed revisions may be materialized")
        existing = self.db.one("SELECT version_id FROM versioned_revision_394 WHERE proposal_id=?", (proposal_id,))
        if existing:
            return self.version(case_id=case_id, version_id=str(existing["version_id"]), identity=identity)
        target_type = str(proposal["target_type"])
        target_id = str(proposal["target_id"])
        source_payload, current_source_hash = self._source_object(case_id, target_type, target_id)
        if current_source_hash != str(proposal["source_object_hash"]):
            raise PermissionError("source object changed after revision proposal; create a new proposal")
        latest = self._latest_version(case_id, target_type, target_id)
        expected_base_version = str(proposal.get("base_version_id") or "")
        observed_base_version = str(latest.get("version_id") or "") if latest else ""
        if expected_base_version != observed_base_version:
            raise PermissionError("version lineage changed after revision proposal; proposal is stale")
        base_payload = dict(latest["payload"] if latest else source_payload)
        if _sha(base_payload) != str(proposal["base_payload_hash"]):
            raise PermissionError("revision base payload hash mismatch")
        patch = dict(_j(proposal.get("patch_json"), {}) or {})
        clean_patch = self._validate_patch(target_type, patch, base_payload)
        payload = self._materialize_payload(target_type, base_payload, clean_patch)
        version_number = int(latest.get("version_number") or 0) + 1 if latest else 1
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        payload_hash = _sha(payload)
        body = {
            "version_id": _stable_id("version394", {"case_id": case_id, "target_type": target_type, "target_id": target_id, "version_number": version_number, "parent": observed_base_version, "payload_hash": payload_hash}),
            "case_id": case_id,
            "target_type": target_type,
            "target_id": target_id,
            "version_number": version_number,
            "parent_version_id": observed_base_version,
            "proposal_id": proposal_id,
            "source_object_hash": current_source_hash,
            "payload_json": _canon(payload),
            "payload_hash": payload_hash,
            "epistemic_status": "versioned_investigation_working_copy_not_fact",
            "execution_authority": 0,
            "created_by": actor,
            "created_at": now,
        }
        self.db.execute(
            "INSERT INTO versioned_revision_394(version_id,case_id,target_type,target_id,version_number,parent_version_id,proposal_id,source_object_hash,payload_json,payload_hash,epistemic_status,execution_authority,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*body.values(), _sha(body)),
        )
        self.audit.log("versioned_revision", "versioned_revision_394", body["version_id"], case_id, {
            "target_type": target_type, "target_id": target_id, "version_number": version_number,
            "upstream_overwritten": False, "execution_authority": False,
        })
        return self.version(case_id=case_id, version_id=body["version_id"], identity=identity)

    def version(self, *, case_id: str, version_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", version_id)
        row = self._version_row(case_id, version_id)
        bridge = self.db.one("SELECT * FROM discussion_kernel_bridge_394 WHERE version_id=?", (version_id,))
        return {
            **row,
            "payload": dict(_j(row.get("payload_json"), {}) or {}),
            "execution_authority": False,
            "upstream_overwritten": False,
            "truth_determined": False,
            "probability_assigned": False,
            "kernel_bridge": dict(bridge) if bridge else None,
        }

    def latest_version(self, *, case_id: str, target_type: str, target_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        row = self._latest_version(case_id, target_type, target_id)
        if not row:
            return None
        return self.version(case_id=case_id, version_id=str(row["version_id"]), identity=identity)

    def admit_version_to_kernel(self, *, case_id: str, version_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_KERNEL_ADMISSION:
            raise PermissionError(f"explicit confirmation {CONFIRM_KERNEL_ADMISSION} required")
        self._authorize(identity, case_id, "dossier.write", version_id)
        version = self.version(case_id=case_id, version_id=version_id)
        existing = self.db.one("SELECT * FROM discussion_kernel_bridge_394 WHERE version_id=?", (version_id,))
        if existing:
            return dict(existing) | {"execution_authority": False}
        actor = str(identity.get("username") or self.actor)[:120]
        payload = version["payload"]
        title = f"Phase-17 versioned {version['target_type']} working copy v{version['version_number']}"
        body_text = _canon({
            "epistemic_status": version["epistemic_status"],
            "version_id": version_id,
            "target_type": version["target_type"],
            "target_id": version["target_id"],
            "version_number": version["version_number"],
            "payload": payload,
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
        })
        kernel_entry_id = self.kernel112.note(case_id, actor, "phase17_versioned_revision", title, body_text, [str(version["target_id"]), version_id])
        now = _now()
        bridge = {
            "bridge_id": _stable_id("kbridge394", {"case_id": case_id, "version_id": version_id, "kernel_entry_id": kernel_entry_id}),
            "case_id": case_id,
            "version_id": version_id,
            "kernel_entry_id": kernel_entry_id,
            "source_version_hash": str(version.get("record_hash") or ""),
            "bridge_state": "kernel_notebook_versioned_working_copy",
            "created_by": actor,
            "created_at": now,
        }
        self.db.execute(
            "INSERT INTO discussion_kernel_bridge_394(bridge_id,case_id,version_id,kernel_entry_id,source_version_hash,bridge_state,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
            (*bridge.values(), _sha(bridge)),
        )
        self.audit.log("bridge", "discussion_kernel_bridge_394", bridge["bridge_id"], case_id, {"version_id": version_id, "execution_authority": False})
        return {**bridge, "record_hash": _sha(bridge), "execution_authority": False}

    def ai_discussion_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        row = self.db.one("SELECT discussion_id FROM investigator_discussion_session_394 WHERE case_id=? ORDER BY updated_at DESC,discussion_id DESC LIMIT 1", (case_id,))
        latest = self.session(case_id=case_id, discussion_id=str(row["discussion_id"])) if row else None
        versions = []
        for v in self.db.all("SELECT version_id,target_type,target_id,version_number,epistemic_status,created_at,record_hash FROM versioned_revision_394 WHERE case_id=? ORDER BY created_at DESC,version_id DESC LIMIT 100", (case_id,)):
            versions.append(dict(v))
        return {
            "case_id": case_id,
            "build": BUILD,
            "latest_discussion": latest,
            "versioned_working_copies": versions,
            "multi_turn_discussion": True,
            "hypothesis_side_by_side_comparison": True,
            "versioned_revision_lineage": True,
            "upstream_overwrite": False,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "automatic_evidence_promotion": False,
            "execution_authority": False,
            "network_requests_created": 0,
        }

    def verify_session(self, *, case_id: str, discussion_id: str) -> dict[str, Any]:
        row = self._discussion_row(case_id, discussion_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        dverify = self.dialogue393.verify_session(case_id=case_id, session_id=str(row["dialogue_session_id"]))
        dialogue = self.dialogue393.session(case_id=case_id, session_id=str(row["dialogue_session_id"]))
        binding = self._dialogue_hash(dialogue) == str(row.get("source_dialogue_hash") or "")
        return {
            "discussion_id": discussion_id,
            "row_hash_valid": row_valid,
            "source_dialogue_valid": bool(dverify.get("valid")),
            "source_dialogue_binding_valid": binding,
            "stale": not binding,
            "valid": row_valid and bool(dverify.get("valid")) and binding,
        }

    def verify_turn(self, *, case_id: str, turn_id: str) -> dict[str, Any]:
        row = self._turn_row(case_id, turn_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        session = self.verify_session(case_id=case_id, discussion_id=str(row["discussion_id"]))
        valid = str(row.get("record_hash") or "") == _sha(body) and bool(session.get("valid"))
        return {"turn_id": turn_id, "valid": valid, "session_valid": bool(session.get("valid"))}

    def verify_revision_proposal(self, *, case_id: str, proposal_id: str) -> dict[str, Any]:
        row = self._proposal_row(case_id, proposal_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        review = self.db.one("SELECT * FROM discussion_revision_review_394 WHERE proposal_id=?", (proposal_id,))
        review_valid = True
        if review:
            rbody = {k: review[k] for k in review if k != "record_hash"}
            review_valid = str(review.get("record_hash") or "") == _sha(rbody)
        return {"proposal_id": proposal_id, "row_hash_valid": str(row.get("record_hash") or "") == _sha(body), "review_hash_valid": review_valid, "valid": str(row.get("record_hash") or "") == _sha(body) and review_valid}

    def verify_version(self, *, case_id: str, version_id: str) -> dict[str, Any]:
        row = self._version_row(case_id, version_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        payload = dict(_j(row.get("payload_json"), {}) or {})
        payload_valid = str(row.get("payload_hash") or "") == _sha(payload)
        return {"version_id": version_id, "row_hash_valid": str(row.get("record_hash") or "") == _sha(body), "payload_hash_valid": payload_valid, "valid": str(row.get("record_hash") or "") == _sha(body) and payload_valid}

    def status(self) -> dict[str, Any]:
        s = self.db.one("SELECT COUNT(*) total FROM investigator_discussion_session_394") or {}
        t = self.db.one("SELECT COUNT(*) total FROM investigator_discussion_turn_394") or {}
        c = self.db.one("SELECT COUNT(*) total FROM hypothesis_comparison_394") or {}
        p = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN status='reviewed_for_versioning' THEN 1 ELSE 0 END) reviewed FROM discussion_revision_proposal_394") or {}
        v = self.db.one("SELECT COUNT(*) total FROM versioned_revision_394") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "multi_turn_discussion": True,
            "argument_counterargument_chains": True,
            "hypothesis_side_by_side_comparison": True,
            "versioned_revision_proposals": True,
            "human_revision_review_required": True,
            "append_only_revision_lineage": True,
            "immutable_upstream_objects": True,
            "evidence_derived_metrics_editable": False,
            "kernel_notebook_version_bridge": True,
            "truth_probability": False,
            "automatic_truth_acceptance": False,
            "automatic_upstream_mutation": False,
            "automatic_claim_overwrite": False,
            "automatic_hypothesis_overwrite": False,
            "automatic_plan_overwrite": False,
            "automatic_evidence_promotion": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "execution_authority": False,
            "direct_network_fetch": False,
            "automatic_identity_merge": False,
            "sessions": int(s.get("total") or 0),
            "turns": int(t.get("total") or 0),
            "comparisons": int(c.get("total") or 0),
            "revision_proposals": int(p.get("total") or 0),
            "revision_proposals_reviewed": int(p.get("reviewed") or 0),
            "versioned_revisions": int(v.get("total") or 0),
        }
