"""Tiefenrecherche: automatisch alle sinnvollen Suchanfragen erzeugen, abfragen und starken Spuren folgen.

Was automatisch entsteht
------------------------
* **Namensvarianten** – Reihenfolge, Umlaut-Schreibweisen (ä/ae, ß/ss), ohne Zweitnamen, Initiale, Kurz- und Rufnamen,
  Transliteration (Kyrillisch, Arabisch, Hebräisch), bekannte Aliasse.
* **Benutzernamen-Kandidaten** aus Vor- und Nachname (vorname.nachname, vnachname, nachname + Geburtsjahr …) – nur, wenn
  Sie das Erraten einschalten, denn jede Prüfung fragt Plattformen ab.
* **Telefon-Schreibweisen** (+49 …, 0049 …, 0 …), Domains aus E-Mail-Adressen.
* **Dorks** – Suchmaschinen-Abfragen nach Ziel geordnet (Profile, Dokumente, Lebenslauf, Presse, Foren, Bilder,
  Register, Kontakt, Benutzernamen, Archiv; bei Vermisstenfällen zusätzlich Polizei, Suchaufrufe, „zuletzt gesehen“).

Wie automatisch abgefragt wird
------------------------------
Runde 1 fragt jede passende Quelle mit jeder Variante ab. Danach werden **starke neue Spuren** (Kennungen aus Treffern
mit hoher Übereinstimmung) automatisch weiterverfolgt – Runde für Runde bis zur gewählten Tiefe (höchstens 3) und nur
im gewählten Abfragebudget. OPSEC-Stufe, Ausgang (Proxy/Tor) und Netzschalter gelten unverändert. Alles bleibt
**Kandidat**: Bestätigen oder verwerfen tun Sie.

Dorks laufen automatisch nur über eine **eigene SearXNG-Instanz** (selbst betriebene Meta-Suchmaschine mit
JSON-Schnittstelle). Google, Bing & Co. verbieten automatisierte Abfragen und sperren sie; ohne SearXNG erscheinen die
Dorks deshalb als abhakbare Liste mit Ein-Klick-Links.
"""
from __future__ import annotations

import ipaddress
import json
import re
import secrets
import threading
import time
import unicodedata
from typing import Any
from urllib.parse import quote_plus, urlencode, urlsplit

from .matching import normalize
from .namematch import transliterate

MAX_DEPTH = 3
MAX_BUDGET = 600
CHUNK = 40
FOLLOW_MIN_SCORE = 70
UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})

#: Kurz- und Rufnamen (beidseitig verwendet); bewusst überschaubar, damit keine Flut fremder Treffer entsteht
NICKNAMES: dict[str, tuple[str, ...]] = {
    "alexander": ("alex", "sascha"), "alexandra": ("alex", "sandra"), "andreas": ("andi",), "katharina": ("kathi", "katja", "kati"),
    "christian": ("chris",), "christina": ("chris", "tina"), "christine": ("tine",), "daniel": ("dani",), "elisabeth": ("lisa", "elli", "liesel"),
    "johannes": ("hannes", "jo"), "johanna": ("hanna", "jo"), "josef": ("sepp", "jupp"), "joseph": ("joe",), "margarete": ("grete", "margit"),
    "michael": ("micha", "mike"), "nikolaus": ("niko", "klaus"), "stefanie": ("steffi",), "stephanie": ("steffi",), "thomas": ("tom",),
    "tobias": ("tobi",), "wolfgang": ("wolf",), "magdalena": ("lena", "magda"), "helena": ("lena",), "susanne": ("susi", "sanne"),
    "william": ("bill", "will"), "robert": ("rob", "bob"), "richard": ("rick", "dick"), "elizabeth": ("liz", "beth"), "jennifer": ("jenny",),
    "maximilian": ("max",), "benjamin": ("ben",), "dominik": ("dome",), "sebastian": ("basti",), "florian": ("flo",), "matthias": ("matze",),
    "franziska": ("franzi",), "anna-lena": ("lena",), "marie-luise": ("malu",), "aleksandr": ("sasha",), "mohammed": ("mohamed", "muhammad"),
}
#: Gängige aktuelle Browserkennungen – je Suche wechselnd (Tarnung gegen Verknüpfung der Abfragen)
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
)
ENGINES = {
    "google": ("Google", "https://www.google.com/search?q="), "bing": ("Bing", "https://www.bing.com/search?q="),
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/?q="), "startpage": ("Startpage", "https://www.startpage.com/do/search?query="),
    "yandex": ("Yandex", "https://yandex.com/search/?text="),
}
SOCIAL = ("linkedin.com/in", "xing.com/profile", "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com", "youtube.com",
          "reddit.com", "pinterest.com", "vk.com", "t.me", "threads.net", "bsky.app", "mastodon.social", "github.com", "medium.com")


