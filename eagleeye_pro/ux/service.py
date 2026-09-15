from __future__ import annotations
from typing import Any, Dict, List

from eagleeye_pro.core.database import Database, dumps, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

WORKSPACES: List[Dict[str, Any]] = [
    {
        "workspace_key": "start_case_guidance",
        "title": "Start & Fallführung",
        "purpose": "Fallüberblick, Fallanlage, Zielperson, Workflow und Playbook-Auswahl an einem Ort.",
        "tabs": ["Ermittlungsnavigator", "Fall-Cockpit", "Fälle", "Zielperson", "Profi-Workflow", "Playbooks"],
    },
    {
        "workspace_key": "research_intake",
        "title": "Recherche & Intake",
        "purpose": "Suchbündel, Provider, Capture, Review und Evidence Intake zusammenführen.",
        "tabs": ["Search Workbench", "Provider Integration", "Review Inbox", "Evidence Vault"],
    },
    {
        "workspace_key": "analysis_intelligence",
        "title": "Analyse & Intelligence",
        "purpose": "Identity-Kandidaten, Risiko, Graph, Timeline und AI-Assistenz bündeln.",
        "tabs": ["Identity & Risk", "Graph & Timeline", "AI Analyst"],
    },
    {
        "workspace_key": "reporting_export",
        "title": "Bericht & Export",
        "purpose": "Berichtsreife, Mandantenreport, interne Fassung, Anlagen und Exportkontrolle.",
        "tabs": ["Reporting Engine Pro"],
    },
    {
        "workspace_key": "governance_security",
        "title": "Governance & Sicherheit",
        "purpose": "Legal Gate, Privacy, Teamrechte, Security und Audit konzentrieren.",
        "tabs": ["Legal Gate", "Legal/Privacy Hardening", "Team/Mandanten", "Security", "Audit"],
    },
    {
        "workspace_key": "operations_release",
        "title": "Betrieb & Release",
        "purpose": "Packaging, Migration, Release Candidate und Betriebsprüfungen.",
        "tabs": ["Packaging", "Release Candidate"],
    },
]

SEARCH_BUNDLES: List[Dict[str, Any]] = [
    {
        "bundle_key": "identity_core",
        "title": "Person & Identität",
        "objective": "Namensanker, Alias, Usernames und E-Mail als Kandidaten prüfen.",
        "categories": ["Identitätsanker", "Alias", "Username", "Username + Name", "E-Mail"],
        "source_mode": "public_search_manual_review",
    },
    {
        "bundle_key": "context_location",
        "title": "Kontext, Ort & Umfeld",
        "objective": "Öffentliche Orts-, Kontext- und Umfeldhinweise ohne private Adressbestimmung bündeln.",
        "categories": ["Ortskontext"],
        "source_mode": "public_context_only_no_private_address_assertion",
    },
    {
        "bundle_key": "professional_business",
        "title": "Beruf, Firma & Register",
        "objective": "Berufliche Profile, Firmenbezüge, Register-/Presse- und Impressumsspuren zusammenführen.",
        "categories": ["Beruf/Firma", "Register/Presse", "Öffentliches Berufsprofil", "Fachprofil", "Publikationen", "Impressum"],
        "source_mode": "public_or_licensed_business_sources",
    },
    {
        "bundle_key": "documents_media_archive",
        "title": "Dokumente, Medien & Archive",
        "objective": "PDFs, Presse, Interviews, Vorträge und archivierte öffentliche Inhalte bündeln.",
        "categories": ["Dokumente", "Presse"],
        "source_mode": "public_documents_and_archives",
    },
    {
        "bundle_key": "technical_web",
        "title": "Technik, Domain & Webspuren",
        "objective": "Domains, technische Profile und öffentliche Web-/GitHub-Spuren prüfen.",
        "categories": ["Domain", "Technisches Profil"],
        "source_mode": "non_intrusive_public_technical_osint",
    },
    {
        "bundle_key": "counter_evidence",
        "title": "Gegenbelege & Namensdoppler",
        "objective": "Widersprüche, Ausschlussmarker und mögliche Namensdoppler sichtbar machen.",
        "categories": ["Gegenbelege/Namensdoppler"],
        "source_mode": "counter_evidence_required_before_conclusions",
    },
]

CATEGORY_TO_BUNDLE: Dict[str, str] = {}
for bundle in SEARCH_BUNDLES:
    for category in bundle["categories"]:
        CATEGORY_TO_BUNDLE[category] = bundle["bundle_key"]

