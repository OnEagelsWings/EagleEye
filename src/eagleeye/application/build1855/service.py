from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build1855GenealogyVitalRecordsService:
    """Public genealogy/vital-record source layer and browser workflow hardening.

    Index hits and user-submitted trees are leads only. The service never treats a
    family-tree edge, name match or date match as a confirmed relationship.
    """

    BUILD = "185.5"
    SOURCE_PROFILES = (
        {"source_id":"familysearch_api","title":"FamilySearch REST API and Genealogies","category":"genealogy_tree_records","access_mode":"oauth_api","base_url":"https://api.familysearch.org","constraints":["app_approval_required","living_persons_restricted","user_submitted_tree_not_primary_evidence","terms_review_required"]},
        {"source_id":"matricula_online","title":"Matricula Online church registers","category":"church_vital_records","access_mode":"guided_public_web","base_url":"https://data.matricula-online.eu","constraints":["historical_records_only","jurisdiction_and_archive_rules","manual_image_review","no_bulk_scraping"]},
        {"source_id":"archion_churchbooks","title":"Archion digitised church books","category":"church_vital_records","access_mode":"credentialed_guided_web","base_url":"https://www.archion.de","constraints":["subscription_may_be_required","terms_review_required","no_credential_automation","manual_record_review"]},
        {"source_id":"compgen_gedbas","title":"CompGen GEDBAS family trees","category":"user_submitted_genealogy","access_mode":"guided_public_web","base_url":"https://gedbas.genealogy.net","constraints":["user_submitted_data","relationship_candidate_only","source_citation_required","living_person_protection"]},
        {"source_id":"compgen_online_ofb","title":"CompGen Online-Ortsfamilienbücher","category":"compiled_local_family_books","access_mode":"guided_public_web","base_url":"https://ofb.genealogy.net","constraints":["compiled_secondary_source","local_coverage_varies","original_record_corroboration_required"]},
        {"source_id":"arolsen_online_archive","title":"Arolsen Archives Online Archive","category":"historical_person_records","access_mode":"guided_public_web","base_url":"https://collections.arolsen-archives.org","constraints":["sensitive_historical_person_data","purpose_limitation","privacy_and_terms_review","citation_required"]},
        {"source_id":"jewishgen_germany","title":"JewishGen Germany and family-tree databases","category":"genealogy_indexes","access_mode":"registered_guided_web","base_url":"https://www.jewishgen.org","constraints":["registration_may_be_required","index_or_user_submitted_data","independent_corroboration_required"]},
        {"source_id":"europeana_genealogy","title":"Europeana archival and genealogy discovery","category":"cultural_archive_discovery","access_mode":"api_key","base_url":"https://api.europeana.eu","constraints":["api_key_required","provider_rights_vary","metadata_is_discovery_lead"]},
    )

    SCORE_PATTERNS = (
        re.compile(r"(?i)\b(?:confidence|score|precision|reliability|zuverlässigkeit|präzision|prüfzahl)\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%?"),
        re.compile(r"(?<!\d)0[.,]\d{1,4}(?!\d)"),
    )

    def __init__(self, db: Any, audit: Any, *, actor: str = "system"):
        self.db = db
        self.audit = audit
        self.actor = actor

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "GENEALOGY SOURCES 1855 ERWEITERN":
            raise PermissionError("explicit source approval required")
        for item in self.SOURCE_PROFILES:
            payload = {**item, "status":"DOCUMENTED", "production_active":False}
            self.db.execute(
                "INSERT OR REPLACE INTO genealogy_source_profiles_1855 VALUES(?,?,?,?,?,?,?,?,?)",
                (item["source_id"], item["title"], item["category"], item["access_mode"], item["base_url"], dumps(item["constraints"]), "DOCUMENTED", now_ts(), _hash(payload)),
            )
        return {"created":len(self.SOURCE_PROFILES), "production_active":0, "review_required":True}

    def clean_external_query(self, text: str) -> str:
        value = str(text or "")
        for pattern in self.SCORE_PATTERNS:
            value = pattern.sub(" ", value)
        value = re.sub(r"[;,|]+", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" ,;|")
        return value

    def plan_search(self, *, case_id: str, person: Mapping[str, Any], source_ids: Sequence[str], lawful_basis: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"GENEALOGY 1855 {case_id} SUCHE PLANEN":
            raise PermissionError("explicit genealogy search approval required")
        if not lawful_basis.strip():
            raise ValueError("lawful basis required")
        allowed = {p["source_id"] if isinstance(p, tuple) else p["source_id"] for p in self.SOURCE_PROFILES}
        unknown = sorted(set(source_ids) - allowed)
        if unknown:
            raise ValueError(f"unknown source ids: {unknown}")
        name = self.clean_external_query(" ".join(str(person.get(k, "")) for k in ("given_name", "family_name", "birth_name")))
        place = self.clean_external_query(str(person.get("place", "")))
        years = [str(person.get(k, "")).strip() for k in ("birth_year", "death_year") if str(person.get(k, "")).strip()]
        query = self.clean_external_query(" ".join([name, place, *years]))
        if not query:
            raise ValueError("at least a name, place or year is required")
        search_id = new_id("gen1855")
        payload = {"search_id":search_id,"case_id":case_id,"query":query,"source_ids":list(source_ids),"lawful_basis":lawful_basis,"status":"planned","review_required":True}
        self.db.execute("INSERT INTO genealogy_searches_1855 VALUES(?,?,?,?,?,?,?,?,?)", (search_id,case_id,query,dumps(list(source_ids)),lawful_basis,"planned",now_ts(),self.actor,_hash(payload)))
        return payload

    def record_candidate(self, *, search_id: str, source_id: str, source_record_id: str, record: Mapping[str, Any], source_url: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"GENEALOGY 1855 {search_id} KANDIDAT SPEICHERN":
            raise PermissionError("explicit candidate capture required")
        if not source_url.startswith("https://"):
            raise ValueError("https source URL required")
        candidate_id = new_id("gencand1855")
        normalized = {
            "names": [str(x).strip() for x in record.get("names", []) if str(x).strip()],
            "birth": dict(record.get("birth") or {}),
            "death": dict(record.get("death") or {}),
            "relationships": list(record.get("relationships") or []),
            "record_type": str(record.get("record_type") or "genealogy_index"),
            "original_citation": str(record.get("citation") or ""),
        }
        payload={"candidate_id":candidate_id,"search_id":search_id,"source_id":source_id,"source_record_id":source_record_id,"source_url":source_url,"normalized":normalized,"status":"candidate","automatic_relationship_confirmation":False,"review_required":True}
        self.db.execute("INSERT INTO genealogy_candidates_1855 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (candidate_id,search_id,source_id,source_record_id,source_url,dumps(normalized),"candidate",0,now_ts(),self.actor,_hash(payload)))
        return payload

    def assess_relationship(self, *, case_id: str, subject_ref: str, related_ref: str, relationship_type: str, evidence: Sequence[Mapping[str, Any]], confirmation: str) -> dict[str, Any]:
        if confirmation != f"GENEALOGY 1855 {case_id} BEZIEHUNG PRUEFEN":
            raise PermissionError("explicit relationship review required")
        source_ids={str(x.get("source_id") or "") for x in evidence if x.get("source_id")}
        primary=sum(1 for x in evidence if x.get("evidence_class") in {"civil_register","church_register","official_archive"})
        status="corroborated_candidate" if len(source_ids)>=2 and primary>=1 else "insufficient_evidence"
        assessment_id=new_id("genrel1855")
        limitations=["genealogy_match_is_not_identity_confirmation","user_submitted_tree_is_not_primary_evidence","living_person_privacy_requires_review","human_review_required"]
        payload={"assessment_id":assessment_id,"case_id":case_id,"subject_ref":subject_ref,"related_ref":related_ref,"relationship_type":relationship_type,"status":status,"source_count":len(source_ids),"primary_evidence_count":primary,"limitations":limitations,"automatic_confirmation":False}
        self.db.execute("INSERT INTO genealogy_relationship_assessments_1855 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (assessment_id,case_id,subject_ref,related_ref,relationship_type,status,len(source_ids),primary,dumps(limitations),now_ts(),_hash(payload)))
        return payload

    def browser_contract(self) -> dict[str, Any]:
        return {"existing_firefox_session":True,"open_mode":"new_tab","separate_profile":False,"no_remote":False,"private_window":False,"internal_scores_in_external_query":False,"legacy_browser_fallback":False}
