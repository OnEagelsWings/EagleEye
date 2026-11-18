"""Encrypted backup: container, run from the office while the app is open, check, rotate, restore."""
import io
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from eagleeye.application.buero import backups, service as buero
from eagleeye.bootstrap import recovery479, securebackup
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
PW = "Herbstlaub!Fenster_2026"
SECRET = "Sicherungsmarker Zielperson Wendelstein"


def _blob(payload: bytes, password=PW) -> bytes:
    raw = io.BytesIO()
    writer = securebackup.EncryptingWriter(raw, password)
    writer.write(payload)
    writer.finish()
    return raw.getvalue()


def test_container_detects_wrong_password_truncation_and_tampering():
    payload = bytes(range(256)) * 50000  # several chunks
    blob = _blob(payload)
    out = io.BytesIO()
    assert securebackup.decrypt_stream(io.BytesIO(blob), out, PW)["bytes"] == len(payload) and out.getvalue() == payload
    assert payload[:4096] not in blob
    with pytest.raises(securebackup.BackupError, match="Passwort falsch"):
        securebackup.decrypt_stream(io.BytesIO(blob), io.BytesIO(), "anderes Passwort 123")
    # Drop the final chunk exactly at a chunk boundary: still detected.
    header_len = len(securebackup.MAGIC) + 4 + int.from_bytes(blob[len(securebackup.MAGIC):len(securebackup.MAGIC) + 4], "big")
    first_len = int.from_bytes(blob[header_len:header_len + 4], "big")
    with pytest.raises(securebackup.BackupError, match="abgeschnitten"):
        securebackup.decrypt_stream(io.BytesIO(blob[:header_len + 4 + first_len]), io.BytesIO(), PW)
    flipped = bytearray(blob)
    flipped[-20] ^= 1
    with pytest.raises(securebackup.BackupError, match="beschädigt"):
        securebackup.decrypt_stream(io.BytesIO(bytes(flipped)), io.BytesIO(), PW)
    with pytest.raises(securebackup.BackupError, match="weitere Daten"):
        securebackup.decrypt_stream(io.BytesIO(blob + blob[-64:]), io.BytesIO(), PW)
    empty = _blob(b"")
    assert securebackup.decrypt_stream(io.BytesIO(empty), io.BytesIO(), PW)["bytes"] == 0
    with pytest.raises(securebackup.BackupError, match="12 Zeichen"):
        securebackup.check_password("zu kurz")


def _office_case(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    buero.attach_mandate(ctx, user, case_id, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                              "client_kind": "privat", "client_name": "Kunde Beispiel"})
    ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="s.txt",
                                               raw=(SECRET + " laut Quelle.\n\nZweiter Absatz.").encode(), title="Quelle")
    return ctx, user, case_id


def _post(client, path, **data):
    return client.post(path, data={"csrf": client.cookies.get(CSRF_COOKIE), **data}, follow_redirects=False)


