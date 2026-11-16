"""Kommandozeile: Server starten und Verwaltungsaufgaben.

    python -m personosint                      Server starten (Standard)
    python -m personosint create-user          Benutzer anlegen
    python -m personosint backup               verschlüsselte Sicherung erstellen
    python -m personosint verify-backup DATEI  Sicherung prüfen
    python -m personosint restore DATEI        Sicherung in leere Installation einspielen
    python -m personosint verify-audit         Hash-Kette des Protokolls prüfen
    python -m personosint reset-2fa NAME | unlock NAME | reset-password NAME
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import threading
import webbrowser
from pathlib import Path


def _lan_addresses() -> list[str]:
    """Rechnername und Adressen dieses Rechners im eigenen Netz (für den Serverbetrieb)."""
    import socket

    names = {socket.gethostname().casefold()}
    try:
        names.add(socket.getfqdn().casefold())
        for info in socket.getaddrinfo(socket.gethostname(), None):
            names.add(info[4][0].split("%", 1)[0])
    except OSError:
        pass
    try:  # die Adresse, über die dieser Rechner nach außen spricht – ohne dass dabei ein Paket gesendet wird
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            names.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(n for n in names if n and n not in {"localhost", "127.0.0.1", "::1"} and not n.startswith("127."))


def _settings(args):
    from .config import Settings

    s = Settings()
    if getattr(args, "data", None):
        s.data_dir = Path(args.data)
    if getattr(args, "server", False):
        # Serverbetrieb im eigenen Netz: von anderen Rechnern erreichbar, Zwei-Faktor-Anmeldung immer Pflicht
        s.require_2fa = True
        s.allowed_hosts = list(dict.fromkeys(list(s.allowed_hosts) + _lan_addresses()))
    return s


def _open(args):
    from .api import open_database
    from .auth import Auth
    from .crypto import Vault
    from .service import Platform

    s = _settings(args)
    vault = Vault(s.resolved_key_file)
    db = open_database(s)
    return s, db, vault, Auth(db, vault, s), Platform(db, s.data_dir, vault=vault, auto_geocode=False)


def _new_password(prompt: str = "Neues Passwort") -> str:
    env = os.environ.get("EAGLEEYE_INITIAL_PASSWORD")
    if env:
        return env
    pw = getpass.getpass(f"{prompt}: ")
    if pw != getpass.getpass("Wiederholen: "):
        sys.exit("Die Passwörter stimmen nicht überein.")
    return pw


def _passphrase(s, needed: bool = False) -> str:
    if s.backup_passphrase:
        return s.backup_passphrase
    return getpass.getpass("Passphrase der Sicherung: ") if needed else ""


def cmd_serve(args) -> None:
    import uvicorn

    from .api import create_app

    if getattr(args, "server", False) and args.host in ("127.0.0.1", "localhost"):
        args.host = "0.0.0.0"  # noqa: S104 - ausdrücklich gewählter Serverbetrieb
    app = create_app(settings=_settings(args))
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = f"http://{shown}:{args.port}/"
    print(f"EagleEye PersonOSINT läuft unter {url}  (Daten: {app.state.settings.data_dir}, Datenbank: {app.state.platform.db.dialect})")
    if getattr(args, "server", False):
        others = [a for a in _lan_addresses() if not a.startswith("fe80")]
        print("SERVERBETRIEB – von anderen Rechnern im eigenen Netz erreichbar unter:")
        for a in others:
            print(f"    http://{'[' + a + ']' if ':' in a else a}:{args.port}/")
        print("  · Zwei-Faktor-Anmeldung ist Pflicht. Jede Person braucht ein eigenes Konto (Verwaltung → Benutzer).")
        print("  · Die Verbindung ist im eigenen Netz unverschlüsselt (http). Für Zugriff von außerhalb oder über WLAN mit Fremden")
        print("    bitte den HTTPS-Betrieb nutzen (README → Teambetrieb mit Docker) – nicht einfach den Port im Router freigeben.")
        print("  · Windows fragt beim ersten Start nach der Firewall-Freigabe: nur „Private Netzwerke“ erlauben.")
    print("Beenden mit Strg+C")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", proxy_headers=True,
                forwarded_allow_ips=os.environ.get("EAGLEEYE_TRUSTED_PROXIES", "127.0.0.1"))


def cmd_create_user(args) -> None:
    from .auth import ROLES

    _, _, _, auth, p = _open(args)
    if args.role not in ROLES:
        sys.exit(f"Rolle muss eine von {', '.join(ROLES)} sein.")
    user = auth.create_user(args.username, args.name or args.username, args.role, _new_password("Passwort"), must_change=not args.no_change)
    p.log(None, "Benutzer angelegt (Kommandozeile)", f"{user['username']} ({ROLES[user['role']]})")
    print(f"Benutzer {user['username']} angelegt ({ROLES[user['role']]}).")


def cmd_user_admin(args) -> None:
    _, db, _, auth, p = _open(args)
    user = db.one("SELECT * FROM users WHERE username = ?", (args.username.casefold(),))
    if not user:
        sys.exit("Benutzer nicht gefunden.")
    payload = {"reset-2fa": {"reset_2fa": True}, "unlock": {"unlock": True}}.get(args.command)
    if args.command == "reset-password":
        payload = {"new_password": _new_password(), "unlock": True}
    auth.update_user(user["id"], payload, actor_id=-1)
    p.log(None, f"Kommandozeile: {args.command}", user["username"])
    print("Erledigt. Bestehende Sitzungen der Person wurden beendet.")


def cmd_backup(args) -> None:
    from .backup import create_backup, prune_backups, verify_backup

    s, db, vault, _, p = _open(args)
    out = Path(args.out) if args.out else s.resolved_backup_dir
    path = create_backup(db, vault, s.data_dir, out, _passphrase(s))
    prune_backups(out, s.backup_keep)
    check = verify_backup(path, vault, _passphrase(s))
    p.log(None, "Sicherung erstellt (Kommandozeile)", path.name)
    print(f"Sicherung: {path}  ({path.stat().st_size // 1024} KB, geprüft: {'OK' if check['ok'] else 'FEHLER'})")


def cmd_verify_backup(args) -> None:
    from .backup import BackupError, verify_backup
    from .crypto import Vault

    s = _settings(args)
    vault = Vault(Path(args.key)) if args.key else (Vault(s.resolved_key_file) if s.resolved_key_file.exists() else None)
    try:
        res = verify_backup(Path(args.file), vault, _passphrase(s, Path(args.file).read_bytes().startswith(b"EEBAK1P")))
    except BackupError as exc:
        sys.exit(f"FEHLER: {exc}")
    print(f"{'OK' if res['ok'] else 'BESCHÄDIGT'} – erstellt {res['created_at']} ({res['source_dialect']}), Tabellen: {res['tables']}, Fotos: {res['photos']}")
    for prob in res["problems"]:
        print(" -", prob)
    sys.exit(0 if res["ok"] else 1)


def cmd_restore(args) -> None:
    from .backup import BackupError, restore_backup
    from .crypto import Vault

    s, db, vault, _, p = _open(args)
    source = Vault(Path(args.source_key)) if args.source_key else None
    try:
        res = restore_backup(Path(args.file), db, vault, s.data_dir, _passphrase(s, Path(args.file).read_bytes().startswith(b"EEBAK1P")),
                             source_vault=source, force=args.force)
    except BackupError as exc:
        sys.exit(f"FEHLER: {exc}")
    p.log(None, "Sicherung wiederhergestellt", f"{Path(args.file).name} vom {res['created_at']}")
    print(f"Wiederhergestellt: {res['tables']} · Fotos: {res['photos']}")


def cmd_check_sources(args) -> None:
    """Prüft alle Quellen mit ihrer Testabfrage und zeigt, welche auf diesem Rechner wirklich antworten."""
    _, _, _, _, p = _open(args)
    print("Prüfe alle Quellen über den Standard-Netzausgang … (dauert je nach Verbindung 1–3 Minuten)")
    res = p.check_sources()
    mark = {"ok": "✓", "leer": "○", "fehler": "✗", "nicht_pruefbar": "–"}
    for r in res["results"]:
        detail = f"{r['count']} Treffer" if r["state"] in ("ok", "leer") else r["message"]
        print(f"  {mark[r['state']]} {r['label'][:52]:<52} {detail}")
    sm = res["summary"]
    print(f"Ergebnis: {sm['ok']} liefern Treffer · {sm['leer']} erreichbar ohne Treffer · {sm['fehler']} Fehler · {sm['nicht_pruefbar']} nicht prüfbar (Schlüssel/Daten fehlen)")
    if args.out:
        Path(args.out).write_text(p.source_report(), encoding="utf-8")
        print(f"Prüfbericht gespeichert: {args.out}")


def cmd_import_refdata(args) -> None:
    from .refdata import DATASETS, RefDataError

    _, _, _, _, p = _open(args)
    if args.name not in DATASETS:
        sys.exit(f"Bestand muss einer von {', '.join(DATASETS)} sein.")
    print(f"Importiere {args.file} nach „{DATASETS[args.name]['label']}“ … (große Dateien dauern einige Minuten)")
    try:
        res = p.refdata.import_file(args.name, Path(args.file))
    except RefDataError as exc:
        sys.exit(f"FEHLER: {exc}")
    p.log(None, "Referenzdaten importiert (Kommandozeile)", f"{args.name}: {res['records']} Einträge")
    print(f"Fertig: {res['records']} Einträge, {res['links']} Verknüpfungen.")


def cmd_verify_audit(args) -> None:
    _, _, _, _, p = _open(args)
    res = p.verify_audit()
    if res["ok"]:
        print(f"Protokoll intakt: {res['entries']} Einträge ({res['redacted']} geschwärzt). Kopf-Hash: {res['head']}")
    else:
        sys.exit(f"PROTOKOLL VERÄNDERT bei Eintrag #{res['broken_at']} ({res['ts']}): {res['problem']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="personosint", description="EagleEye PersonOSINT")
    parser.add_argument("--data", help="Datenordner (Standard: Benutzerprofil bzw. EAGLEEYE_PERSONOSINT_DATA)")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Server starten (Standard)")
    for target in (parser, serve):
        target.add_argument("--host", default=os.environ.get("EAGLEEYE_HOST", "127.0.0.1"))
        target.add_argument("--port", type=int, default=int(os.environ.get("EAGLEEYE_PORT", "8380")))
        target.add_argument("--no-browser", action="store_true")
        target.add_argument("--server", action="store_true",
                            help="Serverbetrieb: im eigenen Netz erreichbar (Zwei-Faktor-Pflicht, Rechnername/Adressen werden automatisch zugelassen)")
    cu = sub.add_parser("create-user", help="Benutzer anlegen")
    cu.add_argument("--username", required=True)
    cu.add_argument("--name", default="")
    cu.add_argument("--role", default="analyst")
    cu.add_argument("--no-change", action="store_true", help="kein Passwortwechsel bei erster Anmeldung")
    for name in ("reset-2fa", "unlock", "reset-password"):
        sp = sub.add_parser(name)
        sp.add_argument("username")
    bk = sub.add_parser("backup", help="verschlüsselte Sicherung erstellen")
    bk.add_argument("--out", default="")
    vb = sub.add_parser("verify-backup")
    vb.add_argument("file")
    vb.add_argument("--key", default="", help="Schlüsseldatei der Quellinstallation")
    rs = sub.add_parser("restore")
    rs.add_argument("file")
    rs.add_argument("--force", action="store_true", help="vorhandene Daten überschreiben")
    rs.add_argument("--source-key", default="", help="Schlüsseldatei der Quellinstallation (bei Sicherung ohne Passphrase)")
    sub.add_parser("verify-audit")
    cs = sub.add_parser("check-sources", help="alle Quellen mit ihrer Testabfrage prüfen (Internetverbindung nötig)")
    cs.add_argument("--out", default="", help="Prüfbericht als Markdown-Datei speichern")
    ir = sub.add_parser("import-refdata", help="lokale Referenzdaten importieren (opensanctions | icij | eigene_liste)")
    ir.add_argument("name")
    ir.add_argument("file")
    args = parser.parse_args(argv)
    {None: cmd_serve, "serve": cmd_serve, "create-user": cmd_create_user, "reset-2fa": cmd_user_admin, "unlock": cmd_user_admin,
     "reset-password": cmd_user_admin, "backup": cmd_backup, "verify-backup": cmd_verify_backup, "restore": cmd_restore,
     "verify-audit": cmd_verify_audit, "import-refdata": cmd_import_refdata, "check-sources": cmd_check_sources}[args.command](args)


if __name__ == "__main__":
    main()
