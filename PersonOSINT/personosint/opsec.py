"""OPSEC-Regelwerk: Schutz der Recherche, der Recherchierenden und ihrer Quellen.

Vier Schichten (siehe OPSEC_KONZEPT.md):
  1. OPSEC-Stufe je Fall mit festen, technisch durchgesetzten Regeln
  2. Kontrollierter Netzausgang (Egress-Profile) – bei Fehlern wird NICHT direkt zugegriffen ("fail closed")
  3. Spurenkontrolle – Außenkontakt-Protokoll, Metadaten-Bereinigung, Export-Register mit Kennung
  4. Arbeitsplatz-Disziplin – Briefing-Bestätigung, Decknamen, Schnellsperre
"""
from __future__ import annotations

import json
import re
import secrets
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

# --------------------------------------------------------------------------- Exposition

#: Wie sichtbar ist eine Abfrage für Außenstehende?
EXPOSURE = {
    "lokal": {"label": "Lokal", "rank": 0,
              "help": "Abfrage in einer lokal importierten Referenzdatenbank. Die Anfrage verlässt den Server nicht."},
    "passiv": {"label": "Passiv", "rank": 0,
               "help": "Abfrage bei Registern/Archiven (z. B. Wikidata, Internet Archive). Keine Plattform der Zielperson wird kontaktiert."},
    "plattform": {"label": "Plattform", "rank": 1,
                  "help": "Abfrage bei einer Plattform, auf der die Zielperson ein Konto haben kann. Die Plattform protokolliert die Anfrage, die Person sieht sie nicht."},
    "sichtbar": {"label": "Sichtbar", "rank": 2,
                 "help": "Die Zielperson kann den Zugriff bemerken (z. B. Profilbesucher-Anzeige bei LinkedIn/XING, Lesebestätigungen)."},
    "zielkontakt": {"label": "Zielkontakt", "rank": 3,
                    "help": "Direkter Zugriff auf Infrastruktur, die die Zielperson selbst kontrolliert (eigene Webseite, eigener Server)."},
}

#: Exposition der automatischen Quellen
SOURCE_EXPOSURE = {
    "wikidata": "passiv", "openalex": "passiv", "orcid": "passiv", "interpol_yellow": "passiv", "wayback": "passiv",
    "nominatim": "passiv", "gravatar": "passiv",
    "companies_house": "passiv", "opencorporates": "passiv", "gleif": "passiv", "wikidata_rel": "passiv", "crtsh": "passiv",
    "rdap": "passiv", "opensanctions": "passiv",
    "lokal_opensanctions": "lokal", "lokal_icij": "lokal", "lokal_eigene_liste": "lokal",
    "github": "plattform", "gitlab": "plattform", "bluesky": "plattform", "mastodon": "plattform", "username_presence": "plattform",
}

#: Exposition manueller Recherchelinks (nach Gruppe bzw. Schlüsselwort im Linktext)
LINK_EXPOSURE_RULES: list[tuple[str, str, str]] = [
    (r"LinkedIn|XING", "sichtbar", "Profilbesuche sind für die Person sichtbar, wenn Sie eingeloggt sind – nur ausgeloggt bzw. im Recherche-Browser öffnen."),
    (r"Facebook", "sichtbar", "Erfordert meist Login – niemals mit persönlichem Konto suchen."),
    (r"Instagram @|TikTok @|X @|Snapchat", "plattform", "Direkter Profilaufruf; ohne Login öffnen, Plattform protokolliert die Anfrage."),
    (r"Telefonbuch|Örtliche|North Data|Handelsregister", "passiv", ""),
    (r"Datenleck|HIBP", "passiv", "Nur mit Einwilligung bzw. Rechtsgrundlage nutzen."),
    (r"Google Lens|Bing Visual|Yandex|TinEye", "plattform", "Hochgeladene Bilder verbleiben beim Anbieter – keine Fotos von Quellen/Hinweisgebenden hochladen."),
]


def link_exposure(label: str, group: str) -> tuple[str, str]:
    for pattern, level, hint in LINK_EXPOSURE_RULES:
        if re.search(pattern, label):
            return level, hint
    if group in {"Suchmaschinen", "Vermisstenfälle", "Verzeichnisse & Register"}:
        return "passiv", ""
    return "plattform", ""


# --------------------------------------------------------------------------- Stufen

@dataclass(frozen=True)
class Level:
    key: int
    name: str
    summary: str
    require_egress: bool          # automatische Abfragen nur über ein Egress-Profil ≠ direkt
    max_exposure: int             # höchste erlaubte Exposition für automatische Quellen
    max_link_exposure: int        # höchste Exposition für angezeigte Recherchelinks
    auto_geocode: bool            # Orte automatisch an OpenStreetMap senden
    map_tiles: bool               # Kartenkacheln standardmäßig laden (Browser fragt OSM-Server an)
    force_restricted: bool        # Fall automatisch vertraulich
    codename: bool                # Deckname statt Klarname in Listen/Titel
    briefing: bool                # Briefing-Bestätigung je Person vor der Arbeit
    export_roles: tuple[str, ...] # Rollen im Fall, die exportieren dürfen
    neutral_user_agent: bool      # keine Produktkennung im User-Agent


