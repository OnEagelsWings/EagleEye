"""Clients, mandates (one per case), mandate screening, time, expenses, deadlines, retention.

Rules that protect the practice and the people it researches:

* A mandate starts as ``anfrage``. Only the mandate screening moves it to ``angenommen``
  (or ``abgelehnt``); research steps that contact the network check this state.
* Warning signals in the screening (relationship to the target, signs that the target
  seeks protection, address search without a documented claim, voluntary disappearance
  of an adult, unchecked client identity) need a written reason of at least 30
  characters from someone who may manage the case.
* A known protection order or information block in favour of the target only allows
  rejection, unless a court or authority is the client.
* Nothing is deleted: wrong time or expense entries are cancelled with a reason and stay
  visible in the history; every change is written to the audit log.

Money is stored in euro cents, durations in minutes, dates as ISO ``YYYY-MM-DD``.
Authorization happens here, not only at the HTTP edge.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

CLIENT_KINDS = {"privat": "Privatperson", "unternehmen": "Unternehmen", "kanzlei": "Rechtsanwaltskanzlei",
                "versicherung": "Versicherung", "behoerde": "Behörde oder Gericht"}
MANDATE_KINDS = {
    "hintergrund": "Hintergrundprüfung (Bewerber, Geschäftspartner)",
    "due_diligence": "Due Diligence / Wirtschaftsauskunft",
    "wirtschaft": "Wirtschaftsermittlung (Betrug, Untreue, Wettbewerb)",
    "person": "Personen- oder Anschriftenermittlung",
    "vermisst": "Vermisstensuche",
    "online": "Online- und Reputationsrecherche",
    "sonstiges": "Sonstiger Auftrag",
}
LEGAL_BASES = {
    "berechtigtes_interesse": "Berechtigtes Interesse des Auftraggebers (Art. 6 Abs. 1 lit. f DSGVO)",
    "rechtsanspruch": "Geltendmachung oder Abwehr von Rechtsansprüchen",
    "vertrag": "Vertrag oder Vertragsanbahnung mit der betroffenen Person",
    "einwilligung": "Einwilligung der betroffenen Person",
    "behoerde": "Auftrag eines Gerichts oder einer Behörde",
    "sonstiges": "Andere Grundlage (bitte erläutern)",
}
STATUSES = {"anfrage": "Anfrage – Prüfung offen", "angenommen": "Angenommen", "in_arbeit": "In Bearbeitung",
            "bericht": "Bericht in Arbeit", "angehalten": "Angehalten – Warnsignal", "abgeschlossen": "Abgeschlossen",
            "abgelehnt": "Abgelehnt"}
OPEN_STATUSES = {"anfrage", "angenommen", "in_arbeit", "bericht", "angehalten"}
ACTIVE_STATUSES = {"angenommen", "in_arbeit", "bericht"}
# Manual transitions; acceptance, rejection and halting have their own actions.
TRANSITIONS = {"angenommen": {"in_arbeit", "abgeschlossen"}, "in_arbeit": {"bericht", "abgeschlossen"},
               "bericht": {"in_arbeit", "abgeschlossen"}, "abgeschlossen": {"in_arbeit"}}
FEE_MODELS = {"stunden": "nach Aufwand (Stundensatz)", "pauschal": "Pauschalhonorar"}
ACTIVITIES = {"recherche": "Recherche", "auswertung": "Auswertung und Analyse", "bericht": "Berichtserstellung",
              "besprechung": "Besprechung mit dem Mandanten", "aussendienst": "Außendienst / Ermittlung vor Ort",
              "fahrt": "Fahrtzeit", "verwaltung": "Verwaltung", "sonstiges": "Sonstiges"}
EXPENSE_KINDS = {"km": "Fahrtkilometer", "gebuehr": "Register- oder Behördengebühr",
                 "datenbank": "Datenbank- oder Auskunfteiabfrage", "reise": "Reise- und Übernachtungskosten",
                 "sonstiges": "Sonstige Auslage"}
VAT_MODES = {"regel": "Umsatzsteuer ausweisen", "kleinunternehmer": "Kleinunternehmer (§ 19 UStG, keine Umsatzsteuer)"}

SCREENING_QUESTIONS = [
    {"key": "beziehung", "warn": "ja", "text": "Besteht oder bestand eine Partnerschaft, Ehe oder enge persönliche "
     "Beziehung zwischen Auftraggeber und Zielperson?"},
    {"key": "schutz", "warn": "ja", "text": "Gibt es Hinweise, dass die Zielperson Schutz sucht (Frauenhaus, "
     "Kontakt- oder Näherungsverbot, Gewaltschutzverfahren, Zeugenschutz)?"},
    {"key": "schutzanordnung", "warn": "ja", "block": True, "text": "Ist eine Schutzanordnung oder Auskunftssperre "
     "zugunsten der Zielperson bekannt?"},
    {"key": "anschrift", "warn": "ja", "text": "Soll vor allem Aufenthaltsort oder Wohnanschrift einer Privatperson "
     "ermittelt werden, ohne belegten Rechtsanspruch (Titel, Verfahren)?"},
    {"key": "vermisst_freiwillig", "warn": "ja", "optional": True, "text": "Nur bei Vermisstensuche: Hat eine "
     "volljährige Person den Kontakt offenbar freiwillig abgebrochen?"},
    {"key": "identitaet", "warn": "nein", "text": "Sind Identität und berechtigtes Interesse des Auftraggebers geprüft?"},
]
ANSWERS = {"ja": "Ja", "nein": "Nein", "unklar": "Unklar", "entfaellt": "Entfällt"}
CHECKLIST = {"ausweis": "Ausweis eingesehen (keine Kopie ohne Rechtsgrundlage)",
             "vollmacht": "Vollmacht oder Firmennachweis liegt vor",
             "anspruch": "Unterlagen zum Anspruch liegen vor (Titel, Vertrag, Anzeige)",
             "zweck": "Zweck ist plausibel und dokumentiert",
             "empfaenger": "Ergebnisempfänger ist festgelegt"}
RECIPIENT_LEVELS = {"mandant": "Mandant", "behoerde": "Behörde oder Gericht", "intern": "nur intern"}
DEFAULT_SETTINGS = {
    "firma": "", "anschrift": "", "kontakt": "", "az_praefix": "", "stundensatz_cent": "0",
    "km_satz_cent": "30", "ust_modus": "regel", "ust_satz": "19", "aufbewahrung_monate": "36",
    "bericht_fusszeile": "Vertraulich – nur für den genannten Empfänger bestimmt.",
}
MIN_REASON = 30

TABLES = [
    """CREATE TABLE IF NOT EXISTS buero_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL,
        updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS buero_clients(client_id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
        contact_person TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
        created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS buero_mandates(case_id TEXT PRIMARY KEY, aktenzeichen TEXT NOT NULL UNIQUE,
        az_year INTEGER NOT NULL, az_number INTEGER NOT NULL, client_id TEXT NOT NULL, kind TEXT NOT NULL,
        legal_basis_key TEXT NOT NULL, received_on TEXT NOT NULL, due_on TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL, fee_model TEXT NOT NULL, hourly_rate_cents INTEGER NOT NULL DEFAULT 0,
        flat_fee_cents INTEGER NOT NULL DEFAULT 0, budget_cents INTEGER NOT NULL DEFAULT 0,
        recipient TEXT NOT NULL DEFAULT '', recipient_level TEXT NOT NULL DEFAULT 'mandant',
        closed_on TEXT NOT NULL DEFAULT '', retention_until TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS buero_screenings(screening_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        answers_json TEXT NOT NULL, checklist_json TEXT NOT NULL, warnings_json TEXT NOT NULL,
        decision TEXT NOT NULL, reason TEXT NOT NULL, decided_by TEXT NOT NULL, decided_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS buero_status_log(entry_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        from_status TEXT NOT NULL, to_status TEXT NOT NULL, note TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS buero_time(entry_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, username TEXT NOT NULL,
        work_date TEXT NOT NULL, minutes INTEGER NOT NULL, activity TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
        billable INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, voided_at TEXT NOT NULL DEFAULT '',
        voided_by TEXT NOT NULL DEFAULT '', void_reason TEXT NOT NULL DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS buero_expenses(expense_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        username TEXT NOT NULL, spent_on TEXT NOT NULL, kind TEXT NOT NULL, km INTEGER NOT NULL DEFAULT 0,
        amount_cents INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', billable INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL, voided_at TEXT NOT NULL DEFAULT '', voided_by TEXT NOT NULL DEFAULT '',
        void_reason TEXT NOT NULL DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS buero_deadlines(deadline_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        due_on TEXT NOT NULL, title TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
        done_at TEXT NOT NULL DEFAULT '', done_by TEXT NOT NULL DEFAULT '')""",
]
INDEXES = ["CREATE INDEX IF NOT EXISTS buero_time_case ON buero_time(case_id, work_date)",
           "CREATE INDEX IF NOT EXISTS buero_expenses_case ON buero_expenses(case_id, spent_on)",
           "CREATE INDEX IF NOT EXISTS buero_deadlines_due ON buero_deadlines(due_on)",
           "CREATE INDEX IF NOT EXISTS buero_mandates_client ON buero_mandates(client_id)",
           "CREATE INDEX IF NOT EXISTS buero_screenings_case ON buero_screenings(case_id, decided_at)"]


class BueroError(ValueError):
    """A user-correctable problem (shown as a readable message, not a crash)."""


class StaleError(BueroError):
    """Somebody else changed the mandate in the meantime."""


# ---------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return prefix + "_" + secrets.token_hex(8)


def _text(value: Any, limit: int, *, field: str = "", required: bool = False) -> str:
    text = " ".join(str(value or "").split()) if limit <= 300 else str(value or "").strip()
    if required and not text:
        raise BueroError(f"Bitte {field} angeben.")
    if len(text) > limit:
        raise BueroError(f"{field or 'Eingabe'} ist zu lang (höchstens {limit} Zeichen).")
    return text


def _choice(value: Any, allowed: dict, field: str) -> str:
    value = str(value or "")
    if value not in allowed:
        raise BueroError(f"Bitte {field} auswählen.")
    return value


def parse_date(value: Any, field: str, *, required: bool = True) -> str:
    value = str(value or "").strip()
    if not value:
        if required:
            raise BueroError(f"Bitte {field} angeben.")
        return ""
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    if match:
        value = f"{match.group(3)}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise BueroError(f"{field}: bitte ein Datum wie 2026-11-16 oder 16.11.2026 angeben.") from None
    if not 2000 <= parsed.year <= 2100:
        raise BueroError(f"{field}: Datum außerhalb des gültigen Bereichs.")
    return parsed.isoformat()


def parse_euro(value: Any, field: str, *, maximum: int = 10_000_000_00) -> int:
    """'85', '85,50', '1.250,00', '1250.5' -> cents. Empty means 0."""
    text = str(value or "").strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not text:
        return 0
    if "," in text or re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "").replace(",", ".")  # German: '.' groups thousands, ',' marks cents
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        raise BueroError(f"{field}: bitte einen Betrag wie 85 oder 85,50 angeben.")
    euros, _, cents = text.partition(".")
    amount = int(euros) * 100 + int((cents + "00")[:2])
    if amount > maximum:
        raise BueroError(f"{field}: Betrag ist unplausibel hoch.")
    return amount


def parse_duration(value: Any) -> int:
    """'1:30', '1,5', '2' (hours), '0:45' -> minutes (1..1440)."""
    text = str(value or "").strip().lower().replace("std", "").replace("h", "").strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if match:
        minutes = int(match.group(1)) * 60 + int(match.group(2))
        if int(match.group(2)) >= 60:
            raise BueroError("Dauer: Minuten müssen unter 60 liegen (z. B. 1:30).")
    elif re.fullmatch(r"\d{1,2}([.,]\d{1,2})?", text):
        minutes = round(float(text.replace(",", ".")) * 60)
    else:
        raise BueroError("Dauer: bitte Stunden wie 1,5 oder 1:30 angeben.")
    if not 1 <= minutes <= 24 * 60:
        raise BueroError("Dauer: zwischen 1 Minute und 24 Stunden.")
    return minutes


def euro(cents: int) -> str:
    """12345 -> '123,45 €' (German format with thousands separator)."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    whole = f"{cents // 100:,}".replace(",", ".")
    return f"{sign}{whole},{cents % 100:02d} €"


def hours(minutes: int) -> str:
    """95 -> '1:35 Std.'"""
    return f"{int(minutes) // 60}:{int(minutes) % 60:02d} Std."


def _today(today: date | None) -> date:
    return today or date.today()


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    for candidate in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, candidate))
        except ValueError:
            continue
    raise AssertionError("unreachable")


def _is_admin(user: dict) -> bool:
    return user.get("global_role") == "system_administrator"


def _caps(ctx, user: dict, case_id: str) -> set[str]:
    return set(ctx.team_governance_359.effective_capabilities(user, case_id))


def _authorize(ctx, user: dict, case_id: str, capability: str) -> None:
    try:
        ctx.team_governance_359.authorize(user, case_id=case_id, capability=capability,
                                          object_type="buero_mandate", object_id=case_id)
    except PermissionError as exc:
        raise PermissionError("Für diesen Auftrag fehlt die Berechtigung.") from exc


def _require_any(ctx, user: dict, case_id: str, capabilities: Iterable[str]) -> None:
    caps = _caps(ctx, user, case_id)
    wanted = list(capabilities)
    for capability in wanted:
        if capability in caps:
            _authorize(ctx, user, case_id, capability)
            return
    _authorize(ctx, user, case_id, wanted[0])  # records the denial and raises


def may_manage(ctx, user: dict, case_id: str) -> bool:
    return "case.manage" in _caps(ctx, user, case_id)


def may_book(ctx, user: dict, case_id: str) -> bool:
    return bool({"research.run", "dossier.write", "case.manage"} & _caps(ctx, user, case_id))


def may_use_clients(user: dict) -> bool:
    return user.get("global_role") in {"system_administrator", "investigator"}


def _audit(ctx, action: str, object_type: str, object_id: str, case_id: str | None, details: dict) -> None:
    ctx.audit.log(action, object_type, object_id, case_id, details)


# ---------------------------------------------------------------- setup and settings

def initialize(ctx) -> None:
    for statement in TABLES + INDEXES:
        ctx.db.conn.execute(statement)
    ctx.db.conn.commit()


def settings(ctx) -> dict[str, str]:
    values = dict(DEFAULT_SETTINGS)
    for row in ctx.db.all("SELECT key, value FROM buero_settings"):
        if row["key"] in values:
            values[row["key"]] = row["value"]
    return values


def save_settings(ctx, user: dict, form: dict) -> dict[str, str]:
    if not _is_admin(user):
        raise PermissionError("Nur die Büroleitung (Administration) ändert die Büroeinstellungen.")
    values = {
        "firma": _text(form.get("firma"), 120, field="Name des Büros"),
        "anschrift": _text(form.get("anschrift"), 400, field="Anschrift"),
        "kontakt": _text(form.get("kontakt"), 200, field="Kontakt"),
        "az_praefix": _text(form.get("az_praefix"), 12, field="Aktenzeichen-Präfix"),
        "stundensatz_cent": str(parse_euro(form.get("stundensatz"), "Stundensatz", maximum=1000_00)),
        "km_satz_cent": str(parse_euro(form.get("km_satz"), "Kilometersatz", maximum=5_00)),
        "ust_modus": _choice(form.get("ust_modus"), VAT_MODES, "die Umsatzsteuer-Regel"),
        "ust_satz": str(form.get("ust_satz") or "19").strip(),
        "aufbewahrung_monate": str(form.get("aufbewahrung_monate") or "").strip(),
        "bericht_fusszeile": _text(form.get("bericht_fusszeile"), 200, field="Fußzeile"),
    }
    if values["az_praefix"] and not re.fullmatch(r"[A-Za-z0-9ÄÖÜäöü]{1,12}", values["az_praefix"]):
        raise BueroError("Aktenzeichen-Präfix: nur Buchstaben und Ziffern, ohne Leerzeichen.")
    if not re.fullmatch(r"\d{1,2}", values["ust_satz"]) or not 0 <= int(values["ust_satz"]) <= 30:
        raise BueroError("Umsatzsteuersatz: ganze Zahl zwischen 0 und 30.")
    if not re.fullmatch(r"\d{1,3}", values["aufbewahrung_monate"]) or not 1 <= int(values["aufbewahrung_monate"]) <= 240:
        raise BueroError("Aufbewahrung: Anzahl Monate zwischen 1 und 240.")
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        for key, value in values.items():
            ctx.db.execute("INSERT INTO buero_settings(key,value,updated_by,updated_at) VALUES(?,?,?,?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_by=excluded.updated_by, "
                           "updated_at=excluded.updated_at", (key, value, user["username"], stamp))
        _audit(ctx, "buero_settings_saved", "buero_settings", "office", None, {"keys": sorted(values)})
    return settings(ctx)


# ---------------------------------------------------------------- clients

def _client_values(form: dict) -> dict:
    return {
        "kind": _choice(form.get("kind"), CLIENT_KINDS, "die Art des Mandanten"),
        "name": _text(form.get("name"), 160, field="den Namen des Mandanten", required=True),
        "contact_person": _text(form.get("contact_person"), 160, field="Ansprechpartner"),
        "address": _text(form.get("address"), 400, field="Anschrift"),
        "email": _text(form.get("email"), 160, field="E-Mail"),
        "phone": _text(form.get("phone"), 60, field="Telefon"),
        "notes": _text(form.get("notes"), 2000, field="Notizen"),
    }


def save_client(ctx, user: dict, form: dict, client_id: str = "") -> dict:
    if not may_use_clients(user):
        raise PermissionError("Die Mandantenliste ist der Büroleitung und Ermittlern vorbehalten.")
    values = _client_values(form)
    if values["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        raise BueroError("E-Mail: bitte eine gültige Adresse angeben.")
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        if client_id:
            if not ctx.db.one("SELECT 1 FROM buero_clients WHERE client_id=?", (client_id,)):
                raise BueroError("Mandant nicht gefunden.")
            ctx.db.execute("UPDATE buero_clients SET kind=?, name=?, contact_person=?, address=?, email=?, phone=?, "
                           "notes=?, updated_at=? WHERE client_id=?", (*values.values(), stamp, client_id))
            _audit(ctx, "buero_client_updated", "buero_client", client_id, None, {"kind": values["kind"]})
        else:
            client_id = _id("client")
            ctx.db.execute("INSERT INTO buero_clients(client_id,kind,name,contact_person,address,email,phone,notes,"
                           "archived,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,0,?,?,?)",
                           (client_id, *values.values(), user["username"], stamp, stamp))
            _audit(ctx, "buero_client_created", "buero_client", client_id, None, {"kind": values["kind"]})
    return client(ctx, user, client_id)


def clients(ctx, user: dict) -> list[dict]:
    if not may_use_clients(user):
        raise PermissionError("Die Mandantenliste ist der Büroleitung und Ermittlern vorbehalten.")
    rows = ctx.db.all("SELECT c.*, (SELECT COUNT(*) FROM buero_mandates m WHERE m.client_id=c.client_id) AS mandates "
                      "FROM buero_clients c ORDER BY c.archived, lower(c.name)")
    return [dict(row) for row in rows]


def client(ctx, user: dict, client_id: str) -> dict:
    if not may_use_clients(user):
        raise PermissionError("Die Mandantenliste ist der Büroleitung und Ermittlern vorbehalten.")
    row = ctx.db.one("SELECT * FROM buero_clients WHERE client_id=?", (str(client_id),))
    if not row:
        raise BueroError("Mandant nicht gefunden.")
    return dict(row)


def _client_row(ctx, client_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM buero_clients WHERE client_id=?", (client_id,))
    return dict(row) if row else {"client_id": client_id, "name": "(unbekannt)", "kind": "privat"}


# ---------------------------------------------------------------- mandates

def visible_cases(ctx, user: dict) -> list[dict]:
    qualification = {str(r["case_id"]) for r in ctx.db.all("SELECT case_id FROM phase20_qualification_case_450")} \
        if ctx.db.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase20_qualification_case_450'") else set()
    return [dict(c) for c in ctx.team_governance_359.visible_cases(user) if str(c["case_id"]) not in qualification]


def _next_number(ctx, year: int) -> int:
    row = ctx.db.one("SELECT MAX(az_number) AS n FROM buero_mandates WHERE az_year=?", (year,))
    return int((row or {}).get("n") or 0) + 1


def _aktenzeichen(prefix: str, year: int, number: int) -> str:
    return (prefix + "-" if prefix else "") + f"{year}-{number:04d}"


def _mandate_values(ctx, form: dict, office: dict) -> dict:
    fee_model = _choice(form.get("fee_model") or "stunden", FEE_MODELS, "das Honorarmodell")
    rate = form.get("hourly_rate")
    values = {
        "kind": _choice(form.get("kind"), MANDATE_KINDS, "die Auftragsart"),
        "legal_basis_key": _choice(form.get("legal_basis_key"), LEGAL_BASES, "die Rechtsgrundlage"),
        "received_on": parse_date(form.get("received_on") or date.today().isoformat(), "Eingangsdatum"),
        "due_on": parse_date(form.get("due_on"), "Abgabefrist", required=False),
        "fee_model": fee_model,
        "hourly_rate_cents": parse_euro(rate, "Stundensatz", maximum=1000_00) if str(rate or "").strip()
        else int(office["stundensatz_cent"]),
        "flat_fee_cents": parse_euro(form.get("flat_fee"), "Pauschale"),
        "budget_cents": parse_euro(form.get("budget"), "Budget-Obergrenze"),
        "recipient": _text(form.get("recipient"), 200, field="Ergebnisempfänger"),
        "recipient_level": _choice(form.get("recipient_level") or "mandant", RECIPIENT_LEVELS, "die Empfängerstufe"),
    }
    if fee_model == "pauschal" and values["flat_fee_cents"] <= 0:
        raise BueroError("Pauschalhonorar: bitte den Betrag angeben.")
    if values["due_on"] and values["due_on"] < values["received_on"]:
        raise BueroError("Die Abgabefrist liegt vor dem Eingangsdatum.")
    return values


def _legal_basis_text(key: str, note: str) -> str:
    return LEGAL_BASES[key] + (" – " + note if note else "")


def create_mandate(ctx, user: dict, form: dict) -> dict:
    """Create the case and its mandate in one step. Returns the mandate."""
    ctx.team_identity_359.require_global(user, "case.create")
    office = settings(ctx)
    title = _text(form.get("title"), 160, field="einen Titel für den Auftrag", required=True)
    purpose = _text(form.get("purpose"), 3000, field="Auftrag und Zweck", required=True)
    note = _text(form.get("legal_basis_note"), 600, field="Erläuterung zur Rechtsgrundlage")
    values = _mandate_values(ctx, form, office)
    if values["legal_basis_key"] == "sonstiges" and len(note) < 10:
        raise BueroError("Bei „Andere Grundlage“ bitte die Rechtsgrundlage erläutern (mindestens 10 Zeichen).")
    client_id = str(form.get("client_id") or "")
    if client_id == "neu" or not client_id:
        new_client = save_client(ctx, user, {k[len("client_"):]: v for k, v in form.items() if k.startswith("client_")})
        client_id = new_client["client_id"]
    else:
        client(ctx, user, client_id)
    client_name = _client_row(ctx, client_id)["name"]
    case = ctx.team_governance_359.create_case(identity=user, title=title, client=client_name, purpose=purpose,
                                               legal_basis=_legal_basis_text(values["legal_basis_key"], note))
    case_id = str(case["case_id"])
    stamp = _now()
    year = int(values["received_on"][:4])
    with ctx.db.transaction(immediate=True):
        number = _next_number(ctx, year)
        row = {"case_id": case_id, "aktenzeichen": _aktenzeichen(office["az_praefix"], year, number), "az_year": year,
               "az_number": number, "client_id": client_id, **values, "status": "anfrage", "closed_on": "",
               "retention_until": "", "version": 1, "created_by": user["username"], "created_at": stamp,
               "updated_at": stamp}
        ctx.db.execute("INSERT INTO buero_mandates(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        _log_status(ctx, case_id, "", "anfrage", "Auftrag angelegt", user["username"])
        _audit(ctx, "buero_mandate_created", "buero_mandate", case_id, case_id,
               {"aktenzeichen": row["aktenzeichen"], "kind": values["kind"], "client_id": client_id})
    return mandate(ctx, user, case_id)


def attach_mandate(ctx, user: dict, case_id: str, form: dict) -> dict:
    """Give an existing case (created before the office module) its mandate data."""
    _authorize(ctx, user, case_id, "case.manage")
    if not case_exists(ctx, case_id):
        raise BueroError("Fall nicht gefunden.")
    if ctx.db.one("SELECT 1 FROM buero_mandates WHERE case_id=?", (case_id,)):
        raise BueroError("Dieser Fall hat bereits Auftragsdaten.")
    office = settings(ctx)
    values = _mandate_values(ctx, form, office)
    client_id = str(form.get("client_id") or "")
    if client_id == "neu" or not client_id:
        client_id = save_client(ctx, user, {k[len("client_"):]: v for k, v in form.items()
                                            if k.startswith("client_")})["client_id"]
    else:
        client(ctx, user, client_id)
    stamp = _now()
    year = int(values["received_on"][:4])
    with ctx.db.transaction(immediate=True):
        number = _next_number(ctx, year)
        row = {"case_id": case_id, "aktenzeichen": _aktenzeichen(office["az_praefix"], year, number), "az_year": year,
               "az_number": number, "client_id": client_id, **values, "status": "anfrage", "closed_on": "",
               "retention_until": "", "version": 1, "created_by": user["username"], "created_at": stamp,
               "updated_at": stamp}
        ctx.db.execute("INSERT INTO buero_mandates(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        _log_status(ctx, case_id, "", "anfrage", "Auftragsdaten zu bestehendem Fall ergänzt", user["username"])
        _audit(ctx, "buero_mandate_attached", "buero_mandate", case_id, case_id, {"aktenzeichen": row["aktenzeichen"]})
    return mandate(ctx, user, case_id)


def update_mandate(ctx, user: dict, case_id: str, form: dict) -> dict:
    _authorize(ctx, user, case_id, "case.manage")
    current = _mandate_row(ctx, case_id)
    _check_version(current, form)
    values = _mandate_values(ctx, {**form, "received_on": form.get("received_on") or current["received_on"]}, settings(ctx))
    client_id = str(form.get("client_id") or current["client_id"])
    if client_id != current["client_id"]:
        client(ctx, user, client_id)
    note = _text(form.get("legal_basis_note"), 600, field="Erläuterung zur Rechtsgrundlage")
    if values["legal_basis_key"] == "sonstiges" and len(note) < 10:
        raise BueroError("Bei „Andere Grundlage“ bitte die Rechtsgrundlage erläutern (mindestens 10 Zeichen).")
    with ctx.db.transaction(immediate=True):
        if values["legal_basis_key"] != current["legal_basis_key"] or note:
            ctx.db.execute("UPDATE cases SET legal_basis=?, updated_at=? WHERE case_id=?",
                           (_legal_basis_text(values["legal_basis_key"], note), _now(), case_id))
        changed = ctx.db.execute(
            "UPDATE buero_mandates SET client_id=?, kind=?, legal_basis_key=?, received_on=?, due_on=?, fee_model=?, "
            "hourly_rate_cents=?, flat_fee_cents=?, budget_cents=?, recipient=?, recipient_level=?, "
            "version=version+1, updated_at=? WHERE case_id=? AND version=?",
            (client_id, *values.values(), _now(), case_id, current["version"])).rowcount
        if changed != 1:
            raise StaleError("Der Auftrag wurde inzwischen geändert. Bitte die Seite neu laden.")
        _audit(ctx, "buero_mandate_updated", "buero_mandate", case_id, case_id,
               {"fields": sorted(values), "client_changed": client_id != current["client_id"]})
    return mandate(ctx, user, case_id)


def case_exists(ctx, case_id: str) -> bool:
    return ctx.db.one("SELECT 1 FROM cases WHERE case_id=?", (str(case_id),)) is not None


def _mandate_row(ctx, case_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM buero_mandates WHERE case_id=?", (str(case_id),))
    if not row:
        raise BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    return dict(row)


def _check_version(current: dict, form: dict) -> None:
    expected = str(form.get("version") or "")
    if expected and expected != str(current["version"]):
        raise StaleError("Der Auftrag wurde inzwischen geändert. Bitte die Seite neu laden.")


def mandate_state(ctx, case_id: str) -> str:
    """Status without authorization (for gates inside already authorized requests); '' if no mandate."""
    row = ctx.db.one("SELECT status FROM buero_mandates WHERE case_id=?", (str(case_id),))
    return str(row["status"]) if row else ""


def mandate(ctx, user: dict, case_id: str) -> dict | None:
    _authorize(ctx, user, case_id, "case.read")
    row = ctx.db.one("SELECT * FROM buero_mandates WHERE case_id=?", (str(case_id),))
    if not row:
        return None
    out = dict(row)
    out["client"] = _client_row(ctx, out["client_id"])
    case = ctx.db.one("SELECT title, purpose, legal_basis FROM cases WHERE case_id=?", (case_id,)) or {}
    out.update({"title": case.get("title", ""), "purpose": case.get("purpose", ""), "legal_basis": case.get("legal_basis", "")})
    out["screening"] = latest_screening(ctx, case_id)
    out["totals"] = totals(ctx, case_id, out)
    return out


def mandates(ctx, user: dict) -> list[dict]:
    cases = {str(c["case_id"]): c for c in visible_cases(ctx, user)}
    if not cases:
        return []
    marks = ",".join("?" for _ in cases)
    rows = [dict(r) for r in ctx.db.all(f"SELECT * FROM buero_mandates WHERE case_id IN ({marks}) "
                                        "ORDER BY az_year DESC, az_number DESC", tuple(cases))]
    minutes = {r["case_id"]: r for r in ctx.db.all(
        f"SELECT case_id, SUM(minutes) AS minutes, SUM(CASE WHEN billable=1 THEN minutes ELSE 0 END) AS billable "
        f"FROM buero_time WHERE voided_at='' AND case_id IN ({marks}) GROUP BY case_id", tuple(cases))}
    spent = {r["case_id"]: r for r in ctx.db.all(
        f"SELECT case_id, SUM(CASE WHEN billable=1 THEN amount_cents ELSE 0 END) AS amount FROM buero_expenses "
        f"WHERE voided_at='' AND case_id IN ({marks}) GROUP BY case_id", tuple(cases))}
    client_names = {r["client_id"]: r["name"] for r in ctx.db.all("SELECT client_id, name FROM buero_clients")}
    for row in rows:
        case = cases[row["case_id"]]
        row["title"] = case.get("title", "")
        row["client_name"] = client_names.get(row["client_id"], "(unbekannt)")
        m = minutes.get(row["case_id"]) or {}
        row["totals"] = _totals(row, int(m.get("minutes") or 0), int(m.get("billable") or 0),
                                int((spent.get(row["case_id"]) or {}).get("amount") or 0))
    return rows


def cases_without_mandate(ctx, user: dict) -> list[dict]:
    known = {r["case_id"] for r in ctx.db.all("SELECT case_id FROM buero_mandates")}
    return [c for c in visible_cases(ctx, user) if str(c["case_id"]) not in known]


# ---------------------------------------------------------------- screening and status

def latest_screening(ctx, case_id: str) -> dict | None:
    import json
    row = ctx.db.one("SELECT * FROM buero_screenings WHERE case_id=? ORDER BY decided_at DESC, rowid DESC LIMIT 1",
                     (str(case_id),))
    if not row:
        return None
    out = dict(row)
    for key in ("answers", "checklist", "warnings"):
        out[key] = json.loads(out.pop(key + "_json"))
    return out


def evaluate_screening(answers: dict, client_kind: str, mandate_kind: str) -> dict:
    """Warnings and whether acceptance is blocked. Pure function, used by the form preview too."""
    warnings, blocked = [], False
    for question in SCREENING_QUESTIONS:
        answer = str(answers.get(question["key"]) or "")
        if question.get("optional") and mandate_kind != "vermisst":
            continue
        if answer not in ANSWERS or answer == "entfaellt":  # 'entfällt' only for questions that do not apply
            raise BueroError("Bitte jede Frage der Auftragsprüfung beantworten.")
        if answer == question["warn"] or answer == "unklar":
            warnings.append(question["key"])
            if question.get("block") and answer == "ja" and client_kind != "behoerde":
                blocked = True
    return {"warnings": warnings, "blocked": blocked}


def screen(ctx, user: dict, case_id: str, form: dict) -> dict:
    """Record the mandate screening and the decision (annehmen / ablehnen)."""
    import json
    _authorize(ctx, user, case_id, "case.manage")
    current = _mandate_row(ctx, case_id)
    _check_version(current, form)
    if current["status"] not in {"anfrage", "angehalten"}:
        raise BueroError("Die Auftragsprüfung ist nur für neue oder angehaltene Aufträge vorgesehen.")
    answers = {q["key"]: str(form.get("q_" + q["key"]) or "") for q in SCREENING_QUESTIONS}
    checklist = sorted(k for k in CHECKLIST if str(form.get("c_" + k) or "") in {"1", "on", "true"})
    decision = _choice(form.get("decision"), {"annehmen": 1, "ablehnen": 1}, "eine Entscheidung")
    reason = _text(form.get("reason"), 2000, field="Begründung")
    client_kind = _client_row(ctx, current["client_id"])["kind"]
    result = evaluate_screening(answers, client_kind, current["kind"])
    if decision == "annehmen" and result["blocked"]:
        raise BueroError("Annahme nicht möglich: Eine Schutzanordnung oder Auskunftssperre ist bekannt und der "
                         "Auftrag kommt nicht von einem Gericht oder einer Behörde. Bitte ablehnen.")
    if (result["warnings"] or decision == "ablehnen" or current["status"] == "angehalten") and len(reason) < MIN_REASON:
        raise BueroError(f"Bitte die Entscheidung schriftlich begründen (mindestens {MIN_REASON} Zeichen).")
    target = ("in_arbeit" if current["status"] == "angehalten" else "angenommen") if decision == "annehmen" else "abgelehnt"
    closed_on, retention = "", ""
    if target == "abgelehnt":  # the rejection is documented, then deleted like any closed file
        day = date.today()
        closed_on = day.isoformat()
        retention = _add_months(day, int(settings(ctx)["aufbewahrung_monate"])).isoformat()
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        changed = ctx.db.execute("UPDATE buero_mandates SET status=?, closed_on=?, retention_until=?, version=version+1, "
                                 "updated_at=? WHERE case_id=? AND version=?",
                                 (target, closed_on, retention, stamp, case_id, current["version"])).rowcount
        if changed != 1:
            raise StaleError("Der Auftrag wurde inzwischen geändert. Bitte die Seite neu laden.")
        screening_id = _id("screen")
        ctx.db.execute("INSERT INTO buero_screenings VALUES(?,?,?,?,?,?,?,?,?)",
                       (screening_id, case_id, json.dumps(answers, sort_keys=True), json.dumps(checklist),
                        json.dumps(result["warnings"]), decision, reason, user["username"], stamp))
        _log_status(ctx, case_id, current["status"], target, "Auftragsprüfung: " + decision, user["username"])
        _audit(ctx, "buero_screening_decided", "buero_mandate", case_id, case_id,
               {"decision": decision, "warnings": result["warnings"], "blocked": result["blocked"],
                "checklist": checklist})
    return latest_screening(ctx, case_id)


def _log_status(ctx, case_id: str, old: str, new: str, note: str, actor: str) -> None:
    ctx.db.execute("INSERT INTO buero_status_log VALUES(?,?,?,?,?,?,?)",
                   (_id("status"), case_id, old, new, note, actor, _now()))


def status_log(ctx, user: dict, case_id: str) -> list[dict]:
    _authorize(ctx, user, case_id, "case.read")
    return [dict(r) for r in ctx.db.all("SELECT * FROM buero_status_log WHERE case_id=? ORDER BY at, rowid", (case_id,))]


def set_status(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    _authorize(ctx, user, case_id, "case.manage")
    current = _mandate_row(ctx, case_id)
    _check_version(current, form)
    target = _choice(form.get("status"), STATUSES, "den neuen Stand")
    if target not in TRANSITIONS.get(current["status"], set()):
        raise BueroError(f"Von „{STATUSES[current['status']]}“ geht es nicht direkt zu „{STATUSES[target]}“.")
    note = _text(form.get("note"), 600, field="Notiz")
    if current["status"] == "abgeschlossen" and len(note) < 10:
        raise BueroError("Zum Wiedereröffnen bitte kurz begründen (mindestens 10 Zeichen).")
    closed_on, retention = current["closed_on"], current["retention_until"]
    if target == "abgeschlossen":
        day = _today(today)
        closed_on = day.isoformat()
        retention = _add_months(day, int(settings(ctx)["aufbewahrung_monate"])).isoformat()
    elif current["status"] == "abgeschlossen":
        closed_on, retention = "", ""
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        changed = ctx.db.execute("UPDATE buero_mandates SET status=?, closed_on=?, retention_until=?, "
                                 "version=version+1, updated_at=? WHERE case_id=? AND version=?",
                                 (target, closed_on, retention, stamp, case_id, current["version"])).rowcount
        if changed != 1:
            raise StaleError("Der Auftrag wurde inzwischen geändert. Bitte die Seite neu laden.")
        ctx.db.execute("UPDATE cases SET retention_until=?, updated_at=? WHERE case_id=?", (retention, stamp, case_id))
        _log_status(ctx, case_id, current["status"], target, note, user["username"])
        _audit(ctx, "buero_status_changed", "buero_mandate", case_id, case_id,
               {"from": current["status"], "to": target, "retention_until": retention})
    return mandate(ctx, user, case_id)


def halt(ctx, user: dict, case_id: str, form: dict) -> dict:
    """A warning sign turned up during the work: stop until the screening is repeated."""
    _require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    current = _mandate_row(ctx, case_id)
    if current["status"] not in ACTIVE_STATUSES:
        raise BueroError("Nur laufende Aufträge können angehalten werden.")
    note = _text(form.get("note"), 600, field="Beschreibung des Warnsignals")
    if len(note) < 10:
        raise BueroError("Bitte das Warnsignal kurz beschreiben (mindestens 10 Zeichen).")
    stamp = _now()
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE buero_mandates SET status='angehalten', version=version+1, updated_at=? WHERE case_id=?",
                       (stamp, case_id))
        _log_status(ctx, case_id, current["status"], "angehalten", note, user["username"])
        _audit(ctx, "buero_mandate_halted", "buero_mandate", case_id, case_id, {"from": current["status"]})
    return mandate(ctx, user, case_id)


# ---------------------------------------------------------------- time, expenses, deadlines

def _bookable(ctx, user: dict, case_id: str) -> dict:
    _require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    current = _mandate_row(ctx, case_id)
    if current["status"] in {"abgelehnt"}:
        raise BueroError("Auf abgelehnte Aufträge wird nichts gebucht.")
    return current


def add_time(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    _bookable(ctx, user, case_id)
    work_date = parse_date(form.get("work_date") or _today(today).isoformat(), "Datum")
    if work_date > _today(today).isoformat():
        raise BueroError("Zeiten werden nicht im Voraus gebucht.")
    row = {"entry_id": _id("time"), "case_id": case_id, "username": user["username"], "work_date": work_date,
           "minutes": parse_duration(form.get("duration")),
           "activity": _choice(form.get("activity"), ACTIVITIES, "die Tätigkeit"),
           "note": _text(form.get("note"), 500, field="Beschreibung"),
           "billable": 0 if str(form.get("billable") or "1") in {"0", "nein"} else 1, "created_at": _now()}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_time(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        _audit(ctx, "buero_time_added", "buero_time", row["entry_id"], case_id,
               {"minutes": row["minutes"], "activity": row["activity"], "billable": row["billable"]})
    return row


def add_expense(ctx, user: dict, case_id: str, form: dict, *, today: date | None = None) -> dict:
    _bookable(ctx, user, case_id)
    spent_on = parse_date(form.get("spent_on") or _today(today).isoformat(), "Datum")
    if spent_on > _today(today).isoformat():
        raise BueroError("Auslagen werden nicht im Voraus gebucht.")
    kind = _choice(form.get("kind"), EXPENSE_KINDS, "die Art der Auslage")
    km = 0
    if kind == "km":
        text = str(form.get("km") or "").strip()
        if not re.fullmatch(r"\d{1,5}", text) or not 1 <= int(text) <= 5000:
            raise BueroError("Kilometer: ganze Zahl zwischen 1 und 5000.")
        km = int(text)
        amount = km * int(settings(ctx)["km_satz_cent"])
    else:
        amount = parse_euro(form.get("amount"), "Betrag", maximum=100_000_00)
        if amount <= 0:
            raise BueroError("Betrag: bitte einen Betrag über 0 angeben.")
    row = {"expense_id": _id("expense"), "case_id": case_id, "username": user["username"], "spent_on": spent_on,
           "kind": kind, "km": km, "amount_cents": amount, "note": _text(form.get("note"), 500, field="Beschreibung"),
           "billable": 0 if str(form.get("billable") or "1") in {"0", "nein"} else 1, "created_at": _now()}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_expenses(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        _audit(ctx, "buero_expense_added", "buero_expense", row["expense_id"], case_id,
               {"amount_cents": amount, "kind": kind, "billable": row["billable"]})
    return row


def void_entry(ctx, user: dict, case_id: str, form: dict) -> None:
    """Cancel a time or expense entry with a reason; own entries, or any entry for case managers."""
    _require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    kind = _choice(form.get("entry_type"), {"time": 1, "expense": 1}, "den Eintrag")
    table, key = ("buero_time", "entry_id") if kind == "time" else ("buero_expenses", "expense_id")
    entry_id = str(form.get("entry_id") or "")
    row = ctx.db.one(f"SELECT * FROM {table} WHERE {key}=? AND case_id=?", (entry_id, case_id))
    if not row:
        raise BueroError("Eintrag nicht gefunden.")
    if row["voided_at"]:
        raise BueroError("Dieser Eintrag ist bereits storniert.")
    if row["username"] != user["username"] and not may_manage(ctx, user, case_id):
        raise PermissionError("Fremde Einträge storniert nur die Fallleitung.")
    reason = _text(form.get("reason"), 300, field="Grund der Stornierung")
    if len(reason) < 5:
        raise BueroError("Bitte den Grund der Stornierung angeben (mindestens 5 Zeichen).")
    with ctx.db.transaction(immediate=True):
        ctx.db.execute(f"UPDATE {table} SET voided_at=?, voided_by=?, void_reason=? WHERE {key}=?",
                       (_now(), user["username"], reason, entry_id))
        _audit(ctx, "buero_entry_voided", table, entry_id, case_id, {"reason": reason})


def time_entries(ctx, user: dict, case_id: str) -> list[dict]:
    _authorize(ctx, user, case_id, "case.read")
    return [dict(r) for r in ctx.db.all("SELECT * FROM buero_time WHERE case_id=? ORDER BY work_date DESC, created_at DESC",
                                        (case_id,))]


def expenses(ctx, user: dict, case_id: str) -> list[dict]:
    _authorize(ctx, user, case_id, "case.read")
    return [dict(r) for r in ctx.db.all("SELECT * FROM buero_expenses WHERE case_id=? ORDER BY spent_on DESC, created_at DESC",
                                        (case_id,))]


def add_deadline(ctx, user: dict, case_id: str, form: dict) -> dict:
    _require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    _mandate_row(ctx, case_id)
    row = {"deadline_id": _id("deadline"), "case_id": case_id,
           "due_on": parse_date(form.get("due_on"), "Datum der Wiedervorlage"),
           "title": _text(form.get("title"), 200, field="was zu tun ist", required=True),
           "created_by": user["username"], "created_at": _now()}
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_deadlines(" + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                       tuple(row.values()))
        _audit(ctx, "buero_deadline_added", "buero_deadline", row["deadline_id"], case_id, {"due_on": row["due_on"]})
    return row


def complete_deadline(ctx, user: dict, case_id: str, form: dict) -> None:
    _require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    deadline_id = str(form.get("deadline_id") or "")
    with ctx.db.transaction(immediate=True):
        changed = ctx.db.execute("UPDATE buero_deadlines SET done_at=?, done_by=? WHERE deadline_id=? AND case_id=? "
                                 "AND done_at=''", (_now(), user["username"], deadline_id, case_id)).rowcount
        if changed != 1:
            raise BueroError("Wiedervorlage nicht gefunden oder bereits erledigt.")
        _audit(ctx, "buero_deadline_done", "buero_deadline", deadline_id, case_id, {})


def deadlines(ctx, user: dict, case_id: str) -> list[dict]:
    _authorize(ctx, user, case_id, "case.read")
    return [dict(r) for r in ctx.db.all("SELECT * FROM buero_deadlines WHERE case_id=? ORDER BY done_at != '', due_on",
                                        (case_id,))]


# ---------------------------------------------------------------- money

def _totals(row: dict, minutes: int, billable_minutes: int, expenses_cents: int) -> dict:
    if row["fee_model"] == "pauschal":
        fee = int(row["flat_fee_cents"])
    else:
        fee = round(billable_minutes * int(row["hourly_rate_cents"]) / 60)
    net = fee + expenses_cents
    budget = int(row["budget_cents"])
    return {"minutes": minutes, "billable_minutes": billable_minutes, "fee_cents": fee, "expenses_cents": expenses_cents,
            "net_cents": net, "budget_cents": budget,
            "budget_share": (net / budget) if budget else None}


def totals(ctx, case_id: str, row: dict | None = None) -> dict:
    row = row or _mandate_row(ctx, case_id)
    t = ctx.db.one("SELECT COALESCE(SUM(minutes),0) AS minutes, COALESCE(SUM(CASE WHEN billable=1 THEN minutes ELSE 0 END),0) "
                   "AS billable FROM buero_time WHERE case_id=? AND voided_at=''", (case_id,)) or {}
    e = ctx.db.one("SELECT COALESCE(SUM(amount_cents),0) AS amount FROM buero_expenses WHERE case_id=? AND voided_at='' "
                   "AND billable=1", (case_id,)) or {}
    return _totals(row, int(t.get("minutes") or 0), int(t.get("billable") or 0), int(e.get("amount") or 0))


def vat(office: dict, net_cents: int) -> dict:
    if office["ust_modus"] == "kleinunternehmer":
        return {"rate": 0, "vat_cents": 0, "gross_cents": net_cents,
                "note": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."}
    rate = int(office["ust_satz"])
    tax = round(net_cents * rate / 100)
    return {"rate": rate, "vat_cents": tax, "gross_cents": net_cents + tax, "note": ""}


def statement(ctx, user: dict, case_id: str) -> dict:
    """Everything a statement of work needs (time and expenses, without cancelled entries)."""
    current = mandate(ctx, user, case_id)
    if current is None:
        raise BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    office = settings(ctx)
    times = [r for r in time_entries(ctx, user, case_id) if not r["voided_at"]]
    spent = [r for r in expenses(ctx, user, case_id) if not r["voided_at"]]
    times.sort(key=lambda r: (r["work_date"], r["created_at"]))
    spent.sort(key=lambda r: (r["spent_on"], r["created_at"]))
    money = current["totals"]
    return {"office": office, "mandate": current, "times": times, "expenses": spent, "totals": money,
            "vat": vat(office, money["net_cents"])}


# ---------------------------------------------------------------- overview

def dashboard(ctx, user: dict, *, today: date | None = None) -> dict:
    day = _today(today)
    rows = mandates(ctx, user)
    visible = {r["case_id"] for r in rows}
    soon = (day + timedelta(days=7)).isoformat()
    iso = day.isoformat()
    open_deadlines = []
    if visible:
        marks = ",".join("?" for _ in visible)
        open_deadlines = [dict(r) for r in ctx.db.all(
            f"SELECT * FROM buero_deadlines WHERE done_at='' AND case_id IN ({marks}) AND due_on<=? ORDER BY due_on",
            (*visible, soon))]
    by_case = {r["case_id"]: r for r in rows}
    for d in open_deadlines:
        d["aktenzeichen"] = by_case[d["case_id"]]["aktenzeichen"]
        d["title_case"] = by_case[d["case_id"]]["title"]
        d["overdue"] = d["due_on"] < iso
    month = iso[:7]
    month_minutes = 0
    if visible:
        marks = ",".join("?" for _ in visible)
        month_minutes = int((ctx.db.one(f"SELECT COALESCE(SUM(minutes),0) AS m FROM buero_time WHERE voided_at='' AND "
                                        f"username=? AND substr(work_date,1,7)=? AND case_id IN ({marks})",
                                        (user["username"], month, *visible)) or {}).get("m") or 0)
    for row in rows:
        row["due_state"] = ("" if not row["due_on"] or row["status"] not in OPEN_STATUSES else
                            "overdue" if row["due_on"] < iso else "soon" if row["due_on"] <= soon else "")
    retention_due = [r for r in rows if r["status"] in {"abgeschlossen", "abgelehnt"} and r["retention_until"]
                     and r["retention_until"] <= iso]
    return {
        "today": iso, "mandates": rows,
        "open": [r for r in rows if r["status"] in OPEN_STATUSES],
        "screening_open": [r for r in rows if r["status"] in {"anfrage", "angehalten"}],
        "deadlines": open_deadlines,
        "due_mandates": [r for r in rows if r["due_state"]],
        "retention_due": retention_due,
        "over_budget": [r for r in rows if r["status"] in OPEN_STATUSES and r["totals"]["budget_share"] is not None
                        and r["totals"]["budget_share"] >= 0.8],
        "month_minutes": month_minutes,
        "without_mandate": cases_without_mandate(ctx, user),
    }


def time_export(ctx, user: dict, month: str) -> list[dict]:
    """All visible, non-cancelled time entries of one month (for accounting)."""
    if not re.fullmatch(r"\d{4}-\d{2}", str(month or "")):
        raise BueroError("Monat bitte als JJJJ-MM angeben.")
    rows = mandates(ctx, user)
    if not rows:
        return []
    by_case = {r["case_id"]: r for r in rows}
    marks = ",".join("?" for _ in by_case)
    out = []
    for entry in ctx.db.all(f"SELECT * FROM buero_time WHERE voided_at='' AND substr(work_date,1,7)=? AND case_id IN ({marks}) "
                            "ORDER BY work_date, created_at", (month, *by_case)):
        m = by_case[entry["case_id"]]
        out.append({**dict(entry), "aktenzeichen": m["aktenzeichen"], "client_name": m["client_name"], "title": m["title"]})
    return out
