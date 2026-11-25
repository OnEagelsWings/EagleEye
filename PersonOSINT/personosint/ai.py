"""Schritt 4b – Lokaler KI-Assistent für Dossier-Zusammenfassungen.

Grundsätze:
  * nur lokale Modelle (z. B. Ollama im eigenen Netz) – Falldaten verlassen die Organisation nicht;
    Endpunkte außerhalb privater Netze werden abgelehnt, die Anfrage läuft nie über Proxy/Tor
  * das Modell erhält ausschließlich geprüfte Aussagen mit Kennung [F<id>] und muss jede Aussage belegen
  * jede Fußnote wird geprüft; unbekannte Kennungen und unbelegte Sätze werden markiert
  * ein Entwurf wird erst nach menschlicher Freigabe im Dossier verwendet
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from .db import now_iso


class AiError(Exception):
    pass


def validate_url(url: str) -> str:
    parts = urlsplit((url or "").strip().rstrip("/"))
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise AiError("Adresse bitte als http://host:port angeben, z. B. http://127.0.0.1:11434 oder http://ollama:11434.")
    try:
        ips = {ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(parts.hostname, parts.port or 80)}
    except OSError as exc:
        raise AiError(f"Rechner „{parts.hostname}“ ist nicht auflösbar.") from exc
    if not ips or not all(ip.is_private or ip.is_loopback for ip in ips):
        raise AiError("Aus Datenschutzgründen sind nur lokale KI-Dienste (eigener Rechner oder internes Netz) erlaubt.")
    return f"{parts.scheme}://{parts.netloc}"


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))  # niemals über Proxy/Tor


def _call(url: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 180) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url + path, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    try:
        with _opener().open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise AiError(f"KI-Dienst nicht erreichbar: {getattr(exc, 'reason', exc)}") from exc


def settings(p) -> dict[str, Any]:
    raw = p._setting("ai")  # noqa: SLF001
    cfg = json.loads(raw) if raw else {}
    return {"url": cfg.get("url", ""), "model": cfg.get("model", ""), "enabled": bool(cfg.get("enabled") and cfg.get("url") and cfg.get("model"))}


def save_settings(p, payload: dict[str, Any]) -> dict[str, Any]:
    url = validate_url(payload.get("url", "")) if payload.get("url") else ""
    model = str(payload.get("model") or "").strip()[:100]
    p._set_setting("ai", json.dumps({"url": url, "model": model, "enabled": bool(payload.get("enabled"))}))  # noqa: SLF001
    p.log(None, "KI-Einstellungen geändert", f"{url} · {model} · {'aktiv' if payload.get('enabled') else 'aus'}")
    return settings(p)


def test(p, url: str = "") -> dict[str, Any]:
    url = validate_url(url or settings(p)["url"])
    tags = _call(url, "/api/tags", timeout=10)
    return {"ok": True, "models": [m.get("name") for m in tags.get("models", [])]}


def build_prompt(case: dict[str, Any], facts: list[dict[str, Any]], redflags: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> str:
    lines = []
    for f in facts:
        period = " – ".join(x for x in [f["valid_from"], f["valid_to"]] if x)
        role = (f.get("data") or {}).get("rolle")
        lines.append(f"[F{f['id']}] {f['subject_label']} – {f['predicate_label']}: {f['object_label']}"
                     + (f" ({role})" if role else "") + (f" [{period}]" if period else "") + f" · Bewertung {f['code']} · Quelle {f['source_label']}")
    ctx = []
    for r in redflags[:8]:
        ctx.append(f"- Auffälligkeit ({r['severity']}): {r['label']} – {r['text']}")
    for c in contradictions[:5]:
        ctx.append(f"- Widerspruch: {c['subject']} – {c['predicate_label']}: " + " / ".join(v["value"] for v in c["values"]))
    return (
        "Du unterstützt eine investigative Recherche. Schreibe auf Deutsch eine sachliche, nüchterne Zusammenfassung "
        "(höchstens 180 Wörter, Fließtext, keine Überschriften, keine Aufzählungen).\n"
        "Regeln:\n"
        "1. Verwende ausschließlich die unten aufgeführten geprüften Fakten. Erfinde nichts, ergänze kein Allgemeinwissen.\n"
        "2. Belege JEDEN Satz mit den Kennungen der verwendeten Fakten in eckigen Klammern im Format [F<Nummer>], bei mehreren [F<Nummer>, F<Nummer>].\n"
        "3. Keine Bewertung der Person, keine Vermutungen, keine Schuldzuweisungen. Auffälligkeiten nur als Prüfhinweis nennen.\n"
        "4. Benenne Widersprüche ausdrücklich als ungeklärt.\n\n"
        f"Fall: {case['title']}\n\nGeprüfte Fakten:\n" + "\n".join(lines) +
        ("\n\nKontext (nur nennen, nicht belegen):\n" + "\n".join(ctx) if ctx else "") + "\n\nZusammenfassung:"
    )


def check(text: str, allowed: set[int]) -> dict[str, Any]:
    cited: set[int] = set()
    for group in re.findall(r"\[(F\d+(?:\s*,\s*F?\d+)*)\]", text):
        cited |= {int(x) for x in re.findall(r"\d+", group)}
    unknown = sorted(cited - allowed)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if len(s.strip()) > 15]
    uncited = [s for s in sentences if not re.search(r"\[F\d+", s)]
    return {"cited": sorted(cited), "unknown": unknown, "sentences": len(sentences), "uncited": uncited[:10],
            "ok": not unknown and not uncited and bool(cited)}


def generate(p, case_id: int) -> dict[str, Any]:
    from .service import current_user

    cfg = settings(p)
    if not cfg["enabled"]:
        raise AiError("Der lokale KI-Assistent ist nicht eingerichtet (Verwaltung → KI-Assistent).")
    case = p.get_case(case_id)
    asm = p.assessment(case_id)
    facts = sorted([f for f in asm["facts"] if f["status"] == "bestätigt"], key=lambda f: (f["credibility_final"], f["category"]))[:120]
    if not facts:
        raise AiError("Es gibt noch keine bestätigten Aussagen – die KI arbeitet nur mit geprüften Fakten.")
    prompt = build_prompt(case, facts, asm["redflags"], asm["contradictions"])
    res = _call(validate_url(cfg["url"]), "/api/generate", {"model": cfg["model"], "prompt": prompt, "stream": False,
                                                           "options": {"temperature": 0.1}})
    text = str(res.get("response") or "").strip()
    if not text:
        raise AiError("Das Modell hat keinen Text geliefert.")
    chk = check(text, {f["id"] for f in facts})
    user = current_user.get()
    did = p.db.insert("ai_drafts", {"case_id": case_id, "text": text[:6000], "model": cfg["model"], "facts_used": [f["id"] for f in facts],
                                    "checks": chk, "status": "entwurf", "created_by": user["display_name"] if user else "System", "created_at": now_iso()})
    p.log(case_id, "KI-Entwurf erzeugt", f"Modell {cfg['model']}, {len(facts)} Fakten, Prüfung: {'ok' if chk['ok'] else 'Nacharbeit nötig'}")
    return p.db.one("SELECT * FROM ai_drafts WHERE id = ?", (did,))


def drafts(p, case_id: int) -> list[dict[str, Any]]:
    return p.db.all("SELECT * FROM ai_drafts WHERE case_id = ? ORDER BY id DESC LIMIT 20", (case_id,))


def update_draft(p, case_id: int, draft_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    from .service import Invalid, NotFound, current_user

    d = p.db.one("SELECT * FROM ai_drafts WHERE id = ? AND case_id = ?", (draft_id, case_id))
    if not d:
        raise NotFound("Entwurf nicht gefunden.")
    user = current_user.get()
    values: dict[str, Any] = {}
    if "text" in payload:
        if d["status"] == "freigegeben":
            raise Invalid("Freigegebene Texte können nicht mehr geändert werden – bitte neuen Entwurf erzeugen.")
        values["text"] = str(payload["text"])[:6000]
        values["checks"] = check(values["text"], set(d["facts_used"] or []))
    status = payload.get("status")
    if status:
        if status not in {"freigegeben", "verworfen"}:
            raise Invalid("Status muss freigegeben oder verworfen sein.")
        checks = values.get("checks") or d["checks"]
        if status == "freigegeben":
            if checks.get("unknown"):
                raise Invalid("Der Text verweist auf unbekannte Fakten – bitte korrigieren.")
            if checks.get("uncited") and not payload.get("accept_uncited"):
                raise Invalid("Einige Sätze haben keinen Faktenbeleg. Bitte belegen oder ausdrücklich bestätigen.")
            p.db.execute("UPDATE ai_drafts SET status = 'ersetzt' WHERE case_id = ? AND status = 'freigegeben'", (case_id,))
            values.update({"approved_by": user["display_name"] if user else "System", "approved_at": now_iso()})
        values["status"] = status
    p.db.update("ai_drafts", draft_id, values)
    p.log(case_id, "KI-Entwurf " + (status or "bearbeitet"), f"Entwurf #{draft_id}")
    return p.db.one("SELECT * FROM ai_drafts WHERE id = ?", (draft_id,))


def approved(p, case_id: int) -> dict[str, Any] | None:
    return p.db.one("SELECT * FROM ai_drafts WHERE case_id = ? AND status = 'freigegeben' ORDER BY id DESC LIMIT 1", (case_id,))
