from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

POLICY = "phase16.dossier-vnext.v376"
CRAWLER_POLICY = "phase16.dossier-coverage-crawler.v376"
AI_POLICY = "phase16.autonomous-investigation.v376"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v376"
ABSENCE_JOB = "bounded_absence_observation_v376"
CRAWL_TYPES = {"governed_crawl_v1", "governed_tor_crawl_v370"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _j(v: Any, default: Any) -> Any:
    try:
        return json.loads(v) if isinstance(v, str) else (v if v is not None else default)
    except Exception:
        return default


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _parse_dt(value: Any) -> datetime | None:
    try:
        s = str(value or "").strip()
        if not s:
            return None
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


class DossierVNext376:
    """Evidence-first dossier coverage layer.

    This component is deliberately read-mostly and adds no new database tables.
    It separates source coverage, bounded absence observations and staleness from
    truth claims. A missing result is never automatically promoted to a fact or
    contradiction.
    """

    def __init__(self, db: Any, audit: Any, *, workflow374: Any, source_quality372: Any, jobs: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.workflow374 = workflow374
        self.source_quality372 = source_quality372
        self.jobs = jobs
        self.actor = actor

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "source_coverage_register": True,
            "bounded_absence_observations": True,
            "staleness_register": True,
            "research_gap_register": True,
            "coverage_is_truth_probability": False,
            "absence_is_nonexistence": False,
            "absence_is_counterevidence_by_default": False,
            "automatic_gap_closure": False,
            "automatic_crawl_from_gap": False,
            "direct_network_authority": False,
            "new_per_build_data_tables": 0,
        }

    @staticmethod
    def freshness_threshold_hours(source_kind: str) -> int:
        kind = str(source_kind or "").casefold()
        if "archive" in kind:
            return 24 * 90
        if any(x in kind for x in ("news", "publication", "public_web", "clearnet")):
            return 24 * 7
        if any(x in kind for x in ("official", "government", "register", "registry", "court", "corporate_api", "public_money_api", "reference_api")):
            return 24 * 30
        return 24 * 30

    def _workflow_scope(self, case_id: str) -> tuple[dict[str, Any], list[str]]:
        row = self.workflow374._state_row(case_id)
        if row:
            wf = self.workflow374._payload(row)
            return wf, list((wf.get("source_budgets") or {}).keys())
        rows = self.db.all(
            "SELECT DISTINCT source_id FROM phase15_crawl_runs WHERE case_id=? AND source_id<>'' UNION SELECT DISTINCT source_id FROM phase15_objects WHERE case_id=? AND source_id<>''",
            (case_id, case_id),
        )
        return {}, sorted({str(r.get("source_id") or "") for r in rows if r.get("source_id")})

    def _source_row(self, source_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT s.*,p.source_health,p.enabled,p.terms_ref,p.auth_type FROM phase15_sources s LEFT JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
            (source_id,),
        )
        return row or {}

    def _latest_run(self, case_id: str, source_id: str) -> dict[str, Any] | None:
        return self.db.one(
            "SELECT * FROM phase15_crawl_runs WHERE case_id=? AND source_id=? ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT 1",
            (case_id, source_id),
        )

    def _latest_success(self, case_id: str, source_id: str) -> dict[str, Any] | None:
        return self.db.one(
            "SELECT * FROM phase15_crawl_runs WHERE case_id=? AND source_id=? AND status='succeeded' ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT 1",
            (case_id, source_id),
        )

    def source_coverage(self, *, case_id: str, as_of: str | None = None, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self.workflow374._authorize_monitor(identity, case_id)
        now = _parse_dt(as_of) or datetime.now(timezone.utc)
        wf, source_ids = self._workflow_scope(case_id)
        entries: list[dict[str, Any]] = []
        counts = {"covered_recent": 0, "covered_stale": 0, "attempted_failed": 0, "not_attempted": 0}
        for sid in source_ids:
            src = self._source_row(sid)
            latest = self._latest_run(case_id, sid)
            success = self._latest_success(case_id, sid)
            threshold = self.freshness_threshold_hours(str(src.get("source_kind") or ""))
            success_at = _parse_dt((success or {}).get("completed_at") or (success or {}).get("created_at"))
            age_hours = None if not success_at else max(0.0, (now - success_at).total_seconds() / 3600.0)
            stale = bool(success_at and age_hours is not None and age_hours > threshold)
            if success:
                coverage_state = "covered_stale" if stale else "covered_recent"
            elif latest:
                coverage_state = "attempted_failed"
            else:
                coverage_state = "not_attempted"
            counts[coverage_state] += 1
            fetch_count = int((self.db.one("SELECT COUNT(*) c FROM phase15_crawl_fetches WHERE crawl_run_id=?", ((success or latest or {}).get("crawl_run_id") or "",)) or {}).get("c") or 0) if (success or latest) else 0
            object_count = int((self.db.one("SELECT COUNT(*) c FROM phase15_objects WHERE case_id=? AND source_id=?", (case_id, sid)) or {}).get("c") or 0)
            quality = self.source_quality372.score_snapshot({
                "source_kind": src.get("source_kind"),
                "review_status": src.get("review_status"),
                "hash_verified": object_count > 0,
                "http_success": bool(success and int(success.get("pages_fetched") or 0) > 0),
                "source_health": src.get("source_health") or "unknown",
                "terms_ref_present": bool(src.get("terms_ref")),
                "degraded": str(src.get("source_health") or "").casefold() in {"degraded", "failing", "blocked", "quarantined"},
                "stale": stale,
            })
            entries.append({
                "source_id": sid,
                "display_name": src.get("display_name") or sid,
                "source_kind": src.get("source_kind") or "unknown",
                "review_status": src.get("review_status") or "unknown",
                "source_health": src.get("source_health") or "not_run",
                "coverage_state": coverage_state,
                "latest_run_status": (latest or {}).get("status") or "not_run",
                "latest_crawl_run_id": (latest or {}).get("crawl_run_id") or "",
                "latest_success_run_id": (success or {}).get("crawl_run_id") or "",
                "last_success_at": (success or {}).get("completed_at") or (success or {}).get("created_at") or "",
                "age_hours": None if age_hours is None else round(age_hours, 2),
                "freshness_threshold_hours": threshold,
                "stale": stale,
                "fetch_count_latest": fetch_count,
                "stored_objects_case_source": object_count,
                "source_quality": quality,
                "coverage_establishes_truth": False,
            })
        total = len(entries)
        recent = counts["covered_recent"]
        attempted = total - counts["not_attempted"]
        gaps: list[dict[str, Any]] = []
        for e in entries:
            if e["coverage_state"] == "not_attempted":
                gaps.append({"source_id": e["source_id"], "gap_type": "not_attempted", "priority": "high", "automatic_crawl": False})
            elif e["coverage_state"] == "attempted_failed":
                gaps.append({"source_id": e["source_id"], "gap_type": "attempt_failed", "priority": "high", "automatic_crawl": False})
            elif e["coverage_state"] == "covered_stale":
                gaps.append({"source_id": e["source_id"], "gap_type": "stale_evidence", "priority": "medium", "automatic_crawl": False})
            elif e["source_health"] in {"degraded", "blocked", "quarantined", "parser_failed", "fetch_failed"}:
                gaps.append({"source_id": e["source_id"], "gap_type": "source_health", "priority": "medium", "automatic_crawl": False})
        return {
            "policy": CRAWLER_POLICY,
            "case_id": case_id,
            "workflow_configured": bool(wf),
            "workflow_id": wf.get("workflow_id") or "",
            "expected_sources": total,
            "counts": counts,
            "recent_coverage_ratio": round(recent / total, 4) if total else 0.0,
            "attempted_ratio": round(attempted / total, 4) if total else 0.0,
            "entries": entries,
            "open_research_gaps": gaps,
            "coverage_is_truth_probability": False,
            "absence_is_nonexistence": False,
            "automatic_gap_closure": False,
            "network_execution": False,
        }

    def record_absence_observation(self, *, case_id: str, source_id: str, crawl_run_id: str, query_scope: str, observation: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        self.workflow374._authorize_monitor(identity, case_id)
        if str(confirmation or "").strip().upper() != "RECORD":
            raise PermissionError("explicit confirmation RECORD required")
        scope = str(query_scope or "").strip()
        note = str(observation or "").strip()
        if len(scope) < 4 or len(note) < 4:
            raise ValueError("bounded query scope and observation are required")
        run = self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=? AND case_id=? AND source_id=?", (crawl_run_id, case_id, source_id))
        if not run:
            raise KeyError(crawl_run_id)
        if run.get("status") != "succeeded":
            raise PermissionError("absence observation requires a succeeded bounded crawl run")
        ok_fetch = int((self.db.one("SELECT COUNT(*) c FROM phase15_crawl_fetches WHERE crawl_run_id=? AND status_code BETWEEN 200 AND 399", (crawl_run_id,)) or {}).get("c") or 0)
        if ok_fetch < 1:
            raise PermissionError("absence observation requires at least one successful fetch")
        actor = str(identity.get("username") or self.actor)[:120]
        core = {
            "policy": POLICY,
            "case_id": case_id,
            "source_id": source_id,
            "crawl_run_id": crawl_run_id,
            "query_scope": scope[:2000],
            "observation": note[:2000],
            "classification": "bounded_absence_observation",
            "counterevidence": False,
            "nonexistence_inferred": False,
            "requires_human_review": True,
            "recorded_by": actor,
        }
        payload = {**core, "observation_hash": _sha(core), "automatic_gap_closure": False}
        row = self.jobs.enqueue(job_type=ABSENCE_JOB, payload=payload, case_id=case_id, search_run_id=str(run.get("search_run_id") or ""), max_attempts=1, priority=900, resource_budget={"max_runtime_seconds": 1, "max_memory_mb": 32, "max_output_bytes": 4096}, rate_budget={"max_requests": 0, "requests_per_minute": 0}, idempotency_key="absence376:" + payload["observation_hash"])
        self.db.execute("UPDATE phase15_jobs SET status='succeeded',result_json=?,updated_at=? WHERE job_id=?", (_canon({"recorded": True, "observation_hash": payload["observation_hash"]}), _now(), row["job_id"]))
        self.audit.log("DOSSIER376_ABSENCE_OBSERVATION_RECORDED", "case", case_id, case_id=case_id, details={"job_id": row["job_id"], "source_id": source_id, "crawl_run_id": crawl_run_id, "observation_hash": payload["observation_hash"], "counterevidence": False, "nonexistence_inferred": False, "policy": POLICY})
        return {"job_id": row["job_id"], **payload, "network_execution": False}

    def absence_observations(self, *, case_id: str, identity: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        if identity is not None:
            self.workflow374._authorize_monitor(identity, case_id)
        out: list[dict[str, Any]] = []
        rows = self.db.all("SELECT * FROM phase15_jobs WHERE case_id=? AND job_type=? AND status='succeeded' ORDER BY created_at DESC LIMIT 200", (case_id, ABSENCE_JOB))
        for row in rows:
            p = _j(row.get("payload_json"), {}) or {}
            core = {k: p.get(k) for k in ("policy", "case_id", "source_id", "crawl_run_id", "query_scope", "observation", "classification", "counterevidence", "nonexistence_inferred", "requires_human_review", "recorded_by")}
            valid = p.get("policy") == POLICY and p.get("case_id") == case_id and p.get("classification") == "bounded_absence_observation" and p.get("counterevidence") is False and p.get("nonexistence_inferred") is False and p.get("observation_hash") == _sha(core)
            run = self.db.one("SELECT status FROM phase15_crawl_runs WHERE crawl_run_id=? AND case_id=? AND source_id=?", (p.get("crawl_run_id") or "", case_id, p.get("source_id") or ""))
            valid = bool(valid and run and run.get("status") == "succeeded")
            out.append({"job_id": row["job_id"], **p, "integrity_valid": valid, "usable_in_dossier": valid, "absence_is_nonexistence": False})
        return out

    def dossier_packet(self, *, case_id: str, as_of: str | None = None, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        coverage = self.source_coverage(case_id=case_id, as_of=as_of, identity=identity)
        absence = self.absence_observations(case_id=case_id, identity=identity)
        valid_absence = [x for x in absence if x.get("usable_in_dossier")]
        stale = [e for e in coverage["entries"] if e.get("stale")]
        invalid_absence = [x for x in absence if not x.get("integrity_valid")]
        return {
            "policy": POLICY,
            "case_id": case_id,
            "source_coverage": coverage,
            "negative_evidence": {
                "bounded_absence_observations": valid_absence,
                "invalid_or_quarantined_observations": len(invalid_absence),
                "absence_is_counterevidence_by_default": False,
                "absence_is_nonexistence": False,
                "requires_scope_and_successful_fetch": True,
            },
            "staleness_register": stale,
            "open_research_gaps": coverage["open_research_gaps"],
            "research_gap_count": len(coverage["open_research_gaps"]),
            "automatic_gap_closure": False,
            "automatic_crawl_from_gap": False,
            "direct_network_authority": False,
            "requires_human_review": True,
        }

    def enrich_dossier(self, *, case_id: str, dossier: Mapping[str, Any] | None, as_of: str | None = None) -> dict[str, Any]:
        out = dict(dossier or {})
        packet = self.dossier_packet(case_id=case_id, as_of=as_of)
        out["phase16_dossier_vnext_v376"] = packet
        uncertainties = list(out.get("uncertainties") or [])
        for item in (
            "Absence observations describe a bounded search result; they do not prove non-existence.",
            "Stale evidence may no longer describe current conditions and must be refreshed or qualified.",
            "Coverage metrics describe research completeness, not truth probability.",
        ):
            if item not in uncertainties:
                uncertainties.append(item)
        out["uncertainties"] = uncertainties
        metrics = dict(out.get("metrics") or {})
        metrics.update({
            "source_scope_expected": packet["source_coverage"]["expected_sources"],
            "source_scope_recently_covered": packet["source_coverage"]["counts"]["covered_recent"],
            "source_scope_stale": packet["source_coverage"]["counts"]["covered_stale"],
            "source_scope_gaps": packet["research_gap_count"],
            "bounded_absence_observations": len(packet["negative_evidence"]["bounded_absence_observations"]),
        })
        out["metrics"] = metrics
        out["research_gap_review_required"] = bool(packet["research_gap_count"])
        out["absence_observation_review_required"] = bool(packet["negative_evidence"]["bounded_absence_observations"])
        out["lead_review_required"] = True
        return out

    def build_vnext_report(self, *, case_id: str, base_dossier: Mapping[str, Any] | None = None, refresh_hypotheses: bool = True) -> dict[str, Any]:
        if base_dossier is None:
            raise ValueError("base dossier required; Build 376 does not silently trigger research")
        dossier = self.enrich_dossier(case_id=case_id, dossier=base_dossier)
        core = {k: v for k, v in dossier.items() if k not in {"report_id", "content_hash", "speech_text", "generated_at"}}
        content_hash = _sha(core)
        report_id = "dossier376_" + content_hash[:24]
        dossier["dossier_version"] = "v376"
        dossier["content_hash"] = content_hash
        dossier["report_id"] = report_id
        dossier["generated_at"] = _now()
        if not self.db.one("SELECT report_id FROM professional_reports WHERE report_id=?", (report_id,)):
            sections = {
                "facts": dossier.get("facts") or [],
                "hypotheses": dossier.get("hypotheses") or [],
                "conflicts": dossier.get("counterevidence_and_conflicts") or [],
                "open_questions": dossier.get("open_questions") or [],
                "metrics": dossier.get("metrics") or {},
                "coverage": dossier.get("phase16_dossier_vnext_v376") or {},
            }
            self.db.execute(
                "INSERT INTO professional_reports(report_id,case_id,report_type,audience,redaction_profile,readiness_status,executive_summary,methodology,source_critique_json,uncertainty_register_json,evidence_annex_json,section_manifest_json,export_paths_json,content_hash,created_at,created_by,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (report_id, case_id, "phase16_ai_dossier_v376", "investigation_team", "internal_review", "draft_review_required", str(dossier.get("executive_summary") or ""), "Evidence-first dossier vNext with explicit source coverage, bounded absence observations, staleness and research gaps. Absence is never auto-promoted to non-existence or counterevidence.", _canon({"coverage_is_truth_probability": False, "source_independence_not_assumed": True}), _canon(dossier.get("uncertainties") or []), _canon(dossier.get("provenance_annex") or []), _canon(sections), "[]", content_hash, dossier["generated_at"], self.actor, "AI-generated/recomposed draft; human review required before release."),
            )
        return dossier


class AutonomousInvestigation376:
    def __init__(self, *, base375: Any, dossier376: DossierVNext376) -> None:
        self.base375 = base375
        self.dossier376 = dossier376

    def status(self) -> dict[str, Any]:
        base = dict(self.base375.status())
        base.update({"policy_version": AI_POLICY, "dossier_vnext_awareness": True, "source_coverage_awareness": True, "negative_evidence_semantics": True, "staleness_awareness": True, "automatic_gap_closure": False, "direct_crawl_execution_authority": False, "automatic_scope_expansion": False})
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base375.run_cycle(case_id=case_id, max_ticks=max_ticks)
        if not isinstance(out, dict):
            out = {"case_id": case_id, "state": "unknown"}
        out["dossier"] = self.dossier376.enrich_dossier(case_id=case_id, dossier=out.get("dossier") if isinstance(out.get("dossier"), dict) else {})
        return out


class DefensiveOpsecSupervisor376:
    def __init__(self, db: Any, audit: Any, *, base375: Any, dossier376: DossierVNext376, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base375 = base375
        self.dossier376 = dossier376
        self.jobs = jobs

    def status(self) -> dict[str, Any]:
        base = dict(self.base375.status())
        base.update({"policy_version": OPSEC_POLICY, "absence_observation_integrity_monitor": True, "automatic_gap_closure_monitor": True, "auto_gap_crawl_block": True, "system_mutations": False})
        return base

    def protect_remote_session(self, **kw: Any) -> dict[str, Any]:
        return self.base375.protect_remote_session(**kw)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        invalid_absence = [x for x in self.dossier376.absence_observations(case_id=case_id) if not x.get("integrity_valid")]
        cancelled: list[str] = []
        invalid_gap_jobs: list[dict[str, Any]] = []
        rows = self.db.all("SELECT * FROM phase15_jobs WHERE case_id=? AND job_type IN ('governed_crawl_v1','governed_tor_crawl_v370') AND status IN ('queued','running','workflow_paused')", (case_id,))
        for row in rows:
            p = _j(row.get("payload_json"), {}) or {}
            if p.get("automatic_gap_closure") is True or p.get("phase16_dossier_gap_auto_crawl_v376") is True:
                invalid_gap_jobs.append({"job_id": row["job_id"], "reason": "automatic_gap_closure_prohibited"})
                if row.get("status") in {"queued", "workflow_paused"}:
                    self.jobs.cancel(row["job_id"], actor="opsec376")
                    cancelled.append(row["job_id"])
        if invalid_absence or invalid_gap_jobs:
            self.audit.log("OPSEC376_DOSSIER_BOUNDARY", "case", case_id, case_id=case_id, details={"invalid_absence_job_ids": [x["job_id"] for x in invalid_absence], "invalid_gap_jobs": invalid_gap_jobs, "cancelled_gap_jobs": cancelled, "policy": OPSEC_POLICY})
        base = self.base375.protect_case(case_id=case_id)
        return {**base, "invalid_absence_observations": [x["job_id"] for x in invalid_absence], "invalid_gap_jobs": invalid_gap_jobs, "cancelled_gap_jobs": cancelled, "policy_version": OPSEC_POLICY, "system_mutations": False}
