from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


SCHEMA_256 = r"""
CREATE TABLE IF NOT EXISTS entity_profiles_256 (
  profile_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  influence_entity_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  display_name TEXT NOT NULL,
  detected_script TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  transliterated_name TEXT NOT NULL,
  legal_form_normalized TEXT NOT NULL,
  official_domain_normalized TEXT NOT NULL,
  pii_class TEXT NOT NULL,
  raw_sensitive_identifier_storage INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  UNIQUE(case_id,influence_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_entprof256_case ON entity_profiles_256(case_id,normalized_name,profile_id);

CREATE TABLE IF NOT EXISTS entity_identifiers_256 (
  identifier_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  identifier_type TEXT NOT NULL,
  identifier_hash TEXT NOT NULL,
  masked_value TEXT NOT NULL,
  value_class TEXT NOT NULL,
  source_class TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(profile_id) REFERENCES entity_profiles_256(profile_id),
  UNIQUE(case_id,profile_id,identifier_type,identifier_hash)
);
CREATE INDEX IF NOT EXISTS idx_entid256_hash ON entity_identifiers_256(case_id,identifier_type,identifier_hash);

CREATE TABLE IF NOT EXISTS entity_match_candidates_256 (
  candidate_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  left_profile_id TEXT NOT NULL,
  right_profile_id TEXT NOT NULL,
  left_entity_id TEXT NOT NULL,
  right_entity_id TEXT NOT NULL,
  name_similarity REAL NOT NULL,
  transliteration_similarity REAL NOT NULL,
  identifier_overlap INTEGER NOT NULL,
  identifier_conflict INTEGER NOT NULL,
  domain_match INTEGER NOT NULL,
  jurisdiction_match INTEGER NOT NULL,
  legal_form_match INTEGER NOT NULL,
  composite_score REAL NOT NULL,
  suggested_class TEXT NOT NULL,
  candidate_only INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  UNIQUE(case_id,left_profile_id,right_profile_id)
);
CREATE INDEX IF NOT EXISTS idx_entmatch256_case ON entity_match_candidates_256(case_id,composite_score,candidate_id);

CREATE TABLE IF NOT EXISTS entity_match_reviews_256 (
  review_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL UNIQUE,
  decision TEXT NOT NULL,
  canonical_entity_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES entity_match_candidates_256(candidate_id)
);

CREATE TABLE IF NOT EXISTS entity_alias_bindings_256 (
  binding_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  canonical_entity_id TEXT NOT NULL,
  alias_entity_id TEXT NOT NULL,
  review_id TEXT NOT NULL,
  binding_class TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  UNIQUE(case_id,canonical_entity_id,alias_entity_id)
);

CREATE TABLE IF NOT EXISTS ai_entity_benchmarks_256 (
  benchmark_id TEXT PRIMARY KEY,
  task_family TEXT NOT NULL,
  left_name TEXT NOT NULL,
  right_name TEXT NOT NULL,
  left_jurisdiction TEXT NOT NULL,
  right_jurisdiction TEXT NOT NULL,
  expected_left_transliteration TEXT NOT NULL,
  expected_right_transliteration TEXT NOT NULL,
  expected_resolution TEXT NOT NULL,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_entity_evaluations_256 (
  evaluation_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  benchmark_id TEXT NOT NULL,
  predicted_left_transliteration TEXT NOT NULL,
  predicted_right_transliteration TEXT NOT NULL,
  predicted_resolution TEXT NOT NULL,
  left_similarity REAL NOT NULL,
  right_similarity REAL NOT NULL,
  decision_match INTEGER NOT NULL,
  passed INTEGER NOT NULL,
  model_or_ruleset TEXT NOT NULL,
  evaluated_by TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  row_hash TEXT NOT NULL,
  FOREIGN KEY(benchmark_id) REFERENCES ai_entity_benchmarks_256(benchmark_id)
);
CREATE INDEX IF NOT EXISTS idx_aient256_case ON ai_entity_evaluations_256(case_id,evaluated_at,evaluation_id);

CREATE TABLE IF NOT EXISTS entity_opsec_controls_256 (
  control_id TEXT PRIMARY KEY,
  control_name TEXT NOT NULL,
  enforcement TEXT NOT NULL,
  required_value TEXT NOT NULL,
  review_status TEXT NOT NULL,
  verified_by TEXT NOT NULL,
  row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build256_events (
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
CREATE INDEX IF NOT EXISTS idx_evt256_case ON build256_events(case_id,created_at,event_id);

CREATE TRIGGER IF NOT EXISTS trg_entprof256_no_update BEFORE UPDATE ON entity_profiles_256 BEGIN SELECT RAISE(ABORT,'entity_profiles_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entprof256_no_delete BEFORE DELETE ON entity_profiles_256 BEGIN SELECT RAISE(ABORT,'entity_profiles_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entid256_no_update BEFORE UPDATE ON entity_identifiers_256 BEGIN SELECT RAISE(ABORT,'entity_identifiers_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entid256_no_delete BEFORE DELETE ON entity_identifiers_256 BEGIN SELECT RAISE(ABORT,'entity_identifiers_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entmatch256_no_update BEFORE UPDATE ON entity_match_candidates_256 BEGIN SELECT RAISE(ABORT,'entity_match_candidates_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entmatch256_no_delete BEFORE DELETE ON entity_match_candidates_256 BEGIN SELECT RAISE(ABORT,'entity_match_candidates_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entrev256_no_update BEFORE UPDATE ON entity_match_reviews_256 BEGIN SELECT RAISE(ABORT,'entity_match_reviews_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entrev256_no_delete BEFORE DELETE ON entity_match_reviews_256 BEGIN SELECT RAISE(ABORT,'entity_match_reviews_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entbind256_no_update BEFORE UPDATE ON entity_alias_bindings_256 BEGIN SELECT RAISE(ABORT,'entity_alias_bindings_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entbind256_no_delete BEFORE DELETE ON entity_alias_bindings_256 BEGIN SELECT RAISE(ABORT,'entity_alias_bindings_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aientbench256_no_update BEFORE UPDATE ON ai_entity_benchmarks_256 BEGIN SELECT RAISE(ABORT,'ai_entity_benchmarks_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aientbench256_no_delete BEFORE DELETE ON ai_entity_benchmarks_256 BEGIN SELECT RAISE(ABORT,'ai_entity_benchmarks_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aienteval256_no_update BEFORE UPDATE ON ai_entity_evaluations_256 BEGIN SELECT RAISE(ABORT,'ai_entity_evaluations_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_aienteval256_no_delete BEFORE DELETE ON ai_entity_evaluations_256 BEGIN SELECT RAISE(ABORT,'ai_entity_evaluations_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entctrl256_no_update BEFORE UPDATE ON entity_opsec_controls_256 BEGIN SELECT RAISE(ABORT,'entity_opsec_controls_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_entctrl256_no_delete BEFORE DELETE ON entity_opsec_controls_256 BEGIN SELECT RAISE(ABORT,'entity_opsec_controls_256 is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt256_no_update BEFORE UPDATE ON build256_events BEGIN SELECT RAISE(ABORT,'build256_events is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_evt256_no_delete BEFORE DELETE ON build256_events BEGIN SELECT RAISE(ABORT,'build256_events is immutable'); END;
"""


