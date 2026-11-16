"""Weitere frei zugängliche Quellen (Version 1.6): Normdaten, Politik, Register, Presse, Fahndung, Konten.

Alle Anbindungen nutzen öffentliche, dokumentierte Schnittstellen ohne Anmeldung. Sie wurden nach der
veröffentlichten Schnittstellenbeschreibung gebaut; ob eine Quelle auf dieser Installation tatsächlich
antwortet, zeigt **Verwaltung → Quellen & Daten → „Alle Quellen prüfen“** (bzw. ``python -m personosint
check-sources``). Bis dahin gilt eine Quelle hier als „noch nicht geprüft“ – nichts wird als geprüft behauptet.

Wie überall: Treffer sind Kandidaten. Bestätigt wird durch Menschen.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlencode

from .connectors import _json
from .facts import claim
from .matching import name_similarity
from .sources import Http, Source, SourceError, _clean


def _labels(items: Any, limit: int = 5) -> list[str]:
    """lobid liefert Listen aus {id, label}; hier nur die Beschriftungen."""
    return [str(x.get("label") or "").strip() for x in (items or []) if isinstance(x, dict) and x.get("label")][:limit]


def _display_name(gnd_name: str) -> str:
    """„Merkel, Angela“ → „Angela Merkel“."""
    parts = [x.strip() for x in str(gnd_name or "").split(",", 1)]
    return f"{parts[1]} {parts[0]}".strip() if len(parts) == 2 else parts[0]


# --------------------------------------------------------------------------- GND (Deutsche Nationalbibliothek) über lobid.org

def _lobid_gnd(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://lobid.org/gnd/search?" + urlencode({"q": value, "filter": "type:Person", "format": "json", "size": 8}))) or {}
    out = []
    for m in data.get("member", []):
        name = _display_name(m.get("preferredName", ""))
        if name_similarity(name, value) < 0.8 and not any(name_similarity(_display_name(v), value) >= 0.85 for v in (m.get("variantName") or [])[:20]):
            continue
        gnd = m.get("gndIdentifier", "")
        claims = [claim("geburtsdatum", (m.get("dateOfBirth") or [""])[0])]
        claims += [claim("geburtsort", x, "ort") for x in _labels(m.get("placeOfBirth"), 1)]
        claims += [claim("beschreibung", x) for x in _labels(m.get("professionOrOccupation"), 4)]
        claims += [claim("arbeitet_bei", x, "organisation") for x in _labels(m.get("affiliation"), 4)]
        claims += [claim("alias", _display_name(v)) for v in (m.get("variantName") or [])[:5] if isinstance(v, str)]
        jobs = ", ".join(_labels(m.get("professionOrOccupation"), 3))
        out.append({"title": f"GND: {name}" + (f" ({(m.get('dateOfBirth') or [''])[0][:4]})" if m.get("dateOfBirth") else ""),
                    "url": f"https://lobid.org/gnd/{quote(gnd)}" if gnd else "", "snippet": _clean(jobs or (m.get("biographicalOrHistoricalInformation") or [""])[0]),
                    "category": "Öffentliche Person", "names": [name], "locations": _labels(m.get("placeOfBirth"), 1) + _labels(m.get("placeOfActivity"), 2),
                    "claims": [c for c in claims if c["object"]],
                    "data": {"gnd_id": gnd, "geburtsdatum": (m.get("dateOfBirth") or [""])[0], "institutionen": _labels(m.get("affiliation"), 3)}})
    return out


# --------------------------------------------------------------------------- abgeordnetenwatch.de (Politik in Deutschland)

def _abgeordnetenwatch(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    parts = value.split()
    params: dict[str, Any] = {"range_end": 10}
    if len(parts) >= 2:
        params.update({"first_name": " ".join(parts[:-1]), "last_name": parts[-1]})
    else:
        params["label[cn]"] = value
    data = _json(src.get(http, "https://www.abgeordnetenwatch.de/api/v2/politicians?" + urlencode(params))) or {}
    out = []
    for p in data.get("data", []):
        name = p.get("label") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        party = (p.get("party") or {}).get("label", "")
        claims = [claim("partei", party, "organisation"), claim("amt", p.get("occupation") or ""),
                  claim("geburtsdatum", str(p.get("year_of_birth") or ""), attrs_precision="Jahr"), claim("beschreibung", p.get("education") or "")]
        out.append({"title": f"abgeordnetenwatch: {name}" + (f" ({party})" if party else ""),
                    "url": p.get("abgeordnetenwatch_url", ""), "snippet": _clean(" · ".join(x for x in [p.get("occupation"), p.get("education"), p.get("residence")] if x)),
                    "category": "Öffentliche Person", "names": [name], "locations": [p.get("residence") or ""],
                    "claims": [c for c in claims if c["object"]],
                    "data": {"abgeordnetenwatch_id": p.get("id"), "wikidata_id": p.get("qid_wikidata"), "geburtsjahr": p.get("year_of_birth")}})
    return out


# --------------------------------------------------------------------------- Frankreich: Annuaire des Entreprises (Firmenregister mit Leitungspersonen)

def _fr_entreprises(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://recherche-entreprises.api.gouv.fr/search?" + urlencode({"q": value, "per_page": 10, "page": 1}))) or {}
    out = []
    for r in data.get("results", []):
        company = (r.get("nom_complet") or r.get("nom_raison_sociale") or "").title()
        siren = r.get("siren", "")
        seat = r.get("siege") or {}
        addr = ", ".join(x for x in [seat.get("adresse") or "", seat.get("libelle_commune") or ""] if x) or (seat.get("libelle_commune") or "")
        people = [d for d in (r.get("dirigeants") or []) if d.get("nom")]
        claims: list[dict] = []
        hit_names: list[str] = []
        if kind == "name":
            for d in people:
                person = f"{(d.get('prenoms') or '').split(',')[0]} {d.get('nom', '')}".strip().title()
                if name_similarity(person, value) < 0.85:
                    continue
                hit_names.append(person)
                claims.append(claim("funktion_bei", company, "organisation", rolle=d.get("qualite"), siren=siren))
                if d.get("date_de_naissance") or d.get("annee_de_naissance"):
                    claims.append(claim("geburtsdatum", str(d.get("date_de_naissance") or d.get("annee_de_naissance")), attrs_precision="Monat"))
            if not hit_names:
                continue
        else:
            claims += [claim("firmensitz", addr, "ort", subject=company, subject_type="organisation"),
                       claim("registriert_als", f"SIREN {siren}", subject=company, subject_type="organisation"),
                       claim("firmenstatus", {"A": "aktiv", "C": "geschlossen"}.get(r.get("etat_administratif"), r.get("etat_administratif") or ""),
                             subject=company, subject_type="organisation")]
            for d in people[:10]:
                person = f"{(d.get('prenoms') or '').split(',')[0]} {d.get('nom', '')}".strip().title()
                claims.append(claim("funktion_bei", company, "organisation", subject=person, subject_type="person", rolle=d.get("qualite")))
        out.append({"title": f"Frankreich (Firmenregister): {company}" + (f" – {hit_names[0]}" if hit_names else ""),
                    "url": f"https://annuaire-entreprises.data.gouv.fr/entreprise/{quote(siren)}" if siren else "",
                    "snippet": _clean(f"SIREN {siren} · {addr} · gegründet {r.get('date_creation') or '?'}"),
                    "category": "Wirtschaft", "names": hit_names, "locations": [addr], "claims": [c for c in claims if c["object"]],
                    "data": {"siren": siren, "organisation": company}})
    return out


# --------------------------------------------------------------------------- ICIJ Offshore Leaks (online, ohne Gesamtdownload)

def _icij_online(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    queries = json.dumps({"q0": {"query": value, "limit": 10}})
    data = _json(src.get(http, "https://offshoreleaks.icij.org/api/v1/reconcile?" + urlencode({"queries": queries}))) or {}
    out = []
    for r in (data.get("q0") or {}).get("result", []):
        name = str(r.get("name") or "").strip()
        if name_similarity(name, value) < 0.85:
            continue
        typ = ", ".join(t.get("name", "") for t in (r.get("types") or []) if isinstance(t, dict)) or "Eintrag"
        node = str(r.get("id") or "")
        url = node if node.startswith("https://") else f"https://offshoreleaks.icij.org/nodes/{quote(node)}"
        pred = "offshore_funktion" if "officer" in typ.casefold() else "gelistet_in"
        obj = "Offshore-Gesellschaft (Details im ICIJ-Eintrag)" if pred == "offshore_funktion" else f"ICIJ Offshore Leaks ({typ})"
        out.append({"title": f"ICIJ Offshore Leaks: {name} ({typ})", "url": url, "snippet": _clean(r.get("description") or f"Eintrag als {typ}"),
                    "category": "Risiko", "names": [name] if kind == "name" else [], "claims": [claim(pred, obj, quelle_url=url)],
                    "data": {"icij_node": node, "typ": typ}})
    return out


# --------------------------------------------------------------------------- Fahndung: INTERPOL Rote Ausschreibungen, FBI

def _interpol_red(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    parts = value.split()
    params: dict[str, Any] = {"resultPerPage": 20}
    if len(parts) >= 2:
        params.update({"forename": " ".join(parts[:-1]), "name": parts[-1]})
    else:
        params["name"] = value
    r = src.get(http, "https://ws-public.interpol.int/notices/v1/red?" + urlencode(params))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    out = []
    for n in r.json().get("_embedded", {}).get("notices", []):
        name = f"{n.get('forename', '')} {n.get('name', '')}".strip().title()
        nid = str(n.get("entity_id", ""))
        out.append({"title": f"INTERPOL Rote Ausschreibung (Fahndung): {name}",
                    "url": f"https://www.interpol.int/How-we-work/Notices/Red-Notices/View-Red-Notices#{nid.replace('/', '-')}",
                    "snippet": f"Geburtsdatum: {n.get('date_of_birth') or 'unbekannt'} · Nationalität: {', '.join(n.get('nationalities') or [])}",
                    "category": "Risiko", "names": [name],
                    "claims": [c for c in [claim("gelistet_in", "INTERPOL Rote Ausschreibung (öffentliche Fahndung)"),
                                           claim("geburtsdatum", str(n.get("date_of_birth") or "").replace("/", "-"))] if c["object"]],
                    "data": {"notice_id": nid, "geburtsdatum": n.get("date_of_birth")}})
    return out


def _fbi_wanted(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://api.fbi.gov/wanted/v1/list?" + urlencode({"title": value, "pageSize": 10}))) or {}
    out = []
    for it in data.get("items", []):
        name = str(it.get("title") or "").title()
        aliases = [str(a).title() for a in (it.get("aliases") or [])]
        if max([name_similarity(name, value)] + [name_similarity(a, value) for a in aliases]) < 0.82:
            continue
        claims = [claim("gelistet_in", "FBI Wanted (" + str(it.get("poster_classification") or "Fahndung") + ")"),
                  claim("geburtsdatum", (it.get("dates_of_birth_used") or [""])[0]), claim("staatsangehoerigkeit", it.get("nationality") or "")]
        claims += [claim("alias", a) for a in aliases[:5]]
        out.append({"title": f"FBI Wanted: {name}", "url": it.get("url", ""), "snippet": _clean(it.get("description") or it.get("caution") or ""),
                    "category": "Risiko", "names": [name] + aliases[:5], "locations": [it.get("place_of_birth") or ""],
                    "claims": [c for c in claims if c["object"]], "data": {"fbi_uid": it.get("uid"), "art": it.get("poster_classification")}})
    return out


# --------------------------------------------------------------------------- Presse (GDELT) und Wikipedia

def _gdelt(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    query = '"' + value.replace('"', " ").strip() + '"'
    r = src.get(http, "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode({"query": query, "mode": "artlist", "maxrecords": 15, "format": "json", "sort": "datedesc"}))
    if r.status != 200:
        raise SourceError(f"HTTP {r.status}")
    try:
        data = json.loads(r.body.decode("utf-8", "replace") or "{}")
    except ValueError:
        raise SourceError("GDELT lieferte keine auswertbare Antwort (häufig bei zu kurzen oder zu häufigen Anfragen)") from None
    out = []
    for a in data.get("articles", []):
        seen = str(a.get("seendate") or "")
        date = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 else ""
        out.append({"title": f"Presse: {_clean(a.get('title'), 200)}", "url": a.get("url", ""),
                    "snippet": _clean(f"{a.get('domain', '')} · {date} · Sprache {a.get('language', '?')} · Land {a.get('sourcecountry', '?')}"),
                    "category": "Presse", "names": [], "data": {"medium": a.get("domain"), "erschienen": date, "sprache": a.get("language")}})
    return out


def _wikipedia(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    out = []
    for lang in ("de", "en"):
        r = src.get(http, f"https://{lang}.wikipedia.org/w/api.php?" + urlencode({"action": "query", "list": "search", "srsearch": f'"{value}"', "format": "json",
                                                                                 "srlimit": 5, "srprop": "snippet"}))
        if r.status != 200:
            raise SourceError(f"HTTP {r.status}")
        for hit in (r.json().get("query") or {}).get("search", []):
            title = hit.get("title", "")
            exact = name_similarity(re.sub(r"\s*\(.*?\)$", "", title), value) >= 0.9
            out.append({"title": f"Wikipedia ({lang}): {title}", "url": f"https://{lang}.wikipedia.org/?curid={hit.get('pageid')}",
                        "snippet": _clean(hit.get("snippet")), "category": "Öffentliche Person" if exact else "Erwähnung",
                        "names": [re.sub(r"\s*\(.*?\)$", "", title)] if exact else [], "data": {"sprache": lang, "pageid": hit.get("pageid")}})
    return out


# --------------------------------------------------------------------------- Wissenschaft: Crossref, DBLP

def _crossref(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://api.crossref.org/works?" + urlencode({"query.author": value, "rows": 8,
                                                                              "select": "DOI,title,author,issued,container-title"}))) or {}
    works, insts = [], {}
    for it in (data.get("message") or {}).get("items", []):
        for au in it.get("author") or []:
            if name_similarity(f"{au.get('given', '')} {au.get('family', '')}".strip(), value) >= 0.88:
                for aff in au.get("affiliation") or []:
                    if aff.get("name"):
                        insts[aff["name"]] = insts.get(aff["name"], 0) + 1
                year = str(((it.get("issued") or {}).get("date-parts") or [[""]])[0][0] or "")
                works.append((year, (it.get("title") or ["(ohne Titel)"])[0], it.get("DOI", "")))
                break
    if not works:
        return []
    works.sort(reverse=True)
    top = [k for k, _ in sorted(insts.items(), key=lambda kv: -kv[1])][:3]
    return [{"title": f"Crossref: {len(works)} Veröffentlichung(en) unter diesem Autorennamen",
             "url": "https://search.crossref.org/?" + urlencode({"q": value, "from_ui": "yes"}),
             "snippet": _clean("; ".join(f"{t} ({y})" for y, t, _ in works[:3])), "category": "Beruf/Bildung", "names": [value],
             "claims": [claim("arbeitet_bei", i, "organisation") for i in top],
             "data": {"institutionen": top, "doi": [d for _, _, d in works[:5] if d]}}]


def _dblp(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://dblp.org/search/author/api?" + urlencode({"q": value, "format": "json", "h": 5}))) or {}
    hits = (((data.get("result") or {}).get("hits") or {}).get("hit")) or []
    out = []
    for h in hits if isinstance(hits, list) else [hits]:
        info = h.get("info") or {}
        name = re.sub(r"\s+\d{4}$", "", str(info.get("author") or ""))
        if name_similarity(name, value) < 0.88:
            continue
        notes = (info.get("notes") or {}).get("note") or []
        affs = [n.get("text", "") for n in (notes if isinstance(notes, list) else [notes]) if isinstance(n, dict) and n.get("@type") == "affiliation"]
        out.append({"title": f"DBLP (Informatik): {name}", "url": info.get("url", ""), "snippet": _clean("; ".join(affs)),
                    "category": "Beruf/Bildung", "names": [name], "claims": [claim("arbeitet_bei", a, "organisation") for a in affs[:3] if a],
                    "data": {"institutionen": affs[:3]}})
    return out


# --------------------------------------------------------------------------- Konten: Keybase, Codeberg, Docker Hub

def _keybase(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    user = value.lstrip("@")
    data = _json(src.get(http, "https://keybase.io/_/api/1.0/user/lookup.json?" + urlencode({"usernames": user, "fields": "basics,profile,proofs_summary"}))) or {}
    them = [t for t in (data.get("them") or []) if isinstance(t, dict)]
    out = []
    for t in them:
        name = ((t.get("profile") or {}).get("full_name") or "").strip()
        proofs = [p for p in ((t.get("proofs_summary") or {}).get("all") or []) if isinstance(p, dict) and p.get("nametag")]
        linked = [f"{p.get('proof_type')}: {p.get('nametag')}" for p in proofs[:12]]
        handle = (t.get("basics") or {}).get("username") or user
        out.append({"title": f"Keybase: {handle}" + (f" ({name})" if name else ""), "url": f"https://keybase.io/{quote(handle)}",
                    "snippet": _clean("Kryptografisch verknüpfte Konten: " + ", ".join(linked)) if linked else _clean((t.get("profile") or {}).get("bio")),
                    "category": "Konto", "names": [name] if name else [], "locations": [(t.get("profile") or {}).get("location") or ""],
                    "claims": [claim("konto", f"{p.get('proof_type')}: {p.get('nametag')}", "konto", quelle_url=p.get("service_url")) for p in proofs[:12]],
                    "data": {"plattform": "Keybase", "benutzername": handle, "verknuepfte_konten": linked}})
    return out


def _codeberg(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    data = _json(src.get(http, "https://codeberg.org/api/v1/users/search?" + urlencode({"q": value.lstrip("@"), "limit": 5}))) or {}
    out = []
    for u in data.get("data", []):
        login, full = u.get("login", ""), (u.get("full_name") or "").strip()
        if kind == "username" and login.casefold() != value.lstrip("@").casefold():
            continue
        if kind == "name" and name_similarity(full, value) < 0.85:
            continue
        out.append({"title": f"Codeberg: {login}" + (f" ({full})" if full else ""), "url": u.get("html_url") or f"https://codeberg.org/{quote(login)}",
                    "snippet": _clean(" · ".join(x for x in [u.get("description"), u.get("location"), u.get("website")] if x)),
                    "category": "Konto", "names": [full] if full else [], "locations": [u.get("location") or ""],
                    "data": {"plattform": "Codeberg", "benutzername": login, "webseite": u.get("website") or None, "erstellt": u.get("created")}})
    return out


def _dockerhub(src: Source, kind: str, value: str, http: Http) -> list[dict]:
    user = value.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_.\-]{2,60}", user):
        return []
    d = _json(src.get(http, f"https://hub.docker.com/v2/users/{quote(user)}/"))
    handle = (d or {}).get("username") or (d or {}).get("orgname")     # Organisationen leitet Docker Hub auf einen Eintrag mit „orgname“ um
    if not handle:
        return []
    full = (d.get("full_name") or "").strip()
    org = bool(d.get("orgname"))
    return [{"title": f"Docker Hub{' (Organisation)' if org else ''}: {handle}" + (f" ({full})" if full else ""), "url": f"https://hub.docker.com/u/{quote(handle)}",
             "snippet": _clean(" · ".join(x for x in [d.get("company"), d.get("location"), "Konto seit " + str(d.get("date_joined") or "")[:10]] if x)),
             "category": "Konto", "names": [full] if full and not org else [], "locations": [d.get("location") or ""],
             "data": {"plattform": "Docker Hub", "benutzername": handle, "organisation": d.get("company") or None, "erstellt": d.get("date_joined")}}]


MORE_SOURCES: list[Source] = [
    Source("lobid_gnd", "GND – Deutsche Nationalbibliothek (lobid)", "Normdaten zu Personen: Lebensdaten, Berufe, Wirkungsorte, Namensvarianten – stark für den deutschsprachigen Raum.",
           ("name",), ("lobid.org",), "Öffentliche Person", 0.9, "Register & Wissen", _lobid_gnd,
           license="CC0 1.0", reliability="B", docs="https://lobid.org/gnd/api", rate_per_min=30),
    Source("abgeordnetenwatch", "abgeordnetenwatch.de", "Abgeordnete und Kandidierende in Bund, Ländern und EU: Partei, Beruf, Ausbildung, Geburtsjahr.",
           ("name",), ("www.abgeordnetenwatch.de",), "Öffentliche Person", 1.0, "Register & Wissen", _abgeordnetenwatch,
           license="CC0 1.0", reliability="B", docs="https://www.abgeordnetenwatch.de/api", rate_per_min=30),
    Source("wikipedia", "Wikipedia (de/en)", "Artikel und Erwähnungen in der deutschen und englischen Wikipedia.",
           ("name",), ("de.wikipedia.org", "en.wikipedia.org"), "Erwähnung", 0.7, "Register & Wissen", _wikipedia,
           license="CC BY-SA 4.0 (Texte)", reliability="C", docs="https://www.mediawiki.org/wiki/API:Search", rate_per_min=30),
    Source("fr_entreprises", "Frankreich – Firmenregister (Annuaire des Entreprises)", "Französische Unternehmen mit Leitungspersonen; Personensuche über Geschäftsführer/Direktoren.",
           ("name", "employer"), ("recherche-entreprises.api.gouv.fr",), "Wirtschaft", 1.0, "Wirtschaft & Register", _fr_entreprises,
           license="Licence Ouverte 2.0 (Etalab)", reliability="A", docs="https://recherche-entreprises.api.gouv.fr/docs/", rate_per_min=30,
           test_query=("name", "Bernard Arnault")),
    Source("icij_online", "ICIJ Offshore Leaks (online)", "Panama/Paradise/Pandora Papers: Personen und Gesellschaften – ohne den Gesamtbestand herunterzuladen.",
           ("name", "employer"), ("offshoreleaks.icij.org",), "Risiko", 1.0, "Risiko & Compliance", _icij_online,
           license="ODbL / CC BY-SA – Quellenangabe ICIJ Pflicht", reliability="B", docs="https://offshoreleaks.icij.org/docs/reconciliation", rate_per_min=20,
           test_query=("name", "Sergei Roldugin")),
    Source("interpol_red", "INTERPOL – Fahndung (Red Notices)", "Öffentliche internationale Fahndungsausschreibungen.",
           ("name",), ("ws-public.interpol.int",), "Risiko", 1.1, "Risiko & Compliance", _interpol_red,
           license="öffentliche Bekanntmachung", reliability="A", docs="https://interpol.api.bund.dev/", rate_per_min=20, test_query=("name", "Smith")),
    Source("fbi_wanted", "FBI – Wanted", "Öffentliche Fahndungs- und Vermisstenliste des FBI (USA).",
           ("name",), ("api.fbi.gov",), "Risiko", 1.0, "Risiko & Compliance", _fbi_wanted,
           license="gemeinfrei (US-Bundesbehörde)", reliability="A", docs="https://www.fbi.gov/wanted/api", rate_per_min=20, test_query=("name", "Smith")),
    Source("gdelt_news", "Presse weltweit (GDELT)", "Aktuelle Presseberichte der letzten Monate aus über 100 Sprachen, in denen der Name genau so vorkommt.",
           ("name", "employer"), ("api.gdeltproject.org",), "Presse", 0.6, "Presse & Medien", _gdelt,
           license="frei nutzbar mit Quellenangabe GDELT; Artikel bleiben bei den Verlagen", reliability="C", docs="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
           rate_per_min=10),
    Source("crossref", "Crossref", "Wissenschaftliche Veröffentlichungen unter dem Autorennamen, mit angegebenen Einrichtungen.",
           ("name",), ("api.crossref.org",), "Beruf/Bildung", 0.7, "Register & Wissen", _crossref,
           license="CC0 (Metadaten)", reliability="B", docs="https://api.crossref.org/swagger-ui/index.html", rate_per_min=30),
    Source("dblp", "DBLP (Informatik)", "Autorinnen und Autoren der Informatik mit Einrichtung.",
           ("name",), ("dblp.org",), "Beruf/Bildung", 0.7, "Register & Wissen", _dblp,
           license="CC0", reliability="B", docs="https://dblp.org/faq/How+to+use+the+dblp+search+API.html", rate_per_min=20, test_query=("name", "Donald Knuth")),
    Source("keybase", "Keybase", "Öffentliches Profil mit kryptografisch nachgewiesenen Verknüpfungen zu anderen Konten.",
           ("username",), ("keybase.io",), "Konto", 1.1, "Online-Präsenz", _keybase,
           license="öffentliche Profilangaben", reliability="B", docs="https://keybase.io/docs/api/1.0/call/user/lookup", rate_per_min=20, test_query=("username", "chris")),
    Source("codeberg", "Codeberg", "Öffentliche Profile auf der europäischen Code-Plattform.",
           ("username", "name"), ("codeberg.org",), "Konto", 0.9, "Online-Präsenz", _codeberg,
           license="öffentliche Profilangaben", reliability="C", docs="https://codeberg.org/api/swagger", rate_per_min=20, test_query=("username", "forgejo")),
    Source("dockerhub", "Docker Hub", "Öffentliches Profil zu einem Benutzernamen (Firma, Ort, Beitrittsdatum).",
           ("username",), ("hub.docker.com",), "Konto", 0.9, "Online-Präsenz", _dockerhub,
           license="öffentliche Profilangaben", reliability="C", docs="https://docs.docker.com/reference/api/hub/latest/", rate_per_min=20, test_query=("username", "library")),
]
