from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

POLICY_VERSION = "phase15.data-platform.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def redact_dsn(dsn: str) -> str:
    """Return a DSN safe for persistence/logging; credentials are never retained."""
    raw = str(dsn or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return "<invalid-dsn>"
    if not parts.scheme:
        return "<invalid-dsn>"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    if parts.username is not None:
        host = f"{quote(parts.username, safe='')}@{host}"
    # Password is deliberately omitted rather than replaced by a reversible marker.
    secret_keys = {"password", "passwd", "pwd", "token", "api_key", "apikey", "secret", "credential"}
    clean_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        clean_query.append((key, "<redacted>" if key.casefold() in secret_keys else value))
    return urlunsplit((parts.scheme, host, parts.path, urlencode(clean_query), ""))


@dataclass(frozen=True, slots=True)
class BackendStatus:
    backend_id: str
    backend_kind: str
    role: str
    configured: bool
    driver_available: bool
    live_validated: bool
    runtime_default: bool
    external_connection_opened: bool
    details: dict[str, Any]


class SQLitePhase15Backend:
    """Adapter around the already-open local SQLite runtime database."""

    kind = "sqlite"

    def __init__(self, db: Any) -> None:
        self.db = db

    def contract_probe(self) -> dict[str, Any]:
        integrity_row = self.db.one("PRAGMA integrity_check") or {}
        integrity = next(iter(integrity_row.values()), "unknown")
        row = self.db.one("SELECT COUNT(*) c FROM phase15_schema_meta") or {"c": 0}
        return {
            "backend_kind": self.kind,
            "connected": True,
            "integrity_check": integrity,
            "schema_meta_rows": int(row["c"]),
            "transactional": True,
            "external_connection_opened": False,
        }


class PostgresPhase15Backend:
    """Real PostgreSQL adapter, fail-closed and never auto-connected.

    The adapter uses psycopg when an operator explicitly requests a live probe.
    A connect_factory can be injected for deterministic contract tests without
    opening a network connection. No DSN secret is persisted by this class.
    """

    kind = "postgresql"

    def __init__(self, dsn: str, *, connect_factory: Callable[[str], Any] | None = None) -> None:
        self._dsn = str(dsn or "").strip()
        self._connect_factory = connect_factory

    @property
    def driver_available(self) -> bool:
        return self._connect_factory is not None or importlib.util.find_spec("psycopg") is not None

    @property
    def redacted_dsn(self) -> str:
        return redact_dsn(self._dsn)

    def _connect(self) -> Any:
        if not self._dsn:
            raise ValueError("PostgreSQL DSN required")
        if self._connect_factory is not None:
            return self._connect_factory(self._dsn)
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("psycopg is not installed; install EagleEye[data-platform]") from exc
        return psycopg.connect(self._dsn, connect_timeout=5, application_name="eagleeye-phase15")

    @staticmethod
    def _bootstrap_contract(cursor: Any) -> None:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS phase15_backend_contract_records(
               record_key TEXT PRIMARY KEY,
               value_json TEXT NOT NULL,
               updated_at TIMESTAMPTZ NOT NULL
            )"""
        )

    def contract_probe(self, *, live: bool = False) -> dict[str, Any]:
        base = {
            "backend_kind": self.kind,
            "configured": bool(self._dsn),
            "driver_available": self.driver_available,
            "redacted_dsn": self.redacted_dsn,
            "live_validated": False,
            "external_connection_opened": False,
        }
        if not live:
            return base | {"status": "not_run", "reason": "live validation requires explicit operator request"}
        connection = self._connect()
        try:
            with connection.cursor() as cur:
                self._bootstrap_contract(cur)
                key = "probe-" + uuid.uuid4().hex
                payload = _canon({"probe": True, "policy": POLICY_VERSION})
                cur.execute(
                    "INSERT INTO phase15_backend_contract_records(record_key,value_json,updated_at) VALUES(%s,%s,CURRENT_TIMESTAMP) ON CONFLICT(record_key) DO UPDATE SET value_json=EXCLUDED.value_json,updated_at=CURRENT_TIMESTAMP",
                    (key, payload),
                )
                cur.execute("SELECT value_json FROM phase15_backend_contract_records WHERE record_key=%s", (key,))
                row = cur.fetchone()
                if not row or row[0] != payload:
                    raise RuntimeError("PostgreSQL contract roundtrip mismatch")
                cur.execute("DELETE FROM phase15_backend_contract_records WHERE record_key=%s", (key,))
            connection.commit()
            return base | {"status": "pass", "live_validated": True, "external_connection_opened": True}
        finally:
            try:
                connection.close()
            except Exception:
                pass


class DataPlatformManager:
    def __init__(self, db: Any, *, actor: str = "local-analyst") -> None:
        self.db = db
        self.actor = actor
        self.sqlite = SQLitePhase15Backend(db)
        self._register_builtin()

    def _register_builtin(self) -> None:
        now = _now()
        config = {"path_ref": "runtime:phase15.sqlite", "external": False, "policy": POLICY_VERSION}
        body = {
            "backend_id": "sqlite_portable_v1",
            "backend_kind": "sqlite",
            "role": "transactional",
            "status": "active",
            "config_json": _canon(config),
            "live_validated": 1,
            "last_checked_at": now,
            "created_at": now,
        }
        self.db.execute(
            """INSERT OR IGNORE INTO phase15_data_backends(
               backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at,record_hash
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (*body.values(), _sha(body)),
        )

    def register_postgres(self, dsn: str, *, backend_id: str = "postgres_team_v1", live_validate: bool = False) -> dict[str, Any]:
        adapter = PostgresPhase15Backend(dsn)
        probe = adapter.contract_probe(live=bool(live_validate))
        now = _now()
        config = {
            "redacted_dsn": adapter.redacted_dsn,
            "credentials_persisted": False,
            "auto_connect": False,
            "driver_available": adapter.driver_available,
            "policy": POLICY_VERSION,
        }
        status = "validated" if probe.get("live_validated") else "configured_not_live_validated"
        body = {
            "backend_id": str(backend_id)[:120],
            "backend_kind": "postgresql",
            "role": "transactional_team",
            "status": status,
            "config_json": _canon(config),
            "live_validated": 1 if probe.get("live_validated") else 0,
            "last_checked_at": now,
            "created_at": now,
        }
        self.db.execute(
            """INSERT OR REPLACE INTO phase15_data_backends(
               backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at,record_hash
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (*body.values(), _sha(body)),
        )
        run = {
            "run_id": "bcr_" + uuid.uuid4().hex[:20],
            "backend_id": body["backend_id"],
            "backend_kind": "postgresql",
            "mode": "live" if live_validate else "configuration_only",
            "status": probe.get("status", "not_run"),
            "details_json": _canon(probe),
            "created_at": now,
        }
        self.db.execute(
            "INSERT INTO phase15_backend_contract_runs(run_id,backend_id,backend_kind,mode,status,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",
            (*run.values(), _sha(run)),
        )
        return {**body, "config": config, "probe": probe}

    def register_s3_config(self, *, endpoint_url: str, bucket: str, prefix: str = "eagleeye/phase15", sse: str = "AES256", backend_id: str = "s3_team_v1") -> dict[str, Any]:
        endpoint = str(endpoint_url or "").strip()
        if not endpoint.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("S3 endpoint must use HTTPS or explicit loopback development endpoint")
        if sse not in {"AES256", "aws:kms"}:
            raise ValueError("S3 server-side encryption is required")
        now = _now()
        config = {"endpoint_url": endpoint, "bucket": str(bucket).strip(), "prefix": str(prefix).strip("/"), "sse": sse, "credentials_persisted": False, "auto_connect": False, "policy": POLICY_VERSION}
        body = {"backend_id": str(backend_id)[:120], "backend_kind": "s3_compatible", "role": "object_store_team", "status": "configured_not_live_validated", "config_json": _canon(config), "live_validated": 0, "last_checked_at": now, "created_at": now}
        self.db.execute("INSERT OR REPLACE INTO phase15_data_backends(backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
        return {**body, "config": config, "live_validation": "not_run"}

    def status(self) -> dict[str, Any]:
        rows = self.db.all(
            "SELECT backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at FROM phase15_data_backends ORDER BY backend_kind,backend_id"
        )
        for row in rows:
            try:
                row["config"] = json.loads(row.pop("config_json"))
            except Exception:
                row["config"] = {}
            row["live_validated"] = bool(row["live_validated"])
        return {
            "policy": POLICY_VERSION,
            "portable_backend": self.sqlite.contract_probe(),
            "backends": rows,
            "postgres_driver_available": importlib.util.find_spec("psycopg") is not None,
            "automatic_external_connections": False,
        }