BENCHMARKS = [
    ("bench256_he_1","hebrew_transliteration","קרן ירושלים למחקר","Keren Yerushalayim LeMehkar","IL","IL","qrn yrwshlym lmhqr","keren yerushalayim lemehkar","same_entity"),
    ("bench256_he_2","hebrew_transliteration","אוניברסיטת תל אביב","Tel Aviv University","IL","IL","avnyvrsyt tl avyb","tel aviv university","same_entity"),
    ("bench256_he_3","false_merge","קרן אור","קרן אור חדש","IL","IL","qrn avr","qrn avr hdsh","abstain"),
    ("bench256_he_4","false_split","מכון ויצמן למדע","Weizmann Institute of Science","IL","IL","mkvn vytsmn lmd","weizmann institute of science","same_entity"),
    ("bench256_ar_1","arabic_transliteration","مؤسسة الشرق للأبحاث","Muassasat Al Sharq Research Foundation","IL","IL","mss alshrq llabhath","muassasat al sharq research foundation","same_entity"),
    ("bench256_ar_2","arabic_transliteration","جامعة القدس","Al-Quds University","IL","IL","jama alqds","al quds university","same_entity"),
    ("bench256_ar_3","false_merge","مركز الحوار","مركز الحوار الدولي","EU","EU","mrkz alhwar","mrkz alhwar aldwly","abstain"),
    ("bench256_ar_4","false_split","الصليب الأحمر","Red Cross","EU","EU","alslyb alahmr","red cross","same_entity"),
    ("bench256_cyr_1","cyrillic_transliteration","Фонд развития науки","Fond razvitiya nauki","EU","EU","fond razvitiia nauki","fond razvitiya nauki","same_entity"),
    ("bench256_cyr_2","cyrillic_transliteration","Институт международных исследований","Institut mezhdunarodnykh issledovanii","EU","EU","institut mezhdunarodnykh issledovanii","institut mezhdunarodnykh issledovanii","same_entity"),
    ("bench256_cyr_3","false_merge","Фонд Европа","Фонд Новая Европа","EU","EU","fond evropa","fond novaia evropa","abstain"),
    ("bench256_cyr_4","false_split","Київський дослідницький центр","Kyiv Research Center","EU","EU","kyivskyi doslidnytskyi tsentr","kyiv research center","same_entity"),
    ("bench256_lat_1","legal_form_normalization","Example Research Foundation e.V.","Example Research Foundation","DE","DE","example research foundation e v","example research foundation","same_entity"),
    ("bench256_lat_2","legal_form_normalization","Northbridge Analytics GmbH","Northbridge Analytics","DE","DE","northbridge analytics gmbh","northbridge analytics","same_entity"),
    ("bench256_lat_3","false_merge","Global Policy Institute","Global Policy Institute Europe","EU","EU","global policy institute","global policy institute europe","abstain"),
    ("bench256_lat_4","false_split","Centre for Democratic Governance","Center for Democratic Governance","EU","US","centre for democratic governance","center for democratic governance","abstain"),
    ("bench256_id_1","identifier_resolution","Alpha Foundation","Alpha Stiftung","DE","DE","alpha foundation","alpha stiftung","same_entity"),
    ("bench256_id_2","identifier_resolution","Beta Research Ltd","Beta Research Limited","UK","UK","beta research ltd","beta research limited","same_entity"),
    ("bench256_id_3","identifier_conflict","Gamma Institute","Gamma Institute","US","US","gamma institute","gamma institute","distinct_entity"),
    ("bench256_id_4","identifier_conflict","Delta Foundation","Delta Foundation","EU","EU","delta foundation","delta foundation","abstain"),
]

