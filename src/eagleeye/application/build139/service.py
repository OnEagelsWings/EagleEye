from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping

from PIL import Image, ImageOps, ImageStat

from eagleeye.application.build137.service import PHOTO_PROVIDERS
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

try:  # Optional at import time; diagnostics expose whether local detection is available.
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - exercised on systems without OpenCV
    cv2 = None
    np = None


IDENTITY_REVIEW_STATES = {"unresolved", "reviewing", "supported_hypothesis", "not_same_person", "confirmed_by_investigator"}
IDENTITY_DECISIONS = {"requires_more_evidence", "not_same_person", "same_person_hypothesis", "confirmed_by_investigator"}
PHOTO_LINK_STATES = {"candidate", "supported", "confirmed_by_investigator", "rejected"}
FACE_RUN_STATUSES = {"prepared", "provider_opened", "uploaded_manually", "results_review", "completed", "cancelled"}
FACE_PROVIDER_KEYS = set(PHOTO_PROVIDERS)
PROHIBITED_ACTIONS = {"biometric_identification", "face_matching", "remote_biometric_identification", "emotion_recognition"}
SENSITIVE_DATA_CLASSES = {"biometric_template", "health", "religion", "political_opinion", "sexual_orientation", "criminal_allegation", "minor_data"}
IDENTITY_WEIGHTS = {
    "name": 0.22,
    "birth_date": 0.22,
    "age": 0.08,
    "occupation": 0.10,
    "organization": 0.10,
    "location": 0.08,
    "username": 0.08,
    "email": 0.07,
    "domain": 0.05,
}


def _safe_text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_safe_text(v, 500) for v in value if _safe_text(v, 500)]
    if isinstance(value, Mapping):
        return [_safe_text(v, 500) for v in value.values() if _safe_text(v, 500)]
    text = _safe_text(value, 3000)
    return [_safe_text(v, 500) for v in re.split(r"[,;|\n]+", text) if _safe_text(v, 500)]


def _similarity(left: Any, right: Any) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_tokens, b_tokens = set(a.split()), set(b.split())
    token_score = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    seq = SequenceMatcher(None, a, b).ratio()
    return round(max(token_score, seq), 4)


def _best_similarity(left: Iterable[Any], right: Iterable[Any]) -> float:
    values = [_similarity(a, b) for a in left for b in right]
    return max(values) if values else 0.0


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        return max(lower, min(upper, float(value)))
    except (TypeError, ValueError):
        return lower


def _iso_year(value: Any) -> int | None:
    match = re.match(r"^(\d{4})", str(value or "").strip())
    return int(match.group(1)) if match else None


