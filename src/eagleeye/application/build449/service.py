from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build449HumanReviewTeamWorkflowService:
    BUILD = "449.0"

    def __init__(self, db, audit, *, build448, review449, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build448 = build448
        self.review449 = review449
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build448, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def team_review_snapshot_449(self, **kwargs):
        return self.review449.snapshot(**kwargs)

    def request_review_449(self, **kwargs):
        return self.review449.request_review(**kwargs)

    def claim_review_449(self, **kwargs):
        return self.review449.claim_review(**kwargs)

    def complete_review_449(self, **kwargs):
        return self.review449.complete_review(**kwargs)

    def add_review_comment_449(self, **kwargs):
        return self.review449.add_comment(**kwargs)

    def execute_approved_export_449(self, **kwargs):
        return self.review449.execute_approved_export(**kwargs)

    def review_queue_449(self, **kwargs):
        return self.review449.queue(**kwargs)

    def human_review_status_449(self):
        status = self.review449.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 9,
            "build448_workspace_integrated": True,
            "build447_review_semantics_preserved": True,
            "production_release_ready": False,
            "next_build": "450.0",
            "next_hard_checkpoint": "450.0",
        }
