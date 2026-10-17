from __future__ import annotations


class Build458DocumentIntelligenceService:
    BUILD="458.0"

    def __init__(self, db, audit, *, build457, documents458, actor="local-analyst"):
        self.db,self.audit=db,audit
        self.build457=build457
        self.documents458=documents458
        self.actor=actor

    def __getattr__(self,name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.build457,name)

    def build458_status(self):
        retained=self.build457.build457_status()
        current=self.documents458.status()
        return {
            **current,
            "integrity_valid":bool(retained.get("integrity_valid")) and bool(current["integrity_valid"]),
            "retained_build457_integrity_valid":bool(retained.get("integrity_valid")),
            "phase":20,
            "focus":"page/paragraph/caption/footnote candidate anchoring",
            "supported_formats":["PDF","TXT","MD"],
            "native_pdf_extraction":True,
            "ocr_required_flag":True,
            "automatic_ocr_execution":False,
            "human_extraction_review":True,
            "claim_citation_link_version_bound":True,
            "retained_workspace_reliability":True,
            "full_research_gate_this_build":False,
            "next_checkpoint":"460.0",
            "next_build":"459.0",
            "next_build_focus":"Integration Burn-in / Field Workflow Readiness",
            "production_release_ready":False,
        }
