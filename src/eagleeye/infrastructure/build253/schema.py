from __future__ import annotations
import hashlib
import json
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


SCHEMA_253 = r"""
CREATE TABLE IF NOT EXISTS german_source_profiles_253 (
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
  historical_scope TEXT NOT NULL,
  key_fields_json TEXT NOT NULL,
  limitations_json TEXT NOT NULL,
  opsec_controls_json TEXT NOT NULL,
  verified_on TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_lookup_plans_253 (
  plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
  research_question TEXT NOT NULL, query_terms_json TEXT NOT NULL,
  expected_artifacts_json TEXT NOT NULL, purpose TEXT NOT NULL,
  access_class TEXT NOT NULL, egress_decision TEXT NOT NULL,
  opsec_review_required INTEGER NOT NULL DEFAULT 1,
  execution_mode TEXT NOT NULL DEFAULT 'manual_or_reviewed_only',
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES german_source_profiles_253(source_id)
);
CREATE INDEX IF NOT EXISTS idx_srcplans253_case ON source_lookup_plans_253(case_id,source_id,created_at);

CREATE TABLE IF NOT EXISTS source_observations_253 (
  observation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
  plan_id TEXT NOT NULL, external_record_ref TEXT NOT NULL, document_date TEXT NOT NULL,
  observed_fields_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
  assertion_class TEXT NOT NULL, notes TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES german_source_profiles_253(source_id)
);
CREATE INDEX IF NOT EXISTS idx_srcobs253_case ON source_observations_253(case_id,source_id,assertion_class,created_at);

CREATE TABLE IF NOT EXISTS ai_source_benchmarks_253 (
  benchmark_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, task TEXT NOT NULL,
  fixture_text TEXT NOT NULL, expected_source_id TEXT NOT NULL,
  expected_assertion_ceiling TEXT NOT NULL, expected_access_class TEXT NOT NULL,
  review_status TEXT NOT NULL, reviewed_by TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(source_id) REFERENCES german_source_profiles_253(source_id)
);

CREATE TABLE IF NOT EXISTS ai_source_evaluations_253 (
  evaluation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, benchmark_id TEXT NOT NULL,
  predicted_source_id TEXT NOT NULL, predicted_assertion_ceiling TEXT NOT NULL,
  predicted_access_class TEXT NOT NULL, source_match INTEGER NOT NULL,
  assertion_match INTEGER NOT NULL, access_match INTEGER NOT NULL,
  passed INTEGER NOT NULL, model_or_ruleset TEXT NOT NULL,
  evaluated_by TEXT NOT NULL, evaluated_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(benchmark_id) REFERENCES ai_source_benchmarks_253(benchmark_id)
);
CREATE INDEX IF NOT EXISTS idx_aieval253_case ON ai_source_evaluations_253(case_id,passed,evaluated_at);

CREATE TABLE IF NOT EXISTS opsec_source_preflights_253 (
  preflight_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL,
  destination_ref TEXT NOT NULL, access_class TEXT NOT NULL,
  egress_decision TEXT NOT NULL, automation_allowed INTEGER NOT NULL DEFAULT 0,
  credential_handling TEXT NOT NULL, required_controls_json TEXT NOT NULL,
  autonomous_network_change INTEGER NOT NULL DEFAULT 0,
  actor TEXT NOT NULL, created_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  FOREIGN KEY(source_id) REFERENCES german_source_profiles_253(source_id)
);
CREATE INDEX IF NOT EXISTS idx_opsecpre253_case ON opsec_source_preflights_253(case_id,source_id,created_at);

CREATE TABLE IF NOT EXISTS build253_events (
  event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_type TEXT NOT NULL,
  object_type TEXT NOT NULL, object_id TEXT NOT NULL, actor TEXT NOT NULL,
  payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt253_case ON build253_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_srcprofiles253_no_update BEFORE UPDATE ON german_source_profiles_253 BEGIN SELECT RAISE(ABORT,'german_source_profiles_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcprofiles253_no_delete BEFORE DELETE ON german_source_profiles_253 BEGIN SELECT RAISE(ABORT,'german_source_profiles_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcplans253_no_update BEFORE UPDATE ON source_lookup_plans_253 BEGIN SELECT RAISE(ABORT,'source_lookup_plans_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcplans253_no_delete BEFORE DELETE ON source_lookup_plans_253 BEGIN SELECT RAISE(ABORT,'source_lookup_plans_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcobs253_no_update BEFORE UPDATE ON source_observations_253 BEGIN SELECT RAISE(ABORT,'source_observations_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_srcobs253_no_delete BEFORE DELETE ON source_observations_253 BEGIN SELECT RAISE(ABORT,'source_observations_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aibench253_no_update BEFORE UPDATE ON ai_source_benchmarks_253 BEGIN SELECT RAISE(ABORT,'ai_source_benchmarks_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aibench253_no_delete BEFORE DELETE ON ai_source_benchmarks_253 BEGIN SELECT RAISE(ABORT,'ai_source_benchmarks_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aieval253_no_update BEFORE UPDATE ON ai_source_evaluations_253 BEGIN SELECT RAISE(ABORT,'ai_source_evaluations_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aieval253_no_delete BEFORE DELETE ON ai_source_evaluations_253 BEGIN SELECT RAISE(ABORT,'ai_source_evaluations_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsecpre253_no_update BEFORE UPDATE ON opsec_source_preflights_253 BEGIN SELECT RAISE(ABORT,'opsec_source_preflights_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_opsecpre253_no_delete BEFORE DELETE ON opsec_source_preflights_253 BEGIN SELECT RAISE(ABORT,'opsec_source_preflights_253 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt253_no_update BEFORE UPDATE ON build253_events BEGIN SELECT RAISE(ABORT,'build253_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt253_no_delete BEFORE DELETE ON build253_events BEGIN SELECT RAISE(ABORT,'build253_events is immutable'); END;
"""


