from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

POLICY = "phase16.entity-resolution-v2.v371"
AI_POLICY = "phase16.autonomous-investigation.v371"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v371"
LEAD_JOB = "entity_link_lead_v371"
STRONG_TYPES = {"email", "phone", "external_id"}
CONFLICT_TYPES = STRONG_TYPES | {"birth_year"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _source_family(ref: str | None) -> str:
    raw = str(ref or "").strip()
    if not raw:
        return ""
    if raw.startswith("crawl:") or raw.startswith("source:"):
        parts = raw.split(":")
        return ":".join(parts[:2]) if len(parts) >= 2 else raw
    if "://" in raw:
        try:
            host = (urlsplit(raw).hostname or "").casefold()
            return host[4:] if host.startswith("www.") else host
        except ValueError:
            pass
    return raw.split("#", 1)[0][:160]


class EntityResolutionV2371:
    """Evidence-weighted review layer over the canonical v115 entity ledger.

    Scores are prioritisation weights, not calibrated identity probabilities.  No
    method in this class performs an automatic merge or identity confirmation.
    """

    def __init__(self, db: Any, audit: Any, *, base_entities: Any, governance: Any, jobs: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.base = base_entities
        self.governance = governance
        self.jobs = jobs
        self.actor = actor

    def _authorize(self, identity: dict[str, Any], case_id: str, capability: str = "research.run", object_id: str = "") -> None:
        self.governance.authorize(identity, case_id=case_id, capability=capability, object_type="entity_resolution_v2", object_id=object_id or case_id)

    def _entity(self, entity_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM resolution_entities_115 WHERE resolution_entity_id=?", (str(entity_id),))
        if not row:
            raise KeyError(entity_id)
        return row

    def _anchors(self, entity_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM resolution_anchors_115 WHERE resolution_entity_id=? ORDER BY created_at", (str(entity_id),))

    def register_candidate(self, *, case_id: str, entity_type: str, display_name: str, identity: dict[str, Any], source_entity_id: str | None = None, attributes: dict[str, Any] | None = None, aliases: list[str] | None = None, anchors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self._authorize(identity, case_id, "research.run")
        actor = str(identity.get("username") or self.actor)
        entity_id = self.base.register_entity(case_id, entity_type, display_name, actor, source_entity_id=source_entity_id, attributes=attributes or {}, aliases=aliases or [], anchors=anchors or [])
        row = self._entity(entity_id)
        return {"policy": POLICY, "entity": row, "candidate_only": True, "identity_confirmed": False, "automatic_merge": False}

    def _compare_core(self, left_entity_id: str, right_entity_id: str, *, actor: str) -> dict[str, Any]:
        base = self.base.compare(left_entity_id, right_entity_id, actor)
        left, right = self._entity(base["left_entity_id"]), self._entity(base["right_entity_id"])
        la, ra = self._anchors(left["resolution_entity_id"]), self._anchors(right["resolution_entity_id"])
        matched: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        source_families: set[str] = set()
        for x in la:
            for y in ra:
                if x["anchor_type"] != y["anchor_type"]:
                    continue
                if x["value_hash"] == y["value_hash"]:
                    strength = min(float(x["reliability"]), float(y["reliability"]))
                    families = {f for f in (_source_family(x.get("source_ref")), _source_family(y.get("source_ref"))) if f}
                    source_families.update(families)
                    matched.append({"type": x["anchor_type"], "strength": round(strength, 4), "strong": x["anchor_type"] in STRONG_TYPES, "source_families": sorted(families)})
                elif x["anchor_type"] in CONFLICT_TYPES:
                    severity = 1.0 if x["anchor_type"] in STRONG_TYPES else 0.65
                    conflicts.append({"type": x["anchor_type"], "severity": severity, "left": x["anchor_value"], "right": y["anchor_value"]})
        strong_matches = sum(1 for m in matched if m["strong"])
        independent_sources = len(source_families)
        same_name_count = int((self.db.one("SELECT COUNT(*) c FROM resolution_entities_115 WHERE case_id=? AND entity_type=? AND normalized_name=?", (left["case_id"], left["entity_type"], left["normalized_name"])) or {}).get("c") or 0)
        common_name_penalty = min(0.25, max(0, same_name_count - 1) * 0.05)
        base_name = float(base.get("name_similarity") or 0)
        base_alias = float(base.get("alias_similarity") or 0)
        anchor_weight = min(1.0, sum((0.55 if m["strong"] else 0.20) * float(m["strength"]) for m in matched))
        independence_bonus = min(0.18, max(0, independent_sources - 1) * 0.06)
        conflict_penalty = min(1.0, sum(float(c["severity"]) for c in conflicts))
        strong_conflict_veto = any(c["type"] in STRONG_TYPES for c in conflicts)
        score = _clamp(0.28 * base_name + 0.14 * base_alias + 0.52 * anchor_weight + independence_bonus - 0.58 * conflict_penalty - common_name_penalty)
        if strong_conflict_veto or conflict_penalty >= 0.9:
            classification = "likely_distinct"
        elif score >= 0.82 and strong_matches >= 1 and independent_sources >= 2:
            classification = "strong_review_candidate"
        elif score >= 0.64 and (matched or base_name >= 0.9):
            classification = "possible_review_candidate"
        elif score >= 0.42:
            classification = "weak_review_candidate"
        else:
            classification = "insufficient"
        explanation = dict(base.get("explanation") or {})
        explanation["v371"] = {
            "evidence_weight": round(score, 4),
            "score_is_probability": False,
            "classification": classification,
            "strong_anchor_matches": strong_matches,
            "independent_source_families": sorted(source_families),
            "independent_source_count": independent_sources,
            "common_name_count": same_name_count,
            "common_name_penalty": round(common_name_penalty, 4),
            "strong_identifier_conflict_veto": strong_conflict_veto,
            "matched_anchors": matched,
            "conflicts": conflicts,
            "review_required": True,
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
            "destructive_merge": False,
        }
        self.db.execute("UPDATE resolution_comparisons_115 SET total_score=?,classification=?,explanation_json=?,state='needs_review' WHERE comparison_id=?", (score, classification, _canon(explanation), base["comparison_id"]))
        self.base._event(left["case_id"], actor, "EntityResolutionV2371Compared", "resolution_comparison", base["comparison_id"], {"classification": classification, "evidence_weight": round(score, 4), "probability_claim": False, "automatic_merge": False})
        return self.base.comparison(base["comparison_id"]) | {"v2": explanation["v371"]}

    def compare(self, *, case_id: str, left_entity_id: str, right_entity_id: str, identity: dict[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "research.run")
        left, right = self._entity(left_entity_id), self._entity(right_entity_id)
        if left["case_id"] != case_id or right["case_id"] != case_id:
            raise PermissionError("cross-case entity resolution prohibited")
        return self._compare_core(left_entity_id, right_entity_id, actor=str(identity.get("username") or self.actor))

    def analyze_internal(self, *, case_id: str, left_entity_id: str, right_entity_id: str, actor: str) -> dict[str, Any]:
        left, right = self._entity(left_entity_id), self._entity(right_entity_id)
        if left["case_id"] != case_id or right["case_id"] != case_id:
            raise PermissionError("cross-case entity resolution prohibited")
        return self._compare_core(left_entity_id, right_entity_id, actor=actor)

    def propose_same_entity(self, *, case_id: str, comparison_id: str, canonical_entity_id: str, identity: dict[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "research.run", comparison_id)
        cmp = self.base.comparison(comparison_id)
        if cmp["case_id"] != case_id:
            raise PermissionError("cross-case proposal prohibited")
        if cmp["classification"] not in {"strong_review_candidate", "possible_review_candidate"}:
            raise ValueError("v371 requires at least possible_review_candidate for a human merge-link proposal")
        pid = self.base.propose_merge(comparison_id, canonical_entity_id, str(identity.get("username") or self.actor))
        return {"proposal_id": pid, "state": "pending", "automatic_merge": False, "independent_review_required": True}

    def review_same_entity(self, *, case_id: str, proposal_id: str, identity: dict[str, Any], approve: bool, reason: str) -> dict[str, Any]:
        self._authorize(identity, case_id, "dossier.review", proposal_id)
        proposal = self.db.one("SELECT * FROM resolution_merge_proposals_115 WHERE proposal_id=?", (proposal_id,))
        if not proposal or proposal["case_id"] != case_id:
            raise KeyError(proposal_id)
        out = self.base.review_merge(proposal_id, str(identity.get("username") or self.actor), bool(approve), reason)
        return out | {"automatic_merge": False, "destructive_merge": False}

    def case_status(self, *, case_id: str) -> dict[str, Any]:
        comparisons = self.db.all("SELECT comparison_id,left_entity_id,right_entity_id,total_score,classification,state,created_at FROM resolution_comparisons_115 WHERE case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
        unresolved = [r for r in comparisons if r["state"] == "needs_review"]
        return {
            "policy": POLICY,
            "case_id": case_id,
            "entities": int((self.db.one("SELECT COUNT(*) c FROM resolution_entities_115 WHERE case_id=?", (case_id,)) or {}).get("c") or 0),
            "comparisons": comparisons,
            "unresolved_review_items": len(unresolved),
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
            "score_is_probability": False,
            "independent_human_review_required": True,
        }

    def status(self) -> dict[str, Any]:
        return {"policy": POLICY, "entity_resolution_v2": True, "strong_identifier_conflict_veto": True, "source_independence_weighting": True, "common_name_penalty": True, "score_is_probability": False, "automatic_identity_confirmation": False, "automatic_merge": False, "destructive_merge": False, "independent_human_review_required": True}


class EntityLinkedCrawler371:
    """Crawler provenance -> entity-review lead bridge using the canonical job ledger."""

    def __init__(self, db: Any, audit: Any, *, build370: Any, jobs: Any, governance: Any, entity371: EntityResolutionV2371, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build370 = build370
        self.jobs = jobs
        self.governance = governance
        self.entity371 = entity371
        self.actor = actor

    def provenance(self, *, crawl_run_id: str, fetch_id: str | None = None) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=?", (str(crawl_run_id),))
        if not run:
            raise KeyError(crawl_run_id)
        source = self.db.one("SELECT source_id,source_kind,locator,display_name,review_status,record_hash FROM phase15_sources WHERE source_id=?", (run["source_id"],))
        if not source:
            raise KeyError(run["source_id"])
        if fetch_id:
            fetches = self.db.all("SELECT fetch_id,url,status_code,content_type,content_sha256,size_bytes,object_id,created_at,record_hash FROM phase15_crawl_fetches WHERE crawl_run_id=? AND fetch_id=?", (crawl_run_id, fetch_id))
            if not fetches:
                raise KeyError(fetch_id)
        else:
            fetches = self.db.all("SELECT fetch_id,url,status_code,content_type,content_sha256,size_bytes,object_id,created_at,record_hash FROM phase15_crawl_fetches WHERE crawl_run_id=? ORDER BY created_at", (crawl_run_id,))
        material = {
            "crawl_run_id": run["crawl_run_id"], "case_id": run["case_id"], "source_id": run["source_id"], "search_run_id": run["search_run_id"], "run_status": run["status"], "run_record_hash": run["record_hash"],
            "source": source, "fetches": fetches,
        }
        return material | {"provenance_hash": _sha(material), "fetch_count": len(fetches), "entity_linkage_state": "lead_only"}

    def enqueue_lead(self, *, case_id: str, crawl_run_id: str, target_entity_id: str, candidate_entity_id: str, identity: dict[str, Any], fetch_id: str | None = None, rationale: str = "") -> dict[str, Any]:
        self.governance.authorize(identity, case_id=case_id, capability="research.run", object_type="entity_link_lead", object_id=crawl_run_id)
        prov = self.provenance(crawl_run_id=crawl_run_id, fetch_id=fetch_id)
        if prov["case_id"] != case_id:
            raise PermissionError("cross-case crawl provenance prohibited")
        if prov["source"]["review_status"] != "approved_read_only":
            raise PermissionError("reviewed source required")
        left, right = self.entity371._entity(target_entity_id), self.entity371._entity(candidate_entity_id)
        if left["case_id"] != case_id or right["case_id"] != case_id:
            raise PermissionError("cross-case entity lead prohibited")
        if target_entity_id == candidate_entity_id:
            raise ValueError("lead requires two distinct entity candidates")
        payload = {
            "policy": POLICY, "case_id": case_id, "crawl_run_id": crawl_run_id, "fetch_id": str(fetch_id or ""), "source_id": prov["source_id"], "target_entity_id": target_entity_id, "candidate_entity_id": candidate_entity_id,
            "provenance_hash": prov["provenance_hash"], "source_record_hash": prov["source"]["record_hash"], "rationale": str(rationale or "")[:1000], "lead_only": True, "automatic_merge": False,
        }
        key = _sha({"job": LEAD_JOB, "case": case_id, "run": crawl_run_id, "fetch": fetch_id or "", "left": target_entity_id, "right": candidate_entity_id})
        job = self.jobs.enqueue(job_type=LEAD_JOB, payload=payload, case_id=case_id, search_run_id=str(prov["search_run_id"] or ""), idempotency_key=key, priority=70, max_attempts=3, resource_budget={"max_runtime_seconds": 120, "max_memory_mb": 256, "max_output_bytes": 2_000_000}, rate_budget={"max_requests": 0, "requests_per_minute": 0})
        self.audit.log("ENTITY371_LEAD_ENQUEUED", "entity_link_lead", job["job_id"], case_id=case_id, details={"crawl_run_id": crawl_run_id, "source_id": prov["source_id"], "provenance_hash": prov["provenance_hash"], "automatic_merge": False})
        return {"policy": POLICY, "job": job, "provenance": prov, "network_execution": False, "automatic_merge": False, "review_required": True}

    def claim_next(self, *, worker_id: str, case_id: str | None = None, lease_seconds: int = 120) -> dict[str, Any] | None:
        now = _now_dt(); now_s = now.isoformat(timespec="seconds"); expiry = (now + timedelta(seconds=max(30, min(int(lease_seconds), 900)))).isoformat(timespec="seconds")
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',updated_at=? WHERE job_type=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?", (now_s, LEAD_JOB, now_s))
            if case_id:
                row = self.db.one("SELECT job_id FROM phase15_jobs WHERE job_type=? AND case_id=? AND status='queued' AND available_at<=? ORDER BY priority,created_at LIMIT 1", (LEAD_JOB, case_id, now_s))
            else:
                row = self.db.one("SELECT job_id FROM phase15_jobs WHERE job_type=? AND status='queued' AND available_at<=? ORDER BY priority,created_at LIMIT 1", (LEAD_JOB, now_s))
            if not row:
                return None
            cur = self.db.execute("UPDATE phase15_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=? AND status='queued'", (str(worker_id)[:120], expiry, now_s, row["job_id"]))
            return self.jobs.get(row["job_id"]) if cur.rowcount == 1 else None

    def run_next(self, *, worker_id: str, case_id: str | None = None) -> dict[str, Any]:
        job = self.claim_next(worker_id=worker_id, case_id=case_id)
        if not job:
            return {"state": "idle", "policy": POLICY}
        payload = _j(job.get("payload_json"), {})
        try:
            prov = self.provenance(crawl_run_id=str(payload.get("crawl_run_id") or ""), fetch_id=str(payload.get("fetch_id") or "") or None)
            if prov["provenance_hash"] != payload.get("provenance_hash") or prov["case_id"] != job["case_id"]:
                raise PermissionError("crawler provenance changed or case mismatch")
            comparison = self.entity371.analyze_internal(case_id=job["case_id"], left_entity_id=str(payload["target_entity_id"]), right_entity_id=str(payload["candidate_entity_id"]), actor=worker_id)
            result = {"policy": POLICY, "comparison_id": comparison["comparison_id"], "classification": comparison["classification"], "evidence_weight": comparison["v2"]["evidence_weight"], "provenance_hash": prov["provenance_hash"], "review_required": True, "automatic_merge": False, "identity_confirmed": False}
            done = self.jobs.complete(job["job_id"], result, worker_id=worker_id)
            self.audit.log("ENTITY371_LEAD_ANALYZED", "entity_link_lead", job["job_id"], case_id=job["case_id"], details=result)
            return {"state": "review_ready", "job": done, "result": result, "comparison": comparison, "provenance": prov}
        except Exception as exc:
            failed = self.jobs.fail(job["job_id"], f"{type(exc).__name__}:{exc}", worker_id=worker_id, retry_delay_seconds=30)
            return {"state": "failed", "job": failed, "error": str(exc), "policy": POLICY}

    def recover_expired_leases(self, *, case_id: str | None = None) -> dict[str, Any]:
        now = _now(); args: list[Any] = [LEAD_JOB, now]; where = "job_type=? AND status='running' AND lease_expires_at<>'' AND lease_expires_at<?"
        if case_id:
            where += " AND case_id=?"; args.append(case_id)
        rows = self.db.all(f"SELECT job_id FROM phase15_jobs WHERE {where}", tuple(args))
        ids = [r["job_id"] for r in rows]
        for jid in ids:
            self.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',updated_at=? WHERE job_id=?", (now, jid))
        return {"policy": POLICY, "recovered_jobs": ids, "checkpoint_preserved": True}

    def invalid_jobs(self, *, case_id: str) -> list[str]:
        invalid: list[str] = []
        rows = self.db.all("SELECT job_id,payload_json,case_id FROM phase15_jobs WHERE job_type=? AND case_id=? AND status IN ('queued','running')", (LEAD_JOB, case_id))
        for row in rows:
            try:
                p = _j(row["payload_json"], {})
                prov = self.provenance(crawl_run_id=str(p.get("crawl_run_id") or ""), fetch_id=str(p.get("fetch_id") or "") or None)
                a = self.entity371._entity(str(p.get("target_entity_id") or "")); b = self.entity371._entity(str(p.get("candidate_entity_id") or ""))
                bad = p.get("policy") != POLICY or p.get("lead_only") is not True or p.get("automatic_merge") is not False or prov["case_id"] != case_id or prov["provenance_hash"] != p.get("provenance_hash") or a["case_id"] != case_id or b["case_id"] != case_id
            except Exception:
                bad = True
            if bad:
                invalid.append(row["job_id"])
        return invalid

    def case_status(self, *, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT job_id,status,payload_json,result_json,created_at FROM phase15_jobs WHERE job_type=? AND case_id=? ORDER BY created_at DESC LIMIT 200", (LEAD_JOB, case_id))
        return {"policy": POLICY, "case_id": case_id, "lead_jobs": [{"job_id": r["job_id"], "status": r["status"], "created_at": r["created_at"], "result": _j(r.get("result_json"), {})} for r in rows], "queued": sum(1 for r in rows if r["status"] == "queued"), "running": sum(1 for r in rows if r["status"] == "running"), "review_ready": sum(1 for r in rows if r["status"] == "succeeded"), "network_execution": False, "automatic_merge": False}

    def status(self) -> dict[str, Any]:
        row = self.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type=? AND status IN ('queued','running')", (LEAD_JOB,)) or {}
        return {"policy": POLICY, "job_type": LEAD_JOB, "active_leads": int(row.get("c") or 0), "canonical_job_ledger": True, "entity_linked_crawl_provenance": True, "source_to_entity_lead_queue": True, "network_execution": False, "automatic_merge": False, "new_per_build_data_tables": 0}


class AutonomousInvestigation371:
    def __init__(self, db: Any, *, base370: Any, entity371: EntityResolutionV2371, crawler371: EntityLinkedCrawler371):
        self.db = db; self.base370 = base370; self.entity371 = entity371; self.crawler371 = crawler371
    def status(self) -> dict[str, Any]:
        base = dict(self.base370.status()); base.update({"policy_version": AI_POLICY, "entity_resolution_v2_awareness": True, "crawler_entity_lead_awareness": True, "automatic_identity_confirmation": False, "automatic_entity_merge": False, "direct_entity_lead_enqueue_authority": False, "direct_merge_approval_authority": False}); return base
    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base370.run_cycle(case_id=case_id, max_ticks=max_ticks); dossier = out.get("dossier")
        if isinstance(dossier, dict):
            er = self.entity371.case_status(case_id=case_id); leads = self.crawler371.case_status(case_id=case_id)
            dossier["phase16_entity_resolution_v2"] = {"unresolved_review_items": er["unresolved_review_items"], "crawler_entity_leads": len(leads["lead_jobs"]), "score_is_probability": False, "automatic_merge": False, "independent_review_required": True}
            dossier["entity_resolution_review_required"] = bool(er["unresolved_review_items"] or leads["lead_jobs"])
        return out


class DefensiveOpsecSupervisor371:
    def __init__(self, db: Any, audit: Any, *, base370: Any, crawler371: EntityLinkedCrawler371, jobs: Any):
        self.db = db; self.audit = audit; self.base370 = base370; self.crawler371 = crawler371; self.jobs = jobs
    def status(self) -> dict[str, Any]:
        base = dict(self.base370.status()); base.update({"policy_version": OPSEC_POLICY, "entity_lead_integrity_monitor": True, "cross_case_entity_lead_block": True, "provenance_hash_validation": True, "automatic_merge_authority": False, "firewall_mutation": False, "os_mutation": False, "tor_configuration_mutation": False, "credential_mutation": False, "acl_mutation": False, "system_mutations": False}); return base
    def protect_remote_session(self, **kw: Any) -> dict[str, Any]: return self.base370.protect_remote_session(**kw)
    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base370.protect_case(case_id=case_id); invalid = self.crawler371.invalid_jobs(case_id=case_id)
        for jid in invalid: self.jobs.cancel(jid, actor="opsec371")
        if invalid: self.audit.log("OPSEC371_ENTITY_LEAD_CANCEL", "case", case_id, case_id=case_id, details={"cancelled_jobs": invalid, "policy": OPSEC_POLICY})
        return {**base, "cancelled_invalid_entity_lead_jobs": invalid, "entity_lead_status": self.crawler371.case_status(case_id=case_id), "policy_version": OPSEC_POLICY, "system_mutations": False, "automatic_merge_authority": False}
