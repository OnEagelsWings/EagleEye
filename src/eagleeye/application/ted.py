"""TED (Tenders Electronic Daily): public procurement notices of the EU, anonymous search API v3.

Who bought what from whom: a company as buyer or as winner of public contracts, with date,
value and a link to the official notice. Searches are stored per case for the documentation.
"""
from __future__ import annotations

import json
import re
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable

API = "https://api.ted.europa.eu/v3/notices/search"
USER_AGENT = "EagleEye/500 (Recherche öffentlicher Ausschreibungen)"
PAGE_SIZE = 50
FIELDS = ["publication-number", "notice-title", "publication-date", "buyer-name", "buyer-country",
          "winner-name", "notice-type", "classification-cpv"]
VALUE_FIELDS = ["total-value", "total-value-cur"]  # checked live; kept separate so a rejected field is dropped
ROLES = {"alle": "Überall (Volltext)", "gewinner": "Als Gewinner (Zuschlag)", "auftraggeber": "Als Auftraggeber"}
NOTICE_TYPES = {"can-standard": "Zuschlag", "can-social": "Zuschlag", "can-desg": "Zuschlag (Wettbewerb)",
                "can-tran": "Zuschlag", "can-modif": "Vertragsänderung", "cn-standard": "Ausschreibung",
                "cn-social": "Ausschreibung", "cn-desg": "Wettbewerb", "pin-only": "Vorinformation",
                "pin-buyer": "Vorinformation", "veat": "Freiwillige Ex-ante-Transparenz", "corr": "Berichtigung"}
TABLE = """CREATE TABLE IF NOT EXISTS ted_searches_500(
    search_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, term TEXT NOT NULL, role TEXT NOT NULL, country TEXT NOT NULL,
    date_from TEXT NOT NULL, date_to TEXT NOT NULL, query TEXT NOT NULL, total INTEGER NOT NULL, result_count INTEGER NOT NULL,
    results_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL)"""


class TedError(ValueError):
    """User-facing error of a TED search."""


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS ted_searches_500_case ON ted_searches_500(case_id, created_at)")
    ctx.db.conn.commit()


