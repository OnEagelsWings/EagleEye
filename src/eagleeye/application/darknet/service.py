"""Darknet research for the case file: Tor connection, source register, search, capture as evidence.

Rules that the code enforces (not just the UI):
- Off until the office lead switches it on and confirms the office instruction.
- A page is only fetched from an onion service in the register with status "freigegeben".
  Anyone with research rights may propose a source; only the office lead releases or blocks it.
- Search goes to Ahmia through Tor (Ahmia filters abuse material). The search term leaves the
  office; the office's IP address does not.
- Saved pages become ordinary evidence (WARC, SHA-256, timestamp, check package, report) of kind
  "darknet". Only text pages: no images, no scripts, no PDFs, no downloads.
- Every step is written to the case audit log.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit

from eagleeye.application.intel492 import captures, webcapture
from eagleeye.application.intel492.webcapture import CaptureError

from . import tor

AHMIA_ONION = "juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion"
MAX_RESULTS = 60
CONFIRMATION = "DARKNET FREIGEBEN"
STATUS = {"vorgeschlagen": "Vorgeschlagen", "freigegeben": "Freigegeben", "gesperrt": "Gesperrt"}
CATEGORIES = {"forum": "Forum", "markt": "Marktplatz", "leak": "Leak-Seite / Datenveröffentlichung", "dienst": "Dienst / Shop",
              "news": "Nachrichten / Blog", "suche": "Suchmaschine / Verzeichnis", "sonstiges": "Sonstiges"}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS darknet_settings_500(
        id INTEGER PRIMARY KEY CHECK (id = 1), enabled INTEGER NOT NULL, socks_port INTEGER NOT NULL,
        changed_by TEXT NOT NULL, changed_at TEXT NOT NULL, note TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS darknet_sources_500(
        source_id TEXT PRIMARY KEY, onion_host TEXT NOT NULL UNIQUE, label TEXT NOT NULL, category TEXT NOT NULL,
        reason TEXT NOT NULL, status TEXT NOT NULL, proposed_by TEXT NOT NULL, proposed_at TEXT NOT NULL,
        decided_by TEXT NOT NULL, decided_at TEXT NOT NULL, decision_note TEXT NOT NULL, case_id TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS darknet_searches_500(
        search_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, query TEXT NOT NULL, engine TEXT NOT NULL,
        result_count INTEGER NOT NULL, results_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS darknet_searches_500_case ON darknet_searches_500(case_id, created_at)",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize(ctx) -> None:
    for statement in SCHEMA:
        ctx.db.conn.execute(statement)
    ctx.db.conn.commit()


def is_lead(user: dict) -> bool:
    return user.get("global_role") == "system_administrator"


# ------------------------------------------------------------------ settings
def settings(ctx) -> dict:
    row = ctx.db.one("SELECT * FROM darknet_settings_500 WHERE id=1")
    if not row:
        return {"enabled": False, "socks_port": tor.DEFAULT_PORT, "changed_by": "", "changed_at": "", "note": ""}
    return {**dict(row), "enabled": bool(row["enabled"])}


def save_settings(ctx, *, user: dict, enabled: bool, socks_port: int, confirmation: str = "", note: str = "") -> dict:
    if not is_lead(user):
        raise PermissionError("Nur die Büroleitung kann das Darknet-Modul ein- oder ausschalten.")
    port = int(socks_port)
    if port not in (9050, 9150) and not 1024 <= port <= 65535:
        raise ValueError("Bitte den Port des Tor-Dienstes angeben (Tor: 9050, Tor Browser: 9150).")
    if enabled and confirmation.strip().upper() != CONFIRMATION:
        raise ValueError(f"Zum Einschalten bitte „{CONFIRMATION}“ eintippen.")
    row = (1, int(bool(enabled)), port, str(user["username"]), _now(), str(note or "")[:500])
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT OR REPLACE INTO darknet_settings_500 VALUES(?,?,?,?,?,?)", row)
        ctx.audit.log("darknet_settings_500", "darknet", "settings", None,
                      {"enabled": bool(enabled), "socks_port": port, "by": user["username"]})
    return settings(ctx)


def require_enabled(ctx) -> dict:
    current = settings(ctx)
    if not current["enabled"]:
        raise PermissionError("Das Darknet-Modul ist ausgeschaltet. Die Büroleitung schaltet es unter „Einstellungen“ ein.")
    return current


def transport(ctx, case_id: str) -> tor.TorTransport:
    """One Tor circuit per case: the isolation key never leaves this computer and changes per case."""
    current = require_enabled(ctx)
    key = hashlib.sha256(("eagleeye-darknet|" + case_id + "|" + str(ctx.db.path)).encode()).hexdigest()[:32]
    return tor.TorTransport(socks_port=current["socks_port"], isolation=key)


# ------------------------------------------------------------------ source register
def sources(ctx, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM darknet_sources_500" + (" WHERE status=?" if status else "") + " ORDER BY status, label"
    return [dict(r) for r in ctx.db.all(sql, (status,) if status else ())]


def source_for_host(ctx, host: str) -> dict | None:
    row = ctx.db.one("SELECT * FROM darknet_sources_500 WHERE onion_host=?", (host,))
    return dict(row) if row else None


def propose_source(ctx, *, user: dict, case_id: str, address: str, label: str, category: str, reason: str) -> dict:
    host = tor.onion_host_of(address)
    if not host:
        raise ValueError("Keine gültige v3-Onion-Adresse (56 Zeichen + .onion, Prüfsumme stimmt nicht).")
    host = host.rsplit(".", 2)[-2] + ".onion"  # register the service, not a subdomain
    label, reason = str(label or "").strip()[:120], str(reason or "").strip()[:1000]
    if len(label) < 2:
        raise ValueError("Bitte einen Namen für die Quelle angeben.")
    if len(reason) < 10:
        raise ValueError("Bitte kurz begründen, wofür die Quelle im Auftrag gebraucht wird.")
    if category not in CATEGORIES:
        raise ValueError("Bitte eine Art der Quelle wählen.")
    existing = source_for_host(ctx, host)
    if existing:
        raise ValueError(f"Diese Adresse ist bereits als „{existing['label']}“ erfasst ({STATUS[existing['status']]}).")
    row = {"source_id": "dn_" + secrets.token_hex(8), "onion_host": host, "label": label, "category": category,
           "reason": reason, "status": "vorgeschlagen", "proposed_by": str(user["username"]), "proposed_at": _now(),
           "decided_by": "", "decided_at": "", "decision_note": "", "case_id": case_id}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO darknet_sources_500 VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        ctx.audit.log("darknet_source_proposed_500", "darknet_source", row["source_id"], case_id,
                      {"onion_host": host, "label": label, "category": category})
    return row


def decide_source(ctx, *, user: dict, source_id: str, status: str, note: str = "") -> dict:
    if not is_lead(user):
        raise PermissionError("Nur die Büroleitung gibt Darknet-Quellen frei oder sperrt sie.")
    if status not in ("freigegeben", "gesperrt"):
        raise ValueError("Unbekannte Entscheidung.")
    row = ctx.db.one("SELECT * FROM darknet_sources_500 WHERE source_id=?", (source_id,))
    if not row:
        raise KeyError(source_id)
    if status == "gesperrt" and len(str(note or "").strip()) < 5:
        raise ValueError("Bitte kurz begründen, warum die Quelle gesperrt wird.")
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE darknet_sources_500 SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE source_id=?",
                       (status, str(user["username"]), _now(), str(note or "")[:500], source_id))
        ctx.audit.log("darknet_source_" + ("released" if status == "freigegeben" else "blocked") + "_500", "darknet_source",
                      source_id, row["case_id"] or None,
                      {"onion_host": row["onion_host"], "own_proposal": row["proposed_by"] == user["username"]})
    return dict(ctx.db.one("SELECT * FROM darknet_sources_500 WHERE source_id=?", (source_id,)))


# ------------------------------------------------------------------ search (Ahmia through Tor)
_RESULT = re.compile(r'<li[^>]*class="[^"]*\bresult\b[^"]*"[^>]*>(.*?)</li>', re.S | re.I)
_HIDDEN = re.compile(r'<input[^>]*type=["\']hidden["\'][^>]*>', re.I)
_ATTR = re.compile(r'(\w+)=["\']([^"\']*)["\']')
_TAG = re.compile(r"<[^>]+>")
_ONION_URL = re.compile(r'https?://[a-z2-7]{56}\.onion[^\s"\'<>]*', re.I)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", fragment))).strip()


def search_form_fields(home_html: str) -> list[tuple[str, str]]:
    """Ahmia's search form carries a changing hidden field that the search request must repeat."""
    fields = []
    for tag in _HIDDEN.findall(home_html):
        attrs = dict((k.lower(), v) for k, v in _ATTR.findall(tag))
        if attrs.get("name"):
            fields.append((attrs["name"], attrs.get("value", "")))
    return fields[:5]


