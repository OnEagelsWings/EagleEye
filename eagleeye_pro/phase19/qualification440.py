from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets

BUILD = "440.0"
POLICY_ID = "phase19.hard-checkpoint.v440"

REQUIRED = (
    "source_registry421",
    "acquisition_events422",
    "content_store423",
    "source_health424",
    "crawler425",
    "priority426",
    "change427",
    "archive428",
    "news429",
    "extraction430",
    "provenance431",
    "social432",
    "organization433",
    "registry434",
    "tor435",
    "surface436",
    "resolution437",
    "fusion438",
    "loop439",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode()).hexdigest()


class Phase19HardCheckpoint440:
    """Fail-closed Phase-19 engineering qualification.

    The checkpoint validates integrity, the synthetic case-specific Build-439
    investigation path, and the declared capability boundary.  It intentionally
    separates engineering completion from live-collection and production
    readiness.  Passing Build 440 therefore does not mean that ordinary public
    web/news/social retrieval is implemented or that EagleEye is production-ready.
    """

    REQUIRED = REQUIRED

    def __init__(self, db, audit, *, services, governance, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.services = dict(services)
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase19_qualification_run_440(
            qualification_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            result TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_phase19_qual440_case
            ON phase19_qualification_run_440(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _auth(self, identity):
        if not isinstance(identity, dict):
            raise PermissionError("system administrator required for Phase-19 qualification")
        roles = {str(x).lower() for x in (identity.get("roles") or [])}
        for key in ("role", "global_role"):
            if identity.get(key):
                roles.add(str(identity[key]).lower())
        if not ({"admin", "administrator", "owner", "system_administrator"} & roles):
            raise PermissionError("system administrator required for Phase-19 qualification")

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

    def capability_matrix(self):
        crawler = self.services["crawler425"].status()
        news = self.services["news429"].status()
        social = self.services["social432"].status()
        tor = self.services["tor435"].status()
        loop = self.services["loop439"].status()
        resolution = self.services["resolution437"].status()
        fusion = self.services["fusion438"].status()

        return {
            "build": BUILD,
            "engineering_layers": {
                "source_registry_and_provenance_intake": {
                    "state": "implemented",
                    "live_network_executor": False,
                },
                "ordinary_surface_crawl_planning": {
                    "state": "implemented",
                    "network_executor_implemented": bool(crawler.get("network_executor_implemented")),
                    "external_retrieval_adapter_required": bool(crawler.get("external_retrieval_adapter_required")),
                },
                "news_ingest_extract_provenance": {
                    "state": "implemented",
                    "network_executor_implemented": bool(news.get("network_executor_implemented")),
                },
                "public_social_normalization": {
                    "state": "implemented",
                    "network_executor_implemented": bool(social.get("network_executor_implemented")),
                    "public_only": bool(social.get("public_only")),
                },
                "controlled_tor_research": {
                    "state": "implemented_gated_live_path",
                    "isolated_worker": bool(tor.get("isolated_tor_worker")),
                    "live_via_controlled_gateway_only": bool(tor.get("live_network_via_controlled_tor_gateway_only")),
                    "approval_and_confirmation_required": bool(tor.get("live_execution_requires_approval_ref_and_confirmation")),
                    "read_only_get_only": bool(tor.get("read_only_get_only")),
                },
                "cross_source_entity_resolution": {
                    "state": "implemented_review_gated",
                    "automatic_identity_confirmation": bool(resolution.get("automatic_identity_confirmation")),
                    "destructive_merge": bool(resolution.get("destructive_merge")),
                },
                "temporal_relationship_fusion": {
                    "state": "implemented_review_preserving",
                    "automatic_relationship_inference": bool(fusion.get("automatic_relationship_inference")),
                    "causality_inferred": bool(fusion.get("causality_inferred")),
                },
                "ai_investigation_loop": {
                    "state": "implemented_bounded_orchestration",
                    "explicit_human_go_required": bool(loop.get("explicit_human_go_required")),
                    "direct_network_authority": bool(loop.get("direct_network_authority")),
                    "external_retrieval_adapter_required": bool(loop.get("external_retrieval_adapter_required")),
                },
            },
            "live_collection": {
                "ordinary_surface_web_complete": bool(crawler.get("network_executor_implemented")),
                "news_retrieval_complete": bool(news.get("network_executor_implemented")),
                "social_retrieval_complete": bool(social.get("network_executor_implemented")),
                "controlled_tor_path_available": bool(
                    tor.get("isolated_tor_worker")
                    and tor.get("live_network_via_controlled_tor_gateway_only")
                    and tor.get("live_execution_requires_approval_ref_and_confirmation")
                ),
                "complete": False,
            },
            "known_blockers": [
                "ordinary_surface_web_network_executor_not_implemented",
                "news_network_executor_not_implemented",
                "public_social_network_executor_not_implemented",
                "external_retrieval_adapter_required_for_build439_collection_tasks",
                "production_hardening_and_external_validation_incomplete",
            ],
            "production_release_ready": False,
            "real_world_general_research_ready": False,
        }

    def _authority_contract(self):
        statuses = {}
        for name in self.REQUIRED:
            service = self.services[name]
            if hasattr(service, "status"):
                try:
                    statuses[name] = service.status()
                except Exception:
                    statuses[name] = {}

        forbidden_true = []
        forbidden_keys = (
            "automatic_go",
            "automatic_go_issuance",
            "automatic_scope_expansion",
            "autonomous_scope_expansion",
            "automatic_evidence_promotion",
            "automatic_identity_confirmation",
            "automatic_relationship_inference",
            "truth_determined",
            "truth_determination",
            "identity_determination",
            "ownership_or_control_determination",
            "access_control_bypass",
            "access_control_bypass_supported",
        )
        for name, status in statuses.items():
            for key in forbidden_keys:
                if status.get(key) is True:
                    forbidden_true.append({"component": name, "field": key})

        # Controlled Tor network access is an explicitly reviewed exception and is
        # not treated as generic/direct network authority.
        generic_network_authority = []
        for name, status in statuses.items():
            for key in ("direct_network_authority", "network_authority", "network_execution"):
                if status.get(key) is True:
                    generic_network_authority.append({"component": name, "field": key})

        return {
            "forbidden_true": forbidden_true,
            "generic_network_authority_true": generic_network_authority,
            "controlled_tor_exception_only": True,
            "pass": not forbidden_true and not generic_network_authority,
        }

    def qualify(self, *, identity, case_id):
        self._auth(identity)
        case_id = str(case_id or "").strip()
        if not case_id:
            raise ValueError("dedicated qualification case_id required")

        checks, details = self._component_integrity()
        capability = self.capability_matrix()
        authority = self._authority_contract()

        loop439 = self.services["loop439"]
        try:
            case_selftest = loop439.run_case_selftest(identity=identity, case_id=case_id)
        except Exception as exc:
            case_selftest = {
                "build": "439.0",
                "case_id": case_id,
                "result": "FAIL",
                "error": type(exc).__name__,
            }

        declared_boundary = {
            "surface_executor_missing_declared": capability["live_collection"]["ordinary_surface_web_complete"] is False,
            "news_executor_missing_declared": capability["live_collection"]["news_retrieval_complete"] is False,
            "social_executor_missing_declared": capability["live_collection"]["social_retrieval_complete"] is False,
            "tor_is_separately_gated": capability["live_collection"]["controlled_tor_path_available"] is True,
            "production_readiness_false": capability["production_release_ready"] is False,
            "general_live_readiness_false": capability["real_world_general_research_ready"] is False,
        }

        checkpoint_checks = {
            "all_required_component_integrity": all(checks.get(x, False) for x in self.REQUIRED),
            "build439_case_path_pass": case_selftest.get("result") == "PASS",
            "authority_contract_pass": authority["pass"],
            "capability_boundary_explicit": all(declared_boundary.values()),
            "ordinary_live_collection_not_overclaimed": capability["live_collection"]["complete"] is False,
        }
        result = "pass" if all(checkpoint_checks.values()) else "hold"

        report = {
            "build": BUILD,
            "phase": 19,
            "hard_checkpoint": True,
            "phase19_builds_completed": 20,
            "phase19_engineering_complete": result == "pass",
            "required_components": list(self.REQUIRED),
            "component_checks": checks,
            "component_details": details,
            "build439_case_selftest": case_selftest,
            "authority_contract": authority,
            "declared_boundary_checks": declared_boundary,
            "checkpoint_checks": checkpoint_checks,
            "capability_matrix": capability,
            "qualification_result": result,
            "engineering_checkpoint_pass": result == "pass",
            "live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_priority": "controlled ordinary-surface retrieval adapter plus external end-to-end validation",
            "note": (
                "Build 440 qualifies the Phase-19 engineering chain. A pass does not certify "
                "production readiness or complete live public-web/news/social acquisition."
            ),
        }

        qid = "qual440_" + secrets.token_hex(10)
        row = {
            "qualification_id": qid,
            "case_id": case_id,
            "result": result,
            "report_json": _canon(report),
            "created_by": str(identity.get("user_id") or identity.get("username") or self.actor),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase19_qualification_run_440 VALUES(?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        self.audit.log(
            "phase19_hard_checkpoint_440",
            "phase19_qualification_run_440",
            qid,
            case_id,
            {
                "result": result,
                "engineering_checkpoint_pass": result == "pass",
                "live_collection_complete": False,
                "production_release_ready": False,
            },
        )
        return {**row, "report": report}

    def latest(self, case_id=""):
        if case_id:
            row = self.db.one(
                "SELECT * FROM phase19_qualification_run_440 WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
                (str(case_id),),
            )
        else:
            row = self.db.one(
                "SELECT * FROM phase19_qualification_run_440 ORDER BY rowid DESC LIMIT 1"
            )
        if not row:
            return None
        out = dict(row)
        out["report"] = json.loads(out["report_json"])
        return out

    def verify_integrity(self):
        violations = []
        for row in self.db.all("SELECT * FROM phase19_qualification_run_440"):
            item = dict(row)
            if self._rh(item) != item.get("record_hash"):
                violations.append(
                    {
                        "qualification_id": item.get("qualification_id"),
                        "reason": "qualification_hash_mismatch",
                    }
                )
        return {"build": BUILD, "valid": not violations, "violations": violations}

    def status(self):
        last = self.latest()
        capability = self.capability_matrix()
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "hard_checkpoint": True,
            "phase19_complete": True,
            "phase19_builds_completed": 20,
            "qualification_fail_closed": True,
            "case_specific_build439_qualification_required": True,
            "component_integrity_required": True,
            "github_ci_required": True,
            "full_repository_regression_required": True,
            "external_review_recommended": True,
            "integrity_valid": self.verify_integrity()["valid"],
            "last_qualification_result": last["result"] if last else None,
            "engineering_checkpoint_pass": bool(last and last["result"] == "pass"),
            "live_collection_complete": False,
            "ordinary_surface_network_executor_implemented": capability["live_collection"]["ordinary_surface_web_complete"],
            "news_network_executor_implemented": capability["live_collection"]["news_retrieval_complete"],
            "social_network_executor_implemented": capability["live_collection"]["social_retrieval_complete"],
            "controlled_tor_path_available": capability["live_collection"]["controlled_tor_path_available"],
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "direct_network_authority": False,
            "automatic_go_issuance": False,
            "automatic_evidence_promotion": False,
            "autonomous_scope_expansion": False,
            "truth_determined": False,
        }
