from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

BUILD = "392.0"
POLICY_ID = "phase17.case-reasoning-workspace.v392"
CONFIRM_PLAN_REVIEW = "REVIEW REASONING PLAN"
CONFIRM_KERNEL_ADMISSION = "ADMIT REASONING PLAN TO KERNEL"

_ALLOWED_PLAN_DISPOSITIONS = {
    "approve_for_investigator_review",
    "revise_requested",
    "rejected",
}

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


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


def _stable_id(prefix: str, value: Any, n: int = 24) -> str:
    return f"{prefix}_{_sha(value)[:n]}"


class CaseReasoningWorkspace392:
    """Deterministic case reasoning workspace over Builds 382/384/388/390/391.

    The workspace is an analytical projection, not a truth engine. It preserves the
    distinctions observation -> corroboration structure -> candidate claim -> hypothesis.
    It can propose a next-investigation plan, but it never grants external authority,
    issues GO tokens, dispatches jobs, promotes evidence, merges identities, or assigns
    truth probability/confidence.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        synthesis391: Any,
        runtime384: Any,
        waves388: Any,
        kernel112: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.synthesis391 = synthesis391
        self.runtime384 = runtime384
        self.waves388 = waves388
        self.kernel112 = kernel112
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS case_reasoning_workspace_392 (
              workspace_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              source_snapshot_hash TEXT NOT NULL,
              coverage_snapshot_hash TEXT NOT NULL,
              source_snapshot_json TEXT NOT NULL,
              coverage_snapshot_json TEXT NOT NULL,
              reasoning_state TEXT NOT NULL,
              issue_count INTEGER NOT NULL,
              argument_count INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,source_snapshot_hash,coverage_snapshot_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_case_reasoning_workspace_392_case
              ON case_reasoning_workspace_392(case_id,created_at);

            CREATE TABLE IF NOT EXISTS reasoning_issue_392 (
              issue_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              issue_type TEXT NOT NULL,
              severity TEXT NOT NULL,
              epistemic_layer TEXT NOT NULL,
              title TEXT NOT NULL,
              rationale TEXT NOT NULL,
              object_refs_json TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(workspace_id,issue_id),
              FOREIGN KEY(workspace_id) REFERENCES case_reasoning_workspace_392(workspace_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_issue_392_workspace
              ON reasoning_issue_392(workspace_id,severity,issue_type);

            CREATE TABLE IF NOT EXISTS reasoning_argument_392 (
              argument_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              from_type TEXT NOT NULL,
              from_id TEXT NOT NULL,
              to_type TEXT NOT NULL,
              to_id TEXT NOT NULL,
              relation TEXT NOT NULL,
              independence_group TEXT NOT NULL,
              source_record_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(workspace_id,from_type,from_id,to_type,to_id,relation),
              FOREIGN KEY(workspace_id) REFERENCES case_reasoning_workspace_392(workspace_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_argument_392_workspace
              ON reasoning_argument_392(workspace_id,to_type,to_id,relation);

            CREATE TABLE IF NOT EXISTS reasoning_plan_392 (
              plan_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              workspace_hash TEXT NOT NULL,
              plan_status TEXT NOT NULL,
              analyst_disposition TEXT NOT NULL DEFAULT '',
              action_count INTEGER NOT NULL,
              external_action_count INTEGER NOT NULL,
              requires_go INTEGER NOT NULL,
              execution_authority INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              plan_hash TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(workspace_id) REFERENCES case_reasoning_workspace_392(workspace_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_plan_392_case
              ON reasoning_plan_392(case_id,created_at);

            CREATE TABLE IF NOT EXISTS reasoning_plan_action_392 (
              action_id TEXT PRIMARY KEY,
              plan_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              action_type TEXT NOT NULL,
              priority TEXT NOT NULL,
              title TEXT NOT NULL,
              rationale TEXT NOT NULL,
              object_refs_json TEXT NOT NULL,
              requires_external_execution INTEGER NOT NULL,
              requires_go INTEGER NOT NULL,
              execution_authority INTEGER NOT NULL,
              source_issue_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(plan_id,ordinal),
              FOREIGN KEY(plan_id) REFERENCES reasoning_plan_392(plan_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reasoning_plan_action_392_plan
              ON reasoning_plan_action_392(plan_id,ordinal);

            CREATE TABLE IF NOT EXISTS reasoning_plan_review_392 (
              review_id TEXT PRIMARY KEY,
              plan_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              disposition TEXT NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(plan_id) REFERENCES reasoning_plan_392(plan_id)
            );

            CREATE TABLE IF NOT EXISTS reasoning_kernel_bridge_392 (
              bridge_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              plan_id TEXT NOT NULL UNIQUE,
              kernel_entry_id TEXT NOT NULL,
              bridge_state TEXT NOT NULL,
              source_plan_hash TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(plan_id) REFERENCES reasoning_plan_392(plan_id)
            );
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(
            dict(identity),
            case_id=case_id,
            capability=capability,
            object_type="phase17_case_reasoning_v392",
            object_id=object_id,
        )

    def _source_snapshot(self, case_id: str) -> dict[str, Any]:
        feed = self.synthesis391.ai_synthesis_feed(case_id=case_id)
        claims = []
        for claim in feed.get("claims") or []:
            cid = str(claim.get("claim_id") or "")
            verify = self.synthesis391.verify_claim(case_id=case_id, claim_id=cid)
            claims.append({
                "claim_id": cid,
                "record_hash": str(claim.get("record_hash") or ""),
                "valid": bool(verify.get("valid")),
                "status": str(claim.get("status") or ""),
                "analyst_disposition": str(claim.get("analyst_disposition") or ""),
                "structural_state": str(claim.get("structural_state") or ""),
                "support_groups": int(claim.get("support_groups") or 0),
                "contradiction_groups": int(claim.get("contradiction_groups") or 0),
                "unresolved_observations": int(claim.get("unresolved_observations") or 0),
                "proposition": str(claim.get("proposition") or ""),
                "candidate_links": [
                    {
                        "candidate_id": str(x.get("candidate_id") or ""),
                        "stance": str(x.get("stance") or "context"),
                        "independence_group": str(x.get("independence_group") or "unresolved"),
                        "counted_as_independent": bool(x.get("counted_as_independent")),
                        "record_hash": str(x.get("record_hash") or ""),
                    }
                    for x in (claim.get("candidate_links") or [])
                ],
            })
        hypotheses = []
        for hyp in feed.get("hypotheses") or []:
            hid = str(hyp.get("hypothesis_id") or "")
            verify = self.synthesis391.verify_hypothesis(case_id=case_id, hypothesis_id=hid)
            links = [dict(r) for r in self.db.all(
                "SELECT claim_id,relation,record_hash FROM hypothesis_claim_link_391 WHERE hypothesis_id=? ORDER BY created_at,link_id",
                (hid,),
            )]
            hypotheses.append({
                "hypothesis_id": hid,
                "record_hash": str(hyp.get("record_hash") or ""),
                "valid": bool(verify.get("valid")),
                "status": str(hyp.get("status") or ""),
                "title": str(hyp.get("title") or ""),
                "statement": str(hyp.get("statement") or ""),
                "test_plan": str(hyp.get("test_plan") or ""),
                "claim_links": links,
            })
        return {
            "build": BUILD,
            "case_id": case_id,
            "claims": claims,
            "hypotheses": hypotheses,
            "counterevidence": list(feed.get("counterevidence") or []),
            "open_questions": list(feed.get("open_questions") or []),
            "epistemic_contract": dict(feed.get("epistemic_contract") or {}),
            "truth_determined": False,
            "probability_assigned": False,
        }

    def _coverage_snapshot(self, case_id: str) -> dict[str, Any]:
        base = self.runtime384.repository.coverage_report(case_id)
        gaps = [
            {"gap_type": str(g.gap_type), "subject": str(g.key), "detail": str(g.detail), "origin": "coverage_382"}
            for g in base.gaps
        ]
        latest = self.db.one(
            "SELECT session_id,wave_plan_id,current_wave,state,decision,updated_at FROM research_wave_session_388 WHERE case_id=? ORDER BY updated_at DESC,session_id DESC LIMIT 1",
            (case_id,),
        )
        wave_plan_id = str((latest or {}).get("wave_plan_id") or "")
        if wave_plan_id:
            for row in self.db.all("SELECT ordinal,gap_json FROM wave_gap_384 WHERE wave_plan_id=? ORDER BY ordinal", (wave_plan_id,)):
                gap = dict(_j(row.get("gap_json"), {}) or {})
                gaps.append({
                    "gap_type": str(gap.get("gap_type") or "planning_gap"),
                    "subject": str(gap.get("subject") or gap.get("source_class") or ""),
                    "detail": str(gap.get("detail") or gap.get("rationale") or ""),
                    "origin": "wave_plan_384",
                })
        # Deduplicate only exact same analytical gap; preserve distinct origins otherwise.
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for gap in gaps:
            key = _sha(gap)
            if key not in seen:
                seen.add(key)
                unique.append(gap)
        return {
            "case_id": case_id,
            "registry_source_count": int(base.registry_source_count),
            "observed_source_count": int(base.observed_source_count),
            "successful_or_partial_count": int(base.successful_or_partial_count),
            "stale_count": int(base.stale_count),
            "failed_or_blocked_count": int(base.failed_or_blocked_count),
            "latest_wave_session": dict(latest) if latest else None,
            "gaps": unique,
            "no_result_is_nonexistence": bool(base.no_result_is_nonexistence),
        }

    @staticmethod
    def _issue(
        workspace_id: str,
        case_id: str,
        issue_type: str,
        severity: str,
        epistemic_layer: str,
        title: str,
        rationale: str,
        refs: Sequence[Mapping[str, Any]],
        created_at: str,
    ) -> dict[str, Any]:
        semantic = {
            "workspace_id": workspace_id,
            "case_id": case_id,
            "issue_type": issue_type,
            "severity": severity,
            "epistemic_layer": epistemic_layer,
            "title": title,
            "rationale": rationale,
            "object_refs": [dict(r) for r in refs],
        }
        return {
            "issue_id": _stable_id("issue392", semantic),
            "workspace_id": workspace_id,
            "case_id": case_id,
            "issue_type": issue_type,
            "severity": severity,
            "epistemic_layer": epistemic_layer,
            "title": title[:500],
            "rationale": rationale[:4000],
            "object_refs_json": _canon(semantic["object_refs"]),
            "status": "open",
            "created_at": created_at,
        }

    @staticmethod
    def _argument(
        workspace_id: str,
        case_id: str,
        *,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        relation: str,
        independence_group: str,
        source_record_hash: str,
        created_at: str,
    ) -> dict[str, Any]:
        semantic = {
            "workspace_id": workspace_id,
            "from_type": from_type,
            "from_id": from_id,
            "to_type": to_type,
            "to_id": to_id,
            "relation": relation,
            "independence_group": independence_group,
            "source_record_hash": source_record_hash,
        }
        return {
            "argument_id": _stable_id("arg392", semantic),
            "workspace_id": workspace_id,
            "case_id": case_id,
            "from_type": from_type,
            "from_id": from_id,
            "to_type": to_type,
            "to_id": to_id,
            "relation": relation,
            "independence_group": independence_group,
            "source_record_hash": source_record_hash,
            "created_at": created_at,
        }

    def _derive(self, workspace_id: str, case_id: str, source: Mapping[str, Any], coverage: Mapping[str, Any], created_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        issues: list[dict[str, Any]] = []
        arguments: list[dict[str, Any]] = []
        for claim in source.get("claims") or []:
            cid = str(claim.get("claim_id") or "")
            refs = [{"object_type": "claim", "object_id": cid}]
            if not bool(claim.get("valid")):
                issues.append(self._issue(workspace_id, case_id, "integrity_review_required", "critical", "claim", "Claim integrity review required", "The stored Build-391 claim or one of its linked records failed integrity verification. Analytical use must stop until reviewed.", refs, created_at))
                continue
            for link in claim.get("candidate_links") or []:
                arguments.append(self._argument(
                    workspace_id, case_id,
                    from_type="evidence_candidate", from_id=str(link.get("candidate_id") or ""),
                    to_type="claim", to_id=cid, relation=str(link.get("stance") or "context"),
                    independence_group=str(link.get("independence_group") or "unresolved"),
                    source_record_hash=str(link.get("record_hash") or ""), created_at=created_at,
                ))
            if str(claim.get("status") or "") != "reviewed_candidate":
                issues.append(self._issue(workspace_id, case_id, "claim_review_pending", "medium", "claim", "Candidate claim still requires analyst review", "Build 391 has synthesized this proposition, but it has not completed claim review.", refs, created_at))
            if int(claim.get("contradiction_groups") or 0) > 0:
                issues.append(self._issue(workspace_id, case_id, "counterevidence_conflict", "high", "claim", "Preserved counterevidence requires resolution", "At least one independent contradiction group is attached to this claim. The contradiction must remain visible and be investigated rather than averaged away.", refs, created_at))
            if int(claim.get("unresolved_observations") or 0) > 0:
                issues.append(self._issue(workspace_id, case_id, "source_independence_gap", "high", "corroboration", "Source independence remains unresolved", "One or more observations cannot yet be assigned to a trustworthy independence group, so they cannot strengthen corroboration.", refs, created_at))
            if int(claim.get("support_groups") or 0) < 2 and str(claim.get("analyst_disposition") or "") != "discard_not_supported":
                issues.append(self._issue(workspace_id, case_id, "independent_support_gap", "medium", "claim", "Additional independent support should be sought", "The claim currently has fewer than two countable independent support groups. This is a research gap, not evidence of falsity.", refs, created_at))
            if str(claim.get("analyst_disposition") or "") == "needs_more_evidence":
                issues.append(self._issue(workspace_id, case_id, "evidence_gap", "high", "claim", "Claim review recorded an evidence gap", "The analyst explicitly retained the claim as requiring more evidence before stronger analytical use.", refs, created_at))
            if str(claim.get("analyst_disposition") or "") == "contested_requires_analysis":
                issues.append(self._issue(workspace_id, case_id, "contested_claim", "high", "claim", "Contested claim requires comparative analysis", "The reviewed claim remains contested. Supporting and contradicting source groups should be compared by date, provenance and scope.", refs, created_at))

        for hyp in source.get("hypotheses") or []:
            hid = str(hyp.get("hypothesis_id") or "")
            refs = [{"object_type": "hypothesis", "object_id": hid}]
            if not bool(hyp.get("valid")):
                issues.append(self._issue(workspace_id, case_id, "integrity_review_required", "critical", "hypothesis", "Hypothesis integrity review required", "The stored Build-391 hypothesis or a claim link failed integrity verification. Testing must stop until reviewed.", refs, created_at))
                continue
            for link in hyp.get("claim_links") or []:
                arguments.append(self._argument(
                    workspace_id, case_id,
                    from_type="claim", from_id=str(link.get("claim_id") or ""),
                    to_type="hypothesis", to_id=hid, relation=str(link.get("relation") or "context"),
                    independence_group="claim_relation", source_record_hash=str(link.get("record_hash") or ""), created_at=created_at,
                ))
            status = str(hyp.get("status") or "")
            if status == "proposal_needs_review":
                issues.append(self._issue(workspace_id, case_id, "hypothesis_review_pending", "medium", "hypothesis", "Hypothesis requires analyst review", "This remains an unreviewed hypothesis proposal and must not be treated as an investigative conclusion.", refs, created_at))
            if status in {"retain_for_testing", "needs_more_evidence", "revise_requested"}:
                severity = "high" if status in {"retain_for_testing", "needs_more_evidence"} else "medium"
                issues.append(self._issue(workspace_id, case_id, "hypothesis_test_gap", severity, "hypothesis", "Hypothesis has an open test requirement", f"Hypothesis status is {status}. Its documented test plan should be executed or revised before stronger use.", refs, created_at))

        for idx, question in enumerate(source.get("open_questions") or []):
            text = str(question or "").strip()
            if text:
                issues.append(self._issue(workspace_id, case_id, "open_question", "medium", "reasoning", "Open investigative question", text, [{"object_type": "open_question", "object_id": str(idx)}], created_at))

        for idx, gap in enumerate(coverage.get("gaps") or []):
            gap_type = str(gap.get("gap_type") or "coverage_gap")
            severity = "high" if gap_type in {"registry_gap", "failed_or_blocked", "coverage_gap"} else "medium"
            issues.append(self._issue(
                workspace_id, case_id, "research_gap", severity, "coverage",
                f"Research gap: {gap_type}",
                f"{str(gap.get('subject') or '')}: {str(gap.get('detail') or '')}".strip(": "),
                [{"object_type": "research_gap", "object_id": f"{gap.get('origin','coverage')}:{idx}", "gap_type": gap_type, "subject": str(gap.get("subject") or "")}],
                created_at,
            ))

        # Deterministic de-duplication by semantic issue/argument id.
        issues = list({x["issue_id"]: x for x in issues}.values())
        arguments = list({x["argument_id"]: x for x in arguments}.values())
        issues.sort(key=lambda x: (_SEVERITY_RANK.get(x["severity"], 9), x["issue_type"], x["issue_id"]))
        arguments.sort(key=lambda x: (x["to_type"], x["to_id"], x["relation"], x["argument_id"]))
        return issues, arguments

    @staticmethod
    def _reasoning_state(issues: Sequence[Mapping[str, Any]]) -> str:
        if any(x.get("severity") == "critical" for x in issues):
            return "integrity_review_required"
        if any(x.get("issue_type") in {"counterevidence_conflict", "contested_claim"} for x in issues):
            return "contested_analysis_required"
        if any(x.get("issue_type") in {"research_gap", "evidence_gap", "independent_support_gap", "source_independence_gap", "hypothesis_test_gap"} for x in issues):
            return "research_required"
        if issues:
            return "analyst_review_required"
        return "analysis_ready"

    def create_workspace(self, *, case_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", case_id)
        source = self._source_snapshot(case_id)
        coverage = self._coverage_snapshot(case_id)
        source_hash = _sha(source)
        coverage_hash = _sha(coverage)
        existing = self.db.one(
            "SELECT workspace_id FROM case_reasoning_workspace_392 WHERE case_id=? AND source_snapshot_hash=? AND coverage_snapshot_hash=?",
            (case_id, source_hash, coverage_hash),
        )
        if existing:
            return self.workspace(case_id=case_id, workspace_id=str(existing["workspace_id"]), identity=identity)
        workspace_id = _stable_id("workspace392", {"case_id": case_id, "source": source_hash, "coverage": coverage_hash})
        created = _now()
        issues, arguments = self._derive(workspace_id, case_id, source, coverage, created)
        state = self._reasoning_state(issues)
        actor = str(identity.get("username") or self.actor)[:120]
        row = {
            "workspace_id": workspace_id,
            "case_id": case_id,
            "source_snapshot_hash": source_hash,
            "coverage_snapshot_hash": coverage_hash,
            "source_snapshot_json": _canon(source),
            "coverage_snapshot_json": _canon(coverage),
            "reasoning_state": state,
            "issue_count": len(issues),
            "argument_count": len(arguments),
            "created_by": actor,
            "created_at": created,
            "updated_at": created,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO case_reasoning_workspace_392(workspace_id,case_id,source_snapshot_hash,coverage_snapshot_hash,source_snapshot_json,coverage_snapshot_json,reasoning_state,issue_count,argument_count,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*row.values(), _sha(row)),
            )
            for issue in issues:
                self.db.execute(
                    "INSERT INTO reasoning_issue_392(issue_id,workspace_id,case_id,issue_type,severity,epistemic_layer,title,rationale,object_refs_json,status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*issue.values(), _sha(issue)),
                )
            for arg in arguments:
                self.db.execute(
                    "INSERT INTO reasoning_argument_392(argument_id,workspace_id,case_id,from_type,from_id,to_type,to_id,relation,independence_group,source_record_hash,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*arg.values(), _sha(arg)),
                )
        self.audit.log("reasoning_workspace", "case_reasoning_workspace_392", workspace_id, case_id, {
            "reasoning_state": state, "issues": len(issues), "arguments": len(arguments),
            "truth_determined": False, "probability_assigned": False, "execution_authority": False,
        })
        return self.workspace(case_id=case_id, workspace_id=workspace_id, identity=identity)

    def _workspace_row(self, case_id: str, workspace_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM case_reasoning_workspace_392 WHERE case_id=? AND workspace_id=?", (case_id, workspace_id))
        if not row:
            raise KeyError(workspace_id)
        return dict(row)

    def workspace(self, *, case_id: str, workspace_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", workspace_id)
        row = self._workspace_row(case_id, workspace_id)
        issues = [dict(r) for r in self.db.all("SELECT * FROM reasoning_issue_392 WHERE workspace_id=? ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,issue_type,issue_id", (workspace_id,))]
        arguments = [dict(r) for r in self.db.all("SELECT * FROM reasoning_argument_392 WHERE workspace_id=? ORDER BY to_type,to_id,relation,argument_id", (workspace_id,))]
        plan = self.db.one("SELECT plan_id FROM reasoning_plan_392 WHERE workspace_id=?", (workspace_id,))
        return {
            **row,
            "source_snapshot": dict(_j(row.get("source_snapshot_json"), {}) or {}),
            "coverage_snapshot": dict(_j(row.get("coverage_snapshot_json"), {}) or {}),
            "issues": [{**x, "object_refs": list(_j(x.get("object_refs_json"), []) or [])} for x in issues],
            "arguments": arguments,
            "plan_id": str((plan or {}).get("plan_id") or ""),
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_research_execution": False,
        }

    def _workspace_hash(self, workspace: Mapping[str, Any]) -> str:
        return _sha({
            "workspace_id": workspace.get("workspace_id"),
            "source_snapshot_hash": workspace.get("source_snapshot_hash"),
            "coverage_snapshot_hash": workspace.get("coverage_snapshot_hash"),
            "reasoning_state": workspace.get("reasoning_state"),
            "issues": [str(x.get("record_hash") or "") for x in workspace.get("issues") or []],
            "arguments": [str(x.get("record_hash") or "") for x in workspace.get("arguments") or []],
        })

    @staticmethod
    def _action_for_issue(issue: Mapping[str, Any]) -> tuple[str, str, bool]:
        t = str(issue.get("issue_type") or "")
        mapping = {
            "integrity_review_required": ("review_record_integrity", "Review record integrity before analytical use", False),
            "claim_review_pending": ("review_claim", "Complete analyst review of the candidate claim", False),
            "counterevidence_conflict": ("reconcile_counterevidence", "Compare supporting and contradicting evidence groups", False),
            "contested_claim": ("reconcile_contested_claim", "Perform comparative analysis of the contested claim", False),
            "source_independence_gap": ("review_source_independence", "Resolve source-family and independence provenance", False),
            "independent_support_gap": ("acquire_independent_support", "Seek an additional independent source group", True),
            "evidence_gap": ("acquire_targeted_evidence", "Collect targeted evidence for the reviewed gap", True),
            "hypothesis_review_pending": ("review_hypothesis", "Complete analyst review of the hypothesis", False),
            "hypothesis_test_gap": ("test_hypothesis", "Execute or refine the documented hypothesis test plan", True),
            "research_gap": ("close_research_gap", "Investigate the recorded source/coverage gap", True),
            "open_question": ("answer_open_question", "Resolve the open investigative question", False),
        }
        return mapping.get(t, ("analyst_review", "Review the analytical issue", False))

    def propose_plan(self, *, case_id: str, workspace_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.write", workspace_id)
        workspace = self.workspace(case_id=case_id, workspace_id=workspace_id)
        verify = self.verify_workspace(case_id=case_id, workspace_id=workspace_id)
        if not bool(verify.get("valid")):
            raise PermissionError("reasoning workspace integrity invalid")
        existing = self.db.one("SELECT plan_id FROM reasoning_plan_392 WHERE workspace_id=?", (workspace_id,))
        if existing:
            return self.plan(case_id=case_id, plan_id=str(existing["plan_id"]), identity=identity)
        created = _now()
        actions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for issue in workspace.get("issues") or []:
            action_type, title, external = self._action_for_issue(issue)
            refs = list(issue.get("object_refs") or [])
            semantic = {"action_type": action_type, "refs": refs, "source_issue_id": issue["issue_id"]}
            dedupe = _sha({"action_type": action_type, "refs": refs})
            if dedupe in seen:
                continue
            seen.add(dedupe)
            actions.append({
                "action_id": _stable_id("action392", {"workspace_id": workspace_id, **semantic}),
                "action_type": action_type,
                "priority": str(issue.get("severity") or "medium"),
                "title": title,
                "rationale": str(issue.get("rationale") or "")[:4000],
                "object_refs_json": _canon(refs),
                "requires_external_execution": int(external),
                "requires_go": int(external),
                "execution_authority": 0,
                "source_issue_id": str(issue.get("issue_id") or ""),
            })
        actions.sort(key=lambda a: (_SEVERITY_RANK.get(a["priority"], 9), a["action_type"], a["action_id"]))
        actions = actions[:100]
        workspace_hash = self._workspace_hash(workspace)
        semantic_actions = [{k: a[k] for k in a if k not in {"action_id"}} for a in actions]
        plan_hash = _sha({"workspace_hash": workspace_hash, "actions": semantic_actions, "execution_authority": False})
        plan_id = _stable_id("plan392", {"workspace_id": workspace_id, "plan_hash": plan_hash})
        actor = str(identity.get("username") or self.actor)[:120]
        row = {
            "plan_id": plan_id,
            "workspace_id": workspace_id,
            "case_id": case_id,
            "workspace_hash": workspace_hash,
            "plan_status": "proposal_needs_review",
            "analyst_disposition": "",
            "action_count": len(actions),
            "external_action_count": sum(int(a["requires_external_execution"]) for a in actions),
            "requires_go": int(any(bool(a["requires_go"]) for a in actions)),
            "execution_authority": 0,
            "created_by": actor,
            "created_at": created,
            "updated_at": created,
            "plan_hash": plan_hash,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO reasoning_plan_392(plan_id,workspace_id,case_id,workspace_hash,plan_status,analyst_disposition,action_count,external_action_count,requires_go,execution_authority,created_by,created_at,updated_at,plan_hash,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*row.values(), _sha(row)),
            )
            for ordinal, action in enumerate(actions, start=1):
                body = {
                    "action_id": action["action_id"], "plan_id": plan_id, "case_id": case_id, "ordinal": ordinal,
                    **action, "created_at": created,
                }
                # remove duplicate action_id from merged dict order if present is harmless semantically but not SQL-compatible
                vals = (
                    body["action_id"], body["plan_id"], body["case_id"], body["ordinal"], body["action_type"], body["priority"],
                    body["title"], body["rationale"], body["object_refs_json"], body["requires_external_execution"], body["requires_go"],
                    body["execution_authority"], body["source_issue_id"], body["created_at"], _sha(body),
                )
                self.db.execute(
                    "INSERT INTO reasoning_plan_action_392(action_id,plan_id,case_id,ordinal,action_type,priority,title,rationale,object_refs_json,requires_external_execution,requires_go,execution_authority,source_issue_id,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    vals,
                )
        self.audit.log("reasoning_plan_proposed", "reasoning_plan_392", plan_id, case_id, {
            "actions": len(actions), "external_actions": row["external_action_count"], "requires_go": bool(row["requires_go"]), "execution_authority": False,
        })
        return self.plan(case_id=case_id, plan_id=plan_id, identity=identity)

    def _plan_row(self, case_id: str, plan_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM reasoning_plan_392 WHERE case_id=? AND plan_id=?", (case_id, plan_id))
        if not row:
            raise KeyError(plan_id)
        return dict(row)

    def plan(self, *, case_id: str, plan_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", plan_id)
        row = self._plan_row(case_id, plan_id)
        actions = [dict(r) for r in self.db.all("SELECT * FROM reasoning_plan_action_392 WHERE plan_id=? ORDER BY ordinal", (plan_id,))]
        review = self.db.one("SELECT * FROM reasoning_plan_review_392 WHERE plan_id=?", (plan_id,))
        bridge = self.db.one("SELECT * FROM reasoning_kernel_bridge_392 WHERE plan_id=?", (plan_id,))
        return {
            **row,
            "actions": [{**a, "object_refs": list(_j(a.get("object_refs_json"), []) or [])} for a in actions],
            "review": dict(review) if review else None,
            "kernel_bridge": dict(bridge) if bridge else None,
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
            "automatic_go_issuance": False,
        }

    def review_plan(self, *, case_id: str, plan_id: str, identity: Mapping[str, Any], disposition: str, rationale: str, confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_PLAN_REVIEW:
            raise PermissionError(f"explicit confirmation {CONFIRM_PLAN_REVIEW} required")
        self._authorize(identity, case_id, "dossier.write", plan_id)
        disp = str(disposition or "").strip().lower()
        if disp not in _ALLOWED_PLAN_DISPOSITIONS:
            raise ValueError("unsupported plan disposition")
        if len(str(rationale or "").strip()) < 12:
            raise ValueError("substantive reasoning-plan review rationale required")
        row = self._plan_row(case_id, plan_id)
        if str(row.get("plan_status") or "") != "proposal_needs_review":
            raise PermissionError("reasoning plan already reviewed or not reviewable")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        review = {
            "review_id": _stable_id("planrev392", {"plan_id": plan_id, "disposition": disp, "reviewer": actor}),
            "plan_id": plan_id,
            "case_id": case_id,
            "disposition": disp,
            "rationale": str(rationale).strip()[:4000],
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        new_status = "reviewed_plan" if disp == "approve_for_investigator_review" else disp
        updated = {k: row[k] for k in row if k != "record_hash"}
        updated.update({"plan_status": new_status, "analyst_disposition": disp, "updated_at": now})
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO reasoning_plan_review_392(review_id,plan_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)", (*review.values(), _sha(review)))
            self.db.execute("UPDATE reasoning_plan_392 SET plan_status=?,analyst_disposition=?,updated_at=?,record_hash=? WHERE plan_id=?", (new_status, disp, now, _sha(updated), plan_id))
        self.audit.log("reasoning_plan_reviewed", "reasoning_plan_392", plan_id, case_id, {"disposition": disp, "execution_authority": False, "automatic_go_issuance": False})
        return self.plan(case_id=case_id, plan_id=plan_id, identity=identity)

    def admit_plan_to_kernel(self, *, case_id: str, plan_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_KERNEL_ADMISSION:
            raise PermissionError(f"explicit confirmation {CONFIRM_KERNEL_ADMISSION} required")
        self._authorize(identity, case_id, "dossier.write", plan_id)
        plan = self.plan(case_id=case_id, plan_id=plan_id)
        if str(plan.get("plan_status") or "") != "reviewed_plan" or str(plan.get("analyst_disposition") or "") != "approve_for_investigator_review":
            raise PermissionError("only an approved reviewed reasoning plan may enter the kernel notebook")
        existing = self.db.one("SELECT * FROM reasoning_kernel_bridge_392 WHERE plan_id=?", (plan_id,))
        if existing:
            return dict(existing) | {"execution_authority": False, "automatic_go_issuance": False}
        actor = str(identity.get("username") or self.actor)[:120]
        related: list[str] = []
        for action in plan.get("actions") or []:
            for ref in action.get("object_refs") or []:
                oid = str(ref.get("object_id") or "")
                if oid:
                    related.append(oid)
        body_text = _canon({
            "epistemic_status": "reviewed_investigation_plan_not_execution_authority",
            "plan_id": plan_id,
            "workspace_id": plan["workspace_id"],
            "actions": [
                {"ordinal": a["ordinal"], "action_type": a["action_type"], "priority": a["priority"], "title": a["title"], "requires_go": bool(a["requires_go"]), "execution_authority": False}
                for a in plan.get("actions") or []
            ],
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_go_issuance": False,
        })
        kernel_entry_id = self.kernel112.note(case_id, actor, "phase17_reasoning_plan", "Reviewed Phase-17 reasoning plan", body_text, list(dict.fromkeys(related))[:200])
        now = _now()
        bridge = {
            "bridge_id": _stable_id("kbridge392", {"case_id": case_id, "plan_id": plan_id, "kernel_entry_id": kernel_entry_id}),
            "case_id": case_id,
            "plan_id": plan_id,
            "kernel_entry_id": kernel_entry_id,
            "bridge_state": "kernel_notebook_plan",
            "source_plan_hash": str(plan.get("plan_hash") or ""),
            "created_by": actor,
            "created_at": now,
        }
        self.db.execute("INSERT INTO reasoning_kernel_bridge_392(bridge_id,case_id,plan_id,kernel_entry_id,bridge_state,source_plan_hash,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)", (*bridge.values(), _sha(bridge)))
        self.audit.log("bridge", "reasoning_kernel_bridge_392", bridge["bridge_id"], case_id, {"plan_id": plan_id, "execution_authority": False, "automatic_go_issuance": False})
        return {**bridge, "record_hash": _sha(bridge), "execution_authority": False, "automatic_go_issuance": False}

    def latest_workspace(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        row = self.db.one("SELECT workspace_id FROM case_reasoning_workspace_392 WHERE case_id=? ORDER BY created_at DESC,workspace_id DESC LIMIT 1", (case_id,))
        return self.workspace(case_id=case_id, workspace_id=str(row["workspace_id"])) if row else None

    def ai_reasoning_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        workspace = self.latest_workspace(case_id=case_id)
        plan = None
        if workspace and workspace.get("plan_id"):
            plan = self.plan(case_id=case_id, plan_id=str(workspace["plan_id"]))
        return {
            "case_id": case_id,
            "build": BUILD,
            "workspace": workspace,
            "next_investigation_plan": plan,
            "argumentative_reasoning": True,
            "counterevidence_preserved": True,
            "research_gaps_preserved": True,
            "epistemic_layers_preserved": True,
            "truth_determined": False,
            "probability_assigned": False,
            "execution_authority": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "network_requests_created": 0,
        }

    def verify_workspace(self, *, case_id: str, workspace_id: str) -> dict[str, Any]:
        row = self._workspace_row(case_id, workspace_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        issues_valid = True
        for issue in self.db.all("SELECT * FROM reasoning_issue_392 WHERE workspace_id=?", (workspace_id,)):
            ibody = {k: issue[k] for k in issue if k != "record_hash"}
            issues_valid = issues_valid and str(issue.get("record_hash") or "") == _sha(ibody)
        args_valid = True
        for arg in self.db.all("SELECT * FROM reasoning_argument_392 WHERE workspace_id=?", (workspace_id,)):
            abody = {k: arg[k] for k in arg if k != "record_hash"}
            args_valid = args_valid and str(arg.get("record_hash") or "") == _sha(abody)
        current_source = _sha(self._source_snapshot(case_id))
        current_coverage = _sha(self._coverage_snapshot(case_id))
        stale = current_source != str(row.get("source_snapshot_hash") or "") or current_coverage != str(row.get("coverage_snapshot_hash") or "")
        return {"workspace_id": workspace_id, "row_hash_valid": row_valid, "issue_hashes_valid": issues_valid, "argument_hashes_valid": args_valid, "stale": stale, "valid": row_valid and issues_valid and args_valid}

    def verify_plan(self, *, case_id: str, plan_id: str) -> dict[str, Any]:
        row = self._plan_row(case_id, plan_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        row_valid = str(row.get("record_hash") or "") == _sha(body)
        actions_valid = True
        for action in self.db.all("SELECT * FROM reasoning_plan_action_392 WHERE plan_id=? ORDER BY ordinal", (plan_id,)):
            abody = {k: action[k] for k in action if k != "record_hash"}
            actions_valid = actions_valid and str(action.get("record_hash") or "") == _sha(abody)
        workspace = self.workspace(case_id=case_id, workspace_id=str(row["workspace_id"]))
        workspace_hash_valid = str(row.get("workspace_hash") or "") == self._workspace_hash(workspace)
        return {"plan_id": plan_id, "row_hash_valid": row_valid, "action_hashes_valid": actions_valid, "workspace_hash_valid": workspace_hash_valid, "valid": row_valid and actions_valid and workspace_hash_valid}

    def status(self) -> dict[str, Any]:
        w = self.db.one("SELECT COUNT(*) total FROM case_reasoning_workspace_392") or {}
        i = self.db.one("SELECT COUNT(*) total FROM reasoning_issue_392") or {}
        p = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN plan_status='reviewed_plan' THEN 1 ELSE 0 END) reviewed FROM reasoning_plan_392") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "case_reasoning_workspace": True,
            "argument_graph": True,
            "counterevidence_preserved": True,
            "research_gap_reasoning": True,
            "next_investigation_plan_proposals": True,
            "human_plan_review_required": True,
            "kernel_notebook_plan_bridge": True,
            "epistemic_layers_preserved": True,
            "truth_probability": False,
            "automatic_truth_acceptance": False,
            "automatic_claim_acceptance": False,
            "automatic_evidence_promotion": False,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "execution_authority": False,
            "direct_network_fetch": False,
            "automatic_identity_merge": False,
            "workspaces": int(w.get("total") or 0),
            "issues": int(i.get("total") or 0),
            "plans": int(p.get("total") or 0),
            "reviewed_plans": int(p.get("reviewed") or 0),
        }
