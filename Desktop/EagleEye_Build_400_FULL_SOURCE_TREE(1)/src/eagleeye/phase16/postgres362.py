from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

POLICY = "phase16.postgresql-team-profile.v362"
AI_POLICY = "phase16.autonomous-investigation.v362"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v362"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _quote_ident(name: str) -> str:
    value = str(name or "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


def _pg_type(sqlite_type: str) -> str:
    t = str(sqlite_type or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(x in t for x in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    if "BLOB" in t:
        return "BYTEA"
    if any(x in t for x in ("NUM", "DEC")):
        return "NUMERIC"
    return "TEXT"


def _is_secret_key(key: str) -> bool:
    s = str(key or "").casefold()
    return any(x in s for x in ("password", "passwd", "pwd", "token", "secret", "credential", "api_key", "apikey"))


@dataclass(frozen=True, slots=True)
class MigrationTable362:
    name: str
    columns: tuple[dict[str, Any], ...]
    row_count: int
    rows_hash: str


class SQLiteMigrationSnapshot362:
    """Deterministic snapshot of the active consolidated SQLite data plane.

    Virtual tables and their internal shadow tables are excluded from the PostgreSQL
    transactional migration plan. Search indexes are rebuilt by the search backend;
    evidence/data rows remain represented by their canonical source tables.
    """

    SHADOW_SUFFIXES = ("_data", "_idx", "_content", "_docsize", "_config")

    def __init__(self, db: Any):
        self.db = db

    def table_names(self) -> list[str]:
        rows = self.db.all("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name")
        out: list[str] = []
        names = {str(r.get("name") or "") for r in rows}
        virtual_roots = {
            str(r.get("name") or "")
            for r in rows
            if str(r.get("sql") or "").lstrip().upper().startswith("CREATE VIRTUAL TABLE")
        }
        shadows = {root + suffix for root in virtual_roots for suffix in self.SHADOW_SUFFIXES}
        for row in rows:
            name = str(row.get("name") or "")
            if not name or name.startswith("sqlite_") or name in virtual_roots or name in shadows:
                continue
            out.append(name)
        return out

    def columns(self, table: str) -> list[dict[str, Any]]:
        q = _quote_ident(table)
        rows = self.db.all(f"PRAGMA table_info({q})")
        return [
            {
                "name": str(r.get("name") or ""),
                "type": str(r.get("type") or "TEXT"),
                "notnull": bool(r.get("notnull")),
                "default": r.get("dflt_value"),
                "pk": int(r.get("pk") or 0),
            }
            for r in rows
        ]

    def rows(self, table: str) -> list[dict[str, Any]]:
        q = _quote_ident(table)
        rows = self.db.all(f"SELECT * FROM {q}")
        return sorted(rows, key=_canon)

    def manifest(self, tables: Iterable[str] | None = None) -> dict[str, Any]:
        selected = list(tables) if tables is not None else self.table_names()
        items: list[dict[str, Any]] = []
        total = 0
        for table in selected:
            cols = self.columns(table)
            rows = self.rows(table)
            total += len(rows)
            items.append(
                {
                    "table": table,
                    "columns": cols,
                    "row_count": len(rows),
                    "rows_hash": _sha(rows),
                }
            )
        payload = {
            "policy": POLICY,
            "tables": items,
            "table_count": len(items),
            "row_count": total,
        }
        payload["manifest_hash"] = _sha(payload)
        return payload

    def export_jsonl_gz(self, target: str | Path, tables: Iterable[str] | None = None) -> dict[str, Any]:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        manifest = self.manifest(tables)
        with gzip.open(target, "wt", encoding="utf-8", newline="\n") as fh:
            fh.write(_canon({"kind": "manifest", "value": manifest}) + "\n")
            for item in manifest["tables"]:
                table = item["table"]
                for row in self.rows(table):
                    fh.write(_canon({"kind": "row", "table": table, "value": row}) + "\n")
        return {
            "path": str(target),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "manifest_hash": manifest["manifest_hash"],
            "table_count": manifest["table_count"],
            "row_count": manifest["row_count"],
        }

    def sqlite_backup_restore_drill(self, target_dir: str | Path) -> dict[str, Any]:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_path = target_dir / "phase16_362_rollback.sqlite"
        source_manifest = self.manifest()
        with sqlite3.connect(str(backup_path)) as dst:
            self.db.conn.backup(dst)
        restored = sqlite3.connect(str(backup_path))
        restored.row_factory = sqlite3.Row
        try:
            class _DB:
                def __init__(self, conn): self.conn = conn
                def all(self, sql, params=()): return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]
            restored_manifest = SQLiteMigrationSnapshot362(_DB(restored)).manifest()
        finally:
            restored.close()
        ok = source_manifest["manifest_hash"] == restored_manifest["manifest_hash"]
        return {
            "status": "pass" if ok else "fail",
            "backup_path": str(backup_path),
            "backup_sha256": hashlib.sha256(backup_path.read_bytes()).hexdigest(),
            "source_manifest_hash": source_manifest["manifest_hash"],
            "restored_manifest_hash": restored_manifest["manifest_hash"],
            "table_count": source_manifest["table_count"],
            "row_count": source_manifest["row_count"],
            "rollback_verified": ok,
            "external_postgresql_used": False,
        }


class PostgresMigrationPlanner362:
    def __init__(self, snapshot: SQLiteMigrationSnapshot362):
        self.snapshot = snapshot

    def create_table_sql(self, table: str) -> str:
        cols = self.snapshot.columns(table)
        if not cols:
            raise ValueError(f"table has no columns: {table}")
        pk_cols = [c for c in sorted(cols, key=lambda x: x["pk"] or 9999) if c["pk"]]
        parts: list[str] = []
        for col in cols:
            definition = f'{_quote_ident(col["name"])} {_pg_type(col["type"])}'
            if col["notnull"]:
                definition += " NOT NULL"
            parts.append(definition)
        if pk_cols:
            parts.append("PRIMARY KEY (" + ",".join(_quote_ident(c["name"]) for c in pk_cols) + ")")
        return f"CREATE TABLE IF NOT EXISTS {_quote_ident(table)} (" + ",".join(parts) + ")"

    def insert_sql(self, table: str) -> tuple[str, list[str]]:
        columns = [c["name"] for c in self.snapshot.columns(table)]
        if not columns:
            raise ValueError("no columns")
        sql = (
            f"INSERT INTO {_quote_ident(table)} (" + ",".join(_quote_ident(c) for c in columns) + ") "
            + "VALUES (" + ",".join(["%s"] * len(columns)) + ")"
        )
        return sql, columns

    def plan(self) -> dict[str, Any]:
        manifest = self.snapshot.manifest()
        tables = []
        for item in manifest["tables"]:
            sql, columns = self.insert_sql(item["table"])
            tables.append(
                {
                    "table": item["table"],
                    "create_sql": self.create_table_sql(item["table"]),
                    "insert_sql": sql,
                    "columns": columns,
                    "row_count": item["row_count"],
                    "rows_hash": item["rows_hash"],
                }
            )
        result = {
            "policy": POLICY,
            "source_manifest_hash": manifest["manifest_hash"],
            "table_count": len(tables),
            "row_count": manifest["row_count"],
            "tables": tables,
            "search_virtual_tables_rebuilt_separately": True,
            "triggers_reimplemented_by_team_backend_migrations": True,
        }
        result["plan_hash"] = _sha(result)
        return result


class PostgresTeamProfile362:
    """Explicit PostgreSQL team profile. Never connects during normal startup."""

    def __init__(self, db: Any, *, data_platform: Any, base_dir: str | Path, actor: str = "local-analyst"):
        self.db = db
        self.data_platform = data_platform
        self.base_dir = Path(base_dir)
        self.actor = actor
        self.snapshot = SQLiteMigrationSnapshot362(db)
        self.planner = PostgresMigrationPlanner362(self.snapshot)
        self._last_live_result: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY,
            "postgres_driver_available": importlib.util.find_spec("psycopg") is not None,
            "postgres_server_available_in_build_environment": False,
            "automatic_external_connections": False,
            "live_validation_status": (self._last_live_result or {}).get("status", "not_run"),
            "externally_validated": bool((self._last_live_result or {}).get("externally_validated")),
            "sqlite_remains_default": True,
            "migration_plan": {
                "table_count": self.snapshot.manifest()["table_count"],
                "row_count": self.snapshot.manifest()["row_count"],
            },
        }

    def migration_plan(self) -> dict[str, Any]:
        return self.planner.plan()

    def local_rollback_drill(self) -> dict[str, Any]:
        return self.snapshot.sqlite_backup_restore_drill(self.base_dir / "data" / "phase16_362_drills")

    def _connect(self, dsn: str, connect_factory: Callable[[str], Any] | None = None) -> Any:
        if connect_factory is not None:
            return connect_factory(dsn)
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError("psycopg is unavailable; install EagleEye[data-platform]") from exc
        return psycopg.connect(dsn, connect_timeout=5, application_name="eagleeye-build362")

    @staticmethod
    def _set_schema(cursor: Any, schema: str) -> None:
        cursor.execute(f"CREATE SCHEMA {_quote_ident(schema)}")
        cursor.execute(f"SET search_path TO {_quote_ident(schema)}")

    def _migrate_into_connection(self, connection: Any, schema: str) -> dict[str, Any]:
        plan = self.planner.plan()
        with connection.cursor() as cur:
            self._set_schema(cur, schema)
            cur.execute("CREATE TABLE eagleeye_362_meta(key TEXT PRIMARY KEY,value_json TEXT NOT NULL)")
            for item in plan["tables"]:
                cur.execute(item["create_sql"])
                rows = self.snapshot.rows(item["table"])
                if rows:
                    values = [tuple(row.get(c) for c in item["columns"]) for row in rows]
                    cur.executemany(item["insert_sql"], values)
            cur.execute("INSERT INTO eagleeye_362_meta(key,value_json) VALUES(%s,%s)", ("source_manifest", _canon({"hash": plan["source_manifest_hash"]})))
        connection.commit()
        return plan

    def _verify_connection(self, connection: Any, schema: str, plan: dict[str, Any]) -> dict[str, Any]:
        verified = 0
        with connection.cursor() as cur:
            cur.execute(f"SET search_path TO {_quote_ident(schema)}")
            for item in plan["tables"]:
                cur.execute(f"SELECT COUNT(*) FROM {_quote_ident(item['table'])}")
                row = cur.fetchone()
                count = int(row[0]) if row else -1
                if count != int(item["row_count"]):
                    return {"status": "fail", "table": item["table"], "expected": item["row_count"], "actual": count}
                verified += 1
        return {"status": "pass", "tables_verified": verified}

    def live_validation(self, *, dsn: str | None = None, connect_factory: Callable[[str], Any] | None = None, destructive_validation_schema_only: bool = True) -> dict[str, Any]:
        raw = str(dsn or os.getenv("EAGLEEYE_POSTGRES_DSN") or "").strip()
        if not raw:
            result = {
                "status": "not_run",
                "reason": "EAGLEEYE_POSTGRES_DSN not configured",
                "externally_validated": False,
                "external_connection_opened": False,
                "policy": POLICY,
            }
            self._last_live_result = result
            return result
        schema = "eagleeye_validate_362_" + uuid.uuid4().hex[:10]
        conn = self._connect(raw, connect_factory)
        conn2 = None
        try:
            plan = self._migrate_into_connection(conn, schema)
            verification = self._verify_connection(conn, schema, plan)
            if verification.get("status") != "pass":
                raise RuntimeError(f"PostgreSQL migration verification failed: {verification}")
            # A second independent connection proves concurrent visibility/commit semantics.
            conn2 = self._connect(raw, connect_factory)
            with conn2.cursor() as cur:
                cur.execute(f"SET search_path TO {_quote_ident(schema)}")
                cur.execute("CREATE TABLE IF NOT EXISTS eagleeye_362_concurrency(worker_id TEXT PRIMARY KEY,value_text TEXT NOT NULL)")
                cur.execute("INSERT INTO eagleeye_362_concurrency(worker_id,value_text) VALUES(%s,%s)", ("worker-b", "committed"))
            conn2.commit()
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {_quote_ident(schema)}")
                cur.execute("INSERT INTO eagleeye_362_concurrency(worker_id,value_text) VALUES(%s,%s)", ("worker-a", "committed"))
                cur.execute("SELECT COUNT(*) FROM eagleeye_362_concurrency")
                count = int(cur.fetchone()[0])
            conn.commit()
            if count != 2:
                raise RuntimeError("PostgreSQL concurrent visibility probe failed")
            result = {
                "status": "pass",
                "externally_validated": connect_factory is None,
                "external_connection_opened": connect_factory is None,
                "schema": schema,
                "migration": {"table_count": plan["table_count"], "row_count": plan["row_count"], "source_manifest_hash": plan["source_manifest_hash"]},
                "verification": verification,
                "concurrency_probe": "pass",
                "truthful_note": "Injected connection factories prove contract behavior only; external validation is true only for an actual psycopg connection.",
                "policy": POLICY,
            }
            self._last_live_result = result
            return result
        finally:
            if destructive_validation_schema_only:
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"DROP SCHEMA IF EXISTS {_quote_ident(schema)} CASCADE")
                    conn.commit()
                except Exception:
                    try: conn.rollback()
                    except Exception: pass
            for item in (conn2, conn):
                if item is not None:
                    try: item.close()
                    except Exception: pass


