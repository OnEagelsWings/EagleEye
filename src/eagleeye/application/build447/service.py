from eagleeye_pro.version import BUILD as RUNTIME_BUILD, SCHEMA_VERSION


class Build447EvidenceClaimsDossierService:
    BUILD = "447.0"

    def __init__(self, db, audit, *, build446, closure447, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build446 = build446
        self.closure447 = closure447
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build446, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def sync_case_evidence_447(self, **kwargs):
        return self.closure447.sync_case_evidence(**kwargs)

    def case_evidence_447(self, case_id):
        return self.closure447.case_evidence(case_id)

    def review_evidence_447(self, **kwargs):
        return self.closure447.review_evidence(**kwargs)

    def propose_claim_447(self, **kwargs):
        return self.closure447.propose_claim(**kwargs)

    def review_claim_447(self, **kwargs):
        return self.closure447.review_claim(**kwargs)

    def case_claims_447(self, case_id):
        return self.closure447.case_claims(case_id)

    def build_dossier_447(self, **kwargs):
        return self.closure447.build_dossier(**kwargs)

    def review_dossier_447(self, **kwargs):
        return self.closure447.review_dossier(**kwargs)

    def export_dossier_447(self, **kwargs):
        return self.closure447.export_dossier(**kwargs)

    def case_dossiers_447(self, case_id):
        return self.closure447.case_dossiers(case_id)

    def case_exports_447(self, case_id):
        return self.closure447.exports(case_id)

    def run_evidence_claims_dossier_case_selftest(self, **kwargs):
        return self.closure447.run_case_selftest(**kwargs)

    def evidence_claims_dossier_status_447(self):
        status = self.closure447.status()
        return {
            **status,
            "version_coherent": (
                RUNTIME_BUILD == SCHEMA_VERSION
                and int(RUNTIME_BUILD.split(".")[0]) >= int(self.BUILD.split(".")[0])
            ),
            "phase": 20,
            "phase20_builds_completed": 7,
            "build446_live_loop_integrated": True,
            "evidence_to_claims_to_dossier_closed": True,
            "formal_four_eyes_export_workflow_deferred_to_build449": True,
            "real_world_general_research_ready": False,
            "production_release_ready": False,
            "next_build": "448.0",
            "next_hard_checkpoint": "450.0",
        }
