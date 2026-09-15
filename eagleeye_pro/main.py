from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

from eagleeye_pro.version import BUILD, BUILD_NAME


def run_selftest(base_dir: str | None = None) -> dict:
    td_obj = tempfile.TemporaryDirectory() if base_dir is None else None
    base = Path(base_dir or td_obj.name)
    ctx = AppContext(base_dir=base)
    try:
        security_seed = ctx.security_hardening.seed_security_defaults()
        local_admin = ctx.security_hardening.create_local_user(
            "qa-admin", "QA Administrator", "Build28-SecurePass!", role="admin",
            notes="Build 36 selftest account; fiktiv und lokal."
        )
        auth_session = ctx.security_hardening.authenticate_user("qa-admin", "Build28-SecurePass!", ttl_minutes=30)
        secret_ref = ctx.security_hardening.create_secret_reference(
            "Bing Web Search API Key", "EAGLEEYE_BING_API_KEY",
            "Optionaler Provider-Key; Build 36 speichert nur Env-Var-Referenz, niemals Klartext.",
            provider_id="bing_web", required=False
        )
        secret_validation = ctx.security_hardening.validate_secret_references()
        code_root = Path(__file__).resolve().parents[1]
        integrity_baseline = ctx.security_hardening.create_integrity_baseline(
            code_root, label="Build 36 code integrity baseline", notes="Selftest-Baseline über Quellcode/Launcher/Dokumentation ohne data/reports."
        )
        integrity_check = ctx.security_hardening.verify_integrity_baseline(integrity_baseline["baseline_id"])
        assert integrity_check["status"] == "pass", integrity_check

        case = ctx.cases.create_case(
            "Build 36 Team / Mandantenfähigkeit Smoke Test",
            "Internal QA",
            "Rechtmäßiger Test eines fallzentrierten PersonenOSINT-Workflows mit fiktiver Zielperson und öffentlichen Quellen",
            "Art. 6 Abs. 1 lit. f DSGVO / interner Funktionstest mit fiktiven Daten",
            retention_until="2026-12-31",
        )
        ctx.workflow.initialize_case_workflow(case["case_id"])
        playbook_seed = ctx.playbooks.seed_defaults()
        recommendations = ctx.playbooks.recommend_playbooks(case["purpose"], limit=3)
        playbook_assignment = ctx.playbooks.apply_playbook_to_case(case["case_id"], "due_diligence", assigned_by="qa-admin", notes="Build 37.0 QA: Due-Diligence-Playbook als Standardworkflow")
        for step in playbook_assignment["steps"][:3]:
            ctx.playbooks.update_step(step["case_step_id"], "done", notes="Build 37.0 QA: Playbook-Schritt im Smoke-Test abgeschlossen.")
        for gate in playbook_assignment["quality_gates"][:2]:
            ctx.playbooks.update_quality_gate(gate["gate_id"], "passed", notes="Build 37.0 QA: Quality Gate im Smoke-Test passiert.")
        playbook_assignment = ctx.playbooks.assignment_detail(playbook_assignment["assignment_id"])
        playbook_dashboard = ctx.playbooks.dashboard(case["case_id"])
        assert playbook_seed["total"] >= 7, playbook_seed
        assert len(recommendations) >= 3, recommendations
        assert playbook_assignment["steps"] and playbook_dashboard["counts"]["assignments"] >= 1, playbook_dashboard
        client = ctx.team.create_client("Internal QA Mandant", client_type="internal_quality", contact="qa@example.org", notes="Build 36 Mandantentrennung QA")
        client_assignment = ctx.team.assign_case_to_client(case["case_id"], client["client_id"], notes="Build 37.0 QA: strikte Mandantengrenze")
        analyst_member = ctx.team.create_member("qa-analyst", "QA Analyst", "analyst@example.org", role_key="senior_analyst", notes="Build 37.0 QA Teammitglied")
        legal_member = ctx.team.create_member("qa-legal", "QA Legal Reviewer", "legal@example.org", role_key="legal_reviewer", notes="Build 37.0 QA Legal Reviewer")
        analyst_access = ctx.team.grant_case_access(case["case_id"], analyst_member["member_id"], "senior_analyst", granted_by="qa-admin")
        legal_access = ctx.team.grant_case_access(case["case_id"], legal_member["member_id"], "legal_reviewer", granted_by="qa-admin")
        perm_check = ctx.team.check_case_permission(case["case_id"], "qa-legal", "export:approve")
        assert perm_check["allowed"], perm_check
        team_comment = ctx.team.add_comment(case["case_id"], "case", case["case_id"], "qa-analyst", "Build 37.0 QA-Kommentar: Fall ist Team-/Mandantenworkflow-fähig.")
        legal = ctx.legal.create_review(
            case["case_id"],
            case["purpose"],
            case["legal_basis"],
            "Test ist erforderlich, um Search Workbench, Legal Gate, Capture-Chain, Review, Evidence und Exportkontrolle zu prüfen.",
            "Fiktive Daten, keine realen Personen, nur öffentliche Quellen, keine Umgehung, keine sensiblen Kategorien.",
            approved=True,
            review_level="senior",
        )
        evaluation = ctx.legal.evaluate_case(case["case_id"])
        assert evaluation["ok"], evaluation
        ctx.compliance.set_retention_policy(case["case_id"], "2026-12-31", "Interner Testfall; kurze Aufbewahrung für QA-Auswertung.")
        privacy_wizard = ctx.privacy.create_legal_case_wizard(
            case["case_id"],
            lawful_basis=case["legal_basis"],
            legitimate_interest=case["purpose"],
            necessity_test="Build-27-Test: Verarbeitung ist erforderlich, um Legal/Privacy Gates, Datenklassenprüfung und Exportblocker zu prüfen.",
            balancing_test="Fiktive Daten, öffentliche Quellen, Datenminimierung, Review-Pflicht, Redaction und Löschfrist senken Betroffenenrisiken.",
            proportionality_test="Nur erforderliche fiktive Treffer werden erfasst; keine privaten Accounts und keine Umgehungstechniken.",
            data_minimization_notes="Nur Fallzweck-relevante Anker; Kandidatenlogik statt Identitätsbehauptung.",
            retention_until="2026-12-31",
            decision="approved",
            risk_level="medium",
            notes="Build 37.0 QA Legal Case Wizard"
        )
        target = ctx.targets.create_target(
            case["case_id"], "Maria Muster", aliases="m.muster", emails="maria@example.org", usernames="mariamuster", locations="Köln", companies="Muster Consulting GmbH", domains="example.org"
        )
        queries = ctx.dorks.generate_queries(target)
        assert len(queries) >= 10
        provider_seed = ctx.provider_integration.seed_capabilities()
        provider_health = ctx.provider_integration.run_health_checks()
        real_provider_seed = ctx.real_providers.seed_defaults()
        real_provider_health = ctx.real_providers.health_check(execute_live=False)
        assert real_provider_seed["connectors"] >= 8, real_provider_seed
        assert real_provider_health["connectors_checked"] >= 8, real_provider_health
        real_provider_sample = ctx.real_providers.run_connector(
            case["case_id"], "brave_web_api", "Maria Muster Muster Consulting GmbH",
            "Build 44.0 QA: sample payload, keine externe Abfrage.", target_id=target["target_id"], execute_live=False,
            sample_payload={"web": {"results": [{"title": "Sample Brave Treffer", "url": "https://example.org/brave-sample", "description": "Fiktives Brave API Sample als Review-Kandidat.", "age": "2026-06-06"}]}},
        )
        assert real_provider_sample["stored_items"] and real_provider_sample["status"] == "completed_sample", real_provider_sample
        real_provider_review = ctx.real_providers.results_to_review(case["case_id"])
        assert real_provider_review["created_review_items"] >= 1, real_provider_review
        real_provider_dash = ctx.real_providers.dashboard(case["case_id"])
        assert real_provider_dash["gate"] == "REAL_PROVIDER_CONNECTORS_READY", real_provider_dash
        assert provider_seed["capabilities"] >= 10, provider_seed
        assert provider_health["providers_checked"] >= 8, provider_health
        pjob = ctx.provider_integration.create_provider_job(
            case["case_id"], "bing_web", "Maria Muster Muster Consulting GmbH",
            "Fiktiver QA Provider Job für öffentliche Suchquelle; Ergebnis bleibt Review-Kandidat.",
            target_id=target["target_id"],
        )
        opened_provider_job = ctx.provider_integration.mark_job_opened(pjob["job_id"])
        imported_provider_result = ctx.provider_integration.import_provider_result(
            case["case_id"], opened_provider_job["job_id"],
            "Provider QA Treffer", "https://example.org/provider-result",
            "Fiktiver öffentlicher Provider-Treffer für Maria Muster / Muster Consulting GmbH.",
            raw_payload={"provider":"Bing Web Search", "qa": True, "candidate_only": True},
            reliability="medium",
        )
        dns_lookup = ctx.provider_integration.run_local_dns_lookup(case["case_id"], "example.org", "Nicht-intrusive lokale DNS-Prüfung für QA.", target_id=target["target_id"])
        provider_review = ctx.provider_integration.create_review_items_from_results(case["case_id"])
        assert provider_review["created_review_items"] >= 2, provider_review
        provider_dashboard = ctx.provider_integration.provider_dashboard(case["case_id"])
        wb = ctx.search_workbench.create_packages_from_target(case["case_id"], target["target_id"], engines=["Bing", "DuckDuckGo", "Brave"])
        assert wb["packages"] >= 5 and wb["tasks"] >= 20, wb
        tasks = ctx.search_workbench.list_tasks(case["case_id"])
        multi_seed = ctx.search_workbench.seed_multi_search_presets()
        assert multi_seed["total"] >= 5, multi_seed
        multi_launch = ctx.search_workbench.create_multi_search_from_task(case["case_id"], tasks[0]["task_id"], preset_key="standard", bundle_key="identity_core")
        assert multi_launch["url_count"] >= 4 and {"Google", "Bing", "DuckDuckGo", "Brave"}.issubset(set(multi_launch["engines"])), multi_launch
        ctx.search_workbench.mark_multi_search_opened(multi_launch["launch_id"])
        free_multi_launch = ctx.search_workbench.create_multi_search_launch(case["case_id"], "\"Maria Muster\" Muster Consulting GmbH", preset_key="deep_public", target_id=target["target_id"], bundle_key="professional_business", notes="Build 37.0 QA freie Mehrfachsuche")
        assert free_multi_launch["url_count"] >= 8, free_multi_launch
        resolved_multi_query = ctx.search_workbench.resolve_multi_search_query(case["case_id"], explicit_query="", target_id=target["target_id"])
        assert resolved_multi_query["source"] == "target_fallback" and "Maria Muster" in resolved_multi_query["query"], resolved_multi_query
        fallback_multi_launch = ctx.search_workbench.create_multi_search_launch(case["case_id"], resolved_multi_query["query"], preset_key="standard", target_id=resolved_multi_query["target_id"], bundle_key="identity_core", notes="Build 37.0 QA Query-Fallback aus Zielperson")
        assert fallback_multi_launch["url_count"] >= 4, fallback_multi_launch
        multi_history = ctx.search_workbench.list_multi_search_launches(case["case_id"])
        assert len(multi_history) >= 2, multi_history
        opened = ctx.search_workbench.mark_task_opened(tasks[0]["task_id"])
        cap = ctx.search_workbench.capture_public_hit(
            case["case_id"], opened["task_id"], "Öffentlicher Muster-Treffer", "https://example.org/profile?utm_source=test",
            "Fiktiver öffentlicher OSINT-Hinweis zu Maria Muster / Muster Consulting GmbH als Kandidat. Kontakt: maria@example.org",
            raw_text="Snapshot-Text aus fiktiver öffentlicher Quelle für QA.", score=0.82
        )
        # Zweiter Treffer mit normalisierter Duplikat-URL prüft Build-20-Duplicate-Clustering.
        cap2 = ctx.search_workbench.capture_public_hit(
            case["case_id"], opened["task_id"], "Öffentlicher Muster-Treffer Kopie", "https://www.example.org/profile",
            "Derselbe fiktive Treffer als Duplicate-Kandidat für Maria Muster / Muster Consulting GmbH.",
            raw_text="Snapshot-Duplikat aus fiktiver öffentlicher Quelle für QA.", score=0.62
        )
        capture_manifest = ctx.search_workbench.capture_manifest(case["case_id"])
        assert capture_manifest["ok"], capture_manifest
        duplicate_result = ctx.review.find_duplicates(case["case_id"])
        assert duplicate_result["cluster_count"] >= 1, duplicate_result
        triage = ctx.review.bulk_triage(case["case_id"])
        review_dashboard = ctx.review.review_dashboard(case["case_id"])
        ctx.review.update_status(cap["review_item_id"], "accepted_as_lead")
        ev = ctx.evidence.promote_review_item(cap["review_item_id"], category="Identitätsanker", export_allowed=False)
        redaction = ctx.evidence.create_redaction_review(ev["evidence_id"], profile="client_safe", decision="redacted", notes="QA: E-Mail wird für Client-Export redigiert.")
        ev = ctx.evidence.decide_evidence(ev["evidence_id"], "accepted", export_allowed=True, redaction_required=False, notes="QA: redigierter Export freigegeben.")
        manifest = ctx.evidence.verify_manifest(case["case_id"])
        assert manifest["ok"], manifest
        evidence_dashboard = ctx.evidence.evidence_dashboard(case["case_id"])
        package_manifest = ctx.evidence.create_package_manifest(case["case_id"], base / "reports", notes="Build 37.0 QA Evidence Package Manifest")
        identities = ctx.identity.generate_candidates(case["case_id"])
        assert identities and identities[0]["score"] > 0
        ctx.identity.decide_candidate(identities[0]["candidate_id"], "accepted_as_probable", "Fiktiver QA-Fall: Marker ausreichend für Testpfad, keine reale Identitätsbestätigung.")
        graph = ctx.graph.rebuild_pro_graph(case["case_id"])
        assert graph["nodes"] >= 8 and graph["edges"] >= 5, graph
        edges = ctx.graph.list_edges(case["case_id"])
        edge_explain = ctx.graph.explain_edge(edges[0]["edge_id"])
        hypothesis = ctx.graph.create_hypothesis(
            case["case_id"],
            "QA-Hypothese: Zielprofil und öffentlicher Treffer hängen zusammen",
            "Die geprüften fiktiven Evidence Items stützen einen möglichen Zusammenhang zwischen Zielprofil, Firma und öffentlichem Profil; Gegenprüfung bleibt erforderlich.",
            confidence=0.61,
            supporting_evidence=[ev["evidence_id"]],
            status="open",
        )
        contradiction = ctx.graph.add_contradiction(
            case["case_id"],
            "QA-Gegenbeleg: Namensdoppler möglich",
            "Der zweite Capture kann als Namensdoppler/Duplikat interpretiert werden; Analyst muss Quellenkontext prüfen.",
            severity="medium",
            related_evidence=[ev["evidence_id"]],
        )
        timeline_build = ctx.timeline.build_from_evidence(case["case_id"])
        ctx.timeline.add_event(case["case_id"], "2026-06-02", "Fiktiver öffentlicher Hinweis erfasst", source_evidence_id=ev["evidence_id"], event_type="manual_osint_event", narrative_weight=0.65, uncertainty_note="QA-Event: manuell gesetzt.")
        timeline_conflicts = ctx.timeline.detect_conflicts(case["case_id"])
        graph_narrative = ctx.graph.build_analysis_narrative(case["case_id"])
        timeline_narrative = ctx.timeline.build_narrative(case["case_id"])
        graph_dashboard = ctx.graph.graph_dashboard(case["case_id"])
        timeline_dashboard = ctx.timeline.timeline_dashboard(case["case_id"])
        assert graph_narrative and timeline_narrative
        privacy_classification = ctx.privacy.classify_case_data(case["case_id"])
        dpia_latest = ctx.privacy.run_dpia_check(case["case_id"])
        privacy_export = ctx.privacy.evaluate_privacy_export(case["case_id"], "redacted_client")
        deletion_job = ctx.privacy.create_retention_deletion_job(case["case_id"], action="review_retention", reason="Build 37.0 QA Retention Review", scheduled_for="2026-12-31")
        deletion_preview = ctx.privacy.execute_retention_deletion_job(deletion_job["job_id"], dry_run=True)
        privacy_dashboard = ctx.privacy.get_privacy_dashboard(case["case_id"])
        risk = ctx.risk.auto_assess_case(case["case_id"])
        export_eval = ctx.export_control.evaluate_export(case["case_id"], "internal_report")
        assert export_eval["decision"] == "approved", export_eval
        dashboard = ctx.compliance.compliance_dashboard(case["case_id"])
        readiness = ctx.reports.report_readiness(case["case_id"], "redacted_client")
        assert readiness["status"] in {"ready", "review_required", "blocked"}, readiness
        gap_assessment = ctx.intelligence_gap.assess_case(case["case_id"], persist=True)
        assert gap_assessment["scores"]["overall_workflow_score"] >= 0, gap_assessment
        report_pipeline = ctx.report_automation.pipeline_dashboard(case["case_id"], "redacted_client")
        assert report_pipeline["metrics"]["evidence_items"] >= 1, report_pipeline
        report_draft = ctx.report_automation.generate_report_draft(case["case_id"], "redacted_client", "client_safe", notes="Build 39.0 QA Evidence-to-Report Draft")
        assert report_draft["sections"], report_draft
        automated_report = ctx.report_automation.export_automated_report(case["case_id"], base / "reports", "redacted_client", "client_safe")
        assert automated_report["content_hash"], automated_report
        pro_report = ctx.reports.export_professional_report(case["case_id"], base / "reports", "redacted_client", "client_safe", notes="Build 39.0 QA redacted client report")
        assert pro_report["report_id"].startswith("rpt_") and pro_report["content_hash"], pro_report
        approval_request = ctx.team.request_approval(case["case_id"], "report_release", "professional_report", pro_report["report_id"], "Freigabe redacted client report", "QA-Freigabe nach Vier-Augen-Prinzip für redigierten Bericht.", requested_by="qa-analyst", required_role="legal_reviewer", min_approvals=1)
        approval_decision = ctx.team.record_approval_decision(approval_request["request_id"], "approved", decided_by="qa-legal", decider_role="legal_reviewer", comment="QA-Freigabe: redigierter Bericht ist exportfähig.")
        approval_request = ctx.team.get_approval_request(approval_request["request_id"])
        release_record = ctx.team.create_release_record(case["case_id"], approval_request["request_id"], "redacted_client_report", "client", pro_report["content_hash"], approved_by=["qa-legal"], notes="Build 37.0 QA Release History")
        team_dashboard = ctx.team.team_dashboard(case["case_id"])
        assert team_dashboard["status"] in {"team_ready", "review_required"}, team_dashboard
        export_watermark = ctx.security_hardening.create_export_watermark(
            "redacted_client", case_id=case["case_id"], report_id=pro_report["report_id"],
            notes="Build 37.0 QA Export Watermark"
        )
        bundle = ctx.reports.export_report_bundle(case["case_id"], base / "reports")
        assert set(bundle.keys()) >= {"redacted_client", "internal_analyst", "full_dossier", "evidence_annex"}
        paths = ctx.reports.export_case_report(case["case_id"], base / "reports")
        hardening = ctx.performance_security.full_hardening_suite(base, case_id=case["case_id"])
        assert hardening["status"] == "pass", hardening
        for p in paths.values():
            assert Path(p).exists() and Path(p).stat().st_size > 0, p
        for report_name, report_paths in bundle.items():
            for key, p in report_paths.items():
                if key in {"report_id", "content_hash", "readiness_status"}:
                    continue
                assert Path(p).exists() and Path(p).stat().st_size > 0, (report_name, key, p)
        report_blueprints = ctx.reports.list_blueprints()
        professional_reports = ctx.db.all("SELECT * FROM professional_reports WHERE case_id=?", [case["case_id"]])
        report_checks = ctx.db.all("SELECT * FROM report_readiness_checks WHERE case_id=?", [case["case_id"]])
        ai_templates = ctx.ai_analyst.seed_templates()
        ai_digest = ctx.ai_analyst.build_case_digest(case["case_id"])
        ai_contradictions = ctx.ai_analyst.suggest_contradictions(case["case_id"])
        ai_hypotheses = ctx.ai_analyst.suggest_counter_hypotheses(case["case_id"])
        ai_timeline = ctx.ai_analyst.draft_timeline_from_evidence(case["case_id"])
        ai_report_drafts = ctx.ai_analyst.draft_report_sections(case["case_id"], "internal_analyst")
        ai_bundle = ctx.ai_analyst.run_assistant_bundle(case["case_id"])
        ai_dashboard = ctx.ai_analyst.dashboard(case["case_id"])
        ai_guardrail_block = ctx.ai_analyst.guardrail_check(case["case_id"], "Diese Person ist sicher dieselbe Person und ist der Täter.", "qa_forbidden_draft", "qa")
        assert ai_dashboard["status"] == "ai_assistant_ready", ai_dashboard
        assert ai_digest["guardrail_status"] in {"pass", "warning", "blocked"}, ai_digest
        assert ai_hypotheses["created"] >= 1, ai_hypotheses
        assert ai_report_drafts["created"] >= 4, ai_report_drafts
        assert ai_bundle["task_id"].startswith("aitask_"), ai_bundle
        assert ai_guardrail_block["status"] == "blocked", ai_guardrail_block
        backup_manifest = ctx.security_hardening.create_backup_bundle(base, base / "backups", notes="Build 37.0 QA Backup Bundle")
        audit_chain = ctx.security_hardening.harden_audit_chain()
        audit_chain_verify = ctx.security_hardening.verify_audit_chain()
        assert audit_chain_verify["ok"], audit_chain_verify
        security_dashboard = ctx.security_hardening.security_dashboard()
        cockpit_dashboard = ctx.cockpit.build_cockpit(case["case_id"])
        assert cockpit_dashboard["readiness_score"] >= 60, cockpit_dashboard
        assert cockpit_dashboard["traffic_light"] in {"yellow", "green"}, cockpit_dashboard
        assert cockpit_dashboard["next_actions"], cockpit_dashboard
        cockpit_snapshot = ctx.cockpit.persist_snapshot(case["case_id"], notes="Build 37.0 QA Cockpit Snapshot")
        cockpit_snapshots = ctx.cockpit.list_snapshots(case["case_id"])
        assert cockpit_snapshot["snapshot_id"].startswith("cockpit_"), cockpit_snapshot
        assert cockpit_snapshots, cockpit_snapshots
        packaging_seed = ctx.packaging.seed_defaults()
        migration_plan = ctx.packaging.create_migration_plan("30.0", "37.0", notes="Build 37.0 QA Migration Plan von Build 30 auf 31.")
        migration_readiness = ctx.packaging.run_migration_readiness(base, "30.0", "37.0")
        assert migration_readiness["status"] in {"ready", "review_required"}, migration_readiness
        rollback_point = ctx.packaging.create_rollback_point(base, label="Build 37.0 QA Rollback", notes="QA Rollbackpunkt nach Selftest-Datenanlage.")
        assert rollback_point["backup_hash"], rollback_point
        distro_manifest = ctx.packaging.build_distribution_manifest(Path(__file__).resolve().parents[1], "portable_local")
        assert distro_manifest["file_count"] > 20 and not distro_manifest["includes_runtime_data"], distro_manifest
        portable_bundle = ctx.packaging.create_portable_bundle(Path(__file__).resolve().parents[1], base / "release", notes="Build 37.0 QA Portable Bundle ohne Runtime-Daten.")
        assert portable_bundle["validation"]["status"] in {"pass", "review_required"}, portable_bundle
        packaging_dashboard = ctx.packaging.dashboard()
        assert packaging_dashboard["status"] in {"packaging_ready", "validation_issue"}, packaging_dashboard
        rc_seed = ctx.release_candidate.seed_defaults()
        rc_gates = ctx.release_candidate.mark_core_gates_from_current_state(case["case_id"])
        rc_audit = ctx.release_candidate.run_release_candidate_audit(Path(__file__).resolve().parents[1])
        assert rc_audit["status"] in {"pass", "review_required"}, rc_audit
        rc_freeze = ctx.release_candidate.create_release_freeze(Path(__file__).resolve().parents[1], manifest_hash=distro_manifest["manifest_hash"], notes="Build 37.0 QA Release-Freeze auf Basis des Distribution-Manifests.")
        rc_assessment = ctx.release_candidate.product_readiness_assessment()
        assert rc_assessment["overall_score"] >= 80, rc_assessment
        rc_dashboard = ctx.release_candidate.dashboard()
        assert rc_dashboard["status"] in {"release_candidate_ready", "qa_review_required"}, rc_dashboard
        ux_seed = ctx.ux_consolidation.seed_defaults()
        ux_dashboard = ctx.ux_consolidation.workspace_dashboard(case["case_id"])
        ux_snapshot = ctx.ux_consolidation.persist_workspace_snapshot(case["case_id"], notes="Build 37.0 QA: UX-Konsolidierung / Suchbündel-Snapshot")
        identity_bundle_tasks = ctx.ux_consolidation.filter_tasks_by_bundle(ctx.search_workbench.list_tasks(case["case_id"]), "identity_core")
        assert ux_dashboard["workspace_count"] == 6, ux_dashboard
        assert ux_dashboard["search_bundle_count"] == 6, ux_dashboard
        assert ux_dashboard["search_bundle_dashboard"]["task_total"] >= 10, ux_dashboard
        assert identity_bundle_tasks, identity_bundle_tasks
        guided_seed = ctx.guided_research.seed_defaults()
        guided_dashboard = ctx.guided_research.start_or_refresh_run(case["case_id"], target_id=target["target_id"], notes="Build 37.0 QA Guided Research Run")
        assert len(guided_dashboard["phases"]) >= 10, guided_dashboard
        image_phase = ctx.guided_research.launch_phase_multi_search(case["case_id"], "04_image_media", target_id=target["target_id"])
        assert image_phase["launch"]["url_count"] >= 4, image_phase
        assert any("Bilder" in e for e in image_phase["launch"]["engines"]), image_phase
        geo_phase = ctx.guided_research.launch_phase_multi_search(case["case_id"], "05_geo_places", target_id=target["target_id"])
        assert geo_phase["launch"]["url_count"] >= 5, geo_phase
        assert "Google Maps" in geo_phase["launch"]["engines"] or "OpenStreetMap" in geo_phase["launch"]["engines"], geo_phase
        guided_security = ctx.guided_research.run_security_checks(case["case_id"], guided_dashboard["run"]["run_id"])
        assert guided_security["gate"] in {"GUIDED_SECURITY_PASS", "GUIDED_SECURITY_REVIEW"}, guided_security
        guided_dashboard = ctx.guided_research.dashboard(case["case_id"], guided_dashboard["run"]["run_id"])
        rex_dashboard = ctx.research_execution.dashboard(case["case_id"], target_id=target["target_id"])
        assert len(rex_dashboard["execution_phases"]) == 6, rex_dashboard
        rex_image = ctx.research_execution.prepare_phase_launch(case["case_id"], "04_image_media", target_id=target["target_id"])
        assert rex_image["launch"]["url_count"] >= 4 and any("Bilder" in e or e == "Yandex Bilder" for e in rex_image["launch"]["engines"]), rex_image
        ctx.research_execution.mark_phase_opened(case["case_id"], rex_image["phase_run_id"], rex_image["launch"]["launch_id"])
        rex_import = ctx.research_execution.import_urls_to_capture(case["case_id"], "https://example.org/build36-research-center", "04_image_media", target_id=target["target_id"], title_prefix="Research Center QA", snippet="Fiktiver öffentlicher Treffer aus Research Execution Center")
        assert rex_import["created"] == 1, rex_import
        rex_security = ctx.research_execution.run_security_checks(case["case_id"])
        assert rex_security["gate"] == "RESEARCH_EXECUTION_SECURITY_PASS", rex_security
        rex_dashboard = ctx.research_execution.dashboard(case["case_id"], target_id=target["target_id"])
        capture_inbox_batch = ctx.capture_inbox.create_batch(
            case["case_id"],
            "https://example.org/build36-capture-inbox\nhttps://github.com/example/public-profile\nhttps://example.org/build36-research-center",
            phase_key="04_image_media",
            target_id=target["target_id"],
            title_prefix="Capture Inbox QA",
            snippet="Build 37.0 QA: manuell geprüfter öffentlicher Browserfund; Kandidat für Review.",
            notes="Build 37.0 QA Capture Inbox Pro Multi-URL Import"
        )
        assert capture_inbox_batch["created_items"] >= 2, capture_inbox_batch
        assert capture_inbox_batch["duplicate_count"] >= 1, capture_inbox_batch
        capture_inbox_promote = ctx.capture_inbox.promote_batch_to_review(capture_inbox_batch["batch_id"], force_duplicates=False)
        assert capture_inbox_promote["promoted"] >= 1, capture_inbox_promote
        assert capture_inbox_promote["held_for_duplicate_review"] >= 1, capture_inbox_promote
        capture_inbox_dashboard = ctx.capture_inbox.dashboard(case["case_id"])
        assert capture_inbox_dashboard["status_counts"].get("captured_to_review", 0) >= 1, capture_inbox_dashboard
        query_factory_dash = ctx.query_factory.generate_for_case(case["case_id"], target["target_id"], notes="Build 37.0 QA Query Factory & Search Matrix")
        assert query_factory_dash["allowed_count"] >= 12 and len(query_factory_dash["matrix"]) >= 8, query_factory_dash
        qf_top = query_factory_dash["top_queries"][0]
        qf_transfer = ctx.query_factory.selected_query_to_research_center(case["case_id"], qf_top["query_id"])
        assert qf_transfer["query"] and qf_transfer["phase_key"], qf_transfer
        qf_security = ctx.query_factory.run_security_checks(case["case_id"], target["target_id"], query_factory_dash["run"]["run_id"])
        assert qf_security["gate"] in {"QUERY_FACTORY_SECURITY_PASS", "QUERY_FACTORY_SECURITY_REVIEW"}, qf_security
        query_intel_dash = ctx.query_intelligence.generate_for_case(case["case_id"], target["target_id"], profile_key="de_eu", notes="Build 44.0 QA Query Intelligence Pro")
        assert query_intel_dash["allowed_count"] >= 20 and len(query_intel_dash.get("variants", [])) >= 2, query_intel_dash
        qi_top = query_intel_dash["top_items"][0]
        qi_transfer = ctx.query_intelligence.selected_query_to_research_center(case["case_id"], qi_top["item_id"])
        assert qi_transfer["query"] and qi_transfer["phase_key"], qi_transfer
        qi_security = ctx.query_intelligence.security_check(case["case_id"], target["target_id"], query_intel_dash["run"]["run_id"])
        assert qi_security["gate"] in {"QUERY_INTELLIGENCE_SECURITY_PASS", "QUERY_INTELLIGENCE_SECURITY_REVIEW"}, qi_security

        fast_lane_session = ctx.review_fast_lane.create_session(case["case_id"], lane_key="new", notes="Build 37.0 QA Review Fast Lane session")
        fast_lane_scan = ctx.review_fast_lane.name_doppler_scan(case["case_id"])
        fast_lane_dash = ctx.review_fast_lane.dashboard(case["case_id"])
        fast_lane_items = ctx.db.all("SELECT item_id FROM review_items WHERE case_id=? AND status IN ('new','in_review','needs_source_review') LIMIT 1", [case["case_id"]])
        fast_lane_decision = {}
        if fast_lane_items:
            fast_lane_decision = ctx.review_fast_lane.decide_item(fast_lane_items[0]["item_id"], "R", analyst_note="Build 37.0 QA Fast-Lane: als relevanter Lead behalten.", session_id=fast_lane_session["session_id"])
        fast_lane_security = ctx.review_fast_lane.security_checks(case["case_id"])
        assert fast_lane_dash["status"] == "review_fast_lane_ready", fast_lane_dash
        assert fast_lane_security["gate"] == "REVIEW_FAST_LANE_SECURITY_PASS", fast_lane_security
        result = {
            "build": BUILD,
            "gate": "BUILD_58_1_SELFTEST_PASS",
            "review_fast_lane_dashboard": fast_lane_dash,
            "review_fast_lane_security": fast_lane_security,
            "case_id": case["case_id"],
            "playbook_seed": playbook_seed,
            "playbook_recommendations": [{"key": r["playbook_key"], "score": r["recommendation_score"]} for r in recommendations],
            "playbook_assignment": {"assignment_id": playbook_assignment["assignment_id"], "playbook_key": playbook_assignment["playbook_key"], "steps": len(playbook_assignment["steps"]), "quality_gates": len(playbook_assignment["quality_gates"])},
            "playbook_dashboard": playbook_dashboard,
            "security_seed": security_seed,
            "local_admin": {k: local_admin[k] for k in ["user_id", "username", "role", "active"]},
            "auth_session": {k: auth_session[k] for k in ["session_id", "username", "role", "expires_at"]},
            "secret_ref": secret_ref,
            "secret_validation": secret_validation,
            "integrity_baseline": {"baseline_id": integrity_baseline["baseline_id"], "manifest_hash": integrity_baseline["manifest_hash"]},
            "integrity_check": integrity_check,
            "export_watermark": export_watermark,
            "backup_manifest": backup_manifest,
            "audit_chain": audit_chain,
            "audit_chain_verify": audit_chain_verify,
            "security_dashboard": security_dashboard,
            "cockpit_dashboard": cockpit_dashboard,
            "cockpit_snapshot": cockpit_snapshot,
            "cockpit_snapshots": len(cockpit_snapshots),
            "ai_templates": ai_templates,
            "ai_digest": {"summary_id": ai_digest.get("summary_id"), "guardrail_status": ai_digest.get("guardrail_status"), "metrics": ai_digest.get("metrics_json")},
            "ai_contradictions": ai_contradictions,
            "ai_hypotheses": ai_hypotheses,
            "ai_timeline": ai_timeline,
            "ai_report_drafts": ai_report_drafts,
            "ai_bundle": ai_bundle,
            "ai_dashboard": ai_dashboard,
            "ai_guardrail_block": ai_guardrail_block,
            "team_dashboard": team_dashboard,
            "client": client,
            "client_assignment": client_assignment,
            "team_members": [analyst_member, legal_member],
            "case_access": [analyst_access, legal_access],
            "permission_check": perm_check,
            "team_comment": team_comment,
            "approval_request": approval_request,
            "approval_decision": approval_decision,
            "release_record": release_record,

            "workflow": ctx.workflow.progress(case["case_id"]),
            "providers": len(ctx.providers.list_providers()),
            "provider_seed": provider_seed,
            "provider_health": provider_health,
            "provider_dashboard": provider_dashboard,
            "provider_job": opened_provider_job,
            "provider_result": imported_provider_result,
            "provider_dns_lookup": dns_lookup,
            "privacy_wizard": privacy_wizard,
            "privacy_classification": privacy_classification,
            "dpia_latest": dpia_latest,
            "privacy_export": privacy_export,
            "privacy_dashboard": privacy_dashboard,
            "retention_deletion_job": deletion_job,
            "retention_deletion_preview": deletion_preview,
            "provider_results_to_review": provider_review,
            "sources": len(ctx.providers.list_sources()),
            "queries": len(queries),
            "search_tasks": len(tasks),
            "search_packages": wb["packages"],
            "multi_search_seed": multi_seed,
            "multi_search_launch": {"launch_id": multi_launch["launch_id"], "url_count": multi_launch["url_count"], "engines": multi_launch["engines"]},
            "free_multi_search_launch": {"launch_id": free_multi_launch["launch_id"], "url_count": free_multi_launch["url_count"], "engines": free_multi_launch["engines"]},
            "resolved_multi_search_query": resolved_multi_query,
            "fallback_multi_search_launch": {"launch_id": fallback_multi_launch["launch_id"], "url_count": fallback_multi_launch["url_count"], "engines": fallback_multi_launch["engines"]},
            "multi_search_history_count": len(multi_history),
            "captures": len(ctx.search_workbench.list_captures(case["case_id"])),
            "capture_manifest": capture_manifest,
            "review_triage": triage,
            "review_dashboard": review_dashboard,
            "duplicate_clusters": duplicate_result,
            "evidence_manifest": manifest,
            "evidence_dashboard": evidence_dashboard,
            "redaction_review": redaction,
            "evidence_package_manifest": package_manifest,
            "identity_candidates": len(identities),
            "risk_findings": len(risk["findings"]),
            "export_control": export_eval,
            "compliance_dashboard": dashboard,
            "graph": graph,
            "graph_dashboard": graph_dashboard,
            "timeline_build": timeline_build,
            "timeline_conflicts": timeline_conflicts,
            "timeline_dashboard": timeline_dashboard,
            "edge_explainability": edge_explain,
            "hypothesis": hypothesis,
            "contradiction": contradiction,
            "graph_narrative_id": graph_narrative.get("narrative_id"),
            "timeline_narrative_id": timeline_narrative.get("narrative_id"),
            "reports": paths,
            "pro_report": pro_report,
            "report_bundle": bundle,
            "report_blueprints": len(report_blueprints),
            "professional_reports": len(professional_reports),
            "report_readiness": readiness,
            "report_pipeline": report_pipeline,
            "report_draft_sections": len(report_draft.get("sections", [])),
            "automated_report": automated_report,
            "gap_assessment": gap_assessment.get("scores", {}),
            "report_readiness_checks": len(report_checks),
            "packaging_seed": packaging_seed,
            "migration_plan": {"migration_id": migration_plan["migration_id"], "status": migration_plan["status"], "events": len(migration_plan.get("events", []))},
            "migration_readiness": migration_readiness,
            "rollback_point": rollback_point,
            "distribution_manifest": {"file_count": distro_manifest["file_count"], "manifest_hash": distro_manifest["manifest_hash"], "includes_runtime_data": distro_manifest["includes_runtime_data"]},
            "portable_bundle": portable_bundle,
            "packaging_dashboard": packaging_dashboard,
            "release_candidate_seed": rc_seed,
            "release_candidate_gates": rc_gates,
            "release_candidate_audit": rc_audit,
            "release_freeze": rc_freeze,
            "release_candidate_assessment": rc_assessment,
            "release_candidate_dashboard": rc_dashboard,
            "ux_seed": ux_seed,
            "ux_dashboard": ux_dashboard,
            "ux_snapshot": ux_snapshot,
            "guided_seed": guided_seed,
            "guided_dashboard": {"phase_count": len(guided_dashboard.get("phases", [])), "gate": guided_dashboard.get("gate"), "current_phase": guided_dashboard.get("current_phase", {}).get("phase_key")},
            "guided_image_phase": {"url_count": image_phase["launch"]["url_count"], "engines": image_phase["launch"]["engines"], "query": image_phase["launch"]["query"]},
            "guided_geo_phase": {"url_count": geo_phase["launch"]["url_count"], "engines": geo_phase["launch"]["engines"], "query": geo_phase["launch"]["query"]},
            "guided_security": guided_security,
            "research_execution_dashboard": {"readiness_score": rex_dashboard.get("readiness_score"), "execution_phases": len(rex_dashboard.get("execution_phases", [])), "active_phase": rex_dashboard.get("active_phase", {}).get("phase_key")},
            "research_execution_image_phase": {"url_count": rex_image["launch"]["url_count"], "engines": rex_image["launch"]["engines"]},
            "research_execution_import": rex_import,
            "research_execution_security": rex_security,
            "capture_inbox_batch": {"batch_id": capture_inbox_batch["batch_id"], "created_items": capture_inbox_batch["created_items"], "duplicate_count": capture_inbox_batch["duplicate_count"]},
            "capture_inbox_promote": capture_inbox_promote,
            "capture_inbox_dashboard": capture_inbox_dashboard,
            "query_factory_dashboard": query_factory_dash,
            "query_factory_transfer": qf_transfer,
            "query_factory_security": qf_security,
            "query_intelligence_dashboard": query_intel_dash,
            "query_intelligence_transfer": qi_transfer,
            "query_intelligence_security": qi_security,
            "identity_bundle_task_count": len(identity_bundle_tasks),
            "performance_security": hardening,
            "db_path": str(ctx.db.path),
        }
        return result
    finally:
        ctx.close()
        if td_obj is not None:
            td_obj.cleanup()


