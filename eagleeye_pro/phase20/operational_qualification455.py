from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import secrets

BUILD = "455.0"
POLICY_ID = "phase20.full-operations-real-source-gate.v455"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class OperationalResearchQualification455:
    """Build-455 hard checkpoint over an already executed governed research case.

    The service does not perform network retrieval itself. It verifies that a case
    was populated through existing acquisition paths, that real/non-fixture public
    sources reached Evidence, that independent review/Claims/Dossier/export were
    completed, and that recovery + reopen verification preserve references.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        registry421,
        events422,
        content423,
        closure447,
        review449,
        build450,
        build451,
        recovery453,
        infrastructure454,
        xref454,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.registry421 = registry421
        self.events422 = events422
        self.content423 = content423
        self.closure447 = closure447
        self.review449 = review449
        self.build450 = build450
        self.build451 = build451
        self.recovery453 = recovery453
        self.infrastructure454 = infrastructure454
        self.xref454 = xref454
        self.governance = governance
        self.actor = actor
        self._schema()

    def _schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS phase20_operational_qualification_run_455(
          qualification_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          support_evidence_id TEXT NOT NULL,
          counter_evidence_id TEXT NOT NULL,
          claim_id TEXT NOT NULL,
          revision_id TEXT NOT NULL,
          export_id TEXT NOT NULL,
          recovery_id TEXT NOT NULL,
          engineering_result TEXT NOT NULL,
          live_case_result TEXT NOT NULL,
          restart_result TEXT NOT NULL,
          overall_result TEXT NOT NULL,
          report_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_oq455_case
          ON phase20_operational_qualification_run_455(case_id, created_at);

        CREATE TABLE IF NOT EXISTS phase20_operational_restart_455(
          restart_id TEXT PRIMARY KEY,
          qualification_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          verification_json TEXT NOT NULL,
          verified_by TEXT NOT NULL,
          verified_at TEXT NOT NULL,
          record_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_or455_qualification
          ON phase20_operational_restart_455(qualification_id, verified_at);
        """)
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity, *, admin=False):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required") from None
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        if admin and user.get("global_role") != "system_administrator":
            raise PermissionError("system administrator required")
        return {**user, "session_id": str(identity.get("session_id") or "ops455")}

    def _authorize(self, identity, case_id, *, admin=False):
        ident = self._identity(identity, admin=admin)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability="research.run",
            object_type="operational_research_qualification_455",
            object_id=str(case_id),
        )
        return ident

    def _row(self, table, key, value, label):
        row = self.db.one(f"SELECT * FROM {table} WHERE {key}=?", (str(value),))
        if not row:
            raise RuntimeError(f"{label} row missing")
        return dict(row)

    def _source_real_public(self, source_id):
        source = self.registry421.get(source_id)
        coverage = source.get("coverage") or {}
        checks = {
            "enabled": int(source.get("enabled") or 0) == 1,
            "public_access": source.get("access_mode") == "public",
            "non_fixture": not bool(coverage.get("fixture_only")),
            "not_live_forbidden": not bool(coverage.get("live_execution_forbidden")),
        }
        return source, checks

    def _evidence_chain(self, evidence_id, expected_case_id):
        evidence = self.closure447.evidence(evidence_id)
        if evidence["case_id"] != str(expected_case_id):
            raise RuntimeError("evidence belongs to another case")
        event = self.events422.get(evidence["event_id"])
        source, source_checks = self._source_real_public(evidence["source_id"])
        content = self._row("content_object_423", "content_id", evidence["content_id"], "content")
        observation = self._row(
            "content_observation_423", "observation_id", evidence["observation_id"], "observation"
        )
        checks = {
            **source_checks,
            "event_retrieved": event.get("status") == "retrieved",
            "event_case_bound": event.get("case_id") == str(expected_case_id),
            "event_source_bound": event.get("source_id") == evidence["source_id"],
            "observation_event_bound": observation.get("event_id") == evidence["event_id"],
            "observation_content_bound": observation.get("content_id") == evidence["content_id"],
            "content_hash_bound": content.get("sha256") == evidence.get("content_sha256"),
            "evidence_human_reviewed": evidence.get("review_state") in {"accepted", "context_only"},
            "evidence_reviewer_present": bool(evidence.get("reviewed_by")),
        }
        return {
            "evidence": evidence,
            "event": event,
            "source": source,
            "content": content,
            "observation": observation,
            "checks": checks,
        }

    def _completed_review(self, case_id, object_type, object_id):
        row = self.db.one(
            "SELECT * FROM review_request_449 WHERE case_id=? AND object_type=? AND object_id=? "
            "AND state='completed' ORDER BY completed_at DESC,rowid DESC LIMIT 1",
            (str(case_id), str(object_type), str(object_id)),
        )
        return dict(row) if row else None

    def _verify_export_files(self, export):
        paths = dict(export.get("paths") or {})
        hashes = dict(export.get("hashes") or {})
        expected = {
            "json": "EagleEye_Living_Dossier.json",
            "docx": "EagleEye_Living_Dossier.docx",
            "pdf": "EagleEye_Living_Dossier.pdf",
            "manifest": "manifest.json",
        }
        file_checks = {}
        actual_hashes = {}
        for key, filename in expected.items():
            raw = paths.get(key)
            path = Path(raw) if isinstance(raw, str) and raw else None
            exists = False
            digest = ""
            try:
                exists = bool(path and path.is_file())
                if exists:
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                exists = False
            actual_hashes[filename] = digest
            file_checks[key] = exists and digest == str(hashes.get(filename) or "")

        package_raw = paths.get("case_package")
        package = Path(package_raw) if isinstance(package_raw, str) and package_raw else None
        package_hash = ""
        package_members = {}
        try:
            package_exists = bool(package and package.is_file())
            if package_exists:
                package_hash = hashlib.sha256(package.read_bytes()).hexdigest()
                with ZipFile(package) as zf:
                    names = set(zf.namelist())
                    for filename in expected.values():
                        package_members[filename] = (
                            filename in names
                            and hashlib.sha256(zf.read(filename)).hexdigest() == str(hashes.get(filename) or "")
                        )
            else:
                package_members = {x: False for x in expected.values()}
        except Exception:
            package_exists = False
            package_members = {x: False for x in expected.values()}

        return {
            "file_hash_matches": file_checks,
            "actual_hashes": actual_hashes,
            "package_exists": package_exists,
            "package_hash": package_hash,
            "package_hash_matches": package_hash == str(export.get("package_hash") or ""),
            "package_member_hash_matches": package_members,
            "valid": (
                all(file_checks.values())
                and package_exists
                and package_hash == str(export.get("package_hash") or "")
                and all(package_members.values())
            ),
        }

    def _engineering_checks(self):
        status450 = self.build450.investigation_workflow_status_450()
        retrieval = self.build451.retrieval_isolation_status_451()
        infra = self.infrastructure454.status()
        xref = self.xref454.status()
        return {
            "build450_checkpoint_pass": bool(status450.get("investigation_workflow_checkpoint_pass")),
            "build450_integrity_valid": bool(status450.get("integrity_valid")),
            "retrieval_process_isolation": bool(retrieval.get("process_isolation")),
            "retrieval_content_risk_gate": bool(retrieval.get("content_risk_gate")),
            "retrieval_unsupported_profile_fails_closed": bool(retrieval.get("unsupported_profile_fails_closed")),
            "infrastructure_integrity": bool(infra.get("integrity_valid")),
            "infrastructure_active_scanning_false": infra.get("active_scanning") is False,
            "xref_integrity": bool(xref.get("integrity_valid")),
            "xref_automatic_ownership_false": xref.get("automatic_ownership_determination") is False,
            "five_build_checkpoint": int(BUILD.split(".", 1)[0]) % 5 == 0,
        }

    def qualify_case(
        self,
        *,
        identity,
        case_id,
        support_evidence_id,
        counter_evidence_id,
        claim_id,
        revision_id,
        export_id,
        recovery_id,
    ):
        ident = self._authorize(identity, case_id, admin=True)

        engineering_checks = self._engineering_checks()
        if not all(engineering_checks.values()):
            raise RuntimeError("Build-455 engineering preflight failed")

        support = self._evidence_chain(support_evidence_id, case_id)
        counter = self._evidence_chain(counter_evidence_id, case_id)
        claim = self.closure447.claim(claim_id)
        dossier = self.closure447.dossier(revision_id)
        export = next(
            (x for x in self.closure447.exports(case_id) if x["export_id"] == str(export_id)),
            None,
        )
        if not export:
            raise RuntimeError("dossier export row missing")
        recovery = self.recovery453.verify(recovery_id)

        claim_links = list(claim.get("links") or [])
        support_linked = any(
            x.get("evidence_id") == str(support_evidence_id) and x.get("stance") == "support"
            for x in claim_links
        )
        counter_linked = any(
            x.get("evidence_id") == str(counter_evidence_id) and x.get("stance") == "contradict"
            for x in claim_links
        )

        evidence_reviews = {
            "support": self._completed_review(case_id, "evidence", support_evidence_id),
            "counter": self._completed_review(case_id, "evidence", counter_evidence_id),
        }
        claim_review = self._completed_review(case_id, "claim", claim_id)
        dossier_review = self._completed_review(case_id, "dossier", revision_id)
        export_review = self._completed_review(case_id, "dossier_export", revision_id)
        export_execution = self.db.one(
            "SELECT * FROM review_export_execution_449 WHERE case_id=? AND export_id=? "
            "ORDER BY executed_at DESC,rowid DESC LIMIT 1",
            (str(case_id), str(export_id)),
        )
        export_execution = dict(export_execution) if export_execution else None

        reviewers = {
            str(x.get("completed_by") or "")
            for x in [*evidence_reviews.values(), claim_review, dossier_review, export_review]
            if x
        }
        creator = str(claim.get("created_by") or "")
        export_files = self._verify_export_files(export)

        infra_facts = self.infrastructure454.facts(case_id)
        xref_candidates = self.xref454.candidates(case_id, min_score=0.20, limit=500)

        live_checks = {
            "support_real_public_provenance": all(support["checks"].values()),
            "counter_real_public_provenance": all(counter["checks"].values()),
            "distinct_evidence_items": support_evidence_id != counter_evidence_id,
            "claim_case_bound": claim.get("case_id") == str(case_id),
            "claim_accepted_for_dossier": claim.get("state") == "accepted_for_dossier",
            "claim_support_linked": support_linked,
            "claim_counterevidence_linked": counter_linked,
            "claim_uncertainty_preserved": len(str(claim.get("uncertainty_note") or "").strip()) >= 12,
            "dossier_case_bound": dossier.get("case_id") == str(case_id),
            "dossier_approved": dossier.get("state") == "approved_for_export",
            "dossier_contains_claim": any(
                x.get("claim_id") == str(claim_id)
                for x in (dossier.get("snapshot") or {}).get("claims", [])
            ),
            "support_review_completed": evidence_reviews["support"] is not None,
            "counter_review_completed": evidence_reviews["counter"] is not None,
            "claim_review_completed": claim_review is not None,
            "dossier_review_completed": dossier_review is not None,
            "export_review_completed": export_review is not None,
            "independent_reviewer_present": bool(reviewers) and creator not in reviewers,
            "export_execution_present": export_execution is not None,
            "export_executor_differs_from_approver": bool(
                export_execution and export_review
                and str(export_execution.get("executed_by") or "")
                != str(export_review.get("completed_by") or "")
            ),
            "physical_export_hashes_valid": export_files["valid"],
            "recovery_point_valid": bool(recovery.get("valid")),
            "recovery_did_not_overwrite_live_db": recovery.get("active_database_overwritten") is False,
            "real_infrastructure_facts_present": len(infra_facts) >= 1,
            "xref_candidates_present": len(xref_candidates) >= 1,
        }

        report = {
            "build": BUILD,
            "phase": 20,
            "hard_checkpoint": True,
            "checkpoint_name": "Full Operations / Real-Source Research Gate",
            "case_id": str(case_id),
            "engineering_checks": engineering_checks,
            "live_case_checks": live_checks,
            "support_evidence": {
                "evidence_id": support_evidence_id,
                "source_id": support["evidence"]["source_id"],
                "event_id": support["evidence"]["event_id"],
                "content_id": support["evidence"]["content_id"],
                "url": support["evidence"]["canonical_url"],
            },
            "counterevidence": {
                "evidence_id": counter_evidence_id,
                "source_id": counter["evidence"]["source_id"],
                "event_id": counter["evidence"]["event_id"],
                "content_id": counter["evidence"]["content_id"],
                "url": counter["evidence"]["canonical_url"],
            },
            "claim_id": str(claim_id),
            "revision_id": str(revision_id),
            "export_id": str(export_id),
            "package_hash": str(export.get("package_hash") or ""),
            "export_verification": export_files,
            "recovery_id": str(recovery_id),
            "infrastructure_fact_count": len(infra_facts),
            "xref_candidate_count": len(xref_candidates),
            "restart_verified": False,
            "all_connector_families_external_validation": "HOLD",
            "live_news_external_validation": "NOT_REQUIRED_FOR_THIS_BOUNDED_CASE",
            "public_social_external_validation": "NOT_REQUIRED_FOR_THIS_BOUNDED_CASE",
            "production_release_ready": False,
            "truth_determined": False,
        }

        engineering_result = "pass" if all(engineering_checks.values()) else "hold"
        live_case_result = "pass" if all(live_checks.values()) else "hold"
        overall = "hold"
        now = _now()
        row = {
            "qualification_id": "ops455_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "support_evidence_id": str(support_evidence_id),
            "counter_evidence_id": str(counter_evidence_id),
            "claim_id": str(claim_id),
            "revision_id": str(revision_id),
            "export_id": str(export_id),
            "recovery_id": str(recovery_id),
            "engineering_result": engineering_result,
            "live_case_result": live_case_result,
            "restart_result": "hold",
            "overall_result": overall,
            "report_json": _canon(report),
            "created_by": str(ident["username"]),
            "created_at": now,
            "updated_at": now,
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_operational_qualification_run_455 VALUES("
            + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "full_operations_qualification_recorded_455",
            "phase20_operational_qualification_run_455",
            row["qualification_id"],
            str(case_id),
            {
                "engineering_result": engineering_result,
                "live_case_result": live_case_result,
                "restart_result": "hold",
                "overall_result": overall,
            },
        )
        return {**row, "report": report}

    def _run(self, qualification_id):
        row = self.db.one(
            "SELECT * FROM phase20_operational_qualification_run_455 WHERE qualification_id=?",
            (str(qualification_id),),
        )
        if not row:
            raise KeyError("Build-455 qualification not found")
        item = dict(row)
        item["report"] = json.loads(item.pop("report_json"))
        return item

    def verify_after_restart(self, *, identity, qualification_id):
        run = self._run(qualification_id)
        ident = self._authorize(identity, run["case_id"], admin=True)

        support = self._evidence_chain(run["support_evidence_id"], run["case_id"])
        counter = self._evidence_chain(run["counter_evidence_id"], run["case_id"])
        claim = self.closure447.claim(run["claim_id"])
        dossier = self.closure447.dossier(run["revision_id"])
        export = next(
            (x for x in self.closure447.exports(run["case_id"]) if x["export_id"] == run["export_id"]),
            None,
        )
        recovery = self.recovery453.verify(run["recovery_id"])
        export_files = self._verify_export_files(export or {})
        integrity = self.verify_integrity()

        checks = {
            "qualification_record_integrity": bool(integrity["valid"]),
            "support_reference_reopens": support["evidence"]["evidence_id"] == run["support_evidence_id"],
            "counter_reference_reopens": counter["evidence"]["evidence_id"] == run["counter_evidence_id"],
            "claim_reference_reopens": claim["claim_id"] == run["claim_id"],
            "dossier_reference_reopens": dossier["revision_id"] == run["revision_id"],
            "export_reference_reopens": bool(export and export["export_id"] == run["export_id"]),
            "physical_export_hashes_still_valid": export_files["valid"],
            "recovery_still_valid": bool(recovery.get("valid")),
            "acquisition_integrity": self.events422.verify_integrity()["valid"],
            "content_integrity": self.content423.verify_integrity()["valid"],
            "dossier_integrity": self.closure447.verify_integrity()["valid"],
            "review_integrity": self.review449.verify_integrity()["valid"],
            "infrastructure_integrity": self.infrastructure454.verify_integrity()["valid"],
            "xref_integrity": self.xref454.verify_integrity()["valid"],
        }
        passed = all(checks.values())

        restart = {
            "restart_id": "restart455_" + secrets.token_hex(10),
            "qualification_id": str(qualification_id),
            "case_id": run["case_id"],
            "verification_json": _canon(checks),
            "verified_by": str(ident["username"]),
            "verified_at": _now(),
        }
        restart["record_hash"] = self._rh(restart)
        self.db.execute(
            "INSERT INTO phase20_operational_restart_455 VALUES(?,?,?,?,?,?,?)",
            tuple(restart.values()),
        )

        raw = self.db.one(
            "SELECT * FROM phase20_operational_qualification_run_455 WHERE qualification_id=?",
            (str(qualification_id),),
        )
        updated = dict(raw)
        report = json.loads(updated["report_json"])
        report["restart_verified"] = passed
        report["restart_checks"] = checks
        updated["restart_result"] = "pass" if passed else "hold"
        updated["overall_result"] = (
            "pass"
            if passed and updated["engineering_result"] == "pass" and updated["live_case_result"] == "pass"
            else "hold"
        )
        updated["report_json"] = _canon(report)
        updated["updated_at"] = _now()
        updated["record_hash"] = self._rh(updated)
        self.db.execute(
            "UPDATE phase20_operational_qualification_run_455 SET restart_result=?,overall_result=?,"
            "report_json=?,updated_at=?,record_hash=? WHERE qualification_id=?",
            (
                updated["restart_result"], updated["overall_result"], updated["report_json"],
                updated["updated_at"], updated["record_hash"], str(qualification_id),
            ),
        )
        self.audit.log(
            "full_operations_restart_verified_455",
            "phase20_operational_restart_455",
            restart["restart_id"],
            run["case_id"],
            {"passed": passed, "overall_result": updated["overall_result"]},
        )
        return {
            "build": BUILD,
            "qualification_id": str(qualification_id),
            "restart_result": updated["restart_result"],
            "overall_result": updated["overall_result"],
            "checks": checks,
            "production_release_ready": False,
        }

    def latest(self, case_id=""):
        if case_id:
            row = self.db.one(
                "SELECT qualification_id FROM phase20_operational_qualification_run_455 "
                "WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (str(case_id),)
            )
        else:
            row = self.db.one(
                "SELECT qualification_id FROM phase20_operational_qualification_run_455 "
                "ORDER BY created_at DESC,rowid DESC LIMIT 1"
            )
        return self._run(row["qualification_id"]) if row else None

    def verify_integrity(self):
        bad = []
        for table, key in (
            ("phase20_operational_qualification_run_455", "qualification_id"),
            ("phase20_operational_restart_455", "restart_id"),
        ):
            for row in self.db.all("SELECT * FROM " + table):
                item = dict(row)
                if self._rh(item) != item["record_hash"]:
                    bad.append({key: item[key], "table": table, "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        last = self.latest()
        integrity = self.verify_integrity()
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "hard_checkpoint": True,
            "checkpoint_name": "Full Operations / Real-Source Research Gate",
            "integrity_valid": integrity["valid"],
            "last_engineering_result": last["engineering_result"] if last else None,
            "last_live_case_result": last["live_case_result"] if last else None,
            "last_restart_result": last["restart_result"] if last else None,
            "operational_research_gate_pass": bool(last and last["overall_result"] == "pass" and integrity["valid"]),
            "requires_real_nonfixture_public_sources": True,
            "requires_support_and_counterevidence": True,
            "requires_independent_review": True,
            "requires_physical_export_hash_verification": True,
            "requires_recovery_verification": True,
            "requires_restart_reference_verification": True,
            "all_connector_families_external_validation": False,
            "production_release_ready": False,
            "automatic_truth_determination": False,
        }
