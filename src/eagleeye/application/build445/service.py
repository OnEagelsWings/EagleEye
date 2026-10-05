from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build445DataAcquisitionQualificationService:
    BUILD = "445.0"

    def __init__(self, db, audit, *, build444, qualification445, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build444 = build444
        self.qualification445 = qualification445
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build444, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def qualify_data_acquisition_445(self, **kwargs):
        return self.qualification445.qualify(**kwargs)

    def data_acquisition_latest_445(self, case_id=""):
        return self.qualification445.latest(case_id)

    def data_acquisition_status_445(self):
        status = self.qualification445.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 5,
            "hard_checkpoint": True,
            "core_public_acquisition_paths_implemented": True,
            "next_build": "446.0",
            "next_hard_checkpoint": "450.0",
            "production_release_ready": False,
        }
