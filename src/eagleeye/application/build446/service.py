from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build446LiveAIInvestigationService:
    BUILD = "446.0"

    def __init__(self, db, audit, *, build445, dispatcher446, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build445 = build445
        self.dispatcher446 = dispatcher446
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build445, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def prepare_live_loop_dispatches_446(self, **kwargs):
        return self.dispatcher446.prepare_loop_dispatches(**kwargs)

    def execute_live_loop_dispatch_446(self, **kwargs):
        return self.dispatcher446.execute_live(**kwargs)

    def live_loop_dispatches_446(self, loop_id):
        return self.dispatcher446.dispatches(loop_id)

    def live_loop_executions_446(self, loop_id):
        return self.dispatcher446.executions(loop_id)

    def run_live_loop_case_selftest(self, **kwargs):
        return self.dispatcher446.run_case_selftest(**kwargs)

    def live_loop_status_446(self):
        status = self.dispatcher446.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 6,
            "build445_checkpoint_retained": True,
            "specialized_news_social_dispatch_gap_closed": True,
            "data_acquisition_gate_may_remain_hold_until_external_validation": True,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "447.0",
            "next_hard_checkpoint": "450.0",
        }
