"""Schritt 502: PersonOSINT-Auswertung auf den Kandidaten der Fallakte.

Grundlage sind ausschließlich die Aussagen (``claims``), die der PersonOSINT-Motor beim freigegebenen Lauf im
Prüfeingang (``provider_intake_120``) abgelegt hat. Die Auswertung liest nur – sie schreibt nichts, fragt keine
Quelle ab und bestätigt keine Identität. Abgelehnte oder als Dublette markierte Kandidaten zählen als verworfen.

* Bewertung je Aussage im Admiralitätscode (Quelle A–F, Inhalt 1–6), Bestätigung durch unabhängige Quellen
* Widersprüche bei Angaben, die nur einen gültigen Wert haben können (z. B. Geburtsdatum)
* Warnhinweise (Sanktionen, PEP, Offshore, viele/kurze Mandate …) – Hinweise, keine Vorwürfe
* Querbezüge (gemeinsame Adresse, gemeinsame Firma …) über mehrere Kandidaten hinweg
"""
from __future__ import annotations

from typing import Any

from eagleeye.infrastructure.providers.personosint_bridge import _personosint

#: Prüfstatus im Eingang → Status einer PersonOSINT-Aussage
STATUS = {"rejected": "verworfen", "duplicate": "verworfen"}


def available() -> bool:
    return _personosint() is not None


def case_facts(ctx, case_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Aussagen aller PersonOSINT-Kandidaten eines Falls im Format der PersonOSINT-Auswertung."""
    from personosint.facts import PREDICATES, norm_key, predicate_label
    from personosint.service import safe_url

    facts: list[dict[str, Any]] = []
    for row in reversed(ctx.provider_collection_120.list_intake(case_id, limit=limit)):
        payload = row.get("raw_payload") or {}
        if payload.get("engine") != "personosint":
            continue
        own = (payload.get("names") or [None])[0] or payload.get("query_value") or row.get("title") or ""
        for claim in payload.get("claims") or []:
            predicate, obj = str(claim.get("predicate") or ""), str(claim.get("object") or "")
            if predicate not in PREDICATES or not obj:
                continue
            subject = str(claim.get("subject") or own)
            attrs = dict(claim.get("attrs") or {})
            facts.append({
                "id": len(facts) + 1, "intake_id": row["intake_id"], "intake_title": row.get("title") or "",
                "subject_entity_id": None, "subject_label": subject,
                "subject_type": "person" if not claim.get("subject") else (claim.get("subject_type") or "sonstiges"),
                "predicate": predicate, "predicate_label": predicate_label(predicate),
                "object_label": obj, "object_type": claim.get("object_type") or "wert",
                "valid_from": str(claim.get("valid_from") or ""), "valid_to": str(claim.get("valid_to") or ""), "data": attrs,
                "source_key": str(payload.get("source_key") or row["provider_key"]),
                "source_label": str(payload.get("source_label") or row["provider_key"]),
                "source_url": safe_url(attrs.get("quelle_url") or row.get("url") or ""),
                "status": STATUS.get(str(row.get("review_status") or "new"), "neu"),
                "reliability": str(payload.get("reliability") or "F"), "credibility": None,
                "norm_key": norm_key(subject, predicate, obj),
            })
    return facts


def analyze(ctx, user, case_id: str) -> dict[str, Any]:
    ctx.team_governance_359.authorize(user, case_id=case_id, capability="case.read",
                                      object_type="operational_case", object_id=case_id)
    if not available():
        return {"available": False, "facts": [], "contradictions": [], "red_flags": [], "correlations": [], "stats": {}}
    from personosint import analysis, correlation

    facts = case_facts(ctx, case_id)
    assessed = analysis.assess(facts, {})
    rules = [{**rule, "enabled": True} for rule in correlation.BUILTIN]
    return {"available": True, "facts": assessed["facts"], "contradictions": assessed["contradictions"],
            "red_flags": analysis.red_flags(assessed, analysis.rule_config("")),
            "correlations": correlation.evaluate(rules, facts), "stats": assessed["stats"],
            "candidates": len({f["intake_id"] for f in facts}), "network_executed": False}
