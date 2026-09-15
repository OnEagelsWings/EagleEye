from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build394InvestigatorDiscussionRevisionService:
    BUILD = "394.0"
    PACKAGE = "394.0.0"
    POLICY = "phase17.investigator-discussion-versioned-revision-build.v394"

    def __init__(self, db: Any, audit: Any, *, build393: Any, discussion394: Any, install_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build393 = build393
        self.discussion394 = discussion394
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build393, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "eagleeye_pro/phase17/discussion_revision394.py",
            "eagleeye_pro/phase17/investigator_dialogue393.py",
            "eagleeye_pro/phase17/case_reasoning392.py",
            "eagleeye_pro/phase17/investigation_synthesis391.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/application/build394/service.py",
            "src/eagleeye/interfaces/web/app394.py",
            "src/eagleeye/interfaces/web/server.py",
            "EAGLEEYE_PRO_394_0.py",
            "START_EAGLEEYE_PRO.bat",
            "START_EAGLEEYE_PRO.sh",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build394_integrated.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_394_0.py",
            "tools/benchmark_build394.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode())
            h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>")
            h.update(b"\0")
        return h.hexdigest()

    def version_status(self) -> dict[str, Any]:
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self.install_dir / "pyproject.toml").read_text(encoding="utf-8")
        def g(pattern: str, text: str) -> str:
            m = re.search(pattern, text, re.M)
            return m.group(1) if m else "unknown"
        runtime = g(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = g(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def schema_metrics(self) -> dict[str, Any]:
        _ = self.discussion394.status()
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        present = {r["name"] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        req = {
            "investigator_discussion_session_394", "investigator_discussion_turn_394", "hypothesis_comparison_394",
            "discussion_revision_proposal_394", "discussion_revision_review_394", "versioned_revision_394", "discussion_kernel_bridge_394",
        }
        return {
            "tables": counts.get("table", 0), "indexes": counts.get("index", 0), "triggers": counts.get("trigger", 0), "views": counts.get("view", 0),
            "integrity_check": integrity, "build394_tables_present": req.issubset(present),
            "within_phase17_gate": counts.get("table", 0) < 290 and counts.get("index", 0) < 480 and integrity == "ok" and req.issubset(present),
        }

    def _evidence(self, filename: str) -> dict[str, Any]:
        value = _read_json(self.install_dir / filename)
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and value.get("result") == "pass" else {}

    def historical_build393_receipt(self) -> dict[str, Any]:
        release = _read_json(self.install_dir / "RELEASE_MANIFEST_BUILD_393_0.json")
        acceptance = _read_json(self.install_dir / "ACCEPTANCE_RESULTS_BUILD_393_0.json")
        valid = (
            release.get("build") == "393.0"
            and release.get("production_release_ready") is False
            and int((release.get("regression") or {}).get("functional_regressions", -1)) == 0
            and (release.get("acceptance") or {}).get("result") == "pass"
            and acceptance.get("build") == "393.0"
            and acceptance.get("result") == "pass"
            and acceptance.get("code_fingerprint") == release.get("code_fingerprint")
        )
        return {"build": "393.0", "valid": bool(valid), "code_fingerprint": release.get("code_fingerprint", ""), "production_release_ready": False}

    def create_investigator_discussion(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.create_session(**kwargs)
    def investigator_discussion(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.session(**kwargs)
    def discuss_case(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.discuss(**kwargs)
    def discussion_turn(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.turn(**kwargs)
    def compare_discussion_hypotheses(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.compare_hypotheses(**kwargs)
    def create_versioned_revision_proposal(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.create_revision_proposal(**kwargs)
    def review_versioned_revision(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.review_revision(**kwargs)
    def apply_versioned_revision(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.apply_revision(**kwargs)
    def versioned_revision(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.version(**kwargs)
    def latest_versioned_revision(self, **kwargs: Any) -> dict[str, Any] | None: return self.discussion394.latest_version(**kwargs)
    def admit_versioned_revision_to_kernel(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.admit_version_to_kernel(**kwargs)
    def ai_investigator_discussion_feed(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.ai_discussion_feed(**kwargs)
    def verify_investigator_discussion(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.verify_session(**kwargs)
    def verify_discussion_turn(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.verify_turn(**kwargs)
    def verify_versioned_revision_proposal(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.verify_revision_proposal(**kwargs)
    def verify_versioned_revision(self, **kwargs: Any) -> dict[str, Any]: return self.discussion394.verify_version(**kwargs)

    def phase17_status(self, case_id: str = "") -> dict[str, Any]:
        out = dict(self.build393.phase17_status(case_id))
        out.update({
            "build": self.BUILD, "phase17_builds_completed": 14, "investigator_discussion_workspace": True,
            "multi_turn_argumentation": True, "hypothesis_comparison": True, "versioned_revision_lineage": True,
            "append_only_upstream": True, "automatic_upstream_mutation": False, "automatic_go_issuance": False,
            "execution_authority": False, "truth_probability": False, "discussion": self.discussion394.status(),
        })
        return out

    def qualified_gate(self) -> dict[str, Any]:
        version = self.version_status(); schema = self.schema_metrics(); tests = self._evidence("BUILD_394_TEST_EVIDENCE.json")
        bench = self._evidence("BENCHMARK_BUILD_394_DISCUSSION.json"); acc = self._evidence("ACCEPTANCE_RESULTS_BUILD_394_0.json")
        pred = self.historical_build393_receipt(); status = self.discussion394.status()
        checks = {
            "version_coherent": bool(version["coherent"]), "schema_integrity": bool(schema["within_phase17_gate"]), "phase17_predecessor_gate": bool(pred.get("valid")),
            "build394_tests": bool(tests), "build394_benchmark": bool(bench) and int(bench.get("violations", -1)) == 0, "build394_acceptance": bool(acc),
            "multi_turn_discussion": bool(status["multi_turn_discussion"]), "argument_counterargument": bool(status["argument_counterargument_chains"]),
            "hypothesis_comparison": bool(status["hypothesis_side_by_side_comparison"]), "versioned_revision": bool(status["versioned_revision_proposals"]),
            "human_revision_review": bool(status["human_revision_review_required"]), "append_only_lineage": bool(status["append_only_revision_lineage"]),
            "immutable_upstream": bool(status["immutable_upstream_objects"]), "evidence_metrics_immutable": not bool(status["evidence_derived_metrics_editable"]),
            "kernel_version_bridge": bool(status["kernel_notebook_version_bridge"]), "no_truth_probability": not bool(status["truth_probability"]),
            "no_auto_truth_acceptance": not bool(status["automatic_truth_acceptance"]), "no_auto_upstream_mutation": not bool(status["automatic_upstream_mutation"]),
            "no_auto_evidence_promotion": not bool(status["automatic_evidence_promotion"]), "no_auto_go": not bool(status["automatic_go_issuance"]),
            "no_live_confirmation": not bool(status["automatic_live_confirmation"]), "no_execution_authority": not bool(status["execution_authority"]),
            "no_direct_fetch": not bool(status["direct_network_fetch"]), "no_identity_merge": not bool(status["automatic_identity_merge"]),
        }
        return {
            "build": self.BUILD, "checks": checks, "build_acceptance_ready": all(checks.values()), "phase17_builds_completed": 14,
            "production_release_ready": False, "professional_pilot_line_preserved": bool(pred.get("valid")),
            "truthful_note": "Build 394 adds a multi-turn investigator discussion workspace, side-by-side hypothesis comparison, and append-only versioned working-copy revisions for claims, hypotheses and reasoning plans. Reviewed revisions create new Phase-17 versions rather than overwriting Build-391/392 source objects. Evidence-derived metrics remain immutable; no truth probability, evidence promotion, GO/LIVE authority, identity merge, network fetch or execution authority is added.",
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {"build": self.BUILD, "phase17": self.phase17_status(case_id), "discussion": self.discussion394.status(), "schema": self.schema_metrics(), "gate": self.qualified_gate()}
