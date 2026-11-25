"""Work lists per mandate type ("Vorlagen je Auftragsart") and the documented scope of a report.

Every mandate type has a fixed list of steps. Each step links to the tool that does it. A step is
"offen", "erledigt" or "entfällt" (with a short reason); the state is kept per case and step key,
so changing the mandate type keeps what was already recorded. The client report lists the scope
from this list: what was checked, what was not, and what did not apply and why.

The hints describe public-source practice only; they are no legal advice.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import service as buero

STATES = {"offen": "offen", "erledigt": "erledigt", "entfaellt": "entfällt"}
REPORT_STATES = {"offen": "nicht geprüft", "erledigt": "geprüft", "entfaellt": "entfällt"}

START = [("auftrag", "Fragestellung, Umfang und Frist mit dem Mandanten abgestimmt",
          "Was soll geklärt werden, was ausdrücklich nicht? Ergebnisempfänger festgelegt.", "")]
END = [("pruefung", "Befunde am Original geprüft",
        "Für Berichte an Behörden oder Gerichte durch ein zweites Konto.", "/workbench/report"),
       ("bericht", "Bericht erstellt und übergeben", "Empfängerstufe beachten; Übergabe in der Akte vermerken.", "")]

SANCTIONS = ("sanktionen", "Sanktions- und Embargolisten geprüft",
             "Z. B. EU-Finanzsanktionsliste und UN-Sanktionsliste; Treffer am Original bestätigen.", "/workbench/public-sources")
PRESS = ("presse", "Presse- und Medienrecherche",
         "Fundstellen als Web-Beleg sichern; abgeschriebene Meldungen über Quellenfamilien erkennen.", "/workbench/intel/lineage")

TEMPLATES: dict[str, list[tuple[str, str, str, str]]] = {
    "due_diligence": [
        ("handelsregister", "Handels- und Unternehmensregister ausgewertet",
         "Aktueller und chronologischer Auszug, Gesellschafterliste, Geschäftsführung, Kapital – als Dokument ablegen.", "/workbench/document"),
        ("bekanntmachungen", "Register- und Insolvenzbekanntmachungen geprüft",
         "Fundstellen als Web-Beleg sichern.", "/workbench/intel/web"),
        ("abschluesse", "Jahresabschlüsse und Offenlegungen ausgewertet",
         "Hinweise auf Verluste, Rückstellungen oder Bestandsgefährdung.", "/workbench/document"),
        ("verflechtungen", "Verflechtungen von Organen und Gesellschaftern",
         "Weitere Mandate und Beteiligungen; Namensabgleich und Netzwerk.", "/workbench/intel/network"),
        SANCTIONS,
        PRESS,
        ("webauftritt", "Webauftritt und Impressum gesichert", "Impressumsangaben mit den Registerdaten abgleichen.",
         "/workbench/intel/web"),
        ("verfahren", "Öffentlich bekannte Verfahren und Aufsichtsmitteilungen",
         "Veröffentlichte Entscheidungen, Bußgeld- und Aufsichtsmitteilungen.", "/workbench/public-sources"),
    ],
    "hintergrund": [
        ("erforderlichkeit", "Rechtsgrundlage und Erforderlichkeit dokumentiert",
         "Bei Bewerbern nur Angaben, die für die Stelle erforderlich sind.", ""),
        ("angaben", "Angaben aus Lebenslauf oder Selbstauskunft abgeglichen",
         "Stationen, Abschlüsse und Funktionen mit öffentlichen Quellen vergleichen.", "/workbench/findings"),
        ("organe", "Unternehmensbeteiligungen und Organfunktionen",
         "Geschäftsführung, Gesellschafterstellung, frühere Insolvenzen.", "/workbench/public-sources"),
        ("berufsregister", "Berufs- und Kammerregister (falls einschlägig)",
         "Z. B. Rechtsanwalts-, Steuerberater- oder Ärzteregister.", "/workbench/public-sources"),
        ("profile", "Berufliche Online-Profile und Veröffentlichungen",
         "Nur berufsbezogene, öffentliche Angaben.", "/workbench/leads483"),
        SANCTIONS,
        PRESS,
    ],
    "wirtschaft": [
        ("unterlagen", "Unterlagen des Mandanten gesichtet", "Belege importieren und die Textübernahme prüfen.",
         "/workbench/document"),
        ("zeitleiste", "Ereignisse zeitlich geordnet", "Befunde mit Datum; Widersprüche festhalten.", "/workbench/findings"),
        ("verflechtungen", "Personen- und Firmenverflechtungen", "Namensabgleich und Netzwerk nutzen.",
         "/workbench/intel/network"),
        ("vermoegen", "Öffentlich sichtbare Vermögenswerte und Beteiligungen", "Register und Bekanntmachungen.",
         "/workbench/public-sources"),
        ("belegkette", "Beweiskette für ein Verfahren aufbereitet",
         "Belege als Evidence übernehmen; Prüfung durch ein zweites Konto.", "/workbench/bridge481"),
    ],
    "person": [
        ("anspruch", "Rechtsanspruch belegt (Titel, Verfahren)",
         "Ohne belegten Anspruch keine Anschriftenermittlung zu Privatpersonen.", ""),
        ("ausgangsdaten", "Ausgangsdaten erfasst (Name, Geburtsdatum, letzte bekannte Anschrift)", "",
         "/workbench/findings"),
        ("auskuenfte", "Behördliche Auskünfte veranlasst und abgelegt",
         "Melderegisterauskünfte holt in der Regel der Mandant oder sein Anwalt ein; Ergebnis als Dokument ablegen.",
         "/workbench/document"),
        ("oeffentlich", "Öffentliche Quellen geprüft", "Verzeichnisse, Registerdaten, berufliche Veröffentlichungen.",
         "/workbench/public-sources"),
        ("verwechslung", "Namensvarianten und Verwechslungsgefahr geprüft",
         "Keine Zuordnung ohne zweites unabhängiges Merkmal.", "/workbench/entities488"),
        ("empfaenger", "Ergebnis nur an den berechtigten Empfänger", "", ""),
    ],
    "vermisst": [
        ("polizei", "Vermisstenanzeige und Zusammenarbeit mit der Polizei geklärt", "", ""),
        ("freiwilligkeit", "Freiwilligkeit eines Kontaktabbruchs bewertet",
         "Bei Volljährigen mit freiwilligem Kontaktabbruch nur ein Lebenszeichen weitergeben.", ""),
        ("aktivitaet", "Letzte öffentliche Online-Aktivitäten gesichert", "Nur öffentlich sichtbare Inhalte, als Web-Beleg.",
         "/workbench/intel/web"),
        ("umfeld", "Öffentlich bekanntes Umfeld ausgewertet", "", "/workbench/intel/network"),
        ("ergebnisform", "Ergebnisform festgelegt (Lebenszeichen, Polizei, Angehörige)", "", ""),
    ],
    "online": [
        ("fundstellen", "Fundstellen gesammelt und gesichert", "Jede Fundstelle als Web-Beleg mit Abrufzeit.",
         "/workbench/intel/web"),
        ("urheber", "Urheber oder Betreiber ermittelt", "Impressum, Domaindaten, Plattformangaben.",
         "/workbench/public-sources"),
        ("verbreitung", "Verbreitung und gemeinsame Ursprünge geprüft", "Quellenfamilien zeigen Übernahmen.",
         "/workbench/intel/lineage"),
        ("zeitleiste", "Zeitleiste der Veröffentlichungen", "", "/workbench/findings"),
        ("beobachtung", "Wiedervorlage für eine erneute Prüfung angelegt", "", ""),
    ],
    "sonstiges": [
        ("methoden", "Quellen und Methoden festgelegt", "", "/workbench/plan496"),
        ("belege", "Belege gesichert", "", "/workbench/intel/web"),
    ],
}

TABLE = """CREATE TABLE IF NOT EXISTS buero_checklist(case_id TEXT NOT NULL, item_key TEXT NOT NULL, state TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', updated_by TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(case_id, item_key))"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.commit()


def items_for(kind: str) -> list[tuple[str, str, str, str]]:
    return START + TEMPLATES.get(kind, TEMPLATES["sonstiges"]) + END


def _states(ctx, case_id: str) -> dict[str, dict]:
    return {r["item_key"]: dict(r) for r in ctx.db.all("SELECT * FROM buero_checklist WHERE case_id=?", (case_id,))}


def checklist(ctx, user: dict, case_id: str) -> list[dict]:
    """The mandate's work list with the recorded state of each step."""
    row = buero.mandate(ctx, user, case_id)
    if row is None:
        raise buero.BueroError("Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    states = _states(ctx, case_id)
    out = []
    for key, title, hint, tool in items_for(row["kind"]):
        state = states.get(key, {})
        out.append({"key": key, "title": title, "hint": hint, "tool": tool, "state": state.get("state", "offen"),
                    "note": state.get("note", ""), "updated_by": state.get("updated_by", ""),
                    "updated_at": state.get("updated_at", "")})
    return out


def set_item(ctx, user: dict, case_id: str, form: dict) -> dict:
    buero._require_any(ctx, user, case_id, ("research.run", "dossier.write", "case.manage"))
    row = buero._mandate_row(ctx, case_id)
    keys = {k for k, *_ in items_for(row["kind"])}
    key = str(form.get("item_key") or "")
    if key not in keys:
        raise buero.BueroError("Diesen Punkt gibt es in der Arbeitsliste nicht.")
    state = buero._choice(form.get("state"), STATES, "den Stand")
    note = buero._text(form.get("note"), 300, field="Begründung")
    if state == "entfaellt" and len(note) < 5:
        raise buero.BueroError("Bitte kurz begründen, warum der Punkt entfällt (mindestens 5 Zeichen).")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("INSERT INTO buero_checklist(case_id,item_key,state,note,updated_by,updated_at) VALUES(?,?,?,?,?,?) "
                       "ON CONFLICT(case_id,item_key) DO UPDATE SET state=excluded.state, note=excluded.note, "
                       "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                       (case_id, key, state, note if state == "entfaellt" else "", user["username"], stamp))
        ctx.audit.log("buero_checklist_item_set", "buero_mandate", case_id, case_id, {"item": key, "state": state})
    return {"item_key": key, "state": state}


def progress(ctx, rows: list[dict]) -> dict[str, tuple[int, int]]:
    """case_id -> (finished steps, all steps); 'entfällt' counts as finished."""
    if not rows:
        return {}
    marks = ",".join("?" for _ in rows)
    finished: dict[str, set[str]] = {}
    for r in ctx.db.all(f"SELECT case_id, item_key FROM buero_checklist WHERE state<>'offen' AND case_id IN ({marks})",
                        tuple(r["case_id"] for r in rows)):
        finished.setdefault(r["case_id"], set()).add(r["item_key"])
    out = {}
    for row in rows:
        keys = {k for k, *_ in items_for(row["kind"])}
        out[row["case_id"]] = (len(finished.get(row["case_id"], set()) & keys), len(keys))
    return out
