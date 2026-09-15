from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List
import re

ALLOWED_CLAIM_TYPES = {
    "claim_public_profile_possible_match",
    "claim_public_employment_hint",
    "claim_public_company_relation",
    "claim_public_domain_or_registry_relation",
    "claim_public_timeline_event",
    "claim_counter_evidence",
    "claim_uncertainty",
    "claim_exclusion",
}

FORBIDDEN_CLAIM_TYPES = {
    "confirmed_identity",
    "guilty",
    "dangerous",
    "home_address_confirmed",
    "biometric_match",
    "private_phone_confirmed",
    "live_location",
}

FORBIDDEN_QUERY_INTENTS = {
    "private_address_lookup",
    "credential_access",
    "account_bypass",
    "stalking_or_live_tracking",
    "biometric_identification",
    "guilt_or_danger_inference",
}

PROHIBITED_QUERY_PATTERNS = [
    r"\bdoxx?\b", r"\bstalk(?:ing|en|er)?\b", r"\bbypass\b", r"\bcaptcha\b",
    r"\bpassword\b", r"\bcredential", r"\blogin\s*umgehen", r"konto\s*knacken",
    r"private\s+address", r"wohnadresse\s+herausfinden", r"adresse\s+finden",
    r"finde\s+die\s+adresse", r"wohnung\s+finden", r"gps\s+tracking",
    r"live\s+location", r"live\s+standort", r"\biban\b", r"bankverbindung",
    r"personalausweis", r"ausweisnummer", r"private\s+phone", r"privatnummer",
    r"biometric", r"face\s*match", r"gesichtserkennung",
]

SENSITIVE_MARKERS = {
    "minor": ["minderjährig", "kind", "kinder", "jugendlich", "schule", "klasse"],
    "religion": ["religion", "kirche", "gemeinde", "synagoge", "jüdisch", "jewish"],
    "health": ["krankheit", "diagnose", "patient", "gesundheit", "therapie"],
    "criminal": ["strafverfahren", "verdächtig", "anklage", "haft", "polizei"],
    "location_private": ["wohnadresse", "privatadresse", "home address", "gps", "live location"],
}

REPORTABILITY_LEVELS = {
    "not_reportable",
    "internal_only",
    "reportable_with_redaction",
    "reportable_with_uncertainty",
    "reportable_as_verified_claim",
}

@dataclass(frozen=True)
class Decision:
    decision: str
    gate: str
    reason_code: str
    message: str
    risk_markers: List[str] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)
    audit_event_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.decision == "allow"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "gate": self.gate,
            "reason_code": self.reason_code,
            "message": self.message,
            "risk_markers": list(self.risk_markers),
            "required_actions": list(self.required_actions),
            "audit_event_id": self.audit_event_id,
        }


def classify_sensitivity(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    markers: List[str] = []
    for key, words in SENSITIVE_MARKERS.items():
        if any(word in lowered for word in words):
            markers.append(key)
    level = "high" if markers else "normal"
    return {"level": level, "markers": sorted(set(markers)), "redaction_required": bool(markers)}


def validate_query(query: str, intent: str = "public_osint") -> Decision:
    q = (query or "").strip()
    if not q:
        return Decision("block", "query_gate", "EMPTY_QUERY", "Die Abfrage ist leer.")
    if len(q) > 384:
        return Decision("block", "query_gate", "QUERY_TOO_LONG", "Die Abfrage ist zu lang und wirkt wie eine Datenabladung.")
    if intent in FORBIDDEN_QUERY_INTENTS:
        return Decision("block", "query_gate", "FORBIDDEN_QUERY_INTENT", f"Der Zweck '{intent}' ist nicht zulässig.", [intent])
    for pattern in PROHIBITED_QUERY_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return Decision("block", "query_gate", "FORBIDDEN_QUERY_PATTERN", f"Die Abfrage verletzt die Policy: {pattern}", ["prohibited_query"])
    sensitivity = classify_sensitivity(q)
    if sensitivity["markers"]:
        return Decision("review_required", "query_gate", "SENSITIVE_QUERY_REVIEW", "Die Abfrage enthält sensible Marker und braucht Review.", sensitivity["markers"], ["privacy_review"])
    return Decision("allow", "query_gate", "QUERY_ALLOWED", "Öffentliche, eingegrenzte Abfrage zugelassen.")


def validate_claim_type(claim_type: str) -> Decision:
    if claim_type in FORBIDDEN_CLAIM_TYPES:
        return Decision("block", "verification_gate", "FORBIDDEN_CLAIM_TYPE", f"Der Claim-Typ '{claim_type}' ist gesperrt.", [claim_type], ["rewrite_as_uncertainty_or_counter_evidence"])
    if claim_type not in ALLOWED_CLAIM_TYPES:
        return Decision("review_required", "verification_gate", "UNKNOWN_CLAIM_TYPE", f"Der Claim-Typ '{claim_type}' ist unbekannt und braucht Review.", ["unknown_claim"], ["legal_review", "verification_review"])
    return Decision("allow", "verification_gate", "CLAIM_TYPE_ALLOWED", "Claim-Typ zugelassen.")


def normalize_reportability(value: str, *, has_uncertainty: bool = True) -> str:
    value = (value or "").strip()
    if value not in REPORTABILITY_LEVELS:
        return "reportable_with_uncertainty" if has_uncertainty else "reportable_with_redaction"
    return value