# --------------------------------------------------------------------------- Varianten
def _fold(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.translate(UMLAUT)) if not unicodedata.combining(ch))


def _split_name(name: str) -> tuple[list[str], str]:
    name = " ".join(str(name or "").split())
    if "," in name:  # „Nachname, Vorname“
        last, first = [x.strip() for x in name.split(",", 1)]
        name = f"{first} {last}"
    parts = name.split()
    return (parts[:-1], parts[-1]) if len(parts) >= 2 else (parts, "")


def name_variants(names: list[str], limit: int = 12) -> list[dict[str, str]]:
    """Schreibweisen eines Namens, jeweils mit Begründung; die erste Form bleibt die Ausgangsform."""
    out: dict[str, dict[str, str]] = {}

    def add(value: str, why: str) -> None:
        value = " ".join(value.split())
        key = value.casefold()
        if len(value) >= 3 and key not in out:
            out[key] = {"value": value, "why": why}

    for raw in names:
        firsts, last = _split_name(raw)
        full = " ".join(firsts + [last]).strip()
        add(full, "Ausgangsform")
        if not last:
            continue
        first = firsts[0] if firsts else ""
        add(f"{last}, {' '.join(firsts)}", "Reihenfolge wie in Registern")
        if len(firsts) > 1:
            add(f"{first} {last}", "ohne Zweitnamen")
            add(f"{firsts[-1]} {last}", "Rufname kann der zweite Vorname sein")
        if _fold(full) != full:
            add(_fold(full), "Umlaute/ß umgeschrieben (ä→ae, ß→ss)")
        if "-" in last:
            for piece in last.split("-"):
                add(f"{first} {piece}", "Teil eines Doppelnamens")
        if first:
            add(f"{first[0]}. {last}", "Initiale")
            for nick in NICKNAMES.get(first.casefold(), ()):
                add(f"{nick.title()} {last}", "Kurz-/Rufname")
        latin = transliterate(full)
        if latin and latin.casefold() != full.casefold():
            add(latin.title(), "Umschrift in lateinische Schrift")
    return list(out.values())[:limit]


def username_candidates(names: list[str], birth_year: str = "", limit: int = 10) -> list[str]:
    """Häufige Muster für Benutzernamen aus Vor- und Nachname (nur Kandidaten – gleicher Name ≠ gleiche Person)."""
    out: list[str] = []
    for raw in names[:2]:
        firsts, last = _split_name(raw)
        if not firsts or not last:
            continue
        f, l = re.sub(r"[^a-z0-9]", "", _fold(firsts[0]).casefold()), re.sub(r"[^a-z0-9]", "", _fold(last).casefold())
        if not f or not l:
            continue
        year = (birth_year or "")[-4:]
        for cand in (f"{f}.{l}", f"{f}{l}", f"{f}_{l}", f"{f[0]}{l}", f"{f}{l[0]}", f"{l}{f}", f"{l}.{f}", f"{f}-{l}",
                     f"{f}{l}{year}" if year else "", f"{f}{l}{year[-2:]}" if year else "", f"{f[0]}{l}{year[-2:]}" if year else ""):
            if cand and 3 <= len(cand) <= 40 and cand not in out:
                out.append(cand)
    return out[:limit]