def parse_results(html: str, base: str) -> list[dict]:
    """Result list of an Ahmia result page: title, onion URL, description. Only valid v3 onions."""
    out, seen = [], set()
    for block in _RESULT.findall(html):
        link = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block, re.S | re.I)
        if not link:
            continue
        href = unescape(link.group(1))
        target = parse_qs(urlsplit(urljoin(base, href)).query).get("redirect_url", [href])[0]
        if not target.startswith(("http://", "https://")):
            cite = re.search(r"<cite[^>]*>(.*?)</cite>", block, re.S | re.I)
            target = "http://" + _text(cite.group(1)) if cite else target
        host = tor.onion_host_of(target)
        if not host or target in seen:
            continue
        seen.add(target)
        desc = re.search(r"<p[^>]*>(.*?)</p>", block, re.S | re.I)
        out.append({"title": _text(link.group(2))[:200] or host, "url": target[:500], "host": host,
                    "description": _text(desc.group(1))[:400] if desc else ""})
        if len(out) >= MAX_RESULTS:
            break
    if not out:  # fallback when the layout changes: plain onion links on the page
        for target in dict.fromkeys(_ONION_URL.findall(html)):
            host = tor.onion_host_of(target)
            if host and host != AHMIA_ONION:
                out.append({"title": host, "url": target[:500], "host": host, "description": ""})
            if len(out) >= MAX_RESULTS:
                break
    return out


