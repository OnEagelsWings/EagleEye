from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


SCHEMA_254 = r"""
CREATE TABLE IF NOT EXISTS international_source_profiles_254 (
  source_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  authority TEXT NOT NULL,
  root_url TEXT NOT NULL,
  official_domain TEXT NOT NULL,
  evidence_value TEXT NOT NULL,
  assertion_ceiling TEXT NOT NULL,
  access_class TEXT NOT NULL,
  capture_mode TEXT NOT NULL,
  machine_readable INTEGER NOT NULL DEFAULT 0,
  automation_policy TEXT NOT NULL,
  languages_json TEXT NOT NULL,
  identifier_types_json TEXT NOT NULL,
  key_fields_json TEXT NOT NULL,
  limitations_json TEXT NOT NULL,
  opsec_controls_json TEXT NOT NULL,
  verified_on TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jurisdiction_policy_profiles_254 (
  jurisdiction TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  preferred_languages_json TEXT NOT NULL,
  egress_destination_class TEXT NOT NULL,
  credential_storage_allowed INTEGER NOT NULL DEFAULT 0,
  cross_case_session_reuse_allowed INTEGER NOT NULL DEFAULT 0,
  automated_login_allowed INTEGER NOT NULL DEFAULT 0,
  api_key_policy TEXT NOT NULL,
  session_policy TEXT NOT NULL,
  controls_json TEXT NOT NULL,
  verified_on TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_lookup_plans_254 (
  plan_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  query_language TEXT NOT NULL,
  research_question TEXT NOT NULL,
  query_terms_json TEXT NOT NULL,
  identifier_variants_json TEXT NOT NULL,
  expected_artifacts_json TEXT NOT NULL,
  purpose TEXT NOT NULL,
  access_class TEXT NOT NULL,
  egress_decision TEXT NOT NULL,
  opsec_review_required INTEGER NOT NULL,
  execution_mode TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES international_source_profiles_254(source_id)
);
CREATE INDEX IF NOT EXISTS idx_srcplan254_case ON source_lookup_plans_254(case_id,created_at,plan_id);

CREATE TABLE IF NOT EXISTS source_observations_254 (
  observation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  plan_id TEXT NOT NULL DEFAULT '',
  external_record_ref TEXT NOT NULL DEFAULT '',
  document_date TEXT NOT NULL DEFAULT '',
  observed_fields_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  assertion_class TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES international_source_profiles_254(source_id)
);
CREATE INDEX IF NOT EXISTS idx_srcobs254_case ON source_observations_254(case_id,created_at,observation_id);

CREATE TABLE IF NOT EXISTS ai_multijurisdiction_benchmarks_254 (
  benchmark_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  task TEXT NOT NULL,
  fixture_text TEXT NOT NULL,
  fixture_language TEXT NOT NULL,
  expected_source_id TEXT NOT NULL,
  expected_jurisdiction TEXT NOT NULL,
  expected_identifier_strategy TEXT NOT NULL,
  expected_assertion_ceiling TEXT NOT NULL,
  expected_access_class TEXT NOT NULL,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES international_source_profiles_254(source_id)
);

CREATE TABLE IF NOT EXISTS ai_multijurisdiction_evaluations_254 (
  evaluation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  benchmark_id TEXT NOT NULL,
  predicted_source_id TEXT NOT NULL,
  predicted_jurisdiction TEXT NOT NULL,
  predicted_language TEXT NOT NULL,
  predicted_identifier_strategy TEXT NOT NULL,
  predicted_assertion_ceiling TEXT NOT NULL,
  predicted_access_class TEXT NOT NULL,
  source_match INTEGER NOT NULL,
  jurisdiction_match INTEGER NOT NULL,
  language_match INTEGER NOT NULL,
  identifier_match INTEGER NOT NULL,
  assertion_match INTEGER NOT NULL,
  access_match INTEGER NOT NULL,
  passed INTEGER NOT NULL,
  model_or_ruleset TEXT NOT NULL,
  evaluated_by TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(benchmark_id) REFERENCES ai_multijurisdiction_benchmarks_254(benchmark_id)
);
CREATE INDEX IF NOT EXISTS idx_aieval254_case ON ai_multijurisdiction_evaluations_254(case_id,evaluated_at,evaluation_id);

CREATE TABLE IF NOT EXISTS opsec_jurisdiction_preflights_254 (
  preflight_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  destination_ref TEXT NOT NULL,
  access_class TEXT NOT NULL,
  egress_decision TEXT NOT NULL,
  machine_access_allowed INTEGER NOT NULL,
  credential_boundary TEXT NOT NULL,
  session_boundary TEXT NOT NULL,
  cross_case_session_reuse INTEGER NOT NULL,
  automated_login INTEGER NOT NULL,
  autonomous_network_change INTEGER NOT NULL,
  controls_json TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES international_source_profiles_254(source_id)
);
CREATE INDEX IF NOT EXISTS idx_preflight254_case ON opsec_jurisdiction_preflights_254(case_id,created_at,preflight_id);

CREATE TABLE IF NOT EXISTS build254_events (
  event_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt254_case ON build254_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_srcprofiles254_no_update BEFORE UPDATE ON international_source_profiles_254 BEGIN SELECT RAISE(ABORT,'international_source_profiles_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcprofiles254_no_delete BEFORE DELETE ON international_source_profiles_254 BEGIN SELECT RAISE(ABORT,'international_source_profiles_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_jurpol254_no_update BEFORE UPDATE ON jurisdiction_policy_profiles_254 BEGIN SELECT RAISE(ABORT,'jurisdiction_policy_profiles_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_jurpol254_no_delete BEFORE DELETE ON jurisdiction_policy_profiles_254 BEGIN SELECT RAISE(ABORT,'jurisdiction_policy_profiles_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcplan254_no_update BEFORE UPDATE ON source_lookup_plans_254 BEGIN SELECT RAISE(ABORT,'source_lookup_plans_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcplan254_no_delete BEFORE DELETE ON source_lookup_plans_254 BEGIN SELECT RAISE(ABORT,'source_lookup_plans_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcobs254_no_update BEFORE UPDATE ON source_observations_254 BEGIN SELECT RAISE(ABORT,'source_observations_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcobs254_no_delete BEFORE DELETE ON source_observations_254 BEGIN SELECT RAISE(ABORT,'source_observations_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aibench254_no_update BEFORE UPDATE ON ai_multijurisdiction_benchmarks_254 BEGIN SELECT RAISE(ABORT,'ai_multijurisdiction_benchmarks_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aibench254_no_delete BEFORE DELETE ON ai_multijurisdiction_benchmarks_254 BEGIN SELECT RAISE(ABORT,'ai_multijurisdiction_benchmarks_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aieval254_no_update BEFORE UPDATE ON ai_multijurisdiction_evaluations_254 BEGIN SELECT RAISE(ABORT,'ai_multijurisdiction_evaluations_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aieval254_no_delete BEFORE DELETE ON ai_multijurisdiction_evaluations_254 BEGIN SELECT RAISE(ABORT,'ai_multijurisdiction_evaluations_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_preflight254_no_update BEFORE UPDATE ON opsec_jurisdiction_preflights_254 BEGIN SELECT RAISE(ABORT,'opsec_jurisdiction_preflights_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_preflight254_no_delete BEFORE DELETE ON opsec_jurisdiction_preflights_254 BEGIN SELECT RAISE(ABORT,'opsec_jurisdiction_preflights_254 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt254_no_update BEFORE UPDATE ON build254_events BEGIN SELECT RAISE(ABORT,'build254_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt254_no_delete BEFORE DELETE ON build254_events BEGIN SELECT RAISE(ABORT,'build254_events is immutable'); END;
"""


