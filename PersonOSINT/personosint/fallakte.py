"""EagleEye-Fallakte im Vault: gleiche Verschlüsselung, gleicher Netzschalter, eine Anmeldung.

Die Fallakte (Büro, Mandanten, Rechnungen, beweissichere Web-Belege, Rechercheplan) öffnet ihre Datenbank an vielen
Stellen direkt als Datei. Sie läuft deshalb nicht im Arbeitsspeicher wie PersonOSINT, sondern so:

* **Im Ruhezustand** liegt jede Datei der Fallakte einzeln verschlüsselt im Vault (``files/fallakte/``). Auch Namen
  und Ordnerstruktur sind nicht lesbar: Die Zuordnung steht im verschlüsselten Verzeichnis ``manifest.enc``.
* **Beim Öffnen** (erster Klick auf „Fallakte“) wird sie in einen Arbeitsordner entschlüsselt und im selben Programm
  gestartet – damit gilt der Netzschalter des Vaults auch für sie.
* **Während der Arbeit** werden Änderungen jede Minute verschlüsselt zurückgeschrieben (Datenbanken als konsistente
  Momentaufnahme).
* **Beim Sperren** wird ein letztes Mal gesichert und der Arbeitsordner gelöscht – aber nur, wenn wirklich jede Datei
  gesichert ist. Der Pfad des Arbeitsordners steht schon **beim Öffnen** verschlüsselt im Vault (``pending.enc``) und
  wird erst nach einem vollständig gesicherten Schließen entfernt. Scheitert die letzte Sicherung (Lesefehler, voller
  Datenträger) oder stürzt der Rechner ab, wird der Arbeitsordner beim nächsten Öffnen übernommen und nachgesichert –
  ohne dass dafür im Fehlerfall noch etwas geschrieben werden muss.

Ehrliche Grenze: Solange der Vault offen ist, liegen die Fallakten-Dateien entschlüsselt im Arbeitsordner. Dagegen
schützt die Laufwerksverschlüsselung (BitLocker). Auf SSDs ist auch gelöschter Inhalt nicht sicher entfernt.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

SKIP_SUFFIXES = ("-wal", "-shm", "-journal", ".lock")
READ_ATTEMPTS = 3


class FallakteSyncError(RuntimeError):
    """Nicht alle Dateien der Fallakte konnten verschlüsselt gesichert werden; der Arbeitsordner bleibt erhalten."""
SQLITE_MAGIC = b"SQLite format 3\x00"
COOKIE, CSRF_COOKIE = "ee_auth_session", "ee_auth_csrf"


def available() -> bool:
    """Ist die EagleEye-Fallakte in diesem Python-Umfeld installiert?"""
    try:
        return importlib.util.find_spec("eagleeye.interfaces.web.app500") is not None
    except (ImportError, ValueError):
        return False


def fingerprint(headers: dict[str, str], client_host: str) -> str:
    """Wie die Fallakte eine Sitzung an den Browser bindet (Browserkennung, Sprache, Adresse)."""
    material = "|".join((headers.get("user-agent", ""), headers.get("accept-language", ""), client_host))
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


class FallakteVault:
    def __init__(self, store_dir: Path, crypto):
        self.store = Path(store_dir)
        self.crypto = crypto
        self.workdir: Path | None = None
        self.app = None
        self._manifest: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.last_sync = 0.0
        self.failed: list[str] = []

    # ------------------------------------------------------------------ verschlüsselter Speicher
    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        path = self.store / "manifest.enc"
        if not path.is_file():
            return {}
        return json.loads(self.crypto.decrypt(path.read_bytes()).decode("utf-8"))

    def _save_manifest(self) -> None:
        self.store.mkdir(parents=True, exist_ok=True)
        tmp = self.store / "manifest.enc.tmp"
        tmp.write_bytes(self.crypto.encrypt(json.dumps(self._manifest).encode("utf-8")))
        os.replace(tmp, self.store / "manifest.enc")

    def _remember_pending(self, work: Path) -> None:
        """Arbeitsordner mit nicht gesicherten Änderungen für das nächste Öffnen vormerken (Pfad verschlüsselt)."""
        self.store.mkdir(parents=True, exist_ok=True)
        tmp = self.store / "pending.enc.tmp"
        tmp.write_bytes(self.crypto.encrypt(str(work).encode("utf-8")))
        os.replace(tmp, self.store / "pending.enc")

    def _pending_workdir(self) -> Path | None:
        marker = self.store / "pending.enc"
        if not marker.is_file():
            return None
        try:
            work = Path(self.crypto.decrypt(marker.read_bytes()).decode("utf-8"))
        except Exception:  # noqa: BLE001 - beschädigter Vermerk: lieber den gesicherten Stand öffnen
            return None
        return work if work.is_dir() else None

    @staticmethod
    def _snapshot(path: Path) -> bytes:
        """SQLite konsistent lesen (auch während die Fallakte schreibt); sonst die Datei selbst."""
        with open(path, "rb") as fh:
            head = fh.read(16)
        if head != SQLITE_MAGIC:
            return path.read_bytes()
        src = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
        mem = sqlite3.connect(":memory:")
        try:
            src.backup(mem)
            data = mem.serialize()
        finally:
            src.close()
            mem.close()
        # im Arbeitsspeicher entsteht kein WAL – Kopf auf Rollback-Modus, damit die Datei überall öffnet
        return data[:18] + b"\x01\x01" + data[20:] if data[18:20] == b"\x02\x02" else data

    # ------------------------------------------------------------------ Lebenszyklus
    @property
    def is_open(self) -> bool:
        return self.app is not None

    def open(self):
        with self._lock:
            if self.app is not None:
                return self.app
            self._manifest = self._load_manifest()
            pending = self._pending_workdir()
            if pending is not None:
                # Letztes Schließen nicht vollständig gesichert (oder Absturz): dieser Ordner hat den neuesten Stand.
                # Der Vermerk bleibt, bis ein späteres Schließen alles gesichert hat.
                self.workdir = pending
                try:
                    self.sync()
                except Exception:  # noqa: BLE001 - die Daten liegen weiter im Arbeitsordner
                    pass
                try:
                    from eagleeye.interfaces.web.app500 import create_workspace_app500

                    self.app = create_workspace_app500(base_dir=pending)
                except Exception:
                    self.workdir = None  # Vermerk bleibt: nächster Versuch übernimmt denselben Ordner
                    raise
                return self.app
            (self.store / "pending.enc").unlink(missing_ok=True)  # Vermerk auf einen nicht mehr vorhandenen Ordner
            work = Path(tempfile.mkdtemp(prefix="eagleeye-fallakte-"))
            try:
                for rel, meta in self._manifest.items():
                    target = work.joinpath(*Path(rel).parts)
                    if ".." in Path(rel).parts or Path(rel).is_absolute():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.crypto.decrypt((self.store / meta["blob"]).read_bytes()))
                # Vorab vermerken, solange noch geschrieben werden kann – nicht erst, wenn eine Sicherung scheitert.
                self._remember_pending(work)
                from eagleeye.interfaces.web.app500 import create_workspace_app500

                self.app = create_workspace_app500(base_dir=work)
            except Exception:
                shutil.rmtree(work, ignore_errors=True)
                (self.store / "pending.enc").unlink(missing_ok=True)
                raise
            self.workdir = work
            return self.app

    def sync(self) -> int:
        """Geänderte Dateien verschlüsselt zurückschreiben. Gibt die Zahl geschriebener Dateien zurück.

        Dateien, die sich auch nach mehreren Versuchen nicht lesen lassen, stehen danach in ``self.failed``;
        ihr zuletzt gesicherter Stand bleibt im Vault unverändert.
        """
        with self._lock:
            if not self.workdir:
                return 0
            written = 0
            seen = set()
            failed: list[str] = []
            for path in sorted(self.workdir.rglob("*")):
                if not path.is_file() or path.name.endswith(SKIP_SUFFIXES):
                    continue
                rel = path.relative_to(self.workdir).as_posix()
                seen.add(rel)
                data = None
                for attempt in range(READ_ATTEMPTS):
                    try:
                        data = self._snapshot(path)
                        break
                    except (OSError, sqlite3.Error):
                        time.sleep(0.2 * (attempt + 1))
                if data is None:
                    failed.append(rel)
                    continue
                digest = hashlib.sha256(data).hexdigest()
                meta = self._manifest.get(rel)
                if meta and meta["sha"] == digest:
                    continue
                blob = meta["blob"] if meta else secrets.token_hex(16) + ".enc"
                self.store.mkdir(parents=True, exist_ok=True)
                tmp = self.store / (blob + ".tmp")
                tmp.write_bytes(self.crypto.encrypt(data))
                os.replace(tmp, self.store / blob)
                self._manifest[rel] = {"blob": blob, "sha": digest, "size": len(data)}
                written += 1
            for rel in [r for r in self._manifest if r not in seen]:
                (self.store / self._manifest.pop(rel)["blob"]).unlink(missing_ok=True)
                written += 1
            if written:
                self._save_manifest()
            self.failed = failed
            self.last_sync = time.time()
            return written

    def close(self) -> None:
        """Letzte Sicherung, dann Arbeitsordner löschen – nur wenn jede Datei gesichert ist.

        Sonst bleibt der Arbeitsordner erhalten, wird für das nächste Öffnen vorgemerkt und ``FallakteSyncError``
        gemeldet. Die Fallakte ist danach in jedem Fall geschlossen.
        """
        with self._lock:
            if not self.workdir:
                return
            work = self.workdir
            ctx = getattr(getattr(self.app, "state", None), "context", None)
            if ctx is not None and hasattr(ctx, "close"):
                try:
                    ctx.close()  # keine Schreibvorgänge mehr während der letzten Sicherung
                except Exception:  # noqa: BLE001
                    pass
            self.app = None
            problem = ""
            try:
                self.sync()
                if self.failed:
                    problem = "nicht lesbar: " + ", ".join(self.failed[:5])
            except Exception as exc:  # noqa: BLE001 - z. B. Datenträger voll
                problem = f"{type(exc).__name__}: {exc}"[:300]
            self.workdir = None
            if not problem:
                shutil.rmtree(work, ignore_errors=True)
                (self.store / "pending.enc").unlink(missing_ok=True)
                return
            # Der Vermerk wurde schon beim Öffnen geschrieben und bleibt stehen; hier ist nichts mehr zu schreiben.
            raise FallakteSyncError("Die Fallakte konnte beim Sperren nicht vollständig gesichert werden (" + problem + "). "
                                    "Der Arbeitsordner bleibt erhalten und wird beim nächsten Öffnen nachgesichert: " + str(work))

    # ------------------------------------------------------------------ eine Anmeldung
    def single_sign_on(self, owner: dict[str, Any], display_name: str, headers: dict[str, str], client_host: str) -> tuple[str, str, int]:
        """Meldet den Vault-Inhaber in der Fallakte an. Das Konto entsteht beim ersten Mal; sein Passwort ist ein
        Zufallswert, der nur verschlüsselt im Vault liegt – angemeldet wird ausschließlich über den Vault."""
        app = self.open()
        team = app.state.context.team_identity_359
        if team.bootstrap_required():
            owner["fallakte_user"] = "inhaber"
            owner["fallakte_password"] = "Vault-" + secrets.token_urlsafe(30) + "-9aA!"
            team.create_initial_admin(username=owner["fallakte_user"], display_name=display_name, password=owner["fallakte_password"])
        if not owner.get("fallakte_password"):
            raise PermissionError("Die Fallakte hat schon ein eigenes Konto (z. B. aus einer früheren Einrichtung). "
                                  "Bitte dort mit Benutzername und Passwort anmelden.")
        issued = team.authenticate(username=owner["fallakte_user"], password=owner["fallakte_password"],
                                   client_fingerprint=fingerprint(headers, client_host))
        if not issued:
            raise PermissionError("Anmeldung in der Fallakte fehlgeschlagen.")
        return issued.token, issued.csrf_token, int(issued.max_age)


__all__ = ["FallakteVault", "FallakteSyncError", "available", "fingerprint", "COOKIE", "CSRF_COOKIE"]