def phone_variants(phone: str) -> list[str]:
    digits = re.sub(r"[^\d+]", "", str(phone or ""))
    if not digits:
        return []
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("0") and not digits.startswith("+"):
        digits = "+49" + digits[1:]
    out = [digits]
    if digits.startswith("+"):
        cc = "49" if digits.startswith("+49") else digits[1:3]
        national = "0" + digits[1 + len(cc):]
        out += ["00" + digits[1:], national, f"{national[:4]} {national[4:]}", f"+{cc} {digits[1 + len(cc):]}"]
    return list(dict.fromkeys(out))


# --------------------------------------------------------------------------- Dorks
def engine_links(query: str) -> list[dict[str, str]]:
    return [{"engine": key, "label": label, "url": base + quote_plus(query)} for key, (label, base) in ENGINES.items()]


def dorks(profile: dict[str, Any], missing: bool = False) -> list[dict[str, Any]]:
    """Dork-Satz nach Rechercheziel. Jeder Eintrag: Gruppe, Ziel, Abfrage, Ein-Klick-Links."""
    names = profile["names"] or [profile["label"]]
    q = f'"{names[0]}"'
    alt = " OR ".join(f'"{n}"' for n in names[:4])
    qa = f"({alt})" if len(names) > 1 else q
    loc = profile["locations"][0].split(",")[0] if profile["locations"] else ""
    out: list[dict[str, Any]] = []

    def add(group: str, goal: str, query: str, exposure: str = "passiv") -> None:
        out.append({"id": f"d{len(out) + 1}", "group": group, "goal": goal, "query": query, "links": engine_links(query), "exposure": exposure})

    add("Überblick", "Alle Schreibweisen", qa + (f" {loc}" if loc else ""))
    add("Profile", "Soziale Netzwerke und Plattformen", f"{qa} ({' OR '.join('site:' + s for s in SOCIAL)})")
    add("Profile", "Berufliche Profile", f"{qa} (site:linkedin.com/in OR site:xing.com/profile OR site:about.me OR site:kununu.com)")
    add("Dokumente", "Dokumente mit dem Namen", f"{qa} (filetype:pdf OR filetype:doc OR filetype:docx OR filetype:xls OR filetype:xlsx OR filetype:ppt OR filetype:pptx)")
    add("Dokumente", "Lebenslauf", f"{qa} (Lebenslauf OR CV OR résumé OR \"curriculum vitae\") (filetype:pdf OR filetype:docx)")
    add("Dokumente", "Listen, Protokolle, Teilnehmer", f"{qa} (Teilnehmerliste OR Protokoll OR Mitgliederliste OR Ergebnisliste OR Vorstand)")
    add("Presse", "Nachrichten und lokale Medien", f"{qa} (zeitung OR nachrichten OR news OR bericht)" + (f" {loc}" if loc else ""))
    add("Foren", "Foren und Communities", f"{qa} (inurl:forum OR inurl:thread OR inurl:community OR site:gutefrage.net OR site:reddit.com)")
    add("Bilder", "Fotos mit Namensbezug", f"{qa} (foto OR bild OR photo) (site:flickr.com OR site:instagram.com OR site:pinterest.com)")
    add("Register", "Unternehmen und Register", f"{qa} (site:northdata.de OR site:unternehmensregister.de OR site:handelsregister.de OR site:firmenwissen.de OR site:opencorporates.com)")
    add("Register", "Vereine, Ehrenamt, Sport", f"{qa} (verein OR e.V. OR ehrenamt OR mannschaft OR spieler)")
    add("Archiv", "Gelöschte und archivierte Seiten", f"{qa} (site:web.archive.org OR site:archive.ph)")
    add("Leaks & Paste", "Erwähnungen auf Paste-Seiten", f"{qa} (site:pastebin.com OR site:ghostbin.co OR site:rentry.co)", "passiv")
    for u in profile["usernames"][:4]:
        add("Benutzernamen", f"Benutzername „{u}“", f'"{u}" -site:{u}.com')
        add("Benutzernamen", f"„{u}“ in Adressen", f"inurl:{u}")
    for e in profile["emails"][:3]:
        add("Kontakt", f"E-Mail „{e}“", f'"{e}"')
        local = e.split("@", 1)[0]
        if len(local) >= 4:
            add("Kontakt", f"E-Mail-Name „{local}“ als Benutzername", f'"{local}" -"{e}"')
    for ph in profile["phones"][:2]:
        add("Kontakt", f"Telefon {ph}", " OR ".join(f'"{v}"' for v in phone_variants(ph)[:4]))
    for d in profile["domains"][:3]:
        add("Domains", f"Seiten von {d}", f"site:{d}")
        add("Domains", f"Erwähnungen von {d}", f'"{d}" -site:{d}')
    for emp in profile["employers"][:2]:
        add("Beruf", f"Name + „{emp}“", f'{qa} "{emp}"')
    if missing:
        add("Vermisst", "Vermisstenmeldungen und Fahndung", f"{qa} (vermisst OR \"zuletzt gesehen\" OR Vermisstenfahndung OR abgängig OR missing)")
        add("Vermisst", "Polizei-Pressemeldungen", f"{qa} (site:presseportal.de OR site:polizei.bayern.de OR site:polizei-bw.de OR site:polizei.nrw OR site:polizei.niedersachsen.de OR site:polizei.berlin.de)")
        add("Vermisst", "Suchaufrufe privat (Teilen-Aufrufe)", f"{qa} (\"bitte teilen\" OR \"wer hat\" OR \"wird vermisst\" OR \"helft\") (site:facebook.com OR site:instagram.com OR site:x.com OR site:tiktok.com)")
        add("Vermisst", "Unbekannte Personen / Funde", f"(\"unbekannte Person\" OR \"unbekannte Tote\" OR \"Identität ungeklärt\")" + (f" {loc}" if loc else ""))
        if loc:
            add("Vermisst", f"Lokale Hinweise {loc}", f"{qa} {loc} (gesehen OR hinweis OR polizei)")
    return out