PROFILES = [
    # European Union
    dict(source_id="eu_transparency_register", display_name="EU Transparency Register", source_kind="lobby_interest_register", jurisdiction="EU", authority="European Parliament and European Commission", root_url="https://transparency-register.europa.eu/search-register_en", official_domain="transparency-register.europa.eu", evidence_value="primary_official_lobby_disclosure", assertion_ceiling="registered_interest_representation_only", access_class="open_search", capture_mode="manual_browser_or_reviewed_export", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en","de","fr","other_eu"], identifier_types=["transparency_register_id","organisation_name"], key_fields=["registration number","organisation","goals/remit","interests represented","clients","financial information","EU relations"], limitations=["Registration records disclose registered interests and self-reported information; they do not prove successful influence or covert direction.","Historical/version context must be preserved when comparing entries."], opsec_controls=["dedicated_case_profile","source_timestamp","no_cross_case_cookie_reuse","manual_or_reviewed_capture"]),
    dict(source_id="eu_financial_transparency_system", display_name="EU Financial Transparency System", source_kind="eu_funding_recipients", jurisdiction="EU", authority="European Commission", root_url="https://commission.europa.eu/about/service-standards-and-principles/transparency/funding-recipients_en", official_domain="commission.europa.eu", evidence_value="primary_official_funding_record", assertion_ceiling="commission_funding_record_only", access_class="open_search", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en","de","fr","other_eu"], identifier_types=["beneficiary_name","budget_line","year"], key_fields=["beneficiary","amount","purpose","recipient location","responsible department","budget source","accounting year"], limitations=["The system covers EU-budget funding directly managed by the Commission and specified funds; absence is not proof of no EU funding.","A recorded award/payment does not by itself prove policy influence or control."], opsec_controls=["dedicated_case_profile","dataset_year_pin","source_timestamp","no_cross_case_cookie_reuse"]),
    dict(source_id="eu_ted", display_name="TED – Tenders Electronic Daily", source_kind="public_procurement", jurisdiction="EU", authority="Publications Office of the European Union", root_url="https://ted.europa.eu/", official_domain="ted.europa.eu", evidence_value="primary_official_procurement_notice", assertion_ceiling="public_procurement_notice_fact_only", access_class="open_search_api_bulk", capture_mode="browser_download_or_reviewed_api", machine_readable=1, automation_policy="reviewed_read_only_api_allowed", languages=["en","de","fr","other_eu"], identifier_types=["ted_notice_number","ocid_like_notice_ref","cpv","nuts"], key_fields=["notice number","buyer","supplier/awardee","procedure","estimated/awarded value","CPV","NUTS","publication date"], limitations=["A notice documents the procurement procedure/status shown, not an inference of improper influence.","Corrections and later award/cancellation notices must be linked before drawing conclusions."], opsec_controls=["dedicated_case_profile","api_egress_review","rate_limit_respect","download_hash","source_timestamp"]),
    dict(source_id="eu_eurlex", display_name="EUR-Lex", source_kind="eu_law_and_official_journal", jurisdiction="EU", authority="Publications Office of the European Union", root_url="https://eur-lex.europa.eu/", official_domain="eur-lex.europa.eu", evidence_value="primary_official_legal_record", assertion_ceiling="official_legal_text_and_procedure_fact_only", access_class="open_search_download", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en","de","fr","other_eu"], identifier_types=["celex","eli","oj_reference"], key_fields=["CELEX","ELI","title","date","legal basis","procedure","Official Journal reference","consolidated status"], limitations=["Legal text and metadata establish official legislative content/status, not who caused a policy outcome.","Consolidated versions must be distinguished from the original act and amendments."], opsec_controls=["dedicated_case_profile","document_hash_on_capture","language_version_pin","source_timestamp"]),

    # United States
    dict(source_id="us_fara", display_name="FARA Public Database", source_kind="foreign_agent_disclosure", jurisdiction="US", authority="U.S. Department of Justice", root_url="https://www.fara.gov/", official_domain="fara.gov", evidence_value="primary_official_fara_filing", assertion_ceiling="filed_fara_disclosure_only", access_class="open_search_api_bulk", capture_mode="browser_bulk_or_reviewed_api", machine_readable=1, automation_policy="reviewed_read_only_api_allowed", languages=["en"], identifier_types=["fara_registration_number","foreign_principal_name","registrant_name"], key_fields=["registrant","registration number","foreign principal","filing type","received date","activities","receipts/disbursements as filed"], limitations=["FARA status and filings reflect statutory registration/disclosure; they are not a general-purpose label of espionage, criminality or loyalty.","Terminated and active registrations must be distinguished."], opsec_controls=["dedicated_case_profile","api_egress_review","bulk_download_hash","source_timestamp","no_login_for_public_search"]),
    dict(source_id="us_lda", display_name="U.S. Lobbying Disclosure Public Search", source_kind="federal_lobbying_disclosure", jurisdiction="US", authority="U.S. House Office of the Clerk / U.S. Senate", root_url="https://lobbyingdisclosure.house.gov/", official_domain="lobbyingdisclosure.house.gov", evidence_value="primary_official_lobbying_filing", assertion_ceiling="filed_lobbying_disclosure_only", access_class="open_search", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en"], identifier_types=["registrant_name","client_name","filing_year","report_id"], key_fields=["registrant","client","lobbyists","issues","houses/agencies contacted","income/expenses","reporting period"], limitations=["Filed lobbying activity does not establish that lobbying succeeded or that an official acted because of it.","Amended reports and reporting periods must be reconciled."], opsec_controls=["dedicated_case_profile","source_timestamp","document_hash_on_capture","no_cross_case_cookie_reuse"]),
    dict(source_id="us_usaspending", display_name="USAspending.gov", source_kind="federal_awards", jurisdiction="US", authority="U.S. Department of the Treasury", root_url="https://www.usaspending.gov/", official_domain="usaspending.gov", evidence_value="primary_official_federal_award_data", assertion_ceiling="federal_award_record_only", access_class="open_search_api_no_auth", capture_mode="browser_download_or_reviewed_api", machine_readable=1, automation_policy="reviewed_read_only_api_allowed", languages=["en"], identifier_types=["uei","award_id","recipient_name","agency_code"], key_fields=["recipient","award ID","UEI","awarding agency","award type","obligation/outlay","period of performance","place of performance"], limitations=["Award and transaction records must be interpreted using award type, action date and obligation/outlay semantics.","Federal funding alone does not establish political direction or influence."], opsec_controls=["dedicated_case_profile","api_egress_review","rate_limit_respect","dataset_timestamp","no_credential_storage"]),
    dict(source_id="us_sec_edgar", display_name="SEC EDGAR", source_kind="company_securities_disclosure", jurisdiction="US", authority="U.S. Securities and Exchange Commission", root_url="https://www.sec.gov/edgar/search/", official_domain="sec.gov", evidence_value="primary_official_company_filing", assertion_ceiling="filed_securities_disclosure_only", access_class="open_search_download", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en"], identifier_types=["cik","accession_number","ticker","company_name"], key_fields=["CIK","company","form type","filing date","reporting period","accession number","exhibits"], limitations=["Issuer filings are filed disclosures and may contain management assertions, estimates or incorporated material requiring separate verification.","Current and historical entity names/CIKs must be resolved carefully."], opsec_controls=["dedicated_case_profile","document_hash_on_capture","source_timestamp","respect_sec_access_policy"]),

    # United Kingdom
    dict(source_id="uk_companies_house", display_name="Companies House", source_kind="company_register", jurisdiction="UK", authority="Companies House / Department for Business and Trade", root_url="https://find-and-update.company-information.service.gov.uk/", official_domain="find-and-update.company-information.service.gov.uk", evidence_value="primary_official_company_register", assertion_ceiling="company_register_filing_fact_only", access_class="open_web_api_key_for_api", capture_mode="manual_web_or_user_managed_api", machine_readable=1, automation_policy="api_key_user_managed_review_required", languages=["en"], identifier_types=["company_number","company_name","officer_name","psc_name"], key_fields=["company number","status","registered office","officers","persons with significant control","filing history","accounts"], limitations=["Public register filings do not prove beneficial control beyond what the specific filing legally records.","API use requires user-managed authentication credentials; EagleEye must not store them in case data."], opsec_controls=["dedicated_case_profile","api_key_user_managed","no_credential_storage_in_case_db","session_isolation","source_timestamp"]),
    dict(source_id="uk_consultant_lobbyists", display_name="UK Register of Consultant Lobbyists", source_kind="consultant_lobbying_register", jurisdiction="UK", authority="Office of the Registrar of Consultant Lobbyists", root_url="https://registrarofconsultantlobbyists.org.uk/", official_domain="registrarofconsultantlobbyists.org.uk", evidence_value="primary_official_lobbying_register", assertion_ceiling="registered_consultant_lobbying_only", access_class="open_search", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en"], identifier_types=["consultant_lobbyist_name","client_name","quarter"], key_fields=["consultant lobbyist","clients","quarterly returns","business details","code of conduct declaration"], limitations=["The statutory register covers consultant lobbying within the Act; it is not a complete register of all lobbying activity in the UK.","Client listing does not prove a specific policy result."], opsec_controls=["dedicated_case_profile","source_timestamp","no_cross_case_cookie_reuse","manual_or_reviewed_capture"]),
    dict(source_id="uk_electoral_commission", display_name="UK Electoral Commission – Political Finance", source_kind="political_finance", jurisdiction="UK", authority="The Electoral Commission", root_url="https://search.electoralcommission.org.uk/", official_domain="search.electoralcommission.org.uk", evidence_value="primary_official_political_finance", assertion_ceiling="reported_political_finance_record_only", access_class="open_search", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["en"], identifier_types=["party_name","regulated_donee","donor_name","reporting_period"], key_fields=["regulated entity","donor/lender","amount","accepted date","donation/loan type","spending","accounts"], limitations=["Political finance records establish reported/regulated transactions, not quid-pro-quo or policy causation.","Reporting periods, permissibility status and amendments must be preserved."], opsec_controls=["dedicated_case_profile","source_timestamp","document_hash_on_capture","no_cross_case_cookie_reuse"]),
    dict(source_id="uk_contracts_finder", display_name="Contracts Finder", source_kind="public_procurement", jurisdiction="UK", authority="UK Government / Crown Commercial Service", root_url="https://www.contractsfinder.service.gov.uk/Search", official_domain="contractsfinder.service.gov.uk", evidence_value="primary_official_procurement_notice", assertion_ceiling="public_contract_notice_fact_only", access_class="open_search_api", capture_mode="browser_download_or_reviewed_api", machine_readable=1, automation_policy="reviewed_read_only_api_allowed", languages=["en"], identifier_types=["ocid","notice_id","supplier_name","buyer_name"], key_fields=["buyer","supplier","title","procurement stage","award value","dates","OCID","notice identifier"], limitations=["Coverage and thresholds vary; other UK nations and high-value procurement may use additional services.","A contract award does not establish improper influence."], opsec_controls=["dedicated_case_profile","api_egress_review","rate_limit_respect","download_hash","source_timestamp"]),

    # Israel
    dict(source_id="il_corporations_companies", display_name="Israel Corporations Authority – Companies", source_kind="company_register", jurisdiction="IL", authority="Israeli Corporations Authority / Ministry of Justice", root_url="https://ica.justice.gov.il/GenericCorporarionInfo/SearchCorporation?unit=8", official_domain="ica.justice.gov.il", evidence_value="primary_official_company_register", assertion_ceiling="company_register_fact_only", access_class="open_basic_paid_full_extract", capture_mode="manual_browser_paid_extract_if_authorized", machine_readable=0, automation_policy="manual_human_controlled_only", languages=["he","en"], identifier_types=["company_number","company_name_he","company_name_en"], key_fields=["corporation number","Hebrew name","English name","company type","status","annual report status","registered details in paid extract"], limitations=["Free basic information may be incomplete or not current; the official site directs users to the corporation file/paid extract for filed details.","Paid or expanded records remain human-controlled; no automated purchasing or account action."], opsec_controls=["dedicated_case_profile","manual_paid_access_only","no_payment_automation","no_credential_storage_in_eagleeye","source_timestamp"]),
    dict(source_id="il_nonprofits", display_name="Israel Corporations Authority – Associations & Public Benefit Companies", source_kind="nonprofit_register", jurisdiction="IL", authority="Israeli Corporations Authority / Ministry of Justice", root_url="https://www.gov.il/he/service/assocoations_online_information", official_domain="gov.il", evidence_value="primary_official_nonprofit_record", assertion_ceiling="nonprofit_register_and_filing_fact_only", access_class="open_free_info_paid_full_file", capture_mode="manual_browser_or_authorized_file_order", machine_readable=0, automation_policy="manual_human_controlled_only", languages=["he","ar"], identifier_types=["association_number","public_benefit_company_number","organisation_name_he"], key_fields=["organisation details","activities","official documents","financial data","registration number"], limitations=["Free data and official documents may differ in scope; paid full-file ordering is a separate human decision.","Financial filings document reported data and do not by themselves prove external direction."], opsec_controls=["dedicated_case_profile","manual_paid_access_only","no_payment_automation","no_credential_storage_in_eagleeye","document_hash_on_capture"]),
    dict(source_id="il_government_procurement", display_name="Israel Government Procurement Portal", source_kind="public_procurement", jurisdiction="IL", authority="Government Procurement Administration / State of Israel", root_url="https://mr.gov.il/ilgstorefront/he/search?s=TENDER", official_domain="mr.gov.il", evidence_value="primary_official_procurement_notice", assertion_ceiling="public_procurement_notice_fact_only", access_class="open_search_submission_external", capture_mode="manual_browser_or_reviewed_download", machine_readable=0, automation_policy="manual_or_reviewed_only", languages=["he","en","ar"], identifier_types=["publication_number","procedure_number","publisher_name"], key_fields=["publisher","publication number","procedure number","status","publication/update date","deadline","documents"], limitations=["Portal notices document procurement procedures and updates, not improper influence or contract performance.","Submission systems and bidder interactions are outside EagleEye and must never be automated."], opsec_controls=["dedicated_case_profile","source_timestamp","no_submission_automation","no_external_contact","document_hash_on_capture"]),
    dict(source_id="il_data_gov_budget", display_name="Israel DataGov / Ministry of Finance Budget Data", source_kind="government_budget_open_data", jurisdiction="IL", authority="Ministry of Finance / National Digital Agency", root_url="https://data.gov.il/he/organizations/mof", official_domain="data.gov.il", evidence_value="primary_official_open_dataset", assertion_ceiling="official_budget_dataset_fact_only", access_class="open_download", capture_mode="manual_or_reviewed_dataset_download", machine_readable=1, automation_policy="reviewed_read_only_download_allowed", languages=["he","en"], identifier_types=["budget_item","fiscal_year","ministry_code","dataset_id"], key_fields=["fiscal year","budget item","ministry","original/updated budget","execution","commitments","dataset update date"], limitations=["Budget and execution aggregates must be distinguished from individual transfers or contracts.","Dataset vintage and definitions must be pinned before cross-year comparison."], opsec_controls=["dedicated_case_profile","dataset_date_pin","download_hash","no_cross_case_cookie_reuse","source_attribution"]),
]


JURISDICTION_POLICIES = [
    dict(jurisdiction="EU", display_name="European Union", preferred_languages=["en","de","fr"], egress_destination_class="official_public_source", api_key_policy="no_key_expected_for_profiled_automatable_sources", session_policy="dedicated_case_session_no_cross_case_reuse", controls=["dedicated_case_profile","language_version_pin","no_cross_case_cookie_reuse","source_timestamp","review_before_machine_access"]),
    dict(jurisdiction="US", display_name="United States", preferred_languages=["en"], egress_destination_class="official_public_source", api_key_policy="public_profiled_APIs_prefer_no_auth; never store filing credentials", session_policy="dedicated_case_session_no_cross_case_reuse", controls=["dedicated_case_profile","no_cross_case_cookie_reuse","source_timestamp","rate_limit_respect","review_before_machine_access"]),
    dict(jurisdiction="UK", display_name="United Kingdom", preferred_languages=["en"], egress_destination_class="official_public_source", api_key_policy="user_managed_key_only_where_official_API_requires_it; never store in case DB", session_policy="dedicated_case_session_no_cross_case_reuse", controls=["dedicated_case_profile","api_key_boundary","no_credential_storage_in_case_db","no_cross_case_cookie_reuse","review_before_machine_access"]),
    dict(jurisdiction="IL", display_name="Israel", preferred_languages=["he","en","ar"], egress_destination_class="official_public_source", api_key_policy="no credential/payment automation; human-controlled paid or authenticated access", session_policy="dedicated_case_session_no_cross_case_reuse", controls=["dedicated_case_profile","rtl_language_awareness","no_payment_automation","no_external_contact","no_cross_case_cookie_reuse","review_before_machine_access"]),
]


BENCHMARKS = [
    ("bench254_eu_tr","eu_transparency_register","EU","source_selection","fr","Quel registre officiel indique les organisations qui représentent des intérêts auprès des institutions de l’Union européenne et leurs clients ?","transparency_register_id_or_name"),
    ("bench254_eu_fts","eu_financial_transparency_system","EU","source_selection","de","Welche offizielle EU-Quelle nennt Begünstigte, Betrag, Zweck und verantwortliche Dienststelle einer direkt von der Kommission vergebenen Finanzierung?","beneficiary_name_plus_year"),
    ("bench254_eu_ted","eu_ted","EU","source_selection","en","Find the official EU procurement notice and award details using a TED notice number and CPV code.","ted_notice_number_or_cpv"),
    ("bench254_eu_lex","eu_eurlex","EU","source_selection","de","Gesucht werden der amtliche EU-Rechtsakt, seine CELEX-Nummer und der Stand der konsolidierten Fassung.","celex_or_eli"),
    ("bench254_us_fara","us_fara","US","source_selection","en","Which DOJ public source shows a foreign principal, registrant, registration number and filed FARA documents?","fara_registration_number_or_names"),
    ("bench254_us_lda","us_lda","US","source_selection","en","Find the official federal lobbying disclosure showing the registrant, client, issues and reported income or expenses.","registrant_client_reporting_period"),
    ("bench254_us_spend","us_usaspending","US","source_selection","en","Find a federal grant or contract using a UEI or award ID and identify the awarding agency and obligation amount.","uei_or_award_id"),
    ("bench254_us_sec","us_sec_edgar","US","source_selection","en","Find an SEC company filing using its CIK or accession number and preserve the filing date and form type.","cik_or_accession_number"),
    ("bench254_uk_ch","uk_companies_house","UK","source_selection","en","Use the official UK company register to resolve a company number, officers, PSC data and filing history.","company_number_preferred"),
    ("bench254_uk_lobby","uk_consultant_lobbyists","UK","source_selection","en","Which statutory UK register lists consultant lobbyists and the clients declared in quarterly returns?","consultant_or_client_name"),
    ("bench254_uk_ec","uk_electoral_commission","UK","source_selection","en","Find official UK political finance records for donations, loans, spending or party accounts.","regulated_entity_donor_period"),
    ("bench254_uk_cf","uk_contracts_finder","UK","source_selection","en","Find a UK government contract notice by buyer, supplier or OCID and preserve award value and procurement stage.","ocid_or_buyer_supplier"),
    ("bench254_il_co","il_corporations_companies","IL","source_selection","he","מצא מידע רשמי על חברה בישראל לפי מספר חברה או שם, כולל סטטוס ופרטי רישום בסיסיים.","israeli_company_number_or_name"),
    ("bench254_il_np","il_nonprofits","IL","source_selection","he","מצא מידע רשמי, מסמכים ונתונים כספיים על עמותה או חברה לתועלת הציבור לפי מספר עמותה.","association_number_or_name"),
    ("bench254_il_proc","il_government_procurement","IL","source_selection","he","מצא מכרז ממשלתי לפי מספר פרסום או מספר הליך ושמור את המפרסם, הסטטוס והמועדים.","publication_or_procedure_number"),
    ("bench254_il_budget","il_data_gov_budget","IL","source_selection","he","מצא נתוני תקציב וביצוע רשמיים של משרד האוצר לפי שנת כספים וסעיף תקציבי.","fiscal_year_plus_budget_item"),
]


def ensure_build254_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_254)
    verified = "2026-08-27"
    for p in PROFILES:
        payload = dict(p)
        payload["verified_on"] = verified
        digest = _hash(payload)
        db.conn.execute(
            "INSERT OR IGNORE INTO international_source_profiles_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["source_id"],p["display_name"],p["source_kind"],p["jurisdiction"],p["authority"],p["root_url"],p["official_domain"],
                p["evidence_value"],p["assertion_ceiling"],p["access_class"],p["capture_mode"],int(p["machine_readable"]),p["automation_policy"],
                json.dumps(p["languages"],ensure_ascii=False),json.dumps(p["identifier_types"],ensure_ascii=False),json.dumps(p["key_fields"],ensure_ascii=False),
                json.dumps(p["limitations"],ensure_ascii=False),json.dumps(p["opsec_controls"],ensure_ascii=False),verified,digest,
            ),
        )
    for policy in JURISDICTION_POLICIES:
        payload = dict(policy)
        payload.update({"credential_storage_allowed":False,"cross_case_session_reuse_allowed":False,"automated_login_allowed":False,"verified_on":verified})
        db.conn.execute(
            "INSERT OR IGNORE INTO jurisdiction_policy_profiles_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                policy["jurisdiction"],policy["display_name"],json.dumps(policy["preferred_languages"],ensure_ascii=False),policy["egress_destination_class"],
                0,0,0,policy["api_key_policy"],policy["session_policy"],json.dumps(policy["controls"],ensure_ascii=False),verified,_hash(payload),
            ),
        )
    profile_map = {p["source_id"]: p for p in PROFILES}
    for bid, sid, jurisdiction, task, language, fixture, identifier_strategy in BENCHMARKS:
        p = profile_map[sid]
        payload = {
            "benchmark_id":bid,"source_id":sid,"jurisdiction":jurisdiction,"task":task,"fixture_text":fixture,"fixture_language":language,
            "expected_source_id":sid,"expected_jurisdiction":jurisdiction,"expected_identifier_strategy":identifier_strategy,
            "expected_assertion_ceiling":p["assertion_ceiling"],"expected_access_class":p["access_class"],
            "review_status":"curated_reviewed","reviewed_by":"build254-curation",
        }
        db.conn.execute(
            "INSERT OR IGNORE INTO ai_multijurisdiction_benchmarks_254 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid,sid,jurisdiction,task,fixture,language,sid,jurisdiction,identifier_strategy,p["assertion_ceiling"],p["access_class"],"curated_reviewed","build254-curation",_hash(payload)),
        )
    for key, value in (
        ("schema_version","254.0"),("application_build","254.0"),
        ("phase10_pack","influence_funding_investigation"),("phase10_module","eu_us_uk_israel_source_profiles"),
        ("ai_crosscut_gate","required_every_build"),("opsec_crosscut_gate","required_every_build"),
        ("build254_ai_delta","multijurisdiction_multilingual_routing_identifier_benchmark"),
        ("build254_opsec_delta","jurisdiction_egress_credential_session_boundaries"),
    ):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(key,value))
    db.conn.commit()
