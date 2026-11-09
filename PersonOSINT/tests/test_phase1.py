"""Phase 1: Anmeldung/2FA, Rollen & Rechte, Vier-Augen, vertrauliche Fälle, Sperren, Protokoll-Hash-Kette,
Verschlüsselung, Sicherung/Wiederherstellung und Migration von Version 1.0."""
from __future__ import annotations

import io
import sqlite3

import pytest
from fastapi.testclient import TestClient

from conftest import ADMIN_PW, H, add_user, build_app, login, make_settings, setup_admin
from personosint.api import create_app
from personosint.auth import new_totp_secret, totp_code, verify_totp
from personosint.backup import create_backup, restore_backup, verify_backup
from personosint.crypto import MAGIC
from personosint.db import MIGRATION_1, Database

CASE = {"title": "Recherche Firma X", "case_type": "verbindungen", "purpose": "Investigative Recherche zu Beteiligungen",
        "legal_basis": "Journalistische Recherche (Medienprivileg)", "subject": {"label": "Erika Beispiel"}}


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), (10, 120, 200)).save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- Anmeldung

def test_totp_rfc6238_vector():
    # RFC 6238, Anhang B: SHA1, Zeit 59 s -> 94287082 (8-stellig); hier 6-stellig = 287082
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_code(secret, at=59) == "287082"
    s = new_totp_secret()
    assert verify_totp(s, totp_code(s)) and not verify_totp(s, "000000" if totp_code(s) != "000000" else "111111")


def test_setup_login_and_mandatory_2fa(tmp_path, backend):
    app = build_app(tmp_path, backend, require_2fa=True)
    anon = TestClient(app)
    assert anon.get("/api/auth/state").json()["setup_required"] is True
    assert anon.get("/api/cases").status_code == 401
    weak = anon.post("/api/auth/setup", json={"username": "chefin", "password": "kurz"}, headers=H)
    assert weak.status_code == 422

    admin = setup_admin(app)
    st = admin.get("/api/auth/state").json()
    assert st["state"] == "mfa_setup"                 # 2FA ist Pflicht
    assert admin.get("/api/cases").status_code == 401  # vorher kein Zugriff
    assert admin.post("/api/auth/setup", json={"username": "x2", "password": ADMIN_PW}).status_code == 409

    setup = admin.post("/api/auth/totp/begin").json()
    secret = setup["secret"].replace(" ", "")
    assert setup["uri"].startswith("otpauth://totp/") and "<svg" in setup["qr_svg"]
    assert admin.post("/api/auth/totp/confirm", json={"code": "000000" if totp_code(secret) != "000000" else "111111"}).status_code == 422
    assert admin.post("/api/auth/totp/confirm", json={"code": totp_code(secret)}).status_code == 200
    assert admin.get("/api/cases").status_code == 200

    admin.post("/api/auth/logout")
    assert admin.get("/api/cases").status_code == 401
    again = login(app, "admin", ADMIN_PW)
    assert again.get("/api/auth/state").json()["state"] == "mfa"
    assert again.get("/api/cases").status_code == 401
    assert again.post("/api/auth/mfa", json={"code": "12345"}).status_code == 422
    assert again.post("/api/auth/mfa", json={"code": totp_code(secret)}).status_code == 200
    assert again.get("/api/cases").status_code == 200

    actions = [a["action"] for a in again.get("/api/admin/audit").json()]
    assert "Zwei-Faktor-Anmeldung eingerichtet" in actions and "Anmeldung" in actions


def test_lockout_and_no_user_enumeration(tmp_path):
    app = build_app(tmp_path)
    setup_admin(app)
    c = TestClient(app)
    unknown = c.post("/api/auth/login", json={"username": "gibtsnicht", "password": "x"}, headers=H)
    wrong = c.post("/api/auth/login", json={"username": "admin", "password": "falsch"}, headers=H)
    assert unknown.status_code == wrong.status_code == 401 and unknown.json() == wrong.json()
    for _ in range(4):
        c.post("/api/auth/login", json={"username": "admin", "password": "falsch"}, headers=H)
    locked = c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}, headers=H)
    assert locked.status_code == 423
    # Entsperren über Kommandozeilen-Logik
    from personosint.__main__ import main
    main(["--data", str(tmp_path), "unlock", "admin"])
    assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}, headers=H).status_code == 200


