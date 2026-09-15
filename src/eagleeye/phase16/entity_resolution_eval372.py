from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable, Mapping

POLICY = "phase16.entity-resolution-eval.v372"
SOURCE_QUALITY_POLICY = "phase16.crawler-source-quality.v372"
AI_POLICY = "phase16.autonomous-investigation.v372"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v372"
POSITIVE_CLASSES = {"strong_review_candidate", "possible_review_candidate"}
DEFER_CLASSES = {"weak_review_candidate", "insufficient"}
DISTINCT_CLASSES = {"likely_distinct"}
GROUND_TRUTHS = {"same_entity", "distinct", "ambiguous"}


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default


def _rate(n: int, d: int) -> float:
    return round(float(n) / float(d), 6) if d else 0.0


def _wilson(successes: int, total: int, z: float = 1.96) -> dict[str, float]:
    if total <= 0:
        return {"low": 0.0, "high": 0.0}
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    margin = (z / den) * math.sqrt((p * (1 - p) / total) + (z * z / (4 * total * total)))
    return {"low": round(max(0.0, center - margin), 6), "high": round(min(1.0, center + margin), 6)}


def _prediction(classification: str) -> str:
    if classification in POSITIVE_CLASSES:
        return "review_positive"
    if classification in DISTINCT_CLASSES:
        return "distinct"
    return "defer"


