from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

SOURCE_CLASSES = {"primary_official", "institutional", "professional_press", "specialist", "aggregator", "user_generated", "unknown"}
CHANGE_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}
ENVELOPE_DESTINATIONS = {"local_only", "guided_browser", "search_provider", "external_ai", "human_reviewer"}
PROHIBITED_CLASSES = {"biometric_template", "face_embedding", "remote_biometric_identification", "health", "religion", "political_opinion", "sexual_orientation"}
IMAGE_DATA_CLASSES = {"image", "face_crop", "photo_metadata"}
PHOTO_PROVIDERS = (
    ("google_lens", "Google Lens", "https://lens.google.com/"),
    ("bing_visual", "Bing Visual Search", "https://www.bing.com/visualsearch"),
    ("tineye", "TinEye", "https://tineye.com/"),
    ("yandex_images", "Yandex Images", "https://yandex.com/images/"),
)


def _safe_text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _canonical_url(value: str) -> str:
    raw = _safe_text(value, 4000)
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return raw
    host = parts.hostname.lower()
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    return urlunsplit((parts.scheme.lower(), host + port, parts.path or "/", parts.query, ""))


def _normalize_content(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", str(value or ""), flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()[:1_000_000]


class Build141Service:
    """Source quality, change monitoring, bounded OPSEC and workflow efficiency.

    All network-facing activity remains manual. Build 141 evaluates locally stored
    evidence and plans; it does not fetch pages, upload images, call external AI,
    identify people from faces or silently alter evidentiary conclusions.
    """

    BUILD = "141.0"

    def __init__(self, db: Any, audit: Any, base_dir: Any, install_dir: Any, *, build140: Any, build139: Any, build138: Any, build137: Any, build136: Any, build135: Any, protection: Any) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = base_dir
        self.install_dir = install_dir
        self.build140 = build140
        self.build139 = build139
        self.build138 = build138
        self.build137 = build137
        self.build136 = build136
        self.build135 = build135
        self.protection = protection

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        return row

    def _source(self, case_id: str, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_sources_138 WHERE case_id=? AND source_id=?", (case_id, source_id))
        if not row:
            raise KeyError("Quelle nicht gefunden oder falscher Fall")
        row["metadata"] = loads(row.get("metadata_json"), {})
        return row

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build141_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        event_id, created_at = new_id("evt141"), now_ts()
        canonical = dumps({"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": dict(payload or {}), "previous_hash": previous_hash, "created_by": _safe_text(actor, 120), "created_at": created_at})
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.db.execute("INSERT INTO build141_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, dumps(dict(payload or {})), previous_hash, event_hash, _safe_text(actor, 120), created_at))
        self.audit.log(event_type, object_type, object_id, case_id, dict(payload or {}))

    # ---------- source quality and monitoring ----------
    @staticmethod
    def _classify_source(row: Mapping[str, Any]) -> str:
        kind = str(row.get("source_type") or "unknown")
        url = str(row.get("canonical_url") or "")
        host = (urlsplit(url).hostname or "").lower()
        if kind in {"primary", "official", "registry", "court", "government"} or host.endswith((".gov", ".gov.uk", ".europa.eu")):
            return "primary_official"
        if kind in {"institutional", "academic", "company", "organization"} or host.endswith((".edu", ".ac.uk")):
            return "institutional"
        if kind in {"press", "news"}:
            return "professional_press"
        if kind in {"specialist", "publication"}:
            return "specialist"
        if kind in {"aggregator", "directory", "mirror"}:
            return "aggregator"
        if kind in {"social", "forum", "user_generated"}:
            return "user_generated"
        return "unknown"

    def assess_source_quality(self, *, case_id: str, source_id: str, actor: str) -> dict[str, Any]:
        row = self._source(case_id, source_id)
        classification = self._classify_source(row)
        base = {
            "primary_official": (0.96, 0.96, 0.94, 0.86, 0.92),
            "institutional": (0.86, 0.78, 0.88, 0.82, 0.84),
            "professional_press": (0.74, 0.58, 0.78, 0.76, 0.72),
            "specialist": (0.72, 0.62, 0.76, 0.72, 0.70),
            "aggregator": (0.42, 0.28, 0.46, 0.34, 0.44),
            "user_generated": (0.32, 0.24, 0.34, 0.38, 0.30),
            "unknown": (0.28, 0.22, 0.28, 0.30, 0.28),
        }[classification]
        authority, primary, traceability, independence, transparency = base
        if row.get("author"): traceability += 0.05
        if row.get("publisher"): transparency += 0.05
        if row.get("content_hash"): traceability += 0.08
        if row.get("parent_source_id"): independence -= 0.18
        if not row.get("canonical_url"): traceability -= 0.20
        retrieved = _parse_time(str(row.get("retrieved_at") or ""))
        age_days = (datetime.now(timezone.utc) - retrieved).days if retrieved else 365
        freshness = 0.95 if age_days <= 7 else 0.82 if age_days <= 30 else 0.68 if age_days <= 180 else 0.48 if age_days <= 730 else 0.28
        changes = self.db.all("SELECT severity,change_type FROM source_change_events_141 WHERE source_id=? AND status='open'", (source_id,))
        stability = 0.92 - min(0.65, sum(0.22 if c["severity"] == "high" else 0.10 for c in changes))
        reliability = _clamp(row.get("reliability"), 0, 1)
        authority = (authority * 0.75) + (reliability * 0.25)
        values = [authority, primary, traceability, independence, freshness, stability, transparency]
        values = [_clamp(v) for v in values]
        overall = round(sum(v * w for v, w in zip(values, (0.20, 0.18, 0.15, 0.15, 0.10, 0.12, 0.10))), 4)
        band = "high" if overall >= 0.78 else "medium" if overall >= 0.52 else "low"
        strengths, weaknesses = [], []
        labels = ("Autorität", "Primärnähe", "Nachvollziehbarkeit", "Unabhängigkeit", "Aktualität", "Stabilität", "Transparenz")
        for label, value in zip(labels, values):
            (strengths if value >= 0.75 else weaknesses if value < 0.50 else []).append(f"{label}: {value:.2f}")
        assessment_id, now = new_id("sq141"), now_ts()
        self.db.execute(
            "INSERT INTO source_quality_assessments_141(assessment_id,case_id,source_id,classification,authority_score,primary_score,traceability_score,independence_score,freshness_score,stability_score,transparency_score,overall_score,quality_band,strengths_json,weaknesses_json,review_required,assessed_by,assessed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(case_id,source_id) DO UPDATE SET classification=excluded.classification,authority_score=excluded.authority_score,primary_score=excluded.primary_score,traceability_score=excluded.traceability_score,independence_score=excluded.independence_score,freshness_score=excluded.freshness_score,stability_score=excluded.stability_score,transparency_score=excluded.transparency_score,overall_score=excluded.overall_score,quality_band=excluded.quality_band,strengths_json=excluded.strengths_json,weaknesses_json=excluded.weaknesses_json,review_required=excluded.review_required,assessed_by=excluded.assessed_by,assessed_at=excluded.assessed_at",
            (assessment_id, case_id, source_id, classification, *values, overall, band, dumps(strengths), dumps(weaknesses), int(band != "high"), _safe_text(actor, 120), now),
        )
        self._event(case_id=case_id, event_type="source_quality_assessed_141", object_type="evidence_source_138", object_id=source_id, actor=actor, payload={"quality_band": band, "overall_score": overall})
        return self.source_quality(case_id=case_id, source_id=source_id)

    def source_quality(self, *, case_id: str, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT q.*,s.title,s.canonical_url,s.source_type FROM source_quality_assessments_141 q JOIN evidence_sources_138 s ON s.source_id=q.source_id WHERE q.case_id=? AND q.source_id=?", (case_id, source_id))
        if not row:
            raise KeyError("Quellenbewertung nicht gefunden")
        row["strengths"] = loads(row.pop("strengths_json", "[]"), [])
        row["weaknesses"] = loads(row.pop("weaknesses_json", "[]"), [])
        return row

    def record_source_snapshot(self, *, case_id: str, source_id: str, observed_url: str, observed_title: str, observed_text: str, http_status: int | None, actor: str) -> dict[str, Any]:
        source = self._source(case_id, source_id)
        normalized = _normalize_content(observed_text)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        canonical = _canonical_url(observed_url or source.get("canonical_url") or "")
        status_code = int(http_status) if http_status is not None else None
        availability = "available" if status_code is None or 200 <= status_code < 400 else "unavailable"
        previous = self.db.one("SELECT * FROM source_snapshots_141 WHERE source_id=? ORDER BY observed_at DESC LIMIT 1", (source_id,))
        snapshot_id, now = new_id("snap141"), now_ts()
        self.db.execute("INSERT INTO source_snapshots_141(snapshot_id,case_id,source_id,observed_url,observed_title,normalized_text_sha256,normalized_text_length,http_status,availability_status,content_excerpt,observed_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (snapshot_id, case_id, source_id, canonical, _safe_text(observed_title or source.get("title"), 1000), digest, len(normalized), status_code, availability, normalized[:2000], now, _safe_text(actor, 120)))
        change_types: list[str] = []
        if not previous:
            change_types.append("first_seen")
        else:
            if previous.get("availability_status") != availability: change_types.append("availability_changed")
            if str(previous.get("observed_url") or "") != canonical: change_types.append("redirect_or_url_changed")
            if _safe_text(previous.get("observed_title"), 1000) != _safe_text(observed_title or source.get("title"), 1000): change_types.append("title_changed")
            if str(previous.get("normalized_text_sha256")) != digest: change_types.append("content_changed")
        affected = [r["assertion_id"] for r in self.db.all("SELECT DISTINCT assertion_id FROM evidence_assertion_sources_138 WHERE source_id=?", (source_id,))]
        if change_types and change_types != ["first_seen"]:
            severity = "high" if affected and ("availability_changed" in change_types or "content_changed" in change_types) else "medium"
            change_id = new_id("chg141")
            self.db.execute("INSERT INTO source_change_events_141(change_id,case_id,source_id,previous_snapshot_id,current_snapshot_id,change_type,severity,summary,details_json,affected_assertion_ids_json,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?, 'open',?,?,?)", (change_id, case_id, source_id, previous["snapshot_id"], snapshot_id, "+".join(change_types), severity, f"Quelle verändert: {', '.join(change_types)}", dumps({"previous_hash": previous.get("normalized_text_sha256"), "current_hash": digest, "http_status": status_code}), dumps(affected), _safe_text(actor, 120), now, now))
            self._event(case_id=case_id, event_type="source_change_detected_141", object_type="source_change_141", object_id=change_id, actor=actor, payload={"types": change_types, "affected_assertions": len(affected)})
        else:
            self._event(case_id=case_id, event_type="source_snapshot_recorded_141", object_type="source_snapshot_141", object_id=snapshot_id, actor=actor, payload={"changed": False, "first_seen": not bool(previous)})
        self.assess_source_quality(case_id=case_id, source_id=source_id, actor=actor)
        return {"snapshot_id": snapshot_id, "source_id": source_id, "sha256": digest, "availability_status": availability, "change_types": change_types, "affected_assertion_ids": affected}

    def review_source_change(self, *, case_id: str, change_id: str, status: str, actor: str) -> dict[str, Any]:
        if status not in CHANGE_STATUSES:
            raise ValueError("Ungültiger Änderungsstatus")
        row = self.db.one("SELECT * FROM source_change_events_141 WHERE case_id=? AND change_id=?", (case_id, change_id))
        if not row: raise KeyError("Quellenänderung nicht gefunden")
        self.db.execute("UPDATE source_change_events_141 SET status=?,updated_at=? WHERE change_id=?", (status, now_ts(), change_id))
        self._event(case_id=case_id, event_type="source_change_reviewed_141", object_type="source_change_141", object_id=change_id, actor=actor, payload={"status": status})
        return self.db.one("SELECT * FROM source_change_events_141 WHERE change_id=?", (change_id,)) or {}

    def analyze_case_source_risks(self, *, case_id: str, actor: str) -> list[dict[str, Any]]:
        self._case(case_id)
        sources = self.db.all("SELECT source_id FROM evidence_sources_138 WHERE case_id=?", (case_id,))
        for source in sources:
            try: self.assess_source_quality(case_id=case_id, source_id=source["source_id"], actor=actor)
            except (KeyError, ValueError): pass
        self.db.execute("UPDATE source_risk_findings_141 SET status='resolved',updated_at=? WHERE case_id=? AND status='open'", (now_ts(), case_id))
        findings: list[dict[str, Any]] = []
        assertions = self.db.all("SELECT * FROM evidence_assertions_138 WHERE case_id=? AND epistemic_state IN ('supported','confirmed')", (case_id,))
        for assertion in assertions:
            linked = self.db.all("SELECT l.source_id,l.stance,q.overall_score,q.quality_band,s.independence_group FROM evidence_assertion_sources_138 l JOIN evidence_sources_138 s ON s.source_id=l.source_id LEFT JOIN source_quality_assessments_141 q ON q.source_id=l.source_id WHERE l.assertion_id=?", (assertion["assertion_id"],))
            support = [r for r in linked if r["stance"] == "supports"]
            avg = sum(float(r.get("overall_score") or 0.35) for r in support) / max(1, len(support))
            groups = {r.get("independence_group") for r in support}
            if support and avg < 0.52:
                findings.append({"type": "low_quality_confirmed_claim", "severity": "high", "title": "Bestätigte Aussage stützt sich auf schwache Quellen", "summary": assertion["assertion_text"], "refs": [assertion["assertion_id"], *[r["source_id"] for r in support]], "action": "Primär- oder institutionelle Quelle ergänzen und Status erneut prüfen."})
            if len(support) > 1 and len(groups) < 2:
                findings.append({"type": "source_monoculture", "severity": "medium", "title": "Mehrere Belege sind nicht unabhängig", "summary": assertion["assertion_text"], "refs": [assertion["assertion_id"], *[r["source_id"] for r in support]], "action": "Mindestens eine unabhängige Quellenfamilie recherchieren."})
        changes = self.db.all("SELECT c.*,s.title FROM source_change_events_141 c JOIN evidence_sources_138 s ON s.source_id=c.source_id WHERE c.case_id=? AND c.status='open'", (case_id,))
        for change in changes:
            affected = loads(change.get("affected_assertion_ids_json"), [])
            findings.append({"type": "changed_supporting_source", "severity": change["severity"], "title": "Tragende Quelle wurde verändert", "summary": f"{change['title']}: {change['summary']}", "refs": [change["source_id"], *affected], "action": "Gesicherte Fassung vergleichen und betroffene Aussagen erneut bewerten."})
        now = now_ts()
        for item in findings:
            finding_id = new_id("risk141")
            self.db.execute("INSERT INTO source_risk_findings_141(finding_id,case_id,finding_type,severity,title,summary,object_refs_json,recommended_action,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?, 'open',?,?,?)", (finding_id, case_id, item["type"], item["severity"], item["title"], item["summary"], dumps(item["refs"]), item["action"], _safe_text(actor, 120), now, now))
        self._event(case_id=case_id, event_type="source_risk_analysis_141", object_type="case", object_id=case_id, actor=actor, payload={"finding_count": len(findings)})
        return self.source_risks(case_id)

    def source_risks(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM source_risk_findings_141 WHERE case_id=? AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,created_at DESC", (case_id,))
        for row in rows: row["object_refs"] = loads(row.pop("object_refs_json", "[]"), [])
        return rows

    # ---------- change-aware AI ----------
    def generate_change_aware_analysis(self, *, case_id: str, target_id: str = "", objective: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        if target_id: self._target(case_id, target_id)
        parent = self.build140.generate_evidence_analysis(case_id=case_id, target_id=target_id, objective=objective, actor=actor)
        adjusted, impacts = [], []
        for claim in parent["claims"]:
            qualities = []
            changes = []
            for source_id in claim.get("source_ids", []):
                try: q = self.source_quality(case_id=case_id, source_id=source_id)
                except KeyError: q = self.assess_source_quality(case_id=case_id, source_id=source_id, actor=actor)
                qualities.append(float(q["overall_score"]))
                open_changes = self.db.all("SELECT change_id,severity,change_type FROM source_change_events_141 WHERE source_id=? AND status='open'", (source_id,))
                changes.extend(open_changes)
            qavg = sum(qualities) / max(1, len(qualities)) if qualities else 0.25
            penalty = min(0.35, sum(0.18 if c["severity"] == "high" else 0.08 for c in changes))
            adjusted_conf = round(_clamp(float(claim["confidence"]) * (0.55 + 0.45 * qavg) - penalty), 3)
            adjusted.append({"claim_id": claim["claim_id"], "statement": claim["statement"], "original_confidence": claim["confidence"], "adjusted_confidence": adjusted_conf, "source_quality": round(qavg, 3), "open_source_changes": [c["change_id"] for c in changes], "review_status": claim["review_status"]})
            if changes: impacts.append({"claim_id": claim["claim_id"], "change_ids": [c["change_id"] for c in changes], "impact": "confidence_reduced_pending_review"})
        base_recs = parent.get("recommendations", [])
        actions = []
        seen = set()
        for impact in impacts:
            key = ("revalidate", impact["claim_id"])
            if key not in seen:
                actions.append({"action_type": "revalidate_changed_source", "title": "Von Quellenänderung betroffene Aussage erneut prüfen", "claim_id": impact["claim_id"], "priority": 0.95, "manual": True}); seen.add(key)
        for rec in base_recs:
            key = (rec.get("action_type"), _safe_text(rec.get("title"), 300).casefold())
            if key in seen: continue
            seen.add(key)
            actions.append({"action_type": rec.get("action_type"), "title": rec.get("title"), "rationale": rec.get("rationale"), "priority": rec.get("priority_score"), "manual": True})
        actions = sorted(actions, key=lambda r: float(r.get("priority") or 0), reverse=True)[:12]
        quality_score = round(sum(float(r["source_quality"]) for r in adjusted) / max(1, len(adjusted)), 3)
        uncertainty = "high" if impacts or quality_score < 0.45 else "medium" if quality_score < 0.72 else "low"
        analysis_id, now = new_id("ai141"), now_ts()
        self.db.execute("INSERT INTO change_aware_analyses_141(analysis141_id,case_id,target_id,parent_analysis140_id,objective,adjusted_claims_json,source_change_impacts_json,next_actions_json,evidence_quality_score,uncertainty_band,external_ai_used,autonomous_actions,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,0,0,?,?)", (analysis_id, case_id, target_id or None, parent["analysis_id"], _safe_text(objective, 1600), dumps(adjusted), dumps(impacts), dumps(actions), quality_score, uncertainty, _safe_text(actor, 120), now))
        self._event(case_id=case_id, event_type="change_aware_analysis_created_141", object_type="change_aware_analysis_141", object_id=analysis_id, actor=actor, payload={"quality_score": quality_score, "change_impacts": len(impacts), "external_ai_used": 0})
        return self.change_aware_analysis(case_id=case_id, analysis_id=analysis_id)

    def change_aware_analysis(self, *, case_id: str, analysis_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM change_aware_analyses_141 WHERE case_id=? AND analysis141_id=?", (case_id, analysis_id))
        if not row: raise KeyError("Build-141-Analyse nicht gefunden")
        row["adjusted_claims"] = loads(row.pop("adjusted_claims_json", "[]"), [])
        row["source_change_impacts"] = loads(row.pop("source_change_impacts_json", "[]"), [])
        row["next_actions"] = loads(row.pop("next_actions_json", "[]"), [])
        return row

    # ---------- bounded OPSEC envelope ----------
    def create_opsec_envelope(self, *, case_id: str, target_id: str = "", purpose: str, legal_basis: str, destination_type: str, destination_label: str, action_types: Iterable[str], data_classes: Iterable[str], max_identity_anchors: int, max_external_actions: int, ttl_minutes: int, actor: str) -> dict[str, Any]:
        self._case(case_id)
        if target_id: self._target(case_id, target_id)
        purpose, legal_basis = _safe_text(purpose, 1600), _safe_text(legal_basis, 1200)
        if len(purpose) < 8 or len(legal_basis) < 4: raise ValueError("Zweck und Rechtsgrundlage müssen dokumentiert werden")
        if destination_type not in ENVELOPE_DESTINATIONS: raise ValueError("Unbekannter Zieltyp")
        actions = list(dict.fromkeys(_safe_text(v, 100) for v in action_types if _safe_text(v, 100)))[:12]
        classes = list(dict.fromkeys(_safe_text(v, 100) for v in data_classes if _safe_text(v, 100)))[:20]
        anchors = max(0, min(int(max_identity_anchors or 0), 3))
        max_actions = max(0, min(int(max_external_actions or 0), 4))
        ttl = max(5, min(int(ttl_minutes or 30), 120))
        findings, mitigations, blocked, risk = [], [], False, "low"
        prohibited = sorted(set(classes) & PROHIBITED_CLASSES)
        if prohibited:
            blocked, risk = True, "prohibited"; findings.append(f"Unzulässige Datenklassen: {', '.join(prohibited)}")
        if destination_type == "local_only" and max_actions > 0:
            blocked = True; findings.append("Lokales Fenster darf keine externe Aktion erlauben.")
        if destination_type == "external_ai":
            risk = "high"; mitigations.extend(["Maximal drei minimierte Anker", "Keine Bilder oder vollständige Fallakte", "Prompt-Injection-Prüfung vor manueller Übertragung"])
            if set(classes) & IMAGE_DATA_CLASSES: blocked = True; findings.append("Bilder und Gesichtsausschnitte sind für externe AI-Pakete gesperrt.")
        if destination_type == "search_provider" and set(classes) & IMAGE_DATA_CLASSES:
            risk = "high"; max_actions = min(max_actions or 1, 1); mitigations.extend(["Nur bereinigte Recherchekopie", "Manueller Upload", "Keine biometrische Identitätsbehauptung"])
        if anchors > 0 and destination_type != "local_only" and risk == "low": risk = "medium"
        if not actions: findings.append("Keine erlaubten Aktionstypen dokumentiert."); blocked = True
        expires = (datetime.now(timezone.utc) + timedelta(minutes=ttl)).isoformat()
        envelope_id, now = new_id("opsec141"), now_ts()
        self.db.execute("INSERT INTO opsec_execution_envelopes_141(envelope_id,case_id,target_id,purpose,legal_basis,destination_type,destination_label,allowed_action_types_json,data_classes_json,max_identity_anchors,max_external_actions,expires_at,risk_level,blocked,findings_json,mitigations_json,approval_status,consumed_actions,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'draft',0,?,?,?)", (envelope_id, case_id, target_id or None, purpose, legal_basis, destination_type, _safe_text(destination_label, 300), dumps(actions), dumps(classes), anchors, max_actions, expires, risk, int(blocked), dumps(findings), dumps(mitigations), _safe_text(actor, 120), now, now))
        self._event(case_id=case_id, event_type="opsec_envelope_created_141", object_type="opsec_envelope_141", object_id=envelope_id, actor=actor, payload={"risk_level": risk, "blocked": blocked, "max_external_actions": max_actions})
        return self.opsec_envelope(case_id=case_id, envelope_id=envelope_id)

    def opsec_envelope(self, *, case_id: str, envelope_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM opsec_execution_envelopes_141 WHERE case_id=? AND envelope_id=?", (case_id, envelope_id))
        if not row: raise KeyError("OPSEC-Ausführungsfenster nicht gefunden")
        for key in ("allowed_action_types_json", "data_classes_json", "findings_json", "mitigations_json"):
            row[key.removesuffix("_json")] = loads(row.pop(key, "[]"), [])
        row["expired"] = bool(_parse_time(row["expires_at"]) and _parse_time(row["expires_at"]) < datetime.now(timezone.utc))
        return row

    def approve_opsec_envelope(self, *, case_id: str, envelope_id: str, decision: str, confirmation: str, actor: str) -> dict[str, Any]:
        env = self.opsec_envelope(case_id=case_id, envelope_id=envelope_id)
        if decision not in {"approved", "rejected", "cancelled"}: raise ValueError("Ungültige Entscheidung")
        if decision == "approved":
            if env["blocked"] or env["expired"]: raise PermissionError("Blockiertes oder abgelaufenes Fenster kann nicht freigegeben werden")
            if confirmation.strip() != "OPSEC-FENSTER MANUELL FREIGEBEN": raise PermissionError("Bestätigungsphrase OPSEC-FENSTER MANUELL FREIGEBEN erforderlich")
        now = now_ts()
        self.db.execute("UPDATE opsec_execution_envelopes_141 SET approval_status=?,approved_by=?,approved_at=?,updated_at=? WHERE envelope_id=?", (decision, _safe_text(actor, 120), now if decision == "approved" else "", now, envelope_id))
        self._event(case_id=case_id, event_type="opsec_envelope_reviewed_141", object_type="opsec_envelope_141", object_id=envelope_id, actor=actor, payload={"decision": decision})
        return self.opsec_envelope(case_id=case_id, envelope_id=envelope_id)

    def document_envelope_use(self, *, case_id: str, envelope_id: str, action_type: str, confirmation: str, actor: str) -> dict[str, Any]:
        env = self.opsec_envelope(case_id=case_id, envelope_id=envelope_id)
        if env["approval_status"] != "approved" or env["expired"]: raise PermissionError("Kein aktives freigegebenes OPSEC-Fenster")
        if action_type not in env["allowed_action_types"]: raise PermissionError("Aktion ist nicht vom OPSEC-Fenster gedeckt")
        if env["consumed_actions"] >= env["max_external_actions"]: raise PermissionError("Aktionsbudget ist ausgeschöpft")
        if confirmation.strip() != "EXTERNE AKTION MANUELL DOKUMENTIEREN": raise PermissionError("Manuelle Dokumentationsphrase erforderlich")
        self.db.execute("UPDATE opsec_execution_envelopes_141 SET consumed_actions=consumed_actions+1,updated_at=? WHERE envelope_id=?", (now_ts(), envelope_id))
        self._event(case_id=case_id, event_type="manual_external_action_documented_141", object_type="opsec_envelope_141", object_id=envelope_id, actor=actor, payload={"action_type": action_type, "performed_by_software": False})
        return self.opsec_envelope(case_id=case_id, envelope_id=envelope_id)

    # ---------- workflow efficiency ----------
    def optimize_workflow(self, *, case_id: str, workflow_id: str, actor: str) -> dict[str, Any]:
        workflow = self.build137.workflow(case_id=case_id, workflow_id=workflow_id)
        tasks = [task for stage in workflow["stages"] for task in stage["tasks"]]
        open_tasks = [t for t in tasks if t["status"] not in {"completed", "skipped"}]
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for task in open_tasks:
            key = (str(task.get("source_key") or ""), re.sub(r"\s+", " ", str(task.get("query_text") or "")).strip().casefold(), str(task.get("task_type") or ""))
            groups.setdefault(key, []).append(task)
        duplicate_groups, recommendations = [], []
        for key, rows in groups.items():
            if key[1] and len(rows) > 1:
                keep = sorted(rows, key=lambda r: int(r.get("priority") or 0), reverse=True)[0]
                duplicate_groups.append([r["workflow_task_id"] for r in rows])
                for row in rows:
                    if row["workflow_task_id"] != keep["workflow_task_id"]:
                        recommendations.append({"action": "skip_exact_duplicate", "task_id": row["workflow_task_id"], "reason": f"Exakte Dublette von {keep['workflow_task_id']}", "reversible": True})
        blocked_sources = []
        for task in open_tasks:
            source_key = str(task.get("source_key") or "")
            if not source_key: continue
            health = self.db.one("SELECT status,detail FROM provider_health_135 WHERE source_key=? ORDER BY checked_at DESC LIMIT 1", (source_key,))
            if health and health["status"] in {"offline", "quarantined", "changed_contract"}:
                blocked_sources.append(source_key)
                recommendations.append({"action": "mark_blocked_source", "task_id": task["workflow_task_id"], "reason": f"Quelle {source_key}: {health['status']}", "reversible": True})
        ranked = []
        for task in open_tasks:
            penalty = 35 if task.get("source_key") in blocked_sources else 0
            score = int(task.get("priority") or 50) - penalty + (8 if task["status"] == "unresolved" else 0)
            ranked.append({"task_id": task["workflow_task_id"], "title": task["title"], "source_key": task.get("source_key") or "", "score": score, "status": task["status"], "manual_review_required": True})
        ranked.sort(key=lambda r: r["score"], reverse=True)
        estimated = len([r for r in recommendations if r["action"] == "skip_exact_duplicate"]) * 6 + len(set(blocked_sources)) * 3
        optimization_id, now = new_id("opt141"), now_ts()
        self.db.execute("INSERT INTO workflow_optimization_runs_141(optimization_id,case_id,workflow_id,recommendations_json,duplicate_groups_json,blocked_sources_json,next_best_actions_json,estimated_minutes_saved,applied,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,0,?,?)", (optimization_id, case_id, workflow_id, dumps(recommendations), dumps(duplicate_groups), dumps(sorted(set(blocked_sources))), dumps(ranked[:10]), estimated, _safe_text(actor, 120), now))
        self._event(case_id=case_id, event_type="workflow_optimized_dry_run_141", object_type="workflow_optimization_141", object_id=optimization_id, actor=actor, payload={"recommendations": len(recommendations), "estimated_minutes_saved": estimated})
        return self.workflow_optimization(case_id=case_id, optimization_id=optimization_id)

    def workflow_optimization(self, *, case_id: str, optimization_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM workflow_optimization_runs_141 WHERE case_id=? AND optimization_id=?", (case_id, optimization_id))
        if not row: raise KeyError("Workflow-Optimierung nicht gefunden")
        for key in ("recommendations_json", "duplicate_groups_json", "blocked_sources_json", "next_best_actions_json"):
            row[key.removesuffix("_json")] = loads(row.pop(key, "[]"), [])
        return row

    def apply_workflow_optimization(self, *, case_id: str, optimization_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        run = self.workflow_optimization(case_id=case_id, optimization_id=optimization_id)
        if run["applied"]: return run
        if confirmation.strip() != "WORKFLOW-OPTIMIERUNG MANUELL ANWENDEN": raise PermissionError("Bestätigungsphrase erforderlich")
        for rec in run["recommendations"]:
            task = self.db.one("SELECT * FROM investigation_workflow_tasks_137 WHERE case_id=? AND workflow_task_id=?", (case_id, rec["task_id"]))
            if not task or task["status"] in {"completed", "skipped"}: continue
            status = "skipped" if rec["action"] == "skip_exact_duplicate" else "blocked"
            self.build137.update_workflow_task(case_id=case_id, workflow_task_id=rec["task_id"], status=status, outcome_note=f"Build 141: {rec['reason']}", actor=actor)
        now = now_ts()
        self.db.execute("UPDATE workflow_optimization_runs_141 SET applied=1,applied_by=?,applied_at=? WHERE optimization_id=?", (_safe_text(actor, 120), now, optimization_id))
        self._event(case_id=case_id, event_type="workflow_optimization_applied_141", object_type="workflow_optimization_141", object_id=optimization_id, actor=actor, payload={"safe_reversible_changes": len(run["recommendations"])})
        return self.workflow_optimization(case_id=case_id, optimization_id=optimization_id)

    # ---------- photo research quality ----------
    def assess_photo_result(self, *, case_id: str, result_id: str, actor: str) -> dict[str, Any]:
        row = self.db.one("SELECT r.*,s.source_type,s.title AS source_title,s.canonical_url,s.retrieved_at,s.independence_group FROM photo_research_results_138 r JOIN evidence_sources_138 s ON s.source_id=r.source_id WHERE r.case_id=? AND r.result_id=?", (case_id, result_id))
        if not row: raise KeyError("Fotorecherche-Treffer nicht gefunden")
        try: source_quality = self.source_quality(case_id=case_id, source_id=row["source_id"])
        except KeyError: source_quality = self.assess_source_quality(case_id=case_id, source_id=row["source_id"], actor=actor)
        authority = float(source_quality["overall_score"])
        provenance_edges = int((self.db.one("SELECT COUNT(*) AS n FROM evidence_provenance_edges_138 WHERE case_id=? AND ((from_object_id=? AND from_object_type='photo_result_138') OR (to_object_id=? AND to_object_type='photo_result_138'))", (case_id, result_id, result_id)) or {}).get("n") or 0)
        provenance = min(1.0, 0.25 + (0.18 if row.get("page_url") else 0) + (0.12 if row.get("image_url") else 0) + (0.20 if row.get("local_result_asset_id") else 0) + min(0.25, provenance_edges * 0.12))
        peers = self.db.all("SELECT result_id,observed_at,image_url,page_url FROM photo_research_results_138 WHERE case_id=? AND parent_asset_id=? ORDER BY observed_at", (case_id, row["parent_asset_id"]))
        earliest = bool(peers and peers[0]["result_id"] == result_id)
        temporal = 0.9 if earliest else 0.55
        comp = self.db.one("SELECT * FROM photo_comparisons_138 WHERE result_id=? ORDER BY updated_at DESC LIMIT 1", (result_id,))
        relation_map = {"exact_file": 1.0, "near_identical_image": 0.90, "near_duplicate_image": 0.90, "probable_variant": 0.76, "edited_or_cropped_candidate": 0.76, "weak_visual_relation": 0.40, "weak_visual_similarity": 0.40, "different_image": 0.10}
        visual = relation_map.get(str((comp or {}).get("image_relation_band") or ""), 0.35 if row.get("local_result_asset_id") else 0.20)
        context = 0.25 + (0.20 if row.get("page_title") else 0) + (0.20 if len(str(row.get("notes") or "")) >= 12 else 0) + (0.20 if source_quality["classification"] in {"primary_official", "institutional", "professional_press"} else 0)
        context = min(1.0, context)
        overall = round(authority * 0.28 + provenance * 0.24 + temporal * 0.14 + visual * 0.20 + context * 0.14, 4)
        band = "high" if overall >= 0.76 else "medium" if overall >= 0.50 else "low"
        duplicate_material = _canonical_url(row.get("image_url") or row.get("page_url") or "")
        duplicate_group = hashlib.sha256(duplicate_material.encode("utf-8")).hexdigest()[:16] if duplicate_material else ""
        findings, recs = [], []
        if provenance < 0.60: findings.append("Provenienzkette ist unvollständig."); recs.append("Fundseite, Bildadresse und lokale Sicherung vollständig dokumentieren.")
        if visual < 0.50: findings.append("Bildbezug ist technisch schwach oder noch nicht lokal verglichen."); recs.append("Trefferbild bewusst sichern und lokal mit dem Ausgangsbild vergleichen.")
        if not earliest: recs.append("Frühere bekannte Fundstellen und mögliche Ursprungsquelle prüfen.")
        if authority < 0.52: recs.append("Unabhängige institutionelle oder primäre Quelle suchen.")
        quality_id, now = new_id("pq141"), now_ts()
        self.db.execute("INSERT INTO photo_result_quality_141(photo_quality_id,case_id,result_id,source_authority,provenance_completeness,temporal_priority,visual_relation,context_quality,overall_score,quality_band,duplicate_group,earliest_known_candidate,candidate_only,findings_json,recommended_actions_json,assessed_by,assessed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?) ON CONFLICT(case_id,result_id) DO UPDATE SET source_authority=excluded.source_authority,provenance_completeness=excluded.provenance_completeness,temporal_priority=excluded.temporal_priority,visual_relation=excluded.visual_relation,context_quality=excluded.context_quality,overall_score=excluded.overall_score,quality_band=excluded.quality_band,duplicate_group=excluded.duplicate_group,earliest_known_candidate=excluded.earliest_known_candidate,findings_json=excluded.findings_json,recommended_actions_json=excluded.recommended_actions_json,assessed_by=excluded.assessed_by,assessed_at=excluded.assessed_at", (quality_id, case_id, result_id, authority, provenance, temporal, visual, context, overall, band, duplicate_group, int(earliest), dumps(findings), dumps(recs), _safe_text(actor, 120), now))
        self._event(case_id=case_id, event_type="photo_result_quality_assessed_141", object_type="photo_result_138", object_id=result_id, actor=actor, payload={"quality_band": band, "identity_claim": 0})
        return self.photo_result_quality(case_id=case_id, result_id=result_id)

    def photo_result_quality(self, *, case_id: str, result_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT q.*,r.page_title,r.page_url,r.image_url FROM photo_result_quality_141 q JOIN photo_research_results_138 r ON r.result_id=q.result_id WHERE q.case_id=? AND q.result_id=?", (case_id, result_id))
        if not row: raise KeyError("Fotoqualitätsbewertung nicht gefunden")
        row["findings"] = loads(row.pop("findings_json", "[]"), [])
        row["recommended_actions"] = loads(row.pop("recommended_actions_json", "[]"), [])
        return row

    def plan_photo_research(self, *, case_id: str, asset_id: str, purpose: str, actor: str) -> dict[str, Any]:
        asset, _ = self.build136.photo_path(case_id=case_id, asset_id=asset_id)
        purpose = _safe_text(purpose, 1200)
        if len(purpose) < 8: raise ValueError("Fotorecherche-Zweck ist zu kurz")
        variants = self.db.all("SELECT * FROM photo_variants_138 WHERE case_id=? AND parent_asset_id=? AND status='ready' ORDER BY created_at DESC", (case_id, asset_id))
        analyses = self.db.one("SELECT quality_band,research_recommendations_json FROM image_analyses_140 WHERE case_id=? AND asset_id=?", (case_id, asset_id))
        preferred_modes = ["clean_full", "contrast", "detail_enhance", "grayscale", "center_square"]
        if analyses and analyses.get("quality_band") == "low": preferred_modes = ["contrast", "detail_enhance", "clean_full", "grayscale", "center_square"]
        chosen = None
        for mode in preferred_modes:
            chosen = next((v for v in variants if v["variant_mode"] == mode), None)
            if chosen: break
        existing = self.db.all("SELECT provider_key,variant_id,copy_id,status FROM photo_search_runs_138 WHERE case_id=? AND parent_asset_id=?", (case_id, asset_id))
        used = {r["provider_key"] for r in existing}
        steps = [{"order": 1, "type": "source_context", "title": "Ursprüngliche Fundseite, Bildunterschrift und früheste bekannte Verwendung prüfen", "external": False, "manual": True, "upload": False}]
        order, redundant = 2, 0
        for key, label, url in PHOTO_PROVIDERS:
            if key in used:
                redundant += 1; continue
            steps.append({"order": order, "type": "reverse_image_provider", "provider_key": key, "provider_label": label, "provider_url": url, "variant_id": (chosen or {}).get("variant_id"), "copy_required": chosen is None, "manual": True, "manual_upload_required": True, "automatic_upload": False, "identity_claim": False}); order += 1
        steps.extend([
            {"order": order, "type": "result_deduplication", "title": "Treffer nach URL, Quellenfamilie und Bildhash deduplizieren", "external": False, "manual": True, "upload": False},
            {"order": order + 1, "type": "origin_analysis", "title": "Früheste bekannte Fundstelle und mögliche Ursprungsquelle bewerten", "external": False, "manual": True, "upload": False},
        ])
        plan_id, now = new_id("pplan141"), now_ts()
        provider_diversity = len({s.get("provider_key") for s in steps if s.get("provider_key")})
        estimated = 5 + provider_diversity * 6 + 8
        self.db.execute("INSERT INTO photo_research_plans_141(plan_id,case_id,target_id,parent_asset_id,purpose,steps_json,provider_diversity,redundant_steps_removed,estimated_minutes,manual_uploads_required,automatic_uploads,identity_claims,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,0,0,?,?)", (plan_id, case_id, asset.get("target_id"), asset_id, purpose, dumps(steps), provider_diversity, redundant, estimated, provider_diversity, _safe_text(actor, 120), now))
        self._event(case_id=case_id, event_type="photo_research_plan_created_141", object_type="photo_research_plan_141", object_id=plan_id, actor=actor, payload={"provider_diversity": provider_diversity, "automatic_uploads": 0, "identity_claims": 0})
        return self.photo_research_plan(case_id=case_id, plan_id=plan_id)

    def photo_research_plan(self, *, case_id: str, plan_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM photo_research_plans_141 WHERE case_id=? AND plan_id=?", (case_id, plan_id))
        if not row: raise KeyError("Fotorechercheplan nicht gefunden")
        row["steps"] = loads(row.pop("steps_json", "[]"), [])
        return row

    # ---------- dashboards ----------
    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        if case_id:
            self._case(case_id)
            qualities = self.db.all("SELECT q.*,s.title FROM source_quality_assessments_141 q JOIN evidence_sources_138 s ON s.source_id=q.source_id WHERE q.case_id=? ORDER BY q.overall_score DESC", (case_id,))
            for row in qualities:
                row["strengths"] = loads(row.pop("strengths_json", "[]"), []); row["weaknesses"] = loads(row.pop("weaknesses_json", "[]"), [])
            changes = self.db.all("SELECT c.*,s.title FROM source_change_events_141 c JOIN evidence_sources_138 s ON s.source_id=c.source_id WHERE c.case_id=? ORDER BY c.created_at DESC LIMIT 100", (case_id,))
            for row in changes: row["affected_assertion_ids"] = loads(row.pop("affected_assertion_ids_json", "[]"), []); row["details"] = loads(row.pop("details_json", "{}"), {})
            analyses = self.db.all("SELECT * FROM change_aware_analyses_141 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
            envelopes = self.db.all("SELECT * FROM opsec_execution_envelopes_141 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
            optimizations = self.db.all("SELECT * FROM workflow_optimization_runs_141 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
            photo_quality = self.db.all("SELECT q.*,r.page_title FROM photo_result_quality_141 q JOIN photo_research_results_138 r ON r.result_id=q.result_id WHERE q.case_id=? ORDER BY q.overall_score DESC", (case_id,))
            photo_plans = self.db.all("SELECT * FROM photo_research_plans_141 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
            return {"build": self.BUILD, "source_qualities": qualities, "source_changes": changes, "source_risks": self.source_risks(case_id), "analyses": analyses, "envelopes": envelopes, "optimizations": optimizations, "photo_quality": photo_quality, "photo_plans": photo_plans, "metrics": {"source_count": len(qualities), "open_changes": sum(1 for r in changes if r["status"] == "open"), "open_risks": len(self.source_risks(case_id)), "change_aware_analyses": len(analyses), "active_envelopes": sum(1 for r in envelopes if r["approval_status"] == "approved"), "estimated_minutes_saved": sum(int(r["estimated_minutes_saved"] or 0) for r in optimizations if r["applied"]), "photo_results_assessed": len(photo_quality)}, "safety": {"external_ai_calls": 0, "autonomous_external_actions": 0, "automatic_image_uploads": 0, "biometric_templates": 0, "face_matching": False, "automatic_identity_claims": 0, "manual_approval_required": True, "change_aware_citations": True}}
        return {"build": self.BUILD, "counts": {"source_quality": int((self.db.one("SELECT COUNT(*) AS n FROM source_quality_assessments_141") or {}).get("n") or 0), "source_changes": int((self.db.one("SELECT COUNT(*) AS n FROM source_change_events_141") or {}).get("n") or 0), "analyses": int((self.db.one("SELECT COUNT(*) AS n FROM change_aware_analyses_141") or {}).get("n") or 0), "photo_plans": int((self.db.one("SELECT COUNT(*) AS n FROM photo_research_plans_141") or {}).get("n") or 0)}, "safety": {"external_ai_calls": 0, "autonomous_external_actions": 0, "automatic_image_uploads": 0, "biometric_templates": 0, "face_matching": False}}