def create_demo_case(ctx: AppContext) -> dict:
    ctx.security_hardening.seed_security_defaults()
    ctx.security_hardening.create_secret_reference("Demo Provider Key", "EAGLEEYE_DEMO_API_KEY", "Demo: Env-Var-Referenz ohne Klartext-Key", provider_id="demo", required=False)
    case = ctx.cases.create_case(
        "Demo PersonenOSINT Pro Architektur",
        "Demo-Mandant",
        "Rechtmäßige Prüfung öffentlicher Identitäts-, Berufs- und Reputationsanker",
        "Art. 6 Abs. 1 lit. f DSGVO / Mandatsauftrag",
        retention_until="2026-12-31",
    )
    ctx.workflow.initialize_case_workflow(case["case_id"])
    ctx.playbooks.seed_defaults()
    ctx.playbooks.apply_playbook_to_case(case["case_id"], "due_diligence", assigned_by="demo-admin", notes="Demo-Playbook Build 36")
    demo_client = ctx.team.create_client("Demo-Mandant", client_type="demo", contact="demo@example.org", notes="Demo-Mandant Build 36")
    ctx.team.assign_case_to_client(case["case_id"], demo_client["client_id"], notes="Demo-Mandantentrennung Build 36")
    demo_analyst = ctx.team.create_member("demo-analyst", "Demo Analyst", role_key="senior_analyst", notes="Demo Teammitglied")
    demo_legal = ctx.team.create_member("demo-legal", "Demo Legal Reviewer", role_key="legal_reviewer", notes="Demo Legal Reviewer")
    ctx.team.grant_case_access(case["case_id"], demo_analyst["member_id"], "senior_analyst", granted_by="demo-admin")
    ctx.team.grant_case_access(case["case_id"], demo_legal["member_id"], "legal_reviewer", granted_by="demo-admin")
    ctx.team.add_comment(case["case_id"], "case", case["case_id"], "demo-analyst", "Demo-Kommentar: Team-Workflow initialisiert.")
    ctx.legal.create_review(
        case["case_id"], case["purpose"], case["legal_basis"],
        "Nur öffentliche Quellen, datenminimiert, manuelle Review-Pflicht.",
        "Interessenabwägung dokumentiert; private Quellen und Umgehungstechniken sind ausgeschlossen.",
        approved=True,
        review_level="senior",
    )
    ctx.compliance.set_retention_policy(case["case_id"], "2026-12-31", "Demo-Fall mit fiktiven Daten.")
    ctx.privacy.create_legal_case_wizard(case["case_id"], case["legal_basis"], case["purpose"], "Nur öffentliche Quellen; kein Umgehen privater Bereiche; fiktive Demo-Daten.", "Interessenabwägung dokumentiert; Datenschutzrisiken durch Review, Redaction und Löschfrist begrenzt.", retention_until="2026-12-31", decision="approved", notes="Demo Privacy Wizard")
    target = ctx.targets.create_target(case["case_id"], "Maria Muster", aliases="m.muster, maria-m", emails="maria@example.org", usernames="mariamuster", locations="Köln", companies="Muster Consulting GmbH", domains="example.org", notes="Fiktive Demo-Zielperson.")
    ctx.provider_integration.seed_capabilities()
    ctx.provider_integration.run_health_checks()
    ctx.real_providers.seed_defaults()
    ctx.real_providers.health_check(execute_live=False)
    ctx.real_providers.run_connector(case["case_id"], "github_users_api", "mariamuster", "Demo Real Provider Connector: GitHub Public API als Dry-Run/Sample", target_id=target["target_id"], execute_live=False, sample_payload={"items": [{"login": "mariamuster", "html_url": "https://github.com/mariamuster", "score": 1.0}]})
    ctx.real_providers.results_to_review(case["case_id"])
    pjob = ctx.provider_integration.create_provider_job(case["case_id"], "bing_web", "Maria Muster Muster Consulting GmbH", "Demo-Providerjob: öffentliche Suchquelle als Review-Kandidat.", target_id=target["target_id"])
    ctx.provider_integration.import_provider_result(case["case_id"], pjob["job_id"], "Demo Provider Ergebnis", "https://example.org/demo-provider", "Fiktiver Provider-Treffer; wird nur als Review-Kandidat übernommen.")
    ctx.provider_integration.create_review_items_from_results(case["case_id"])
    ctx.search_workbench.create_packages_from_target(case["case_id"], target["target_id"], engines=["Bing", "DuckDuckGo", "Brave"])
    first_task = ctx.search_workbench.list_tasks(case["case_id"])[0]
    ctx.search_workbench.create_multi_search_from_task(case["case_id"], first_task["task_id"], preset_key="standard", bundle_key="identity_core")
    ctx.guided_research.start_or_refresh_run(case["case_id"], target_id=target["target_id"], notes="Demo Guided Research Workflow Build 36")
    ctx.guided_research.launch_phase_multi_search(case["case_id"], "04_image_media", target_id=target["target_id"])
    ctx.guided_research.launch_phase_multi_search(case["case_id"], "05_geo_places", target_id=target["target_id"])
    ctx.research_execution.dashboard(case["case_id"], target_id=target["target_id"])
    ctx.research_execution.prepare_phase_launch(case["case_id"], "02_identity_web", target_id=target["target_id"])
    ctx.research_execution.import_urls_to_capture(case["case_id"], "https://example.org/demo-research-center", "02_identity_web", target_id=target["target_id"], title_prefix="Demo Research Center Treffer", snippet="Fiktive öffentliche URL aus dem Research Execution Center")
    cap = ctx.search_workbench.capture_public_hit(case["case_id"], first_task["task_id"], "Demo Treffer: öffentliches Profil", "https://example.org/profile", "Fiktiver Treffer als Review-Kandidat für Maria Muster und Muster Consulting GmbH.", raw_text="Fiktiver Snapshot aus öffentlicher Demo-Quelle.", score=0.66)
    ctx.review.update_status(cap["review_item_id"], "accepted_as_lead")
    ev = ctx.evidence.promote_review_item(cap["review_item_id"], notes="Demo Evidence Candidate; nicht als bestätigte reale Identität verwenden.", export_allowed=False)
    ctx.evidence.create_redaction_review(ev["evidence_id"], profile="client_safe", decision="redacted", notes="Demo-Redaction vor Client-Export.")
    ev = ctx.evidence.decide_evidence(ev["evidence_id"], "accepted", export_allowed=True, redaction_required=False, notes="Demo Evidence reviewed.")
    ctx.identity.generate_candidates(case["case_id"])
    ctx.graph.rebuild_pro_graph(case["case_id"])
    ctx.graph.create_hypothesis(case["case_id"], "Demo-Hypothese: Profil/Firma/Anker prüfen", "Öffentliche Treffer können einen Zusammenhang nahelegen; Gegenbelege und menschliche Review bleiben erforderlich.", confidence=0.55, supporting_evidence=[ev["evidence_id"]])
    ctx.timeline.build_from_evidence(case["case_id"])
    ctx.timeline.add_event(case["case_id"], "2026-06-02", "Demo-Treffer in Evidence Vault übernommen", source_evidence_id=ev["evidence_id"], event_type="evidence_capture", uncertainty_note="Demo-Zeitpunkt: Capture-/Übernahmezeitpunkt.")
    ctx.graph.build_analysis_narrative(case["case_id"])
    ctx.timeline.build_narrative(case["case_id"])
    ctx.risk.auto_assess_case(case["case_id"])
    ctx.ai_analyst.run_assistant_bundle(case["case_id"])
    ctx.export_control.evaluate_export(case["case_id"], "internal_report", notes="Demo-Exportprüfung")
    ctx.intelligence_gap.assess_case(case["case_id"], persist=True)
    ctx.query_intelligence.generate_for_case(case["case_id"], target["target_id"], profile_key="de_eu", notes="Demo Build 44 Query Intelligence")
    ctx.report_automation.generate_report_draft(case["case_id"], "redacted_client", "client_safe", notes="Demo Build 39 Evidence-to-Report Draft")
    return case