class UXConsolidationService:
    """Build 37.0: guided UI workspaces and bundled search categories.

    This service is deliberately deterministic and local. It does not run any
    searches; it groups already-created search tasks into analyst-friendly
    bundles and provides a six-workspace navigation model so the GUI no longer
    feels like a long row of unrelated tabs.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def seed_defaults(self) -> Dict[str, int]:
        ws_inserted = 0
        for idx, ws in enumerate(WORKSPACES, start=1):
            if not self.db.one("SELECT workspace_id FROM ui_workspaces WHERE workspace_key=?", [ws["workspace_key"]]):
                self.db.execute(
                    "INSERT INTO ui_workspaces(workspace_id,workspace_key,title,purpose,display_order,tabs_json,created_at,active) VALUES(?,?,?,?,?,?,?,?)",
                    [new_id("uxws"), ws["workspace_key"], ws["title"], ws["purpose"], idx, dumps(ws["tabs"]), now_ts(), 1],
                )
                ws_inserted += 1
        bundle_inserted = 0
        for idx, bundle in enumerate(SEARCH_BUNDLES, start=1):
            if not self.db.one("SELECT bundle_id FROM search_category_bundles WHERE bundle_key=?", [bundle["bundle_key"]]):
                self.db.execute(
                    "INSERT INTO search_category_bundles(bundle_id,bundle_key,title,objective,categories_json,source_mode,display_order,created_at,active) VALUES(?,?,?,?,?,?,?,?,?)",
                    [new_id("uxbundle"), bundle["bundle_key"], bundle["title"], bundle["objective"], dumps(bundle["categories"]), bundle["source_mode"], idx, now_ts(), 1],
                )
                bundle_inserted += 1
        self.audit.log("UX_CONSOLIDATION_DEFAULTS_SEEDED", "ux_consolidation", details={"workspaces_inserted": ws_inserted, "bundles_inserted": bundle_inserted})
        return {"workspaces_inserted": ws_inserted, "bundles_inserted": bundle_inserted}

    def workspaces(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM ui_workspaces WHERE active=1 ORDER BY display_order, title")
        if rows:
            return rows
        return WORKSPACES

    def search_bundles(self) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM search_category_bundles WHERE active=1 ORDER BY display_order, title")
        if rows:
            return rows
        return SEARCH_BUNDLES

    def bundle_options(self) -> List[str]:
        return ["Alle Suchbündel"] + [f"{b['bundle_key']} | {b['title']}" for b in self.search_bundles()]

    def bundle_key_for_category(self, category: str) -> str:
        return CATEGORY_TO_BUNDLE.get(category or "", "identity_core")

    def filter_tasks_by_bundle(self, tasks: List[Dict[str, Any]], bundle_key: str = "") -> List[Dict[str, Any]]:
        if not bundle_key:
            return tasks
        return [t for t in tasks if self.bundle_key_for_category(t.get("category", "")) == bundle_key]

    def search_bundle_dashboard(self, case_id: str) -> Dict[str, Any]:
        tasks = self.db.all("SELECT * FROM search_tasks WHERE case_id=?", [case_id]) if case_id else []
        review_items = self.db.all("SELECT * FROM review_items WHERE case_id=?", [case_id]) if case_id else []
        evidence_items = self.db.all("SELECT * FROM evidence_items WHERE case_id=?", [case_id]) if case_id else []
        bundles = []
        for b in self.search_bundles():
            key = b["bundle_key"]
            cats = set(CATEGORY_TO_BUNDLE.keys())
            bundle_tasks = self.filter_tasks_by_bundle(tasks, key)
            opened = sum(1 for t in bundle_tasks if t.get("status") in {"opened", "captured"})
            captured = sum(1 for t in bundle_tasks if t.get("status") == "captured")
            bundles.append({
                "bundle_key": key,
                "title": b["title"],
                "objective": b["objective"],
                "categories": b.get("categories_json", b.get("categories", [])),
                "tasks": len(bundle_tasks),
                "opened": opened,
                "captured": captured,
                "review_items": len(review_items),
                "evidence_items": len(evidence_items),
                "status": "ready" if bundle_tasks else "empty",
            })
        next_focus = "Recherchepakete aus Zielperson erzeugen" if not tasks else "Suchbündel auswählen und Treffer in Review/Evidence überführen"
        return {"case_id": case_id, "bundles": bundles, "task_total": len(tasks), "next_focus": next_focus}

    def workspace_dashboard(self, case_id: str = "") -> Dict[str, Any]:
        workspaces = self.workspaces()
        bundle_dash = self.search_bundle_dashboard(case_id) if case_id else {"bundles": [], "task_total": 0, "next_focus": "Fall auswählen"}
        return {
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "search_bundle_count": len(self.search_bundles()),
            "search_bundle_dashboard": bundle_dash,
            "design_decision": "Build 37.0 reduziert die Hauptnavigation auf sechs Arbeitsbereiche und bündelt Suchkategorien in sechs Recherchebündel.",
        }

    def persist_workspace_snapshot(self, case_id: str = "", notes: str = "") -> Dict[str, Any]:
        snap = self.workspace_dashboard(case_id)
        sid = new_id("uxsnap")
        self.db.execute(
            "INSERT INTO ux_workspace_snapshots(snapshot_id,case_id,snapshot_json,created_at,notes) VALUES(?,?,?,?,?)",
            [sid, case_id, dumps(snap), now_ts(), notes],
        )
        self.audit.log("UX_WORKSPACE_SNAPSHOT", "ux_workspace_snapshot", sid, case_id or None, {"workspace_count": snap["workspace_count"], "search_bundle_count": snap["search_bundle_count"]})
        snap["snapshot_id"] = sid
        return snap