LEVELS: dict[int, Level] = {
    1: Level(1, "Standard", "Unkritische Recherchen, z. B. öffentliche Personen oder Vermisstensuche mit Einverständnis der Angehörigen.",
             False, 3, 3, True, True, False, False, False, ("bearbeiter", "pruefer", "leser", "leitung"), False),
    2: Level(2, "Erhöht", "Recherchen, bei denen die Zielperson nichts bemerken soll. Abfragen nur über einen Anonymisierungs-Ausgang, Deckname, Briefing.",
             True, 1, 2, True, False, False, True, True, ("bearbeiter", "pruefer", "leitung"), True),
    3: Level(3, "Streng", "Gefährdete Quellen oder wehrhafte Zielpersonen. Nur passive und Plattform-Abfragen über Anonymisierung, keine sichtbaren Zugriffe, "
             "keine automatische Verortung, Fall vertraulich, Export nur durch Verantwortliche/Prüfung.",
             True, 1, 1, False, False, True, True, True, ("bearbeiter", "pruefer"), True),
}


def level(key: int | None) -> Level:
    return LEVELS.get(int(key or 1), LEVELS[1])


def level_dict(lv: Level) -> dict[str, Any]:
    return {"key": lv.key, "name": lv.name, "summary": lv.summary, "rules": rules_text(lv), **{
        k: getattr(lv, k) for k in ("require_egress", "max_exposure", "max_link_exposure", "auto_geocode", "map_tiles",
                                    "force_restricted", "codename", "briefing", "neutral_user_agent")},
        "export_roles": list(lv.export_roles)}


def rules_text(lv: Level) -> list[str]:
    exp = [v["label"] for v in EXPOSURE.values() if v["rank"] <= lv.max_exposure]
    out = [
        "Automatische Abfragen " + ("nur über einen Anonymisierungs-Ausgang (kein Direktzugriff; bei Störung wird blockiert)" if lv.require_egress else "über den Standard-Netzausgang"),
        "Erlaubte automatische Quellen: " + ", ".join(exp),
        "Recherchelinks bis Exposition „" + [v["label"] for v in EXPOSURE.values() if v["rank"] == lv.max_link_exposure][0] + "“",
        "Orte werden " + ("automatisch" if lv.auto_geocode else "nicht automatisch") + " an OpenStreetMap übermittelt",
        "Kartenhintergrund " + ("wird geladen" if lv.map_tiles else "nur auf ausdrücklichen Klick (OSM sieht sonst den Kartenausschnitt)"),
    ]
    if lv.force_restricted:
        out.append("Fall ist zwingend vertraulich (nur Fallteam)")
    if lv.codename:
        out.append("Listen und Browsertitel zeigen nur den Decknamen")
    if lv.briefing:
        out.append("Jede Person bestätigt vor der Arbeit das OPSEC-Briefing")
    out.append("Export durch: " + ", ".join({"bearbeiter": "Bearbeitung", "pruefer": "Prüfung", "leser": "Lesende", "leitung": "Teamleitung"}[r] for r in lv.export_roles))
    if lv.neutral_user_agent:
        out.append("Abfragen ohne Produktkennung (neutraler User-Agent)")
    return out


BRIEFING: dict[int, list[str]] = {
    2: [
        "Ich arbeite in einer getrennten Recherche-Umgebung (eigener Browser-Profil/VM), nicht im privaten oder Redaktions-Hauptbrowser.",
        "Ich nutze keine persönlichen Konten (Social Media, E-Mail, Cloud) für diese Recherche und bin auf Plattformen ausgeloggt.",
        "Ich nehme keinen Kontakt zur Zielperson oder ihrem Umfeld auf und interagiere nicht (keine Likes, Follows, Anfragen).",
        "Ich öffne Links der Kategorie „Sichtbar“ nur, wenn es unvermeidlich ist, und dokumentiere es.",
        "Ich bespreche den Fall nur mit dem Fallteam und verwende in Kommunikation den Decknamen.",
    ],
    3: [
        "Ich arbeite ausschließlich in einer isolierten Recherche-Umgebung mit eigenem, anonymisiertem Netzzugang.",
        "Ich nutze keine persönlichen oder dienstlich zuordenbaren Konten und lade keine Dateien von Quellen ungeprüft hoch.",
        "Ich nehme keinen Kontakt zur Zielperson oder ihrem Umfeld auf und rufe keine von ihr kontrollierten Webseiten direkt auf.",
        "Ich speichere keine Falldaten außerhalb von EagleEye (keine Notizen-Apps, Messenger, private Geräte).",
        "Ich kenne den Notfallweg: Bei Anzeichen einer Enttarnung sofort Arbeit einstellen, Teamleitung/Verantwortliche informieren.",
        "Exporte verlasse ich nur verschlüsselt und nur an das Fallteam; jede Exportdatei trägt eine Kennung.",
    ],
}

CODENAME_WORDS = ["ADLER", "FALKE", "KOMPASS", "LEUCHTTURM", "NORDSTERN", "PELIKAN", "SEXTANT", "KRANICH", "BUSSARD",
                  "MERIDIAN", "SPERBER", "KORMORAN", "ATLAS", "POLARIS", "ORION", "MILAN", "HABICHT", "REIHER"]


