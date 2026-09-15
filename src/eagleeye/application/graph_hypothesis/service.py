from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _sha_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", errors="replace")).hexdigest()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class GraphHypothesisError(ValueError):
    pass


class GraphHypothesisConflict(GraphHypothesisError):
    pass


class GraphHypothesis130Service:
    """Review-first graph analytics and hypothesis laboratory.

    Analytics describe stored graph structure, not real-world importance. Hypotheses,
    red-team output and AI briefs remain candidate-only suggestions and cannot promote
    evidence, relations, identities, timelines or culpability assessments.
    """

    BUILD = "130.0"
    MAX_NODES = 5000
    MAX_EDGES = 20000
    MAX_PATH_DEPTH = 10
    STANCES = {"supports", "contradicts", "neutral", "context"}
    CLAIM_TYPES = {"identity", "temporal", "location", "relationship", "source", "causality", "other"}
    REVIEW_DECISIONS = {"supported_for_working_use", "insufficient_evidence", "rejected", "deferred"}
    OBJECT_TABLES = {
        "evidence": ("evidence_packages_121", "package_id"),
        "intake": ("provider_intake_120", "intake_id"),
        "capture": ("browser_captures_129", "capture_id"),
        "relation": ("graph_relations_116", "relation_id"),
        "timeline_event": ("timeline_events_117", "event_id"),
        "contradiction": ("contradictions_118", "contradiction_id"),
        "source": ("graph_sources_116", "source_id"),
        "entity": ("resolution_entities_115", "resolution_entity_id"),
    }

    def __init__(self, db: Any, audit: Any, *, cases: Any, targets: Any, scale_getter: Callable[[], Any]) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets
        self._scale_getter = scale_getter

    @property
    def scale(self) -> Any:
        return self._scale_getter()

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (str(case_id),))
        if not row:
            raise GraphHypothesisError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise GraphHypothesisError("Zielperson gehört nicht zu diesem Fall")
        return row

    def _opsec(self, *, case_id: str, action_type: str, object_type: str, object_id: str = "", value: str = "", minimization: dict[str, Any] | None = None, outcome: str, actor: str) -> None:
        self.db.execute(
            "INSERT INTO opsec_events_130 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (_id("op130"), case_id, action_type, object_type, object_id, _sha_text(value) if value else "", _json(minimization or {}), outcome, actor, _now()),
        )

    @staticmethod
    def _adjacency(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[tuple[str, str], list[dict[str, Any]]]]:
        nodes = {str(n["id"]): dict(n) for n in payload.get("nodes") or []}
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
        edge_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for edge in payload.get("edges") or []:
            source, target = str(edge.get("source") or ""), str(edge.get("target") or "")
            if source not in nodes or target not in nodes or source == target:
                continue
            adjacency[source].add(target)
            adjacency[target].add(source)
            edge_map[(source, target)].append(dict(edge))
            edge_map[(target, source)].append(dict(edge))
        return nodes, adjacency, edge_map

    def graph_projection(self, case_id: str, *, node_types: Iterable[str] = (), date_from: str = "", date_to: str = "", location_query: str = "", include_candidates: bool = True, limit_nodes: int = 1500, limit_edges: int = 4000) -> dict[str, Any]:
        self._case(case_id)
        node_types = {str(x).strip() for x in node_types if str(x).strip()}
        limit_nodes = max(50, min(self.MAX_NODES, int(limit_nodes)))
        limit_edges = max(100, min(self.MAX_EDGES, int(limit_edges)))
        payload = self.scale.graph_payload(case_id, limit_nodes=limit_nodes, limit_edges=limit_edges)
        nodes = {str(n["id"]): dict(n) for n in payload.get("nodes") or []}
        edges = [dict(e) for e in payload.get("edges") or []]
        if node_types:
            keep = {node_id for node_id, row in nodes.items() if row.get("type") in node_types}
            # Preserve one-hop context to avoid analytically misleading isolated filters.
            for edge in edges:
                if edge.get("source") in keep or edge.get("target") in keep:
                    keep.add(str(edge.get("source"))); keep.add(str(edge.get("target")))
            nodes = {k: v for k, v in nodes.items() if k in keep}
        if not include_candidates:
            nodes = {k: v for k, v in nodes.items() if not bool(v.get("candidate", True))}
        if location_query.strip():
            needle = location_query.casefold().strip()
            locations = {k for k, v in nodes.items() if v.get("type") == "location" and needle in f"{v.get('label','')} {v.get('value','')}".casefold()}
            keep = set(locations)
            for edge in edges:
                if edge.get("source") in locations or edge.get("target") in locations:
                    keep.add(str(edge.get("source"))); keep.add(str(edge.get("target")))
            nodes = {k: v for k, v in nodes.items() if k in keep}
        if date_from or date_to:
            dated_relation_ids: set[str] = set()
            if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='graph_relation_versions_116'"):
                rows = self.db.all(
                    """SELECT r.relation_id,v.valid_from,v.valid_to,v.observed_at
                       FROM graph_relations_116 r JOIN graph_relation_versions_116 v
                       ON v.relation_id=r.relation_id AND v.version_no=r.current_version
                       WHERE r.case_id=?""", (case_id,),
                )
                for row in rows:
                    start = str(row.get("valid_from") or row.get("observed_at") or "")
                    end = str(row.get("valid_to") or row.get("observed_at") or start)
                    if date_from and end and end < date_from:
                        continue
                    if date_to and start and start > date_to:
                        continue
                    dated_relation_ids.add(str(row["relation_id"]))
            edges = [e for e in edges if e.get("type") != "canonical_relation" or str(e.get("id")) in dated_relation_ids]
        visible_edges = [e for e in edges if str(e.get("source")) in nodes and str(e.get("target")) in nodes]
        type_counts: dict[str, int] = defaultdict(int)
        for row in nodes.values():
            type_counts[str(row.get("type") or "other")] += 1
        return {"nodes": list(nodes.values()), "edges": visible_edges[:limit_edges], "meta": {"node_count": len(nodes), "edge_count": len(visible_edges[:limit_edges]), "type_counts": dict(type_counts), "filters": {"node_types": sorted(node_types), "date_from": date_from, "date_to": date_to, "location_query": location_query, "include_candidates": include_candidates}, "truncated": bool(payload.get("meta", {}).get("truncated")) or len(visible_edges) > limit_edges}}

    @staticmethod
    def _components(adjacency: dict[str, set[str]]) -> dict[str, str]:
        result: dict[str, str] = {}
        index = 0
        for start in sorted(adjacency):
            if start in result:
                continue
            index += 1
            cid = f"component_{index}"
            queue = [start]; result[start] = cid
            while queue:
                current = queue.pop()
                for nxt in sorted(adjacency[current]):
                    if nxt not in result:
                        result[nxt] = cid; queue.append(nxt)
        return result

    @staticmethod
    def _communities(adjacency: dict[str, set[str]], iterations: int = 12) -> dict[str, str]:
        labels = {node: node for node in adjacency}
        for _ in range(iterations):
            changed = False
            for node in sorted(adjacency, key=lambda n: (-len(adjacency[n]), n)):
                if not adjacency[node]:
                    continue
                counts: dict[str, int] = defaultdict(int)
                for neighbour in adjacency[node]:
                    counts[labels[neighbour]] += 1
                best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
                if best != labels[node]:
                    labels[node] = best; changed = True
            if not changed:
                break
        canonical: dict[str, str] = {}
        for label in sorted(set(labels.values())):
            canonical[label] = f"community_{len(canonical)+1}"
        return {node: canonical[label] for node, label in labels.items()}

    @staticmethod
    def _betweenness(adjacency: dict[str, set[str]], max_sources: int = 40) -> dict[str, float]:
        nodes = sorted(adjacency)
        if not nodes:
            return {}
        if len(nodes) <= max_sources:
            sources = nodes
        else:
            step = max(1, len(nodes) // max_sources)
            sources = nodes[::step][:max_sources]
        scores = {node: 0.0 for node in nodes}
        for source in sources:
            stack: list[str] = []
            pred: dict[str, list[str]] = {v: [] for v in nodes}
            sigma = dict.fromkeys(nodes, 0.0); sigma[source] = 1.0
            dist = dict.fromkeys(nodes, -1); dist[source] = 0
            queue = deque([source])
            while queue:
                v = queue.popleft(); stack.append(v)
                for w in adjacency[v]:
                    if dist[w] < 0:
                        queue.append(w); dist[w] = dist[v] + 1
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]; pred[w].append(v)
            delta = dict.fromkeys(nodes, 0.0)
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    if sigma[w]:
                        delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != source:
                    scores[w] += delta[w]
        scale = 1.0 / max(1, len(sources))
        maximum = max(scores.values(), default=0.0)
        return {node: round((value * scale / maximum) if maximum else 0.0, 6) for node, value in scores.items()}

    def run_graph_analysis(self, *, case_id: str, actor: str, node_types: Iterable[str] = (), date_from: str = "", date_to: str = "", location_query: str = "", include_candidates: bool = True, limit_nodes: int = 1500, limit_edges: int = 4000) -> dict[str, Any]:
        payload = self.graph_projection(case_id, node_types=node_types, date_from=date_from, date_to=date_to, location_query=location_query, include_candidates=include_candidates, limit_nodes=limit_nodes, limit_edges=limit_edges)
        nodes, adjacency, _ = self._adjacency(payload)
        components = self._components(adjacency)
        communities = self._communities(adjacency)
        betweenness = self._betweenness(adjacency)
        n = max(1, len(nodes) - 1)
        degrees = {node: len(adjacency[node]) for node in nodes}
        run_id, created = _id("gran130"), _now()
        component_sizes: dict[str, int] = defaultdict(int)
        community_sizes: dict[str, int] = defaultdict(int)
        for value in components.values(): component_sizes[value] += 1
        for value in communities.values(): community_sizes[value] += 1
        top = sorted(nodes, key=lambda node: (-betweenness.get(node, 0.0), -degrees.get(node, 0), node))[:20]
        summary = {
            "component_count": len(set(components.values())),
            "community_count": len(set(communities.values())),
            "isolated_nodes": sum(1 for node in nodes if degrees[node] == 0),
            "largest_component": max(component_sizes.values(), default=0),
            "largest_community": max(community_sizes.values(), default=0),
            "top_bridge_nodes": [{"node_id": node, "label": nodes[node].get("label"), "type": nodes[node].get("type"), "degree": degrees[node], "betweenness": betweenness.get(node, 0.0)} for node in top],
            "interpretation_warning": "Strukturelle Zentralität ist keine Bedeutung, Schuld, Gefährlichkeit oder reale Einflussbewertung.",
        }
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO graph_analysis_runs_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, case_id, "structural_graph_analysis", "completed", len(nodes), len(payload.get("edges") or []), _json(payload["meta"]["filters"]), _json({"algorithms": ["components", "label_propagation", "degree", "sampled_betweenness"], "max_sources": 40}), _json(summary), actor, created, _now()))
            for node_id, row in nodes.items():
                self.db.execute("INSERT INTO graph_node_metrics_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (_id("gmet130"), run_id, case_id, node_id, str(row.get("type") or "other"), str(row.get("label") or node_id)[:500], degrees[node_id], round(degrees[node_id] / n, 6), betweenness.get(node_id, 0.0), components[node_id], communities[node_id], 1 if row.get("candidate", True) else 0, _json({"source": row.get("source"), "confidence": row.get("confidence")}), created))
            self._opsec(case_id=case_id, action_type="run_graph_analysis", object_type="graph_analysis", object_id=run_id, minimization={"raw_labels_in_audit": False, "network_actions": 0, "node_count": len(nodes), "edge_count": len(payload.get("edges") or [])}, outcome="completed", actor=actor)
            self.audit.log("run_graph_analysis_130", "graph_analysis_130", run_id, case_id, {"node_count": len(nodes), "edge_count": len(payload.get("edges") or []), "filters_fingerprint": _sha_text(_json(payload["meta"]["filters"]))})
        self._create_ai_graph_brief(case_id=case_id, run_id=run_id, summary=summary, actor=actor)
        return {"run_id": run_id, "node_count": len(nodes), "edge_count": len(payload.get("edges") or []), "summary": summary}

    def _create_ai_graph_brief(self, *, case_id: str, run_id: str, summary: dict[str, Any], actor: str) -> str:
        content = {
            "working_observations": [
                f"Der gespeicherte Graph enthält {summary['component_count']} Komponenten und {summary['community_count']} strukturelle Communities.",
                f"{summary['isolated_nodes']} Knoten sind aktuell isoliert und benötigen gegebenenfalls weitere Quellen- oder Relationsprüfung.",
            ],
            "next_checks": [
                "Brückenknoten anhand der zugrunde liegenden Evidence prüfen, nicht anhand des Zentralitätswertes allein.",
                "Für zentrale Beziehungen unabhängige Gegenquellen und widersprechende Evidence suchen.",
                "Zeit- und Ortsfilter verwenden, bevor aus struktureller Nähe eine reale Verbindung abgeleitet wird.",
            ],
            "prohibited_inference": "Keine Schuld-, Gefährlichkeits-, Einfluss- oder Identitätsbestätigung aus Graphmetriken.",
        }
        suggestion_id = _id("gai130")
        self.db.execute("INSERT INTO graph_ai_suggestions_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (suggestion_id, case_id, "", run_id, "graph_investigation_brief", _json(content), _json([{"object_type": "graph_analysis", "object_id": run_id}]), "suggestions_only", "pending", "local_graph_analyst_130", "130.0", actor, _now()))
        return suggestion_id

    def find_paths(self, *, case_id: str, source_node_id: str, target_node_id: str, actor: str, max_depth: int = 6, max_paths: int = 5) -> dict[str, Any]:
        self._case(case_id)
        max_depth = max(1, min(self.MAX_PATH_DEPTH, int(max_depth)))
        max_paths = max(1, min(10, int(max_paths)))
        payload = self.graph_projection(case_id, limit_nodes=self.MAX_NODES, limit_edges=self.MAX_EDGES)
        nodes, adjacency, edge_map = self._adjacency(payload)
        if source_node_id not in nodes or target_node_id not in nodes:
            raise GraphHypothesisError("Start- oder Zielknoten ist im fallgebundenen Graph nicht vorhanden")
        queue: deque[list[str]] = deque([[source_node_id]])
        paths: list[list[str]] = []
        shortest: int | None = None
        while queue and len(paths) < max_paths:
            path = queue.popleft()
            if len(path) - 1 > max_depth:
                continue
            current = path[-1]
            if current == target_node_id:
                shortest = len(path) - 1 if shortest is None else shortest
                if len(path) - 1 == shortest:
                    paths.append(path)
                continue
            if shortest is not None and len(path) - 1 >= shortest:
                continue
            for nxt in sorted(adjacency[current]):
                if nxt not in path:
                    queue.append([*path, nxt])
        stored: list[dict[str, Any]] = []
        for rank, path in enumerate(paths, 1):
            edge_path = []
            for a, b in zip(path, path[1:]):
                edges = edge_map.get((a, b)) or []
                edge_path.append(edges[0] if edges else {"source": a, "target": b, "label": "relation"})
            path_id = _id("gpath130")
            explanation = {"candidate_path": any(bool(nodes[node].get("candidate", True)) for node in path), "warning": "Ein struktureller Pfad bestätigt keine reale, direkte oder kausale Beziehung."}
            self.db.execute("INSERT INTO graph_paths_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (path_id, "", case_id, source_node_id, target_node_id, rank, len(path)-1, _json(path), _json(edge_path), _json(explanation), actor, _now()))
            stored.append({"path_id": path_id, "rank": rank, "hop_count": len(path)-1, "nodes": [{"id": node, "label": nodes[node].get("label"), "type": nodes[node].get("type")} for node in path], "edges": edge_path, "explanation": explanation})
        self._opsec(case_id=case_id, action_type="find_graph_paths", object_type="graph_path", value=f"{source_node_id}|{target_node_id}", minimization={"raw_node_ids_in_audit": False, "max_depth": max_depth, "max_paths": max_paths}, outcome="found" if stored else "none", actor=actor)
        self.audit.log("find_graph_paths_130", "graph_path_130", stored[0]["path_id"] if stored else "", case_id, {"path_count": len(stored), "endpoint_fingerprint": _sha_text(f"{source_node_id}|{target_node_id}")})
        return {"source": nodes[source_node_id], "target": nodes[target_node_id], "paths": stored, "path_count": len(stored)}

    def source_independence_graph(self, case_id: str, *, limit: int = 1500) -> dict[str, Any]:
        self._case(case_id)
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        groups: dict[str, list[str]] = defaultdict(list)
        if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='source_records_128'"):
            for row in self.db.all("SELECT * FROM source_records_128 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(10, min(5000, int(limit))))):
                sid = f"source128:{row['source_id']}"
                group = str(row.get("content_fingerprint") or row.get("canonical_url") or row.get("source_host") or sid)
                nodes[sid] = {"id": sid, "label": row.get("title") or row.get("source_host") or sid, "type": "source", "host": row.get("source_host"), "candidate": row.get("review_state") != "reviewed"}
                groups[group].append(sid)
        if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='graph_sources_116'"):
            for row in self.db.all("SELECT * FROM graph_sources_116 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(10, min(5000, int(limit))))):
                sid = f"source116:{row['source_id']}"
                group = str(row.get("content_hash") or row.get("independence_group") or row.get("canonical_url") or sid)
                nodes[sid] = {"id": sid, "label": row.get("title") or row.get("publisher") or sid, "type": "source", "host": row.get("publisher") or "", "candidate": True}
                groups[group].append(sid)
        for index, (group, members) in enumerate(sorted(groups.items()), 1):
            if len(members) < 2:
                continue
            cluster_id = f"independence:{hashlib.sha256(group.encode()).hexdigest()[:16]}"
            nodes[cluster_id] = {"id": cluster_id, "label": f"Abhängigkeitscluster {index}", "type": "source_cluster", "candidate": True, "member_count": len(members)}
            for member in members:
                edges.append({"id": f"dep:{cluster_id}:{member}", "source": cluster_id, "target": member, "label": "possible shared origin", "type": "source_dependency", "candidate": True})
        return {"nodes": list(nodes.values()), "edges": edges, "meta": {"source_count": sum(1 for n in nodes.values() if n["type"] == "source"), "cluster_count": sum(1 for n in nodes.values() if n["type"] == "source_cluster"), "warning": "Cluster zeigen mögliche Abhängigkeit, nicht bewiesene Kopierbeziehungen."}}

    def create_hypothesis(self, *, case_id: str, target_id: str = "", title: str, statement: str, rationale: str, actor: str, claim_type: str = "other") -> dict[str, Any]:
        self._case(case_id); self._target(case_id, target_id)
        title, statement, rationale = title.strip(), statement.strip(), rationale.strip()
        if len(title) < 4 or len(statement) < 12 or len(rationale) < 12:
            raise GraphHypothesisError("Titel, Hypothese und Begründung müssen substanziell sein")
        if claim_type not in self.CLAIM_TYPES:
            raise GraphHypothesisError("Unzulässiger Claim-Typ")
        hid, cid, ts = _id("hyp130"), _id("claim130"), _now()
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO hypotheses_130 VALUES(?,?,?,?,?,?,'candidate',1,?,?,?,?,?,?,?)", (hid, case_id, target_id, title[:500], statement[:8000], rationale[:8000], actor, ts, ts, "", "", "", ""))
            self.db.execute("INSERT INTO hypothesis_claims_130 VALUES(?,?,?,?,?,?,?,?)", (cid, hid, case_id, claim_type, statement[:8000], "hypothesis_candidate", actor, ts))
            self._opsec(case_id=case_id, action_type="create_hypothesis", object_type="hypothesis", object_id=hid, value=statement, minimization={"statement_in_audit": False, "network_actions": 0, "automatic_promotion": False}, outcome="candidate", actor=actor)
            self.audit.log("create_hypothesis_130", "hypothesis_130", hid, case_id, {"target_id": target_id, "claim_type": claim_type, "statement_fingerprint": _sha_text(statement)})
        return {"hypothesis_id": hid, "claim_id": cid, "state": "candidate", "candidate_only": True, "automatic_promotion": False}

    def add_claim(self, *, case_id: str, hypothesis_id: str, claim_type: str, statement: str, actor: str) -> str:
        hypothesis = self._hypothesis(case_id, hypothesis_id)
        if hypothesis["state"] not in {"candidate", "needs_review"}:
            raise GraphHypothesisConflict("Abgeschlossene Hypothese kann nicht erweitert werden")
        if claim_type not in self.CLAIM_TYPES or len(statement.strip()) < 10:
            raise GraphHypothesisError("Gültiger Claim-Typ und substanzielle Aussage erforderlich")
        cid = _id("claim130")
        self.db.execute("INSERT INTO hypothesis_claims_130 VALUES(?,?,?,?,?,?,?,?)", (cid, hypothesis_id, case_id, claim_type, statement.strip()[:8000], "claim_candidate", actor, _now()))
        self._opsec(case_id=case_id, action_type="add_hypothesis_claim", object_type="claim", object_id=cid, value=statement, minimization={"statement_in_audit": False}, outcome="candidate", actor=actor)
        return cid

    def _hypothesis(self, case_id: str, hypothesis_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM hypotheses_130 WHERE case_id=? AND hypothesis_id=?", (case_id, hypothesis_id))
        if not row:
            raise GraphHypothesisError("Hypothese nicht gefunden")
        return row

    def _validate_object(self, case_id: str, object_type: str, object_id: str) -> dict[str, Any]:
        if object_type not in self.OBJECT_TABLES:
            raise GraphHypothesisError("Unzulässiger Evidence-Objekttyp")
        table, key = self.OBJECT_TABLES[object_type]
        row = self.db.one(f"SELECT * FROM {table} WHERE {key}=? AND case_id=?", (object_id, case_id))
        if not row:
            raise GraphHypothesisError("Evidence-Objekt ist nicht im Fall vorhanden")
        return row

    def link_evidence(self, *, case_id: str, hypothesis_id: str, claim_id: str, object_type: str, object_id: str, stance: str, weight: float, summary: str, actor: str) -> str:
        self._hypothesis(case_id, hypothesis_id)
        claim = self.db.one("SELECT * FROM hypothesis_claims_130 WHERE claim_id=? AND hypothesis_id=? AND case_id=?", (claim_id, hypothesis_id, case_id))
        if not claim:
            raise GraphHypothesisError("Claim gehört nicht zu dieser Hypothese")
        if stance not in self.STANCES:
            raise GraphHypothesisError("Unzulässige Evidence-Stance")
        obj = self._validate_object(case_id, object_type, object_id)
        if len(summary.strip()) < 8:
            raise GraphHypothesisError("Evidence-Einordnung ist zu kurz")
        group = str(obj.get("independence_group") or obj.get("source_host") or obj.get("provider_key") or obj.get("canonical_url") or f"{object_type}:{object_id}")[:500]
        link_id = _id("hev130")
        self.db.execute("INSERT INTO hypothesis_evidence_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (link_id, hypothesis_id, claim_id, case_id, object_type, object_id, stance, _clamp(weight), group, summary.strip()[:4000], actor, _now()))
        self._opsec(case_id=case_id, action_type="link_hypothesis_evidence", object_type=object_type, object_id=object_id, minimization={"hypothesis_id": hypothesis_id, "stance": stance, "raw_summary_in_audit": False}, outcome="linked", actor=actor)
        self.audit.log("link_hypothesis_evidence_130", object_type, object_id, case_id, {"hypothesis_id": hypothesis_id, "claim_id": claim_id, "stance": stance, "summary_fingerprint": _sha_text(summary)})
        return link_id

    def claim_evidence_matrix(self, case_id: str, hypothesis_id: str) -> dict[str, Any]:
        hypothesis = self._hypothesis(case_id, hypothesis_id)
        claims = self.db.all("SELECT * FROM hypothesis_claims_130 WHERE hypothesis_id=? ORDER BY created_at", (hypothesis_id,))
        evidence = self.db.all("SELECT * FROM hypothesis_evidence_130 WHERE hypothesis_id=? ORDER BY created_at", (hypothesis_id,))
        by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in evidence:
            by_claim[str(row["claim_id"])].append(row)
        matrix = []
        for claim in claims:
            rows = by_claim.get(str(claim["claim_id"]), [])
            independent: dict[tuple[str, str], float] = {}
            for row in rows:
                key = (str(row.get("independence_group") or row["object_id"]), row["stance"])
                independent[key] = max(independent.get(key, 0.0), float(row["weight"]))
            support = sum(v for (g, stance), v in independent.items() if stance == "supports")
            contradict = sum(v for (g, stance), v in independent.items() if stance == "contradicts")
            matrix.append({"claim": claim, "evidence": rows, "independent_support": round(support, 4), "independent_contradiction": round(contradict, 4), "evidence_count": len(rows), "status": "contested" if support and contradict else "supported_candidate" if support else "contradicted_candidate" if contradict else "unsubstantiated"})
        return {"hypothesis": hypothesis, "claims": matrix, "summary": {"claim_count": len(matrix), "evidence_links": len(evidence), "unsubstantiated_claims": sum(1 for row in matrix if row["status"] == "unsubstantiated"), "contested_claims": sum(1 for row in matrix if row["status"] == "contested")}, "epistemic_warning": "Die Matrix bewertet Dokumentationsstützung, nicht Schuld, Kausalität oder Wahrheit."}

    def generate_red_team_review(self, *, case_id: str, hypothesis_id: str, actor: str) -> dict[str, Any]:
        matrix = self.claim_evidence_matrix(case_id, hypothesis_id)
        hypothesis = matrix["hypothesis"]
        support_only = [row for row in matrix["claims"] if row["independent_support"] > 0 and row["independent_contradiction"] == 0]
        unsubstantiated = [row for row in matrix["claims"] if row["status"] == "unsubstantiated"]
        counter = "Die beobachteten Hinweise können durch eine alternative Identität, gemeinsame Quelle, zeitliche Überschneidung oder zufällige strukturelle Nähe erklärt werden."
        tests = [
            "Suche gezielt nach einer unabhängigen Quelle, die die Kernannahme widerlegt.",
            "Prüfe, ob scheinbar unabhängige Quellen auf denselben Ursprung zurückgehen.",
            "Teste Zeit-, Orts- und Identitätskonflikte getrennt voneinander.",
            "Formuliere ein Ergebnis, das die Hypothese falsifizieren würde, bevor weitere Bestätigungsquellen gesucht werden.",
        ]
        if unsubstantiated:
            tests.insert(0, f"{len(unsubstantiated)} Claim(s) besitzen noch keine fallgebundene Evidence und dürfen nicht verwendet werden.")
        bias = ["Bestätigungsfehler", "Quellenzählung ohne Unabhängigkeitsprüfung", "Korrelation-als-Kausalität"]
        if support_only:
            bias.append("Einseitige Evidence-Lage ohne dokumentierten Gegenbeleg")
        gaps = [f"Claim {row['claim']['claim_id']}: Gegenquelle oder Falsifikation fehlt" for row in support_only[:10]]
        red_id = _id("red130")
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO red_team_reviews_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (red_id, hypothesis_id, case_id, "generated", counter, _json(tests), _json(bias), _json(gaps), "suggestions_only", "local_red_team_130", "130.0", actor, _now(), "", "", "pending", ""))
            self.db.execute("INSERT INTO graph_ai_suggestions_130 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (_id("gai130"), case_id, hypothesis_id, "", "red_team_brief", _json({"counter_hypothesis": counter, "falsification_tests": tests, "bias_warnings": bias, "source_gaps": gaps}), _json([{"object_type": "hypothesis", "object_id": hypothesis_id}]), "suggestions_only", "pending", "local_red_team_130", "130.0", actor, _now()))
            self._opsec(case_id=case_id, action_type="generate_red_team_review", object_type="hypothesis", object_id=hypothesis_id, value=hypothesis["statement"], minimization={"raw_hypothesis_in_audit": False, "external_actions": 0, "tool_actions": 0}, outcome="suggestions_only", actor=actor)
            self.audit.log("generate_red_team_review_130", "hypothesis_130", hypothesis_id, case_id, {"red_team_id": red_id, "hypothesis_fingerprint": _sha_text(hypothesis["statement"]), "external_actions": 0})
        return {"red_team_id": red_id, "trust_state": "suggestions_only", "review_status": "pending", "counter_hypothesis": counter, "falsification_tests": tests, "bias_warnings": bias, "source_gaps": gaps, "external_actions": 0}

    def review_red_team(self, *, case_id: str, red_team_id: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        decision = str(decision or "").strip()
        if decision not in {"accepted_for_working_notes", "needs_revision", "rejected", "deferred"}:
            raise GraphHypothesisError("Unzulässige Red-Team-Reviewentscheidung")
        if len(str(reason or "").strip()) < 10:
            raise GraphHypothesisError("Substanzielle Red-Team-Reviewbegründung erforderlich")
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT * FROM red_team_reviews_130 WHERE red_team_id=? AND case_id=?", (red_team_id, case_id))
            if not row:
                raise GraphHypothesisError("Red-Team-Prüfung nicht gefunden")
            cur = self.db.execute("""UPDATE red_team_reviews_130 SET review_status=?,reviewed_by=?,reviewed_at=?,review_reason=?
                                   WHERE red_team_id=? AND case_id=? AND review_status='pending'""",
                                  (decision, actor, _now(), str(reason).strip()[:4000], red_team_id, case_id))
            if cur.rowcount != 1:
                raise GraphHypothesisConflict("Red-Team-Prüfung wurde bereits reviewed")
            self._opsec(case_id=case_id, action_type="review_red_team", object_type="red_team_review", object_id=red_team_id, value=reason, minimization={"reason_in_audit": False, "automatic_promotion": False}, outcome=decision, actor=actor)
            self.audit.log("review_red_team_130", "red_team_review_130", red_team_id, case_id, {"decision": decision, "reason_fingerprint": _sha_text(reason)})
        return {"red_team_id": red_team_id, "review_status": decision, "trust_state": "suggestions_only", "automatic_promotion": False}

    def request_hypothesis_review(self, *, case_id: str, hypothesis_id: str, actor: str) -> dict[str, Any]:
        matrix = self.claim_evidence_matrix(case_id, hypothesis_id)
        if matrix["summary"]["claim_count"] == 0:
            raise GraphHypothesisError("Mindestens ein Claim ist erforderlich")
        cur = self.db.execute("UPDATE hypotheses_130 SET state='needs_review',updated_at=? WHERE case_id=? AND hypothesis_id=? AND state='candidate'", (_now(), case_id, hypothesis_id))
        if cur.rowcount != 1:
            raise GraphHypothesisConflict("Hypothese ist nicht mehr für Review verfügbar")
        self.audit.log("request_hypothesis_review_130", "hypothesis_130", hypothesis_id, case_id, {"unsubstantiated_claims": matrix["summary"]["unsubstantiated_claims"], "contested_claims": matrix["summary"]["contested_claims"]})
        return {"hypothesis_id": hypothesis_id, "state": "needs_review"}

    def review_hypothesis(self, *, case_id: str, hypothesis_id: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        if decision not in self.REVIEW_DECISIONS:
            raise GraphHypothesisError("Unzulässige Reviewentscheidung")
        if len(reason.strip()) < 12:
            raise GraphHypothesisError("Substanzielle Reviewbegründung erforderlich")
        with self.db.transaction(immediate=True):
            cur = self.db.execute("""UPDATE hypotheses_130 SET state='reviewed',reviewed_by=?,reviewed_at=?,review_decision=?,review_reason=?,updated_at=?
                                   WHERE case_id=? AND hypothesis_id=? AND state='needs_review'""", (actor, _now(), decision, reason.strip()[:4000], _now(), case_id, hypothesis_id))
            if cur.rowcount != 1:
                raise GraphHypothesisConflict("Hypothese wurde bereits entschieden oder ist nicht im Review")
            self._opsec(case_id=case_id, action_type="review_hypothesis", object_type="hypothesis", object_id=hypothesis_id, value=reason, minimization={"reason_in_audit": False, "automatic_fact_promotion": False, "automatic_graph_promotion": False}, outcome=decision, actor=actor)
            self.audit.log("review_hypothesis_130", "hypothesis_130", hypothesis_id, case_id, {"decision": decision, "reason_fingerprint": _sha_text(reason), "automatic_promotion": False})
        return {"hypothesis_id": hypothesis_id, "state": "reviewed", "review_decision": decision, "candidate_only": True, "automatic_promotion": False}

    def dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        metrics = {
            "analysis_runs": int((self.db.one("SELECT COUNT(*) AS n FROM graph_analysis_runs_130 WHERE case_id=?", (case_id,)) or {}).get("n") or 0),
            "stored_paths": int((self.db.one("SELECT COUNT(*) AS n FROM graph_paths_130 WHERE case_id=?", (case_id,)) or {}).get("n") or 0),
            "hypotheses": int((self.db.one("SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=?", (case_id,)) or {}).get("n") or 0),
            "pending_reviews": int((self.db.one("SELECT COUNT(*) AS n FROM hypotheses_130 WHERE case_id=? AND state='needs_review'", (case_id,)) or {}).get("n") or 0),
            "red_team_pending": int((self.db.one("SELECT COUNT(*) AS n FROM red_team_reviews_130 WHERE case_id=? AND review_status='pending'", (case_id,)) or {}).get("n") or 0),
            "ai_suggestions_pending": int((self.db.one("SELECT COUNT(*) AS n FROM graph_ai_suggestions_130 WHERE case_id=? AND review_status='pending'", (case_id,)) or {}).get("n") or 0),
        }
        latest_run = self.db.one("SELECT * FROM graph_analysis_runs_130 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,))
        if latest_run:
            latest_run["summary"] = _loads(latest_run.get("summary_json"), {})
            latest_run["filters"] = _loads(latest_run.get("filters_json"), {})
        hypotheses = self.db.all("SELECT * FROM hypotheses_130 WHERE case_id=? ORDER BY updated_at DESC LIMIT 100", (case_id,))
        for row in hypotheses:
            matrix = self.claim_evidence_matrix(case_id, row["hypothesis_id"])
            row["matrix_summary"] = matrix["summary"]
        return {
            "build": self.BUILD,
            "metrics": metrics,
            "latest_run": latest_run,
            "top_metrics": self.db.all("SELECT * FROM graph_node_metrics_130 WHERE case_id=? ORDER BY betweenness DESC,degree DESC LIMIT 50", (case_id,)),
            "paths": self.db.all("SELECT * FROM graph_paths_130 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "hypotheses": hypotheses,
            "red_team": self.db.all("SELECT * FROM red_team_reviews_130 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "suggestions": self.db.all("SELECT * FROM graph_ai_suggestions_130 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "source_independence": self.source_independence_graph(case_id, limit=500),
            "status": {"network_actions": 0, "automatic_identity_merge": False, "automatic_graph_promotion": False, "automatic_timeline_promotion": False, "culpability_scoring": False, "trust_state": "suggestions_only"},
        }