PROFILES = [
    dict(source_id="de_handelsregister", display_name="Gemeinsames Registerportal der Länder (Handelsregister)", source_kind="company_register", jurisdiction="DE", authority="Justizverwaltungen der Länder", root_url="https://www.handelsregister.de/", official_domain="handelsregister.de", evidence_value="primary_official_register", assertion_ceiling="direct_register_fact_only", access_class="session_or_login_may_apply", capture_mode="manual_browser", machine_readable=0, historical_scope="Registereintragungen und eingereichte Dokumente; Verfügbarkeit je Dokument/Portal", key_fields=["Firma","Sitz","Registergericht","Registernummer","Vertretungsberechtigte","Eintragungen","Dokumentdatum"], limitations=["Keine automatische Umgehung von Login, Session, Captcha oder Portalbeschränkungen.","Registereintrag belegt nur den registrierten Sachverhalt, nicht informelle Kontrolle oder Einfluss."], opsec_controls=["dedicated_case_profile","no_credential_storage_in_eagleeye","manual_login_only","capture_source_timestamp"]),
    dict(source_id="de_unternehmensregister", display_name="Unternehmensregister", source_kind="company_disclosure_register", jurisdiction="DE", authority="Bundesanzeiger Verlag im gesetzlichen Registerverbund", root_url="https://www.unternehmensregister.de/", official_domain="unternehmensregister.de", evidence_value="primary_official_disclosure", assertion_ceiling="direct_disclosure_fact_only", access_class="mixed_open_account_for_some_documents", capture_mode="manual_browser_or_document_download", machine_readable=0, historical_scope="Registerinformationen, Rechnungslegung, Veröffentlichungen; einzelne hinterlegte Unterlagen zugangsbeschränkt", key_fields=["Firmenname","EUID","Registerinformationen","Jahresabschluss","Unternehmensbericht","Veröffentlichungsdatum"], limitations=["Einige hinterlegte Unterlagen erfordern Anmeldung.","Finanzberichte dürfen nicht ohne Kontext als aktueller Zahlungsfluss interpretiert werden."], opsec_controls=["dedicated_case_profile","session_isolation","no_credential_storage_in_eagleeye","document_hash_on_capture"]),
    dict(source_id="de_bundesanzeiger", display_name="Bundesanzeiger", source_kind="official_announcements", jurisdiction="DE", authority="Bundesministerium der Justiz und für Verbraucherschutz / Bundesanzeiger Verlag", root_url="https://www.bundesanzeiger.de/", official_domain="bundesanzeiger.de", evidence_value="primary_official_announcement", assertion_ceiling="published_announcement_fact_only", access_class="open_session_based", capture_mode="manual_browser_or_document_download", machine_readable=0, historical_scope="Amtliche Bekanntmachungen und gesetzlich vorgesehene Veröffentlichungen", key_fields=["Rubrik","Veröffentlicher","Bekanntmachung","Datum","Dokument"], limitations=["Veröffentlichung belegt den veröffentlichten Inhalt; sie ersetzt keine gesonderte Prüfung der materiellen Aussage.","Session- und Nutzungsbedingungen beachten."], opsec_controls=["dedicated_case_profile","session_isolation","document_hash_on_capture","source_timestamp"]),
    dict(source_id="de_transparenzregister", display_name="Transparenzregister", source_kind="beneficial_ownership_register", jurisdiction="DE", authority="Bundesrepublik Deutschland / registerführende Stelle", root_url="https://www.transparenzregister.de/", official_domain="transparenzregister.de", evidence_value="primary_official_beneficial_ownership", assertion_ceiling="direct_register_fact_only", access_class="account_and_request_required", capture_mode="manual_authenticated_request_only", machine_readable=0, historical_scope="Angaben zu wirtschaftlich Berechtigten im gesetzlichen Einsichtsrahmen", key_fields=["Rechtseinheit","wirtschaftlich Berechtigte","Art/Umfang des wirtschaftlichen Interesses","Auszugsdatum"], limitations=["Einsichtnahme erfordert Nutzerkonto und ggf. Antrag/Berechtigungsprüfung.","Keine Credential-Automation, kein Login-Bypass, keine Massenabfrage."], opsec_controls=["dedicated_case_profile","manual_login_only","no_credential_storage_in_eagleeye","legal_access_check","no_bulk_collection"]),
    dict(source_id="de_lobbyregister", display_name="Lobbyregister beim Deutschen Bundestag", source_kind="lobby_register", jurisdiction="DE", authority="Deutscher Bundestag", root_url="https://www.lobbyregister.bundestag.de/", official_domain="lobbyregister.bundestag.de", evidence_value="primary_official_lobby_disclosure", assertion_ceiling="registered_lobby_disclosure_only", access_class="open_search_and_download", capture_mode="browser_or_reviewed_download", machine_readable=1, historical_scope="Aktive/frühere Registereinträge; historische Suche im angebotenen Rahmen", key_fields=["Registernummer","Interessenvertretung","Auftraggeber","Unterauftragnehmer","Regelungsvorhaben","Zuwendungen","Schenkungen","Personal-/Finanzaufwand"], limitations=["Registerangabe belegt die registrierte Interessenvertretung, nicht Erfolg oder verdeckte Steuerung.","Gleiche Ursprungsangabe nicht als mehrere unabhängige Quellen zählen."], opsec_controls=["dedicated_case_profile","download_hash","source_timestamp","respect_export_limits"]),
    dict(source_id="de_bundeshaushalt", display_name="Bundeshaushalt digital", source_kind="federal_budget", jurisdiction="DE", authority="Bundesministerium der Finanzen", root_url="https://www.bundeshaushalt.de/", official_domain="bundeshaushalt.de", evidence_value="primary_official_budget", assertion_ceiling="budget_appropriation_fact_only", access_class="open_visual_and_csv", capture_mode="browser_or_reviewed_csv_download", machine_readable=1, historical_scope="Haushaltsdaten mehrerer Jahre einschließlich Soll/Ist soweit verfügbar", key_fields=["Haushaltsjahr","Einzelplan","Kapitel","Titel","Funktion","Soll","Ist","Einnahmen","Ausgaben"], limitations=["Haushaltsansatz oder Ist-Aggregat ist nicht automatisch eine konkrete Zahlung an eine Organisation.","Jahres-/Entwurfsstatus und Soll/Ist strikt trennen."], opsec_controls=["dedicated_case_profile","download_hash","dataset_date_pin","no_cross_case_cookie_reuse"]),
    dict(source_id="de_bundestag_dip", display_name="DIP – Dokumentations- und Informationssystem für Parlamentsmaterialien", source_kind="parliamentary_records", jurisdiction="DE", authority="Deutscher Bundestag / Bundesrat", root_url="https://dip.bundestag.de/", official_domain="dip.bundestag.de", evidence_value="primary_official_parliamentary_record", assertion_ceiling="parliamentary_record_fact_only", access_class="open_search_download_api", capture_mode="browser_download_or_reviewed_api", machine_readable=1, historical_scope="Drucksachen, Plenarprotokolle und Beratungsvorgänge über Wahlperioden", key_fields=["Drucksachennummer","Vorgang","Urheber","Datum","Beratungsstand","Plenarprotokoll","Fundstelle"], limitations=["Parlamentarische Äußerung ist eine dokumentierte Äußerung, nicht automatisch eine wahre Tatsachenfeststellung.","Bei API-/Dokumentnutzung Quellenangabe und Veränderungskennzeichnung beachten."], opsec_controls=["dedicated_case_profile","api_egress_review","document_hash_on_capture","source_attribution"]),
]

