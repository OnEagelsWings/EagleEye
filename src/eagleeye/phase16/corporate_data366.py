from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from eagleeye.connectors.sdk import OFFICIAL_CONNECTORS
from eagleeye.crawler.engine import CrawlTransport, StaticTransport, UrllibReadOnlyTransport

POLICY = "phase16.corporate-live-data.v366"
AI_POLICY = "phase16.autonomous-investigation.v366"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v366"
LIVE_CONNECTORS = {"gleif_lei_api_v1", "sec_edgar_submissions_v1"}
PLAN_ONLY_CONNECTORS = {"companies_house_company_v1"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


class CorporateLiveData366:
    """Governed live corporate-data execution over the consolidated Phase-15 stack.

    No new evidence, receipt or connector tables are introduced. Source approval,
    search capsules, crawler fetches, object hashes, parser runs and health events
    remain the canonical ledgers. Build 366 derives a receipt from those ledgers and
    can anchor its hash in the ordinary case audit log.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build365: Any,
        connector_sdk: Any,
        jobs: Any,
        crawler: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build365 = build365
        self.connector_sdk = connector_sdk
        self.jobs = jobs
        self.crawler = crawler
        self.governance = governance
        self.actor = actor

    def status(self) -> dict[str, Any]:
        receipts = self.db.one(
            "SELECT COUNT(*) c FROM audit_events WHERE action='CORPORATE366_RECEIPT'"
        ) or {"c": 0}
        return {
            "policy": POLICY,
            "live_public_connectors": sorted(LIVE_CONNECTORS),
            "plan_only_connectors": sorted(PLAN_ONLY_CONNECTORS),
            "explicit_live_confirmation_required": True,
            "human_source_review_required": True,
            "case_rbac_required": True,
            "read_only_transport": True,
            "automatic_external_connections": False,
            "authenticated_live_connectors": False,
            "credential_storage_added": False,
            "query_input_types": ["lei", "cik"],
            "person_name_live_lookup_supported": False,
            "derived_receipt_audit_events": int(receipts.get("c") or 0),
            "new_per_build_data_tables": 0,
        }

    def connector_catalog(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        manifests = {row["connector_key"]: row for row in self.connector_sdk.manifests()}
        for key in sorted(OFFICIAL_CONNECTORS):
            spec = OFFICIAL_CONNECTORS[key]
            row = manifests.get(key, {})
            out.append({
                "connector_key": key,
                "display_name": spec["display_name"],
                "provider": spec["provider"],
                "jurisdiction": spec["jurisdiction"],
                "source_class": spec["source_class"],
                "auth_type": spec["auth_type"],
                "base_host": spec["base_host"],
                "parser_version": spec["parser_version"],
                "terms_ref": spec["terms_ref"],
                "manifest_status": row.get("status", "unknown"),
                "build366_live_eligible": key in LIVE_CONNECTORS and spec["auth_type"] == "none",
                "plan_only": key in PLAN_ONLY_CONNECTORS or spec["auth_type"] != "none",
                "requires_declared_user_agent": bool(spec.get("requires_declared_user_agent")),
                "automatic_live_fetch": False,
            })
        return out

    def source_plan(self, connector_key: str, identifier: str) -> dict[str, Any]:
        plan = dict(self.connector_sdk.source_plan(connector_key, identifier))
        spec = OFFICIAL_CONNECTORS[connector_key]
        plan.update({
            "build366_live_eligible": connector_key in LIVE_CONNECTORS and spec["auth_type"] == "none",
            "explicit_live_confirmation_required": True,
            "human_source_review_required": True,
            "case_rbac_required": True,
            "automatic_external_connection": False,
        })
        return plan

    def prepare_source(self, *, case_id: str, connector_key: str, identifier: str, identity: dict[str, Any]) -> dict[str, Any]:
        self.governance.authorize(identity, case_id=case_id, capability="research.run", object_type="corporate_connector", object_id=connector_key)
        plan = self.source_plan(connector_key, identifier)
        if connector_key not in LIVE_CONNECTORS:
            self.audit.log(
                "CORPORATE366_PLAN_ONLY",
                "corporate_connector",
                connector_key,
                case_id=case_id,
                details={"identifier_hash": _sha(str(identifier)), "auth_type": plan["auth_type"], "policy": POLICY},
            )
            return {"case_id": case_id, "plan": plan, "source": None, "state": "plan_only_auth_required"}
        spec = OFFICIAL_CONNECTORS[connector_key]
        ident = str(identifier).strip().upper() if connector_key == "gleif_lei_api_v1" else str(int(str(identifier).strip()))
        source_id = "src366_" + _sha({"connector_key": connector_key, "identifier": ident})[:20]
        locator = "corporate:" + connector_key + ":" + _sha(ident)[:24]
        source = self.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (source_id,))
        if not source:
            now = _now()
            source_body = {
                "source_id": source_id, "source_kind": "corporate_api", "locator": locator,
                "display_name": f"{spec['display_name']} · {ident}"[:240], "source_class": spec["source_class"],
                "jurisdiction": spec["jurisdiction"], "allowed_use": "public_read_only_corporate_data",
                "review_status": "pending_review", "risk_class": "standard",
                "provenance_json": _canon({"terms_ref": spec["terms_ref"], "official_ref": spec["official_ref"], "connector_key": connector_key, "registered_by": self.actor, "policy": POLICY}),
                "created_by": self.actor, "created_at": now, "updated_at": now,
            }
            self.db.execute("INSERT INTO phase15_sources(source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*source_body.values(), _sha(source_body)))
            policy = {
                "source_id": source_id, "seed_urls_json": _canon([plan["url"]]), "allowed_hosts_json": _canon([plan["host"]]),
                "terms_ref": spec["terms_ref"], "robots_mode": "respect_required", "auth_type": "none",
                "max_depth": 0, "max_pages": 1, "requests_per_minute": int(spec["requests_per_minute"]),
                "max_response_bytes": 5_000_000, "parser_version": spec["parser_version"], "enabled": 0, "source_health": "not_run",
                "created_at": now, "updated_at": now,
            }
            self.db.execute("INSERT INTO phase15_crawler_policies(source_id,seed_urls_json,allowed_hosts_json,terms_ref,robots_mode,auth_type,max_depth,max_pages,requests_per_minute,max_response_bytes,parser_version,enabled,source_health,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*policy.values(), _sha(policy)))
            link = {"source_id": source_id, "connector_key": connector_key, "identifier": ident, "created_at": now}
            self.db.execute("INSERT INTO phase15_connector_source_links(source_id,connector_key,identifier,created_at,record_hash) VALUES(?,?,?,?,?)", (*link.values(), _sha(link)))
            source = self.db.one("SELECT s.*,p.* FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?", (source_id,))
        self.audit.log(
            "CORPORATE366_SOURCE_PREPARED",
            "crawler_source",
            source["source_id"],
            case_id=case_id,
            details={"connector_key": connector_key, "identifier_hash": _sha(str(identifier)), "review_status": source["review_status"], "policy": POLICY},
        )
        return {"case_id": case_id, "plan": plan, "source": source, "state": "pending_source_review"}

    def _source_link(self, source_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT l.source_id,l.connector_key,l.identifier,m.provider,m.base_host,m.auth_type,m.parser_version,m.terms_ref,s.review_status,s.display_name,s.source_class,p.enabled,p.source_health "
            "FROM phase15_connector_source_links l JOIN phase15_connector_manifests m ON m.connector_key=l.connector_key "
            "JOIN phase15_sources s ON s.source_id=l.source_id JOIN phase15_crawler_policies p ON p.source_id=l.source_id WHERE l.source_id=?",
            (source_id,),
        )
        if not row:
            raise KeyError(source_id)
        return row

    def enqueue_live(self, *, case_id: str, source_id: str, identity: dict[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation).strip() != "LIVE":
            raise PermissionError("explicit confirmation LIVE required")
        self.governance.authorize(identity, case_id=case_id, capability="crawler.run", object_type="corporate_connector", object_id=source_id)
        link = self._source_link(source_id)
        if link["connector_key"] not in LIVE_CONNECTORS or link["auth_type"] != "none":
            raise PermissionError("connector is not eligible for Build-366 unauthenticated live execution")
        if link["review_status"] != "approved_read_only" or int(link["enabled"] or 0) != 1:
            raise PermissionError("human-reviewed approved source required")
        out = self.build365.enqueue_crawl(case_id=case_id, source_id=source_id)
        job_id = out["job"]["job_id"]
        payload = _json(out["job"].get("payload_json"), {})
        payload.update({
            "phase16_corporate_connector": link["connector_key"],
            "phase16_corporate_live_confirmation": True,
            "phase16_corporate_policy": POLICY,
        })
        self.db.execute(
            "UPDATE phase15_jobs SET payload_json=?,priority=?,updated_at=? WHERE job_id=?",
            (_canon(payload), min(int(out["job"].get("priority") or 80), 40), _now(), job_id),
        )
        self.audit.log(
            "CORPORATE366_LIVE_ENQUEUED",
            "job",
            job_id,
            case_id=case_id,
            details={"source_id": source_id, "connector_key": link["connector_key"], "explicit_live_confirmation": True, "policy": POLICY},
        )
        return {**out, "job": self.jobs.get(job_id), "connector": link, "explicit_live_confirmation": True}

    def _claim_specific(self, job_id: str, *, worker_id: str, lease_seconds: int = 300) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        now_s = now.isoformat(timespec="seconds")
        expiry = (now + timedelta(seconds=max(30, min(int(lease_seconds), 3600)))).isoformat(timespec="seconds")
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM phase15_jobs WHERE job_id=?", (job_id,))
            if not row:
                raise KeyError(job_id)
            if row["status"] != "queued" or str(row.get("available_at") or "") > now_s:
                raise PermissionError("corporate job must be queued and available")
            cur = self.db.execute(
                "UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'",
                (str(worker_id)[:120], expiry, now_s, job_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("corporate job claim race")
            self.db.execute(
                "INSERT INTO phase15_job_events(event_id,job_id,event_type,actor,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?)",
                (
                    "evt366_" + hashlib.sha256(f"{job_id}|{worker_id}|{now_s}".encode()).hexdigest()[:20],
                    job_id,
                    "claimed",
                    str(worker_id)[:120],
                    _canon({"worker_id": worker_id, "lease_expires_at": expiry, "policy": POLICY}),
                    now_s,
                    _sha({"job_id": job_id, "event_type": "claimed", "worker_id": worker_id, "lease_expires_at": expiry, "policy": POLICY}),
                ),
            )
        return self.jobs.get(job_id)

    def run_live_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        declared_user_agent: str = "",
        transport: CrawlTransport | None = None,
        resolver: Callable[[str], Sequence[str]] | None = None,
    ) -> dict[str, Any]:
        row = self.jobs.get(job_id)
        payload = _json(row.get("payload_json"), {})
        connector_key = str(payload.get("phase16_corporate_connector") or "")
        if connector_key not in LIVE_CONNECTORS or payload.get("phase16_corporate_live_confirmation") is not True:
            raise PermissionError("job is not an explicitly confirmed Build-366 corporate live job")
        source_id = str(payload.get("source_id") or "")
        link = self._source_link(source_id)
        if link["connector_key"] != connector_key:
            raise PermissionError("connector/source mismatch")
        ua = str(declared_user_agent or "").strip()
        if connector_key == "sec_edgar_submissions_v1":
            if len(ua) < 12 or "@" not in ua:
                raise PermissionError("SEC live execution requires a declared operator User-Agent containing contact information")
        if transport is None:
            transport = UrllibReadOnlyTransport(user_agent=ua or "EagleEye/366 corporate-data read-only")
        policy = self.connector_sdk.validate_transport_for_source(source_id, transport)
        if not policy.get("allowed"):
            raise PermissionError(str(policy.get("reason") or "connector transport denied"))
        if isinstance(transport, StaticTransport):
            # Replay is explicitly supported for deterministic tests but cannot ever
            # become an external-validation receipt.
            pass
        self._claim_specific(job_id, worker_id=worker_id)
        result = self.crawler.execute_claimed_job(job_id=job_id, worker_id=worker_id, transport=transport, resolver=resolver)
        crawl_run_id = str(payload.get("crawl_run_id") or "")
        post: dict[str, Any] = {}
        run = self.db.one("SELECT status FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,)) if crawl_run_id else None
        if run and run["status"] == "succeeded":
            post["parse"] = self.connector_sdk.parse_crawl_run(crawl_run_id)
            post["source_health"] = self.connector_sdk.record_source_health(source_id, crawl_run_id=crawl_run_id)
        receipt = self.receipt(crawl_run_id=crawl_run_id, anchor_audit=True) if crawl_run_id else {}
        return {"job": self.jobs.get(job_id), "crawler_result": result, "postprocess": post, "receipt": receipt}

    def receipt(self, *, crawl_run_id: str, anchor_audit: bool = False) -> dict[str, Any]:
        run = self.db.one(
            "SELECT r.*,s.display_name,s.review_status,s.source_class,l.connector_key,l.identifier,m.provider,m.base_host,m.auth_type,m.parser_version,m.terms_ref "
            "FROM phase15_crawl_runs r JOIN phase15_sources s ON s.source_id=r.source_id "
            "JOIN phase15_connector_source_links l ON l.source_id=r.source_id JOIN phase15_connector_manifests m ON m.connector_key=l.connector_key WHERE r.crawl_run_id=?",
            (crawl_run_id,),
        )
        if not run:
            raise KeyError(crawl_run_id)
        fetches = self.db.all("SELECT * FROM phase15_crawl_fetches WHERE crawl_run_id=? ORDER BY created_at", (crawl_run_id,))
        objects = self.db.all("SELECT object_id,sha256,size_bytes,media_type,security_state,record_hash,created_at FROM phase15_objects WHERE search_run_id=? AND source_id=? ORDER BY created_at", (run["search_run_id"], run["source_id"]))
        object_ids = [o["object_id"] for o in objects]
        parses: list[dict[str, Any]] = []
        for oid in object_ids:
            parses.extend(self.db.all("SELECT parse_run_id,object_id,source_id,parser_version,status,record_count,error_text,record_hash,created_at FROM phase15_parse_runs WHERE object_id=? ORDER BY created_at", (oid,)))
        review = self.db.one("SELECT decision,rationale,reviewer,created_at,record_hash FROM phase15_source_review_events WHERE source_id=? ORDER BY created_at DESC LIMIT 1", (run["source_id"],)) or {}
        summary = _json(run.get("summary_json"), {})
        stored_fetches = [f for f in fetches if f.get("object_id")]
        http_ok = bool(stored_fetches) and all(200 <= int(f.get("status_code") or 0) < 300 for f in stored_fetches)
        parser_ok = bool(parses) and all(p.get("status") == "parsed" for p in parses)
        transport_kind = str(summary.get("transport_kind") or "")
        external_transport = bool(summary.get("external_transport")) and transport_kind == "clearnet_urllib_explicit_v1"
        live_confirmed_job = self.db.one("SELECT payload_json FROM phase15_jobs WHERE case_id=? AND search_run_id=? AND job_type='governed_crawl_v1' ORDER BY created_at DESC LIMIT 1", (run["case_id"], run["search_run_id"])) or {}
        job_payload = _json(live_confirmed_job.get("payload_json"), {})
        explicit_live = job_payload.get("phase16_corporate_live_confirmation") is True and job_payload.get("phase16_corporate_connector") == run["connector_key"]
        externally_validated = bool(
            run["connector_key"] in LIVE_CONNECTORS
            and run["auth_type"] == "none"
            and run["review_status"] == "approved_read_only"
            and run["status"] == "succeeded"
            and explicit_live
            and external_transport
            and http_ok
            and parser_ok
        )
        body = {
            "policy": POLICY,
            "receipt_kind": "derived_canonical_ledger_receipt",
            "crawl_run_id": run["crawl_run_id"],
            "case_id": run["case_id"],
            "source_id": run["source_id"],
            "connector_key": run["connector_key"],
            "provider": run["provider"],
            "identifier": run["identifier"],
            "base_host": run["base_host"],
            "terms_ref": run["terms_ref"],
            "source_review": review,
            "crawl_status": run["status"],
            "transport_kind": transport_kind,
            "external_transport": external_transport,
            "explicit_live_confirmation": explicit_live,
            "fetches": [{k: f.get(k) for k in ("fetch_id","url","status_code","content_type","content_sha256","size_bytes","elapsed_ms","disposition","object_id","record_hash","created_at")} for f in fetches],
            "objects": objects,
            "parse_runs": parses,
            "http_success": http_ok,
            "parser_success": parser_ok,
            "externally_validated": externally_validated,
            "replay_or_fixture": transport_kind == "static_replay_v1" or not bool(summary.get("external_transport")),
            "production_release_ready": False,
        }
        receipt_hash = _sha(body)
        body["receipt_sha256"] = receipt_hash
        if anchor_audit:
            self.audit.log(
                "CORPORATE366_RECEIPT",
                "corporate_live_receipt",
                crawl_run_id,
                case_id=run["case_id"],
                details={"receipt_sha256": receipt_hash, "connector_key": run["connector_key"], "externally_validated": externally_validated, "policy": POLICY},
            )
        return body

    def receipts(self, *, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT r.crawl_run_id FROM phase15_crawl_runs r JOIN phase15_connector_source_links l ON l.source_id=r.source_id WHERE r.case_id=? ORDER BY r.created_at DESC LIMIT ?",
            (case_id, max(1, min(int(limit), 500))),
        )
        return [self.receipt(crawl_run_id=r["crawl_run_id"]) for r in rows]

    @staticmethod
    def _safe_org_record(record: Mapping[str, Any]) -> dict[str, Any]:
        # Addresses, EINs and person-linked fields remain in evidence artifacts but
        # are deliberately excluded from the AI's routine corporate context.
        allowed = {
            "entity_type", "lei", "legal_name", "entity_status", "registration_authority",
            "cik", "name", "entity_type_sec", "sic", "sic_description", "tickers", "exchanges",
            "company_number", "company_name", "company_status", "company_type", "jurisdiction", "date_of_creation",
        }
        out = {k: record.get(k) for k in allowed if record.get(k) not in (None, "", [], {})}
        if isinstance(record.get("recent_filings"), list):
            out["recent_filings"] = [
                {k: item.get(k) for k in ("form", "accession_number", "filing_date") if item.get(k)}
                for item in record["recent_filings"][:50] if isinstance(item, Mapping)
            ]
        return out

    def case_summary(self, *, case_id: str) -> dict[str, Any]:
        receipts = self.receipts(case_id=case_id, limit=200)
        rows = self.db.all(
            "SELECT p.normalized_json,p.parse_run_id,p.object_id,p.source_id,l.connector_key FROM phase15_parse_runs p "
            "JOIN phase15_objects o ON o.object_id=p.object_id JOIN phase15_connector_source_links l ON l.source_id=p.source_id "
            "WHERE o.case_id=? AND p.status='parsed' ORDER BY p.created_at DESC LIMIT 500",
            (case_id,),
        )
        records: list[dict[str, Any]] = []
        for row in rows:
            doc = _json(row.get("normalized_json"), {})
            for rec in doc.get("records", []) if isinstance(doc, dict) else []:
                if not isinstance(rec, Mapping):
                    continue
                safe = self._safe_org_record(rec)
                if safe:
                    records.append({"connector_key": row["connector_key"], "parse_run_id": row["parse_run_id"], "object_id": row["object_id"], "record": safe})
        correlations = self.connector_sdk.correlation_candidates(case_id=case_id)
        return {
            "policy": POLICY,
            "case_id": case_id,
            "receipt_count": len(receipts),
            "externally_validated_receipts": sum(1 for r in receipts if r["externally_validated"]),
            "records": records[:200],
            "correlation_candidates": correlations[:100],
            "identity_auto_merge": False,
            "address_fields_in_ai_context": False,
            "person_name_live_lookup_supported": False,
            "lead_review_required": True,
        }


class AutonomousInvestigation366:
    def __init__(self, db: Any, *, base365: Any, corporate366: CorporateLiveData366):
        self.db = db
        self.base365 = base365
        self.corporate366 = corporate366

    def status(self) -> dict[str, Any]:
        base = dict(self.base365.status())
        base.update({
            "policy_version": AI_POLICY,
            "corporate_receipt_aware": True,
            "corporate_safe_org_context": True,
            "address_fields_excluded_from_routine_ai_context": True,
            "corporate_identity_auto_merge": False,
            "direct_connector_network_authority": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base365.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            dossier["phase16_corporate_data_context"] = self.corporate366.case_summary(case_id=case_id)
            dossier["lead_review_required"] = True
        return out


class DefensiveOpsecSupervisor366:
    def __init__(self, db: Any, audit: Any, *, base365: Any, corporate366: CorporateLiveData366, jobs: Any):
        self.db = db
        self.audit = audit
        self.base365 = base365
        self.corporate366 = corporate366
        self.jobs = jobs

    def status(self) -> dict[str, Any]:
        base = dict(self.base365.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "corporate_connector_allowlist": sorted(LIVE_CONNECTORS),
            "explicit_live_confirmation_enforced": True,
            "source_review_enforced": True,
            "auth_connector_live_blocked": True,
            "declared_sec_user_agent_enforced": True,
            "cross_host_redirect_block_inherited": True,
            "person_name_live_lookup_blocked": True,
            "firewall_mutation": False,
            "os_mutation": False,
            "tor_configuration_mutation": False,
            "credential_mutation": False,
            "acl_mutation": False,
            "system_mutations": False,
        })
        return base

    def protect_remote_session(self, **kwargs: Any) -> dict[str, Any]:
        return self.base365.protect_remote_session(**kwargs)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base365.protect_case(case_id=case_id)
        cancelled: list[str] = []
        rows = self.db.all(
            "SELECT j.job_id,j.payload_json FROM phase15_jobs j WHERE j.case_id=? AND j.status IN ('queued','running') AND j.job_type='governed_crawl_v1'",
            (case_id,),
        )
        for row in rows:
            payload = _json(row.get("payload_json"), {})
            key = str(payload.get("phase16_corporate_connector") or "")
            if not key:
                continue
            source_id = str(payload.get("source_id") or "")
            try:
                link = self.corporate366._source_link(source_id)
                invalid = key not in LIVE_CONNECTORS or link["connector_key"] != key or link["auth_type"] != "none" or link["review_status"] != "approved_read_only"
            except Exception:
                invalid = True
            if invalid or payload.get("phase16_corporate_live_confirmation") is not True:
                self.jobs.cancel(row["job_id"], actor="opsec366")
                cancelled.append(row["job_id"])
        if cancelled:
            self.audit.log("OPSEC366_CORPORATE_JOB_CANCEL", "case", case_id, case_id=case_id, details={"cancelled_jobs": cancelled, "policy": OPSEC_POLICY})
        return {**base, "cancelled_invalid_corporate_jobs": cancelled, "policy_version": OPSEC_POLICY, "system_mutations": False}
