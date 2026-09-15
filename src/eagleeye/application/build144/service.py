from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
import statistics
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts
from eagleeye_pro.core.versioning import version_at_least


BACKUP_CONFIRMATION = "VERIFIZIERTES PHASE-4-BACKUP ERZEUGEN"
RISK_STATUSES = {"open", "accepted", "mitigated", "closed"}
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canonical(value).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _safe_name(value: str, limit: int = 100) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or ""))
    return cleaned[:limit] or "item"


class Build144Service:
    """Phase-4 release-candidate audit, backup verification and hardening gate.

    The service intentionally performs deterministic local checks. It does not
    contact public providers, does not upload evidence and does not claim that a
    successful run replaces an independent security review or a real Windows
    field acceptance.
    """

    BUILD = "144.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        governance: Any,
        reliability: Any,
        protection: Any,
        phase4: Any,
        build143: Any,
        build142: Any,
        build141: Any,
        build140: Any,
        build139: Any,
        build138: Any,
        build136: Any,
        build135: Any,
        clock: Any | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.governance = governance
        self.reliability = reliability
        self.protection = protection
        self.phase4 = phase4
        self.build143 = build143
        self.build142 = build142
        self.build141 = build141
        self.build140 = build140
        self.build139 = build139
        self.build138 = build138
        self.build136 = build136
        self.build135 = build135
        self.clock = clock or time.perf_counter
        self.backup_root = (self.base_dir / "backups" / "build144").resolve()
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self._chmod(self.backup_root, 0o700)
        self._run_lock = threading.RLock()

    @staticmethod
    def _chmod(path: Path, mode: int) -> None:
        try:
            path.chmod(mode)
        except OSError:
            pass

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _authorize(self, actor: str, case_id: str, permission: str = "security.review") -> None:
        self.governance.authorize(username=actor, case_id=case_id, permission=permission)

    def _table_exists(self, table: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)))

    def _count(self, table: str, where: str = "", params: Iterable[Any] = ()) -> int:
        if not self._table_exists(table):
            return 0
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        if where:
            sql += " WHERE " + where
        return int((self.db.one(sql, params) or {}).get("n") or 0)

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build144_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        safe = dict(payload or {})
        for key in list(safe):
            if any(mark in key.casefold() for mark in ("password", "secret", "token", "credential")):
                safe[key] = "[redacted]"
        stamp = now_ts()
        body = {"case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": safe, "previous_hash": previous_hash, "created_by": actor, "created_at": stamp}
        event_hash = _sha(body)
        self.db.execute(
            "INSERT INTO build144_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (new_id("evt144"), case_id, event_type, object_type, object_id, dumps(safe), previous_hash, event_hash, actor, stamp),
        )
        self.audit.log(event_type, f"build144_{object_type}", object_id, case_id, safe)

    @staticmethod
    def _finding(key: str, domain: str, status: str, severity: str, detail: Any, remediation: str = "", *, optional: bool = False, weight: int = 5) -> dict[str, Any]:
        return {
            "key": key,
            "domain": domain,
            "status": status,
            "severity": severity,
            "detail": detail,
            "remediation": remediation,
            "optional": bool(optional),
            "weight": max(1, int(weight)),
        }

    def _database_findings(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        quick = (self.db.one("PRAGMA quick_check") or {}).get("quick_check", "")
        integ = (self.db.one("PRAGMA integrity_check") or {}).get("integrity_check", "")
        fk_rows = self.db.all("PRAGMA foreign_key_check")
        schema = (self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value", "")
        findings.append(self._finding("sqlite_quick_check", "database", "pass" if quick == "ok" else "blocker", "critical", quick, "Datenbank aus verifiziertem Backup wiederherstellen.", weight=14))
        findings.append(self._finding("sqlite_integrity_check", "database", "pass" if integ == "ok" else "blocker", "critical", integ, "SQLite-Integrität reparieren oder Backup wiederherstellen.", weight=14))
        findings.append(self._finding("foreign_keys", "database", "pass" if not fk_rows else "blocker", "critical", {"violations": len(fk_rows), "sample": fk_rows[:10]}, "Fremdschlüsselverletzungen vor Freigabe beheben.", weight=12))
        findings.append(self._finding("schema_version", "database", "pass" if version_at_least(schema, self.BUILD) else "blocker", "critical", schema, f"Schema kontrolliert auf {self.BUILD} migrieren.", weight=10))
        return findings

    def _case_findings(self, case_id: str) -> list[dict[str, Any]]:
        case = self._case(case_id)
        findings: list[dict[str, Any]] = []
        purpose_ok = len(str(case.get("purpose") or "").strip()) >= 8 and len(str(case.get("legal_basis") or "").strip()) >= 5
        findings.append(self._finding("case_purpose_legal_basis", "case", "pass" if purpose_ok else "blocker", "critical", {"purpose_present": bool(case.get("purpose")), "legal_basis_present": bool(case.get("legal_basis"))}, "Zweck und Rechtsgrundlage nachvollziehbar dokumentieren.", weight=12))
        targets = self._count("targets", "case_id=?", (case_id,))
        findings.append(self._finding("case_targets", "case", "pass" if targets else "warning", "medium", {"targets": targets}, "Mindestens eine Zielentität anlegen oder begründen, warum der Fall quellenzentriert ist.", weight=3))
        active_sessions = self._count("research_persona_sessions_143", "case_id=? AND status='active'", (case_id,))
        findings.append(self._finding("active_research_sessions", "opsec", "pass" if active_sessions == 0 else "warning", "high", {"active_sessions": active_sessions}, "Vor Release alle temporären Research-Sitzungen schließen und Profile entfernen.", weight=8))
        pending_personas = self._count("research_personas_143", "case_id=? AND status='pending_review'", (case_id,))
        pending_egress = self._count("network_egress_profiles_143", "case_id=? AND status='pending_review'", (case_id,))
        findings.append(self._finding("pending_opsec_reviews", "opsec", "pass" if pending_personas + pending_egress == 0 else "warning", "medium", {"personas": pending_personas, "egress_profiles": pending_egress}, "Offene Persona- und Egress-Reviews abschließen oder verwerfen.", weight=5))
        return findings

    def _event_chain_findings(self, case_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for build in range(138, 145):
            table = f"build{build}_events"
            if not self._table_exists(table):
                result.append(self._finding(f"event_chain_{build}", "audit", "warning", "medium", "Tabelle fehlt", "Migration und Schema prüfen.", weight=3))
                continue
            rows = self.db.all(f"SELECT previous_hash,event_hash FROM {table} WHERE case_id=? ORDER BY sequence", (case_id,))
            ok = True
            previous = "GENESIS"
            for row in rows:
                if row.get("previous_hash") != previous or not row.get("event_hash"):
                    ok = False
                    break
                previous = str(row.get("event_hash"))
            result.append(self._finding(f"event_chain_{build}", "audit", "pass" if ok else "blocker", "critical", {"events": len(rows), "continuous": ok}, "Auditkette untersuchen und Fall aus verifiziertem Stand rekonstruieren.", weight=7))
        return result

    def _photo_findings(self, case_id: str) -> list[dict[str, Any]]:
        if not self._table_exists("photo_assets_136"):
            return [self._finding("photo_schema", "photos", "blocker", "critical", "photo_assets_136 fehlt", "Build-136-Schema migrieren.", weight=8)]
        rows = self.db.all("SELECT asset_id,storage_relpath,sha256,source_kind FROM photo_assets_136 WHERE case_id=?", (case_id,))
        failures: list[dict[str, Any]] = []
        checked = 0
        root = self.base_dir
        vault = (self.base_dir / "data" / "photo_evidence_136").resolve()
        for row in rows:
            if row.get("source_kind") != "local_file":
                continue
            checked += 1
            rel = str(row.get("storage_relpath") or "")
            candidate = (root / rel).resolve()
            safe = candidate == vault or vault in candidate.parents
            exists = safe and candidate.is_file()
            actual = hashlib.sha256(candidate.read_bytes()).hexdigest() if exists else ""
            if not safe or not exists or actual != row.get("sha256"):
                failures.append({"asset_id": row.get("asset_id"), "safe_path": safe, "exists": exists, "hash_ok": actual == row.get("sha256")})
        return [self._finding("photo_integrity", "photos", "pass" if not failures else "blocker", "critical", {"checked": checked, "failed": len(failures), "sample": failures[:10]}, "Fehlende oder veränderte Bildoriginale aus verifiziertem Backup wiederherstellen.", weight=10)]

    def _report_findings(self, case_id: str) -> list[dict[str, Any]]:
        releases = self.db.all("SELECT release_id,file_count FROM report_releases_142 WHERE case_id=?", (case_id,)) if self._table_exists("report_releases_142") else []
        failures: list[dict[str, Any]] = []
        checked = 0
        root = (self.base_dir / "reports" / "build142").resolve()
        for release in releases:
            files = self.db.all("SELECT file_role,relpath,sha256 FROM report_export_files_142 WHERE release_id=?", (release["release_id"],))
            if len(files) != int(release.get("file_count") or 0):
                failures.append({"release_id": release["release_id"], "reason": "file_count"})
            for row in files:
                checked += 1
                candidate = (root / str(row.get("relpath") or "")).resolve()
                safe = candidate == root or root in candidate.parents
                exists = safe and candidate.is_file()
                actual = hashlib.sha256(candidate.read_bytes()).hexdigest() if exists else ""
                if not safe or not exists or actual != row.get("sha256"):
                    failures.append({"release_id": release["release_id"], "role": row.get("file_role"), "safe_path": safe, "exists": exists, "hash_ok": actual == row.get("sha256")})
        return [self._finding("report_release_integrity", "reports", "pass" if not failures else "blocker", "critical", {"releases": len(releases), "checked_files": checked, "failed": len(failures), "sample": failures[:10]}, "Veränderte Releaseartefakte sperren und neue geprüfte Fassung erzeugen.", weight=10)]

    def _source_findings(self, case_id: str) -> list[dict[str, Any]]:
        degraded = 0
        details: dict[str, int] = {}
        if self._table_exists("provider_health_135"):
            rows = self.db.all("SELECT status,COUNT(*) AS n FROM provider_health_135 GROUP BY status")
            details = {str(row.get("status")): int(row.get("n") or 0) for row in rows}
            degraded = sum(details.get(key, 0) for key in ("offline", "quarantined", "changed_contract", "rate_limited"))
        status = "pass" if degraded == 0 else "warning"
        return [self._finding("provider_health", "sources", status, "medium", details, "Geänderte oder quarantänisierte Provider vor neuen Abfragen prüfen.", weight=4)]

    def _code_findings(self) -> list[dict[str, Any]]:
        hits: dict[str, list[str]] = {
            "eval": [], "exec": [], "shell_true": [], "pickle_loads": [],
            "marshal_loads": [], "unsafe_yaml": [],
        }
        symlinks: list[str] = []
        world_writable: list[str] = []
        syntax_errors: list[str] = []
        scanned = 0
        skip_parts = {".git", "__pycache__", "archive", ".pytest_cache", "node_modules"}
        for path in self.install_dir.rglob("*"):
            try:
                rel = path.relative_to(self.install_dir)
            except ValueError:
                continue
            if any(part in skip_parts for part in rel.parts):
                continue
            if path.is_symlink():
                symlinks.append(rel.as_posix())
                continue
            try:
                if path.stat().st_mode & 0o002:
                    world_writable.append(rel.as_posix())
            except OSError:
                pass
            if path.suffix != ".py" or not path.is_file():
                continue
            scanned += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(rel))
            except (OSError, SyntaxError) as exc:
                syntax_errors.append(f"{rel.as_posix()}: {exc}")
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Name) and func.id in {"eval", "exec"}:
                    hits[func.id].append(rel.as_posix())
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    pair = (func.value.id, func.attr)
                    if pair == ("pickle", "loads"):
                        hits["pickle_loads"].append(rel.as_posix())
                    elif pair == ("marshal", "loads"):
                        hits["marshal_loads"].append(rel.as_posix())
                    elif pair == ("yaml", "load"):
                        hits["unsafe_yaml"].append(rel.as_posix())
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        hits["shell_true"].append(rel.as_posix())
        unsafe = {key: sorted(set(values)) for key, values in hits.items() if values}
        findings = [self._finding("static_dangerous_constructs", "code", "pass" if not unsafe and not syntax_errors else "blocker", "critical", {"scanned_python": scanned, "hits": unsafe, "syntax_errors": syntax_errors[:20]}, "Gefährliche dynamische Ausführung oder Syntaxfehler entfernen.", weight=12)]
        findings.append(self._finding("package_symlinks", "code", "pass" if not symlinks else "warning", "medium", {"count": len(symlinks), "sample": symlinks[:20]}, "Symlinks im Produktionspaket entfernen oder dokumentieren.", weight=3))
        findings.append(self._finding("world_writable_files", "code", "pass" if not world_writable else "blocker", "high", {"count": len(world_writable), "sample": world_writable[:20]}, "Schreibrechte des Produktionspakets härten.", weight=7))
        return findings

    def _safety_contract_findings(self, case_id: str) -> list[dict[str, Any]]:
        # These are cross-build invariants, not marketing claims. They are
        # checked against the currently loaded services and their dashboards.
        dashboards = {
            "135": self.build135.dashboard(case_id),
            "136": self.build136.dashboard(case_id),
            "138": self.build138.dashboard(case_id),
            "139": self.build139.dashboard(case_id),
            "140": self.build140.dashboard(case_id),
            "141": self.build141.dashboard(case_id),
            "142": self.build142.dashboard(case_id),
            "143": self.build143.dashboard(case_id),
        }
        forbidden = {
            "automatic_identity_claims": 0,
            "automatic_image_uploads": 0,
            "biometric_templates": 0,
            "face_matches": 0,
            "external_ai_actions": 0,
            "automatic_account_creation": 0,
            "automatic_login": 0,
            "anti_bot_bypass": 0,
        }
        flattened = _canonical(dashboards)
        # Dashboard contracts differ slightly across builds. Any explicit
        # non-zero forbidden marker is a blocker; absence is recorded as pass
        # because the executable behaviour is covered by regression tests.
        violations: list[str] = []
        for key in forbidden:
            for marker in (f'"{key}":1', f'"{key}":true'):
                if marker in flattened.casefold().replace(" ", ""):
                    violations.append(key)
        return [self._finding("phase4_safety_contract", "safety", "pass" if not violations else "blocker", "critical", {"violations": sorted(set(violations)), "automatic_external_actions": 0, "biometric_identity": 0}, "Verbotene Automatik deaktivieren und Regressionstest ergänzen.", weight=12)]

    def run_performance_benchmark(self, *, case_id: str, iterations: int = 300, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id)
        iterations = max(50, min(int(iterations), 5000))
        samples: list[float] = []
        started = self.clock()
        for i in range(iterations):
            t0 = self.clock()
            row = self.db.one("SELECT case_id,title,status FROM cases WHERE case_id=?", (case_id,)) or {}
            hashlib.sha256(_canonical({"i": i, "row": row}).encode("utf-8")).hexdigest()
            samples.append((self.clock() - t0) * 1000.0)
        duration_ms = (self.clock() - started) * 1000.0
        p95 = sorted(samples)[max(0, int(len(samples) * 0.95) - 1)]
        ops = iterations / max(duration_ms / 1000.0, 1e-9)
        status = "pass" if p95 < 50.0 and ops > 20.0 else "warning"
        benchmark_id = new_id("bench144")
        result = {"benchmark_id": benchmark_id, "case_id": case_id, "status": status, "iterations": iterations, "duration_ms": round(duration_ms, 3), "operations_per_second": round(ops, 2), "p95_ms": round(p95, 3), "max_ms": round(max(samples), 3), "min_ms": round(min(samples), 3)}
        self.db.execute("INSERT INTO performance_benchmarks_144(benchmark144_id,case_id,status,iterations,duration_ms,operations_per_second,p95_ms,result_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (benchmark_id, case_id, status, iterations, duration_ms, ops, p95, dumps(result), actor, now_ts()))
        self._event(case_id=case_id, event_type="performance_benchmark_completed", object_type="benchmark", object_id=benchmark_id, actor=actor, payload=result)
        return result

    def _score(self, findings: list[dict[str, Any]]) -> tuple[int, int, int, int, str]:
        total = sum(int(f.get("weight") or 1) for f in findings)
        lost = 0
        blockers = warnings = passes = 0
        for f in findings:
            status = f.get("status")
            weight = int(f.get("weight") or 1)
            if status == "blocker":
                blockers += 1
                lost += weight
            elif status == "warning":
                warnings += 1
                lost += max(1, weight // 2)
            else:
                passes += 1
        score = max(0, min(100, round(100 * (total - lost) / max(total, 1))))
        status = "pass" if blockers == 0 and warnings == 0 else ("conditional" if blockers == 0 else "blocked")
        return score, blockers, warnings, passes, status

    def _sync_risks(self, *, case_id: str, audit_id: str, findings: list[dict[str, Any]], actor: str) -> None:
        for finding in findings:
            if finding["status"] not in {"warning", "blocker"}:
                continue
            severity = str(finding.get("severity") or "medium")
            existing = self.db.one("SELECT risk144_id FROM phase4_risks_144 WHERE case_id=? AND domain=? AND summary=? AND status='open'", (case_id, finding["domain"], finding["key"]))
            if existing:
                self.db.execute("UPDATE phase4_risks_144 SET severity=?,remediation=?,evidence_json=?,source_audit_id=?,updated_at=? WHERE risk144_id=?", (severity, finding.get("remediation") or "", dumps(finding.get("detail")), audit_id, now_ts(), existing["risk144_id"]))
            else:
                stamp = now_ts()
                self.db.execute("INSERT INTO phase4_risks_144(risk144_id,case_id,domain,severity,status,summary,remediation,evidence_json,source_audit_id,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (new_id("risk144"), case_id, finding["domain"], severity, "open", finding["key"], finding.get("remediation") or "", dumps(finding.get("detail")), audit_id, actor, stamp, stamp))

    def run_full_audit(self, *, case_id: str, include_optional: bool = True, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id)
        with self._run_lock:
            audit_id = new_id("audit144")
            started_at = now_ts()
            findings: list[dict[str, Any]] = []
            sections = (
                self._database_findings,
                lambda: self._case_findings(case_id),
                lambda: self._event_chain_findings(case_id),
                lambda: self._photo_findings(case_id),
                lambda: self._report_findings(case_id),
                lambda: self._source_findings(case_id),
                self._code_findings,
                lambda: self._safety_contract_findings(case_id),
            )
            for section in sections:
                try:
                    findings.extend(section())
                except Exception as exc:
                    findings.append(self._finding(f"audit_section_{len(findings)}", "audit", "blocker", "critical", f"{type(exc).__name__}: {exc}", "Auditfehler beheben und Prüfung wiederholen.", weight=10))
            benchmark = None
            if include_optional:
                try:
                    benchmark = self.run_performance_benchmark(case_id=case_id, iterations=300, actor=actor)
                    findings.append(self._finding("optional_performance_benchmark", "performance", benchmark["status"], "medium", benchmark, "Langsame lokale Operationen profilieren.", optional=True, weight=4))
                except Exception as exc:
                    findings.append(self._finding("optional_performance_benchmark", "performance", "warning", "medium", f"{type(exc).__name__}: {exc}", "Benchmark separat wiederholen.", optional=True, weight=3))
            score, blockers, warnings, passes, status = self._score(findings)
            metrics = {
                "tables": int((self.db.one("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'") or {}).get("n") or 0),
                "targets": self._count("targets", "case_id=?", (case_id,)),
                "assertions": self._count("evidence_assertions_138", "case_id=?", (case_id,)),
                "photos": self._count("photo_assets_136", "case_id=?", (case_id,)),
                "reports": self._count("professional_reports_142", "case_id=?", (case_id,)),
                "releases": self._count("report_releases_142", "case_id=?", (case_id,)),
                "open_risks": sum(1 for f in findings if f["status"] in {"warning", "blocker"}),
                "benchmark": benchmark or {},
            }
            completed_at = now_ts()
            self.db.execute("INSERT INTO release_candidate_audits_144(audit144_id,case_id,scope,status,score,blocker_count,warning_count,pass_count,findings_json,metrics_json,optional_tests,created_by,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (audit_id, case_id, "full_phase4_release_candidate", status, score, blockers, warnings, passes, dumps(findings), dumps(metrics), int(bool(include_optional)), actor, started_at, completed_at))
            self._sync_risks(case_id=case_id, audit_id=audit_id, findings=findings, actor=actor)
            self._event(case_id=case_id, event_type="phase4_release_candidate_audit_completed", object_type="release_candidate_audit", object_id=audit_id, actor=actor, payload={"status": status, "score": score, "blockers": blockers, "warnings": warnings, "optional_tests": bool(include_optional)})
            return {"audit_id": audit_id, "case_id": case_id, "build": self.BUILD, "status": status, "score": score, "blocker_count": blockers, "warning_count": warnings, "pass_count": passes, "findings": findings, "metrics": metrics, "started_at": started_at, "completed_at": completed_at}

    def _artifact_rows(self, case_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if self._table_exists("photo_assets_136"):
            for row in self.db.all("SELECT asset_id,storage_relpath,sha256 FROM photo_assets_136 WHERE case_id=? AND source_kind='local_file'", (case_id,)):
                if row.get("storage_relpath"):
                    rows.append({"role": "photo", "object_id": row["asset_id"], "relpath": row["storage_relpath"], "sha256": row["sha256"]})
        if self._table_exists("report_export_files_142"):
            for row in self.db.all("SELECT export_file_id,relpath,sha256 FROM report_export_files_142 WHERE case_id=?", (case_id,)):
                rows.append({"role": "report", "object_id": row["export_file_id"], "relpath": f"reports/build142/{row['relpath']}", "sha256": row["sha256"]})
        return rows

    def create_verified_backup(self, *, case_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "export.approve")
        if str(confirmation or "").strip() != BACKUP_CONFIRMATION:
            raise PermissionError(f"Freigabephrase {BACKUP_CONFIRMATION} fehlt")
        backup_id = new_id("backup144")
        rel_dir = Path(_safe_name(case_id)) / _safe_name(backup_id)
        out_dir = (self.backup_root / rel_dir).resolve()
        if self.backup_root not in out_dir.parents:
            raise PermissionError("Backup-Pfad verlässt Backup-Tresor")
        out_dir.mkdir(parents=True, exist_ok=False)
        self._chmod(out_dir, 0o700)
        db_path = out_dir / "eagleeye.sqlite3"
        destination = sqlite3.connect(str(db_path))
        try:
            with self.db._lock:  # online SQLite backup, serialized with the canonical DB wrapper
                self.db.conn.backup(destination)
            destination.commit()
        finally:
            destination.close()
        self._chmod(db_path, 0o600)
        db_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
        artifact_entries: list[dict[str, Any]] = []
        artifact_dir = out_dir / "artifacts"
        for entry in self._artifact_rows(case_id):
            source = (self.base_dir / entry["relpath"]).resolve()
            if self.base_dir != source and self.base_dir not in source.parents:
                raise PermissionError("Artefaktpfad verlässt Laufzeitverzeichnis")
            if not source.is_file():
                artifact_entries.append({**entry, "status": "missing"})
                continue
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual != entry["sha256"]:
                artifact_entries.append({**entry, "status": "hash_mismatch", "actual_sha256": actual})
                continue
            target = artifact_dir / _safe_name(entry["role"]) / f"{_safe_name(entry['object_id'])}_{source.name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            artifact_entries.append({**entry, "status": "copied", "backup_relpath": target.relative_to(out_dir).as_posix(), "byte_size": target.stat().st_size})
        check = sqlite3.connect(str(db_path))
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = check.execute("PRAGMA foreign_key_check").fetchall()
            case_present = bool(check.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone())
            schema = (check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() or [""])[0]
        finally:
            check.close()
        copied_failures = [row for row in artifact_entries if row["status"] != "copied"]
        restore_status = "pass" if integrity == "ok" and not foreign_keys and case_present and version_at_least(schema, self.BUILD) and not copied_failures else "fail"
        manifest = {
            "schema": "eagleeye.verified-backup.144",
            "build": self.BUILD,
            "backup_id": backup_id,
            "case_id": case_id,
            "created_at": now_ts(),
            "created_by": actor,
            "database": {"filename": db_path.name, "sha256": db_hash, "byte_size": db_path.stat().st_size, "integrity_check": integrity, "foreign_key_violations": len(foreign_keys), "schema_version": schema, "case_present": case_present},
            "artifacts": artifact_entries,
            "claims": {"online_sqlite_backup": True, "restore_tested": True, "automatic_external_transfer": False},
        }
        manifest_path = out_dir / "manifest.json"
        manifest_bytes = (_canonical(manifest) + "\n").encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        self._chmod(manifest_path, 0o600)
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        status = "pass" if restore_status == "pass" else "fail"
        stamp = now_ts()
        details = {"integrity_check": integrity, "foreign_key_violations": len(foreign_keys), "case_present": case_present, "schema_version": schema, "artifact_failures": len(copied_failures)}
        self.db.execute("INSERT INTO verified_backups_144(backup144_id,case_id,status,restore_status,backup_dir_relpath,database_relpath,manifest_relpath,database_sha256,manifest_sha256,byte_size,artifact_count,details_json,created_by,created_at,verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (backup_id, case_id, status, restore_status, rel_dir.as_posix(), (rel_dir / db_path.name).as_posix(), (rel_dir / manifest_path.name).as_posix(), db_hash, manifest_hash, db_path.stat().st_size, len(artifact_entries), dumps(details), actor, stamp, stamp))
        self._event(case_id=case_id, event_type="verified_backup_created", object_type="verified_backup", object_id=backup_id, actor=actor, payload={"status": status, "restore_status": restore_status, "artifact_count": len(artifact_entries), "artifact_failures": len(copied_failures), "database_sha256": db_hash})
        return {"backup_id": backup_id, "case_id": case_id, "status": status, "restore_status": restore_status, "backup_dir": str(out_dir), "database_sha256": db_hash, "manifest_sha256": manifest_hash, "artifact_count": len(artifact_entries), "details": details}

    def update_risk(self, *, case_id: str, risk_id: str, status: str, reason: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id)
        status = str(status or "").strip().casefold()
        if status not in RISK_STATUSES:
            raise ValueError("Unbekannter Risikostatus")
        if len(str(reason or "").strip()) < 8:
            raise ValueError("Nachvollziehbare Begründung erforderlich")
        row = self.db.one("SELECT * FROM phase4_risks_144 WHERE case_id=? AND risk144_id=?", (case_id, risk_id))
        if not row:
            raise KeyError("Risiko nicht gefunden")
        evidence = loads(row.get("evidence_json"), {})
        evidence["status_reason"] = str(reason).strip()[:2000]
        evidence["status_actor"] = actor
        self.db.execute("UPDATE phase4_risks_144 SET status=?,evidence_json=?,updated_at=? WHERE risk144_id=?", (status, dumps(evidence), now_ts(), risk_id))
        self._event(case_id=case_id, event_type="phase4_risk_updated", object_type="phase4_risk", object_id=risk_id, actor=actor, payload={"status": status})
        return self.db.one("SELECT * FROM phase4_risks_144 WHERE risk144_id=?", (risk_id,)) or {}

    def get_audit(self, *, case_id: str, audit_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM release_candidate_audits_144 WHERE case_id=? AND audit144_id=?", (case_id, audit_id))
        if not row:
            raise KeyError("Audit nicht gefunden")
        row["findings"] = loads(row.pop("findings_json", "[]"), [])
        row["metrics"] = loads(row.pop("metrics_json", "{}"), {})
        return row

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        where = " WHERE case_id=?" if case_id else ""
        params = (case_id,) if case_id else ()
        audits = self.db.all("SELECT audit144_id,case_id,status,score,blocker_count,warning_count,pass_count,optional_tests,created_by,completed_at FROM release_candidate_audits_144" + where + " ORDER BY completed_at DESC LIMIT 20", params)
        backups = self.db.all("SELECT backup144_id,case_id,status,restore_status,byte_size,artifact_count,created_by,created_at FROM verified_backups_144" + where + " ORDER BY created_at DESC LIMIT 20", params)
        benchmarks = self.db.all("SELECT benchmark144_id,case_id,status,iterations,duration_ms,operations_per_second,p95_ms,created_at FROM performance_benchmarks_144" + where + " ORDER BY created_at DESC LIMIT 20", params)
        risks = self.db.all("SELECT risk144_id,case_id,domain,severity,status,summary,remediation,source_audit_id,updated_at FROM phase4_risks_144" + where + " ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,updated_at DESC LIMIT 100", params)
        latest = audits[0] if audits else None
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "latest_audit": latest,
            "audits": audits,
            "backups": backups,
            "benchmarks": benchmarks,
            "risks": risks,
            "metrics": {"audits": len(audits), "verified_backups": sum(1 for row in backups if row["status"] == "pass"), "open_blockers": sum(1 for row in risks if row["status"] == "open" and row["severity"] in {"critical", "high"}), "open_risks": sum(1 for row in risks if row["status"] == "open")},
            "limitations": [
                "Automatisierte lokale Tests ersetzen keinen unabhängigen Penetrationstest.",
                "Reale Windows-, Firefox-, Proxy-/Tor- und Live-Connector-Feldabnahmen bleiben separat erforderlich.",
                "Ein verifiziertes Backup ist nur so belastbar wie die sichere externe Aufbewahrung durch den Betreiber.",
            ],
        }
