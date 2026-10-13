from __future__ import annotations


class Build458DocumentIntelligenceService:
    BUILD = "458.0"

    def __init__(self, db, audit, *, build457, documents458, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.build457 = build457
        self.documents458 = documents458
        self.actor = actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.build457, name)

    def ingest_document_458(self, **kwargs):
        return self.documents458.ingest_document(**kwargs)

    def case_documents_458(self, **kwargs):
        return self.documents458.case_documents(**kwargs)

    def document_458(self, **kwargs):
        return self.documents458.document(**kwargs)

    def link_claim_anchor_458(self, **kwargs):
        return self.documents458.link_claim_anchor(**kwargs)

    def claim_anchor_citations_458(self, **kwargs):
        return self.documents458.claim_anchor_citations(**kwargs)

    def dossier_anchor_manifest_458(self, **kwargs):
        return self.documents458.dossier_anchor_manifest(**kwargs)

    def build458_status(self):
        retained = self.build457.build457_status()
        current = self.documents458.status()
        return {
            **current,
            "phase": 20,
            "integrity_valid": bool(retained.get("integrity_valid")) and bool(current.get("integrity_valid")),
            "retained_build457_integrity_valid": bool(retained.get("integrity_valid")),
            "workspace_reliability_retained": True,
            "multilingual_lineage_retained": True,
            "focused_development_build": True,
            "next_build_focus": "Integration Burn-in + Field Workflow Readiness",
            "next_checkpoint": "460.0",
        }