def main(argv=None):
    parser = argparse.ArgumentParser(description=BUILD_NAME)
    parser.add_argument("--selftest", action="store_true", help="führt Build-46-Selbsttest aus")
    parser.add_argument("--init-demo", action="store_true", help="legt Demo-Fall in lokaler Datenbank an")
    parser.add_argument("--no-gui", action="store_true", help="nur CLI, keine GUI starten")
    parser.add_argument("--gui", action="store_true", help="GUI explizit starten; Kompatibilitätsflag für Windows-Launcher")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args(argv)
    if args.selftest:
        print(json.dumps(run_selftest(args.base_dir), ensure_ascii=False, indent=2))
        return
    ctx = AppContext(base_dir=args.base_dir)
    if args.init_demo:
        case = create_demo_case(ctx)
        print(json.dumps({"gate":"DEMO_CASE_CREATED", "case_id": case["case_id"], "db_path": str(ctx.db.path)}, ensure_ascii=False, indent=2))
        if args.no_gui:
            ctx.close(); return
    ctx.close()
    if not args.no_gui:
        # Build 50.0: resilient startup. If the full GUI fails, a Safe-Mode/Pilot UI opens
        # and writes logs/startup_latest.log instead of silently closing.
        from eagleeye.bootstrap.startup import run_gui
        rc = run_gui(base_dir=args.base_dir)
        if rc:
            raise SystemExit(rc)

if __name__ == "__main__":
    main()
