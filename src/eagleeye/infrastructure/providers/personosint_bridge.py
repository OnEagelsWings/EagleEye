"""PersonOSINT als Recherche-Motor von EagleEye (Schritt 501 der Zusammenführung).

PersonOSINT-Quellen laufen hier als gewöhnliche EagleEye-Provider: Freigabe pro Fall und Suchanfrage,
Hostliste, SSRF-Prüfung, Ratenbegrenzung, Wiederholung, Aufzeichnung und Prüfwarteschlange bleiben
vollständig beim bestehenden Motor (``ProviderCollection120Service``). PersonOSINT liefert nur zwei
Dinge, beide ohne eigenen Netzzugriff:

* **welche Adressen** eine Quelle abfragen würde (Planungsdurchlauf gegen eine Attrappe),
* **was in den Antworten steht** – Treffer samt strukturierter Aussagen (``claims``), Namen, Orten.

Übernommen werden nur Quellen, die EagleEye noch fehlen, ohne Zugangsschlüssel auskommen und in einem
Schritt abfragen. Eine Quelle, deren zweiter Abruf vom ersten abhinge, würde hier nicht vollständig
ausgewertet – solche Quellen sind ausgeschlossen (siehe ``EXCLUDED``).

Alles bleibt Kandidat: ``identity_confirmed`` ist immer ``False``; bestätigt wird in der Prüfwarteschlange.
"""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path
from typing import Any, Sequence

from .contracts import (
    NormalizedProviderItem, ProviderAdapter, ProviderDefinition, ProviderHttpRequest, ProviderRunRequest,
    ProviderTransportError, ProviderTransportResponse, ProviderValidationError,
)
from .policy import canonicalize_public_url

#: PersonOSINT-Quellen, die als EagleEye-Provider laufen (Schlüssel der PersonOSINT-Quelle)
BRIDGED = (
    "username_presence", "gravatar", "interpol_yellow", "nominatim", "crtsh",
    "wikipedia", "fr_entreprises", "icij_online", "interpol_red", "fbi_wanted", "keybase", "codeberg", "dockerhub",
    "fbi_missing", "gdelt_missing",
)
#: Bewusst nicht übernommen – mit Grund (wird in der Oberfläche und im Bericht angezeigt)
EXCLUDED = {
    "github": "in EagleEye vorhanden (github_public_profile_120)",
    "gitlab": "in EagleEye vorhanden (gitlab_public_profile_120)",
    "bluesky": "in EagleEye vorhanden (bluesky_actor_search_public_147)",
    "mastodon": "in EagleEye vorhanden (mastodon_social_search_public_147)",
    "wikidata": "in EagleEye vorhanden (wikidata_entities_public_128)",
    "openalex": "in EagleEye vorhanden (openalex_authors_public_128)",
    "wayback": "in EagleEye vorhanden (wayback_cdx_public_120)",
    "gleif": "in EagleEye vorhanden (gleif_lei_public_135)",
    "rdap": "in EagleEye vorhanden (rdap_public_120)",
    "lobid_gnd": "in EagleEye vorhanden (lobid_gnd_persons_public_501)",
    "abgeordnetenwatch": "in EagleEye vorhanden (abgeordnetenwatch_persons_public_501)",
    "crossref": "in EagleEye vorhanden (crossref_topics_public_501, crossref_works_public_128)",
    "dblp": "in EagleEye vorhanden (dblp_authors_public_149)",
    "gdelt_news": "in EagleEye vorhanden (gdelt_doc_public_149)",
    "wikidata_rel": "zweistufige Abfrage (Suche, dann SPARQL) – passt nicht in den freigegebenen Einzelabruf",
    "orcid": "Public API nur für nichtkommerzielle Dienste – im Büroeinsatz nicht automatisch (manuelle Suche im Quellenkatalog)",
    "opencorporates": "API verlangt einen Zugangsschlüssel, kommerzielle Nutzung nur mit Lizenz",
    "companies_house": "braucht einen Zugangsschlüssel; der EagleEye-Motor lässt keine Zugangsdaten zu",
    "opensanctions": "braucht einen Zugangsschlüssel; der EagleEye-Motor lässt keine Zugangsdaten zu",
}
#: Eingabearten, die in der Suchanfrage als Präfix angegeben werden können („benutzername: maxmuster“)
KIND_PREFIX = {"name": "name", "benutzername": "username", "username": "username", "email": "email", "e-mail": "email",
               "domain": "domain", "url": "url", "webadresse": "url", "ort": "location", "firma": "employer",
               "arbeitgeber": "employer", "organisation": "employer"}
KIND_LABEL = {"name": "Name", "username": "Benutzername", "email": "E-Mail", "domain": "Domain", "url": "Webadresse",
              "location": "Ort", "employer": "Firma"}
EXPOSURE = {"username_presence": "plattform", "keybase": "plattform", "codeberg": "plattform", "dockerhub": "plattform",
            "gravatar": "passiv"}


