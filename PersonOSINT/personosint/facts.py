"""Faktenmodell: aus Quellentreffern werden strukturierte, belegte Aussagen.

Eine Aussage lautet immer: *Subjekt – Prädikat – Objekt (Zeitraum)*, z. B.
„Max Muster – Funktion bei – Beispiel GmbH (seit 2019-03)“, mit Quelle, Abrufzeit und Bewertung.
"""
from __future__ import annotations

from typing import Any

from .matching import fold, name_tokens

#: Prädikate: Beschriftung, Kategorie im Dossier, Beziehung im Graphen, funktional = nur ein gültiger Wert (Widerspruchsprüfung)
PREDICATES: dict[str, dict[str, Any]] = {
    # Identität
    "geburtsdatum": {"label": "Geburtsdatum", "category": "Identität", "functional": True},
    "geburtsort": {"label": "Geburtsort", "category": "Identität", "functional": True},
    "staatsangehoerigkeit": {"label": "Staatsangehörigkeit", "category": "Identität", "functional": False},
    "geschlecht": {"label": "Geschlecht", "category": "Identität", "functional": True},
    "adresse": {"label": "Adresse", "category": "Identität", "functional": False, "relation": "wohnt in"},
    "alias": {"label": "Auch bekannt als", "category": "Identität", "functional": False},
    "email": {"label": "E-Mail-Adresse", "category": "Identität", "functional": False},
    "beschreibung": {"label": "Beschreibung", "category": "Identität", "functional": False},
    # Familie & Umfeld
    "verheiratet_mit": {"label": "verheiratet mit", "category": "Familie & Umfeld", "relation": "Partner/in von"},
    "elternteil": {"label": "Elternteil", "category": "Familie & Umfeld", "relation": "verwandt mit"},
    "kind": {"label": "Kind", "category": "Familie & Umfeld", "relation": "verwandt mit"},
    "geschwister": {"label": "Geschwister", "category": "Familie & Umfeld", "relation": "verwandt mit"},
    # Beruf & Wirtschaft
    "funktion_bei": {"label": "Funktion bei", "category": "Beruf & Wirtschaft", "relation": "Funktion bei"},
    "arbeitet_bei": {"label": "arbeitet/arbeitete bei", "category": "Beruf & Wirtschaft", "relation": "arbeitet bei"},
    "mitglied_von": {"label": "Mitglied von", "category": "Beruf & Wirtschaft", "relation": "Mitglied von"},
    "partei": {"label": "Partei", "category": "Beruf & Wirtschaft", "relation": "Mitglied von"},
    "amt": {"label": "Amt / Position", "category": "Beruf & Wirtschaft"},
    "ausbildung": {"label": "Ausbildung an", "category": "Beruf & Wirtschaft", "relation": "Mitglied von"},
    "tochter_von": {"label": "Tochtergesellschaft von", "category": "Beruf & Wirtschaft", "relation": "beteiligt an"},
    "oberste_mutter": {"label": "oberste Muttergesellschaft", "category": "Beruf & Wirtschaft", "relation": "beteiligt an"},
    "firmensitz": {"label": "Firmensitz", "category": "Beruf & Wirtschaft", "functional": False},
    "registriert_als": {"label": "registriert als", "category": "Beruf & Wirtschaft"},
    "firmenstatus": {"label": "Status der Firma", "category": "Beruf & Wirtschaft"},
    # Online & Technik
    "domain_registrar": {"label": "Registrar", "category": "Online & Technik"},
    "domain_registriert_am": {"label": "registriert am", "category": "Online & Technik", "functional": True},
    "domain_inhaber": {"label": "Domain-Inhaber", "category": "Online & Technik"},
    "nameserver": {"label": "Nameserver", "category": "Online & Technik"},
    "subdomain": {"label": "Subdomain", "category": "Online & Technik", "relation": "sonstige Verbindung"},
    "zertifikat_fuer": {"label": "Zertifikat für", "category": "Online & Technik", "relation": "sonstige Verbindung"},
    "konto": {"label": "Online-Konto", "category": "Online & Technik", "relation": "besitzt Konto"},
    # Risiko
    "sanktioniert": {"label": "steht auf Sanktionsliste", "category": "Risiko", "risk": "sanktion"},
    "pep": {"label": "politisch exponierte Person (PEP)", "category": "Risiko", "risk": "pep"},
    "gelistet_in": {"label": "gelistet in", "category": "Risiko"},
    "offshore_funktion": {"label": "Funktion bei Offshore-Gesellschaft", "category": "Risiko", "relation": "Funktion bei", "risk": "offshore"},
    "offshore_vermittler": {"label": "Offshore-Vermittler", "category": "Risiko", "relation": "sonstige Verbindung", "risk": "offshore"},
}

CATEGORY_ORDER = ["Identität", "Familie & Umfeld", "Beruf & Wirtschaft", "Online & Technik", "Risiko"]

#: Objekttypen, die im Graphen zu eigenen Knoten werden
GRAPH_TYPES = {"person": "person", "organisation": "organisation", "ort": "ort", "domain": "domain", "konto": "konto"}


def predicate_label(key: str) -> str:
    return PREDICATES.get(key, {}).get("label", key.replace("_", " "))


def norm_value(predicate: str, value: str) -> str:
    """Normalisierung für den Abgleich gleicher Aussagen aus verschiedenen Quellen."""
    value = (value or "").strip()
    if predicate == "geburtsdatum":
        return value[:7]  # Jahr-Monat: Register liefern oft nur den Monat
    if predicate == "domain_registriert_am":
        return value[:10]
    if predicate in {"email", "subdomain", "zertifikat_fuer", "nameserver"}:
        return value.casefold().rstrip(".")
    tokens = name_tokens(value)
    drop = {"gmbh", "ag", "ltd", "limited", "inc", "llc", "plc", "co", "kg", "se", "sa", "bv", "the", "und", "and"}
    core = [t for t in tokens if t not in drop]
    return " ".join(core or tokens) or fold(value)


def norm_key(subject: str, predicate: str, obj: str) -> str:
    return f"{norm_value('x', subject)}|{predicate}|{norm_value(predicate, obj)}"


def claim(predicate: str, obj: str, object_type: str = "wert", valid_from: str = "", valid_to: str = "",
          subject: str = "", subject_type: str = "", **attrs: Any) -> dict[str, Any]:
    """Hilfsfunktion für Konnektoren: eine Aussage im einheitlichen Format."""
    return {"predicate": predicate, "object": str(obj or "").strip()[:300], "object_type": object_type,
            "valid_from": str(valid_from or "")[:10], "valid_to": str(valid_to or "")[:10],
            "subject": subject, "subject_type": subject_type, "attrs": {k: v for k, v in attrs.items() if v not in (None, "", [])}}
