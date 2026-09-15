from __future__ import annotations
import hashlib, json
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS person_document_profiles_273(
 profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
 country_code TEXT NOT NULL, country_name TEXT NOT NULL, birth_place TEXT NOT NULL,
 language_hints_json TEXT NOT NULL, country_basis TEXT NOT NULL, research_scope TEXT NOT NULL,
 allow_sensitive_public_records INTEGER NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL,
 created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(target_id,revision_no)
);
CREATE INDEX IF NOT EXISTS idx_pdprofile273_case ON person_document_profiles_273(case_id,target_id);

CREATE TABLE IF NOT EXISTS country_source_catalog_273(
 source_id TEXT PRIMARY KEY, country_code TEXT NOT NULL, country_name TEXT NOT NULL, language TEXT NOT NULL,
 source_class TEXT NOT NULL, source_name TEXT NOT NULL, base_domain TEXT NOT NULL, query_template TEXT NOT NULL,
 access_mode TEXT NOT NULL, auto_query_allowed INTEGER NOT NULL, privacy_class TEXT NOT NULL, notes TEXT NOT NULL,
 review_status TEXT NOT NULL, reviewed_by TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_countrycat273_country ON country_source_catalog_273(country_code,auto_query_allowed,source_class);

CREATE TABLE IF NOT EXISTS person_manual_source_tasks_273(
 task_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT NOT NULL,
 source_id TEXT NOT NULL, source_name TEXT NOT NULL, objective TEXT NOT NULL, access_mode TEXT NOT NULL,
 status TEXT NOT NULL, requires_user_action INTEGER NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(profile_id,source_id)
);

CREATE TABLE IF NOT EXISTS document_candidates_273(
 document_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, parent_run_id TEXT NOT NULL, observed_run_id TEXT NOT NULL,
 target_id TEXT NOT NULL, evidence_ref TEXT NOT NULL, url TEXT NOT NULL, canonical_url TEXT NOT NULL,
 title TEXT NOT NULL, normalized_title TEXT NOT NULL, document_type TEXT NOT NULL, source_class TEXT NOT NULL,
 country_code TEXT NOT NULL, language TEXT NOT NULL, access_mode TEXT NOT NULL, sensitivity_class TEXT NOT NULL,
 original_snippet TEXT NOT NULL, translated_summary_de TEXT NOT NULL, translation_engine TEXT NOT NULL,
 translation_status TEXT NOT NULL, translation_uncertainties_json TEXT NOT NULL, publication_date TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,parent_run_id,evidence_ref)
);
CREATE INDEX IF NOT EXISTS idx_doccand273_run ON document_candidates_273(case_id,parent_run_id,document_type);

CREATE TABLE IF NOT EXISTS document_families_273(
 family_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, parent_run_id TEXT NOT NULL, target_id TEXT NOT NULL,
 revision_no INTEGER NOT NULL, family_key TEXT NOT NULL, document_type TEXT NOT NULL,
 member_document_ids_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, source_hosts_json TEXT NOT NULL,
 version_count INTEGER NOT NULL, language_set_json TEXT NOT NULL, earliest_date TEXT NOT NULL, latest_date TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 UNIQUE(case_id,parent_run_id,revision_no,family_key)
);
CREATE INDEX IF NOT EXISTS idx_docfam273_run ON document_families_273(case_id,parent_run_id,revision_no);

