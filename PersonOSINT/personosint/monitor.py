"""Schritt 4a – Überwachung: gespeicherte Suchen laufen regelmäßig und melden nur Neues.

Jede Überwachung läuft im Namen der Person, die sie angelegt hat – mit deren Rechten und unter den
OPSEC-Regeln des Falls (Netzausgang, Briefing, Exposition). Fehlt etwas, wird blockiert und gemeldet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import opsec as ops
from .db import now_iso

INTERVALS = {6: "alle 6 Stunden", 12: "alle 12 Stunden", 24: "täglich", 72: "alle 3 Tage", 168: "wöchentlich"}


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _display(p, case: dict[str, Any]) -> str:
    lv = ops.level(case.get("opsec_level"))
    return case["codename"] if lv.codename and case.get("codename") else case["title"]


def notify(p, user_ids: set[int], case_id: int | None, text: str, link: str = "", kind: str = "info") -> int:
    n = 0
    for uid in user_ids:
        if not uid:
            continue
        p.db.insert("notifications", {"user_id": uid, "case_id": case_id, "ts": now_iso(), "kind": kind, "text": text[:500], "link": link}, returning=False)
        n += 1
    return n


def team_ids(p, case: dict[str, Any]) -> set[int]:
    ids = {i for i in (case.get("owner_id"), case.get("reviewer_id")) if i}
    ids |= {m["user_id"] for m in p.db.all("SELECT user_id FROM case_members WHERE case_id = ?", (case["id"],))}
    active = {u["id"] for u in p.db.all("SELECT id FROM users WHERE active = 1")}
    return ids & active


def create_watch(p, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    from .service import Invalid, current_user

    case = p.get_case(case_id)
    entity_id = int(payload.get("entity_id") or 0)
    p._entity(case_id, entity_id)  # noqa: SLF001
    sources = [s for s in (payload.get("sources") or []) if s in p.source_map()]
    if not sources:
        raise Invalid("Bitte mindestens eine Quelle für die Überwachung wählen.")
    hours = int(payload.get("interval_hours") or 24)
    if hours not in INTERVALS:
        raise Invalid("Ungültiger Abstand.")
    user = current_user.get()
    now = datetime.now(timezone.utc)
    wid = p.db.insert("watches", {"case_id": case_id, "entity_id": entity_id, "sources": sources, "interval_hours": hours, "active": 1,
                                  "created_by": user["id"] if user else None, "created_at": _iso(now), "next_run": _iso(now + timedelta(hours=hours))})
    p.log(case_id, "Überwachung angelegt", f"{len(sources)} Quellen, {INTERVALS[hours]}")
    del case
    return get_watch(p, case_id, wid)


def get_watch(p, case_id: int, wid: int) -> dict[str, Any]:
    from .service import NotFound

    w = p.db.one("SELECT w.*, e.label AS entity_label, u.display_name AS created_by_name FROM watches w JOIN entities e ON e.id = w.entity_id "
                 "LEFT JOIN users u ON u.id = w.created_by WHERE w.id = ? AND w.case_id = ?", (wid, case_id))
    if not w:
        raise NotFound("Überwachung nicht gefunden.")
    w["interval_label"] = INTERVALS.get(w["interval_hours"], f"alle {w['interval_hours']} h")
    return w


def list_watches(p, case_id: int) -> list[dict[str, Any]]:
    return [get_watch(p, case_id, r["id"]) for r in p.db.all("SELECT id FROM watches WHERE case_id = ? ORDER BY id", (case_id,))]


def update_watch(p, case_id: int, wid: int, payload: dict[str, Any]) -> dict[str, Any]:
    from .service import Invalid

    get_watch(p, case_id, wid)
    values: dict[str, Any] = {}
    if "active" in payload:
        values["active"] = 1 if payload["active"] else 0
    if "interval_hours" in payload:
        if int(payload["interval_hours"]) not in INTERVALS:
            raise Invalid("Ungültiger Abstand.")
        values["interval_hours"] = int(payload["interval_hours"])
    p.db.update("watches", wid, values)
    p.log(case_id, "Überwachung geändert", ", ".join(f"{k}={v}" for k, v in values.items()))
    return get_watch(p, case_id, wid)


def delete_watch(p, case_id: int, wid: int) -> None:
    get_watch(p, case_id, wid)
    p.db.execute("DELETE FROM watches WHERE id = ?", (wid,))
    p.log(case_id, "Überwachung gelöscht", f"#{wid}")


def run_watch(p, wid: int) -> dict[str, Any]:
    """Führt eine Überwachung im Namen ihrer Erstellerin bzw. ihres Erstellers aus."""
    from .service import current_user

    w = p.db.one("SELECT * FROM watches WHERE id = ?", (wid,))
    if not w:
        return {"ok": False, "message": "nicht gefunden"}
    case = p.get_case(w["case_id"])
    user = p.db.one("SELECT * FROM users WHERE id = ? AND active = 1", (w["created_by"],)) if w["created_by"] else None
    now = datetime.now(timezone.utc)
    token = current_user.set(user)
    try:
        if case["status"] in {"abgeschlossen", "archiviert"}:
            p.db.update("watches", wid, {"active": 0, "last_result": "Fall abgeschlossen – Überwachung beendet", "last_run": _iso(now)})
            return {"ok": False, "message": "Fall abgeschlossen"}
        if not user or "write" not in p.permissions(case, user):
            raise PermissionError("Die anlegende Person hat keine Bearbeitungsrechte mehr für diesen Fall.")
        res = p.run_search(w["case_id"], w["entity_id"], w["sources"])
        new = res["new_findings"]
        msg = f"{new} neue Treffer, {res.get('new_facts', 0)} neue Aussagen über „{res['egress']}“"
        p.db.update("watches", wid, {"last_run": _iso(now), "next_run": _iso(now + timedelta(hours=w["interval_hours"])), "last_result": msg,
                                     "last_new": new, "runs": w["runs"] + 1})
        if new:
            notify(p, team_ids(p, case), case["id"], f"Überwachung „{_display(p, case)}“: {new} neue Treffer zu prüfen", f"#/case/{case['id']}/search")
        return {"ok": True, "message": msg, "new": new}
    except Exception as exc:  # noqa: BLE001 - OPSEC-Sperren, fehlende Schlüssel, Netzfehler
        msg = f"Blockiert/Fehler: {exc}"
        p.db.update("watches", wid, {"last_run": _iso(now), "next_run": _iso(now + timedelta(hours=w["interval_hours"])), "last_result": msg[:500],
                                     "runs": w["runs"] + 1})
        if w["created_by"]:
            notify(p, {w["created_by"]}, case["id"], f"Überwachung „{_display(p, case)}“ konnte nicht laufen: {exc}"[:500], f"#/case/{case['id']}/search", "warnung")
        return {"ok": False, "message": msg}
    finally:
        current_user.reset(token)


def run_due(p, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    due = p.db.all("SELECT id FROM watches WHERE active = 1 AND next_run <= ? ORDER BY next_run", (_iso(now),))
    for row in due:
        run_watch(p, row["id"])
    return len(due)


def notifications(p, user_id: int, limit: int = 30) -> dict[str, Any]:
    rows = p.db.all("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    unread = int(p.db.scalar("SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND seen = 0", (user_id,)) or 0)
    return {"items": rows, "unread": unread}


def mark_seen(p, user_id: int, ids: list[int] | None = None) -> None:
    if ids:
        p.db.execute(f"UPDATE notifications SET seen = 1 WHERE user_id = ? AND id IN ({', '.join('?' for _ in ids)})", [user_id, *ids])
    else:
        p.db.execute("UPDATE notifications SET seen = 1 WHERE user_id = ?", (user_id,))