def new_codename() -> str:
    return f"{secrets.choice(CODENAME_WORDS)}-{secrets.randbelow(900) + 100}"


NEUTRAL_UA = "Mozilla/5.0"


# --------------------------------------------------------------------------- Egress-Profile

class OpsecBlocked(Exception):
    """Eine OPSEC-Regel verhindert die Aktion."""


@dataclass
class EgressProfile:
    id: str
    name: str
    kind: str            # "direkt" | "proxy"
    proxy_url: str = ""
    user_agent: str = ""
    notes: str = ""

    def as_dict(self, reveal: bool = False) -> dict[str, Any]:
        url = self.proxy_url if reveal else re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:***@", self.proxy_url)
        return {"id": self.id, "name": self.name, "kind": self.kind, "proxy_url": url, "user_agent": self.user_agent, "notes": self.notes}


DIRECT = EgressProfile("direkt", "Direkt (Standard-Netz)", "direkt", notes="Abfragen mit der normalen IP-Adresse dieses Servers.")


def validate_profile(data: dict[str, Any]) -> EgressProfile:
    name = (data.get("name") or "").strip()
    kind = data.get("kind") or "proxy"
    url = (data.get("proxy_url") or "").strip()
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    if kind != "proxy":
        raise ValueError("Nur Proxy-Profile können angelegt werden (Direkt ist fest vorhanden).")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or not parts.port:
        raise ValueError("Proxy-Adresse bitte als http://host:port angeben (für Tor: HTTPTunnelPort, z. B. http://tor:9080).")
    ua = (data.get("user_agent") or "").strip()[:200]
    return EgressProfile(data.get("id") or "p-" + secrets.token_hex(4), name, "proxy", url, ua, (data.get("notes") or "").strip()[:500])


class _StrictProxyHandler(urllib.request.ProxyHandler):
    """Proxy ohne Ausnahmen: no_proxy-Listen des Systems werden ignoriert (sonst Direktzugriff = Leck)."""

    def proxy_open(self, req, proxy, type):  # noqa: A002 - Signatur von urllib
        orig_type = req.type
        proxy_type, user, password, hostport = urllib.request._parse_proxy(proxy)  # noqa: SLF001
        if proxy_type is None:
            proxy_type = orig_type
        if user and password:
            import base64
            creds = base64.b64encode(f"{urllib.request.unquote(user)}:{urllib.request.unquote(password)}".encode()).decode()
            req.add_header("Proxy-authorization", "Basic " + creds)
        req.set_proxy(urllib.request.unquote(hostport), proxy_type)
        if orig_type == proxy_type or orig_type == "https":
            return None
        return self.parent.open(req, timeout=req.timeout)


def is_internal_host(host: str, resolve: bool) -> bool:
    """True, wenn ein Ziel auf interne Netze zeigt (localhost, private/link-local Adressen, Cloud-Metadaten)."""
    import ipaddress

    host = (host or "").lower().strip("[]")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost", ".lan")):
        return True
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve:
            return False
        try:
            ips = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, None)]
        except OSError:
            return False
    return any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified for ip in ips)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Folgt Weiterleitungen nur zu öffentlichen http(s)-Zielen."""

    def __init__(self, resolve: bool):
        super().__init__()
        self.resolve = resolve

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        parts = urlsplit(newurl)
        if parts.scheme not in {"http", "https"} or is_internal_host(parts.hostname or "", self.resolve):
            raise urllib.error.HTTPError(newurl, 403, "Weiterleitung auf internes Ziel blockiert", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener(profile: EgressProfile) -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    if profile.kind == "proxy":
        handler = _StrictProxyHandler({"http": profile.proxy_url, "https": profile.proxy_url})
        return urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=ctx), _SafeRedirectHandler(resolve=False))
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _SafeRedirectHandler(resolve=True))


def check_proxy_reachable(profile: EgressProfile, timeout: float = 4.0) -> None:
    """Fail closed: ist der Proxy nicht erreichbar, wird gar nicht erst abgefragt."""
    if profile.kind != "proxy":
        return
    parts = urlsplit(profile.proxy_url)
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=timeout):
            pass
    except OSError as exc:
        raise OpsecBlocked(f"Anonymisierungs-Ausgang „{profile.name}“ ist nicht erreichbar ({exc.strerror or exc}). "
                           "Aus OPSEC-Gründen wird nicht direkt abgefragt.") from exc


def egress_test(profile: EgressProfile, timeout: float = 15.0) -> dict[str, Any]:
    """Ermittelt die öffentliche Ausgangs-IP über das Profil (Abgleich mit Direktzugriff im Aufrufer)."""
    check_proxy_reachable(profile)
    opener = build_opener(profile)
    req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": profile.user_agent or NEUTRAL_UA})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return {"ok": True, "ip": json.loads(resp.read(2000).decode()).get("ip", "?")}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(getattr(exc, "reason", exc))}


Recorder = Callable[[dict[str, Any]], None]