# --------------------------------------------------------------------------- eigene Websuche (SearXNG)
def validate_websearch_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Bitte die Adresse der eigenen SearXNG-Instanz angeben, z. B. http://127.0.0.1:8888")
    try:
        ip = ipaddress.ip_address(parts.hostname)
        if ip.is_link_local or ip.is_multicast:
            raise ValueError("Unzulässige Adresse")
    except ValueError as exc:
        if "Unzulässige" in str(exc):
            raise
    return url


def websearch_source(cfg: dict[str, Any]):
    """Quelle „Websuche“ – nur vorhanden, wenn eine eigene SearXNG-Instanz eingetragen ist."""
    url = (cfg or {}).get("url") or ""
    if not url:
        return None
    from .sources import Source, SourceError

    host = urlsplit(url).hostname or ""

    def run(src, kind: str, value: str, http) -> list[dict]:
        from .opsec import DIRECT, build_opener

        req_url = url + "/search?" + urlencode({"q": value, "format": "json", "language": "all", "safesearch": 0})
        import urllib.request

        req = urllib.request.Request(req_url, headers={"Accept": "application/json", "User-Agent": "EagleEye-PersonOSINT"})
        try:
            with build_opener(DIRECT).open(req, timeout=25) as resp:  # Netzschalter gilt (gated opener)
                data = json.loads(resp.read(3_000_000).decode("utf-8", "replace") or "{}")
        except (OSError, ValueError) as exc:
            raise SourceError(f"Websuche nicht erreichbar: {getattr(exc, 'reason', exc)}") from None
        out = []
        for r in (data.get("results") or [])[:25]:
            link = str(r.get("url") or "")
            if not link.startswith(("http://", "https://")):
                continue
            out.append({"title": f"Web: {str(r.get('title') or link)[:200]}", "url": link, "snippet": str(r.get("content") or "")[:500],
                        "category": "Web", "names": [], "data": {"suchmaschinen": ", ".join(r.get("engines") or []), "dork": value[:300],
                                                                 "host": urlsplit(link).hostname or ""}})
        return out

    return Source("websuche", "Websuche (eigene SearXNG-Instanz)", "Führt die Dorks der Tiefenrecherche über Ihre eigene Meta-Suchmaschine aus.",
                  ("dork",), (host,), "Web", 0.6, "Websuche", run, license="Treffer gehören den jeweiligen Seiten", reliability="D",
                  docs="https://docs.searxng.org/dev/search_api.html", rate_per_min=20)


