from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build188RecordsDeepIntegrationService:
    """Progressive activation of German and European records sources.

    This service deliberately separates documentation, fixture validation, live validation,
    production readiness and activation. No stage is inferred from a catalogue entry.
    """

    BUILD = "188.0"
    STAGES = (
        "DOCUMENTED", "CONTRACT_VALIDATED", "FIXTURE_VALIDATED", "LIVE_VALIDATED",
        "PRODUCTION_READY", "PRODUCTION_ACTIVE", "DEGRADED", "SUSPENDED"
    )
    PRIMARY_SOURCES = (
        {
            "source_id": "de_bundestag_dip", "title": "Deutscher Bundestag DIP", "family": "parliament",
            "authority": "official_primary", "endpoint": "https://search.dip.bundestag.de/api/v1",
            "access_mode": "rest_json", "auth": "api_key", "query_template": "/person?f.person={query}",
            "parser_version": "dip-person-v1", "required": ["documents"], "wave": 1,
        },
        {
            "source_id": "global_gleif_lei", "title": "GLEIF LEI API", "family": "organization",
            "authority": "official_primary", "endpoint": "https://api.gleif.org/api/v1",
            "access_mode": "rest_json", "auth": "none", "query_template": "/lei-records?filter[entity.legalName]={query}",
            "parser_version": "gleif-lei-v1", "required": ["data"], "wave": 1,
        },
        {
            "source_id": "dnb_gnd", "title": "DNB Gemeinsame Normdatei", "family": "authority_file",
            "authority": "curated_authority", "endpoint": "https://services.dnb.de/sru/authorities",
            "access_mode": "sru_xml", "auth": "none", "query_template": "?version=1.1&operation=searchRetrieve&query=PER={query}",
            "parser_version": "gnd-sru-v1", "required": ["records"], "wave": 1,
        },
        {
            "source_id": "govdata_source_discovery", "title": "GovData CKAN", "family": "open_data",
            "authority": "official_catalog", "endpoint": "https://ckan.govdata.de/api/3/action",
            "access_mode": "rest_json", "auth": "none", "query_template": "/package_search?q={query}",
            "parser_version": "govdata-ckan-v1", "required": ["success", "result"], "wave": 1,
        },
        {
            "source_id": "eu_parliament_open_data", "title": "European Parliament Open Data", "family": "parliament",
            "authority": "official_primary", "endpoint": "https://data.europarl.europa.eu/api/v2",
            "access_mode": "rest_jsonld", "auth": "none", "query_template": "/meps?label={query}",
            "parser_version": "ep-open-data-v1", "required": ["data"], "wave": 2,
        },
        {
            "source_id": "eu_cellar_multilingual", "title": "EU Publications Office Cellar", "family": "publications",
            "authority": "official_primary", "endpoint": "https://publications.europa.eu/webapi/rdf/sparql",
            "access_mode": "sparql", "auth": "none", "query_template": "?query={query}",
            "parser_version": "cellar-sparql-v1", "required": ["results"], "wave": 2,
        },
        {
            "source_id": "eu_ted_procurement", "title": "TED Search API", "family": "procurement",
            "authority": "official_primary", "endpoint": "https://api.ted.europa.eu/v3/notices/search",
            "access_mode": "rest_json", "auth": "api_key_or_public", "query_template": "POST search:{query}",
            "parser_version": "ted-search-v1", "required": ["notices"], "wave": 2,
        },
        {
            "source_id": "eu_data_portal", "title": "data.europa.eu Search", "family": "open_data",
            "authority": "official_catalog", "endpoint": "https://data.europa.eu/api/hub/search",
            "access_mode": "rest_json", "auth": "none", "query_template": "/datasets/{query}",
            "parser_version": "dataeu-search-v1", "required": ["result"], "wave": 2,
        },
        {
            "source_id": "archivportal_d", "title": "Archivportal-D", "family": "archive",
            "authority": "official_archive_index", "endpoint": "https://www.archivportal-d.de",
            "access_mode": "guided_browser", "auth": "none", "query_template": "/search?query={query}",
            "parser_version": "guided-only", "required": ["records"], "wave": 3,
        },
        {
            "source_id": "matricula_online", "title": "Matricula Online", "family": "vital_records",
            "authority": "primary_archive_images", "endpoint": "https://data.matricula-online.eu",
            "access_mode": "guided_browser", "auth": "none", "query_template": "/de/suchen/?q={query}",
            "parser_version": "guided-only", "required": ["records"], "wave": 3,
        },
    )

    def __init__(self, db: Any, audit: Any, *, source_ops: Any, guided_router: Any, actor: str = "system"):
        self.db, self.audit, self.source_ops, self.guided_router, self.actor = db, audit, source_ops, guided_router, actor

    def seed_contracts(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RECORD SOURCES 188 ANLEGEN":
            raise PermissionError("explicit approval required")
        created = 0
        for item in self.PRIMARY_SOURCES:
            payload = dict(item)
            self.db.execute(
                "INSERT OR REPLACE INTO records_source_contracts_188 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["source_id"], item["title"], item["family"], item["authority"], item["endpoint"],
                 item["access_mode"], item["auth"], item["query_template"], item["parser_version"],
                 dumps(item["required"]), int(item["wave"]), "CONTRACT_VALIDATED", 0, now_ts(), _hash(payload)),
            )
            created += 1
        self._event("contracts_seeded", "*", {"count": created})
        return {"created": created, "production_active": 0, "automatic_activation": False}

    def validate_fixture(self, source_id: str, fixture: Mapping[str, Any], *, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RECORD FIXTURE 188 {source_id} VALIDIEREN":
            raise PermissionError("explicit approval required")
        contract = self._contract(source_id)
        required = json.loads(contract["required_fields_json"])
        missing = [field for field in required if field not in fixture]
        if missing:
            raise ValueError(f"missing fixture fields: {', '.join(missing)}")
        normalized = self._parse(source_id, fixture)
        fid = new_id("fixture188")
        payload = {"fixture_id": fid, "source_id": source_id, "fixture": fixture, "normalized_count": len(normalized)}
        self.db.execute("INSERT INTO records_source_fixtures_188 VALUES(?,?,?,?,?,?,?)",
                        (fid, source_id, dumps(fixture), 1, len(normalized), now_ts(), _hash(payload)))
        self._transition(source_id, "FIXTURE_VALIDATED", approved_by="fixture-validator", blockers=[])
        return {"source_id": source_id, "parser_ok": True, "normalized_count": len(normalized), "status": "FIXTURE_VALIDATED"}

    def record_live_probe(self, source_id: str, *, http_status: int, content_type: str, latency_ms: int,
                          parser_ok: bool, terms_reviewed: bool, records_received: int, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RECORD LIVE 188 {source_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        self._contract(source_id)
        pid = new_id("probe188"); observed = now_ts()
        payload = {"probe_id": pid, "source_id": source_id, "http_status": int(http_status),
                   "content_type": content_type, "latency_ms": max(0, int(latency_ms)), "parser_ok": bool(parser_ok),
                   "terms_reviewed": bool(terms_reviewed), "records_received": max(0, int(records_received)), "observed_at": observed}
        self.db.execute("INSERT INTO records_source_probes_188 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (pid, source_id, payload["http_status"], content_type, payload["latency_ms"], int(parser_ok),
                         int(terms_reviewed), payload["records_received"], observed, _hash(payload)))
        healthy = 200 <= int(http_status) < 300 and parser_ok
        try:
            self.source_ops.record_health(source_id, health_status="healthy" if healthy else "down",
                                          http_status=http_status, latency_ms=latency_ms, records_received=records_received,
                                          error_code="" if healthy else "live_probe_failed",
                                          error_message="" if healthy else "Live parser or HTTP probe failed",
                                          confirmation=f"SOURCE HEALTH 187 {source_id} SPEICHERN")
        except KeyError:
            pass
        if healthy and terms_reviewed and self._has_fixture(source_id):
            self._transition(source_id, "LIVE_VALIDATED", approved_by="live-validator", blockers=[])
        return {**payload, "healthy": healthy, "status": self._contract(source_id)["status"], "automatic_activation": False}

    def promote(self, source_id: str, *, target: str, approved_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RECORD SOURCE 188 {source_id} {target} FREIGEBEN":
            raise PermissionError("explicit approval required")
        if target not in {"PRODUCTION_READY", "PRODUCTION_ACTIVE"}:
            raise ValueError("unsupported promotion target")
        row = self._contract(source_id)
        blockers = self._blockers(source_id, target)
        if blockers:
            self._transition(source_id, row["status"], approved_by=approved_by, blockers=blockers)
            return {"source_id": source_id, "status": row["status"], "promoted": False, "blockers": blockers}
        if target == "PRODUCTION_ACTIVE" and row["status"] != "PRODUCTION_READY":
            return {"source_id": source_id, "status": row["status"], "promoted": False, "blockers": ["production_ready_required"]}
        self._transition(source_id, target, approved_by=approved_by, blockers=[])
        if target == "PRODUCTION_ACTIVE":
            self.db.execute("UPDATE records_source_contracts_188 SET production_active=1,updated_at=? WHERE source_id=?", (now_ts(), source_id))
        return {"source_id": source_id, "status": target, "promoted": True, "blockers": [], "automatic_activation": False}

    def activation_board(self) -> dict[str, Any]:
        rows = [dict(r) for r in self.db.all("SELECT * FROM records_source_contracts_188 ORDER BY activation_wave,status,title")]
        cards = []
        counts = {"total": len(rows), "active": 0, "ready": 0, "live_validated": 0, "blocked": 0}
        for row in rows:
            if row["production_active"]: counts["active"] += 1
            if row["status"] == "PRODUCTION_READY": counts["ready"] += 1
            if row["status"] == "LIVE_VALIDATED": counts["live_validated"] += 1
            blockers = self._blockers(row["source_id"], "PRODUCTION_READY")
            if blockers: counts["blocked"] += 1
            cards.append({
                "source_id": row["source_id"], "title": row["title"], "wave": row["activation_wave"],
                "status": row["status"], "production_active": bool(row["production_active"]),
                "access_mode": row["access_mode"], "authority": row["authority"], "blockers": blockers,
                "next_action": self._next_action(row, blockers),
            })
        return {"build": self.BUILD, "counts": counts, "sources": cards,
                "activation_policy": "one_source_at_a_time", "automatic_activation": False,
                "global_workflow": "question -> source -> candidate -> verification -> case file"}

    def route_question(self, *, case_id: str, question: str, person: Mapping[str, Any], lawful_basis: str,
                       confirmation: str) -> dict[str, Any]:
        base = self.guided_router.route_question(case_id=case_id, question=question, person=person, lawful_basis=lawful_basis,
                                                confirmation=confirmation)
        states = {r["source_id"]: r for r in self.activation_board()["sources"]}
        steps = []
        for step in base.get("steps", []):
            item = dict(step); state = states.get(item.get("source_id"))
            if state:
                item.update({"production_status": state["status"], "production_active": state["production_active"],
                             "activation_wave": state["wave"], "next_source_action": state["next_action"]})
                item["execution_mode"] = "structured_connector" if state["production_active"] else "guided_browser_tab"
            steps.append(item)
        steps.sort(key=lambda x: (not x.get("production_active", False), int(x.get("activation_wave", 99)), int(x.get("priority", 99))))
        return {**base, "steps": steps, "candidate_only": True, "automatic_identity_confirmation": False,
                "next_global_step": "3_verify_candidates"}

    def normalize_candidate(self, *, case_id: str, source_id: str, record: Mapping[str, Any], source_ref: str,
                            confirmation: str) -> dict[str, Any]:
        if confirmation != f"RECORD CANDIDATE 188 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        self._contract(source_id)
        parsed = self._parse(source_id, record)
        saved = []
        for item in parsed:
            cid = new_id("record188"); observed = now_ts()
            payload = {"candidate_id": cid, "case_id": case_id, "source_id": source_id,
                       "source_record_id": str(item.get("source_record_id", "")), "entity_type": item.get("entity_type", "unknown"),
                       "names": item.get("names", []), "identifiers": item.get("identifiers", {}), "dates": item.get("dates", {}),
                       "places": item.get("places", []), "relationships": item.get("relationships", []),
                       "source_ref": source_ref, "observed_at": observed, "review_status": "candidate"}
            self.db.execute("INSERT INTO records_normalized_candidates_188 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (cid, case_id, source_id, payload["source_record_id"], payload["entity_type"], dumps(payload["names"]),
                             dumps(payload["identifiers"]), dumps(payload["dates"]), dumps(payload["places"]),
                             dumps(payload["relationships"]), source_ref, observed, "candidate", _hash(payload)))
            saved.append(payload)
        return {"saved": len(saved), "candidates": saved, "automatic_identity_confirmation": False, "human_review_required": True}

    def _parse(self, source_id: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        if source_id == "global_gleif_lei":
            rows = payload.get("data", [])
            return [{"source_record_id": r.get("id", ""), "entity_type": "organization",
                     "names": [(((r.get("attributes") or {}).get("entity") or {}).get("legalName") or {}).get("name", "")],
                     "identifiers": {"lei": r.get("id", "")}, "dates": {},
                     "places": [(((r.get("attributes") or {}).get("entity") or {}).get("legalAddress") or {}).get("city", "")],
                     "relationships": []} for r in rows]
        if source_id == "de_bundestag_dip":
            rows = payload.get("documents", [])
            return [{"source_record_id": str(r.get("id", "")), "entity_type": "person",
                     "names": [r.get("name", r.get("vorname", "") + " " + r.get("nachname", ""))],
                     "identifiers": {"dip_id": r.get("id")}, "dates": {"birth": r.get("geburtsdatum")},
                     "places": [r.get("geburtsort", "")], "relationships": r.get("funktionen", [])} for r in rows]
        if source_id == "dnb_gnd":
            rows = payload.get("records", [])
            return [{"source_record_id": str(r.get("gnd_id", "")), "entity_type": r.get("entity_type", "person"),
                     "names": [r.get("preferred_name", "")] + list(r.get("variant_names", [])),
                     "identifiers": {"gnd": r.get("gnd_id")}, "dates": r.get("dates", {}),
                     "places": list(r.get("places", [])), "relationships": list(r.get("relationships", []))} for r in rows]
        if source_id == "govdata_source_discovery":
            result = payload.get("result", {})
            rows = result.get("results", []) if isinstance(result, Mapping) else []
            return [{"source_record_id": str(r.get("id", "")), "entity_type": "dataset",
                     "names": [r.get("title", "")], "identifiers": {"dataset_id": r.get("id")},
                     "dates": {"modified": r.get("metadata_modified")}, "places": [], "relationships": []} for r in rows]
        generic = payload.get("data") or payload.get("notices") or payload.get("result") or payload.get("records") or []
        if isinstance(generic, Mapping): generic = generic.get("results", [])
        if not isinstance(generic, Sequence) or isinstance(generic, (str, bytes)): generic = []
        return [{"source_record_id": str(r.get("id", "")), "entity_type": r.get("type", "record"),
                 "names": [r.get("title", r.get("name", ""))], "identifiers": {}, "dates": {}, "places": [], "relationships": []}
                for r in generic if isinstance(r, Mapping)]

    def _contract(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM records_source_contracts_188 WHERE source_id=?", (source_id,))
        if not row: raise KeyError(source_id)
        return dict(row)

    def _has_fixture(self, source_id: str) -> bool:
        return bool(self.db.one("SELECT fixture_id FROM records_source_fixtures_188 WHERE source_id=? AND parser_ok=1 ORDER BY created_at DESC LIMIT 1", (source_id,)))

    def _latest_probe(self, source_id: str) -> Mapping[str, Any] | None:
        row = self.db.one("SELECT * FROM records_source_probes_188 WHERE source_id=? ORDER BY observed_at DESC LIMIT 1", (source_id,))
        return dict(row) if row else None

    def _blockers(self, source_id: str, target: str) -> list[str]:
        row = self._contract(source_id); blockers = []
        if not self._has_fixture(source_id): blockers.append("fixture_not_validated")
        probe = self._latest_probe(source_id)
        if not probe: blockers.append("live_probe_missing")
        else:
            if not (200 <= int(probe["http_status"] or 0) < 300): blockers.append("http_probe_failed")
            if not probe["parser_ok"]: blockers.append("live_parser_failed")
            if not probe["terms_reviewed"]: blockers.append("terms_not_reviewed")
        if target == "PRODUCTION_ACTIVE" and row["status"] != "PRODUCTION_READY": blockers.append("production_ready_required")
        return blockers

    def _transition(self, source_id: str, target: str, *, approved_by: str, blockers: list[str]) -> None:
        row = self._contract(source_id); aid = new_id("activation188"); created = now_ts()
        payload = {"activation_id": aid, "source_id": source_id, "from": row["status"], "to": target,
                   "approved_by": approved_by, "blockers": blockers, "created_at": created}
        self.db.execute("INSERT INTO records_source_activations_188 VALUES(?,?,?,?,?,?,?,?)",
                        (aid, source_id, row["status"], target, approved_by, dumps(blockers), created, _hash(payload)))
        if not blockers:
            self.db.execute("UPDATE records_source_contracts_188 SET status=?,updated_at=? WHERE source_id=?", (target, created, source_id))
        self._event("source_transition", source_id, payload)

    @staticmethod
    def _next_action(row: Mapping[str, Any], blockers: list[str]) -> str:
        if row.get("production_active"): return "Produktive Quelle überwachen und Parserversion pflegen"
        mapping = {
            "fixture_not_validated": "Fixture und Parservertrag validieren",
            "live_probe_missing": "Reale Live-Probe ausführen",
            "http_probe_failed": "Endpunkt und HTTP-Antwort prüfen",
            "live_parser_failed": "Parser an reale Antwort anpassen",
            "terms_not_reviewed": "Nutzungsbedingungen dokumentieren",
            "production_ready_required": "Zuerst Production Ready freigeben",
        }
        return mapping.get(blockers[0], "Source Gate prüfen") if blockers else "Production Ready freigeben"

    def _event(self, event_type: str, source_id: str, payload: Mapping[str, Any]) -> None:
        prev = self.db.one("SELECT event_sha256 FROM records_operations_events_188 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        prev_sha = prev["event_sha256"] if prev else "0" * 64
        eid = new_id("recordevt188"); created = now_ts()
        digest = _hash({"event_id": eid, "event_type": event_type, "source_id": source_id,
                        "payload": payload, "created_at": created, "actor": self.actor, "prev": prev_sha})
        self.db.execute("INSERT INTO records_operations_events_188 VALUES(?,?,?,?,?,?,?,?)",
                        (eid, event_type, source_id, dumps(payload), created, self.actor, prev_sha, digest))
