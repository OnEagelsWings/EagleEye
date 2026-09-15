from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


class ResearchStrategyValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConnectorSpec128:
    connector_key: str
    label: str
    provider_key: str
    connector_type: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    execution_mode: str
    allowed_hosts: tuple[str, ...]
    terms_profile: str
    network_policy: str = "human_approved"
    query_minimization: str = "required"


CONNECTORS_128: tuple[ConnectorSpec128, ...] = (
    ConnectorSpec128("rdap_domain_128", "RDAP Domain Registry", "rdap_public_120", "registry", ("domain",), ("domain_record", "nameserver"), "controlled_provider", ("rdap.org",), "Public RDAP metadata; domain context only."),
    ConnectorSpec128("github_profile_128", "GitHub Public Profile", "github_public_profile_120", "code_profile", ("username",), ("public_profile",), "controlled_provider", ("api.github.com",), "Public profile metadata; username equality is not identity proof."),
    ConnectorSpec128("gitlab_profile_128", "GitLab Public Profile", "gitlab_public_profile_120", "code_profile", ("username",), ("public_profile",), "controlled_provider", ("gitlab.com",), "Public profile metadata; username equality is not identity proof."),
    ConnectorSpec128("wayback_index_128", "Wayback CDX Index", "wayback_cdx_public_120", "web_archive", ("public_url", "domain"), ("archive_snapshot",), "controlled_provider", ("web.archive.org",), "Public archive index metadata; capture and review remain separate."),
    ConnectorSpec128("crossref_works_128", "Crossref Works", "crossref_works_public_128", "scholarly_metadata", ("name", "organisation", "identifier"), ("publication", "doi"), "controlled_provider", ("api.crossref.org",), "Public scholarly metadata; author-name matches require human disambiguation."),
    ConnectorSpec128("openalex_authors_128", "OpenAlex Authors", "openalex_authors_public_128", "scholarly_identity", ("name", "organisation", "identifier"), ("author_profile", "institution"), "controlled_provider", ("api.openalex.org",), "Open scholarly metadata; profiles remain candidates until reviewed."),
    ConnectorSpec128("internet_archive_128", "Internet Archive Search", "internet_archive_public_128", "public_archive", ("name", "organisation", "keyword"), ("archive_item",), "controlled_provider", ("archive.org",), "Public metadata search; item content requires separate capture."),
    ConnectorSpec128("wikidata_entities_128", "Wikidata Entity Search", "wikidata_entities_public_128", "knowledge_base", ("name", "alias", "organisation", "location"), ("knowledge_entity",), "controlled_provider", ("www.wikidata.org",), "Community-maintained public metadata; not an identity confirmation."),
    ConnectorSpec128("europe_pmc_128", "Europe PMC Search", "europe_pmc_public_128", "scholarly_metadata", ("name", "organisation", "identifier"), ("publication", "author_record"), "controlled_provider", ("www.ebi.ac.uk",), "Public biomedical literature metadata; author matches require review."),
    ConnectorSpec128("openlibrary_authors_128", "Open Library Authors", "openlibrary_authors_public_128", "bibliographic_identity", ("name", "alias"), ("author_record", "work_reference"), "controlled_provider", ("openlibrary.org",), "Public bibliographic metadata; names may be ambiguous."),
)

