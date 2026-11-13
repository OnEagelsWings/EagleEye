"""Öffentliche Quellen (ohne API-Schlüssel) für Personen- und Vermisstenrecherche.

Grundsätze (übernommen aus EagleEye Build 380):
* nur öffentlich zugängliche, nicht zugangsgeschützte Endpunkte,
* jede Quelle ist explizit auf ihre Hosts begrenzt,
* Treffer sind *Kandidaten* – eine Bestätigung erfolgt immer durch Menschen.
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import quote, quote_plus, urlencode, urlsplit

USER_AGENT = "EagleEye-PersonOSINT/1.0 (lokale Recherche-Software)"


class SourceError(Exception):
    pass


@dataclass
class HttpResponse:
    status: int
    body: bytes
    url: str
    #: Antwort-Kopfzeilen, Statustext und gesendete Kopfzeilen – für die WARC-Aufzeichnung von Belegen
    headers: list[tuple[str, str]] = field(default_factory=list)
    reason: str = ""
    request_headers: list[tuple[str, str]] = field(default_factory=list)

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceError("Quelle lieferte kein gültiges JSON") from exc

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


class Http:
    """Minimaler HTTP-Client mit Host-Allowlist; in Tests austauschbar.

    Mit einem Egress-Profil laufen alle Anfragen ausschließlich über den dort hinterlegten Proxy
    (keine Ausnahmen über no_proxy, DNS-Auflösung beim Proxy).
    """

    def __init__(self, timeout: float = 12.0, profile: Any = None, user_agent: str = ""):
        from .opsec import DIRECT, build_opener

        self.timeout = timeout
        self.profile = profile or DIRECT
        self.user_agent = user_agent or USER_AGENT
        self._opener = build_opener(self.profile)

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        sent = {"User-Agent": self.user_agent, "Accept": "application/json, text/html;q=0.8", **(headers or {})}
        req = urllib.request.Request(url, headers=sent)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310 - Allowlist pro Quelle
                return HttpResponse(resp.status, resp.read(2_000_000), resp.geturl(), headers=[(str(k), str(v)) for k, v in resp.getheaders()],
                                    reason=str(getattr(resp, "reason", "") or ""), request_headers=list(sent.items()))
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, exc.read(200_000) if exc.fp else b"", url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceError(f"Quelle nicht erreichbar: {getattr(exc, 'reason', exc)}") from exc


class RecordingHttp:
    """Hüllt einen HTTP-Client ein und meldet jede Außenabfrage an das Außenkontakt-Protokoll."""

    def __init__(self, inner: Any, record: Any, source_key: str = "", egress: str = "direkt", keys: dict[str, str] | None = None):
        self.inner, self.record, self.source_key, self.egress = inner, record, source_key, egress
        self.keys = keys or {}

    def for_source(self, key: str) -> "RecordingHttp":
        return RecordingHttp(self.inner, self.record, key, self.egress, self.keys)

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        status = 0
        try:
            resp = self.inner.get(url, headers)
            status = resp.status
            return resp
        except SourceError:
            status = -1
            raise
        finally:
            parts = urlsplit(url)
            self.record({"source": self.source_key, "host": parts.hostname or "", "path": parts.path[:200],
                         "query": parts.query[:300], "status": status, "egress": self.egress})


#: in Tests abschaltbar
THROTTLE_ENABLED = True
_THROTTLE_LOCK = threading.Lock()
_LAST_CALL: dict[str, float] = {}


def api_key(http: Any, source_key: str) -> str:
    """API-Schlüssel einer Quelle (vom Fall-Client mitgeführt, nie im Klartext gespeichert)."""
    return (getattr(http, "keys", None) or {}).get(source_key, "")


@dataclass
class Source:
    key: str
    label: str
    description: str
    kinds: tuple[str, ...]
    hosts: tuple[str, ...]
    category: str
    weight: float = 1.0
    group: str = "Personen"
    runner: Callable[["Source", str, str, Http], list[dict[str, Any]]] = field(repr=False, default=None)  # type: ignore[assignment]
    #: Name des benötigten API-Schlüssels ("" = keiner); key_optional = funktioniert auch ohne (eingeschränkt)
    requires_key: bool = False
    key_optional: bool = False
    key_help: str = ""
    license: str = "Öffentliche Schnittstelle; Nutzungsbedingungen des Anbieters beachten."
    cost: str = "kostenlos"
    #: Verlässlichkeit der Quelle nach Admiralty-Code (A = amtlich/zuverlässig … F = nicht beurteilbar)
    reliability: str = "C"
    docs: str = ""
    rate_per_min: int = 30
    local: bool = False
    #: Testabfrage für den Selbsttest in der Verwaltung
    test_query: tuple[str, str] = ("name", "Angela Merkel")
    #: Arten von Kennungen, die Treffer dieser Quelle liefern können (Gegenstück zu ``kinds`` = verarbeitet).
    #: Daraus entstehen Folgesuch-Vorschläge – ausgeführt wird erst nach Freigabe (siehe pivot.py).
    produces: tuple[str, ...] = ()

    def run(self, kind: str, value: str, http: Http) -> list[dict[str, Any]]:
        if isinstance(http, RecordingHttp):
            http = http.for_source(self.key)
        if self.requires_key and not self.key_optional and not api_key(http, self.key):
            raise SourceError("API-Schlüssel fehlt – Verwaltung → Quellen & Daten")
        out = self.runner(self, kind, value, http)
        for item in out:
            host = (urlsplit(item.get("url", "")).hostname or "")
            item.setdefault("category", self.category)
            item.setdefault("names", [])
            item.setdefault("locations", [])
            item.setdefault("data", {})
            item["source"] = self.label
            item["source_key"] = self.key
            item["source_weight"] = self.weight
            item["match_kind"] = kind
            item["query"] = value
            item["host"] = host
        return out

    def get(self, http: Http, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        host = urlsplit(url).hostname or ""
        if host not in self.hosts:
            raise SourceError(f"Host {host} ist für {self.label} nicht freigegeben")
        self._throttle()
        resp = http.get(url, headers)
        if resp.status == 429:
            raise SourceError("Abfragelimit des Anbieters erreicht (HTTP 429) – später erneut versuchen")
        if resp.status in (401, 403) and self.requires_key:
            raise SourceError(f"Zugriff verweigert (HTTP {resp.status}) – API-Schlüssel prüfen")
        return resp

    def _throttle(self) -> None:
        """Einfache Drosselung je Quelle (Abstand zwischen Anfragen), schont Limits und fällt weniger auf."""
        if self.rate_per_min <= 0 or not THROTTLE_ENABLED:
            return
        gap = 60.0 / self.rate_per_min
        with _THROTTLE_LOCK:
            now = time.monotonic()
            wait = _LAST_CALL.get(self.key, 0.0) + gap - now
            _LAST_CALL[self.key] = max(now, _LAST_CALL.get(self.key, 0.0) + gap)
        if wait > 0:
            time.sleep(min(wait, 5.0))


def _clean(text: Any, limit: int = 400) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


# --------------------------------------------------------------------------- Runner

def _wikidata(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://www.wikidata.org/w/api.php?" + urlencode({
        "action": "wbsearchentities", "search": value, "language": "de", "uselang": "de",
        "type": "item", "limit": 10, "format": "json"}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for item in r.json().get("search", []):
        out.append({"title": item.get("label") or item.get("id"), "url": item.get("concepturi", ""),
                    "snippet": item.get("description", ""), "names": [item.get("label", "")],
                    "data": {"wikidata_id": item.get("id")}})
    return out


def _github(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    if kind == "username":
        r = src.get(http, f"https://api.github.com/users/{quote(value.lstrip('@'), safe='')}")
        if r.status == 404:
            return []
        if r.status != 200:
            raise SourceError(f"HTTP {r.status}")
        d = r.json()
        snippet = " · ".join(x for x in [d.get("bio"), d.get("company"), d.get("location"), d.get("blog")] if x)
        return [{"title": f"GitHub: {d.get('login')}" + (f" ({d['name']})" if d.get("name") else ""),
                 "url": d.get("html_url", ""), "snippet": _clean(snippet), "category": "Konto",
                 "names": [d.get("name") or ""], "locations": [d.get("location") or ""],
                 "data": {"plattform": "GitHub", "benutzername": d.get("login"), "erstellt": d.get("created_at"),
                          "organisation": d.get("company"), "webseite": d.get("blog"), "email": d.get("email")}}]
    r = src.get(http, "https://api.github.com/search/users?" + urlencode({"q": f'fullname:"{value}"', "per_page": 10}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    return [{"title": f"GitHub: {i.get('login')}", "url": i.get("html_url", ""), "snippet": "Profil über Namenssuche gefunden",
             "category": "Konto", "names": [value], "data": {"plattform": "GitHub", "benutzername": i.get("login")}}
            for i in r.json().get("items", [])[:10]]


def _gitlab(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://gitlab.com/api/v4/users?" + urlencode({"username": value.lstrip("@")}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    return [{"title": f"GitLab: {u.get('username')} ({u.get('name')})", "url": u.get("web_url", ""),
             "snippet": "Öffentliches GitLab-Profil", "category": "Konto", "names": [u.get("name", "")],
             "data": {"plattform": "GitLab", "benutzername": u.get("username")}} for u in r.json()[:5]]


def _bluesky(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?" + urlencode({"q": value.lstrip("@"), "limit": 10}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for a in r.json().get("actors", []):
        handle = a.get("handle", "")
        out.append({"title": f"Bluesky: {a.get('displayName') or handle} (@{handle})", "url": f"https://bsky.app/profile/{handle}",
                    "snippet": _clean(a.get("description")), "category": "Konto",
                    "names": [a.get("displayName") or ""], "data": {"plattform": "Bluesky", "benutzername": handle}})
    return out


def _mastodon(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://mastodon.social/api/v2/search?" + urlencode({"q": value, "type": "accounts", "limit": 10}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    return [{"title": f"Mastodon: {a.get('display_name') or a.get('acct')} (@{a.get('acct')})", "url": a.get("url", ""),
             "snippet": _clean(a.get("note")), "category": "Konto", "names": [a.get("display_name") or ""],
             "data": {"plattform": "Mastodon", "benutzername": a.get("acct"), "erstellt": a.get("created_at")}}
            for a in r.json().get("accounts", [])]


def _gravatar(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    digest = hashlib.sha256(value.strip().casefold().encode()).hexdigest()
    r = src.get(http, f"https://api.gravatar.com/v3/profiles/{digest}")
    if r.status == 404:
        return []
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    d = r.json()
    accounts = [a.get("url", "") for a in d.get("verified_accounts", []) if a.get("url")]
    return [{"title": f"Gravatar-Profil: {d.get('display_name') or 'ohne Namen'}", "url": d.get("profile_url", ""),
             "snippet": _clean(" · ".join(x for x in [d.get("description"), d.get("location"), d.get("job_title"), d.get("company")] if x)),
             "category": "Konto", "names": [d.get("display_name") or ""], "locations": [d.get("location") or ""],
             "data": {"plattform": "Gravatar", "verknuepfte_konten": accounts, "avatar": d.get("avatar_url")}}]


def _openalex(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://api.openalex.org/authors?" + urlencode({"search": value, "per-page": 8}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for a in r.json().get("results", []):
        insts = [i.get("display_name", "") for i in (a.get("last_known_institutions") or [])]
        out.append({"title": f"Wissenschaft: {a.get('display_name')}", "url": a.get("id", ""),
                    "snippet": _clean(f"{a.get('works_count', 0)} Publikationen · " + ", ".join(insts)),
                    "category": "Beruf/Bildung", "names": [a.get("display_name", "")],
                    "data": {"institutionen": insts, "orcid": a.get("orcid")}})
    return out


def _orcid(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://pub.orcid.org/v3.0/expanded-search/?" + urlencode({"q": value, "rows": 8}), {"Accept": "application/json"})
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for p in r.json().get("expanded-result") or []:
        name = f"{p.get('given-names', '')} {p.get('family-names', '')}".strip()
        oid = p.get("orcid-id", "")
        out.append({"title": f"ORCID: {name}", "url": f"https://orcid.org/{oid}",
                    "snippet": _clean(", ".join(p.get("institution-name") or [])), "category": "Beruf/Bildung",
                    "names": [name], "data": {"orcid": oid, "institutionen": p.get("institution-name") or []}})
    return out


def _interpol_yellow(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    parts = value.split()
    params = {"resultPerPage": 20}
    if len(parts) >= 2:
        params.update({"forename": " ".join(parts[:-1]), "name": parts[-1]})
    else:
        params["name"] = value
    r = src.get(http, "https://ws-public.interpol.int/notices/v1/yellow?" + urlencode(params))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for n in r.json().get("_embedded", {}).get("notices", []):
        name = f"{n.get('forename', '')} {n.get('name', '')}".strip().title()
        out.append({"title": f"INTERPOL Gelbe Ausschreibung (vermisst): {name}",
                    "url": f"https://www.interpol.int/How-we-work/Notices/View-Yellow-Notices#{n.get('entity_id', '').replace('/', '-')}",
                    "snippet": f"Geburtsdatum: {n.get('date_of_birth') or 'unbekannt'} · Nationalität: {', '.join(n.get('nationalities') or [])}",
                    "category": "Vermisstenregister", "names": [name],
                    "data": {"notice_id": n.get("entity_id"), "geburtsdatum": n.get("date_of_birth")}})
    return out


def _wayback(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    target = re.sub(r"^https?://", "", value.strip())
    r = src.get(http, "https://web.archive.org/cdx/search/cdx?" + urlencode({
        "url": target, "output": "json", "limit": 15, "fl": "timestamp,original,statuscode", "collapse": "digest"}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    rows = r.json() or []
    out = []
    for ts, original, code in rows[1:]:
        out.append({"title": f"Archivkopie {ts[:4]}-{ts[4:6]}-{ts[6:8]}: {original}", "url": f"https://web.archive.org/web/{ts}/{original}",
                    "snippet": f"HTTP-Status zum Zeitpunkt der Archivierung: {code}", "category": "Archiv",
                    "data": {"zeitstempel": ts}})
    return out


def _nominatim(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    r = src.get(http, "https://nominatim.openstreetmap.org/search?" + urlencode({"q": value, "format": "json", "limit": 5, "accept-language": "de"}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    return [{"title": f"Ort: {p.get('display_name')}", "url": f"https://www.openstreetmap.org/{p.get('osm_type')}/{p.get('osm_id')}",
             "snippet": f"Typ: {p.get('type')} · Koordinaten {p.get('lat')}, {p.get('lon')}", "category": "Ort",
             "locations": [p.get("display_name", "")], "data": {"lat": float(p.get("lat")), "lon": float(p.get("lon"))}}
            for p in r.json()]


# Plattform-Prüfung für Benutzernamen: nur Endpunkte mit eindeutigem "existiert/existiert nicht"-Verhalten.
USERNAME_PLATFORMS: list[dict[str, Any]] = [
    {"name": "GitHub", "check": "https://api.github.com/users/{u}", "profile": "https://github.com/{u}", "mode": "status"},
    {"name": "GitLab", "check": "https://gitlab.com/api/v4/users?username={u}", "profile": "https://gitlab.com/{u}", "mode": "nonempty"},
    {"name": "Codeberg", "check": "https://codeberg.org/api/v1/users/{u}", "profile": "https://codeberg.org/{u}", "mode": "status"},
    {"name": "Reddit", "check": "https://www.reddit.com/user/{u}/about.json", "profile": "https://www.reddit.com/user/{u}", "mode": "status"},
    {"name": "Keybase", "check": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={u}", "profile": "https://keybase.io/{u}", "mode": "keybase"},
    {"name": "Hacker News", "check": "https://hacker-news.firebaseio.com/v0/user/{u}.json", "profile": "https://news.ycombinator.com/user?id={u}", "mode": "notnull"},
    {"name": "Chess.com", "check": "https://api.chess.com/pub/player/{u}", "profile": "https://www.chess.com/member/{u}", "mode": "status"},
    {"name": "Lichess", "check": "https://lichess.org/api/user/{u}", "profile": "https://lichess.org/@/{u}", "mode": "status"},
    {"name": "Docker Hub", "check": "https://hub.docker.com/v2/users/{u}", "profile": "https://hub.docker.com/u/{u}", "mode": "status"},
    {"name": "dev.to", "check": "https://dev.to/api/users/by_username?url={u}", "profile": "https://dev.to/{u}", "mode": "status"},
    {"name": "PyPI", "check": "https://pypi.org/user/{u}/", "profile": "https://pypi.org/user/{u}/", "mode": "status"},
    {"name": "Telegram", "check": "https://t.me/{u}", "profile": "https://t.me/{u}", "mode": "telegram"},
    {"name": "Bluesky", "check": "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={u}.bsky.social", "profile": "https://bsky.app/profile/{u}.bsky.social", "mode": "status"},
]
USERNAME_HOSTS = tuple(sorted({urlsplit(p["check"]).hostname for p in USERNAME_PLATFORMS}))  # type: ignore[misc]


def _username_presence(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor

    user = value.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._-]{2,40}", user):
        raise SourceError("Ungültiger Benutzername (erlaubt: Buchstaben, Ziffern, . _ -)")

    def probe(p: dict) -> dict | None:
        try:
            r = src.get(http, p["check"].format(u=quote(user, safe="")))
        except SourceError:
            return None
        exists = False
        if p["mode"] == "status":
            exists = r.status == 200
        elif p["mode"] == "nonempty":
            exists = r.status == 200 and bool(r.body.strip() not in (b"", b"[]"))
        elif p["mode"] == "notnull":
            exists = r.status == 200 and r.body.strip() not in (b"null", b"")
        elif p["mode"] == "keybase":
            exists = r.status == 200 and b'"them":[{' in r.body.replace(b" ", b"")
        elif p["mode"] == "telegram":
            exists = r.status == 200 and b"tgme_page_title" in r.body
        if not exists:
            return None
        return {"title": f"{p['name']}: Konto „{user}“ vorhanden", "url": p["profile"].format(u=user),
                "snippet": f"Ein öffentliches Konto mit dem Namen „{user}“ existiert auf {p['name']}.",
                "category": "Konto", "data": {"plattform": p["name"], "benutzername": user}}

    with ThreadPoolExecutor(max_workers=6) as pool:
        return [r for r in pool.map(probe, USERNAME_PLATFORMS) if r]


SOURCES: list[Source] = [
    Source("username_presence", "Benutzernamen-Check (13 Plattformen)", "Prüft, auf welchen Plattformen ein Benutzername existiert.",
           ("username",), USERNAME_HOSTS, "Konto", 1.0, "Online-Präsenz", _username_presence, test_query=("username", "github")),
    Source("github", "GitHub", "Öffentliche Profile (Benutzername oder vollständiger Name).", ("username", "name"),
           ("api.github.com",), "Konto", 1.0, "Online-Präsenz", _github),
    Source("gitlab", "GitLab", "Öffentliche Profile nach Benutzername.", ("username",), ("gitlab.com",), "Konto", 1.0, "Online-Präsenz", _gitlab, test_query=("username", "gitlab-bot")),
    Source("bluesky", "Bluesky", "Öffentliche Personensuche im Bluesky-Netzwerk.", ("name", "username"),
           ("public.api.bsky.app",), "Konto", 0.9, "Online-Präsenz", _bluesky),
    Source("mastodon", "Mastodon (mastodon.social)", "Kontensuche im Fediverse.", ("name", "username"),
           ("mastodon.social",), "Konto", 0.9, "Online-Präsenz", _mastodon),
    Source("gravatar", "Gravatar", "Öffentliches Profil hinter einer E-Mail-Adresse.", ("email",),
           ("api.gravatar.com",), "Konto", 1.0, "Online-Präsenz", _gravatar, test_query=("email", "test@example.com")),
    Source("wikidata", "Wikidata", "Personen des öffentlichen Lebens.", ("name",), ("www.wikidata.org",),
           "Öffentliche Person", 0.8, "Register & Wissen", _wikidata),
    Source("openalex", "OpenAlex", "Autorinnen/Autoren wissenschaftlicher Arbeiten mit Institution.", ("name",),
           ("api.openalex.org",), "Beruf/Bildung", 0.8, "Register & Wissen", _openalex),
    Source("orcid", "ORCID", "Forschende mit Institution.", ("name",), ("pub.orcid.org",), "Beruf/Bildung", 0.8, "Register & Wissen", _orcid),
    Source("interpol_yellow", "INTERPOL – Vermisste (Yellow Notices)", "Öffentliche internationale Vermisstenausschreibungen.",
           ("name",), ("ws-public.interpol.int",), "Vermisstenregister", 1.1, "Vermisstenfälle", _interpol_yellow),
    Source("wayback", "Internet Archive (Wayback)", "Historische Kopien von Webseiten/Profil-URLs.", ("url",),
           ("web.archive.org",), "Archiv", 1.0, "Register & Wissen", _wayback, test_query=("url", "https://example.com")),
    Source("nominatim", "OpenStreetMap Nominatim", "Ortsauflösung (Koordinaten) für Orte und Adressen.", ("location",),
           ("nominatim.openstreetmap.org",), "Ort", 0.6, "Orte", _nominatim, test_query=("location", "Berlin")),
]
SOURCE_MAP = {s.key: s for s in SOURCES}


def geocode(text: str, http: Http | None = None) -> tuple[float, float] | None:
    try:
        res = SOURCE_MAP["nominatim"].run("location", text, http or Http(timeout=8))
    except SourceError:
        return None
    if res:
        return res[0]["data"]["lat"], res[0]["data"]["lon"]
    return None


# --------------------------------------------------------------------------- Recherchelinks

def research_links(subject: dict[str, Any], identifiers: Iterable[dict[str, Any]], missing: bool = False) -> list[dict[str, str]]:
    """Erzeugt manuelle Recherche-Links (werden NICHT automatisch abgerufen)."""
    idents = list(identifiers)
    names = [i["value"] for i in idents if i["kind"] in ("name", "alias")] or [subject.get("label", "")]
    name = names[0]
    locs = [i["value"].split(",")[0] for i in idents if i["kind"] == "location"]
    users = [i["value"].lstrip("@") for i in idents if i["kind"] == "username"]
    emails = [i["value"] for i in idents if i["kind"] == "email"]
    phones = [i["value"] for i in idents if i["kind"] == "phone"]
    q = f'"{name}"'
    ql = q + (f" {locs[0]}" if locs else "")
    links: list[dict[str, str]] = []

    def add(group: str, label: str, url: str, hint: str = "") -> None:
        links.append({"group": group, "label": label, "url": url, "hint": hint})

    g = "https://www.google.com/search?q="
    add("Suchmaschinen", "Google: Name (+ Ort)", g + quote_plus(ql))
    add("Suchmaschinen", "Bing: Name (+ Ort)", "https://www.bing.com/search?q=" + quote_plus(ql))
    add("Suchmaschinen", "DuckDuckGo: Name", "https://duckduckgo.com/?q=" + quote_plus(ql))
    add("Suchmaschinen", "Google News: Name", "https://news.google.com/search?hl=de&q=" + quote_plus(q))
    add("Suchmaschinen", "Dokumente (PDF/DOC) mit Name", g + quote_plus(q + " (filetype:pdf OR filetype:doc OR filetype:docx)"))
    add("Soziale Netzwerke", "LinkedIn-Profile", g + quote_plus(q + " site:linkedin.com/in"))
    add("Soziale Netzwerke", "XING-Profile", g + quote_plus(q + " site:xing.com/profile"))
    add("Soziale Netzwerke", "Facebook-Suche", "https://www.facebook.com/search/people/?q=" + quote_plus(name))
    add("Soziale Netzwerke", "Instagram (über Google)", g + quote_plus(q + " site:instagram.com"))
    add("Soziale Netzwerke", "TikTok (über Google)", g + quote_plus(q + " site:tiktok.com"))
    add("Soziale Netzwerke", "X/Twitter-Suche", "https://x.com/search?f=user&q=" + quote_plus(name))
    add("Soziale Netzwerke", "YouTube-Suche", "https://www.youtube.com/results?search_query=" + quote_plus(name))
    for u in users[:3]:
        add("Benutzernamen", f"„{u}“ im Web", g + quote_plus(f'"{u}"'))
        add("Benutzernamen", f"Instagram @{u}", f"https://www.instagram.com/{quote(u)}/")
        add("Benutzernamen", f"TikTok @{u}", f"https://www.tiktok.com/@{quote(u)}")
        add("Benutzernamen", f"X @{u}", f"https://x.com/{quote(u)}")
        add("Benutzernamen", f"Snapchat {u}", f"https://www.snapchat.com/add/{quote(u)}")
    for e in emails[:3]:
        add("E-Mail & Telefon", f"E-Mail „{e}“ im Web", g + quote_plus(f'"{e}"'))
        add("E-Mail & Telefon", f"Datenleck-Prüfung (HIBP) {e}", "https://haveibeenpwned.com/", "Nur mit Einwilligung bzw. Rechtsgrundlage nutzen")
    for p in phones[:3]:
        add("E-Mail & Telefon", f"Nummer „{p}“ im Web", g + quote_plus(f'"{p}"'))
        add("E-Mail & Telefon", f"Rückwärtssuche Das Örtliche {p}", "https://www.dasoertliche.de/rueckwaertssuche/?ph=" + quote_plus(p))
    parts = name.split()
    if parts:
        add("Verzeichnisse & Register", "Das Telefonbuch", "https://www.dastelefonbuch.de/Personen/" + quote(name) + ("/" + quote(locs[0]) if locs else ""))
        add("Verzeichnisse & Register", "North Data (Firmenbeteiligungen)", "https://www.northdata.de/" + quote(name))
        add("Verzeichnisse & Register", "Handelsregister (Personensuche)", "https://www.handelsregister.de/rp_web/normalesuche.xhtml")
        add("Verzeichnisse & Register", "Traueranzeigen / Todesanzeigen", g + quote_plus(q + " (traueranzeige OR todesanzeige OR trauer.de)"))
    if missing:
        add("Vermisstenfälle", "BKA-Fahndung (Vermisste)", "https://www.bka.de/DE/IhreSicherheit/Fahndungen/Personen/personen_node.html")
        add("Vermisstenfälle", "Polizei-Fahndungsportale der Länder", g + quote_plus(f"{q} vermisst polizei"))
        add("Vermisstenfälle", "Presseportal Blaulicht", "https://www.presseportal.de/blaulicht/suche.htx?q=" + quote_plus(name))
        add("Vermisstenfälle", "INTERPOL Yellow Notices", "https://www.interpol.int/How-we-work/Notices/View-Yellow-Notices")
        add("Vermisstenfälle", "Initiative Vermisste Kinder", "https://www.vermisste-kinder.de/")
        add("Vermisstenfälle", "NamUs (USA)", "https://www.namus.nij.ojp.gov/")
        add("Vermisstenfälle", "Missing People (UK)", "https://www.missingpeople.org.uk/appeal-search")
        add("Vermisstenfälle", "Unbekannte Tote (BKA)", "https://www.bka.de/DE/IhreSicherheit/Fahndungen/UnbekannteTote/unbekannteTote_node.html", "Behutsam einsetzen – nur bei entsprechender Lage")
        if locs:
            add("Vermisstenfälle", f"Lokale Nachrichten {locs[0]}", "https://news.google.com/search?hl=de&q=" + quote_plus(f"{q} {locs[0]}"))
    add("Bildersuche", "Google Lens (Foto hochladen)", "https://lens.google.com/", "Foto der Person zur Rückwärtssuche hochladen")
    add("Bildersuche", "Bing Visual Search", "https://www.bing.com/visualsearch")
    add("Bildersuche", "Yandex Bilder", "https://yandex.com/images/")
    add("Bildersuche", "TinEye", "https://tineye.com/")
    from .opsec import EXPOSURE, link_exposure

    for link in links:
        level, hint = link_exposure(link["label"], link["group"])
        link["exposure"] = level
        link["exposure_label"] = EXPOSURE[level]["label"]
        link["exposure_rank"] = EXPOSURE[level]["rank"]
        if hint:
            link["hint"] = (link.get("hint", "") + " " + hint).strip()
    return links

# Verlässlichkeit der Basisquellen nach Admiralty-Code (A = amtlich … F = nicht beurteilbar)
for _src, _rel in {"interpol_yellow": "A", "wayback": "B", "openalex": "B", "orcid": "B", "wikidata": "C", "nominatim": "B",
                   "gravatar": "C", "github": "C", "gitlab": "C", "bluesky": "C", "mastodon": "C", "username_presence": "D"}.items():
    SOURCE_MAP[_src].reliability = _rel
