"""Fachlogik: Fälle, Personen, Suche, Prüfung, Verbindungen, Vermisstenmodul."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path
from typing import Any

from . import graph as g
from .auth import SUPERVISORS
from .crypto import Vault
from .db import ConflictError, Database, now_iso
from .matching import confidence_label, fold, normalize, score_candidate
from .sources import SOURCE_MAP, SOURCES, Http, SourceError, geocode, research_links


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


class Forbidden(Exception):
    pass


#: angemeldete Person der aktuellen Anfrage (von der API gesetzt; None = System/CLI)
current_user: ContextVar[dict[str, Any] | None] = ContextVar("current_user", default=None)

CASE_STATUSES = ["offen", "in Bearbeitung", "zur Prüfung", "freigegeben", "abgeschlossen", "archiviert"]
MEMBER_ROLES = {"bearbeiter": "Bearbeitung", "pruefer": "Prüfung", "leser": "nur lesen"}
GENESIS = "0" * 64


def _audit_hash(prev: str, ts: str, case_id: Any, user_id: Any, username: str, action: str, detail_hash: str) -> str:
    payload = json.dumps([prev, ts, case_id, user_id, username, action, detail_hash], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def seal_audit_chain(db: Database) -> None:
    """Migration 2: vorhandene Protokolleinträge (Version 1.0) nachträglich in die Hash-Kette aufnehmen."""
    prev = GENESIS
    for row in db.all("SELECT * FROM audit ORDER BY id"):
        dh = hashlib.sha256(row["detail"].encode()).hexdigest()
        h = _audit_hash(prev, row["ts"], row["case_id"], row["user_id"], row["username"], row["action"], dh)
        db.update("audit", row["id"], {"detail_hash": dh, "prev_hash": prev, "hash": h})
        prev = h


CASE_TYPES = {
    "investigativ": "Investigativrecherche",
    "personensuche": "Personensuche",
    "vermisst": "Vermisstenfall",
    "verbindungen": "Verbindungsanalyse",
}
ENTITY_TYPES = {
    "person": "Person", "organisation": "Organisation", "ort": "Ort", "konto": "Online-Konto",
    "telefon": "Telefon", "email": "E-Mail", "fahrzeug": "Fahrzeug", "ereignis": "Ereignis",
    "dokument": "Dokument", "sonstiges": "Sonstiges",
}
IDENTIFIER_KINDS = {
    "name": "Name", "alias": "Alias/Spitzname", "email": "E-Mail", "phone": "Telefon",
    "username": "Benutzername", "url": "Webseite/Profil-URL", "location": "Ort/Adresse",
    "employer": "Arbeitgeber/Schule", "other": "Sonstiges",
}
RELATIONS = [
    "verwandt mit", "Partner/in von", "befreundet mit", "Kollege/Kollegin von", "Kontakt mit",
    "arbeitet bei", "Mitglied von", "wohnt in", "hält sich auf in", "zuletzt gesehen in",
    "besitzt Konto", "nutzt Telefon", "nutzt E-Mail", "besitzt Fahrzeug", "beteiligt an",
    "erwähnt in", "identisch mit (vermutet)", "sonstige Verbindung",
]
EVENT_KINDS = ["Letzte Sichtung", "Sichtung (Hinweis)", "Letzter Kontakt", "Online-Aktivität", "Bewegung/Reise",
               "Kontobewegung (Polizei)", "Wohnortwechsel", "Ereignis", "Auffindung"]
RISK_FACTORS = {
    "kind": ("Minderjährig (unter 14 Jahre)", 3),
    "jugendlich": ("Jugendlich (14–17 Jahre)", 2),
    "senior": ("Hohes Alter (über 75 Jahre)", 2),
    "medizinisch": ("Auf Medikamente/medizinische Versorgung angewiesen", 3),
    "orientierung": ("Demenz / Orientierungsstörung", 3),
    "suizid": ("Hinweise auf Suizidgefahr / psychische Krise", 4),
    "gewalt": ("Verdacht auf Straftat oder Gewalt", 4),
    "untypisch": ("Verschwinden völlig untypisch", 2),
    "ohne_mittel": ("Ohne Geld, Handy oder Medikamente unterwegs", 1),
    "wetter": ("Extreme Witterung / gefährliches Gelände", 2),
    "behinderung": ("Behinderung / besondere Hilfsbedürftigkeit", 2),
    "sucht": ("Suchterkrankung", 1),
}
PERSON_FIELDS = [
    ("geburtsdatum", "Geburtsdatum"), ("geschlecht", "Geschlecht"), ("nationalitaet", "Staatsangehörigkeit"),
    ("wohnort", "Wohnort"), ("beruf", "Beruf / Tätigkeit"), ("groesse", "Größe"), ("statur", "Statur"),
    ("haare", "Haare"), ("augen", "Augen"), ("merkmale", "Besondere Merkmale"), ("sprachen", "Sprachen"),
    ("notizen", "Notizen"),
]
MISSING_FIELDS = [
    ("vermisst_status", "Status"), ("vermisst_seit", "Vermisst seit"), ("zuletzt_gesehen_zeit", "Zuletzt gesehen (Zeit)"),
    ("zuletzt_gesehen_ort", "Zuletzt gesehen (Ort)"), ("kleidung", "Kleidung"), ("mitgefuehrt", "Mitgeführte Gegenstände"),
    ("fahrzeug", "Fahrzeug / Verkehrsmittel"), ("umstaende", "Umstände des Verschwindens"),
    ("gesundheit", "Gesundheit / Medikamente"), ("anlaufpunkte", "Mögliche Anlaufpunkte"),
    ("polizei_dienststelle", "Zuständige Polizei"), ("aktenzeichen", "Aktenzeichen"), ("kontakt_hinweise", "Kontakt für Hinweise"),
]


def _age(birth: str) -> int | None:
    try:
        b = date.fromisoformat(birth[:10])
    except (TypeError, ValueError):
        return None
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


class Platform:
    def __init__(self, db: Database, data_dir: Path, http: Http | None = None, auto_geocode: bool = True, vault: Vault | None = None):
        self.db = db
        self.data_dir = Path(data_dir)
        self.http = http or Http()
        self.auto_geocode = auto_geocode
        self.vault = vault or Vault(self.data_dir / "secret.key")
        (self.data_dir / "photos").mkdir(parents=True, exist_ok=True)
        self._audit_lock = threading.Lock()
        self._presence: dict[int, dict[int, tuple[str, float, str]]] = {}

    # ------------------------------------------------------------------ Protokoll (Hash-Kette)
    def log(self, case_id: int | None, action: str, detail: str = "") -> None:
        user = current_user.get()
        uid, uname = (user["id"], user["username"]) if user else (None, "system")
        detail = detail[:2000]
        dh = hashlib.sha256(detail.encode()).hexdigest()
        with self._audit_lock, self.db.tx():
            self.db.advisory_lock(4711)
            row = self.db.run_in_tx("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev = (row["hash"] if row else "") or GENESIS
            ts = now_iso()
            h = _audit_hash(prev, ts, case_id, uid, uname, action, dh)
            self.db.run_in_tx("INSERT INTO audit (case_id, ts, user_id, username, action, detail, detail_hash, prev_hash, hash) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (case_id, ts, uid, uname, action, detail, dh, prev, h))

    def verify_audit(self) -> dict[str, Any]:
        """Prüft die gesamte Kette: Verknüpfung, Hashes und (sofern nicht geschwärzt) die Detailtexte."""
        prev = GENESIS
        count = redacted = 0
        for row in self.db.all("SELECT * FROM audit ORDER BY id"):
            count += 1
            problem = ""
            if row["prev_hash"] != prev:
                problem = "Verkettung unterbrochen (Eintrag gelöscht oder eingefügt)"
            elif _audit_hash(prev, row["ts"], row["case_id"], row["user_id"], row["username"], row["action"], row["detail_hash"]) != row["hash"]:
                problem = "Eintrag wurde nachträglich verändert"
            elif row["redacted"]:
                redacted += 1
            elif hashlib.sha256(row["detail"].encode()).hexdigest() != row["detail_hash"]:
                problem = "Detailtext wurde nachträglich verändert"
            if problem:
                return {"ok": False, "entries": count, "broken_at": row["id"], "ts": row["ts"], "problem": problem, "redacted": redacted}
            prev = row["hash"]
        return {"ok": True, "entries": count, "redacted": redacted, "head": prev}

    # ------------------------------------------------------------------ Rechte
    @staticmethod
    def _uid() -> int | None:
        user = current_user.get()
        return user["id"] if user else None

    def member_role(self, case: dict[str, Any], user: dict[str, Any]) -> str | None:
        if case.get("owner_id") == user["id"]:
            return "bearbeiter"
        if case.get("reviewer_id") == user["id"]:
            return "pruefer"
        row = self.db.one("SELECT role FROM case_members WHERE case_id = ? AND user_id = ?", (case["id"], user["id"]))
        return row["role"] if row else None

    def permissions(self, case: dict[str, Any], user: dict[str, Any] | None) -> set[str]:
        """read · write (recherchieren) · review (Treffer/Freigabe prüfen) · manage (Team, Stammdaten) · delete"""
        if user is None:  # System/CLI
            return {"read", "write", "review", "manage", "delete"}
        role = self.member_role(case, user)
        perms: set[str] = set()
        supervisor = user["role"] in SUPERVISORS and not case.get("restricted")
        if supervisor:
            perms |= {"read", "review", "manage"}
            if user["role"] == "leitung":
                perms |= {"write", "delete"}
        if role:
            perms.add("read")
            if user["role"] != "leser" and role in {"bearbeiter", "pruefer"}:
                perms |= {"write", "review"}
            if role == "bearbeiter" and user["role"] != "leser" and case.get("owner_id") == user["id"]:
                perms |= {"manage", "delete"}
            if user["role"] == "leser" or role == "leser":
                perms -= {"write", "review", "manage", "delete"}
                perms.add("read")
        return perms

    def require(self, case_id: int, perm: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        if perm not in self.permissions(case, current_user.get()):
            if "read" not in self.permissions(case, current_user.get()):
                raise NotFound("Fall nicht gefunden.")  # Existenz vertraulicher Fälle nicht preisgeben
            raise Forbidden({"write": "Sie haben für diesen Fall nur Leserechte.",
                             "review": "Prüfen/Freigeben ist für diesen Fall nicht erlaubt.",
                             "manage": "Nur Fallverantwortliche oder die Teamleitung dürfen das ändern.",
                             "delete": "Nur Fallverantwortliche oder die Teamleitung dürfen den Fall löschen."}.get(perm, "Keine Berechtigung."))
        return case

    # ------------------------------------------------------------------ Anwesenheit („bearbeitet gerade“)
    def heartbeat(self, case_id: int, tab: str = "") -> list[dict[str, Any]]:
        user = current_user.get()
        now = time.time()
        bucket = self._presence.setdefault(case_id, {})
        if user:
            bucket[user["id"]] = (user["display_name"], now, tab)
        for uid in [u for u, (_, ts, _) in bucket.items() if now - ts > 90]:
            bucket.pop(uid, None)
        return [{"user_id": uid, "name": name, "tab": t, "seconds_ago": int(now - ts)}
                for uid, (name, ts, t) in bucket.items() if not user or uid != user["id"]]

    # ------------------------------------------------------------------ Fälle
    def create_case(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        purpose = (payload.get("purpose") or "").strip()
        legal = (payload.get("legal_basis") or "").strip()
        ctype = payload.get("case_type") or "personensuche"
        if not title:
            raise Invalid("Bitte einen Falltitel angeben.")
        if ctype not in CASE_TYPES:
            raise Invalid("Unbekannte Fallart.")
        if len(purpose) < 10:
            raise Invalid("Bitte den Zweck der Recherche nachvollziehbar beschreiben (mind. 10 Zeichen).")
        if len(legal) < 3:
            raise Invalid("Bitte Rechtsgrundlage bzw. Auftrag/Einwilligung angeben.")
        year = datetime.now().year
        count = (self.db.one("SELECT COUNT(*) AS n FROM cases WHERE reference LIKE ?", (f"EE-{year}-%",)) or {"n": 0})["n"]
        ts = now_iso()
        cid = self.db.insert("cases", {
            "reference": f"EE-{year}-{count + 1:04d}", "title": title, "case_type": ctype, "purpose": purpose,
            "legal_basis": legal, "client": (payload.get("client") or "").strip(), "analyst": (payload.get("analyst") or "").strip(),
            "status": "offen", "notes": payload.get("notes") or "", "created_at": ts, "updated_at": ts,
            "owner_id": self._uid(), "due_date": (payload.get("due_date") or "").strip(),
            "priority": payload.get("priority") if payload.get("priority") in {"niedrig", "normal", "hoch", "dringend"} else ("dringend" if ctype == "vermisst" else "normal"),
            "restricted": 1 if payload.get("restricted") else 0})
        self.log(cid, "Fall angelegt", f"{CASE_TYPES[ctype]}: {title} · Zweck: {purpose} · Grundlage: {legal}")
        subject = payload.get("subject")
        if subject and (subject.get("label") or "").strip():
            self.create_entity(cid, {**subject, "type": "person", "is_subject": True})
        if ctype in {"vermisst", "investigativ"}:
            self.generate_tasks(cid)
        return self.get_case(cid)

    def list_cases(self, view: str = "") -> list[dict[str, Any]]:
        rows = self.db.all("""
            SELECT c.*,
              (SELECT COUNT(*) FROM entities e WHERE e.case_id = c.id) AS entity_count,
              (SELECT COUNT(*) FROM findings f WHERE f.case_id = c.id AND f.status = 'neu') AS open_findings,
              (SELECT COUNT(*) FROM findings f WHERE f.case_id = c.id AND f.status = 'bestätigt') AS confirmed_findings,
              (SELECT label FROM entities e WHERE e.case_id = c.id AND e.is_subject = 1 ORDER BY e.id LIMIT 1) AS subject_label,
              (SELECT display_name FROM users u WHERE u.id = c.owner_id) AS owner_name,
              (SELECT display_name FROM users u WHERE u.id = c.reviewer_id) AS reviewer_name
            FROM cases c ORDER BY c.updated_at DESC, c.id DESC""")
        user = current_user.get()
        today = date.today().isoformat()
        out = []
        for r in rows:
            perms = self.permissions(r, user)
            if "read" not in perms:
                continue
            r["case_type_label"] = CASE_TYPES.get(r["case_type"], r["case_type"])
            r["my_role"] = self.member_role(r, user) if user else None
            r["overdue"] = bool(r["due_date"]) and r["due_date"] < today and r["status"] not in {"freigegeben", "abgeschlossen", "archiviert"}
            mine = bool(user) and r["my_role"] in {"bearbeiter", "pruefer"}
            if view == "mine" and not mine:
                continue
            if view == "review" and not (r["status"] == "zur Prüfung" and "review" in perms and (not user or r["owner_id"] != user["id"])):
                continue
            if view == "overdue" and not r["overdue"]:
                continue
            out.append(r)
        return out

    def get_case(self, case_id: int) -> dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE id = ?", (case_id,))
        if not case:
            raise NotFound("Fall nicht gefunden.")
        case["case_type_label"] = CASE_TYPES.get(case["case_type"], case["case_type"])
        return case

    def case_team(self, case: dict[str, Any]) -> dict[str, Any]:
        names = {u["id"]: u for u in self.db.all("SELECT id, username, display_name, role FROM users")}
        members = self.db.all("SELECT m.user_id, m.role, u.display_name, u.username FROM case_members m JOIN users u ON u.id = m.user_id "
                              "WHERE m.case_id = ? ORDER BY u.display_name", (case["id"],))
        return {"owner": names.get(case.get("owner_id")), "reviewer": names.get(case.get("reviewer_id")), "members": members}

    def update_case(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        case = self.get_case(case_id)
        user = current_user.get()
        perms = self.permissions(case, user)
        basic = {"title", "purpose", "legal_basis", "client", "analyst", "notes"}
        team = {"owner_id", "reviewer_id", "due_date", "priority", "restricted"}
        values = {k: v for k, v in payload.items() if k in basic | team | {"status"} and v is not None}
        if set(values) & (basic | team) and "manage" not in perms:
            raise Forbidden("Nur Fallverantwortliche oder die Teamleitung dürfen Stammdaten und Team ändern.")
        for key in ("owner_id", "reviewer_id"):
            if key in values:
                values[key] = int(values[key]) if values[key] not in ("", 0, "0") else None
                if values[key] and not self.db.one("SELECT id FROM users WHERE id = ? AND active = 1", (values[key],)):
                    raise Invalid("Ausgewählte Person existiert nicht oder ist deaktiviert.")
        owner = values.get("owner_id", case["owner_id"])
        reviewer = values.get("reviewer_id", case["reviewer_id"])
        if owner and reviewer and owner == reviewer:
            raise Invalid("Vier-Augen-Prinzip: Bearbeitung und Prüfung müssen verschiedene Personen sein.")
        if "priority" in values and values["priority"] not in {"niedrig", "normal", "hoch", "dringend"}:
            raise Invalid("Ungültige Priorität.")
        if "restricted" in values:
            values["restricted"] = 1 if values["restricted"] else 0
            if values["restricted"] and not owner:
                raise Invalid("Ein vertraulicher Fall braucht eine verantwortliche Person.")
        if "status" in values:
            self._check_status_change(case, values["status"], user, perms, reviewer)
        if "due_date" in values and values["due_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["due_date"]):
            raise Invalid("Fälligkeit bitte als Datum angeben.")
        values["updated_at"] = now_iso()
        self.db.update("cases", case_id, values, expected_version=payload.get("version"))
        changed = [k for k in values if k != "updated_at"]
        names = {u["id"]: u["display_name"] for u in self.db.all("SELECT id, display_name FROM users")}
        labels = {"owner_id": "Verantwortlich", "reviewer_id": "Prüfperson", "due_date": "Fällig", "priority": "Priorität",
                  "restricted": "Vertraulich", "status": "Status"}

        def fmt(k: str) -> str:
            if k in {"owner_id", "reviewer_id"}:
                return f"{labels[k]} → {names.get(values[k], 'niemand')}"
            if k == "restricted":
                return f"Vertraulich → {'ja' if values[k] else 'nein'}"
            return f"{labels[k]} → {values[k]}" if k in labels else k

        detail = ", ".join(fmt(k) for k in changed)
        self.log(case_id, "Status geändert" if changed == ["status"] else "Fall geändert", detail)
        return self.get_case(case_id)

    def _check_status_change(self, case: dict[str, Any], status: str, user: dict[str, Any] | None, perms: set[str], reviewer: Any) -> None:
        if status not in CASE_STATUSES:
            raise Invalid("Ungültiger Status.")
        if status == case["status"]:
            return
        if user is None:
            return
        if status == "freigegeben":
            if "review" not in perms:
                raise Forbidden("Freigeben dürfen nur die zugewiesene Prüfperson oder die Teamleitung.")
            if case["owner_id"] == user["id"]:
                raise Forbidden("Vier-Augen-Prinzip: Den eigenen Fall kann man nicht selbst freigeben.")
            if case["status"] != "zur Prüfung":
                raise Invalid("Freigeben ist nur aus dem Status „zur Prüfung“ möglich.")
        elif status == "zur Prüfung":
            if "write" not in perms:
                raise Forbidden("Keine Berechtigung.")
            if not reviewer:
                raise Invalid("Bitte zuerst eine Prüfperson zuweisen (Fall bearbeiten → Team).")
        elif "write" not in perms and "manage" not in perms:
            raise Forbidden("Keine Berechtigung, den Status zu ändern.")

    def set_members(self, case_id: int, members: list[dict[str, Any]]) -> dict[str, Any]:
        case = self.get_case(case_id)
        clean: dict[int, str] = {}
        for m in members:
            uid = int(m.get("user_id") or 0)
            role = m.get("role") or "bearbeiter"
            if role not in MEMBER_ROLES:
                raise Invalid("Unbekannte Rolle im Fall.")
            if not self.db.one("SELECT id FROM users WHERE id = ?", (uid,)):
                raise Invalid("Unbekannte Person.")
            if uid not in (case["owner_id"], case["reviewer_id"]):
                clean[uid] = role
        with self.db.tx():
            self.db.run_in_tx("DELETE FROM case_members WHERE case_id = ?", (case_id,))
            for uid, role in clean.items():
                self.db.run_in_tx("INSERT INTO case_members (case_id, user_id, role, added_at) VALUES (?, ?, ?, ?)", (case_id, uid, role, now_iso()))
        names = {u["id"]: u["display_name"] for u in self.db.all("SELECT id, display_name FROM users")}
        self.log(case_id, "Team geändert", ", ".join(f"{names.get(u, u)} ({MEMBER_ROLES[r]})" for u, r in clean.items()) or "keine weiteren Mitglieder")
        return self.case_team(self.get_case(case_id))

    def emergency_access(self, case_id: int, reason: str) -> None:
        """Administrativer Notfallzugriff auf einen vertraulichen Fall – nur mit Begründung, dauerhaft protokolliert."""
        user = current_user.get()
        if not user or user["role"] != "admin":
            raise Forbidden("Nur die Administration darf Notfallzugriff erteilen.")
        if len((reason or "").strip()) < 15:
            raise Invalid("Bitte den Notfallzugriff ausführlich begründen (mind. 15 Zeichen).")
        self.get_case(case_id)
        self.db.execute("DELETE FROM case_members WHERE case_id = ? AND user_id = ?", (case_id, user["id"]))
        self.db.insert("case_members", {"case_id": case_id, "user_id": user["id"], "role": "leser", "added_at": now_iso()}, returning=False)
        self.log(case_id, "NOTFALLZUGRIFF", f"{user['display_name']}: {reason.strip()}")

    def restricted_cases(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT c.id, c.reference, c.created_at, c.status, u.display_name AS owner_name FROM cases c "
                           "LEFT JOIN users u ON u.id = c.owner_id WHERE c.restricted = 1 ORDER BY c.id DESC")

    def delete_case(self, case_id: int) -> None:
        case = self.get_case(case_id)
        for e in self.db.all("SELECT photo FROM entities WHERE case_id = ? AND photo != ''", (case_id,)):
            (self.data_dir / "photos" / e["photo"]).unlink(missing_ok=True)
        self.db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        # Personenbezogene Protokolltexte schwärzen; Hashes bleiben, damit die Kette prüfbar bleibt
        self.db.execute("UPDATE audit SET detail = '[gelöscht]', redacted = 1 WHERE case_id = ?", (case_id,))
        self.log(case_id, "Fall gelöscht", f"Fall {case['reference']} inkl. aller Daten gelöscht; Protokolltexte geschwärzt")

    def touch(self, case_id: int) -> None:
        self.db.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now_iso(), case_id))

    # ------------------------------------------------------------------ Entitäten
    def _entity(self, case_id: int, entity_id: int) -> dict[str, Any]:
        e = self.db.one("SELECT * FROM entities WHERE id = ? AND case_id = ?", (entity_id, case_id))
        if not e:
            raise NotFound("Eintrag nicht gefunden.")
        return e

    def create_entity(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_case(case_id)
        etype = payload.get("type") or "person"
        label = (payload.get("label") or "").strip()
        if etype not in ENTITY_TYPES:
            raise Invalid("Unbekannter Typ.")
        if not label:
            raise Invalid("Bitte eine Bezeichnung bzw. einen Namen angeben.")
        data = {k: v for k, v in (payload.get("data") or {}).items() if v not in (None, "")}
        eid = self.db.insert("entities", {"case_id": case_id, "type": etype, "label": label,
                                          "is_subject": 1 if payload.get("is_subject") else 0, "data": data, "created_at": now_iso()})
        if etype == "person":
            self.add_identifier(case_id, eid, {"kind": "name", "value": label, "verified": True}, log=False)
        for ident in payload.get("identifiers") or []:
            if (ident.get("value") or "").strip():
                self.add_identifier(case_id, eid, ident, log=False)
        if self.auto_geocode and etype == "ort":
            coords = geocode(label, self.http)
            if coords:
                data.update({"lat": coords[0], "lon": coords[1]})
                self.db.update("entities", eid, {"data": data})
        self.log(case_id, "Eintrag angelegt", f"{ENTITY_TYPES[etype]}: {label}" + (" (Zielperson)" if payload.get("is_subject") else ""))
        self.touch(case_id)
        return self.get_entity(case_id, eid)

    def get_entity(self, case_id: int, entity_id: int) -> dict[str, Any]:
        e = self._entity(case_id, entity_id)
        e["identifiers"] = self.db.all("SELECT * FROM identifiers WHERE entity_id = ? ORDER BY kind, id", (entity_id,))
        e["type_label"] = ENTITY_TYPES.get(e["type"], e["type"])
        if e["type"] == "person":
            e["risk"] = self.risk_assessment(e)
        return e

    def list_entities(self, case_id: int) -> list[dict[str, Any]]:
        self.get_case(case_id)
        out = []
        for e in self.db.all("SELECT * FROM entities WHERE case_id = ? ORDER BY is_subject DESC, type, label", (case_id,)):
            e["identifiers"] = self.db.all("SELECT * FROM identifiers WHERE entity_id = ? ORDER BY kind, id", (e["id"],))
            e["type_label"] = ENTITY_TYPES.get(e["type"], e["type"])
            e["finding_count"] = (self.db.one("SELECT COUNT(*) AS n FROM findings WHERE entity_id = ?", (e["id"],)) or {})["n"]
            out.append(e)
        return out

    def update_entity(self, case_id: int, entity_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        e = self._entity(case_id, entity_id)
        values: dict[str, Any] = {}
        if payload.get("label"):
            values["label"] = payload["label"].strip()
        if "data" in payload and isinstance(payload["data"], dict):
            data = {**e["data"], **payload["data"]}
            values["data"] = {k: v for k, v in data.items() if v not in (None, "", [])}
        if "is_subject" in payload:
            values["is_subject"] = 1 if payload["is_subject"] else 0
        self.db.update("entities", entity_id, values, expected_version=payload.get("version"))
        self.log(case_id, "Eintrag geändert", f"{e['label']}: " + ", ".join(values))
        self.touch(case_id)
        return self.get_entity(case_id, entity_id)

    def delete_entity(self, case_id: int, entity_id: int) -> None:
        e = self._entity(case_id, entity_id)
        if e["photo"]:
            (self.data_dir / "photos" / e["photo"]).unlink(missing_ok=True)
        self.db.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
        self.log(case_id, "Eintrag gelöscht", e["label"])

    def set_photo(self, case_id: int, entity_id: int, content: bytes, filename: str) -> dict[str, Any]:
        e = self._entity(case_id, entity_id)
        ext = Path(filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise Invalid("Nur JPG, PNG oder WEBP erlaubt.")
        if len(content) > 8_000_000:
            raise Invalid("Bild ist größer als 8 MB.")
        try:
            from io import BytesIO

            from PIL import Image
            img = Image.open(BytesIO(content))
            img.verify()
        except Exception as exc:  # noqa: BLE001
            raise Invalid("Datei ist kein gültiges Bild.") from exc
        name = f"{entity_id}_{hashlib.sha256(content).hexdigest()[:16]}{'.jpg' if ext == '.jpeg' else ext}.enc"
        if e["photo"]:
            (self.data_dir / "photos" / e["photo"]).unlink(missing_ok=True)
        (self.data_dir / "photos" / name).write_bytes(self.vault.encrypt(content))
        self.db.update("entities", entity_id, {"photo": name})
        self.log(case_id, "Foto hinterlegt", e["label"])
        return self.get_entity(case_id, entity_id)

    def photo_bytes(self, case_id: int, entity_id: int) -> tuple[bytes, str] | None:
        """Entschlüsseltes Foto und Medientyp (Altbestände ohne Verschlüsselung werden ebenfalls gelesen)."""
        path = self.photo_path(case_id, entity_id)
        if not path:
            return None
        name = path.name.removesuffix(".enc")
        media = {"png": "image/png", "webp": "image/webp"}.get(name.rsplit(".", 1)[-1], "image/jpeg")
        return self.vault.decrypt(path.read_bytes()), media

    def photo_path(self, case_id: int, entity_id: int) -> Path | None:
        e = self._entity(case_id, entity_id)
        if not e["photo"]:
            return None
        p = self.data_dir / "photos" / e["photo"]
        return p if p.exists() else None

    # ------------------------------------------------------------------ Identifikatoren
    def add_identifier(self, case_id: int, entity_id: int, payload: dict[str, Any], log: bool = True, source: str = "Analyst") -> dict[str, Any]:
        e = self._entity(case_id, entity_id)
        kind = payload.get("kind") or "other"
        value = (payload.get("value") or "").strip()
        if kind not in IDENTIFIER_KINDS:
            raise Invalid("Unbekannte Art des Identifikators.")
        if not value:
            raise Invalid("Bitte einen Wert eingeben.")
        if kind == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise Invalid("Ungültige E-Mail-Adresse.")
        if kind == "phone" and len(re.sub(r"\D", "", value)) < 6:
            raise Invalid("Telefonnummer zu kurz.")
        norm = normalize(kind, value)
        existing = self.db.one("SELECT * FROM identifiers WHERE entity_id = ? AND kind = ? AND normalized = ?", (entity_id, kind, norm))
        if existing:
            return existing
        iid = self.db.insert("identifiers", {"case_id": case_id, "entity_id": entity_id, "kind": kind, "value": value,
                                             "normalized": norm, "source": payload.get("source") or source,
                                             "verified": 1 if payload.get("verified") else 0, "created_at": now_iso()})
        if log:
            self.log(case_id, "Identifikator ergänzt", f"{e['label']}: {IDENTIFIER_KINDS[kind]} = {value}")
            self.touch(case_id)
        return self.db.one("SELECT * FROM identifiers WHERE id = ?", (iid,))  # type: ignore[return-value]

    def delete_identifier(self, case_id: int, ident_id: int) -> None:
        row = self.db.one("SELECT * FROM identifiers WHERE id = ? AND case_id = ?", (ident_id, case_id))
        if not row:
            raise NotFound("Identifikator nicht gefunden.")
        self.db.execute("DELETE FROM identifiers WHERE id = ?", (ident_id,))
        self.log(case_id, "Identifikator entfernt", f"{row['kind']}: {row['value']}")

    # ------------------------------------------------------------------ Suche
    def available_sources(self) -> list[dict[str, Any]]:
        return [{"key": s.key, "label": s.label, "description": s.description, "kinds": list(s.kinds),
                 "kind_labels": [IDENTIFIER_KINDS[k] for k in s.kinds], "group": s.group} for s in SOURCES]

    def plan_search(self, case_id: int, entity_id: int, source_keys: list[str] | None = None) -> list[tuple[str, str, str]]:
        idents = self.db.all("SELECT * FROM identifiers WHERE entity_id = ? AND case_id = ?", (entity_id, case_id))
        keys = source_keys or [s.key for s in SOURCES]
        plan: list[tuple[str, str, str]] = []
        for key in keys:
            src = SOURCE_MAP.get(key)
            if not src:
                continue
            seen = set()
            for ident in idents:
                kind = "name" if ident["kind"] == "alias" else ident["kind"]
                if kind in src.kinds and ident["normalized"] not in seen:
                    seen.add(ident["normalized"])
                    # Benutzernamen/E-Mails normalisiert abfragen (ohne @, Kleinschreibung)
                    value = ident["normalized"] if kind in {"username", "email"} else ident["value"]
                    plan.append((key, kind, value))
        return plan

    def run_search(self, case_id: int, entity_id: int, source_keys: list[str] | None = None) -> dict[str, Any]:
        case = self.get_case(case_id)
        subject = self.get_entity(case_id, entity_id)
        plan = self.plan_search(case_id, entity_id, source_keys)
        if not plan:
            raise Invalid("Keine passenden Identifikatoren für die gewählten Quellen. Bitte z. B. Name, Benutzername oder E-Mail ergänzen.")
        sid = self.db.insert("searches", {"case_id": case_id, "entity_id": entity_id, "started_at": now_iso(),
                                          "queries": [{"source": k, "kind": kd, "value": v} for k, kd, v in plan]})
        status: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(SOURCE_MAP[k].run, kd, v, self.http): (k, kd, v) for k, kd, v in plan}
            for fut in as_completed(futures):
                k, kd, v = futures[fut]
                try:
                    res = fut.result()
                    candidates.extend(res)
                    status.append({"source": SOURCE_MAP[k].label, "query": v, "ok": True, "count": len(res), "message": ""})
                except SourceError as exc:
                    status.append({"source": SOURCE_MAP[k].label, "query": v, "ok": False, "count": 0, "message": str(exc)})
                except Exception as exc:  # noqa: BLE001 - eine defekte Quelle darf die Suche nicht abbrechen
                    status.append({"source": SOURCE_MAP[k].label, "query": v, "ok": False, "count": 0, "message": f"Fehler: {exc}"})
        new = 0
        for c in candidates:
            score, reasons = score_candidate(subject, subject["identifiers"], c)
            fp = hashlib.sha1(f"{c['source_key']}|{c.get('url') or c.get('title')}".encode()).hexdigest()
            data = {**c.get("data", {}), "host": c.get("host", "")}
            try:
                self.db.insert("findings", {
                    "case_id": case_id, "entity_id": entity_id, "search_id": sid, "source": c["source"],
                    "category": c.get("category", ""), "title": str(c.get("title", ""))[:300], "url": c.get("url", ""),
                    "snippet": c.get("snippet", ""), "query": c.get("query", ""), "data": data, "score": score,
                    "reasons": reasons, "fingerprint": fp, "status": "neu", "created_at": now_iso()})
                new += 1
            except Exception:  # noqa: BLE001 - Duplikat (bereits bekannter Treffer)
                continue
        self.db.update("searches", sid, {"finished_at": now_iso(), "source_status": status, "result_count": new})
        ok = sum(1 for s in status if s["ok"])
        self.log(case_id, "Suche ausgeführt", f"{subject['label']}: {len(plan)} Abfragen, {ok} erfolgreich, {new} neue Treffer")
        self.touch(case_id)
        return {"search_id": sid, "case": case["reference"], "queries": len(plan), "new_findings": new,
                "total_candidates": len(candidates), "status": sorted(status, key=lambda s: (s["ok"], s["source"]))}

    def list_searches(self, case_id: int) -> list[dict[str, Any]]:
        return self.db.all("SELECT s.*, e.label AS entity_label FROM searches s LEFT JOIN entities e ON e.id = s.entity_id "
                           "WHERE s.case_id = ? ORDER BY s.id DESC", (case_id,))

    def list_findings(self, case_id: int, status: str | None = None, entity_id: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT f.*, e.label AS entity_label FROM findings f LEFT JOIN entities e ON e.id = f.entity_id WHERE f.case_id = ?"
        params: list[Any] = [case_id]
        if status:
            sql += " AND f.status = ?"
            params.append(status)
        if entity_id:
            sql += " AND f.entity_id = ?"
            params.append(entity_id)
        rows = self.db.all(sql + " ORDER BY CASE f.status WHEN 'neu' THEN 0 WHEN 'bestätigt' THEN 1 ELSE 2 END, f.score DESC, f.id DESC", params)
        for r in rows:
            r["confidence"] = confidence_label(r["score"])
        return rows

    def add_manual_finding(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        entity_id = int(payload.get("entity_id") or 0) or None
        if entity_id:
            self._entity(case_id, entity_id)
        title = (payload.get("title") or "").strip()
        if not title:
            raise Invalid("Bitte einen Titel für die Erkenntnis angeben.")
        fid = self.db.insert("findings", {
            "case_id": case_id, "entity_id": entity_id, "source": payload.get("source") or "Manuelle Erfassung",
            "category": payload.get("category") or "Hinweis", "title": title, "url": payload.get("url") or "",
            "snippet": payload.get("snippet") or "", "data": {}, "score": int(payload.get("score") or 60),
            "reasons": ["Manuell durch Analyst erfasst"], "fingerprint": hashlib.sha1(f"manual|{title}|{now_iso()}".encode()).hexdigest(),
            "status": "bestätigt" if payload.get("confirmed") else "neu", "created_at": now_iso(),
            "reviewed_at": now_iso() if payload.get("confirmed") else None})
        self.log(case_id, "Erkenntnis manuell erfasst", title)
        return self.db.one("SELECT * FROM findings WHERE id = ?", (fid,))  # type: ignore[return-value]

    def review_finding(self, case_id: int, finding_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        f = self.db.one("SELECT * FROM findings WHERE id = ? AND case_id = ?", (finding_id, case_id))
        if not f:
            raise NotFound("Treffer nicht gefunden.")
        status = payload.get("status")
        if status not in {"neu", "bestätigt", "verworfen"}:
            raise Invalid("Status muss neu, bestätigt oder verworfen sein.")
        user = current_user.get()
        self.db.update("findings", finding_id, {"status": status, "review_note": (payload.get("note") or "").strip(),
                                                "reviewed_at": now_iso(), "reviewed_by": user["display_name"] if user else "System"})
        created: list[str] = []
        if status == "bestätigt" and payload.get("add_to_graph", True) and f["entity_id"]:
            created = self._promote_finding(case_id, f)
        self.log(case_id, f"Treffer {status}", f"{f['title']} ({f['source']})" + (f" · Notiz: {payload.get('note')}" if payload.get("note") else ""))
        self.touch(case_id)
        out = self.db.one("SELECT * FROM findings WHERE id = ?", (finding_id,))
        out["created"] = created  # type: ignore[index]
        return out  # type: ignore[return-value]

    def _find_or_create(self, case_id: int, etype: str, label: str, data: dict[str, Any] | None = None) -> tuple[int, bool]:
        row = self.db.one("SELECT id FROM entities WHERE case_id = ? AND type = ? AND lower(label) = lower(?)", (case_id, etype, label))
        if row:
            return row["id"], False
        return self.db.insert("entities", {"case_id": case_id, "type": etype, "label": label, "data": data or {}, "created_at": now_iso()}), True

    def _link_once(self, case_id: int, s: int, t: int, relation: str, confidence: int, evidence: str) -> None:
        if self.db.one("SELECT id FROM links WHERE case_id = ? AND source_id = ? AND target_id = ? AND relation = ?", (case_id, s, t, relation)):
            return
        self.db.insert("links", {"case_id": case_id, "source_id": s, "target_id": t, "relation": relation,
                                 "confidence": confidence, "evidence": evidence, "created_at": now_iso()})

    def _promote_finding(self, case_id: int, f: dict[str, Any]) -> list[str]:
        """Übernimmt einen bestätigten Treffer als Knoten/Kante in den Verbindungsgraphen."""
        person = f["entity_id"]
        data = f["data"] or {}
        conf = max(40, min(95, f["score"]))
        created: list[str] = []
        evidence = f"{f['source']}: {f['url'] or f['title']}"
        if f["category"] == "Konto" and data.get("plattform"):
            label = f"{data['plattform']}: {data.get('benutzername') or f['title']}"
            eid, new = self._find_or_create(case_id, "konto", label, {"url": f["url"], "plattform": data["plattform"]})
            self._link_once(case_id, person, eid, "besitzt Konto", conf, evidence)
            created.append(label)
            if data.get("benutzername"):
                self.add_identifier(case_id, person, {"kind": "username", "value": str(data["benutzername"]).split("@")[0], "verified": True}, log=False, source=f["source"])
            if f["url"]:
                self.add_identifier(case_id, person, {"kind": "url", "value": f["url"], "verified": True}, log=False, source=f["source"])
            if data.get("organisation"):
                oid, _ = self._find_or_create(case_id, "organisation", str(data["organisation"]).lstrip("@"))
                self._link_once(case_id, person, oid, "arbeitet bei", max(30, conf - 20), evidence)
                created.append(str(data["organisation"]))
        elif f["category"] == "Beruf/Bildung":
            for inst in (data.get("institutionen") or [])[:3]:
                oid, _ = self._find_or_create(case_id, "organisation", inst)
                self._link_once(case_id, person, oid, "arbeitet bei", conf, evidence)
                created.append(inst)
        elif f["category"] == "Ort" and data.get("lat") is not None:
            label = f["title"].removeprefix("Ort: ").split(",")[0]
            oid, _ = self._find_or_create(case_id, "ort", label, {"lat": data["lat"], "lon": data["lon"]})
            self._link_once(case_id, person, oid, "hält sich auf in", conf, evidence)
            created.append(label)
        else:
            label = f["title"][:80]
            did, _ = self._find_or_create(case_id, "dokument", label, {"url": f["url"]})
            self._link_once(case_id, person, did, "erwähnt in", conf, evidence)
            created.append(label)
        return created

    # ------------------------------------------------------------------ Verbindungen
    def create_link(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        s, t = int(payload.get("source_id") or 0), int(payload.get("target_id") or 0)
        a, b = self._entity(case_id, s), self._entity(case_id, t)
        if s == t:
            raise Invalid("Eine Verbindung braucht zwei verschiedene Einträge.")
        relation = (payload.get("relation") or "").strip() or "sonstige Verbindung"
        conf = int(payload.get("confidence") or 50)
        if not 0 <= conf <= 100:
            raise Invalid("Sicherheit muss zwischen 0 und 100 liegen.")
        lid = self.db.insert("links", {"case_id": case_id, "source_id": s, "target_id": t, "relation": relation, "confidence": conf,
                                       "evidence": payload.get("evidence") or "", "note": payload.get("note") or "", "created_at": now_iso()})
        self.log(case_id, "Verbindung angelegt", f"{a['label']} — {relation} → {b['label']} ({conf} %)")
        self.touch(case_id)
        return self.db.one("SELECT * FROM links WHERE id = ?", (lid,))  # type: ignore[return-value]

    def delete_link(self, case_id: int, link_id: int) -> None:
        row = self.db.one("SELECT * FROM links WHERE id = ? AND case_id = ?", (link_id, case_id))
        if not row:
            raise NotFound("Verbindung nicht gefunden.")
        self.db.execute("DELETE FROM links WHERE id = ?", (link_id,))
        self.log(case_id, "Verbindung gelöscht", f"#{link_id} {row['relation']}")

    def list_links(self, case_id: int) -> list[dict[str, Any]]:
        return self.db.all("""SELECT l.*, a.label AS source_label, a.type AS source_type, b.label AS target_label, b.type AS target_type
                              FROM links l JOIN entities a ON a.id = l.source_id JOIN entities b ON b.id = l.target_id
                              WHERE l.case_id = ? ORDER BY l.id""", (case_id,))

    def graph(self, case_id: int, min_confidence: int = 0) -> dict[str, Any]:
        self.get_case(case_id)
        ents = self.db.all("SELECT id, type, label, is_subject, data, photo FROM entities WHERE case_id = ?", (case_id,))
        links = [l for l in self.list_links(case_id) if l["confidence"] >= min_confidence]
        adj = g.adjacency([e["id"] for e in ents], links)
        bc = g.betweenness(adj)
        groups = g.communities(adj)
        nodes = [{"id": e["id"], "label": e["label"], "type": e["type"], "type_label": ENTITY_TYPES.get(e["type"], e["type"]),
                  "subject": bool(e["is_subject"]), "degree": len(adj[e["id"]]), "betweenness": bc.get(e["id"], 0.0),
                  "group": groups.get(e["id"], 0), "has_photo": bool(e["photo"]),
                  "lat": (e["data"] or {}).get("lat"), "lon": (e["data"] or {}).get("lon")} for e in ents]
        edges = [{"id": l["id"], "source": l["source_id"], "target": l["target_id"], "relation": l["relation"],
                  "confidence": l["confidence"], "evidence": l["evidence"], "note": l["note"]} for l in links]
        key = sorted(nodes, key=lambda n: (-n["betweenness"], -n["degree"]))[:5]
        return {"nodes": nodes, "edges": edges,
                "key_nodes": [{"id": n["id"], "label": n["label"], "degree": n["degree"], "betweenness": n["betweenness"]} for n in key if n["degree"]],
                "group_count": len(set(groups.values())) if groups else 0}

    def find_paths(self, case_id: int, a: int, b: int, max_len: int = 5) -> dict[str, Any]:
        self._entity(case_id, a)
        self._entity(case_id, b)
        ents = {e["id"]: e for e in self.db.all("SELECT id, label, type FROM entities WHERE case_id = ?", (case_id,))}
        links = self.list_links(case_id)
        adj = g.adjacency(ents, links)
        edge_by_pair: dict[frozenset, dict] = {}
        for l in links:
            k = frozenset((l["source_id"], l["target_id"]))
            if k not in edge_by_pair or l["confidence"] > edge_by_pair[k]["confidence"]:
                edge_by_pair[k] = l
        paths = g.simple_paths(adj, a, b, max_len=max_len, limit=12)
        shortest = g.shortest_paths(adj, a, b)
        out = []
        for p in paths:
            steps = []
            conf = 1.0
            for x, y in zip(p, p[1:]):
                l = edge_by_pair[frozenset((x, y))]
                conf *= l["confidence"] / 100
                steps.append({"from": ents[x]["label"], "to": ents[y]["label"], "relation": l["relation"], "confidence": l["confidence"], "link_id": l["id"]})
            out.append({"nodes": p, "labels": [ents[n]["label"] for n in p], "length": len(p) - 1,
                        "combined_confidence": round(conf * 100), "steps": steps})
        out.sort(key=lambda x: (x["length"], -x["combined_confidence"]))
        common = sorted(adj.get(a, set()) & adj.get(b, set()))
        self.log(case_id, "Verbindungssuche", f"{ents[a]['label']} ↔ {ents[b]['label']}: {len(out)} Pfade")
        return {"paths": out, "shortest_length": (len(shortest[0]) - 1) if shortest else None,
                "common_neighbours": [{"id": c, "label": ents[c]["label"], "type": ents[c]["type"]} for c in common]}

    def suggestions(self, case_id: int) -> list[dict[str, Any]]:
        """Vorschläge für noch nicht erfasste Verbindungen (müssen geprüft werden)."""
        ents = {e["id"]: e for e in self.db.all("SELECT id, label, type FROM entities WHERE case_id = ?", (case_id,))}
        linked = {frozenset((l["source_id"], l["target_id"])) for l in self.list_links(case_id)}
        out: list[dict[str, Any]] = []
        seen: set[frozenset] = set()

        def add(a: int, b: int, reason: str, relation: str, conf: int) -> None:
            k = frozenset((a, b))
            if a == b or k in linked or k in seen:
                return
            seen.add(k)
            out.append({"source_id": a, "target_id": b, "source_label": ents[a]["label"], "target_label": ents[b]["label"],
                        "reason": reason, "relation": relation, "confidence": conf})

        rows = self.db.all("""SELECT a.entity_id AS a, b.entity_id AS b, a.kind, a.value FROM identifiers a
                              JOIN identifiers b ON a.normalized = b.normalized AND a.kind = b.kind AND a.entity_id < b.entity_id
                              WHERE a.case_id = ? AND b.case_id = ? AND a.kind != 'name'""", (case_id, case_id))
        for r in rows:
            kind = IDENTIFIER_KINDS.get(r["kind"], r["kind"])
            rel = "wohnt in" if r["kind"] == "location" else "identisch mit (vermutet)" if r["kind"] in {"email", "phone", "username"} else "Kontakt mit"
            add(r["a"], r["b"], f"Gemeinsamer Identifikator ({kind}): {r['value']}", rel, 60 if r["kind"] in {"email", "phone"} else 40)
        names = self.db.all("SELECT a.entity_id AS a, b.entity_id AS b, a.value FROM identifiers a JOIN identifiers b "
                            "ON a.normalized = b.normalized AND a.kind IN ('name','alias') AND b.kind IN ('name','alias') AND a.entity_id < b.entity_id "
                            "WHERE a.case_id = ?", (case_id,))
        for r in names:
            add(r["a"], r["b"], f"Gleicher Name „{r['value']}“ – möglicherweise dieselbe Person (Dublette?)", "identisch mit (vermutet)", 30)
        persons = [e for e in ents.values() if e["type"] == "person"]
        for f in self.db.all("SELECT entity_id, title, snippet, url FROM findings WHERE case_id = ? AND status = 'bestätigt'", (case_id,)):
            text = fold(f"{f['title']} {f['snippet']}")
            for p in persons:
                if p["id"] != f["entity_id"] and f["entity_id"] in ents and len(p["label"]) > 4 and fold(p["label"]) in text:
                    add(f["entity_id"], p["id"], f"Gemeinsame Erwähnung in bestätigter Quelle: {f['title'][:80]}", "Kontakt mit", 35)
        evs = self.db.all("SELECT entity_id, location FROM events WHERE case_id = ? AND entity_id IS NOT NULL AND location != ''", (case_id,))
        by_loc: dict[str, set[int]] = {}
        for ev in evs:
            by_loc.setdefault(fold(ev["location"].split(",")[0]), set()).add(ev["entity_id"])
        for loc, ids in by_loc.items():
            ids_l = sorted(i for i in ids if i in ents)
            for i, a in enumerate(ids_l):
                for b in ids_l[i + 1:]:
                    add(a, b, f"Beide in der Zeitleiste am selben Ort: {loc.title()}", "Kontakt mit", 30)
        adj = g.adjacency(ents, self.list_links(case_id))
        for a in persons:
            for b in persons:
                if a["id"] < b["id"]:
                    common = adj[a["id"]] & adj[b["id"]]
                    if len(common) >= 2:
                        add(a["id"], b["id"], f"{len(common)} gemeinsame Verbindungen: " + ", ".join(ents[c]["label"] for c in list(common)[:3]), "Kontakt mit", 45)
        return sorted(out, key=lambda s: -s["confidence"])

    # ------------------------------------------------------------------ Zeitleiste
    def create_event(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_case(case_id)
        when = (payload.get("occurred_at") or "").strip()
        if not when:
            raise Invalid("Bitte Datum/Uhrzeit angeben.")
        entity_id = int(payload.get("entity_id") or 0) or None
        if entity_id:
            self._entity(case_id, entity_id)
        lat, lon = payload.get("lat"), payload.get("lon")
        location = (payload.get("location") or "").strip()
        if location and (lat in (None, "") or lon in (None, "")) and self.auto_geocode:
            coords = geocode(location, self.http)
            lat, lon = coords if coords else (None, None)
        eid = self.db.insert("events", {
            "case_id": case_id, "entity_id": entity_id, "occurred_at": when, "kind": payload.get("kind") or "Ereignis",
            "location": location, "lat": float(lat) if lat not in (None, "") else None, "lon": float(lon) if lon not in (None, "") else None,
            "description": payload.get("description") or "", "source": payload.get("source") or "",
            "reliability": payload.get("reliability") or "ungeprüft", "created_at": now_iso()})
        self.log(case_id, "Zeitleiste ergänzt", f"{when} {payload.get('kind')}: {location}")
        self.touch(case_id)
        return self.db.one("SELECT * FROM events WHERE id = ?", (eid,))  # type: ignore[return-value]

    def list_events(self, case_id: int) -> list[dict[str, Any]]:
        return self.db.all("SELECT ev.*, e.label AS entity_label FROM events ev LEFT JOIN entities e ON e.id = ev.entity_id "
                           "WHERE ev.case_id = ? ORDER BY ev.occurred_at, ev.id", (case_id,))

    def delete_event(self, case_id: int, event_id: int) -> None:
        if not self.db.execute("DELETE FROM events WHERE id = ? AND case_id = ?", (event_id, case_id)):
            raise NotFound("Ereignis nicht gefunden.")
        self.log(case_id, "Zeitleisteneintrag gelöscht", f"#{event_id}")

    # ------------------------------------------------------------------ Vermisstenmodul
    def risk_assessment(self, person: dict[str, Any]) -> dict[str, Any]:
        data = person.get("data") or {}
        flags = set(data.get("risiko") or [])
        age = _age(data.get("geburtsdatum", ""))
        if age is not None:
            if age < 14:
                flags.add("kind")
            elif age < 18:
                flags.add("jugendlich")
            elif age > 75:
                flags.add("senior")
        points = sum(RISK_FACTORS[f][1] for f in flags if f in RISK_FACTORS)
        level = "hoch" if points >= 6 else "erhöht" if points >= 3 else "normal"
        advice = {
            "hoch": "Akute Gefahr möglich: sofort Polizei (110) informieren bzw. Kontakt zur zuständigen Dienststelle halten.",
            "erhöht": "Erhöhtes Risiko: Polizei einbinden, Suchmaßnahmen priorisieren und eng dokumentieren.",
            "normal": "Keine besonderen Risikofaktoren erfasst – Einschätzung regelmäßig überprüfen.",
        }[level]
        return {"age": age, "points": points, "level": level, "advice": advice,
                "factors": [{"key": f, "label": RISK_FACTORS[f][0], "weight": RISK_FACTORS[f][1]} for f in sorted(flags) if f in RISK_FACTORS]}

    def generate_tasks(self, case_id: int) -> list[dict[str, Any]]:
        case = self.get_case(case_id)
        existing = {t["title"] for t in self.db.all("SELECT title FROM tasks WHERE case_id = ?", (case_id,))}
        if case["case_type"] == "vermisst":
            template = [
                ("Vermisstenanzeige bei der Polizei sicherstellen und Aktenzeichen notieren", "hoch"),
                ("Letzte Sichtung exakt erfassen (Zeit, Ort, Kleidung, Begleitung)", "hoch"),
                ("Aktuelles Foto beschaffen und im Profil hinterlegen", "hoch"),
                ("Engste Kontaktpersonen befragen (Familie, Freunde, Partner, Arbeit/Schule)", "hoch"),
                ("Krankenhäuser und Notaufnahmen im Umkreis abfragen", "hoch"),
                ("Letzte Online-Aktivität in sozialen Netzwerken prüfen", "normal"),
                ("Bekannte Anlaufpunkte und Lieblingsorte aufsuchen/abklären", "normal"),
                ("Bahnhöfe, ÖPNV, Taxiunternehmen als Bewegungsoptionen prüfen", "normal"),
                ("Hinweise auf mögliche Videoaufnahmen sammeln (Sicherung nur durch Polizei)", "normal"),
                ("Suchplakat erstellen (Export) und – in Abstimmung mit der Polizei – verbreiten", "normal"),
                ("Notunterkünfte, Beratungsstellen und Hilfseinrichtungen informieren", "normal"),
                ("Zeitleiste fortlaufend pflegen und Hinweise bewerten", "normal"),
            ]
        elif case["case_type"] == "investigativ":
            template = [
                ("Recherchehypothese und Leitfragen schriftlich festhalten", "hoch"),
                ("Quellenschutz klären: Fall als vertraulich markieren, Kontaktwege zu Hinweisgebenden absichern", "hoch"),
                ("Akteure, Organisationen und Identifikatoren vollständig erfassen", "hoch"),
                ("Automatische Quellensuche ausführen und Treffer einzeln prüfen", "hoch"),
                ("Register prüfen: Handelsregister, Beteiligungen (North Data), Grundbuch-/Gerichtsauskünfte soweit zulässig", "normal"),
                ("Belege sichern (Archivkopie/Screenshot mit Datum) bevor Inhalte verschwinden", "hoch"),
                ("Verbindungen im Graphen modellieren, Pfade zwischen Schlüsselakteuren prüfen", "normal"),
                ("Gegenrecherche: entlastende Informationen und alternative Erklärungen suchen", "hoch"),
                ("Jede Kernaussage mit mindestens zwei unabhängigen Quellen belegen", "hoch"),
                ("Betroffene vor Veröffentlichung mit konkreten Vorwürfen konfrontieren, Frist und Antwort dokumentieren", "hoch"),
                ("Vier-Augen-Prüfung (Prüfperson zuweisen, Status „zur Prüfung“)", "normal"),
                ("Recherchedossier exportieren; personenbezogene Daten nach Abschluss löschen bzw. minimieren", "normal"),
            ]
        else:
            template = [
                ("Zweck und Rechtsgrundlage der Recherche dokumentieren und prüfen", "hoch"),
                ("Bekannte Identifikatoren erfassen (Namen, Aliasse, Benutzernamen, E-Mail, Telefon, Orte)", "hoch"),
                ("Automatische Quellensuche ausführen und Treffer einzeln prüfen", "hoch"),
                ("Manuelle Recherchelinks (Suchmaschinen, Netzwerke, Register) abarbeiten", "normal"),
                ("Bestätigte Konten auf weitere Verknüpfungen (Freunde, Arbeitgeber, Orte) prüfen", "normal"),
                ("Verbindungen im Graphen modellieren und Schlüsselpersonen identifizieren", "normal"),
                ("Widersprüche und offene Fragen dokumentieren", "normal"),
                ("Dossier exportieren und Ergebnisse vier-Augen-prüfen lassen", "normal"),
            ]
        made = []
        for title, prio in template:
            if title not in existing:
                made.append(self.db.insert("tasks", {"case_id": case_id, "title": title, "priority": prio, "origin": "Leitfaden", "created_at": now_iso()}))
        if made:
            self.log(case_id, "Leitfaden-Aufgaben erzeugt", f"{len(made)} Aufgaben")
        return self.list_tasks(case_id)

    def list_tasks(self, case_id: int) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM tasks WHERE case_id = ? ORDER BY done, CASE priority WHEN 'hoch' THEN 0 ELSE 1 END, id", (case_id,))

    def create_task(self, case_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_case(case_id)
        title = (payload.get("title") or "").strip()
        if not title:
            raise Invalid("Bitte eine Aufgabe eingeben.")
        tid = self.db.insert("tasks", {"case_id": case_id, "title": title, "detail": payload.get("detail") or "",
                                       "priority": payload.get("priority") or "normal", "created_at": now_iso()})
        return self.db.one("SELECT * FROM tasks WHERE id = ?", (tid,))  # type: ignore[return-value]

    def update_task(self, case_id: int, task_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        t = self.db.one("SELECT * FROM tasks WHERE id = ? AND case_id = ?", (task_id, case_id))
        if not t:
            raise NotFound("Aufgabe nicht gefunden.")
        values = {}
        if "done" in payload:
            values["done"] = 1 if payload["done"] else 0
        for k in ("title", "detail", "priority"):
            if payload.get(k):
                values[k] = payload[k]
        self.db.update("tasks", task_id, values)
        if "done" in values:
            self.log(case_id, "Aufgabe erledigt" if values["done"] else "Aufgabe wieder geöffnet", t["title"])
        return self.db.one("SELECT * FROM tasks WHERE id = ?", (task_id,))  # type: ignore[return-value]

    def delete_task(self, case_id: int, task_id: int) -> None:
        self.db.execute("DELETE FROM tasks WHERE id = ? AND case_id = ?", (task_id, case_id))

    # ------------------------------------------------------------------ Übersicht
    def subject(self, case_id: int) -> dict[str, Any] | None:
        row = self.db.one("SELECT id FROM entities WHERE case_id = ? AND is_subject = 1 ORDER BY id LIMIT 1", (case_id,))
        if not row:
            row = self.db.one("SELECT id FROM entities WHERE case_id = ? AND type = 'person' ORDER BY id LIMIT 1", (case_id,))
        return self.get_entity(case_id, row["id"]) if row else None

    def overview(self, case_id: int) -> dict[str, Any]:
        case = self.get_case(case_id)
        subj = self.subject(case_id)
        q = [("entities", "SELECT COUNT(*) FROM entities WHERE case_id = ?"),
             ("persons", "SELECT COUNT(*) FROM entities WHERE case_id = ? AND type = 'person'"),
             ("identifiers", "SELECT COUNT(*) FROM identifiers WHERE case_id = ?"),
             ("searches", "SELECT COUNT(*) FROM searches WHERE case_id = ?"),
             ("open_findings", "SELECT COUNT(*) FROM findings WHERE case_id = ? AND status = 'neu'"),
             ("confirmed", "SELECT COUNT(*) FROM findings WHERE case_id = ? AND status = 'bestätigt'"),
             ("rejected", "SELECT COUNT(*) FROM findings WHERE case_id = ? AND status = 'verworfen'"),
             ("links", "SELECT COUNT(*) FROM links WHERE case_id = ?"),
             ("events", "SELECT COUNT(*) FROM events WHERE case_id = ?"),
             ("open_tasks", "SELECT COUNT(*) FROM tasks WHERE case_id = ? AND done = 0"),
             ("exports", "SELECT COUNT(*) FROM audit WHERE case_id = ? AND action = 'Dossier exportiert'")]
        counts = self.db.one("SELECT " + ", ".join(f"({sql}) AS {name}" for name, sql in q), [case_id] * len(q)) or {}
        steps = [
            {"key": "fall", "label": "Fall mit Zweck & Rechtsgrundlage angelegt", "done": True, "tab": "overview"},
            {"key": "person", "label": "Zielperson erfasst", "done": bool(subj), "tab": "persons"},
            {"key": "ident", "label": "Mindestens 2 Identifikatoren (z. B. Benutzername, E-Mail, Ort)",
             "done": bool(subj) and len(subj["identifiers"]) >= 2, "tab": "persons"},
            {"key": "search", "label": "Quellensuche ausgeführt", "done": counts["searches"] > 0, "tab": "search"},
            {"key": "review", "label": "Treffer geprüft (bestätigt/verworfen)",
             "done": counts["searches"] > 0 and counts["open_findings"] == 0 and (counts["confirmed"] + counts["rejected"]) > 0, "tab": "search"},
            {"key": "links", "label": "Verbindungen erfasst", "done": counts["links"] > 0, "tab": "graph"},
            {"key": "dossier", "label": "Dossier als Word-Dokument exportiert", "done": counts["exports"] > 0, "tab": "dossier"},
        ]
        if case["case_type"] == "vermisst":
            steps.insert(3, {"key": "timeline", "label": "Letzte Sichtung in der Zeitleiste erfasst", "done": counts["events"] > 0, "tab": "timeline"})
        nxt = next((s for s in steps if not s["done"]), None)
        user = current_user.get()
        perms = sorted(self.permissions(case, user))
        return {"case": case, "subject": subj, "counts": counts, "steps": steps, "next_step": nxt, "permissions": perms,
                "team": self.case_team(case), "my_role": self.member_role(case, user) if user else None,
                "progress": round(100 * sum(s["done"] for s in steps) / len(steps)),
                "recent": self.db.all("SELECT * FROM audit WHERE case_id = ? ORDER BY id DESC LIMIT 8", (case_id,))}

    def audit(self, case_id: int) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM audit WHERE case_id = ? ORDER BY id DESC", (case_id,))

    def links_for(self, case_id: int, entity_id: int) -> list[dict[str, Any]]:
        idents = self.db.all("SELECT * FROM identifiers WHERE entity_id = ? AND case_id = ?", (entity_id, case_id))
        e = self._entity(case_id, entity_id)
        case = self.get_case(case_id)
        return research_links(e, idents, missing=case["case_type"] == "vermisst")
