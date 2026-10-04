from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
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
            CREATE TABLE IF NOT EXISTS phase20_qualification_case_450(
            case_id TEXT PRIMARY KEY,
            reviewer_username TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase20_qualification_consent_450(
            consent_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            reviewer_username TEXT NOT NULL,
            session_id_hash TEXT NOT NULL,
            confirmation TEXT NOT NULL,
            consented_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_qual_consent450_case
            ON phase20_qualification_consent_450(case_id,consented_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _authenticated_session(self, *, session_token, client_fingerprint):
        token = str(session_token or "")
        fingerprint = str(client_fingerprint or "")
        if not token or not fingerprint:
            raise PermissionError("reviewer session token and client fingerprint required for Build-450 qualification")
        identity = self.governance.identity.validate_session(
            token,
            client_fingerprint=fingerprint,
            touch=False,
        )
        if not identity:
            raise PermissionError("reviewer authentication failed for Build-450 qualification")
        return identity

    def _session_identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("authenticated identity required for Build-450 qualification")
        session_id = str(identity.get("session_id") or "").strip()
        if not session_id:
            raise PermissionError("active authenticated session required for Build-450 qualification")
        now = int(self.governance.identity.clock())
        row = self.db.one(
            "SELECT s.*,u.username,u.display_name,u.global_role,u.active,"
            "u.session_generation AS user_generation "
            "FROM phase15_team_sessions s JOIN phase15_team_users u ON u.user_id=s.user_id "
            "WHERE s.session_id=?",
            (session_id,),
        )
        if (
            not row
            or not bool(row.get("active"))
            or bool(row.get("revoked"))
            or int(row.get("idle_expires_epoch") or 0) <= now
            or int(row.get("absolute_expires_epoch") or 0) <= now
            or int(row.get("session_generation") if row.get("session_generation") is not None else -1)
            != int(row.get("user_generation") if row.get("user_generation") is not None else -2)
            or str(row.get("user_id")) != str(identity.get("user_id"))
            or str(row.get("username") or "").casefold() != str(identity.get("username") or "").casefold()
        ):
            raise PermissionError("active authenticated session required for Build-450 qualification")
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "global_role": row["global_role"],
            "session_id": row["session_id"],
        }

    def _auth_admin(self, identity):
        identity = self._session_identity(identity)
        roles = {str(x).lower() for x in (identity.get("roles") or [])}
        for key in ("role", "global_role"):
            if identity.get(key):
                roles.add(str(identity[key]).lower())
        if "system_administrator" not in roles and not ({"admin", "administrator", "owner"} & roles):
            raise PermissionError("system administrator required for Build-450 qualification")
        return identity

    def _reviewer(self, admin, reviewer_identity, case_id):
        reviewer = self._session_identity(reviewer_identity)
        if reviewer["username"].casefold() == str(admin["username"]).casefold():
            raise PermissionError("Build-450 qualification requires an independent reviewer")
        required_caps = {"source.review", "dossier.review", "dossier.export.approve"}
        caps = set(self.governance.effective_capabilities(reviewer, str(case_id)))
        missing = sorted(required_caps - caps)
        if missing:
            raise PermissionError(
                "reviewer lacks Build-450 case capabilities: " + ",".join(missing)
            )
        return reviewer

    def prepare_qualification_case(self, *, identity, reviewer_username):
        admin = self._auth_admin(identity)
        reviewer = self.governance.identity.public_user(str(reviewer_username or "").strip())
        if not reviewer.get("active"):
            raise PermissionError("Build-450 qualification reviewer must be active")
        if reviewer["username"].casefold() == admin["username"].casefold():
            raise PermissionError("Build-450 qualification requires an independent reviewer")
        case = self.governance.create_case(
            identity=admin,
            title="Build 450 Isolated Qualification",
            client="INTERNAL-QA",
            purpose="Isolated deterministic Build 450 hard-checkpoint qualification; no operational investigation data.",
            legal_basis="synthetic_test_fixture",
        )
        self.governance.assign_case_role(
            identity=admin,
            case_id=case["case_id"],
            username=reviewer["username"],
            case_role="reviewer",
            notes="Build 450 isolated qualification reviewer",
        )
        row = {
            "case_id": str(case["case_id"]),
            "reviewer_username": str(reviewer["username"]),
            "created_by": str(admin["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_qualification_case_450 VALUES(?,?,?,?,?)",
            tuple(row.values()),
        )
        return {**case, "qualification_marker": row}

    def _qualification_case(self, case_id):
        row = self.db.one(
            "SELECT * FROM phase20_qualification_case_450 WHERE case_id=?",
            (str(case_id),),
        )
        if not row:
            raise PermissionError(
                "Build-450 qualification may run only on an isolated qualification case"
            )
        item = dict(row)
        if self._rh(item) != item.get("record_hash"):
            raise PermissionError("Build-450 qualification-case marker integrity invalid")
        return item

    def consent_qualification_case(
        self,
        *,
        case_id,
        confirmation,
        reviewer_session_token,
        reviewer_client_fingerprint,
    ):
        reviewer = self._session_identity(
            self._authenticated_session(
                session_token=reviewer_session_token,
                client_fingerprint=reviewer_client_fingerprint,
            )
        )
        marker = self._qualification_case(case_id)
        if reviewer["username"].casefold() != str(marker["reviewer_username"]).casefold():
            raise PermissionError("only the designated reviewer may consent to this qualification case")
        self._reviewer({"username": marker["created_by"]}, reviewer, case_id)
        if str(confirmation or "").strip().upper() != "CONSENT BUILD 450 QUALIFICATION":
            raise PermissionError("explicit CONSENT BUILD 450 QUALIFICATION confirmation required")
        row = {
            "consent_id": "consent450_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "reviewer_username": reviewer["username"],
            "session_id_hash": hashlib.sha256(str(reviewer["session_id"]).encode("utf-8")).hexdigest(),
            "confirmation": "CONSENT BUILD 450 QUALIFICATION",
            "consented_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_qualification_consent_450 VALUES(?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        self.audit.log(
            "build450_reviewer_consent",
            "phase20_qualification_consent_450",
            row["consent_id"],
            str(case_id),
            {"reviewer": reviewer["username"], "explicit_consent": True},
        )
        return dict(row)

    def _qualification_consent(self, case_id, reviewer):
        row = self.db.one(
            "SELECT * FROM phase20_qualification_consent_450 WHERE case_id=? "
            "ORDER BY consented_at DESC,rowid DESC LIMIT 1",
            (str(case_id),),
        )
        if not row:
            raise PermissionError("explicit reviewer consent required for Build-450 qualification")
        item = dict(row)
        if self._rh(item) != item.get("record_hash"):
            raise PermissionError("Build-450 reviewer-consent integrity invalid")
        if item["reviewer_username"].casefold() != reviewer["username"].casefold():
            raise PermissionError("reviewer consent belongs to a different reviewer")
        session_hash = hashlib.sha256(str(reviewer["session_id"]).encode("utf-8")).hexdigest()
        if item["session_id_hash"] != session_hash:
            raise PermissionError("reviewer consent is not bound to the active reviewer session")
        return item

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

    def _preflight(self):
        component_checks, component_details = self._component_integrity()
        statuses = self._statuses()
        authority = self._authority_contract(statuses)
        if not all(component_checks.values()):
            raise RuntimeError("Build-450 preflight integrity failed before any workflow mutation")
        if not authority["pass"]:
            raise RuntimeError("Build-450 authority contract failed before any workflow mutation")
        return component_checks, component_details, statuses, authority

    def _verify_export_artifacts(self, export):
        paths = dict(export.get("paths") or {})
        recorded_hashes = dict(export.get("hashes") or {})
        required = {
            "json": "EagleEye_Living_Dossier.json",
            "docx": "EagleEye_Living_Dossier.docx",
            "pdf": "EagleEye_Living_Dossier.pdf",
            "manifest": "manifest.json",
        }
        exists = {}
        hash_matches = {}
        actual_hashes = {}
        for key, expected_name in required.items():
            raw = paths.get(key)
            path = Path(raw) if raw else None
            exists[key] = bool(path and path.exists() and path.is_file())
            if exists[key]:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                actual_hashes[expected_name] = digest
                hash_matches[key] = digest == str(recorded_hashes.get(expected_name) or "")
            else:
                hash_matches[key] = False

        package_raw = paths.get("case_package")
        package = Path(package_raw) if package_raw else None
        package_exists = bool(package and package.exists() and package.is_file())
        package_digest = hashlib.sha256(package.read_bytes()).hexdigest() if package_exists else ""
        package_hash_matches = package_digest == str(export.get("package_hash") or "")

        package_members_ok = False
        if package_exists:
            try:
                with ZipFile(package) as zf:
                    names = set(zf.namelist())
                package_members_ok = set(required.values()).issubset(names)
            except Exception:
                package_members_ok = False

        return {
            "exists": exists,
            "hash_matches": hash_matches,
            "actual_hashes": actual_hashes,
            "package_exists": package_exists,
            "package_actual_hash": package_digest,
            "package_hash_matches": package_hash_matches,
            "package_members_ok": package_members_ok,
            "valid": (
                all(exists.values())
                and all(hash_matches.values())
                and package_exists
                and package_hash_matches
                and package_members_ok
            ),
        }

    def _latest_artifacts_valid(self, last):
        if not last:
            return False
        workflow = (last.get("report") or {}).get("workflow_selftest") or {}
        paths = workflow.get("artifact_paths") or {}
        hashes = workflow.get("artifact_hashes") or {}
        package_hash = workflow.get("package_hash") or ""
        if not paths:
            return False
        return self._verify_export_artifacts(
            {"paths": paths, "hashes": hashes, "package_hash": package_hash}
        )["valid"]

    def _bound_workflow_rows_valid(self, last):
        if not last:
            return {"valid": False, "violations": [{"reason": "qualification_run_missing"}]}
        workflow = (last.get("report") or {}).get("workflow_selftest") or {}
        case_id = str(last.get("case_id") or "")
        reviewer = str(workflow.get("reviewer") or "")
        executor = str(workflow.get("executor") or "")
        violations = []

        def row(table, key, value, label):
            if not value:
                violations.append({"reason": f"{label}_id_missing"})
                return None
            found = self.db.one(f"SELECT * FROM {table} WHERE {key}=?", (str(value),))
            if not found:
                violations.append({"reason": f"{label}_row_missing", "id": str(value)})
                return None
            item = dict(found)
            if str(item.get("case_id") or "") != case_id:
                violations.append({"reason": f"{label}_case_mismatch", "id": str(value)})
            return item

        evidence = row("evidence_item_447", "evidence_id", workflow.get("evidence_id"), "evidence")
        claim = row("claim_447", "claim_id", workflow.get("claim_id"), "claim")
        dossier = row("dossier_revision_447", "revision_id", workflow.get("revision_id"), "dossier")
        export = row("dossier_export_447", "export_id", workflow.get("export_id"), "export")
        evidence_review = row("review_request_449", "review_id", workflow.get("evidence_review_id"), "evidence_review")
        claim_review = row("review_request_449", "review_id", workflow.get("claim_review_id"), "claim_review")
        dossier_review = row("review_request_449", "review_id", workflow.get("dossier_review_id"), "dossier_review")
        export_review = row("review_request_449", "review_id", workflow.get("export_review_id"), "export_review")
        export_execution = row("review_export_execution_449", "execution_id", workflow.get("export_execution_id"), "export_execution")

        if evidence and (evidence.get("review_state") != "accepted" or str(evidence.get("reviewed_by") or "") != reviewer):
            violations.append({"reason": "evidence_review_binding_invalid"})
        if claim:
            if claim.get("state") != "accepted_for_dossier" or str(claim.get("reviewed_by") or "") != reviewer:
                violations.append({"reason": "claim_review_binding_invalid"})
            if evidence and not self.db.one(
                "SELECT 1 FROM claim_evidence_link_447 WHERE claim_id=? AND evidence_id=? AND stance='support'",
                (str(claim["claim_id"]), str(evidence["evidence_id"])),
            ):
                violations.append({"reason": "claim_support_link_missing"})
        if dossier and (dossier.get("state") != "approved_for_export" or str(dossier.get("reviewed_by") or "") != reviewer):
            violations.append({"reason": "dossier_review_binding_invalid"})
        for item, kind, object_id in (
            (evidence_review, "evidence", workflow.get("evidence_id")),
            (claim_review, "claim", workflow.get("claim_id")),
            (dossier_review, "dossier", workflow.get("revision_id")),
            (export_review, "dossier_export", workflow.get("revision_id")),
        ):
            if item and (
                str(item.get("object_type") or "") != kind
                or str(item.get("object_id") or "") != str(object_id or "")
                or str(item.get("completed_by") or "") != reviewer
                or str(item.get("state") or "") != "completed"
            ):
                violations.append({"reason": f"{kind}_review_relationship_invalid"})
        if export and (
            str(export.get("revision_id") or "") != str(workflow.get("revision_id") or "")
            or str(export.get("package_hash") or "") != str(workflow.get("package_hash") or "")
        ):
            violations.append({"reason": "dossier_export_binding_invalid"})
        if export_execution and (
            str(export_execution.get("review_id") or "") != str(workflow.get("export_review_id") or "")
            or str(export_execution.get("export_id") or "") != str(workflow.get("export_id") or "")
            or str(export_execution.get("revision_id") or "") != str(workflow.get("revision_id") or "")
            or str(export_execution.get("executed_by") or "") != executor
            or str(export_execution.get("package_hash") or "") != str(workflow.get("package_hash") or "")
        ):
            violations.append({"reason": "export_execution_binding_invalid"})
        return {"valid": not violations, "violations": violations}

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

    def run_case_workflow(
        self,
        *,
        identity,
        case_id,
        reviewer_session_token,
        reviewer_client_fingerprint,
    ):
        admin = self._auth_admin(identity)
        marker = self._qualification_case(case_id)
        reviewer_identity = self._authenticated_session(
            session_token=reviewer_session_token,
            client_fingerprint=reviewer_client_fingerprint,
        )
        reviewer = self._reviewer(admin, reviewer_identity, case_id)
        if reviewer["username"].casefold() != str(marker["reviewer_username"]).casefold():
            raise PermissionError("authenticated reviewer does not match qualification-case reviewer")
        self._qualification_consent(case_id, reviewer)
        self._preflight()
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

        artifact_verification = self._verify_export_artifacts(exported["export"])
        workspace = review449.snapshot(
            identity=admin,
            case_id=str(case_id),
        )

        checks = {
            "build446_acquisition_pass": acquisition.get("result") == "PASS",
            "evidence_synchronized": bool(sync.get("evidence_ids")) and int(sync.get("created") or 0) >= 1,
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
            "case_package_exists": artifact_verification["package_exists"],
            "json_exists": artifact_verification["exists"]["json"],
            "docx_exists": artifact_verification["exists"]["docx"],
            "pdf_exists": artifact_verification["exists"]["pdf"],
            "manifest_exists": artifact_verification["exists"]["manifest"],
            "artifact_hashes_recomputed_match": all(artifact_verification["hash_matches"].values()),
            "package_hash_recomputed_match": artifact_verification["package_hash_matches"],
            "package_contains_expected_files": artifact_verification["package_members_ok"],
            "package_hash_bound": (
                exported["execution"].get("package_hash")
                == exported["export"].get("package_hash")
                == artifact_verification["package_actual_hash"]
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
            "evidence_review_id": evidence_request["review_id"],
            "claim_review_id": claim_request["review_id"],
            "dossier_review_id": dossier_request["review_id"],
            "export_review_id": export_request["review_id"],
            "export_execution_id": exported["execution"]["execution_id"],
            "export_id": exported["export"]["export_id"],
            "package_hash": exported["export"]["package_hash"],
            "artifact_paths": dict(exported["export"].get("paths") or {}),
            "artifact_hashes": dict(exported["export"].get("hashes") or {}),
            "artifact_verification": artifact_verification,
            "reviewer": reviewer["username"],
            "executor": exported["execution"]["executed_by"],
            "truth_determined": False,
        }

    def qualify(
        self,
        *,
        identity,
        case_id,
        reviewer_session_token,
        reviewer_client_fingerprint,
    ):
        admin = self._auth_admin(identity)
        marker = self._qualification_case(case_id)
        reviewer_identity = self._authenticated_session(
            session_token=reviewer_session_token,
            client_fingerprint=reviewer_client_fingerprint,
        )
        reviewer = self._reviewer(admin, reviewer_identity, case_id)
        if reviewer["username"].casefold() != str(marker["reviewer_username"]).casefold():
            raise PermissionError("authenticated reviewer does not match qualification-case reviewer")
        consent = self._qualification_consent(case_id, reviewer)

        component_checks, component_details, statuses, authority = self._preflight()

        workflow = self.run_case_workflow(
            identity=admin,
            case_id=case_id,
            reviewer_session_token=reviewer_session_token,
            reviewer_client_fingerprint=reviewer_client_fingerprint,
        )

        post_component_checks, post_component_details = self._component_integrity()
        q445 = statuses.get("qualification445", {})
        external_validation_pass = bool(q445.get("data_acquisition_gate_pass"))
        external_validation_result = "pass" if external_validation_pass else "hold"

        engineering_checks = {
            "isolated_qualification_case": True,
            "authenticated_independent_reviewer": True,
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
            "qualification_case": {
                "case_id": str(case_id),
                "isolated": True,
                "reviewer_username": reviewer["username"],
                "marker_record_hash": marker["record_hash"],
                "consent_id": consent["consent_id"],
                "consent_record_hash": consent["record_hash"],
                "reviewer_session_id_hash": consent["session_id_hash"],
            },
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
                "Build 450 qualifies deterministic engineering coherence only in an isolated "
                "synthetic qualification case with a separately authenticated reviewer. "
                "It does not certify external endpoint reliability, factual truth, or production readiness."
            ),
        }

        row = {
            "qualification_id": "qual450_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "reviewer_username": reviewer["username"],
            "engineering_result": engineering_result,
            "external_validation_result": external_validation_result,
            "release_result": release_result,
            "report_json": _canon(report),
            "created_by": str(admin["username"]),
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
            str(case_id),
            {
                "engineering_result": engineering_result,
                "external_validation_result": external_validation_result,
                "release_result": release_result,
                "isolated_qualification_case": True,
                "authenticated_reviewer": reviewer["username"],
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
        try:
            out["report"] = json.loads(out.get("report_json") or "{}")
            out["report_decode_error"] = False
        except Exception:
            out["report"] = {}
            out["report_decode_error"] = True
        return out

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("phase20_workflow_qualification_run_450", "qualification_id"),
            ("phase20_qualification_case_450", "case_id"),
            ("phase20_qualification_consent_450", "consent_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append(
                        {
                            key: item.get(key),
                            "table": table,
                            "reason": "record_hash_mismatch",
                        }
                    )
        for row in self.db.all("SELECT * FROM phase20_workflow_qualification_run_450"):
            run = dict(row)
            try:
                report = json.loads(run.get("report_json") or "{}")
            except Exception:
                report = {}
                bad.append({
                    "qualification_id": run.get("qualification_id"),
                    "table": "phase20_workflow_qualification_run_450",
                    "reason": "report_json_invalid",
                })
            qcase = report.get("qualification_case") or {}
            case_id = str(run.get("case_id") or "")
            marker = self.db.one(
                "SELECT * FROM phase20_qualification_case_450 WHERE case_id=?",
                (case_id,),
            )
            consent_id = str(qcase.get("consent_id") or "")
            consent = self.db.one(
                "SELECT * FROM phase20_qualification_consent_450 WHERE consent_id=?",
                (consent_id,),
            ) if consent_id else None
            if not marker:
                bad.append({
                    "qualification_id": run.get("qualification_id"),
                    "table": "phase20_qualification_case_450",
                    "reason": "qualification_case_marker_missing",
                })
            else:
                marker = dict(marker)
                if str(marker.get("record_hash") or "") != str(qcase.get("marker_record_hash") or ""):
                    bad.append({
                        "qualification_id": run.get("qualification_id"),
                        "table": "phase20_qualification_case_450",
                        "reason": "qualification_case_marker_not_bound_to_run",
                    })
            if not consent:
                bad.append({
                    "qualification_id": run.get("qualification_id"),
                    "table": "phase20_qualification_consent_450",
                    "reason": "reviewer_consent_missing",
                })
            else:
                consent = dict(consent)
                if str(consent.get("case_id") or "") != case_id:
                    bad.append({
                        "qualification_id": run.get("qualification_id"),
                        "table": "phase20_qualification_consent_450",
                        "reason": "reviewer_consent_case_mismatch",
                    })
                if str(consent.get("record_hash") or "") != str(qcase.get("consent_record_hash") or ""):
                    bad.append({
                        "qualification_id": run.get("qualification_id"),
                        "table": "phase20_qualification_consent_450",
                        "reason": "reviewer_consent_not_bound_to_run",
                    })
                if str(consent.get("session_id_hash") or "") != str(qcase.get("reviewer_session_id_hash") or ""):
                    bad.append({
                        "qualification_id": run.get("qualification_id"),
                        "table": "phase20_qualification_consent_450",
                        "reason": "reviewer_session_binding_mismatch",
                    })
                if str(consent.get("reviewer_username") or "").casefold() != str(run.get("reviewer_username") or "").casefold():
                    bad.append({
                        "qualification_id": run.get("qualification_id"),
                        "table": "phase20_qualification_consent_450",
                        "reason": "reviewer_identity_binding_mismatch",
                    })
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        last = self.latest()
        q445 = self.services["qualification445"].status()
        component_checks, _component_details = self._component_integrity()
        authority = self._authority_contract(self._statuses())
        local_integrity = self.verify_integrity()
        artifacts_valid = self._latest_artifacts_valid(last) if last else False
        bound_rows = self._bound_workflow_rows_valid(last) if last else {"valid": False, "violations": [{"reason": "qualification_run_missing"}]}
        current_components_valid = all(component_checks.values())
        checkpoint_pass = bool(
            local_integrity["valid"]
            and current_components_valid
            and authority["pass"]
            and artifacts_valid
            and bound_rows["valid"]
            and last
            and last["engineering_result"] == "pass"
        )
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
            "authenticated_reviewer_session_required": True,
            "explicit_reviewer_consent_required": True,
            "isolated_qualification_case_required": True,
            "interactive_http_qualification_disabled": True,
            "component_integrity_required": True,
            "full_governed_case_workflow_required": True,
            "github_ci_required": True,
            "full_repository_regression_required": True,
            "ui_regression_required": True,
            "codex_review_required_for_current_head": True,
            "integrity_valid": local_integrity["valid"],
            "current_component_integrity_valid": current_components_valid,
            "current_authority_contract_valid": authority["pass"],
            "qualified_artifacts_valid": artifacts_valid,
            "qualified_workflow_rows_valid": bound_rows["valid"],
            "qualified_workflow_row_violations": bound_rows["violations"],
            "last_engineering_result": last["engineering_result"] if last else None,
            "last_external_validation_result": last["external_validation_result"] if last else None,
            "last_release_result": last["release_result"] if last else None,
            "investigation_workflow_checkpoint_pass": checkpoint_pass,
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
