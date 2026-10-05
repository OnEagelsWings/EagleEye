from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build442SurfaceHardeningService:
    BUILD = "442.0"

    def __init__(self, db, audit, *, build441, hardening442, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build441 = build441
        self.hardening442 = hardening442
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build441, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def execute_hardened_surface_task_442(self, **kwargs):
        return self.hardening442.execute_live(**kwargs)

    def execute_hardened_loop_surface_task_442(self, **kwargs):
        return self.hardening442.execute_authorized_loop_task(**kwargs)

    def validate_external_surface_task_442(self, **kwargs):
        return self.hardening442.validate_external_task(**kwargs)

    def surface_hardening_runs_442(self, case_id):
        return self.hardening442.case_runs(case_id)

    def surface_task_telemetry_442(self, task_id):
        return self.hardening442.task_telemetry(task_id)

    def run_surface_hardening_case_selftest(self, **kwargs):
        return self.hardening442.run_case_selftest(**kwargs)

    def surface_hardening_status_442(self):
        status = self.hardening442.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 2,
            "build441_surface_executor_retained": True,
            "surface_hardening_complete_for_current_scope": True,
            "external_validation_framework": True,
            "external_validation_automatic": False,
            "news_retrieval_adapter_complete": False,
            "public_social_retrieval_adapter_complete": False,
            "general_live_collection_complete": False,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "443.0",
            "next_hard_checkpoint": "445.0",
        }
