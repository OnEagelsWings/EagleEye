"""Vault: Der ganze Datenbestand liegt nur verschlüsselt auf der Platte und wird nur im Arbeitsspeicher geöffnet.

Aufbau des Vault-Ordners
------------------------
* ``vault.json``  – Kopf: Verfahren und Parameter, Salz, zweifach eingewickelter Datenschlüssel (Passphrase,
  Wiederherstellungsschlüssel), verschlüsselte Inhaberangaben (Name, Geheimnis der Zwei-Faktor-Anmeldung).
* ``vault.db.enc`` – die gesamte SQLite-Datenbank, verschlüsselt (AES-256-GCM). Geöffnet wird sie mit
  ``sqlite3.Connection.deserialize`` direkt in den Arbeitsspeicher; eine Klartextdatei entsteht nie.
* ``files/`` – Fotos und Belege, wie bisher mit Fernet verschlüsselt – nur dass der Schlüssel jetzt aus dem
  Datenschlüssel abgeleitet wird und nirgends unverschlüsselt liegt.

Schlüssel
---------
Passphrase ──Argon2id──▶ Schlüsselschlüssel (KEK) ──AES-GCM──▶ Datenschlüssel (32 Byte, zufällig)
Wiederherstellungsschlüssel (einmal angezeigt) ──Argon2id──▶ zweiter KEK ──▶ derselbe Datenschlüssel
Datenschlüssel ──HKDF──▶ Datenbankschlüssel, Dateischlüssel (getrennte Zwecke)

Eine vergessene Passphrase ohne Wiederherstellungsschlüssel bedeutet: Die Daten sind verloren. Das ist Absicht.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

FORMAT = "eagleeye-vault-1"
HEADER = "vault.json"
DB_FILE = "vault.db.enc"
#: Argon2id-Parameter (OWASP-Empfehlung, auf üblichen Büro-PCs ca. 0,5–1,5 s je Entsperrung)
KDF_DEFAULT = {"name": "argon2id", "time_cost": 3, "memory_kib": 65536, "parallelism": 4}
MIN_PASSPHRASE = 12
RECOVERY_GROUPS = 6


class VaultError(Exception):
    """Lesbare deutsche Fehlermeldung rund um den Vault."""


class WrongSecret(VaultError):
    pass


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode())


def _kek(secret: str, salt: bytes, kdf: dict[str, Any]) -> bytes:
    return hash_secret_raw(secret.encode("utf-8"), salt, time_cost=int(kdf["time_cost"]), memory_cost=int(kdf["memory_kib"]),
                           parallelism=int(kdf["parallelism"]), hash_len=32, type=Type.ID)


def _seal(key: bytes, data: bytes, aad: bytes) -> dict[str, str]:
    nonce = os.urandom(12)
    return {"nonce": _b64(nonce), "data": _b64(AESGCM(key).encrypt(nonce, data, aad))}


def _open(key: bytes, box: dict[str, str], aad: bytes) -> bytes:
    return AESGCM(key).decrypt(_unb64(box["nonce"]), _unb64(box["data"]), aad)


def _derive(data_key: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"eagleeye-vault/" + purpose).derive(data_key)


def new_recovery_key() -> str:
    """Wiederherstellungsschlüssel zum Aufschreiben: 6 Gruppen à 5 Zeichen ohne verwechselbare Zeichen (≈ 145 Bit)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(RECOVERY_GROUPS))


def normalize_recovery(text: str) -> str:
    raw = "".join(ch for ch in str(text or "").upper() if ch.isalnum())
    return "-".join(raw[i:i + 5] for i in range(0, len(raw), 5))


def check_passphrase(passphrase: str) -> None:
    if len(passphrase or "") < MIN_PASSPHRASE:
        raise VaultError(f"Die Passphrase muss mindestens {MIN_PASSPHRASE} Zeichen haben – besser ein Satz aus mehreren Wörtern.")
    if len(set(passphrase)) < 6:
        raise VaultError("Die Passphrase ist zu gleichförmig. Bitte einen Satz aus mehreren unterschiedlichen Wörtern wählen.")


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


