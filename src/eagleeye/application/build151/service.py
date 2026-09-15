from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

VALID_CLASSIFICATIONS = {"canonical", "legacy", "adapter", "experimental", "deprecated"}
BUILD151_CONFIRMATION = "ARCHITEKTURBASELINE 151 ERSTELLEN"


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class Build151ArchitectureReliabilityService:
    BUILD = "151.0"
    OVERSIZED_LINES = 1200

    def __init__(self, db: Any, audit: Any, base_dir: str | Path, *, registry: Any) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.registry = registry
        self._inventory_cache: dict[str, Any] | None = None

    def _repo_root(self) -> Path:
        candidates = [self.base_dir, Path(__file__).resolve().parents[4]]
        for candidate in candidates:
            if (candidate / "pyproject.toml").exists():
                return candidate
        return Path(__file__).resolve().parents[4]

    @staticmethod
    def _classification(relative: str) -> str:
        value = relative.replace("\\", "/")
        if value.startswith("eagleeye_pro/"):
            return "legacy"
        if "/build" in value and re.search(r"/build\d+", value):
            return "adapter"
        if any(token in value.casefold() for token in ("experimental", "prototype", "sandbox")):
            return "experimental"
        return "canonical"

    @staticmethod
    def _silent_exception_lines(path: Path) -> list[int]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            # AST parsing is expensive across several hundred modules. Only parse
            # files that can actually contain a silent handler.
            if "except" not in text or ("pass" not in text and "..." not in text):
                return []
            tree = ast.parse(text)
        except (SyntaxError, OSError):
            return []
        lines: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not node.body:
                continue
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                lines.append(node.lineno)
            elif all(isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and item.value.value is Ellipsis for item in body):
                lines.append(node.lineno)
        return lines

    def inventory(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._inventory_cache is not None and not refresh:
            return json.loads(json.dumps(self._inventory_cache))
        root = self._repo_root()
        modules: list[dict[str, Any]] = []
        counts = {key: 0 for key in VALID_CLASSIFICATIONS}
        silent_total = 0
        total_lines = 0
        for source_root in (root / "src", root / "eagleeye_pro"):
            if not source_root.exists():
                continue
            for path in sorted(source_root.rglob("*.py")):
                relative = path.relative_to(root).as_posix()
                text = path.read_text(encoding="utf-8", errors="replace")
                line_count = len(text.splitlines())
                silent = self._silent_exception_lines(path)
                classification = self._classification(relative)
                counts[classification] += 1
                silent_total += len(silent)
                total_lines += line_count
                modules.append({
                    "path": relative,
                    "classification": classification,
                    "lines": line_count,
                    "oversized": line_count >= self.OVERSIZED_LINES,
                    "silent_exception_lines": silent,
                })
        result = {
            "build": self.BUILD,
            "repository_root": str(root),
            "python_file_count": len(modules),
            "module_count": len(modules),
            "python_lines": total_lines,
            "classifications": counts,
            "silent_exception_count": silent_total,
            "oversized_module_count": sum(1 for item in modules if item["oversized"]),
            "modules": modules,
        }
        self._inventory_cache = result
        return json.loads(json.dumps(result))

    def save_architecture_snapshot(self, *, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation != BUILD151_CONFIRMATION:
            raise PermissionError("Explizite Bestätigung für die Architektur-Baseline fehlt")
        payload = self.inventory()
        snapshot_id = new_id("arch151")
        created = now_ts()
        counts = payload["classifications"]
        digest = _digest(payload)
        self.db.execute(
            "INSERT INTO architecture_snapshots_151(snapshot_id,created_at,actor,repository_root,module_count,python_file_count,python_lines,canonical_count,legacy_count,adapter_count,experimental_count,deprecated_count,silent_exception_count,oversized_module_count,payload_json,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snapshot_id, created, actor, payload["repository_root"], payload["module_count"], payload["python_file_count"], payload["python_lines"], counts["canonical"], counts["legacy"], counts["adapter"], counts["experimental"], counts["deprecated"], payload["silent_exception_count"], payload["oversized_module_count"], dumps(payload), digest),
        )
        self.audit.log("architecture_snapshot_151", "architecture", snapshot_id, None, {"sha256": digest, "module_count": payload["module_count"]})
        return {**payload, "snapshot_id": snapshot_id, "created_at": created, "payload_sha256": digest}

    def record_decision(self, *, module_pattern: str, classification: str, canonical_target: str = "", rationale: str = "", actor: str) -> dict[str, Any]:
        classification = classification.strip().casefold()
        if classification not in VALID_CLASSIFICATIONS:
            raise ValueError("Ungültige Architekturklassifikation")
        pattern = module_pattern.strip().replace("\\", "/")
        if not pattern or ".." in pattern:
            raise ValueError("Ungültiges Modul-Muster")
        now = now_ts()
        existing = self.db.one("SELECT decision_id,created_at FROM architecture_decisions_151 WHERE module_pattern=?", (pattern,))
        decision_id = (existing or {}).get("decision_id") or new_id("decision151")
        created = (existing or {}).get("created_at") or now
        self.db.execute("INSERT OR REPLACE INTO architecture_decisions_151(decision_id,module_pattern,classification,canonical_target,rationale,status,created_at,updated_at) VALUES(?,?,?,?,?,'active',?,?)", (decision_id, pattern, classification, canonical_target.strip(), rationale.strip(), created, now))
        self.audit.log("architecture_decision_151", "architecture_decision", decision_id, None, {"pattern": pattern, "classification": classification, "actor": actor})
        return self.db.one("SELECT * FROM architecture_decisions_151 WHERE decision_id=?", (decision_id,))

    def reliability_baseline(self, *, actor: str = "system") -> dict[str, Any]:
        started = time.perf_counter()
        threads = threading.enumerate()
        descriptors = self.registry.descriptors()
        payload = {
            "build": self.BUILD,
            "registered_services": len(descriptors),
            "initialized_services": len(self.registry.initialized_names()),
            "active_threads": len(threads),
            "non_daemon_threads": [thread.name for thread in threads if thread.is_alive() and not thread.daemon],
            "service_groups": {},
            "service_statuses": {},
            "db_in_transaction": bool(getattr(self.db.conn, "in_transaction", False)),
            "process_rss_bytes": self._rss_bytes(),
        }
        for descriptor in descriptors:
            payload["service_groups"][descriptor.group] = payload["service_groups"].get(descriptor.group, 0) + 1
            payload["service_statuses"][descriptor.status] = payload["service_statuses"].get(descriptor.status, 0) + 1
        payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        baseline_id = new_id("rel151")
        created = now_ts()
        digest = _digest(payload)
        self.db.execute("INSERT INTO reliability_baselines_151(baseline_id,created_at,actor,initialized_services,registered_services,active_threads,non_daemon_threads,open_db_transaction,process_rss_bytes,elapsed_ms,payload_json,payload_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (baseline_id, created, actor, payload["initialized_services"], payload["registered_services"], payload["active_threads"], len(payload["non_daemon_threads"]), int(payload["db_in_transaction"]), payload["process_rss_bytes"], payload["elapsed_ms"], dumps(payload), digest))
        return {**payload, "baseline_id": baseline_id, "created_at": created, "payload_sha256": digest}

    @staticmethod
    def _rss_bytes() -> int:
        try:
            import resource
            value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            return value if os.name == "posix" and value > 10_000_000 else value * 1024
        except (ImportError, OSError, ValueError):
            return 0

    def dashboard(self) -> dict[str, Any]:
        latest_arch = self.db.one("SELECT * FROM architecture_snapshots_151 ORDER BY created_at DESC LIMIT 1")
        latest_rel = self.db.one("SELECT * FROM reliability_baselines_151 ORDER BY created_at DESC LIMIT 1")
        return {
            "build": self.BUILD,
            "mission": "Architecture and Reliability Baseline",
            "feature_freeze": True,
            "person_osint_core_preserved": True,
            "firefox_workflow_changed": False,
            "automatic_identity_assertions_added": 0,
            "latest_architecture_snapshot": dict(latest_arch) if latest_arch else None,
            "latest_reliability_baseline": dict(latest_rel) if latest_rel else None,
            "decisions": self.db.all("SELECT * FROM architecture_decisions_151 WHERE status='active' ORDER BY module_pattern"),
        }