# --------------------------------------------------------------------------- Planung
def profile_of(p, case_id: int, entity_id: int) -> dict[str, Any]:
    ent = p.get_entity(case_id, entity_id)
    idents = ent["identifiers"]
    by = lambda *kinds: [i["value"] for i in idents if i["kind"] in kinds]  # noqa: E731
    emails = by("email")
    domains = list(dict.fromkeys(by("domain") + [e.rsplit("@", 1)[-1] for e in emails if "@" in e]))
    from .pivot import FREEMAIL

    data = ent.get("data") or {}
    birth = re.search(r"(?:19|20)\d\d", str(data.get("geburtsdatum") or data.get("birth_date") or ""))
    names = list(dict.fromkeys([ent["label"]] + by("name", "alias")))
    last = _split_name(ent["label"])[1]
    # einzelne Spitz-/Rufnamen („Leni“) nie allein abfragen, sondern mit dem Nachnamen („Leni Hoffmann“)
    names = list(dict.fromkeys(n if len(n.split()) > 1 or "," in n or not last else f"{n} {last}" for n in names))
    return {"label": ent["label"], "names": names, "usernames": [u.lstrip("@") for u in by("username")],
            "emails": emails, "phones": by("phone"), "domains": [d for d in domains if d.casefold() not in FREEMAIL], "locations": by("location"),
            "employers": by("employer"), "urls": by("url"), "birth_year": birth.group(0) if birth else ""}


