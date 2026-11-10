"""Folgesuchen: Aus geprüften Treffern entstehen Vorschläge für die nächste Suche – ausgeführt wird erst nach Freigabe.

Übernommenes Muster aus der SpiderFoot-Analyse (Abschnitt 6): Jede Quelle erklärt, welche Kennungen sie
**verarbeitet** (``kinds``) und welche sie **liefern** kann (``produces``). SpiderFoot verkettet Module
daraus automatisch; hier entsteht nur ein **Vorschlag**, den ein Mensch freigibt oder verwirft. Dazu kommen
zwei Lehren aus den Schwächen von SpiderFoot:

* **Begrenzte Tiefe** (``MAX_DEPTH``): Die Suche darf sich nicht selbständig immer weiter vom Auftrag entfernen.
* **Lückenlose Herkunftskette**: Zu jedem Treffer lässt sich zeigen, über welche Kennung aus welchem
  früheren Treffer er gefunden wurde – bis zurück zur Zielperson.

Vorschläge entstehen nur aus **bestätigten** Treffern und Aussagen. OPSEC-Regeln des Falls gelten unverändert.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .db import now_iso
from .matching import normalize

MAX_DEPTH = 3

#: Welche Arten von Kennungen können Treffer einer Quelle liefern? (Gegenstück zu Source.kinds)
PRODUCES: dict[str, tuple[str, ...]] = {
    "username_presence": ("username", "url"), "github": ("username", "url", "email", "employer", "location"),
    "gitlab": ("username", "url"), "bluesky": ("username", "url"), "mastodon": ("username", "url"), "gravatar": ("username", "url"),
    "wikidata": ("alias",), "wikidata_rel": ("alias", "employer", "location"), "openalex": ("employer",), "orcid": ("employer",),
    "interpol_yellow": (), "wayback": ("url",), "nominatim": ("location",),
    "companies_house": ("employer", "location"), "opencorporates": ("employer",), "gleif": ("employer", "location"),
    "crtsh": ("domain",), "rdap": ("domain", "employer"), "opensanctions": ("alias",),
    "lokal_opensanctions": ("alias",), "lokal_icij": ("employer", "location"), "lokal_eigene_liste": ("alias",),
}
KIND_LABEL = {"name": "Name", "alias": "Alias", "email": "E-Mail", "phone": "Telefon", "username": "Benutzername", "url": "Webadresse",
              "location": "Ort/Adresse", "employer": "Arbeitgeber/Firma", "domain": "Domain"}
#: Felder in den Daten eines Treffers → Art der Kennung
DATA_KIND = {"benutzername": "username", "email": "email", "e_mail": "email", "blog": "url", "website": "url", "webseite": "url",
             "homepage": "url", "organisation": "employer", "ort": "location", "standort": "location", "domain": "domain"}
#: Prädikate geprüfter Aussagen → Art der Kennung (Objekt der Aussage)
FACT_KIND = {"email": "email", "alias": "alias", "adresse": "location", "arbeitet_bei": "employer", "funktion_bei": "employer"}
FREEMAIL = {"gmail.com", "googlemail.com", "gmx.de", "gmx.net", "gmx.at", "gmx.ch", "web.de", "outlook.com", "outlook.de", "hotmail.com", "hotmail.de",
            "live.com", "live.de", "yahoo.com", "yahoo.de", "icloud.com", "me.com", "t-online.de", "posteo.de", "mailbox.org", "proton.me",
            "protonmail.com", "aol.com", "freenet.de", "mail.de", "arcor.de", "msn.com", "yandex.ru", "mail.ru", "tutanota.com", "tuta.io"}
#: Plattform-Adressen sind keine eigene Domain der Person
PLATFORM_HOSTS = ("github.com", "gitlab.com", "bsky.app", "mastodon.social", "gravatar.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
                  "linkedin.com", "xing.com", "youtube.com", "tiktok.com", "reddit.com", "wikipedia.org", "wikidata.org", "archive.org")


def apply_manifest(sources: list[Any]) -> list[Any]:
    """Trägt ``produces`` aus der zentralen Tabelle ein (Quellen können es auch selbst angeben)."""
    for s in sources:
        if not s.produces and s.key in PRODUCES:
            s.produces = PRODUCES[s.key]
    return sources


def _search_kind(kind: str) -> str:
    return "name" if kind == "alias" else kind


def _clean_value(kind: str, value: Any) -> str:
    value = str(value or "").strip()
    if kind == "username":
        value = value.lstrip("@").split("@")[0]
        return value if re.fullmatch(r"[\w.\-]{2,60}", value) else ""
    if kind == "email":
        return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) else ""
    if kind == "url":
        if value and not value.startswith(("http://", "https://")):
            value = "https://" + value
        return value if urlsplit(value).hostname and "." in (urlsplit(value).hostname or "") else ""
    if kind == "domain":
        value = value.casefold().removeprefix("www.")
        return value if re.fullmatch(r"[a-z0-9.\-]+\.[a-z]{2,}", value) else ""
    if kind == "employer":
        value = value.lstrip("@")
    return value[:200] if len(value) >= 2 else ""


def _own_domain(host: str) -> str:
    host = (host or "").casefold().removeprefix("www.")
    if not host or host in FREEMAIL or any(host == h or host.endswith("." + h) for h in PLATFORM_HOSTS):
        return ""
    return host if re.fullmatch(r"[a-z0-9.\-]+\.[a-z]{2,}", host) else ""


def _depths(p, case_id: int) -> dict[int, int]:
    """Suchlauf-ID → Tiefe (0 = von Analyst gestartet)."""
    return {s["id"]: int((s.get("pivot") or {}).get("depth") or 0) for s in p.db.all("SELECT id, pivot FROM searches WHERE case_id = ?", (case_id,))}


def harvest(p, case_id: int, entity_id: int) -> list[dict[str, Any]]:
    """Kennungen aus bestätigten Treffern und Aussagen einer Person – mit Herkunft und Tiefe."""
    depths = _depths(p, case_id)
    out: dict[tuple[str, str], dict[str, Any]] = {}

    def add(kind: str, value: Any, origin: dict[str, Any], depth: int) -> None:
        value = _clean_value(kind, value)
        if not value:
            return
        key = (kind, normalize(kind, value))
        if key not in out or depth < out[key]["depth"]:
            out[key] = {"kind": kind, "kind_label": KIND_LABEL.get(kind, kind), "value": value, "normalized": key[1], "origin": origin, "depth": depth}

    findings = p.db.all("SELECT id, search_id, source, title, url, category, data FROM findings WHERE case_id = ? AND entity_id = ? AND status = 'bestätigt'",
                        (case_id, entity_id))
    by_id = {f["id"]: f for f in findings}
    for f in findings:
        depth = depths.get(f["search_id"], 0) + 1
        origin = {"type": "finding", "finding_id": f["id"], "label": f["title"][:120], "source": f["source"]}
        for field, val in (f["data"] or {}).items():
            kind = DATA_KIND.get(field)
            if not kind or isinstance(val, (dict, list)):
                continue
            add(kind, val, origin, depth)
            if kind in {"url", "email"}:
                host = urlsplit(_clean_value("url", val)).hostname if kind == "url" else str(val).rsplit("@", 1)[-1]
                add("domain", _own_domain(host or ""), origin, depth)
    for fa in p.db.all("SELECT id, finding_id, predicate, object_label, source_label FROM facts WHERE case_id = ? AND subject_entity_id = ? AND status = 'bestätigt'",
                       (case_id, entity_id)):
        kind = FACT_KIND.get(fa["predicate"])
        if not kind:
            continue
        parent = by_id.get(fa["finding_id"])
        depth = (depths.get(parent["search_id"], 0) if parent else 0) + 1
        origin = {"type": "fact", "fact_id": fa["id"], "finding_id": fa["finding_id"], "label": f"{fa['predicate']}: {fa['object_label']}"[:120],
                  "source": fa["source_label"]}
        add(kind, fa["object_label"], origin, depth)
        if kind == "email":
            add("domain", _own_domain(str(fa["object_label"]).rsplit("@", 1)[-1]), origin, depth)
    # Eigene Domain hinter einer bekannten E-Mail-Adresse (auch vom Analysten erfasst)
    for ident in p.db.all("SELECT id, kind, value, finding_id FROM identifiers WHERE case_id = ? AND entity_id = ? AND kind = 'email'", (case_id, entity_id)):
        parent = by_id.get(ident["finding_id"]) if ident.get("finding_id") else None
        add("domain", _own_domain(ident["value"].rsplit("@", 1)[-1]),
            {"type": "identifier", "identifier_id": ident["id"], "finding_id": ident.get("finding_id"), "label": f"E-Mail {ident['value']}", "source": "Kennung"},
            (depths.get(parent["search_id"], 0) if parent else 0) + 1)
    return list(out.values())


def _searched(p, case_id: int, entity_id: int) -> set[tuple[str, str, str]]:
    done = set()
    for s in p.db.all("SELECT queries FROM searches WHERE case_id = ? AND entity_id = ?", (case_id, entity_id)):
        for q in s["queries"] or []:
            done.add((q["source"], q["kind"], normalize(q["kind"], q["value"])))
    return done


def suggestions(p, case_id: int, entity_id: int) -> dict[str, Any]:
    """Offene Folgesuchen einer Person: welche neue Kennung, woher, welche Quellen könnten damit suchen."""
    from . import opsec as ops
    from .opsec import EXPOSURE, SOURCE_EXPOSURE

    case = p.get_case(case_id)
    p._entity(case_id, entity_id)  # noqa: SLF001
    lv = ops.level(case["opsec_level"])
    keys = p.api_keys()
    sources = p.all_sources()
    done = _searched(p, case_id, entity_id)
    decided = {(r["kind"], r["normalized"]): r["state"] for r in
               p.db.all("SELECT kind, normalized, state FROM pivots WHERE case_id = ? AND entity_id = ?", (case_id, entity_id))}
    items, dismissed, too_deep = [], 0, 0
    for cand in harvest(p, case_id, entity_id):
        sk = _search_kind(cand["kind"])
        norm = normalize(sk, cand["value"])
        capable = []
        for s in sources:
            if sk not in s.kinds or (s.key, sk, norm) in done:
                continue
            expo = "lokal" if s.local else SOURCE_EXPOSURE.get(s.key, "plattform")
            reason = p.source_unavailable(s, keys)
            blocked = EXPOSURE[expo]["rank"] > lv.max_exposure
            capable.append({"key": s.key, "label": s.label, "exposure": expo, "exposure_label": EXPOSURE[expo]["label"],
                            "usable": not reason and not blocked,
                            "reason": reason or (f"durch OPSEC-Stufe {lv.key} gesperrt" if blocked else ""),
                            "produces": [KIND_LABEL.get(k, k) for k in s.produces]})
        if not any(c["usable"] for c in capable):
            continue
        if decided.get((cand["kind"], cand["normalized"])) == "verworfen":
            dismissed += 1
            continue
        if cand["depth"] > MAX_DEPTH:
            too_deep += 1
            continue
        items.append({**cand, "sources": capable})
    items.sort(key=lambda c: (c["depth"], c["kind"], c["value"].casefold()))
    return {"items": items, "dismissed": dismissed, "too_deep": too_deep, "max_depth": MAX_DEPTH}


def run(p, case_id: int, entity_id: int, kind: str, value: str, source_keys: list[str] | None = None) -> dict[str, Any]:
    """Führt eine freigegebene Folgesuche aus: Kennung übernehmen und nur mit ihr in den gewählten Quellen suchen."""
    from .service import Invalid, current_user

    cand = next((c for c in suggestions(p, case_id, entity_id)["items"] if c["kind"] == kind and c["normalized"] == normalize(kind, value)), None)
    if not cand:
        raise Invalid("Diese Folgesuche ist nicht (mehr) offen – bitte die Vorschläge neu laden.")
    usable = [s["key"] for s in cand["sources"] if s["usable"]]
    chosen = [k for k in (source_keys or usable) if k in usable]
    if not chosen:
        raise Invalid("Keine der gewählten Quellen ist für diese Kennung nutzbar.")
    ident = p.add_identifier(case_id, entity_id, {"kind": kind, "value": cand["value"]}, source=f"Folgesuche aus: {cand['origin']['label']}"[:200])
    if cand["origin"].get("finding_id") and not ident.get("finding_id"):
        p.db.update("identifiers", ident["id"], {"finding_id": cand["origin"]["finding_id"]})
    sk = _search_kind(kind)
    res = p.run_search(case_id, entity_id, chosen, only=(sk, normalize(sk, cand["value"])),
                       pivot={"kind": kind, "value": cand["value"], "depth": cand["depth"], "origin": cand["origin"]})
    _decide(p, case_id, entity_id, cand, "ausgeführt", current_user.get())
    return res


def _decide(p, case_id: int, entity_id: int, cand: dict[str, Any], state: str, user: dict[str, Any] | None) -> None:
    p.db.execute("DELETE FROM pivots WHERE entity_id = ? AND kind = ? AND normalized = ?", (entity_id, cand["kind"], cand["normalized"]))
    p.db.insert("pivots", {"case_id": case_id, "entity_id": entity_id, "kind": cand["kind"], "value": cand["value"], "normalized": cand["normalized"],
                           "state": state, "decided_by": user["display_name"] if user else "System", "decided_at": now_iso()}, returning=False)


def dismiss(p, case_id: int, entity_id: int, kind: str, value: str) -> None:
    from .service import current_user

    p._entity(case_id, entity_id)  # noqa: SLF001
    cand = {"kind": kind, "value": str(value)[:200], "normalized": normalize(kind, value)}
    _decide(p, case_id, entity_id, cand, "verworfen", current_user.get())
    p.log(case_id, "Folgesuche verworfen", f"{KIND_LABEL.get(kind, kind)}: {value}")


def restore(p, case_id: int, entity_id: int) -> int:
    n = int(p.db.scalar("SELECT COUNT(*) AS n FROM pivots WHERE case_id = ? AND entity_id = ? AND state = 'verworfen'", (case_id, entity_id)) or 0)
    p.db.execute("DELETE FROM pivots WHERE case_id = ? AND entity_id = ? AND state = 'verworfen'", (case_id, entity_id))
    return n


def chain(p, case_id: int, finding_id: int) -> list[dict[str, Any]]:
    """Herkunftskette eines Treffers: von der Zielperson über jede Zwischenkennung bis zu diesem Treffer."""
    from .service import NotFound

    f = p.db.one("SELECT * FROM findings WHERE id = ? AND case_id = ?", (finding_id, case_id))
    if not f:
        raise NotFound("Treffer nicht gefunden.")
    steps: list[dict[str, Any]] = []
    seen: set[int] = set()
    entity = p.db.one("SELECT label FROM entities WHERE id = ?", (f["entity_id"],)) if f["entity_id"] else None
    while f and f["id"] not in seen:
        seen.add(f["id"])
        steps.append({"type": "finding", "id": f["id"], "label": f["title"], "source": f["source"], "status": f["status"], "query": f["query"]})
        s = p.db.one("SELECT id, started_at, snapshot, pivot FROM searches WHERE id = ?", (f["search_id"],)) if f["search_id"] else None
        if not s:
            steps.append({"type": "manual", "label": "von Hand erfasst"})
            break
        piv = s.get("pivot") or {}
        steps.append({"type": "search", "id": s["id"], "at": s["started_at"], "egress": (s.get("snapshot") or {}).get("egress", ""),
                      "depth": int(piv.get("depth") or 0)})
        if not piv.get("kind"):
            break
        steps.append({"type": "identifier", "kind": piv["kind"], "kind_label": KIND_LABEL.get(piv["kind"], piv["kind"]), "value": piv.get("value", ""),
                      "from": (piv.get("origin") or {}).get("label", "")})
        parent = (piv.get("origin") or {}).get("finding_id")
        f = p.db.one("SELECT * FROM findings WHERE id = ? AND case_id = ?", (parent, case_id)) if parent else None
    steps.append({"type": "start", "label": entity["label"] if entity else "Fall"})
    return list(reversed(steps))


def routes(p, case_id: int, entity_id: int, want: str) -> list[dict[str, Any]]:
    """„Wie komme ich an X?“ – Quellen, die die gewünschte Art von Kennung liefern, und was sie dafür brauchen."""
    ent = p.get_entity(case_id, entity_id)
    have = {_search_kind(i["kind"]) for i in ent["identifiers"]}
    keys = p.api_keys()
    out = []
    for s in p.all_sources():
        if want not in s.produces:
            continue
        out.append({"key": s.key, "label": s.label, "needs": [KIND_LABEL.get(k, k) for k in s.kinds],
                    "ready": bool(have & set(s.kinds)), "unavailable": p.source_unavailable(s, keys)})
    return sorted(out, key=lambda r: (not r["ready"], bool(r["unavailable"]), r["label"]))
