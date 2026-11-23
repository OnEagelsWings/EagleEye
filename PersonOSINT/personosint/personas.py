"""Legenden (Sockpuppets) für die manuelle Recherche – erfinden, verwalten, Einsatz protokollieren.

Grundsatz: Die automatischen Abfragen der Plattform brauchen **kein** Konto und übertragen keine Identität von Ihnen.
Eine Legende brauchen Sie nur, wenn Sie selbst auf Plattformen recherchieren, die eine Anmeldung verlangen.

Was hier geschieht
------------------
* **Erfinden**: ein fiktiver, unauffälliger Name, Benutzername, Geburtsjahr und Wohnort, dazu eine eigene
  Alias-E-Mail-Adresse nach Ihrem Muster (z. B. auf Ihrer eigenen Domain oder bei einem Alias-Dienst).
* **Verwalten**: Zugangsdaten verschlüsselt im Vault, Plattformen, auf denen Sie das Konto angelegt haben, Status
  (aktiv · ruhend · verbrannt).
* **Einsatz protokollieren**: welche Legende in welchem Fall benutzt wurde. Warnung, wenn eine Legende in mehreren
  Fällen auftaucht (Verknüpfungsgefahr) oder verbrannt ist.

Was hier bewusst **nicht** geschieht: Konten bei Plattformen werden nicht automatisch angelegt. Automatisch erzeugte
Konten fallen auf, werden gesperrt, verstoßen gegen die Nutzungsbedingungen und gefährden damit gerade die Tarnung.
Legen Sie Konten von Hand an, über den Anonymisierungs-Ausgang und mit einem eigenen Browserprofil je Legende.
Keine echten Personen nachahmen.
"""
from __future__ import annotations

import json
import re
import secrets
from typing import Any

from .db import now_iso

FIRST_F = ("Anna", "Laura", "Julia", "Sarah", "Lisa", "Katrin", "Sabine", "Nicole", "Melanie", "Jana", "Miriam", "Carina", "Tanja", "Svenja",
           "Kerstin", "Daniela", "Vanessa", "Nadine", "Simone", "Bianca", "Lea", "Marie", "Hanna", "Clara", "Johanna", "Leonie", "Paula", "Theresa")
FIRST_M = ("Michael", "Thomas", "Andreas", "Stefan", "Christian", "Markus", "Daniel", "Tobias", "Jan", "Sebastian", "Florian", "Matthias",
           "Alexander", "Patrick", "Dennis", "Philipp", "Tim", "Lukas", "Jonas", "Felix", "Marco", "Sven", "Oliver", "Benjamin", "Simon", "Kai")
LAST = ("Brandt", "Lorenz", "Hartmann", "Krüger", "Vogt", "Seidel", "Engel", "Kuhn", "Pohl", "Franke", "Sommer", "Winkler", "Busch", "Arnold",
        "Haas", "Graf", "Ludwig", "Böhm", "Kraus", "Albrecht", "Jansen", "Dietrich", "Walter", "Keller", "Möller", "Thiel", "Ernst", "Brinkmann",
        "Kolbe", "Reuter", "Wendt", "Busse", "Kröger", "Hahn", "Schütte", "Lindner", "Reimann", "Gärtner", "Ebert", "Stein")
CITIES = ("Kassel", "Bielefeld", "Würzburg", "Osnabrück", "Regensburg", "Göttingen", "Erfurt", "Rostock", "Kiel", "Ulm", "Trier", "Oldenburg",
          "Paderborn", "Heilbronn", "Magdeburg", "Koblenz", "Siegen", "Bamberg", "Lübeck", "Gießen")
HOBBIES = ("Fotografie", "Wandern", "Kochen", "Radfahren", "Gärtnern", "Lesen", "Brettspiele", "Laufen", "Angeln", "Heimwerken", "Reisen", "Yoga")
STATUSES = {"aktiv": "aktiv", "ruhend": "ruhend", "verbrannt": "verbrannt (enttarnt – nicht mehr verwenden)"}
CODEWORDS = ("ALBATROS", "BERNSTEIN", "DÜNE", "FJORD", "GRANIT", "HERBST", "IRIS", "KIESEL", "LOTSE", "MARSCH", "NEBEL", "OSTWIND",
             "PRISMA", "QUARZ", "RIFF", "SALZ", "TORF", "UFER", "WATT", "ZEDER")
UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


class PersonaError(ValueError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.translate(UMLAUT).casefold())


def alias_email(pattern: str, username: str) -> str:
    """Alias-Adresse nach Muster. Platzhalter: {user} (Benutzername) und {token} (zufällig, 6 Zeichen)."""
    pattern = (pattern or "").strip()
    if not pattern:
        return ""
    if "@" not in pattern or not any(p in pattern for p in ("{user}", "{token}")):
        raise PersonaError("Muster braucht ein @ und {user} oder {token}, z. B. {user}@alias.meinedomain.de oder recherche+{token}@meinedomain.de")
    token = secrets.token_hex(3)
    address = pattern.replace("{user}", username).replace("{token}", token).casefold()
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", address):
        raise PersonaError("Daraus entsteht keine gültige E-Mail-Adresse – Muster prüfen.")
    return address


def generate(email_pattern: str = "", gender: str = "") -> dict[str, Any]:
    """Vorschlag für eine fiktive Legende (nichts wird gespeichert oder irgendwo angelegt)."""
    gender = gender if gender in {"w", "m"} else secrets.choice(("w", "m"))
    first = secrets.choice(FIRST_F if gender == "w" else FIRST_M)
    last = secrets.choice(LAST)
    year = str(1972 + secrets.randbelow(30))
    city = secrets.choice(CITIES)
    f, l = _slug(first), _slug(last)
    username = secrets.choice((f"{f}.{l}{year[-2:]}", f"{f[0]}{l}{secrets.randbelow(90) + 10}", f"{f}_{l[:4]}{year[-2:]}",
                               f"{l}{f[:3]}{secrets.randbelow(900) + 100}"))
    hobbies = sorted({secrets.choice(HOBBIES) for _ in range(3)})
    return {"codename": f"{secrets.choice(CODEWORDS)}-{secrets.randbelow(900) + 100}", "display_name": f"{first} {last}", "username": username,
            "email_alias": alias_email(email_pattern, username) if email_pattern else "", "birth_year": year, "city": city,
            "bio": f"Wohnt in {city}. Interessen: {', '.join(hobbies)}.", "gender": gender}