BENCHMARKS = [
    ("bench253_hr","de_handelsregister","source_selection","Gesucht werden aktuelle Registervertretung, Sitz und formale Registereintragungen einer deutschen GmbH."),
    ("bench253_ur","de_unternehmensregister","source_selection","Gesucht werden veröffentlichte Jahresabschlüsse, Unternehmensberichte und Registerinformationen zu einem deutschen Unternehmen."),
    ("bench253_banz","de_bundesanzeiger","source_selection","Gesucht wird eine amtlich veröffentlichte Bekanntmachung des Bundes bzw. eine gesetzlich vorgesehene Veröffentlichung."),
    ("bench253_tr","de_transparenzregister","source_selection","Gesucht werden Angaben zu wirtschaftlich Berechtigten einer deutschen Rechtseinheit im zulässigen Einsichtsrahmen."),
    ("bench253_lr","de_lobbyregister","source_selection","Gesucht werden registrierte Auftraggeber, Regelungsvorhaben, Zuwendungen und personelle oder finanzielle Aufwendungen der Interessenvertretung."),
    ("bench253_bhh","de_bundeshaushalt","source_selection","Gesucht werden Soll- und Ist-Haushaltsdaten des Bundes nach Jahr, Einzelplan, Kapitel oder Titel."),
    ("bench253_dip","de_bundestag_dip","source_selection","Gesucht werden Bundestagsdrucksachen, Plenarprotokolle und der Beratungsablauf eines Gesetzgebungsvorhabens."),
]