class EntityResolutionEvaluation372:
    """Offline, review-oriented calibration for Build-371 Entity Resolution v2.

    It evaluates already-produced comparison decisions against analyst supplied
    holdout labels. It does not alter the production scorer, confirm identities,
    approve links, or perform network access.
    """

    def __init__(self, db: Any, audit: Any, *, entity371: Any, governance: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.entity371 = entity371
        self.governance = governance
        self.actor = actor

    def _authorize(self, identity: dict[str, Any], case_id: str) -> None:
        self.governance.authorize(identity, case_id=case_id, capability="research.run", object_type="entity_resolution_eval", object_id=case_id)

    def comparison_record(self, *, case_id: str, comparison_id: str) -> dict[str, Any]:
        row = self.entity371.base.comparison(comparison_id)
        if row["case_id"] != case_id:
            raise PermissionError("cross-case evaluation prohibited")
        v2 = dict((row.get("explanation") or {}).get("v371") or {})
        return {
            "comparison_id": comparison_id,
            "case_id": case_id,
            "classification": str(row.get("classification") or "insufficient"),
            "prediction": _prediction(str(row.get("classification") or "insufficient")),
            "evidence_weight": float(v2.get("evidence_weight") or row.get("total_score") or 0.0),
            "strong_identifier_conflict_veto": bool(v2.get("strong_identifier_conflict_veto")),
            "common_name_count": int(v2.get("common_name_count") or 0),
            "common_name_penalty": float(v2.get("common_name_penalty") or 0.0),
            "independent_source_count": int(v2.get("independent_source_count") or 0),
            "review_required": True,
            "score_is_probability": False,
            "automatic_merge": False,
        }

    def evaluate_labeled(self, *, case_id: str, labeled: Iterable[Mapping[str, Any]], identity: dict[str, Any], evaluation_name: str = "analyst_holdout") -> dict[str, Any]:
        self._authorize(identity, case_id)
        actor = str(identity.get("username") or self.actor)
        records: list[dict[str, Any]] = []
        for item in labeled:
            truth = str(item.get("ground_truth") or "").strip()
            if truth not in GROUND_TRUTHS:
                raise ValueError("ground_truth must be same_entity, distinct, or ambiguous")
            rec = self.comparison_record(case_id=case_id, comparison_id=str(item.get("comparison_id") or ""))
            rec.update({"ground_truth": truth, "cohort": str(item.get("cohort") or "general")[:120], "scenario_id": str(item.get("scenario_id") or rec["comparison_id"])[:160]})
            records.append(rec)
        report = self.evaluate_records(records, evaluation_name=evaluation_name)
        self.audit.log("ENTITY372_HOLDOUT_EVALUATED", "entity_resolution_eval", report["evaluation_id"], case_id=case_id, details={"evaluation_name": evaluation_name, "metrics": report["metrics"], "gate": report["gate"], "record_count": len(records)})
        report["case_id"] = case_id
        report["actor"] = actor
        return report

    def evaluate_records(self, records: Iterable[Mapping[str, Any]], *, evaluation_name: str = "holdout") -> dict[str, Any]:
        rows = [dict(r) for r in records]
        if not rows:
            raise ValueError("evaluation requires at least one labeled record")
        binary = [r for r in rows if r.get("ground_truth") in {"same_entity", "distinct"}]
        same = [r for r in binary if r["ground_truth"] == "same_entity"]
        distinct = [r for r in binary if r["ground_truth"] == "distinct"]
        positives = [r for r in binary if r.get("prediction") == "review_positive"]
        unsafe_false_links = [r for r in distinct if r.get("prediction") == "review_positive"]
        false_distinct = [r for r in same if r.get("prediction") == "distinct"]
        same_candidates = [r for r in same if r.get("prediction") == "review_positive"]
        correct_positive = [r for r in positives if r.get("ground_truth") == "same_entity"]
        deferred = [r for r in rows if r.get("prediction") == "defer"]
        conflict_rows = [r for r in distinct if r.get("strong_identifier_conflict_veto")]
        conflict_escapes = [r for r in conflict_rows if r.get("prediction") != "distinct"]
        common_rows = [r for r in distinct if int(r.get("common_name_count") or 0) >= 3]
        common_false_links = [r for r in common_rows if r.get("prediction") == "review_positive"]
        strong_rows = [r for r in rows if r.get("classification") == "strong_review_candidate"]
        strong_false_links = [r for r in strong_rows if r.get("ground_truth") == "distinct"]
        metrics = {
            "records": len(rows),
            "binary_records": len(binary),
            "same_entity_records": len(same),
            "distinct_records": len(distinct),
            "ambiguous_records": sum(1 for r in rows if r.get("ground_truth") == "ambiguous"),
            "review_positive_count": len(positives),
            "defer_count": len(deferred),
            "unsafe_false_link_count": len(unsafe_false_links),
            "unsafe_false_link_rate": _rate(len(unsafe_false_links), len(distinct)),
            "review_positive_precision": _rate(len(correct_positive), len(positives)),
            "same_entity_candidate_recall": _rate(len(same_candidates), len(same)),
            "false_distinct_count": len(false_distinct),
            "false_distinct_rate": _rate(len(false_distinct), len(same)),
            "defer_rate": _rate(len(deferred), len(rows)),
            "strong_identifier_conflict_cases": len(conflict_rows),
            "strong_identifier_conflict_escape_count": len(conflict_escapes),
            "strong_identifier_conflict_escape_rate": _rate(len(conflict_escapes), len(conflict_rows)),
            "common_name_distinct_cases": len(common_rows),
            "common_name_false_link_rate": _rate(len(common_false_links), len(common_rows)),
            "strong_review_count": len(strong_rows),
            "strong_review_false_link_rate": _rate(len(strong_false_links), len(strong_rows)),
            "unsafe_false_link_wilson95": _wilson(len(unsafe_false_links), len(distinct)),
        }
        cohorts: dict[str, dict[str, Any]] = {}
        for cohort in sorted({str(r.get("cohort") or "general") for r in rows}):
            cr = [r for r in rows if str(r.get("cohort") or "general") == cohort]
            cd = [r for r in cr if r.get("ground_truth") == "distinct"]
            cs = [r for r in cr if r.get("ground_truth") == "same_entity"]
            cohorts[cohort] = {
                "records": len(cr),
                "false_link_rate": _rate(sum(1 for r in cd if r.get("prediction") == "review_positive"), len(cd)),
                "same_entity_candidate_recall": _rate(sum(1 for r in cs if r.get("prediction") == "review_positive"), len(cs)),
                "defer_rate": _rate(sum(1 for r in cr if r.get("prediction") == "defer"), len(cr)),
            }
        checks = {
            "minimum_binary_holdout_12": len(binary) >= 12,
            "both_binary_classes_present": bool(same and distinct),
            "unsafe_false_link_rate_le_005": metrics["unsafe_false_link_rate"] <= 0.05,
            "strong_review_false_link_rate_le_002": metrics["strong_review_false_link_rate"] <= 0.02,
            "strong_identifier_conflict_escape_zero": metrics["strong_identifier_conflict_escape_count"] == 0,
            "common_name_false_link_rate_le_005": metrics["common_name_false_link_rate"] <= 0.05,
            "false_distinct_rate_le_005": metrics["false_distinct_rate"] <= 0.05,
            "review_positive_precision_ge_090": metrics["review_positive_precision"] >= 0.90,
            "same_entity_candidate_recall_ge_080": metrics["same_entity_candidate_recall"] >= 0.80,
            "defer_rate_le_060": metrics["defer_rate"] <= 0.60,
        }
        evaluation_id = "eval372_" + _sha({"name": evaluation_name, "rows": rows})[:20]
        return {
            "policy": POLICY,
            "evaluation_id": evaluation_id,
            "evaluation_name": str(evaluation_name)[:160],
            "metrics": metrics,
            "cohorts": cohorts,
            "gate": {"checks": checks, "passed": all(bool(v) for v in checks.values())},
            "records": rows,
            "score_is_probability": False,
            "automatic_threshold_change": False,
            "automatic_merge": False,
            "production_scorer_mutated": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "offline_holdout_evaluation": True,
            "false_link_metrics": True,
            "false_distinct_metrics": True,
            "common_name_cohort": True,
            "strong_conflict_escape_metric": True,
            "wilson_interval": True,
            "automatic_threshold_change": False,
            "score_is_probability": False,
            "automatic_merge": False,
            "network_execution": False,
            "real_person_training_data_required": False,
        }


class CrawlerSourceQuality372:
    """Calibrated source-quality annotation for crawler→entity review leads.

    Quality is a bounded evidence-quality heuristic, never an identity probability
    and never authority to merge or skip review.
    """

    def __init__(self, db: Any, audit: Any, *, crawler371: Any, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.crawler371 = crawler371
        self.jobs = jobs

    @staticmethod
    def score_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        kind = str(snapshot.get("source_kind") or "unknown").casefold()
        if any(x in kind for x in ("official", "government", "authority", "register", "registry", "court")):
            base = 78
        elif any(x in kind for x in ("licensed", "primary", "public_api", "api")):
            base = 70
        elif "archive" in kind:
            base = 64
        elif any(x in kind for x in ("news", "publication")):
            base = 56
        elif any(x in kind for x in ("public", "web", "clearnet")):
            base = 50
        else:
            base = 38
        signals: list[str] = []
        penalties: list[str] = []
        score = base
        if snapshot.get("review_status") == "approved_read_only":
            score += 10; signals.append("human_source_review")
        if bool(snapshot.get("hash_verified")):
            score += 6; signals.append("content_hash")
        if bool(snapshot.get("http_success")):
            score += 4; signals.append("successful_fetch")
        if str(snapshot.get("source_health") or "").casefold() in {"healthy", "ok", "good", "unknown"}:
            score += 3; signals.append("non_failing_source_health")
        if bool(snapshot.get("terms_ref_present")):
            score += 3; signals.append("terms_reference")
        if bool(snapshot.get("replay_or_fixture")):
            score -= 12; penalties.append("replay_or_fixture_not_external_validation")
        if bool(snapshot.get("degraded")):
            score -= 20; penalties.append("source_degraded")
        if bool(snapshot.get("contradicted")):
            score -= 25; penalties.append("source_contradicted")
        if bool(snapshot.get("stale")):
            score -= 12; penalties.append("source_stale")
        score = max(0, min(100, int(score)))
        band = "high" if score >= 80 else "medium" if score >= 60 else "low" if score >= 40 else "very_low"
        return {
            "policy": SOURCE_QUALITY_POLICY,
            "quality_score": score,
            "quality_band": band,
            "signals": signals,
            "penalties": penalties,
            "score_is_identity_probability": False,
            "can_confirm_identity": False,
            "can_skip_human_review": False,
            "automatic_merge": False,
        }

    def provenance_quality(self, *, crawl_run_id: str, fetch_id: str | None = None) -> dict[str, Any]:
        prov = self.crawler371.provenance(crawl_run_id=crawl_run_id, fetch_id=fetch_id)
        policy = self.db.one("SELECT source_health,terms_ref,auth_type FROM phase15_crawler_policies WHERE source_id=?", (prov["source_id"],)) or {}
        run = self.db.one("SELECT summary_json FROM phase15_crawl_runs WHERE crawl_run_id=?", (crawl_run_id,)) or {}
        summary = _j(run.get("summary_json"), {}) or {}
        fetches = list(prov.get("fetches") or [])
        success = any(200 <= int(f.get("status_code") or 0) < 400 for f in fetches)
        hash_verified = any(bool(f.get("content_sha256")) and len(str(f.get("content_sha256"))) == 64 for f in fetches)
        transport_kind = str(summary.get("transport_kind") or "")
        replay = transport_kind.startswith("static") or bool(summary.get("replay_or_fixture"))
        health = str(policy.get("source_health") or "unknown")
        snapshot = {
            "source_kind": prov["source"].get("source_kind"),
            "review_status": prov["source"].get("review_status"),
            "hash_verified": hash_verified,
            "http_success": success,
            "source_health": health,
            "terms_ref_present": bool(str(policy.get("terms_ref") or "").strip()),
            "replay_or_fixture": replay,
            "degraded": health.casefold() in {"degraded", "failing", "blocked", "quarantined"},
        }
        quality = self.score_snapshot(snapshot)
        return {
            "policy": SOURCE_QUALITY_POLICY,
            "case_id": prov["case_id"],
            "source_id": prov["source_id"],
            "crawl_run_id": crawl_run_id,
            "fetch_id": str(fetch_id or ""),
            "provenance_hash": prov["provenance_hash"],
            "source_snapshot": snapshot,
            "quality": quality,
            "used_for_auto_identity_decision": False,
            "automatic_merge": False,
        }

    def lead_quality_packet(self, *, job_id: str) -> dict[str, Any]:
        job = self.jobs.get(job_id)
        if str(job.get("job_type")) != "entity_link_lead_v371":
            raise ValueError("job is not an entity-link lead")
        payload = _j(job.get("payload_json"), {}) or {}
        quality = self.provenance_quality(crawl_run_id=str(payload.get("crawl_run_id") or ""), fetch_id=str(payload.get("fetch_id") or "") or None)
        result = _j(job.get("result_json"), {}) or {}
        packet = {
            "policy": SOURCE_QUALITY_POLICY,
            "job_id": job_id,
            "case_id": job.get("case_id"),
            "job_status": job.get("status"),
            "classification": result.get("classification", "not_analyzed"),
            "quality": quality,
            "review_required": True,
            "source_quality_can_confirm_identity": False,
            "automatic_merge": False,
        }
        return packet

    def case_summary(self, *, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT job_id FROM phase15_jobs WHERE job_type='entity_link_lead_v371' AND case_id=? ORDER BY created_at DESC LIMIT 200", (case_id,))
        packets: list[dict[str, Any]] = []
        for row in rows:
            try:
                packets.append(self.lead_quality_packet(job_id=row["job_id"]))
            except Exception:
                continue
        bands = {"high": 0, "medium": 0, "low": 0, "very_low": 0}
        for p in packets:
            band = str((p.get("quality") or {}).get("quality", {}).get("quality_band") or "very_low")
            bands[band] = bands.get(band, 0) + 1
        return {"policy": SOURCE_QUALITY_POLICY, "case_id": case_id, "lead_count": len(packets), "quality_bands": bands, "packets": packets, "automatic_merge": False}

    def calibration_contract(self) -> dict[str, Any]:
        samples = {
            "official_reviewed_hashed": self.score_snapshot({"source_kind": "official_register", "review_status": "approved_read_only", "hash_verified": True, "http_success": True, "source_health": "healthy", "terms_ref_present": True}),
            "public_web_reviewed_hashed": self.score_snapshot({"source_kind": "public_web", "review_status": "approved_read_only", "hash_verified": True, "http_success": True, "source_health": "healthy", "terms_ref_present": True}),
            "unknown_unreviewed": self.score_snapshot({"source_kind": "unknown", "review_status": "pending", "hash_verified": False, "http_success": False, "source_health": "degraded", "terms_ref_present": False}),
        }
        monotonic = samples["official_reviewed_hashed"]["quality_score"] > samples["public_web_reviewed_hashed"]["quality_score"] > samples["unknown_unreviewed"]["quality_score"]
        return {"policy": SOURCE_QUALITY_POLICY, "samples": samples, "monotonic_reference_order": monotonic, "automatic_threshold_change": False, "identity_probability": False}

    def status(self) -> dict[str, Any]:
        return {
            "policy": SOURCE_QUALITY_POLICY,
            "crawler_source_quality_annotation": True,
            "source_quality_calibration": True,
            "lead_quality_packet": True,
            "no_new_network_authority": True,
            "score_is_identity_probability": False,
            "automatic_identity_confirmation": False,
            "automatic_merge": False,
            "new_per_build_data_tables": 0,
        }


class AutonomousInvestigation372:
    def __init__(self, *, base371: Any, eval372: EntityResolutionEvaluation372, source_quality372: CrawlerSourceQuality372) -> None:
        self.base371 = base371
        self.eval372 = eval372
        self.source_quality372 = source_quality372

    def status(self) -> dict[str, Any]:
        base = dict(self.base371.status())
        base.update({
            "policy_version": AI_POLICY,
            "entity_eval_awareness": True,
            "source_quality_awareness": True,
            "source_quality_is_identity_probability": False,
            "automatic_threshold_tuning": False,
            "automatic_entity_merge": False,
            "direct_merge_approval_authority": False,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base371.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            dossier["phase16_entity_eval_v372"] = {
                "holdout_required_for_threshold_change": True,
                "automatic_threshold_tuning": False,
                "score_is_probability": False,
                "crawler_source_quality": self.source_quality372.case_summary(case_id=case_id)["quality_bands"],
                "automatic_merge": False,
            }
        return out


class DefensiveOpsecSupervisor372:
    def __init__(self, db: Any, audit: Any, *, base371: Any, jobs: Any) -> None:
        self.db = db
        self.audit = audit
        self.base371 = base371
        self.jobs = jobs

    def status(self) -> dict[str, Any]:
        base = dict(self.base371.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "entity_eval_boundary_monitor": True,
            "source_quality_cannot_bypass_review": True,
            "automatic_threshold_mutation": False,
            "automatic_merge_authority": False,
            "system_mutations": False,
        })
        return base

    def protect_remote_session(self, **kw: Any) -> dict[str, Any]:
        return self.base371.protect_remote_session(**kw)

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        # Capture the Build-372 semantic violation before Build 371 performs its
        # lower-level provenance/payload quarantine, so the reason remains auditable.
        violations: list[str] = []
        rows = self.db.all("SELECT job_id,payload_json,result_json,status FROM phase15_jobs WHERE job_type='entity_link_lead_v371' AND case_id=? AND status IN ('queued','running','succeeded')", (case_id,))
        for row in rows:
            p = _j(row.get("payload_json"), {}) or {}
            r = _j(row.get("result_json"), {}) or {}
            if p.get("automatic_merge") is not False or r.get("automatic_merge") is True or r.get("identity_confirmed") is True:
                violations.append(row["job_id"])
        base = self.base371.protect_case(case_id=case_id)
        cancelled: list[str] = []
        inherited_cancelled = set(base.get("cancelled_invalid_entity_lead_jobs") or [])
        for jid in violations:
            row = self.db.one("SELECT status FROM phase15_jobs WHERE job_id=?", (jid,)) or {}
            if row.get("status") in {"queued", "running"}:
                self.jobs.cancel(jid, actor="opsec372")
                cancelled.append(jid)
            elif jid in inherited_cancelled:
                cancelled.append(jid)
        if violations:
            self.audit.log("OPSEC372_ENTITY_EVAL_BOUNDARY", "case", case_id, case_id=case_id, details={"violations": violations, "cancelled": cancelled, "policy": OPSEC_POLICY})
        return {**base, "entity_eval_boundary_violations": violations, "cancelled_entity_eval_jobs": cancelled, "policy_version": OPSEC_POLICY, "system_mutations": False, "automatic_merge_authority": False}