def _personosint():
    """PersonOSINT importieren – installiert als Paket oder aus dem Ordner ``PersonOSINT`` neben ``src``."""
    try:
        import personosint  # noqa: F401
    except ImportError:
        root = Path(__file__).resolve().parents[4] / "PersonOSINT"
        if not (root / "personosint" / "__init__.py").is_file():
            return None
        sys.path.insert(0, str(root))
        try:
            import personosint  # noqa: F401
        except ImportError:
            return None
    from personosint import sources as po_sources
    from personosint.connectors import ONLINE_SOURCES
    from personosint.connectors2 import MORE_SOURCES
    from personosint.facts import predicate_label

    # Ratenbegrenzung übernimmt der EagleEye-Motor; die eigene Wartezeit von PersonOSINT würde nur doppelt bremsen.
    po_sources.THROTTLE_ENABLED = False
    return po_sources, {s.key: s for s in list(po_sources.SOURCES) + list(ONLINE_SOURCES) + list(MORE_SOURCES)}, predicate_label


class _PlanHttp:
    """Attrappe für den Planungsdurchlauf: merkt sich jede Adresse, liefert nichts, verlässt den Rechner nie."""

    def __init__(self, po_sources) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._resp = po_sources.HttpResponse
        self._lock = threading.Lock()

    def get(self, url: str, headers: dict[str, str] | None = None):
        with self._lock:
            self.calls.append((url, dict(headers or {})))
        return self._resp(404, b"", url)


class _ReplayHttp:
    """Gibt der PersonOSINT-Auswertung genau die Antworten, die der EagleEye-Motor abgerufen hat."""

    def __init__(self, po_sources, responses: dict[str, ProviderTransportResponse]) -> None:
        self._resp = po_sources.HttpResponse
        self._responses = responses

    def get(self, url: str, headers: dict[str, str] | None = None):
        try:
            key = canonicalize_public_url(url)
        except ProviderValidationError:
            key = url
        found = self._responses.get(key)
        if found is None:
            raise ProviderValidationError("PersonOSINT-Quelle verlangte eine nicht freigegebene Folgeadresse")
        return self._resp(int(found.status_code), bytes(found.body), found.final_url,
                          headers=[(str(k), str(v)) for k, v in dict(found.headers).items()])


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        canonicalize_public_url(url)
    except ProviderValidationError:
        return ""
    return url


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("_")


