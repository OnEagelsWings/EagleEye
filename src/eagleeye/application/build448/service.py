from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build448InvestigatorWorkspaceService:
    BUILD = "448.0"

    def __init__(self, db, audit, *, build447, workspace448, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build447 = build447
        self.workspace448 = workspace448
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build447, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def investigator_workspace_snapshot_448(self, **kwargs):
        return self.workspace448.snapshot(**kwargs)

    def run_ui_audit_448(self, **kwargs):
        return self.workspace448.audit_markup(**kwargs)

    def ui_audit_history_448(self, case_id, limit=25):
        return self.workspace448.audit_history(case_id, limit=limit)

    def investigator_workspace_status_448(self):
        status = self.workspace448.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 8,
            "build447_closure_integrated": True,
            "primary_workspace_replaced": True,
            "legacy_workspace_available": True,
            "scheduled_ui_audit_supported": True,
            "production_release_ready": False,
            "next_build": "449.0",
            "next_hard_checkpoint": "450.0",
        }
