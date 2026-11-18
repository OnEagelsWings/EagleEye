"""Encrypted workspace backup that can run while EagleEye is open.

Archive: the same ZIP layout and manifest as ``recovery479`` (so its verified restore applies),
built while the application keeps running. SQLite databases are copied through the SQLite
online-backup API into memory and checked with ``quick_check``; no unencrypted copy is written
to disk while the backup is made.

Container (``.eebak``):

    MAGIC | 4-byte header length | header JSON | chunk*
    chunk = 4-byte ciphertext length | AES-256-GCM ciphertext (incl. 16-byte tag)

* The key comes from the password via scrypt (fresh random salt per file, parameters in the
  header and bounded when read). The password is never stored.
* Each chunk's nonce is its counter plus a "last chunk" flag; the associated data binds the
  header digest, so header, order and length cannot be changed and a cut-off file is detected.
* A wrong password and a damaged file both fail authentication of the first chunk.

Restore: ``recovery479`` asks for the password, decrypts to a temporary ZIP next to the new
workspace folder, verifies every file against the manifest and removes the temporary ZIP.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import io
import json
import os
import secrets
import sqlite3
import struct
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from eagleeye_pro.version import BUILD
from . import recovery479

MAGIC = b"EAGLEEYE-ENCRYPTED-BACKUP-1\n"
FORMAT = "eagleeye-encrypted-backup-v1"
SUFFIX = ".eebak"
CHUNK = 4 * 1024 * 1024
KDF = {"n": 2 ** 17, "r": 8, "p": 1}
MAX_HEADER = 64 * 1024
MIN_PASSWORD = 12
SQLITE_MAGIC = b"SQLite format 3\x00"
SIDE_FILES = ("-wal", "-shm", "-journal")


class BackupError(ValueError):
    """A user-facing problem with creating, checking or opening an encrypted backup."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_password(password: str, repeat: str | None = None) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise BackupError(f"Das Sicherungspasswort muss mindestens {MIN_PASSWORD} Zeichen lang sein.")
    if repeat is not None and password != repeat:
        raise BackupError("Die beiden Passwörter stimmen nicht überein.")


def _key(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))


def _nonce(counter: int, final: bool) -> bytes:
    return counter.to_bytes(11, "big") + (b"\x01" if final else b"\x00")


class EncryptingWriter(io.RawIOBase):
    """Write-only stream: everything written is encrypted chunk by chunk into ``raw``."""

    def __init__(self, raw, password: str, *, meta: dict | None = None):
        super().__init__()
        salt = secrets.token_bytes(16)
        header = {"format": FORMAT, "kdf": "scrypt", **KDF, "salt": base64.b64encode(salt).decode("ascii"),
                  "cipher": "AES-256-GCM", "chunk": CHUNK, "created_at": _now(), "source_build": BUILD, **(meta or {})}
        self._header = json.dumps(header, sort_keys=True).encode("utf-8")
        self._aead = AESGCM(_key(password, salt, KDF["n"], KDF["r"], KDF["p"]))
        self._digest = hashlib.sha256(MAGIC + self._header).digest()
        self._raw = raw
        self._buffer = bytearray()
        self._counter = 0
        self._finished = False
        raw.write(MAGIC + struct.pack(">I", len(self._header)) + self._header)

    def writable(self):
        return True

    def write(self, data) -> int:
        if self._finished:
            raise ValueError("Sicherung bereits abgeschlossen.")
        self._buffer.extend(data)
        while len(self._buffer) > CHUNK:  # keep at least one byte back for the final chunk
            self._emit(bytes(self._buffer[:CHUNK]), final=False)
            del self._buffer[:CHUNK]
        return len(data)

    def _emit(self, plain: bytes, *, final: bool) -> None:
        sealed = self._aead.encrypt(_nonce(self._counter, final), plain, self._digest + struct.pack(">Q?", self._counter, final))
        self._raw.write(struct.pack(">I", len(sealed)) + sealed)
        self._counter += 1

    def finish(self) -> None:
        if not self._finished:
            self._emit(bytes(self._buffer), final=True)
            self._buffer.clear()
            self._finished = True

    def close(self) -> None:
        # Closing without finish() leaves a file without a final chunk: it will not decrypt.
        super().close()