class PersonOsintSourceAdapter(ProviderAdapter):
    """Eine PersonOSINT-Quelle als EagleEye-Provider."""

    def __init__(self, source, po_sources, predicate_label) -> None:
        self.source = source
        self._po = po_sources
        self._predicate_label = predicate_label
        self._pending: dict[tuple, dict[str, Any]] = {}
        self._lock = threading.Lock()
        kinds = [KIND_LABEL.get(k, k) for k in source.kinds]
        self.definition = ProviderDefinition(
            provider_key=f"personosint_{source.key}_501",
            label=f"PersonOSINT: {source.label}",
            provider_type="personosint_" + _slug(source.group),
            allowed_hosts=tuple(source.hosts),
            rate_limit_per_minute=max(1, min(int(source.rate_per_min or 20), 60)),
            min_interval_seconds=0.0 if source.key == "username_presence" else round(60.0 / max(1, int(source.rate_per_min or 20)), 2),
            terms_profile=source.license,
            # Die Aufzeichnung für die Offline-Wiederholung verlangt JSON-Antworten. Kontoquellen antworten oft mit leerem
            # 404 oder HTML (Telegram, PyPI); gesichert wird hier über die Kandidaten samt Rohdaten im Prüfeingang.
            supports_replay=False,
            metadata={
                "build": "501-personosint-engine", "engine": "personosint", "source_key": source.key,
                "documentation": source.docs, "description": source.description, "reliability": source.reliability,
                "exposure": EXPOSURE.get(source.key, "passiv"), "input_types": list(source.kinds),
                "input_hint": "Eingabe: " + " oder ".join(kinds) + (
                    " – andere Art mit Präfix angeben, z. B. „" + KIND_LABEL.get(source.kinds[1], source.kinds[1]).lower() + ": …“"
                    if len(source.kinds) > 1 else ""),
                "candidate_only": True, "structured_claims": True,
                # Bei Konto- und Profilquellen bedeutet HTTP 404 „gibt es nicht“ – das ist ein Ergebnis, kein Fehler.
                # Die PersonOSINT-Quelle bekommt den Status und entscheidet selbst (wie in PersonOSINT allein).
                "http_4xx_is_result": True,
            },
        )

    # ---------- Eingabe ----------
    def _kind_value(self, query: str) -> tuple[str, str]:
        text = " ".join(query.split())
        match = re.match(r"^([A-Za-zÄÖÜäöü-]+):\s*(.+)$", text)
        if match and match[1].casefold() in KIND_PREFIX:
            kind, value = KIND_PREFIX[match[1].casefold()], match[2].strip()
        else:
            kind, value = self.source.kinds[0], text
        if kind not in self.source.kinds:
            allowed = ", ".join(KIND_LABEL.get(k, k) for k in self.source.kinds)
            raise ProviderValidationError(f"{self.source.label} verarbeitet nur: {allowed}")
        if not value or len(value) > 200:
            raise ProviderValidationError("Suchbegriff fehlt oder ist zu lang")
        return kind, value

    def validate_request(self, request: ProviderRunRequest) -> None:
        super().validate_request(request)
        self._kind_value(request.query)

    @staticmethod
    def _run_key(request: ProviderRunRequest) -> tuple:
        return (id(request), request.case_id, request.provider_key, request.query)

    # ---------- Planung: welche Adressen? ----------
    def build_requests(self, request: ProviderRunRequest) -> Sequence[ProviderHttpRequest]:
        kind, value = self._kind_value(request.query)
        plan = _PlanHttp(self._po)
        try:
            self.source.runner(self.source, kind, value, plan)
        except Exception:  # noqa: BLE001 - die Attrappe antwortet absichtlich mit 404; nur die Adressen zählen
            pass
        planned: list[ProviderHttpRequest] = []
        seen: set[str] = set()
        for url, headers in plan.calls:
            canonical = canonicalize_public_url(url)
            if canonical in seen:
                continue
            seen.add(canonical)
            safe_headers = {k: v for k, v in headers.items() if k.casefold() in {"accept", "accept-language"}}
            planned.append(ProviderHttpRequest(canonical, headers=safe_headers, label=self.source.key))
        if not planned:
            raise ProviderValidationError(f"{self.source.label}: Für diese Eingabe gibt es keine Abfrage (Format prüfen)")
        with self._lock:
            if len(self._pending) > 200:   # Reste abgebrochener Läufe nicht anhäufen
                self._pending.clear()
            self._pending[self._run_key(request)] = {"kind": kind, "value": value, "expected": [r.url for r in planned],
                                                     "responses": {}}
        return tuple(planned)

    # ---------- Auswertung: was steht in den Antworten? ----------
    def normalize(self, response: ProviderTransportResponse, request: ProviderRunRequest) -> Sequence[NormalizedProviderItem]:
        key = self._run_key(request)
        with self._lock:
            state = self._pending.get(key)
            if state is None:
                raise ProviderValidationError("PersonOSINT-Auswertung ohne zugehörige Planung")
            state["responses"][canonicalize_public_url(response.requested_url)] = response
            if len(state["responses"]) < len(state["expected"]):
                return ()      # mehrteilige Abfrage: erst auswerten, wenn alle Antworten da sind
            self._pending.pop(key, None)
        try:
            found = self.source.runner(self.source, state["kind"], state["value"], _ReplayHttp(self._po, state["responses"]))
        except ProviderValidationError:
            raise
        except self._po.SourceError as exc:
            raise ProviderTransportError(f"{self.source.label}: {exc}") from exc
        fallback = canonicalize_public_url(response.requested_url)
        out = []
        for item in found or []:
            claims = []
            for c in item.get("claims") or []:
                if not c.get("object"):
                    continue
                claims.append({"subject": c.get("subject") or "", "subject_type": c.get("subject_type") or "",
                               "predicate": c["predicate"], "predicate_label": self._predicate_label(c["predicate"]),
                               "object": c["object"], "object_type": c.get("object_type") or "wert",
                               "valid_from": c.get("valid_from") or "", "valid_to": c.get("valid_to") or "",
                               "attrs": dict(c.get("attrs") or {})})
            url = _safe_url(item.get("url")) or fallback
            payload = {
                "engine": "personosint", "source_key": self.source.key, "source_label": self.source.label,
                "category": item.get("category") or self.source.category, "query_kind": state["kind"],
                "query_value": state["value"],
                "names": [n for n in (item.get("names") or []) if n][:10],
                "locations": [x for x in (item.get("locations") or []) if x][:10],
                "data": {k: v for k, v in (item.get("data") or {}).items() if v not in (None, "", [])},
                "claims": claims, "reliability": self.source.reliability, "license": self.source.license,
                "identity_confirmed": False, "candidate_only": True,
            }
            out.append(NormalizedProviderItem(
                title=str(item.get("title") or self.source.label)[:500], url=url,
                snippet=str(item.get("snippet") or "")[:2000],
                source_type="personosint_" + _slug(str(item.get("category") or self.source.category)),
                raw_payload=payload,
            ))
        return tuple(out)

    def health_check(self) -> dict[str, Any]:
        return {"provider_key": self.definition.provider_key, "configuration": "valid", "engine": "personosint",
                "source_key": self.source.key}


def personosint_adapters() -> tuple[ProviderAdapter, ...]:
    """Alle übernommenen PersonOSINT-Quellen als Adapter – leer, wenn PersonOSINT nicht vorhanden ist."""
    loaded = _personosint()
    if loaded is None:
        return ()
    po_sources, catalog, predicate_label = loaded
    return tuple(PersonOsintSourceAdapter(catalog[key], po_sources, predicate_label) for key in BRIDGED if key in catalog)
