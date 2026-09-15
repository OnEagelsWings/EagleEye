from __future__ import annotations

import ast
import hashlib
import html
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye.data_platform.backends import DataPlatformManager, POLICY_VERSION as DATA_POLICY
from eagleeye.storage.object_store import ObjectStoreCoordinator, POLICY_VERSION as OBJECT_POLICY

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class Build347DataPlatformService:
    BUILD = "347.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build346: Any,
        data_platform: DataPlatformManager,
        object_store: ObjectStoreCoordinator,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build346 = build346
        self.data_platform = data_platform
        self.object_store = object_store
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/data_platform/backends.py",
            "src/eagleeye/storage/object_store.py",
            "src/eagleeye/application/build347/service.py",
            "src/eagleeye/interfaces/web/app347.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_347_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_347_0.py",
            "tests/test_build347.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(path.read_bytes() if path.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_347_TEST_EVIDENCE.json")
        if data.get("build") == self.BUILD and data.get("result") == "pass" and data.get("code_fingerprint") == self.code_fingerprint() and isinstance(data.get("probes"), dict):
            return data
        return {}

    def _probe(self, name: str) -> bool:
        return self._test_evidence().get("probes", {}).get(name) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_347_DATA_PLATFORM.json")
        if data.get("build") != self.BUILD or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        if data.get("cases", 0) < 250 or data.get("violations") != 0 or data.get("result") != "pass":
            return {}
        return data

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def schema_metrics(self) -> dict[str, Any]:
        return self.build346.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.M)
        runtime = rb.group(1) if rb else "unknown"
        schema = rs.group(1) if rs else "unknown"
        package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "347.0.0"}

    # Build 345/346 security capabilities remain the only path for search planning.
    def register_darknet_source(self, **kwargs: Any) -> dict[str, Any]: return self.build346.register_darknet_source(**kwargs)
    def review_darknet_source(self, source_id: str, **kwargs: Any) -> dict[str, Any]: return self.build346.review_darknet_source(source_id, **kwargs)
    def create_clearnet_capsule(self, **kwargs: Any) -> dict[str, Any]: return self.build346.create_clearnet_capsule(**kwargs)
    def create_darknet_research(self, **kwargs: Any) -> dict[str, Any]: return self.build346.create_darknet_research(**kwargs)
    def preflight_request(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]: return self.build346.preflight_request(search_run_id, **kwargs)
    def inspect_content(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]: return self.build346.inspect_content(search_run_id, **kwargs)
    def close_capsule(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]: return self.build346.close_capsule(search_run_id, **kwargs)
    def list_capsules(self, **kwargs: Any) -> list[dict[str, Any]]: return self.build346.list_capsules(**kwargs)
    def decisions(self, search_run_id: str) -> list[dict[str, Any]]: return self.build346.decisions(search_run_id)
    def assessments(self, search_run_id: str) -> list[dict[str, Any]]: return self.build346.assessments(search_run_id)

    def data_platform_status(self) -> dict[str, Any]:
        return {"database": self.data_platform.status(), "object_store": self.object_store.status(), "runtime_external_backend_connections": False}

    def configure_postgres(self, dsn: str, *, backend_id: str = "postgres_team_v1", live_validate: bool = False) -> dict[str, Any]:
        return self.data_platform.register_postgres(dsn, backend_id=backend_id, live_validate=live_validate)

    def configure_s3(self, *, endpoint_url: str, bucket: str, prefix: str = "eagleeye/phase15", sse: str = "AES256", backend_id: str = "s3_team_v1") -> dict[str, Any]:
        return self.data_platform.register_s3_config(endpoint_url=endpoint_url, bucket=bucket, prefix=prefix, sse=sse, backend_id=backend_id)

    def ingest_artifact(
        self,
        *,
        case_id: str,
        content: bytes | str,
        media_type: str = "text/plain",
        search_run_id: str | None = None,
        source_id: str | None = None,
        security_state: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        return self.object_store.ingest(case_id=case_id, content=raw, media_type=media_type, search_run_id=search_run_id, source_id=source_id, security_state=security_state, provenance=provenance, actor=self.actor)

    def artifact(self, object_id: str) -> dict[str, Any]:
        return self.object_store.metadata(object_id)

    def artifact_bytes(self, object_id: str) -> bytes:
        return self.object_store.read_verified(object_id)

    def artifacts(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.object_store.list_objects(case_id=case_id, limit=limit)

    def review_artifact(self, object_id: str, *, decision: str, rationale: str, reviewer: str | None = None) -> dict[str, Any]:
        return self.object_store.review(object_id, decision=decision, rationale=rationale, reviewer=reviewer or self.actor)

    def architecture_status(self) -> dict[str, Any]:
        data_text = (self._root / "src/eagleeye/data_platform/backends.py").read_text(encoding="utf-8")
        object_text = (self._root / "src/eagleeye/storage/object_store.py").read_text(encoding="utf-8")
        return {
            "data_policy": DATA_POLICY,
            "object_store_policy": OBJECT_POLICY,
            "sqlite_portable_default": True,
            "postgresql_opt_in": True,
            "postgres_driver_available": importlib.util.find_spec("psycopg") is not None,
            "postgres_auto_connect": False,
            "postgres_credentials_persisted": False,
            "local_cas_default": True,
            "s3_compatible_opt_in": True,
            "s3_auto_connect": False,
            "external_backend_connections_opened_on_boot": 0,
            "runtime_search_network_execution": False,
            "security_policy_bypass_for_storage": False,
            "subprocess_in_new_data_modules": "subprocess" in data_text or "subprocess" in object_text,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        metrics = self.schema_metrics()
        version = self.version_status()
        arch = self.architecture_status()
        bench = bool(self._benchmark())
        fingerprint = self.code_fingerprint()
        specs = [
            ("schema_baseline_v1_347", "Schema Baseline retained", "schema", metrics["within_gate"], metrics["within_gate"], "schema", False, False),
            ("sqlite_phase15_backend_v1", "SQLite portable Phase-15 backend", "data", True, True, "sqlite", bench, False),
            ("postgresql_phase15_backend_v1", "PostgreSQL opt-in Phase-15 backend adapter", "data", True, True, "postgres_contract", bench, False),
            ("local_cas_object_store_v1", "Local content-addressed object store", "storage", True, True, "local_cas", bench, False),
            ("s3_compatible_object_store_v1", "S3/MinIO compatible object-store adapter", "storage", True, True, "s3_contract", bench, False),
            ("darknet_artifact_provenance_v1", "Darknet artifact provenance + quarantine", "darknet", True, True, "darknet_artifact", bench, False),
            ("opsec_intelligence_v2_retained_347", "OPSEC Intelligence v2 retained", "opsec", True, True, "opsec", False, False),
            ("canonical_versioning_347", "Canonical Build 347 version contract", "packaging", version["coherent"], version["coherent"], "version", False, False),
        ]
        rows = []
        for key, name, category, implemented, integrated, probe, benchmarked, externally_validated in specs:
            tested = bool(integrated and self._probe(probe))
            states = {
                "implemented": bool(implemented),
                "integrated": bool(implemented and integrated),
                "tested": tested,
                "benchmarked": bool(tested and benchmarked),
                "externally_validated": bool(tested and externally_validated),
            }
            rows.append({
                "capability_key": key,
                "display_name": name,
                "category": category,
                **states,
                "maturity": self._maturity(states),
                "required_for_baseline": key not in {"canonical_versioning_347"} or True,
                "required_for_production": True,
                "live_external_validation": "not_run" if category in {"data", "storage"} and key.startswith(("postgresql", "s3_")) else "not_applicable_or_pending",
                "code_fingerprint": fingerprint,
            })
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities()
        baseline = [r for r in rows if r["required_for_baseline"]]
        baseline_tested = bool(baseline) and all(r["tested"] for r in baseline)
        schema_gate = self.schema_metrics()["within_gate"]
        build_acceptance = baseline_tested and schema_gate
        production = bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build347_data_platform_evidence_gate",
            "build_acceptance_ready": build_acceptance,
            "production_release_ready": production,
            "release_ready": production,
            "baseline_tested": baseline_tested,
            "schema_gate": schema_gate,
            "external_postgres_validated": any(r["capability_key"] == "postgresql_phase15_backend_v1" and r["externally_validated"] for r in rows),
            "external_s3_validated": any(r["capability_key"] == "s3_compatible_object_store_v1" and r["externally_validated"] for r in rows),
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "Portable SQLite + local CAS are active defaults. PostgreSQL and S3 are explicit opt-in adapters; contract tests never count as external live validation.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase": "15",
            "name": "Data Platform Foundation",
            "schema": self.schema_metrics(),
            "data_platform": self.data_platform_status(),
            "architecture": self.architecture_status(),
            "gate": self.qualified_gate(),
            "version": self.version_status(),
            "capabilities": self.capabilities(),
            "darknet_runtime_execution": False,
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        status = self.data_platform_status()
        gate = self.qualified_gate()
        objects = self.artifacts(case_id=case_id, limit=20)
        rows = "".join(
            f"<tr><td><code>{html.escape(o['object_id'])}</code></td><td>{html.escape(o['media_type'])}</td><td>{o['size_bytes']}</td><td>{html.escape(o['security_state'])}</td><td><code>{html.escape(o['sha256'][:16])}…</code></td></tr>"
            for o in objects
        ) or "<tr><td colspan='5'>Noch keine Phase-15-Objekte.</td></tr>"
        return (
            "<section class='card'><h2>Phase 15 · Build 347 · Data Platform Foundation</h2>"
            f"<p><b>SQLite:</b> aktiv · <b>Local CAS:</b> aktiv · <b>PostgreSQL:</b> opt-in, Live-Validierung nicht behauptet · <b>S3/MinIO:</b> opt-in, Live-Validierung nicht behauptet.</p>"
            f"<p><b>Objects:</b> {status['object_store']['objects']} · <b>Quarantäne:</b> {status['object_store']['quarantined']} · <b>Build-Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'offen'} · <b>Production:</b> nicht freigegeben.</p>"
            "<p>Darknet-Artefakte werden hashgebunden und standardmäßig quarantänisiert. Build 347 führt selbst weiterhin keinen Tor-/HTTP-Fetch aus.</p>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/objects/text'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Lokales/übergebenes Text-Artefakt</label><textarea name='content' required></textarea><label>Search Run ID (optional)</label><input name='search_run_id'><label>Source ID (bei Darknet erforderlich)</label><input name='source_id'><button>Hashgebunden speichern</button></form>"
            f"<table><thead><tr><th>Object</th><th>Typ</th><th>Bytes</th><th>Security</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p><small>Status: <code>/api/build347</code></small></p></section>"
        )