def read_header(handle) -> dict:
    magic = handle.read(len(MAGIC))
    if magic != MAGIC:
        raise BackupError("Keine verschlüsselte EagleEye-Sicherung.")
    (length,) = struct.unpack(">I", handle.read(4))
    if not 0 < length <= MAX_HEADER:
        raise BackupError("Sicherungskopf beschädigt.")
    raw = handle.read(length)
    header = json.loads(raw)
    if header.get("format") != FORMAT or header.get("kdf") != "scrypt" or header.get("cipher") != "AES-256-GCM":
        raise BackupError("Unbekanntes Sicherungsformat.")
    n, r, p, chunk = (int(header.get(k, 0)) for k in ("n", "r", "p", "chunk"))
    if not (2 ** 14 <= n <= 2 ** 20 and n & (n - 1) == 0 and 1 <= r <= 16 and 1 <= p <= 4 and 1 <= chunk <= 64 * 1024 * 1024):
        raise BackupError("Unzulässige Sicherungsparameter.")
    header["_raw"] = raw
    return header


def decrypt_stream(source, target, password: str) -> dict:
    """Decrypt ``source`` into the writable ``target``; authenticates every chunk and the end."""
    header = read_header(source)
    salt = base64.b64decode(header["salt"])
    aead = AESGCM(_key(password, salt, int(header["n"]), int(header["r"]), int(header["p"])))
    digest = hashlib.sha256(MAGIC + header["_raw"]).digest()
    limit = int(header["chunk"]) + 16
    counter, total, finished = 0, 0, False
    while True:
        prefix = source.read(4)
        if not prefix:
            break
        if finished:
            raise BackupError("Nach dem Ende der Sicherung folgen weitere Daten – Datei verändert.")
        if len(prefix) != 4:
            raise BackupError("Sicherung unvollständig (abgeschnitten).")
        (length,) = struct.unpack(">I", prefix)
        if not 16 <= length <= limit:
            raise BackupError("Sicherung beschädigt.")
        sealed = source.read(length)
        if len(sealed) != length:
            raise BackupError("Sicherung unvollständig (abgeschnitten).")
        for final in (False, True):
            try:
                plain = aead.decrypt(_nonce(counter, final), sealed, digest + struct.pack(">Q?", counter, final))
                break
            except InvalidTag:
                plain = None
        if plain is None:
            if counter == 0:
                raise BackupError("Passwort falsch oder Sicherung beschädigt.")
            raise BackupError("Sicherung beschädigt oder verändert.")
        finished = final
        target.write(plain)
        total += len(plain)
        counter += 1
    if not finished:
        raise BackupError("Sicherung unvollständig (abgeschnitten).")
    return {"bytes": total, "chunks": counter, "created_at": header.get("created_at", ""),
            "source_build": header.get("source_build", "")}


def is_encrypted(path) -> bool:
    try:
        with Path(path).open("rb") as handle:
            return handle.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def _sqlite_bytes(path: Path) -> bytes:
    """Consistent copy of a live SQLite database, kept in memory only."""
    source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
    memory = sqlite3.connect(":memory:")
    try:
        source.backup(memory)
        if memory.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise BackupError(f"Datenbank {path.name} ist nicht konsistent – Sicherung abgebrochen.")
        return memory.serialize()
    finally:
        memory.close()
        source.close()


def _workspace_files(root: Path) -> tuple[list[tuple[str, Path]], set[str]]:
    files = recovery479.collect_files(root)
    sqlite_names = set()
    for name, path in files:
        with path.open("rb") as handle:
            if handle.read(16) == SQLITE_MAGIC:
                sqlite_names.add(name)
    # Live side files belong to the database snapshot, not to the archive.
    return [(n, p) for n, p in files if not any(n == db + s for db in sqlite_names for s in SIDE_FILES)], sqlite_names


