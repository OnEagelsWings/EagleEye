"""EagleEye-Fallakte im Vault: gleiche Verschlüsselung, gleicher Netzschalter, eine Anmeldung.

Die Fallakte (Büro, Mandanten, Rechnungen, beweissichere Web-Belege, Rechercheplan) öffnet ihre Datenbank an vielen
Stellen direkt als Datei. Sie läuft deshalb nicht im Arbeitsspeicher wie PersonOSINT, sondern so:

* **Im Ruhezustand** liegt jede Datei der Fallakte einzeln verschlüsselt im Vault (``files/fallakte/``). Auch Namen
  und Ordnerstruktur sind nicht lesbar: Die Zuordnung steht im verschlüsselten Verzeichnis ``manifest.enc``.
* **Beim Öffnen** (erster Klick auf „Fallakte“) wird sie in einen Arbeitsordner entschlüsselt und im selben Programm
  gestartet – damit gilt der Netzschalter des Vaults auch für sie.
* **Während der Arbeit** werden Änderungen jede Minute verschlüsselt zurückgeschrieben (Datenbanken als konsistente
  Momentaufnahme).
* **Beim Sperren** wird ein letztes Mal gesichert und der Arbeitsordner gelöscht.

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
            work = Path(tempfile.mkdtemp(prefix="eagleeye-fallakte-"))
            try:
                for rel, meta in self._manifest.items():
                    target = work.joinpath(*Path(rel).parts)
                    if ".." in Path(rel).parts or Path(rel).is_absolute():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.crypto.decrypt((self.store / meta["blob"]).read_bytes()))
                from eagleeye.interfaces.web.app500 import create_workspace_app500

                self.app = create_workspace_app500(base_dir=work)
            except Exception:
                shutil.rmtree(work, ignore_errors=True)
                raise
            self.workdir = work
            return self.app

    def sync(self) -> int:
        """Geänderte Dateien verschlüsselt zurückschreiben. Gibt die Zahl geschriebener Dateien zurück."""
        with self._lock:
            if not self.workdir:
                return 0
            written = 0
            seen = set()
            for path in sorted(self.workdir.rglob("*")):
                if not path.is_file() or path.name.endswith(SKIP_SUFFIXES):
                    continue
                rel = path.relative_to(self.workdir).as_posix()
                seen.add(rel)
                try:
                    data = self._snapshot(path)
                except (OSError, sqlite3.Error):
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
            self.last_sync = time.time()
            return written

    def close(self) -> None:
        with self._lock:
            if not self.workdir:
                return
            try:
                self.sync()
            finally:
                ctx = getattr(getattr(self.app, "state", None), "context", None)
                if ctx is not None and hasattr(ctx, "close"):
                    try:
                        ctx.close()
                    except Exception:  # noqa: BLE001
                        pass
                shutil.rmtree(self.workdir, ignore_errors=True)
                self.app = None
                self.workdir = None

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


__all__ = ["FallakteVault", "available", "fingerprint", "COOKIE", "CSRF_COOKIE"]
