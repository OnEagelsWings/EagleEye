"""Billing per mandate: invoices from unbilled time and expenses, cancellation, payment, journal.

* An invoice takes every billable, not cancelled, not yet billed time and expense entry of the
  mandate up to a cut-off date, plus the flat fee once for flat-fee mandates. The entries are
  marked with the invoice, so nothing is billed twice; a billed entry cannot be cancelled.
* Numbers run per year without gaps (``RE-2026-0001``). An issued invoice is never changed or
  deleted: a correction is a cancellation invoice with its own number and negative amounts, which
  frees the entries again.
* An invoice is only issued when the mandatory content of § 14 UStG is available (names and
  addresses, tax number or VAT ID, date, number, period, items, amounts, VAT or the § 19 note).
  Missing data is listed instead of producing an incomplete invoice. The tax rules are
  described, not decided here – details belong with the tax adviser.
* The journal ("Rechnungsausgangsbuch") exports all invoices for accounting.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from . import service as buero

DEFAULTS = {"re_praefix": "RE", "steuernummer": "", "ust_idnr": "", "iban": "", "bic": "", "bank": "",
            "zahlungsziel_tage": "14"}
STATUSES = {"gestellt": "gestellt", "bezahlt": "bezahlt", "storniert": "storniert", "storno": "Stornorechnung"}
TABLE = """CREATE TABLE IF NOT EXISTS buero_invoices(invoice_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
    number TEXT NOT NULL UNIQUE, year INTEGER NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL,
    refers_to TEXT NOT NULL DEFAULT '', issued_on TEXT NOT NULL, due_on TEXT NOT NULL, period_from TEXT NOT NULL,
    period_to TEXT NOT NULL, positions_json TEXT NOT NULL, net_cents INTEGER NOT NULL, vat_rate INTEGER NOT NULL,
    vat_cents INTEGER NOT NULL, gross_cents INTEGER NOT NULL, vat_note TEXT NOT NULL, seller_json TEXT NOT NULL,
    buyer_json TEXT NOT NULL, flat_fee INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, paid_on TEXT NOT NULL DEFAULT '',
    cancelled_by_number TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL,
    created_at TEXT NOT NULL, UNIQUE(year, seq))"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS buero_invoices_case ON buero_invoices(case_id, issued_on)")
    for table in ("buero_time", "buero_expenses"):
        present = {r[1] for r in ctx.db.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "invoice_id" not in present:
            ctx.db.conn.execute(f"ALTER TABLE {table} ADD COLUMN invoice_id TEXT NOT NULL DEFAULT ''")
    ctx.db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- settings

def iban_valid(value: str) -> bool:
    text = re.sub(r"\s+", "", str(value or "")).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", text):
        return False
    digits = "".join(str(int(c, 36)) for c in text[4:] + text[:4])
    return int(digits) % 97 == 1


def settings(ctx) -> dict:
    values = dict(DEFAULTS)
    marks = ",".join("?" for _ in DEFAULTS)
    for row in ctx.db.all(f"SELECT key, value FROM buero_settings WHERE key IN ({marks})", tuple(DEFAULTS)):
        values[row["key"]] = row["value"]
    return values


def save_settings(ctx, user: dict, form: dict) -> dict:
    if not buero._is_admin(user):
        raise PermissionError("Rechnungsangaben ändert die Büroleitung (Administration).")
    values = {
        "re_praefix": buero._text(form.get("re_praefix"), 8, field="Präfix der Rechnungsnummer"),
        "steuernummer": buero._text(form.get("steuernummer"), 40, field="Steuernummer"),
        "ust_idnr": buero._text(form.get("ust_idnr"), 20, field="USt-IdNr.").replace(" ", "").upper(),
        "iban": re.sub(r"\s+", "", str(form.get("iban") or "")).upper(),
        "bic": buero._text(form.get("bic"), 11, field="BIC").replace(" ", "").upper(),
        "bank": buero._text(form.get("bank"), 80, field="Bank"),
        "zahlungsziel_tage": str(form.get("zahlungsziel_tage") or "").strip(),
    }
    if values["re_praefix"] and not re.fullmatch(r"[A-Za-z0-9]{1,8}", values["re_praefix"]):
        raise buero.BueroError("Präfix der Rechnungsnummer: nur Buchstaben und Ziffern.")
    if values["ust_idnr"] and not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{8,12}", values["ust_idnr"]):
        raise buero.BueroError("USt-IdNr.: Länderkennung und Nummer, z. B. DE123456789.")
    if values["ust_idnr"].startswith("DE") and not re.fullmatch(r"DE\d{9}", values["ust_idnr"]):
        raise buero.BueroError("Deutsche USt-IdNr.: DE und 9 Ziffern.")
    if values["iban"] and not iban_valid(values["iban"]):
        raise buero.BueroError("IBAN: Prüfziffer stimmt nicht – bitte Tippfehler prüfen.")
    if values["bic"] and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", values["bic"]):
        raise buero.BueroError("BIC: 8 oder 11 Zeichen, z. B. COBADEFFXXX.")
    if not re.fullmatch(r"\d{1,3}", values["zahlungsziel_tage"]) or not 0 <= int(values["zahlungsziel_tage"]) <= 120:
        raise buero.BueroError("Zahlungsziel: 0 bis 120 Tage.")
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        for key, value in values.items():
            ctx.db.execute("INSERT INTO buero_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) "
                           "DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                           (key, value, user["username"], stamp))
        ctx.audit.log("buero_invoice_settings_saved", "buero_settings", "billing", None, {"keys": sorted(values)})
    return settings(ctx)


# ---------------------------------------------------------------- what is open

def _open_entries(ctx, case_id: str, until: str = "") -> tuple[list[dict], list[dict]]:
    cut = until or "9999-12-31"
    times = [dict(r) for r in ctx.db.all(
        "SELECT * FROM buero_time WHERE case_id=? AND voided_at='' AND billable=1 AND invoice_id='' AND work_date<=? "
        "ORDER BY work_date, created_at", (case_id, cut))]
    spent = [dict(r) for r in ctx.db.all(
        "SELECT * FROM buero_expenses WHERE case_id=? AND voided_at='' AND billable=1 AND invoice_id='' AND spent_on<=? "
        "ORDER BY spent_on, created_at", (case_id, cut))]
    return times, spent


def _flat_fee_open(ctx, case_id: str, row: dict) -> bool:
    if row["fee_model"] != "pauschal" or int(row["flat_fee_cents"]) <= 0:
        return False
    return ctx.db.one("SELECT 1 FROM buero_invoices WHERE case_id=? AND kind='rechnung' AND flat_fee=1 AND status<>'storniert'",
                      (case_id,)) is None


def _positions(row: dict, times: list[dict], spent: list[dict], flat_fee: bool, office: dict) -> list[dict]:
    out = []
    if flat_fee:
        out.append({"text": "Pauschalhonorar gemäß Auftrag", "quantity": "1", "unit_cents": int(row["flat_fee_cents"]),
                    "amount_cents": int(row["flat_fee_cents"])})
    if row["fee_model"] == "stunden":
        rate = int(row["hourly_rate_cents"])
        by_activity: dict[str, int] = {}
        for entry in times:
            by_activity[entry["activity"]] = by_activity.get(entry["activity"], 0) + int(entry["minutes"])
        for activity, minutes in by_activity.items():
            out.append({"text": buero.ACTIVITIES.get(activity, activity), "quantity": buero.hours(minutes),
                        "unit_cents": rate, "amount_cents": round(minutes * rate / 60)})
    km = [e for e in spent if e["kind"] == "km"]
    if km:
        total_km = sum(int(e["km"]) for e in km)
        out.append({"text": "Fahrtkilometer", "quantity": f"{total_km} km", "unit_cents": int(office["km_satz_cent"]),
                    "amount_cents": sum(int(e["amount_cents"]) for e in km)})
    by_kind: dict[str, list[dict]] = {}
    for entry in spent:
        if entry["kind"] != "km":
            by_kind.setdefault(entry["kind"], []).append(entry)
    for kind, entries in by_kind.items():
        out.append({"text": buero.EXPENSE_KINDS.get(kind, kind) + " (Auslage)", "quantity": f"{len(entries)} Posten",
                    "unit_cents": None, "amount_cents": sum(int(e["amount_cents"]) for e in entries)})
    return out


def preview(ctx, user: dict, case_id: str, *, until: str = "") -> dict:
    """What an invoice issued now would contain (nothing is changed)."""
    row = buero.mandate(ctx, user, case_id)
    if row is None:
        raise buero.BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    office = buero.settings(ctx)
    times, spent = _open_entries(ctx, case_id, until)
    flat = _flat_fee_open(ctx, case_id, row)
    positions = _positions(row, times, spent, flat, office)
    net = sum(p["amount_cents"] for p in positions)
    dates = [t["work_date"] for t in times] + [e["spent_on"] for e in spent]
    return {"mandate": row, "times": times, "expenses": spent, "flat_fee": flat, "positions": positions,
            "net_cents": net, "vat": buero.vat(office, net), "period": (min(dates), max(dates)) if dates else ("", "")}


def missing_data(ctx, row: dict) -> list[str]:
    """Mandatory invoice content that is not yet recorded."""
    office, bill = buero.settings(ctx), settings(ctx)
    missing = []
    if not office["firma"]:
        missing.append("Name des Büros (Einstellungen)")
    if not office["anschrift"]:
        missing.append("Anschrift des Büros (Einstellungen)")
    if not bill["steuernummer"] and not bill["ust_idnr"]:
        missing.append("Steuernummer oder USt-IdNr. (Rechnungen → Rechnungsangaben)")
    if not row["client"].get("name"):
        missing.append("Name des Mandanten")
    if not row["client"].get("address"):
        missing.append("Anschrift des Mandanten (Mandant bearbeiten)")
    return missing


# ---------------------------------------------------------------- issue, cancel, pay

def _next(ctx, year: int) -> int:
    row = ctx.db.one("SELECT MAX(seq) AS n FROM buero_invoices WHERE year=?", (year,))
    return int((row or {}).get("n") or 0) + 1


def _number(prefix: str, year: int, seq: int) -> str:
    return (prefix + "-" if prefix else "") + f"{year}-{seq:04d}"


def issue(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    buero._authorize(ctx, user, case_id, "case.manage")
    issued_on = buero.parse_date(form.get("issued_on") or (today or date.today()).isoformat(), "Rechnungsdatum")
    until = buero.parse_date(form.get("until"), "Abrechnen bis", required=False) or issued_on
    if str(form.get("geprueft") or "") not in {"on", "1", "true"}:
        raise buero.BueroError("Bitte bestätigen, dass die Positionen geprüft sind.")
    draft = preview(ctx, user, case_id, until=until)
    row = draft["mandate"]
    if row["status"] in {"anfrage", "abgelehnt"}:
        raise buero.BueroError("Für Anfragen und abgelehnte Aufträge werden keine Rechnungen gestellt.")
    missing = missing_data(ctx, row)
    if missing:
        raise buero.BueroError("Für eine vollständige Rechnung fehlt: " + "; ".join(missing) + ".")
    if not draft["positions"]:
        raise buero.BueroError("Es gibt nichts abzurechnen (keine offenen abrechenbaren Zeiten oder Auslagen).")
    office, bill = buero.settings(ctx), settings(ctx)
    period = draft["period"] if draft["period"][0] else (issued_on, issued_on)
    year = int(issued_on[:4])
    seller = {"firma": office["firma"], "anschrift": office["anschrift"], "kontakt": office["kontakt"],
              "steuernummer": bill["steuernummer"], "ust_idnr": bill["ust_idnr"], "iban": bill["iban"], "bic": bill["bic"],
              "bank": bill["bank"]}
    client = row["client"]
    buyer = {"name": client["name"], "contact_person": client.get("contact_person", ""), "address": client.get("address", "")}
    due_on = (date.fromisoformat(issued_on) + timedelta(days=int(bill["zahlungsziel_tage"]))).isoformat()
    with ctx.db.transaction(immediate=True):
        seq = _next(ctx, year)
        invoice = {"invoice_id": "invoice_" + secrets.token_hex(8), "case_id": case_id,
                   "number": _number(bill["re_praefix"], year, seq), "year": year, "seq": seq, "kind": "rechnung",
                   "refers_to": "", "issued_on": issued_on, "due_on": due_on, "period_from": period[0], "period_to": period[1],
                   "positions_json": json.dumps(draft["positions"], ensure_ascii=False), "net_cents": draft["net_cents"],
                   "vat_rate": draft["vat"]["rate"], "vat_cents": draft["vat"]["vat_cents"],
                   "gross_cents": draft["vat"]["gross_cents"], "vat_note": draft["vat"]["note"],
                   "seller_json": json.dumps(seller, ensure_ascii=False), "buyer_json": json.dumps(buyer, ensure_ascii=False),
                   "flat_fee": 1 if draft["flat_fee"] else 0, "status": "gestellt", "created_by": user["username"],
                   "created_at": _now()}
        ctx.db.execute("INSERT INTO buero_invoices(" + ",".join(invoice) + ") VALUES(" + ",".join("?" for _ in invoice) + ")",
                       tuple(invoice.values()))
        for entry in draft["times"]:
            ctx.db.execute("UPDATE buero_time SET invoice_id=? WHERE entry_id=? AND invoice_id=''",
                           (invoice["invoice_id"], entry["entry_id"]))
        for entry in draft["expenses"]:
            ctx.db.execute("UPDATE buero_expenses SET invoice_id=? WHERE expense_id=? AND invoice_id=''",
                           (invoice["invoice_id"], entry["expense_id"]))
        ctx.audit.log("buero_invoice_issued", "buero_invoice", invoice["invoice_id"], case_id,
                      {"number": invoice["number"], "gross_cents": invoice["gross_cents"],
                       "entries": len(draft["times"]) + len(draft["expenses"])})
    return invoice


def _invoice(ctx, invoice_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM buero_invoices WHERE invoice_id=?", (str(invoice_id),))
    if not row:
        raise buero.BueroError("Rechnung nicht gefunden.")
    return dict(row)


def cancel(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    """Cancellation invoice with its own number; the original keeps its number, entries are freed."""
    buero._authorize(ctx, user, case_id, "case.manage")
    original = _invoice(ctx, str(form.get("invoice_id") or ""))
    if original["case_id"] != case_id or original["kind"] != "rechnung":
        raise buero.BueroError("Rechnung nicht gefunden.")
    if original["status"] == "storniert":
        raise buero.BueroError("Diese Rechnung ist bereits storniert.")
    reason = buero._text(form.get("reason"), 300, field="Grund")
    if len(reason) < 5:
        raise buero.BueroError("Bitte den Grund der Stornierung angeben (mindestens 5 Zeichen).")
    issued_on = (today or date.today()).isoformat()
    year = int(issued_on[:4])
    prefix = settings(ctx)["re_praefix"]
    negated = [{**p, "amount_cents": -int(p["amount_cents"])} for p in json.loads(original["positions_json"])]
    with ctx.db.transaction(immediate=True):
        seq = _next(ctx, year)
        storno = {**original, "invoice_id": "invoice_" + secrets.token_hex(8), "number": _number(prefix, year, seq),
                  "year": year, "seq": seq, "kind": "storno", "refers_to": original["number"], "issued_on": issued_on,
                  "due_on": issued_on, "positions_json": json.dumps(negated, ensure_ascii=False),
                  "net_cents": -int(original["net_cents"]), "vat_cents": -int(original["vat_cents"]),
                  "gross_cents": -int(original["gross_cents"]), "flat_fee": 0, "status": "storno", "paid_on": "",
                  "cancelled_by_number": "", "reason": reason, "created_by": user["username"], "created_at": _now()}
        ctx.db.execute("INSERT INTO buero_invoices(" + ",".join(storno) + ") VALUES(" + ",".join("?" for _ in storno) + ")",
                       tuple(storno.values()))
        ctx.db.execute("UPDATE buero_invoices SET status='storniert', cancelled_by_number=?, reason=? WHERE invoice_id=?",
                       (storno["number"], reason, original["invoice_id"]))
        ctx.db.execute("UPDATE buero_time SET invoice_id='' WHERE invoice_id=?", (original["invoice_id"],))
        ctx.db.execute("UPDATE buero_expenses SET invoice_id='' WHERE invoice_id=?", (original["invoice_id"],))
        ctx.audit.log("buero_invoice_cancelled", "buero_invoice", original["invoice_id"], case_id,
                      {"number": original["number"], "storno": storno["number"]})
    return storno


def mark_paid(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> None:
    buero._authorize(ctx, user, case_id, "case.manage")
    invoice = _invoice(ctx, str(form.get("invoice_id") or ""))
    if invoice["case_id"] != case_id or invoice["kind"] != "rechnung":
        raise buero.BueroError("Rechnung nicht gefunden.")
    if invoice["status"] != "gestellt":
        raise buero.BueroError("Nur gestellte, nicht stornierte Rechnungen können als bezahlt markiert werden.")
    paid_on = buero.parse_date(form.get("paid_on") or (today or date.today()).isoformat(), "Zahlungseingang")
    if paid_on < invoice["issued_on"]:
        raise buero.BueroError("Der Zahlungseingang liegt vor dem Rechnungsdatum.")
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE buero_invoices SET status='bezahlt', paid_on=? WHERE invoice_id=?", (paid_on, invoice["invoice_id"]))
        ctx.audit.log("buero_invoice_paid", "buero_invoice", invoice["invoice_id"], case_id, {"paid_on": paid_on})


# ---------------------------------------------------------------- reading

def _decode(row: dict) -> dict:
    row = dict(row)
    for key in ("positions", "seller", "buyer"):
        row[key] = json.loads(row.pop(key + "_json"))
    return row


def invoices(ctx, user: dict, case_id: str) -> list[dict]:
    buero._authorize(ctx, user, case_id, "case.read")
    return [_decode(r) for r in ctx.db.all("SELECT * FROM buero_invoices WHERE case_id=? ORDER BY year, seq", (case_id,))]


def invoice(ctx, user: dict, invoice_id: str) -> dict:
    row = _invoice(ctx, invoice_id)
    buero._authorize(ctx, user, row["case_id"], "case.read")
    out = _decode(row)
    out["aktenzeichen"] = (ctx.db.one("SELECT aktenzeichen FROM buero_mandates WHERE case_id=?", (row["case_id"],)) or {}).get("aktenzeichen", "")
    out["mandate_title"] = (ctx.db.one("SELECT title FROM cases WHERE case_id=?", (row["case_id"],)) or {}).get("title", "")
    source = row["invoice_id"] if row["kind"] == "rechnung" else ""
    out["times"] = [dict(r) for r in ctx.db.all("SELECT * FROM buero_time WHERE invoice_id=? ORDER BY work_date", (source,))] if source else []
    out["expenses"] = [dict(r) for r in ctx.db.all("SELECT * FROM buero_expenses WHERE invoice_id=? ORDER BY spent_on", (source,))] if source else []
    return out


def journal(ctx, user: dict, year: int) -> list[dict]:
    """All invoices of a year for accounting (office management only)."""
    if not buero._is_admin(user):
        raise PermissionError("Das Rechnungsausgangsbuch sieht die Büroleitung (Administration).")
    out = []
    for r in ctx.db.all("SELECT i.*, m.aktenzeichen FROM buero_invoices i LEFT JOIN buero_mandates m ON m.case_id=i.case_id "
                        "WHERE i.year=? ORDER BY i.seq", (int(year),)):
        out.append(_decode(r))
    return out


def overdue(ctx, user: dict, *, today: date | None = None) -> list[dict]:
    visible = {str(c["case_id"]) for c in buero.visible_cases(ctx, user)}
    iso = (today or date.today()).isoformat()
    return [dict(r) for r in ctx.db.all("SELECT i.invoice_id, i.case_id, i.number, i.due_on, i.gross_cents, m.aktenzeichen "
                                        "FROM buero_invoices i LEFT JOIN buero_mandates m ON m.case_id=i.case_id "
                                        "WHERE i.kind='rechnung' AND i.status='gestellt' AND i.due_on<? ORDER BY i.due_on", (iso,))
            if r["case_id"] in visible]


def open_amounts(ctx, rows: list[dict]) -> dict[str, int]:
    """case_id -> net amount of billable entries not yet invoiced (for the overview)."""
    out = {}
    office = buero.settings(ctx)
    for row in rows:
        times, spent = _open_entries(ctx, row["case_id"])
        positions = _positions(row, times, spent, _flat_fee_open(ctx, row["case_id"], row), office)
        out[row["case_id"]] = sum(p["amount_cents"] for p in positions)
    return out
