"""Protection classes for findings and documents, and recipient levels for reports.

Recipient levels decide what a working report may contain:

* ``intern``   – everything, as before;
* ``mandant``  – only reviewed findings whose effective class is ``offen``;
* ``behoerde`` – only findings reviewed by a second account, with an unchanged source,
  whose effective class is ``offen`` or ``besonders_schutzwuerdig`` (never ``intern``).

A finding's effective class is the stricter of its own class and its source document's.
Unmarked findings count as ``intern`` (nothing leaves the house by default); unmarked
documents count as ``offen`` (EagleEye stores public sources). Every omission is counted
with its reason, so a report never silently shrinks.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

CLASSES = {
    "offen": "offen",
    "intern": "intern",
    "besonders_schutzwuerdig": "besonders schutzwürdig (Art. 9/10 DSGVO)",
}
LEVELS = {"intern": "intern", "mandant": "Mandant", "behoerde": "Behörde/Gericht"}
ALLOWED = {"intern": set(CLASSES), "mandant": {"offen"}, "behoerde": {"offen", "besonders_schutzwuerdig"}}
DEFAULT = {"finding": "intern", "document": "offen"}
# Strictness for combining finding and document class into the effective class.
_RANK = {"offen": 0, "besonders_schutzwuerdig": 1, "intern": 2}
REVIEWED = {"reviewed_self", "reviewed_second_account"}

TABLE = """CREATE TABLE IF NOT EXISTS marking_492(
    marking_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL,
    object_id TEXT NOT NULL, marking TEXT NOT NULL, reason TEXT NOT NULL,
    set_by TEXT NOT NULL, set_at TEXT NOT NULL, record_hash TEXT NOT NULL)"""


def _hash(row: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS marking_492_object ON marking_492(case_id,object_type,object_id)")
    ctx.db.conn.commit()


def set_marking(ctx, *, case_id: str, object_type: str, object_id: str, marking: str, reason: str, actor: str) -> dict:
    """Append a marking (history is kept; the latest valid entry wins). Caller authorizes."""
    if object_type not in DEFAULT:
        raise ValueError("Unbekannter Objekttyp.")
    if marking not in CLASSES:
        raise ValueError("Unbekannte Schutzklasse.")
    reason = " ".join(str(reason or "").split())
    if not 3 <= len(reason) <= 600:
        raise ValueError("Bitte die Schutzklasse kurz begründen (3–600 Zeichen).")
    row = {"marking_id": "mark492_" + secrets.token_hex(10), "case_id": str(case_id), "object_type": object_type,
           "object_id": str(object_id), "marking": marking, "reason": reason, "set_by": str(actor),
           "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    row["record_hash"] = _hash(row)
    ctx.db.execute("INSERT INTO marking_492 VALUES(" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    ctx.audit.log("marking_set_492", object_type, str(object_id), str(case_id),
                  {"marking": marking, "reason": reason, "truth_determined": False})
    return row


def current(ctx, case_id: str) -> dict[tuple[str, str], dict]:
    """(object_type, object_id) -> latest marking row; damaged rows become 'intern'."""
    out: dict[tuple[str, str], dict] = {}
    for row in ctx.db.all("SELECT * FROM marking_492 WHERE case_id=? ORDER BY rowid", (str(case_id),)):
        row = dict(row)
        if _hash(row) != row["record_hash"]:
            row = {**row, "marking": "intern", "damaged": True}
        out[(row["object_type"], row["object_id"])] = row
    return out


def marking_of(marks: dict, object_type: str, object_id: str) -> tuple[str, bool]:
    """(class, explicitly set?)"""
    row = marks.get((object_type, object_id))
    return (row["marking"], True) if row else (DEFAULT[object_type], False)


def effective(marks: dict, finding: dict) -> str:
    own, _ = marking_of(marks, "finding", finding["finding_id"])
    doc, _ = marking_of(marks, "document", finding["document_id"])
    return own if _RANK[own] >= _RANK[doc] else doc


def select(ctx, case_id: str, findings: list[dict], level: str, source_states: dict[str, str],
           web_ok: dict[str, bool] | None = None) -> tuple[list[dict], dict[str, int]]:
    """Findings allowed for a recipient level, plus counted omission reasons."""
    if level not in LEVELS:
        raise ValueError("Unbekannte Empfängerstufe.")
    marks = current(ctx, case_id)
    kept, omitted = [], {}

    def skip(reason):
        omitted[reason] = omitted.get(reason, 0) + 1

    for finding in findings:
        cls = effective(marks, finding)
        if cls not in ALLOWED[level]:
            skip("Schutzklasse " + CLASSES[cls])
        elif level != "intern" and finding["review_state"] not in REVIEWED:
            skip("nicht geprüft oder verworfen")
        elif level == "behoerde" and finding["review_state"] != "reviewed_second_account":
            skip("nicht von einem zweiten Konto geprüft")
        elif level == "behoerde" and source_states.get(finding["finding_id"]) != "snapshot_match":
            skip("Quelle verändert oder nicht mehr verfügbar")
        elif level == "behoerde" and web_ok is not None and web_ok.get(finding["document_id"]) is False:
            skip("WARC-Datei des Web-Belegs verändert")
        else:
            kept.append(finding)
    return kept, omitted


def report_header(level: str, kept: int, total: int, omitted: dict[str, int]) -> list[str]:
    lines = ["Empfängerstufe: " + LEVELS[level], "",
             f"Enthaltene Arbeitsbefunde: {kept} von {total}.", ""]
    if omitted:
        lines += ["Ausgelassen (ausgewiesen, nicht verschwiegen):", ""]
        lines += [f"- {count} × {reason}" for reason, count in sorted(omitted.items())]
        lines.append("")
    rule = {"intern": "Interner Arbeitsstand mit allen Befunden.",
            "mandant": "Nur geprüfte Befunde mit Schutzklasse „offen“ (Befund und Quelldokument).",
            "behoerde": "Nur von einem zweiten Konto geprüfte Befunde mit unveränderter Quelle; "
                        "besonders schutzwürdige Angaben sind enthalten und gekennzeichnet."}[level]
    return lines + ["Regel dieser Stufe: " + rule, ""]
