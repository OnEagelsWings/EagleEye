from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts
from eagleeye_pro.version import SCHEMA_VERSION


class ReliabilityError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name and not path.is_absolute() and ".." not in path.parts and "\\" not in name)


def _parse_ts(value: str) -> float:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0.0


class ReliabilityQuality125Service:
    """Crash-aware reliability, encrypted backup and quality gate service.

    Build 125 keeps execution deterministic: it does not start hidden worker threads
    or background network activity. Recovery is explicit, persistent and audited.
    """

    BACKUP_MAGIC = b"EEBACKUP125\n"
    VAULT_REFERENCE = "reliability_backup_key_ref_125"

    def __init__(self, db: Any, audit: Any, base_dir: str | Path, *, protection: Any, scale_getter: Any) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.protection = protection
        self._scale_getter = scale_getter
        self._backup_key_lock = threading.RLock()
        self.root = self.base_dir / "data" / "reliability_125_0"
        self.backup_dir = self.root / "backups"
        self.stage_dir = self.root / "restore_staging"
        for path in (self.root, self.backup_dir, self.stage_dir):
            path.mkdir(parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass
        self.session_id = new_id("startup125")
        self._last_heartbeat_epoch = 0.0
        self._start_session()
        self.cleanup_expired_restore_stages(max_age_seconds=3600)
        self.recover_stale_state(stale_seconds=300, actor="startup-recovery")

    def _audit(self, action: str, object_type: str, object_id: str, case_id: str | None, details: dict[str, Any]) -> None:
        self.audit.log(action, object_type, object_id, case_id, details)

    def _start_session(self) -> None:
        now = now_ts()
        self.db.execute(
            "INSERT INTO reliability_startup_sessions_125(session_id,process_id,started_at,heartbeat_at) VALUES(?,?,?,?)",
            (self.session_id, os.getpid(), now, now),
        )
        self._audit("start", "reliability_startup_125", self.session_id, None, {"process_id": os.getpid()})

    def heartbeat(self, *, force: bool = False) -> None:
        now_epoch = time.time()
        if not force and now_epoch - self._last_heartbeat_epoch < 30.0:
            return
        self.db.execute(
            "UPDATE reliability_startup_sessions_125 SET heartbeat_at=? WHERE session_id=? AND clean_shutdown=0",
            (now_ts(), self.session_id),
        )
        self._last_heartbeat_epoch = now_epoch

    def close(self) -> None:
        try:
            self.db.execute(
                "UPDATE reliability_startup_sessions_125 SET heartbeat_at=?,clean_shutdown=1 WHERE session_id=?",
                (now_ts(), self.session_id),
            )
            self._audit("close", "reliability_startup_125", self.session_id, None, {"clean_shutdown": True})
        except Exception:
            pass

    @contextmanager
    def operation(
        self,
        operation_type: str,
        *,
        case_id: str | None = None,
        idempotency_key: str = "",
    ) -> Iterator[str]:
        operation_type = " ".join(str(operation_type).strip().split())[:100]
        if not operation_type:
            raise ReliabilityError("Operationstyp fehlt")
        idempotency_key = str(idempotency_key or "").strip()[:180]
        if idempotency_key:
            existing = self.db.one(
                "SELECT * FROM reliability_operations_125 WHERE case_id IS ? AND operation_type=? AND idempotency_key=?",
                (case_id, operation_type, idempotency_key),
            )
            if existing and existing["state"] == "completed":
                yield existing["operation_id"]
                return
            if existing and existing["state"] in {"running", "starting"}:
                raise ReliabilityError("Operation mit diesem Idempotenzschlüssel läuft bereits")
        operation_id = new_id("relop125")
        now = now_ts()
        self.db.execute(
            """INSERT INTO reliability_operations_125(
               operation_id,case_id,operation_type,idempotency_key,state,started_at,heartbeat_at)
               VALUES(?,?,?,?, 'running',?,?)""",
            (operation_id, case_id, operation_type, idempotency_key, now, now),
        )
        try:
            yield operation_id
        except BaseException as exc:
            self.db.execute(
                "UPDATE reliability_operations_125 SET state='failed',completed_at=?,heartbeat_at=?,error_text=? WHERE operation_id=?",
                (now_ts(), now_ts(), f"{type(exc).__name__}: {exc}"[:1200], operation_id),
            )
            self._audit("fail", "reliability_operation_125", operation_id, case_id, {"operation_type": operation_type, "error_type": type(exc).__name__})
            raise
        else:
            self.db.execute(
                "UPDATE reliability_operations_125 SET state='completed',completed_at=?,heartbeat_at=? WHERE operation_id=?",
                (now_ts(), now_ts(), operation_id),
            )
            self._audit("complete", "reliability_operation_125", operation_id, case_id, {"operation_type": operation_type})

    def _backup_key(self) -> bytes:
        # Backup creation may be triggered concurrently from the browser or CLI.
        # Serialize first-use key creation so every backup is encrypted with the
        # single key that is ultimately persisted in the protected vault.
        with self._backup_key_lock:
            encoded = self.protection.get_secret(self.VAULT_REFERENCE)
            if not encoded:
                key = AESGCM.generate_key(bit_length=256)
                self.protection.set_secret(self.VAULT_REFERENCE, base64.b64encode(key).decode("ascii"))
                encoded = self.protection.get_secret(self.VAULT_REFERENCE)
                if not encoded:
                    raise ReliabilityError("Backup-Schlüssel konnte nicht dauerhaft im Vault gespeichert werden")
            try:
                key = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise ReliabilityError("Backup-Schlüssel im Vault ist beschädigt") from exc
            if len(key) != 32:
                raise ReliabilityError("Backup-Schlüssel besitzt eine ungültige Länge")
            return key

    def _sqlite_snapshot(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(destination)) as target:
            self.db.conn.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.commit()
        try:
            with destination.open("rb") as handle:
                os.fsync(handle.fileno())
        except OSError:
            pass

    def _critical_files(self, include_evidence: bool) -> list[tuple[Path, str]]:
        files: list[tuple[Path, str]] = []
        if include_evidence:
            for relative_root in (
                Path("data/evidence_preservation_121"),
                Path("data/evidence_vault"),
                Path("data/local_evidence_vault_75"),
            ):
                root = self.base_dir / relative_root
                if not root.exists():
                    continue
                for file in root.rglob("*"):
                    if file.is_file() and not file.is_symlink():
                        files.append((file, file.relative_to(self.base_dir).as_posix()))
        return files

    def create_backup(
        self,
        *,
        actor: str,
        case_id: str | None = None,
        include_evidence: bool = True,
    ) -> dict[str, Any]:
        if case_id:
            if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
                raise KeyError("Fall nicht gefunden")
        backup_id = new_id("backup125")
        backup_key = self._backup_key()  # ensure the encrypted key record is part of the database snapshot
        with self.operation("encrypted_backup", case_id=case_id, idempotency_key=backup_id):
            with tempfile.TemporaryDirectory(prefix="eagleeye-backup125-") as tmp:
                tmpdir = Path(tmp)
                snapshot = tmpdir / "database.sqlite"
                archive = tmpdir / "payload.zip"
                self._sqlite_snapshot(snapshot)
                entries: list[dict[str, Any]] = []
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                    zf.write(snapshot, "database.sqlite")
                    entries.append({"path": "database.sqlite", "sha256": _sha256_file(snapshot), "size": snapshot.stat().st_size})
                    for source, arcname in self._critical_files(include_evidence):
                        zf.write(source, arcname)
                        entries.append({"path": arcname, "sha256": _sha256_file(source), "size": source.stat().st_size})
                    manifest = {
                        "format": "eagleeye-backup-125",
                        "backup_id": backup_id,
                        "schema_version": SCHEMA_VERSION,
                        "created_at": now_ts(),
                        "case_id": case_id or "",
                        "include_evidence": bool(include_evidence),
                        "entries": entries,
                    }
                    zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
                plaintext = archive.read_bytes()
                plaintext_sha = hashlib.sha256(plaintext).hexdigest()
                nonce = os.urandom(12)
                aad = f"eagleeye-backup-125:{backup_id}:{SCHEMA_VERSION}".encode("utf-8")
                ciphertext = AESGCM(backup_key).encrypt(nonce, plaintext, aad)
                header = {
                    "backup_id": backup_id,
                    "schema_version": SCHEMA_VERSION,
                    "nonce_b64": base64.b64encode(nonce).decode("ascii"),
                    "aad_b64": base64.b64encode(aad).decode("ascii"),
                    "plaintext_sha256": plaintext_sha,
                    "created_at": now_ts(),
                }
                final = self.backup_dir / f"{backup_id}.eebak"
                temporary = final.with_suffix(".tmp")
                with temporary.open("wb") as handle:
                    handle.write(self.BACKUP_MAGIC)
                    handle.write(json.dumps(header, sort_keys=True).encode("utf-8") + b"\n")
                    handle.write(ciphertext)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, final)
                try:
                    final.chmod(0o600)
                except OSError:
                    pass
                package_sha = _sha256_file(final)
                self.db.execute(
                    """INSERT INTO reliability_backups_125(
                    backup_id,case_id,file_name,status,encrypted,includes_evidence,package_sha256,
                    plaintext_sha256,size_bytes,schema_version,created_by,created_at)
                    VALUES(?,?,?,'created',1,?,?,?,?,?,?,?)""",
                    (
                        backup_id, case_id, final.name, int(bool(include_evidence)), package_sha,
                        plaintext_sha, final.stat().st_size, SCHEMA_VERSION, actor, now_ts(),
                    ),
                )
                verification = self.verify_backup(backup_id, actor=actor)
                return self.db.one("SELECT * FROM reliability_backups_125 WHERE backup_id=?", (backup_id,)) | {"verification": verification}

    def _read_backup(self, row: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        path = self.backup_dir / row["file_name"]
        if not path.is_file():
            raise ReliabilityError("Backup-Datei fehlt")
        if not hashlib.sha256(path.read_bytes()).hexdigest() == row["package_sha256"]:
            raise ReliabilityError("Backup-Paket-Hash stimmt nicht")
        with path.open("rb") as handle:
            if handle.readline() != self.BACKUP_MAGIC:
                raise ReliabilityError("Unbekanntes Backup-Format")
            try:
                header = json.loads(handle.readline().decode("utf-8"))
            except Exception as exc:
                raise ReliabilityError("Backup-Header ist beschädigt") from exc
            ciphertext = handle.read()
        if header.get("backup_id") != row["backup_id"]:
            raise ReliabilityError("Backup-ID stimmt nicht")
        nonce = base64.b64decode(header["nonce_b64"])
        aad = base64.b64decode(header["aad_b64"])
        try:
            plaintext = AESGCM(self._backup_key()).decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ReliabilityError("Backup konnte nicht authentifiziert oder entschlüsselt werden") from exc
        if hashlib.sha256(plaintext).hexdigest() != header.get("plaintext_sha256"):
            raise ReliabilityError("Entschlüsselter Backup-Hash stimmt nicht")
        return header, plaintext

    def verify_backup(self, backup_id: str, *, actor: str = "local-analyst") -> dict[str, Any]:
        row = self.db.one("SELECT * FROM reliability_backups_125 WHERE backup_id=?", (backup_id,))
        if not row:
            raise KeyError("Backup nicht gefunden")
        with self.operation("verify_backup", case_id=row.get("case_id"), idempotency_key=f"verify:{backup_id}:{int(time.time())}"):
            _header, plaintext = self._read_backup(row)
            with tempfile.TemporaryDirectory(prefix="eagleeye-verify125-") as tmp:
                archive = Path(tmp) / "payload.zip"
                archive.write_bytes(plaintext)
                with zipfile.ZipFile(archive, "r") as zf:
                    bad = zf.testzip()
                    if bad:
                        raise ReliabilityError(f"ZIP-Prüfung fehlgeschlagen: {bad}")
                    for item in zf.infolist():
                        if not _safe_member(item.filename):
                            raise ReliabilityError("Unsicherer Pfad im Backup")
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                    zf.extract("database.sqlite", tmp)
                    for entry in manifest.get("entries", []):
                        name = str(entry.get("path") or "")
                        if name == "database.sqlite":
                            content = (Path(tmp) / "database.sqlite").read_bytes()
                        else:
                            content = zf.read(name)
                        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                            raise ReliabilityError(f"Datei-Hash im Backup stimmt nicht: {name}")
                database = Path(tmp) / "database.sqlite"
                with sqlite3.connect(str(database)) as conn:
                    quick = conn.execute("PRAGMA quick_check").fetchone()[0]
                    foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
                    schema = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                result = {
                    "valid": quick == "ok" and not foreign,
                    "quick_check": quick,
                    "foreign_key_issues": len(foreign),
                    "schema_version": schema[0] if schema else "",
                    "entry_count": len(manifest.get("entries", [])),
                }
                if not result["valid"]:
                    raise ReliabilityError("Backup-Datenbank ist nicht integer")
                self.db.execute(
                    "UPDATE reliability_backups_125 SET status='verified',verified_at=?,verification_json=? WHERE backup_id=?",
                    (now_ts(), dumps(result), backup_id),
                )
                self._audit("verify", "reliability_backup_125", backup_id, row.get("case_id"), {**result, "actor": actor})
                return result

    def stage_restore(self, backup_id: str, *, actor: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM reliability_backups_125 WHERE backup_id=?", (backup_id,))
        if not row:
            raise KeyError("Backup nicht gefunden")
        self.verify_backup(backup_id, actor=actor)
        _header, plaintext = self._read_backup(row)
        stage_id = new_id("restore125")
        destination = self.stage_dir / stage_id
        destination.mkdir(parents=True, exist_ok=False)
        try:
            archive = destination / "payload.zip"
            archive.write_bytes(plaintext)
            with zipfile.ZipFile(archive, "r") as zf:
                for item in zf.infolist():
                    if not _safe_member(item.filename):
                        raise ReliabilityError("Unsicherer Pfad im Backup")
                zf.extractall(destination / "payload")
            archive.unlink(missing_ok=True)
            database = destination / "payload" / "database.sqlite"
            database_sha = _sha256_file(database)
            marker = {
                "stage_id": stage_id,
                "backup_id": backup_id,
                "database": str(database),
                "database_sha256": database_sha,
                "created_at": now_ts(),
                "instruction": "Anwendung schließen und die geprüfte Restore-Stufe über den Offline-Recovery-Befehl anwenden.",
            }
            (destination / "RESTORE_STAGE.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
            self.db.execute(
                "INSERT INTO reliability_restore_stages_125(stage_id,backup_id,stage_relpath,status,database_sha256,created_by,created_at,verified_at) VALUES(?,?,?,'staged',?,?,?,?)",
                (stage_id, backup_id, destination.relative_to(self.base_dir).as_posix(), database_sha, actor, now_ts(), now_ts()),
            )
            self._audit("stage", "reliability_restore_125", stage_id, row.get("case_id"), {"backup_id": backup_id, "database_sha256": database_sha})
            return self.db.one("SELECT * FROM reliability_restore_stages_125 WHERE stage_id=?", (stage_id,)) or {}
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def cleanup_expired_restore_stages(self, *, max_age_seconds: int = 3600) -> dict[str, int]:
        cutoff = time.time() - max(300, int(max_age_seconds))
        removed = 0
        for row in self.db.all("SELECT * FROM reliability_restore_stages_125 WHERE status='staged'"):
            created = _parse_ts(row.get("created_at", ""))
            if created and created >= cutoff:
                continue
            path = (self.base_dir / row["stage_relpath"]).resolve()
            if self.stage_dir.resolve() in path.parents:
                shutil.rmtree(path, ignore_errors=True)
            self.db.execute("UPDATE reliability_restore_stages_125 SET status='expired' WHERE stage_id=?", (row["stage_id"],))
            removed += 1
        if removed:
            self._audit("cleanup", "reliability_restore_125", new_id("cleanup125"), None, {"expired_stages_removed": removed})
        return {"removed": removed}

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _case_boundary_issues(self) -> list[dict[str, Any]]:
        checks: list[tuple[str, str]] = [
            (
                "search_task_target_case",
                """SELECT COUNT(*) AS n FROM search_tasks s JOIN targets t ON t.target_id=s.target_id
                   WHERE s.target_id IS NOT NULL AND s.case_id<>t.case_id""",
            ),
            (
                "adaptive_task_target_case",
                """SELECT COUNT(*) AS n FROM adaptive_search_tasks_123 a JOIN targets t ON t.target_id=a.target_id
                   WHERE a.case_id<>t.case_id""",
            ),
            (
                "workspace_intake_case",
                """SELECT COUNT(*) AS n FROM provider_intake_items_120 i JOIN provider_runs_120 r ON r.run_id=i.run_id
                   WHERE i.case_id<>r.case_id""",
            ),
            (
                "resolution_entity_source_case",
                """SELECT COUNT(*) AS n FROM resolution_entities_115 e JOIN targets t ON t.target_id=e.source_entity_id
                   WHERE e.case_id<>t.case_id""",
            ),
        ]
        issues: list[dict[str, Any]] = []
        for key, sql in checks:
            tables = [token for token in ("adaptive_search_tasks_123", "provider_intake_items_120", "provider_runs_120", "resolution_entities_115") if token in sql]
            if any(not self._table_exists(table) for table in tables):
                continue
            row = self.db.one(sql) or {"n": 0}
            count = int(row.get("n") or 0)
            if count:
                issues.append({"key": key, "count": count, "severity": "high"})
        return issues

    def run_integrity_check(self, *, case_id: str | None = None, actor: str = "local-analyst") -> dict[str, Any]:
        if case_id and not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("Fall nicht gefunden")
        started = time.perf_counter()
        quick = (self.db.one("PRAGMA quick_check") or {}).get("quick_check", "")
        foreign = self.db.all("PRAGMA foreign_key_check")
        issues = self._case_boundary_issues()
        if quick != "ok":
            issues.append({"key": "sqlite_quick_check", "detail": quick, "severity": "critical"})
        if foreign:
            issues.append({"key": "foreign_key_check", "count": len(foreign), "severity": "critical"})
        stale_jobs = 0
        if self._table_exists("background_jobs_123"):
            stale_jobs = int((self.db.one("SELECT COUNT(*) AS n FROM background_jobs_123 WHERE status='running'") or {}).get("n") or 0)
            if stale_jobs:
                issues.append({"key": "running_jobs_review", "count": stale_jobs, "severity": "warning"})
        evidence = self.protection.verify_evidence_checkpoints(case_id) if case_id else {"valid": True, "checkpoint_count": 0}
        if case_id and not evidence.get("valid"):
            issues.append({"key": "evidence_checkpoint", "errors": evidence.get("errors", []), "severity": "critical"})
        security = self.protection.assess(case_id)
        if security["score"] < 85:
            issues.append({"key": "investigator_protection", "score": security["score"], "severity": "warning"})
        latest_backup = self.db.one("SELECT created_at,status FROM reliability_backups_125 ORDER BY created_at DESC LIMIT 1")
        if not latest_backup:
            issues.append({"key": "backup_missing", "severity": "warning"})
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        critical = sum(1 for item in issues if item.get("severity") in {"critical", "high"})
        score = max(0, 100 - critical * 25 - sum(1 for item in issues if item.get("severity") == "warning") * 8)
        status = "pass" if critical == 0 else "fail"
        report = {
            "status": status,
            "score": score,
            "quick_check": quick,
            "foreign_key_issues": len(foreign),
            "issues": issues,
            "stale_jobs": stale_jobs,
            "evidence": evidence,
            "security_score": security["score"],
            "latest_backup": latest_backup or {},
            "elapsed_ms": round(elapsed_ms, 3),
        }
        run_id = new_id("integrity125")
        self.db.execute(
            "INSERT INTO reliability_integrity_runs_125(run_id,case_id,status,score,issue_count,report_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (run_id, case_id, status, score, len(issues), dumps(report), actor, now_ts()),
        )
        self._audit("check", "reliability_integrity_125", run_id, case_id, {"status": status, "score": score, "issue_count": len(issues), "elapsed_ms": elapsed_ms})
        return {"run_id": run_id, **report}

    def recover_stale_state(self, *, case_id: str | None = None, stale_seconds: int = 300, actor: str = "local-analyst") -> dict[str, Any]:
        threshold = time.time() - max(30, int(stale_seconds))
        recovered_operations = 0
        for row in self.db.all("SELECT * FROM reliability_operations_125 WHERE state='running'"):
            if _parse_ts(row.get("heartbeat_at", "")) and _parse_ts(row["heartbeat_at"]) >= threshold:
                continue
            self.db.execute(
                "UPDATE reliability_operations_125 SET state='failed',completed_at=?,error_text='Recovered after stale running state' WHERE operation_id=? AND state='running'",
                (now_ts(), row["operation_id"]),
            )
            recovered_operations += 1
        recovered_sessions = 0
        for row in self.db.all("SELECT * FROM reliability_startup_sessions_125 WHERE clean_shutdown=0 AND session_id<>?", (self.session_id,)):
            if _parse_ts(row.get("heartbeat_at", "")) and _parse_ts(row["heartbeat_at"]) >= threshold:
                continue
            self.db.execute(
                "UPDATE reliability_startup_sessions_125 SET recovered_at=?,notes='unclean shutdown detected' WHERE session_id=?",
                (now_ts(), row["session_id"]),
            )
            recovered_sessions += 1
        job_result = {"recovered": 0}
        cases_for_recovery = [{"case_id": case_id}] if case_id else (self.db.all("SELECT case_id FROM cases") if self._table_exists("background_jobs_123") else [])
        if cases_for_recovery:
            scale = self._scale_getter()
            total = 0
            for case in cases_for_recovery:
                result = scale.recover_stale_jobs(case_id=case["case_id"], stale_seconds=stale_seconds)
                total += int(result.get("recovered") or 0)
            job_result = {"recovered": total}
        result = {
            "operations": recovered_operations,
            "startup_sessions": recovered_sessions,
            "jobs": int(job_result.get("recovered") or 0),
        }
        if any(result.values()):
            self._audit("recover", "reliability_recovery_125", new_id("recover125"), case_id, {**result, "actor": actor})
        return result

    def record_performance_gate(self, *, operation: str, budget_ms: float, observed_ms: float, sample_count: int = 1, details: dict[str, Any] | None = None) -> dict[str, Any]:
        gate_id = new_id("perfgate125")
        within = float(observed_ms) <= float(budget_ms)
        self.db.execute(
            "INSERT INTO reliability_performance_gates_125(gate_id,operation,budget_ms,observed_ms,within_budget,sample_count,details_json,measured_at) VALUES(?,?,?,?,?,?,?,?)",
            (gate_id, operation[:100], float(budget_ms), float(observed_ms), int(within), max(1, int(sample_count)), dumps(details or {}), now_ts()),
        )
        return self.db.one("SELECT * FROM reliability_performance_gates_125 WHERE gate_id=?", (gate_id,)) or {}

    def dashboard(self, case_id: str | None = None) -> dict[str, Any]:
        latest = self.db.one(
            "SELECT * FROM reliability_integrity_runs_125 WHERE case_id IS ? ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        )
        backups = self.db.all("SELECT * FROM reliability_backups_125 ORDER BY created_at DESC LIMIT 30")
        operations = self.db.all(
            "SELECT * FROM reliability_operations_125 WHERE case_id IS ? OR case_id IS NULL ORDER BY started_at DESC LIMIT 50",
            (case_id,),
        )
        stages = self.db.all("SELECT * FROM reliability_restore_stages_125 ORDER BY created_at DESC LIMIT 20")
        startups = self.db.all("SELECT * FROM reliability_startup_sessions_125 ORDER BY started_at DESC LIMIT 20")
        return {
            "latest_integrity": latest or {},
            "backups": backups,
            "operations": operations,
            "restore_stages": stages,
            "startup_sessions": startups,
            "protection": self.protection.assess(case_id),
        }


def apply_restore_stage(base_dir: str | Path, stage_id: str) -> dict[str, Any]:
    """Apply a previously verified restore stage while EagleEye is offline.

    The function intentionally has no AppContext dependency. The live server holds
    the same cross-process lock for its entire lifetime, so a restore fails closed
    whenever the workspace is still running.
    """
    from eagleeye.bootstrap.runtime_lock import workspace_runtime_lock

    root = Path(base_dir).resolve()
    clean_stage = str(stage_id or "").strip()
    if not clean_stage or not all(ch.isalnum() or ch in "_-" for ch in clean_stage):
        raise ReliabilityError("Ungültige Restore-Stufe")
    stage_root = (root / "data" / "reliability_125_0" / "restore_staging" / clean_stage).resolve()
    allowed_root = (root / "data" / "reliability_125_0" / "restore_staging").resolve()
    if allowed_root not in stage_root.parents or not stage_root.is_dir():
        raise ReliabilityError("Restore-Stufe nicht gefunden oder außerhalb des erlaubten Bereichs")
    marker_path = stage_root / "RESTORE_STAGE.json"
    if not marker_path.is_file():
        raise ReliabilityError("Restore-Marker fehlt")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("stage_id") != clean_stage:
        raise ReliabilityError("Restore-Marker stimmt nicht mit der Stufe überein")
    payload = stage_root / "payload"
    database = payload / "database.sqlite"
    if not database.is_file():
        raise ReliabilityError("Geprüfte Restore-Datenbank fehlt")
    database_sha = _sha256_file(database)
    if marker.get("database_sha256") and marker["database_sha256"] != database_sha:
        raise ReliabilityError("Restore-Datenbank wurde nach dem Staging verändert")
    with sqlite3.connect(str(database)) as conn:
        quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
    if quick != "ok" or foreign:
        raise ReliabilityError("Restore-Datenbank ist nicht integer")

    with workspace_runtime_lock(root, timeout=0.0):
        data_dir = root / "data"
        active_db = data_dir / "eagleeye.db"
        safety_root = root / "data" / "reliability_125_0" / "pre_restore_safety" / f"{clean_stage}_{int(time.time())}"
        safety_root.mkdir(parents=True, exist_ok=False)
        try:
            if active_db.exists():
                shutil.copy2(active_db, safety_root / "eagleeye.db")
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(active_db) + suffix)
                if sidecar.exists():
                    shutil.copy2(sidecar, safety_root / sidecar.name)
            temporary = active_db.with_suffix(".restore.tmp")
            shutil.copy2(database, temporary)
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, active_db)
            for suffix in ("-wal", "-shm"):
                Path(str(active_db) + suffix).unlink(missing_ok=True)

            restored_dirs: list[str] = []
            staged_data = payload / "data"
            if staged_data.is_dir():
                for name in ("evidence_preservation_121", "evidence_vault", "local_evidence_vault_75"):
                    source = staged_data / name
                    if not source.exists():
                        continue
                    destination = data_dir / name
                    if destination.exists():
                        shutil.move(str(destination), str(safety_root / name))
                    shutil.copytree(source, destination)
                    restored_dirs.append(name)
            result = {
                "applied": True,
                "stage_id": clean_stage,
                "database_sha256": database_sha,
                "restored_directories": restored_dirs,
                "safety_copy": str(safety_root),
                "applied_at": now_ts(),
            }
            (safety_root / "RESTORE_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            shutil.rmtree(stage_root, ignore_errors=True)
            return result
        except Exception:
            backup_db = safety_root / "eagleeye.db"
            if backup_db.exists():
                shutil.copy2(backup_db, active_db)
            raise
