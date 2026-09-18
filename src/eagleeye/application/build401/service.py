from __future__ import annotations
import re
from pathlib import Path


class Build401SecurityQualificationHardeningService:
    BUILD = "401.0"
    PACKAGE = "401.0.0"
    POLICY = "phase18.security-qualification-hardening.v401"

    def __init__(self, db, audit, *, build400, gate401, install_dir, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build400 = build400
        self.gate401 = gate401
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build400, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def version_status(self):
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text()
        pt = (self.install_dir / "pyproject.toml").read_text()
        pick = lambda pattern, text: (re.search(pattern, text, re.M).group(1) if re.search(pattern, text, re.M) else "unknown")
        runtime = pick(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = pick(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = pick(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def security_gate(self, case_id=""):
        return self.gate401.evaluate(case_id)

    def phase18_status(self, case_id=""):
        previous = dict(self.build400.phase17_status(case_id))
        gate = self.security_gate(case_id)
        previous.update({
            "build": self.BUILD,
            "phase": 18,
            "phase18_builds_completed": 1,
            "security_qualification_gate": gate["security_gate_pass"],
            "github_feedback_integrated": True,
            "five_build_feedback_cycle": True,
            "next_public_feedback_build": "405.0",
            "production_release_ready": False,
        })
        return previous

    def qualified_gate(self):
        version = self.version_status()
        security = self.security_gate()
        checks = {
            "version_coherent": version["coherent"],
            "security_gate_pass": security["security_gate_pass"],
            "fail_closed": security["fail_closed"],
            "read_only_gate": security["read_only"],
            "feedback_cycle_declared": security["feedback_cycle"]["publish_after_build"] == 405,
            "production_not_released": security["production_release_ready"] is False,
        }
        return {"build": self.BUILD, "checks": checks, "build_acceptance_ready": all(checks.values()), "phase18_entry": True, "production_release_ready": False}