CREATE TABLE IF NOT EXISTS document_references_273(
 reference_id TEXT PRIMARY KEY, family_id TEXT NOT NULL, document_id TEXT NOT NULL, case_id TEXT NOT NULL,
 reference_type TEXT NOT NULL, reference_value TEXT NOT NULL, source_context TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS person_document_briefs_273(
 brief_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, case_id TEXT NOT NULL, parent_run_id TEXT NOT NULL,
 target_id TEXT NOT NULL, revision_no INTEGER NOT NULL, person_name TEXT NOT NULL, country_context TEXT NOT NULL,
 document_count INTEGER NOT NULL, family_count INTEGER NOT NULL, source_class_count INTEGER NOT NULL,
 country_count INTEGER NOT NULL, language_count INTEGER NOT NULL, document_type_counts_json TEXT NOT NULL,
 source_coverage_json TEXT NOT NULL, key_facts_json TEXT NOT NULL, summary_de TEXT NOT NULL, caveats_json TEXT NOT NULL,
 status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pdbrief273_case ON person_document_briefs_273(case_id,parent_run_id,revision_no);

CREATE TABLE IF NOT EXISTS person_document_reviews_273(
 review_id TEXT PRIMARY KEY, brief_id TEXT NOT NULL, case_id TEXT NOT NULL, decision TEXT NOT NULL,
 rationale TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_safety_audits_273(
 audit_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, parent_run_id TEXT NOT NULL, document_id TEXT NOT NULL,
 source_mode TEXT NOT NULL, remote_content_executed INTEGER NOT NULL, automatic_download INTEGER NOT NULL,
 active_content_execution INTEGER NOT NULL, external_resource_loading INTEGER NOT NULL, embedded_payload_execution INTEGER NOT NULL,
 local_build255_assessment TEXT NOT NULL, controlled_source INTEGER NOT NULL, identifiers_redacted INTEGER NOT NULL,
 decision TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_document_corpus_benchmarks_273(
 benchmark_id TEXT PRIMARY KEY, task_family TEXT NOT NULL, input_summary TEXT NOT NULL, expected_class TEXT NOT NULL,
 expected_decision TEXT NOT NULL, review_status TEXT NOT NULL, reviewed_by TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opsec_controls_273(
 control_id TEXT PRIMARY KEY, control_name TEXT NOT NULL, enforcement TEXT NOT NULL, required_value TEXT NOT NULL,
 review_status TEXT NOT NULL, verified_by TEXT NOT NULL, row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS build273_events(
 event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL, object_type TEXT NOT NULL,
 object_id TEXT NOT NULL, actor TEXT NOT NULL, payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS trg_pdprofile273_no_update BEFORE UPDATE ON person_document_profiles_273 BEGIN SELECT RAISE(ABORT,'person_document_profiles_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_doccand273_no_update BEFORE UPDATE ON document_candidates_273 BEGIN SELECT RAISE(ABORT,'document_candidates_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_doccand273_no_delete BEFORE DELETE ON document_candidates_273 BEGIN SELECT RAISE(ABORT,'document_candidates_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docfam273_no_update BEFORE UPDATE ON document_families_273 BEGIN SELECT RAISE(ABORT,'document_families_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_pdbrief273_no_update BEFORE UPDATE ON person_document_briefs_273 BEGIN SELECT RAISE(ABORT,'person_document_briefs_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_docsafe273_no_update BEFORE UPDATE ON document_safety_audits_273 BEGIN SELECT RAISE(ABORT,'document_safety_audits_273 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt273_no_update BEFORE UPDATE ON build273_events BEGIN SELECT RAISE(ABORT,'build273_events immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt273_no_delete BEFORE DELETE ON build273_events BEGIN SELECT RAISE(ABORT,'build273_events immutable'); END;
"""

# access_mode values are policy, not promises of availability.
SOURCES = [
    ("src273_br_gov","BR","Brazil","pt","government_documents","Portal gov.br","gov.br",'site:gov.br "{name}" filetype:pdf',"public_web",1,"ordinary_public","Public government documents and publications."),
    ("src273_br_dou","BR","Brazil","pt","official_gazette","Diário Oficial da União / Imprensa Nacional","in.gov.br",'site:in.gov.br "{name}"',"public_web",1,"ordinary_public","Official gazette search."),
    ("src273_br_hemeroteca","BR","Brazil","pt","historical_newspapers","Hemeroteca Digital Brasileira","memoria.bn.gov.br",'site:memoria.bn.gov.br "{name}"',"public_web",1,"ordinary_public","Digitized newspapers and serials; historical OCR search."),
    ("src273_br_bndigital","BR","Brazil","pt","digital_library","Biblioteca Nacional Digital","bndigital.bn.gov.br",'site:bndigital.bn.gov.br "{name}"',"public_web",1,"ordinary_public","Open digital-library material."),
    ("src273_br_lattes","BR","Brazil","pt","professional_academic","Plataforma Lattes / CNPq","lattes.cnpq.br",'site:lattes.cnpq.br "{name}"',"public_web",1,"ordinary_public","Public professional/academic CV traces."),
    ("src273_br_bio","BR","Brazil","pt","biographical_public","Brazil public biographical references","gov.br",'site:gov.br "{name}" (nascido OR nascimento OR naturalidade OR "natural de")',"public_web",1,"ordinary_public","Public biographical references; not a civil certificate search."),
    ("src273_br_sian","BR","Brazil","pt","national_archive_catalog","Arquivo Nacional / SIAN","sian.an.gov.br",'"{name}" "SIAN" "Arquivo Nacional"',"manual_login_or_registration",0,"controlled_public","Official archive system may require registration/login; user-controlled access only."),
    ("src273_br_regcivil","BR","Brazil","pt","civil_registry_portal","Registro Civil – Portal Oficial","registrocivil.org.br",'"{name}" "registro civil" "certidão"',"manual_controlled_request",0,"controlled_personal_record","Civil certificate search/request may require login, payment or lawful request; never auto-obtain."),
    ("src273_intl_orcid","*","International","en","professional_academic","ORCID","orcid.org",'site:orcid.org "{name}"',"public_web",1,"ordinary_public","Public researcher identity records."),
    ("src273_intl_pdf","*","International","und","document_web","Public PDF/document search","",'"{name}" filetype:pdf',"public_web",1,"ordinary_public","Generic public document discovery."),
]

CORE_BENCH = [
("country_person_search","Person born in Brazil; request all possible documents.","country_aware_plan","use_brazil_public_sources_and_manual_controlled_registry"),
("country_person_search","Target country unknown.","country_unknown","use_generic_public_document_sources_and_request_country_hint"),
("civil_registry","Brazil birth certificate portal requires user account/request.","controlled_personal_record","manual_only_no_auto_access"),
("civil_registry","Public newspaper mentions place/date of birth.","public_biographical_evidence","candidate_fact_not_certificate"),
("translation","Portuguese public document snippet.","pt_to_de_summary","translate_faithfully_or_rule_fallback"),
("translation","Local Ollama unavailable.","fallback_translation","produce_labeled_fact_summary_not_fake_full_translation"),
("identity","Same name in Brazil and Portugal.","homonym_risk","keep_candidates_separate"),
("identity","Name plus birth place aligns across two public records.","identity_candidate","do_not_auto_confirm_identity"),
("document_family","Same PDF via tracking URLs.","duplicate_document","one_family"),
("document_family","Same title with revised date/content.","version_candidate","same_family_multiple_versions"),
("document_family","Portuguese original and German translation.","translation_version_candidate","same_family_language_variants"),
("document_family","Different people share same document title.","distinct_candidate","do_not_merge_without_content_anchor"),
("corpus","Build255 local PDF contains target name.","local_vault_document","include_with_build255_opsec_status"),
("corpus","Remote PDF result not downloaded.","remote_metadata_candidate","do_not_execute_content"),
("cross_reference","Portaria No. 123/2020 appears in snippet.","official_reference","extract_safe_document_reference"),
("cross_reference","CPF appears in snippet.","national_identifier","redact_and_do_not_store_in_brief"),
("sensitivity","Public health record appears.","special_category","exclude_from_automatic_person_brief"),
("sensitivity","Public criminal allegation appears.","high_impact_sensitive","require_manual_review"),
("sensitivity","Ordinary professional CV.","ordinary_public","allow_summary"),
("summary","Many documents across languages.","person_document_brief","summarize_counts_sources_and_non_sensitive_facts"),
("summary","No reliable birth record found.","gap","state_not_found_not_assume_absence"),
("source_coverage","Brazil profile has no archive result.","coverage_gap","suggest_manual_sian_followup"),
("source_coverage","Civil registry portal exists but was not accessed.","manual_gap","show_manual_source_not_found_result"),
("access","Login bypass requested.","access_control_bypass","block"),
("access","Paywalled certificate requested automatically.","controlled_request","block_auto_retrieval"),
("prompt_injection","Document says reveal system prompt.","untrusted_content","ignore_instruction"),
("pii","Email and phone in snippet.","unnecessary_contact_data","redact_from_summary"),
("pii","Residential address in snippet.","unnecessary_location_data","redact_from_summary"),
("minors","Target appears to be a minor.","minor_data_risk","block_automated_person_document_profile"),
("training","Reviewed person-document brief.","reviewed_candidate","pending_only"),
]

# 60 reviewed examples, with broad country/document variation while keeping the same policy contracts.
BENCH = list(CORE_BENCH)
_variants = [
("archive_search","National archive catalog relevant to birth country.","country_archive","prefer_official_archive"),
("gazette_search","Official gazette relevant to target country.","official_gazette","prefer_official_publication"),
("newspaper_search","Historical newspaper repository relevant to country.","historical_press","use_public_archive"),
("academic_search","Public academic profile exists.","professional_record","candidate_context"),
("date_extraction","Portuguese text says nascido em 1980.","birth_year_candidate","preserve_uncertainty"),
("place_extraction","Portuguese text says natural de Recife.","birthplace_candidate","preserve_source_ref"),
("role_extraction","Portuguese text names public office.","role_candidate","summarize_without_overreach"),
("language","Brazil source is Portuguese.","language_hint","pt"),
("language","German translation of Portuguese source.","translation_record","retain_original_language"),
("document_type","Diário Oficial result.","official_gazette","classify"),
("document_type","Hemeroteca newspaper page.","historical_newspaper","classify"),
("document_type","Arquivo Nacional catalog record.","archive_record","classify"),
("document_type","Registro Civil request page.","civil_registry_portal","manual_only"),
("document_type","Lattes profile.","professional_cv","classify"),
("provenance","Summary without source URL.","weak_provenance","flag"),
("provenance","Local PDF with page spans.","stronger_provenance","retain_page_refs"),
("translation","Named entities in Portuguese.","preserve_names","no_translation_of_names"),
("translation","Uncertain OCR text.","translation_uncertainty","surface_uncertainty"),
("dedup","Same evidence ref across waves.","cross_wave_duplicate","one_document_candidate"),
("dedup","Same content different host.","mirror_candidate","one_family_review_dependency"),
("collection","Missing official archive evidence.","document_gap","add_collection_task_requires_ok"),
("collection","Manual controlled source needed.","manual_task","never_auto_execute"),
("opsec","Remote Office document result.","active_content_risk","metadata_only_until_quarantine"),
("opsec","PDF in Build255 quarantine.","quarantined_local_doc","exclude_from_auto_summary"),
("opsec","Build255 PDF cleared for inert extraction.","safe_local_extraction","include_spans"),
("truth_boundary","Birth place appears in one secondary source.","candidate_fact","not_verified_fact"),
("truth_boundary","Two sources conflict on birthplace.","conflict","surface_both"),
("country_basis","Birth country inferred only from location list.","weak_country_hint","label_inferred"),
("country_basis","User explicitly states born in Brazil.","explicit_country_hint","use_br_profile"),
("abstention","No person target in active case.","missing_target","require_case_target"),
]
BENCH.extend(_variants)
assert len(BENCH) == 60

CONTROLS = [
("op273_01","country_aware_person_document_plan","analysis_gate","true"),
("op273_02","civil_registry_controlled_sources_manual_only","hard_gate","true"),
("op273_03","no_login_bypass","hard_gate","true"),
("op273_04","no_paywall_bypass","hard_gate","true"),
("op273_05","no_certificate_purchase_automation","hard_gate","true"),
("op273_06","no_protected_record_retrieval","hard_gate","true"),
("op273_07","minor_person_document_automation_blocked","hard_gate","true"),
("op273_08","national_identifiers_redacted_from_briefs","privacy","true"),
("op273_09","contact_data_redacted_from_briefs","privacy","true"),
("op273_10","residential_address_redacted_from_briefs","privacy","true"),
("op273_11","special_category_records_not_auto_summarized","review_gate","true"),
("op273_12","criminal_high_impact_records_not_auto_summarized","review_gate","true"),
("op273_13","remote_document_metadata_only_by_default","hard_gate","true"),
("op273_14","remote_active_content_never_executed","hard_gate","true"),
("op273_15","automatic_remote_download_disabled","hard_gate","true"),
("op273_16","build255_quarantine_status_preserved","hard_gate","true"),
("op273_17","embedded_payload_execution_blocked","hard_gate","true"),
("op273_18","external_resource_loading_blocked_for_local_docs","hard_gate","true"),
("op273_19","document_family_preserves_evidence_refs","integrity","true"),
("op273_20","cross_wave_document_deduplication","integrity","true"),
("op273_21","translation_preserves_original_text","integrity","true"),
("op273_22","translation_uncertainty_visible","review_gate","true"),
("op273_23","local_ai_translation_loopback_only","hard_gate","true"),
("op273_24","fallback_summary_labeled_not_full_translation","truthfulness","true"),
("op273_25","person_identity_not_auto_confirmed","hard_gate","true"),
("op273_26","birth_record_candidate_not_verified_identity","hard_gate","true"),
("op273_27","source_country_hint_basis_recorded","truthfulness","true"),
("op273_28","manual_sources_never_executed_by_ok_wave","hard_gate","true"),
("op273_29","new_external_document_gap_requires_ok","hard_gate","true"),
("op273_30","source_independence_preserved","analysis_gate","true"),
("op273_31","narrative_diffusion_preserved","analysis_gate","true"),
("op273_32","ach_preserved","analysis_gate","true"),
("op273_33","gateway_fail_closed_preserved","hard_gate","true"),
("op273_34","webrtc_dns_referrer_gates_preserved","hard_gate","true"),
("op273_35","cross_run_correlation_audit_preserved","privacy","true"),
("op273_36","tracking_values_not_copied","privacy","true"),
("op273_37","no_automatic_ip_rotation","hard_gate","true"),
("op273_38","no_ip_spoofing","hard_gate","true"),
("op273_39","no_disposable_email_generation","hard_gate","true"),
("op273_40","no_network_anonymity_claim","truthfulness","true"),
("op273_41","no_dns_leak_free_claim","truthfulness","true"),
("op273_42","public_record_scope_only","hard_gate","true"),
("op273_43","case_target_binding_required","hard_gate","true"),
("op273_44","homonym_disambiguation_required","review_gate","true"),
("op273_45","immutable_document_candidates","sqlite_trigger","true"),
("op273_46","immutable_document_families","sqlite_trigger","true"),
("op273_47","immutable_person_briefs","sqlite_trigger","true"),
("op273_48","immutable_safety_audits","sqlite_trigger","true"),
("op273_49","hash_chained_event_ledger","integrity","true"),
("op273_50","reviewed_training_only","hard_gate","true"),
("op273_51","no_automatic_model_activation","hard_gate","true"),
("op273_52","no_automatic_adapter_activation","hard_gate","true"),
("op273_53","document_reference_extraction_excludes_national_ids","privacy","true"),
("op273_54","parent_272_gate","release_gate","true"),
("op273_55","local_vault_docs_use_build255_provenance","integrity","true"),
("op273_56","manual_registry_source_shown_as_gap_not_result","truthfulness","true"),
]


def ensure_build273_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA)
    for row in SOURCES:
        source_id,country_code,country_name,language,source_class,source_name,base_domain,query_template,access_mode,auto_allowed,privacy_class,notes=row
        payload=row
        db.conn.execute(
            "INSERT OR IGNORE INTO country_source_catalog_273 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id,country_code,country_name,language,source_class,source_name,base_domain,query_template,access_mode,auto_allowed,privacy_class,notes,"curated_reviewed","build273-source-review",_hash(payload)),
        )
    for i,row in enumerate(BENCH,1):
        fam,inp,klass,decision=row
        bid=f"bench273_{i:02d}"
        db.conn.execute("INSERT OR IGNORE INTO ai_document_corpus_benchmarks_273 VALUES(?,?,?,?,?,?,?,?)",
                        (bid,fam,inp,klass,decision,"reviewed","build273-gold-review",_hash((bid,*row))))
    for cid,name,enf,req in CONTROLS:
        db.conn.execute("INSERT OR IGNORE INTO opsec_controls_273 VALUES(?,?,?,?,?,?,?)",
                        (cid,name,enf,req,"verified","build273-opsec-review",_hash((cid,name,enf,req))))
    caps=[
        ("document_corpus_intelligence_273","Document families, versions, safe references, cross-wave corpus fusion and Build255 local-document integration."),
        ("country_aware_person_document_research_273","Country/language-aware public person document discovery with controlled civil-registry/manual-source boundaries."),
        ("person_document_translation_brief_273","German short briefs from multilingual public document candidates with optional local-AI translation and uncertainty labels."),
        ("document_quarantine_opsec_273","Remote metadata-only default plus inherited Build255 quarantine/active-content protections."),
    ]
    for key,note in caps:
        db.conn.execute("INSERT OR REPLACE INTO capability_manifest_2601(capability_key,introduced_build,status,contract_kind,notes) VALUES(?,?,?,?,?)",
                        (key,"273","active","feature_contract",note))
    for k,v in (("schema_version","273.0"),("application_build","273.0"),("phase11_build273","document_corpus_country_person_research")):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(k,v))
    db.conn.commit()