def ensure_build253_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_253)
    for p in PROFILES:
        payload = dict(p)
        payload["verified_on"] = "2026-08-27"
        digest = _hash(payload)
        db.conn.execute(
            "INSERT OR IGNORE INTO german_source_profiles_253 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p["source_id"],p["display_name"],p["source_kind"],p["jurisdiction"],p["authority"],p["root_url"],p["official_domain"],p["evidence_value"],p["assertion_ceiling"],p["access_class"],p["capture_mode"],int(p["machine_readable"]),p["historical_scope"],json.dumps(p["key_fields"],ensure_ascii=False),json.dumps(p["limitations"],ensure_ascii=False),json.dumps(p["opsec_controls"],ensure_ascii=False),"2026-08-27",digest),
        )
    profile_map = {p["source_id"]: p for p in PROFILES}
    for bid, sid, task, fixture in BENCHMARKS:
        p = profile_map[sid]
        payload = {"benchmark_id":bid,"source_id":sid,"task":task,"fixture_text":fixture,"expected_source_id":sid,"expected_assertion_ceiling":p["assertion_ceiling"],"expected_access_class":p["access_class"],"review_status":"curated_reviewed","reviewed_by":"build253-curation"}
        db.conn.execute("INSERT OR IGNORE INTO ai_source_benchmarks_253 VALUES(?,?,?,?,?,?,?,?,?,?)",(bid,sid,task,fixture,sid,p["assertion_ceiling"],p["access_class"],"curated_reviewed","build253-curation",_hash(payload)))
    for key,value in (
        ("schema_version","253.0"),("application_build","253.0"),
        ("phase10_pack","influence_funding_investigation"),("phase10_module","german_source_profiles"),
        ("ai_crosscut_gate","required_every_build"),("opsec_crosscut_gate","required_every_build"),
    ):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(key,value))
    db.conn.commit()