@dataclass
class Opened:
    """Ein geöffneter Vault: Schlüssel und Inhaberangaben nur im Arbeitsspeicher."""
    data_key: bytes
    owner: dict[str, Any]

    @property
    def files_key(self) -> bytes:
        """Fernet-Schlüssel für Fotos und Belege (aus dem Datenschlüssel abgeleitet)."""
        return base64.urlsafe_b64encode(_derive(self.data_key, b"files"))

    @property
    def db_key(self) -> bytes:
        return _derive(self.data_key, b"database")


class VaultStore:
    """Liest und schreibt den Vault-Ordner. Kennt keine Anwendung – nur Schlüssel und verschlüsselte Bytes."""

    def __init__(self, folder: Path | str, kdf: dict[str, Any] | None = None):
        self.folder = Path(folder)
        self.kdf = dict(kdf or KDF_DEFAULT)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ Zustand
    @property
    def header_path(self) -> Path:
        return self.folder / HEADER

    @property
    def db_path(self) -> Path:
        return self.folder / DB_FILE

    @property
    def files_dir(self) -> Path:
        return self.folder / "files"

    def exists(self) -> bool:
        return self.header_path.is_file()

    def header(self) -> dict[str, Any]:
        try:
            head = json.loads(self.header_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VaultError("Der Vault-Kopf (vault.json) fehlt oder ist beschädigt.") from exc
        if head.get("format") != FORMAT:
            raise VaultError("Unbekanntes Vault-Format.")
        return head

    def _write_header(self, head: dict[str, Any]) -> None:
        _atomic_write(self.header_path, json.dumps(head, indent=2).encode("utf-8"))

    def public_info(self) -> dict[str, Any]:
        """Was ohne Passphrase sichtbar ist: nur, dass es einen Vault gibt, und Zähler für Fehlversuche."""
        if not self.exists():
            return {"exists": False}
        head = self.header()
        return {"exists": True, "created": head.get("created", ""), "failed": int(head.get("failed", 0)),
                "wait_seconds": max(0, int(head.get("retry_after", 0) - time.time()))}

    # ------------------------------------------------------------------ Einrichtung
    def create(self, passphrase: str, owner: dict[str, Any]) -> tuple[Opened, str]:
        """Legt einen neuen Vault an. Gibt den geöffneten Vault und den Wiederherstellungsschlüssel (einmalig!) zurück."""
        check_passphrase(passphrase)
        if self.exists():
            raise VaultError("Hier gibt es bereits einen Vault.")
        self.folder.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(exist_ok=True)
        data_key = secrets.token_bytes(32)
        recovery = new_recovery_key()
        salt_p, salt_r = os.urandom(16), os.urandom(16)
        aad = FORMAT.encode()
        head = {
            "format": FORMAT, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "kdf": self.kdf,
            "passphrase": {"salt": _b64(salt_p), **_seal(_kek(passphrase, salt_p, self.kdf), data_key, aad + b"/pass")},
            "recovery": {"salt": _b64(salt_r), **_seal(_kek(recovery, salt_r, self.kdf), data_key, aad + b"/recovery")},
            "owner": _seal(_derive(data_key, b"owner"), json.dumps(owner).encode(), aad + b"/owner"),
            "failed": 0, "retry_after": 0,
        }
        self._write_header(head)
        return Opened(data_key, dict(owner)), recovery

    # ------------------------------------------------------------------ Öffnen
    def _throttle(self, head: dict[str, Any]) -> None:
        wait = int(head.get("retry_after", 0) - time.time())
        if wait > 0:
            raise VaultError(f"Zu viele Fehlversuche. Bitte {wait} Sekunden warten.")

    def _failed(self, head: dict[str, Any]) -> None:
        failed = int(head.get("failed", 0)) + 1
        head["failed"] = failed
        # ab dem dritten Fehlversuch wachsende Wartezeit: 5 s, 10 s, 20 s … höchstens 15 Minuten
        head["retry_after"] = time.time() + (min(900, 5 * 2 ** (failed - 3)) if failed >= 3 else 0)
        self._write_header(head)

    def open(self, secret: str, *, recovery: bool = False, reset: bool = True) -> Opened:
        """Öffnet mit Passphrase (oder Wiederherstellungsschlüssel). ``reset=False``: Fehlversuchszähler erst zurücksetzen,
        wenn auch der zweite Faktor stimmt (sonst ließe sich der Code bei bekannter Passphrase durchprobieren)."""
        with self._lock:
            head = self.header()
            self._throttle(head)
            slot = head["recovery" if recovery else "passphrase"]
            value = normalize_recovery(secret) if recovery else secret
            try:
                data_key = _open(_kek(value, _unb64(slot["salt"]), head["kdf"]), slot,
                                 FORMAT.encode() + (b"/recovery" if recovery else b"/pass"))
            except (InvalidTag, ValueError, KeyError):
                self._failed(head)
                raise WrongSecret("Wiederherstellungsschlüssel ist falsch." if recovery else "Passphrase ist falsch.") from None
            owner = json.loads(_open(_derive(data_key, b"owner"), head["owner"], FORMAT.encode() + b"/owner"))
            if reset and (head.get("failed") or head.get("retry_after")):
                head["failed"], head["retry_after"] = 0, 0
                self._write_header(head)
            return Opened(data_key, owner)

    def reset_failures(self) -> None:
        with self._lock:
            head = self.header()
            head["failed"], head["retry_after"] = 0, 0
            self._write_header(head)

    def note_failure(self) -> None:
        """Fehlversuch zählen, der erst nach der Passphrase auffällt (falscher Zwei-Faktor-Code)."""
        with self._lock:
            self._failed(self.header())

    # ------------------------------------------------------------------ Ändern
    def change_passphrase(self, opened: Opened, new_passphrase: str) -> None:
        check_passphrase(new_passphrase)
        with self._lock:
            head = self.header()
            salt = os.urandom(16)
            head["passphrase"] = {"salt": _b64(salt), **_seal(_kek(new_passphrase, salt, head["kdf"]), opened.data_key, FORMAT.encode() + b"/pass")}
            self._write_header(head)

    def new_recovery(self, opened: Opened) -> str:
        recovery = new_recovery_key()
        with self._lock:
            head = self.header()
            salt = os.urandom(16)
            head["recovery"] = {"salt": _b64(salt), **_seal(_kek(recovery, salt, head["kdf"]), opened.data_key, FORMAT.encode() + b"/recovery")}
            self._write_header(head)
        return recovery

    def save_owner(self, opened: Opened) -> None:
        with self._lock:
            head = self.header()
            head["owner"] = _seal(_derive(opened.data_key, b"owner"), json.dumps(opened.owner).encode(), FORMAT.encode() + b"/owner")
            self._write_header(head)

    # ------------------------------------------------------------------ Datenbank
    def load_db(self, opened: Opened) -> bytes | None:
        if not self.db_path.is_file():
            return None
        box = json.loads(self.db_path.read_bytes())
        try:
            return _open(opened.db_key, box, FORMAT.encode() + b"/db")
        except InvalidTag as exc:
            raise VaultError("Die verschlüsselte Datenbank ist beschädigt oder gehört nicht zu diesem Vault.") from exc

    def save_db(self, opened: Opened, data: bytes) -> None:
        box = _seal(opened.db_key, data, FORMAT.encode() + b"/db")
        box["saved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        box["size"] = len(data)
        _atomic_write(self.db_path, json.dumps(box).encode())


def open_memory_db(raw: bytes | None) -> sqlite3.Connection:
    """SQLite-Verbindung im Arbeitsspeicher, auf Wunsch mit dem entschlüsselten Datenbestand gefüllt."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    if raw:
        conn.deserialize(raw)
    return conn


def fingerprint(data_key: bytes) -> str:
    """Kurzer, nicht umkehrbarer Kennwert des Vaults (für Anzeige und Sicherungen)."""
    return hashlib.sha256(b"eagleeye-vault-id" + data_key).hexdigest()[:12]


__all__ = ["VaultStore", "Opened", "VaultError", "WrongSecret", "new_recovery_key", "normalize_recovery", "check_passphrase",
           "open_memory_db", "fingerprint", "KDF_DEFAULT"]
