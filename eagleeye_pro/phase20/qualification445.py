from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets

BUILD = "445.0"
POLICY_ID = "phase20.data-acquisition-hard-checkpoint.v445"

REQUIRED = (
    "registry421",
    "events422",
    "content423",
    "health424",
    "crawler425",
    "surface441",
    "hardening442",
    "news443",
    "social444",
    "news429",
    "provenance431",
    "social432",
    "loop439",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class DataAcquisitionHardCheckpoint445:
    """Fail-closed Phase-20 acquisition qualification.

    Build 445 separates four statements that must never be conflated:
    implementation, deterministic qualification, external validation and
    production readiness. Deterministic replay can prove engineering coherence,
    but it cannot certify that live public endpoints work in the field.
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
            """CREATE TABLE IF NOT EXISTS phase20_data_qualification_run_445(
            qualification_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            engineering_result TEXT NOT NULL,
            external_result TEXT NOT NULL,
            overall_result TEXT NOT NULL,
            report_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_phase20_qual445_case
            ON phase20_data_qualification_run_445(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _auth(self, identity):
        if not isinstance(identity, dict):
            raise PermissionError("system administrator required for Build-445 qualification")
        roles = {str(x).lower() for x in (identity.get("roles") or [])}
        for key in ("role", "global_role"):
            if identity.get(key):
                roles.add(str(identity[key]).lower())
        if not ({"admin", "administrator", "owner", "system_administrator"} & roles):
            raise PermissionError("system administrator required for Build-445 qualification")

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

    def _status_matrix(self):
        s441 = self.services["surface441"].status()
        s442 = self.services["hardening442"].status()
        s443 = self.services["news443"].status()
        s444 = self.services["social444"].status()
        s439 = self.services["loop439"].status()
        return {
            "surface": {
                "implemented": bool(s441.get("controlled_surface_network_executor")),
                "public_get": bool(s441.get("live_public_http_get")),
                "robots_fail_closed": bool(s441.get("robots_required_fail_closed")),
                "dns_ip_pinning": bool(s441.get("dns_ip_pinning")),
                "exact_host_scope": bool(s441.get("exact_registered_host_only")),
                "authenticated_sources_supported": bool(s441.get("authenticated_sources_supported")),
            },
            "hardening": {
                "implemented": bool(s442.get("surface441_boundary_retained")),
                "dns_rebinding_defense": bool(s442.get("dns_rebinding_defense")),
                "bounded_retry": bool(s442.get("bounded_retry")),
                "per_source_rate_limit": bool(s442.get("per_source_rate_limit")),
                "process_isolation": bool(s442.get("process_isolation")),
                "os_sandbox_qualified": bool(s442.get("os_sandbox_qualified")),
                "malware_scanner_qualified": bool(s442.get("malware_scanner_qualified")),
            },
            "news": {
                "implemented": bool(s443.get("live_news_acquisition")),
                "public_sources_only": bool(s443.get("public_sources_only")),
                "raw_feed_persisted": bool(s443.get("raw_feed_persisted")),
                "automatic_semantic_extraction_430": bool(s443.get("automatic_semantic_extraction_430")),
                "article_body_fetch": bool(s443.get("article_body_fetch")),
            },
            "social": {
                "implemented": bool(s444.get("controlled_public_social_acquisition")),
                "public_sources_only": bool(s444.get("public_sources_only")),
                "automatic_pagination": bool(s444.get("automatic_pagination")),
                "social_graph_enumeration": bool(s444.get("social_graph_enumeration")),
                "private_or_direct_content_supported": bool(s444.get("private_or_direct_content_supported")),
                "raw_endpoint_response_persisted": bool(s444.get("raw_endpoint_response_persisted")),
            },
            "ai_investigation_loop": {
                "implemented": True,
                "explicit_human_go_required": bool(s439.get("explicit_human_go_required")),
                "direct_network_authority": bool(s439.get("direct_network_authority")),
                "external_retrieval_adapter_required": bool(s439.get("external_retrieval_adapter_required")),
                "specialized_news_social_dispatch_implemented": False,
            },
        }

    def _authority_contract(self):
        statuses = {}
        for name in ("surface441", "hardening442", "news443", "social444", "loop439"):
            service = self.services[name]
            statuses[name] = service.status() if hasattr(service, "status") else {}

        forbidden_true = []
        forbidden_keys = (
            "automatic_go",
            "automatic_go_issuance",
            "automatic_live_execution",
            "automatic_scope_expansion",
            "autonomous_scope_expansion",
            "automatic_evidence_promotion",
            "truth_determined",
            "truth_determination",
            "access_control_bypass",
            "access_control_bypass_supported",
            "private_or_direct_content_supported",
            "social_graph_enumeration",
            "follower_following_enumeration",
            "messaging_supported",
        )
        for name, status in statuses.items():
            for key in forbidden_keys:
                if status.get(key) is True:
                    forbidden_true.append({"component": name, "field": key})

        return {
            "forbidden_true": forbidden_true,
            "pass": not forbidden_true,
            "explicit_live_confirmations": {
                "surface": "SURFACE442_LIVE",
                "news": "NEWS443_LIVE",
                "social": "SOCIAL444_LIVE",
            },
            "automatic_live_execution": False,
            "automatic_scope_expansion": False,
        }

    def _run_selftest(self, name, *, identity, case_id):
        service = self.services[name]
        try:
            result = service.run_case_selftest(identity=identity, case_id=case_id)
        except Exception as exc:
            return {
                "build": getattr(service, "BUILD", name),
                "case_id": str(case_id),
                "result": "FAIL",
                "error": type(exc).__name__,
            }
        return result

    def _deterministic_qualification(self, *, identity, case_id):
        surface = self._run_selftest("surface441", identity=identity, case_id=case_id)
        hardening = self._run_selftest("hardening442", identity=identity, case_id=case_id)
        news = self._run_selftest("news443", identity=identity, case_id=case_id)
        social = self._run_selftest("social444", identity=identity, case_id=case_id)
        results = {
            "surface441": surface,
            "hardening442": hardening,
            "news443": news,
            "social444": social,
        }
        return {
            "results": results,
            "all_pass": all(x.get("result") == "PASS" for x in results.values()),
            "external_network_used": False,
        }

    def _nonfixture_source(self, source_id):
        try:
            source = self.services["registry421"].get(str(source_id))
        except Exception:
            return False
        return not bool((source.get("coverage") or {}).get("fixture_only"))

    def _external_evidence(self):
        surface_rows = self.db.all(
            "SELECT hardening_run_id,source_id,task_id,case_id,completed_at "
            "FROM surface_hardening_run_442 "
            "WHERE external_validation=1 AND state='completed' "
            "ORDER BY rowid DESC"
        )
        news_rows = self.db.all(
            "SELECT run_id,source_id,task_id,case_id,created_at "
            "FROM news_acquisition_run_443 "
            "WHERE external_network=1 AND ingested_items>0 "
            "ORDER BY rowid DESC"
        )
        social_rows = self.db.all(
            "SELECT run_id,source_id,task_id,case_id,created_at "
            "FROM social_acquisition_run_444 "
            "WHERE external_network=1 AND ingested_objects>0 "
            "ORDER BY rowid DESC"
        )

        def valid(rows, id_field):
            out = []
            seen = set()
            for row in rows:
                d = dict(row)
                if not self._nonfixture_source(d["source_id"]):
                    continue
                key = str(d["source_id"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "evidence_id": str(d[id_field]),
                        "source_id": key,
                        "task_id": str(d["task_id"]),
                        "case_id": str(d["case_id"]),
                        "timestamp": str(d.get("completed_at") or d.get("created_at") or ""),
                    }
                )
            return out

        surface = valid(surface_rows, "hardening_run_id")
        news = valid(news_rows, "run_id")
        social = valid(social_rows, "run_id")
        paths = {
            "surface": {
                "validated": bool(surface),
                "nonfixture_source_count": len(surface),
                "evidence": surface[:10],
            },
            "news": {
                "validated": bool(news),
                "nonfixture_source_count": len(news),
                "evidence": news[:10],
            },
            "social": {
                "validated": bool(social),
                "nonfixture_source_count": len(social),
                "evidence": social[:10],
            },
        }
        return {
            "paths": paths,
            "all_three_paths_externally_validated": all(x["validated"] for x in paths.values()),
            "fixture_runs_do_not_count": True,
            "ci_replay_does_not_count": True,
        }

    def _provenance_snapshot(self, case_id):
        tables = {
            "acquisition_events_422": "acquisition_event_422",
            "content_observations_423": "content_observation_423",
            "crawl_tasks_425": "crawl_task_425",
            "news_items_429": "news_item_429",
            "social_observations_432": "social_observation_432",
        }
        counts = {}
        for key, table in tables.items():
            counts[key] = int(
                self.db.one(
                    f"SELECT COUNT(*) n FROM {table} WHERE case_id=?",
                    (str(case_id),),
                )["n"]
            )
        return counts

    def qualify(self, *, identity, case_id):
        self._auth(identity)
        case_id = str(case_id or "").strip()
        if not case_id:
            raise ValueError("dedicated Build-445 qualification case_id required")

        pre_component_checks, pre_component_details = self._component_integrity()
        matrix = self._status_matrix()
        authority = self._authority_contract()
        before = self._provenance_snapshot(case_id)
        deterministic = self._deterministic_qualification(identity=identity, case_id=case_id)
        after = self._provenance_snapshot(case_id)
        component_checks, component_details = self._component_integrity()
        external = self._external_evidence()

        capability_checks = {
            "surface_executor_present": matrix["surface"]["implemented"],
            "surface_public_get_present": matrix["surface"]["public_get"],
            "surface_robots_fail_closed": matrix["surface"]["robots_fail_closed"],
            "surface_dns_pinning_present": matrix["surface"]["dns_ip_pinning"],
            "surface_auth_not_supported": matrix["surface"]["authenticated_sources_supported"] is False,
            "hardening_dns_rebinding_present": matrix["hardening"]["dns_rebinding_defense"],
            "hardening_retry_present": matrix["hardening"]["bounded_retry"],
            "hardening_rate_limit_present": matrix["hardening"]["per_source_rate_limit"],
            "news_live_path_present": matrix["news"]["implemented"],
            "news_public_only": matrix["news"]["public_sources_only"],
            "news_raw_feed_not_persisted": matrix["news"]["raw_feed_persisted"] is False,
            "news_semantic_claims_not_fabricated": matrix["news"]["automatic_semantic_extraction_430"] is False,
            "social_live_path_present": matrix["social"]["implemented"],
            "social_public_only": matrix["social"]["public_sources_only"],
            "social_no_automatic_pagination": matrix["social"]["automatic_pagination"] is False,
            "social_no_graph_enumeration": matrix["social"]["social_graph_enumeration"] is False,
            "social_no_private_direct": matrix["social"]["private_or_direct_content_supported"] is False,
        }

        provenance_checks = {
            "events_created": after["acquisition_events_422"] > before["acquisition_events_422"],
            "content_observations_created": after["content_observations_423"] > before["content_observations_423"],
            "crawl_tasks_created": after["crawl_tasks_425"] > before["crawl_tasks_425"],
            "news_items_created": after["news_items_429"] > before["news_items_429"],
            "social_observations_created": after["social_observations_432"] > before["social_observations_432"],
        }

        engineering_checks = {
            "all_required_component_integrity_before": all(pre_component_checks.get(x, False) for x in self.REQUIRED),
            "all_required_component_integrity_after": all(component_checks.get(x, False) for x in self.REQUIRED),
            "all_deterministic_acquisition_selftests_pass": deterministic["all_pass"],
            "capability_contract_pass": all(capability_checks.values()),
            "authority_contract_pass": authority["pass"],
            "provenance_chain_observed": all(provenance_checks.values()),
            "deterministic_qualification_used_no_external_network": deterministic["external_network_used"] is False,
        }
        engineering_result = "pass" if all(engineering_checks.values()) else "fail"
        external_result = "pass" if external["all_three_paths_externally_validated"] else "hold"

        unresolved = []
        for path, detail in external["paths"].items():
            if not detail["validated"]:
                unresolved.append(f"{path}_external_nonfixture_validation_missing")
        if not matrix["ai_investigation_loop"]["specialized_news_social_dispatch_implemented"]:
            unresolved.append("build439_specialized_news_social_adapter_dispatch_not_implemented")
        if matrix["hardening"]["process_isolation"] is False:
            unresolved.append("retrieval_process_isolation_not_implemented")
        if not matrix["hardening"]["os_sandbox_qualified"]:
            unresolved.append("retrieval_os_sandbox_not_qualified")
        if not matrix["hardening"]["malware_scanner_qualified"]:
            unresolved.append("retrieval_malware_scanner_not_qualified")

        if engineering_result == "fail":
            overall_result = "fail"
        elif external_result == "pass":
            overall_result = "pass"
        else:
            overall_result = "hold"

        report = {
            "build": BUILD,
            "phase": 20,
            "hard_checkpoint": True,
            "checkpoint_name": "Data Acquisition Hard Checkpoint",
            "phase20_builds_completed": 5,
            "pre_component_checks": pre_component_checks,
            "pre_component_details": pre_component_details,
            "component_checks": component_checks,
            "component_details": component_details,
            "capability_matrix": matrix,
            "capability_checks": capability_checks,
            "authority_contract": authority,
            "provenance_before": before,
            "provenance_after": after,
            "provenance_checks": provenance_checks,
            "deterministic_qualification": deterministic,
            "external_validation": external,
            "engineering_checks": engineering_checks,
            "engineering_result": engineering_result,
            "external_result": external_result,
            "qualification_result": overall_result,
            "data_acquisition_gate_pass": overall_result == "pass",
            "engineering_acquisition_stack_qualified": engineering_result == "pass",
            "real_world_three_path_validation_complete": external_result == "pass",
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "known_unresolved_items": unresolved,
            "next_build": "446.0",
            "next_hard_checkpoint": "450.0",
            "next_priority": (
                "Build 446 should route human-authorized AI investigation collection tasks "
                "into the specialized Surface/News/Public-Social execution adapters while "
                "preserving separate per-path live authorization and the Build-445 gate evidence."
            ),
            "note": (
                "A deterministic PASS proves the acquisition engineering chain, not real-world "
                "endpoint coverage. Build 445 remains HOLD until each core public acquisition "
                "path has at least one successful non-fixture external validation."
            ),
        }

        qid = "qual445_" + secrets.token_hex(10)
        row = {
            "qualification_id": qid,
            "case_id": case_id,
            "engineering_result": engineering_result,
            "external_result": external_result,
            "overall_result": overall_result,
            "report_json": _canon(report),
            "created_by": str(identity.get("user_id") or identity.get("username") or self.actor),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase20_data_qualification_run_445 VALUES(?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        self.audit.log(
            "phase20_data_hard_checkpoint_445",
            "phase20_data_qualification_run_445",
            qid,
            case_id,
            {
                "engineering_result": engineering_result,
                "external_result": external_result,
                "overall_result": overall_result,
                "production_release_ready": False,
            },
        )
        return {**row, "report": report}

    def latest(self, case_id=""):
        if case_id:
            row = self.db.one(
                "SELECT * FROM phase20_data_qualification_run_445 "
                "WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
                (str(case_id),),
            )
        else:
            row = self.db.one(
                "SELECT * FROM phase20_data_qualification_run_445 ORDER BY rowid DESC LIMIT 1"
            )
        if not row:
            return None
        out = dict(row)
        out["report"] = json.loads(out["report_json"])
        return out

    def verify_integrity(self):
        bad = []
        for row in self.db.all("SELECT * FROM phase20_data_qualification_run_445"):
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
        external = self._external_evidence()
        integrity = self.verify_integrity()["valid"]
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "hard_checkpoint": True,
            "checkpoint_name": "Data Acquisition Hard Checkpoint",
            "phase": 20,
            "phase20_builds_completed": 5,
            "qualification_fail_closed": True,
            "admin_qualification_required": True,
            "case_specific_deterministic_qualification_required": True,
            "component_integrity_required": True,
            "external_nonfixture_validation_required_for_gate_pass": True,
            "surface_external_validation_present": external["paths"]["surface"]["validated"],
            "news_external_validation_present": external["paths"]["news"]["validated"],
            "social_external_validation_present": external["paths"]["social"]["validated"],
            "all_three_paths_externally_validated": external["all_three_paths_externally_validated"],
            "integrity_valid": integrity,
            "last_engineering_result": last["engineering_result"] if last else None,
            "last_external_result": last["external_result"] if last else None,
            "last_qualification_result": last["overall_result"] if last else None,
            "data_acquisition_gate_pass": bool(
                integrity and last and last["overall_result"] == "pass"
            ),
            "engineering_acquisition_stack_qualified": bool(
                integrity and last and last["engineering_result"] == "pass"
            ),
            "build439_specialized_news_social_dispatch_implemented": False,
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "446.0",
            "next_hard_checkpoint": "450.0",
        }
