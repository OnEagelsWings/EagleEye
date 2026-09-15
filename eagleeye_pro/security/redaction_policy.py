from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple

PATTERNS: List[Tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[E-MAIL REDIGIERT]"),
    ("phone", re.compile(r"(?<!\w)(?:\+?\d[\d\s()/.-]{7,}\d)(?!\w)"), "[TELEFON REDIGIERT]"),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[\s-]?(?:[A-Z0-9]{4}[\s-]?){3,7}[A-Z0-9]{0,4}\b"), "[IBAN REDIGIERT]"),
    ("birthdate", re.compile(r"\b(?:geb\.?|geboren|birth(?:date)?)\s*(?:am)?\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", re.I), "[GEBURTSDATUM REDIGIERT]"),
    ("possible_address", re.compile(r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+){0,3}\s+)?[A-ZÄÖÜ][\wÄÖÜäöüß.-]*(?:straße|strasse|weg|platz|allee|gasse|ring)\s+\d+[a-zA-Z]?\b", re.I), "[ADRESSE REDIGIERT]"),
    ("license_plate", re.compile(r"\b[A-ZÄÖÜ]{1,3}\s*[- ]\s*[A-Z]{1,2}\s*[- ]\s*\d{1,4}\b"), "[KENNZEICHEN REDIGIERT]"),
    ("private_handle", re.compile(r"(?<!\w)@[A-Za-z0-9_.-]{3,32}\b"), "[HANDLE REDIGIERT]"),
]
SENSITIVE_MARKERS = {
    "minor_related": ["minderjähr", "kind", "schüler", "schülerin", "klasse", "jugendlich"],
    "victim_witness_related": ["opfer", "zeuge", "zeugin", "victim", "witness"],
    "health_related": ["diagnose", "krankheit", "therapie", "gesundheit", "medical"],
    "religion_political_union_related": ["religion", "gewerkschaft", "partei", "politisch"],
}
@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str; detections: List[Dict[str, Any]]; decision: str; mode: str
    def as_dict(self) -> Dict[str, Any]: return asdict(self)
class RedactionEngine:
    """Build 63.0 redaction engine with explicit detection metadata."""
    @staticmethod
    def detect(text: str) -> Dict[str, Any]:
        value = text or ""; detections: List[Dict[str, Any]] = []
        for dtype, pattern, _replacement in PATTERNS:
            count = len(pattern.findall(value))
            if count: detections.append({"type": dtype, "count": count})
        low = value.lower()
        for dtype, terms in SENSITIVE_MARKERS.items():
            hits = [t for t in terms if t in low]
            if hits: detections.append({"type": dtype, "count": len(hits), "markers": hits[:8]})
        critical = {"possible_address", "minor_related", "victim_witness_related", "health_related", "religion_political_union_related"}
        decision = "redaction_required" if any(d["type"] in critical for d in detections) else ("redaction_recommended" if detections else "no_redaction_detected")
        return {"detections": detections, "decision": decision}
    @staticmethod
    def redact(text: str, mode: str = "authority_redacted") -> Dict[str, Any]:
        value = text or ""; detection = RedactionEngine.detect(value); redacted = value
        if mode != "internal_full":
            for dtype, pattern, replacement in PATTERNS:
                if mode == "authority_redacted" and dtype == "private_handle": continue
                redacted = pattern.sub(replacement, redacted)
        decision = detection["decision"]
        if mode != "internal_full" and detection["detections"]:
            decision = "redacted_with_warnings" if decision != "redaction_required" else "redacted_review_required"
        return RedactionResult(redacted, detection["detections"], decision, mode).as_dict()