@ws
def test_backup_from_the_office_check_rotate_and_remind(workspace, tmp_path_factory):
    app, client, *_ = workspace
    ctx, user, case_id = _office_case(workspace)
    folder = tmp_path_factory.mktemp("extern") / "Sicherungen"  # outside the workspace
    assert backups.reminder(ctx) == "Noch keine verschlüsselte Sicherung angelegt."
    page = client.get("/buero/sicherung")
    assert page.status_code == 200 and "Verschlüsselte Sicherung erstellen" in page.text
    assert _post(client, "/buero/sicherung/einstellungen", sicherung_ordner=str(Path(ctx.base_dir) / "data" / "x"),
                 sicherung_behalten="2", sicherung_intervall_tage="7").status_code == 422
    assert _post(client, "/buero/sicherung/einstellungen", sicherung_ordner=str(folder), sicherung_behalten="2",
                 sicherung_intervall_tage="7").status_code == 303

    assert "mindestens 12" in _post(client, "/buero/sicherung", password="kurz", repeat="kurz", notiert="on").text
    assert "stimmen nicht" in _post(client, "/buero/sicherung", password=PW, repeat=PW + "x", notiert="on").text
    assert "getrennt" in _post(client, "/buero/sicherung", password=PW, repeat=PW).text
    made = _post(client, "/buero/sicherung", password=PW, repeat=PW, notiert="on")
    assert made.status_code == 303 and made.headers["location"] == "/buero/sicherung?done=backup"
    files = sorted(folder.glob("*.eebak"))
    assert len(files) == 1 and securebackup.is_encrypted(files[0])
    raw = files[0].read_bytes()
    assert SECRET.encode() not in raw and b"SQLite format 3" not in raw, "nothing readable in the backup file"
    assert backups.reminder(ctx) == ""
    assert "Sicherung fällig" in backups.reminder(ctx, today=date.today() + timedelta(days=8))

    row = backups.backups(ctx, user)[0]
    wrong = _post(client, "/buero/sicherung/pruefen", backup_id=row["backup_id"], password="falsches Passwort 1")
    assert wrong.status_code == 422 and "Passwort falsch" in wrong.text
    assert _post(client, "/buero/sicherung/pruefen", backup_id=row["backup_id"], password=PW).status_code == 303
    assert backups.backups(ctx, user)[0]["verified_at"]
    download = client.get("/buero/sicherung/datei", params={"backup_id": row["backup_id"]})
    assert download.status_code == 200 and download.content == raw

    for _ in range(2):
        assert _post(client, "/buero/sicherung", password=PW, repeat=PW, notiert="on").status_code == 303
    assert len(list(folder.glob("*.eebak"))) == 2, "only the configured number is kept"
    assert backups.backups(ctx, user)[-1]["removed_at"]
    assert "entfernt" in client.get("/buero/sicherung").text


@ws
def test_restore_encrypted_backup_directly_and_through_the_launcher(workspace, tmp_path_factory, monkeypatch):
    app, client, *_ = workspace
    ctx, user, case_id = _office_case(workspace)
    tmp_path = tmp_path_factory.mktemp("ablage")
    result = securebackup.create(ctx.base_dir, tmp_path / "out", PW)
    path = Path(result["path"])
    assert securebackup.verify(path, PW)["files"] == result["files"]

    receipt = securebackup.restore(path, PW, tmp_path / "wiederhergestellt")
    assert receipt["encrypted_backup"] and receipt["verified_files"] == result["files"]
    db = sqlite3.connect(tmp_path / "wiederhergestellt" / "data" / "eagleeye.db")
    try:
        assert db.execute("SELECT aktenzeichen FROM buero_mandates WHERE case_id=?", (case_id,)).fetchone()
        assert db.execute("SELECT COUNT(*) FROM phase15_team_sessions WHERE revoked=0").fetchone()[0] == 0
    finally:
        db.close()
    assert not list(tmp_path.glob("eagleeye-restore-*.zip")), "no decrypted archive is left behind"

    monkeypatch.setattr(securebackup, "ask_password", lambda: PW)
    code = recovery479.main(["--install-root", str(tmp_path), "--restore", "--archive", str(path),
                             "--target", str(tmp_path / "ueber_batch")])
    assert code == 0 and (tmp_path / "ueber_batch" / "data" / "eagleeye.db").is_file()
    monkeypatch.setattr(securebackup, "ask_password", lambda: "falsches Passwort 1")
    assert recovery479.main(["--install-root", str(tmp_path), "--restore", "--archive", str(path),
                             "--target", str(tmp_path / "falsch")]) == 1
    assert not (tmp_path / "falsch").exists()


@ws
def test_only_office_management_handles_backups(workspace):
    app, client, user, *_ = workspace
    ctx = app.state.context
    ctx.team_identity_359.create_user(identity=user, username="anna", display_name="Anna Beispiel",
                                      global_role="investigator", password=PW)
    csrf_session(workspace, "anna", PW)
    assert client.get("/buero/sicherung").status_code == 403
    assert _post(client, "/buero/sicherung", password=PW, repeat=PW, notiert="on").status_code == 403
    with pytest.raises(PermissionError):
        backups.run(ctx, ctx.team_identity_359.public_user("anna"), {"password": PW, "repeat": PW, "notiert": "on"})
    assert "Datensicherung" not in client.get("/buero").text


