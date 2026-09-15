from __future__ import annotations
from typing import Any, Dict
import inspect
import re

from eagleeye_pro.application.commands import Command
from eagleeye_pro.security_kernel.kernel import CommandEnvelope, SecurityKernel

class CommandBus:
    """Single Build 50.0 entry point for sensitive MVFPE operations."""

    def __init__(self, kernel: SecurityKernel, services: Dict[str, Any]):
        self.kernel = kernel
        self.services = services
        try:
            source = inspect.getsource(self._execute)
            known = set(re.findall(r'if name == ["\']([^"\']+)["\']', source))
            self.kernel.register_commands(known)
        except Exception:
            pass

    def dispatch(self, command: Command | str, payload: Dict[str, Any] | None = None, actor: str = "local-analyst") -> Dict[str, Any]:
        if isinstance(command, str):
            command = Command(command, payload or {}, actor)
        decision = self.kernel.authorize(CommandEnvelope(command.name, command.payload, command.actor))
        if decision.decision == "block":
            return {"ok": False, "decision": decision.as_dict(), "result": None}
        if decision.decision == "review_required" and not command.payload.get("override_review_gate"):
            return {"ok": False, "decision": decision.as_dict(), "result": None}
        result = self._execute(command)
        return {"ok": True, "decision": decision.as_dict(), "result": result}

    def _execute(self, command: Command) -> Any:
        name = command.name
        p = command.payload
        if name == "create_case":
            return self.services["cases"].create_case(p["title"], p.get("client", ""), p["purpose"], p["legal_basis"], jurisdiction=p.get("jurisdiction", "DE/EU"), risk_level=p.get("risk_level", "medium"), retention_until=p.get("retention_until", ""))
        if name == "list_cases":
            return self.services["cases"].list_cases()
        if name == "approve_legal_scope":
            return self.services["legal"].create_review(p["case_id"], p.get("purpose", "public person osint review"), p.get("legal_basis", "legitimate_interest"), p.get("necessity", "Manual public-source review needed for the defined case purpose."), p.get("balancing", "Public-only, review-first, minimized collection; no bypass or private account access."), approved=bool(p.get("approved", True)), review_level=p.get("review_level", "senior"), reviewer=p.get("reviewer", command.actor), notes=p.get("notes", ""))
        if name == "create_target":
            return self.services["targets"].create_target(p["case_id"], p["name"], aliases=p.get("aliases", ""), emails=p.get("emails", ""), usernames=p.get("usernames", ""), locations=p.get("locations", ""), companies=p.get("companies", ""), domains=p.get("domains", ""), notes=p.get("notes", ""))
        if name == "build_profile":
            return self.services["profile_engine"].build_profile(p["case_id"], p.get("profile_type", "redacted_profile"), p.get("outdir"))
        if name == "create_verified_claim":
            return self.services["profile_engine"].create_claim(
                p["case_id"], p["claim_type"], p["statement"],
                supporting_evidence=p.get("supporting_evidence"), contra_evidence=p.get("contra_evidence"),
                assessment_label=p.get("assessment_label", "plausibler öffentlicher Hinweis – menschliche Prüfung bleibt Pflicht"),
                reportability=p.get("reportability", "reportable_with_uncertainty"),
                uncertainty_note=p.get("uncertainty_note", ""), notes=p.get("notes", ""),
            )
        if name == "prepare_provider_run":
            return self.services["real_providers"].prepare_run(p["case_id"], p["connector_key"], p["query"], p.get("purpose", "public_osint"), p.get("target_id", ""), p.get("notes", ""))
        if name == "run_provider":
            budget = self.services["provider_budget"].check(p["connector_key"], consume=bool(p.get("execute_live")))
            if not budget["allowed"]:
                return {"status": "blocked_by_budget", "budget": budget}
            return self.services["real_providers"].run_connector(p["case_id"], p["connector_key"], p["query"], p.get("purpose", "public_osint"), p.get("target_id", ""), bool(p.get("execute_live")), p.get("sample_payload"), p.get("notes", ""))
        if name == "create_search_plan":
            return self.services["search_expander"].create_plan(
                p["case_id"], p.get("mode", "person"), p.get("seed") or {},
                p.get("target_id", ""), p.get("notes", "")
            )
        if name == "extract_public_document":
            if p.get("text") is not None:
                return self.services["document_extractor"].extract_from_text(
                    p.get("case_id", ""), p.get("text", ""), title=p.get("title", "public document"),
                    source_url=p.get("source_url", ""), document_type=p.get("document_type", "text"),
                    document_date=p.get("document_date", ""), notes=p.get("notes", "")
                )
            return self.services["document_extractor"].extract_from_file(
                p["case_id"], p["path"], source_url=p.get("source_url", ""),
                document_title=p.get("title", ""), document_date=p.get("document_date", ""), notes=p.get("notes", "")
            )
        if name == "stage_review_hit":
            return self.services["review_inbox_pro"].stage_hit(
                p["case_id"], p.get("source_object_type", "manual"), p.get("source_object_id", ""),
                title=p.get("title", "public candidate"), source_url=p.get("source_url", ""),
                summary=p.get("summary", ""), source_category=p.get("source_category", ""),
                priority=int(p.get("priority", 50))
            )
        if name == "update_review_checklist":
            return self.services["review_inbox_pro"].update_checklist(
                p["review_id"], p.get("updates") or {}, p.get("reviewer", command.actor), p.get("note", "")
            )
        if name == "set_review_stage":
            return self.services["review_inbox_pro"].set_stage(
                p["review_id"], p["stage"], p.get("reason", ""), p.get("reportability"), p.get("reviewer", command.actor)
            )
        if name == "ingest_evidence_text":
            return self.services["evidence_vault_50"].ingest_text_artifact(
                p["case_id"], p.get("title", "public artifact"), p.get("content", ""),
                source_url=p.get("source_url", ""), source_type=p.get("source_type", "public_document"),
                document_date=p.get("document_date", ""), classification=p.get("classification", "normal"),
                public_access_proof=p.get("public_access_proof", ""), linked_object_type=p.get("linked_object_type", ""),
                linked_object_id=p.get("linked_object_id", ""), notes=p.get("notes", ""), actor=command.actor,
            )
        if name == "update_evidence_review_status":
            return self.services["evidence_vault_50"].update_review_status(p["artifact_id"], p["review_status"], p.get("reason", ""), command.actor)
        if name == "verify_evidence_chain":
            return self.services["evidence_vault_50"].verify_chain(p["artifact_id"])
        if name == "assess_verification_pro":
            return self.services["verification_pro_50"].assess_case(p["case_id"], target_id=p.get("target_id", ""), profile_type=p.get("profile_type", "case"), notes=p.get("notes", ""))
        if name == "build_spearhead_profile":
            return self.services["spearhead_profile_50"].build(p["case_id"], p.get("profile_type", "authority_handover"))
        if name == "register_missing_child_case":
            return self.services["missing_child_50"].register(
                p["case_id"], p["child_name"], p["last_seen_time"], p["last_seen_place"],
                age_hint=p.get("age_hint", ""), last_confirmed_by=p.get("last_confirmed_by", ""),
                clothing_description=p.get("clothing_description", ""), risk_notes=p.get("risk_notes", ""),
                official_refs=p.get("official_refs"), public_notice_urls=p.get("public_notice_urls"), open_questions=p.get("open_questions"),
            )
        if name == "build_missing_child_brief":
            return self.services["missing_child_50"].build_situation_brief(p["case_id"])
        if name == "register_antisemitism_incident":
            return self.services["jewish_life_50"].register_incident(
                p["case_id"], p.get("incident_type", "other"), p.get("title", "antisemitism incident"),
                incident_time=p.get("incident_time", ""), incident_place=p.get("incident_place", ""),
                public_urls=p.get("public_urls"), evidence_artifacts=p.get("evidence_artifacts"), markers=p.get("markers"),
                risk_level=p.get("risk_level", "medium"), description=p.get("description", ""),
            )
        if name == "prepare_provider_sdk_run":
            return self.services["provider_sdk_50"].prepare(p["case_id"], p["connector_key"], p["query"], p.get("purpose", "public_osint"), bool(p.get("execute_live_requested", False)))
        if name == "rank_candidate":
            return self.services["precision_ranking_50"].rank_candidate(
                p["case_id"], p.get("object_type", "manual_candidate"), p.get("object_id", "manual"),
                text=p.get("text", ""), target=p.get("target"), source_category=p.get("source_category", ""), document_date=p.get("document_date", ""), url=p.get("url", ""),
            )
        if name == "rank_review_inbox":
            return self.services["precision_ranking_50"].rank_review_inbox(p["case_id"], int(p.get("limit", 200)))
        if name == "add_timeline_event_50":
            return self.services["link_analysis_50"].add_timeline_event(
                p["case_id"], p["event_time"], p["title"], description=p.get("description", ""), place=p.get("place", ""),
                source_object_type=p.get("source_object_type", ""), source_object_id=p.get("source_object_id", ""),
                confidence_label=p.get("confidence_label", "candidate"), uncertainty_note=p.get("uncertainty_note", ""),
            )
        if name == "add_link_edge_50":
            return self.services["link_analysis_50"].add_link(
                p["case_id"], p["source_label"], p["target_label"], p["relationship_type"],
                source_object_type=p["source_object_type"], source_object_id=p["source_object_id"],
                confidence_label=p.get("confidence_label", "candidate"), counter_evidence=p.get("counter_evidence"),
            )
        if name == "build_case_map_50":
            return self.services["link_analysis_50"].build_case_map(p["case_id"])
        if name == "create_handover_report":
            return self.services["handover_50"].create_report(
                p["case_id"], profile_id=p.get("profile_id", ""), report_type=p.get("report_type", "authority_handover"),
                recipient_class=p.get("recipient_class", "authority_or_meldestelle"), markdown=p.get("markdown", ""), profile=p.get("profile"),
            )
        if name == "create_investigation_entity":
            return self.services["case_cockpit_54"].create_entity(
                p["case_id"], p.get("entity_type", "person"), p["display_name"],
                known_names=p.get("known_names"), aliases=p.get("aliases"), dates=p.get("dates"),
                places=p.get("places") or p.get("locations"), organizations=p.get("organizations") or p.get("companies"),
                roles=p.get("roles"), identifiers=p.get("identifiers"), public_links=p.get("public_links") or p.get("links"),
                notes=p.get("notes", ""),
            )
        if name == "update_investigation_entity":
            return self.services["case_cockpit_54"].update_entity(p["entity_id"], **{k:v for k,v in p.items() if k != "entity_id"})
        if name == "get_case_cockpit_dashboard":
            return self.services["case_cockpit_54"].dashboard(p["case_id"])
        if name == "generate_cockpit_search_parameters":
            return self.services["case_cockpit_54"].generate_search_parameters(p["entity_id"])
        if name == "add_chain_seed":
            return self.services["search_chain_54"].add_node(p["case_id"], "seed_info", p["title"], p["value"], entity_id=p.get("entity_id", ""), metadata=p.get("metadata"), relevance_score=p.get("relevance_score", 80), confidence_label=p.get("confidence_label", "seed"))
        if name == "add_chain_query":
            return self.services["search_chain_54"].add_node(p["case_id"], "search_query", p["title"], p["query"], entity_id=p.get("entity_id", ""), parent_node_id=p.get("parent_node_id", ""), relation_type="generated_query", metadata={"engine": p.get("engine", "google"), "search_url": p.get("search_url", "")}, relevance_score=p.get("relevance_score", 70), confidence_label="planned")
        if name == "add_chain_finding":
            return self.services["search_chain_54"].add_finding(
                p["case_id"], p["query_node_id"], p["title"], p.get("url", ""), p.get("snippet", ""),
                entity_id=p.get("entity_id", ""), document_date=p.get("document_date", ""), source_category=p.get("source_category", "public_web"), relevance_score=p.get("relevance_score", 50),
            )
        if name == "include_chain_information":
            return self.services["search_chain_54"].include_information(p["finding_node_id"], p.get("included_facts") or [], reviewer=p.get("reviewer", command.actor))
        if name == "build_search_chain":
            return self.services["search_chain_54"].build_chain(p["case_id"], p.get("entity_id", ""))
        if name == "create_secure_case_package":
            return self.services["secure_storage_54"].create_package(p["case_id"], package_type=p.get("package_type", "sealed_case_package"), passphrase=p.get("passphrase", ""), include_reports=bool(p.get("include_reports", True)), include_evidence=bool(p.get("include_evidence", True)), notes=p.get("notes", ""))
        if name == "verify_secure_case_package":
            return self.services["secure_storage_54"].verify_package(p["package_id"])
        if name == "build_audit_hash_chain":
            return self.services["audit_hash_chain_54"].build_for_case(p.get("case_id", ""))
        if name == "verify_audit_hash_chain":
            return self.services["audit_hash_chain_54"].verify(p.get("case_id", ""))
        if name == "append_evidence_chain_64":
            return self.services["evidence_chain_64"].append_event(p["case_id"], p.get("source_type", "manual"), p.get("source_id", "manual"), p.get("payload") or {})
        if name == "build_evidence_chain_64":
            return self.services["evidence_chain_64"].build_from_audit(p["case_id"])
        if name == "verify_evidence_chain_64":
            return self.services["evidence_chain_64"].verify(p["case_id"])
        if name == "create_hypothesis":
            return self.services["analyst_quality_54"].create_hypothesis(p["case_id"], p["title"], p["hypothesis_text"], supporting_nodes=p.get("supporting_nodes"), counter_nodes=p.get("counter_nodes"), open_questions=p.get("open_questions"))
        if name == "evaluate_analyst_quality":
            return self.services["analyst_quality_54"].evaluate_case(p["case_id"])
        if name == "evaluate_quality_control_65":
            return self.services["quality_control_65"].evaluate_workspace(p["case_id"], p.get("entity_id", ""), p.get("workspace") or {}, persist=bool(p.get("persist", True)))
        if name == "create_collaboration_bundle":
            return self.services["collaboration_54"].create_bundle(p["case_id"], bundle_type=p.get("bundle_type", "authority_handover_package"), recipient_class=p.get("recipient_class", "authority_or_meldestelle"), redaction_level=p.get("redaction_level", "redacted"), notes=p.get("notes", ""))
        if name == "verify_collaboration_bundle":
            return self.services["collaboration_54"].verify_bundle(p["bundle_id"])
        if name == "assess_privacy_export_55":
            return self.services["privacy_finish_55"].assess_export(
                p["case_id"], entity_id=p.get("entity_id", ""), draft_id=p.get("draft_id", ""),
                recipient_class=p.get("recipient_class", "authority_or_meldestelle"),
                redaction_level=p.get("redaction_level", "redacted"), text=p.get("text", ""),
            )
        if name == "redact_text_55":
            return self.services["privacy_finish_55"].redact_text(p.get("text", ""), level=p.get("level", "redacted"))
        if name == "create_retention_review_55":
            return self.services["privacy_finish_55"].create_retention_review(p["case_id"])
        if name == "run_stable_audit_55":
            return self.services["stable_release_55"].run_static_audit(p.get("root_dir"))
        if name == "run_release_gate":
            return self.services["release_gate"].run_checks(p.get("root_dir"), p.get("create_manifest", True))
        if name == "build_spearhead_architecture_66":
            return self.services["spearhead_architecture_66"].build_blueprint(p.get("case_id", ""), p.get("goal", "top_tier_person_osint_platform"), p.get("current_state") or {}, persist=bool(p.get("persist", True)))
        if name == "assess_spearhead_maturity_66":
            return self.services["spearhead_architecture_66"].assess_maturity(p.get("current_state") or {})
        if name == "list_source_adapter_specs_67":
            return self.services["source_adapter_architecture_67"].list_specs()
        if name == "register_source_adapter_spec_67":
            return self.services["source_adapter_architecture_67"].register_spec(p["key"], p["name"], p["category"], p.get("execution_mode", "manual_or_approved_provider"), inputs=p.get("inputs") or [], outputs=p.get("outputs") or [], gates=p.get("gates"), forbidden_features=p.get("forbidden_features") or [])
        if name == "add_graph_node_68":
            return self.services["graph_workspace_68"].add_node(p["case_id"], p["node_type"], p["label"], value=p.get("value", ""), confidence=int(p.get("confidence", 50)), sensitivity=p.get("sensitivity", "normal"), source_ref=p.get("source_ref", ""), metadata=p.get("metadata") or {})
        if name == "add_graph_edge_68":
            return self.services["graph_workspace_68"].add_edge(p["case_id"], p["source_node_id"], p["target_node_id"], p["edge_type"], confidence=int(p.get("confidence", 50)), review_status=p.get("review_status", "candidate"), evidence_ref=p.get("evidence_ref", ""), metadata=p.get("metadata") or {})
        if name == "build_graph_workspace_68":
            return self.services["graph_workspace_68"].build_graph(p["case_id"])
        if name == "record_text_capture_69":
            return self.services["capture_vault_69"].record_text_capture(p.get("case_id", ""), p["url"], p.get("title", "public capture"), p.get("text", ""), html=p.get("html", ""), screenshot_hash=p.get("screenshot_hash", ""), metadata=p.get("metadata") or {}, persist_text=bool(p.get("persist_text", True)))
        if name == "verify_capture_artifact_69":
            return self.services["capture_vault_69"].verify_artifact(p["artifact_id"])
        if name == "build_analyst_cockpit_70":
            return self.services["analyst_cockpit_70"].build_dashboard(p["case_id"], entity_id=p.get("entity_id", ""), persist=bool(p.get("persist", True)))
        if name == "build_analyst_workspace_71":
            return self.services["analyst_workspace_ui_71"].build_workspace(p["case_id"], entity_id=p.get("entity_id", ""), persist=bool(p.get("persist", True)), export_files=bool(p.get("export_files", True)))
        if name == "latest_analyst_workspace_71":
            return self.services["analyst_workspace_ui_71"].latest(p["case_id"])
        if name == "review_graph_edge_72":
            return self.services["workspace_actions_72"].review_graph_edge(p["case_id"], p["edge_id"], p["status"], reason=p.get("reason", ""), actor=command.actor)
        if name == "verify_capture_72":
            return self.services["workspace_actions_72"].verify_capture(p["case_id"], p["artifact_id"], actor=command.actor, reason=p.get("reason", ""))
        if name == "review_claim_72":
            return self.services["workspace_actions_72"].create_or_update_claim_review(p["case_id"], p["statement"], status=p.get("status", "unverified_hint"), entity_id=p.get("entity_id", ""), support_refs=p.get("support_refs") or [], contra_refs=p.get("contra_refs") or [], actor=command.actor, reason=p.get("reason", ""), claim_id=p.get("claim_id", ""))
        if name == "set_export_gate_72":
            return self.services["workspace_actions_72"].set_export_gate(p["case_id"], export_mode=p.get("export_mode", "internal_redacted"), decision=p.get("decision", "review_required"), reasons=p.get("reasons") or [], entity_id=p.get("entity_id", ""), actor=command.actor)
        if name == "list_workspace_actions_72":
            return self.services["workspace_actions_72"].list_actions(p["case_id"])
        if name == "index_case_db_73":
            return self.services["persistent_case_db_73"].index_existing_case(p["case_id"])
        if name == "case_db_summary_73":
            return self.services["persistent_case_db_73"].case_summary(p["case_id"])
        if name == "upsert_case_object_73":
            return self.services["persistent_case_db_73"].upsert_object(p["case_id"], p["object_type"], p["label"], data=p.get("data") or {}, status=p.get("status", "active"), source_table=p.get("source_table", ""), source_id=p.get("source_id", ""))
        if name == "capture_snapshot_74":
            return self.services["real_capture_engine_74"].capture_snapshot(p.get("case_id", ""), p["url"], html=p.get("html", ""), text=p.get("text", ""), title=p.get("title", ""), http_status=int(p.get("http_status", 0) or 0), content_type=p.get("content_type", "text/html"), metadata=p.get("metadata") or {})
        if name == "verify_real_capture_74":
            return self.services["real_capture_engine_74"].verify_capture(p["capture_id"])
        if name == "list_real_captures_74":
            return self.services["real_capture_engine_74"].list_case_captures(p["case_id"])
        if name == "ingest_evidence_text_75":
            return self.services["local_evidence_vault_75"].ingest_text(p["case_id"], p.get("title", "public evidence text"), p.get("text", ""), artifact_type=p.get("artifact_type", "text_note"), source_ref=p.get("source_ref", ""), linked_object_type=p.get("linked_object_type", ""), linked_object_id=p.get("linked_object_id", ""), metadata=p.get("metadata") or {})
        if name == "ingest_evidence_file_75":
            return self.services["local_evidence_vault_75"].ingest_file(p["case_id"], p["path"], title=p.get("title", "public evidence file"), artifact_type=p.get("artifact_type", "file"), source_ref=p.get("source_ref", ""), linked_object_type=p.get("linked_object_type", ""), linked_object_id=p.get("linked_object_id", ""), metadata=p.get("metadata") or {})
        if name == "verify_evidence_item_75":
            return self.services["local_evidence_vault_75"].verify_item(p["evidence_id"])
        if name == "list_evidence_items_75":
            return self.services["local_evidence_vault_75"].list_case_items(p["case_id"])
        if name == "render_graph_ui_76":
            return self.services["graph_ui_76"].render(p["case_id"], title=p.get("title", "Investigation Graph"), persist=bool(p.get("persist", True)))
        if name == "latest_graph_ui_76":
            return self.services["graph_ui_76"].latest(p["case_id"])
        if name == "generate_pivots_77":
            return self.services["pivot_engine_77"].generate(p["case_id"], p["seed_type"], p["seed_value"], metadata=p.get("metadata") or {})
        if name == "list_pivots_77":
            return self.services["pivot_engine_77"].list(p["case_id"])
        if name == "assess_identity_v3_78":
            return self.services["identity_resolution_v3_78"].assess(p["case_id"], p["subject_label"], p["candidate_label"], positive_signals=p.get("positive_signals") or [], conflict_signals=p.get("conflict_signals") or [], notes=p.get("notes", ""))
        if name == "list_identity_assessments_78":
            return self.services["identity_resolution_v3_78"].list(p["case_id"])
        if name == "add_counter_evidence_79":
            return self.services["counter_evidence_79"].add(p["case_id"], p["claim_ref"], p["title"], p["description"], severity=p.get("severity", "medium"), source_ref=p.get("source_ref", ""), metadata=p.get("metadata") or {})
        if name == "evaluate_claim_counter_evidence_79":
            return self.services["counter_evidence_79"].evaluate(p["case_id"], p["claim_ref"], statement=p.get("statement", ""), support_refs=p.get("support_refs") or [], contra_refs=p.get("contra_refs") or [])
        if name == "list_counter_evidence_79":
            return self.services["counter_evidence_79"].list(p["case_id"])
        if name == "build_claim_v3_80":
            return self.services["claim_engine_v3_80"].build(p["case_id"], p["statement"], support_refs=p.get("support_refs") or [], contra_refs=p.get("contra_refs") or [], identity_assessment=p.get("identity_assessment") or {}, metadata=p.get("metadata") or {})
        if name == "review_claim_v3_80":
            return self.services["claim_engine_v3_80"].review(p["claim_id"], p["status"], reason=p.get("reason", ""), actor=command.actor)
        if name == "list_claims_v3_80":
            return self.services["claim_engine_v3_80"].list(p["case_id"])
        if name == "claim_matrix_v3_80":
            return self.services["claim_engine_v3_80"].matrix(p["case_id"])
        if name == "list_source_adapters_104":
            return self.services["source_adapter_execution_104"].list_adapters()
        if name == "source_adapter_readiness_104":
            return self.services["source_adapter_execution_104"].readiness(p.get("case_id", ""))
        if name == "execute_source_adapter_104":
            # Build 104.1 compatibility route: the historical command now enters through
            # the typed Connector SDK and then delegates to the proven Build-104 backend.
            return self.services["core_recomposition_104_1"].connectors.execute(
                case_id=p.get("case_id", ""), connector_id=p["adapter_id"], input_value=p["input_value"],
                options=p.get("options") or {},
                explicit_live_confirmation=bool(p.get("explicit_live_confirmation")),
                actor=command.actor,
            )
        if name == "list_source_adapter_executions_104":
            return self.services["source_adapter_execution_104"].list_executions(p.get("case_id", ""), int(p.get("limit", 100)))
        if name == "get_source_adapter_execution_104":
            return self.services["source_adapter_execution_104"].get_execution(p["execution_id"])
        if name == "verify_source_adapter_execution_104":
            return self.services["source_adapter_execution_104"].verify_execution(p["execution_id"])
        if name == "core_status_104_1":
            return self.services["core_recomposition_104_1"].status(p.get("case_id", ""))
        if name == "core_intake_104_1":
            return self.services["core_recomposition_104_1"].include_finding(**p)
        if name == "list_connectors_104_1":
            return self.services["core_recomposition_104_1"].connectors.list_connectors()
        if name == "execute_connector_104_1":
            return self.services["core_recomposition_104_1"].connectors.execute(
                case_id=p.get("case_id", ""), connector_id=p["connector_id"], input_value=p["input_value"],
                options=p.get("options") or {}, explicit_live_confirmation=bool(p.get("explicit_live_confirmation", False)), actor=command.actor,
            )
        if name == "collection_profiles_105":
            return self.services["collection_engine_105"].profiles()
        if name == "collection_readiness_105":
            return self.services["collection_engine_105"].readiness()
        if name == "create_collection_job_105":
            return self.services["collection_engine_105"].create_job(p)
        if name == "start_collection_job_105":
            return self.services["collection_engine_105"].start_background(p["job_id"])
        if name == "run_collection_job_105":
            return self.services["collection_engine_105"].execute_job(p["job_id"])
        if name == "cancel_collection_job_105":
            return self.services["collection_engine_105"].cancel_job(p["job_id"])
        if name == "get_collection_job_105":
            return self.services["collection_engine_105"].get_job(p["job_id"])
        if name == "list_collection_jobs_105":
            return self.services["collection_engine_105"].list_jobs(p.get("case_id", ""), int(p.get("limit", 100)))
        if name == "browser_capture_105":
            return self.services["collection_engine_105"].capture_browser(p)
        if name == "plan_search_81":
            return self.services["search_adapter_81"].plan(p["case_id"], p["query"], engines=p.get("engines"), target_ref=p.get("target_ref", ""))
        if name == "import_search_result_81":
            return self.services["search_adapter_81"].import_result(p["case_id"], p["title"], p["url"], snippet=p.get("snippet", ""), plan_id=p.get("plan_id", ""), metadata=p.get("metadata") or {})
        if name == "list_search_results_81":
            return self.services["search_adapter_81"].list_results(p["case_id"])
        if name == "prepare_web_archive_82":
            return self.services["web_archive_adapter_82"].prepare(p.get("case_id", ""), p["url"], timestamp_hint=p.get("timestamp_hint", ""), metadata=p.get("metadata") or {})
        if name == "list_web_archives_82":
            return self.services["web_archive_adapter_82"].list(p["case_id"])
        if name == "prepare_domain_lookup_83":
            return self.services["rdap_dns_intel_83"].prepare_lookup(p["case_id"], p["domain"])
        if name == "import_domain_intel_83":
            return self.services["rdap_dns_intel_83"].import_payload(p["case_id"], p["domain"], p["intel_type"], p.get("payload") or {})
        if name == "list_domain_intel_83":
            return self.services["rdap_dns_intel_83"].list(p["case_id"])
        if name == "prepare_code_profile_84":
            return self.services["public_code_profile_84"].prepare_profile(p["case_id"], p["platform"], p["username"])
        if name == "import_code_profile_84":
            return self.services["public_code_profile_84"].import_profile(p["case_id"], p["platform"], p["username"], profile_url=p.get("profile_url", ""), payload=p.get("payload") or {})
        if name == "list_code_profiles_84":
            return self.services["public_code_profile_84"].list(p["case_id"])
        if name == "analyze_public_document_text_85":
            return self.services["public_document_intel_85"].analyze_text(p["case_id"], p["title"], p.get("text", ""), source_url=p.get("source_url", ""), document_type=p.get("document_type", "text"), metadata=p.get("metadata") or {})
        if name == "analyze_public_document_file_85":
            return self.services["public_document_intel_85"].analyze_file(p["case_id"], p["path"], title=p.get("title", ""), source_url=p.get("source_url", ""), metadata=p.get("metadata") or {})
        if name == "list_public_documents_85":
            return self.services["public_document_intel_85"].list(p["case_id"])
        if name == "build_case_dashboard_86":
            return self.services["case_dashboard_v2_86"].build(p["case_id"], persist=bool(p.get("persist", True)))
        if name == "latest_case_dashboard_86":
            return self.services["case_dashboard_v2_86"].latest(p["case_id"])
        if name == "add_timeline_event_87":
            return self.services["investigation_timeline_87"].add_event(p["case_id"], p["event_time"], p["title"], description=p.get("description", ""), time_type=p.get("time_type", "event_time"), source_ref=p.get("source_ref", ""), confidence=p.get("confidence", "candidate"), review_status=p.get("review_status", "candidate"), metadata=p.get("metadata") or {})
        if name == "build_timeline_87":
            return self.services["investigation_timeline_87"].build(p["case_id"], include_derived=bool(p.get("include_derived", True)))
        if name == "build_review_board_88":
            return self.services["review_board_v2_88"].board(p["case_id"])
        if name == "decide_review_88":
            return self.services["review_board_v2_88"].decide(p["case_id"], p["object_type"], p["object_id"], p["decision"], reason=p.get("reason", ""), actor=command.actor, metadata=p.get("metadata") or {})
        if name == "build_report_pro_89":
            return self.services["report_builder_pro_89"].build(p["case_id"], report_type=p.get("report_type", "long_report"), export_mode=p.get("export_mode", "internal_redacted"), title=p.get("title", ""), persist=bool(p.get("persist", True)))
        if name == "latest_report_pro_89":
            return self.services["report_builder_pro_89"].latest(p["case_id"])
        if name == "build_casefile_pro_90":
            return self.services["casefile_pro_90"].build(p["case_id"], export_mode=p.get("export_mode", "authority_redacted"), include_evidence_files=bool(p.get("include_evidence_files", False)))
        if name == "verify_casefile_pro_90":
            return self.services["casefile_pro_90"].verify(p["package_id"])
        if name == "latest_casefile_pro_90":
            return self.services["casefile_pro_90"].latest(p["case_id"])
        if name == "include_url_91":
            return self.services["copy_paste_intake_91"].include_url(p.get("case_id", ""), p["url"], title=p.get("title", ""), note=p.get("note", ""), snippet=p.get("snippet", ""), html=p.get("html", ""), text=p.get("text", ""), target_ref=p.get("target_ref", ""), metadata=p.get("metadata") or {})
        if name == "include_pasted_text_91":
            return self.services["copy_paste_intake_91"].include_text(p.get("case_id", ""), p.get("text", ""), title=p.get("title", "Pasted public finding"), source_url=p.get("source_url", ""), metadata=p.get("metadata") or {})
        if name == "list_pasted_findings_91":
            return self.services["copy_paste_intake_91"].list(p.get("case_id", ""), int(p.get("limit", 100)))
        if name == "intake_include_101":
            return self.services["intake_console_101"].include(case_id=p.get("case_id", ""), url=p.get("url", ""), text=p.get("text", ""), html_snapshot=p.get("html_snapshot", p.get("html", "")), title=p.get("title", ""), note=p.get("note", ""), snippet=p.get("snippet", ""), source_label=p.get("source_label", ""), run_security=bool(p.get("run_security", True)), run_ai_triage=bool(p.get("run_ai_triage", True)))
        if name == "intake_recent_101":
            return self.services["intake_console_101"].recent(p.get("case_id", ""), int(p.get("limit", 25)))
        if name == "intake_render_html_101":
            return self.services["intake_console_101"].render_html(case_id=p.get("case_id", ""), message=p.get("message", ""), result=p.get("result"))
        if name == "local_ai_status_101":
            return self.services["local_ai_agent_101"].status()
        if name == "local_ai_case_context_101":
            return self.services["local_ai_agent_101"].build_case_context(p["case_id"])
        if name == "local_ai_suggest_next_steps_101":
            return self.services["local_ai_agent_101"].suggest_next_steps(p["case_id"], p.get("prompt", ""))
        if name == "local_ai_triage_paste_101":
            return self.services["local_ai_agent_101"].triage_pasted_finding(p["case_id"], p["paste_id"])
        if name == "local_ai_runs_101":
            return self.services["local_ai_agent_101"].list_runs(p["case_id"], int(p.get("limit", 20)))
        if name == "browser_capture_102":
            return self.services["browser_capture_bridge_102"].capture_from_browser(case_id=p.get("case_id", ""), url=p["url"], title=p.get("title", ""), visible_text=p.get("visible_text", p.get("text", "")), html_snapshot=p.get("html_snapshot", p.get("html", "")), screenshot_path=p.get("screenshot_path", ""), source_label=p.get("source_label", "browser_manual_public_capture"), notes=p.get("notes", ""), run_security=bool(p.get("run_security", True)), run_ai_triage=bool(p.get("run_ai_triage", True)), metadata=p.get("metadata") or {})
        if name == "browser_capture_file_102":
            return self.services["browser_capture_bridge_102"].capture_from_file(case_id=p.get("case_id", ""), url=p["url"], file_path=p["file_path"], title=p.get("title", ""), source_label=p.get("source_label", "browser_saved_file"), notes=p.get("notes", ""), metadata=p.get("metadata") or {})
        if name == "browser_capture_list_102":
            return self.services["browser_capture_bridge_102"].list(case_id=p.get("case_id", ""), limit=int(p.get("limit", 50)))
        if name == "browser_capture_verify_102":
            return self.services["browser_capture_bridge_102"].verify(p["bridge_capture_id"])
        if name == "browser_capture_render_html_102":
            return self.services["browser_capture_bridge_102"].render_html(case_id=p.get("case_id", ""), message=p.get("message", ""), result=p.get("result"))
        if name == "assess_gdpr_91":
            return self.services["gdpr_compliance_91"].assess(p["case_id"], purpose=p.get("purpose", "public person osint review"), lawful_basis=p.get("lawful_basis", "legitimate_interest"), data_classes=p.get("data_classes") or ["public_low", "public_personal"], export_mode=p.get("export_mode", "internal_redacted"), retention_days=int(p.get("retention_days", 90)), rationale=p.get("rationale", ""))
        if name == "latest_gdpr_91":
            return self.services["gdpr_compliance_91"].latest(p["case_id"])
        if name == "evaluate_guardrail_92":
            return self.services["ethical_guardrails_92"].evaluate(p["case_id"], p.get("action_type", "review"), subject=p.get("subject", ""), context=p.get("context") or {})
        if name == "list_guardrails_92":
            return self.services["ethical_guardrails_92"].list(p["case_id"])
        if name == "list_training_scenarios_93":
            return self.services["analyst_training_93"].scenarios()
        if name == "start_training_93":
            return self.services["analyst_training_93"].start(p["case_id"], p["scenario_key"], analyst=p.get("analyst", command.actor))
        if name == "grade_training_93":
            return self.services["analyst_training_93"].grade(p["case_id"], p["scenario_key"], p.get("answers") or {}, analyst=p.get("analyst", command.actor))
        if name == "add_team_member_94":
            return self.services["team_workflow_94"].add_member(p["display_name"], p.get("role", "reviewer"), email=p.get("email", ""))
        if name == "assign_review_94":
            return self.services["team_workflow_94"].assign_review(p["case_id"], p["object_type"], p["object_id"], p["assigned_to"], required_role=p.get("required_role", "reviewer"), due_at=p.get("due_at", ""), notes=p.get("notes", ""))
        if name == "decide_assignment_94":
            return self.services["team_workflow_94"].decide(p["assignment_id"], p["decision"], actor=command.actor)
        if name == "lock_case_94":
            return self.services["team_workflow_94"].lock_case(p["case_id"], p.get("locked_by", command.actor), p.get("reason", "manual lock"))
        if name == "release_case_lock_94":
            return self.services["team_workflow_94"].release_lock(p["case_id"], actor=command.actor)
        if name == "team_board_94":
            return self.services["team_workflow_94"].board(p["case_id"])
        if name == "create_deployment_profile_95":
            return self.services["enterprise_deployment_95"].create_profile(p.get("name", "Local EagleEye Deployment"), mode=p.get("mode", "local_single_user"), settings=p.get("settings") or {})
        if name == "plan_backup_95":
            return self.services["enterprise_deployment_95"].plan_backup(case_id=p.get("case_id", ""), destination=p.get("destination", "local_backup"), include_evidence=bool(p.get("include_evidence", True)), include_reports=bool(p.get("include_reports", True)), encryption_required=bool(p.get("encryption_required", True)))
        if name == "deployment_readiness_95":
            return self.services["enterprise_deployment_95"].readiness()
        if name == "analyze_graph_96":
            return self.services["advanced_graph_analytics_96"].analyze(p["case_id"])
        if name == "latest_graph_analytics_96":
            return self.services["advanced_graph_analytics_96"].latest(p["case_id"])
        if name == "suggest_ai_assist_97":
            return self.services["ai_assisted_analyst_97"].suggest(p["case_id"], assist_type=p.get("assist_type", "hypothesis_review"), prompt=p.get("prompt", ""), context=p.get("context") or {})
        if name == "list_ai_assists_97":
            return self.services["ai_assisted_analyst_97"].list(p["case_id"])
        if name == "rate_source_98":
            return self.services["source_reliability_98"].rate(p["case_id"], p.get("source_ref", "manual"), source_type=p.get("source_type", "paste_or_unknown"), factors=p.get("factors") or {})
        if name == "list_source_ratings_98":
            return self.services["source_reliability_98"].latest_for_case(p["case_id"])
        if name == "build_authority_package_99":
            return self.services["authority_ready_99"].build(p["case_id"], export_mode=p.get("export_mode", "authority_redacted"))
        if name == "latest_authority_package_99":
            return self.services["authority_ready_99"].latest(p["case_id"])
        if name == "assess_security_complex_100":
            return self.services["security_complex_100"].assess_case_security(p["case_id"], scope=p.get("scope", "full_case"))
        if name == "security_event_100":
            return self.services["security_complex_100"].log_event(p["case_id"], p.get("event_type", "manual_security_note"), severity=p.get("severity", "info"), object_ref=p.get("object_ref", ""), details=p.get("details") or {})
        if name == "spearhead_beta_readiness_100":
            return self.services["security_complex_100"].spearhead_beta_readiness(p["case_id"])


        if name == "graph_workspace_build_103":
            return self.services["interactive_graph_workspace_103"].build_workspace(p.get("case_id", ""), sync_sources=bool(p.get("sync_sources", True)), persist=bool(p.get("persist", True)))
        if name == "graph_workspace_latest_103":
            return self.services["interactive_graph_workspace_103"].latest(p.get("case_id", ""))
        if name == "graph_workspace_sync_103":
            return self.services["interactive_graph_workspace_103"].sync_from_sources(p.get("case_id", ""))
        if name == "graph_workspace_add_node_103":
            return self.services["interactive_graph_workspace_103"].add_node(p.get("case_id", ""), p["node_type"], p["label"], value=p.get("value", ""), confidence=int(p.get("confidence", 50)), sensitivity=p.get("sensitivity", "normal"), source_ref=p.get("source_ref", ""), metadata=p.get("metadata") or {})
        if name == "graph_workspace_add_edge_103":
            return self.services["interactive_graph_workspace_103"].add_edge(p.get("case_id", ""), p["source_node_id"], p["target_node_id"], p["edge_type"], confidence=int(p.get("confidence", 50)), review_status=p.get("review_status", "candidate"), evidence_ref=p.get("evidence_ref", ""), metadata=p.get("metadata") or {})
        if name == "graph_workspace_review_edge_103":
            return self.services["interactive_graph_workspace_103"].review_edge(p.get("case_id", ""), p["edge_id"], p["decision"], reason=p.get("reason", ""), actor=command.actor)
        if name == "graph_workspace_html_103":
            return self.services["interactive_graph_workspace_103"].render_html(case_id=p.get("case_id", ""), message=p.get("message", ""), result=p.get("result"))
        if name == "platform_list_cases_103_1":
            return self.services["platform_103_1"].list_cases()
        if name == "platform_create_case_103_1":
            return self.services["platform_103_1"].create_case(p["title"], p["purpose"], p["legal_basis"], client=p.get("client", "Local Analyst"))
        if name == "platform_select_case_103_1":
            return self.services["platform_103_1"].select_case(p["case_id"])
        if name == "platform_active_case_103_1":
            return self.services["platform_103_1"].active_case()
        if name == "platform_intake_103_1":
            return self.services["platform_103_1"].include_finding(case_id=p.get("case_id", ""), url=p.get("url", ""), text=p.get("text", ""), html_snapshot=p.get("html_snapshot", ""), title=p.get("title", ""), source_label=p.get("source_label", "unified_workspace"), notes=p.get("notes", ""), screenshot_path=p.get("screenshot_path", ""), input_kind=p.get("input_kind", "paste"), run_security=bool(p.get("run_security", True)), run_ai_triage=bool(p.get("run_ai_triage", True)), metadata=p.get("metadata") or {})
        if name == "platform_dashboard_103_1":
            return self.services["platform_103_1"].dashboard(p.get("case_id", ""))
        if name == "platform_list_captures_103_1":
            return self.services["platform_103_1"].list_captures(p.get("case_id", ""), int(p.get("limit", 100)))
        if name == "platform_list_findings_103_1":
            return self.services["platform_103_1"].list_findings(p.get("case_id", ""), int(p.get("limit", 100)))
        if name == "platform_review_finding_103_1":
            return self.services["platform_103_1"].review_finding(p["finding_id"], p["decision"], p.get("reason", ""), command.actor)
        if name == "platform_verify_capture_103_1":
            return self.services["platform_103_1"].verify_capture(p["capture_id"])
        if name == "platform_export_casefile_103_1":
            return self.services["platform_103_1"].export_casefile(p.get("case_id", ""), p.get("export_mode", "authority_redacted"))

        raise ValueError(f"Unbekannter Command: {name}")