CONTROLS = [
    ("ctrl256_case_scope","Case-scoped entity resolution","Automatic comparisons are restricted to one case and never cross case boundaries.","required"),
    ("ctrl256_org_scope","Organization/legal-entity automation only","Build 256 automatic resolution rejects person entities and private-person profiling.","required"),
    ("ctrl256_public_ids","Public organization identifiers only","Only allow-listed public organization/legal-entity identifier types are accepted.","required"),
    ("ctrl256_no_raw_sensitive_ids","No raw sensitive identifier storage","Build 256 stores identifier hashes and masked display values, not raw sensitive identifiers.","0"),
    ("ctrl256_mask_ui","Identifier exposure minimization","Workspace renders masked identifier values only.","required"),
    ("ctrl256_no_auto_merge","No automatic merge","Similarity creates candidates only; underlying entities are never automatically merged.","false"),
    ("ctrl256_four_eyes","Independent resolution review","same_entity bindings require a reviewer different from the candidate creator.","required"),
    ("ctrl256_no_biometric","No biometric identity resolution","No facial recognition, biometric matching or image-based identity inference.","false"),
    ("ctrl256_no_contact","No automated source contact","No contact, messaging, account creation or covert identity activity.","false"),
    ("ctrl256_no_network","No network side effects","Normalization and matching are local and do not initiate network requests.","false"),
    ("ctrl256_pair_cap","Pair generation cap","Automatic candidate generation is capped per case to prevent uncontrolled bulk expansion.","1000"),
    ("ctrl256_entity_cap","Entity input cap","Automatic candidate generation considers at most 200 staged organization profiles per run.","200"),
]


def ensure_build256_schema(db: Any) -> None:
    db.conn.executescript(SCHEMA_256)
    for row in BENCHMARKS:
        bid,family,left,right,lj,rj,ltrans,rtrans,resolution=row
        payload={"benchmark_id":bid,"task_family":family,"left_name":left,"right_name":right,"left_jurisdiction":lj,"right_jurisdiction":rj,"expected_left_transliteration":ltrans,"expected_right_transliteration":rtrans,"expected_resolution":resolution,"review_status":"curated_reviewed","reviewed_by":"build256-curation"}
        db.conn.execute("INSERT OR IGNORE INTO ai_entity_benchmarks_256 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(*row,"curated_reviewed","build256-curation",_hash(payload)))
    for cid,name,enforcement,required in CONTROLS:
        payload={"control_id":cid,"control_name":name,"enforcement":enforcement,"required_value":required,"review_status":"verified","verified_by":"build256-opsec-review"}
        db.conn.execute("INSERT OR IGNORE INTO entity_opsec_controls_256 VALUES(?,?,?,?,?,?,?)",(cid,name,enforcement,required,"verified","build256-opsec-review",_hash(payload)))
    for key,value in (
        ("schema_version","256.0"),("application_build","256.0"),
        ("phase10_pack","influence_funding_investigation"),("phase10_module","international_entity_resolution_transliteration"),
        ("ai_crosscut_gate","required_every_build"),("opsec_crosscut_gate","required_every_build"),
        ("build256_ai_delta","multiscript_transliteration_false_merge_false_split_identifier_resolution_benchmark"),
        ("build256_opsec_delta","pii_minimization_identity_separation_identifier_exposure_controls"),
    ):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(key,value))
    db.conn.commit()
