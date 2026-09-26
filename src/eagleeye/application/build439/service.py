from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build439AIInvestigationLoopService:
    BUILD = "439.0"

    def __init__(self, db, audit, *, build438, loop439, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build438 = build438
        self.loop439 = loop439
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build438, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def create_ai_investigation_loop_439(self, **kwargs):
        return self.loop439.create_loop(**kwargs)

    def authorize_ai_investigation_loop_439(self, **kwargs):
        return self.loop439.authorize_loop(**kwargs)

    def advance_ai_investigation_loop_439(self, **kwargs):
        return self.loop439.advance_loop(**kwargs)

    def ai_investigation_loop_439(self, loop_id):
        return self.loop439.loop(loop_id)

    def ai_investigation_loops_439(self, case_id):
        return self.loop439.loops(case_id)

    def ai_investigation_steps_439(self, loop_id):
        return self.loop439.steps(loop_id)

    def ai_investigation_report_439(self, loop_id, **kwargs):
        return self.loop439.report(loop_id, **kwargs)

    def run_ai_investigation_case_selftest(self, **kwargs):
        return self.loop439.run_case_selftest(**kwargs)

    def ai_investigation_status_439(self):
        status = self.loop439.status()
        return {
            **status,
            "version_coherent": RUNTIME_BUILD == SCHEMA_VERSION and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0]),
            "phase": 19,
            "phase19_builds_completed": 19,
            "next_hard_checkpoint": "440.0",
            "production_release_ready": False,
        }