def search(ctx, *, user: dict, case_id: str, query: str, transport_factory=None) -> dict:
    query = " ".join(str(query or "").split())[:200]
    if len(query) < 2:
        raise ValueError("Bitte einen Suchbegriff eingeben.")
    channel = (transport_factory or (lambda: transport(ctx, case_id)))()
    base = f"http://{AHMIA_ONION}/"
    home = channel.get(base)
    fields = search_form_fields(home.body.decode("utf-8", "replace")) if home.status == 200 else []
    url = base + "search/?q=" + quote_plus(query) + "".join("&" + quote_plus(k) + "=" + quote_plus(v) for k, v in fields)
    page = channel.get(url)
    if page.status != 200:
        raise CaptureError(f"Ahmia antwortete mit HTTP {page.status}.")
    results = parse_results(page.body.decode("utf-8", "replace"), base)
    known = {s["onion_host"]: s for s in sources(ctx)}
    for item in results:
        source = known.get(item["host"])
        item["source_status"] = source["status"] if source else ""
    row = {"search_id": "dns_" + secrets.token_hex(8), "case_id": case_id, "query": query, "engine": "Ahmia (über Tor)",
           "result_count": len(results), "results_json": json.dumps(results, ensure_ascii=False),
           "created_by": str(user["username"]), "created_at": _now()}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO darknet_searches_500 VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
        ctx.audit.log("darknet_search_500", "darknet_search", row["search_id"], case_id,
                      {"query_sha256": hashlib.sha256(query.encode()).hexdigest(), "results": len(results), "engine": "ahmia"})
    return {**row, "results": results}


def searches(ctx, case_id: str, limit: int = 20) -> list[dict]:
    rows = ctx.db.all("SELECT * FROM darknet_searches_500 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit))
    return [{**dict(r), "results": json.loads(r["results_json"] or "[]")} for r in rows]


# ------------------------------------------------------------------ capture as evidence
def capture(ctx, *, user: dict, case_id: str, url: str, transport_factory=None) -> dict:
    clean = tor.normalize_onion_url(url)
    host = urlsplit(clean).hostname or ""
    service_host = host.rsplit(".", 2)[-2] + ".onion"
    source = source_for_host(ctx, service_host)
    if not source or source["status"] != "freigegeben":
        raise PermissionError("Diese Onion-Quelle ist nicht freigegeben. Bitte zuerst vorschlagen und von der Büroleitung freigeben lassen.")
    channel = (transport_factory or (lambda: transport(ctx, case_id)))()
    result = webcapture.capture(clean, transport=channel, kind="Darknet-Seite (Tor)", normalize=tor.normalize_onion_url,
                                allow_pdf=False)
    if result.get("redirect"):
        target = result.get("location") or ""
        raise CaptureError("Die Seite leitet weiter" + (f" nach {target}" if target else "") +
                           ". Weiterleitungen auf andere Dienste werden nicht automatisch gesichert.")
    with ctx.audit.actor_scope(user["username"]):
        row = captures.store_capture(ctx, identity=user, case_id=case_id, result=result, kind="darknet")
        ctx.audit.log("darknet_capture_500", "web_capture", row["capture_id"], case_id,
                      {"source_id": source["source_id"], "onion_host": service_host, "warc_sha256": row["warc_sha256"]})
    return row


def captures_for_case(ctx, case_id: str) -> list[dict]:
    return [r for r in captures.captures_for_case(ctx, case_id, verify=False) if r["kind"] == "darknet"]