def test_cookie_flags_and_security_headers(tmp_path):
    app = build_app(tmp_path)
    c = TestClient(app)
    r = c.post("/api/auth/setup", json={"username": "admin", "display_name": "A", "password": ADMIN_PW}, headers=H)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    page = c.get("/")
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"


# ---------------------------------------------------------------- Rollen, Team, Vier-Augen

def test_roles_membership_and_four_eyes(tmp_path, backend):
    app = build_app(tmp_path, backend)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    ben = add_user(admin, app, "ben", "analyst")
    rita = add_user(admin, app, "rita", "pruefer")
    lea = add_user(admin, app, "lea", "leser")
    lisa = add_user(admin, app, "lisa", "leitung")

    assert lea.post("/api/cases", json=CASE).status_code == 403   # Leser legen keine Fälle an
    case = anna.post("/api/cases", json=CASE).json()
    cid = case["id"]
    assert case["owner_id"] == anna.uid

    # Fremde Analystin sieht den Fall nicht (404 statt 403: Existenz bleibt verborgen)
    assert ben.get(f"/api/cases/{cid}").status_code == 404
    assert cid not in [c["id"] for c in ben.get("/api/cases").json()]
    # Teamleitung und Administration sehen nicht-vertrauliche Fälle
    assert lisa.get(f"/api/cases/{cid}").status_code == 200
    assert admin.get(f"/api/cases/{cid}/overview").status_code == 200
    # Administration darf lesen, aber nicht recherchieren
    assert admin.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "X"}).status_code == 403

    # Team: Lea liest mit, Ben bearbeitet mit
    r = anna.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": lea.uid, "role": "leser"}, {"user_id": ben.uid, "role": "bearbeiter"}]})
    assert r.status_code == 200 and len(r.json()["members"]) == 2
    assert lea.get(f"/api/cases/{cid}/overview").json()["permissions"] == ["read"]
    assert lea.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "X"}).status_code == 403
    assert lea.get(f"/api/cases/{cid}/export/dossier.docx").status_code == 200
    assert ben.post(f"/api/cases/{cid}/entities", json={"type": "organisation", "label": "Firma X"}).status_code == 201
    assert ben.put(f"/api/cases/{cid}/members", json={"members": []}).status_code == 403   # nur Verantwortliche verwalten
    assert ben.delete(f"/api/cases/{cid}").status_code == 403

    # Vier-Augen-Prinzip
    version = anna.get(f"/api/cases/{cid}").json()["version"]
    assert anna.patch(f"/api/cases/{cid}", json={"reviewer_id": anna.uid, "version": version}).status_code == 422
    assert anna.patch(f"/api/cases/{cid}", json={"status": "zur Prüfung"}).status_code == 422          # ohne Prüfperson
    assert anna.patch(f"/api/cases/{cid}", json={"reviewer_id": rita.uid, "due_date": "2020-01-01", "version": version}).status_code == 200
    assert anna.patch(f"/api/cases/{cid}", json={"status": "zur Prüfung"}).status_code == 200
    assert cid in [c["id"] for c in rita.get("/api/cases?view=review").json()]
    assert cid in [c["id"] for c in anna.get("/api/cases?view=overdue").json()]
    assert cid in [c["id"] for c in anna.get("/api/cases?view=mine").json()]
    assert anna.patch(f"/api/cases/{cid}", json={"status": "freigegeben"}).status_code == 403          # eigener Fall
    assert lea.patch(f"/api/cases/{cid}", json={"status": "freigegeben"}).status_code == 403
    assert rita.patch(f"/api/cases/{cid}", json={"title": "Umbenannt"}).status_code == 403             # Prüfer ändert keine Stammdaten
    assert rita.patch(f"/api/cases/{cid}", json={"status": "freigegeben"}).status_code == 200
    audit = anna.get(f"/api/cases/{cid}/audit").json()
    release = next(a for a in audit if a["action"] == "Status geändert" and "freigegeben" in a["detail"])
    assert release["username"] == "rita"
    assert lisa.delete(f"/api/cases/{cid}").status_code == 204