@ws
def test_backup_is_consistent_with_imports_and_deletions_during_the_run(workspace, tmp_path_factory):
    app, client, *_ = workspace
    ctx, user, case_id = _office_case(workspace)
    out = tmp_path_factory.mktemp("konsistenz")
    imported = []

    def concurrent_import(stage):
        if stage == "after_snapshot" and not imported:
            imported.append(ctx.document_intelligence_458.import_bytes(
                identity=user, case_id=case_id, filename="neu.txt", raw=b"Neu importiert waehrend der Sicherung.\n\nZwei.",
                title="Neu")["document_id"])
    result = securebackup.create(ctx.base_dir, out, PW, _hook=concurrent_import)
    assert result["missing_documents"] == [] and result["attempts"] == 1
    receipt = securebackup.restore(Path(result["path"]), PW, out / "r1")
    db = sqlite3.connect(out / "r1" / "data" / "eagleeye.db")
    try:
        for (rel,) in db.execute("SELECT stored_relpath FROM phase20_document_458"):
            assert (out / "r1" / "data" / "documents_458" / rel).is_file(), rel
        assert db.execute("SELECT COUNT(*) FROM phase20_document_458 WHERE document_id=?", (imported[0],)).fetchone()[0] == 0
    finally:
        db.close()
    assert receipt["verified_files"] == result["files"]

    victim = next(Path(ctx.base_dir, "data", "documents_458").glob("*.bin"))
    calls = []

    def concurrent_delete(stage):
        calls.append(stage)
        victim.unlink(missing_ok=True)
    warned = securebackup.create(ctx.base_dir, out, PW, _hook=concurrent_delete)
    assert warned["attempts"] == 3 and warned["missing_documents"] == ["data/documents_458/" + victim.name]
    assert len(list(out.glob("*.eebak"))) == 2, "failed attempts leave no extra files"
    assert securebackup.is_encrypted(warned["path"])


@ws
def test_rotation_keeps_the_newest_and_waits_for_unplugged_drives(workspace, tmp_path_factory, monkeypatch):
    app, client, *_ = workspace
    ctx, user, case_id = _office_case(workspace)
    drive = tmp_path_factory.mktemp("laufwerk") / "E"
    other = tmp_path_factory.mktemp("intern") / "Sicherungen"
    form = {"password": PW, "repeat": PW, "notiert": "on"}
    backups.save_settings(ctx, user, {"sicherung_ordner": str(drive), "sicherung_behalten": "1", "sicherung_intervall_tage": "7"})
    monkeypatch.setattr(backups, "_now", lambda: "2026-11-18T10:00:00+00:00")  # same second for every backup
    first = backups.run(ctx, user, form)
    second = backups.run(ctx, user, form)
    kept = [r["backup_id"] for r in backups.backups(ctx, user) if not r["removed_at"]]
    assert kept == [second["backup_id"]], "the newest backup survives a timestamp tie"

    unplugged = drive.with_name("E_abgezogen")
    drive.rename(unplugged)
    backups.save_settings(ctx, user, {"sicherung_ordner": str(other), "sicherung_behalten": "1", "sicherung_intervall_tage": "7"})
    third = backups.run(ctx, user, form)
    state = {r["backup_id"]: r["removed_at"] for r in backups.backups(ctx, user)}
    assert state[second["backup_id"]] == "", "a backup on a disconnected drive is not forgotten"
    unplugged.rename(drive)
    backups.run(ctx, user, form)
    state = {r["backup_id"]: r["removed_at"] for r in backups.backups(ctx, user)}
    assert state[second["backup_id"]] and not list(drive.glob("*.eebak")), "deleted once the drive is back"
    assert state[first["backup_id"]] and state[third["backup_id"]]
