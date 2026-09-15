from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote_plus

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build1856GuidedSourceRoutingService:
    """Beginner-friendly workflow and question-aware source routing.

    The service chooses source *classes* and creates source-specific launch plans.
    It does not claim that a source result identifies a person and does not send
    internal scores or review metadata to an external service.
    """

    BUILD = "185.6"
    SOURCE_PROFILES = (
        {"source_id":"archivportal_d","title":"Archivportal-D","category":"official_archive_discovery","authority":"primary_discovery","access_mode":"guided_public_web","base_url":"https://www.archivportal-d.de","search_url":"https://www.archivportal-d.de/suche?query={query}","intents":["historical_record","family_history","occupation","residence","death"],"constraints":["archive_holdings_vary","record_access_may_be_restricted","manual_record_review"]},
        {"source_id":"deutsche_digitale_bibliothek","title":"Deutsche Digitale Bibliothek","category":"cultural_archive_discovery","authority":"primary_discovery","access_mode":"public_search_api_key_optional","base_url":"https://www.deutsche-digitale-bibliothek.de","search_url":"https://www.deutsche-digitale-bibliothek.de/searchresults?query={query}","intents":["historical_record","family_history","occupation","media_provenance"],"constraints":["provider_rights_vary","metadata_is_discovery_lead","api_key_for_api"]},
        {"source_id":"bundesarchiv_invenio","title":"Bundesarchiv invenio","category":"federal_archive_catalogue","authority":"official_archive","access_mode":"guided_public_web","base_url":"https://invenio.bundesarchiv.de","search_url":"https://invenio.bundesarchiv.de/invenio/main.xhtml","intents":["historical_record","occupation","military_history","organization","residence"],"constraints":["registration_or_ordering_may_be_required","person_data_protection","manual_catalogue_search"]},
        {"source_id":"dnb_gnd","title":"Deutsche Nationalbibliothek GND","category":"authority_identifiers","authority":"curated_authority_file","access_mode":"public_sru_and_linked_data","base_url":"https://www.dnb.de","search_url":"https://portal.dnb.de/opac.htm?method=simpleSearch&query={query}","intents":["identity","name_variant","occupation","publication","organization"],"constraints":["authority_record_not_identity_proof","manual_disambiguation_required"]},
        {"source_id":"archives_portal_europe","title":"Archives Portal Europe","category":"european_archive_discovery","authority":"primary_discovery","access_mode":"guided_public_web","base_url":"https://archivesportaleurope.net","search_url":"https://archivesportaleurope.net/search/-/s?query={query}","intents":["historical_record","family_history","migration","residence","organization"],"constraints":["cross_archive_metadata","holding_institution_rules","manual_record_review"]},
        {"source_id":"familysearch_catalog","title":"FamilySearch Catalog","category":"genealogy_catalogue","authority":"catalogue_and_index","access_mode":"registered_guided_web","base_url":"https://www.familysearch.org/search/catalog","search_url":"https://www.familysearch.org/search/catalog/results?count=20&query=%2Bkeywords%3A{query}","intents":["birth","death","marriage","family_history","residence"],"constraints":["account_may_be_required","image_restrictions_vary","index_is_not_primary_record"]},
        {"source_id":"grabsteine_compgen","title":"CompGen Grabsteine","category":"cemetery_memorial_index","authority":"compiled_index","access_mode":"guided_public_web","base_url":"https://grabsteine.genealogy.net","search_url":"https://grabsteine.genealogy.net/search.php?nachname={family_name}&vorname={given_name}","intents":["death","burial","family_history","residence"],"constraints":["compiled_index","image_and_transcription_require_review","not_complete"]},
        {"source_id":"govdata_source_discovery","title":"GovData Quellen- und Datensatzsuche","category":"official_open_data_discovery","authority":"official_metadata_portal","access_mode":"public_web_and_api","base_url":"https://www.govdata.de","search_url":"https://www.govdata.de/suche/-/searchresult/q/{query}","intents":["official_dataset","location","organization","statistics","public_register"],"constraints":["dataset_licence_varies","aggregated_data_not_person_identity"]},
    )

    INTENT_RULES = {
        "birth": ("geboren", "geburt", "geburtsdatum", "taufe", "baptism", "birth"),
        "death": ("gestorben", "tod", "sterbe", "beerdigt", "grab", "friedhof", "death", "burial"),
        "marriage": ("heirat", "verheiratet", "trauung", "ehe", "marriage", "wedding"),
        "family_history": ("eltern", "mutter", "vater", "kind", "geschwister", "vorfahr", "stammbaum", "familie", "genealog"),
        "residence": ("wohnte", "wohnort", "adresse", "aufenthalt", "lebte", "residence"),
        "occupation": ("beruf", "arbeitete", "tätig", "funktion", "occupation", "profession"),
        "publication": ("buch", "autor", "publikation", "artikel", "publication"),
        "organization": ("firma", "unternehmen", "verein", "organisation", "behörde", "company"),
        "military_history": ("wehrmacht", "bundeswehr", "soldat", "militär", "military"),
        "migration": ("ausgewandert", "eingewandert", "migration", "emigration", "immigration"),
        "media_provenance": ("bild", "foto", "video", "aufnahme", "quelle des bildes", "provenienz"),
        "identity": ("wer ist", "identität", "identifizieren", "name", "person"),
        "name_variant": ("alias", "geburtsname", "namensvariante", "schreibweise"),
        "location": ("ort", "wo", "adresse", "region", "geograf"),
        "official_dataset": ("datensatz", "open data", "statistik", "register"),
        "public_register": ("register", "amtlich", "behördlich"),
        "historical_record": ("historisch", "archiv", "akte", "urkunde", "dokument"),
    }

    def __init__(self, db: Any, audit: Any, *, genealogy: Any | None = None, actor: str = "system"):
        self.db = db
        self.audit = audit
        self.genealogy = genealogy
        self.actor = actor

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "GUIDED SOURCES 1856 ERWEITERN":
            raise PermissionError("explicit source approval required")
        for item in self.SOURCE_PROFILES:
            payload = {**item, "status":"DOCUMENTED", "production_active":False}
            self.db.execute(
                "INSERT OR REPLACE INTO guided_source_profiles_1856 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["source_id"],item["title"],item["category"],item["authority"],item["access_mode"],item["base_url"],item["search_url"],dumps(item["intents"]),dumps(item["constraints"]),"DOCUMENTED",now_ts(),_hash(payload)),
            )
        return {"created":len(self.SOURCE_PROFILES),"production_active":0,"review_required":True}

    def classify_question(self, question: str) -> dict[str, Any]:
        text = re.sub(r"\s+", " ", str(question or "").strip()).casefold()
        if not text:
            raise ValueError("question required")
        matched=[]
        for intent, terms in self.INTENT_RULES.items():
            hits=sum(1 for term in terms if term in text)
            if hits:
                matched.append((intent,hits))
        matched.sort(key=lambda x:(-x[1],x[0]))
        intents=[x[0] for x in matched] or ["identity"]
        return {"question":question,"intents":intents,"method":"deterministic_keyword_routing","review_required":True}

    def _profile_map(self) -> dict[str, Mapping[str, Any]]:
        profiles={p["source_id"]:p for p in self.SOURCE_PROFILES}
        if self.genealogy is not None:
            profiles.update({p["source_id"]:p for p in self.genealogy.SOURCE_PROFILES})
        return profiles

    def route_question(self, *, case_id: str, question: str, person: Mapping[str, Any], lawful_basis: str, max_sources: int = 8, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE ROUTING 1856 {case_id} PLANEN":
            raise PermissionError("explicit routing approval required")
        if not lawful_basis.strip():
            raise ValueError("lawful basis required")
        if not 1 <= int(max_sources) <= 12:
            raise ValueError("max_sources must be between 1 and 12")
        classified=self.classify_question(question)
        profiles=self._profile_map()
        ranked=[]
        for source_id, profile in profiles.items():
            intents=set(profile.get("intents") or self._fallback_intents(profile.get("category","")))
            overlap=[i for i in classified["intents"] if i in intents]
            if not overlap:
                continue
            authority=profile.get("authority") or self._authority_for(profile.get("category",""))
            authority_score={"official_archive":5,"primary_discovery":4,"curated_authority_file":4,"official_metadata_portal":4,"catalogue_and_index":3,"compiled_index":2,"user_submitted":1}.get(authority,2)
            ranked.append((len(overlap)*10+authority_score,source_id,profile,overlap,authority))
        ranked.sort(key=lambda x:(-x[0],x[1]))
        chosen=ranked[:int(max_sources)]
        query=self._build_query(person, classified["intents"])
        route_id=new_id("route1856")
        steps=[]
        for position,(_,source_id,profile,overlap,authority) in enumerate(chosen,1):
            url=self._build_url(profile,person,query)
            steps.append({"position":position,"source_id":source_id,"title":profile["title"],"authority":authority,"matched_intents":overlap,"query":query,"launch_url":url,"access_mode":profile["access_mode"],"constraints":list(profile.get("constraints") or []),"result_status":"candidate_only"})
        payload={"route_id":route_id,"case_id":case_id,"question":question,"intents":classified["intents"],"query":query,"steps":steps,"lawful_basis":lawful_basis,"workflow":["Person und Auftrag","Gezielte Quellen","Treffer als Kandidaten","Prüfen und korroborieren","Auswertung","Fallakte"],"general_search_is_secondary":True,"automatic_identity_confirmation":False,"review_required":True}
        self.db.execute("INSERT INTO guided_research_routes_1856 VALUES(?,?,?,?,?,?,?,?,?,?)",(route_id,case_id,question,dumps(classified["intents"]),query,dumps(steps),lawful_basis,now_ts(),self.actor,_hash(payload)))
        return payload

    def _fallback_intents(self, category: str) -> list[str]:
        c=str(category)
        if "church" in c or "vital" in c: return ["birth","death","marriage","family_history"]
        if "genealogy" in c or "family" in c: return ["family_history","birth","death","marriage"]
        if "historical" in c or "archive" in c: return ["historical_record","residence","family_history"]
        return ["identity"]

    def _authority_for(self, category: str) -> str:
        c=str(category)
        if "church_vital" in c: return "official_archive"
        if "historical_person" in c: return "official_archive"
        if "user_submitted" in c: return "user_submitted"
        if "compiled" in c or "index" in c: return "compiled_index"
        return "primary_discovery"

    def _build_query(self, person: Mapping[str, Any], intents: Sequence[str]) -> str:
        parts=[]
        for key in ("given_name","family_name","birth_name","place","birth_year","death_year"):
            value=str(person.get(key) or "").strip()
            if value: parts.append(value)
        if self.genealogy is not None:
            query=self.genealogy.clean_external_query(" ".join(parts))
        else:
            query=re.sub(r"\s+"," "," ".join(parts)).strip()
        if not query:
            raise ValueError("person name, place or year required")
        return query

    def _build_url(self, profile: Mapping[str, Any], person: Mapping[str, Any], query: str) -> str:
        template=str(profile.get("search_url") or profile.get("base_url") or "")
        if "{" not in template:
            return template
        values={
            "query":quote_plus(query),
            "given_name":quote_plus(str(person.get("given_name") or "")),
            "family_name":quote_plus(str(person.get("family_name") or "")),
            "place":quote_plus(str(person.get("place") or "")),
        }
        try: return template.format(**values)
        except KeyError: return str(profile.get("base_url") or "")

    def workflow_guide(self) -> dict[str, Any]:
        return {"mode":"guided_beginner","steps":[
            {"number":1,"title":"Person & Auftrag","question":"Wen untersuchst du und was soll geklärt werden?","completion":["Personendaten","Fragestellung","Rechtsgrundlage"]},
            {"number":2,"title":"Gezielte Quellen","question":"Welche Quellen passen genau zu dieser Fragestellung?","completion":["Quellenroute","Priorität","Zugriffsart"]},
            {"number":3,"title":"Treffer prüfen","question":"Ist es dieselbe Person und ist die Quelle belastbar?","completion":["Kandidat","Primärquelle","Zweitquelle","Widersprüche"]},
            {"number":4,"title":"Auswertung","question":"Welche Erkenntnis ist belegt und welche bleibt Hypothese?","completion":["Timeline","Beziehungen","Unsicherheit"]},
            {"number":5,"title":"Fallakte","question":"Welche geprüften Befunde dürfen übernommen werden?","completion":["Zitate","Provenienz","Review","Export"]},
        ],"candidate_not_claim":True,"next_step_always_visible":True,"technical_build_names_hidden":True}