def test_optimistic_locking_and_presence(tmp_path, backend):
    app = build_app(tmp_path, backend)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    ben = add_user(admin, app, "ben", "analyst")
    cid = anna.post("/api/cases", json=CASE).json()["id"]
    anna.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": ben.uid, "role": "bearbeiter"}]})
    subj = anna.get(f"/api/cases/{cid}/overview").json()["subject"]
    v = subj["version"]
    assert anna.patch(f"/api/cases/{cid}/entities/{subj['id']}", json={"data": {"beruf": "Journalistin"}, "version": v}).status_code == 200
    stale = ben.patch(f"/api/cases/{cid}/entities/{subj['id']}", json={"data": {"beruf": "Lehrerin"}, "version": v})
    assert stale.status_code == 409 and "geändert" in stale.json()["detail"]
    assert anna.get(f"/api/cases/{cid}/entities/{subj['id']}").json()["data"]["beruf"] == "Journalistin"

    anna.post(f"/api/cases/{cid}/presence", json={"tab": "persons"})
    others = ben.post(f"/api/cases/{cid}/presence", json={"tab": "graph"}).json()["others"]
    assert [o["name"] for o in others] == ["Anna"] and others[0]["tab"] == "persons"


def test_restricted_case_and_emergency_access(tmp_path, backend):
    app = build_app(tmp_path, backend)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    lisa = add_user(admin, app, "lisa", "leitung")
    cid = anna.post("/api/cases", json={**CASE, "restricted": True, "title": "Quellenschutz: Hinweisgeberin"}).json()["id"]
    assert lisa.get(f"/api/cases/{cid}").status_code == 404
    assert admin.get(f"/api/cases/{cid}").status_code == 404
    assert cid not in [c["id"] for c in lisa.get("/api/cases").json()]
    detail = [a for a in admin.get("/api/admin/audit").json() if a["case_id"] == cid]
    assert detail and all(a["detail"] == "[vertraulicher Fall]" for a in detail)
    listed = admin.get("/api/admin/restricted-cases").json()
    assert listed[0]["id"] == cid and "title" not in listed[0]

    assert admin.post(f"/api/admin/cases/{cid}/emergency-access", json={"reason": "kurz"}).status_code == 422
    assert admin.post(f"/api/admin/cases/{cid}/emergency-access", json={"reason": "Bearbeiterin dauerhaft erkrankt, Frist läuft ab"}).status_code == 200
    assert admin.get(f"/api/cases/{cid}").status_code == 200
    assert any(a["action"] == "NOTFALLZUGRIFF" for a in anna.get(f"/api/cases/{cid}/audit").json())


def test_admin_user_management(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    assert anna.get("/api/admin/users").status_code == 403
    assert admin.post("/api/admin/users", json={"username": "anna", "role": "analyst", "password": "Ganz-Neues-Pw#2026"}).status_code == 409
    me = next(u for u in admin.get("/api/admin/users").json() if u["username"] == "admin")
    assert admin.patch(f"/api/admin/users/{me['id']}", json={"active": False}).status_code == 422
    assert admin.patch(f"/api/admin/users/{anna.uid}", json={"active": False}).status_code == 200
    assert anna.get("/api/cases").status_code == 401          # Sitzung sofort beendet
    sysinfo = admin.get("/api/admin/system").json()
    assert sysinfo["database"] == "sqlite" and sysinfo["warnings"]


# ---------------------------------------------------------------- Protokoll, Verschlüsselung, Sicherung

def test_audit_hash_chain_detects_tampering_and_survives_deletion(tmp_path, backend):
    app = build_app(tmp_path, backend)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json=CASE).json()["id"]
    anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Zweite Person"})
    assert admin.get("/api/admin/audit/verify").json()["ok"]

    anna.delete(f"/api/cases/{cid}")
    res = admin.get("/api/admin/audit/verify").json()
    assert res["ok"] and res["redacted"] >= 2      # Inhalte geschwärzt, Kette weiter prüfbar
    db = app.state.platform.db
    assert db.scalar("SELECT COUNT(*) AS n FROM audit WHERE case_id = ? AND detail LIKE ?", (cid, "%Erika%")) == 0

    row = db.one("SELECT id FROM audit WHERE action = 'Benutzer angelegt'")
    db.execute("UPDATE audit SET detail = 'manipuliert' WHERE id = ?", (row["id"],))
    broken = admin.get("/api/admin/audit/verify").json()
    assert not broken["ok"] and broken["broken_at"] == row["id"] and "Detailtext" in broken["problem"]
    db.execute("DELETE FROM audit WHERE id = ?", (row["id"],))
    assert "Verkettung" in admin.get("/api/admin/audit/verify").json()["problem"]


