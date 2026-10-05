from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build444ControlledPublicSocialService:
    BUILD = "444.0"

    def __init__(self, db, audit, *, build443, social444, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build443 = build443
        self.social444 = social444
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build443, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def create_public_social_task_444(self, **kwargs):
        return self.social444.create_task(**kwargs)

    def execute_public_social_task_444(self, **kwargs):
        return self.social444.execute_live(**kwargs)

    def public_social_runs_444(self, case_id):
        return self.social444.case_runs(case_id)

    def run_public_social_case_selftest(self, **kwargs):
        return self.social444.run_case_selftest(**kwargs)

    def public_social_status_444(self):
        status = self.social444.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 4,
            "surface_retrieval_hardened": True,
            "live_news_adapter_complete_for_public_feeds": True,
            "public_social_adapter_complete_for_reviewed_json_endpoints": True,
            "core_public_acquisition_paths_implemented": True,
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "445.0",
            "next_hard_checkpoint": "445.0",
        }