_TOKEN_RE = re.compile(r"[\w@.-]+", re.UNICODE)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _sha(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = dumps(value)
    else:
        text = str(value or "")
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _tokens(*values: Any) -> set[str]:
    text = " ".join(str(v or "") for v in values).casefold()
    return {token for token in _TOKEN_RE.findall(text) if len(token) > 2}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


class ResearchStrategy128Service:
    """Query-graph, source-intelligence and connector-SDK foundation.

    The service never performs autonomous network access. It prepares a bounded
    strategy from reviewed person anchors, registers public-only connectors and
    stores all AI-derived material as ``suggestions_only``.
    """

    def __init__(self, db: Any, audit: Any, *, cases: Any, targets: Any, scale: Any, providers: Any, protection: Any) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets
        self.scale = scale
        self.providers = providers
        self.protection = protection
        self.ensure_schema()
        self._seed_connectors()

    def ensure_schema(self) -> None:
        from eagleeye.infrastructure.research_strategy.schema import ensure_research_strategy_schema_128

        ensure_research_strategy_schema_128(self.db)

    def _seed_connectors(self) -> None:
        stamp = now_ts()
        provider_rows = {row["provider_key"]: row for row in self.providers.list_providers(enabled_only=False)}
        with self.db.transaction(immediate=True):
            for spec in CONNECTORS_128:
                provider = provider_rows.get(spec.provider_key, {})
                enabled = bool(provider.get("enabled", True))
                self.db.execute(
                    """INSERT INTO connector_catalog_128(
                      connector_key,label,connector_version,provider_key,connector_type,input_types_json,
                      output_types_json,execution_mode,public_only,network_policy,query_minimization,
                      allowed_hosts_json,terms_profile,enabled,metadata_json,updated_at)
                      VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?)
                      ON CONFLICT(connector_key) DO UPDATE SET
                        label=excluded.label,connector_version=excluded.connector_version,
                        provider_key=excluded.provider_key,connector_type=excluded.connector_type,
                        input_types_json=excluded.input_types_json,output_types_json=excluded.output_types_json,
                        execution_mode=excluded.execution_mode,network_policy=excluded.network_policy,
                        query_minimization=excluded.query_minimization,allowed_hosts_json=excluded.allowed_hosts_json,
                        terms_profile=excluded.terms_profile,enabled=excluded.enabled,
                        metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                    (
                        spec.connector_key, spec.label, "1.0", spec.provider_key, spec.connector_type,
                        dumps(spec.input_types), dumps(spec.output_types), spec.execution_mode,
                        spec.network_policy, spec.query_minimization, dumps(spec.allowed_hosts),
                        spec.terms_profile, int(enabled),
                        dumps({"provider_registered": bool(provider), "candidate_only": True, "automatic_promotion": False}),
                        stamp,
                    ),
                )

    def status(self) -> dict[str, Any]:
        return {
            "build": "128.0",
            "mode": "query_graph_source_intelligence_connector_sdk",
            "connectors": len(self.list_connectors()),
            "external_network_default": "blocked_until_human_provider_approval",
            "ai_trust_state": "suggestions_only",
            "automatic_identity_confirmation": False,
            "automatic_evidence_promotion": False,
            "legacy_runtime_policy": "canonical_services_only",
        }

    def list_connectors(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM connector_catalog_128 ORDER BY connector_type,label")
        for row in rows:
            row["input_types"] = loads(row.pop("input_types_json", "[]"), [])
            row["output_types"] = loads(row.pop("output_types_json", "[]"), [])
            row["allowed_hosts"] = loads(row.pop("allowed_hosts_json", "[]"), [])
            row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
            row["enabled"] = bool(row.get("enabled"))
            row["public_only"] = bool(row.get("public_only"))
        return rows

    def _require_target(self, case_id: str, target_id: str) -> dict[str, Any]:
        self.cases.get_case(case_id)
        target = self.targets.get_target(target_id)
        if target.get("case_id") != case_id:
            raise ResearchStrategyValidationError("Fall-/Zielbindung verletzt")
        return target

    @staticmethod
    def _connector_matches(connector: dict[str, Any], anchor_types: set[str], category: str) -> bool:
        inputs = set(connector.get("input_types") or [])
        if inputs & anchor_types:
            return True
        lowered = category.casefold()
        ctype = str(connector.get("connector_type") or "")
        return any(
            (
                "dokument" in lowered and ctype in {"scholarly_metadata", "public_archive", "bibliographic_identity"},
                "presse" in lowered and ctype in {"public_archive", "knowledge_base"},
                "gegenbeleg" in lowered and ctype in {"knowledge_base", "web_archive", "public_archive"},
                "beruf" in lowered and ctype in {"scholarly_identity", "knowledge_base", "code_profile"},
            )
        )


    def prepare_connector_query(self, *, case_id: str, target_id: str, connector_key: str) -> dict[str, Any]:
        self._require_target(case_id, target_id)
        connector = next((row for row in self.list_connectors() if row["connector_key"] == connector_key and row.get("enabled")), None)
        if not connector:
            raise ResearchStrategyValidationError("Connector nicht gefunden oder deaktiviert")
        profile = self.scale.build_profile(case_id, target_id, persist=False)
        grouped: dict[str, list[str]] = defaultdict(list)
        for anchor in profile.get("anchors", []):
            typ = str(anchor.get("type") or "")
            value = str(anchor.get("value") or "").strip()
            if value and value not in grouped[typ]:
                grouped[typ].append(value)
        priority = ("domain", "username", "public_url", "identifier", "email", "name", "organisation", "alias", "location", "keyword")
        allowed = set(connector.get("input_types") or [])
        selected_type = ""
        selected_value = ""
        for typ in priority:
            if typ in allowed and grouped.get(typ):
                selected_type = typ
                selected_value = grouped[typ][0]
                break
        if not selected_value:
            raise ResearchStrategyValidationError(
                "Kein überprüfter Rechercheanker passt zu den Eingabetypen dieses Connectors"
            )
        if selected_type == "public_url" and not selected_value.startswith(("http://", "https://")):
            selected_value = "https://" + selected_value.lstrip("/")
        result = {
            "connector_key": connector_key,
            "provider_key": connector["provider_key"],
            "query": selected_value,
            "query_fingerprint": _sha(selected_value),
            "anchor_type": selected_type,
            "anchor_count": 1,
            "data_minimization": "single_reviewed_anchor",
            "network_policy": connector["network_policy"],
        }
        self.db.execute(
            """INSERT INTO research_opsec_events_128(
              event_id,case_id,target_id,strategy_id,action_type,connector_key,query_fingerprint,
              data_minimization_json,network_state,outcome,actor,created_at)
              VALUES(?,?,?,'','prepare_connector_query',?,?,?,'network_not_used','prepared',?,?)""",
            (new_id("opsec128"), case_id, target_id, connector_key, result["query_fingerprint"], dumps({"anchor_type": selected_type, "anchor_count": 1, "raw_query_in_audit": False}), "local-analyst", now_ts()),
        )
        return result

    def execute_connector(self, *, case_id: str, target_id: str, connector_key: str, purpose: str, approved_by: str, confirmation: str, mode: str = "live", max_results: int = 20) -> dict[str, Any]:
        if confirmation.strip() != "CONNECTOR RUN APPROVED":
            raise ResearchStrategyValidationError("Freigabephrase CONNECTOR RUN APPROVED fehlt")
        prepared = self.prepare_connector_query(case_id=case_id, target_id=target_id, connector_key=connector_key)
        provider_key = prepared["provider_key"]
        approval_id = ""
        if mode == "live":
            approval_id = self.protection.reserve_provider_egress(case_id=case_id, provider=provider_key)
        try:
            result = self.providers.execute(
                case_id=case_id, provider_key=provider_key, query=prepared["query"], purpose=purpose,
                approved_by=approved_by, confirmation=self.providers.APPROVAL_PHRASE, mode=mode,
                target_id=target_id, max_results=max(1, min(int(max_results), 50)),
            )
            if mode == "live":
                self.protection.consume_provider_egress(approval_id)
            outcome = "completed"
            return {"prepared": {k: v for k, v in prepared.items() if k != "query"}, "run": result}
        except Exception:
            if mode == "live":
                self.protection.release_provider_egress(approval_id)
            outcome = "failed"
            raise
        finally:
            self.db.execute(
                """INSERT INTO research_opsec_events_128(
                  event_id,case_id,target_id,strategy_id,action_type,connector_key,query_fingerprint,
                  data_minimization_json,network_state,outcome,actor,created_at)
                  VALUES(?,?,?,'','execute_connector',?,?,?, ?,?,?,?)""",
                (new_id("opsec128"), case_id, target_id, connector_key, prepared["query_fingerprint"], dumps({"anchor_type": prepared["anchor_type"], "anchor_count": 1, "raw_query_in_audit": False}), "live_human_approved" if mode == "live" else "replay_offline", outcome, approved_by, now_ts()),
            )

    def _node(self, *, strategy_id: str, case_id: str, target_id: str, node_type: str, node_key: str, label: str, trust_state: str, score: float, properties: dict[str, Any]) -> str:
        node_id = "qnode128_" + _sha((strategy_id, node_type, node_key))[:32]
        self.db.execute(
            """INSERT OR IGNORE INTO query_graph_nodes_128(
              node_id,strategy_id,case_id,target_id,node_type,node_key,label,trust_state,score,properties_json,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (node_id, strategy_id, case_id, target_id, node_type, node_key, label[:500], trust_state, float(score), dumps(properties), now_ts()),
        )
        return node_id

    def _edge(self, *, strategy_id: str, case_id: str, source: str, target: str, relation: str, rationale: str, properties: dict[str, Any] | None = None) -> None:
        edge_id = "qedge128_" + _sha((strategy_id, source, target, relation))[:32]
        self.db.execute(
            """INSERT OR IGNORE INTO query_graph_edges_128(
              edge_id,strategy_id,case_id,source_node_id,target_node_id,relation_type,rationale,properties_json,created_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
            (edge_id, strategy_id, case_id, source, target, relation, rationale[:800], dumps(properties or {}), now_ts()),
        )

    def _upsert_sources(self, case_id: str, target_id: str) -> list[dict[str, Any]]:
        stamp = now_ts()
        sources: list[dict[str, Any]] = []
        intake = self.db.all(
            """SELECT intake_id,target_id,provider_key,title,canonical_url,source_host,snippet,source_type,
                      published_at,content_fingerprint,review_status,created_at
               FROM provider_intake_120 WHERE case_id=? AND (?='' OR target_id=? ) ORDER BY created_at""",
            (case_id, target_id, target_id),
        )
        for row in intake:
            role = "primary_record" if str(row.get("source_type") or "").casefold() in {"public_registry", "public_code_profile"} else "archive_index" if "archive" in str(row.get("source_type") or "").casefold() else "index_record"
            title = str(row.get("title") or "")
            snippet = str(row.get("snippet") or "")
            text_fp = _sha(" ".join(sorted(_tokens(title, snippet))))
            source_id = "src128_" + _sha((case_id, "intake", row["intake_id"]))[:32]
            provenance = {"object_type": "provider_intake_120", "object_id": row["intake_id"], "candidate_only": True, "truth_certified": False}
            self.db.execute(
                """INSERT INTO source_records_128(
                  source_id,case_id,target_id,object_type,object_id,canonical_url,source_host,title,text_fingerprint,
                  content_fingerprint,source_role,provider_key,published_at,captured_at,review_state,
                  independence_cluster_id,provenance_json,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'',?,?,?)
                  ON CONFLICT(case_id,object_type,object_id) DO UPDATE SET
                    canonical_url=excluded.canonical_url,source_host=excluded.source_host,title=excluded.title,
                    text_fingerprint=excluded.text_fingerprint,content_fingerprint=excluded.content_fingerprint,
                    source_role=excluded.source_role,provider_key=excluded.provider_key,published_at=excluded.published_at,
                    review_state=excluded.review_state,provenance_json=excluded.provenance_json,updated_at=excluded.updated_at""",
                (
                    source_id, case_id, str(row.get("target_id") or ""), "intake", row["intake_id"],
                    str(row.get("canonical_url") or ""), str(row.get("source_host") or ""), title,
                    text_fp, str(row.get("content_fingerprint") or ""), role, str(row.get("provider_key") or ""),
                    str(row.get("published_at") or ""), str(row.get("created_at") or ""), str(row.get("review_status") or "candidate"),
                    dumps(provenance), stamp, stamp,
                ),
            )
        evidence = self.db.all(
            "SELECT package_id,source_ref,title,source_url,raw_sha256,metadata_sha256,captured_at,status,candidate_only FROM evidence_packages_121 WHERE case_id=? ORDER BY captured_at",
            (case_id,),
        )
        for row in evidence:
            host = (urlsplit(str(row.get("source_url") or "")).hostname or "").casefold()
            title = str(row.get("title") or "")
            source_id = "src128_" + _sha((case_id, "evidence", row["package_id"]))[:32]
            provenance = {"object_type": "evidence_packages_121", "object_id": row["package_id"], "candidate_only": bool(row.get("candidate_only")), "truth_certified": False}
            self.db.execute(
                """INSERT INTO source_records_128(
                  source_id,case_id,target_id,object_type,object_id,canonical_url,source_host,title,text_fingerprint,
                  content_fingerprint,source_role,provider_key,published_at,captured_at,review_state,
                  independence_cluster_id,provenance_json,created_at,updated_at)
                  VALUES(?,?,?,'evidence',?,?,?,?,?,?,?,'preserved_evidence','', '',?,?, '',?,?,?)
                  ON CONFLICT(case_id,object_type,object_id) DO UPDATE SET
                    canonical_url=excluded.canonical_url,source_host=excluded.source_host,title=excluded.title,
                    content_fingerprint=excluded.content_fingerprint,captured_at=excluded.captured_at,
                    review_state=excluded.review_state,provenance_json=excluded.provenance_json,updated_at=excluded.updated_at""",
                (
                    source_id, case_id, target_id, row["package_id"], str(row.get("source_url") or ""), host, title,
                    _sha(" ".join(sorted(_tokens(title)))), str(row.get("raw_sha256") or row.get("metadata_sha256") or ""),
                    str(row.get("captured_at") or ""), str(row.get("status") or "preserved"), dumps(provenance), stamp, stamp,
                ),
            )
        sources = self.db.all("SELECT * FROM source_records_128 WHERE case_id=? AND (?='' OR target_id IN ('',?)) ORDER BY created_at", (case_id, target_id, target_id))
        return sources

    def _cluster_sources(self, case_id: str, target_id: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.db.execute("DELETE FROM source_clusters_128 WHERE case_id=? AND target_id=?", (case_id, target_id))
        groups: list[list[dict[str, Any]]] = []
        for source in sources:
            source_tokens = _tokens(source.get("title"), source.get("canonical_url"))
            chosen: list[dict[str, Any]] | None = None
            for group in groups:
                rep = group[0]
                same_url = bool(source.get("canonical_url")) and source.get("canonical_url") == rep.get("canonical_url")
                same_content = bool(source.get("content_fingerprint")) and source.get("content_fingerprint") == rep.get("content_fingerprint")
                similarity = _jaccard(source_tokens, _tokens(rep.get("title"), rep.get("canonical_url")))
                if same_url or same_content or similarity >= 0.82:
                    chosen = group
                    break
            if chosen is None:
                chosen = []
                groups.append(chosen)
            chosen.append(source)
        stamp = now_ts()
        output: list[dict[str, Any]] = []
        for group in groups:
            rep = group[0]
            member_ids = sorted(str(item["source_id"]) for item in group)
            hosts = {str(item.get("source_host") or "") for item in group if item.get("source_host")}
            cluster_fp = _sha(member_ids)
            cluster_id = "cluster128_" + cluster_fp[:32]
            kind = "duplicate_or_copy_chain" if len(group) > 1 else "independent_singleton"
            rationale = "Gleiche URL, gleicher Inhaltsfingerprint oder hohe Titelähnlichkeit" if len(group) > 1 else "Kein hinreichend ähnlicher Quellennachweis im aktuellen Fall"
            self.db.execute(
                """INSERT INTO source_clusters_128(
                  cluster_id,case_id,target_id,cluster_kind,representative_source_id,member_count,independent_count,
                  rationale,cluster_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (cluster_id, case_id, target_id, kind, rep["source_id"], len(group), max(1, len(hosts)), rationale, cluster_fp, stamp, stamp),
            )
            for item in group:
                self.db.execute("UPDATE source_records_128 SET independence_cluster_id=?,updated_at=? WHERE source_id=?", (cluster_id, stamp, item["source_id"]))
            output.append({"cluster_id": cluster_id, "member_count": len(group), "independent_hosts": len(hosts), "kind": kind, "rationale": rationale})
        return output

    def _coverage(self, *, strategy_id: str, case_id: str, target_id: str, profile: dict[str, Any], queries: list[dict[str, Any]], sources: list[dict[str, Any]], clusters: list[dict[str, Any]]) -> dict[str, Any]:
        anchor_types = {str(item.get("type") or "") for item in profile.get("anchors", [])}
        categories = {str(item.get("category") or "") for item in queries}
        hosts = {str(item.get("source_host") or "") for item in sources if item.get("source_host")}
        primary = sum(1 for item in sources if item.get("source_role") in {"primary_record", "preserved_evidence"})
        duplicated = sum(max(0, int(item.get("member_count") or 0) - 1) for item in clusters)
        source_diversity = min(100, len(hosts) * 15)
        primary_score = min(100, primary * 20)
        counter = 100 if any("Gegenbeleg" in category or "Namensdoppler" in category for category in categories) else 20
        temporal = 100 if anchor_types & {"birth_year", "date"} else 35
        identity = min(100, len(anchor_types & {"alias", "username", "email", "location", "organisation", "role", "domain", "identifier"}) * 13)
        duplicate_penalty = min(45, duplicated * 5)
        score = max(0, min(100, round((source_diversity + primary_score + counter + temporal + identity) / 5 - duplicate_penalty)))
        gaps: list[str] = []
        if len(hosts) < 2:
            gaps.append("Mindestens zwei voneinander unabhängige Quellendomains fehlen")
        if primary == 0:
            gaps.append("Keine Primär- oder beweisgesicherte Quelle vorhanden")
        if not anchor_types & {"birth_year", "date"}:
            gaps.append("Zeitliche Disambiguierung der Zielperson fehlt")
        if not anchor_types & {"location", "organisation", "role"}:
            gaps.append("Kontextanker für Ort, Organisation oder Rolle fehlen")
        if not any("Gegenbeleg" in category or "Namensdoppler" in category for category in categories):
            gaps.append("Aktive Gegenbeleg- und Namensdopplersuche fehlt")
        if duplicated:
            gaps.append(f"{duplicated} Quellen wirken als Kopien oder abhängige Wiederholungen")
        covered = sorted(anchor_types | {"source_diversity" if hosts else "", "primary_source" if primary else ""} - {""})
        coverage = {
            "coverage_score": score,
            "source_diversity_score": source_diversity,
            "primary_source_score": primary_score,
            "counter_evidence_score": counter,
            "temporal_coverage_score": temporal,
            "identity_disambiguation_score": identity,
            "duplicate_penalty": duplicate_penalty,
            "independent_hosts": len(hosts),
            "source_clusters": len(clusters),
            "open_gaps": gaps,
            "covered_dimensions": covered,
            "metrics": {"anchors": len(profile.get("anchors", [])), "queries": len(queries), "sources": len(sources), "primary_sources": primary, "duplicate_members": duplicated},
        }
        self.db.execute(
            """INSERT INTO research_coverage_128(
              coverage_id,strategy_id,case_id,target_id,coverage_score,source_diversity_score,primary_source_score,
              counter_evidence_score,temporal_coverage_score,identity_disambiguation_score,duplicate_penalty,
              independent_hosts,source_clusters,open_gaps_json,covered_dimensions_json,metrics_json,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                new_id("coverage128"), strategy_id, case_id, target_id, score, source_diversity, primary_score,
                counter, temporal, identity, duplicate_penalty, len(hosts), len(clusters), dumps(gaps), dumps(covered),
                dumps(coverage["metrics"]), now_ts(),
            ),
        )
        return coverage

    def _ai_brief(self, *, strategy_id: str, case_id: str, target_id: str, coverage: dict[str, Any], connector_labels: list[str]) -> dict[str, Any]:
        gaps = list(coverage.get("open_gaps") or [])
        next_steps = []
        for gap in gaps[:8]:
            if "unabhängige" in gap:
                next_steps.append("Dieselbe konkrete Aussage in einer unabhängigen Primär- oder Registerquelle gegenprüfen")
            elif "Primär" in gap:
                next_steps.append("Primärquelle, Originalregister oder Originalpublikation priorisieren")
            elif "Zeitliche" in gap:
                next_steps.append("Geburtsjahr, Beschäftigungszeitraum oder Ereignisdatum als geprüften Anker ergänzen")
            elif "Kontextanker" in gap:
                next_steps.append("Ort, Organisation und Rolle getrennt verifizieren und anschließend kombinieren")
            elif "Namensdoppler" in gap:
                next_steps.append("Explizite Gegenhypothese zu mindestens einer alternativen Person anlegen")
            elif "Kopien" in gap:
                next_steps.append("Ursprungsquelle des Quellenclusters bestimmen und Kopien nicht mehrfach zählen")
        content = {
            "summary": "Lokale Research-Intelligence-Empfehlung",
            "coverage_score": coverage["coverage_score"],
            "open_gaps": gaps,
            "recommended_next_steps": next_steps or ["Vorhandene Quellen und Kandidaten menschlich gegenprüfen"],
            "recommended_connectors": connector_labels[:10],
            "guardrails": [
                "Keine autonome Netzwerkausführung.",
                "Keine Identitäts- oder Wahrheitsbestätigung.",
                "Nur minimierte, für den jeweiligen Connector erforderliche Suchanker verwenden.",
                "Alle Ergebnisse bleiben candidate_only bis zum menschlichen Review.",
            ],
        }
        suggestion_id = new_id("aisug128")
        refs = [{"object_type": "research_strategy", "object_id": strategy_id}]
        self.db.execute(
            """INSERT INTO research_ai_suggestions_128(
              suggestion_id,strategy_id,case_id,target_id,suggestion_type,content_json,source_refs_json,
              trust_state,review_status,model_key,model_version,prompt_version,created_at)
              VALUES(?,?,?,?,?,?,?,'suggestions_only','pending','deterministic_research128','1.0','128.0',?)""",
            (suggestion_id, strategy_id, case_id, target_id, "research_strategy_brief", dumps(content), dumps(refs), now_ts()),
        )
        return {"suggestion_id": suggestion_id, **content, "trust_state": "suggestions_only", "review_status": "pending"}

    def create_strategy(self, *, case_id: str, target_id: str, actor: str, query_limit: int = 80) -> dict[str, Any]:
        self._require_target(case_id, target_id)
        profile = self.scale.build_profile(case_id, target_id)
        plan = self.scale.generate_query_plan(case_id, target_id, limit=max(10, min(160, int(query_limit))))
        queries = list(plan.get("queries") or [])
        connectors = [row for row in self.list_connectors() if row.get("enabled")]
        strategy_id = new_id("strategy128")
        created = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute(
                """INSERT INTO research_strategy_runs_128(
                  strategy_id,case_id,target_id,profile_digest,status,query_count,connector_count,
                  created_by,created_at) VALUES(?,?,?,?, 'building',?,?,?,?)""",
                (strategy_id, case_id, target_id, profile["profile_digest"], len(queries), len(connectors), actor, created),
            )
            connector_nodes: dict[str, str] = {}
            for connector in connectors:
                connector_nodes[connector["connector_key"]] = self._node(
                    strategy_id=strategy_id, case_id=case_id, target_id=target_id,
                    node_type="connector", node_key=connector["connector_key"], label=connector["label"],
                    trust_state="system_capability", score=1.0,
                    properties={"provider_key": connector["provider_key"], "execution_mode": connector["execution_mode"], "network_policy": connector["network_policy"], "query_minimization": connector["query_minimization"]},
                )
            for query in queries:
                qkey = _sha(query.get("query"))
                qnode = self._node(
                    strategy_id=strategy_id, case_id=case_id, target_id=target_id,
                    node_type="query", node_key=qkey, label=str(query.get("query") or "")[:500],
                    trust_state="planned", score=float(query.get("precision_score") or 0), properties=query,
                )
                anchor_types: set[str] = set()
                for anchor in query.get("anchors") or []:
                    atype = str(anchor.get("type") or "keyword")
                    avalue = str(anchor.get("value") or "")
                    anchor_types.add(atype)
                    anode = self._node(
                        strategy_id=strategy_id, case_id=case_id, target_id=target_id,
                        node_type="anchor", node_key=f"{atype}:{_norm(avalue)}", label=avalue,
                        trust_state="reviewed_input", score=1.0, properties={"anchor_type": atype},
                    )
                    self._edge(strategy_id=strategy_id, case_id=case_id, source=anode, target=qnode, relation="generates_query", rationale=str(query.get("rationale") or ""))
                for connector in connectors:
                    if self._connector_matches(connector, anchor_types, str(query.get("category") or "")):
                        self._edge(
                            strategy_id=strategy_id, case_id=case_id, source=qnode,
                            target=connector_nodes[connector["connector_key"]], relation="candidate_connector",
                            rationale="Connector unterstützt mindestens einen verwendeten Ankertyp oder die Recherchekategorie",
                            properties={"human_approval_required": True, "automatic_execution": False},
                        )
            sources = self._upsert_sources(case_id, target_id)
            clusters = self._cluster_sources(case_id, target_id, sources)
            coverage = self._coverage(strategy_id=strategy_id, case_id=case_id, target_id=target_id, profile=profile, queries=queries, sources=sources, clusters=clusters)
            for source in sources:
                snode = self._node(
                    strategy_id=strategy_id, case_id=case_id, target_id=target_id,
                    node_type="source", node_key=source["source_id"], label=str(source.get("title") or source.get("canonical_url") or source["source_id"]),
                    trust_state=str(source.get("review_state") or "candidate"), score=1.0,
                    properties={"source_role": source.get("source_role"), "source_host": source.get("source_host"), "cluster_id": source.get("independence_cluster_id"), "object_type": source.get("object_type"), "object_id": source.get("object_id")},
                )
                provider = str(source.get("provider_key") or "")
                for connector in connectors:
                    if connector.get("provider_key") == provider:
                        self._edge(strategy_id=strategy_id, case_id=case_id, source=connector_nodes[connector["connector_key"]], target=snode, relation="produced_candidate", rationale="Quelle wurde über den zugeordneten Provider erfasst")
            graph_rows = self.db.all("SELECT node_type,node_key,label,score,properties_json FROM query_graph_nodes_128 WHERE strategy_id=? ORDER BY node_type,node_key", (strategy_id,))
            graph_edges = self.db.all("SELECT source_node_id,target_node_id,relation_type FROM query_graph_edges_128 WHERE strategy_id=? ORDER BY source_node_id,target_node_id,relation_type", (strategy_id,))
            graph_digest = _sha({"nodes": graph_rows, "edges": graph_edges})
            matched_labels = [connector["label"] for connector in connectors]
            ai = self._ai_brief(strategy_id=strategy_id, case_id=case_id, target_id=target_id, coverage=coverage, connector_labels=matched_labels)
            self.db.execute(
                """UPDATE research_strategy_runs_128 SET status='ready',source_count=?,cluster_count=?,coverage_score=?,
                   graph_digest=?,ai_brief_id=? WHERE strategy_id=?""",
                (len(sources), len(clusters), coverage["coverage_score"], graph_digest, ai["suggestion_id"], strategy_id),
            )
            self.db.execute(
                """INSERT INTO research_opsec_events_128(
                  event_id,case_id,target_id,strategy_id,action_type,connector_key,query_fingerprint,
                  data_minimization_json,network_state,outcome,actor,created_at)
                  VALUES(?,?,?,?, 'create_strategy','',?,?,'network_not_used','ready',?,?)""",
                (new_id("opsec128"), case_id, target_id, strategy_id, _sha([q.get("query") for q in queries]), dumps({"raw_query_in_audit": False, "connector_queries": "not_executed", "anchor_scope": "reviewed_only"}), actor, now_ts()),
            )
        self.audit.log("create_strategy", "research_strategy_128", strategy_id, case_id, {"target_id": target_id, "query_count": len(queries), "connector_count": len(connectors), "coverage_score": coverage["coverage_score"], "query_bundle_sha256": _sha([q.get("query") for q in queries])})
        return self.get_strategy(case_id, strategy_id)

    def get_strategy(self, case_id: str, strategy_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_strategy_runs_128 WHERE strategy_id=? AND case_id=?", (strategy_id, case_id))
        if not row:
            raise ResearchStrategyValidationError("Research-Strategie nicht gefunden")
        coverage = self.db.one("SELECT * FROM research_coverage_128 WHERE strategy_id=?", (strategy_id,)) or {}
        for key in ("open_gaps_json", "covered_dimensions_json", "metrics_json"):
            if key in coverage:
                coverage[key.removesuffix("_json")] = loads(coverage.pop(key), [] if key != "metrics_json" else {})
        ai_row = self.db.one("SELECT * FROM research_ai_suggestions_128 WHERE strategy_id=? ORDER BY created_at DESC LIMIT 1", (strategy_id,)) or {}
        if ai_row:
            ai_row["content"] = loads(ai_row.pop("content_json", "{}"), {})
            ai_row["source_refs"] = loads(ai_row.pop("source_refs_json", "[]"), [])
        row["coverage"] = coverage
        row["ai_brief"] = ai_row
        row["nodes"] = self.db.all("SELECT * FROM query_graph_nodes_128 WHERE strategy_id=? ORDER BY node_type,score DESC LIMIT 1000", (strategy_id,))
        for node in row["nodes"]:
            node["properties"] = loads(node.pop("properties_json", "{}"), {})
        row["edges"] = self.db.all("SELECT * FROM query_graph_edges_128 WHERE strategy_id=? ORDER BY relation_type LIMIT 3000", (strategy_id,))
        for edge in row["edges"]:
            edge["properties"] = loads(edge.pop("properties_json", "{}"), {})
        return row

    def latest_strategy(self, case_id: str, target_id: str = "") -> dict[str, Any] | None:
        row = self.db.one(
            "SELECT strategy_id FROM research_strategy_runs_128 WHERE case_id=? AND (?='' OR target_id=?) ORDER BY created_at DESC LIMIT 1",
            (case_id, target_id, target_id),
        )
        return self.get_strategy(case_id, row["strategy_id"]) if row else None

    def dashboard(self, case_id: str) -> dict[str, Any]:
        latest = self.db.all("SELECT * FROM research_strategy_runs_128 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        coverage = self.db.all("SELECT * FROM research_coverage_128 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        connectors = self.list_connectors()
        sources = self.db.all("SELECT source_role,COUNT(*) AS n FROM source_records_128 WHERE case_id=? GROUP BY source_role ORDER BY n DESC", (case_id,))
        clusters = self.db.all("SELECT cluster_kind,COUNT(*) AS n,SUM(member_count) AS members FROM source_clusters_128 WHERE case_id=? GROUP BY cluster_kind", (case_id,))
        return {"status": self.status(), "strategies": latest, "coverage": coverage, "connectors": connectors, "source_roles": sources, "clusters": clusters}
