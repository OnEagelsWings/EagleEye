from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build450InvestigationWorkflowQualificationService:
    BUILD = "450.0"

    def __init__(self, db, audit, *, build449, qualification450, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build449 = build449
        self.qualification450 = qualification450
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build449, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def qualify_investigation_workflow_450(self, **kwargs):
        return self.qualification450.qualify(**kwargs)

    def investigation_workflow_latest_450(self, case_id=""):
        return self.qualification450.latest(case_id)

    def investigation_workflow_status_450(self):
        status = self.qualification450.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 10,
            "hard_checkpoint": True,
            "build449_team_review_integrated": True,
            "build448_ui_audit_retained": True,
            "build447_evidence_claim_dossier_integrated": True,
            "build446_live_dispatch_integrated": True,
            "production_release_ready": False,
        }
