from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

POLICY = "phase16.image-live-validation.v377"
HANDOFF_POLICY = "phase16.image-agent-handoff.v377"
PRESSURE_POLICY = "phase16.media-object-pressure.v377"
MEDIA_JOB_TYPES = {"media_image_fetch_v1", "image_intelligence_handoff_v377", "reverse_image_search_lead_v1"}
DEFAULT_CASE_SOFT_BYTES = 128 * 1024 * 1024
DEFAULT_CASE_HARD_BYTES = 256 * 1024 * 1024
DEFAULT_GLOBAL_SOFT_BYTES = 1024 * 1024 * 1024
DEFAULT_GLOBAL_HARD_BYTES = 2 * 1024 * 1024 * 1024


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class ImageMediaPipeline377:
    """Production boundary around the existing local image-intelligence stack.

    It adds provenance, exact pre-ingest deduplication, logical object-store pressure gates,
    and review-first handoff records. It does not fetch arbitrary media, identify people,
    confirm locations, or create network authority for the image agent.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build376: Any,
        build355: Any,
        image_agent: Any,
        media_crawler: Any,
        jobs: Any,
        actor: str = "local-analyst",
        case_soft_bytes: int = DEFAULT_CASE_SOFT_BYTES,
        case_hard_bytes: int = DEFAULT_CASE_HARD_BYTES,
        global_soft_bytes: int = DEFAULT_GLOBAL_SOFT_BYTES,
        global_hard_bytes: int = DEFAULT_GLOBAL_HARD_BYTES,
    ) -> None:
        self.db = db
        self.audit = audit
        self.build376 = build376
        self.build355 = build355
        self.image_agent = image_agent
        self.media_crawler = media_crawler
        self.jobs = jobs
        self.actor = actor
        self.case_soft_bytes = max(1, int(case_soft_bytes))
        self.case_hard_bytes = max(self.case_soft_bytes + 1, int(case_hard_bytes))
        self.global_soft_bytes = max(self.case_hard_bytes + 1, int(global_soft_bytes))
        self.global_hard_bytes = max(self.global_soft_bytes + 1, int(global_hard_bytes))

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "crawler_improvement_build": 377,
            "image_agent_network_authority": False,
            "automatic_reverse_image_search": False,
            "automatic_face_identity": False,
            "automatic_scene_location_confirmation": False,
            "exact_dedup_pre_ingest": True,
            "media_crawl_provenance": True,
            "object_store_pressure_control": True,
            "raw_image_bytes_in_handoff_job": False,
            "human_review_required_for_visual_geolocation": True,
            "external_image_live_validation": "not_run",
            "external_reverse_image_provider_validation": "not_run",
        }

    def storage_pressure(self, *, case_id: str | None = None, incoming_bytes: int = 0) -> dict[str, Any]:
        incoming = max(0, int(incoming_bytes))
        total = int((self.db.one("SELECT COALESCE(SUM(size_bytes),0) n FROM phase15_objects") or {}).get("n") or 0)
        case_total = 0
        if case_id:
            case_total = int((self.db.one("SELECT COALESCE(SUM(size_bytes),0) n FROM phase15_objects WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
        total_after = total + incoming
        case_after = case_total + incoming
        hard = total_after > self.global_hard_bytes or (bool(case_id) and case_after > self.case_hard_bytes)
        soft = total_after > self.global_soft_bytes or (bool(case_id) and case_after > self.case_soft_bytes)
        state = "hard_limit" if hard else "soft_limit" if soft else "normal"
        return {
            "policy": PRESSURE_POLICY,
            "case_id": case_id or "",
            "incoming_bytes": incoming,
            "global_bytes": total,
            "global_bytes_after": total_after,
            "case_bytes": case_total,
            "case_bytes_after": case_after,
            "state": state,
            "allow_new_media_object": not hard,
            "throttle_media_discovery": soft,
            "case_soft_bytes": self.case_soft_bytes,
            "case_hard_bytes": self.case_hard_bytes,
            "global_soft_bytes": self.global_soft_bytes,
            "global_hard_bytes": self.global_hard_bytes,
            "deletion_or_eviction_automatic": False,
        }

    def exact_duplicate(self, *, case_id: str, sha256: str) -> dict[str, Any] | None:
        row = self.db.one(
            "SELECT media_id,object_ref,sha256,review_status,created_at FROM phase15_media_assets WHERE case_id=? AND media_kind='image' AND sha256=? ORDER BY created_at ASC LIMIT 1",
            (case_id, str(sha256).lower()),
        )
        if not row:
            return None
        obj = self.db.one("SELECT object_id,size_bytes,media_type,security_state,source_id,search_run_id,provenance_json FROM phase15_objects WHERE object_id=?", (row["object_ref"],)) or {}
        return {
            "media_id": row["media_id"],
            "object_id": row["object_ref"],
            "sha256": row["sha256"],
            "review_status": row["review_status"],
            "size_bytes": int(obj.get("size_bytes") or 0),
            "media_type": str(obj.get("media_type") or ""),
            "security_state": str(obj.get("security_state") or ""),
            "source_id": str(obj.get("source_id") or ""),
            "search_run_id": str(obj.get("search_run_id") or ""),
            "exact_duplicate": True,
        }

    def _source_and_run_guard(self, *, case_id: str, source_id: str = "", crawl_run_id: str = "") -> None:
        if source_id:
            src = self.db.one("SELECT source_id FROM phase15_sources WHERE source_id=?", (source_id,))
            if not src:
                raise KeyError(source_id)
        if crawl_run_id:
            run = self.db.one("SELECT case_id,source_id FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,))
            if not run:
                raise KeyError(crawl_run_id)
            if str(run["case_id"]) != case_id:
                raise PermissionError("crawl run must belong to case")
            if source_id and str(run["source_id"]) != source_id:
                raise PermissionError("crawl/source mismatch")

    def _record_agent_handoff(self, *, case_id: str, media_id: str, object_id: str, provenance: dict[str, Any]) -> dict[str, Any]:
        now = self.db.one("SELECT datetime('now') t")["t"]
        task_id = "task_" + uuid.uuid4().hex[:24]
        task_payload = {
            "media_id": media_id,
            "object_id": object_id,
            "policy": HANDOFF_POLICY,
            "provenance": provenance,
            "raw_image_bytes_in_task": False,
            "network_budget": 0,
            "identity_confirmation_allowed": False,
            "scene_location_confirmation_allowed": False,
        }
        task = {
            "task_id": task_id,
            "case_id": case_id,
            "agent_role": "image_intelligence",
            "action_class": "image_validation_handoff_v377",
            "requested_gateway": "local_image_analysis",
            "approval_state": "local_review_first",
            "contract_version": HANDOFF_POLICY,
            "task_json": _canon(task_payload),
            "record_hash": "",
            "created_at": now,
        }
        task["record_hash"] = _sha({k: v for k, v in task.items() if k != "record_hash"})
        self.db.execute(
            "INSERT INTO phase15_agent_tasks(task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            tuple(task.values()),
        )
        result_id = "res_" + uuid.uuid4().hex[:24]
        result_payload = {
            "media_id": media_id,
            "object_id": object_id,
            "handoff_valid": True,
            "requires_human_review": True,
            "network_used": False,
            "identity_confirmed": False,
            "scene_location_confirmed": False,
        }
        result = {
            "result_id": result_id,
            "task_id": task_id,
            "status": "completed",
            "gateway_used": "local_image_analysis",
            "contract_version": HANDOFF_POLICY,
            "result_json": _canon(result_payload),
            "record_hash": "",
            "created_at": now,
        }
        result["record_hash"] = _sha({k: v for k, v in result.items() if k != "record_hash"})
        self.db.execute(
            "INSERT INTO phase15_agent_results(result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
            tuple(result.values()),
        )
        return {"task_id": task_id, "result_id": result_id, "payload": result_payload}

    def ingest_image(
        self,
        *,
        case_id: str,
        content: bytes,
        declared_media_type: str = "",
        filename: str = "",
        search_run_id: str | None = None,
        source_id: str | None = None,
        crawl_run_id: str = "",
        source_url: str = "",
    ) -> dict[str, Any]:
        raw = bytes(content)
        inspection = self.image_agent.inspect_bytes(raw, declared_media_type=declared_media_type, filename=filename)
        self._source_and_run_guard(case_id=case_id, source_id=str(source_id or ""), crawl_run_id=crawl_run_id)
        duplicate = self.exact_duplicate(case_id=case_id, sha256=inspection["sha256"])
        if duplicate:
            handoff = self._record_agent_handoff(
                case_id=case_id,
                media_id=duplicate["media_id"],
                object_id=duplicate["object_id"],
                provenance={
                    "policy": POLICY,
                    "deduplicated": True,
                    "crawl_run_id": crawl_run_id,
                    "source_id": source_id or "",
                    "source_url": source_url[:3000],
                    "sha256": inspection["sha256"],
                },
            )
            return {
                "deduplicated": True,
                "new_object_written": False,
                "media_id": duplicate["media_id"],
                "object_id": duplicate["object_id"],
                "inspection": inspection,
                "handoff": handoff,
            }
        pressure = self.storage_pressure(case_id=case_id, incoming_bytes=len(raw))
        if not pressure["allow_new_media_object"]:
            raise PermissionError("object_store_hard_limit_blocks_new_media")
        stored = self.build376.ingest_image(
            case_id=case_id,
            content=raw,
            declared_media_type=declared_media_type,
            filename=filename,
            search_run_id=search_run_id,
            source_id=source_id,
            provenance={
                "image_live_validation_policy": POLICY,
                "crawl_run_id": crawl_run_id,
                "source_url": source_url[:3000],
                "pre_ingest_exact_dedup": True,
                "object_store_pressure_state": pressure["state"],
                "external_network_execution_by_build377": False,
            },
        )
        media_id = stored["media_id"]
        object_id = stored["object"]["object_id"]
        technical = self.build355.technical_manipulation_signals(media_id, persist=True)
        handoff = self._record_agent_handoff(
            case_id=case_id,
            media_id=media_id,
            object_id=object_id,
            provenance={
                "policy": POLICY,
                "deduplicated": False,
                "crawl_run_id": crawl_run_id,
                "source_id": source_id or "",
                "source_url": source_url[:3000],
                "sha256": inspection["sha256"],
                "object_store_pressure_state": pressure["state"],
            },
        )
        return {
            **stored,
            "deduplicated": False,
            "new_object_written": True,
            "technical_signals": technical,
            "handoff": handoff,
            "storage_pressure": pressure,
        }

    def media_provenance(self, *, case_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT m.media_id,m.object_ref,m.sha256,m.review_status,m.created_at,o.source_id,o.search_run_id,o.size_bytes,o.media_type,o.security_state,o.provenance_json FROM phase15_media_assets m JOIN phase15_objects o ON o.object_id=m.object_ref WHERE m.case_id=? AND m.media_kind='image' ORDER BY m.created_at DESC LIMIT ?",
            (case_id, max(1, min(int(limit), 1000))),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                prov = json.loads(row.get("provenance_json") or "{}")
            except Exception:
                prov = {}
            crawl_run_id = str(prov.get("crawl_run_id") or "")
            valid = True
            if crawl_run_id:
                cr = self.db.one("SELECT case_id,source_id FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,))
                valid = bool(cr and str(cr["case_id"]) == case_id and (not row.get("source_id") or str(cr["source_id"]) == str(row.get("source_id"))))
            out.append({
                "media_id": row["media_id"],
                "object_id": row["object_ref"],
                "sha256": row["sha256"],
                "review_status": row["review_status"],
                "source_id": str(row.get("source_id") or ""),
                "search_run_id": str(row.get("search_run_id") or ""),
                "crawl_run_id": crawl_run_id,
                "source_url": str(prov.get("source_url") or prov.get("url") or ""),
                "size_bytes": int(row.get("size_bytes") or 0),
                "media_type": str(row.get("media_type") or ""),
                "security_state": str(row.get("security_state") or ""),
                "provenance_integrity_valid": valid,
                "requires_human_review": True,
            })
        return out

    def case_media_summary(self, *, case_id: str) -> dict[str, Any]:
        prov = self.media_provenance(case_id=case_id)
        by_hash: dict[str, int] = {}
        for item in prov:
            by_hash[item["sha256"]] = by_hash.get(item["sha256"], 0) + 1
        duplicate_groups = sum(1 for n in by_hash.values() if n > 1)
        invalid = [x["media_id"] for x in prov if not x["provenance_integrity_valid"]]
        pressure = self.storage_pressure(case_id=case_id)
        handoffs = int((self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=? AND action_class='image_validation_handoff_v377'", (case_id,)) or {}).get("c") or 0)
        return {
            "policy": POLICY,
            "case_id": case_id,
            "image_assets": len(prov),
            "exact_duplicate_groups_persisted": duplicate_groups,
            "invalid_provenance_media_ids": invalid,
            "handoff_records": handoffs,
            "storage_pressure": pressure,
            "identity_confirmed": False,
            "scene_location_confirmed": False,
            "external_network_used": False,
        }

    def visual_geolocation(self, *, media_id: str, confirmation: str = "") -> dict[str, Any]:
        if confirmation != "ANALYZE":
            raise PermissionError("explicit ANALYZE confirmation required")
        return self.build355.analyze_visual_geolocation(media_id, human_approved=True)


class AutonomousInvestigation377:
    def __init__(self, *, base376: Any, image377: ImageMediaPipeline377) -> None:
        self.base376 = base376
        self.image377 = image377

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base376, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = dict(self.base376.run_cycle(case_id=case_id, max_ticks=max_ticks))
        summary = self.image377.case_media_summary(case_id=case_id)
        dossier = dict(out.get("dossier") or {})
        dossier["phase16_image_validation_v377"] = summary
        dossier.setdefault("uncertainties", [])
        dossier["uncertainties"] = list(dossier["uncertainties"]) + [
            "Image similarity, metadata and visual geolocation outputs require human review and do not confirm identity or scene location."
        ]
        out["dossier"] = dossier
        out["image_validation"] = summary
        out["direct_image_network_authority"] = False
        return out

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "image_summary_in_dossier": True,
            "direct_image_network_authority": False,
            "automatic_reverse_image_search": False,
            "automatic_identity_confirmation": False,
            "automatic_scene_location_confirmation": False,
        }


class DefensiveOpsecSupervisor377:
    def __init__(self, db: Any, audit: Any, *, base376: Any, image377: ImageMediaPipeline377, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base376 = base376
        self.image377 = image377
        self.jobs = jobs

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.base376, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = dict(self.base376.protect_case(case_id=case_id))
        cancelled: list[str] = []
        violations: list[dict[str, str]] = []
        rows = self.db.all("SELECT * FROM phase15_jobs WHERE case_id=? AND job_type IN ('media_image_fetch_v1','image_intelligence_handoff_v377','reverse_image_search_lead_v1') ORDER BY created_at", (case_id,))
        for row in rows:
            try:
                payload = json.loads(row.get("payload_json") or "{}")
            except Exception:
                payload = {}
            reasons: list[str] = []
            if payload.get("raw_image_bytes_in_job") is True or payload.get("raw_image_bytes_in_task") is True:
                reasons.append("raw_image_bytes_in_job")
            if payload.get("identity_confirmation_allowed") is True:
                reasons.append("identity_confirmation_claim")
            if payload.get("scene_location_confirmation_allowed") is True:
                reasons.append("scene_location_confirmation_claim")
            if payload.get("automatic_reverse_image_search") is True or payload.get("automatic_image_scope_expansion") is True:
                reasons.append("automatic_image_scope_expansion")
            if reasons:
                violations.append({"job_id": row["job_id"], "reason": ",".join(reasons)})
                if row["status"] in {"queued", "workflow_paused"}:
                    self.jobs.cancel(row["job_id"], actor="opsec377")
                    cancelled.append(row["job_id"])
        invalid_prov = self.image377.case_media_summary(case_id=case_id)["invalid_provenance_media_ids"]
        base.update({
            "policy_377": POLICY,
            "image_job_violations": violations,
            "cancelled_image_jobs": cancelled,
            "invalid_image_provenance_media_ids": invalid_prov,
            "storage_pressure": self.image377.storage_pressure(case_id=case_id),
            "system_mutations": False,
            "firewall_mutations": False,
            "os_mutations": False,
            "tor_mutations": False,
            "credential_mutations": False,
        })
        return base

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "image_job_boundary_monitor": True,
            "raw_image_job_payload_block": True,
            "auto_reverse_image_search_block": True,
            "identity_confirmation_claim_block": True,
            "scene_location_confirmation_claim_block": True,
            "system_mutations": False,
        }
