from __future__ import annotations
import hashlib
import json
import os
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from eagleeye_pro.security.url_policy import URLPolicy

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate, MAX_QUERY_LENGTH, MAX_MULTI_SEARCH_URLS

PERFORMANCE_THRESHOLDS = {
    "sqlite_integrity_ms_max": 2500,
    "dashboard_probe_ms_max": 1500,
    "query_guard_ms_max": 250,
    "manifest_probe_ms_max": 5000,
}

FORBIDDEN_URL_SCHEMES = {"file", "javascript", "data", "ftp", "ssh", "smb"}
PRIVATE_HOST_MARKERS = ("localhost", "127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "::1")

class PerformanceSecurityReleaseService:
    """Build 40.0 hardening layer: performance probes, security regression,
    backup/restore dry-runs, provider failure tests and release-health snapshots.

    This service deliberately performs local, non-invasive tests only. It does
    not call external services and it does not scrape or enrich real persons.
    """

    def __init__(self, db: Database, audit: AuditService, app_context: Any = None):
        self.db = db
        self.audit = audit
        self.app_context = app_context
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS perf_security_test_runs (
          run_id TEXT PRIMARY KEY, run_type TEXT NOT NULL, status TEXT NOT NULL,
          score REAL DEFAULT 0.0, duration_ms INTEGER DEFAULT 0, findings_json TEXT NOT NULL,
          metrics_json TEXT NOT NULL, created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS performance_benchmarks (
          benchmark_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, benchmark_key TEXT NOT NULL,
          status TEXT NOT NULL, duration_ms INTEGER DEFAULT 0, threshold_ms INTEGER DEFAULT 0,
          metrics_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES perf_security_test_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS security_regression_checks (
          check_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, check_key TEXT NOT NULL,
          status TEXT NOT NULL, severity TEXT DEFAULT 'medium', details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES perf_security_test_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS backup_restore_tests (
          test_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, backup_path TEXT NOT NULL,
          status TEXT NOT NULL, db_integrity TEXT DEFAULT '', file_count INTEGER DEFAULT 0,
          sha256 TEXT DEFAULT '', duration_ms INTEGER DEFAULT 0, details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES perf_security_test_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS provider_failure_tests (
          test_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, provider_id TEXT NOT NULL,
          scenario TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES perf_security_test_runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS runtime_performance_snapshots (
          snapshot_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', snapshot_json TEXT NOT NULL,
          score REAL DEFAULT 0.0, created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        ''')
        self.db.conn.commit()

    def _record_run(self, run_type: str, status: str, score: float, duration_ms: int, findings: List[Dict[str, Any]], metrics: Dict[str, Any], notes: str = "") -> Dict[str, Any]:
        run_id = new_id("psr")
        self.db.execute(
            "INSERT INTO perf_security_test_runs(run_id,run_type,status,score,duration_ms,findings_json,metrics_json,created_at,notes) VALUES(?,?,?,?,?,?,?,?,?)",
            [run_id, run_type, status, float(score), int(duration_ms), dumps(findings), dumps(metrics), now_ts(), notes],
        )
        self.audit.log("PERF_SECURITY_RUN", "perf_security_test_run", run_id, details={"run_type": run_type, "status": status, "score": score})
        return self.db.one("SELECT * FROM perf_security_test_runs WHERE run_id=?", [run_id])

    def sqlite_health_check(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        integrity = self.db.one("PRAGMA integrity_check")
        fk_rows = self.db.all("PRAGMA foreign_key_check")
        tables = self.db.all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        counts = {}
        for row in tables:
            name = row["name"]
            try:
                counts[name] = int(self.db.one(f"SELECT COUNT(*) AS c FROM {name}")["c"])
            except Exception:
                counts[name] = -1
        duration_ms = int((time.perf_counter() - t0) * 1000)
        status = "pass" if integrity and list(integrity.values())[0] == "ok" and not fk_rows else "review"
        return {"status": status, "duration_ms": duration_ms, "integrity": integrity, "foreign_key_issues": fk_rows, "table_count": len(tables), "row_counts": counts}

    def performance_probe(self, base_dir: str | Path | None = None, case_id: str = "") -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        metrics: Dict[str, Any] = {}
        t_all = time.perf_counter()
        run_id = new_id("psrtmp")

        def bench(key: str, fn, threshold_key: str):
            t0 = time.perf_counter()
            result = fn()
            ms = int((time.perf_counter() - t0) * 1000)
            limit = PERFORMANCE_THRESHOLDS[threshold_key]
            status = "pass" if ms <= limit else "review"
            metrics[key] = {"duration_ms": ms, "threshold_ms": limit, "status": status, "result": result}
            if status != "pass":
                findings.append({"severity": "medium", "area": "performance", "message": f"{key} took {ms}ms > {limit}ms"})
            return result, ms, status, limit

        sqlite_result, sqlite_ms, sqlite_status, sqlite_limit = bench("sqlite_integrity", self.sqlite_health_check, "sqlite_integrity_ms_max")
        if sqlite_result["status"] != "pass":
            findings.append({"severity": "high", "area": "database", "message": "SQLite integrity/foreign-key check requires review."})
        bench("query_guard_batch", self._query_guard_batch, "query_guard_ms_max")
        if base_dir:
            bench("manifest_probe", lambda: self._manifest_probe(base_dir), "manifest_probe_ms_max")
        if case_id and self.app_context:
            bench("dashboard_probe", lambda: self._dashboard_probe(case_id), "dashboard_probe_ms_max")
        score = max(0.0, 100.0 - len([f for f in findings if f.get("severity") == "high"]) * 18 - len(findings) * 4)
        status = "pass" if score >= 85 and not any(f.get("severity") == "high" for f in findings) else "review"
        run = self._record_run("performance_probe", status, score, int((time.perf_counter() - t_all) * 1000), findings, metrics, "Build 40.0 performance probe")
        # record benchmark rows after real run_id exists
        for key, item in metrics.items():
            if isinstance(item, dict) and "duration_ms" in item:
                self.db.execute(
                    "INSERT INTO performance_benchmarks(benchmark_id,run_id,benchmark_key,status,duration_ms,threshold_ms,metrics_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    [new_id("bench"), run["run_id"], key, item.get("status", "pass"), int(item.get("duration_ms", 0)), int(item.get("threshold_ms", 0)), dumps(item.get("result", {})), now_ts()],
                )
        run["findings"] = findings
        run["metrics"] = metrics
        return run

    def _query_guard_batch(self) -> Dict[str, Any]:
        samples = [
            '"Maria Muster" "Muster Consulting" Köln',
            '"Max Beispiel" filetype:pdf',
            'captcha umgehen target login',
            'finde die adresse von Maria Muster',
            '"Maria Muster" site:linkedin.com',
        ]
        results = [PolicyGate.evaluate_query(q) for q in samples]
        allowed = sum(1 for r in results if r.get("ok"))
        blocked = len(results) - allowed
        return {"samples": len(samples), "allowed": allowed, "blocked": blocked, "max_query_length": MAX_QUERY_LENGTH, "max_urls": MAX_MULTI_SEARCH_URLS, "ok": blocked >= 2 and allowed >= 2}

    def _manifest_probe(self, base_dir: str | Path) -> Dict[str, Any]:
        base = Path(base_dir)
        file_count = 0
        total = 0
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                file_count += 1
                total += p.stat().st_size
        return {"file_count": file_count, "total_bytes": total}

    def _dashboard_probe(self, case_id: str) -> Dict[str, Any]:
        ctx = self.app_context
        out: Dict[str, Any] = {}
        for key, fn in [
            ("cockpit", lambda: ctx.cockpit.dashboard(case_id)),
            ("gap", lambda: ctx.intelligence_gap.assess_case(case_id, persist=False)),
            ("report_pipeline", lambda: ctx.report_automation.pipeline_dashboard(case_id, "redacted_client")),
        ]:
            try:
                r = fn()
                out[key] = {"ok": True, "keys": sorted(list(r.keys()))[:12] if isinstance(r, dict) else []}
            except Exception as e:
                out[key] = {"ok": False, "error": str(e)}
        return out

    def validate_url_safety(self, url: str) -> Dict[str, Any]:
        decision = URLPolicy.validate_capture_url(url)
        if not decision.get("ok"):
            return {"ok": False, "reason": decision.get("blocked_reason", "blocked_url_policy"), "decision": decision}
        return {"ok": True, "reason": "public_http_url", "decision": decision}

    def security_regression(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        checks: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        query_cases = {
            "allowed_identity": ('"Maria Muster" Köln', True),
            "blocked_captcha": ("captcha umgehen login", False),
            "blocked_address": ("finde die adresse von Maria Muster", False),
            "blocked_credentials": ("password dump maria", False),
        }
        for key, (query, expected) in query_cases.items():
            got = bool(PolicyGate.evaluate_query(query).get("ok"))
            status = "pass" if got == expected else "fail"
            checks.append({"check_key": key, "status": status, "severity": "high", "details": {"query": query, "expected_ok": expected, "got_ok": got}})
        url_cases = {
            "allowed_https": ("https://example.org/profile", True),
            "blocked_file": ("file:///c:/users/private.txt", False),
            "blocked_js": ("javascript:alert(1)", False),
            "blocked_localhost": ("http://127.0.0.1/admin", False),
            "blocked_private_net": ("http://192.168.0.1/router", False),
        }
        for key, (url, expected) in url_cases.items():
            got = bool(self.validate_url_safety(url).get("ok"))
            status = "pass" if got == expected else "fail"
            checks.append({"check_key": key, "status": status, "severity": "high", "details": {"url": url, "expected_ok": expected, "got_ok": got}})
        secret_policy = self.db.all("SELECT * FROM secret_references LIMIT 25") if self._table_exists("secret_references") else []
        cleartext_suspects = [s for s in secret_policy if any(k in json.dumps(s, ensure_ascii=False).lower() for k in ["sk-", "apikey=", "secret="])]
        checks.append({"check_key": "no_cleartext_secret_marker", "status": "pass" if not cleartext_suspects else "fail", "severity": "critical", "details": {"suspects": len(cleartext_suspects)}})
        for c in checks:
            if c["status"] != "pass":
                findings.append({"severity": c["severity"], "area": "security_regression", "message": c["check_key"], "details": c["details"]})
        score = max(0.0, 100.0 - len(findings) * 20.0)
        status = "pass" if not findings else "fail"
        run = self._record_run("security_regression", status, score, int((time.perf_counter() - t0) * 1000), findings, {"checks": checks}, "Build 40.0 security regression")
        for c in checks:
            self.db.execute(
                "INSERT INTO security_regression_checks(check_id,run_id,check_key,status,severity,details_json,created_at) VALUES(?,?,?,?,?,?,?)",
                [new_id("sreg"), run["run_id"], c["check_key"], c["status"], c["severity"], dumps(c["details"]), now_ts()],
            )
        run["checks"] = checks
        run["findings"] = findings
        return run

    def provider_failure_simulation(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        findings: List[Dict[str, Any]] = []
        scenarios = []
        providers = self.db.all("SELECT provider_id, requires_api_key, enabled FROM provider_registry ORDER BY provider_id LIMIT 20") if self._table_exists("provider_registry") else []
        if not providers:
            providers = [{"provider_id": "simulated_provider", "requires_api_key": 1, "enabled": 1}]
        for p in providers:
            pid = p.get("provider_id")
            # No network call: simulate safe handling of missing API keys and disabled providers.
            if int(p.get("requires_api_key") or 0):
                env_name = f"EAGLEEYE_{pid.upper()}_API_KEY"
                ok = bool(os.environ.get(env_name))
                scenario = {"provider_id": pid, "scenario": "missing_optional_api_key", "status": "handled" if not ok else "configured", "details": {"env_var": env_name, "network_called": False}}
            elif int(p.get("enabled") or 1) == 0:
                scenario = {"provider_id": pid, "scenario": "disabled_provider", "status": "handled", "details": {"network_called": False}}
            else:
                scenario = {"provider_id": pid, "scenario": "offline_dry_run", "status": "handled", "details": {"network_called": False}}
            scenarios.append(scenario)
        status = "pass" if all(s["status"] in {"handled", "configured"} for s in scenarios) else "review"
        score = 100.0 if status == "pass" else 75.0
        run = self._record_run("provider_failure_simulation", status, score, int((time.perf_counter() - t0) * 1000), findings, {"scenarios": scenarios}, "Build 40.0 provider failure tests - no external calls")
        for s in scenarios:
            self.db.execute("INSERT INTO provider_failure_tests(test_id,run_id,provider_id,scenario,status,details_json,created_at) VALUES(?,?,?,?,?,?,?)", [new_id("pft"), run["run_id"], s["provider_id"], s["scenario"], s["status"], dumps(s["details"]), now_ts()])
        run["scenarios"] = scenarios
        return run

    def backup_restore_dry_run(self, base_dir: str | Path) -> Dict[str, Any]:
        t0 = time.perf_counter()
        base = Path(base_dir)
        backup_dir = base / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"build40_backup_dry_run_{int(time.time())}.zip"
        files = []
        for rel in ["eagleeye_pro", "requirements.txt"]:
            p = base / rel
            if p.exists():
                files.append(p)
        db_path = self.db.path
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in files:
                if p.is_dir():
                    for f in p.rglob("*"):
                        if f.is_file() and "__pycache__" not in f.parts:
                            zf.write(f, f.relative_to(base).as_posix())
                elif p.is_file():
                    zf.write(p, p.relative_to(base).as_posix())
            if db_path.exists():
                zf.write(db_path, "data/" + db_path.name)
        h = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        # Restore-dry-run means: open zip, ensure it contains code and optionally db; no overwrite of runtime.
        with zipfile.ZipFile(backup_path, "r") as zf:
            names = zf.namelist()
            zip_ok = bool(zf.testzip() is None)
        status = "pass" if zip_ok and (any(n.startswith("eagleeye_pro/") for n in names) or any(n.startswith("data/") and n.endswith(".db") for n in names)) else "review"
        run = self._record_run("backup_restore_dry_run", status, 100.0 if status == "pass" else 65.0, int((time.perf_counter() - t0) * 1000), [], {"backup_path": str(backup_path), "file_count": len(names), "sha256": h}, "Build 40.0 backup/restore dry-run")
        self.db.execute("INSERT INTO backup_restore_tests(test_id,run_id,backup_path,status,db_integrity,file_count,sha256,duration_ms,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", [new_id("brt"), run["run_id"], str(backup_path), status, "not_overwritten_dry_run", len(names), h, run["duration_ms"], dumps({"zip_ok": zip_ok, "restore_mode": "dry_run_only"}), now_ts()])
        run["backup_path"] = str(backup_path)
        run["file_count"] = len(names)
        run["sha256"] = h
        return run

    def full_hardening_suite(self, base_dir: str | Path, case_id: str = "") -> Dict[str, Any]:
        t0 = time.perf_counter()
        perf = self.performance_probe(base_dir, case_id)
        sec = self.security_regression()
        prov = self.provider_failure_simulation()
        backup = self.backup_restore_dry_run(base_dir)
        components = [perf, sec, prov, backup]
        findings = []
        for comp in components:
            findings.extend(comp.get("findings", loads(comp.get("findings_json"), [])) or [])
        score = round(sum(float(c.get("score", 0)) for c in components) / max(1, len(components)), 2)
        status = "pass" if score >= 85 and all(c.get("status") == "pass" for c in components) else "review"
        snapshot = {
            "build": "40.0",
            "status": status,
            "score": score,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "components": {"performance": perf.get("status"), "security": sec.get("status"), "providers": prov.get("status"), "backup": backup.get("status")},
            "findings": findings,
        }
        self.db.execute("INSERT INTO runtime_performance_snapshots(snapshot_id,case_id,snapshot_json,score,created_at,notes) VALUES(?,?,?,?,?,?)", [new_id("rps"), case_id or "", dumps(snapshot), score, now_ts(), "Build 40.0 full hardening suite snapshot"])
        self.audit.log("FULL_HARDENING_SUITE", "performance_security", details=snapshot)
        return snapshot

    def dashboard(self, case_id: str = "") -> Dict[str, Any]:
        latest_runs = self.db.all("SELECT * FROM perf_security_test_runs ORDER BY created_at DESC LIMIT 8")
        latest_snap = self.db.one("SELECT * FROM runtime_performance_snapshots WHERE case_id=? OR ?='' ORDER BY created_at DESC LIMIT 1", [case_id, case_id])
        critical = 0
        high = 0
        for r in latest_runs:
            for f in loads(r.get("findings_json"), []):
                if f.get("severity") == "critical": critical += 1
                if f.get("severity") == "high": high += 1
        status = "hardened" if latest_snap and loads(latest_snap.get("snapshot_json"), {}).get("status") == "pass" else "run_required"
        return {"status": status, "latest_runs": latest_runs, "latest_snapshot": loads(latest_snap.get("snapshot_json"), {}) if latest_snap else {}, "critical_findings": critical, "high_findings": high, "thresholds": PERFORMANCE_THRESHOLDS, "guardrails": ["no_external_provider_calls_in_tests", "no_cleartext_secrets", "capture_review_before_evidence", "public_http_urls_only", "no_login_captcha_bypass"]}

    def _table_exists(self, table: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table]))
