from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Iterable
from urllib.parse import quote_plus

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


@dataclass(frozen=True)
class SearchEngineProfile:
    key: str
    label: str
    base_url: str
    image_url: str | None = None

    def url(self, query: str, *, image_mode: bool = False) -> str:
        q = quote_plus(query)
        if image_mode and self.image_url:
            return self.image_url.format(q=q)
        return self.base_url.format(q=q)


TEN_SEARCH_ENGINES: List[SearchEngineProfile] = [
    SearchEngineProfile("google", "Google", "https://www.google.com/search?q={q}", "https://www.google.com/search?tbm=isch&q={q}"),
    SearchEngineProfile("bing", "Bing", "https://www.bing.com/search?q={q}", "https://www.bing.com/images/search?q={q}"),
    SearchEngineProfile("brave", "Brave", "https://search.brave.com/search?q={q}", "https://search.brave.com/images?q={q}"),
    SearchEngineProfile("duckduckgo", "DuckDuckGo", "https://duckduckgo.com/?q={q}", "https://duckduckgo.com/?iax=images&ia=images&q={q}"),
    SearchEngineProfile("startpage", "Startpage", "https://www.startpage.com/sp/search?query={q}"),
    SearchEngineProfile("qwant", "Qwant", "https://www.qwant.com/?q={q}&t=web", "https://www.qwant.com/?q={q}&t=images"),
    SearchEngineProfile("mojeek", "Mojeek", "https://www.mojeek.com/search?q={q}"),
    SearchEngineProfile("ecosia", "Ecosia", "https://www.ecosia.org/search?q={q}", "https://www.ecosia.org/images?q={q}"),
    SearchEngineProfile("yahoo", "Yahoo", "https://search.yahoo.com/search?p={q}", "https://images.search.yahoo.com/search/images?p={q}"),
    SearchEngineProfile("swisscows", "Swisscows", "https://swisscows.com/web?query={q}", "https://swisscows.com/images?query={q}"),
]

# Backwards compatible symbol name; Build 55.3 uses ten engines but older code
# may still import the historical constant.
EIGHT_SEARCH_ENGINES = TEN_SEARCH_ENGINES


SEARCH_CATEGORIES_55_1: List[Dict[str, Any]] = [
    {
        "key": "person_core",
        "letter": "a",
        "label": "Person",
        "description": "Basisidentität, Namensvarianten, öffentliche Profile, Presse- und PDF-Funde.",
        "sensitivity": "normal",
        "open_policy": "category_allowed",
    },
    {
        "key": "person_organization",
        "letter": "b",
        "label": "Person in Bezug zu Organisation",
        "description": "Person + Organisation, Rollen, Vorstand, Team, Verein, Gemeinde, Firma, Satzung, Amtsblatt.",
        "sensitivity": "normal",
        "open_policy": "category_allowed",
    },
    {
        "key": "person_images",
        "letter": "c",
        "label": "Person in Bezug zu Bilder",
        "description": "Bild-/Foto-/Medienhinweise und visuelle Quellen; keine biometrische Identitätsbestätigung.",
        "sensitivity": "high_review",
        "open_policy": "image_review_required",
    },
    {
        "key": "person_public_personal_data",
        "letter": "d",
        "label": "Person in Bezug zu öffentlich zugänglichen persönlichen Daten",
        "description": "Öffentliche Register-/Archiv-/Impressums-/Nachruf-Kontexte zu Geburtsdatum, Geburtsort, Sterbedatum, öffentlicher Kontaktangabe. Private Wohnadressen bleiben exportgesperrt.",
        "sensitivity": "authority_sensitive",
        "open_policy": "manual_review_required",
    },
    {
        "key": "person_legal_proceedings",
        "letter": "e",
        "label": "Person in Bezug zu amtlichen Verfahren / Gerichtsverfahren / Urteilen",
        "description": "Öffentliche Gerichtsentscheidungen, Verfahren, Aktenzeichen, Pressemitteilungen, Prozessberichte, Justiz-PDFs.",
        "sensitivity": "criminal_allegation_review",
        "open_policy": "manual_review_required",
    },
    {
        "key": "person_networks_company_networks",
        "letter": "f",
        "label": "Person in Bezug zu Netzwerken / Firmennetzwerken",
        "description": "Öffentliche Rollen-, Firmen-, Vereins-, Domain-, Vergabe- und Netzwerkbezüge.",
        "sensitivity": "normal_review",
        "open_policy": "category_allowed",
    },
    {
        "key": "person_public_financial_data",
        "letter": "g",
        "label": "Person in Bezug zu öffentlich einsehbaren Finanzangaben",
        "description": "Öffentliche Finanz-/Register-/Jahresabschluss-/Förder-/Vergabe-Kontexte. Keine private Kredit-, Konten- oder Vermögensausforschung.",
        "sensitivity": "financial_review",
        "open_policy": "manual_review_required",
    },
]


