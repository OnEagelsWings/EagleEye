from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build378VoiceLiveValidationService:
    BUILD = "378.0"
    PACKAGE = "378.0.0"
    POLICY = "phase16.voice-live-validation-build.v378"

    def __init__(self, db: Any, audit: Any, *, build377: Any, voice378: Any, ai378: Any, opsec378: Any, install_dir: Any, base_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build377 = build377
        self.voice378 = voice378
        self.ai378 = ai378
        self.opsec378 = opsec378
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build377, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/phase16/voice_live_validation378.py",
            "src/eagleeye/application/build378/service.py",
            "src/eagleeye/interfaces/web/app378.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build378.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_378_0.py",
            "tools/benchmark_build378.py",
            "tools/live_voice_validate_378.py",
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
        value = _read_json(self.install_dir / "BUILD_378_TEST_EVIDENCE.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BENCHMARK_BUILD_378_VOICE_LIVE_VALIDATION.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 5200 and int(value.get("violations", -1)) == 0 else {}

    def _validation(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "LIVE_VALIDATION_BUILD_378_VOICE_PIPELINE.json")
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
            "voice_validation_new_tables": 0,
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

    def voice_crawler_propose(self, **kwargs: Any) -> dict[str, Any]:
        return self.voice378.propose(**kwargs)

    def voice_crawler_transcribe(self, **kwargs: Any) -> dict[str, Any]:
        return self.voice378.transcribe_push_to_talk(**kwargs)

    def voice_crawler_confirm(self, **kwargs: Any) -> dict[str, Any]:
        return self.voice378.confirm(**kwargs)

    def voice_crawler_interactions(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.voice378.interactions(**kwargs)

    def voice_status(self) -> dict[str, Any]:
        return self.voice378.status()

    def run_autonomous_investigation(self, **kwargs: Any) -> dict[str, Any]:
        return self.ai378.run_cycle(**kwargs)

    def autonomous_opsec_protect(self, **kwargs: Any) -> dict[str, Any]:
        return self.opsec378.protect_case(**kwargs)

    def phase16_status(self) -> dict[str, Any]:
        base = dict(self.build377.phase16_status())
        base.update({
            "build": self.BUILD,
            "builds_completed": 18,
            "voice_live_validation": self.voice378.status(),
            "ai": self.ai378.status(),
            "opsec": self.opsec378.status(),
            "crawler_improvement_build": 378,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build377.crawler_status())
        base.update({
            "crawler_improvement_build": 378,
            "voice_to_crawler_intent_preview": True,
            "voice_explicit_source_selection": True,
            "voice_request_budget_preview": True,
            "voice_edit_reconfirmation": True,
            "voice_preview_hash_provenance": True,
            "voice_case_workflow_delegation": True,
            "voice_direct_network_authority": False,
            "voice_automatic_source_selection": False,
            "voice_automatic_scope_expansion": False,
            "voice_provider_connector_execution": False,
            "voice_tor_execution_standard_path": False,
            "continuous_crawler_expansion_370_380": True,
            "automatic_external_connections_on_boot": 0,
            "background_workers_started_on_boot": 0,
        })
        return base

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark())
        val = self._validation()
        local = val.get("local_voice_pipeline_validation") == "pass"
        specs = [
            ("voice_crawler_intent_preview_v378", "preview"),
            ("voice_edit_reconfirmation_v378", "edit"),
            ("voice_source_budget_gate_v378", "budget"),
            ("voice_workflow_delegate_v378", "delegate"),
            ("voice_preview_hash_provenance_v378", "provenance"),
            ("voice_local_stt_boundary_v378", "stt"),
            ("voice_opsec_boundary_v378", "opsec"),
            ("local_voice_pipeline_validation_v378", "local"),
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
            "benchmark_5200_no_violations": bool(self._benchmark()),
            "local_voice_pipeline_validation": val.get("local_voice_pipeline_validation") == "pass",
            "preview_tested": self._probe("preview"),
            "edit_reconfirmation_tested": self._probe("edit"),
            "budget_gate_tested": self._probe("budget"),
            "workflow_delegate_tested": self._probe("delegate"),
            "provenance_tested": self._probe("provenance"),
            "stt_boundary_tested": self._probe("stt"),
            "opsec_tested": self._probe("opsec"),
            "no_literal_true_gate": self.active_gate_literal_true_lines() == [],
        }
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": all(bool(x) for x in checks.values()),
            "external_voice_stt_validation": "not_run",
            "external_multi_analyst_voice_validation": "not_run",
            "external_voice_crawler_network_validation": "not_run",
            "production_release_ready": False,
            "truthful_note": "Build 378 locally validates the voice-to-crawler intent, edit/reconfirmation, budget preview and case-workflow delegation boundaries. It does not claim external STT accuracy, production voice UX, or external crawler validation.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase16": self.phase16_status(),
            "crawler": self.crawler_status(),
            "voice": self.voice378.status(),
            "validation": self._validation(),
            "capabilities": self.capabilities(),
            "gate": self.qualified_gate(),
        }
