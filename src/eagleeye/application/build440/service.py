from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build440Phase19QualificationService:
    BUILD = "440.0"

    def __init__(self, db, audit, *, build439, qualification440, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build439 = build439
        self.qualification440 = qualification440
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build439, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def qualify_phase19(self, **kwargs):
        return self.qualification440.qualify(**kwargs)

    def phase19_capability_matrix_440(self):
        return self.qualification440.capability_matrix()

    def phase19_qualification_latest_440(self, case_id=""):
        return self.qualification440.latest(case_id)

    def phase19_qualification_status_440(self):
        status = self.qualification440.status()
        component_integrity = {}
        for name in self.qualification440.REQUIRED:
            service = self.qualification440.services.get(name)
            try:
                if hasattr(service, "verify_integrity"):
                    component_integrity[name] = bool(service.verify_integrity().get("valid", False))
                elif hasattr(service, "status"):
                    component_integrity[name] = bool(service.status().get("integrity_valid", False))
                else:
                    component_integrity[name] = service is not None
            except Exception:
                component_integrity[name] = False
        last = self.qualification440.latest()
        checks = {
            "version_coherent": RUNTIME_BUILD == SCHEMA_VERSION == self.BUILD,
            "qualification_record_integrity": status["integrity_valid"],
            "all_current_component_integrity": all(component_integrity.values()),
            "passing_phase19_qualification": bool(last and last["result"] == "pass"),
            "live_limitations_declared": (
                status["live_collection_complete"] is False
                and status["real_world_general_research_ready"] is False
                and status["production_release_ready"] is False
            ),
        }
        return {
            **status,
            "version_coherent": checks["version_coherent"],
            "component_integrity": component_integrity,
            "checks": checks,
            "phase": 19,
            "phase19_builds_completed": 20,
            "hard_checkpoint": True,
            "phase19_gate_pass": all(checks.values()),
            "production_release_ready": False,
        }