CATEGORY_ORDER = {c["key"]: i for i, c in enumerate(SEARCH_CATEGORIES_55_1)}


class CategorizedDeepSearchService:
    """Build 55.3 categorized deep-search workbench.

    Generates category-bound deep search parameters and ten search-engine links per
    parameter. It does not bypass logins, paywalls, CAPTCHAs or restricted systems.
    Sensitive personal-data categories are marked for manual review and redaction.
    """

    def __init__(self, db: Database, audit: AuditService, search_chain):
        self.db = db
        self.audit = audit
        self.search_chain = search_chain
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS categorized_search_plans_55_3 (
          plan_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          category_count INTEGER DEFAULT 0,
          parameter_count INTEGER DEFAULT 0,
          engine_count INTEGER DEFAULT 10,
          query_node_count INTEGER DEFAULT 0,
          source_seed_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          status TEXT DEFAULT 'planned',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_catsearch552_case ON categorized_search_plans_55_3(case_id, created_at);
        ''')
        self.db.conn.commit()

    def categories(self) -> List[Dict[str, Any]]:
        return [dict(c) for c in SEARCH_CATEGORIES_55_1]

    def engines(self) -> List[Dict[str, str]]:
        return [{"key": e.key, "label": e.label} for e in TEN_SEARCH_ENGINES]

    def generate_for_entity(self, case_id: str, entity: Dict[str, Any], *, root_node_id: str = "", replace_existing: bool = False, max_parameters_per_category: int = 14) -> Dict[str, Any]:
        if not case_id:
            raise ValueError("case_id is required")
        entity_id = entity.get("entity_id", "")
        if not entity_id:
            raise ValueError("entity_id is required")
        root = root_node_id or self._ensure_root(case_id, entity)
        seed = self._normalize_seed(entity)
        if replace_existing:
            self._delete_existing_generated_queries(case_id, entity_id)
        plan_id = new_id("cat55_3")
        total_params = 0
        total_nodes = 0
        by_category: Dict[str, Dict[str, Any]] = {}
        for cat in SEARCH_CATEGORIES_55_1:
            params = self._build_category_parameters(cat["key"], seed)[:max_parameters_per_category]
            by_category[cat["key"]] = {
                "category": cat,
                "parameters": params,
                "query_nodes": 0,
            }
            total_params += len(params)
            category_parent = self.search_chain.add_node(
                case_id,
                "search_category",
                f"{cat['letter']}) {cat['label']}",
                cat["description"],
                entity_id=entity_id,
                parent_node_id=root,
                relation_type="generated_category",
                relevance_score=85,
                confidence_label="planned_category",
                metadata={"category_key": cat["key"], "category_label": cat["label"], "letter": cat["letter"], "sensitivity": cat["sensitivity"], "open_policy": cat["open_policy"], "build": "55.3"},
                status="planned",
            )
            for param_index, p in enumerate(params, start=1):
                param_node = self.search_chain.add_node(
                    case_id,
                    "search_parameter",
                    f"{cat['letter']}{param_index:02d}: {p['title']}",
                    p["query"],
                    entity_id=entity_id,
                    parent_node_id=category_parent["node_id"],
                    relation_type="generated_parameter",
                    relevance_score=int(p.get("priority", 70)),
                    confidence_label="deep_parameter",
                    metadata={"category_key": cat["key"], "category_label": cat["label"], "parameter_title": p["title"], "dork_level": p.get("dork_level", "standard"), "sensitivity": cat["sensitivity"], "review_required": bool(p.get("review_required", True)), "redaction_required": bool(p.get("redaction_required", False)), "privacy_note": p.get("privacy_note", ""), "build": "55.3"},
                    status="planned",
                )
                image_mode = cat["key"] == "person_images"
                for engine in TEN_SEARCH_ENGINES:
                    url = engine.url(p["query"], image_mode=image_mode)
                    existing = self.db.one(
                        "SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='search_query' AND title=?",
                        [param_node["node_id"], f"{engine.label}: {p['query']}"]
                    )
                    if existing:
                        continue
                    self.search_chain.add_node(
                        case_id,
                        "search_query",
                        f"{engine.label}: {p['query']}",
                        p["query"],
                        entity_id=entity_id,
                        parent_node_id=param_node["node_id"],
                        relation_type="generated_engine_query",
                        relevance_score=int(p.get("priority", 70)),
                        confidence_label="planned",
                        metadata={"engine": engine.key, "engine_label": engine.label, "search_url": url, "category_key": cat["key"], "category_label": cat["label"], "parameter_title": p["title"], "dork_level": p.get("dork_level", "standard"), "sensitivity": cat["sensitivity"], "review_required": bool(p.get("review_required", True)), "redaction_required": bool(p.get("redaction_required", False)), "privacy_note": p.get("privacy_note", ""), "build": "55.3"},
                        status="planned",
                    )
                    total_nodes += 1
                    by_category[cat["key"]]["query_nodes"] += 1
        self.db.execute('''INSERT INTO categorized_search_plans_55_3(plan_id,case_id,entity_id,category_count,parameter_count,engine_count,query_node_count,source_seed_json,created_at,status)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [plan_id, case_id, entity_id, len(SEARCH_CATEGORIES_55_1), total_params, len(TEN_SEARCH_ENGINES), total_nodes, dumps(seed), now_ts(), "planned"])
        self.audit.log("create", "categorized_search_plan_55_3", plan_id, case_id, {"entity_id": entity_id, "parameters": total_params, "query_nodes": total_nodes})
        return {"plan_id": plan_id, "case_id": case_id, "entity_id": entity_id, "categories": self.categories(), "category_count": len(SEARCH_CATEGORIES_55_1), "parameter_count": total_params, "query_node_count": total_nodes, "engine_count": len(TEN_SEARCH_ENGINES), "by_category": by_category}

    def generate_for_category(self, case_id: str, entity: Dict[str, Any], category_key: str, *, root_node_id: str = "", replace_existing: bool = False, max_parameters: int = 10) -> Dict[str, Any]:
        """Build 55.3: generate deep search nodes for one selected category only.

        This prevents the previous 55.1 behaviour where all seven categories could
        create hundreds of browser-opening rows at once. The user selects a category,
        generates only that category, and then opens ten engines for one chosen
        parameter.
        """
        if not case_id:
            raise ValueError("case_id is required")
        entity_id = entity.get("entity_id", "")
        if not entity_id:
            raise ValueError("entity_id is required")
        if not category_key or category_key == "all":
            raise ValueError("Bitte eine konkrete personenbezogene Suchkategorie auswählen.")
        cat = next((c for c in SEARCH_CATEGORIES_55_1 if c["key"] == category_key), None)
        if not cat:
            raise ValueError(f"Unknown search category: {category_key}")
        root = root_node_id or self._ensure_root(case_id, entity)
        seed = self._normalize_seed(entity)
        if replace_existing:
            self._delete_existing_generated_category(case_id, entity_id, category_key)
        plan_id = new_id("cat55_3")
        params = self._build_category_parameters(category_key, seed)[:max_parameters]
        category_parent = self.search_chain.add_node(
            case_id,
            "search_category",
            f"{cat['letter']}) {cat['label']}",
            cat["description"],
            entity_id=entity_id,
            parent_node_id=root,
            relation_type="generated_selected_category",
            relevance_score=90,
            confidence_label="selected_category",
            metadata={"category_key": cat["key"], "category_label": cat["label"], "letter": cat["letter"], "sensitivity": cat["sensitivity"], "open_policy": cat["open_policy"], "build": "55.3", "selected_only": True},
            status="planned",
        )
        query_nodes = 0
        for param_index, p in enumerate(params, start=1):
            param_node = self.search_chain.add_node(
                case_id,
                "search_parameter",
                f"{cat['letter']}{param_index:02d}: {p['title']}",
                p["query"],
                entity_id=entity_id,
                parent_node_id=category_parent["node_id"],
                relation_type="generated_selected_parameter",
                relevance_score=int(p.get("priority", 70)),
                confidence_label="deep_parameter",
                metadata={"category_key": cat["key"], "category_label": cat["label"], "parameter_title": p["title"], "dork_level": p.get("dork_level", "standard"), "sensitivity": cat["sensitivity"], "review_required": bool(p.get("review_required", True)), "redaction_required": bool(p.get("redaction_required", False)), "privacy_note": p.get("privacy_note", ""), "build": "55.3", "selected_only": True},
                status="planned",
            )
            image_mode = cat["key"] == "person_images"
            for engine in TEN_SEARCH_ENGINES:
                self.search_chain.add_node(
                    case_id,
                    "search_query",
                    f"{engine.label}: {p['query']}",
                    p["query"],
                    entity_id=entity_id,
                    parent_node_id=param_node["node_id"],
                    relation_type="generated_ten_engine_query",
                    relevance_score=int(p.get("priority", 70)),
                    confidence_label="planned",
                    metadata={"engine": engine.key, "engine_label": engine.label, "search_url": engine.url(p["query"], image_mode=image_mode), "category_key": cat["key"], "category_label": cat["label"], "parameter_title": p["title"], "dork_level": p.get("dork_level", "standard"), "sensitivity": cat["sensitivity"], "review_required": bool(p.get("review_required", True)), "redaction_required": bool(p.get("redaction_required", False)), "privacy_note": p.get("privacy_note", ""), "build": "55.3", "selected_only": True},
                    status="planned",
                )
                query_nodes += 1
        self.db.execute("""INSERT INTO categorized_search_plans_55_3(plan_id,case_id,entity_id,category_count,parameter_count,engine_count,query_node_count,source_seed_json,created_at,status)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [plan_id, case_id, entity_id, 1, len(params), len(TEN_SEARCH_ENGINES), query_nodes, dumps({**seed, "selected_category": category_key}), now_ts(), "planned"])
        self.audit.log("create", "categorized_search_plan_55_3", plan_id, case_id, {"entity_id": entity_id, "category_key": category_key, "parameters": len(params), "query_nodes": query_nodes})
        return {"plan_id": plan_id, "case_id": case_id, "entity_id": entity_id, "category_key": category_key, "category": cat, "category_count": 1, "parameter_count": len(params), "query_node_count": query_nodes, "engine_count": len(TEN_SEARCH_ENGINES)}



    def first_parameter_node_id(self, case_id: str, entity_id: str = "", category_key: str = "") -> str:
        """Build 55.3: return the first generated parameter for a selected category.

        Used by the one-page UI to open exactly ten search engines immediately
        after a selected category has been derived, without requiring a manual
        row selection first.
        """
        chain = self.search_chain.build_professional_chain(case_id, entity_id=entity_id)
        candidates = []
        for n in chain.get("nodes", []):
            if n.get("node_type") != "search_parameter":
                continue
            meta = n.get("metadata") or {}
            if category_key and category_key != "all" and meta.get("category_key") != category_key:
                continue
            candidates.append(n)
        candidates.sort(key=lambda n: (CATEGORY_ORDER.get((n.get("metadata") or {}).get("category_key", "zzz"), 999), n.get("title", ""), n.get("created_at", "")))
        return candidates[0].get("node_id", "") if candidates else ""

    def query_rows_for_parameter(self, parameter_node_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='search_query' ORDER BY created_at, title", [parameter_node_id])
        return [self.search_chain.get_node(r["node_id"]) for r in rows]

    def _delete_existing_generated_category(self, case_id: str, entity_id: str, category_key: str) -> None:
        rows = self.db.all("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND metadata_json LIKE ? AND metadata_json LIKE '%selected_only%'", [case_id, entity_id, f'%{category_key}%'])
        for r in rows:
            nid = r["node_id"]
            child = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type NOT IN ('search_query','search_parameter') LIMIT 1", [nid])
            if child:
                continue
            self.db.execute("DELETE FROM search_chain_edges_54 WHERE from_node_id=? OR to_node_id=?", [nid, nid])
            self.db.execute("DELETE FROM search_chain_nodes_54 WHERE node_id=?", [nid])
        self.db.conn.commit()

    def summarize_chain_categories(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        chain = self.search_chain.build_professional_chain(case_id, entity_id=entity_id)
        summary: Dict[str, Dict[str, Any]] = {}
        for cat in SEARCH_CATEGORIES_55_1:
            summary[cat["key"]] = {"category": cat, "parameters": 0, "queries": 0, "opened": 0, "findings": 0, "included": 0, "review_required": cat["open_policy"] != "category_allowed"}
        for n in chain.get("nodes", []):
            meta = n.get("metadata") or {}
            ckey = meta.get("category_key")
            if ckey not in summary:
                continue
            if n.get("node_type") == "search_parameter":
                summary[ckey]["parameters"] += 1
            elif n.get("node_type") in {"search_query", "derived_query"}:
                summary[ckey]["queries"] += 1
                if n.get("status") == "opened":
                    summary[ckey]["opened"] += 1
            elif n.get("node_type") == "source_hit":
                summary[ckey]["findings"] += 1
            elif n.get("node_type") == "included_fact":
                summary[ckey]["included"] += 1
        return {"case_id": case_id, "entity_id": entity_id, "categories": list(summary.values())}

    def filtered_query_rows(self, case_id: str, entity_id: str = "", category_key: str = "") -> List[Dict[str, Any]]:
        chain = self.search_chain.build_professional_chain(case_id, entity_id=entity_id)
        rows = []
        for n in chain.get("nodes", []):
            if n.get("node_type") not in {"search_query", "derived_query"}:
                continue
            meta = n.get("metadata") or {}
            if category_key and category_key != "all" and meta.get("category_key") != category_key:
                continue
            rows.append(n)
        rows.sort(key=lambda n: (CATEGORY_ORDER.get((n.get("metadata") or {}).get("category_key", "zzz"), 999), n.get("title", "")))
        return rows


    def expand_included_fact(self, fact_node_id: str, *, max_parameters: int = 6) -> Dict[str, Any]:
        """Build 55.3: derive new category-bound search parameters from an included fact.

        This is the Search/Fund-Chain recursion step: Finding → included information
        → new deep parameters → eight search engines per parameter.
        """
        fact = self.search_chain.get_node(fact_node_id)
        if fact.get("node_type") != "included_fact":
            raise ValueError("expand_included_fact requires an included_fact node")
        fmeta = fact.get("metadata", {}) or {}
        category_key = fmeta.get("category_key") or self._category_for_fact_type(fmeta.get("fact_type", "included_fact"))
        cat = next((c for c in SEARCH_CATEGORIES_55_1 if c["key"] == category_key), SEARCH_CATEGORIES_55_1[0])
        seed = {"name": fact.get("value", ""), "names": [fact.get("value", "")], "places": [], "organizations": [], "roles": [], "identifiers": [], "public_links": [], "dates": []}
        params = self._build_category_parameters(category_key, seed)[:max_parameters]
        if not params:
            value = fact.get("value", "")
            params = [
                {"title": "Inkludierte Information exakt", "query": f'"{value}"', "priority": 72, "dork_level": "derived", "review_required": True, "redaction_required": bool(fmeta.get("redaction_required", False)), "privacy_note": fmeta.get("privacy_note", "")},
                {"title": "Inkludierte Information PDF/Quelle", "query": f'"{value}" filetype:pdf', "priority": 70, "dork_level": "derived_dork", "review_required": True, "redaction_required": bool(fmeta.get("redaction_required", False)), "privacy_note": fmeta.get("privacy_note", "")},
                {"title": "Inkludierte Information Amts-/Registerkontext", "query": f'"{value}" (Amtsblatt OR Register OR Presse OR Bericht)', "priority": 68, "dork_level": "derived_dork", "review_required": True, "redaction_required": bool(fmeta.get("redaction_required", False)), "privacy_note": fmeta.get("privacy_note", "")},
            ][:max_parameters]
        created_parameters: List[Dict[str, Any]] = []
        created_queries: List[Dict[str, Any]] = []
        for idx, param in enumerate(params, start=1):
            ptitle = f"Ableitung {cat['letter']}{idx:02d}: {param['title']}"
            existing = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='search_parameter' AND title=?", [fact_node_id, ptitle])
            if existing:
                param_node = self.search_chain.get_node(existing["node_id"])
            else:
                param_node = self.search_chain.add_node(
                    fact["case_id"],
                    "search_parameter",
                    ptitle,
                    param["query"],
                    entity_id=fact.get("entity_id", ""),
                    parent_node_id=fact_node_id,
                    relation_type="derived_parameter_from_included_fact",
                    relevance_score=int(param.get("priority", 70)),
                    confidence_label="derived_deep_parameter",
                    metadata={"category_key": category_key, "category_label": cat["label"], "parameter_title": param["title"], "dork_level": param.get("dork_level", "derived"), "sensitivity": cat["sensitivity"], "review_required": True, "redaction_required": bool(param.get("redaction_required", False) or fmeta.get("redaction_required", False)), "privacy_note": param.get("privacy_note", fmeta.get("privacy_note", "")), "build": "55.3", "derived_from_included_fact": fact_node_id},
                    status="planned",
                )
            created_parameters.append(param_node)
            image_mode = category_key == "person_images"
            for engine in TEN_SEARCH_ENGINES:
                title = f"{engine.label}: {param['query']}"
                existing_q = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type='search_query' AND title=?", [param_node["node_id"], title])
                if existing_q:
                    created_queries.append(self.search_chain.get_node(existing_q["node_id"]))
                    continue
                created_queries.append(self.search_chain.add_node(
                    fact["case_id"],
                    "search_query",
                    title,
                    param["query"],
                    entity_id=fact.get("entity_id", ""),
                    parent_node_id=param_node["node_id"],
                    relation_type="generated_engine_query_from_included_fact",
                    relevance_score=int(param.get("priority", 70)),
                    confidence_label="planned",
                    metadata={"engine": engine.key, "engine_label": engine.label, "search_url": engine.url(param["query"], image_mode=image_mode), "category_key": category_key, "category_label": cat["label"], "parameter_title": param["title"], "dork_level": param.get("dork_level", "derived"), "sensitivity": cat["sensitivity"], "review_required": True, "redaction_required": bool(param.get("redaction_required", False) or fmeta.get("redaction_required", False)), "privacy_note": param.get("privacy_note", fmeta.get("privacy_note", "")), "build": "55.3", "derived_from_included_fact": fact_node_id},
                    status="planned",
                ))
        self.audit.log("create", "categorized_search_derived_55_3", fact_node_id, fact["case_id"], {"category_key": category_key, "parameters": len(created_parameters), "queries": len(created_queries)})
        return {"fact_node_id": fact_node_id, "category_key": category_key, "parameters": created_parameters, "queries": created_queries, "parameter_count": len(created_parameters), "query_count": len(created_queries)}

    def _category_for_fact_type(self, fact_type: str) -> str:
        mapping = {
            "organization": "person_organization",
            "role": "person_networks_company_networks",
            "place": "person_core",
            "domain": "person_networks_company_networks",
            "case_number": "person_legal_proceedings",
            "person_name": "person_core",
            "document": "person_core",
            "finance": "person_public_financial_data",
            "image": "person_images",
        }
        return mapping.get(str(fact_type or "").strip(), "person_core")

    def _ensure_root(self, case_id: str, entity: Dict[str, Any]) -> str:
        entity_id = entity.get("entity_id", "")
        existing = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND node_type='seed_info' AND parent_node_id='' ORDER BY created_at LIMIT 1", [case_id, entity_id])
        if existing:
            return existing["node_id"]
        return self.search_chain.seed_from_entity(case_id, entity).get("root_node", {}).get("node_id", "")

    def _delete_existing_generated_queries(self, case_id: str, entity_id: str) -> None:
        # Keep prior manually added findings/evidence. Only remove 55.1 planned query scaffolding without descendants.
        rows = self.db.all("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND metadata_json LIKE '%55.1%' AND node_type IN ('search_query','search_parameter','search_category')", [case_id, entity_id])
        ids = [r["node_id"] for r in rows]
        for nid in ids:
            child = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE parent_node_id=? AND node_type NOT IN ('search_query','search_parameter') LIMIT 1", [nid])
            if child:
                continue
            self.db.execute("DELETE FROM search_chain_edges_54 WHERE from_node_id=? OR to_node_id=?", [nid, nid])
            self.db.execute("DELETE FROM search_chain_nodes_54 WHERE node_id=?", [nid])

    def _normalize_seed(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        name = str(entity.get("display_name") or entity.get("name") or "").strip()
        known_names = _as_list(entity.get("known_names")) or [name]
        aliases = _as_list(entity.get("aliases"))
        places = _as_list(entity.get("places"))
        orgs = _as_list(entity.get("organizations"))
        roles = _as_list(entity.get("roles"))
        identifiers = _as_list(entity.get("identifiers"))
        links = _as_list(entity.get("public_links"))
        dates = _as_list(entity.get("dates"))
        names = _dedupe([name, *known_names, *aliases])[:10]
        return {"name": name, "names": names, "places": places[:8], "organizations": orgs[:8], "roles": roles[:8], "identifiers": identifiers[:8], "public_links": links[:8], "dates": dates[:8]}

    def _build_category_parameters(self, category_key: str, seed: Dict[str, Any]) -> List[Dict[str, Any]]:
        names = seed.get("names") or [seed.get("name", "")]
        places = seed.get("places") or []
        orgs = seed.get("organizations") or []
        roles = seed.get("roles") or []
        dates = seed.get("dates") or []
        identifiers = seed.get("identifiers") or []
        params: List[Dict[str, Any]] = []

        def add(title: str, query: str, *, priority: int = 70, dork_level: str = "standard", review: bool = True, redaction: bool = False, note: str = ""):
            q = " ".join(str(query).split()).strip()
            if q:
                params.append({"title": title, "query": q, "priority": priority, "dork_level": dork_level, "review_required": review, "redaction_required": redaction, "privacy_note": note})

        for name in names[:6]:
            if category_key == "person_core":
                add("Exakter Name", f'"{name}"', priority=95)
                add("Name + PDF", f'"{name}" filetype:pdf', priority=92, dork_level="dork")
                add("Name + Presse", f'"{name}" (Presse OR Zeitung OR Bericht OR Interview)', priority=86)
                add("Name + Profil", f'"{name}" (Profil OR Vita OR Lebenslauf OR Team OR Mitarbeiter)', priority=82)
                add("Name im Titel", f'intitle:"{name}"', priority=78, dork_level="dork")
                add("Name in URL", f'inurl:"{name.split()[-1] if name.split() else name}" "{name}"', priority=70, dork_level="dork")
                add("Name + Archiv", f'"{name}" (Archiv OR Zeitungsarchiv OR Nachruf)', priority=72)
            elif category_key == "person_images":
                add("Name + Foto/Bild", f'"{name}" (Foto OR Bild OR Bilder OR image OR portrait)', priority=88, redaction=True, note="Bildtreffer sind keine biometrische Identitätsbestätigung.")
                add("Name + Medien", f'"{name}" (Galerie OR Pressefoto OR Veranstaltung OR Vortrag)', priority=82, redaction=True)
                add("Name + Dateiformate", f'"{name}" (filetype:jpg OR filetype:png OR filetype:webp)', priority=76, dork_level="dork", redaction=True)
                add("Name + Site/Bilddaten", f'"{name}" (site:commons.wikimedia.org OR site:flickr.com OR site:instagram.com)', priority=62, dork_level="dork", redaction=True)
            elif category_key == "person_public_personal_data":
                add("Öffentliche Lebensdaten", f'"{name}" (Geburtsdatum OR geboren OR Geburtsort OR Sterbedatum OR verstorben OR Nachruf)', priority=86, dork_level="dork", redaction=True, note="Lebensdaten nur bei öffentlicher Quelle und manueller Prüfung verwerten.")
                add("Öffentliche Kontaktangaben", f'"{name}" (E-Mail OR Email OR Kontakt OR Impressum) filetype:pdf', priority=78, dork_level="dork", redaction=True, note="Private Kontakte bleiben exportgesperrt; nur öffentlich-funktionale Kontakte prüfen.")
                add("Öffentliche Anschrift-Kontexte", f'"{name}" (Adresse OR Anschrift OR Impressum OR Register OR Sitz) -Telefonbuch', priority=62, dork_level="sensitive_dork", redaction=True, note="Private Wohnadressen nicht exportieren; nur offizielle/funktionale öffentliche Anschriften prüfen.")
                add("Register-/Archiv-Kontext", f'"{name}" (Personenstandsregister OR Standesamt OR Kirchenbuch OR Sterberegister OR Geburtsregister)', priority=72, dork_level="archive_dork", redaction=True)
            elif category_key == "person_legal_proceedings":
                add("Gericht/Urteil", f'"{name}" (Urteil OR Beschluss OR Aktenzeichen OR Gericht)', priority=90, dork_level="legal_dork", redaction=True, note="Gerichtstreffer sind Kandidaten; keine Schuldbehauptung.")
                add("Verfahren/Prozess", f'"{name}" (Prozess OR Gerichtsverfahren OR Verhandlung OR Anklage OR Staatsanwaltschaft)', priority=86, dork_level="legal_dork", redaction=True)
                add("Justiz-PDF", f'"{name}" (Urteil OR Beschluss OR Aktenzeichen) filetype:pdf', priority=88, dork_level="legal_dork", redaction=True)
                add("Amtliche Quellen", f'"{name}" (site:justiz.de OR site:gerichte.* OR site:bund.de OR site:land.de) (Urteil OR Beschluss OR Aktenzeichen)', priority=78, dork_level="site_dork", redaction=True)
            elif category_key == "person_networks_company_networks":
                add("Netzwerk/Rolle", f'"{name}" (Vorstand OR Geschäftsführer OR Beirat OR Kuratorium OR Mitglied OR Netzwerk)', priority=86)
                add("Firma/Verein", f'"{name}" (GmbH OR gGmbH OR e.V. OR Verein OR Verband OR Handelsregister OR Vereinsregister)', priority=84, dork_level="registry_dork")
                add("Domain/Impressum", f'"{name}" (Domain OR Webseite OR Impressum OR Kontakt)', priority=72, dork_level="dork")
                add("Vergabe/Förderung", f'"{name}" (Zuwendung OR Förderung OR Vergabe OR Projektpartner)', priority=66)
            elif category_key == "person_public_financial_data":
                add("Öffentliche Finanzkontexte", f'"{name}" (Jahresabschluss OR Bundesanzeiger OR Unternehmensregister OR Geschäftsbericht)', priority=72, dork_level="finance_dork", redaction=True, note="Nur öffentliche organisations-/rollenbezogene Finanzdaten; keine private Vermögensausforschung.")
                add("Insolvenz/Restrukturierung öffentlich", f'"{name}" (Insolvenz OR Insolvenzbekanntmachung OR Restrukturierung) -Kredit -Schufa', priority=58, dork_level="sensitive_finance_dork", redaction=True)
                add("Förder-/Spendenkontext", f'"{name}" (Spenden OR Zuwendung OR Förderung OR Transparenzbericht OR Rechenschaftsbericht)', priority=64, redaction=True)
        for name in names[:5]:
            for org in orgs[:6]:
                if category_key == "person_organization":
                    add("Person + Organisation", f'"{name}" "{org}"', priority=96)
                    add("Person + Organisation PDF", f'"{name}" "{org}" filetype:pdf', priority=92, dork_level="dork")
                    add("Person + Organisation + Rolle", f'"{name}" "{org}" (Vorstand OR Team OR Mitarbeiter OR Ansprechpartner OR Projekt)', priority=88)
                    add("Person + Organisation + Amtlich", f'"{name}" "{org}" (Amtsblatt OR Satzung OR Protokoll OR Geschäftsbericht)', priority=82)
                if category_key == "person_networks_company_networks":
                    add("Person-Organisation-Netzwerk", f'"{name}" "{org}" (Netzwerk OR Partner OR Vorstand OR Beirat OR Geschäftsführung)', priority=90)
                    add("Register-Bezug", f'"{name}" "{org}" (Handelsregister OR Vereinsregister OR Unternehmensregister OR Bundesanzeiger)', priority=88, dork_level="registry_dork")
                if category_key == "person_public_financial_data":
                    add("Person + Organisation + Finanzbericht", f'"{name}" "{org}" (Jahresabschluss OR Geschäftsbericht OR Bundesanzeiger OR Förderung OR Zuwendung)', priority=82, dork_level="finance_dork", redaction=True)
        for name in names[:5]:
            for place in places[:6]:
                if category_key == "person_core":
                    add("Name + Ort", f'"{name}" "{place}"', priority=90)
                    add("Name + Ort + PDF", f'"{name}" "{place}" filetype:pdf', priority=88, dork_level="dork")
                if category_key == "person_public_personal_data":
                    add("Lebensdaten + Ort", f'"{name}" "{place}" (geboren OR Geburtsort OR verstorben OR Nachruf OR Adresse OR Anschrift)', priority=76, redaction=True)
                if category_key == "person_legal_proceedings":
                    add("Gericht + Ort", f'"{name}" "{place}" (Gericht OR Urteil OR Prozess OR Polizei OR Staatsanwaltschaft)', priority=80, redaction=True)
        for name in names[:4]:
            for role in roles[:4]:
                if category_key in {"person_organization", "person_networks_company_networks"}:
                    add("Name + Rolle", f'"{name}" "{role}"', priority=78)
                    add("Name + Rolle PDF", f'"{name}" "{role}" filetype:pdf', priority=76, dork_level="dork")
        for name in names[:4]:
            for d in dates[:4]:
                if category_key == "person_core":
                    add("Name + Zeitraum", f'"{name}" "{d}"', priority=68)
                if category_key == "person_legal_proceedings":
                    add("Name + Zeitraum + Gericht", f'"{name}" "{d}" (Gericht OR Urteil OR Verfahren)', priority=74, redaction=True)
                if category_key == "person_public_personal_data":
                    add("Name + Zeitraum + Lebensdaten", f'"{name}" "{d}" (geboren OR verstorben OR Heirat OR Trauung)', priority=66, redaction=True)
        for identifier in identifiers[:4]:
            for name in names[:3]:
                if category_key in {"person_core", "person_networks_company_networks", "person_legal_proceedings"}:
                    add("Name + Kennung", f'"{name}" "{identifier}"', priority=70, dork_level="identifier_dork", redaction=True)
        return _dedupe_params(params, limit=40)


def _as_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).replace(";", ",").split(",") if v.strip()]


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        val = str(v).strip()
        key = val.lower()
        if val and key not in seen:
            seen.add(key)
            out.append(val)
    return out


def _dedupe_params(params: List[Dict[str, Any]], limit: int = 40) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for p in sorted(params, key=lambda x: int(x.get("priority", 0)), reverse=True):
        key = p["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= limit:
            break
    return out