def create(root, folder, password: str, *, progress=None) -> dict:
    """Write an encrypted backup of the workspace ``root`` into ``folder``; returns file facts."""
    check_password(password)
    root = recovery479.local_path(root)
    folder = recovery479.local_path(folder)
    if not (root / "data" / "eagleeye.db").is_file():
        raise BackupError("Kein EagleEye-Arbeitsordner.")
    if folder == root or root in folder.parents:
        raise BackupError("Sicherungen bitte außerhalb des Arbeitsordners ablegen.")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("EagleEye-Sicherung_" + datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_" + secrets.token_hex(2) + SUFFIX)
    files, sqlite_names = _workspace_files(root)
    entries, total = [], 0
    try:
        with target.open("xb") as raw:
            try:
                target.chmod(0o600)
            except OSError:
                pass
            writer = EncryptingWriter(raw, password, meta={"workspace_files": len(files)})
            with zipfile.ZipFile(writer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for index, (name, path) in enumerate(files):
                    if progress:
                        progress(index, len(files), name)
                    digest = hashlib.sha256()
                    if name in sqlite_names:
                        data = _sqlite_bytes(path)
                        size = len(data)
                        if total + size > recovery479.MAX_BYTES:
                            raise BackupError("Sicherung überschreitet 2 GiB.")
                        with archive.open(name, "w", force_zip64=True) as out:
                            out.write(data)
                        digest.update(data)
                        del data
                    else:
                        before = path.stat()
                        size = 0
                        with path.open("rb") as incoming, archive.open(name, "w", force_zip64=True) as out:
                            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                                size += len(block)
                                if total + size > recovery479.MAX_BYTES:
                                    raise BackupError("Sicherung überschreitet 2 GiB.")
                                out.write(block)
                                digest.update(block)
                        after = path.stat()
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise BackupError(f"Die Datei {name} wurde während der Sicherung geändert – bitte erneut sichern.")
                    total += size
                    entries.append({"path": name, "bytes": size, "sha256": digest.hexdigest()})
                manifest = {"format": recovery479.FORMAT, "source_build": BUILD, "created_at": _now(),
                            "scope": ["all regular files inside workspace except runtime, virtualenvs, git metadata, "
                                      "regenerated receipt and session admission token; SQLite via online backup"],
                            "files": entries, "total_bytes": total, "sessions_reactivated_on_restore": False,
                            "encrypted": True}
                archive.writestr(recovery479.MANIFEST, json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode())
            writer.finish()
        digest = recovery479.sha_file(target)
        return {"path": str(target), "file_name": target.name, "size": target.stat().st_size, "sha256": digest,
                "files": len(entries), "bytes": total}
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _decrypt_to_temp(path: Path, password: str, folder: Path) -> tuple[Path, dict]:
    handle, name = tempfile.mkstemp(prefix="eagleeye-restore-", suffix=".zip", dir=str(folder))
    temp = Path(name)
    try:
        with os.fdopen(handle, "wb") as out, path.open("rb") as source:
            facts = decrypt_stream(source, out, password)
        return temp, facts
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def verify(path, password: str) -> dict:
    """Decrypt (in memory up to 512 MB), check every archived file against the manifest."""
    path = recovery479.local_path(path)
    with tempfile.SpooledTemporaryFile(max_size=512 * 1024 * 1024) as plain:
        with path.open("rb") as source:
            facts = decrypt_stream(source, plain, password)
        plain.seek(0)
        with zipfile.ZipFile(plain) as archive:
            manifest = json.loads(archive.read(recovery479.MANIFEST))
            if manifest.get("format") != recovery479.FORMAT:
                raise BackupError("Unbekanntes Archivformat in der Sicherung.")
            checked = 0
            for entry in manifest["files"]:
                digest = hashlib.sha256()
                with archive.open(entry["path"]) as member:
                    for block in iter(lambda: member.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != entry["sha256"]:
                    raise BackupError(f"Prüfsumme stimmt nicht: {entry['path']}")
                checked += 1
            if "data/eagleeye.db" not in {e["path"] for e in manifest["files"]}:
                raise BackupError("Hauptdatenbank fehlt in der Sicherung.")
    return {**facts, "files": checked, "total_bytes": manifest.get("total_bytes", 0)}


def restore(path, password: str, target) -> dict:
    """Restore an encrypted backup into a new folder (verified like a plain recovery479 backup)."""
    path = recovery479.local_path(path)
    target = recovery479.local_path(target)
    if not target.parent.is_dir():
        raise BackupError("Ziel-Elternordner fehlt.")
    temp, facts = _decrypt_to_temp(path, password, target.parent)
    try:
        receipt = recovery479.restore_backup(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return {**receipt, "encrypted_backup": True, "backup_created_at": facts.get("created_at", "")}


def ask_password() -> str:
    return getpass.getpass("Passwort der verschlüsselten Sicherung: ")
