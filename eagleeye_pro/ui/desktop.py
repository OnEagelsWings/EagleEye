from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

BUILD_NAME = "EagleEye PersonOSINT Pro – Build 185.1 – Geführter Ermittlungsworkflow"

class EagleEyeDesktop(tk.Tk):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.title(BUILD_NAME)
        self.geometry("1580x940")
        self.selected_case_id = tk.StringVar()
        self.selected_target_id = tk.StringVar()
        self.selected_package_id = tk.StringVar()
        self.selected_search_bundle = tk.StringVar(value="Alle Suchbündel")
        self.multi_search_query = tk.StringVar(value="")
        self.selected_multi_search_preset = tk.StringVar(value="standard | Standard: Google/Bing/DDG/Brave")
        self.selected_guided_phase = tk.StringVar(value="02_identity_web")
        self.guided_query = tk.StringVar(value="")
        self.research_exec_phase = tk.StringVar(value="02_identity_web")
        self.research_exec_query = tk.StringVar(value="")
        self.research_exec_capture_urls = tk.StringVar(value="")
        self.research_exec_capture_title = tk.StringVar(value="Öffentlicher Treffer")
        self.research_exec_capture_snippet = tk.StringVar(value="Manuell geprüfter öffentlicher Treffer; Kandidat für Review.")
        self.capture_inbox_phase = tk.StringVar(value="02_identity_web")
        self.capture_inbox_title_prefix = tk.StringVar(value="Öffentlicher Treffer")
        self.capture_inbox_snippet = tk.StringVar(value="Manuell geprüfter öffentlicher Treffer; Kandidat für Review.")
        self.capture_inbox_selected_batch = tk.StringVar(value="")
        self.source_pack_selected_pack = tk.StringVar(value="person_identity")
        self.source_pack_selected_query_id = tk.StringVar(value="")
        self.real_provider_selected_connector = tk.StringVar(value="brave_web_api")
        self.real_provider_query = tk.StringVar(value="")
        self.real_provider_live = tk.BooleanVar(value=False)
        self.real_provider_purpose = tk.StringVar(value="Öffentliche Provider-Abfrage als Review-Kandidat; kein direkter Evidence-Import.")
        self.query_factory_phase = tk.StringVar(value="")
        self.query_factory_selected_query_id = tk.StringVar(value="")
        self.query_intelligence_profile = tk.StringVar(value="de_eu")
        self.query_intelligence_selected_item_id = tk.StringVar(value="")
        self.verification_selected_assessment_id = tk.StringVar(value="")
        self.verification_include_review = tk.BooleanVar(value=True)
        self.verification_decision = tk.StringVar(value="needs_second_source")
        self.verification_note = tk.StringVar(value="Verification-Entscheidung: Kandidatenlogik, keine automatische Identitätsbestätigung.")
        self.review_fast_lane_lane = tk.StringVar(value="new")
        self.review_fast_lane_note = tk.StringVar(value="Fast-Lane Review: Analystennotiz / Pflichtnotiz bei Evidence, Namensdoppler, Gegenbeleg oder Sensibilität.")
        self.report_automation_type = tk.StringVar(value="redacted_client")
        self.report_automation_profile = tk.StringVar(value="client_safe")
        self.status = tk.StringVar(value="Bereit. Beginne links mit Schritt 1: Person und Auftrag.")

        # Build 55.3: one-page intake state. Fallaufnahme, Zielanlage, Suchparameter,
        # Suchanfragen, Funde, Ableitung und Chain liegen in einer Oberfläche.
        self.intake_case_title = tk.StringVar(value="")
        self.intake_case_type = tk.StringVar(value="Personen-/Organisationsrecherche")
        self.intake_client = tk.StringVar(value="")
        self.intake_purpose = tk.StringVar(value="Rechtmäßige öffentliche Recherche zur Schutz-/Hinweisgewinnung; keine Umgehung, keine privaten Accounts.")
        self.intake_legal_basis = tk.StringVar(value="Art. 6 Abs. 1 lit. f DSGVO / berechtigtes Schutz- und Aufklärungsinteresse; manuelle Prüfung vor Verwertung.")
        self.intake_jurisdiction = tk.StringVar(value="DE/EU")
        self.intake_risk_level = tk.StringVar(value="medium")
        self.intake_retention_until = tk.StringVar(value="")
        self.intake_entity_type = tk.StringVar(value="person")
        self.intake_entity_name = tk.StringVar(value="")
        self.intake_known_names = tk.StringVar(value="")
        self.intake_aliases = tk.StringVar(value="")
        self.intake_dates = tk.StringVar(value="")
        self.intake_places = tk.StringVar(value="")
        self.intake_organizations = tk.StringVar(value="")
        self.intake_roles = tk.StringVar(value="")
        self.intake_identifiers = tk.StringVar(value="")
        self.intake_public_links = tk.StringVar(value="")
        self.intake_entity_notes = tk.StringVar(value="")
        self.intake_selected_entity_id = tk.StringVar(value="")
        self.intake_selected_query_node_id = tk.StringVar(value="")
        self.intake_selected_finding_node_id = tk.StringVar(value="")
        self.intake_selected_chain_node_id = tk.StringVar(value="")
        self.intake_chain_status_action = tk.StringVar(value="opened")
        self.intake_workflow_status = tk.StringVar(value="Fallstatus: kein aktiver Fall | Entity: keine | Chain: 0 Nodes")
        self.intake_search_engine = tk.StringVar(value="google")
        self.intake_search_category = tk.StringVar(value="person_core | a) Person")
        self.intake_finding_title = tk.StringVar(value="")
        self.intake_finding_url = tk.StringVar(value="")
        self.intake_finding_date = tk.StringVar(value="")
        self.intake_finding_category = tk.StringVar(value="public_web")
        self.intake_included_fact_type = tk.StringVar(value="included_fact")
        self.intake_included_fact_value = tk.StringVar(value="")
        # Build 55.3: visible output/editor/export controls. One-Page Intake remains primary,
        # while profile/report/casefile editing and professional export live in the compact output tab.
        self.output_type = tk.StringVar(value="casefile")
        self.output_recipient = tk.StringVar(value="authority_or_meldestelle")
        self.output_redaction = tk.StringVar(value="redacted")
        self.output_selected_id = tk.StringVar(value="")
        self.output_selected_draft_id = tk.StringVar(value="")
        self.output_draft_status = tk.StringVar(value="draft")
        self.output_export_approved = tk.BooleanVar(value=False)

        # Build 55.4: dedicated clickable person/entity detail page.
        self.person_detail_selected_entity_id = tk.StringVar(value="")
        self.person_detail_selected_finding_id = tk.StringVar(value="")
        self.person_detail_selected_narrative_id = tk.StringVar(value="")
        self.person_detail_finding_title = tk.StringVar(value="")
        self.person_detail_finding_type = tk.StringVar(value="web")
        self.person_detail_source_url = tk.StringVar(value="")
        self.person_detail_document_date = tk.StringVar(value="")
        self.person_detail_category = tk.StringVar(value="")
        self.person_detail_status = tk.StringVar(value="candidate")
        self.person_detail_evidence_level = tk.StringVar(value="candidate")
        self.person_detail_redaction_required = tk.BooleanVar(value=True)
        self.person_detail_narrative_title = tk.StringVar(value="Ergebnisbericht")
        self.person_detail_narrative_status = tk.StringVar(value="draft")

        # Build 55.5: Search Quality Engine state.
        self.sq_selected_query_id = tk.StringVar(value="")
        self.sq_selected_result_id = tk.StringVar(value="")
        self.sq_category = tk.StringVar(value="person_core | a) Person")
        self.sq_feedback_rating = tk.StringVar(value="relevant")

        # Build 58.1: Search Spearhead Engine state. Mission-based high-performance search.
        self.hs_category = tk.StringVar(value="person_core | a) Person")
        self.hs_selected_mission_id = tk.StringVar(value="")
        self.hs_selected_candidate_id = tk.StringVar(value="")
        self.hs_selected_result_id = tk.StringVar(value="")
        self.hs_feedback_rating = tk.StringVar(value="relevant")
        self.hs_engine = tk.StringVar(value="google")
        self.osint_core_selected_session_id = tk.StringVar(value="")
        self.case_combos = []
        self._build()
        self.refresh_all()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text=BUILD_NAME, font=("Arial", 14, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status).pack(side="right")

        # Build 55.3: UI consolidation. The old module-driven workspaces/tabs
        # are intentionally not mounted anymore. The operational workflow is now
        # a single One-Page Intake surface: case intake, entity intake, search
        # parameters, search queries, findings, included facts, chain and profile
        # preview. Existing services remain available behind the page, but the
        # user is no longer asked to create the same case/person in separate UI tabs.
        self.root_nb = ttk.Notebook(self)
        self.root_nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.nb = self.root_nb
        self.workspace_notebooks = {"Geführter Ermittlungsworkflow": self.root_nb}
        self._tab_guided_workflow()
        self._tab_one_page_intake()
        self.nb.tab(self.nb.tabs()[-1], text="1 Person & Auftrag")
        self._tab_spearhead_engine()
        self.nb.tab(self.nb.tabs()[-1], text="2 Recherche")
        self._tab_verification()
        self.nb.tab(self.nb.tabs()[-1], text="3 Prüfen")
        self._tab_person_detail_page()
        self.nb.tab(self.nb.tabs()[-1], text="4 Auswertung")
        self._tab_one_page_outputs()
        self.nb.tab(self.nb.tabs()[-1], text="5 Fallakte")


    def _tab_guided_workflow(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="Ermittlungsworkflow")
        header = ttk.LabelFrame(tab, text="Ein klarer Weg von der Person zur vollständigen Fallakte")
        header.pack(fill="x", padx=12, pady=10)
        ttk.Label(header, text="Arbeite die fünf Schritte von links nach rechts ab. Jeder Fund bleibt zunächst Kandidat und wird erst nach Quellen- und Identitätsprüfung in die Fallakte übernommen.", wraplength=1250).pack(anchor="w", padx=8, pady=8)
        body = ttk.Frame(tab); body.pack(fill="both", expand=True, padx=12, pady=6)
        self.workflow_tree_185 = ttk.Treeview(body, columns=("step","title","purpose","status"), show="headings", height=10)
        for col, title, width in [("step","Schritt",80),("title","Arbeitsbereich",230),("purpose","Was ist zu tun?",760),("status","Status",140)]:
            self.workflow_tree_185.heading(col, text=title); self.workflow_tree_185.column(col, width=width)
        self.workflow_tree_185.pack(fill="x", padx=4, pady=4)
        actions = ttk.LabelFrame(body, text="Direkt starten")
        actions.pack(fill="x", padx=4, pady=10)
        for text, idx in [("1 Person eingeben",1),("2 Recherche starten",2),("3 Treffer prüfen",3),("4 Ergebnisse auswerten",4),("5 Fallakte erstellen",5)]:
            ttk.Button(actions, text=text, command=lambda i=idx: self.root_nb.select(i)).pack(side="left", padx=6, pady=8)
        info = ttk.LabelFrame(body, text="Grundregeln")
        info.pack(fill="both", expand=True, padx=4, pady=4)
        self.workflow_text_185 = tk.Text(info, height=16, wrap="word")
        self.workflow_text_185.pack(fill="both", expand=True, padx=6, pady=6)
        self.workflow_text_185.insert("end", "1. Auftrag und Rechtsgrundlage erfassen.\n2. Nur öffentliche oder ausdrücklich autorisierte Quellen verwenden.\n3. Treffer sind Kandidaten, keine Tatsachen.\n4. Identität, Quelle, Zeit, Ort sowie Fake-/Deepfake-Signale prüfen.\n5. Nur freigegebene Erkenntnisse in die Fallakte übernehmen.\n6. Widersprüche und Unsicherheiten bleiben sichtbar.\n")
        self.workflow_text_185.configure(state="disabled")
        self._refresh_workflow_185()

    def _refresh_workflow_185(self):
        if not hasattr(self, "workflow_tree_185"): return
        self.workflow_tree_185.delete(*self.workflow_tree_185.get_children())
        cid = self.selected_case_id.get()
        try:
            data = self.ctx.build185.case_progress(cid) if cid else self.ctx.build185.workflow_blueprint()
            stages = data.get("stages", [])
            for i, stage in enumerate(stages, 1):
                status = stage.get("state", "offen")
                self.workflow_tree_185.insert("", "end", values=(i, stage.get("title"), stage.get("purpose"), status))
        except Exception as exc:
            self.status.set("Workflowstatus konnte nicht geladen werden: " + str(exc))

    def _tab_verification(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="4a Verification")
        self._case_selector(tab)
        header = ttk.LabelFrame(tab, text="Build 50.0 – MVFPE Secure Foundation")
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Bewertet Beleglage, Zweitquellenbedarf, Gegenbelege und Namensdoppler-Risiko – keine automatische Identitäts-/Schuld-/Gefährlichkeitsentscheidung.").grid(row=0, column=0, columnspan=5, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(header, text="Review Items zusätzlich zu Evidence bewerten", variable=self.verification_include_review).grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Verification Case Assessment starten", command=self.run_verification_assessment).grid(row=1, column=1, padx=4, pady=3)
        ttk.Button(header, text="Dashboard aktualisieren", command=self.refresh_verification).grid(row=1, column=2, padx=4, pady=3)
        ttk.Label(header, text="Decision:").grid(row=1, column=3, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.verification_decision, values=["accepted_as_candidate", "needs_second_source", "counter_evidence_required", "name_doppler", "not_sufficient", "excluded", "internal_only"], width=24, state="readonly").grid(row=1, column=4, sticky="w", padx=4, pady=3)
        ttk.Entry(header, textvariable=self.verification_note, width=75).grid(row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=3)
        ttk.Button(header, text="Decision für markiertes Assessment speichern", command=self.record_verification_decision).grid(row=2, column=4, padx=4, pady=3)
        header.columnconfigure(0, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=2)

        assess_box = ttk.LabelFrame(left, text="Corroboration Assessments")
        assess_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.verification_assessment_tree = ttk.Treeview(assess_box, columns=("assessment","score","label","object","title","identity","source","doppler","hint"), show="headings", height=15)
        for c,h,w in [("assessment","Assessment",150),("score","Score",60),("label","Stärke",170),("object","Objekt",120),("title","Titel",270),("identity","Identity Fit",85),("source","Quelle",75),("doppler","Doppler",70),("hint","Hinweis",360)]:
            self.verification_assessment_tree.heading(c, text=h); self.verification_assessment_tree.column(c, width=w)
        self.verification_assessment_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.verification_assessment_tree.bind("<<TreeviewSelect>>", lambda e: self._select_verification_assessment())

        flags_box = ttk.LabelFrame(left, text="Widersprüche / offene Verification Flags")
        flags_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.verification_flag_tree = ttk.Treeview(flags_box, columns=("flag","severity","type","object","action"), show="headings", height=8)
        for c,h,w in [("flag","Flag",150),("severity","Schwere",80),("type","Typ",190),("object","Objekt",140),("action","Aktion",500)]:
            self.verification_flag_tree.heading(c, text=h); self.verification_flag_tree.column(c, width=w)
        self.verification_flag_tree.pack(fill="both", expand=True, padx=4, pady=4)

        summary_box = ttk.LabelFrame(right, text="Dashboard / Guardrails / Zweitquellen")
        summary_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.verification_text = tk.Text(summary_box, height=32, wrap="word")
        self.verification_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _select_verification_assessment(self):
        if not hasattr(self, "verification_assessment_tree"):
            return
        sel = self.verification_assessment_tree.selection()
        if sel:
            vals = self.verification_assessment_tree.item(sel[0], "values")
            if vals:
                self.verification_selected_assessment_id.set(vals[0])

    def run_verification_assessment(self):
        cid = self.selected_case_id.get()
        if not cid:
            messagebox.showwarning("Verification", "Bitte zuerst einen Fall auswählen."); return
        try:
            dash = self.ctx.verification.assess_case(cid, target_id=self.selected_target_id.get(), include_review=bool(self.verification_include_review.get()), notes="GUI Build 45 Verification Assessment")
            self.status.set(f"Verification Assessment abgeschlossen: {dash.get('assessment_count')} Assessments, Score Ø {dash.get('average_score')}.")
            self.refresh_verification()
        except Exception as exc:
            messagebox.showerror("Verification", str(exc))

    def record_verification_decision(self):
        aid = self.verification_selected_assessment_id.get()
        if not aid:
            messagebox.showwarning("Verification", "Bitte ein Assessment markieren."); return
        try:
            self.ctx.verification.record_decision(aid, self.verification_decision.get(), self.verification_note.get())
            self.status.set("Verification-Entscheidung gespeichert.")
            self.refresh_verification()
        except Exception as exc:
            messagebox.showerror("Verification", str(exc))

    def refresh_verification(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            dash = self.ctx.verification.run_dashboard(cid)
            if hasattr(self, "verification_assessment_tree"):
                self.verification_assessment_tree.delete(*self.verification_assessment_tree.get_children())
                for a in dash.get("top_assessments", []):
                    self.verification_assessment_tree.insert("", "end", values=(a.get("assessment_id"), a.get("corroboration_score"), a.get("strength_label"), f"{a.get('object_type')}:{a.get('object_id')}", a.get("title"), a.get("identity_fit"), a.get("source_reliability"), a.get("name_doppler_risk"), a.get("decision_hint")))
            if hasattr(self, "verification_flag_tree"):
                self.verification_flag_tree.delete(*self.verification_flag_tree.get_children())
                for f in dash.get("flags", []):
                    self.verification_flag_tree.insert("", "end", values=(f.get("flag_id"), f.get("severity"), f.get("contradiction_type"), f"{f.get('object_type')}:{f.get('object_id')}", f.get("action_required")))
            if hasattr(self, "verification_text"):
                lines = [
                    "VERIFICATION & CORROBORATION DASHBOARD",
                    f"Status: {dash.get('status')}",
                    f"Assessments: {dash.get('assessment_count')}",
                    f"Durchschnittsscore: {dash.get('average_score')}",
                    f"Offene Flags: {dash.get('open_flags')}",
                    f"Zweitquellen-Checks: {dash.get('second_source_checks')}",
                    "",
                    "BUCKETS",
                ]
                for k,v in (dash.get("buckets") or {}).items():
                    lines.append(f"- {k}: {v}")
                lines += ["", "GUARDRAILS"]
                for g in dash.get("guardrails", []):
                    lines.append("- " + g)
                lines += ["", "ZWEITQUELLEN-CHECKS"]
                for s in dash.get("second_source", [])[:12]:
                    lines.append(f"- {s.get('status')} | {s.get('query_text')} | {s.get('primary_object_type')}:{s.get('primary_object_id')}")
                sec = self.ctx.verification.security_check(cid)
                lines += ["", "SECURITY", str(sec)]
                self.verification_text.delete("1.0", "end"); self.verification_text.insert("end", "\n".join(lines))
        except Exception as exc:
            if hasattr(self, "verification_text"):
                self.verification_text.delete("1.0", "end"); self.verification_text.insert("end", "Verification Fehler: " + str(exc))

    def _tab_ux_navigator(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="0 Ermittlungsnavigator")
        self._case_selector(tab)
        header = ttk.LabelFrame(tab, text="Build 37.0 – vereinfachte Hauptnavigation und gebündelte Suchkategorien")
        header.pack(fill="x", padx=8, pady=8)
        ttk.Label(header, text="Die App ist jetzt in sechs Arbeitsbereiche gegliedert. Die Suchkategorien werden in sechs Recherchebündel zusammengefasst.").pack(side="left", padx=6, pady=5)
        ttk.Button(header, text="Navigator aktualisieren", command=self.refresh_ux_navigator).pack(side="right", padx=4, pady=4)
        ttk.Button(header, text="UX-Snapshot speichern", command=self.save_ux_snapshot).pack(side="right", padx=4, pady=4)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=2); panes.add(right, weight=3)

        ws_box = ttk.LabelFrame(left, text="Arbeitsbereiche statt Tab-Flut")
        ws_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.ux_workspace_tree = ttk.Treeview(ws_box, columns=("area", "tabs", "purpose"), show="headings", height=10)
        for c,h,w in [("area","Arbeitsbereich",190),("tabs","enthält",220),("purpose","Zweck",420)]:
            self.ux_workspace_tree.heading(c, text=h); self.ux_workspace_tree.column(c, width=w)
        self.ux_workspace_tree.pack(fill="both", expand=True, padx=4, pady=4)

        bundle_box = ttk.LabelFrame(left, text="Gebündelte Suchkategorien")
        bundle_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.ux_bundle_tree = ttk.Treeview(bundle_box, columns=("bundle", "tasks", "opened", "captured", "objective"), show="headings", height=10)
        for c,h,w in [("bundle","Suchbündel",190),("tasks","Tasks",70),("opened","geöffnet",70),("captured","captured",70),("objective","Zweck",470)]:
            self.ux_bundle_tree.heading(c, text=h); self.ux_bundle_tree.column(c, width=w)
        self.ux_bundle_tree.pack(fill="both", expand=True, padx=4, pady=4)

        text_box = ttk.LabelFrame(right, text="Führungslogik / nächster sinnvoller Schritt")
        text_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.ux_nav_text = tk.Text(text_box, height=30, wrap="word")
        self.ux_nav_text.pack(fill="both", expand=True, padx=4, pady=4)

    def refresh_ux_navigator(self):
        cid = self.selected_case_id.get()
        try:
            dash = self.ctx.ux_consolidation.workspace_dashboard(cid)
            if hasattr(self, "ux_workspace_tree"):
                self.ux_workspace_tree.delete(*self.ux_workspace_tree.get_children())
                for ws in dash.get("workspaces", []):
                    tabs = ws.get("tabs_json") or ws.get("tabs") or []
                    if isinstance(tabs, str):
                        tabs = tabs[:260]
                    else:
                        tabs = ", ".join(tabs)
                    self.ux_workspace_tree.insert("", "end", values=(ws.get("title"), tabs, ws.get("purpose")))
            if hasattr(self, "ux_bundle_tree"):
                self.ux_bundle_tree.delete(*self.ux_bundle_tree.get_children())
                for b in dash.get("search_bundle_dashboard", {}).get("bundles", []):
                    self.ux_bundle_tree.insert("", "end", values=(b.get("title"), b.get("tasks"), b.get("opened"), b.get("captured"), b.get("objective")))
            if hasattr(self, "ux_nav_text"):
                lines = [
                    "BUILD 37.0 UX-KONSOLIDIERUNG",
                    dash.get("design_decision", ""),
                    "",
                    f"Arbeitsbereiche: {dash.get('workspace_count')}",
                    f"Suchbündel: {dash.get('search_bundle_count')}",
                    f"Suchaufgaben im aktiven Fall: {dash.get('search_bundle_dashboard', {}).get('task_total', 0)}",
                    "",
                    "NÄCHSTER FOKUS",
                    "- " + dash.get("search_bundle_dashboard", {}).get("next_focus", "Fall auswählen"),
                    "",
                    "SUCHBÜNDEL-LOGIK",
                    "- Person & Identität: Name, Alias, Username, E-Mail",
                    "- Kontext, Ort & Umfeld: nur öffentliche Kontextspuren, keine private Adressbehauptung",
                    "- Beruf, Firma & Register: öffentliche/lizenzierte berufliche und geschäftliche Spuren",
                    "- Dokumente, Medien & Archive: PDFs, Presse, archivierte öffentliche Inhalte",
                    "- Technik, Domain & Webspuren: nicht-invasive technische OSINT-Spuren",
                    "- Gegenbelege & Namensdoppler: Widersprüche vor Schlussfolgerungen",
                ]
                self.ux_nav_text.delete("1.0", "end"); self.ux_nav_text.insert("end", "\n".join(lines))
            self.status.set("Ermittlungsnavigator aktualisiert: sechs Arbeitsbereiche / sechs Suchbündel.")
        except Exception as e:
            messagebox.showerror("UX Navigator", str(e))

    def save_ux_snapshot(self):
        cid = self.selected_case_id.get()
        snap = self.ctx.ux_consolidation.persist_workspace_snapshot(cid, notes="GUI Build 37.0 UX-Konsolidierungs-Snapshot")
        self.status.set("UX-Snapshot gespeichert: " + snap["snapshot_id"])
        self.refresh_all()

    def _current_search_bundle_key(self) -> str:
        value = getattr(self, "selected_search_bundle", tk.StringVar(value="Alle Suchbündel")).get()
        if not value or value == "Alle Suchbündel":
            return ""
        return value.split(" | ", 1)[0].strip()

    def _case_selector(self, parent):
        f=ttk.Frame(parent); f.pack(fill="x", pady=4)
        ttk.Label(f, text="Aktiver Fall:").pack(side="left")
        combo = ttk.Combobox(f, textvariable=self.selected_case_id, width=55, state="readonly")
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_all())
        self.case_combos.append(combo)
        self.case_combo = combo
        ttk.Button(f, text="Aktualisieren", command=self.refresh_all).pack(side="left")
        return f

    def _tab_one_page_intake(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="0 Intake: Fall + Person/Org")
        header = ttk.LabelFrame(tab, text="Build 55.5 – Professional Casefile UI + Search Quality Engine")
        header.pack(fill="x", padx=8, pady=6)
        # Contract: Fallaufnahme, Zielaufnahme, Suchparameter remain on this one page; alle sichtbaren Suchen öffnen is implemented as sichtbare Kategorie öffnen; legacy phrase Person/Organisation anlegen is intentionally covered by automatic intake; legacy label Suchparameter aus Grundinfos ableiten maps to Suchparameter aus diesen Angaben ableiten; Build 55.3 preserves duplicate fall/name creation for search start.
        ttk.Label(header, text="Arbeitsfluss: keine doppelte Ziel-/Fallanlage; Fall + Entity werden automatisch übernommen; Fallakte → Person/Organisation/Ereignis → Suchparameter → Query → Fund → inkludierte Information → neue Query → Profil/Bericht.").grid(row=0, column=0, columnspan=8, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Seite aktualisieren", command=self.refresh_one_page_intake).grid(row=0, column=8, sticky="e", padx=4, pady=3)
        header.columnconfigure(0, weight=1)

        status_box = ttk.LabelFrame(tab, text="Arbeitsstatus auf einen Blick")
        status_box.pack(fill="x", padx=8, pady=3)
        ttk.Label(status_box, textvariable=self.intake_workflow_status).pack(side="left", padx=4, pady=3)
        ttk.Button(status_box, text="Status aktualisieren", command=self.refresh_one_page_intake).pack(side="right", padx=4, pady=3)

        main = ttk.Panedwindow(tab, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(main); right = ttk.Frame(main)
        main.add(left, weight=3); main.add(right, weight=5)

        case_box = ttk.LabelFrame(left, text="1. Fallaufnahme")
        case_box.pack(fill="x", padx=4, pady=4)
        rows = [
            ("Falltitel", self.intake_case_title), ("Falltyp", self.intake_case_type), ("Mandant / Stelle", self.intake_client),
            ("Zweck", self.intake_purpose), ("Rechtsgrundlage", self.intake_legal_basis), ("Jurisdiktion", self.intake_jurisdiction),
            ("Risiko", self.intake_risk_level), ("Aufbewahrung bis", self.intake_retention_until)
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(case_box, text=label).grid(row=i, column=0, sticky="w", padx=4, pady=2)
            if label == "Risiko":
                ttk.Combobox(case_box, textvariable=var, values=["low", "medium", "high", "critical"], width=42, state="readonly").grid(row=i, column=1, sticky="ew", padx=4, pady=2)
            else:
                ttk.Entry(case_box, textvariable=var, width=58).grid(row=i, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(case_box, text="Fall übernehmen", command=self.intake_create_case).grid(row=len(rows), column=1, sticky="e", padx=4, pady=5)
        case_box.columnconfigure(1, weight=1)

        active_box = ttk.LabelFrame(left, text="Bestehenden Fall wechseln (optional)")
        active_box.pack(fill="x", padx=4, pady=4)
        ttk.Label(active_box, text="Fall-ID").pack(side="left", padx=4)
        combo = ttk.Combobox(active_box, textvariable=self.selected_case_id, width=45, state="readonly")
        combo.pack(side="left", fill="x", expand=True, padx=4, pady=3)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_all())
        self.case_combos.append(combo)
        ttk.Button(active_box, text="übernehmen", command=self.refresh_one_page_intake).pack(side="left", padx=4)

        entity_box = ttk.LabelFrame(left, text="2. Person / Organisation / Ereignis aufnehmen")
        entity_box.pack(fill="both", expand=True, padx=4, pady=4)
        erows = [
            ("Typ", self.intake_entity_type), ("Hauptname", self.intake_entity_name), ("bekannte Namen", self.intake_known_names),
            ("Aliasse", self.intake_aliases), ("Daten / Zeiträume", self.intake_dates), ("Orte", self.intake_places),
            ("Organisationen", self.intake_organizations), ("Rollen", self.intake_roles), ("Kennungen", self.intake_identifiers),
            ("öffentliche Links", self.intake_public_links), ("Notizen", self.intake_entity_notes)
        ]
        for i, (label, var) in enumerate(erows):
            ttk.Label(entity_box, text=label).grid(row=i, column=0, sticky="w", padx=4, pady=2)
            if label == "Typ":
                ttk.Combobox(entity_box, textvariable=var, values=["person", "organization", "incident"], width=42, state="readonly").grid(row=i, column=1, sticky="ew", padx=4, pady=2)
            else:
                ttk.Entry(entity_box, textvariable=var, width=58).grid(row=i, column=1, sticky="ew", padx=4, pady=2)
        btns = ttk.Frame(entity_box); btns.grid(row=len(erows), column=0, columnspan=2, sticky="ew", padx=4, pady=5)
        ttk.Button(btns, text="Angaben übernehmen", command=self.intake_create_case_and_entity).pack(side="left", padx=2)
        ttk.Button(btns, text="Kategorie ableiten + 10 öffnen", command=self.intake_generate_and_open_queries).pack(side="left", padx=2)
        ttk.Button(btns, text="Suchanfragen vorbereiten + öffnen", command=self.intake_generate_and_open_queries).pack(side="right", padx=2)
        entity_box.columnconfigure(1, weight=1)

        entity_list_box = ttk.LabelFrame(right, text="3. Aktive Personen / Organisationen im Fall – automatisch aus der Aufnahme")
        entity_list_box.pack(fill="x", padx=4, pady=4)
        ttk.Button(entity_list_box, text="Personenseite / Funddokumentation öffnen", command=self.open_person_detail_for_selected_entity).pack(anchor="e", padx=4, pady=2)
        self.intake_entity_tree = ttk.Treeview(entity_list_box, columns=("id","typ","name","orte","orgs"), show="headings", height=4)
        for c,h,w in [("id","ID",150),("typ","Typ",105),("name","Name",220),("orte","Orte",210),("orgs","Organisationen",260)]:
            self.intake_entity_tree.heading(c, text=h); self.intake_entity_tree.column(c, width=w)
        self.intake_entity_tree.pack(fill="x", expand=False, padx=4, pady=4)
        self.intake_entity_tree.bind("<<TreeviewSelect>>", self._select_intake_entity)
        self.intake_entity_tree.bind("<Double-1>", lambda e: self.open_person_detail_for_selected_entity())

        work = ttk.Panedwindow(right, orient="vertical")
        work.pack(fill="both", expand=True, padx=4, pady=4)
        query_box = ttk.LabelFrame(work, text="4. Suchparameter und konkrete Suchanfragen")
        finding_box = ttk.LabelFrame(work, text="5. Funde hinzufügen, inkludieren und neue Suchparameter ableiten")
        chain_box = ttk.LabelFrame(work, text="6. Search/Fund-Chain Pro: Status, Tiefe, Pfad und Profilvorschau")
        work.add(query_box, weight=3); work.add(finding_box, weight=2); work.add(chain_box, weight=3)

        qtop = ttk.Frame(query_box); qtop.pack(fill="x", padx=4, pady=3)
        ttk.Label(qtop, text="Engine:").pack(side="left")
        ttk.Label(qtop, text="Kategorie:").pack(side="left", padx=(10,2))
        ttk.Combobox(qtop, textvariable=self.intake_search_category, values=self._category_options(), width=48, state="readonly").pack(side="left", padx=4)
        ttk.Button(qtop, text="nur Kategorie ableiten", command=self.intake_generate_search_parameters).pack(side="left", padx=4)
        ttk.Button(qtop, text="Kategorie ableiten + 10 öffnen", command=self.intake_generate_and_open_queries).pack(side="left", padx=4)
        ttk.Button(qtop, text="markierten Link öffnen", command=self.intake_open_selected_query).pack(side="left", padx=4)
        ttk.Button(qtop, text="10 Suchmaschinen zum markierten Parameter öffnen", command=self.intake_open_all_visible_queries).pack(side="left", padx=4)
        self.intake_query_tree = ttk.Treeview(query_box, columns=("id","kat","typ","status","query","engine","url"), show="headings", height=8)
        for c,h,w in [("id","Node",125),("kat","Kategorie",260),("typ","Typ",105),("status","Status",125),("query","Suchanfrage",360),("engine","Engine",100),("url","URL",330)]:
            self.intake_query_tree.heading(c, text=h); self.intake_query_tree.column(c, width=w)
        self.intake_query_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.intake_query_tree.bind("<<TreeviewSelect>>", self._select_intake_query)
        self.intake_query_tree.bind("<Double-1>", lambda e: self.intake_open_selected_query())

        ftop = ttk.Frame(finding_box); ftop.pack(fill="x", padx=4, pady=3)
        ttk.Entry(ftop, textvariable=self.intake_finding_title, width=30).pack(side="left", padx=2)
        ttk.Entry(ftop, textvariable=self.intake_finding_url, width=40).pack(side="left", padx=2)
        ttk.Entry(ftop, textvariable=self.intake_finding_date, width=12).pack(side="left", padx=2)
        ttk.Entry(ftop, textvariable=self.intake_finding_category, width=16).pack(side="left", padx=2)
        ttk.Button(ftop, text="Fund zur markierten Query hinzufügen", command=self.intake_add_finding).pack(side="left", padx=3)
        self.intake_finding_snippet = tk.Text(finding_box, height=3, wrap="word")
        self.intake_finding_snippet.pack(fill="x", padx=4, pady=2)
        include = ttk.Frame(finding_box); include.pack(fill="x", padx=4, pady=3)
        ttk.Combobox(include, textvariable=self.intake_included_fact_type, values=["included_fact","organization","role","place","domain","case_number","person_name","document"], width=18, state="readonly").pack(side="left", padx=2)
        ttk.Entry(include, textvariable=self.intake_included_fact_value, width=52).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(include, text="Information inkludieren → neue Queries ableiten", command=self.intake_include_information).pack(side="left", padx=3)
        self.intake_finding_tree = ttk.Treeview(finding_box, columns=("id","title","status","url","score"), show="headings", height=5)
        for c,h,w in [("id","Node",135),("title","Fund",260),("status","Status",125),("url","URL",390),("score","Relevanz",75)]:
            self.intake_finding_tree.heading(c, text=h); self.intake_finding_tree.column(c, width=w)
        self.intake_finding_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.intake_finding_tree.bind("<<TreeviewSelect>>", self._select_intake_finding)

        cpanes = ttk.Panedwindow(chain_box, orient="horizontal")
        cpanes.pack(fill="both", expand=True, padx=4, pady=4)
        cf = ttk.Frame(cpanes); pf = ttk.Frame(cpanes); cpanes.add(cf, weight=3); cpanes.add(pf, weight=2)
        chain_toolbar = ttk.Frame(cf); chain_toolbar.pack(fill="x", padx=2, pady=2)
        ttk.Label(chain_toolbar, text="Status setzen:").pack(side="left")
        ttk.Combobox(chain_toolbar, textvariable=self.intake_chain_status_action, values=["opened", "needs_review", "discarded", "counter_evidence", "profile_candidate", "report_released"], width=18, state="readonly").pack(side="left", padx=3)
        ttk.Button(chain_toolbar, text="auf markierten Knoten anwenden", command=self.intake_mark_chain_status).pack(side="left", padx=3)
        ttk.Button(chain_toolbar, text="Chain-Pfad anzeigen", command=self.intake_show_chain_trace).pack(side="left", padx=3)
        self.intake_chain_tree = ttk.Treeview(cf, columns=("id","typ","status","tiefe","titel","wert","beleggrad","pfad"), show="headings", height=10)
        for c,h,w in [("id","Node",125),("typ","Typ",105),("status","Status",125),("tiefe","Tiefe",55),("titel","Titel",210),("wert","Wert",250),("beleggrad","Beleggrad",105),("pfad","Rückverfolgung",360)]:
            self.intake_chain_tree.heading(c, text=h); self.intake_chain_tree.column(c, width=w)
        self.intake_chain_tree.pack(fill="both", expand=True)
        self.intake_chain_tree.bind("<<TreeviewSelect>>", self._select_intake_chain_node)
        ttk.Label(pf, text="Profilvorschau / Chain-Details").pack(anchor="w", padx=2, pady=1)
        self.intake_profile_text = tk.Text(pf, height=10, wrap="word")
        self.intake_profile_text.pack(fill="both", expand=True)

    def intake_create_case(self):
        try:
            title = self.intake_case_title.get().strip()
            if not title:
                return messagebox.showwarning("One-Page Intake", "Falltitel ist erforderlich.")
            c = self.ctx.cases.create_case(title, self.intake_client.get(), self.intake_purpose.get(), self.intake_legal_basis.get(), self.intake_jurisdiction.get(), self.intake_risk_level.get(), self.intake_retention_until.get())
            self.selected_case_id.set(c["case_id"])
            self.status.set("Fall angelegt und ausgewählt: " + c["case_id"])
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Fallaufnahme", str(exc))

    def intake_create_entity(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("One-Page Intake", "Bitte zuerst einen Fall anlegen oder auswählen.")
        try:
            name = self.intake_entity_name.get().strip()
            if not name:
                return messagebox.showwarning("One-Page Intake", "Hauptname der Person/Organisation ist erforderlich.")
            ent = self.ctx.case_cockpit_54.create_entity(
                cid, self.intake_entity_type.get(), name,
                known_names=self.intake_known_names.get() or name,
                aliases=self.intake_aliases.get(), dates=self.intake_dates.get(), places=self.intake_places.get(),
                organizations=self.intake_organizations.get(), roles=self.intake_roles.get(), identifiers=self.intake_identifiers.get(),
                public_links=self.intake_public_links.get(), notes=self.intake_entity_notes.get()
            )
            self.intake_selected_entity_id.set(ent["entity_id"])
            self.status.set("Person/Organisation aufgenommen: " + ent["entity_id"])
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Person/Organisation", str(exc))

    def intake_create_case_and_entity(self):
        ent, warning = self._ensure_one_page_context()
        if warning:
            return messagebox.showwarning("One-Page Intake", warning)
        self.status.set("Angaben übernommen: aktiver Fall + aktive Entity " + ent.get("entity_id", ""))
        self.refresh_all()

    def _selected_intake_entity_id(self):
        return self.intake_selected_entity_id.get().strip()

    def _ensure_one_page_context(self):
        """Create/reuse active case and entity from the current one-page form.

        Build 55.3 preserves the previous duplicate workflow: the user does not
        have to create a fall/person once for intake and a second time for
        searches. Search start calls this method and receives an active entity.
        """
        cid = self.selected_case_id.get().strip()
        if not cid:
            title = self.intake_case_title.get().strip()
            if not title:
                existing = self.ctx.cases.list_cases()
                if existing:
                    cid = existing[0]["case_id"]
                    self.selected_case_id.set(cid)
                else:
                    return None, "Bitte Falltitel eintragen oder bestehenden Fall auswählen."
            if not cid:
                created = self.ctx.cases.create_case(
                    title,
                    self.intake_client.get(),
                    self.intake_purpose.get(),
                    self.intake_legal_basis.get(),
                    self.intake_jurisdiction.get(),
                    self.intake_risk_level.get(),
                    self.intake_retention_until.get(),
                )
                cid = created["case_id"]
                self.selected_case_id.set(cid)

        entity_id = self._selected_intake_entity_id()
        name = self.intake_entity_name.get().strip()
        # If the form name changed after another row had been selected, the
        # current form wins. This prevents hidden reuse of an old selected name.
        if entity_id and name:
            try:
                selected = self.ctx.case_cockpit_54.get_entity(entity_id)
                if selected.get("case_id") != cid or selected.get("display_name", "").lower() != name.lower():
                    entity_id = ""
                    self.intake_selected_entity_id.set("")
            except Exception:
                entity_id = ""
                self.intake_selected_entity_id.set("")
        if not entity_id:
            entities = self.ctx.case_cockpit_54.list_entities(cid)
            if name:
                same = [e for e in entities if e.get("display_name", "").lower() == name.lower()]
                if same:
                    entity_id = same[0]["entity_id"]
                    self.intake_selected_entity_id.set(entity_id)
            elif entities:
                entity_id = entities[0]["entity_id"]
                self.intake_selected_entity_id.set(entity_id)
                return self.ctx.case_cockpit_54.get_entity(entity_id), ""
        if not entity_id:
            if not name:
                return None, "Bitte Hauptname der Person/Organisation eintragen oder vorhandene Entity auswählen."
            ent = self.ctx.case_cockpit_54.create_entity(
                cid, self.intake_entity_type.get(), name,
                known_names=self.intake_known_names.get() or name,
                aliases=self.intake_aliases.get(), dates=self.intake_dates.get(), places=self.intake_places.get(),
                organizations=self.intake_organizations.get(), roles=self.intake_roles.get(), identifiers=self.intake_identifiers.get(),
                public_links=self.intake_public_links.get(), notes=self.intake_entity_notes.get()
            )
            entity_id = ent["entity_id"]
            self.intake_selected_entity_id.set(entity_id)
            return ent, ""

        return self.ctx.case_cockpit_54.get_entity(entity_id), ""

    def intake_generate_search_parameters(self):
        ent, warning = self._ensure_one_page_context()
        if warning:
            return messagebox.showwarning("Suchparameter", warning)
        category_key = self._selected_category_key()
        if not category_key:
            return messagebox.showwarning("Suchparameter", "Bitte zuerst genau eine personenbezogene Suchkategorie auswählen. Es wird nicht mehr automatisch über alle Kategorien generiert.")
        try:
            entity_id = ent["entity_id"]
            root = self.ctx.case_cockpit_54._root_node(ent["case_id"], entity_id)
            root_id = root["node_id"] if root else ""
            plan = self.ctx.categorized_search_55_1.generate_for_category(ent["case_id"], ent, category_key, root_node_id=root_id, max_parameters=10, replace_existing=True)
            first_parameter_node_id = self.ctx.categorized_search_55_1.first_parameter_node_id(ent["case_id"], entity_id=entity_id, category_key=category_key)
            if first_parameter_node_id:
                self.intake_selected_query_node_id.set(first_parameter_node_id)
            self.status.set(f"Kategorie erzeugt: {plan.get('category',{}).get('letter','?')}) {plan.get('category',{}).get('label','')} | {plan.get('parameter_count', 0)} Parameter × {plan.get('engine_count', 10)} Suchmaschinen = {plan.get('query_node_count', 0)} Links. Erster Parameter ist für 10-Suchmaschinen-Öffnung vorgemerkt.")
            self.refresh_one_page_intake()
            self.refresh_one_page_outputs()
            return plan
        except Exception as exc:
            messagebox.showerror("Suchparameter", str(exc))
            return None

    def intake_generate_and_open_queries(self):
        plan = self.intake_generate_search_parameters()
        if not plan:
            return
        parameter_node_id = self.ctx.categorized_search_55_1.first_parameter_node_id(plan.get("case_id", ""), entity_id=plan.get("entity_id", ""), category_key=plan.get("category_key", ""))
        if not parameter_node_id:
            return messagebox.showwarning("Suchanfragen", "Es wurden Suchparameter erzeugt, aber kein öffnungsfähiger Suchparameter gefunden.")
        self.intake_selected_query_node_id.set(parameter_node_id)
        self._open_ten_search_engines_for_parameter(parameter_node_id, confirm=False, note="Automatische 10-Engine-Öffnung direkt nach Kategorie-Ableitung")

    def _category_options(self):
        try:
            cats = self.ctx.categorized_search_55_1.categories()
        except Exception:
            cats = []
        return [f"{c.get('key')} | {c.get('letter')}) {c.get('label')}" for c in cats]

    def _selected_category_key(self):
        value = self.intake_search_category.get() if hasattr(self, "intake_search_category") else "all"
        if not value or value.startswith("all"):
            return ""
        return value.split("|", 1)[0].strip()

    def _category_key_from_value(self, value: str) -> str:
        if not value or str(value).startswith("all"):
            return ""
        return str(value).split("|", 1)[0].strip()

    def _select_intake_entity(self, event=None):
        sel = getattr(self, "intake_entity_tree", None).selection() if hasattr(self, "intake_entity_tree") else []
        if sel:
            vals = self.intake_entity_tree.item(sel[0], "values")
            if vals:
                self.intake_selected_entity_id.set(vals[0])
                try:
                    ent = self.ctx.case_cockpit_54.get_entity(vals[0])
                    self.intake_entity_type.set(ent.get("entity_type", "person"))
                    self.intake_entity_name.set(ent.get("display_name", ""))
                    self.intake_known_names.set(", ".join(ent.get("known_names") or []))
                    self.intake_aliases.set(", ".join(ent.get("aliases") or []))
                    self.intake_dates.set(", ".join(ent.get("dates") or []))
                    self.intake_places.set(", ".join(ent.get("places") or []))
                    self.intake_organizations.set(", ".join(ent.get("organizations") or []))
                    self.intake_roles.set(", ".join(ent.get("roles") or []))
                    self.intake_identifiers.set(", ".join(ent.get("identifiers") or []))
                    self.intake_public_links.set(", ".join(ent.get("public_links") or []))
                    self.intake_entity_notes.set(ent.get("notes", ""))
                except Exception:
                    pass
                self.status.set("Aktive Entity: " + vals[0])
                self.refresh_one_page_intake()

    def _select_intake_query(self, event=None):
        sel = getattr(self, "intake_query_tree", None).selection() if hasattr(self, "intake_query_tree") else []
        if sel:
            vals = self.intake_query_tree.item(sel[0], "values")
            if vals:
                self.intake_selected_query_node_id.set(vals[0])

    def _select_intake_finding(self, event=None):
        sel = getattr(self, "intake_finding_tree", None).selection() if hasattr(self, "intake_finding_tree") else []
        if sel:
            vals = self.intake_finding_tree.item(sel[0], "values")
            if vals:
                self.intake_selected_finding_node_id.set(vals[0])
                if not self.intake_included_fact_value.get():
                    self.intake_included_fact_value.set(vals[1])

    def _select_intake_chain_node(self, event=None):
        sel = getattr(self, "intake_chain_tree", None).selection() if hasattr(self, "intake_chain_tree") else []
        if sel:
            vals = self.intake_chain_tree.item(sel[0], "values")
            if vals:
                self.intake_selected_chain_node_id.set(vals[0])
                try:
                    self.intake_show_chain_trace(silent=True)
                except Exception:
                    pass

    def _intake_query_rows(self):
        cid = self.selected_case_id.get(); entity_id = self._selected_intake_entity_id()
        if not cid:
            return []
        category_key = self._selected_category_key()
        nodes = self.ctx.categorized_search_55_1.filtered_query_rows(cid, entity_id=entity_id, category_key=category_key)
        rows = []
        for n in nodes:
            meta = n.get("metadata") or {}
            rows.append((n, meta.get("search_url", ""), meta.get("engine", "")))
        return rows

    def intake_open_selected_query(self):
        node_id = self.intake_selected_query_node_id.get()
        if not node_id:
            return messagebox.showwarning("Suchanfrage", "Bitte eine Suchanfrage markieren.")
        try:
            n = self.ctx.search_chain_54.get_node(node_id)
            url = (n.get("metadata") or {}).get("search_url") or self.ctx.search_chain_54._search_url("google", n.get("value", ""))
            webbrowser.open(url)
            self.ctx.search_chain_54.mark_node_status(node_id, "opened", note="Suche aus One-Page Intake geöffnet")
            self.status.set("Suchanfrage geöffnet: " + n.get("value", ""))
            self.refresh_one_page_intake()
        except Exception as exc:
            messagebox.showerror("Suchanfrage", str(exc))

    def _open_ten_search_engines_for_parameter(self, parameter_node_id: str, *, confirm: bool = True, note: str = "10-Engine-Öffnung für markierten Suchparameter"):
        rows = self.ctx.categorized_search_55_1.query_rows_for_parameter(parameter_node_id)[:10]
        if not rows:
            return messagebox.showwarning("10 Suchmaschinen", "Zum gewählten Suchparameter wurden keine Suchmaschinenlinks gefunden.")
        if confirm:
            ok = messagebox.askyesno("10 Suchmaschinen öffnen", f"Es werden genau {len(rows)} Suchmaschinen für diesen einen Suchparameter geöffnet. Fortfahren?")
            if not ok:
                return
        for n in rows:
            meta = n.get("metadata") or {}
            url = meta.get("search_url") or self.ctx.search_chain_54._search_url(meta.get("engine") or "google", n.get("value", ""))
            webbrowser.open(url)
            try:
                self.ctx.search_chain_54.mark_node_status(n.get("node_id"), "opened", note=note)
            except Exception:
                pass
        self.status.set(f"{len(rows)} Suchmaschinen geöffnet: genau ein Suchparameter, keine Kategorie-Massenöffnung.")
        self.refresh_one_page_intake()

    def intake_open_all_visible_queries(self):
        node_id = self.intake_selected_query_node_id.get()
        if not node_id:
            return messagebox.showwarning("10 Suchmaschinen", "Bitte zuerst einen Suchparameter-/Suchmaschinenlink markieren. Dann werden nur die 10 Suchmaschinen dieses einen Parameters geöffnet.")
        try:
            selected = self.ctx.search_chain_54.get_node(node_id)
            parameter_node_id = selected.get("parent_node_id") if selected.get("node_type") == "search_query" else selected.get("node_id")
            self._open_ten_search_engines_for_parameter(parameter_node_id, confirm=True)
        except Exception as exc:
            messagebox.showerror("10 Suchmaschinen", str(exc))

    def intake_add_finding(self):
        ent, warning = self._ensure_one_page_context()
        if warning:
            return messagebox.showwarning("Fund", warning)
        cid = self.selected_case_id.get(); qid = self.intake_selected_query_node_id.get()
        if not qid:
            return messagebox.showwarning("Fund", "Bitte eine Suchanfrage auswählen oder zuerst Suchparameter aus den aktuellen Angaben erzeugen.")
        title = self.intake_finding_title.get().strip() or "Öffentlicher Fund"
        url = self.intake_finding_url.get().strip()
        if not url:
            return messagebox.showwarning("Fund", "URL des Fundes ist erforderlich.")
        snippet = self.intake_finding_snippet.get("1.0", "end").strip() or title
        try:
            f = self.ctx.search_chain_54.add_finding(cid, qid, title, url, snippet, entity_id=self._selected_intake_entity_id(), document_date=self.intake_finding_date.get(), source_category=self.intake_finding_category.get(), relevance_score=60)
            self.intake_selected_finding_node_id.set(f["node_id"])
            self.status.set("Fund hinzugefügt: " + f["node_id"])
            self.refresh_one_page_intake()
        except Exception as exc:
            messagebox.showerror("Fund", str(exc))

    def intake_include_information(self):
        fid = self.intake_selected_finding_node_id.get()
        value = self.intake_included_fact_value.get().strip()
        if not fid or not value:
            return messagebox.showwarning("Inkludieren", "Bitte Fund markieren und eine zu inkludierende Information eintragen.")
        try:
            res = self.ctx.search_chain_54.include_information(fid, [{"type": self.intake_included_fact_type.get(), "label": self.intake_included_fact_type.get(), "value": value}], reviewer="one-page-intake")
            expanded = {"query_count": 0, "parameter_count": 0}
            for node in res.get("included_nodes", []):
                try:
                    e = self.ctx.categorized_search_55_1.expand_included_fact(node.get("node_id"), max_parameters=6)
                    expanded["query_count"] += e.get("query_count", 0)
                    expanded["parameter_count"] += e.get("parameter_count", 0)
                except Exception:
                    pass
            self.status.set(f"Information inkludiert: {res.get('included_count')} Fakt, {res.get('derived_query_count')} klassische Queries + {expanded.get('parameter_count',0)} Tiefenparameter / {expanded.get('query_count',0)} 10-Engine-Queries.")
            self.intake_included_fact_value.set("")
            self.refresh_one_page_intake()
        except Exception as exc:
            messagebox.showerror("Inkludieren", str(exc))

    def refresh_one_page_intake(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            if hasattr(self, "intake_entity_tree"):
                self.intake_entity_tree.delete(*self.intake_entity_tree.get_children())
                for e in self.ctx.case_cockpit_54.list_entities(cid):
                    self.intake_entity_tree.insert("", "end", values=(e.get("entity_id"), e.get("entity_type"), e.get("display_name"), ", ".join(e.get("places") or []), ", ".join(e.get("organizations") or [])))
                    if not self.intake_selected_entity_id.get():
                        self.intake_selected_entity_id.set(e.get("entity_id"))
            entity_id = self._selected_intake_entity_id()
            chain = self.ctx.search_chain_54.build_professional_chain(cid, entity_id=entity_id)
            if hasattr(self, "intake_query_tree"):
                self.intake_query_tree.delete(*self.intake_query_tree.get_children())
                category_filter = self._selected_category_key()
                for n in self.ctx.categorized_search_55_1.filtered_query_rows(cid, entity_id=entity_id, category_key=category_filter):
                    meta = n.get("metadata") or {}
                    cat = meta.get("category_label", "ohne Kategorie")
                    self.intake_query_tree.insert("", "end", values=(n.get("node_id"), cat, n.get("node_type"), n.get("status_label", n.get("status", "")), n.get("value"), meta.get("engine_label") or meta.get("engine", ""), meta.get("search_url", "")))
            if hasattr(self, "intake_finding_tree"):
                self.intake_finding_tree.delete(*self.intake_finding_tree.get_children())
                for n in chain.get("nodes", []):
                    if n.get("node_type") == "source_hit":
                        self.intake_finding_tree.insert("", "end", values=(n.get("node_id"), n.get("title"), n.get("status_label", n.get("status", "")), n.get("source_url"), n.get("relevance_score")))
            if hasattr(self, "intake_chain_tree"):
                self.intake_chain_tree.delete(*self.intake_chain_tree.get_children())
                for n in chain.get("nodes", [])[-120:]:
                    self.intake_chain_tree.insert("", "end", values=(n.get("node_id"), n.get("node_type"), n.get("status_label", n.get("status", "")), n.get("depth", 0), n.get("title"), n.get("value"), n.get("beleggrad", n.get("confidence_label", "")), n.get("path_text", "")))
            if hasattr(self, "intake_profile_text"):
                metrics = chain.get("metrics", {})
                if hasattr(self, "intake_workflow_status"):
                    active_name = self.intake_entity_name.get().strip() or self._selected_intake_entity_id() or "keine"
                    cat_summary = self.ctx.categorized_search_55_1.summarize_chain_categories(cid, entity_id=entity_id)
                    cat_bits = [f"{c['category']['letter']}) {c['queries']}Q" for c in cat_summary.get('categories', []) if c.get('queries')]
                    self.intake_workflow_status.set(f"Fallstatus: {cid or 'kein Fall'} | Entity: {active_name} | Chain: {metrics.get('nodes',0)} Nodes / {metrics.get('queries',0)} Queries / {metrics.get('findings',0)} Funde / {metrics.get('included_facts',0)} inkludiert | Kategorien: {', '.join(cat_bits) or 'noch keine'}")
                included = [n for n in chain.get("nodes", []) if n.get("node_type") == "included_fact"]
                lines = [
                    "ONE-PAGE PROFILVORSCHAU AUS DER SEARCH/FUND-CHAIN",
                    f"Nodes: {metrics.get('nodes',0)} | Queries: {metrics.get('queries',0)} | Funde: {metrics.get('findings',0)} | Inkludierte Fakten: {metrics.get('included_facts',0)} | Profilkandidaten: {metrics.get('profile_candidates',0)} | Berichtsfähig: {metrics.get('report_ready',0)}",
                    "",
                    "Inkludierte Informationen / Profilkandidaten:",
                ]
                for n in included[-30:]:
                    lines.append(f"- {n.get('value')}  [Status: {n.get('status_label','')}]  [Beleggrad: {n.get('beleggrad','')}]\n  Rückverfolgung: {n.get('path_text','')}")
                lines += ["", "Regel: Kein Profilpunkt ohne Chain, kein Export ohne Beleggrad, keine automatische Identitäts-/Schuld-/Gefährlichkeitsbehauptung."]
                self.intake_profile_text.delete("1.0", "end"); self.intake_profile_text.insert("end", "\n".join(lines))
        except Exception as exc:
            if hasattr(self, "intake_profile_text"):
                self.intake_profile_text.delete("1.0", "end"); self.intake_profile_text.insert("end", "One-Page Intake Fehler: " + str(exc))

    def intake_mark_chain_status(self):
        node_id = self.intake_selected_chain_node_id.get()
        if not node_id:
            return messagebox.showwarning("Search/Fund-Chain", "Bitte einen Chain-Knoten markieren.")
        try:
            node = self.ctx.search_chain_54.mark_node_status(node_id, self.intake_chain_status_action.get(), note="Status über Build 55.3 Chain-Pro-UI gesetzt")
            self.status.set(f"Chain-Status gesetzt: {node.get('status')} für {node_id}")
            self.refresh_one_page_intake()
            self.refresh_one_page_outputs()
        except Exception as exc:
            messagebox.showerror("Search/Fund-Chain", str(exc))

    def intake_show_chain_trace(self, silent: bool = False):
        node_id = self.intake_selected_chain_node_id.get()
        if not node_id:
            if not silent:
                return messagebox.showwarning("Chain-Pfad", "Bitte einen Chain-Knoten markieren.")
            return
        trace = self.ctx.search_chain_54.get_trace(node_id)
        lines = ["CHAIN-RÜCKVERFOLGUNG", "", trace.get("path_text", ""), ""]
        for i, n in enumerate(trace.get("trace", []), start=1):
            lines.append(f"{i}. {n.get('node_type')} | {n.get('status_label','')} | {n.get('title')}")
            lines.append(f"   Wert: {n.get('value')}")
            if n.get('source_url'):
                lines.append(f"   Quelle: {n.get('source_url')}")
        if hasattr(self, "intake_profile_text"):
            self.intake_profile_text.delete("1.0", "end")
            self.intake_profile_text.insert("end", "\n".join(lines))

    def _tab_person_detail_page(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="1 Personenakte")
        header = ttk.LabelFrame(tab, text="Build 55.5 – Personenakte: Funde dokumentieren, Bericht verfassen, Research-Qualität nutzen")
        header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text="Diese Seite ist die Arbeitsakte zur markierten Person/Organisation. Funde werden dokumentiert; der Ergebnisbericht wird als Fließtext verfasst und bleibt nachvollziehbar mit Fall, Entity und Chain verbunden.").grid(row=0, column=0, columnspan=8, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="aus markierter Intake-Person öffnen", command=self.open_person_detail_for_selected_entity).grid(row=1, column=0, padx=4, pady=3)
        ttk.Button(header, text="Seite aktualisieren", command=self.refresh_person_detail_page).grid(row=1, column=1, padx=4, pady=3)
        ttk.Button(header, text="Narrativ-Vorlage aus Funden erzeugen", command=self.person_detail_build_default_narrative).grid(row=1, column=2, padx=4, pady=3)
        ttk.Button(header, text="Ergebnisbericht speichern", command=self.person_detail_save_narrative).grid(row=1, column=3, padx=4, pady=3)
        ttk.Button(header, text="Personenakte exportieren", command=self.person_detail_export_markdown).grid(row=1, column=4, padx=4, pady=3)
        ttk.Button(header, text="Phase B: Dashboard Final", command=self.person_detail_phase_b_dashboard_final).grid(row=2, column=0, padx=4, pady=3)
        ttk.Button(header, text="Phase B: Final-Fallakte", command=self.person_detail_phase_b_casefile_final).grid(row=2, column=1, padx=4, pady=3)
        header.columnconfigure(5, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=2); panes.add(right, weight=5)

        entity_box = ttk.LabelFrame(left, text="Person / Organisation auswählen")
        entity_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_entity_tree = ttk.Treeview(entity_box, columns=("id","typ","name","orte","orgs"), show="headings", height=9)
        for c,h,w in [("id","ID",135),("typ","Typ",90),("name","Name",180),("orte","Orte",170),("orgs","Organisationen",190)]:
            self.person_detail_entity_tree.heading(c, text=h); self.person_detail_entity_tree.column(c, width=w)
        self.person_detail_entity_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_entity_tree.bind("<<TreeviewSelect>>", self._select_person_detail_entity)
        self.person_detail_entity_tree.bind("<Double-1>", lambda e: self.refresh_person_detail_page())

        meta_box = ttk.LabelFrame(left, text="Grunddaten / Status")
        meta_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_meta_text = tk.Text(meta_box, height=12, wrap="word")
        self.person_detail_meta_text.pack(fill="both", expand=True, padx=4, pady=4)

        old_box = ttk.LabelFrame(left, text="Gespeicherte Fließtextberichte")
        old_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_narrative_tree = ttk.Treeview(old_box, columns=("id","status","title","updated","sha"), show="headings", height=7)
        for c,h,w in [("id","ID",135),("status","Status",90),("title","Titel",210),("updated","Aktualisiert",145),("sha","SHA",120)]:
            self.person_detail_narrative_tree.heading(c, text=h); self.person_detail_narrative_tree.column(c, width=w)
        self.person_detail_narrative_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_narrative_tree.bind("<<TreeviewSelect>>", self._select_person_detail_narrative)

        right_panes = ttk.Panedwindow(right, orient="vertical")
        right_panes.pack(fill="both", expand=True, padx=4, pady=4)
        finding_frame = ttk.LabelFrame(right_panes, text="Funde zur Person dokumentieren")
        narrative_frame = ttk.LabelFrame(right_panes, text="Ergebnisbericht im Fließtext")
        right_panes.add(finding_frame, weight=3); right_panes.add(narrative_frame, weight=4)

        form = ttk.Frame(finding_frame); form.pack(fill="x", padx=4, pady=3)
        ttk.Label(form, text="Titel").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.person_detail_finding_title, width=34).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(form, text="Typ").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        ttk.Combobox(form, textvariable=self.person_detail_finding_type, values=["web","pdf","image","registry","court","finance","network","note","other"], width=12, state="readonly").grid(row=0, column=3, sticky="w", padx=2, pady=2)
        ttk.Label(form, text="Status").grid(row=0, column=4, sticky="w", padx=2, pady=2)
        ttk.Combobox(form, textvariable=self.person_detail_status, values=["candidate","included","needs_review","counter_evidence","discarded","report_ready"], width=15, state="readonly").grid(row=0, column=5, sticky="w", padx=2, pady=2)
        ttk.Label(form, text="Quelle/URL").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.person_detail_source_url, width=34).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(form, text="Datum").grid(row=1, column=2, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.person_detail_document_date, width=14).grid(row=1, column=3, sticky="w", padx=2, pady=2)
        ttk.Label(form, text="Kategorie").grid(row=1, column=4, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.person_detail_category, width=18).grid(row=1, column=5, sticky="w", padx=2, pady=2)
        ttk.Label(form, text="Beleggrad").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        ttk.Combobox(form, textvariable=self.person_detail_evidence_level, values=["candidate","weak_indicator","strong_indicator","verified_public_fact","counter_evidence","internal_only"], width=22, state="readonly").grid(row=2, column=1, sticky="w", padx=2, pady=2)
        ttk.Checkbutton(form, text="redaktionspflichtig", variable=self.person_detail_redaction_required).grid(row=2, column=2, columnspan=2, sticky="w", padx=2, pady=2)
        ttk.Button(form, text="Fund dokumentieren", command=self.person_detail_add_finding).grid(row=2, column=4, padx=2, pady=2)
        ttk.Button(form, text="Status aktualisieren", command=self.person_detail_update_finding_status).grid(row=2, column=5, padx=2, pady=2)
        form.columnconfigure(1, weight=1)

        text_area = ttk.Panedwindow(finding_frame, orient="horizontal")
        text_area.pack(fill="both", expand=True, padx=4, pady=3)
        summary_box = ttk.LabelFrame(text_area, text="Fund-Zusammenfassung")
        note_box = ttk.LabelFrame(text_area, text="Analystische Notiz / Bewertung")
        text_area.add(summary_box, weight=3); text_area.add(note_box, weight=2)
        self.person_detail_finding_summary = tk.Text(summary_box, height=5, wrap="word")
        self.person_detail_finding_summary.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_analyst_note = tk.Text(note_box, height=5, wrap="word")
        self.person_detail_analyst_note.pack(fill="both", expand=True, padx=4, pady=4)

        self.person_detail_finding_tree = ttk.Treeview(finding_frame, columns=("id","status","typ","titel","quelle","beleg","updated"), show="headings", height=8)
        for c,h,w in [("id","ID",135),("status","Status",105),("typ","Typ",80),("titel","Titel",260),("quelle","Quelle",260),("beleg","Beleg",120),("updated","Aktualisiert",145)]:
            self.person_detail_finding_tree.heading(c, text=h); self.person_detail_finding_tree.column(c, width=w)
        self.person_detail_finding_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.person_detail_finding_tree.bind("<<TreeviewSelect>>", self._select_person_detail_finding)

        nbar = ttk.Frame(narrative_frame); nbar.pack(fill="x", padx=4, pady=3)
        ttk.Label(nbar, text="Titel").pack(side="left", padx=2)
        ttk.Entry(nbar, textvariable=self.person_detail_narrative_title, width=45).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Label(nbar, text="Status").pack(side="left", padx=2)
        ttk.Combobox(nbar, textvariable=self.person_detail_narrative_status, values=["draft","review","approved","blocked"], width=12, state="readonly").pack(side="left", padx=2)
        ttk.Button(nbar, text="speichern", command=self.person_detail_save_narrative).pack(side="left", padx=3)
        self.person_detail_narrative_text = tk.Text(narrative_frame, wrap="word")
        self.person_detail_narrative_text.pack(fill="both", expand=True, padx=4, pady=4)

    def open_person_detail_for_selected_entity(self):
        ent, warning = self._ensure_one_page_context()
        if warning:
            return messagebox.showwarning("Personenakte", warning)
        self.person_detail_selected_entity_id.set(ent.get("entity_id", ""))
        try:
            self.root_nb.select(1)
        except Exception:
            pass
        self.refresh_person_detail_page()
        self.status.set("Personenakte geöffnet: " + ent.get("display_name", ent.get("entity_id", "")))

    def _active_person_detail_context(self):
        cid = self.selected_case_id.get().strip()
        entity_id = self.person_detail_selected_entity_id.get().strip() or self._selected_intake_entity_id()
        if not cid:
            return None, "Bitte zuerst Fall anlegen oder auswählen."
        if not entity_id:
            return None, "Bitte zuerst Person/Organisation auswählen oder in der Intake-Seite anlegen."
        return {"case_id": cid, "entity_id": entity_id}, ""

    def _select_person_detail_entity(self, event=None):
        sel = getattr(self, "person_detail_entity_tree", None).selection() if hasattr(self, "person_detail_entity_tree") else []
        if sel:
            vals = self.person_detail_entity_tree.item(sel[0], "values")
            if vals:
                self.person_detail_selected_entity_id.set(vals[0])
                self.intake_selected_entity_id.set(vals[0])
                self.refresh_person_detail_page()

    def _select_person_detail_finding(self, event=None):
        sel = getattr(self, "person_detail_finding_tree", None).selection() if hasattr(self, "person_detail_finding_tree") else []
        if not sel:
            return
        vals = self.person_detail_finding_tree.item(sel[0], "values")
        if not vals:
            return
        fid = vals[0]
        self.person_detail_selected_finding_id.set(fid)
        try:
            f = self.ctx.person_detail_55_4.get_finding(fid)
            self.person_detail_finding_title.set(f.get("title", ""))
            self.person_detail_finding_type.set(f.get("finding_type", "web"))
            self.person_detail_source_url.set(f.get("source_url", ""))
            self.person_detail_document_date.set(f.get("document_date", ""))
            self.person_detail_category.set(f.get("category", ""))
            self.person_detail_status.set(f.get("status", "candidate"))
            self.person_detail_evidence_level.set(f.get("evidence_level", "candidate"))
            self.person_detail_redaction_required.set(bool(f.get("redaction_required", True)))
            self.person_detail_finding_summary.delete("1.0", "end"); self.person_detail_finding_summary.insert("end", f.get("summary", ""))
            self.person_detail_analyst_note.delete("1.0", "end"); self.person_detail_analyst_note.insert("end", f.get("analyst_note", ""))
        except Exception:
            pass

    def _select_person_detail_narrative(self, event=None):
        sel = getattr(self, "person_detail_narrative_tree", None).selection() if hasattr(self, "person_detail_narrative_tree") else []
        if not sel:
            return
        vals = self.person_detail_narrative_tree.item(sel[0], "values")
        if not vals:
            return
        nid = vals[0]
        self.person_detail_selected_narrative_id.set(nid)
        try:
            n = self.ctx.person_detail_55_4.get_narrative(nid)
            self.person_detail_narrative_title.set(n.get("title", "Ergebnisbericht"))
            self.person_detail_narrative_status.set(n.get("status", "draft"))
            self.person_detail_narrative_text.delete("1.0", "end"); self.person_detail_narrative_text.insert("end", n.get("body", ""))
        except Exception:
            pass

    def person_detail_add_finding(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Personenakte", warning)
        try:
            summary = self.person_detail_finding_summary.get("1.0", "end").strip()
            note = self.person_detail_analyst_note.get("1.0", "end").strip()
            linked_chain = self.intake_selected_chain_node_id.get() or self.intake_selected_finding_node_id.get()
            f = self.ctx.person_detail_55_4.add_finding_note(
                ctx["case_id"], ctx["entity_id"],
                title=self.person_detail_finding_title.get(), summary=summary,
                finding_type=self.person_detail_finding_type.get(), source_url=self.person_detail_source_url.get(),
                document_date=self.person_detail_document_date.get(), category=self.person_detail_category.get(),
                status=self.person_detail_status.get(), analyst_note=note, chain_node_id=linked_chain,
                evidence_level=self.person_detail_evidence_level.get(), redaction_required=self.person_detail_redaction_required.get(),
            )
            self.person_detail_selected_finding_id.set(f.get("finding_note_id", ""))
            self.status.set("Fund dokumentiert: " + f.get("finding_note_id", ""))
            self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Fund dokumentieren", str(exc))

    def person_detail_update_finding_status(self):
        fid = self.person_detail_selected_finding_id.get().strip()
        if not fid:
            return messagebox.showwarning("Personenakte", "Bitte einen dokumentierten Fund markieren.")
        try:
            f = self.ctx.person_detail_55_4.update_finding_status(fid, self.person_detail_status.get(), analyst_note=self.person_detail_analyst_note.get("1.0", "end").strip())
            self.status.set("Fundstatus aktualisiert: " + f.get("status", ""))
            self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Fundstatus", str(exc))

    def person_detail_build_default_narrative(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Personenakte", warning)
        try:
            default = self.ctx.person_detail_55_4.build_default_narrative(ctx["case_id"], ctx["entity_id"])
            self.person_detail_narrative_title.set(default.get("title", "Ergebnisbericht"))
            self.person_detail_narrative_text.delete("1.0", "end"); self.person_detail_narrative_text.insert("end", default.get("body", ""))
            self.status.set("Narrativ-Vorlage erzeugt.")
        except Exception as exc:
            messagebox.showerror("Narrativ", str(exc))

    def person_detail_save_narrative(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Personenakte", warning)
        body = self.person_detail_narrative_text.get("1.0", "end").strip()
        if not body:
            return messagebox.showwarning("Ergebnisbericht", "Bitte zuerst einen Fließtext-Bericht verfassen oder eine Vorlage erzeugen.")
        try:
            n = self.ctx.person_detail_55_4.save_narrative(ctx["case_id"], ctx["entity_id"], title=self.person_detail_narrative_title.get(), body=body, status=self.person_detail_narrative_status.get())
            self.person_detail_selected_narrative_id.set(n.get("narrative_id", ""))
            self.status.set("Ergebnisbericht gespeichert: " + n.get("narrative_id", ""))
            self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Ergebnisbericht speichern", str(exc))

    def person_detail_export_markdown(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Personenakte", warning)
        try:
            out = self.ctx.person_detail_55_4.export_person_page_markdown(ctx["case_id"], ctx["entity_id"], narrative_id=self.person_detail_selected_narrative_id.get())
            self.status.set("Personenakte exportiert: " + out.get("path", ""))
            messagebox.showinfo("Personenakte exportiert", out.get("path", ""))
        except Exception as exc:
            messagebox.showerror("Personenakte exportieren", str(exc))

    def refresh_person_detail_page(self):
        cid = self.selected_case_id.get().strip()
        if not cid:
            return
        try:
            if hasattr(self, "person_detail_entity_tree"):
                self.person_detail_entity_tree.delete(*self.person_detail_entity_tree.get_children())
                for e in self.ctx.case_cockpit_54.list_entities(cid):
                    self.person_detail_entity_tree.insert("", "end", values=(e.get("entity_id"), e.get("entity_type"), e.get("display_name"), ", ".join(e.get("places") or []), ", ".join(e.get("organizations") or [])))
                    if not self.person_detail_selected_entity_id.get() and self._selected_intake_entity_id() == e.get("entity_id"):
                        self.person_detail_selected_entity_id.set(e.get("entity_id"))
            entity_id = self.person_detail_selected_entity_id.get().strip() or self._selected_intake_entity_id()
            if not entity_id:
                if hasattr(self, "person_detail_meta_text"):
                    self.person_detail_meta_text.delete("1.0", "end"); self.person_detail_meta_text.insert("end", "Keine Person/Organisation ausgewählt.")
                return
            self.person_detail_selected_entity_id.set(entity_id)
            page = self.ctx.person_detail_55_4.build_person_page(cid, entity_id)
            ent = page.get("entity", {})
            if hasattr(self, "person_detail_meta_text"):
                lines = [
                    page.get("page_title", "Personenakte"), "",
                    f"Typ: {ent.get('entity_type','')}",
                    f"Name: {ent.get('display_name','')}",
                    f"bekannte Namen: {', '.join(ent.get('known_names') or [])}",
                    f"Aliasse: {', '.join(ent.get('aliases') or [])}",
                    f"Orte: {', '.join(ent.get('places') or [])}",
                    f"Organisationen: {', '.join(ent.get('organizations') or [])}",
                    f"Rollen: {', '.join(ent.get('roles') or [])}",
                    "",
                    f"Funde: {page.get('metrics',{}).get('finding_count',0)} | Berichte: {page.get('metrics',{}).get('narrative_count',0)} | Chain-Knoten: {page.get('metrics',{}).get('chain_node_count',0)}",
                    f"Status: {page.get('metrics',{}).get('status_counts',{})}",
                ]
                try:
                    dash61 = self.ctx.person_dashboard_60_4.dashboard(cid, entity_id)
                    lines += [
                        "",
                        "Research-Dashboard 61:",
                        f"Claims: {dash61.get('metrics',{}).get('claim_count')} | Doppler hoch: {dash61.get('metrics',{}).get('doppler_high')} | Fit-Prüfungen: {dash61.get('metrics',{}).get('fit_assessment_count')}",
                        "Statusampel: " + str(dash61.get('status_ampel', {})),
                        "Nächste Aktionen:",
                    ]
                    for action in dash61.get('next_actions', [])[:5]:
                        lines.append(f"- {action.get('title')} {action.get('query','')}")
                except Exception:
                    pass
                self.person_detail_meta_text.delete("1.0", "end"); self.person_detail_meta_text.insert("end", "\n".join(lines))
            if hasattr(self, "person_detail_finding_tree"):
                self.person_detail_finding_tree.delete(*self.person_detail_finding_tree.get_children())
                for f in page.get("findings", []):
                    self.person_detail_finding_tree.insert("", "end", values=(f.get("finding_note_id"), f.get("status"), f.get("finding_type"), f.get("title"), f.get("source_url"), f.get("evidence_level"), f.get("updated_at")))
            if hasattr(self, "person_detail_narrative_tree"):
                self.person_detail_narrative_tree.delete(*self.person_detail_narrative_tree.get_children())
                for n in page.get("narratives", []):
                    self.person_detail_narrative_tree.insert("", "end", values=(n.get("narrative_id"), n.get("status"), n.get("title"), n.get("updated_at"), n.get("body_sha256", "")[:12]))
        except Exception as exc:
            if hasattr(self, "person_detail_meta_text"):
                self.person_detail_meta_text.delete("1.0", "end"); self.person_detail_meta_text.insert("end", "Personenakte-Fehler: " + str(exc))



    def person_detail_phase_b_dashboard_final(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Phase B Dashboard", warning)
        try:
            ws = self.ctx.phase_b_workspace_62_4.build_workspace(ctx["case_id"], ctx["entity_id"], persist=True)
            lines = [
                "PHASE B – PERSONENAKTE FINAL",
                "",
                f"Readiness: {ws.get('readiness_score')}/100 – {ws.get('readiness_label')}",
                "",
                "STATUSAMPEL:",
            ]
            for k, v in (ws.get("status_ampel") or {}).items():
                lines.append(f"- {k}: {v}")
            lines += ["", "TOP-FUNDE:"]
            for item in ws.get("top_findings", [])[:8]:
                f = item.get("finding", {})
                lines.append(f"- {f.get('title', 'Fund')} | Score {item.get('score')} | Gate {item.get('report_gate')}")
            lines += ["", "WARNUNGEN:"]
            for w in ws.get("warnings", []):
                lines.append(f"- [{w.get('level')}] {w.get('text')}")
            lines += ["", "NÄCHSTE SCHRITTE:"]
            for step in ws.get("next_steps", [])[:10]:
                lines.append(f"- {step.get('title')}")
            self.person_detail_meta_text.delete("1.0", "end")
            self.person_detail_meta_text.insert("end", "\n".join(lines))
            self.status.set("Phase-B-Dashboard erzeugt: " + str(ws.get("workspace_id", "workspace")))
        except Exception as exc:
            messagebox.showerror("Phase B Dashboard", str(exc))

    def person_detail_phase_b_casefile_final(self):
        ctx, warning = self._active_person_detail_context()
        if warning:
            return messagebox.showwarning("Phase B Fallakte", warning)
        try:
            out = self.ctx.phase_b_casefile_62_5.create_final_casefile(ctx["case_id"], ctx["entity_id"], export_mode="authority_redacted")
            self.status.set("Phase-B-Final-Fallakte erzeugt: " + out.get("path", ""))
            messagebox.showinfo("Final-Fallakte erzeugt", out.get("path", ""))
        except Exception as exc:
            messagebox.showerror("Phase B Fallakte", str(exc))

    def _tab_quality_engine(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2 Research Engine")
        header = ttk.LabelFrame(tab, text="Build 56.0 – Research Engine: Fundimport, Entity Resolution, Query Optimizer, Claims, Benchmark")
        header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text="Ziel: Treffer sauber importieren, Identitätsfit bewerten, Queries optimieren, Claims bilden und Precision@10 messen.").grid(row=0, column=0, columnspan=8, sticky="w", padx=4, pady=3)
        ttk.Label(header, text="Kategorie:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.sq_category, values=self._category_options(), width=50, state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="1 Fingerprint erzeugen", command=self.sq_build_fingerprint).grid(row=1, column=2, padx=4, pady=3)
        ttk.Button(header, text="2 Query-Pyramide bauen", command=self.sq_build_query_pyramid).grid(row=1, column=3, padx=4, pady=3)
        ttk.Button(header, text="3 10 Engines zur markierten Query", command=self.sq_open_selected_quality_query).grid(row=1, column=4, padx=4, pady=3)
        ttk.Button(header, text="4 Chain-Funde ranken", command=self.sq_score_chain_findings).grid(row=1, column=5, padx=4, pady=3)
        ttk.Button(header, text="Benchmark", command=self.sq_compute_benchmark).grid(row=1, column=6, padx=4, pady=3)
        ttk.Button(header, text="Aktualisieren", command=self.refresh_search_quality).grid(row=1, column=7, padx=4, pady=3)
        ttk.Button(header, text="URL-Fund importieren", command=self.sq_import_person_detail_url).grid(row=2, column=2, padx=4, pady=3)
        ttk.Button(header, text="Entity Resolution", command=self.sq_entity_resolution).grid(row=2, column=3, padx=4, pady=3)
        ttk.Button(header, text="Queries optimieren", command=self.sq_optimize_queries).grid(row=2, column=4, padx=4, pady=3)
        ttk.Button(header, text="Claims bilden", command=self.sq_build_claims).grid(row=2, column=5, padx=4, pady=3)
        ttk.Button(header, text="Integrated Cycle", command=self.sq_run_integrated_cycle).grid(row=2, column=6, padx=4, pady=3)
        header.columnconfigure(1, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=3)

        qbox = ttk.LabelFrame(left, text="Query-Pyramide: L1 Identitätsanker → L2 Kontext → L3 Quellen-Dorks → L4 Gegenprüfung")
        qbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.sq_query_tree = ttk.Treeview(qbox, columns=("id","level","cat","precision","query","expected"), show="headings", height=16)
        for c,h,w in [("id","Query-ID",130),("level","Ebene",165),("cat","Kategorie",160),("precision","Precision",75),("query","Suchanfrage",410),("expected","erwarteter Beleg",260)]:
            self.sq_query_tree.heading(c, text=h); self.sq_query_tree.column(c, width=w)
        self.sq_query_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.sq_query_tree.bind("<<TreeviewSelect>>", self._sq_select_query)

        rbox = ttk.LabelFrame(right, text="Treffer-Ranking: Entity Fit, Quellengewichtung, Sensibilität, Doppler-Risiko")
        rbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.sq_result_tree = ttk.Treeview(rbox, columns=("id","score","label","entity","source","sens","title","domain","flags"), show="headings", height=16)
        for c,h,w in [("id","Result-ID",120),("score","Score",55),("label","Label",125),("entity","Entity",60),("source","Quelle",60),("sens","Sens.",55),("title","Titel",260),("domain","Domain",140),("flags","Flags",260)]:
            self.sq_result_tree.heading(c, text=h); self.sq_result_tree.column(c, width=w)
        self.sq_result_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.sq_result_tree.bind("<<TreeviewSelect>>", self._sq_select_result)

        fb = ttk.Frame(rbox); fb.pack(fill="x", padx=4, pady=3)
        ttk.Label(fb, text="Feedback:").pack(side="left")
        ttk.Combobox(fb, textvariable=self.sq_feedback_rating, values=["relevant","useful","top_hit","false_positive","name_doppler","counter_evidence","not_relevant"], width=18, state="readonly").pack(side="left", padx=4)
        ttk.Button(fb, text="Feedback speichern", command=self.sq_record_feedback).pack(side="left", padx=4)

        tbox = ttk.LabelFrame(tab, text="Research-Dashboard / Benchmark")
        tbox.pack(fill="both", expand=False, padx=8, pady=6)
        self.sq_text = tk.Text(tbox, height=12, wrap="word")
        self.sq_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _sq_context(self):
        cid = self.selected_case_id.get()
        entity_id = self._selected_intake_entity_id() or self.person_detail_selected_entity_id.get()
        if not cid:
            return None, "Bitte zuerst einen Fall anlegen oder auswählen."
        if not entity_id:
            return None, "Bitte zuerst eine Person/Organisation im Intake auswählen."
        try:
            ent = self.ctx.case_cockpit_54.get_entity(entity_id)
            return {"case_id": cid, "entity_id": entity_id, "entity": ent}, ""
        except Exception as exc:
            return None, str(exc)

    def _sq_select_query(self, event=None):
        sel = getattr(self, "sq_query_tree", None).selection() if hasattr(self, "sq_query_tree") else []
        if sel:
            vals = self.sq_query_tree.item(sel[0], "values")
            if vals:
                self.sq_selected_query_id.set(vals[0])

    def _sq_select_result(self, event=None):
        sel = getattr(self, "sq_result_tree", None).selection() if hasattr(self, "sq_result_tree") else []
        if sel:
            vals = self.sq_result_tree.item(sel[0], "values")
            if vals:
                self.sq_selected_result_id.set(vals[0])

    def sq_build_fingerprint(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Research Engine", warning)
        try:
            fp = self.ctx.search_quality_55_5.build_entity_fingerprint(ctx["case_id"], ctx["entity"])
            f = fp.get("fingerprint", {})
            self.status.set(f"Entity Fingerprint erzeugt: {f.get('display_name')} | {len(f.get('strong_anchors', []))} starke Anker")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Fingerprint", str(exc))

    def sq_build_query_pyramid(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Research Engine", warning)
        try:
            category_key = self._category_key_from_value(self.sq_category.get())
            pyramid = self.ctx.search_quality_55_5.build_query_pyramid(ctx["case_id"], ctx["entity"], category_key, persist=True, create_chain_nodes=True, max_per_level=5)
            self.status.set(f"Query-Pyramide gebaut: {pyramid.get('query_count')} Qualitätsqueries | Precision Ø {pyramid.get('quality_profile',{}).get('precision_avg')}")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Query-Pyramide", str(exc))

    def sq_open_selected_quality_query(self):
        qid = self.sq_selected_query_id.get()
        if not qid:
            return messagebox.showwarning("Research Engine", "Bitte zuerst eine Qualitätsquery markieren.")
        try:
            links = self.ctx.search_quality_55_5.get_engine_links_for_quality_query(qid)
            ok = messagebox.askyesno("10 Suchmaschinen öffnen", f"Es werden genau {links.get('count', 0)} Suchmaschinen für diese eine Qualitätsquery geöffnet. Fortfahren?")
            if not ok:
                return
            for item in links.get("links", []):
                webbrowser.open(item.get("url", ""))
            self.status.set(f"{links.get('count')} Suchmaschinen für Qualitätsquery geöffnet.")
        except Exception as exc:
            messagebox.showerror("Research Engine", str(exc))

    def sq_score_chain_findings(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Research Engine", warning)
        try:
            fp = self.ctx.search_quality_55_5.build_entity_fingerprint(ctx["case_id"], ctx["entity"])
            scored = self.ctx.search_quality_55_5.score_chain_findings(ctx["case_id"], entity_id=ctx["entity_id"])
            self.status.set(f"Chain-Funde gerankt: {scored.get('created_or_updated')} Ergebnisse | Fingerprint {fp.get('fingerprint_hash','')[:10]}")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Treffer-Ranking", str(exc))

    def sq_record_feedback(self):
        rid = self.sq_selected_result_id.get()
        if not rid:
            return messagebox.showwarning("Feedback", "Bitte zuerst einen gerankten Treffer markieren.")
        try:
            fb = self.ctx.search_quality_55_5.record_feedback(rid, self.sq_feedback_rating.get(), note="UI Feedback Build 55.5")
            self.status.set("Feedback gespeichert: " + fb.get("rating", ""))
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Feedback", str(exc))

    def sq_compute_benchmark(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Benchmark", warning)
        try:
            b = self.ctx.search_quality_55_5.compute_benchmark(ctx["case_id"], entity_id=ctx["entity_id"])
            self.status.set("Benchmark erzeugt: Precision@10=" + str(b.get("metrics", {}).get("precision_at_10")))
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Benchmark", str(exc))

    def sq_import_person_detail_url(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Fundimport", warning)
        url = self.person_detail_source_url.get().strip() or self.intake_finding_url.get().strip()
        if not url:
            return messagebox.showwarning("Fundimport", "Bitte in der Personenakte oder im Intake zuerst eine URL eintragen.")
        try:
            imported = self.ctx.result_capture_55_6.import_public_result(
                ctx["case_id"], ctx["entity_id"],
                url=url,
                title=self.person_detail_finding_title.get().strip() or self.intake_finding_title.get().strip() or "Öffentlicher Treffer",
                snippet=self.person_detail_finding_summary.get("1.0", "end").strip() if hasattr(self, "person_detail_finding_summary") else "",
                category_key=self._category_key_from_value(self.sq_category.get()),
                quality_query_id=self.sq_selected_query_id.get(),
                document_date=self.person_detail_document_date.get().strip() or self.intake_finding_date.get().strip(),
            )
            self.status.set("Fund importiert und gerankt: " + imported.get("import_id", ""))
            self.refresh_person_detail_page(); self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Fundimport", str(exc))

    def sq_entity_resolution(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Entity Resolution", warning)
        try:
            res = self.ctx.entity_resolution_55_7.assess_ranked_results(ctx["case_id"], ctx["entity_id"], limit=25)
            self.status.set(f"Entity Resolution: {res.get('assessment_count')} Treffer bewertet")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Entity Resolution", str(exc))

    def sq_optimize_queries(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Query Optimizer", warning)
        try:
            res = self.ctx.query_optimizer_55_8.optimize_entity_queries(ctx["case_id"], ctx["entity_id"])
            self.status.set(f"Queries optimiert: {res.get('review_count')} Reviews")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Query Optimizer", str(exc))

    def sq_build_claims(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Claim Builder", warning)
        try:
            res = self.ctx.claim_builder_55_9.build_claims_from_person_findings(ctx["case_id"], ctx["entity_id"])
            self.status.set(f"Claims gebildet: {res.get('claim_count')}")
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Claim Builder", str(exc))

    def sq_run_integrated_cycle(self):
        ctx, warning = self._sq_context()
        if warning:
            return messagebox.showwarning("Integrated Cycle", warning)
        try:
            res = self.ctx.research_stable_56_0.run_integrated_quality_cycle(ctx["case_id"], ctx["entity"], self._category_key_from_value(self.sq_category.get()))
            self.status.set("Integrated Research Cycle abgeschlossen: " + res.get("session_id", ""))
            self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Integrated Cycle", str(exc))

    def refresh_search_quality(self):
        ctx, warning = self._sq_context()
        if warning:
            if hasattr(self, "sq_text"):
                self.sq_text.delete("1.0", "end"); self.sq_text.insert("end", warning)
            return
        try:
            dash = self.ctx.search_quality_55_5.dashboard(ctx["case_id"], entity_id=ctx["entity_id"])
            if hasattr(self, "sq_query_tree"):
                self.sq_query_tree.delete(*self.sq_query_tree.get_children())
                for q in self.ctx.search_quality_55_5.list_quality_queries(ctx["case_id"], entity_id=ctx["entity_id"], category_key=self._category_key_from_value(self.sq_category.get())):
                    self.sq_query_tree.insert("", "end", values=(q.get("quality_query_id"), q.get("level_key"), q.get("category_key"), q.get("precision_bias"), q.get("query"), q.get("expected_evidence")))
            if hasattr(self, "sq_result_tree"):
                self.sq_result_tree.delete(*self.sq_result_tree.get_children())
                for r in dash.get("top_results", []):
                    self.sq_result_tree.insert("", "end", values=(r.get("result_id"), r.get("total_score"), r.get("ranking_label"), r.get("entity_match_score"), r.get("source_quality_score"), r.get("sensitivity_score"), r.get("title"), r.get("domain"), ", ".join(r.get("flags") or [])))
            if hasattr(self, "sq_text"):
                lines = [
                    "SEARCH QUALITY ENGINE – DASHBOARD",
                    f"Build: {dash.get('build')}",
                    f"Queries: {dash.get('query_count')} | Top-Ergebnisse: {len(dash.get('top_results', []))} | Duplikat-Cluster: {dash.get('duplicate_clusters',{}).get('cluster_count',0)}",
                    "",
                    "Queries nach Ebene:",
                ]
                for k,v in (dash.get("queries_by_level") or {}).items(): lines.append(f"- {k}: {v}")
                lines += ["", "Queries nach Kategorie:"]
                for k,v in (dash.get("queries_by_category") or {}).items(): lines.append(f"- {k}: {v}")
                lines += ["", "Feedback:"]
                for k,v in (dash.get("feedback_counts") or {}).items(): lines.append(f"- {k}: {v}")
                lines += ["", "Top Treffer:"]
                for r in dash.get("top_results", [])[:8]:
                    lines.append(f"- {r.get('total_score')} | {r.get('ranking_label')} | {r.get('title')} | {r.get('domain')} | Flags: {', '.join(r.get('flags') or [])}")
                lines += ["", "Qualitätsziel: Precision@10 erhöhen, Namensdoppler senken, Dubletten clustern, Feedback in Query-Strategie zurückführen."]
                self.sq_text.delete("1.0", "end"); self.sq_text.insert("end", "\n".join(lines))
        except Exception as exc:
            if hasattr(self, "sq_text"):
                self.sq_text.delete("1.0", "end"); self.sq_text.insert("end", "Research-Engine-Fehler: " + str(exc))


    def _tab_spearhead_engine(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2b Search Spearhead")
        header = ttk.LabelFrame(tab, text="Build 62.3 – Operational Research: Browser Helper, Claim Report Pro, Benchmark Suite, Adaptive Tuning")
        header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text="Kategorie:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.hs_category, values=self._category_options(), width=50, state="readonly").grid(row=0, column=1, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Mission anlegen", command=self.hs_create_mission).grid(row=0, column=2, padx=4, pady=3)
        ttk.Button(header, text="Top-Query: 10 Engines öffnen", command=self.hs_open_selected_query).grid(row=0, column=3, padx=4, pady=3)
        ttk.Button(header, text="SERP-Text importieren", command=self.hs_import_serp_text).grid(row=0, column=4, padx=4, pady=3)
        ttk.Button(header, text="Folgequeries ableiten", command=self.hs_recommend_next_queries).grid(row=0, column=5, padx=4, pady=3)
        ttk.Button(header, text="Aktualisieren", command=self.refresh_search_spearhead).grid(row=0, column=6, padx=4, pady=3)
        ttk.Label(header, text="Engine SERP:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.hs_engine, values=["google","bing","brave","duckduckgo","startpage","qwant","mojeek","ecosia","yahoo","swisscows"], width=16, state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(header, text="Feedback:").grid(row=1, column=2, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.hs_feedback_rating, values=["top_hit","relevant","useful","not_relevant","false_positive","name_doppler","counter_evidence"], width=18, state="readonly").grid(row=1, column=3, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Feedback speichern", command=self.hs_record_feedback).grid(row=1, column=4, padx=4, pady=3)
        ttk.Button(header, text="OSINT Core 59 starten", command=self.hs_start_osint_core_session).grid(row=2, column=0, padx=4, pady=3)
        ttk.Button(header, text="SERP in OSINT Core importieren", command=self.hs_import_serp_to_core).grid(row=2, column=1, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Graph/Claims/Actions aktualisieren", command=self.hs_refresh_osint_core).grid(row=2, column=2, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="OSINT 60 Profizyklus", command=self.hs_run_professional_osint_60).grid(row=2, column=4, padx=4, pady=3)
        ttk.Button(header, text="Evaluation 60", command=self.hs_evaluate_osint_60).grid(row=2, column=5, padx=4, pady=3)
        ttk.Button(header, text="Operational Import 61", command=self.hs_operational_import_61).grid(row=3, column=0, padx=4, pady=3)
        ttk.Button(header, text="Personen-Dashboard 61", command=self.hs_person_dashboard_61).grid(row=3, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(header, text="Kalibrieren/Tuning 61", command=self.hs_calibrate_tune_61).grid(row=3, column=2, padx=4, pady=3)
        ttk.Button(header, text="Browser Helper 62", command=self.hs_browser_helper_62).grid(row=4, column=0, padx=4, pady=3)
        ttk.Button(header, text="Capture/Clipboard 62 importieren", command=self.hs_import_capture_62).grid(row=4, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(header, text="Claim-Bericht Pro 62", command=self.hs_claim_report_62).grid(row=4, column=2, padx=4, pady=3)
        ttk.Button(header, text="Benchmark/Tuning 62", command=self.hs_benchmark_tuning_62).grid(row=4, column=3, padx=4, pady=3)
        ttk.Button(header, text="Research-Zyklus 62", command=self.hs_professional_research_cycle_62).grid(row=4, column=4, padx=4, pady=3)
        ttk.Button(header, text="Phase A: Capture Final", command=self.hs_phase_a_capture_final).grid(row=5, column=0, padx=4, pady=3)
        ttk.Button(header, text="Phase A: Funde bewerten", command=self.hs_phase_a_fund_final).grid(row=5, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(header, text="Phase A: Doppler/Report-Gate", command=self.hs_phase_a_entity_final).grid(row=5, column=2, padx=4, pady=3)
        ttk.Button(header, text="Phase A: Zyklus", command=self.hs_phase_a_cycle_final).grid(row=5, column=3, padx=4, pady=3)
        header.columnconfigure(1, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); mid = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(mid, weight=3); panes.add(right, weight=3)

        qbox = ttk.LabelFrame(left, text="Mission-Queries nach Priorität")
        qbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.hs_query_tree = ttk.Treeview(qbox, columns=("id","stage","prio","query","intent","risk"), show="headings", height=18)
        for c,h,w in [("id","Query-ID",115),("stage","Stufe",130),("prio","Prio",50),("query","Query",360),("intent","Zweck",260),("risk","Risiko",90)]:
            self.hs_query_tree.heading(c, text=h); self.hs_query_tree.column(c, width=w)
        self.hs_query_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.hs_query_tree.bind("<<TreeviewSelect>>", self._hs_select_query)

        rbox = ttk.LabelFrame(mid, text="Trefferkandidaten / Ranking")
        rbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.hs_result_tree = ttk.Treeview(rbox, columns=("id","score","label","fit","doppler","source","title","domain","flags"), show="headings", height=18)
        for c,h,w in [("id","Result-ID",115),("score","Score",55),("label","Label",120),("fit","Fit",50),("doppler","Doppler",65),("source","Quelle",55),("title","Titel",245),("domain","Domain",140),("flags","Flags",230)]:
            self.hs_result_tree.heading(c, text=h); self.hs_result_tree.column(c, width=w)
        self.hs_result_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.hs_result_tree.bind("<<TreeviewSelect>>", self._hs_select_result)

        sbox = ttk.LabelFrame(right, text="SERP-Paste + Dashboard")
        sbox.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Label(sbox, text="Suchmaschinen-Ergebnisse hier einfügen: Titel / URL / Snippet aus Browser kopieren.").pack(anchor="w", padx=4, pady=2)
        self.hs_serp_text = tk.Text(sbox, height=9, wrap="word")
        self.hs_serp_text.pack(fill="x", padx=4, pady=4)
        self.hs_dashboard_text = tk.Text(sbox, height=22, wrap="word")
        self.hs_dashboard_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _hs_context(self):
        cid = self.selected_case_id.get()
        entity_id = self._selected_intake_entity_id() or self.person_detail_selected_entity_id.get()
        if not cid:
            return None, "Bitte zuerst einen Fall anlegen oder auswählen."
        if not entity_id:
            return None, "Bitte zuerst eine Person/Organisation im Intake auswählen."
        try:
            ent = self.ctx.case_cockpit_54.get_entity(entity_id)
            return {"case_id": cid, "entity_id": entity_id, "entity": ent}, ""
        except Exception as exc:
            return None, str(exc)

    def _hs_select_query(self, event=None):
        sel = getattr(self, "hs_query_tree", None).selection() if hasattr(self, "hs_query_tree") else []
        if sel:
            vals = self.hs_query_tree.item(sel[0], "values")
            if vals:
                self.hs_selected_candidate_id.set(vals[0])

    def _hs_select_result(self, event=None):
        sel = getattr(self, "hs_result_tree", None).selection() if hasattr(self, "hs_result_tree") else []
        if sel:
            vals = self.hs_result_tree.item(sel[0], "values")
            if vals:
                self.hs_selected_result_id.set(vals[0])

    def hs_create_mission(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Search Spearhead", warning)
        try:
            category_key = self._category_key_from_value(self.hs_category.get())
            mission = self.ctx.search_spearhead_58_1.create_search_mission(ctx["case_id"], ctx["entity"], category_key, max_queries=28, max_engines_per_query=10)
            self.hs_selected_mission_id.set(mission["mission_id"])
            self.status.set(f"Search-Spearhead-Mission angelegt: {mission['mission_id']} | {mission.get('metrics',{}).get('query_count',0)} Queries")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("Search Spearhead", str(exc))

    def hs_open_selected_query(self):
        cid = self.hs_selected_candidate_id.get()
        if not cid:
            return messagebox.showwarning("Search Spearhead", "Bitte zuerst eine Mission-Query markieren.")
        try:
            links = self.ctx.search_spearhead_58_1.engine_links_for_candidate(cid, max_engines=10)
            ok = messagebox.askyesno("10 Engines öffnen", f"Es werden genau {links.get('count',0)} Suchmaschinen für diese eine Spearhead-Query geöffnet. Fortfahren?")
            if not ok:
                return
            for item in links.get("links", []):
                webbrowser.open(item.get("url", ""))
            self.status.set(f"{links.get('count',0)} Suchmaschinen geöffnet: {links.get('query','')[:80]}")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("Search Spearhead", str(exc))

    def hs_import_serp_text(self):
        mid = self.hs_selected_mission_id.get()
        if not mid:
            return messagebox.showwarning("Search Spearhead", "Bitte zuerst eine Search-Spearhead-Mission anlegen.")
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        if not raw:
            return messagebox.showwarning("SERP-Import", "Bitte Suchergebnis-Text mit URLs einfügen.")
        try:
            res = self.ctx.search_spearhead_58_1.import_serp_text(mid, raw, engine=self.hs_engine.get(), candidate_id=self.hs_selected_candidate_id.get())
            self.status.set(f"SERP importiert: {res.get('parsed_count',0)} Trefferkandidaten")
            self.refresh_search_spearhead(); self.refresh_person_detail_page(); self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("SERP-Import", str(exc))

    def hs_recommend_next_queries(self):
        mid = self.hs_selected_mission_id.get()
        if not mid:
            return messagebox.showwarning("Search Spearhead", "Bitte zuerst eine Mission auswählen/anlegen.")
        try:
            rec = self.ctx.search_spearhead_58_1.recommend_next_queries(mid, limit=10)
            self.status.set(f"Adaptive Folgequeries erzeugt: {rec.get('recommended_count',0)}")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("Folgequeries", str(exc))

    def hs_record_feedback(self):
        rid = self.hs_selected_result_id.get()
        if not rid:
            return messagebox.showwarning("Search Spearhead", "Bitte zuerst einen Trefferkandidaten markieren.")
        try:
            fb = self.ctx.search_spearhead_58_1.record_learning_feedback(rid, self.hs_feedback_rating.get(), note="UI Feedback Build 58.1")
            self.status.set("Spearhead-Feedback gespeichert: " + fb.get("rating", ""))
            self.refresh_search_spearhead(); self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("Spearhead Feedback", str(exc))

    def hs_start_osint_core_session(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("OSINT Core 59", warning)
        try:
            category_key = self._category_key_from_value(self.hs_category.get())
            sess = self.ctx.osint_core_59_0.start_session(ctx["case_id"], ctx["entity"], category_key)
            self.osint_core_selected_session_id.set(sess["session_id"])
            self.hs_selected_mission_id.set(sess["mission_id"])
            self.status.set(f"OSINT Core 59 gestartet: {sess['session_id']} | Mission {sess['mission_id']}")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("OSINT Core 59", str(exc))

    def _ensure_osint_core_session(self):
        sid = self.osint_core_selected_session_id.get()
        if sid:
            return sid
        ctx, warning = self._hs_context()
        if warning:
            raise RuntimeError(warning)
        category_key = self._category_key_from_value(self.hs_category.get())
        sess = self.ctx.osint_core_59_0.latest_or_start(ctx["case_id"], ctx["entity"], category_key)
        self.osint_core_selected_session_id.set(sess["session_id"])
        self.hs_selected_mission_id.set(sess["mission_id"])
        return sess["session_id"]

    def hs_import_serp_to_core(self):
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        if not raw:
            return messagebox.showwarning("OSINT Core 59", "Bitte Suchergebnis-Text mit URLs einfügen.")
        try:
            sid = self._ensure_osint_core_session()
            res = self.ctx.osint_core_59_0.import_result_feed(sid, raw, engine=self.hs_engine.get(), candidate_id=self.hs_selected_candidate_id.get())
            self.status.set(f"OSINT Core Feed importiert: {res.get('result_count',0)} Treffer | Claims {res.get('claims',{}).get('claim_count',0)}")
            self.refresh_search_spearhead(); self.refresh_person_detail_page(); self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("OSINT Core 59", str(exc))

    def hs_refresh_osint_core(self):
        try:
            sid = self._ensure_osint_core_session()
            self.ctx.osint_core_59_0.build_source_graph(sid)
            claims = self.ctx.osint_core_59_0.build_claims(sid)
            actions = self.ctx.osint_core_59_0.generate_next_actions(sid)
            self.status.set(f"OSINT Core aktualisiert: Claims {claims.get('claim_count',0)} | Actions {actions.get('recommended_count',0)}")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("OSINT Core 59", str(exc))

    def hs_evaluate_osint_60(self):
        try:
            sid = self._ensure_osint_core_session()
            ev = self.ctx.osint_eval_lab_60.evaluate_session(sid)
            self.status.set(f"OSINT Evaluation 60: {ev.get('overall_score')} | {ev.get('professional_label')}")
            self.refresh_search_spearhead()
        except Exception as exc:
            messagebox.showerror("OSINT Evaluation 60", str(exc))

    def hs_run_professional_osint_60(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("OSINT 60", warning)
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        try:
            category_key = self._category_key_from_value(self.hs_category.get())
            cycle = self.ctx.professional_osint_60.run_professional_cycle(ctx["case_id"], ctx["entity"], category_key, serp_text=raw, engine=self.hs_engine.get() or "manual_serp_capture")
            self.osint_core_selected_session_id.set(cycle["session"]["session_id"])
            self.hs_selected_mission_id.set(cycle["session"]["mission_id"])
            self.status.set(f"OSINT 60 Profizyklus: {cycle['evaluation'].get('overall_score')} | Paket {cycle['package'].get('package_id')}")
            self.refresh_search_spearhead(); self.refresh_person_detail_page(); self.refresh_search_quality()
        except Exception as exc:
            messagebox.showerror("OSINT 60", str(exc))


    def hs_browser_helper_62(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Browser Helper 62", warning)
        try:
            helper = self.ctx.browser_helper_62.create_helper_session(ctx["case_id"], ctx["entity_id"])
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end")
                self.hs_dashboard_text.insert("end", "BROWSER HELPER 62\n\nHelper-Datei:\n" + helper.get("helper_path", "") + "\n\nBookmarklet:\n" + helper.get("bookmarklet", "") + "\n\nNutzung: Helper-Datei öffnen oder Bookmarklet als Lesezeichen speichern. Auf öffentlicher Trefferseite anklicken, JSON kopieren und im SERP/Capture-Feld einfügen.")
            self.status.set("Browser Helper 62 erzeugt: " + helper.get("helper_path", ""))
        except Exception as exc:
            messagebox.showerror("Browser Helper 62", str(exc))

    def hs_import_capture_62(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Capture 62", warning)
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        if not raw:
            return messagebox.showwarning("Capture 62", "Bitte Browser-Capture-JSON, URL oder SERP-Block einfügen.")
        try:
            category_key = self._category_key_from_value(self.hs_category.get())
            # JSON/single URL/import block: try payload first, fallback to SERP block.
            try:
                res = self.ctx.browser_helper_62.import_payload(ctx["case_id"], ctx["entity_id"], raw, category_key=category_key, query="", engine=self.hs_engine.get() or "browser_helper")
                count = 1
            except Exception:
                res = self.ctx.browser_helper_62.import_serp_clipboard(ctx["case_id"], ctx["entity_id"], raw, category_key=category_key, query="", engine=self.hs_engine.get() or "browser_clipboard")
                count = int(res.get("count", 0))
            self.status.set(f"Capture 62 importiert: {count} Treffer/Funde")
            self.refresh_search_spearhead(); self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Capture 62", str(exc))

    def hs_claim_report_62(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Claim-Bericht 62", warning)
        try:
            sid = self.osint_core_selected_session_id.get()
            report = self.ctx.claim_report_62.build_report(ctx["case_id"], ctx["entity_id"], session_id=sid, save_to_person_file=True)
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end")
                self.hs_dashboard_text.insert("end", report.get("body", ""))
            self.status.set(f"Claim-Bericht 62 erzeugt: {report.get('export_readiness')} | Narrative {report.get('narrative_id')}")
            self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Claim-Bericht 62", str(exc))

    def hs_benchmark_tuning_62(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Benchmark 62", warning)
        try:
            sid = self.osint_core_selected_session_id.get()
            bench = self.ctx.osint_benchmark_suite_62.run_suite(ctx["case_id"], ctx["entity_id"], session_id=sid, scenario_key="person_org")
            tune = self.ctx.adaptive_tuning_62.create_profile(ctx["case_id"], ctx["entity_id"])
            lines = ["BENCHMARK / ADAPTIVES TUNING – 62.0", f"Suite Score: {bench.get('metrics',{}).get('suite_score')}", f"Precision@10 Proxy: {bench.get('metrics',{}).get('precision_at_10_proxy')}", "", "Benchmark-Befunde:"]
            for item in bench.get("findings", []): lines.append("- " + item)
            lines += ["", "Tuning-Empfehlungen:"]
            for item in tune.get("recommendations", []): lines.append("- " + item)
            lines += ["", "Query-Gewichte:", str(tune.get("query_weights", {})), "", "Quellen-Gewichte:", str(tune.get("source_weights", {}))]
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "\n".join(lines))
            self.status.set("Benchmark/Tuning 62 erstellt.")
        except Exception as exc:
            messagebox.showerror("Benchmark/Tuning 62", str(exc))

    def hs_professional_research_cycle_62(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Research-Zyklus 62", warning)
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        try:
            cycle = self.ctx.professional_research_62.run_cycle(
                ctx["case_id"], ctx["entity_id"], capture_text=raw,
                category_key=self._category_key_from_value(self.hs_category.get()),
                engine=self.hs_engine.get() or "browser_capture", session_id=self.osint_core_selected_session_id.get(),
            )
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end")
                self.hs_dashboard_text.insert("end", "PROFESSIONAL RESEARCH CYCLE 62\n\n" + cycle.get("report", {}).get("body", "") + "\n\nPaket: " + cycle.get("package", {}).get("path", ""))
            self.status.set(f"Research-Zyklus 62: {cycle.get('imported_count')} Treffer importiert | Paket {cycle.get('package',{}).get('path','')}")
            self.refresh_search_spearhead(); self.refresh_person_detail_page()
        except Exception as exc:
            messagebox.showerror("Research-Zyklus 62", str(exc))

    def hs_operational_import_61(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Operational Research 61", warning)
        raw = self.hs_serp_text.get("1.0", "end").strip() if hasattr(self, "hs_serp_text") else ""
        if not raw:
            return messagebox.showwarning("Operational Research 61", "Bitte Suchergebnis-Text aus dem Browser einfügen.")
        try:
            sid = ""
            try:
                sid = self._ensure_osint_core_session()
            except Exception:
                sid = ""
            cycle = self.ctx.operational_research_61_0.run_cycle(
                ctx["case_id"], ctx["entity_id"], raw_serp_text=raw,
                category_key=self._category_key_from_value(self.hs_category.get()),
                query="", engine=self.hs_engine.get() or "manual_serp", session_id=sid,
            )
            self.status.set(f"Operational Research 61: {len(cycle.get('captures', []))} Treffer übernommen, {len(cycle.get('assessments', []))} Fit-Prüfungen")
            self.refresh_search_spearhead(); self.refresh_person_detail_page()
        except Exception as exc:
            msg = self.ctx.ux_polish_61_2.humanize_error(str(exc)) if hasattr(self.ctx, "ux_polish_61_2") else str(exc)
            messagebox.showerror("Operational Research 61", msg)

    def hs_person_dashboard_61(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Personen-Dashboard 61", warning)
        try:
            dash = self.ctx.person_dashboard_60_4.dashboard(ctx["case_id"], ctx["entity_id"])
            lines = [
                "PERSONENAKTE RESEARCH DASHBOARD – 61.2",
                f"Entity: {dash.get('entity', {}).get('display_name', ctx['entity_id'])}",
                f"Funde: {dash.get('metrics', {}).get('finding_count')} | Claims: {dash.get('metrics', {}).get('claim_count')} | Doppler hoch: {dash.get('metrics', {}).get('doppler_high')}",
                "",
                "Statusampel:",
            ]
            for k, v in (dash.get("status_ampel") or {}).items():
                lines.append(f"- {k}: {v}")
            lines += ["", "Nächste Aktionen:"]
            for a in dash.get("next_actions", [])[:10]:
                lines.append(f"- Prio {a.get('priority')}: {a.get('title')} {a.get('query','')}")
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "\n".join(lines))
            self.status.set("Personen-Dashboard 61 aktualisiert.")
        except Exception as exc:
            messagebox.showerror("Personen-Dashboard 61", str(exc))

    def hs_calibrate_tune_61(self):
        ctx, warning = self._hs_context()
        if warning:
            return messagebox.showwarning("Kalibrierung 61", warning)
        try:
            sid = self.osint_core_selected_session_id.get()
            cal = self.ctx.osint_calibration_60_5.evaluate_entity(ctx["case_id"], ctx["entity_id"], session_id=sid)
            tune = self.ctx.osint_tuning_61_1.create_tuning_report(ctx["case_id"], ctx["entity_id"])
            lines = [
                "OSINT KALIBRIERUNG / TUNING – 61.2",
                f"Operational Score: {cal.get('metrics', {}).get('operational_score')}",
                "", "Empfehlungen:",
            ]
            for r in cal.get("recommendations", []): lines.append("- " + r)
            lines += ["", "Tuning:"]
            for r in tune.get("recommendations", []): lines.append("- " + r)
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "\n".join(lines))
            self.status.set("Kalibrierung/Tuning 61 erstellt.")
        except Exception as exc:
            messagebox.showerror("Kalibrierung 61", str(exc))

    # Build 185.1: canonical Phase-A actions. These replace four dangling UI callbacks
    # that previously prevented the desktop window from being constructed.
    def hs_phase_a_capture_final(self):
        return self.hs_import_capture_62()

    def hs_phase_a_fund_final(self):
        return self.hs_operational_import_61()

    def hs_phase_a_entity_final(self):
        return self.hs_claim_report_62()

    def hs_phase_a_cycle_final(self):
        return self.hs_professional_research_cycle_62()

    def refresh_search_spearhead(self):
        ctx, warning = self._hs_context()
        if warning:
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", warning)
            return
        try:
            mid = self.hs_selected_mission_id.get()
            if not mid:
                missions = self.ctx.search_spearhead_58_1.list_missions(ctx["case_id"], ctx["entity_id"], limit=1)
                if missions:
                    mid = missions[0]["mission_id"]; self.hs_selected_mission_id.set(mid)
            if not mid:
                if hasattr(self, "hs_dashboard_text"):
                    self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "Noch keine Search-Spearhead-Mission. Kategorie wählen und Mission anlegen.")
                return
            dash = self.ctx.search_spearhead_58_1.dashboard(mid)
            if hasattr(self, "hs_query_tree"):
                self.hs_query_tree.delete(*self.hs_query_tree.get_children())
                for q in dash.get("top_queries", []):
                    self.hs_query_tree.insert("", "end", values=(q.get("candidate_id"), q.get("stage"), q.get("priority"), q.get("query"), q.get("intent"), q.get("pii_risk")))
            if hasattr(self, "hs_result_tree"):
                self.hs_result_tree.delete(*self.hs_result_tree.get_children())
                for r in dash.get("top_results", []):
                    self.hs_result_tree.insert("", "end", values=(r.get("result_candidate_id"), r.get("total_score"), r.get("ranking_label"), r.get("identity_fit"), r.get("doppler_risk"), r.get("source_weight"), r.get("title"), r.get("domain"), ", ".join(r.get("flags") or [])))
            if hasattr(self, "hs_dashboard_text"):
                m = dash.get("metrics", {})
                ready = dash.get("professional_readiness", {})
                lines = [
                    "SEARCH SPEARHEAD ENGINE – DASHBOARD",
                    f"Mission: {mid}",
                    f"Queries: {dash.get('query_count')} | Treffer: {dash.get('result_count')} | Readiness: {ready.get('score')}%",
                    f"Top10 Ø Score: {m.get('top10_avg_score')} | Strong Candidates: {m.get('strong_candidates')} | Duplicate Rate: {m.get('duplicate_rate')}",
                    "",
                    "Queries nach Stufe:",
                ]
                for k,v in (dash.get("queries_by_stage") or {}).items(): lines.append(f"- {k}: {v}")
                lines += ["", "Feedback:"]
                for k,v in (dash.get("feedback_counts") or {}).items(): lines.append(f"- {k}: {v}")
                if ready.get("gaps"):
                    lines += ["", "Nächste Qualitätslücken:"] + [f"- {g}" for g in ready.get("gaps", [])]
                lines += ["", "Top Treffer:"]
                for r in dash.get("top_results", [])[:8]:
                    lines.append(f"- {r.get('total_score')} | {r.get('ranking_label')} | {r.get('title')} | {r.get('domain')} | Actions: {', '.join(r.get('recommended_actions') or [])}")
                sid = self.osint_core_selected_session_id.get()
                if sid:
                    try:
                        core = self.ctx.osint_core_59_0.dashboard(sid)
                        cr = core.get("professional_readiness", {})
                        graph = core.get("graph", {})
                        lines += ["", "OSINT SEARCH CORE 59 – STABLE", f"Session: {sid}", f"Readiness: {cr.get('score')}% | Claims: {len(core.get('claims', []))} | Graph Nodes/Edges: {graph.get('node_count')}/{graph.get('edge_count')}"]
                        if cr.get("gaps"):
                            lines += ["Core-Lücken:"] + [f"- {g}" for g in cr.get("gaps", [])]
                        lines += ["Nächste Aktionen:"] + [f"- {a.get('priority')} | {a.get('title')} | {a.get('query')}" for a in core.get("next_actions", [])[:5]]
                        try:
                            ev = self.ctx.osint_eval_lab_60.latest(ctx["case_id"], ctx["entity_id"], limit=1)
                            if ev:
                                lines += ["", "OSINT 60 – PROFESSIONAL EVALUATION", f"Score: {ev[0].get('overall_score')} | Label: {ev[0].get('professional_label')}"]
                                if ev[0].get("gaps"):
                                    lines += ["Qualitätslücken:"] + [f"- {g}" for g in ev[0].get("gaps", [])]
                        except Exception:
                            pass
                    except Exception as core_exc:
                        lines += ["", "OSINT Core 59 Fehler: " + str(core_exc)]
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "\n".join(lines))
        except Exception as exc:
            if hasattr(self, "hs_dashboard_text"):
                self.hs_dashboard_text.delete("1.0", "end"); self.hs_dashboard_text.insert("end", "Search-Spearhead-Fehler: " + str(exc))

    def _tab_one_page_outputs(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="3 Profil / Bericht / Fallakte")
        header = ttk.LabelFrame(tab, text="Build 56.0 – Profil/Bericht/Fallakte mit Datenschutz-, Stable- und Research-Quality-Gate")
        header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text="Phase 3–6: Entwurf, Redaktion, PrivacyGate, Profi-Export und Stable-Audit in einem klaren Ausgabe-Workflow.").grid(row=0, column=0, columnspan=8, sticky="w", padx=4, pady=3)
        ttk.Label(header, text="Ausgabe:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.output_type, values=["profile", "report", "casefile", "authority_handover", "missing_child_brief", "organization_profile", "antisemitism_incident_profile"], width=20, state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(header, text="Empfänger:").grid(row=1, column=2, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.output_recipient, values=["authority_or_meldestelle", "internal_analyst", "police", "rias_or_community_security", "child_protection", "client_redacted"], width=28).grid(row=1, column=3, sticky="w", padx=4, pady=3)
        ttk.Label(header, text="Redaktion:").grid(row=1, column=4, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.output_redaction, values=["redacted", "internal", "minimal_public", "authority_sensitive"], width=18).grid(row=1, column=5, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Entwurf aus Chain erzeugen", command=self.output_create_editor_draft).grid(row=1, column=6, padx=4, pady=3)
        ttk.Button(header, text="Entwurf speichern", command=self.output_save_editor_draft).grid(row=1, column=7, padx=4, pady=3)
        ttk.Button(header, text="Profi-Exportpaket", command=self.output_create_professional_export).grid(row=1, column=8, padx=4, pady=3)
        ttk.Button(header, text="MD erzeugen", command=self.output_create_markdown).grid(row=2, column=6, padx=4, pady=3)
        ttk.Button(header, text="Fallakte-Bundle erzeugen", command=self.output_create_casefile_bundle).grid(row=2, column=7, padx=4, pady=3)
        ttk.Button(header, text="aktualisieren", command=self.refresh_one_page_outputs).grid(row=2, column=8, padx=4, pady=3)
        ttk.Label(header, text="Entwurfsstatus:").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(header, textvariable=self.output_draft_status, values=["draft", "review", "approved", "redaction_required", "blocked"], width=18, state="readonly").grid(row=2, column=1, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(header, text="Export freigegeben", variable=self.output_export_approved).grid(row=2, column=2, sticky="w", padx=4, pady=3)
        ttk.Button(header, text="Datenschutz-/Exportprüfung", command=self.output_privacy_check).grid(row=2, column=3, padx=4, pady=3)
        ttk.Button(header, text="Text redigieren", command=self.output_redact_preview_text).grid(row=2, column=4, padx=4, pady=3)
        ttk.Button(header, text="Stable-Audit", command=self.output_stable_audit).grid(row=2, column=5, padx=4, pady=3)
        ttk.Button(header, text="Phase B: Final-Fallakte 62.5", command=self.output_create_phase_b_casefile_final).grid(row=3, column=6, padx=4, pady=3)
        ttk.Button(header, text="Phase B: Zyklus", command=self.output_run_phase_b_cycle).grid(row=3, column=7, padx=4, pady=3)
        header.columnconfigure(0, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=2); panes.add(right, weight=5)

        outputs_box = ttk.LabelFrame(left, text="Erzeugte Ausgaben")
        outputs_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_tree = ttk.Treeview(outputs_box, columns=("id","type","recipient","redaction","sha","path"), show="headings", height=18)
        for c,h,w in [("id","ID",150),("type","Typ",120),("recipient","Empfänger",190),("redaction","Redaktion",110),("sha","SHA-256",170),("path","Pfad",380)]:
            self.output_tree.heading(c, text=h); self.output_tree.column(c, width=w)
        self.output_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_tree.bind("<<TreeviewSelect>>", self._select_one_page_output)
        ttk.Button(outputs_box, text="markierte Ausgabe öffnen", command=self.output_open_selected).pack(anchor="e", padx=4, pady=4)

        drafts_box = ttk.LabelFrame(left, text="Editor-Entwürfe")
        drafts_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_draft_tree = ttk.Treeview(drafts_box, columns=("id","type","status","redaction","approved","updated"), show="headings", height=8)
        for c,h,w in [("id","Draft",150),("type","Typ",120),("status","Status",90),("redaction","Redaktion",120),("approved","Freigabe",80),("updated","Aktualisiert",150)]:
            self.output_draft_tree.heading(c, text=h); self.output_draft_tree.column(c, width=w)
        self.output_draft_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_draft_tree.bind("<<TreeviewSelect>>", self._select_one_page_draft)

        privacy_box = ttk.LabelFrame(left, text="Datenschutz-/Stable-Prüfung")
        privacy_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_privacy_text = tk.Text(privacy_box, height=10, wrap="word")
        self.output_privacy_text.pack(fill="both", expand=True, padx=4, pady=4)

        preview_box = ttk.LabelFrame(right, text="Profil-/Berichtseditor – bearbeitbarer Entwurf")
        preview_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.output_preview_text = tk.Text(preview_box, wrap="word")
        self.output_preview_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _active_output_context(self):
        ent, warning = self._ensure_one_page_context()
        if warning:
            return None, warning
        return {"case_id": self.selected_case_id.get(), "entity_id": self._selected_intake_entity_id()}, ""

    def output_create_markdown(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Ausgabe", warning)
        try:
            out = self.ctx.one_page_output_54.create_markdown_output(
                ctx["case_id"], entity_id=ctx.get("entity_id", ""), output_type=self.output_type.get(), recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get()
            )
            self.output_selected_id.set(out["output_id"])
            self.status.set("Ausgabe erzeugt: " + out["output_path"])
            self.refresh_one_page_outputs()
            self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", out.get("markdown", ""))
        except Exception as exc:
            messagebox.showerror("Ausgabe", str(exc))

    def output_create_casefile_bundle(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Fallakte", warning)
        try:
            bundle = self.ctx.one_page_output_54.create_casefile_bundle(
                ctx["case_id"], entity_id=ctx.get("entity_id", ""), recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get()
            )
            self.status.set("Fallakte-Bundle erzeugt: " + bundle["bundle_path"])
            self.refresh_one_page_outputs()
            if hasattr(self, "output_preview_text"):
                self.output_preview_text.delete("1.0", "end")
                self.output_preview_text.insert("end", "FALLAKTE-BUNDLE ERZEUGT\n\n" + "\n".join(f"{k}: {v}" for k,v in bundle.items() if k != "manifest"))
        except Exception as exc:
            messagebox.showerror("Fallakte", str(exc))

    def output_create_editor_draft(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Editor", warning)
        try:
            draft = self.ctx.one_page_output_54.create_editor_draft(
                ctx["case_id"], entity_id=ctx.get("entity_id", ""), output_type=self.output_type.get(), recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get()
            )
            self.output_selected_draft_id.set(draft["draft_id"])
            self.output_draft_status.set(draft.get("status", "draft"))
            self.output_export_approved.set(bool(draft.get("export_approved", 0)))
            self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", draft.get("body", ""))
            self.status.set("Editor-Entwurf aus Chain erzeugt: " + draft["draft_id"])
            self.refresh_one_page_outputs()
        except Exception as exc:
            messagebox.showerror("Editor", str(exc))

    def output_save_editor_draft(self):
        draft_id = self.output_selected_draft_id.get()
        if not draft_id:
            return messagebox.showwarning("Editor", "Bitte zuerst einen Editor-Entwurf erzeugen oder markieren.")
        try:
            body = self.output_preview_text.get("1.0", "end").rstrip() + "\n"
            draft = self.ctx.one_page_output_54.update_editor_draft(
                draft_id, body=body, status=self.output_draft_status.get(), redaction_status=self.output_redaction.get(), export_approved=bool(self.output_export_approved.get())
            )
            self.status.set("Editor-Entwurf gespeichert: " + draft["draft_id"])
            self.refresh_one_page_outputs()
        except Exception as exc:
            messagebox.showerror("Editor", str(exc))

    def output_create_professional_export(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Profi-Export", warning)
        try:
            draft_id = self.output_selected_draft_id.get()
            bundle = self.ctx.one_page_output_54.create_professional_export_bundle(
                ctx["case_id"], entity_id=ctx.get("entity_id", ""), draft_id=draft_id, recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get()
            )
            self.status.set("Professionelles Exportpaket erzeugt: " + bundle["bundle_path"])
            self.refresh_one_page_outputs()
            self.output_preview_text.delete("1.0", "end")
            privacy = bundle.get("manifest", {}).get("privacy_review", {})
            self.output_preview_text.insert("end", "PROFESSIONELLES EXPORTPAKET ERZEUGT\n\n" + "\n".join(f"{k}: {v}" for k, v in bundle.items() if k != "manifest") + "\n\nPrivacyGate: " + str(privacy.get("decision", "not_run")))
        except Exception as exc:
            messagebox.showerror("Profi-Export", str(exc))



    def output_create_phase_b_casefile_final(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Phase B Final-Fallakte", warning)
        try:
            out = self.ctx.phase_b_casefile_62_5.create_final_casefile(ctx["case_id"], ctx.get("entity_id", ""), export_mode="authority_redacted")
            self.output_preview_text.delete("1.0", "end")
            self.output_preview_text.insert("end", "PHASE B FINAL-FALLAKTE ERZEUGT\n\n" + out.get("path", "") + "\n\nEntscheidung: " + out.get("export_decision", ""))
            self.output_privacy_text.delete("1.0", "end")
            self.output_privacy_text.insert("end", "Privacy/Redaction: " + str(out.get("privacy", {})))
            self.status.set("Phase-B-Final-Fallakte erzeugt: " + out.get("path", ""))
        except Exception as exc:
            messagebox.showerror("Phase B Final-Fallakte", str(exc))

    def output_run_phase_b_cycle(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Phase B Zyklus", warning)
        try:
            out = self.ctx.phase_b_ops_62_5.run_phase_b_cycle(ctx["case_id"], ctx.get("entity_id", ""), export_mode="authority_redacted")
            self.output_preview_text.delete("1.0", "end")
            self.output_preview_text.insert("end", "PHASE B ZYKLUS ABGESCHLOSSEN\n\n" + str(out.get("summary", {})) + "\n\nExport: " + str(out.get("casefile_export", {}).get("path", "")))
            self.status.set("Phase-B-Zyklus abgeschlossen: " + out.get("phase_b_cycle_id", ""))
        except Exception as exc:
            messagebox.showerror("Phase B Zyklus", str(exc))

    def output_privacy_check(self):
        ctx, warning = self._active_output_context()
        if warning:
            return messagebox.showwarning("Datenschutzprüfung", warning)
        try:
            draft_id = self.output_selected_draft_id.get()
            text = self.output_preview_text.get("1.0", "end").rstrip()
            review = self.ctx.privacy_finish_55.assess_export(
                ctx["case_id"], entity_id=ctx.get("entity_id", ""), draft_id=draft_id,
                recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get(), text=text
            )
            lines = [
                "DATENSCHUTZ-/EXPORTPRÜFUNG BUILD 55.3",
                f"Entscheidung: {review.get('decision')}",
                f"Schweregrad: {review.get('severity')}",
                f"Flags: {len(review.get('flags', []))}",
                f"Blocker: {len(review.get('blockers', []))}",
                "",
                "Blocker:",
            ]
            for b in review.get("blockers", [])[:20]:
                lines.append("- " + str(b))
            lines.append("\nEmpfohlene Aktionen:")
            for a in review.get("actions", [])[:30]:
                lines.append("- " + str(a))
            self.output_privacy_text.delete("1.0", "end"); self.output_privacy_text.insert("end", "\n".join(lines))
            self.status.set("Datenschutzprüfung: " + review.get("decision", "unknown"))
        except Exception as exc:
            messagebox.showerror("Datenschutzprüfung", str(exc))

    def output_redact_preview_text(self):
        try:
            text = self.output_preview_text.get("1.0", "end")
            res = self.ctx.privacy_finish_55.redact_text(text, level=self.output_redaction.get())
            self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", res.get("text", ""))
            self.output_privacy_text.delete("1.0", "end"); self.output_privacy_text.insert("end", f"Redigiert: {res.get('replacement_count', 0)} Ersetzungen\nSHA-256: {res.get('sha256')}")
            self.status.set("Text redigiert; bitte Entwurf speichern und Export prüfen.")
        except Exception as exc:
            messagebox.showerror("Redaktion", str(exc))

    def output_stable_audit(self):
        try:
            audit = self.ctx.stable_release_55.run_static_audit()
            lines = ["STABLE-AUDIT BUILD 55.3", f"Entscheidung: {audit.get('decision')}", ""]
            for c in audit.get("checks", []):
                lines.append(f"{c.get('status').upper()} | {c.get('name')} | {c.get('details')}")
            self.output_privacy_text.delete("1.0", "end"); self.output_privacy_text.insert("end", "\n".join(lines))
            self.status.set("Stable-Audit: " + audit.get("decision", "unknown"))
        except Exception as exc:
            messagebox.showerror("Stable-Audit", str(exc))

    def _select_one_page_draft(self, event=None):
        sel = getattr(self, "output_draft_tree", None).selection() if hasattr(self, "output_draft_tree") else []
        if sel:
            vals = self.output_draft_tree.item(sel[0], "values")
            if vals:
                draft_id = vals[0]
                self.output_selected_draft_id.set(draft_id)
                try:
                    draft = self.ctx.one_page_output_54.get_editor_draft(draft_id)
                    self.output_draft_status.set(draft.get("status", "draft"))
                    self.output_redaction.set(draft.get("redaction_status", "redacted"))
                    self.output_export_approved.set(bool(draft.get("export_approved", 0)))
                    self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", draft.get("body", ""))
                except Exception as exc:
                    self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", str(exc))

    def _select_one_page_output(self, event=None):
        sel = getattr(self, "output_tree", None).selection() if hasattr(self, "output_tree") else []
        if sel:
            vals = self.output_tree.item(sel[0], "values")
            if vals:
                self.output_selected_id.set(vals[0])
                try:
                    row = self.ctx.one_page_output_54.get_output(vals[0])
                    p = Path(row.get("output_path", ""))
                    text = p.read_text(encoding="utf-8") if p.exists() else str(row)
                    self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", text)
                except Exception as exc:
                    self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", str(exc))

    def output_open_selected(self):
        oid = self.output_selected_id.get()
        if not oid:
            return messagebox.showwarning("Ausgabe", "Bitte eine Ausgabe markieren.")
        try:
            row = self.ctx.one_page_output_54.get_output(oid)
            webbrowser.open(Path(row["output_path"]).as_uri())
        except Exception as exc:
            messagebox.showerror("Ausgabe", str(exc))

    def refresh_one_page_outputs(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            if hasattr(self, "output_tree"):
                self.output_tree.delete(*self.output_tree.get_children())
                for row in self.ctx.one_page_output_54.latest_outputs(cid):
                    self.output_tree.insert("", "end", values=(row.get("output_id"), row.get("output_type"), row.get("recipient_class"), row.get("redaction_level"), row.get("sha256"), row.get("output_path")))
            if hasattr(self, "output_draft_tree"):
                self.output_draft_tree.delete(*self.output_draft_tree.get_children())
                for row in self.ctx.one_page_output_54.list_editor_drafts(cid):
                    self.output_draft_tree.insert("", "end", values=(row.get("draft_id"), row.get("output_type"), row.get("status"), row.get("redaction_status"), "ja" if row.get("export_approved") else "nein", row.get("updated_at")))
            if hasattr(self, "output_preview_text") and not self.output_preview_text.get("1.0", "end").strip():
                entity_id = self._selected_intake_entity_id()
                preview = self.ctx.one_page_output_54.build_markdown(cid, entity_id=entity_id, output_type=self.output_type.get(), recipient_class=self.output_recipient.get(), redaction_level=self.output_redaction.get())
                self.output_preview_text.insert("end", preview)
        except Exception as exc:
            if hasattr(self, "output_preview_text"):
                self.output_preview_text.delete("1.0", "end"); self.output_preview_text.insert("end", "Ausgabe-Fehler: " + str(exc))

    def _tab_cockpit(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="0 Fall-Cockpit")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – Enterprise Packaging / Installation / Migration / Rollback")
        top.pack(fill="x",padx=8,pady=8)
        self.cockpit_score=tk.StringVar(value="Score: –")
        self.cockpit_light=tk.StringVar(value="Ampel: –")
        self.cockpit_case=tk.StringVar(value="Fall: –")
        ttk.Label(top,textvariable=self.cockpit_case,font=("Arial",11,"bold")).grid(row=0,column=0,sticky="w",padx=4,pady=3)
        ttk.Label(top,textvariable=self.cockpit_score).grid(row=0,column=1,sticky="w",padx=16,pady=3)
        ttk.Label(top,textvariable=self.cockpit_light).grid(row=0,column=2,sticky="w",padx=16,pady=3)
        ttk.Button(top,text="Cockpit aktualisieren",command=self.refresh_cockpit).grid(row=0,column=3,padx=4,pady=3)
        ttk.Button(top,text="Snapshot speichern",command=self.save_cockpit_snapshot).grid(row=0,column=4,padx=4,pady=3)
        ttk.Button(top,text="Report-Readiness prüfen",command=self.cockpit_run_readiness).grid(row=0,column=5,padx=4,pady=3)
        ttk.Button(top,text="Graph/Timeline neu aufbauen",command=self.cockpit_rebuild_analysis).grid(row=0,column=6,padx=4,pady=3)
        top.columnconfigure(0,weight=1)

        paned=ttk.Panedwindow(tab,orient="horizontal"); paned.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(paned); right=ttk.Frame(paned)
        paned.add(left,weight=2); paned.add(right,weight=3)

        kpi_box=ttk.LabelFrame(left,text="KPI / Fallstatus")
        kpi_box.pack(fill="both",expand=True,padx=4,pady=4)
        self.cockpit_kpi_tree=ttk.Treeview(kpi_box,columns=("metric","value"),show="headings",height=17)
        for c,h,w in [("metric","Metrik",220),("value","Wert",110)]: self.cockpit_kpi_tree.heading(c,text=h); self.cockpit_kpi_tree.column(c,width=w)
        self.cockpit_kpi_tree.pack(fill="both",expand=True,padx=4,pady=4)

        gate_box=ttk.LabelFrame(left,text="Gates")
        gate_box.pack(fill="both",expand=True,padx=4,pady=4)
        self.cockpit_gate_tree=ttk.Treeview(gate_box,columns=("gate","state"),show="headings",height=12)
        for c,h,w in [("gate","Gate",220),("state","Ampel",110)]: self.cockpit_gate_tree.heading(c,text=h); self.cockpit_gate_tree.column(c,width=w)
        self.cockpit_gate_tree.pack(fill="both",expand=True,padx=4,pady=4)

        text_box=ttk.LabelFrame(right,text="Blocker, Warnungen und nächste Schritte")
        text_box.pack(fill="both",expand=True,padx=4,pady=4)
        self.cockpit_text=tk.Text(text_box,height=22,wrap="word")
        self.cockpit_text.pack(fill="both",expand=True,padx=4,pady=4)

        queue_box=ttk.LabelFrame(right,text="Operative Queues")
        queue_box.pack(fill="both",expand=True,padx=4,pady=4)
        self.cockpit_queue_tree=ttk.Treeview(queue_box,columns=("queue","id","title","status"),show="headings",height=12)
        for c,h,w in [("queue","Queue",140),("id","ID",150),("title","Titel/Grund",420),("status","Status",120)]: self.cockpit_queue_tree.heading(c,text=h); self.cockpit_queue_tree.column(c,width=w)
        self.cockpit_queue_tree.pack(fill="both",expand=True,padx=4,pady=4)

    def _format_cockpit_text(self, dash):
        lines=[]
        lines.append("BLOCKER")
        blockers=dash.get("blockers") or []
        lines += [f"- {b}" for b in blockers] or ["- keine"]
        lines.append("\nWARNUNGEN")
        warnings=dash.get("warnings") or []
        lines += [f"- {w}" for w in warnings] or ["- keine"]
        lines.append("\nNÄCHSTE SINNVOLLE SCHRITTE")
        for a in dash.get("next_actions") or []:
            lines.append(f"[{a.get('priority')}] {a.get('area')}: {a.get('title')} → {a.get('target_tab')}")
            lines.append(f"    {a.get('detail')}")
        lines.append("\nPHASENSTATUS")
        for p in dash.get("phase_status") or []:
            lines.append(f"Phase {p.get('phase')}: {p.get('status_light')} | {p.get('completion_pct')}% | offen={p.get('open')} | blockiert={p.get('blocked')} | owner={', '.join(p.get('owners') or [])}")
        return "\n".join(lines)

    def refresh_cockpit(self):
        cid=self.selected_case_id.get()
        if not cid: return
        try:
            dash=self.ctx.cockpit.build_cockpit(cid)
            case=dash.get("case") or {}
            self.cockpit_case.set(f"Fall: {case.get('title','')} ({cid})")
            self.cockpit_score.set(f"Score: {dash.get('readiness_score')} %")
            self.cockpit_light.set(f"Ampel: {dash.get('traffic_light')}")
            if hasattr(self,"cockpit_kpi_tree"):
                self.cockpit_kpi_tree.delete(*self.cockpit_kpi_tree.get_children())
                for k,v in dash.get("kpis",{}).items(): self.cockpit_kpi_tree.insert("","end",values=(k,v))
            if hasattr(self,"cockpit_gate_tree"):
                self.cockpit_gate_tree.delete(*self.cockpit_gate_tree.get_children())
                for k,v in dash.get("gates",{}).items(): self.cockpit_gate_tree.insert("","end",values=(k,v))
            if hasattr(self,"cockpit_text"):
                self.cockpit_text.delete("1.0","end"); self.cockpit_text.insert("end", self._format_cockpit_text(dash))
            if hasattr(self,"cockpit_queue_tree"):
                self.cockpit_queue_tree.delete(*self.cockpit_queue_tree.get_children())
                queues=dash.get("queues",{})
                for qname, items in queues.items():
                    for item in items:
                        oid=item.get("item_id") or item.get("evidence_id") or item.get("flag_id") or item.get("blocker_id") or item.get("job_id") or ""
                        title=item.get("title") or item.get("reason") or item.get("action_required") or item.get("query") or ""
                        status=item.get("status") or item.get("review_decision") or ""
                        self.cockpit_queue_tree.insert("","end",values=(qname,oid,title,status))
            self.status.set(f"Cockpit aktualisiert: {dash.get('traffic_light')} / {dash.get('readiness_score')}%")
        except Exception as e:
            messagebox.showerror("Cockpit",str(e))

    def save_cockpit_snapshot(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Bitte zuerst Fall auswählen.")
        snap=self.ctx.cockpit.persist_snapshot(cid, notes="GUI Snapshot Build 37.0")
        self.status.set("Cockpit-Snapshot gespeichert: "+snap["snapshot_id"])
        self.refresh_all()

    def cockpit_run_readiness(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.reports.report_readiness(cid,"redacted_client")
        self.status.set("Report-Readiness: "+res.get("status",""))
        self.refresh_all()

    def cockpit_rebuild_analysis(self):
        cid=self.selected_case_id.get()
        if not cid: return
        graph=self.ctx.graph.rebuild_pro_graph(cid)
        timeline=self.ctx.timeline.build_from_evidence(cid)
        try:
            self.ctx.graph.build_analysis_narrative(cid)
            self.ctx.timeline.build_narrative(cid)
        except Exception:
            pass
        self.status.set(f"Graph/Timeline neu aufgebaut: nodes={graph.get('nodes_created')} edges={graph.get('edges_created')} events={timeline.get('created', timeline.get('events_created', 0))}")
        self.refresh_all()

    def _tab_cases(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="1 Fälle")
        form=ttk.LabelFrame(tab, text="Fall anlegen")
        form.pack(fill="x", padx=8, pady=8)
        self.case_title=tk.StringVar(value="Demo Due Diligence")
        self.case_client=tk.StringVar(value="Interner Testmandant")
        self.case_purpose=tk.StringVar(value="Rechtmäßige Prüfung öffentlich verfügbarer Reputations- und Identitätsanker")
        self.case_basis=tk.StringVar(value="Art. 6 Abs. 1 lit. f DSGVO / berechtigtes Interesse / Mandatsauftrag")
        self.case_retention=tk.StringVar(value="")
        rows=[("Titel",self.case_title),("Mandant",self.case_client),("Zweck",self.case_purpose),("Rechtsgrundlage",self.case_basis),("Lösch-/Reviewfrist",self.case_retention)]
        for i,(lbl,var) in enumerate(rows):
            ttk.Label(form,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=3)
            ttk.Entry(form,textvariable=var,width=110).grid(row=i,column=1,sticky="ew",padx=4,pady=3)
        form.columnconfigure(1, weight=1)
        ttk.Button(form,text="Fall anlegen",command=self.create_case).grid(row=len(rows),column=1,sticky="e",padx=4,pady=5)
        self.cases_tree=ttk.Treeview(tab, columns=("id","title","client","status","risk"), show="headings", height=18)
        for c,h,w in [("id","Fall-ID",170),("title","Titel",350),("client","Mandant",180),("status","Status",100),("risk","Risiko",100)]:
            self.cases_tree.heading(c,text=h); self.cases_tree.column(c,width=w)
        self.cases_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.cases_tree.bind("<<TreeviewSelect>>", self._select_case_from_tree)

    def create_case(self):
        try:
            case=self.ctx.cases.create_case(self.case_title.get(), self.case_client.get(), self.case_purpose.get(), self.case_basis.get(), retention_until=self.case_retention.get())
            self.ctx.workflow.initialize_case_workflow(case["case_id"])
            if self.case_retention.get():
                self.ctx.compliance.set_retention_policy(case["case_id"], self.case_retention.get(), "Retention aus Fallanlage")
            self.selected_case_id.set(case["case_id"])
            self.status.set("Fall angelegt: "+case["case_id"])
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def _select_case_from_tree(self, event=None):
        sel=self.cases_tree.selection()
        if sel:
            vals=self.cases_tree.item(sel[0], "values")
            self.selected_case_id.set(vals[0])
            self.refresh_all()

    def _tab_legal(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="2 Legal Gate")
        self._case_selector(tab)
        f=ttk.LabelFrame(tab,text="Legal-/Compliance-Prüfung")
        f.pack(fill="both",expand=True,padx=8,pady=8)
        self.legal_purpose=tk.StringVar(value="Rechtmäßige, zweckgebundene OSINT-Recherche aus öffentlichen Quellen")
        self.legal_basis=tk.StringVar(value="Art. 6 Abs. 1 lit. f DSGVO / Mandatsauftrag")
        self.legal_necessity=tk.StringVar(value="Recherche ist erforderlich, weil mildere interne Informationen nicht ausreichen und nur öffentliche Quellen verwendet werden.")
        self.legal_balancing=tk.StringVar(value="Interessenabwägung: zweckgebunden, datenminimiert, Review-Pflicht, keine privaten Quellen, Löschfrist.")
        self.legal_review_level=tk.StringVar(value="analyst")
        self.legal_approved=tk.BooleanVar(value=True)
        self.legal_special=tk.BooleanVar(value=False); self.legal_minor=tk.BooleanVar(value=False); self.legal_criminal=tk.BooleanVar(value=False)
        for i,(lbl,var) in enumerate([("Zweck",self.legal_purpose),("Rechtsgrundlage",self.legal_basis),("Erforderlichkeit",self.legal_necessity),("Interessenabwägung",self.legal_balancing),("Review-Level analyst/senior/legal/dpo",self.legal_review_level)]):
            ttk.Label(f,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=4)
            ttk.Entry(f,textvariable=var,width=120).grid(row=i,column=1,sticky="ew",padx=4,pady=4)
        ttk.Checkbutton(f,text="besondere Kategorien möglich",variable=self.legal_special).grid(row=5,column=1,sticky="w")
        ttk.Checkbutton(f,text="Minderjährige betroffen",variable=self.legal_minor).grid(row=6,column=1,sticky="w")
        ttk.Checkbutton(f,text="strafrechtliche Daten möglich",variable=self.legal_criminal).grid(row=7,column=1,sticky="w")
        ttk.Checkbutton(f,text="Fall freigeben",variable=self.legal_approved).grid(row=8,column=1,sticky="w")
        ttk.Button(f,text="Legal Gate speichern/evaluieren",command=self.save_legal).grid(row=9,column=1,sticky="e",pady=8)
        self.legal_text=tk.Text(f,height=14)
        self.legal_text.grid(row=10,column=0,columnspan=2,sticky="nsew",padx=4,pady=4)
        f.columnconfigure(1,weight=1); f.rowconfigure(10,weight=1)

    def save_legal(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Bitte zuerst Fall auswählen.")
        try:
            self.ctx.legal.create_review(cid,self.legal_purpose.get(),self.legal_basis.get(),self.legal_necessity.get(),self.legal_balancing.get(),special_categories=self.legal_special.get(),minor_data=self.legal_minor.get(),criminal_data=self.legal_criminal.get(),approved=self.legal_approved.get(),review_level=self.legal_review_level.get())
            ev=self.ctx.legal.evaluate_case(cid)
            self.legal_text.delete("1.0","end"); self.legal_text.insert("end", str(ev))
            self.status.set(ev["gate"])
            self.refresh_all()
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def _tab_target(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="3 Zielperson")
        self._case_selector(tab)
        f=ttk.LabelFrame(tab,text="Zielperson / Suchanker anlegen")
        f.pack(fill="x",padx=8,pady=8)
        vars=[]
        self.target_name=tk.StringVar(value="Maria Muster")
        self.target_aliases=tk.StringVar(value="m.muster, maria-m")
        self.target_emails=tk.StringVar(value="")
        self.target_users=tk.StringVar(value="mariamuster")
        self.target_locs=tk.StringVar(value="Köln")
        self.target_companies=tk.StringVar(value="Muster Consulting GmbH")
        self.target_domains=tk.StringVar(value="")
        self.target_notes=tk.StringVar(value="Nur öffentliche Quellen und Kandidatenprüfung.")
        rows=[("Name/Anker",self.target_name),("Aliasse",self.target_aliases),("E-Mails",self.target_emails),("Usernames",self.target_users),("Orte",self.target_locs),("Firmen",self.target_companies),("Domains",self.target_domains),("Notizen",self.target_notes)]
        for i,(lbl,var) in enumerate(rows):
            ttk.Label(f,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=3)
            ttk.Entry(f,textvariable=var,width=110).grid(row=i,column=1,sticky="ew",padx=4,pady=3)
        f.columnconfigure(1,weight=1)
        ttk.Button(f,text="Zielperson anlegen",command=self.create_target).grid(row=len(rows),column=1,sticky="e")
        self.target_tree=ttk.Treeview(tab,columns=("id","name","aliases","users","locs","companies"),show="headings",height=14)
        for c,h,w in [("id","ID",160),("name","Name",180),("aliases","Aliasse",220),("users","Usernames",160),("locs","Orte",160),("companies","Firmen",220)]: self.target_tree.heading(c,text=h); self.target_tree.column(c,width=w)
        self.target_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.target_tree.bind("<<TreeviewSelect>>", self._select_target_from_tree)

    def create_target(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Bitte zuerst Fall auswählen.")
        try:
            t=self.ctx.targets.create_target(cid,self.target_name.get(),self.target_aliases.get(),self.target_emails.get(),self.target_users.get(),self.target_locs.get(),self.target_companies.get(),self.target_domains.get(),self.target_notes.get())
            self.selected_target_id.set(t["target_id"]); self.status.set("Zielperson angelegt."); self.refresh_all()
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def _select_target_from_tree(self,event=None):
        sel=self.target_tree.selection()
        if sel:
            self.selected_target_id.set(self.target_tree.item(sel[0],"values")[0])
            self.status.set("Aktive Zielperson: "+self.selected_target_id.get())

    def _tab_workflow(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="4 Profi-Workflow")
        self._case_selector(tab)
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=6)
        ttk.Button(toolbar,text="Workflow initialisieren",command=self.init_workflow).pack(side="left")
        ttk.Button(toolbar,text="Ausgewählten Schritt erledigt",command=lambda:self.update_selected_workflow("done")).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Ausgewählten Schritt blockiert",command=lambda:self.update_selected_workflow("blocked")).pack(side="left",padx=6)
        self.workflow_tree=ttk.Treeview(tab,columns=("id","phase","status","gate","title","owner"),show="headings",height=24)
        for c,h,w in [("id","ID",140),("phase","Phase",160),("status","Status",100),("gate","Gate",160),("title","Schritt",520),("owner","Owner",120)]: self.workflow_tree.heading(c,text=h); self.workflow_tree.column(c,width=w)
        self.workflow_tree.pack(fill="both",expand=True,padx=8,pady=8)

    def init_workflow(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        n=self.ctx.workflow.initialize_case_workflow(cid)
        self.status.set(f"Workflow aktiv: {n} Schritte."); self.refresh_all()

    def update_selected_workflow(self,status):
        sel=self.workflow_tree.selection()
        if not sel: return
        step_id=self.workflow_tree.item(sel[0],"values")[0]
        self.ctx.workflow.update_step(step_id,status)
        self.refresh_all()


    def _tab_playbooks(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="5 Playbooks")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – Case Templates & Playbooks: sichere Profi-Workflows statt freier Feature-Sammlung")
        top.pack(fill="x",padx=8,pady=6)
        self.playbook_choice=tk.StringVar(value="due_diligence")
        ttk.Label(top,text="Playbook:").pack(side="left",padx=4)
        combo=ttk.Combobox(top,textvariable=self.playbook_choice,width=36,state="readonly")
        combo["values"]=[p["playbook_key"] for p in self.ctx.playbooks.list_playbooks()]
        combo.pack(side="left",padx=4)
        ttk.Button(top,text="Playbook auf Fall anwenden",command=self.apply_selected_playbook).pack(side="left",padx=4)
        ttk.Button(top,text="Empfehlungen prüfen",command=self.show_playbook_recommendations).pack(side="left",padx=4)
        ttk.Button(top,text="Ausgewählten Schritt erledigt",command=lambda:self.update_selected_playbook_step("done")).pack(side="left",padx=4)
        ttk.Button(top,text="Ausgewählten Schritt blockiert",command=lambda:self.update_selected_playbook_step("blocked")).pack(side="left",padx=4)
        panes=ttk.Panedwindow(tab,orient="vertical"); panes.pack(fill="both",expand=True,padx=8,pady=8)
        f1=ttk.LabelFrame(panes,text="Aktive Playbook-Schritte")
        f2=ttk.LabelFrame(panes,text="Source Plans / Deliverables / Quality Gates")
        f3=ttk.LabelFrame(panes,text="Playbook Dashboard")
        panes.add(f1,weight=3); panes.add(f2,weight=2); panes.add(f3,weight=2)
        self.playbook_step_tree=ttk.Treeview(f1,columns=("id","assignment","order","status","gate","title","objective"),show="headings",height=10)
        for c,h,w in [("id","Step-ID",140),("assignment","Assignment",140),("order","Nr.",50),("status","Status",95),("gate","Gate",160),("title","Schritt",330),("objective","Ziel",520)]:
            self.playbook_step_tree.heading(c,text=h); self.playbook_step_tree.column(c,width=w)
        self.playbook_step_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.playbook_gate_tree=ttk.Treeview(f2,columns=("kind","id","status","severity","title","note"),show="headings",height=9)
        for c,h,w in [("kind","Typ",110),("id","ID",140),("status","Status",100),("severity","Risiko",80),("title","Titel/Quelle",360),("note","Notiz",520)]:
            self.playbook_gate_tree.heading(c,text=h); self.playbook_gate_tree.column(c,width=w)
        self.playbook_gate_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.playbook_text=tk.Text(f3,height=9,wrap="word")
        self.playbook_text.pack(fill="both",expand=True,padx=4,pady=4)

    def apply_selected_playbook(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.playbooks.apply_playbook_to_case(cid,self.playbook_choice.get(),assigned_by="gui-user",notes="GUI-Anwendung Build 37.0")
            self.status.set(f"Playbook angewendet: {res.get('title')} mit {len(res.get('steps',[]))} Schritten")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Playbook",str(e))

    def show_playbook_recommendations(self):
        cid=self.selected_case_id.get()
        if not cid: return
        case=self.ctx.cases.get_case(cid)
        recs=self.ctx.playbooks.recommend_playbooks(case.get("purpose", ""), limit=5)
        msg="\n".join(f"{r['playbook_key']} | Score {r['recommendation_score']} | {r['title']}" for r in recs)
        if hasattr(self,"playbook_text"):
            self.playbook_text.delete("1.0","end"); self.playbook_text.insert("end","PLAYBOOK-EMPFEHLUNGEN\n"+msg)
        self.status.set("Playbook-Empfehlungen aktualisiert.")

    def update_selected_playbook_step(self,status):
        sel=getattr(self,"playbook_step_tree",None).selection() if hasattr(self,"playbook_step_tree") else []
        if not sel: return
        step_id=self.playbook_step_tree.item(sel[0],"values")[0]
        self.ctx.playbooks.update_step(step_id,status,notes=f"GUI Build 37.0: {status}")
        self.refresh_all()

    def _tab_guided_research(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="1 Guided Research")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 37.0 – Geführter Ermittlungs-/Intelligence-Workflow")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Workflow starten/aktualisieren", command=self.refresh_guided_research).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Suchpakete aus Zielperson vorbereiten", command=self.generate_search_packages).pack(side="left", padx=4, pady=4)
        ttk.Label(top, text="Suchanfrage:").pack(side="left", padx=(14,2))
        ttk.Entry(top, textvariable=self.guided_query, width=64).pack(side="left", padx=4, pady=4, fill="x", expand=True)
        ttk.Button(top, text="aus Zielperson", command=self.fill_guided_query_from_target).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Aktuelle Phase in mehreren Suchmaschinen öffnen", command=self.open_guided_phase_multi_search).pack(side="left", padx=4, pady=4)

        panes = ttk.Panedwindow(tab, orient="vertical"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        pf = ttk.LabelFrame(panes, text="Klare Reihenfolge: erst Legal/Scope, dann Suchanker, dann Suche, dann Capture/Review/Evidence/Report")
        df = ttk.LabelFrame(panes, text="Workflow-Status, nächste Aktion und Sicherheitsparameter")
        panes.add(pf, weight=2); panes.add(df, weight=1)
        self.guided_phase_tree = ttk.Treeview(pf, columns=("key","seq","status","title","bundle","preset","opened","captures","next"), show="headings", height=14)
        for c,h,w in [("key","Phase-Key",150),("seq","#",45),("status","Status",105),("title","Phase",280),("bundle","Suchbündel",140),("preset","Preset",140),("opened","Launches",70),("captures","Captures",70),("next","Nächster Schritt",520)]:
            self.guided_phase_tree.heading(c, text=h); self.guided_phase_tree.column(c, width=w)
        self.guided_phase_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.guided_phase_tree.bind("<<TreeviewSelect>>", self._select_guided_phase)
        self.guided_text = tk.Text(df, height=12, wrap="word")
        self.guided_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _select_guided_phase(self, event=None):
        sel = getattr(self, "guided_phase_tree", None).selection() if hasattr(self, "guided_phase_tree") else []
        if sel:
            vals = self.guided_phase_tree.item(sel[0], "values")
            if vals:
                self.selected_guided_phase.set(vals[0])

    def refresh_guided_research(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Guided Research", "Bitte zuerst einen Fall auswählen.")
        try:
            dash = self.ctx.guided_research.start_or_refresh_run(cid, target_id=self.selected_target_id.get())
            self._render_guided_dashboard(dash)
            self.status.set("Guided Research aktualisiert: klare Phasefolge geladen.")
        except Exception as e:
            messagebox.showerror("Guided Research", str(e))

    def _render_guided_dashboard(self, dash: dict):
        if hasattr(self, "guided_phase_tree"):
            self.guided_phase_tree.delete(*self.guided_phase_tree.get_children())
            for p in dash.get("phases", []):
                self.guided_phase_tree.insert("", "end", values=(p.get("phase_key"), p.get("sequence_no"), p.get("status"), p.get("title"), p.get("bundle_key"), p.get("preset_key"), p.get("opened_launches"), p.get("captures"), p.get("next_action")))
        if hasattr(self, "guided_text"):
            cur = dash.get("current_phase") or {}
            lines = [
                "GUIDED RESEARCH – ABLAUF OHNE HIN-UND-HER-KLICKEREI",
                f"Gate: {dash.get('gate')}",
                f"Readiness: {dash.get('readiness_score')} %",
                "",
                "AKTUELLE / NÄCHSTE PHASE",
                f"{cur.get('sequence_no','')} | {cur.get('title','')}",
                f"Status: {cur.get('status','')}",
                f"Aktion: {cur.get('next_action','')}",
                "",
                "SICHERHEITSPARAMETER",
                "- no_private_account_bypass",
                "- no_login_or_captcha_bypass",
                "- no_automatic_identity_claim",
                "- no_automatic_biometric_identification",
                "- no_private_address_certainty",
                "- image_upload_only_after_opsec_legal_review",
                "",
                "BLOCKER / HINWEISE",
            ]
            for b in dash.get("blockers", []) or ["Keine harten Blocker im Guided-Workflow-Status."]:
                lines.append(f"- {b}")
            self.guided_text.delete("1.0", "end"); self.guided_text.insert("end", "\n".join(lines))

    def fill_guided_query_from_target(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Guided Research", "Bitte zuerst einen Fall auswählen.")
        try:
            resolved = self.ctx.search_workbench.suggest_multi_search_query_from_target(cid, self.selected_target_id.get())
            self.guided_query.set(resolved["query"])
            if resolved.get("target_id"):
                self.selected_target_id.set(resolved["target_id"])
            self.multi_search_query.set(resolved["query"])
            self.status.set("Guided Query aus Zielperson erzeugt.")
        except Exception as e:
            messagebox.showwarning("Guided Research", str(e))

    def open_guided_phase_multi_search(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Guided Research", "Bitte zuerst einen Fall auswählen.")
        phase_key = self.selected_guided_phase.get() or "02_identity_web"
        try:
            prepared = self.ctx.guided_research.launch_phase_multi_search(
                cid, phase_key, target_id=self.selected_target_id.get(), explicit_query=self.guided_query.get().strip()
            )
            launch = prepared["launch"]
            self.multi_search_query.set(launch.get("query", ""))
            self._open_multi_search_launch(launch)
            sec = self.ctx.guided_research.run_security_checks(cid)
            self.status.set(f"Guided Phase geöffnet: {prepared['phase'].get('title')} | Security={sec.get('gate')}")
        except Exception as e:
            messagebox.showerror("Guided Research", str(e))


    def _tab_research_execution(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2 Research Center")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 37.0 – Research Execution Center: Phase → Query → Quellen → Trefferaufnahme → nächster Schritt")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Center aktualisieren", command=self.refresh_research_execution).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Query aus Zielperson", command=self.fill_research_execution_query_from_target).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Aktuelle Phase öffnen", command=self.open_research_execution_phase).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="URLs aus Zwischenablage capturen", command=self.capture_research_execution_clipboard).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Nächste Phase", command=self.advance_research_execution_phase).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Security Check", command=self.run_research_execution_security).pack(side="left", padx=4, pady=4)

        qf = ttk.LabelFrame(tab, text="Aktuelle Rechercheausführung")
        qf.pack(fill="x", padx=8, pady=4)
        ttk.Label(qf, text="Phase:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.research_exec_phase_combo = ttk.Combobox(qf, textvariable=self.research_exec_phase, width=34, state="readonly", values=[
            "02_identity_web", "03_profiles_context", "04_image_media", "05_geo_places", "06_docs_business_archives", "07_counter_evidence"
        ])
        self.research_exec_phase_combo.grid(row=0, column=1, sticky="w", padx=4, pady=3)
        self.research_exec_phase_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_research_execution())
        ttk.Label(qf, text="Suchanfrage:").grid(row=0, column=2, sticky="w", padx=4, pady=3)
        ttk.Entry(qf, textvariable=self.research_exec_query, width=92).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
        qf.columnconfigure(3, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=2)

        phase_box = ttk.LabelFrame(left, text="Phasen, Quellenpakete und Intelligence-Gaps")
        phase_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.research_exec_phase_tree = ttk.Treeview(phase_box, columns=("key","seq","status","sources","launches","captures","next"), show="headings", height=13)
        for c,h,w in [("key","Phase",150),("seq","#",40),("status","Status",90),("sources","Quellen",65),("launches","Launches",70),("captures","Captures",70),("next","Nächster Schritt",480)]:
            self.research_exec_phase_tree.heading(c, text=h); self.research_exec_phase_tree.column(c, width=w)
        self.research_exec_phase_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.research_exec_phase_tree.bind("<<TreeviewSelect>>", self._select_research_execution_phase)

        source_box = ttk.LabelFrame(left, text="Quellenmatrix der aktiven Phase")
        source_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.research_exec_source_tree = ttk.Treeview(source_box, columns=("engine","purpose"), show="headings", height=8)
        for c,h,w in [("engine","Suchmaschine/Quelle",210),("purpose","Nutzung",520)]:
            self.research_exec_source_tree.heading(c, text=h); self.research_exec_source_tree.column(c, width=w)
        self.research_exec_source_tree.pack(fill="both", expand=True, padx=4, pady=4)

        cap_box = ttk.LabelFrame(right, text="Trefferaufnahme direkt aus dem Browser")
        cap_box.pack(fill="x", padx=4, pady=4)
        ttk.Label(cap_box, text="Titel-Präfix:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(cap_box, textvariable=self.research_exec_capture_title, width=45).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Label(cap_box, text="URL(s), eine pro Zeile oder aus Zwischenablage:").grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        self.research_exec_urls_text = tk.Text(cap_box, height=7, wrap="word")
        self.research_exec_urls_text.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=3)
        ttk.Label(cap_box, text="Snippet/Notiz:").grid(row=3, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(cap_box, textvariable=self.research_exec_capture_snippet, width=56).grid(row=3, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(cap_box, text="URL(s) capturen → Review Inbox", command=self.capture_research_execution_urls).grid(row=4, column=1, sticky="e", padx=4, pady=4)
        cap_box.columnconfigure(1, weight=1)

        info_box = ttk.LabelFrame(right, text="Ablauf, Guardrails und nächster Schritt")
        info_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.research_exec_text = tk.Text(info_box, height=18, wrap="word")
        self.research_exec_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _select_research_execution_phase(self, event=None):
        sel = getattr(self, "research_exec_phase_tree", None).selection() if hasattr(self, "research_exec_phase_tree") else []
        if sel:
            vals = self.research_exec_phase_tree.item(sel[0], "values")
            if vals:
                self.research_exec_phase.set(vals[0])
                self.refresh_research_execution()

    def refresh_research_execution(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            dash = self.ctx.research_execution.dashboard(cid, target_id=self.selected_target_id.get(), query=self.research_exec_query.get().strip())
            session = dash.get("session") or {}
            if session.get("query") and not self.research_exec_query.get().strip():
                self.research_exec_query.set(session.get("query"))
            if session.get("active_phase_key"):
                self.research_exec_phase.set(session.get("active_phase_key"))
            if hasattr(self, "research_exec_phase_tree"):
                self.research_exec_phase_tree.delete(*self.research_exec_phase_tree.get_children())
                for p in dash.get("execution_phases", []):
                    self.research_exec_phase_tree.insert("", "end", values=(p.get("phase_key"), p.get("sequence_no"), p.get("status"), p.get("source_count"), p.get("launches"), p.get("captures"), p.get("next_action")))
            if hasattr(self, "research_exec_source_tree"):
                self.research_exec_source_tree.delete(*self.research_exec_source_tree.get_children())
                active = dash.get("active_phase") or {}
                for src in active.get("sources", []):
                    self.research_exec_source_tree.insert("", "end", values=(src, active.get("capture_hint", "öffentliche Quelle prüfen")))
            if hasattr(self, "research_exec_text"):
                active = dash.get("active_phase") or {}
                lines = [
                    "RESEARCH EXECUTION CENTER",
                    f"Session: {session.get('session_id','')}",
                    f"Readiness: {dash.get('readiness_score')} %",
                    "",
                    "AKTIVE PHASE",
                    f"{active.get('sequence_no','')} | {active.get('title','')}",
                    f"Preset: {active.get('preset_key','')}",
                    f"Nächster Schritt: {active.get('next_action','')}",
                    f"Capture-Hinweis: {active.get('capture_hint','')}",
                    "",
                    "INTELLIGENCE-GAPS",
                ]
                gaps = dash.get("intelligence_gaps") or []
                lines += [f"- {g}" for g in gaps[:8]] or ["- keine offenen Gaps"]
                lines += ["", "GUARDRAILS"] + [f"- {g}" for g in dash.get("guardrails", [])]
                self.research_exec_text.delete("1.0", "end"); self.research_exec_text.insert("end", "\n".join(lines))
            self.status.set(f"Research Center aktualisiert: {dash.get('readiness_score')}% / Phase {self.research_exec_phase.get()}")
        except Exception as e:
            messagebox.showerror("Research Execution Center", str(e))

    def fill_research_execution_query_from_target(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Research Center", "Bitte zuerst einen Fall auswählen.")
        try:
            resolved = self.ctx.search_workbench.suggest_multi_search_query_from_target(cid, self.selected_target_id.get())
            self.research_exec_query.set(resolved["query"])
            self.guided_query.set(resolved["query"])
            self.multi_search_query.set(resolved["query"])
            if resolved.get("target_id"):
                self.selected_target_id.set(resolved["target_id"])
            self.refresh_research_execution()
        except Exception as e:
            messagebox.showwarning("Research Center", str(e))

    def open_research_execution_phase(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Research Center", "Bitte zuerst einen Fall auswählen.")
        try:
            prepared = self.ctx.research_execution.prepare_phase_launch(
                cid, self.research_exec_phase.get(), target_id=self.selected_target_id.get(), query=self.research_exec_query.get().strip()
            )
            launch = prepared["launch"]
            self.research_exec_query.set(launch.get("query", ""))
            self.guided_query.set(launch.get("query", ""))
            self.multi_search_query.set(launch.get("query", ""))
            self._open_multi_search_launch(launch)
            self.ctx.research_execution.mark_phase_opened(cid, prepared["phase_run_id"], launch["launch_id"])
            self.refresh_all()
            self.status.set(f"Research Phase geöffnet: {prepared['matrix'].get('title')} | {launch.get('url_count')} Quellen")
        except Exception as e:
            messagebox.showerror("Research Center", str(e))

    def _research_execution_urls_value(self) -> str:
        if hasattr(self, "research_exec_urls_text"):
            return self.research_exec_urls_text.get("1.0", "end").strip()
        return ""

    def capture_research_execution_urls(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Research Center", "Bitte zuerst einen Fall auswählen.")
        urls_text = self._research_execution_urls_value()
        try:
            res = self.ctx.research_execution.import_urls_to_capture(
                cid, urls_text, self.research_exec_phase.get(), target_id=self.selected_target_id.get(),
                title_prefix=self.research_exec_capture_title.get().strip() or "Öffentlicher Treffer",
                snippet=self.research_exec_capture_snippet.get().strip(),
                notes="Build 37.0 Research Execution Center: Browserfund manuell geprüft und an Review gesendet."
            )
            self.status.set(f"Research Capture erstellt: {res.get('created')} URL(s) → Review Inbox")
            if hasattr(self, "research_exec_urls_text"):
                self.research_exec_urls_text.delete("1.0", "end")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Research Capture", str(e))

    def capture_research_execution_clipboard(self):
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        if hasattr(self, "research_exec_urls_text"):
            self.research_exec_urls_text.delete("1.0", "end")
            self.research_exec_urls_text.insert("end", text)
        self.capture_research_execution_urls()

    def advance_research_execution_phase(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            dash = self.ctx.research_execution.advance_phase(cid, target_id=self.selected_target_id.get(), query=self.research_exec_query.get().strip())
            active = dash.get("active_phase") or {}
            self.research_exec_phase.set(active.get("phase_key", self.research_exec_phase.get()))
            self.refresh_research_execution()
        except Exception as e:
            messagebox.showerror("Research Center", str(e))

    def run_research_execution_security(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        try:
            sec = self.ctx.research_execution.run_security_checks(cid)
            msg = sec.get("gate", "") + "\n" + "\n".join(f"{c['check_key']}: {c['status']}" for c in sec.get("checks", []))
            messagebox.showinfo("Research Security", msg)
            self.status.set("Research Security Check: " + sec.get("gate", ""))
        except Exception as e:
            messagebox.showerror("Research Security", str(e))




    def _tab_real_providers(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2c Real Providers")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 44.0 – Query Intelligence Pro: API-/Public-Provider → Provider Result → Review Inbox")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Connectoren laden", command=self.seed_real_providers).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Health Check", command=self.real_provider_health_check).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Run vorbereiten / Dry-Run", command=lambda: self.run_real_provider(False)).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Live ausführen (falls Key/öffentlich)", command=lambda: self.run_real_provider(True)).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Ergebnisse in Review", command=self.real_provider_results_to_review).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Dashboard aktualisieren", command=self.refresh_real_providers).pack(side="left", padx=4, pady=4)

        form = ttk.LabelFrame(tab, text="Provider-Abfrage – nur öffentliche/lizenzierte Quellen, Review-first")
        form.pack(fill="x", padx=8, pady=4)
        ttk.Label(form, text="Connector:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.real_provider_combo = ttk.Combobox(form, textvariable=self.real_provider_selected_connector, width=42, state="readonly")
        self.real_provider_combo.grid(row=0, column=1, sticky="we", padx=4, pady=3)
        ttk.Label(form, text="Query/Domain:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.real_provider_query, width=80).grid(row=1, column=1, sticky="we", padx=4, pady=3)
        ttk.Button(form, text="Query aus Research Center", command=self.real_provider_query_from_research).grid(row=1, column=2, sticky="w", padx=4, pady=3)
        ttk.Label(form, text="Zweck:").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.real_provider_purpose, width=80).grid(row=2, column=1, sticky="we", padx=4, pady=3)
        ttk.Checkbutton(form, text="Live erlauben (nur mit Key/öffentlicher API; sonst Dry-Run)", variable=self.real_provider_live).grid(row=2, column=2, sticky="w", padx=4, pady=3)
        form.columnconfigure(1, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=2); panes.add(right, weight=3)

        conn_box = ttk.LabelFrame(left, text="Connectoren / Konfiguration")
        conn_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.real_provider_tree = ttk.Treeview(conn_box, columns=("key","title","family","mode","api","configured","guardrails"), show="headings", height=14)
        for c,h,w in [("key","Key",145),("title","Titel",220),("family","Familie",135),("mode","Modus",90),("api","API",45),("configured","Konfig",60),("guardrails","Guardrails",360)]:
            self.real_provider_tree.heading(c, text=h); self.real_provider_tree.column(c, width=w)
        self.real_provider_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.real_provider_tree.bind("<<TreeviewSelect>>", self._select_real_provider_connector)

        run_box = ttk.LabelFrame(right, text="Runs")
        run_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.real_provider_run_tree = ttk.Treeview(run_box, columns=("id","connector","status","query","results","issues","live"), show="headings", height=9)
        for c,h,w in [("id","Run-ID",130),("connector","Connector",135),("status","Status",120),("query","Query",330),("results","Results",70),("issues","Issues",70),("live","Live",45)]:
            self.real_provider_run_tree.heading(c, text=h); self.real_provider_run_tree.column(c, width=w)
        self.real_provider_run_tree.pack(fill="both", expand=True, padx=4, pady=4)

        item_box = ttk.LabelFrame(right, text="Normalisierte Provider Items")
        item_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.real_provider_item_tree = ttk.Treeview(item_box, columns=("id","connector","title","url","hash","review"), show="headings", height=10)
        for c,h,w in [("id","Item-ID",130),("connector","Connector",135),("title","Titel",250),("url","URL",360),("hash","Hash",130),("review","Review",130)]:
            self.real_provider_item_tree.heading(c, text=h); self.real_provider_item_tree.column(c, width=w)
        self.real_provider_item_tree.pack(fill="both", expand=True, padx=4, pady=4)

        info_box = ttk.LabelFrame(tab, text="Provider-Regeln / Hinweise")
        info_box.pack(fill="x", padx=8, pady=4)
        self.real_provider_text = tk.Text(info_box, height=7, wrap="word")
        self.real_provider_text.pack(fill="x", expand=False, padx=4, pady=4)

    def _select_real_provider_connector(self, event=None):
        sel = getattr(self, "real_provider_tree", None).selection() if hasattr(self, "real_provider_tree") else []
        if sel:
            vals = self.real_provider_tree.item(sel[0], "values")
            if vals:
                self.real_provider_selected_connector.set(vals[0])

    def real_provider_query_from_research(self):
        q = (self.research_exec_query.get() or self.multi_search_query.get() or self.guided_query.get() or "").strip()
        if not q:
            return messagebox.showinfo("Real Provider", "Keine Query im Research Center/Multi-Search gefunden.")
        self.real_provider_query.set(q)
        self.status.set("Provider-Query übernommen: " + q)

    def seed_real_providers(self):
        try:
            res = self.ctx.real_providers.seed_defaults()
            self.status.set(f"Real Provider Connectoren geladen: {res.get('connectors')} Connectoren.")
            self.refresh_real_providers()
        except Exception as e: messagebox.showerror("Real Provider", str(e))

    def real_provider_health_check(self):
        try:
            res = self.ctx.real_providers.health_check(execute_live=False)
            self.status.set(f"Real Provider Health: {res.get('connectors_checked')} Connectoren geprüft.")
            self.refresh_real_providers()
        except Exception as e: messagebox.showerror("Real Provider Health", str(e))

    def run_real_provider(self, execute_live=False):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Real Provider", "Bitte zuerst einen Fall auswählen.")
        q = (self.real_provider_query.get() or self.research_exec_query.get() or self.multi_search_query.get() or "").strip()
        if not q: return messagebox.showwarning("Real Provider", "Bitte Query/Domain eingeben oder aus dem Research Center übernehmen.")
        try:
            legal = self.ctx.legal.evaluate_case(cid)
            if not legal.get("ok"):
                return messagebox.showwarning("Legal Gate", "Provider-Run gesperrt bis Legal Gate PASS:\n"+"\n".join(legal.get("issues",[])))
            live = bool(execute_live and self.real_provider_live.get())
            res = self.ctx.real_providers.run_connector(cid, self.real_provider_selected_connector.get(), q, self.real_provider_purpose.get(), target_id=self.selected_target_id.get(), execute_live=live, notes="GUI Build 44.0 Real Provider")
            self.status.set(f"Real Provider Run: {res.get('status')} | Items={len(res.get('stored_items',[]))} | Issues={len(res.get('issues',[]))}")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Real Provider Run", str(e))

    def real_provider_results_to_review(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Real Provider", "Bitte zuerst einen Fall auswählen.")
        try:
            res = self.ctx.real_providers.results_to_review(cid)
            self.status.set(f"Real Provider → Review: {res.get('created_review_items',0)} neue Review Items; Items verknüpft={res.get('linked_real_provider_items',0)}")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Real Provider Review", str(e))

    def refresh_real_providers(self):
        try:
            cid = self.selected_case_id.get()
            dash = self.ctx.real_providers.dashboard(cid)
            if hasattr(self, "real_provider_combo"):
                vals = [c.get("connector_key") for c in dash.get("connectors", [])]
                self.real_provider_combo["values"] = vals
                if vals and self.real_provider_selected_connector.get() not in vals:
                    self.real_provider_selected_connector.set(vals[0])
            if hasattr(self, "real_provider_tree"):
                self.real_provider_tree.delete(*self.real_provider_tree.get_children())
                for c in dash.get("connectors", []):
                    self.real_provider_tree.insert("", "end", values=(c.get("connector_key"), c.get("title"), c.get("family"), c.get("mode"), "yes" if c.get("requires_api_key") else "no", "yes" if c.get("configured") else "no", ", ".join(c.get("guardrails") or [])))
            if hasattr(self, "real_provider_run_tree"):
                self.real_provider_run_tree.delete(*self.real_provider_run_tree.get_children())
                for r in dash.get("runs", []):
                    issues = len(__import__('json').loads(r.get("issues_json") or "[]")) if r.get("issues_json") else 0
                    self.real_provider_run_tree.insert("", "end", values=(r.get("run_id"), r.get("connector_key"), r.get("status"), r.get("query"), r.get("result_count"), issues, "yes" if r.get("execute_live") else "no"))
            if hasattr(self, "real_provider_item_tree"):
                self.real_provider_item_tree.delete(*self.real_provider_item_tree.get_children())
                for it in dash.get("items", []):
                    self.real_provider_item_tree.insert("", "end", values=(it.get("item_id"), it.get("connector_key"), it.get("title"), it.get("source_url"), (it.get("raw_hash") or "")[:16], it.get("review_item_id")))
            if hasattr(self, "real_provider_text"):
                lines = ["REAL PROVIDER CONNECTORS", f"Gate: {dash.get('gate')}", f"API-Connectoren konfiguriert: {dash.get('configured_api_connectors')}/{dash.get('api_required_connectors')}", "", "KETTE", dash.get("review_first_chain", "Connector → Review"), "", "LIVE-NUTZUNG", "Live wird nur ausgeführt, wenn explizit aktiviert und nötige Env-Var-Keys gesetzt sind. Tests und Standardpfade bleiben offline-sicher.", "", "GUARDRAILS", "- keine privaten Accounts", "- keine Login-/Captcha-Umgehung", "- keine automatische Identitätsbestätigung", "- Provider Results bleiben Review-Kandidaten"]
                self.real_provider_text.delete("1.0", "end"); self.real_provider_text.insert("end", "\n".join(lines))
        except Exception as e:
            # keep refresh_all robust; show only in status, not modal loop
            self.status.set("Real Provider Refresh Hinweis: " + str(e)[:180])

    def _tab_source_packs(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2a Source Packs")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 44.0 – OSINT Source Packs Pro: Ermittlungsfrage → Quellenpaket → Query → Research Center")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Dashboard aktualisieren", command=self.refresh_source_packs).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Pack-Queries erzeugen", command=self.generate_selected_source_pack).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Alle Source Packs erzeugen", command=self.generate_all_source_packs).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Query an Research Center", command=self.send_source_pack_query_to_research_center).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Query in Multi-Search öffnen", command=self.open_source_pack_query_multi_search).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Security Check", command=self.run_source_pack_security).pack(side="left", padx=4, pady=4)

        selector = ttk.LabelFrame(tab, text="Quellenpaket auswählen")
        selector.pack(fill="x", padx=8, pady=4)
        ttk.Label(selector, text="Source Pack:").pack(side="left", padx=4)
        self.source_pack_combo = ttk.Combobox(selector, textvariable=self.source_pack_selected_pack, width=42, state="readonly")
        self.source_pack_combo.pack(side="left", padx=4, pady=4)
        self.source_pack_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_source_packs())

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=2); panes.add(right, weight=3)

        pack_box = ttk.LabelFrame(left, text="Source Packs / Quellenabdeckung")
        pack_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.source_pack_tree = ttk.Treeview(pack_box, columns=("key","title","phase","status","queries","captures","evidence","gap"), show="headings", height=13)
        for c,h,w in [("key","Pack",150),("title","Titel",210),("phase","Phase",150),("status","Status",130),("queries","Queries",70),("captures","Captures",70),("evidence","Evidence",70),("gap","Gap",70)]:
            self.source_pack_tree.heading(c, text=h); self.source_pack_tree.column(c, width=w)
        self.source_pack_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.source_pack_tree.bind("<<TreeviewSelect>>", self._select_source_pack)

        query_box = ttk.LabelFrame(right, text="Erzeugte Source-Pack-Queries")
        query_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.source_pack_query_tree = ttk.Treeview(query_box, columns=("id","pack","prio","policy","label","query","preset"), show="headings", height=15)
        for c,h,w in [("id","ID",110),("pack","Pack",130),("prio","Prio",45),("policy","Policy",75),("label","Label",150),("query","Query",520),("preset","Preset",110)]:
            self.source_pack_query_tree.heading(c, text=h); self.source_pack_query_tree.column(c, width=w)
        self.source_pack_query_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.source_pack_query_tree.bind("<<TreeviewSelect>>", self._select_source_pack_query)

        info_box = ttk.LabelFrame(right, text="Zweck, Guardrails und nächster Schritt")
        info_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.source_pack_text = tk.Text(info_box, height=15, wrap="word")
        self.source_pack_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _source_pack_key(self) -> str:
        value = (self.source_pack_selected_pack.get() or "person_identity").strip()
        return value.split(" | ", 1)[0].strip() if " | " in value else value

    def _select_source_pack(self, event=None):
        sel = getattr(self, "source_pack_tree", None).selection() if hasattr(self, "source_pack_tree") else []
        if sel:
            vals = self.source_pack_tree.item(sel[0], "values")
            if vals:
                self.source_pack_selected_pack.set(vals[0]); self.refresh_source_packs()

    def _select_source_pack_query(self, event=None):
        sel = getattr(self, "source_pack_query_tree", None).selection() if hasattr(self, "source_pack_query_tree") else []
        if sel:
            vals = self.source_pack_query_tree.item(sel[0], "values")
            if vals:
                self.source_pack_selected_query_id.set(vals[0])

    def refresh_source_packs(self):
        cid = self.selected_case_id.get()
        if not cid: return
        try:
            dash = self.ctx.source_packs.dashboard(cid)
            if hasattr(self, "source_pack_combo"):
                self.source_pack_combo["values"] = [f"{p['pack_key']} | {p['title']}" for p in dash.get("packs", [])]
            if hasattr(self, "source_pack_tree"):
                self.source_pack_tree.delete(*self.source_pack_tree.get_children())
                cov_lookup = {c.get("pack_key"): c for c in dash.get("coverage", [])}
                for p in dash.get("packs", []):
                    cov = cov_lookup.get(p.get("pack_key"), {})
                    self.source_pack_tree.insert("", "end", values=(p.get("pack_key"), p.get("title"), p.get("workflow_phase"), cov.get("status", "open"), cov.get("query_count", 0), cov.get("captures", 0), cov.get("evidence_items", 0), cov.get("gap_level", "red")))
            if hasattr(self, "source_pack_query_tree"):
                self.source_pack_query_tree.delete(*self.source_pack_query_tree.get_children())
                pack_key = self._source_pack_key()
                for q in dash.get("queries", []):
                    if pack_key and q.get("pack_key") != pack_key: continue
                    self.source_pack_query_tree.insert("", "end", values=(q.get("run_query_id"), q.get("pack_key"), q.get("priority"), q.get("policy_status"), q.get("label"), q.get("query_text"), q.get("preset_key")))
            if hasattr(self, "source_pack_text"):
                pack_key = self._source_pack_key()
                pack = next((p for p in dash.get("packs", []) if p.get("pack_key") == pack_key), None)
                lines = ["OSINT SOURCE PACKS PRO", f"Status: {dash.get('status')}", f"Nächster Schritt: {dash.get('next_action')}", f"Open Gaps: {dash.get('open_gap_count')}", ""]
                if pack:
                    lines += ["AUSGEWÄHLTES PACK", f"{pack.get('title')} ({pack.get('pack_key')})", f"Phase: {pack.get('workflow_phase')}", f"Frage: {pack.get('primary_question')}", f"Preset: {pack.get('default_preset')}", "Engines: " + ", ".join(pack.get('engines') or []), "Guardrails:"]
                    lines += [f"- {g}" for g in pack.get("guardrails", [])]
                lines += ["", "SECURITY CHECKS"]
                for c in dash.get("security_checks", [])[:3]:
                    lines.append(f"- {c.get('status')} | {c.get('severity')} | {c.get('details',{})}")
                lines += ["", "GRUNDREGEL", "Provider/Source-Pack-Resultate bleiben Hinweise: Capture → Review → Evidence → Report."]
                self.source_pack_text.delete("1.0", "end"); self.source_pack_text.insert("end", "\n".join(lines))
            self.status.set("Source Packs aktualisiert.")
        except Exception as e:
            messagebox.showerror("Source Packs", str(e))

    def generate_selected_source_pack(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Source Packs", "Bitte zuerst einen Fall auswählen.")
        try:
            legal = self.ctx.legal.evaluate_case(cid)
            if not legal.get("ok"):
                return messagebox.showwarning("Legal Gate", "Recherche gesperrt bis Legal Gate PASS:\n" + "\n".join(legal.get("issues", [])))
            dash = self.ctx.source_packs.generate_pack_queries(cid, self._source_pack_key(), target_id=self.selected_target_id.get(), notes="GUI Build 44.0 Source Pack")
            self.status.set(f"Source Pack erzeugt: {dash.get('allowed_count',0)} erlaubte / {dash.get('blocked_count',0)} blockierte Queries.")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Source Packs", str(e))

    def generate_all_source_packs(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Source Packs", "Bitte zuerst einen Fall auswählen.")
        try:
            legal = self.ctx.legal.evaluate_case(cid)
            if not legal.get("ok"):
                return messagebox.showwarning("Legal Gate", "Recherche gesperrt bis Legal Gate PASS:\n" + "\n".join(legal.get("issues", [])))
            dash = self.ctx.source_packs.generate_all_packs(cid, target_id=self.selected_target_id.get())
            self.status.set(f"Alle Source Packs erzeugt: Runs={dash.get('generated_runs',0)} | Gaps offen={dash.get('open_gap_count',0)}")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Source Packs", str(e))

    def send_source_pack_query_to_research_center(self):
        cid = self.selected_case_id.get(); qid = self.source_pack_selected_query_id.get()
        if not cid or not qid: return messagebox.showwarning("Source Packs", "Bitte eine Source-Pack-Query markieren.")
        try:
            res = self.ctx.source_packs.send_query_to_research_center(cid, qid)
            self.research_exec_query.set(res.get("query", "")); self.research_exec_phase.set(res.get("phase_key", "02_identity_web")); self.multi_search_query.set(res.get("query", ""))
            self.status.set("Source-Pack-Query an Research Center übergeben: " + res.get("query", "")); self.refresh_all()
        except Exception as e: messagebox.showerror("Source Packs", str(e))

    def open_source_pack_query_multi_search(self):
        cid = self.selected_case_id.get(); qid = self.source_pack_selected_query_id.get()
        if not cid or not qid: return messagebox.showwarning("Source Packs", "Bitte eine Source-Pack-Query markieren.")
        try:
            launch = self.ctx.source_packs.run_multi_search_for_query(cid, qid)
            self._open_multi_search_launch(launch)
            self.status.set(f"Source-Pack-Multi-Search geöffnet: {launch.get('url_count')} URLs")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Source Packs", str(e))

    def run_source_pack_security(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Source Packs", "Bitte Fall auswählen.")
        try:
            res = self.ctx.source_packs.run_security_checks(cid)
            self.status.set("Source Pack Security: " + res.get("status", "")); self.refresh_source_packs()
        except Exception as e: messagebox.showerror("Source Packs", str(e))

    def _tab_query_factory(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2b Query Factory")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 37.0 – Query Factory & Search Matrix: Zielperson → Query-Sets → Research Center")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Query Matrix aus Zielperson erzeugen", command=self.generate_query_factory_matrix).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Dashboard aktualisieren", command=self.refresh_query_factory).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Markierte Query ins Research Center", command=self.send_query_factory_to_research_center).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Security Check", command=self.run_query_factory_security).pack(side="left", padx=4, pady=4)
        split = ttk.Panedwindow(tab, orient="horizontal"); split.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(split); right = ttk.Frame(split)
        split.add(left, weight=3); split.add(right, weight=2)
        matrix_box = ttk.LabelFrame(left, text="Search Matrix je Ermittlungsphase"); matrix_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_factory_matrix_tree = ttk.Treeview(matrix_box, columns=("phase","queries","allowed","blocked","preset","engines","next"), show="headings", height=8)
        for c,h,w in [("phase","Phase",190),("queries","Queries",70),("allowed","erlaubt",70),("blocked","blockiert",70),("preset","Preset",120),("engines","Engines",70),("next","Nächster Schritt",430)]:
            self.query_factory_matrix_tree.heading(c, text=h); self.query_factory_matrix_tree.column(c, width=w)
        self.query_factory_matrix_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_factory_matrix_tree.bind("<<TreeviewSelect>>", self._select_query_factory_phase)
        query_box = ttk.LabelFrame(left, text="Priorisierte Queries"); query_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_factory_tree = ttk.Treeview(query_box, columns=("id","phase","prio","status","cat","query","preset"), show="headings", height=14)
        for c,h,w in [("id","Query-ID",135),("phase","Phase",145),("prio","Prio",55),("status","Policy",75),("cat","Kategorie",170),("query","Query",500),("preset","Preset",120)]:
            self.query_factory_tree.heading(c, text=h); self.query_factory_tree.column(c, width=w)
        self.query_factory_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_factory_tree.bind("<<TreeviewSelect>>", self._select_query_factory_query)
        info_box = ttk.LabelFrame(right, text="Effizienzlogik, Guardrails und Top-Queries"); info_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_factory_text = tk.Text(info_box, height=34, wrap="word"); self.query_factory_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _select_query_factory_phase(self, event=None):
        sel = getattr(self, "query_factory_matrix_tree", None).selection() if hasattr(self, "query_factory_matrix_tree") else []
        if sel:
            vals = self.query_factory_matrix_tree.item(sel[0], "values")
            if vals:
                self.query_factory_phase.set(vals[0]); self.refresh_query_factory()

    def _select_query_factory_query(self, event=None):
        sel = getattr(self, "query_factory_tree", None).selection() if hasattr(self, "query_factory_tree") else []
        if sel:
            vals = self.query_factory_tree.item(sel[0], "values")
            if vals: self.query_factory_selected_query_id.set(vals[0])

    def generate_query_factory_matrix(self):
        cid = self.selected_case_id.get(); tid = self.selected_target_id.get()
        if not cid: return messagebox.showwarning("Query Factory", "Bitte zuerst einen Fall auswählen.")
        try:
            targets = self.ctx.targets.list_targets(cid)
            if not targets: return messagebox.showwarning("Query Factory", "Bitte zuerst eine Zielperson anlegen.")
            if not tid: tid = targets[0]["target_id"]; self.selected_target_id.set(tid)
            legal = self.ctx.legal.evaluate_case(cid)
            if not legal.get("ok"):
                return messagebox.showwarning("Legal Gate", "Recherche gesperrt bis Legal Gate PASS:\n" + "\n".join(legal.get("issues", [])))
            dash = self.ctx.query_factory.generate_for_case(cid, tid, notes="GUI Build 37.0 Query Factory")
            self.status.set(f"Query Factory erzeugt: {dash.get('allowed_count',0)} erlaubte / {dash.get('blocked_count',0)} blockierte Queries.")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Query Factory", str(e))

    def refresh_query_factory(self):
        cid = self.selected_case_id.get()
        if not cid: return
        try:
            dash = self.ctx.query_factory.dashboard(cid, target_id=self.selected_target_id.get())
            selected_phase = self.query_factory_phase.get().strip()
            if hasattr(self, "query_factory_matrix_tree"):
                self.query_factory_matrix_tree.delete(*self.query_factory_matrix_tree.get_children())
                for m in dash.get("matrix", []): self.query_factory_matrix_tree.insert("", "end", values=(m.get("phase_key"), m.get("query_count"), m.get("allowed_count"), m.get("blocked_count"), m.get("preset_key"), m.get("engine_count"), m.get("next_action")))
            if hasattr(self, "query_factory_tree"):
                self.query_factory_tree.delete(*self.query_factory_tree.get_children())
                for q in dash.get("queries", []):
                    if selected_phase and q.get("phase_key") != selected_phase: continue
                    self.query_factory_tree.insert("", "end", values=(q.get("query_id"), q.get("phase_key"), q.get("priority"), q.get("policy_status"), q.get("category"), q.get("query_text"), q.get("preset_key")))
            if hasattr(self, "query_factory_text"):
                lines = ["QUERY FACTORY & SEARCH MATRIX PRO", f"Status: {dash.get('status')}", f"Nächster Schritt: {dash.get('next_action')}", f"Queries: {dash.get('query_count',0)} | erlaubt: {dash.get('allowed_count',0)} | blockiert: {dash.get('blocked_count',0)}", "", "TOP-QUERIES"]
                for q in dash.get("top_queries", [])[:12]: lines.append(f"- [{q.get('phase_key')}] prio={q.get('priority')} | {q.get('category')} | {q.get('query_text')}")
                lines += ["", "GUARDRAILS"] + [f"- {g}" for g in dash.get("guardrails", [])]
                checks = dash.get("security_checks", [])
                if checks: lines += ["", "LETZTE SECURITY CHECKS"] + [f"- {c.get('status')} | {c.get('severity')} | {c.get('details',{})}" for c in checks[:3]]
                self.query_factory_text.delete("1.0", "end"); self.query_factory_text.insert("end", "\n".join(lines))
        except Exception as e:
            if hasattr(self, "query_factory_text"):
                self.query_factory_text.delete("1.0", "end"); self.query_factory_text.insert("end", "Query Factory Fehler: " + str(e))

    def send_query_factory_to_research_center(self):
        cid = self.selected_case_id.get(); qid = self.query_factory_selected_query_id.get()
        if not cid or not qid: return messagebox.showwarning("Query Factory", "Bitte eine Query markieren.")
        try:
            res = self.ctx.query_factory.selected_query_to_research_center(cid, qid)
            self.research_exec_query.set(res.get("query", "")); self.research_exec_phase.set(res.get("phase_key", "02_identity_web")); self.multi_search_query.set(res.get("query", ""))
            self.status.set("Query an Research Center übergeben: " + res.get("query", "")); self.refresh_all()
        except Exception as e: messagebox.showerror("Query Factory", str(e))

    def run_query_factory_security(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Query Factory", "Bitte Fall auswählen.")
        try:
            res = self.ctx.query_factory.run_security_checks(cid, self.selected_target_id.get())
            self.status.set("Query Factory Security: " + res.get("gate", "")); self.refresh_query_factory()
        except Exception as e: messagebox.showerror("Query Factory Security", str(e))


    def _tab_query_intelligence(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="2d Query Intelligence")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 44.0 – Query Intelligence Pro: Namensvarianten, Operatoren, Sprache/Land und Gegenbeleg-Queries")
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Profil:").pack(side="left", padx=4)
        self.query_intelligence_profile_combo = ttk.Combobox(top, textvariable=self.query_intelligence_profile, values=["de_eu", "en_global"], width=14, state="readonly")
        self.query_intelligence_profile_combo.pack(side="left", padx=4)
        ttk.Button(top, text="Query Intelligence erzeugen", command=self.generate_query_intelligence).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Markierte Query ins Research Center", command=self.send_query_intelligence_to_research).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Security Check", command=self.run_query_intelligence_security).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Aktualisieren", command=self.refresh_query_intelligence).pack(side="left", padx=4, pady=4)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=2)

        var_box = ttk.LabelFrame(left, text="Namensvarianten / Suchanker")
        var_box.pack(fill="x", padx=4, pady=4)
        self.query_intelligence_variant_tree = ttk.Treeview(var_box, columns=("type","value"), show="headings", height=6)
        for c,h,w in [("type","Typ",140),("value","Variante",420)]:
            self.query_intelligence_variant_tree.heading(c, text=h); self.query_intelligence_variant_tree.column(c, width=w)
        self.query_intelligence_variant_tree.pack(fill="x", expand=False, padx=4, pady=4)

        query_box = ttk.LabelFrame(left, text="Priorisierte Query Intelligence Items")
        query_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_intelligence_tree = ttk.Treeview(query_box, columns=("id","phase","prio","family","strategy","query","policy"), show="headings", height=18)
        for c,h,w in [("id","ID",120),("phase","Phase",160),("prio","Prio",55),("family","Familie",130),("strategy","Strategie",170),("query","Query",460),("policy","Policy",80)]:
            self.query_intelligence_tree.heading(c, text=h); self.query_intelligence_tree.column(c, width=w)
        self.query_intelligence_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_intelligence_tree.bind("<<TreeviewSelect>>", self._select_query_intelligence_item)

        info_box = ttk.LabelFrame(right, text="Dashboard / Guardrails / Rationale")
        info_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.query_intelligence_text = tk.Text(info_box, height=35, wrap="word"); self.query_intelligence_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _select_query_intelligence_item(self, event=None):
        if not hasattr(self, "query_intelligence_tree"): return
        sel = self.query_intelligence_tree.selection()
        if sel:
            vals = self.query_intelligence_tree.item(sel[0], "values")
            if vals: self.query_intelligence_selected_item_id.set(vals[0])

    def generate_query_intelligence(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Query Intelligence", "Bitte zuerst einen Fall auswählen.")
        try:
            targets = self.ctx.targets.list_targets(cid)
            tid = self.selected_target_id.get() or (targets[0]["target_id"] if targets else "")
            if not tid: return messagebox.showwarning("Query Intelligence", "Bitte zuerst eine Zielperson anlegen.")
            dash = self.ctx.query_intelligence.generate_for_case(cid, tid, profile_key=self.query_intelligence_profile.get(), notes="GUI Build 44.0 Query Intelligence")
            self.status.set(f"Query Intelligence erzeugt: {dash.get('allowed_count',0)} erlaubt / {dash.get('blocked_count',0)} blockiert.")
            self.refresh_query_intelligence()
        except Exception as e:
            messagebox.showerror("Query Intelligence", str(e))

    def refresh_query_intelligence(self):
        cid = self.selected_case_id.get()
        if not cid or not hasattr(self, "query_intelligence_tree"): return
        try:
            dash = self.ctx.query_intelligence.dashboard(cid)
            self.query_intelligence_tree.delete(*self.query_intelligence_tree.get_children())
            self.query_intelligence_variant_tree.delete(*self.query_intelligence_variant_tree.get_children())
            for v in dash.get("variants", []):
                self.query_intelligence_variant_tree.insert("", "end", values=(v.get("variant_type"), v.get("variant_value")))
            for it in dash.get("items", []):
                self.query_intelligence_tree.insert("", "end", values=(it.get("item_id"), it.get("phase_title"), it.get("priority"), it.get("query_family"), it.get("strategy_title"), it.get("query_text"), it.get("policy_status")))
            lines = [
                "QUERY INTELLIGENCE DASHBOARD",
                f"Status: {dash.get('status')}",
                f"Queries: {dash.get('query_count',0)} | allowed={dash.get('allowed_count',0)} | blocked={dash.get('blocked_count',0)}",
                f"Nächster Schritt: {dash.get('next_action','')}",
                "",
                "FAMILIEN",
                str(dash.get("family_counts", {})),
                "",
                "PHASEN",
                str(dash.get("phase_counts", {})),
                "",
                "GUARDRAILS",
                "\n".join("- "+g for g in dash.get("guardrails", [])),
                "",
                "TOP QUERIES",
                "\n".join(f"{q.get('priority')} | {q.get('phase_title')} | {q.get('strategy_title')} | {q.get('query_text')}" for q in dash.get("top_items", [])[:20]),
            ]
            self.query_intelligence_text.delete("1.0", "end"); self.query_intelligence_text.insert("end", "\n".join(lines))
        except Exception as e:
            self.query_intelligence_text.delete("1.0", "end"); self.query_intelligence_text.insert("end", "Query Intelligence Fehler: " + str(e))

    def send_query_intelligence_to_research(self):
        cid = self.selected_case_id.get(); item_id = self.query_intelligence_selected_item_id.get()
        if not cid or not item_id: return messagebox.showwarning("Query Intelligence", "Bitte eine Query markieren.")
        try:
            res = self.ctx.query_intelligence.selected_query_to_research_center(cid, item_id)
            self.research_exec_phase.set(res.get("phase_key", "02_identity_web"))
            self.research_exec_query.set(res.get("query", ""))
            self.status.set("Query Intelligence → Research Center: " + res.get("query", ""))
            self.refresh_research_execution()
        except Exception as e:
            messagebox.showerror("Query Intelligence", str(e))

    def run_query_intelligence_security(self):
        cid = self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Query Intelligence", "Bitte Fall auswählen.")
        try:
            res = self.ctx.query_intelligence.security_check(cid)
            self.status.set("Query Intelligence Security: " + res.get("gate", "")); self.refresh_query_intelligence()
        except Exception as e:
            messagebox.showerror("Query Intelligence Security", str(e))

    def _tab_capture_inbox(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="3 Capture Inbox")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 37.0 – Capture Inbox Pro: Browserfund → Duplicate-Check → Capture → Review")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Inbox aktualisieren", command=self.refresh_capture_inbox).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Zwischenablage einfügen", command=self.capture_inbox_paste_clipboard).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="URLs parsen/vorprüfen", command=self.capture_inbox_parse).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Batch → Review capturen", command=self.capture_inbox_promote_batch).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Ausgewähltes Item capturen", command=self.capture_inbox_promote_selected).pack(side="left", padx=4, pady=4)
        ttk.Button(top, text="Duplikate erzwingen", command=lambda: self.capture_inbox_promote_selected(force=True)).pack(side="left", padx=4, pady=4)

        cfg = ttk.LabelFrame(tab, text="Schneller URL-/Clipboard-Import")
        cfg.pack(fill="x", padx=8, pady=4)
        ttk.Label(cfg, text="Phase:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(cfg, textvariable=self.capture_inbox_phase, width=30, state="readonly", values=[
            "02_identity_web", "03_profiles_context", "04_image_media", "05_geo_places", "06_docs_business_archives", "07_counter_evidence"
        ]).grid(row=0, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(cfg, text="Titel-Präfix:").grid(row=0, column=2, sticky="w", padx=4, pady=3)
        ttk.Entry(cfg, textvariable=self.capture_inbox_title_prefix, width=38).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
        ttk.Label(cfg, text="Snippet/Notiz:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(cfg, textvariable=self.capture_inbox_snippet, width=80).grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
        cfg.columnconfigure(3, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=3); panes.add(right, weight=2)

        paste_box = ttk.LabelFrame(left, text="URL-Sammelfeld – mehrere Treffer aus Browser/Suchmaschine einfügen")
        paste_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.capture_inbox_urls_text = tk.Text(paste_box, height=12, wrap="word")
        self.capture_inbox_urls_text.pack(fill="both", expand=True, padx=4, pady=4)

        items_box = ttk.LabelFrame(left, text="Vorprüfung / Ready Queue")
        items_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.capture_inbox_tree = ttk.Treeview(items_box, columns=("id","status","dup","category","host","title","url"), show="headings", height=13)
        for c,h,w in [("id","Inbox-ID",145),("status","Status",125),("dup","Duplicate",120),("category","Kategorie",155),("host","Host",190),("title","Titelvorschlag",300),("url","URL",420)]:
            self.capture_inbox_tree.heading(c, text=h); self.capture_inbox_tree.column(c, width=w)
        self.capture_inbox_tree.pack(fill="both", expand=True, padx=4, pady=4)

        dash_box = ttk.LabelFrame(right, text="Dashboard / Guardrails / nächster Schritt")
        dash_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.capture_inbox_text = tk.Text(dash_box, height=24, wrap="word")
        self.capture_inbox_text.pack(fill="both", expand=True, padx=4, pady=4)

        batches_box = ttk.LabelFrame(right, text="Letzte Batches")
        batches_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.capture_inbox_batch_tree = ttk.Treeview(batches_box, columns=("id","time","valid","invalid","dups","status"), show="headings", height=8)
        for c,h,w in [("id","Batch",150),("time","Zeit",150),("valid","valid",55),("invalid","invalid",55),("dups","dups",55),("status","Status",130)]:
            self.capture_inbox_batch_tree.heading(c, text=h); self.capture_inbox_batch_tree.column(c, width=w)
        self.capture_inbox_batch_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.capture_inbox_batch_tree.bind("<<TreeviewSelect>>", self._select_capture_inbox_batch)

    def _capture_inbox_text_value(self) -> str:
        if hasattr(self, "capture_inbox_urls_text"):
            return self.capture_inbox_urls_text.get("1.0", "end").strip()
        return ""

    def _select_capture_inbox_batch(self, event=None):
        sel = getattr(self, "capture_inbox_batch_tree", None).selection() if hasattr(self, "capture_inbox_batch_tree") else []
        if sel:
            vals = self.capture_inbox_batch_tree.item(sel[0], "values")
            if vals:
                self.capture_inbox_selected_batch.set(vals[0])

    def capture_inbox_paste_clipboard(self):
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        if hasattr(self, "capture_inbox_urls_text"):
            self.capture_inbox_urls_text.delete("1.0", "end")
            self.capture_inbox_urls_text.insert("end", text)
        self.status.set("Zwischenablage in Capture Inbox eingefügt.")

    def capture_inbox_parse(self):
        cid = self.selected_case_id.get()
        if not cid:
            return messagebox.showwarning("Capture Inbox", "Bitte zuerst einen Fall auswählen.")
        try:
            res = self.ctx.capture_inbox.create_batch(
                cid, self._capture_inbox_text_value(), phase_key=self.capture_inbox_phase.get(), target_id=self.selected_target_id.get(),
                title_prefix=self.capture_inbox_title_prefix.get().strip() or "Öffentlicher Treffer",
                snippet=self.capture_inbox_snippet.get().strip(),
                notes="Build 39.0 Evidence-to-Report Automation: schneller URL-/Clipboard-Import mit Duplicate-Vorprüfung."
            )
            self.capture_inbox_selected_batch.set(res["batch_id"])
            self.status.set(f"Capture Inbox Batch erstellt: {res['created_items']} gültig / {len(res.get('invalid_items', []))} ungültig / {res.get('duplicate_count',0)} Duplikat-Hinweise")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Capture Inbox", str(e))

    def capture_inbox_promote_batch(self):
        bid = self.capture_inbox_selected_batch.get()
        if not bid:
            return messagebox.showwarning("Capture Inbox", "Bitte zuerst einen Batch auswählen oder URLs parsen.")
        try:
            res = self.ctx.capture_inbox.promote_batch_to_review(bid, force_duplicates=False)
            self.status.set(f"Batch verarbeitet: {res.get('promoted')} capturen → Review, {res.get('held_for_duplicate_review')} Duplikate gehalten")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Capture Inbox", str(e))

    def capture_inbox_promote_selected(self, force: bool=False):
        if not hasattr(self, "capture_inbox_tree"):
            return
        sel = self.capture_inbox_tree.selection()
        if not sel:
            return messagebox.showwarning("Capture Inbox", "Bitte zuerst ein Inbox-Item auswählen.")
        item_id = self.capture_inbox_tree.item(sel[0], "values")[0]
        try:
            item = self.ctx.capture_inbox.promote_item_to_review(item_id, force_duplicate=force)
            self.status.set(f"Capture Inbox Item verarbeitet: {item.get('status')} / capture={item.get('capture_id','')}")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Capture Inbox", str(e))

    def refresh_capture_inbox(self):
        cid = self.selected_case_id.get()
        if not cid:
            return
        dash = self.ctx.capture_inbox.dashboard(cid)
        if hasattr(self, "capture_inbox_tree"):
            self.capture_inbox_tree.delete(*self.capture_inbox_tree.get_children())
            for item in dash.get("recent_items", []):
                self.capture_inbox_tree.insert("", "end", values=(item.get("inbox_item_id"), item.get("status"), item.get("duplicate_status"), item.get("category_label"), item.get("host"), item.get("title_suggestion"), item.get("normalized_url")))
        if hasattr(self, "capture_inbox_batch_tree"):
            self.capture_inbox_batch_tree.delete(*self.capture_inbox_batch_tree.get_children())
            for b in dash.get("batches", []):
                self.capture_inbox_batch_tree.insert("", "end", values=(b.get("batch_id"), b.get("created_at"), b.get("valid_count"), b.get("invalid_count"), b.get("duplicate_count"), b.get("status")))
        if hasattr(self, "capture_inbox_text"):
            lines = [
                "CAPTURE INBOX PRO",
                f"Nächster Schritt: {dash.get('next_action')}",
                "",
                "Status:",
            ]
            lines += [f"- {k}: {v}" for k,v in sorted(dash.get("status_counts", {}).items())] or ["- keine Items"]
            lines += ["", "Kategorien:"] + ([f"- {k}: {v}" for k,v in sorted(dash.get("category_counts", {}).items())] or ["- keine Kategorien"])
            lines += ["", f"Duplicate-Kandidaten: {dash.get('duplicate_candidates',0)}", "", "Guardrails:"] + [f"- {g}" for g in dash.get("guardrails", [])]
            self.capture_inbox_text.delete("1.0", "end"); self.capture_inbox_text.insert("end", "\n".join(lines))

    def _tab_search(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="Search Workbench")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 Search Workbench – gebündelte Recherche plus Multi-Search Launcher")
        top.pack(fill="x",padx=8,pady=6)
        ttk.Button(top,text="Recherchepakete aus Zielperson erzeugen",command=self.generate_search_packages).pack(side="left",padx=4,pady=4)
        ttk.Label(top,text="Suchbündel:").pack(side="left",padx=(14,2),pady=4)
        self.search_bundle_combo=ttk.Combobox(top,textvariable=self.selected_search_bundle,width=36,state="readonly",values=self.ctx.ux_consolidation.bundle_options())
        self.search_bundle_combo.pack(side="left",padx=4,pady=4)
        self.search_bundle_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_all())
        ttk.Label(top,text="Multi-Search Preset:").pack(side="left",padx=(14,2),pady=4)
        self.multi_search_preset_combo=ttk.Combobox(top,textvariable=self.selected_multi_search_preset,width=34,state="readonly",values=self.ctx.search_workbench.multi_search_preset_options())
        self.multi_search_preset_combo.pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Markierte Query in mehreren Engines öffnen",command=self.open_selected_query_multi_search).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Ausgewählten Suchlink öffnen",command=self.open_selected_search).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Ausgewählte Aufgabe als öffentlichen Treffer capturen",command=self.capture_selected_search_task).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Capture-Manifest prüfen",command=self.verify_capture_manifest).pack(side="left",padx=4,pady=4)

        quick=ttk.LabelFrame(tab,text="Suchanfrage / freie Mehrfachsuche: Suchbegriff sichtbar eingeben oder automatisch aus Zielperson/Suchaufgabe übernehmen")
        quick.pack(fill="x",padx=8,pady=4)
        ttk.Label(quick,text="Suchanfrage:").pack(side="left",padx=4,pady=4)
        ttk.Entry(quick,textvariable=self.multi_search_query,width=96).pack(side="left",fill="x",expand=True,padx=4,pady=4)
        ttk.Button(quick,text="Mehrere Suchmaschinen öffnen",command=self.open_free_multi_search).pack(side="left",padx=4,pady=4)
        ttk.Button(quick,text="Suchanfrage aus Zielperson erzeugen",command=self.fill_multi_search_from_target).pack(side="left",padx=4,pady=4)
        ttk.Button(quick,text="Query aus markierter Aufgabe übernehmen",command=self.copy_selected_query_to_multi_search).pack(side="left",padx=4,pady=4)
        self.search_capture_title=tk.StringVar(value="Öffentlicher Treffer / Profil / Dokument")
        self.search_capture_url=tk.StringVar(value="https://example.org/public-source")
        self.search_capture_snippet=tk.StringVar(value="Kurzer Auszug oder eigene Zusammenfassung des öffentlich sichtbaren Treffers.")
        cap=ttk.LabelFrame(tab,text="Capture-Metadaten für den aktuell geprüften Treffer")
        cap.pack(fill="x",padx=8,pady=4)
        for i,(lbl,var,w) in enumerate([("Titel",self.search_capture_title,80),("URL",self.search_capture_url,100),("Snippet/Notiz",self.search_capture_snippet,120)]):
            ttk.Label(cap,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=2)
            ttk.Entry(cap,textvariable=var,width=w).grid(row=i,column=1,sticky="ew",padx=4,pady=2)
        cap.columnconfigure(1,weight=1)
        panes=ttk.Panedwindow(tab,orient="vertical"); panes.pack(fill="both",expand=True,padx=8,pady=8)
        pf=ttk.LabelFrame(panes,text="Recherchepakete / Suchbündel")
        tf=ttk.LabelFrame(panes,text="Suchaufgaben")
        mf=ttk.LabelFrame(panes,text="Multi-Search Launches / gleichzeitig geöffnete Suchmaschinen")
        cf=ttk.LabelFrame(panes,text="Capture-Snapshots / Übergabe in Review Inbox")
        panes.add(pf,weight=1); panes.add(tf,weight=3); panes.add(mf,weight=1); panes.add(cf,weight=2)
        self.package_tree=ttk.Treeview(pf,columns=("id","key","name","tasks","status","objective"),show="headings",height=5)
        for c,h,w in [("id","Paket-ID",150),("key","Key",140),("name","Name",180),("tasks","Tasks",70),("status","Status",90),("objective","Zweck",650)]:
            self.package_tree.heading(c,text=h); self.package_tree.column(c,width=w)
        self.package_tree.pack(fill="both",expand=True)
        self.package_tree.bind("<<TreeviewSelect>>", self._select_package_from_tree)
        self.search_tree=ttk.Treeview(tf,columns=("id","package","status","cat","engine","query","url"),show="headings",height=12)
        for c,h,w in [("id","Task-ID",140),("package","Paket",150),("status","Status",90),("cat","Kategorie",160),("engine","Engine",90),("query","Query",320),("url","URL",500)]:
            self.search_tree.heading(c,text=h); self.search_tree.column(c,width=w)
        self.search_tree.pack(fill="both",expand=True)
        self.multi_search_tree=ttk.Treeview(mf,columns=("id","time","preset","engines","count","query","status"),show="headings",height=5)
        for c,h,w in [("id","Launch-ID",145),("time","Zeit",150),("preset","Preset",140),("engines","Engines",270),("count","Tabs",60),("query","Query",520),("status","Status",100)]:
            self.multi_search_tree.heading(c,text=h); self.multi_search_tree.column(c,width=w)
        self.multi_search_tree.pack(fill="both",expand=True)
        self.capture_tree=ttk.Treeview(cf,columns=("id","time","title","host","hash","review","status"),show="headings",height=8)
        for c,h,w in [("id","Capture-ID",145),("time","Zeit",150),("title","Titel",260),("host","Host",170),("hash","Hash",160),("review","Review-ID",145),("status","Status",140)]:
            self.capture_tree.heading(c,text=h); self.capture_tree.column(c,width=w)
        self.capture_tree.pack(fill="both",expand=True)

    def _select_package_from_tree(self,event=None):
        sel=getattr(self,"package_tree",None).selection() if hasattr(self,"package_tree") else []
        if sel:
            self.selected_package_id.set(self.package_tree.item(sel[0],"values")[0])
            self.refresh_all()

    def generate_search_packages(self):
        cid=self.selected_case_id.get(); tid=self.selected_target_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        targets=self.ctx.targets.list_targets(cid)
        if not targets: return messagebox.showwarning("Hinweis","Zuerst Zielperson anlegen.")
        if not tid: tid=targets[0]["target_id"]; self.selected_target_id.set(tid)
        legal=self.ctx.legal.evaluate_case(cid)
        if not legal.get("ok"):
            return messagebox.showwarning("Legal Gate", "Recherche gesperrt bis Legal Gate PASS:\n"+"\n".join(legal.get("issues",[])))
        res=self.ctx.search_workbench.create_packages_from_target(cid,tid)
        self.status.set(f"Search Workbench: {res['packages']} Pakete und {res['tasks']} Suchaufgaben erzeugt.")
        self.refresh_all()

    def generate_search_tasks(self):
        # Backward-compatible alias from Build 17.0.
        return self.generate_search_packages()

    def _current_multi_search_preset_key(self) -> str:
        value = getattr(self, "selected_multi_search_preset", tk.StringVar(value="standard")).get()
        if not value:
            return "standard"
        return value.split(" | ", 1)[0].strip() or "standard"

    def _open_multi_search_launch(self, launch: dict):
        urls = launch.get("urls") or []
        if not urls and launch.get("launch_id"):
            urls = self.ctx.search_workbench.get_multi_search_urls(launch["launch_id"])
        for u in urls:
            webbrowser.open_new_tab(u.get("url"))
        if launch.get("launch_id"):
            self.ctx.search_workbench.mark_multi_search_opened(launch["launch_id"])
        self.status.set(f"Multi-Search geöffnet: {len(urls)} Suchmaschinen für Query: {launch.get('query','')}")
        self.refresh_all()

    def copy_selected_query_to_multi_search(self):
        sel = getattr(self, "search_tree", None).selection() if hasattr(self, "search_tree") else []
        if not sel:
            return messagebox.showinfo("Multi-Search", "Bitte zuerst eine Suchaufgabe auswählen.")
        vals = self.search_tree.item(sel[0], "values")
        self.multi_search_query.set(vals[5])
        self.status.set("Query in freie Mehrfachsuche übernommen.")

    def _selected_search_task_id(self) -> str:
        sel = getattr(self, "search_tree", None).selection() if hasattr(self, "search_tree") else []
        if not sel:
            return ""
        vals = self.search_tree.item(sel[0], "values")
        return vals[0] if vals else ""

    def _resolve_visible_multi_search_query(self, prefer_selected_task: bool = False) -> dict:
        cid = self.selected_case_id.get()
        if not cid:
            raise ValueError("Bitte zuerst einen Fall auswählen.")
        task_id = self._selected_search_task_id() if prefer_selected_task else ""
        if not task_id and not self.multi_search_query.get().strip():
            # Fallback: a selected task should work even when the visible field is still empty.
            task_id = self._selected_search_task_id()
        resolved = self.ctx.search_workbench.resolve_multi_search_query(
            cid,
            explicit_query=self.multi_search_query.get().strip(),
            target_id=self.selected_target_id.get(),
            task_id=task_id,
        )
        self.multi_search_query.set(resolved.get("query", ""))
        if resolved.get("target_id") and not self.selected_target_id.get():
            self.selected_target_id.set(resolved["target_id"])
        return resolved

    def fill_multi_search_from_target(self):
        try:
            if not self.selected_case_id.get():
                return messagebox.showwarning("Hinweis", "Bitte zuerst einen Fall auswählen.")
            resolved = self.ctx.search_workbench.suggest_multi_search_query_from_target(
                self.selected_case_id.get(), self.selected_target_id.get()
            )
            self.multi_search_query.set(resolved["query"])
            if resolved.get("target_id"):
                self.selected_target_id.set(resolved["target_id"])
            self.status.set("Suchanfrage aus Zielperson erzeugt und ins sichtbare Feld eingetragen.")
        except Exception as e:
            messagebox.showwarning("Suchanfrage", str(e))

    def open_free_multi_search(self):
        try:
            cid = self.selected_case_id.get()
            resolved = self._resolve_visible_multi_search_query(prefer_selected_task=False)
            launch = self.ctx.search_workbench.create_multi_search_launch(
                cid,
                resolved["query"],
                preset_key=self._current_multi_search_preset_key(),
                target_id=resolved.get("target_id", "") or self.selected_target_id.get(),
                source_task_id=resolved.get("task_id", ""),
                bundle_key=self._current_search_bundle_key(),
                notes=f"GUI Build 37.0 Hotfix: Mehrfachsuche, Query-Quelle={resolved.get('source','unknown')}",
            )
            self._open_multi_search_launch(launch)
        except Exception as e:
            messagebox.showerror("Multi-Search", str(e))

    def open_selected_query_multi_search(self):
        try:
            cid = self.selected_case_id.get()
            resolved = self._resolve_visible_multi_search_query(prefer_selected_task=True)
            launch = self.ctx.search_workbench.create_multi_search_launch(
                cid,
                resolved["query"],
                preset_key=self._current_multi_search_preset_key(),
                target_id=resolved.get("target_id", "") or self.selected_target_id.get(),
                source_task_id=resolved.get("task_id", ""),
                bundle_key=self._current_search_bundle_key(),
                notes=f"GUI Build 37.0 Hotfix: Mehrfachsuche aus markierter Aufgabe/Fallback, Query-Quelle={resolved.get('source','unknown')}",
            )
            self._open_multi_search_launch(launch)
        except Exception as e:
            messagebox.showerror("Multi-Search", str(e))

    def open_selected_search(self):
        sel=self.search_tree.selection()
        if not sel: return
        task_id=self.search_tree.item(sel[0],"values")[0]
        url=self.search_tree.item(sel[0],"values")[6]
        try:
            self.ctx.search_workbench.mark_task_opened(task_id)
        except Exception:
            pass
        webbrowser.open(url)
        self.refresh_all()

    def capture_selected_search_task(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        sel=self.search_tree.selection()
        if not sel: return messagebox.showinfo("Hinweis","Bitte zuerst eine Suchaufgabe auswählen.")
        vals=self.search_tree.item(sel[0],"values")
        task_id=vals[0]
        if not self.search_capture_url.get().strip() or self.search_capture_url.get().strip()=="https://example.org/public-source":
            self.search_capture_url.set(vals[6])
        try:
            cap=self.ctx.search_workbench.capture_public_hit(
                cid, task_id, self.search_capture_title.get(), self.search_capture_url.get(),
                self.search_capture_snippet.get(), notes="Build 37.0 Capture: manuell geprüfter öffentlicher Treffer; automatisch an Review Inbox übergeben.")
            self.status.set("Capture erstellt und an Review Inbox übergeben: "+cap["capture_id"])
            self.refresh_all()
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def verify_capture_manifest(self):
        cid=self.selected_case_id.get()
        if not cid: return
        messagebox.showinfo("Capture Manifest", str(self.ctx.search_workbench.capture_manifest(cid)))

    def _tab_review(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="6 Review Inbox")
        self._case_selector(tab)
        f=ttk.LabelFrame(tab,text="Manuellen Treffer speichern")
        f.pack(fill="x",padx=8,pady=6)
        self.hit_title=tk.StringVar(value="Öffentlicher Beispieltreffer")
        self.hit_url=tk.StringVar(value="https://example.org/profile")
        self.hit_snippet=tk.StringVar(value="Öffentlicher Hinweis, muss geprüft werden.")
        self.hit_score=tk.StringVar(value="0.6")
        rows=[("Titel",self.hit_title),("URL",self.hit_url),("Snippet",self.hit_snippet),("Score 0-1",self.hit_score)]
        for i,(lbl,var) in enumerate(rows): ttk.Label(f,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=3); ttk.Entry(f,textvariable=var,width=120).grid(row=i,column=1,sticky="ew",padx=4,pady=3)
        f.columnconfigure(1,weight=1)
        ttk.Button(f,text="Treffer in Review Inbox speichern",command=self.add_review_hit).grid(row=4,column=1,sticky="e")
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=2)
        ttk.Button(toolbar,text="Ausgewählten Treffer als Lead akzeptieren",command=lambda:self.update_selected_review("accepted_as_lead")).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Ausgewählten Treffer ablehnen",command=lambda:self.update_selected_review("rejected")).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Duplikate clustern",command=self.find_review_duplicates).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Bulk-Triage ausführen",command=self.bulk_triage_review).pack(side="left",padx=2)
        self.review_tree=ttk.Treeview(tab,columns=("id","status","score","quality","sens","title","url","triage"),show="headings",height=17)
        for c,h,w in [("id","ID",145),("status","Status",150),("score","Score",65),("quality","Quality",70),("sens","Sens.",70),("title","Titel",260),("url","URL",360),("triage","Triage-Grund",320)]: self.review_tree.heading(c,text=h); self.review_tree.column(c,width=w)
        self.review_tree.pack(fill="both",expand=True,padx=8,pady=8)

    def add_review_hit(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        try:
            self.ctx.review.add_manual_hit(cid,self.hit_title.get(),self.hit_url.get(),self.hit_snippet.get(),score=float(self.hit_score.get() or 0.5))
            self.refresh_all()
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def update_selected_review(self,status):
        sel=self.review_tree.selection()
        if not sel: return
        item_id=self.review_tree.item(sel[0],"values")[0]
        self.ctx.review.update_status(item_id,status)
        self.refresh_all()

    def find_review_duplicates(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.review.find_duplicates(cid)
        self.status.set(f"Duplikatprüfung: {res['cluster_count']} Cluster erkannt.")
        self.refresh_all()

    def bulk_triage_review(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.review.bulk_triage(cid)
        self.status.set(f"Bulk-Triage: {res['triaged']} Treffer geprüft – {res['summary']}.")
        self.refresh_all()

    def _tab_evidence(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="7 Evidence Vault")
        self._case_selector(tab)
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=6)
        ttk.Button(toolbar,text="Ausgewählten Review-Treffer zu Evidence Candidate hochstufen",command=self.promote_selected_evidence).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Evidence akzeptieren + Export freigeben",command=self.accept_selected_evidence).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Redaction Review",command=self.redact_selected_evidence).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Evidence Manifest prüfen",command=self.verify_evidence).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Evidence Package Manifest erzeugen",command=self.create_evidence_package_manifest).pack(side="left",padx=2)
        self.evidence_tree=ttk.Treeview(tab,columns=("id","cat","conf","decision","rel","export","redact","title","hash"),show="headings",height=25)
        for c,h,w in [("id","Evidence-ID",145),("cat","Kategorie",170),("conf","Confidence",90),("decision","Entscheidung",120),("rel","Reliability",80),("export","Export",65),("redact","Redact",65),("title","Titel",270),("hash","Hash",230)]: self.evidence_tree.heading(c,text=h); self.evidence_tree.column(c,width=w)
        self.evidence_tree.pack(fill="both",expand=True,padx=8,pady=8)

    def promote_selected_evidence(self):
        sel=self.review_tree.selection()
        if not sel:
            messagebox.showinfo("Hinweis","Bitte im Tab Review Inbox einen Treffer auswählen."); return
        item_id=self.review_tree.item(sel[0],"values")[0]
        try:
            self.ctx.evidence.promote_review_item(item_id, export_allowed=False, notes="Build 17 Promotion; Export bleibt bis Export Control/Legal Review blockiert.")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def accept_selected_evidence(self):
        sel=self.evidence_tree.selection()
        if not sel: return messagebox.showinfo("Hinweis","Bitte Evidence auswählen.")
        evidence_id=self.evidence_tree.item(sel[0],"values")[0]
        self.ctx.evidence.decide_evidence(evidence_id,"accepted",export_allowed=True,redaction_required=False,notes="Build 20 GUI Review: exportfähig nach Analystenprüfung.")
        self.refresh_all()

    def redact_selected_evidence(self):
        sel=self.evidence_tree.selection()
        if not sel: return messagebox.showinfo("Hinweis","Bitte Evidence auswählen.")
        evidence_id=self.evidence_tree.item(sel[0],"values")[0]
        res=self.ctx.evidence.create_redaction_review(evidence_id,profile="client_safe",decision="redacted",notes="Build 20 GUI Redaction Review")
        messagebox.showinfo("Redaction Review", str(res))
        self.refresh_all()

    def create_evidence_package_manifest(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.evidence.create_package_manifest(cid,self.ctx.reports_dir,notes="GUI Evidence Package Manifest")
        messagebox.showinfo("Evidence Package Manifest", str(res))
        self.refresh_all()

    def verify_evidence(self):
        cid=self.selected_case_id.get()
        if not cid: return
        messagebox.showinfo("Evidence Manifest", str(self.ctx.evidence.verify_manifest(cid)))

    def _tab_identity_risk(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="8 Identity & Risk")
        self._case_selector(tab)
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=6)
        ttk.Button(toolbar,text="Identity Candidates erzeugen",command=self.generate_identity_candidates).pack(side="left")
        ttk.Button(toolbar,text="Risk Assessment aktualisieren",command=self.run_risk_assessment).pack(side="left",padx=6)
        panes=ttk.Panedwindow(tab,orient="horizontal"); panes.pack(fill="both",expand=True,padx=8,pady=8)
        lf=ttk.LabelFrame(panes,text="Identity Candidates – keine automatische Identitätsbestätigung"); rf=ttk.LabelFrame(panes,text="Risiko-/Unsicherheitenregister")
        panes.add(lf,weight=1); panes.add(rf,weight=1)
        self.identity_tree=ttk.Treeview(lf,columns=("id","label","score","status","positive","negative"),show="headings")
        for c,h,w in [("id","ID",140),("label","Label",220),("score","Score",80),("status","Status",150),("positive","Positive Marker",260),("negative","Negative Marker",260)]: self.identity_tree.heading(c,text=h); self.identity_tree.column(c,width=w)
        self.identity_tree.pack(fill="both",expand=True)
        self.risk_tree=ttk.Treeview(rf,columns=("id","sev","cat","title","status"),show="headings")
        for c,h,w in [("id","ID",130),("sev","Severity",90),("cat","Kategorie",150),("title","Titel",320),("status","Status",120)]: self.risk_tree.heading(c,text=h); self.risk_tree.column(c,width=w)
        self.risk_tree.pack(fill="both",expand=True)

    def generate_identity_candidates(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.identity.generate_candidates(cid)
        self.status.set(f"{len(res)} Identity Candidate(s) aktualisiert."); self.refresh_all()

    def run_risk_assessment(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.risk.auto_assess_case(cid)
        self.status.set(f"Risk Assessment: {len(res['findings'])} Finding(s).")
        self.refresh_all()

    def _tab_graph_timeline(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="9 Graph & Timeline Pro")
        self._case_selector(tab)
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=5)
        ttk.Button(toolbar,text="Pro-Graph aus Evidence/Ankern neu aufbauen",command=self.rebuild_graph).pack(side="left")
        ttk.Button(toolbar,text="Timeline aus Evidence erzeugen",command=self.build_timeline_from_evidence).pack(side="left",padx=4)
        ttk.Button(toolbar,text="Konflikte prüfen",command=self.detect_timeline_conflicts).pack(side="left",padx=4)
        ttk.Button(toolbar,text="Analyse-Narrative erzeugen",command=self.build_analysis_narratives).pack(side="left",padx=4)
        ttk.Button(toolbar,text="Hypothese anlegen",command=self.create_graph_hypothesis).pack(side="left",padx=4)
        self.tdate=tk.StringVar(value="2026-06-02"); self.ttitle=tk.StringVar(value="OSINT-Hinweis erfasst")
        self.tevent_type=tk.StringVar(value="osint_finding")
        entrybar=ttk.Frame(tab); entrybar.pack(fill="x",padx=8,pady=3)
        ttk.Label(entrybar,text="Datum").pack(side="left",padx=(0,2)); ttk.Entry(entrybar,textvariable=self.tdate,width=12).pack(side="left")
        ttk.Label(entrybar,text="Typ").pack(side="left",padx=(8,2)); ttk.Entry(entrybar,textvariable=self.tevent_type,width=18).pack(side="left")
        ttk.Label(entrybar,text="Titel").pack(side="left",padx=(8,2)); ttk.Entry(entrybar,textvariable=self.ttitle,width=46).pack(side="left")
        ttk.Button(entrybar,text="Timeline-Ereignis hinzufügen",command=self.add_timeline).pack(side="left",padx=8)
        panes=ttk.Panedwindow(tab,orient="horizontal"); panes.pack(fill="both",expand=True,padx=8,pady=8)
        lf=ttk.LabelFrame(panes,text="Explainable Graph / Hypothesen / Gegenbelege"); rf=ttk.LabelFrame(panes,text="Timeline Pro")
        panes.add(lf,weight=2); panes.add(rf,weight=1)
        self.graph_text=tk.Text(lf); self.graph_text.pack(fill="both",expand=True)
        self.timeline_tree=ttk.Treeview(rf,columns=("date","type","title","status","weight"),show="headings")
        for c,h,w in [("date","Datum",110),("type","Typ",120),("title","Titel",260),("status","Status",100),("weight","Gewicht",70)]: self.timeline_tree.heading(c,text=h); self.timeline_tree.column(c,width=w)
        self.timeline_tree.pack(fill="both",expand=True)

    def rebuild_graph(self):
        cid=self.selected_case_id.get();
        if not cid: return
        res=self.ctx.graph.rebuild_pro_graph(cid); self.status.set(f"Graph Pro: {res.get('nodes')} Knoten / {res.get('edges')} Kanten"); self.refresh_all()

    def build_timeline_from_evidence(self):
        cid=self.selected_case_id.get();
        if not cid: return
        res=self.ctx.timeline.build_from_evidence(cid); self.status.set(f"Timeline Pro aus Evidence: {res}"); self.refresh_all()

    def detect_timeline_conflicts(self):
        cid=self.selected_case_id.get();
        if not cid: return
        res=self.ctx.timeline.detect_conflicts(cid); messagebox.showinfo("Timeline-Konflikte", str(res)); self.refresh_all()

    def build_analysis_narratives(self):
        cid=self.selected_case_id.get();
        if not cid: return
        gn=self.ctx.graph.build_analysis_narrative(cid)
        tn=self.ctx.timeline.build_narrative(cid)
        self.status.set(f"Analyse-Narrative erzeugt: {gn.get('narrative_id')} / {tn.get('narrative_id')}"); self.refresh_all()

    def create_graph_hypothesis(self):
        cid=self.selected_case_id.get();
        if not cid: return
        evidence=self.ctx.evidence.list_evidence(cid)
        supporting=[e["evidence_id"] for e in evidence[:3]]
        hyp=self.ctx.graph.create_hypothesis(cid,"Prüfhypothese: öffentliche Anker gehören zusammen","Die bisher geprüften Evidence Items könnten dieselbe OSINT-Spur/Entität stützen; menschliche Prüfung und Gegenbelege erforderlich.",confidence=0.55,supporting_evidence=supporting,notes="GUI-Hypothese Build 37.0")
        self.status.set("Hypothese angelegt: "+hyp["hypothesis_id"]); self.refresh_all()

    def add_timeline(self):
        cid=self.selected_case_id.get();
        if not cid: return
        self.ctx.timeline.add_event(cid,self.tdate.get(),self.ttitle.get(),"Manuell erfasstes Timeline-Ereignis; muss quellenkritisch geprüft werden.",event_type=self.tevent_type.get(),narrative_weight=0.5,uncertainty_note="Manuell erfasst; Quelle/Evidence bitte nachtragen.")
        self.refresh_all()

    def _tab_ai_assistant(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="10 AI Analyst")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – assistierende KI-Schicht: keine automatische Identitäts-, Schuld-, Gefährlichkeits- oder Wohnortentscheidung")
        top.pack(fill="x",padx=8,pady=8)
        ttk.Button(top,text="AI Bundle ausführen",command=self.ai_run_bundle).grid(row=0,column=0,padx=4,pady=4)
        ttk.Button(top,text="Case Digest",command=self.ai_case_digest).grid(row=0,column=1,padx=4,pady=4)
        ttk.Button(top,text="Widersprüche scannen",command=self.ai_scan_contradictions).grid(row=0,column=2,padx=4,pady=4)
        ttk.Button(top,text="Gegenhypothesen",command=self.ai_counter_hypotheses).grid(row=0,column=3,padx=4,pady=4)
        ttk.Button(top,text="Timeline-Entwürfe",command=self.ai_timeline_drafts).grid(row=0,column=4,padx=4,pady=4)
        ttk.Button(top,text="Report-Entwürfe",command=self.ai_report_drafts).grid(row=0,column=5,padx=4,pady=4)
        ttk.Button(top,text="Aktualisieren",command=self.refresh_all).grid(row=0,column=6,padx=4,pady=4)
        self.ai_text=tk.Text(tab,height=34,wrap="word")
        self.ai_text.pack(fill="both",expand=True,padx=8,pady=8)

    def _ai_print(self, title, data):
        if hasattr(self,"ai_text"):
            self.ai_text.delete("1.0","end")
            self.ai_text.insert("end", title+"\n"+str(data))

    def ai_run_bundle(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.run_assistant_bundle(cid)
            self._ai_print("AI ANALYST BUNDLE",res)
            self.status.set("AI Bundle ausgeführt: "+res.get("task_id", "")); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))

    def ai_case_digest(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.build_case_digest(cid)
            self._ai_print("AI CASE DIGEST",res)
            self.status.set("AI Case Digest erzeugt."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))

    def ai_scan_contradictions(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.suggest_contradictions(cid)
            self._ai_print("AI WIDERSPRUCHSSCAN",res)
            self.status.set("AI Widerspruchsscan abgeschlossen."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))

    def ai_counter_hypotheses(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.suggest_counter_hypotheses(cid)
            self._ai_print("AI GEGENHYPOTHESEN",res)
            self.status.set("AI Gegenhypothesen erzeugt."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))

    def ai_timeline_drafts(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.draft_timeline_from_evidence(cid)
            self._ai_print("AI TIMELINE-ENTWÜRFE",res)
            self.status.set("AI Timeline-Entwürfe erzeugt."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))

    def ai_report_drafts(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("AI Analyst","Bitte zuerst Fall auswählen.")
        try:
            res=self.ctx.ai_analyst.draft_report_sections(cid,"internal_analyst")
            self._ai_print("AI REPORT-ENTWÜRFE",res)
            self.status.set("AI Report-Entwürfe erzeugt."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("AI Analyst",str(e))


    def _tab_report_automation(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="4 Evidence→Report")
        self._case_selector(tab)
        top = ttk.LabelFrame(tab, text="Build 41.0 – Evidence-to-Report Automation / Pilot-Hardening")
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Erzeugt assistierende Berichtsentwürfe aus geprüfter Evidence, Gap-Analyse, Graph/Timeline und Readiness-Check. Menschliche Review bleibt Pflicht.").grid(row=0, column=0, columnspan=6, sticky="w", padx=4, pady=4)
        ttk.Label(top, text="Reporttyp").grid(row=1, column=0, sticky="w", padx=4)
        ttk.Combobox(top, textvariable=self.report_automation_type, values=["redacted_client", "client_short", "full_dossier", "internal_analyst", "evidence_annex"], width=22, state="readonly").grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(top, text="Redaction").grid(row=1, column=2, sticky="w", padx=4)
        ttk.Combobox(top, textvariable=self.report_automation_profile, values=["client_safe", "internal", "full", "public_minimal"], width=18).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Button(top, text="Pipeline prüfen", command=self.refresh_report_automation).grid(row=1, column=4, padx=4)
        ttk.Button(top, text="Entwurf erzeugen", command=self.generate_report_automation_draft).grid(row=1, column=5, padx=4)
        ttk.Button(top, text="Automatisierten Report exportieren", command=self.export_report_automation).grid(row=1, column=6, padx=4)
        top.columnconfigure(0, weight=1)

        panes = ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=1); panes.add(right, weight=2)

        metric_box = ttk.LabelFrame(left, text="Readiness / Metriken")
        metric_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.report_auto_metric_tree = ttk.Treeview(metric_box, columns=("metric", "value"), show="headings", height=14)
        self.report_auto_metric_tree.heading("metric", text="Metrik"); self.report_auto_metric_tree.heading("value", text="Wert")
        self.report_auto_metric_tree.column("metric", width=220); self.report_auto_metric_tree.column("value", width=140)
        self.report_auto_metric_tree.pack(fill="both", expand=True, padx=4, pady=4)

        text_box = ttk.LabelFrame(right, text="Pipeline, Blocker, Warnungen und Entwürfe")
        text_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.report_automation_text = tk.Text(text_box, wrap="word")
        self.report_automation_text.pack(fill="both", expand=True, padx=4, pady=4)

    def refresh_report_automation(self):
        cid = self.selected_case_id.get()
        if not cid:
            messagebox.showwarning("Evidence→Report", "Bitte zuerst einen Fall auswählen.")
            return
        try:
            dash = self.ctx.report_automation.pipeline_dashboard(cid, self.report_automation_type.get())
            if hasattr(self, "report_auto_metric_tree"):
                self.report_auto_metric_tree.delete(*self.report_auto_metric_tree.get_children())
                for k, v in dash.get("metrics", {}).items():
                    self.report_auto_metric_tree.insert("", "end", values=(k, v))
                for k, v in dash.get("gap_scores", {}).items():
                    self.report_auto_metric_tree.insert("", "end", values=("gap_" + str(k), v))
            lines = [
                "EVIDENCE → REPORT PIPELINE",
                f"Status: {dash.get('status')}",
                f"Reporttyp: {dash.get('report_type')}",
                "",
                "BLOCKER",
            ]
            lines += ["- " + b for b in dash.get("blockers", [])] or ["- keine"]
            lines.append("\nWARNUNGEN")
            lines += ["- " + w for w in dash.get("warnings", [])] or ["- keine"]
            lines.append("\nGAP-EMPFEHLUNGEN")
            for r in dash.get("gap_recommendations", [])[:12]:
                lines.append(f"- {r.get('phase_key','')}: {r.get('recommendation','')}")
            if hasattr(self, "report_automation_text"):
                self.report_automation_text.delete("1.0", "end")
                self.report_automation_text.insert("end", "\n".join(lines))
            self.status.set("Evidence→Report Pipeline geprüft: " + str(dash.get("status")))
        except Exception as exc:
            messagebox.showerror("Evidence→Report", str(exc))

    def generate_report_automation_draft(self):
        cid = self.selected_case_id.get()
        if not cid:
            messagebox.showwarning("Evidence→Report", "Bitte zuerst einen Fall auswählen.")
            return
        try:
            res = self.ctx.report_automation.generate_report_draft(
                cid,
                self.report_automation_type.get(),
                self.report_automation_profile.get(),
                notes="GUI Build 41.0: Evidence-to-Report Entwurf, menschliche Review erforderlich."
            )
            lines = [f"ENTWURF ERZEUGT: {res.get('run_id')}", f"Status: {res.get('status')}", "", "SEKTIONEN"]
            for sec in res.get("sections", []):
                lines.append("\n--- " + sec.get("title", sec.get("section_key", "Sektion")) + " ---")
                lines.append(sec.get("draft_text", "")[:2500])
            self.report_automation_text.delete("1.0", "end")
            self.report_automation_text.insert("end", "\n".join(lines))
            self.status.set("Evidence→Report Entwurf erzeugt: " + res.get("run_id", ""))
        except Exception as exc:
            messagebox.showerror("Evidence→Report Entwurf", str(exc))

    def export_report_automation(self):
        cid = self.selected_case_id.get()
        if not cid:
            messagebox.showwarning("Evidence→Report", "Bitte zuerst einen Fall auswählen.")
            return
        try:
            res = self.ctx.report_automation.export_automated_report(
                cid,
                self.ctx.reports_dir,
                self.report_automation_type.get(),
                self.report_automation_profile.get(),
            )
            self.report_automation_text.delete("1.0", "end")
            self.report_automation_text.insert("end", "AUTOMATISIERTER REPORT EXPORT\n\n" + str(res))
            self.status.set("Evidence→Report Export erstellt: " + res.get("export_id", res.get("report_id", "")))
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Evidence→Report Export", str(exc))

    def _tab_reports(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="10 Reporting Engine Pro")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – Behörden-/Mandantenreports, Readiness-Check, Redaction und Evidence-Anlagen")
        top.pack(fill="x",padx=8,pady=8)
        self.report_type_var=tk.StringVar(value="redacted_client")
        ttk.Label(top,text="Reporttyp").pack(side="left",padx=4)
        ttk.Combobox(top,textvariable=self.report_type_var,values=["client_short","redacted_client","full_dossier","internal_analyst","evidence_annex"],width=22,state="readonly").pack(side="left",padx=4)
        ttk.Button(top,text="Readiness prüfen",command=self.check_report_readiness).pack(side="left",padx=4)
        ttk.Button(top,text="Ausgewählten Profi-Report exportieren",command=self.export_professional_report).pack(side="left",padx=4)
        ttk.Button(top,text="Report-Bundle exportieren",command=self.export_report_bundle).pack(side="left",padx=4)
        ttk.Button(top,text="Gesamtbericht exportieren",command=self.export_report).pack(side="left",padx=4)
        self.report_text=tk.Text(tab,height=25); self.report_text.pack(fill="both",expand=True,padx=8,pady=8)

    def check_report_readiness(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        try:
            result=self.ctx.reports.report_readiness(cid,self.report_type_var.get())
            self.report_text.delete("1.0","end"); self.report_text.insert("end", "Report Readiness:\n"+str(result))
            self.status.set("Report Readiness: "+result.get("status",""))
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def export_professional_report(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        outdir=filedialog.askdirectory(initialdir=str(self.ctx.reports_dir), title="Report-Zielordner wählen") or str(self.ctx.reports_dir)
        try:
            paths=self.ctx.reports.export_professional_report(cid,outdir,self.report_type_var.get())
            self.report_text.delete("1.0","end"); self.report_text.insert("end", "Profi-Report exportiert:\n"+"\n".join(f"{k}: {v}" for k,v in paths.items()))
            self.status.set("Profi-Report exportiert: "+self.report_type_var.get())
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def export_report_bundle(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        outdir=filedialog.askdirectory(initialdir=str(self.ctx.reports_dir), title="Report-Zielordner wählen") or str(self.ctx.reports_dir)
        try:
            bundle=self.ctx.reports.export_report_bundle(cid,outdir)
            lines=[]
            for name,paths in bundle.items():
                lines.append("["+name+"]")
                lines.extend(f"{k}: {v}" for k,v in paths.items())
            self.report_text.delete("1.0","end"); self.report_text.insert("end", "Report-Bundle exportiert:\n"+"\n".join(lines))
            self.status.set("Report-Bundle exportiert")
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def export_report(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        outdir=filedialog.askdirectory(initialdir=str(self.ctx.reports_dir), title="Report-Zielordner wählen") or str(self.ctx.reports_dir)
        try:
            paths=self.ctx.reports.export_case_report(cid,outdir)
            self.report_text.delete("1.0","end"); self.report_text.insert("end", "Gesamtbericht exportiert:\n"+"\n".join(f"{k}: {v}" for k,v in paths.items()))
        except Exception as e: messagebox.showerror("Fehler",str(e))

    def _tab_providers_compliance(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="11 Provider Integration Pro")
        self._case_selector(tab)
        toolbar=ttk.Frame(tab); toolbar.pack(fill="x",padx=8,pady=6)
        ttk.Button(toolbar,text="Provider/Sources Defaults laden",command=self.seed_providers).pack(side="left")
        ttk.Button(toolbar,text="Capabilities + Health Checks",command=self.run_provider_health).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Provider Job vorbereiten",command=self.create_provider_job).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Ausgewählten Provider-Link öffnen",command=self.open_selected_provider_job).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Manuelles Provider-Ergebnis importieren",command=self.import_selected_provider_result).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Provider-Ergebnisse in Review",command=self.provider_results_to_review).pack(side="left",padx=6)
        ttk.Button(toolbar,text="Export Control prüfen",command=self.check_export_control).pack(side="left",padx=6)
        form=ttk.LabelFrame(tab,text="Provider Job – öffentliche/lizenzierte Quellen, kein Login-/Captcha-/Privatbereich-Bypass")
        form.pack(fill="x",padx=8,pady=4)
        self.provider_capability=tk.StringVar(value="bing_web")
        self.provider_query=tk.StringVar(value="Maria Muster Muster Consulting GmbH")
        self.provider_purpose=tk.StringVar(value="Fallbezogene Prüfung öffentlicher Identitäts-/Berufsanker als Review-Kandidat")
        self.provider_result_title=tk.StringVar(value="Manuell geprüfter öffentlicher Provider-Treffer")
        self.provider_result_url=tk.StringVar(value="https://example.org/public-provider-result")
        self.provider_result_snippet=tk.StringVar(value="Kurznotiz zum öffentlich sichtbaren Ergebnis; wird nur als Review-Kandidat übernommen.")
        for i,(lbl,var,w) in enumerate([("Capability Key",self.provider_capability,36),("Query",self.provider_query,80),("Zweck",self.provider_purpose,120),("Result Titel",self.provider_result_title,70),("Result URL",self.provider_result_url,100),("Result Snippet",self.provider_result_snippet,120)]):
            ttk.Label(form,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=2)
            ttk.Entry(form,textvariable=var,width=w).grid(row=i,column=1,sticky="ew",padx=4,pady=2)
        form.columnconfigure(1,weight=1)
        panes=ttk.Panedwindow(tab,orient="vertical"); panes.pack(fill="both",expand=True,padx=8,pady=8)
        pf=ttk.LabelFrame(panes,text="Provider Registry / Capabilities"); jf=ttk.LabelFrame(panes,text="Provider Jobs"); rf=ttk.LabelFrame(panes,text="Provider Results / Logs / Compliance")
        panes.add(pf,weight=2); panes.add(jf,weight=2); panes.add(rf,weight=2)
        self.provider_tree=ttk.Treeview(pf,columns=("name","type","enabled","api","public","tags"),show="headings",height=8)
        for c,h,w in [("name","Provider",220),("type","Typ",150),("enabled","Aktiv",60),("api","API",60),("public","Public",70),("tags","Tags",420)]: self.provider_tree.heading(c,text=h); self.provider_tree.column(c,width=w)
        self.provider_tree.pack(fill="both",expand=True)
        self.provider_job_tree=ttk.Treeview(jf,columns=("id","provider","capability","status","query","url","results"),show="headings",height=7)
        for c,h,w in [("id","Job-ID",145),("provider","Provider",180),("capability","Capability",130),("status","Status",100),("query","Query",280),("url","URL",430),("results","Results",70)]: self.provider_job_tree.heading(c,text=h); self.provider_job_tree.column(c,width=w)
        self.provider_job_tree.pack(fill="both",expand=True)
        self.provider_result_tree=ttk.Treeview(rf,columns=("id","provider","title","url","hash","review"),show="headings",height=6)
        for c,h,w in [("id","Result-ID",145),("provider","Provider",180),("title","Titel",260),("url","URL",360),("hash","Hash",160),("review","Review-ID",145)]: self.provider_result_tree.heading(c,text=h); self.provider_result_tree.column(c,width=w)
        self.provider_result_tree.pack(fill="both",expand=True)
        self.compliance_text=tk.Text(rf,height=8); self.compliance_text.pack(fill="both",expand=True)

    def seed_providers(self):
        res=self.ctx.providers.seed_defaults()
        caps=self.ctx.provider_integration.seed_capabilities()
        self.status.set(f"Provider Registry aktualisiert: {res}; Capabilities: {caps}"); self.refresh_all()

    def run_provider_health(self):
        res=self.ctx.provider_integration.run_health_checks()
        self.status.set(f"Provider Health Checks: {res.get('providers_checked')} Provider geprüft.")
        self.refresh_all()

    def create_provider_job(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        legal=self.ctx.legal.evaluate_case(cid)
        if not legal.get("ok"):
            return messagebox.showwarning("Legal Gate", "Provider Job gesperrt bis Legal Gate PASS:\n"+"\n".join(legal.get("issues",[])))
        try:
            job=self.ctx.provider_integration.create_provider_job(cid,self.provider_capability.get().strip(),self.provider_query.get().strip(),self.provider_purpose.get().strip(),target_id=self.selected_target_id.get())
            self.status.set("Provider Job vorbereitet: "+job["job_id"])
            self.refresh_all()
        except Exception as e: messagebox.showerror("Provider Job",str(e))

    def open_selected_provider_job(self):
        sel=getattr(self,"provider_job_tree",None).selection() if hasattr(self,"provider_job_tree") else []
        if not sel: return messagebox.showinfo("Hinweis","Provider Job auswählen.")
        job_id=self.provider_job_tree.item(sel[0],"values")[0]
        try:
            job=self.ctx.provider_integration.mark_job_opened(job_id)
            webbrowser.open(job.get("request_url") or "")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Provider öffnen",str(e))

    def import_selected_provider_result(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        sel=getattr(self,"provider_job_tree",None).selection() if hasattr(self,"provider_job_tree") else []
        if not sel: return messagebox.showinfo("Hinweis","Provider Job auswählen.")
        job_id=self.provider_job_tree.item(sel[0],"values")[0]
        try:
            res=self.ctx.provider_integration.import_provider_result(cid,job_id,self.provider_result_title.get(),self.provider_result_url.get(),self.provider_result_snippet.get())
            self.status.set("Provider Ergebnis importiert: "+res["result_id"])
            self.refresh_all()
        except Exception as e: messagebox.showerror("Provider Ergebnis",str(e))

    def provider_results_to_review(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        res=self.ctx.provider_integration.create_review_items_from_results(cid)
        self.status.set(f"Provider Results → Review Inbox: {res['created_review_items']} neue Review Items.")
        self.refresh_all()

    def check_export_control(self):
        cid=self.selected_case_id.get()
        if not cid: return
        res=self.ctx.export_control.evaluate_export(cid,"client_report")
        messagebox.showinfo("Export Control", str(res))
        self.refresh_all()


    def _tab_privacy(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="3 Legal/Privacy Hardening")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – Legal Case Wizard, Interessenabwägung, DSFA/DPIA, Datenklassen, Retention")
        top.pack(fill="x",padx=8,pady=6)
        self.privacy_lawful_basis=tk.StringVar(value="Art. 6 Abs. 1 lit. f DSGVO / berechtigtes Interesse / Mandatsauftrag")
        self.privacy_interest=tk.StringVar(value="Rechtmäßige, zweckgebundene Prüfung öffentlich verfügbarer OSINT-Anker")
        self.privacy_necessity=tk.StringVar(value="Recherche ist erforderlich, weil nur öffentliche, fallzweckrelevante Informationen geprüft werden.")
        self.privacy_balancing=tk.StringVar(value="Betroffenenrisiken werden durch Datenminimierung, Review, Redaction, Exportblocker und Löschfrist begrenzt.")
        self.privacy_retention=tk.StringVar(value="2026-12-31")
        self.privacy_special=tk.BooleanVar(value=False)
        self.privacy_minor=tk.BooleanVar(value=False)
        self.privacy_criminal=tk.BooleanVar(value=False)
        for i,(lbl,var,w) in enumerate([
            ("Rechtsgrundlage",self.privacy_lawful_basis,110),
            ("Legitimes Interesse/Zweck",self.privacy_interest,120),
            ("Erforderlichkeit",self.privacy_necessity,120),
            ("Interessenabwägung",self.privacy_balancing,120),
            ("Lösch-/Reviewfrist",self.privacy_retention,40),
        ]):
            ttk.Label(top,text=lbl).grid(row=i,column=0,sticky="w",padx=4,pady=2)
            ttk.Entry(top,textvariable=var,width=w).grid(row=i,column=1,sticky="ew",padx=4,pady=2)
        top.columnconfigure(1,weight=1)
        ttk.Checkbutton(top,text="Art. 9 / besondere Kategorien möglich",variable=self.privacy_special).grid(row=5,column=1,sticky="w")
        ttk.Checkbutton(top,text="Minderjährige/Schutzinteressen möglich",variable=self.privacy_minor).grid(row=6,column=1,sticky="w")
        ttk.Checkbutton(top,text="Art. 10 / strafrechtliche Daten möglich",variable=self.privacy_criminal).grid(row=7,column=1,sticky="w")
        buttons=ttk.Frame(tab); buttons.pack(fill="x",padx=8,pady=4)
        ttk.Button(buttons,text="Legal Case Wizard speichern",command=self.run_privacy_wizard).pack(side="left",padx=4)
        ttk.Button(buttons,text="Datenklassen prüfen",command=self.classify_privacy_data).pack(side="left",padx=4)
        ttk.Button(buttons,text="DSFA/DPIA prüfen",command=self.run_dpia_check).pack(side="left",padx=4)
        ttk.Button(buttons,text="Privacy Export prüfen",command=self.check_privacy_export).pack(side="left",padx=4)
        ttk.Button(buttons,text="Retention-Dry-Run",command=self.retention_dry_run).pack(side="left",padx=4)
        self.privacy_text=tk.Text(tab,height=28)
        self.privacy_text.pack(fill="both",expand=True,padx=8,pady=8)

    def run_privacy_wizard(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        try:
            res=self.ctx.privacy.create_legal_case_wizard(
                cid,self.privacy_lawful_basis.get(),self.privacy_interest.get(),self.privacy_necessity.get(),self.privacy_balancing.get(),
                proportionality_test="GUI-Wizard: nur öffentliche/autorisierte Quellen, Kandidatenlogik, keine Umgehungstechniken.",
                data_minimization_notes="Nur fallzweckrelevante Datenklassen; Client-Export mit Redaction/Blockern.",
                retention_until=self.privacy_retention.get(),decision="approved",risk_level="medium",
                special_categories=self.privacy_special.get(),minor_data=self.privacy_minor.get(),criminal_data=self.privacy_criminal.get(),
                notes="GUI Legal Case Wizard Build 37.0")
            self.privacy_text.delete("1.0","end"); self.privacy_text.insert("end", "PRIVACY WIZARD\n"+str(res))
            self.status.set("Privacy Wizard gespeichert."); self.refresh_all()
        except Exception as e: messagebox.showerror("Privacy Wizard",str(e))

    def classify_privacy_data(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        res=self.ctx.privacy.classify_case_data(cid)
        self.privacy_text.delete("1.0","end"); self.privacy_text.insert("end", "DATENKLASSENPRÜFUNG\n"+str(res))
        self.status.set(f"Datenklassen geprüft: {res.get('created_flags')} Flags."); self.refresh_all()

    def run_dpia_check(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        res=self.ctx.privacy.run_dpia_check(cid)
        self.privacy_text.delete("1.0","end"); self.privacy_text.insert("end", "DSFA/DPIA CHECK\n"+str(res))
        self.status.set("DSFA/DPIA: "+res.get("status","")); self.refresh_all()

    def check_privacy_export(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        res=self.ctx.privacy.evaluate_privacy_export(cid,"redacted_client")
        self.privacy_text.delete("1.0","end"); self.privacy_text.insert("end", "PRIVACY EXPORT CHECK\n"+str(res))
        self.status.set("Privacy Export: "+res.get("decision","")); self.refresh_all()

    def retention_dry_run(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Hinweis","Fall auswählen.")
        job=self.ctx.privacy.create_retention_deletion_job(cid,action="review_retention",reason="GUI Retention Review",scheduled_for=self.privacy_retention.get())
        res=self.ctx.privacy.execute_retention_deletion_job(job["job_id"],dry_run=True)
        self.privacy_text.delete("1.0","end"); self.privacy_text.insert("end", "RETENTION DRY RUN\n"+str(res))
        self.status.set("Retention-Dry-Run abgeschlossen."); self.refresh_all()



    def _tab_team(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="13 Team/Mandanten")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 – Mandantenfähigkeit, Fallrechte, Vier-Augen-Prinzip und Freigabehistorie")
        top.pack(fill="x",padx=8,pady=8)
        ttk.Button(top,text="Demo-Mandant + Team anlegen",command=self.team_create_demo).grid(row=0,column=0,padx=4,pady=4)
        ttk.Button(top,text="Freigabeanfrage erstellen",command=self.team_request_approval).grid(row=0,column=1,padx=4,pady=4)
        ttk.Button(top,text="Als Legal Reviewer genehmigen",command=self.team_approve_latest).grid(row=0,column=2,padx=4,pady=4)
        ttk.Button(top,text="Team-Kommentar",command=self.team_add_comment).grid(row=0,column=3,padx=4,pady=4)
        ttk.Button(top,text="Aktualisieren",command=self.refresh_all).grid(row=0,column=4,padx=4,pady=4)
        paned=ttk.Panedwindow(tab,orient="horizontal"); paned.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(paned); right=ttk.Frame(paned)
        paned.add(left,weight=2); paned.add(right,weight=3)
        self.team_access_tree=ttk.Treeview(left,columns=("user","role","org","permissions"),show="headings",height=12)
        for c,h,w in [("user","Nutzer",150),("role","Rolle",130),("org","Organisation",120),("permissions","Berechtigungen",420)]: self.team_access_tree.heading(c,text=h); self.team_access_tree.column(c,width=w)
        ttk.Label(left,text="Fallzugriffe").pack(anchor="w",padx=4)
        self.team_access_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.team_approval_tree=ttk.Treeview(left,columns=("id","type","status","requested_by","title"),show="headings",height=12)
        for c,h,w in [("id","ID",150),("type","Typ",120),("status","Status",120),("requested_by","Antragsteller",120),("title","Titel",280)]: self.team_approval_tree.heading(c,text=h); self.team_approval_tree.column(c,width=w)
        ttk.Label(left,text="Freigaben / Vier-Augen-Prinzip").pack(anchor="w",padx=4)
        self.team_approval_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.team_text=tk.Text(right,height=28,wrap="word")
        self.team_text.pack(fill="both",expand=True,padx=4,pady=4)

    def team_create_demo(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Team","Bitte zuerst Fall auswählen.")
        try:
            client=self.ctx.team.create_client("Demo Mandant", client_type="demo", contact="demo@example.org", notes="GUI Demo Build 31")
            self.ctx.team.assign_case_to_client(cid, client["client_id"], notes="GUI Mandantenzuordnung Build 31")
            analyst=self.ctx.team.create_member("gui-analyst", "GUI Senior Analyst", role_key="senior_analyst", notes="GUI Teammitglied Build 31")
            legal=self.ctx.team.create_member("gui-legal", "GUI Legal Reviewer", role_key="legal_reviewer", notes="GUI Legal Reviewer Build 31")
            self.ctx.team.grant_case_access(cid, analyst["member_id"], "senior_analyst", granted_by="gui-admin")
            self.ctx.team.grant_case_access(cid, legal["member_id"], "legal_reviewer", granted_by="gui-admin")
            self.status.set("Mandant und Team für Fall angelegt."); self.refresh_all()
        except Exception as e:
            messagebox.showerror("Team",str(e))

    def team_request_approval(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Team","Bitte zuerst Fall auswählen.")
        try:
            req=self.ctx.team.request_approval(cid,"case_export_release","case",cid,"Export-/Berichtsfreigabe","GUI-Freigabeanfrage nach Vier-Augen-Prinzip.",requested_by="gui-analyst",required_role="legal_reviewer",min_approvals=1)
            self.status.set("Freigabeanfrage erstellt: "+req["request_id"]); self.refresh_all()
        except Exception as e:
            messagebox.showerror("Team",str(e))

    def team_approve_latest(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Team","Bitte zuerst Fall auswählen.")
        try:
            pending=self.ctx.team.list_approval_requests(cid,"pending") or self.ctx.team.list_approval_requests(cid,"needs_changes")
            if not pending: return messagebox.showinfo("Team","Keine offene Freigabeanfrage gefunden.")
            dec=self.ctx.team.record_approval_decision(pending[0]["request_id"],"approved","gui-legal","legal_reviewer","GUI-Freigabe Build 31")
            self.status.set("Freigabeentscheidung gespeichert: "+dec["decision_id"]); self.refresh_all()
        except Exception as e:
            messagebox.showerror("Team",str(e))

    def team_add_comment(self):
        cid=self.selected_case_id.get()
        if not cid: return messagebox.showwarning("Team","Bitte zuerst Fall auswählen.")
        try:
            comment=self.ctx.team.add_comment(cid,"case",cid,"gui-analyst","GUI-Kommentar: nächster Review-/Freigabeschritt dokumentiert.")
            self.status.set("Team-Kommentar gespeichert: "+comment["comment_id"]); self.refresh_all()
        except Exception as e:
            messagebox.showerror("Team",str(e))

    def _tab_security(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="12 Security")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 37.0 Release Candidate – lokale Zugriffskontrolle, Secrets-Referenzen, Integrity, Backup, Audit-Chain")
        top.pack(fill="x",padx=8,pady=6)
        ttk.Button(top,text="Security Defaults prüfen/setzen",command=self.security_seed_defaults).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="QA-Admin lokal anlegen",command=self.security_create_qa_admin).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Secret-Refs validieren",command=self.security_validate_secrets).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Integrity Baseline erstellen/prüfen",command=self.security_integrity_baseline).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Audit-Chain härten/prüfen",command=self.security_audit_chain).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Backup-Bundle erzeugen",command=self.security_backup).pack(side="left",padx=4,pady=4)
        self.security_env=tk.StringVar(value="EAGLEEYE_BING_API_KEY")
        envf=ttk.Frame(tab); envf.pack(fill="x",padx=8,pady=4)
        ttk.Label(envf,text="Env-Var Secret Reference:").pack(side="left")
        ttk.Entry(envf,textvariable=self.security_env,width=36).pack(side="left",padx=4)
        ttk.Button(envf,text="Secret-Reference anlegen",command=self.security_add_secret_ref).pack(side="left",padx=4)
        self.security_text=tk.Text(tab,height=30)
        self.security_text.pack(fill="both",expand=True,padx=8,pady=8)

    def _security_print(self, title, data):
        if hasattr(self,"security_text"):
            self.security_text.delete("1.0","end")
            self.security_text.insert("end", title+"\n"+str(data))

    def security_seed_defaults(self):
        res=self.ctx.security_hardening.seed_security_defaults()
        self._security_print("SECURITY DEFAULTS",res); self.status.set("Security Defaults geprüft."); self.refresh_all()

    def security_create_qa_admin(self):
        try:
            user=self.ctx.security_hardening.create_local_user("local-admin","Lokaler Administrator","ChangeMe-Build24!",role="admin",notes="Bitte Passwort nach Erststart ändern; Demo-/Local-Account.")
            self._security_print("LOCAL USER", {k:user[k] for k in user if k not in {"password_hash","password_salt"}})
            self.status.set("Lokaler Admin angelegt/vorhanden."); self.refresh_all()
        except Exception as e: messagebox.showerror("Security",str(e))

    def security_add_secret_ref(self):
        try:
            ref=self.ctx.security_hardening.create_secret_reference("GUI Provider Secret", self.security_env.get(), "API-Key nur über Umgebungsvariable referenzieren, kein Klartext im Tool.")
            self._security_print("SECRET REFERENCE",ref); self.status.set("Secret-Reference angelegt."); self.refresh_all()
        except Exception as e: messagebox.showerror("Security",str(e))

    def security_validate_secrets(self):
        res=self.ctx.security_hardening.validate_secret_references()
        self._security_print("SECRET VALIDATION",res); self.status.set("Secret-Refs validiert."); self.refresh_all()

    def security_integrity_baseline(self):
        try:
            root=Path(__file__).resolve().parents[2]
            base=self.ctx.security_hardening.create_integrity_baseline(root,label="GUI Build 31 Integrity Baseline",notes="Baseline über Programmdateien ohne data/reports.")
            check=self.ctx.security_hardening.verify_integrity_baseline(base["baseline_id"])
            self._security_print("INTEGRITY BASELINE + CHECK",{"baseline":base,"check":check})
            self.status.set("Integrity Baseline geprüft: "+check.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Security",str(e))

    def security_audit_chain(self):
        chain=self.ctx.security_hardening.harden_audit_chain()
        verify=self.ctx.security_hardening.verify_audit_chain()
        self._security_print("AUDIT CHAIN",{"chain":chain,"verify":verify})
        self.status.set("Audit-Chain: "+("OK" if verify.get("ok") else "prüfen")); self.refresh_all()

    def security_backup(self):
        try:
            base=self.ctx.base_dir
            res=self.ctx.security_hardening.create_backup_bundle(base, base/"backups", notes="GUI Backup Build 31")
            self._security_print("BACKUP BUNDLE",res); self.status.set("Backup-Bundle erzeugt."); self.refresh_all()
        except Exception as e: messagebox.showerror("Backup",str(e))


    def _tab_packaging(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="14 Packaging")
        top=ttk.LabelFrame(tab,text="Build 37.0 – Enterprise Packaging / Installation / Migration / Rollback")
        top.pack(fill="x",padx=8,pady=8)
        ttk.Button(top,text="Dashboard aktualisieren",command=self.packaging_refresh).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Migration 28→29 planen",command=self.packaging_create_migration).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Migration-Readiness prüfen",command=self.packaging_migration_readiness).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Rollbackpunkt erzeugen",command=self.packaging_create_rollback).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Release-Manifest berechnen",command=self.packaging_manifest).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Portable Bundle erzeugen",command=self.packaging_portable_bundle).pack(side="left",padx=4,pady=4)

        split=ttk.Panedwindow(tab,orient="horizontal"); split.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(split); right=ttk.Frame(split)
        split.add(left,weight=2); split.add(right,weight=3)
        self.packaging_profile_tree=ttk.Treeview(left,columns=("profile","target","runtime","admin","title"),show="headings",height=10)
        for c,h,w in [("profile","Profil",170),("target","Ziel",160),("runtime","Runtime",80),("admin","Admin",70),("title","Titel",320)]:
            self.packaging_profile_tree.heading(c,text=h); self.packaging_profile_tree.column(c,width=w)
        self.packaging_profile_tree.pack(fill="x",padx=4,pady=4)
        self.packaging_artifact_tree=ttk.Treeview(left,columns=("created","type","profile","status","hash","path"),show="headings",height=14)
        for c,h,w in [("created","Zeit",150),("type","Typ",140),("profile","Profil",130),("status","Status",100),("hash","SHA-256",150),("path","Pfad",420)]:
            self.packaging_artifact_tree.heading(c,text=h); self.packaging_artifact_tree.column(c,width=w)
        self.packaging_artifact_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.packaging_text=tk.Text(right,height=32,wrap="word")
        self.packaging_text.pack(fill="both",expand=True,padx=4,pady=4)

    def _packaging_print(self,title,data):
        if hasattr(self,"packaging_text"):
            import json
            self.packaging_text.delete("1.0","end")
            self.packaging_text.insert("end", title+"\n"+json.dumps(data,ensure_ascii=False,indent=2,default=str))

    def packaging_refresh(self):
        try:
            dash=self.ctx.packaging.dashboard()
            if hasattr(self,"packaging_profile_tree"):
                self.packaging_profile_tree.delete(*self.packaging_profile_tree.get_children())
                for p in dash.get("profiles",[]):
                    self.packaging_profile_tree.insert("","end",values=(p.get("profile_key"),p.get("target"),p.get("includes_runtime_data",0),p.get("requires_admin",0),p.get("title")))
            if hasattr(self,"packaging_artifact_tree"):
                self.packaging_artifact_tree.delete(*self.packaging_artifact_tree.get_children())
                for a in dash.get("latest_artifacts",[]):
                    self.packaging_artifact_tree.insert("","end",values=(a.get("created_at"),a.get("artifact_type"),a.get("profile_key"),a.get("status"),(a.get("sha256") or "")[:16]+"...",a.get("path")))
            self._packaging_print("PACKAGING DASHBOARD",dash)
            self.status.set("Packaging Dashboard aktualisiert: "+dash.get("status",""))
        except Exception as e:
            messagebox.showerror("Packaging",str(e))

    def packaging_create_migration(self):
        try:
            plan=self.ctx.packaging.create_migration_plan("28.0","37.0",notes="GUI: Migration von Build 28.0 auf Build 37.0 vorbereitet.")
            self._packaging_print("MIGRATION PLAN",plan); self.status.set("Migration geplant: "+plan.get("migration_id","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Migration",str(e))

    def packaging_migration_readiness(self):
        try:
            res=self.ctx.packaging.run_migration_readiness(self.ctx.base_dir,"28.0","37.0")
            self._packaging_print("MIGRATION READINESS",res); self.status.set("Migration Readiness: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Migration",str(e))

    def packaging_create_rollback(self):
        try:
            rb=self.ctx.packaging.create_rollback_point(self.ctx.base_dir,label="GUI Rollbackpunkt",notes="Vor Update/Migration manuell über Packaging-Tab erzeugt.")
            self._packaging_print("ROLLBACK POINT",rb); self.status.set("Rollbackpunkt erzeugt: "+rb.get("rollback_id","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Rollback",str(e))

    def packaging_manifest(self):
        try:
            mf=self.ctx.packaging.build_distribution_manifest(self.ctx.base_dir,"portable_local")
            self._packaging_print("RELEASE MANIFEST",{"file_count":mf.get("file_count"),"total_bytes":mf.get("total_bytes"),"manifest_hash":mf.get("manifest_hash"),"guardrails":mf.get("guardrails")}); self.status.set("Release-Manifest berechnet.")
        except Exception as e: messagebox.showerror("Manifest",str(e))

    def packaging_portable_bundle(self):
        try:
            res=self.ctx.packaging.create_portable_bundle(self.ctx.base_dir,self.ctx.base_dir/"dist",notes="GUI Portable Bundle Build 31")
            self._packaging_print("PORTABLE BUNDLE",res); self.status.set("Portable Bundle erzeugt."); self.refresh_all()
        except Exception as e: messagebox.showerror("Portable Bundle",str(e))

    def _tab_release_candidate(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="15 Release Candidate")
        top=ttk.LabelFrame(tab,text="Build 37.0 – Release Candidate / Stabilisierung / QA / Standbewertung")
        top.pack(fill="x",padx=8,pady=8)
        ttk.Button(top,text="Dashboard aktualisieren",command=self.rc_refresh).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="RC-Audit ausführen",command=self.rc_run_audit).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Core-Gates bestehen",command=self.rc_mark_gates).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Release-Freeze erzeugen",command=self.rc_create_freeze).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Stand bewerten",command=self.rc_assess).pack(side="left",padx=4,pady=4)

        split=ttk.Panedwindow(tab,orient="horizontal"); split.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(split); right=ttk.Frame(split)
        split.add(left,weight=2); split.add(right,weight=3)
        self.rc_gate_tree=ttk.Treeview(left,columns=("key","severity","status","title"),show="headings",height=12)
        for c,h,w in [("key","Gate",170),("severity","Schwere",90),("status","Status",100),("title","Titel",360)]:
            self.rc_gate_tree.heading(c,text=h); self.rc_gate_tree.column(c,width=w)
        self.rc_gate_tree.pack(fill="x",padx=4,pady=4)
        self.rc_qa_tree=ttk.Treeview(left,columns=("key","severity","title","command"),show="headings",height=12)
        for c,h,w in [("key","Check",160),("severity","Schwere",90),("title","Titel",280),("command","Hinweis",360)]:
            self.rc_qa_tree.heading(c,text=h); self.rc_qa_tree.column(c,width=w)
        self.rc_qa_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.rc_text=tk.Text(right,height=36,wrap="word")
        self.rc_text.pack(fill="both",expand=True,padx=4,pady=4)

    def _rc_print(self,title,data):
        if hasattr(self,"rc_text"):
            import json
            self.rc_text.delete("1.0","end")
            self.rc_text.insert("end", title+"\n"+json.dumps(data,ensure_ascii=False,indent=2,default=str))

    def rc_refresh(self):
        try:
            dash=self.ctx.release_candidate.dashboard()
            if hasattr(self,"rc_gate_tree"):
                self.rc_gate_tree.delete(*self.rc_gate_tree.get_children())
                for g in dash.get("acceptance_gates",[]):
                    self.rc_gate_tree.insert("","end",values=(g.get("gate_key"),g.get("severity"),g.get("status"),g.get("title")))
            if hasattr(self,"rc_qa_tree"):
                self.rc_qa_tree.delete(*self.rc_qa_tree.get_children())
                for q in dash.get("qa_matrix",[]):
                    self.rc_qa_tree.insert("","end",values=(q.get("check_key"),q.get("severity"),q.get("title"),q.get("command_hint")))
            self._rc_print("RELEASE CANDIDATE DASHBOARD",dash)
            self.status.set("Release Candidate Dashboard: "+dash.get("status",""))
        except Exception as e:
            messagebox.showerror("Release Candidate",str(e))

    def rc_run_audit(self):
        try:
            res=self.ctx.release_candidate.run_release_candidate_audit(self.ctx.base_dir)
            self._rc_print("RELEASE CANDIDATE AUDIT",res); self.status.set("RC-Audit: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("RC-Audit",str(e))

    def rc_mark_gates(self):
        try:
            res=self.ctx.release_candidate.mark_core_gates_from_current_state(self.selected_case_id.get() or None)
            self._rc_print("ACCEPTANCE GATES",res); self.status.set("Acceptance Gates aktualisiert."); self.refresh_all()
        except Exception as e: messagebox.showerror("Acceptance Gates",str(e))

    def rc_create_freeze(self):
        try:
            mf=self.ctx.packaging.build_distribution_manifest(self.ctx.base_dir,"portable_local")
            res=self.ctx.release_candidate.create_release_freeze(self.ctx.base_dir,manifest_hash=mf.get("manifest_hash",""),notes="GUI Release-Freeze Build 31")
            self._rc_print("RELEASE FREEZE",res); self.status.set("Release Freeze erzeugt."); self.refresh_all()
        except Exception as e: messagebox.showerror("Release Freeze",str(e))

    def rc_assess(self):
        try:
            res=self.ctx.release_candidate.product_readiness_assessment()
            self._rc_print("STANDBEWERTUNG",res); self.status.set(f"Standbewertung: {res.get('overall_score')} %"); self.refresh_all()
        except Exception as e: messagebox.showerror("Standbewertung",str(e))



    def _tab_performance_security(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="16 Performance/Security")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab,text="Build 40.0 – Performance & Security Release")
        top.pack(fill="x",padx=8,pady=8)
        ttk.Button(top,text="Dashboard",command=self.performance_security_refresh).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Performance Probe",command=self.performance_security_probe).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Security Regression",command=self.performance_security_regression).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Provider Failure Test",command=self.performance_security_provider_test).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Backup/Restore Dry-Run",command=self.performance_security_backup_test).pack(side="left",padx=4,pady=4)
        ttk.Button(top,text="Full Hardening Suite",command=self.performance_security_full_suite).pack(side="left",padx=4,pady=4)
        split=ttk.Panedwindow(tab,orient="horizontal"); split.pack(fill="both",expand=True,padx=8,pady=6)
        left=ttk.Frame(split); right=ttk.Frame(split); split.add(left,weight=2); split.add(right,weight=3)
        self.performance_security_runs_tree=ttk.Treeview(left,columns=("created","type","status","score","duration"),show="headings",height=18)
        for c,h,w in [("created","Zeit",150),("type","Typ",190),("status","Status",90),("score","Score",80),("duration","ms",80)]:
            self.performance_security_runs_tree.heading(c,text=h); self.performance_security_runs_tree.column(c,width=w)
        self.performance_security_runs_tree.pack(fill="both",expand=True,padx=4,pady=4)
        self.performance_security_text=tk.Text(right,height=32,wrap="word")
        self.performance_security_text.pack(fill="both",expand=True,padx=4,pady=4)

    def _performance_security_print(self,title,data):
        if hasattr(self,"performance_security_text"):
            import json
            self.performance_security_text.delete("1.0","end")
            self.performance_security_text.insert("end", title+"\n"+json.dumps(data,ensure_ascii=False,indent=2,default=str))

    def performance_security_refresh(self):
        try:
            cid=self.selected_case_id.get()
            dash=self.ctx.performance_security.dashboard(cid)
            if hasattr(self,"performance_security_runs_tree"):
                self.performance_security_runs_tree.delete(*self.performance_security_runs_tree.get_children())
                for r in dash.get("latest_runs",[]):
                    self.performance_security_runs_tree.insert("","end",values=(r.get("created_at"),r.get("run_type"),r.get("status"),r.get("score"),r.get("duration_ms")))
            self._performance_security_print("PERFORMANCE / SECURITY DASHBOARD",dash)
            self.status.set("Performance/Security Dashboard: "+dash.get("status",""))
        except Exception as e:
            messagebox.showerror("Performance/Security",str(e))

    def performance_security_probe(self):
        try:
            res=self.ctx.performance_security.performance_probe(self.ctx.base_dir,self.selected_case_id.get())
            self._performance_security_print("PERFORMANCE PROBE",res); self.status.set("Performance Probe: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Performance Probe",str(e))

    def performance_security_regression(self):
        try:
            res=self.ctx.performance_security.security_regression()
            self._performance_security_print("SECURITY REGRESSION",res); self.status.set("Security Regression: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Security Regression",str(e))

    def performance_security_provider_test(self):
        try:
            res=self.ctx.performance_security.provider_failure_simulation()
            self._performance_security_print("PROVIDER FAILURE TEST",res); self.status.set("Provider Failure Test: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Provider Failure",str(e))

    def performance_security_backup_test(self):
        try:
            res=self.ctx.performance_security.backup_restore_dry_run(self.ctx.base_dir)
            self._performance_security_print("BACKUP/RESTORE DRY-RUN",res); self.status.set("Backup/Restore Dry-Run: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Backup/Restore",str(e))

    def performance_security_full_suite(self):
        try:
            res=self.ctx.performance_security.full_hardening_suite(self.ctx.base_dir,self.selected_case_id.get())
            self._performance_security_print("FULL HARDENING SUITE",res); self.status.set("Full Hardening Suite: "+res.get("status","")); self.refresh_all()
        except Exception as e: messagebox.showerror("Full Hardening",str(e))

    def _tab_review_fast_lane(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab, text="3b Review Fast Lane")
        self._case_selector(tab)
        top=ttk.LabelFrame(tab, text="Build 37.0 – schnelle Review-Entscheidungen ohne Evidenz-Abkürzung")
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Lane:").pack(side="left", padx=4)
        ttk.Combobox(top, textvariable=self.review_fast_lane_lane, width=22, state="readonly", values=["new","ready","duplicates","sensitive","doppler","all"]).pack(side="left", padx=4)
        ttk.Button(top, text="Fast Lane aktualisieren", command=self.refresh_review_fast_lane).pack(side="left", padx=4)
        ttk.Button(top, text="Duplikate/Namensdoppler scannen", command=self.review_fast_lane_scan).pack(side="left", padx=4)
        ttk.Button(top, text="Bulk-Triage", command=self.review_fast_lane_bulk_triage).pack(side="left", padx=4)
        ttk.Button(top, text="Ready → Evidence", command=self.review_fast_lane_promote_ready).pack(side="left", padx=4)
        cfg=ttk.LabelFrame(tab, text="Pflichtnotiz / Analystenvermerk"); cfg.pack(fill="x", padx=8, pady=4)
        ttk.Entry(cfg, textvariable=self.review_fast_lane_note, width=120).pack(fill="x", padx=4, pady=4)
        panes=ttk.Panedwindow(tab, orient="horizontal"); panes.pack(fill="both", expand=True, padx=8, pady=6)
        left=ttk.Frame(panes); right=ttk.Frame(panes); panes.add(left, weight=3); panes.add(right, weight=2)
        qbox=ttk.LabelFrame(left, text="Fast-Lane Queue – R/D/N/S/L/C/A/E"); qbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.review_fast_lane_tree=ttk.Treeview(qbox, columns=("id","status","quality","score","sens","title","url"), show="headings", height=22)
        for c,h,w in [("id","ID",145),("status","Status",125),("quality","Q",55),("score","Score",55),("sens","Sens",70),("title","Titel",320),("url","URL",380)]:
            self.review_fast_lane_tree.heading(c,text=h); self.review_fast_lane_tree.column(c,width=w)
        self.review_fast_lane_tree.pack(fill="both", expand=True, padx=4, pady=4)
        btns=ttk.Frame(qbox); btns.pack(fill="x", padx=4, pady=4)
        for key,label in [("R","Relevant"),("D","Duplikat"),("N","Namensdoppler"),("S","Sensibel"),("L","Quellenprüfung"),("C","Gegenbeleg"),("A","Ablehnen"),("E","Evidence")]:
            ttk.Button(btns, text=f"{key} {label}", command=lambda k=key: self.review_fast_lane_decide(k)).pack(side="left", padx=2)
        dbox=ttk.LabelFrame(right, text="Dashboard / Flags / Guardrails"); dbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.review_fast_lane_text=tk.Text(dbox, height=32, wrap="word"); self.review_fast_lane_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _selected_review_fast_lane_item_ids(self):
        if not hasattr(self, "review_fast_lane_tree"): return []
        ids=[]
        for sel in self.review_fast_lane_tree.selection():
            vals=self.review_fast_lane_tree.item(sel, "values")
            if vals: ids.append(vals[0])
        return ids

    def refresh_review_fast_lane(self):
        cid=self.selected_case_id.get()
        if not cid: return
        try:
            dash=self.ctx.review_fast_lane.dashboard(cid); lane=self.review_fast_lane_lane.get() or "new"
            rows=self.ctx.review_fast_lane.queue(cid, lane_key=lane, limit=200)
            if hasattr(self, "review_fast_lane_tree"):
                self.review_fast_lane_tree.delete(*self.review_fast_lane_tree.get_children())
                for r in rows: self.review_fast_lane_tree.insert("", "end", values=(r.get("item_id"), r.get("status"), r.get("quality_score"), r.get("score"), r.get("sensitivity_level"), r.get("title"), r.get("url")))
            if hasattr(self, "review_fast_lane_text"):
                lines=["REVIEW FAST LANE", f"Status: {dash.get('status')}", f"Nächster Schritt: {dash.get('next_action')}", "", "METRIKEN", str(dash.get('metrics')), "", "SHORTCUTS"]
                for sh in dash.get("shortcuts", []): lines.append(f"{sh.get('shortcut_key')}: {sh.get('label')} → {sh.get('status')} | Note={sh.get('requires_note')}")
                lines.append("\nNAMENSDOPPLER-/GEGENBELEG-FLAGS")
                for f in dash.get("doppler_flags", [])[:20]: lines.append(f"- {f.get('item_id')} | {f.get('reason')} | {f.get('title')}")
                lines.append("\nSECURITY"); lines.append(str(self.ctx.review_fast_lane.security_checks(cid)))
                self.review_fast_lane_text.delete("1.0","end"); self.review_fast_lane_text.insert("end", "\n".join(lines))
        except Exception as e: messagebox.showerror("Review Fast Lane", str(e))

    def review_fast_lane_decide(self, action_key):
        ids=self._selected_review_fast_lane_item_ids()
        if not ids: messagebox.showwarning("Review Fast Lane", "Bitte mindestens einen Treffer auswählen."); return
        try:
            note=self.review_fast_lane_note.get().strip()
            if len(ids)==1: res=self.ctx.review_fast_lane.decide_item(ids[0], action_key, analyst_note=note); self.status.set(f"Fast-Lane: {action_key} → {res.get('new_status')}")
            else: res=self.ctx.review_fast_lane.bulk_decide(self.selected_case_id.get(), ids, action_key, analyst_note=note); self.status.set(f"Bulk-Fast-Lane: {res.get('affected_count')} betroffen, {res.get('blocked_count')} blockiert")
            self.refresh_all()
        except Exception as e: messagebox.showerror("Review Fast Lane", str(e))

    def review_fast_lane_scan(self):
        cid=self.selected_case_id.get()
        try:
            dup=self.ctx.review.find_duplicates(cid); dop=self.ctx.review_fast_lane.name_doppler_scan(cid)
            self.status.set(f"Review Scan: Duplikatcluster={dup.get('cluster_count')} | Doppler-Flags neu={dop.get('created')}"); self.refresh_review_fast_lane()
        except Exception as e: messagebox.showerror("Review Scan", str(e))

    def review_fast_lane_bulk_triage(self):
        try:
            res=self.ctx.review.bulk_triage(self.selected_case_id.get()); self.status.set(f"Bulk-Triage: {res.get('triaged')} Treffer geprüft"); self.refresh_all()
        except Exception as e: messagebox.showerror("Bulk-Triage", str(e))

    def review_fast_lane_promote_ready(self):
        try:
            res=self.ctx.review_fast_lane.promote_ready_to_evidence(self.selected_case_id.get(), analyst_note=self.review_fast_lane_note.get().strip(), evidence_category="Identitätsanker")
            self.status.set(f"Ready → Evidence: {res.get('promoted_count')} hochgestuft, {res.get('blocked_count')} blockiert"); self.refresh_all()
        except Exception as e: messagebox.showerror("Ready → Evidence", str(e))

    def _tab_audit(self):
        tab=ttk.Frame(self.nb); self.nb.add(tab,text="16 Audit")
        self._case_selector(tab)
        self.audit_tree=ttk.Treeview(tab,columns=("ts","actor","action","otype","oid","details"),show="headings",height=28)
        for c,h,w in [("ts","Zeit",160),("actor","Akteur",120),("action","Aktion",120),("otype","Objekt",130),("oid","ID",150),("details","Details",500)]: self.audit_tree.heading(c,text=h); self.audit_tree.column(c,width=w)
        self.audit_tree.pack(fill="both",expand=True,padx=8,pady=8)

    def refresh_all(self):
        self._refresh_workflow_185()
        cases=self.ctx.cases.list_cases()
        values=[c["case_id"] for c in cases]
        try:
            for combo in getattr(self, "case_combos", []):
                combo["values"] = values
        except Exception:
            pass
        if not self.selected_case_id.get() and cases: self.selected_case_id.set(cases[0]["case_id"])
        if hasattr(self,"cases_tree"):
            self.cases_tree.delete(*self.cases_tree.get_children())
            for c in cases: self.cases_tree.insert("", "end", values=(c["case_id"],c["title"],c.get("client",""),c.get("status",""),c.get("risk_level","")))
        cid=self.selected_case_id.get()
        if not cid: return
        if hasattr(self,"cockpit_text"):
            try:
                self.refresh_cockpit()
            except Exception:
                pass
        if hasattr(self,"target_tree"):
            self.target_tree.delete(*self.target_tree.get_children())
            for t in self.ctx.targets.list_targets(cid): self.target_tree.insert("","end",values=(t["target_id"],t["name"],", ".join(t["aliases_json"]),", ".join(t["usernames_json"]),", ".join(t["locations_json"]),", ".join(t["companies_json"])))

        if hasattr(self,"playbook_step_tree"):
            try:
                dash=self.ctx.playbooks.dashboard(cid)
                self.playbook_step_tree.delete(*self.playbook_step_tree.get_children())
                for a in dash.get("assignments",[]):
                    detail=self.ctx.playbooks.assignment_detail(a["assignment_id"])
                    for st in detail.get("steps",[]):
                        self.playbook_step_tree.insert("","end",values=(st.get("case_step_id"),a.get("assignment_id"),st.get("phase_order"),st.get("status"),st.get("required_gate"),st.get("title"),st.get("objective")))
                self.playbook_gate_tree.delete(*self.playbook_gate_tree.get_children())
                for g in dash.get("open_quality_gates",[]):
                    self.playbook_gate_tree.insert("","end",values=("quality_gate",g.get("gate_id"),g.get("status"),g.get("severity"),g.get("gate_name"),g.get("notes","")))
                for d in dash.get("deliverables",[])[:30]:
                    self.playbook_gate_tree.insert("","end",values=("deliverable",d.get("deliverable_id"),d.get("status"),"review" if d.get("required_review") else "normal",d.get("deliverable_type"),d.get("notes","")))
                for sp in dash.get("source_plans",[])[:30]:
                    self.playbook_gate_tree.insert("","end",values=("source",sp.get("plan_id"),sp.get("status"),sp.get("risk_level"),sp.get("source_name"),sp.get("allowed_use")))
                out="PLAYBOOK DASHBOARD\n"+str(dash.get("status"))+"\n\nCOUNTS\n"+str(dash.get("counts"))+"\n\nNÄCHSTE SCHRITTE\n"+"\n".join(f"{s.get('phase_order')}. {s.get('status')} | {s.get('title')} | Gate={s.get('required_gate')}" for s in dash.get("next_steps",[]))
                self.playbook_text.delete("1.0","end"); self.playbook_text.insert("end",out)
            except Exception as exc:
                self.playbook_text.delete("1.0","end"); self.playbook_text.insert("end","Playbook Dashboard Fehler: "+str(exc))
        if hasattr(self,"ux_nav_text"):
            try:
                self.refresh_ux_navigator()
            except Exception:
                pass
        if hasattr(self,"guided_phase_tree"):
            try:
                dash = self.ctx.guided_research.start_or_refresh_run(cid, target_id=self.selected_target_id.get())
                self._render_guided_dashboard(dash)
            except Exception as exc:
                if hasattr(self,"guided_text"):
                    self.guided_text.delete("1.0","end"); self.guided_text.insert("end","Guided Research Fehler: "+str(exc))
        if hasattr(self,"research_exec_phase_tree"):
            try:
                self.refresh_research_execution()
            except Exception:
                pass
        if hasattr(self,"source_pack_tree"):
            try:
                self.refresh_source_packs()
            except Exception:
                pass
        if hasattr(self,"real_provider_tree"):
            try:
                self.refresh_real_providers()
            except Exception:
                pass
        if hasattr(self,"query_intelligence_tree"):
            try:
                self.refresh_query_intelligence()
            except Exception:
                pass
        if hasattr(self,"verification_assessment_tree"):
            try:
                self.refresh_verification()
            except Exception:
                pass
        if hasattr(self,"capture_inbox_tree"):
            try:
                self.refresh_capture_inbox()
            except Exception:
                pass
        if hasattr(self,"review_fast_lane_tree"):
            try:
                self.refresh_review_fast_lane()
            except Exception:
                pass
        if hasattr(self,"search_bundle_combo"):
            try:
                self.search_bundle_combo["values"] = self.ctx.ux_consolidation.bundle_options()
            except Exception:
                pass
        if hasattr(self,"multi_search_preset_combo"):
            try:
                self.multi_search_preset_combo["values"] = self.ctx.search_workbench.multi_search_preset_options()
            except Exception:
                pass
        if hasattr(self,"package_tree"):
            self.package_tree.delete(*self.package_tree.get_children())
            for p in self.ctx.search_workbench.list_packages(cid): self.package_tree.insert("","end",values=(p["package_id"],p["package_key"],p["name"],p.get("task_count",0),p["status"],p["objective"]))
        if hasattr(self,"search_tree"):
            self.search_tree.delete(*self.search_tree.get_children())
            pkg = self.selected_package_id.get() if hasattr(self,"selected_package_id") else ""
            tasks = self.ctx.search_workbench.list_tasks(cid, pkg)
            bundle_key = self._current_search_bundle_key() if hasattr(self,"_current_search_bundle_key") else ""
            tasks = self.ctx.ux_consolidation.filter_tasks_by_bundle(tasks, bundle_key)
            for t in tasks: self.search_tree.insert("","end",values=(t["task_id"],t.get("package_name",""),t.get("status",""),t["category"],t["engine"],t["query"],t["url"]))
        if hasattr(self,"multi_search_tree"):
            self.multi_search_tree.delete(*self.multi_search_tree.get_children())
            for m in self.ctx.search_workbench.list_multi_search_launches(cid):
                self.multi_search_tree.insert("","end",values=(m["launch_id"],m["created_at"],m.get("preset_key",""),", ".join(m.get("engines") or []),m.get("url_count",0),m.get("query",""),m.get("status","")))
        if hasattr(self,"capture_tree"):
            self.capture_tree.delete(*self.capture_tree.get_children())
            for cap in self.ctx.search_workbench.list_captures(cid): self.capture_tree.insert("","end",values=(cap["capture_id"],cap["captured_at"],cap["title"],cap.get("host",""),cap["content_hash"][:16]+"...",cap.get("review_item_id") or "",cap.get("chain_status") or ""))
        if hasattr(self,"review_tree"):
            self.review_tree.delete(*self.review_tree.get_children())
            for r in self.ctx.review.list_items(cid): self.review_tree.insert("","end",values=(r["item_id"],r["status"],r.get("score",0),r.get("quality_score",0),r.get("sensitivity_level",""),r["title"],r.get("url") or "",r.get("triage_reason") or ""))
        if hasattr(self,"evidence_tree"):
            self.evidence_tree.delete(*self.evidence_tree.get_children())
            for ev in self.ctx.evidence.list_evidence(cid): self.evidence_tree.insert("","end",values=(ev["evidence_id"],ev["category"],ev["confidence"],ev.get("review_decision",""),ev.get("reliability_score",0),bool(ev["export_allowed"]),bool(ev["redaction_required"]),ev["title"],ev["content_hash"]))
        if hasattr(self,"workflow_tree"):
            self.workflow_tree.delete(*self.workflow_tree.get_children())
            for w in self.ctx.workflow.list_steps(cid): self.workflow_tree.insert("","end",values=(w["step_id"],w["phase"],w["status"],w["gate_required"],w["title"],w["owner"]))
        if hasattr(self,"identity_tree"):
            self.identity_tree.delete(*self.identity_tree.get_children())
            for ic in self.ctx.identity.list_candidates(cid): self.identity_tree.insert("","end",values=(ic["candidate_id"],ic["label"],ic["score"],ic["status"],str(ic["positive_markers_json"]),str(ic["negative_markers_json"])))
        if hasattr(self,"risk_tree"):
            self.risk_tree.delete(*self.risk_tree.get_children())
            for rf in self.ctx.risk.list_findings(cid): self.risk_tree.insert("","end",values=(rf["finding_id"],rf["severity"],rf["category"],rf["title"],rf["status"]))
        if hasattr(self,"provider_tree"):
            self.provider_tree.delete(*self.provider_tree.get_children())
            for pr in self.ctx.providers.list_providers(): self.provider_tree.insert("","end",values=(pr["name"],pr["provider_type"],bool(pr["enabled"]),bool(pr["requires_api_key"]),bool(pr["public_only"]),pr["compliance_tags_json"]))
        if hasattr(self,"provider_job_tree"):
            self.provider_job_tree.delete(*self.provider_job_tree.get_children())
            for job in self.ctx.provider_integration.list_jobs(cid): self.provider_job_tree.insert("","end",values=(job["job_id"],job.get("provider_name",""),job.get("capability_key",""),job.get("status",""),job.get("query",""),job.get("request_url",""),job.get("result_count",0)))
        if hasattr(self,"provider_result_tree"):
            self.provider_result_tree.delete(*self.provider_result_tree.get_children())
            for r in self.ctx.provider_integration.list_results(cid): self.provider_result_tree.insert("","end",values=(r["result_id"],r.get("provider_name",""),r.get("title",""),r.get("source_url",""),r.get("raw_hash","")[:16]+"...",r.get("review_item_id","") or ""))
        if hasattr(self,"privacy_text"):
            pdash=self.ctx.privacy.get_privacy_dashboard(cid)
            flags=self.ctx.privacy.list_flags(cid)[:60]
            self.privacy_text.delete("1.0","end")
            self.privacy_text.insert("end", "PRIVACY DASHBOARD\n"+str(pdash)+"\n\nFLAGS\n"+"\n".join(f"{f['severity']} | {f['status']} | {f['data_category']} | {f['article_reference']} | {f['action_required']}" for f in flags))
        if hasattr(self,"compliance_text"):
            dash=self.ctx.compliance.compliance_dashboard(cid)
            pdash=self.ctx.provider_integration.provider_dashboard(cid)
            sources=self.ctx.providers.list_sources()
            caps=self.ctx.provider_integration.list_capabilities(enabled_only=False)
            logs=self.ctx.provider_integration.list_logs(cid)[:20]
            self.compliance_text.delete("1.0","end")
            self.compliance_text.insert("end", "COMPLIANCE DASHBOARD\n"+str(dash)+"\n\nPROVIDER DASHBOARD\n"+str(pdash)+"\n\nCAPABILITIES\n"+"\n".join(f"{c['capability_key']} | {c['provider_name']} | {c['mode']} | reliability={c['default_reliability']}" for c in caps[:80])+"\n\nSOURCE CATALOG\n"+"\n".join(f"{s['name']} | {s['category']} | {s['access_model']} | risk={s['default_risk']}" for s in sources)+"\n\nPROVIDER LOGS\n"+"\n".join(f"{l['created_at']} | {l.get('provider_name','')} | {l['event_type']} | {l['status']}" for l in logs))
        if hasattr(self,"graph_text"):
            nodes=self.ctx.graph.list_nodes(cid); edges=self.ctx.graph.list_edges(cid); dash=self.ctx.graph.graph_dashboard(cid)
            hyps=self.ctx.graph.list_hypotheses(cid); cons=self.ctx.graph.list_contradictions(cid)
            edge_lines=[]
            node_lookup={n['node_id']: n for n in nodes}
            for e in edges[:120]:
                src=node_lookup.get(e['source_node_id'],{}).get('label',e['source_node_id'])
                tgt=node_lookup.get(e['target_node_id'],{}).get('label',e['target_node_id'])
                edge_lines.append(f"{src} --{e['relationship_type']} ({e.get('confidence')})--> {tgt} | {e.get('review_status')} | {e.get('explanation') or ''}")
            hyp_lines=[f"{h.get('status')} | {h.get('confidence')} | {h.get('title')} :: {h.get('statement')}" for h in hyps[:30]]
            con_lines=[f"{c.get('severity')} | {c.get('status')} | {c.get('title')} :: {c.get('description')}" for c in cons[:30]]
            graph_out = "GRAPH DASHBOARD\n" + str(dash)
            graph_out += "\n\nNODES\n" + "\n".join(f"{n['node_type']} | {n['label']} | {n['review_status']} | conf={n.get('confidence')}" for n in nodes[:120])
            graph_out += "\n\nEDGES / EXPLAINABILITY\n" + "\n".join(edge_lines)
            graph_out += "\n\nHYPOTHESEN\n" + "\n".join(hyp_lines)
            graph_out += "\n\nGEGENBELEGE / WIDERSPRÜCHE\n" + "\n".join(con_lines)
            self.graph_text.delete("1.0","end"); self.graph_text.insert("end", graph_out)
        if hasattr(self,"timeline_tree"):
            self.timeline_tree.delete(*self.timeline_tree.get_children())
            for te in self.ctx.timeline.list_events(cid): self.timeline_tree.insert("","end",values=(te["event_date"],te.get("event_type",""),te["title"],te["review_status"],te.get("narrative_weight",0)))

        if hasattr(self,"team_text"):
            try:
                tdash=self.ctx.team.team_dashboard(cid)
                access=self.ctx.team.list_case_access(cid)
                approvals=self.ctx.team.list_approval_requests(cid)
                releases=self.ctx.team.list_releases(cid)
                comments=self.ctx.team.list_comments(cid,limit=20)
                clients=tdash.get("clients",[])
                self.team_access_tree.delete(*self.team_access_tree.get_children())
                for a in access:
                    perms=", ".join(a.get("permissions_json") or [])
                    self.team_access_tree.insert("","end",values=(a.get("username"),a.get("role_key"),a.get("organization"),perms[:220]))
                self.team_approval_tree.delete(*self.team_approval_tree.get_children())
                for ar in approvals:
                    self.team_approval_tree.insert("","end",values=(ar.get("request_id"),ar.get("request_type"),ar.get("status"),ar.get("requested_by"),ar.get("title")))
                out="TEAM / MANDANTEN DASHBOARD\n"+str(tdash)
                out += "\n\nMANDANTEN\n"+"\n".join(f"{c.get('name')} | {c.get('client_type')} | {c.get('assignment_type')} | {c.get('data_boundary')}" for c in clients)
                out += "\n\nFREIGABEHISTORIE\n"+"\n".join(f"{r.get('created_at')} | {r.get('release_type')} | {r.get('audience')} | {r.get('status')} | {str(r.get('approved_by_json'))}" for r in releases)
                out += "\n\nTEAM-KOMMENTARE\n"+"\n".join(f"{c.get('created_at')} | {c.get('author')} | {c.get('visibility')} | {c.get('body')}" for c in comments)
                self.team_text.delete("1.0","end"); self.team_text.insert("end",out)
            except Exception as exc:
                self.team_text.delete("1.0","end"); self.team_text.insert("end","Team Dashboard Fehler: "+str(exc))

        if hasattr(self,"security_text"):
            try:
                sdash=self.ctx.security_hardening.security_dashboard()
                roles=self.ctx.security_hardening.list_roles()
                users=self.ctx.security_hardening.list_users()
                refs=self.ctx.db.all("SELECT name,env_var,status,required,purpose FROM secret_references ORDER BY name")
                baselines=self.ctx.db.all("SELECT baseline_id,label,manifest_hash,created_at FROM integrity_baselines ORDER BY created_at DESC LIMIT 10")
                backups=self.ctx.db.all("SELECT backup_id,backup_path,backup_hash,file_count,total_bytes,created_at FROM backup_manifests ORDER BY created_at DESC LIMIT 10")
                self.security_text.delete("1.0","end")
                self.security_text.insert("end", "SECURITY DASHBOARD\n"+str(sdash)+"\n\nROLES\n"+"\n".join(f"{r['role_key']} | {r['name']} | {r['permissions']}" for r in roles)+"\n\nUSERS\n"+"\n".join(f"{u['username']} | {u['role']} | active={u['active']} | last={u.get('last_login_at','')}" for u in users)+"\n\nSECRET REFERENCES\n"+"\n".join(f"{r['name']} | {r['env_var']} | {r['status']} | required={r['required']}" for r in refs)+"\n\nINTEGRITY BASELINES\n"+"\n".join(f"{b['baseline_id']} | {b['label']} | {b['manifest_hash'][:16]}..." for b in baselines)+"\n\nBACKUPS\n"+"\n".join(f"{b['created_at']} | {b['backup_id']} | files={b['file_count']} | hash={b['backup_hash'][:16]}..." for b in backups))
            except Exception as exc:
                self.security_text.delete("1.0","end"); self.security_text.insert("end", "Security Dashboard Fehler: "+str(exc))

        if hasattr(self,"ai_text"):
            try:
                adash=self.ctx.ai_analyst.dashboard(cid)
                summaries=self.ctx.ai_analyst.list_summaries(cid)[:5]
                contradictions=self.ctx.ai_analyst.list_contradiction_suggestions(cid)[:20]
                hypotheses=self.ctx.ai_analyst.list_hypothesis_suggestions(cid)[:20]
                timeline_drafts=self.ctx.ai_analyst.list_timeline_drafts(cid)[:20]
                report_drafts=self.ctx.ai_analyst.list_report_drafts(cid)[:12]
                tasks=self.ctx.ai_analyst.list_tasks(cid)[:20]
                out="AI ANALYST DASHBOARD\n"+str(adash)
                out += "\n\nTASKS\n"+"\n".join(f"{t.get('created_at')} | {t.get('task_type')} | {t.get('status')} | {t.get('guardrail_status')} | {t.get('title')}" for t in tasks)
                out += "\n\nSUMMARIES\n"+"\n\n".join(f"{s.get('title')} | {s.get('guardrail_status')}\n{s.get('body')}" for s in summaries)
                out += "\n\nWIDERSPRUCHS-VORSCHLÄGE\n"+"\n".join(f"{c.get('severity')} | {c.get('guardrail_status')} | {c.get('title')} :: {c.get('description')}" for c in contradictions)
                out += "\n\nGEGENHYPOTHESEN\n"+"\n".join(f"{h.get('confidence')} | {h.get('guardrail_status')} | {h.get('title')} :: {h.get('statement')}" for h in hypotheses)
                out += "\n\nTIMELINE-DRAFTS\n"+"\n".join(f"{t.get('event_date')} | {t.get('guardrail_status')} | {t.get('title')}" for t in timeline_drafts)
                out += "\n\nREPORT-DRAFTS\n"+"\n".join(f"{r.get('section_key')} | {r.get('guardrail_status')} | {r.get('title')}" for r in report_drafts)
                self.ai_text.delete("1.0","end"); self.ai_text.insert("end",out)
            except Exception as exc:
                self.ai_text.delete("1.0","end"); self.ai_text.insert("end","AI Dashboard Fehler: "+str(exc))

        if hasattr(self,"packaging_text"):
            try:
                self.packaging_refresh()
            except Exception:
                pass

        if hasattr(self,"rc_text"):
            try:
                self.rc_refresh()
            except Exception:
                pass

        if hasattr(self,"query_factory_text"):
            try:
                self.refresh_query_factory()
            except Exception:
                pass

        if hasattr(self,"person_detail_entity_tree"):
            try:
                self.refresh_person_detail_page()
            except Exception:
                pass

        if hasattr(self,"sq_query_tree"):
            try:
                self.refresh_search_quality()
            except Exception:
                pass

        if hasattr(self,"hs_query_tree"):
            try:
                self.refresh_search_spearhead()
            except Exception:
                pass

        if hasattr(self,"output_tree"):
            try:
                self.refresh_one_page_outputs()
            except Exception:
                pass
        if hasattr(self,"audit_tree"):
            self.audit_tree.delete(*self.audit_tree.get_children())
            for a in self.ctx.audit.list_for_case(cid): self.audit_tree.insert("","end",values=(a["timestamp"],a["actor"],a["action"],a["object_type"],a.get("object_id") or "",a.get("details_json") or ""))

def run_desktop(base_dir=None):
    ctx=AppContext(base_dir=base_dir)
    app=EagleEyeDesktop(ctx)
    app.mainloop()
    ctx.close()
