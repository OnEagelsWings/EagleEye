from __future__ import annotations
from typing import List, Dict
import re

PROHIBITED_QUERY_PATTERNS = [
    r"\bbypass\b", r"\bcaptcha\b", r"\bpassword\b", r"\bcredential", r"\bhack\b",
    r"\bstalk", r"\bdox", r"private\s+address", r"wohnadresse\s+herausfinden",
    r"login\s*umgehen", r"captcha\s*umgehen", r"konto\s*knacken",
    # Build 37.0 hardening: keine Abfragen, die auf geheime/private Identifikatoren,
    # Accountzugriff oder Doxxing-/Stalking-Zwecke ausgerichtet sind.
    r"social\s+security\s+number", r"\bssn\b", r"personalausweis", r"ausweisnummer",
    r"kreditkarte", r"credit\s+card", r"\biban\b", r"bankverbindung",
    r"private\s+phone", r"privatnummer", r"gps\s+tracking", r"live\s+location",
    r"wohnung\s+finden", r"adresse\s+finden", r"finde\s+die\s+adresse",
]

MAX_QUERY_LENGTH = 512
MAX_MULTI_SEARCH_URLS = 12
SENSITIVE_MARKERS = {
    "health": ["krankheit", "diagnose", "gesundheit", "therapy", "patient"],
    "religion": ["religion", "church", "kirche", "moschee", "synagoge", "gemeinde"],
    "politics": ["partei", "political", "politisch", "wahlkampf"],
    "criminal": ["strafverfahren", "verurteilt", "anklage", "polizei", "haft"],
    "minor": ["schule", "klasse", "minderjährig", "kind", "jugendlich"],
}

class PolicyGate:
    @staticmethod
    def evaluate_query(query: str) -> Dict[str, object]:
        q = (query or "").strip()
        if len(q) > MAX_QUERY_LENGTH:
            return {"ok": False, "gate": "QUERY_BLOCKED", "reason": "Query too long; possible data dump or overbroad personal-data collection."}
        for pattern in PROHIBITED_QUERY_PATTERNS:
            if re.search(pattern, q, re.IGNORECASE):
                return {"ok": False, "gate": "QUERY_BLOCKED", "reason": f"Blocked policy pattern: {pattern}"}
        return {"ok": True, "gate": "QUERY_ALLOWED"}

    @staticmethod
    def classify_sensitivity(text: str) -> Dict[str, object]:
        t = (text or "").lower()
        hits: List[str] = []
        for category, words in SENSITIVE_MARKERS.items():
            if any(w in t for w in words):
                hits.append(category)
        level = "high" if hits else "normal"
        return {"level": level, "markers": hits, "redaction_required": level == "high"}