def _date(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise TedError(f"{label}: bitte als Datum (JJJJ-MM-TT) angeben.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise TedError(f"{label}: kein gültiges Datum.") from None
    return value.replace("-", "")


def build_query(term: str, *, role: str = "alle", country: str = "", date_from: str = "", date_to: str = "") -> str:
    """TED expert query. Names are searched as phrases; the term must not contain quotes or brackets."""
    clean = " ".join(re.sub(r'["()\\]', " ", str(term or "")).split())[:120]
    if len(clean) < 2:
        raise TedError("Bitte einen Firmennamen oder Suchbegriff eingeben.")
    if role not in ROLES:
        raise TedError("Unbekannte Suchart.")
    field = {"alle": "FT", "gewinner": "winner-name", "auftraggeber": "buyer-name"}[role]
    parts = [f'{field} ~ ("{clean}")']
    code = str(country or "").strip().upper()
    if code:
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise TedError("Land bitte als dreistelligen Code angeben (z. B. DEU, AUT, FRA).")
        parts.append(f"buyer-country = {code}")
    start, end = _date(date_from, "Von"), _date(date_to, "Bis")
    if start:
        parts.append(f"publication-date >= {start}")
    if end:
        parts.append(f"publication-date <= {end}")
    if start and end and start > end:
        raise TedError("Das Von-Datum liegt nach dem Bis-Datum.")
    return " AND ".join(parts)


def _post(body: dict) -> dict:
    request = urllib.request.Request(API, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json",
                                              "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", "replace")
        raise TedError(f"TED lehnte die Anfrage ab (HTTP {exc.code}): {detail[:300]}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TedError("TED ist nicht erreichbar: " + str(getattr(exc, "reason", exc))[:150]) from None
    except json.JSONDecodeError:
        raise TedError("TED lieferte keine lesbare Antwort.") from None


def _text(value, prefer=("deu", "eng", "fra")) -> str:
    """TED fields are plain values, lists or language maps ({"deu": [...], "eng": [...]})."""
    if value is None:
        return ""
    if isinstance(value, dict):
        lowered = {str(k).lower(): v for k, v in value.items()}
        for lang in prefer:
            if lang in lowered:
                return _text(lowered[lang], prefer)
        return _text(next(iter(lowered.values()), ""), prefer)
    if isinstance(value, (list, tuple)):
        seen = []
        for item in value:
            text = _text(item, prefer)
            if text and text not in seen:
                seen.append(text)
        return "; ".join(seen)
    return str(value).strip()


def _link(notice: dict) -> str:
    links = notice.get("links") or {}
    for kind in ("html", "htmlDirect", "pdf"):
        group = links.get(kind) or {}
        if isinstance(group, dict):
            for lang in ("DEU", "ENG", "deu", "eng"):
                if group.get(lang):
                    return str(group[lang])
            if group:
                return str(next(iter(group.values())))
    number = _text(notice.get("publication-number"))
    return f"https://ted.europa.eu/de/notice/-/detail/{number}" if number else ""


def parse_notice(notice: dict) -> dict:
    kind = _text(notice.get("notice-type"))
    value = _text(notice.get("total-value"))
    currency = _text(notice.get("total-value-cur"))
    date = _text(notice.get("publication-date"))[:10]
    return {"number": _text(notice.get("publication-number")), "date": date, "title": _text(notice.get("notice-title"))[:300],
            "buyer": _text(notice.get("buyer-name"))[:300], "country": _text(notice.get("buyer-country"))[:40],
            "winner": _text(notice.get("winner-name"))[:400], "type": NOTICE_TYPES.get(kind, kind),
            "cpv": _text(notice.get("classification-cpv"))[:120],
            "value": (value + " " + currency).strip() if value else "", "url": _link(notice)}


def search(ctx, *, user: dict, case_id: str, term: str, role: str = "alle", country: str = "",
           date_from: str = "", date_to: str = "", page: int = 1, post: Callable[[dict], dict] | None = None) -> dict:
    query = build_query(term, role=role, country=country, date_from=date_from, date_to=date_to)
    body = {"query": query, "fields": FIELDS + VALUE_FIELDS, "page": max(1, int(page)), "limit": PAGE_SIZE,
            "scope": "ALL", "paginationMode": "PAGE_NUMBER"}
    send = post or _post
    try:
        data = send(body)
    except TedError as exc:
        if "total-value" not in str(exc):
            raise
        body["fields"] = FIELDS  # value fields unknown to this API version: search without them
        data = send(body)
    notices = [parse_notice(n) for n in (data.get("notices") or []) if isinstance(n, dict)]
    total = int(data.get("totalNoticeCount") or len(notices))
    row = {"search_id": "ted_" + secrets.token_hex(8), "case_id": case_id, "term": " ".join(str(term).split())[:120],
           "role": role, "country": str(country or "").upper(), "date_from": date_from or "", "date_to": date_to or "",
           "query": query, "total": total, "result_count": len(notices),
           "results_json": json.dumps(notices, ensure_ascii=False), "created_by": str(user["username"]),
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO ted_searches_500 VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        ctx.audit.log("ted_search_500", "ted_search", row["search_id"], case_id,
                      {"role": role, "country": row["country"], "total": total, "results": len(notices)})
    return {**row, "results": notices}


def searches(ctx, case_id: str, limit: int = 15) -> list[dict]:
    rows = ctx.db.all("SELECT * FROM ted_searches_500 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit))
    return [{**dict(r), "results": json.loads(r["results_json"] or "[]")} for r in rows]


def search_row(ctx, case_id: str, search_id: str) -> dict | None:
    row = ctx.db.one("SELECT * FROM ted_searches_500 WHERE case_id=? AND search_id=?", (case_id, search_id))
    return {**dict(row), "results": json.loads(row["results_json"] or "[]")} if row else None