class Personas:
    def __init__(self, p):
        self.p = p
        self.db = p.db

    # ------------------------------------------------------------------ Einstellungen
    def email_pattern(self) -> str:
        return self.p._setting("persona_email_pattern", "")  # noqa: SLF001

    def set_email_pattern(self, pattern: str) -> str:
        pattern = (pattern or "").strip()
        if pattern:
            alias_email(pattern, "test")  # prüft das Muster
        self.p._set_setting("persona_email_pattern", pattern)  # noqa: SLF001
        return pattern

    # ------------------------------------------------------------------ Verwaltung
    def _public(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        secret = row.pop("secret_enc", "")
        row["has_secret"] = bool(secret)
        row["status_label"] = STATUSES.get(row["status"], row["status"])
        uses = self.db.all("SELECT u.*, c.reference, c.title FROM persona_use u LEFT JOIN cases c ON c.id = u.case_id WHERE u.persona_id = ? "
                           "ORDER BY u.id DESC", (row["id"],))
        row["uses"] = uses[:20]
        row["case_count"] = len({u["case_id"] for u in uses if u["case_id"]})
        return row

    def list(self) -> list[dict[str, Any]]:
        return [self._public(r) for r in self.db.all("SELECT * FROM personas ORDER BY status, codename")]

    def get(self, pid: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM personas WHERE id = ?", (pid,))
        if not row:
            raise PersonaError("Legende nicht gefunden.")
        return row

    def save(self, data: dict[str, Any], actor: str, pid: int | None = None) -> dict[str, Any]:
        fields = {}
        for key, limit in (("codename", 60), ("display_name", 80), ("username", 60), ("email_alias", 120), ("birth_year", 4), ("city", 60),
                           ("bio", 600), ("notes", 2000)):
            if key in data:
                fields[key] = " ".join(str(data.get(key) or "").split())[:limit] if key not in {"bio", "notes"} else str(data.get(key) or "")[:limit]
        if "egress_profile" in data:
            eg = str(data.get("egress_profile") or "")
            if eg:
                prof = self.p.egress_profile(eg)
                if prof.kind != "proxy":
                    raise PersonaError("Eine Legende braucht einen Anonymisierungs-Ausgang (Tor oder Proxy), nicht den Direktzugang.")
            fields["egress_profile"] = eg
        if "status" in data:
            if data["status"] not in STATUSES:
                raise PersonaError("Unbekannter Status.")
            fields["status"] = data["status"]
        if "platforms" in data:
            plats = [" ".join(str(x).split())[:60] for x in (data.get("platforms") or []) if str(x).strip()]
            fields["platforms"] = json.dumps(plats[:30])
        if data.get("secret") is not None:
            secret = str(data.get("secret") or "")
            fields["secret_enc"] = self.p.vault.encrypt_text(secret) if secret else ""
        fields["updated_at"] = now_iso()
        if pid is None:
            if not fields.get("codename") or not fields.get("display_name"):
                raise PersonaError("Deckname und Name der Legende fehlen.")
            if self.db.one("SELECT id FROM personas WHERE codename = ?", (fields["codename"],)):
                raise PersonaError("Diesen Decknamen gibt es schon.")
            fields.update(created_by=actor, created_at=fields["updated_at"])
            fields.setdefault("platforms", "[]")
            pid = self.db.insert("personas", fields)
            self.p.log(None, "Legende angelegt", fields["codename"])
        else:
            self.get(pid)
            self.db.update("personas", pid, fields)
            if fields.get("status") == "verbrannt":
                self.p.log(None, "Legende als verbrannt markiert", self.get(pid)["codename"])
        return self._public(self.get(pid))

    def secret(self, pid: int) -> str:
        row = self.get(pid)
        self.p.log(None, "Zugangsdaten einer Legende angezeigt", row["codename"])
        return self.p.vault.decrypt_text(row["secret_enc"]) if row["secret_enc"] else ""

    def delete(self, pid: int) -> None:
        row = self.get(pid)
        self.db.execute("DELETE FROM personas WHERE id = ?", (pid,))
        self.p.log(None, "Legende gelöscht", row["codename"])

    # ------------------------------------------------------------------ Einsatz
    def use(self, pid: int, case_id: int | None, purpose: str, actor: str) -> dict[str, Any]:
        row = self.get(pid)
        warnings = []
        if row["status"] == "verbrannt":
            raise PersonaError("Diese Legende ist als verbrannt markiert und darf nicht mehr verwendet werden.")
        if row["status"] == "ruhend":
            warnings.append("Die Legende ist als ruhend markiert.")
        other = {u["case_id"] for u in self.db.all("SELECT case_id FROM persona_use WHERE persona_id = ? AND case_id IS NOT NULL", (pid,))}
        if case_id and other - {case_id}:
            warnings.append(f"Diese Legende wurde schon in {len(other - {case_id})} anderen Fall/Fällen benutzt. Wer beide Recherchen sieht, "
                            "kann sie verknüpfen – für heikle Fälle eine eigene Legende nehmen.")
        self.db.insert("persona_use", {"persona_id": pid, "case_id": case_id, "purpose": str(purpose or "")[:300], "used_by": actor, "used_at": now_iso()})
        self.p.log(case_id, "Legende eingesetzt", f"{row['codename']}: {str(purpose or '')[:120]}")
        return {"persona": self._public(self.get(pid)), "warnings": warnings}

    def for_case(self, case_id: int) -> list[dict[str, Any]]:
        ids = [r["persona_id"] for r in self.db.all("SELECT DISTINCT persona_id FROM persona_use WHERE case_id = ?", (case_id,))]
        return [self._public(self.get(i)) for i in ids]


__all__ = ["Personas", "PersonaError", "generate", "alias_email", "STATUSES"]
