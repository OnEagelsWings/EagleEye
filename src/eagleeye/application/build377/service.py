from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build377ImageLiveValidationService:
    BUILD = "377.0"
    PACKAGE = "377.0.0"
    POLICY = "phase16.image-live-validation-build.v377"

    def __init__(self, db: Any, audit: Any, *, build376: Any, image377: Any, ai377: Any, opsec377: Any, install_dir: Any, base_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build376 = build376
        self.image377 = image377
        self.ai377 = ai377
        self.opsec377 = opsec377
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build376, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/phase16/image_live_validation377.py",
            "src/eagleeye/application/build377/service.py",
            "src/eagleeye/interfaces/web/app377.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build377.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_377_0.py",
            "tools/benchmark_build377.py",
            "tools/live_image_validate_377.py",
            "CRAWLER_ROADMAP_BUILD_370_TO_380.md",
            "PHASE_16_MASTERPLAN_BUILD_361_TO_380.md",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BUILD_377_TEST_EVIDENCE.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BENCHMARK_BUILD_377_IMAGE_LIVE_VALIDATION.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 5000 and int(value.get("violations", -1)) == 0 else {}

    def _validation(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "LIVE_VALIDATION_BUILD_377_IMAGE_PIPELINE.json")
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def schema_metrics(self) -> dict[str, Any]:
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        logical = int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get("n") or 0)
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        out = {
            "table": counts.get("table", 0), "index": counts.get("index", 0), "trigger": counts.get("trigger", 0), "view": counts.get("view", 0),
            "logical_bytes": logical, "integrity_check": integrity,
            "targets": {"tables_lt": 180, "indexes_lt": 300, "logical_bytes_lt": 5 * 1024 * 1024},
            "image_validation_new_tables": 0,
        }
        out["within_gate"] = out["table"] < 180 and out["index"] < 300 and logical < 5 * 1024 * 1024 and integrity == "ok"
        return out

    def version_status(self) -> dict[str, Any]:
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self.install_dir / "pyproject.toml").read_text(encoding="utf-8")
        def g(pattern: str, text: str) -> str:
            m = re.search(pattern, text, re.M); return m.group(1) if m else "unknown"
        runtime = g(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = g(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def image_ingest(self, **kwargs: Any) -> dict[str, Any]:
        return self.image377.ingest_image(**kwargs)

    def image_case_summary(self, *, case_id: str) -> dict[str, Any]:
        return self.image377.case_media_summary(case_id=case_id)

    def image_provenance(self, *, case_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.image377.media_provenance(case_id=case_id, limit=limit)

    def image_storage_pressure(self, *, case_id: str | None = None, incoming_bytes: int = 0) -> dict[str, Any]:
        return self.image377.storage_pressure(case_id=case_id, incoming_bytes=incoming_bytes)

    def visual_geolocation(self, **kwargs: Any) -> dict[str, Any]:
        return self.image377.visual_geolocation(**kwargs)

    def run_autonomous_investigation(self, **kwargs: Any) -> dict[str, Any]:
        return self.ai377.run_cycle(**kwargs)

    def autonomous_opsec_protect(self, **kwargs: Any) -> dict[str, Any]:
        return self.opsec377.protect_case(**kwargs)

    def phase16_status(self) -> dict[str, Any]:
        base = dict(self.build376.phase16_status())
        base.update({
            "build": self.BUILD,
            "builds_completed": 17,
            "image_live_validation": self.image377.status(),
            "ai": self.ai377.status(),
            "opsec": self.opsec377.status(),
            "crawler_improvement_build": 377,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build376.crawler_status())
        base.update({
            "crawler_improvement_build": 377,
            "image_media_provenance": True,
            "exact_image_dedup_before_object_write": True,
            "object_store_pressure_control": True,
            "image_agent_handoff_review_first": True,
            "automatic_reverse_image_search": False,
            "automatic_image_scope_expansion": False,
            "continuous_crawler_expansion_370_380": True,
            "automatic_external_connections_on_boot": 0,
            "background_workers_started_on_boot": 0,
        })
        return base

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark())
        val = self._validation()
        local = val.get("local_image_pipeline_validation") == "pass"
        specs = [
            ("image_live_pipeline_v377", "pipeline"),
            ("crawler_media_provenance_v377", "provenance"),
            ("exact_media_dedup_v377", "dedup"),
            ("object_store_pressure_v377", "pressure"),
            ("image_agent_handoff_v377", "handoff"),
            ("image_epistemic_boundaries_v377", "epistemics"),
            ("opsec_image_boundary_v377", "opsec"),
            ("local_image_pipeline_validation_v377", "local"),
        ]
        out = []
        for key, probe in specs:
            tested = local if probe == "local" else self._probe(probe)
            states = {"implemented": True, "integrated": True, "tested": tested, "benchmarked": bench, "externally_validated": False}
            maturity = next((k for k in reversed(DIMENSIONS) if states[k]), "declared")
            out.append({"key": key, "states": states, "maturity": maturity})
        return out

    def qualified_gate(self) -> dict[str, Any]:
        s = self.schema_metrics(); v = self.version_status(); val = self._validation()
        checks = {
            "schema_within_gate": s["within_gate"],
            "version_coherent": v["coherent"],
            "test_evidence_current": bool(self._test_evidence()),
            "benchmark_5000_no_violations": bool(self._benchmark()),
            "local_image_pipeline_validation": val.get("local_image_pipeline_validation") == "pass",
            "pipeline_tested": self._probe("pipeline"),
            "provenance_tested": self._probe("provenance"),
            "dedup_tested": self._probe("dedup"),
            "pressure_tested": self._probe("pressure"),
            "handoff_tested": self._probe("handoff"),
            "epistemics_tested": self._probe("epistemics"),
            "opsec_tested": self._probe("opsec"),
            "no_literal_true_gate": self.active_gate_literal_true_lines() == [],
        }
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": all(bool(x) for x in checks.values()),
            "external_image_source_validation": "not_run",
            "external_reverse_image_provider_validation": "not_run",
            "external_image_analyst_validation": "not_run",
            "production_release_ready": False,
            "truthful_note": "Build 377 validates and hardens the local image/media pipeline. It does not claim external image-provider validation, identity confirmation, or scene-location confirmation.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase16": self.phase16_status(),
            "crawler": self.crawler_status(),
            "image": self.image377.status(),
            "validation": self._validation(),
            "capabilities": self.capabilities(),
            "gate": self.qualified_gate(),
        }
