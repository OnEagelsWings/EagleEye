from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote_plus

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

ENTITY_TERMS = {
    "person": ["filetype:pdf", "Zeitung", "Presse", "Gericht OR Urteil", "Amtsblatt", "Register", "Verein OR Organisation"],
    "organization": ["Vorstand", "Satzung filetype:pdf", "Vereinsregister OR Handelsregister", "Amtsblatt", "Presse", "Insolvenz", "Förderung OR Vergabe"],
    "incident": ["Polizei", "Presse", "Amtsblatt", "Gericht", "Zeugenaufruf", "Timeline"],
}

CHAIN_STATUS_LABELS = {
    "active": "aktiv",
    "new": "neu",
    "planned": "geplant",
    "opened": "gesucht/geöffnet",
    "found": "Fund vorhanden",
    "included": "inkludiert",
    "discarded": "verworfen",
    "counter_evidence": "Gegenbeleg",
    "profile_candidate": "Profilkandidat",
    "report_released": "für Bericht freigegeben",
    "needs_review": "Review erforderlich",
}


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).replace(";", ",").split(",") if v.strip()]


class SearchFundChainService:
    """Build 54 searchable provenance chain.

    Every query and finding has an origin. A profile claim can point back to the
    chain instead of appearing as a free-floating assertion.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS search_chain_nodes_54 (
          node_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          node_type TEXT NOT NULL,
          title TEXT NOT NULL,
          value TEXT NOT NULL,
          source_url TEXT DEFAULT '',
          source_object_type TEXT DEFAULT '',
          source_object_id TEXT DEFAULT '',
          parent_node_id TEXT DEFAULT '',
          status TEXT DEFAULT 'active',
          relevance_score INTEGER DEFAULT 50,
          confidence_label TEXT DEFAULT 'candidate',
          metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS search_chain_edges_54 (
          edge_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          from_node_id TEXT NOT NULL,
          to_node_id TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          explanation TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_chain54_case ON search_chain_nodes_54(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_chain54_parent ON search_chain_nodes_54(parent_node_id);
        ''')
        self.db.conn.commit()

    def add_node(self, case_id: str, node_type: str, title: str, value: str, *, entity_id: str = "", parent_node_id: str = "", relation_type: str = "generated", source_url: str = "", source_object_type: str = "", source_object_id: str = "", relevance_score: int = 50, confidence_label: str = "candidate", metadata: Dict[str, Any] | None = None, status: str = "active") -> Dict[str, Any]:
        if not title.strip() or not value.strip():
            raise ValueError("Chain node title and value are required.")
        node_id = new_id("chain54")
        self.db.execute('''INSERT INTO search_chain_nodes_54(node_id,case_id,entity_id,node_type,title,value,source_url,source_object_type,source_object_id,parent_node_id,status,relevance_score,confidence_label,metadata_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [node_id, case_id, entity_id, node_type, title.strip(), value.strip(), source_url, source_object_type, source_object_id, parent_node_id, status, int(relevance_score), confidence_label, dumps(metadata or {}), now_ts()])
        if parent_node_id:
            self._add_edge(case_id, parent_node_id, node_id, relation_type, f"{node_type} derived from {parent_node_id}")
        self.audit.log("create", "search_chain_node_54", node_id, case_id, {"node_type": node_type, "parent": parent_node_id})
        return self.get_node(node_id)

    def _add_edge(self, case_id: str, from_node_id: str, to_node_id: str, relation_type: str, explanation: str = "") -> Dict[str, Any]:
        edge_id = new_id("edge54")
        self.db.execute('''INSERT INTO search_chain_edges_54(edge_id,case_id,from_node_id,to_node_id,relation_type,explanation,created_at)
        VALUES(?,?,?,?,?,?,?)''', [edge_id, case_id, from_node_id, to_node_id, relation_type, explanation, now_ts()])
        return {"edge_id": edge_id, "from_node_id": from_node_id, "to_node_id": to_node_id, "relation_type": relation_type}

    def seed_from_entity(self, case_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = entity.get("entity_id", "")
        entity_type = entity.get("entity_type", "person")
        name = entity.get("display_name") or entity.get("name") or "Unnamed entity"
        root = self.add_node(case_id, "seed_info", f"Seed: {name}", name, entity_id=entity_id, relevance_score=90, confidence_label="seed", metadata={"entity_type": entity_type})
        values = []
        for key in ["known_names", "aliases", "places", "organizations", "roles", "identifiers", "public_links"]:
            for item in _as_list(entity.get(key)):
                values.append((key, item))
        for key, item in values:
            self.add_node(case_id, "seed_info", f"{key}: {item}", item, entity_id=entity_id, parent_node_id=root["node_id"], relation_type="has_seed_detail", relevance_score=80, confidence_label="seed", metadata={"field": key}, status="active")
        return {"root_node": root, "seed_detail_count": len(values)}

    def generate_queries_from_node(self, node_id: str, *, engine: str = "google", limit: int = 24) -> Dict[str, Any]:
        node = self.get_node(node_id)
        meta = node.get("metadata", {})
        entity_type = meta.get("entity_type") or "person"
        base = node["value"]
        terms = ENTITY_TERMS.get(entity_type, ENTITY_TERMS["person"])
        created: List[Dict[str, Any]] = []
        seen = set()
        for term in ["", *terms]:
            query = f'"{base}" {term}'.strip()
            if query in seen:
                continue
            seen.add(query)
            search_url = self._search_url(engine, query)
            title = f"{engine}: {query}"
            existing = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='search_query' AND title=?", [node_id, title])
            if existing:
                created.append(self.get_node(existing["node_id"]))
            else:
                created.append(self.add_node(node["case_id"], "search_query", title, query, entity_id=node.get("entity_id", ""), parent_node_id=node_id, relation_type="generated_query", relevance_score=75, confidence_label="planned", metadata={"engine": engine, "search_url": search_url, "source": "derived_from_seed"}, status="planned"))
            if len(created) >= limit:
                break
        return {"origin_node_id": node_id, "created_queries": created, "count": len(created)}

    def add_finding(self, case_id: str, query_node_id: str, title: str, url: str, snippet: str = "", *, entity_id: str = "", document_date: str = "", source_category: str = "public_web", relevance_score: int = 50) -> Dict[str, Any]:
        query = self.get_node(query_node_id)
        qmeta = query.get("metadata", {}) or {}
        meta = {"document_date": document_date, "source_category": source_category, "query": query.get("value", "")}
        for k in ["category_key", "category_label", "parameter_title", "engine", "engine_label", "dork_level", "sensitivity", "review_required", "redaction_required", "privacy_note"]:
            if k in qmeta:
                meta[k] = qmeta[k]
        return self.add_node(case_id, "source_hit", title, snippet or title, entity_id=entity_id or query.get("entity_id", ""), parent_node_id=query_node_id, relation_type="found", source_url=url, relevance_score=relevance_score, confidence_label="candidate", metadata=meta, status="found")

    def include_information(self, finding_node_id: str, included_facts: List[Dict[str, Any]] | List[str], *, reviewer: str = "local-analyst") -> Dict[str, Any]:
        finding = self.get_node(finding_node_id)
        included_nodes: List[Dict[str, Any]] = []
        derived_queries: List[Dict[str, Any]] = []
        for fact in included_facts:
            if isinstance(fact, str):
                fact = {"label": fact, "value": fact, "type": "included_fact"}
            label = str(fact.get("label") or fact.get("type") or "included_fact")
            value = str(fact.get("value") or fact.get("text") or label)
            fmeta = finding.get("metadata", {}) or {}
            included_meta = {"fact_type": fact.get("type", "included_fact"), "reviewer": reviewer}
            for k in ["category_key", "category_label", "parameter_title", "engine", "engine_label", "dork_level", "sensitivity", "review_required", "redaction_required", "privacy_note"]:
                if k in fmeta:
                    included_meta[k] = fmeta[k]
            node = self.add_node(finding["case_id"], "included_fact", label, value, entity_id=finding.get("entity_id", ""), parent_node_id=finding_node_id, relation_type="included", source_url=finding.get("source_url", ""), relevance_score=int(fact.get("relevance_score", 70)), confidence_label=fact.get("confidence_label", "included_candidate"), metadata=included_meta, status="included")
            included_nodes.append(node)
            derived_queries.extend(self._derive_queries_from_fact(node))
        return {"finding_node_id": finding_node_id, "included_nodes": included_nodes, "derived_queries": derived_queries, "included_count": len(included_nodes), "derived_query_count": len(derived_queries)}

    def _derive_queries_from_fact(self, fact_node: Dict[str, Any]) -> List[Dict[str, Any]]:
        value = fact_node["value"]
        fact_type = fact_node.get("metadata", {}).get("fact_type", "included_fact")
        templates = {
            "organization": [f'"{value}" Vorstand', f'"{value}" Satzung filetype:pdf', f'"{value}" Vereinsregister OR Handelsregister', f'"{value}" Amtsblatt'],
            "role": [f'"{value}"', f'"{value}" filetype:pdf'],
            "place": [f'"{value}" Presse', f'"{value}" Amtsblatt'],
            "domain": [f'"{value}"', f'site:{value}'],
            "case_number": [f'"{value}" Gericht', f'"{value}" Urteil'],
            "included_fact": [f'"{value}"', f'"{value}" filetype:pdf'],
        }
        queries = templates.get(fact_type, templates["included_fact"])
        out: List[Dict[str, Any]] = []
        for q in queries[:8]:
            title = f"Derived: {q}"
            existing = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='derived_query' AND title=?", [fact_node["node_id"], title])
            if existing:
                out.append(self.get_node(existing["node_id"]))
            else:
                fmeta = fact_node.get("metadata", {}) or {}
                meta = {"engine": "google", "search_url": self._search_url("google", q), "derived_from_fact_type": fact_type}
                for k in ["category_key", "category_label", "sensitivity", "review_required", "redaction_required", "privacy_note"]:
                    if k in fmeta:
                        meta[k] = fmeta[k]
                out.append(self.add_node(fact_node["case_id"], "derived_query", title, q, entity_id=fact_node.get("entity_id", ""), parent_node_id=fact_node["node_id"], relation_type="derived_query", relevance_score=70, confidence_label="planned", metadata=meta, status="planned"))
        return out

    def get_node(self, node_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM search_chain_nodes_54 WHERE node_id=?", [node_id])
        if not row:
            raise KeyError(node_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def build_chain(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        if entity_id:
            nodes = self.db.all("SELECT * FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? ORDER BY created_at", [case_id, entity_id])
            edges = self.db.all("SELECT * FROM search_chain_edges_54 WHERE case_id=? AND (from_node_id IN (SELECT node_id FROM search_chain_nodes_54 WHERE entity_id=?) OR to_node_id IN (SELECT node_id FROM search_chain_nodes_54 WHERE entity_id=?)) ORDER BY created_at", [case_id, entity_id, entity_id])
        else:
            nodes = self.db.all("SELECT * FROM search_chain_nodes_54 WHERE case_id=? ORDER BY created_at", [case_id])
            edges = self.db.all("SELECT * FROM search_chain_edges_54 WHERE case_id=? ORDER BY created_at", [case_id])
        for n in nodes:
            n["metadata"] = loads(n.pop("metadata_json", "{}"), {})
        metrics = {"nodes": len(nodes), "edges": len(edges), "seed_info": 0, "queries": 0, "findings": 0, "included_facts": 0}
        for n in nodes:
            if n["node_type"] == "seed_info": metrics["seed_info"] += 1
            if n["node_type"] in {"search_query", "derived_query"}: metrics["queries"] += 1
            if n["node_type"] == "source_hit": metrics["findings"] += 1
            if n["node_type"] == "included_fact": metrics["included_facts"] += 1
        return {"case_id": case_id, "entity_id": entity_id, "nodes": nodes, "edges": edges, "metrics": metrics}

    def mark_node_status(self, node_id: str, status: str, *, note: str = "") -> Dict[str, Any]:
        """Set the visible professional workflow status for a chain node."""
        if status not in CHAIN_STATUS_LABELS:
            raise ValueError("Unsupported chain status: " + str(status))
        node = self.get_node(node_id)
        meta = dict(node.get("metadata") or {})
        if note:
            meta.setdefault("status_notes", []).append({"status": status, "note": note, "at": now_ts()})
        self.db.execute("UPDATE search_chain_nodes_54 SET status=?, metadata_json=? WHERE node_id=?", [status, dumps(meta), node_id])
        self.audit.log("update", "search_chain_node_status_55_1", node_id, node["case_id"], {"status": status, "note": note})
        return self.get_node(node_id)

    def get_trace(self, node_id: str) -> Dict[str, Any]:
        """Return the provenance path from seed information to the selected node."""
        trace: List[Dict[str, Any]] = []
        current_id = node_id
        safety = 0
        while current_id and safety < 100:
            node = self.get_node(current_id)
            trace.append(self._decorate_node_for_ui(node, depth=len(trace)))
            current_id = node.get("parent_node_id") or ""
            safety += 1
        trace = list(reversed(trace))
        path_text = " → ".join(f"{n.get('node_type')}:{n.get('title')}" for n in trace)
        return {"node_id": node_id, "trace": trace, "path_text": path_text, "depth": max(0, len(trace) - 1)}

    def build_professional_chain(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        """Build 55.3 professional Search/Fund-Chain with status, depth and provenance path."""
        chain = self.build_chain(case_id, entity_id=entity_id)
        decorated: List[Dict[str, Any]] = []
        status_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for node in chain.get("nodes", []):
            trace = self.get_trace(node["node_id"])
            decorated_node = self._decorate_node_for_ui(node, depth=trace["depth"])
            decorated_node["path_text"] = trace["path_text"]
            decorated_node["trace_node_ids"] = [t["node_id"] for t in trace["trace"]]
            decorated_node["origin_title"] = trace["trace"][0]["title"] if trace["trace"] else node.get("title", "")
            decorated_node["profile_eligible"] = node.get("node_type") == "included_fact" and node.get("status") not in {"discarded", "counter_evidence"}
            decorated_node["report_ready"] = node.get("status") == "report_released"
            decorated.append(decorated_node)
            status_counts[decorated_node["status"]] = status_counts.get(decorated_node["status"], 0) + 1
            type_counts[decorated_node["node_type"]] = type_counts.get(decorated_node["node_type"], 0) + 1
        metrics = dict(chain.get("metrics", {}))
        metrics.update({"status_counts": status_counts, "type_counts": type_counts, "profile_candidates": sum(1 for n in decorated if n.get("profile_eligible")), "report_ready": sum(1 for n in decorated if n.get("report_ready"))})
        chain["nodes"] = decorated
        chain["metrics"] = metrics
        chain["build"] = "55.1"
        chain["quality_rule"] = "Kein Profilpunkt ohne Chain-Rückverfolgung: Grundinfo → Query → Fund → inkludierte Information."
        return chain

    def _decorate_node_for_ui(self, node: Dict[str, Any], *, depth: int = 0) -> Dict[str, Any]:
        out = dict(node)
        status = out.get("status") or "active"
        out["status_label"] = CHAIN_STATUS_LABELS.get(status, status)
        out["depth"] = depth
        out["short_id"] = str(out.get("node_id", ""))[:12]
        out["beleggrad"] = out.get("confidence_label", "candidate")
        out["chain_path_hint"] = "  " * depth + f"{out.get('node_type')} · {out.get('title')}"
        return out

    def _search_url(self, engine: str, query: str) -> str:
        engine = (engine or "google").lower()
        q = quote_plus(query)
        if engine == "brave":
            return f"https://search.brave.com/search?q={q}"
        if engine == "bing":
            return f"https://www.bing.com/search?q={q}"
        if engine == "duckduckgo":
            return f"https://duckduckgo.com/?q={q}"
        return f"https://www.google.com/search?q={q}"
