from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import secrets

BUILD = "450.0"
POLICY_ID = "phase20.investigation-workflow-hard-checkpoint.v450"

REQUIRED = (
    "surface441",
    "hardening442",
    "news443",
    "social444",
    "qualification445",
    "dispatcher446",
    "closure447",
    "workspace448",
    "review449",
)

FORBIDDEN_TRUE_KEYS = (
    "automatic_go",
    "automatic_go_issuance",
    "automatic_live_execution",
    "automatic_scope_expansion",
    "autonomous_scope_expansion",
    "automatic_evidence_promotion",
    "automatic_claim_creation",
    "automatic_claim_acceptance",
    "automatic_truth_determination",
    "truth_determined",
    "truth_determination",
    "automatic_review_completion",
    "automatic_dossier_publication",
    "access_control_bypass",
    "access_control_bypass_supported",
    "private_or_direct_content_supported",
    "private_or_direct_social_supported",
    "social_graph_enumeration",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class InvestigationWorkflowHardCheckpoint450:
    """Fail-closed engineering checkpoint for the current Phase-20 workflow.

    The checkpoint qualifies the deterministic governed chain from acquisition
    through Evidence, Claims, Dossier, independent review and four-eyes export.
    It deliberately keeps engineering qualification separate from external
    public-endpoint validation and production readiness.
    """

    REQUIRED = REQUIRED

    def __init__(
        self,
        db,
        audit,
        *,
        services,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.services = dict(services)
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase20_workflow_qualification_run_450(
            qualification_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            reviewer_username TEXT NOT NULL,
            engineering_result TEXT NOT NULL,
            external_validation_result TEXT NOT NULL,
            release_result TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_workflow_qual450_case
            ON phase20_workflow_qualification_run_450(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _auth_admin(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("system administrator identity required for Build-450 qualification")
        roles = {str(x).lower() for x in (identity.get("roles") or [])}
        for key in ("role", "global_role"):
            if identity.get(key):
                roles.add(str(identity[key]).lower())
        if "system_administrator" not in roles and not ({"admin", "administrator", "owner"} & roles):
            raise PermissionError("system administrator required for Build-450 qualification")
        return identity

    def _reviewer(self, identity, reviewer_username, case_id):
        reviewer_username = str(reviewer_username or "").strip()
        if not reviewer_username:
            raise ValueError("independent reviewer_username required")
        if reviewer_username.casefold() == str(identity["username"]).casefold():
            raise PermissionError("Build-450 qualification requires an independent reviewer")
        user = self.governance.identity.public_user(reviewer_username)
        reviewer = {**user, "session_id": "checkpoint450"}
        required_caps = {
            "source.review",
            "dossier.review",
            "dossier.export.approve",
        }
        caps = set(self.governance.effective_capabilities(reviewer, str(case_id)))
        missing = sorted(required_caps - caps)
        if missing:
            raise PermissionError(
                "reviewer lacks Build-450 case capabilities: " + ",".join(missing)
            )
        return reviewer

    def _component_integrity(self):
        checks = {}
        details = {}
        for name in self.REQUIRED:
            service = self.services.get(name)
            if service is None:
                checks[name] = False
                details[name] = {"available": False, "reason": "service_missing"}
                continue
            try:
                if hasattr(service, "verify_integrity"):
                    detail = service.verify_integrity()
                    ok = bool(detail.get("valid", False))
                elif hasattr(service, "status"):
                    detail = service.status()
                    ok = bool(detail.get("integrity_valid", False))
                else:
                    detail = {"available": True}
                    ok = True
            except Exception as exc:
                detail = {"available": True, "error": type(exc).__name__}
                ok = False
            checks[name] = ok
            details[name] = detail
        return checks, details

    def _statuses(self):
        out = {}
        for name in self.REQUIRED:
            service = self.services[name]
            try:
                out[name] = service.status() if hasattr(service, "status") else {}
            except Exception as exc:
                out[name] = {"status_error": type(exc).__name__}
        return out

    def _authority_contract(self, statuses):
        forbidden = []
        for component, status in statuses.items():
            for key in FORBIDDEN_TRUE_KEYS:
                if status.get(key) is True:
                    forbidden.append({"component": component, "field": key})
        review = statuses.get("review449", {})
        dispatcher = statuses.get("dispatcher446", {})
        checks = {
            "no_forbidden_automatic_authority": not forbidden,
            "per_path_acquisition_confirmation": bool(dispatcher.get("per_path_confirmation_required")),
            "generic_network_authority_false": dispatcher.get("generic_network_authority") is False,
            "four_eyes_export_required": bool(review.get("dossier_export_four_eyes")),
            "requester_reviewer_separation": bool(review.get("requester_reviewer_separation")),
            "creator_reviewer_separation": bool(review.get("creator_reviewer_separation")),
            "stale_review_detection": bool(review.get("stale_object_detection")),
            "direct_review_bypass_forbidden_current_ui": bool(review.get("direct_build447_review_bypass_forbidden")),
        }
        return {
            "checks": checks,
            "forbidden_true": forbidden,
            "pass": all(checks.values()),
        }

    def _new_evidence(self, before_ids, case_id):
        rows = self.services["closure447"].case_evidence(str(case_id))
        candidates = [
            x for x in rows
            if x["evidence_id"] not in before_ids and x["review_state"] == "unreviewed"
        ]
        if not candidates:
            candidates = [x for x in rows if x["review_state"] == "unreviewed"]
        if not candidates:
            raise RuntimeError("Build-450 qualification requires newly synchronized unreviewed Evidence")
        return candidates[0]

    def _complete_review(self, reviewer, request, decision, note):
        review449 = self.services["review449"]
        claimed = review449.claim_review(
            identity=reviewer,
            review_id=request["review_id"],
        )
        if claimed["state"] != "claimed":
            raise RuntimeError("Build-450 reviewer could not claim review")
        confirmation = {
            "evidence": "REVIEW EVIDENCE 447",
            "claim": "REVIEW CLAIM 447",
            "dossier": "APPROVE DOSSIER 447",
            "dossier_export": "APPROVE DOSSIER EXPORT 449",
        }[request["object_type"]]
        return review449.complete_review(
            identity=reviewer,
            review_id=request["review_id"],
            decision=decision,
            note=note,
            confirmation=confirmation,
        )

    def run_case_workflow(self, *, identity, case_id, reviewer_username):
        admin = self._auth_admin(identity)
        reviewer = self._reviewer(admin, reviewer_username, case_id)
        dispatcher = self.services["dispatcher446"]
        closure = self.services["closure447"]
        review449 = self.services["review449"]

        before_ids = {
            x["evidence_id"] for x in closure.case_evidence(str(case_id))
        }

        acquisition = dispatcher.run_case_selftest(
            identity=admin,
            case_id=str(case_id),
        )
        if acquisition.get("result") != "PASS":
            raise RuntimeError("Build-446 deterministic acquisition/dispatch selftest failed")

        sync = closure.sync_case_evidence(
            identity=admin,
            case_id=str(case_id),
        )
        evidence = self._new_evidence(before_ids, case_id)

        evidence_request = review449.request_review(
            identity=admin,
            object_type="evidence",
            object_id=evidence["evidence_id"],
            note="Build 450 independent Evidence qualification review.",
            assigned_to=reviewer["username"],
        )
        evidence_done = self._complete_review(
            reviewer,
            evidence_request,
            "accepted",
            "Independent Build-450 Evidence review confirms provenance integrity for the deterministic fixture only.",
        )
        reviewed_evidence = evidence_done["object"]

        claim = closure.propose_claim(
            identity=admin,
            case_id=str(case_id),
            statement="Synthetic Build 450 proposition used only to qualify the governed investigation workflow.",
            support_evidence_ids=[reviewed_evidence["evidence_id"]],
            uncertainty_note="Deterministic engineering qualification only; this is not a real-world truth assertion.",
        )
        claim_request = review449.request_review(
            identity=admin,
            object_type="claim",
            object_id=claim["claim_id"],
            note="Build 450 independent Claim review before Dossier inclusion.",
            assigned_to=reviewer["username"],
        )
        claim_done = self._complete_review(
            reviewer,
            claim_request,
            "accepted_for_dossier",
            "Claim is bounded to independently reviewed synthetic Evidence and may enter the qualification Dossier.",
        )

        dossier = closure.build_dossier(
            identity=admin,
            case_id=str(case_id),
            title="Build 450 Investigation Workflow Qualification Dossier",
        )
        dossier_request = review449.request_review(
            identity=admin,
            object_type="dossier",
            object_id=dossier["revision_id"],
            note="Build 450 independent Dossier review before release approval.",
            assigned_to=reviewer["username"],
        )
        dossier_done = self._complete_review(
            reviewer,
            dossier_request,
            "approved_for_export",
            "Dossier preserves reviewed Claims, provenance and uncertainty boundaries for checkpoint qualification.",
        )

        export_request = review449.request_review(
            identity=admin,
            object_type="dossier_export",
            object_id=dossier["revision_id"],
            note="Build 450 independent four-eyes export approval request.",
            assigned_to=reviewer["username"],
        )
        export_approval = self._complete_review(
            reviewer,
            export_request,
            "approve",
            "Independent reviewer approves deterministic checkpoint package release; no truth certification is implied.",
        )
        exported = review449.execute_approved_export(
            identity=admin,
            review_id=export_request["review_id"],
            confirmation="EXPORT DOSSIER 447",
        )

        package_path = Path(exported["export"]["paths"]["case_package"])
        docx_path = Path(exported["export"]["paths"]["docx"])
        pdf_path = Path(exported["export"]["paths"]["pdf"])
        workspace = review449.snapshot(
            identity=admin,
            case_id=str(case_id),
        )

        checks = {
            "build446_acquisition_pass": acquisition.get("result") == "PASS",
            "evidence_synchronized": int(sync.get("evidence_count") or 0) >= 1,
            "independent_evidence_review": (
                reviewed_evidence.get("reviewed_by") == reviewer["username"]
                and reviewed_evidence.get("review_state") == "accepted"
            ),
            "independent_claim_review": (
                claim_done["object"].get("reviewed_by") == reviewer["username"]
                and claim_done["object"].get("state") == "accepted_for_dossier"
            ),
            "independent_dossier_review": (
                dossier_done["object"].get("reviewed_by") == reviewer["username"]
                and dossier_done["object"].get("state") == "approved_for_export"
            ),
            "independent_export_approval": (
                export_approval["review"].get("completed_by") == reviewer["username"]
                and export_approval["review"].get("decision") == "approve"
            ),
            "executor_differs_from_export_approver": (
                exported["execution"].get("executed_by") != reviewer["username"]
            ),
            "case_package_exists": package_path.exists(),
            "docx_exists": docx_path.exists(),
            "pdf_exists": pdf_path.exists(),
            "package_hash_bound": (
                exported["execution"].get("package_hash")
                == exported["export"].get("package_hash")
            ),
            "workspace_review_layer_visible": bool(workspace.get("team_review449")),
            "review_integrity_valid": review449.verify_integrity()["valid"],
            "dossier_integrity_valid": closure.verify_integrity()["valid"],
        }
        return {
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "acquisition": acquisition,
            "evidence_id": reviewed_evidence["evidence_id"],
            "claim_id": claim["claim_id"],
            "revision_id": dossier["revision_id"],
            "export_review_id": export_request["review_id"],
            "export_id": exported["export"]["export_id"],
            "package_hash": exported["export"]["package_hash"],
            "reviewer": reviewer["username"],
            "executor": exported["execution"]["executed_by"],
            "truth_determined": False,
        }

    def qualify(self, *, identity, case_id, reviewer_username):
        admin = self._auth_admin(identity)
        case_id = str(case_id or "").strip()
        if not case_id:
            raise ValueError("dedicated qualification case_id required")

        component_checks, component_details = self._component_integrity()
        statuses = self._statuses()
        authority = self._authority_contract(statuses)

        try:
            workflow = self.run_case_workflow(
                identity=admin,
                case_id=case_id,
                reviewer_username=reviewer_username,
            )
        except Exception as exc:
            workflow = {
                "result": "FAIL",
                "error": type(exc).__name__,
                "message": str(exc),
                "truth_determined": False,
            }

        # Re-check after the complete workflow because the checkpoint itself
        # created Evidence/Claims/Dossier/review/export records.
        post_component_checks, post_component_details = self._component_integrity()

        q445 = statuses.get("qualification445", {})
        external_validation_pass = bool(q445.get("data_acquisition_gate_pass"))
        external_validation_result = "pass" if external_validation_pass else "hold"

        engineering_checks = {
            "all_components_integrity_before": all(component_checks.values()),
            "all_components_integrity_after": all(post_component_checks.values()),
            "authority_contract_pass": authority["pass"],
            "full_governed_case_workflow_pass": workflow.get("result") == "PASS",
            "four_eyes_release_exercised": bool(
                workflow.get("checks", {}).get("independent_export_approval")
            ),
            "package_export_exercised": bool(
                workflow.get("checks", {}).get("case_package_exists")
            ),
        }
        engineering_result = "pass" if all(engineering_checks.values()) else "hold"

        # Production release is deliberately not granted by deterministic tests.
        # Build 445 external non-fixture validation may lift one gate, but broader
        # field validation/security/deployment qualification still remains.
        release_checks = {
            "engineering_checkpoint_pass": engineering_result == "pass",
            "external_acquisition_validation_pass": external_validation_pass,
            "production_hardening_complete": False,
            "external_user_validation_complete": False,
        }
        release_result = "hold"

        report = {
            "build": BUILD,
            "phase": 20,
            "hard_checkpoint": True,
            "checkpoint_name": "Investigation Workflow Hard Checkpoint",
            "phase20_builds_completed": 10,
            "required_components": list(self.REQUIRED),
            "component_checks_before": component_checks,
            "component_details_before": component_details,
            "component_checks_after": post_component_checks,
            "component_details_after": post_component_details,
            "authority_contract": authority,
            "workflow_selftest": workflow,
            "engineering_checks": engineering_checks,
            "engineering_result": engineering_result,
            "external_validation_result": external_validation_result,
            "release_checks": release_checks,
            "release_result": release_result,
            "investigation_workflow_checkpoint_pass": engineering_result == "pass",
            "external_nonfixture_acquisition_validated": external_validation_pass,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "truth_determined": False,
            "note": (
                "Build 450 qualifies deterministic engineering coherence of the governed "
                "investigation workflow. It does not certify external endpoint reliability, "
                "operational security in every deployment, factual truth, or production readiness."
            ),
        }

        row = {
            "qualification_id": "qual450_" + secrets.token_hex(10),
            "case_id": case_id,
            "reviewer_username": str(reviewer_username),
            "engineering_result": engineering_result,
            "external_validation_result": external_validation_result,
            "release_result": release_result,
            "report_json": _canon(report),
            "created_by": str(admin.get("username") or self.actor),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_workflow_qualification_run_450 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "investigation_workflow_hard_checkpoint_450",
            "phase20_workflow_qualification_run_450",
            row["qualification_id"],
            case_id,
            {
                "engineering_result": engineering_result,
                "external_validation_result": external_validation_result,
                "release_result": release_result,
                "production_release_ready": False,
            },
        )
        return {**row, "report": report}

    def latest(self, case_id=""):
        if case_id:
            row = self.db.one(
                "SELECT * FROM phase20_workflow_qualification_run_450 "
                "WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
                (str(case_id),),
            )
        else:
            row = self.db.one(
                "SELECT * FROM phase20_workflow_qualification_run_450 ORDER BY rowid DESC LIMIT 1"
            )
        if not row:
            return None
        out = dict(row)
        out["report"] = json.loads(out["report_json"])
        return out

    def verify_integrity(self):
        bad = []
        for row in self.db.all("SELECT * FROM phase20_workflow_qualification_run_450"):
            item = dict(row)
            if self._rh(item) != item.get("record_hash"):
                bad.append(
                    {
                        "qualification_id": item.get("qualification_id"),
                        "reason": "qualification_hash_mismatch",
                    }
                )
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        last = self.latest()
        q445 = self.services["qualification445"].status()
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "hard_checkpoint": True,
            "checkpoint_name": "Investigation Workflow Hard Checkpoint",
            "phase": 20,
            "phase20_complete": True,
            "phase20_builds_completed": 10,
            "qualification_fail_closed": True,
            "admin_qualification_required": True,
            "independent_reviewer_required": True,
            "component_integrity_required": True,
            "full_governed_case_workflow_required": True,
            "github_ci_required": True,
            "full_repository_regression_required": True,
            "ui_regression_required": True,
            "codex_review_required_for_current_head": True,
            "integrity_valid": self.verify_integrity()["valid"],
            "last_engineering_result": last["engineering_result"] if last else None,
            "last_external_validation_result": last["external_validation_result"] if last else None,
            "last_release_result": last["release_result"] if last else None,
            "investigation_workflow_checkpoint_pass": bool(
                last and last["engineering_result"] == "pass"
            ),
            "external_nonfixture_acquisition_validated": bool(
                q445.get("data_acquisition_gate_pass")
            ),
            "release_gate_pass": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "automatic_truth_determination": False,
            "automatic_review_completion": False,
            "next_phase_requires_checkpoint_findings": True,
        }
