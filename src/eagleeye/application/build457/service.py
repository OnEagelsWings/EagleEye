from __future__ import annotations


class Build457WorkspaceReliabilityService:
    BUILD = "457.0"

    def __init__(self, db, audit, *, build456, workspace457, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build456 = build456
        self.workspace457 = workspace457
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.build456, name)

    def workspace_snapshot_457(self, **kwargs):
        return self.workspace457.snapshot(**kwargs)

    def build457_status(self):
        retained = self.build456.build456_status()
        current = self.workspace457.status()
        return {
            **current,
            "phase": 20,
            "integrity_valid": bool(retained.get("integrity_valid")) and bool(current.get("integrity_valid", True)),
            "retained_build456_integrity_valid": bool(retained.get("integrity_valid")),
            "focused_development_build": True,
            "build456_multilingual_lineage_retained": True,
            "next_build_focus": "Document Intelligence 2.0 / precise Evidence anchors",
        }