def test_photos_encrypted_at_rest(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json=CASE).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    png = _png()
    assert anna.post(f"/api/cases/{cid}/entities/{sid}/photo", files={"file": ("f.png", png, "image/png")}).status_code == 200
    files = list((tmp_path / "photos").iterdir())
    assert len(files) == 1 and files[0].read_bytes().startswith(MAGIC) and png not in files[0].read_bytes()
    r = anna.get(f"/api/cases/{cid}/entities/{sid}/photo")
    assert r.content == png and r.headers["content-type"] == "image/png"
    assert anna.get(f"/api/cases/{cid}/export/dossier.docx").status_code == 200


def test_backup_restore_roundtrip_to_new_installation(tmp_path, backend):
    src_dir, dst_dir = tmp_path / "quelle", tmp_path / "ziel"
    app = build_app(src_dir, "sqlite")
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json=CASE).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    anna.post(f"/api/cases/{cid}/entities/{sid}/photo", files={"file": ("f.png", _png(), "image/png")})
    made = admin.post("/api/admin/backups").json()
    assert made["verified"] and made["tables"]["cases"] == 1
    assert admin.get("/api/admin/backups").json()[0]["name"] == made["name"]
    assert anna.get("/api/admin/backups").status_code == 403

    # Passphrasen-Sicherung, Einspielen in neue Installation (anderer Schlüssel, ggf. PostgreSQL)
    p = app.state.platform
    backup = create_backup(p.db, p.vault, src_dir, tmp_path / "bk", passphrase="lange geheime Passphrase")
    with pytest.raises(Exception):
        verify_backup(backup, None, "falsch")
    target_settings = make_settings(dst_dir, backend)
    from personosint.api import open_database
    from personosint.crypto import Vault
    dst_db, dst_vault = open_database(target_settings), Vault(target_settings.resolved_key_file)
    restore_backup(backup, dst_db, dst_vault, dst_dir, passphrase="lange geheime Passphrase")
    dst_db.close()
    app2 = create_app(settings=target_settings, auto_geocode=False, start_scheduler=False)
    anna2 = login(app2, "anna", "Eigenes-Kennwort#9x")
    ov = anna2.get(f"/api/cases/{cid}/overview").json()
    assert ov["case"]["title"] == CASE["title"] and ov["subject"]["label"] == "Erika Beispiel"
    assert anna2.get(f"/api/cases/{cid}/entities/{sid}/photo").content == _png()
    admin2 = login(app2, "admin", ADMIN_PW)
    assert admin2.get("/api/admin/audit/verify").json()["ok"]
    # neue Datensätze nach der Wiederherstellung (Zähler korrekt nachgezogen)
    assert anna2.post("/api/cases", json=CASE).status_code == 201
    with pytest.raises(Exception):
        restore_backup(backup, app2.state.platform.db, app2.state.platform.vault, dst_dir, passphrase="lange geheime Passphrase")


def test_migration_from_version_1_0(tmp_path):
    path = tmp_path / "personosint.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(MIGRATION_1.format(PK="INTEGER PRIMARY KEY AUTOINCREMENT", REAL="REAL"))
    conn.execute("INSERT INTO cases (reference, title, case_type, purpose, legal_basis, created_at, updated_at) "
                 "VALUES ('EE-2026-0001', 'Altfall', 'personensuche', 'Zweck der Altrecherche', 'Einwilligung', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')")
    conn.execute("INSERT INTO audit (case_id, ts, action, detail) VALUES (1, '2026-01-01T00:00:00+00:00', 'Fall angelegt', 'Altfall')")
    conn.commit()
    conn.close()
    app = build_app(tmp_path)
    db: Database = app.state.platform.db
    assert db.schema_version() == 3
    admin = setup_admin(app)
    assert admin.get("/api/admin/audit/verify").json()["ok"]
    cases = admin.get("/api/cases").json()
    assert cases[0]["title"] == "Altfall" and cases[0]["owner_id"] is None
    # Altfall ohne Verantwortliche: Administration weist zu
    anna = add_user(admin, app, "anna", "analyst")
    assert admin.patch("/api/cases/1", json={"owner_id": anna.uid}).status_code == 200
    assert anna.get("/api/cases/1").status_code == 200
