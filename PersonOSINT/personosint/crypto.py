"""Verschlüsselung ruhender Daten (Fotos, 2FA-Geheimnisse, Sicherungen) mit Fernet (AES-128-CBC + HMAC)."""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

MAGIC = b"EEENC1:"  # Kennzeichnung verschlüsselter Dateien


class Vault:
    def __init__(self, key_file: Path):
        self.key_file = Path(key_file)
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_file.exists():
            key = Fernet.generate_key()
            fd = os.open(self.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(key)
        self._f = Fernet(self.key_file.read_bytes().strip())

    def encrypt(self, data: bytes) -> bytes:
        return MAGIC + self._f.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        """Entschlüsselt; unverschlüsselte Altdaten (Version 1.0) werden unverändert zurückgegeben."""
        if not data.startswith(MAGIC):
            return data
        return self._f.decrypt(data[len(MAGIC):])

    def encrypt_text(self, text: str) -> str:
        return self._f.encrypt(text.encode()).decode()

    def decrypt_text(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Geheimnis konnte nicht entschlüsselt werden (falscher Schlüssel?)") from exc


def passphrase_fernet(passphrase: str, salt: bytes) -> Fernet:
    key = hashlib.scrypt(passphrase.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return Fernet(base64.urlsafe_b64encode(key))


__all__ = ["Vault", "passphrase_fernet", "InvalidToken", "Fernet"]
