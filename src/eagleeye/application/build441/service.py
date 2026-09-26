from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build441ControlledSurfaceRetrievalService:
    BUILD = "441.0"

    def __init__(self, db, audit, *, build440, surface441, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build440 = build440
        self.surface441 = surface441
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build440, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def execute_surface_task_441(self, **kwargs):
        return self.surface441.execute_live(**kwargs)

    def execute_authorized_loop_surface_task_441(self, **kwargs):
        return self.surface441.execute_authorized_loop_task(**kwargs)

    def surface_retrieval_runs_441(self, case_id):
        return self.surface441.case_runs(case_id)

    def run_surface_retrieval_case_selftest(self, **kwargs):
        return self.surface441.run_case_selftest(**kwargs)

    def surface_retrieval_status_441(self):
        status = self.surface441.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 1,
            "phase19_checkpoint_retained": True,
            "ordinary_surface_retrieval_available": True,
            "news_retrieval_adapter_complete": False,
            "public_social_retrieval_adapter_complete": False,
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_hard_checkpoint": "460.0",
        }