def plan(p, case_id: int, entity_id: int, opts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Welche Abfragen eine Tiefenrecherche jetzt stellen würde – ohne etwas abzufragen."""
    from . import opsec as ops
    from .opsec import EXPOSURE, SOURCE_EXPOSURE
    from .pivot import _searched

    opts = opts or {}
    case = p.get_case(case_id)
    missing = case.get("case_type") == "vermisst" or bool(opts.get("missing"))
    prof = profile_of(p, case_id, entity_id)
    lv = ops.level(case["opsec_level"])
    keys = p.api_keys()
    sources = [s for s in p.all_sources() if s.key != "websuche"]
    done = _searched(p, case_id, entity_id)
    variants = name_variants(prof["names"], limit=int(opts.get("max_name_variants") or 8))
    guessed = username_candidates(prof["names"], prof["birth_year"]) if opts.get("guess_usernames") else []
    inputs: list[tuple[str, str, str]] = [("name", v["value"], v["why"]) for v in variants]
    inputs += [("username", normalize("username", u), "bekannter Benutzername") for u in prof["usernames"]]
    inputs += [("username", g, "erratener Benutzername (Muster aus dem Namen)") for g in guessed if g not in {normalize("username", u) for u in prof["usernames"]}]
    inputs += [("email", normalize("email", e), "bekannte E-Mail") for e in prof["emails"]]
    inputs += [("phone", ph, "Telefon") for ph in prof["phones"]]
    inputs += [("domain", d, "Domain der Person") for d in prof["domains"]]
    inputs += [("url", u, "Webadresse") for u in prof["urls"]]
    inputs += [("employer", e, "Arbeitgeber/Firma") for e in prof["employers"]]
    inputs += [("location", loc, "Ort") for loc in prof["locations"][:2]]
    queries, skipped = [], {"opsec": 0, "unavailable": 0, "done": 0}
    for kind, value, why in inputs:
        for s in sources:
            if kind not in s.kinds:
                continue
            expo = "lokal" if s.local else SOURCE_EXPOSURE.get(s.key, "plattform")
            if EXPOSURE[expo]["rank"] > lv.max_exposure:
                skipped["opsec"] += 1
                continue
            if p.source_unavailable(s, keys):
                skipped["unavailable"] += 1
                continue
            if (s.key, kind, normalize(kind, value)) in done:
                skipped["done"] += 1
                continue
            queries.append({"source": s.key, "source_label": s.label, "kind": kind, "value": value, "why": why, "exposure": expo})
    budget = max(10, min(int(opts.get("budget") or 200), MAX_BUDGET))
    ds = dorks(prof, missing)
    web = p.websearch_config()
    web_ok, web_reason = bool(web.get("url")), ""
    if web_ok and lv.require_egress and not web.get("anonymized"):
        web_ok, web_reason = False, (f"OPSEC-Stufe {lv.key} verlangt einen Anonymisierungs-Ausgang – die eigene Websuche ist nicht als "
                                     "anonymisiert eingetragen. Dorks deshalb nur als Liste.")
    if not web.get("url"):
        web_reason = "Keine eigene Websuche (SearXNG) eingetragen – Dorks als Liste mit Ein-Klick-Links (Verwaltung → Tiefenrecherche)."
    return {"profile": prof, "missing": missing, "variants": variants, "guessed_usernames": guessed, "queries": queries[:budget],
            "over_budget": max(0, len(queries) - budget), "budget": budget, "skipped": skipped, "dorks": ds,
            "websearch": {"available": web_ok, "reason": web_reason}, "depth": max(1, min(int(opts.get("depth") or 2), MAX_DEPTH)),
            "opsec_level": lv.key}


# --------------------------------------------------------------------------- Ausführung im Hintergrund
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def job(job_id: str) -> dict[str, Any]:
    with _LOCK:
        j = _JOBS.get(job_id)
        return {k: v for k, v in j.items() if not k.startswith("_")} if j else {}


def start(p, case_id: int, entity_id: int, opts: dict[str, Any], user: dict[str, Any] | None) -> dict[str, Any]:
    from .service import Invalid

    pl = plan(p, case_id, entity_id, opts)
    p.require_briefing(p.get_case(case_id))
    if not pl["queries"] and not (opts.get("run_dorks") and pl["websearch"]["available"]):
        raise Invalid("Für die Tiefenrecherche gibt es keine offenen Abfragen mehr – alle Varianten sind schon abgefragt oder durch OPSEC gesperrt.")
    with _LOCK:
        if any(j["case_id"] == case_id and j["state"] == "läuft" for j in _JOBS.values()):
            raise Invalid("In diesem Fall läuft bereits eine Tiefenrecherche.")
        job_id = secrets.token_hex(6)
        _JOBS[job_id] = {"id": job_id, "case_id": case_id, "entity_id": entity_id, "state": "läuft", "started": time.time(), "finished": None,
                         "round": 0, "depth": pl["depth"], "budget": pl["budget"], "used": 0, "new_findings": 0, "followed": [],
                         "log": [], "rotate_identity": bool(opts.get("rotate_identity")), "_cancel": False}
    threading.Thread(target=_run, args=(p, job_id, pl, opts, user), name=f"tiefenrecherche-{job_id}", daemon=True).start()
    return job(job_id)


def cancel(job_id: str) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["_cancel"] = True


def _note(job_id: str, text: str, **update: Any) -> None:
    with _LOCK:
        j = _JOBS[job_id]
        j["log"].append({"time": time.time(), "text": text})
        j.update(update)


def _run(p, job_id: str, pl: dict[str, Any], opts: dict[str, Any], user: dict[str, Any] | None) -> None:
    from . import pivot as pv
    from .service import current_user

    current_user.set(user)
    case_id, entity_id = _JOBS[job_id]["case_id"], _JOBS[job_id]["entity_id"]
    budget, used, new_total = pl["budget"], 0, 0
    queries = [(q["source"], q["kind"], q["value"]) for q in pl["queries"]]
    if opts.get("run_dorks") and pl["websearch"]["available"]:
        queries += [("websuche", "dork", d["query"]) for d in pl["dorks"]]
    try:
        for depth in range(1, pl["depth"] + 1):
            if not queries:
                _note(job_id, f"Runde {depth}: keine neuen Spuren – fertig.")
                break
            queries = queries[: max(0, budget - used)]
            if not queries:
                _note(job_id, "Abfragebudget ausgeschöpft.")
                break
            _note(job_id, f"Runde {depth}: {len(queries)} Abfragen", round=depth)
            for i in range(0, len(queries), CHUNK):
                if _JOBS[job_id]["_cancel"]:
                    raise InterruptedError
                chunk = queries[i:i + CHUNK]
                ua = ""
                if _JOBS[job_id]["rotate_identity"]:
                    ua = secrets.choice(USER_AGENTS)
                    renewed = p.renew_identity()
                    _note(job_id, "Neue Netzidentität: " + ("neuer Tor-Ausgang + " if renewed else "") + "wechselnde Browserkennung")
                res = p.run_search(case_id, entity_id, queries=chunk, user_agent=ua,
                                   pivot={"kind": "tiefenrecherche", "value": f"Runde {depth}", "depth": depth - 1,
                                          "origin": {"type": "deep", "label": f"Tiefenrecherche {job_id} · Runde {depth}"}, "deep": job_id})
                used += res["queries"]
                new_total += res["new_findings"]
                _note(job_id, f"  {res['queries']} Abfragen, {res['new_findings']} neue Treffer"
                      + (f", {res['blocked']} durch OPSEC gesperrt" if res["blocked"] else ""), used=used, new_findings=new_total)
            if depth == pl["depth"]:
                break
            # starke neue Spuren automatisch weiterverfolgen
            done = pv._searched(p, case_id, entity_id)  # noqa: SLF001
            follow, nxt = [], []
            sources = [s for s in p.all_sources() if s.key != "websuche"]
            for cand in pv.harvest(p, case_id, entity_id, min_score=int(opts.get("follow_min_score") or FOLLOW_MIN_SCORE)):
                if cand["kind"] not in {"username", "email", "domain", "url", "alias"}:
                    continue
                sk = pv._search_kind(cand["kind"])  # noqa: SLF001
                norm = normalize(sk, cand["value"])
                added = [(s.key, sk, norm if sk in {"username", "email"} else cand["value"]) for s in sources
                         if sk in s.kinds and (s.key, sk, norm) not in done and not p.source_unavailable(s)]
                if added:
                    follow.append(f"{cand['kind_label']}: {cand['value']}")
                    nxt += added
            queries = list(dict.fromkeys(nxt))
            with _LOCK:
                _JOBS[job_id]["followed"] += follow
            if follow:
                _note(job_id, f"Starke neue Spuren: {', '.join(follow[:8])}" + (" …" if len(follow) > 8 else ""))
        _note(job_id, f"Fertig: {used} Abfragen, {new_total} neue Treffer.", state="fertig", finished=time.time())
        p.log(case_id, "Tiefenrecherche abgeschlossen", f"{used} Abfragen, {new_total} neue Treffer, {len(_JOBS[job_id]['followed'])} Spuren verfolgt")
    except InterruptedError:
        _note(job_id, "Abgebrochen.", state="abgebrochen", finished=time.time())
    except Exception as exc:  # noqa: BLE001 - Fehler sichtbar machen statt Thread still sterben lassen
        _note(job_id, f"Abgebrochen: {exc}", state="fehler", finished=time.time())


__all__ = ["name_variants", "username_candidates", "phone_variants", "dorks", "plan", "start", "job", "cancel", "websearch_source",
           "validate_websearch_url", "USER_AGENTS"]
