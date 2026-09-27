from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build443LiveNewsAcquisitionService:
    BUILD = "443.0"

    def __init__(self, db, audit, *, build442, news443, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build442 = build442
        self.news443 = news443
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build442, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def create_news_feed_task_443(self, **kwargs):
        return self.news443.create_feed_task(**kwargs)

    def execute_live_news_feed_443(self, **kwargs):
        return self.news443.execute_live(**kwargs)

    def live_news_runs_443(self, case_id):
        return self.news443.case_runs(case_id)

    def run_live_news_case_selftest(self, **kwargs):
        return self.news443.run_case_selftest(**kwargs)

    def live_news_status_443(self):
        status = self.news443.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 3,
            "surface_retrieval_hardened": True,
            "live_news_adapter_complete_for_public_feeds": True,
            "public_social_retrieval_adapter_complete": False,
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "444.0",
            "next_hard_checkpoint": "445.0",
        }