class Build139Service:
    """Explainable identity resolution, local AI assistance, OPSEC and face-region analysis.

    This build intentionally does not create facial embeddings, biometric templates,
    one-to-one verification, one-to-many identification, or automatic identity merges.
    Face detection is used only to locate a face region, estimate image research quality,
    and create a metadata-free crop for an explicitly approved manual research step.
    """

    BUILD = "139.0"
    DETECTOR_NAME = "opencv_haar_frontalface_default"
    DETECTOR_VERSION = "1"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        build138: Any,
        build137: Any,
        build136: Any,
        build135: Any,
        protection: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.build138 = build138
        self.build137 = build137
        self.build136 = build136
        self.build135 = build135
        self.protection = protection
        self.photo_root = self.build136.photo_root.resolve()

    # ---------- common validation / event chain ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        for key in ("aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"):
            row[key] = loads(row.get(key), [])
        return row

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        event_id = new_id("evt139")
        previous = self.db.one("SELECT event_hash FROM build139_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        created_at = now_ts()
        body = dumps({
            "event_id": event_id,
            "case_id": case_id,
            "event_type": event_type,
            "object_type": object_type,
            "object_id": object_id,
            "payload": dict(payload or {}),
            "previous_hash": previous_hash,
            "created_by": _safe_text(actor, 120),
            "created_at": created_at,
        })
        event_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO build139_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, object_type, object_id, dumps(dict(payload or {})), previous_hash, event_hash, _safe_text(actor, 120), created_at),
        )
        self.audit.log(event_type, object_type, object_id, case_id, dict(payload or {}))

    # ---------- identity resolution ----------
    def _profile_attributes(self, target_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT attribute_key,value_json,known,review_status,confidence FROM person_profile_attributes_135 WHERE target_id=?", (target_id,))
        result: dict[str, Any] = {}
        for row in rows:
            if int(row.get("known") or 0):
                result[row["attribute_key"]] = loads(row.get("value_json"), None)
        return result

    def target_identity_features(self, *, case_id: str, target_id: str) -> dict[str, list[str]]:
        target = self._target(case_id, target_id)
        attrs = self._profile_attributes(target_id)
        occupation = attrs.get("occupation") or attrs.get("occupation_history") or attrs.get("profession")
        birth = attrs.get("birth_date") or attrs.get("date_of_birth")
        age = attrs.get("age_estimate") or attrs.get("age")
        return {
            "name": [target["name"], *target["aliases_json"]],
            "birth_date": _as_list(birth),
            "age": _as_list(age),
            "occupation": _as_list(occupation),
            "organization": list(target["companies_json"]),
            "location": list(target["locations_json"]),
            "username": list(target["usernames_json"]),
            "email": list(target["emails_json"]),
            "domain": list(target["domains_json"]),
        }

    def create_identity_candidate(
        self,
        *,
        case_id: str,
        target_id: str,
        label: str,
        attributes: Mapping[str, Any],
        source_refs: Iterable[str] = (),
        source_node_id: str = "",
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        self._target(case_id, target_id)
        label = _safe_text(label, 500)
        if not label:
            raise ValueError("Bezeichnung des Identitätskandidaten fehlt")
        if source_node_id:
            node = self.db.one("SELECT node_id FROM evidence_nodes_138 WHERE case_id=? AND node_id=?", (case_id, source_node_id))
            if not node:
                raise KeyError("Evidence Node gehört nicht zu diesem Fall")
        clean_attrs = {str(k)[:80]: _as_list(v) for k, v in dict(attributes or {}).items() if str(k) in IDENTITY_WEIGHTS}
        candidate_id = new_id("idcand139")
        now = now_ts()
        self.db.execute(
            "INSERT INTO identity_candidates_139(candidate_id,case_id,target_id,label,source_node_id,attributes_json,source_refs_json,review_status,candidate_only,automatic_merge,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'unresolved',1,0,?,?,?)",
            (candidate_id, case_id, target_id, label, source_node_id or None, dumps(clean_attrs), dumps([_safe_text(v, 300) for v in source_refs if _safe_text(v, 300)]), _safe_text(actor, 120), now, now),
        )
        self._event(case_id=case_id, event_type="identity_candidate_created_139", object_type="identity_candidate_139", object_id=candidate_id, actor=actor, payload={"target_id": target_id, "automatic_merge": False, "face_features_used": False})
        return self.identity_candidate(case_id=case_id, candidate_id=candidate_id)

    def identity_candidate(self, *, case_id: str, candidate_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM identity_candidates_139 WHERE case_id=? AND candidate_id=?", (case_id, candidate_id))
        if not row:
            raise KeyError("Identitätskandidat nicht gefunden")
        row["attributes"] = loads(row.pop("attributes_json", "{}"), {})
        row["source_refs"] = loads(row.pop("source_refs_json", "[]"), [])
        row["comparison"] = self.db.one("SELECT * FROM identity_comparisons_139 WHERE candidate_id=?", (candidate_id,))
        if row["comparison"]:
            for key in ("feature_results_json", "missing_fields_json", "rationale_json"):
                row["comparison"][key.removesuffix("_json")] = loads(row["comparison"].pop(key, "[]"), [])
        return row

    def compare_identity_candidate(self, *, case_id: str, candidate_id: str, actor: str) -> dict[str, Any]:
        candidate = self.identity_candidate(case_id=case_id, candidate_id=candidate_id)
        target_features = self.target_identity_features(case_id=case_id, target_id=candidate["target_id"])
        candidate_features = {key: _as_list(candidate["attributes"].get(key)) for key in IDENTITY_WEIGHTS}
        feature_rows: list[dict[str, Any]] = []
        rationale: list[str] = []
        missing: list[str] = []
        positive = 0.0
        conflict = 0.0
        hard_conflict = False

        for key, weight in IDENTITY_WEIGHTS.items():
            left, right = target_features.get(key, []), candidate_features.get(key, [])
            if not left or not right:
                missing.append(key)
                feature_rows.append({"feature": key, "weight": weight, "state": "missing", "similarity": 0.0, "face_feature": False})
                continue
            similarity = _best_similarity(left, right)
            state = "supports" if similarity >= 0.82 else "partial" if similarity >= 0.5 else "conflicts" if similarity <= 0.15 else "unclear"
            if key == "birth_date":
                target_years = {_iso_year(v) for v in left} - {None}
                candidate_years = {_iso_year(v) for v in right} - {None}
                exact_values = {_norm(v) for v in left} & {_norm(v) for v in right}
                if target_years and candidate_years and not (target_years & candidate_years):
                    hard_conflict = True
                    state = "hard_conflict"
                    similarity = 0.0
                    rationale.append("Geburtsjahre sind unvereinbar.")
                elif exact_values:
                    similarity = 1.0
                    state = "supports"
            if key == "email" and similarity < 1.0:
                left_norm, right_norm = {_norm(v) for v in left}, {_norm(v) for v in right}
                if left_norm and right_norm and not (left_norm & right_norm):
                    state = "conflicts"
                    conflict += weight * 0.8
            if state in {"supports", "partial"}:
                positive += weight * similarity
            elif state in {"conflicts", "hard_conflict"}:
                conflict += weight * (1.0 - similarity)
            feature_rows.append({"feature": key, "weight": weight, "state": state, "similarity": round(similarity, 4), "target_values": left[:5], "candidate_values": right[:5], "face_feature": False})

        positive = round(_clamp(positive), 4)
        conflict = round(_clamp(conflict), 4)
        overall = round(max(0.0, positive - conflict * 0.75), 4)
        if hard_conflict:
            band = "excluded_by_hard_conflict"
        elif overall >= 0.72 and conflict < 0.12:
            band = "strong_nonbiometric_candidate"
        elif overall >= 0.48:
            band = "plausible_candidate"
        elif conflict >= 0.35:
            band = "likely_different_person"
        else:
            band = "insufficient_evidence"
        if not rationale:
            rationale.append("Bewertung ausschließlich aus erklärbaren, nichtbiometrischen Identitätsankern.")
        comparison_id = (candidate.get("comparison") or {}).get("comparison_id") or new_id("idcmp139")
        now = now_ts()
        existing = self.db.one("SELECT comparison_id FROM identity_comparisons_139 WHERE candidate_id=?", (candidate_id,))
        values = (positive, conflict, overall, band, int(hard_conflict), dumps(feature_rows), dumps(missing), dumps(rationale), _safe_text(actor, 120), now, comparison_id)
        if existing:
            self.db.execute("UPDATE identity_comparisons_139 SET positive_score=?,conflict_score=?,overall_score=?,result_band=?,hard_conflict=?,feature_results_json=?,missing_fields_json=?,rationale_json=?,face_features_used=0,candidate_only=1,generated_by='local_explainable_rules',created_by=?,updated_at=? WHERE comparison_id=?", values)
        else:
            self.db.execute(
                "INSERT INTO identity_comparisons_139(comparison_id,case_id,target_id,candidate_id,positive_score,conflict_score,overall_score,result_band,hard_conflict,feature_results_json,missing_fields_json,rationale_json,face_features_used,candidate_only,generated_by,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,'local_explainable_rules',?,?,?)",
                (comparison_id, case_id, candidate["target_id"], candidate_id, positive, conflict, overall, band, int(hard_conflict), dumps(feature_rows), dumps(missing), dumps(rationale), _safe_text(actor, 120), now, now),
            )
        self.db.execute("UPDATE identity_candidates_139 SET review_status='reviewing',updated_at=? WHERE candidate_id=?", (now, candidate_id))
        self._event(case_id=case_id, event_type="identity_candidate_compared_139", object_type="identity_comparison_139", object_id=comparison_id, actor=actor, payload={"result_band": band, "overall_score": overall, "hard_conflict": hard_conflict, "face_features_used": False, "automatic_decision": False})
        return self.identity_candidate(case_id=case_id, candidate_id=candidate_id)["comparison"]

    def decide_identity_candidate(self, *, case_id: str, candidate_id: str, decision: str, rationale: str, confirmation: str, actor: str) -> dict[str, Any]:
        candidate = self.identity_candidate(case_id=case_id, candidate_id=candidate_id)
        if decision not in IDENTITY_DECISIONS:
            raise ValueError("Ungültige Identitätsentscheidung")
        rationale = _safe_text(rationale, 5000)
        if len(rationale) < 12:
            raise ValueError("Eine nachvollziehbare manuelle Begründung ist erforderlich")
        if decision == "confirmed_by_investigator" and confirmation.strip() != "IDENTITÄT MANUELL BESTÄTIGEN":
            raise PermissionError("Für eine manuelle Bestätigung ist die Phrase IDENTITÄT MANUELL BESTÄTIGEN erforderlich")
        decision_id = new_id("iddec139")
        now = now_ts()
        review_status = decision if decision in IDENTITY_REVIEW_STATES else "supported_hypothesis" if decision == "same_person_hypothesis" else "unresolved"
        self.db.execute("INSERT INTO identity_decisions_139(decision_id,case_id,target_id,candidate_id,decision,rationale,decided_by,decided_at,automatic_decision) VALUES(?,?,?,?,?,?,?,?,0)", (decision_id, case_id, candidate["target_id"], candidate_id, decision, rationale, _safe_text(actor, 120), now))
        self.db.execute("UPDATE identity_candidates_139 SET review_status=?,candidate_only=?,automatic_merge=0,updated_at=? WHERE candidate_id=?", (review_status, 0 if decision == "confirmed_by_investigator" else 1, now, candidate_id))
        self._event(case_id=case_id, event_type="identity_candidate_decided_139", object_type="identity_decision_139", object_id=decision_id, actor=actor, payload={"decision": decision, "automatic_decision": False, "automatic_merge": False, "face_features_used": False})
        return self.db.one("SELECT * FROM identity_decisions_139 WHERE decision_id=?", (decision_id,)) or {}

    # ---------- AI assistance ----------
    def generate_ai_brief(self, *, case_id: str, target_id: str = "", objective: str, actor: str) -> dict[str, Any]:
        case = self._case(case_id)
        target = self._target(case_id, target_id) if target_id else None
        objective = _safe_text(objective, 1500)
        if len(objective) < 8:
            raise ValueError("Ermittlungsziel ist zu kurz")
        assertions = self.db.all(
            "SELECT a.*,s.label AS subject_label,o.label AS object_label FROM evidence_assertions_138 a JOIN evidence_nodes_138 s ON s.node_id=a.subject_node_id JOIN evidence_nodes_138 o ON o.node_id=a.object_node_id WHERE a.case_id=? AND (?='' OR a.target_id=? OR a.target_id IS NULL) ORDER BY a.confidence DESC,a.updated_at DESC LIMIT 200",
            (case_id, target_id, target_id),
        )
        warnings = self.db.all("SELECT * FROM evidence_warnings_138 WHERE case_id=? AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,created_at DESC LIMIT 50", (case_id,))
        facts = [{"assertion_id": r["assertion_id"], "text": r["assertion_text"], "confidence": r["confidence"], "state": r["epistemic_state"], "source_count": r["source_count"], "independence_count": r["independence_count"]} for r in assertions if r["epistemic_state"] in {"confirmed", "supported"}]
        hypotheses = [{"assertion_id": r["assertion_id"], "text": r["assertion_text"], "confidence": r["confidence"], "state": r["epistemic_state"]} for r in assertions if r["epistemic_state"] in {"hypothesis", "lead"}]
        contradictions = [{"warning_id": r["warning_id"], "type": r["warning_type"], "severity": r["severity"], "summary": r["summary"]} for r in warnings]
        gaps: list[dict[str, Any]] = []
        next_steps: list[dict[str, Any]] = []
        if not facts:
            gaps.append({"gap": "Keine gestützte oder bestätigte Aussage", "priority": "high"})
            next_steps.append({"step": "Mindestens zwei voneinander unabhängige Quellen für die Kernidentität sichern", "priority": 1, "external_action": False})
        if contradictions:
            gaps.append({"gap": "Offene Beleg- oder Zeitkonflikte", "priority": "high", "count": len(contradictions)})
            next_steps.append({"step": "Höchstrangige Widerspruchswarnung gegen Primärquelle prüfen", "priority": 1, "external_action": False})
        if target:
            features = self.target_identity_features(case_id=case_id, target_id=target_id)
            for key in ("birth_date", "occupation", "organization", "location"):
                if not features.get(key):
                    gaps.append({"gap": f"Identitätsanker fehlt: {key}", "priority": "medium"})
            unresolved = self.db.all("SELECT candidate_id,label FROM identity_candidates_139 WHERE case_id=? AND target_id=? AND review_status IN ('unresolved','reviewing') ORDER BY updated_at DESC LIMIT 20", (case_id, target_id))
            if unresolved:
                next_steps.append({"step": f"{len(unresolved)} offene Identitätskandidaten anhand harter Ausschlussmerkmale prüfen", "priority": 2, "external_action": False})
        if len(next_steps) < 3:
            next_steps.extend([
                {"step": "Quellenabhängigkeit und gemeinsame Ursprungsquelle kontrollieren", "priority": 3, "external_action": False},
                {"step": "Gegenhypothese formulieren: Treffer gehört zu einer namensgleichen anderen Person", "priority": 4, "external_action": False},
                {"step": "Zeitliche Vereinbarkeit von Orten, Arbeitgebern und Veröffentlichungen prüfen", "priority": 5, "external_action": False},
            ])
        bias_checks = [
            {"bias": "Bestätigungsfehler", "check": "Wurde aktiv nach widerlegenden Merkmalen gesucht?"},
            {"bias": "Namensgleichheit", "check": "Sind mindestens zwei unabhängige Anker außer dem Namen vorhanden?"},
            {"bias": "Quellenillusion", "check": "Stammen mehrere Seiten tatsächlich aus derselben Ursprungsquelle?"},
            {"bias": "Fotoüberbewertung", "check": "Wird Bildähnlichkeit fälschlich als Personenidentität behandelt?"},
        ]
        anchors = []
        if target:
            anchors.append({"type": "name", "value": target["name"]})
            if target["locations_json"]:
                anchors.append({"type": "location", "value": target["locations_json"][0]})
            if target["companies_json"]:
                anchors.append({"type": "organization", "value": target["companies_json"][0]})
        disclosure = {
            "external_ai_used": False,
            "maximum_anchors": 3,
            "proposed_anchors": anchors[:3],
            "excluded": ["photos", "facial_regions", "birth_date_full", "children", "health", "religion", "political_views", "contact_details"],
            "manual_approval_required": True,
            "purpose": objective,
        }
        brief_id = new_id("aibrief139")
        self.db.execute(
            "INSERT INTO ai_investigation_briefs_139(brief_id,case_id,target_id,objective,facts_json,hypotheses_json,contradictions_json,evidence_gaps_json,next_steps_json,bias_checks_json,disclosure_plan_json,external_ai_used,identity_claims,generated_by,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,0,0,'local_evidence_assistant',?,?)",
            (brief_id, case_id, target_id or None, objective, dumps(facts[:50]), dumps(hypotheses[:50]), dumps(contradictions[:50]), dumps(gaps[:30]), dumps(next_steps[:8]), dumps(bias_checks), dumps(disclosure), _safe_text(actor, 120), now_ts()),
        )
        self._event(case_id=case_id, event_type="ai_investigation_brief_generated_139", object_type="ai_brief_139", object_id=brief_id, actor=actor, payload={"external_ai_used": False, "identity_claims": 0, "facts": len(facts), "hypotheses": len(hypotheses), "warnings": len(contradictions)})
        return self.ai_brief(case_id=case_id, brief_id=brief_id)

    def ai_brief(self, *, case_id: str, brief_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_investigation_briefs_139 WHERE case_id=? AND brief_id=?", (case_id, brief_id))
        if not row:
            raise KeyError("AI-Brief nicht gefunden")
        for key in ("facts_json", "hypotheses_json", "contradictions_json", "evidence_gaps_json", "next_steps_json", "bias_checks_json", "disclosure_plan_json"):
            row[key.removesuffix("_json")] = loads(row.pop(key), [] if key != "disclosure_plan_json" else {})
        return row

    # ---------- OPSEC ----------
    def assess_opsec(
        self,
        *,
        case_id: str,
        target_id: str = "",
        action_type: str,
        purpose: str,
        legal_basis: str,
        data_classes: Iterable[str],
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if target_id:
            self._target(case_id, target_id)
        action_type = _safe_text(action_type, 100)
        purpose = _safe_text(purpose, 1000)
        legal_basis = _safe_text(legal_basis, 500)
        classes = sorted({_safe_text(v, 80) for v in data_classes if _safe_text(v, 80)})
        findings: list[str] = []
        mitigations: list[str] = []
        blocked = action_type in PROHIBITED_ACTIONS or "biometric_template" in classes
        if blocked:
            risk = "prohibited"
            findings.append("Die angeforderte Funktion würde biometrische Identifizierung, Gesichtsabgleich oder Emotionserkennung ermöglichen.")
            mitigations.append("Nur lokale Gesichtsbereichserkennung und Qualitätsanalyse ohne Templates oder Identitätsvergleich verwenden.")
        else:
            sensitive = sorted(set(classes) & SENSITIVE_DATA_CLASSES)
            external = action_type in {"external_ai_assist", "reverse_image_search", "web_search", "export"}
            risk = "high" if sensitive or (external and "facial_image" in classes) else "medium" if external else "low"
            if sensitive:
                findings.append("Besondere oder besonders schutzbedürftige Datenklassen sind betroffen: " + ", ".join(sensitive))
            if external:
                findings.append("Die Aktion kann Daten an einen externen Empfänger offenlegen.")
                mitigations.extend(["Nur die minimal erforderlichen Daten offenlegen.", "Empfänger, Zweck und Zeitpunkt in der Auditspur dokumentieren.", "Keine geheimen URLs, Tokens oder vollständige Fallakte übertragen."])
            if "facial_image" in classes:
                findings.append("Ein Gesichtsausschnitt bleibt ein personenbezogenes Bild und erfordert eine dokumentierte Zweck- und Rechtsgrundlagenprüfung.")
                mitigations.extend(["Metadatenfreie Recherchekopie verwenden.", "Manuellen Upload verlangen.", "Ablaufzeit und lokale Löschung der Recherchekopie vorsehen."])
        if not purpose or not legal_basis:
            blocked = True
            risk = "prohibited"
            findings.append("Zweck und Rechtsgrundlage müssen vor der Verarbeitung dokumentiert sein.")
        budget = {
            "max_identity_anchors": 3 if action_type == "external_ai_assist" else 5,
            "full_case_export": False,
            "photos_allowed": action_type == "reverse_image_search" and not blocked,
            "biometric_templates_allowed": False,
            "automatic_upload_allowed": False,
        }
        assessment_id = new_id("opsec139")
        self.db.execute(
            "INSERT INTO opsec_assessments_139(assessment_id,case_id,target_id,action_type,purpose,legal_basis,data_classes_json,risk_level,blocked,findings_json,mitigations_json,disclosure_budget_json,retention_hours,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,24,?,?)",
            (assessment_id, case_id, target_id or None, action_type, purpose, legal_basis, dumps(classes), risk, int(blocked), dumps(findings), dumps(mitigations), dumps(budget), _safe_text(actor, 120), now_ts()),
        )
        self._event(case_id=case_id, event_type="opsec_assessment_created_139", object_type="opsec_assessment_139", object_id=assessment_id, actor=actor, payload={"action_type": action_type, "risk_level": risk, "blocked": blocked, "data_classes": classes})
        return self.opsec_assessment(case_id=case_id, assessment_id=assessment_id)

    def opsec_assessment(self, *, case_id: str, assessment_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM opsec_assessments_139 WHERE case_id=? AND assessment_id=?", (case_id, assessment_id))
        if not row:
            raise KeyError("OPSEC-Bewertung nicht gefunden")
        for key in ("data_classes_json", "findings_json", "mitigations_json", "disclosure_budget_json"):
            row[key.removesuffix("_json")] = loads(row.pop(key), [] if key != "disclosure_budget_json" else {})
        row["blocked"] = bool(row["blocked"])
        return row

    # ---------- local face-region detection and research crops ----------
    @property
    def face_detection_available(self) -> bool:
        if cv2 is None or np is None:
            return False
        cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        return cascade.exists()

    def _face_crop_path(self, case_id: str, detection_id: str) -> Path:
        folder = (self.photo_root / case_id / "face_crops_139").resolve()
        root = self.photo_root.resolve()
        if root not in folder.parents:
            raise PermissionError("Ungültiger Gesichtsausschnittspfad")
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{detection_id}.jpg"

    def _store_face_detection(self, *, case_id: str, asset: Mapping[str, Any], image: Image.Image, bbox: tuple[int, int, int, int], face_index: int, confidence: float, actor: str) -> dict[str, Any]:
        x, y, w, h = bbox
        full_w, full_h = image.size
        padding = int(max(w, h) * 0.18)
        left, top = max(0, x - padding), max(0, y - padding)
        right, bottom = min(full_w, x + w + padding), min(full_h, y + h + padding)
        clipped = int(left == 0 or top == 0 or right == full_w or bottom == full_h)
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        crop.thumbnail((768, 768), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(crop)
        stat = ImageStat.Stat(gray)
        brightness = float(stat.mean[0])
        contrast = float(stat.stddev[0])
        gray_np = np.array(gray) if np is not None else None
        blur_variance = float(cv2.Laplacian(gray_np, cv2.CV_64F).var()) if cv2 is not None and gray_np is not None else 0.0
        face_ratio = round((w * h) / max(1, full_w * full_h), 6)
        if w >= 160 and h >= 160 and blur_variance >= 80 and 45 <= brightness <= 215 and contrast >= 28 and not clipped:
            quality = "high"
            suitability = "suitable_for_manual_reverse_image_research"
        elif w >= 90 and h >= 90 and blur_variance >= 35 and 30 <= brightness <= 230 and contrast >= 18:
            quality = "medium"
            suitability = "usable_with_caution"
        else:
            quality = "low"
            suitability = "poor_research_quality"
        detection_id = new_id("face139")
        crop_path = self._face_crop_path(case_id, detection_id)
        crop.save(crop_path, "JPEG", quality=92, optimize=True)
        payload = crop_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        rel = str(crop_path.relative_to(self.photo_root)).replace("\\", "/")
        target_id = asset.get("target_id") or None
        self.db.execute(
            "INSERT INTO face_detections_139(detection_id,case_id,target_id,asset_id,face_index,x_px,y_px,width_px,height_px,detector_name,detector_version,detection_confidence,blur_variance,brightness,contrast,face_area_ratio,clipped,quality_band,research_suitability,crop_relpath,crop_sha256,biometric_template_created,identity_comparison_performed,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?)",
            (detection_id, case_id, target_id, asset["asset_id"], face_index, x, y, w, h, self.DETECTOR_NAME, self.DETECTOR_VERSION, round(_clamp(confidence), 4), round(blur_variance, 4), round(brightness, 4), round(contrast, 4), face_ratio, clipped, quality, suitability, rel, digest, _safe_text(actor, 120), now_ts()),
        )
        crop.close(); gray.close()
        return self.face_detection(case_id=case_id, detection_id=detection_id)

    def detect_faces(self, *, case_id: str, asset_id: str, actor: str, manual_regions: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
        self._case(case_id)
        asset, path = self.build136.photo_path(case_id=case_id, asset_id=asset_id)
        if not path.is_file():
            raise FileNotFoundError("Lokales Foto nicht gefunden")
        assessment = self.assess_opsec(case_id=case_id, target_id=asset.get("target_id") or "", action_type="local_face_detection", purpose="Lokale Erkennung von Gesichtsbereichen und Bildqualitätsprüfung", legal_basis=(self._case(case_id).get("legal_basis") or "dokumentierte Fallrechtsgrundlage"), data_classes=["facial_image"], actor=actor)
        if assessment["blocked"]:
            raise PermissionError("OPSEC-Prüfung blockiert die lokale Gesichtsanalyse")
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        regions: list[tuple[int, int, int, int, float]] = []
        for region in manual_regions:
            try:
                x, y, w, h = (int(region.get(k, 0)) for k in ("x", "y", "width", "height"))
            except (TypeError, ValueError):
                continue
            if w >= 40 and h >= 40 and x >= 0 and y >= 0 and x + w <= image.width and y + h <= image.height:
                regions.append((x, y, w, h, 1.0))
        if not regions:
            if not self.face_detection_available:
                image.close()
                raise RuntimeError("Lokale Gesichtsbereichserkennung ist nicht verfügbar; opencv-python-headless fehlt oder das Haar-Modell ist nicht vorhanden")
            rgb = np.array(image)
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
            detector = cv2.CascadeClassifier(cascade_path)
            try:
                rects, _reject, weights = detector.detectMultiScale3(gray, scaleFactor=1.08, minNeighbors=5, minSize=(48, 48), outputRejectLevels=True)
                for rect, weight in zip(rects, weights):
                    confidence = 1.0 / (1.0 + math.exp(-float(weight) / 2.0))
                    regions.append((int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]), confidence))
            except Exception:
                for rect in detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(48, 48)):
                    regions.append((int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]), 0.5))
        old = self.db.all("SELECT crop_relpath FROM face_detections_139 WHERE case_id=? AND asset_id=?", (case_id, asset_id))
        for row in old:
            old_path = (self.photo_root / row["crop_relpath"]).resolve()
            if self.photo_root in old_path.parents:
                old_path.unlink(missing_ok=True)
        self.db.execute("DELETE FROM face_detections_139 WHERE case_id=? AND asset_id=?", (case_id, asset_id))
        detections = [self._store_face_detection(case_id=case_id, asset=asset, image=image, bbox=(x, y, w, h), face_index=index, confidence=confidence, actor=actor) for index, (x, y, w, h, confidence) in enumerate(sorted(regions, key=lambda r: r[2] * r[3], reverse=True), 1)]
        image.close()
        self._event(case_id=case_id, event_type="face_regions_detected_139", object_type="photo_asset_136", object_id=asset_id, actor=actor, payload={"face_count": len(detections), "biometric_templates": 0, "identity_comparisons": 0, "detector": self.DETECTOR_NAME})
        return {"asset_id": asset_id, "face_count": len(detections), "detections": detections, "biometric_templates": 0, "identity_comparisons": 0, "face_recognition": False, "face_region_detection": True}

    def face_detection(self, *, case_id: str, detection_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM face_detections_139 WHERE case_id=? AND detection_id=?", (case_id, detection_id))
        if not row:
            raise KeyError("Gesichtsbereich nicht gefunden")
        row["crop_url"] = f"/api/photo139/face/{detection_id}?case_id={case_id}"
        return row

    def face_crop_path(self, *, case_id: str, detection_id: str) -> tuple[dict[str, Any], Path]:
        row = self.face_detection(case_id=case_id, detection_id=detection_id)
        path = (self.photo_root / row["crop_relpath"]).resolve()
        if self.photo_root not in path.parents or not path.is_file():
            raise FileNotFoundError("Gesichtsausschnitt fehlt")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["crop_sha256"]:
            raise PermissionError("Integritätsprüfung des Gesichtsausschnitts fehlgeschlagen")
        return row, path

    def create_face_research_runs(self, *, case_id: str, detection_id: str, provider_keys: Iterable[str], purpose: str, confirmation: str, actor: str) -> dict[str, Any]:
        detection, _path = self.face_crop_path(case_id=case_id, detection_id=detection_id)
        if confirmation.strip() != "GESICHTSAUSSCHNITT-RECHERCHE FREIGEBEN":
            raise PermissionError("Freigabephrase GESICHTSAUSSCHNITT-RECHERCHE FREIGEBEN erforderlich")
        providers = []
        for key in provider_keys:
            key = _safe_text(key, 80)
            if key and key not in providers:
                providers.append(key)
        if not providers or len(providers) > 4 or any(key not in FACE_PROVIDER_KEYS for key in providers):
            raise ValueError("Ein bis vier bekannte Bildsuchanbieter auswählen")
        purpose = _safe_text(purpose, 1500)
        if len(purpose) < 12:
            raise ValueError("Der Recherche-Zweck muss nachvollziehbar dokumentiert sein")
        case = self._case(case_id)
        opsec = self.assess_opsec(case_id=case_id, target_id=detection.get("target_id") or "", action_type="reverse_image_search", purpose=purpose, legal_basis=case.get("legal_basis") or "", data_classes=["facial_image"], actor=actor)
        if opsec["blocked"]:
            raise PermissionError("OPSEC-Prüfung blockiert die externe Fotorecherche")
        runs: list[dict[str, Any]] = []
        now = now_ts()
        with self.db.transaction(immediate=True):
            for provider_key in providers:
                provider = PHOTO_PROVIDERS[provider_key]
                task_id = new_id("task")
                run_id = new_id("frun139")
                self.db.execute("INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)", (task_id, case_id, detection.get("target_id"), "face_crop_reverse_search_139", "Manuelle Reverse-Image-Recherche mit metadatenfreiem Gesichtsausschnitt", provider["label"], provider["url"], now))
                self.db.execute("INSERT INTO face_research_runs_139(run_id,case_id,target_id,detection_id,provider_key,provider_label,provider_url,purpose,status,search_task_id,manual_upload_required,external_upload_performed,identity_claims,approved_by,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'prepared',?,1,0,0,?,?,?)", (run_id, case_id, detection.get("target_id"), detection_id, provider_key, provider["label"], provider["url"], purpose, task_id, _safe_text(actor, 120), now, now))
                runs.append(self.face_research_run(case_id=case_id, run_id=run_id))
        self._event(case_id=case_id, event_type="face_crop_research_prepared_139", object_type="face_research_run_139", object_id=runs[0]["run_id"], actor=actor, payload={"run_ids": [r["run_id"] for r in runs], "automatic_uploads": 0, "identity_claims": 0, "biometric_templates": 0})
        return {"runs": runs, "run_count": len(runs), "automatic_uploads": 0, "identity_claims": 0, "biometric_templates": 0}

    def face_research_run(self, *, case_id: str, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM face_research_runs_139 WHERE case_id=? AND run_id=?", (case_id, run_id))
        if not row:
            raise KeyError("Gesichtsausschnitt-Recherche nicht gefunden")
        row["crop_url"] = f"/api/photo139/face/{row['detection_id']}?case_id={case_id}"
        return row

    def launch_face_research_run(self, *, case_id: str, run_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        row = self.face_research_run(case_id=case_id, run_id=run_id)
        result = self.build136.launch_research_task(case_id=case_id, task_id=row["search_task_id"], actor=actor, local_redirect_origin=local_redirect_origin)
        self.db.execute("UPDATE face_research_runs_139 SET status='provider_opened',updated_at=? WHERE case_id=? AND run_id=?", (now_ts(), case_id, run_id))
        self._event(case_id=case_id, event_type="face_crop_provider_opened_139", object_type="face_research_run_139", object_id=run_id, actor=actor, payload={"provider": row["provider_key"], "manual_upload_required": True, "automatic_upload": False, "identity_claims": 0})
        result.update({"run_id": run_id, "crop_url": row["crop_url"], "manual_upload_required": True, "automatic_upload": False, "identity_claims": 0})
        return result

    def update_face_research_run(self, *, case_id: str, run_id: str, status: str, actor: str) -> dict[str, Any]:
        if status not in FACE_RUN_STATUSES:
            raise ValueError("Ungültiger Recherche-Status")
        row = self.face_research_run(case_id=case_id, run_id=run_id)
        external = 1 if status in {"uploaded_manually", "results_review", "completed"} else int(row.get("external_upload_performed") or 0)
        self.db.execute("UPDATE face_research_runs_139 SET status=?,external_upload_performed=?,updated_at=? WHERE case_id=? AND run_id=?", (status, external, now_ts(), case_id, run_id))
        self._event(case_id=case_id, event_type="face_crop_research_updated_139", object_type="face_research_run_139", object_id=run_id, actor=actor, payload={"status": status, "external_upload_performed": bool(external), "automatic_upload": False})
        return self.face_research_run(case_id=case_id, run_id=run_id)

    # ---------- photo-to-person evidence link without face matching ----------
    def assess_photo_person_link(self, *, case_id: str, target_id: str, asset_id: str, basis: Iterable[str], source_result_id: str = "", actor: str) -> dict[str, Any]:
        self._target(case_id, target_id)
        asset = self.db.one("SELECT * FROM photo_assets_136 WHERE case_id=? AND asset_id=?", (case_id, asset_id))
        if not asset:
            raise KeyError("Foto gehört nicht zu diesem Fall")
        if source_result_id:
            result = self.db.one("SELECT result_id FROM photo_research_results_138 WHERE case_id=? AND result_id=?", (case_id, source_result_id))
            if not result:
                raise KeyError("Fototreffer gehört nicht zu diesem Fall")
        bases = sorted({_safe_text(v, 80) for v in basis if _safe_text(v, 80)})
        weights = {"source_page_names_person": 0.30, "caption_names_person": 0.28, "official_profile_context": 0.35, "exact_image_provenance": 0.25, "timeline_compatible": 0.12, "location_compatible": 0.10, "manual_context_only": 0.05}
        conflicts = {"caption_names_other_person": 0.55, "timeline_conflict": 0.35, "location_conflict": 0.20, "source_disclaims_identity": 0.60}
        support = round(_clamp(sum(weights.get(v, 0.0) for v in bases)), 4)
        conflict = round(_clamp(sum(conflicts.get(v, 0.0) for v in bases)), 4)
        link_id = (self.db.one("SELECT link_id FROM photo_person_links_139 WHERE case_id=? AND target_id=? AND asset_id=?", (case_id, target_id, asset_id)) or {}).get("link_id") or new_id("pplink139")
        now = now_ts()
        existing = self.db.one("SELECT link_id FROM photo_person_links_139 WHERE link_id=?", (link_id,))
        if existing:
            self.db.execute("UPDATE photo_person_links_139 SET source_result_id=?,basis_json=?,support_score=?,conflict_score=?,review_status='candidate',review_note='',face_match_used=0,biometric_template_used=0,candidate_only=1,updated_at=? WHERE link_id=?", (source_result_id or None, dumps(bases), support, conflict, now, link_id))
        else:
            self.db.execute("INSERT INTO photo_person_links_139(link_id,case_id,target_id,asset_id,source_result_id,basis_json,support_score,conflict_score,review_status,review_note,face_match_used,biometric_template_used,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'candidate','',0,0,1,?,?,?)", (link_id, case_id, target_id, asset_id, source_result_id or None, dumps(bases), support, conflict, _safe_text(actor, 120), now, now))
        self._event(case_id=case_id, event_type="photo_person_link_assessed_139", object_type="photo_person_link_139", object_id=link_id, actor=actor, payload={"support_score": support, "conflict_score": conflict, "face_match_used": False, "biometric_template_used": False, "automatic_identity_claim": False})
        return self.photo_person_link(case_id=case_id, link_id=link_id)

    def review_photo_person_link(self, *, case_id: str, link_id: str, review_status: str, review_note: str, confirmation: str, actor: str) -> dict[str, Any]:
        row = self.photo_person_link(case_id=case_id, link_id=link_id)
        if review_status not in PHOTO_LINK_STATES:
            raise ValueError("Ungültiger Fotozuordnungsstatus")
        if review_status == "confirmed_by_investigator" and confirmation.strip() != "FOTOZUORDNUNG MANUELL BESTÄTIGEN":
            raise PermissionError("Bestätigungsphrase FOTOZUORDNUNG MANUELL BESTÄTIGEN erforderlich")
        note = _safe_text(review_note, 4000)
        if review_status == "confirmed_by_investigator" and len(note) < 12:
            raise ValueError("Manuelle Bestätigung erfordert eine Begründung")
        self.db.execute("UPDATE photo_person_links_139 SET review_status=?,review_note=?,candidate_only=?,face_match_used=0,biometric_template_used=0,updated_at=? WHERE case_id=? AND link_id=?", (review_status, note, 0 if review_status == "confirmed_by_investigator" else 1, now_ts(), case_id, link_id))
        self._event(case_id=case_id, event_type="photo_person_link_reviewed_139", object_type="photo_person_link_139", object_id=link_id, actor=actor, payload={"review_status": review_status, "manual": True, "face_match_used": False})
        return self.photo_person_link(case_id=case_id, link_id=link_id)

    def photo_person_link(self, *, case_id: str, link_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM photo_person_links_139 WHERE case_id=? AND link_id=?", (case_id, link_id))
        if not row:
            raise KeyError("Foto-Person-Zuordnung nicht gefunden")
        row["basis"] = loads(row.pop("basis_json", "[]"), [])
        return row

    # ---------- dashboards ----------
    def identity_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        candidates = self.db.all("SELECT c.*,cmp.overall_score,cmp.conflict_score,cmp.result_band,cmp.hard_conflict,cmp.face_features_used FROM identity_candidates_139 c LEFT JOIN identity_comparisons_139 cmp ON cmp.candidate_id=c.candidate_id WHERE c.case_id=? ORDER BY c.updated_at DESC LIMIT 300", (case_id,))
        for row in candidates:
            row["attributes"] = loads(row.pop("attributes_json", "{}"), {})
            row["source_refs"] = loads(row.pop("source_refs_json", "[]"), [])
        decisions = self.db.all("SELECT * FROM identity_decisions_139 WHERE case_id=? ORDER BY decided_at DESC LIMIT 100", (case_id,))
        return {"candidates": candidates, "decisions": decisions, "candidate_count": len(candidates), "open_count": sum(1 for r in candidates if r["review_status"] in {"unresolved", "reviewing"}), "automatic_merges": 0, "face_features_used": 0}

    def photo_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        detections = self.db.all("SELECT d.*,a.title AS asset_title FROM face_detections_139 d JOIN photo_assets_136 a ON a.asset_id=d.asset_id WHERE d.case_id=? ORDER BY d.created_at DESC LIMIT 300", (case_id,))
        for row in detections:
            row["crop_url"] = f"/api/photo139/face/{row['detection_id']}?case_id={case_id}"
        runs = self.db.all("SELECT * FROM face_research_runs_139 WHERE case_id=? ORDER BY updated_at DESC LIMIT 300", (case_id,))
        links = self.db.all("SELECT l.*,a.title AS asset_title,t.name AS target_name FROM photo_person_links_139 l JOIN photo_assets_136 a ON a.asset_id=l.asset_id JOIN targets t ON t.target_id=l.target_id WHERE l.case_id=? ORDER BY l.updated_at DESC LIMIT 300", (case_id,))
        for row in links:
            row["basis"] = loads(row.pop("basis_json", "[]"), [])
        return {"detections": detections, "runs": runs, "links": links, "face_count": len(detections), "run_count": len(runs), "link_count": len(links), "face_detection_available": self.face_detection_available, "biometric_templates": 0, "face_matches": 0, "automatic_uploads": 0}

    def assistant_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        briefs = self.db.all("SELECT brief_id,target_id,objective,external_ai_used,identity_claims,generated_by,created_by,created_at FROM ai_investigation_briefs_139 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))
        opsec = self.db.all("SELECT assessment_id,target_id,action_type,risk_level,blocked,purpose,created_by,created_at FROM opsec_assessments_139 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))
        return {"briefs": briefs, "opsec": opsec, "brief_count": len(briefs), "blocked_count": sum(int(r["blocked"] or 0) for r in opsec), "external_ai_calls": 0}

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "identity": self.identity_dashboard(case_id) if case_id else {"candidate_count": int((self.db.one("SELECT COUNT(*) AS n FROM identity_candidates_139") or {}).get("n") or 0)},
            "photos": self.photo_dashboard(case_id) if case_id else {"face_count": int((self.db.one("SELECT COUNT(*) AS n FROM face_detections_139") or {}).get("n") or 0)},
            "assistant": self.assistant_dashboard(case_id) if case_id else {"brief_count": int((self.db.one("SELECT COUNT(*) AS n FROM ai_investigation_briefs_139") or {}).get("n") or 0)},
            "safety": {
                "automatic_identity_claims": 0,
                "automatic_identity_merges": 0,
                "automatic_image_uploads": 0,
                "biometric_templates": 0,
                "face_matching": False,
                "remote_biometric_identification": False,
                "face_region_detection": self.face_detection_available,
                "manual_review_required": True,
                "explainable_nonbiometric_identity_scoring": True,
            },
        }
