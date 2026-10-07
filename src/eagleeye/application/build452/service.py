from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path


class Build452DeploymentService:
    BUILD = "452.0"
    PACKAGE = "eagleeye-personosint-pro"
    PACKAGE_VERSION = "452.0.0"

    def __init__(self, db, audit, *, build451, actor="local-analyst"):
        self.db, self.audit, self.build451, self.actor = db, audit, build451, actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.build451, name)

    def deployment_status_452(self):
        installed_version = ""
        editable = None
        package_root = ""
        try:
            dist = importlib.metadata.distribution(self.PACKAGE)
            installed_version = dist.version
            raw = dist.read_text("direct_url.json")
            if raw:
                try:
                    editable = bool((json.loads(raw).get("dir_info") or {}).get("editable", False))
                except (TypeError, ValueError, json.JSONDecodeError):
                    editable = None
            try:
                package_root = str(Path(dist.locate_file("")).resolve())
            except (OSError, RuntimeError):
                package_root = ""
        except importlib.metadata.PackageNotFoundError:
            pass

        expected = installed_version == self.PACKAGE_VERSION
        non_editable = editable is not True
        return {
            "build": self.BUILD,
            "phase": 20,
            "name": "Deterministic Local Deployment",
            "package": self.PACKAGE,
            "expected_package_version": self.PACKAGE_VERSION,
            "installed_package_version": installed_version,
            "package_version_matches": expected,
            "editable_install": editable,
            "non_editable_runtime_expected": True,
            "non_editable_runtime_observed": non_editable if installed_version else False,
            "python_executable": str(Path(sys.executable).resolve()),
            "package_root": package_root,
            "launcher_isolated_mode_required": True,
            "installer_receipt_required": True,
            "research_chain_retained": True,
            "operational_qualification": "HOLD",
            "production_release_ready": False,
            "next_build": "453.0",
            "next_hard_checkpoint": "455.0",
        }
