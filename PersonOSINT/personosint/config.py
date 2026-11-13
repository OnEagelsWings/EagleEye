"""Zentrale Konfiguration (Umgebungsvariablen mit sicheren Standardwerten)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "ja", "on"}


def default_data_dir() -> Path:
    env = os.environ.get("EAGLEEYE_PERSONOSINT_DATA")
    if env:
        return Path(env)
    base = Path(os.environ.get("APPDATA") or Path.home() / ".local" / "share")
    return base / "EagleEye-PersonOSINT"


@dataclass
class Settings:
    data_dir: Path = field(default_factory=default_data_dir)
    #: leer = SQLite im Datenordner; sonst z. B. postgresql://user:pass@db:5432/eagleeye
    database_url: str = field(default_factory=lambda: os.environ.get("EAGLEEYE_DATABASE_URL", ""))
    #: Pfad zur Schlüsseldatei; Standard: <data_dir>/secret.key (besser: getrennt ablegen!)
    key_file: str = field(default_factory=lambda: os.environ.get("EAGLEEYE_KEY_FILE", ""))
    require_2fa: bool = field(default_factory=lambda: _bool("EAGLEEYE_REQUIRE_2FA", True))
    cookie_secure: bool = field(default_factory=lambda: _bool("EAGLEEYE_COOKIE_SECURE", False))
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(
        ["127.0.0.1", "localhost"] + [h.strip() for h in os.environ.get("EAGLEEYE_ALLOWED_HOSTS", "").split(",") if h.strip()]))
    session_idle_minutes: int = field(default_factory=lambda: int(os.environ.get("EAGLEEYE_SESSION_IDLE_MINUTES", "120")))
    session_max_hours: int = field(default_factory=lambda: int(os.environ.get("EAGLEEYE_SESSION_MAX_HOURS", "12")))
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    backup_dir: str = field(default_factory=lambda: os.environ.get("EAGLEEYE_BACKUP_DIR", ""))
    backup_keep: int = field(default_factory=lambda: int(os.environ.get("EAGLEEYE_BACKUP_KEEP", "14")))
    #: Stunde (0–23) für die automatische Sicherung; leer = aus
    backup_hour: str = field(default_factory=lambda: os.environ.get("EAGLEEYE_BACKUP_HOUR", ""))
    backup_passphrase: str = field(default_factory=lambda: os.environ.get("EAGLEEYE_BACKUP_PASSPHRASE", ""))
    auto_geocode: bool = True

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        # Passwort aus Datei (Docker-Secret) in die Verbindungs-URL einsetzen, ohne es in Umgebungsvariablen zu führen
        pw_file = os.environ.get("EAGLEEYE_DB_PASSWORD_FILE", "")
        if pw_file and self.database_url and "@" in self.database_url and ":" not in self.database_url.split("//", 1)[1].split("@", 1)[0]:
            from urllib.parse import quote

            password = Path(pw_file).read_text().strip()
            scheme, rest = self.database_url.split("//", 1)
            user, host = rest.split("@", 1)
            self.database_url = f"{scheme}//{user}:{quote(password, safe='')}@{host}"

    @property
    def resolved_key_file(self) -> Path:
        return Path(self.key_file) if self.key_file else self.data_dir / "secret.key"

    @property
    def resolved_backup_dir(self) -> Path:
        return Path(self.backup_dir) if self.backup_dir else self.data_dir / "backups"

    @property
    def dialect(self) -> str:
        return "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