class AutonomousInvestigation362:
    def __init__(self, db: Any, *, base361: Any, postgres362: PostgresTeamProfile362):
        self.db = db
        self.base361 = base361
        self.postgres362 = postgres362

    def status(self) -> dict[str, Any]:
        base = dict(self.base361.status())
        base.update({
            "policy_version": AI_POLICY,
            "infrastructure_aware": True,
            "plausibility_bands": True,
            "dossier_records_backend_validation_state": True,
        })
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base361.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            for h in dossier.get("hypotheses") or []:
                value = float(h.get("plausibility") or h.get("confidence") or 0.0)
                h["plausibility_band"] = "high" if value >= 0.70 else "medium" if value >= 0.40 else "low"
            pg = self.postgres362.status()
            dossier["phase16_infrastructure_context"] = {
                "team_backend": "postgresql",
                "externally_validated": pg["externally_validated"],
                "live_validation_status": pg["live_validation_status"],
                "sqlite_portable_fallback": True,
            }
            dossier["lead_review_required"] = True
        return out


class DefensiveOpsecSupervisor362:
    def __init__(self, db: Any, *, base361: Any, data_platform: Any):
        self.db = db
        self.base361 = base361
        self.data_platform = data_platform

    def status(self) -> dict[str, Any]:
        base = dict(self.base361.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "backend_secret_hygiene_monitor": True,
            "can_defensively_stop_jobs_on_backend_secret_risk": True,
            "system_mutations": False,
        })
        return base

    def _backend_secret_findings(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for row in self.db.all("SELECT backend_id,backend_kind,config_json FROM phase15_data_backends ORDER BY backend_id"):
            try:
                config = json.loads(row.get("config_json") or "{}")
            except Exception:
                config = {}
            for key, value in config.items():
                if _is_secret_key(key) and value not in (None, "", False, "<redacted>"):
                    findings.append({"backend_id": row.get("backend_id"), "backend_kind": row.get("backend_kind"), "field": key})
            text = str(row.get("config_json") or "")
            if re.search(r"postgres(?:ql)?://[^/@:\s]+:[^/@\s]+@", text, re.I):
                findings.append({"backend_id": row.get("backend_id"), "backend_kind": row.get("backend_kind"), "field": "dsn_password"})
        return findings

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base361.protect_case(case_id=case_id)
        findings = self._backend_secret_findings()
        stopped: list[str] = []
        if findings:
            jobs = self.db.all("SELECT job_id FROM phase15_jobs WHERE case_id=? AND status IN ('queued','retry','running')", (case_id,))
            for job in jobs:
                self.db.execute(
                    "UPDATE phase15_jobs SET status='cancelled',error_text=?,updated_at=? WHERE job_id=?",
                    ("OPSEC362 backend secret hygiene defensive stop", _now(), job["job_id"]),
                )
                stopped.append(job["job_id"])
        return {
            **base,
            "backend_secret_findings": findings,
            "backend_risk_jobs_stopped": stopped,
            "system_mutations": False,
            "policy_version": OPSEC_POLICY,
        }
