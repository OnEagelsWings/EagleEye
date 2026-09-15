from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.categorized_search.service import SEARCH_CATEGORIES_55_1, TEN_SEARCH_ENGINES


LEVELS = [
    {"key": "L1_identity_anchor", "label": "L1 Identitätsanker", "precision_bias": 95, "purpose": "hochpräzise Treffer mit Name + vorhandenen Ankern"},
    {"key": "L2_context_expansion", "label": "L2 Kontext-Erweiterung", "precision_bias": 80, "purpose": "relevanten Kontext über Rollen, Orte, Organisationen, Zeiträume erweitern"},
    {"key": "L3_source_dorks", "label": "L3 Quellen-/Dork-Suche", "precision_bias": 78, "purpose": "gezielte Suche in PDFs, Registern, Presse-/Archiv-/Gerichtsquellen"},
    {"key": "L4_countercheck_doppler", "label": "L4 Gegenprüfung / Namensdoppler", "precision_bias": 62, "purpose": "falsche Personen, Ortswidersprüche und Gegenhinweise sichtbar machen"},
]

SOURCE_WEIGHTS = {
    "official_public_record": 24,
    "court_or_justice": 22,
    "registry": 21,
    "public_pdf": 16,
    "newspaper_press": 14,
    "organization_site": 13,
    "archival_source": 13,
    "image_media": 7,
    "public_web": 8,
    "social_public_profile": 5,
    "unknown": 0,
}

RISKY_CATEGORY_KEYS = {
    "person_public_personal_data",
    "person_legal_proceedings",
    "person_images",
    "person_public_financial_data",
}


def _split_values(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return _dedupe([str(v).strip() for v in value if str(v).strip()])
    return _dedupe([v.strip() for v in str(value).replace(";", ",").split(",") if v.strip()])


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        s = str(v).strip()
        if not s:
            continue
        key = re.sub(r"\s+", " ", s.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _tokens(values: Iterable[str]) -> List[str]:
    toks: List[str] = []
    for value in values:
        toks.extend(re.findall(r"[\wÄÖÜäöüß.-]{3,}", str(value), flags=re.UNICODE))
    return _dedupe(toks)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _canonical_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        scheme = p.scheme.lower() or "https"
        netloc = p.netloc.lower().replace("www.", "")
        path = re.sub(r"/+$", "", p.path or "/")
        keep = []
        for k, v in parse_qsl(p.query, keep_blank_values=False):
            if k.lower().startswith("utm_") or k.lower() in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
                continue
            keep.append((k, v))
        return urlunparse((scheme, netloc, path, "", urlencode(keep), ""))
    except Exception:
        return url.strip()


def _hash_text(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore"))
        h.update(b"\x00")
    return h.hexdigest()


@dataclass(frozen=True)
class QualityQuery:
    category_key: str
    level_key: str
    title: str
    query: str
    precision_bias: int
    recall_bias: int
    expected_evidence: str
    review_required: bool = True
    redaction_required: bool = False


class SearchQualityEngineService:
    """Build 55.5 high-precision search quality engine.

    The service turns one-page intake data into an entity fingerprint, builds a
    four-level query pyramid, scores captured/found results, clusters duplicates,
    records analyst feedback and calculates research quality metrics. It is a
    quality layer, not a bypass layer: all outputs remain public-source, review-
    first and export-gated.
    """

    def __init__(self, db: Database, audit: AuditService, search_chain=None):
        self.db = db
        self.audit = audit
        self.search_chain = search_chain
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS search_quality_fingerprints_55_5 (
          fingerprint_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          fingerprint_hash TEXT NOT NULL,
          fingerprint_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id)
        );
        CREATE TABLE IF NOT EXISTS search_quality_queries_55_5 (
          quality_query_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          level_key TEXT NOT NULL,
          title TEXT NOT NULL,
          query TEXT NOT NULL,
          precision_bias INTEGER DEFAULT 70,
          recall_bias INTEGER DEFAULT 50,
          expected_evidence TEXT DEFAULT '',
          review_required INTEGER DEFAULT 1,
          redaction_required INTEGER DEFAULT 0,
          chain_parameter_node_id TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          status TEXT DEFAULT 'planned',
          UNIQUE(case_id, entity_id, category_key, level_key, query)
        );
        CREATE TABLE IF NOT EXISTS search_quality_results_55_5 (
          result_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          quality_query_id TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          source_type TEXT DEFAULT 'public_web',
          document_date TEXT DEFAULT '',
          source_hit_node_id TEXT DEFAULT '',
          duplicate_cluster_id TEXT DEFAULT '',
          entity_match_score INTEGER DEFAULT 0,
          source_quality_score INTEGER DEFAULT 0,
          sensitivity_score INTEGER DEFAULT 0,
          total_score INTEGER DEFAULT 0,
          ranking_label TEXT DEFAULT 'candidate',
          flags_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sq555_results_case_entity ON search_quality_results_55_5(case_id, entity_id, total_score DESC);
        CREATE INDEX IF NOT EXISTS idx_sq555_results_cluster ON search_quality_results_55_5(duplicate_cluster_id);
        CREATE TABLE IF NOT EXISTS search_quality_feedback_55_5 (
          feedback_id TEXT PRIMARY KEY,
          result_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          rating TEXT NOT NULL,
          note TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS search_quality_benchmarks_55_5 (
          benchmark_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          precision_at_10 REAL DEFAULT 0,
          useful_query_rate REAL DEFAULT 0,
          duplicate_rate REAL DEFAULT 0,
          false_positive_rate REAL DEFAULT 0,
          top_result_count INTEGER DEFAULT 0,
          feedback_count INTEGER DEFAULT 0,
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    # ------------------------------------------------------------------
    # Entity fingerprint
    # ------------------------------------------------------------------
    def build_entity_fingerprint(self, case_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
        if not case_id:
            raise ValueError("case_id is required")
        entity_id = entity.get("entity_id") or entity.get("target_id") or ""
        if not entity_id:
            raise ValueError("entity_id is required")
        display_name = str(entity.get("display_name") or entity.get("name") or "").strip()
        if not display_name:
            raise ValueError("display_name/name is required")
        names = _dedupe([display_name, *_split_values(entity.get("known_names")), *_split_values(entity.get("aliases"))])
        places = _split_values(entity.get("places") or entity.get("locations"))
        organizations = _split_values(entity.get("organizations") or entity.get("companies"))
        roles = _split_values(entity.get("roles"))
        identifiers = _split_values(entity.get("identifiers") or entity.get("domains") or entity.get("usernames"))
        dates = _split_values(entity.get("dates"))
        links = _split_values(entity.get("public_links") or entity.get("links"))
        domain_anchors = _dedupe([_domain(x) for x in links + identifiers if "." in str(x)])
        surname = display_name.split()[-1] if display_name.split() else display_name
        initials = "".join(part[0] for part in display_name.split() if part).upper()
        fingerprint = {
            "entity_id": entity_id,
            "entity_type": entity.get("entity_type", "person"),
            "display_name": display_name,
            "names": names,
            "surname": surname,
            "initials": initials,
            "places": places,
            "organizations": organizations,
            "roles": roles,
            "identifiers": identifiers,
            "dates": dates,
            "public_links": links,
            "domain_anchors": domain_anchors,
            "positive_terms": _tokens(names + places + organizations + roles + identifiers + dates),
            "strong_anchors": [v for v in [*places, *organizations, *roles, *identifiers, *dates] if v],
            "negative_terms": [],
            "sensitivity_notes": self._sensitivity_notes(entity),
        }
        fp_hash = _hash_text(dumps(fingerprint))
        row = self.db.one("SELECT fingerprint_id FROM search_quality_fingerprints_55_5 WHERE case_id=? AND entity_id=?", [case_id, entity_id])
        now = now_ts()
        if row:
            fid = row["fingerprint_id"]
            self.db.execute("UPDATE search_quality_fingerprints_55_5 SET display_name=?, fingerprint_hash=?, fingerprint_json=?, updated_at=? WHERE fingerprint_id=?", [display_name, fp_hash, dumps(fingerprint), now, fid])
        else:
            fid = new_id("fp55_5")
            self.db.execute("INSERT INTO search_quality_fingerprints_55_5(fingerprint_id,case_id,entity_id,display_name,fingerprint_hash,fingerprint_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", [fid, case_id, entity_id, display_name, fp_hash, dumps(fingerprint), now, now])
        self.audit.log("upsert", "search_quality_fingerprint_55_5", fid, case_id, {"entity_id": entity_id, "anchors": len(fingerprint["strong_anchors"])})
        return {"fingerprint_id": fid, "case_id": case_id, "entity_id": entity_id, "fingerprint_hash": fp_hash, "fingerprint": fingerprint}

    def get_fingerprint(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM search_quality_fingerprints_55_5 WHERE case_id=? AND entity_id=?", [case_id, entity_id])
        if not row:
            raise KeyError(f"No fingerprint for {case_id}/{entity_id}")
        row["fingerprint"] = loads(row.pop("fingerprint_json", "{}"), {})
        return row

    # ------------------------------------------------------------------
    # Query pyramid
    # ------------------------------------------------------------------
    def build_query_pyramid(self, case_id: str, entity: Dict[str, Any], category_key: str, *, persist: bool = True, create_chain_nodes: bool = True, max_per_level: int = 5) -> Dict[str, Any]:
        fp = self.build_entity_fingerprint(case_id, entity)["fingerprint"]
        category = self._category(category_key)
        queries = self._query_pyramid_for_category(fp, category_key)
        by_level: Dict[str, List[Dict[str, Any]]] = {lvl["key"]: [] for lvl in LEVELS}
        persisted: List[Dict[str, Any]] = []
        for q in queries:
            if len(by_level.get(q.level_key, [])) >= max_per_level:
                continue
            qd = {
                "category_key": q.category_key,
                "category_label": category["label"],
                "level_key": q.level_key,
                "level_label": next(l["label"] for l in LEVELS if l["key"] == q.level_key),
                "title": q.title,
                "query": q.query,
                "precision_bias": q.precision_bias,
                "recall_bias": q.recall_bias,
                "expected_evidence": q.expected_evidence,
                "review_required": q.review_required,
                "redaction_required": q.redaction_required,
            }
            if persist:
                qd.update(self._persist_quality_query(case_id, fp["entity_id"], qd))
            if create_chain_nodes and self.search_chain:
                qd["chain_parameter_node_id"] = self._ensure_chain_parameter(case_id, fp["entity_id"], qd)
                if qd.get("quality_query_id"):
                    self.db.execute("UPDATE search_quality_queries_55_5 SET chain_parameter_node_id=? WHERE quality_query_id=?", [qd["chain_parameter_node_id"], qd["quality_query_id"]])
            by_level[q.level_key].append(qd)
            persisted.append(qd)
        quality_profile = self._query_quality_profile(persisted)
        self.audit.log("create", "search_quality_query_pyramid_55_5", fp["entity_id"], case_id, {"category_key": category_key, "queries": len(persisted), "quality": quality_profile})
        return {"case_id": case_id, "entity_id": fp["entity_id"], "category": category, "levels": LEVELS, "by_level": by_level, "queries": persisted, "query_count": len(persisted), "quality_profile": quality_profile, "engines_per_query": len(TEN_SEARCH_ENGINES)}

    def get_engine_links_for_quality_query(self, quality_query_id: str) -> Dict[str, Any]:
        q = self.db.one("SELECT * FROM search_quality_queries_55_5 WHERE quality_query_id=?", [quality_query_id])
        if not q:
            raise KeyError(quality_query_id)
        image_mode = q["category_key"] == "person_images"
        links = []
        for e in TEN_SEARCH_ENGINES:
            links.append({"engine": e.key, "engine_label": e.label, "query": q["query"], "url": e.url(q["query"], image_mode=image_mode)})
        return {"quality_query_id": quality_query_id, "case_id": q["case_id"], "entity_id": q["entity_id"], "query": q["query"], "links": links, "count": len(links)}

    def list_quality_queries(self, case_id: str, entity_id: str = "", category_key: str = "") -> List[Dict[str, Any]]:
        sql = "SELECT * FROM search_quality_queries_55_5 WHERE case_id=?"
        params: List[Any] = [case_id]
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        if category_key:
            sql += " AND category_key=?"; params.append(category_key)
        sql += " ORDER BY precision_bias DESC, level_key, created_at"
        return self.db.all(sql, params)

    # ------------------------------------------------------------------
    # Result capture, normalization and ranking
    # ------------------------------------------------------------------
    def add_or_score_result(self, case_id: str, entity_id: str, *, title: str, url: str, snippet: str = "", quality_query_id: str = "", query: str = "", engine: str = "", source_type: str = "public_web", document_date: str = "", source_hit_node_id: str = "") -> Dict[str, Any]:
        if not title.strip() or not url.strip():
            raise ValueError("title and url are required")
        try:
            fp = self.get_fingerprint(case_id, entity_id)["fingerprint"]
        except KeyError:
            ent = self._entity_from_db(entity_id)
            fp = self.build_entity_fingerprint(case_id, ent)["fingerprint"]
        if quality_query_id and not query:
            qrow = self.db.one("SELECT query, category_key FROM search_quality_queries_55_5 WHERE quality_query_id=?", [quality_query_id])
            if qrow:
                query = qrow.get("query", "")
        canonical = _canonical_url(url)
        cluster = _hash_text(canonical)[:24]
        score = self.score_result(fp, title=title, url=url, snippet=snippet, source_type=source_type, query=query, document_date=document_date)
        existing = self.db.one("SELECT result_id FROM search_quality_results_55_5 WHERE case_id=? AND entity_id=? AND canonical_url=?", [case_id, entity_id, canonical])
        now = now_ts()
        if existing:
            rid = existing["result_id"]
            self.db.execute('''UPDATE search_quality_results_55_5 SET quality_query_id=?, query=?, engine=?, title=?, url=?, domain=?, snippet=?, source_type=?, document_date=?, source_hit_node_id=?, duplicate_cluster_id=?, entity_match_score=?, source_quality_score=?, sensitivity_score=?, total_score=?, ranking_label=?, flags_json=?, updated_at=? WHERE result_id=?''',
                            [quality_query_id, query, engine, title.strip(), url.strip(), _domain(url), snippet, source_type, document_date, source_hit_node_id, cluster, score["entity_match_score"], score["source_quality_score"], score["sensitivity_score"], score["total_score"], score["ranking_label"], dumps(score["flags"]), now, rid])
        else:
            rid = new_id("res55_5")
            self.db.execute('''INSERT INTO search_quality_results_55_5(result_id,case_id,entity_id,quality_query_id,query,engine,title,url,canonical_url,domain,snippet,source_type,document_date,source_hit_node_id,duplicate_cluster_id,entity_match_score,source_quality_score,sensitivity_score,total_score,ranking_label,flags_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            [rid, case_id, entity_id, quality_query_id, query, engine, title.strip(), url.strip(), canonical, _domain(url), snippet, source_type, document_date, source_hit_node_id, cluster, score["entity_match_score"], score["source_quality_score"], score["sensitivity_score"], score["total_score"], score["ranking_label"], dumps(score["flags"]), now, now])
        self.audit.log("upsert", "search_quality_result_55_5", rid, case_id, {"entity_id": entity_id, "score": score["total_score"], "label": score["ranking_label"]})
        return self.get_result(rid)

    def score_chain_findings(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        if not self.search_chain:
            return {"created": 0, "results": []}
        chain = self.search_chain.build_professional_chain(case_id, entity_id=entity_id)
        results = []
        for n in chain.get("nodes", []):
            if n.get("node_type") != "source_hit":
                continue
            meta = n.get("metadata") or {}
            res = self.add_or_score_result(
                case_id,
                n.get("entity_id") or entity_id,
                title=n.get("title", ""),
                url=n.get("source_url") or "https://example.invalid/manual-source/" + n.get("node_id", ""),
                snippet=n.get("value", ""),
                query=meta.get("query", ""),
                engine=meta.get("engine", ""),
                source_type=meta.get("source_category", "public_web"),
                document_date=meta.get("document_date", ""),
                source_hit_node_id=n.get("node_id", ""),
            )
            results.append(res)
        return {"case_id": case_id, "entity_id": entity_id, "created_or_updated": len(results), "results": results}

    def score_result(self, fingerprint: Dict[str, Any], *, title: str, url: str, snippet: str = "", source_type: str = "public_web", query: str = "", document_date: str = "") -> Dict[str, Any]:
        hay = f"{title} {snippet} {url}".lower()
        query_l = query.lower()
        name_score = 0
        matched_names = []
        for name in fingerprint.get("names", [])[:10]:
            n = name.lower()
            if n and n in hay:
                name_score = max(name_score, 38 if " " in n else 22)
                matched_names.append(name)
        anchor_score = 0
        matched_anchors = []
        for group, weight in [("organizations", 20), ("places", 13), ("roles", 12), ("dates", 8), ("identifiers", 14), ("domain_anchors", 15)]:
            for val in fingerprint.get(group, [])[:12]:
                v = str(val).lower()
                if v and v in hay:
                    anchor_score += weight
                    matched_anchors.append({"field": group, "value": val, "weight": weight})
                    break
        query_fit = 10 if any(str(name).lower() in query_l for name in fingerprint.get("names", [])[:5]) else 0
        source_quality = SOURCE_WEIGHTS.get(source_type, SOURCE_WEIGHTS["unknown"])
        if url.lower().endswith(".pdf") or "filetype:pdf" in query_l:
            source_quality += 6
        if document_date:
            source_quality += 3
        doppler_risk = self._doppler_risk(fingerprint, title=title, snippet=snippet, url=url, matched_names=matched_names, matched_anchors=matched_anchors)
        sensitivity = self._sensitivity_score(title, snippet, query, source_type)
        entity_match = max(0, min(100, name_score + min(anchor_score, 42) + query_fit - doppler_risk))
        total = max(0, min(100, entity_match + min(source_quality, 30) - max(0, sensitivity - 18)))
        flags = []
        if not matched_names:
            flags.append("name_not_in_snippet_or_title")
        if doppler_risk >= 25:
            flags.append("name_doppler_risk")
        if source_type in {"court_or_justice", "registry", "official_public_record"}:
            flags.append("high_value_source_type")
        if sensitivity >= 25:
            flags.append("sensitive_review_required")
        if anchor_score == 0:
            flags.append("missing_context_anchor")
        label = "top_candidate" if total >= 78 else "strong_candidate" if total >= 64 else "review_candidate" if total >= 45 else "weak_or_doppler_risk"
        return {
            "entity_match_score": entity_match,
            "source_quality_score": min(source_quality, 30),
            "sensitivity_score": sensitivity,
            "total_score": total,
            "ranking_label": label,
            "flags": flags,
            "matched_names": matched_names,
            "matched_anchors": matched_anchors,
            "doppler_risk": doppler_risk,
        }

    def get_result(self, result_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM search_quality_results_55_5 WHERE result_id=?", [result_id])
        if not row:
            raise KeyError(result_id)
        row["flags"] = loads(row.pop("flags_json", "[]"), [])
        return row

    def ranked_results(self, case_id: str, entity_id: str = "", limit: int = 25) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM search_quality_results_55_5 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY total_score DESC, source_quality_score DESC, updated_at DESC LIMIT ?"; params.append(limit)
        rows = self.db.all(sql, params)
        out = []
        for r in rows:
            r["flags"] = loads(r.pop("flags_json", "[]"), [])
            out.append(r)
        return out

    def duplicate_clusters(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        params: List[Any] = [case_id]
        sql = "SELECT duplicate_cluster_id, COUNT(*) AS count, MAX(total_score) AS best_score FROM search_quality_results_55_5 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " GROUP BY duplicate_cluster_id HAVING COUNT(*) > 1 ORDER BY count DESC, best_score DESC"
        clusters = self.db.all(sql, params)
        return {"case_id": case_id, "entity_id": entity_id, "cluster_count": len(clusters), "clusters": clusters}

    # ------------------------------------------------------------------
    # Feedback and benchmarks
    # ------------------------------------------------------------------
    def record_feedback(self, result_id: str, rating: str, note: str = "") -> Dict[str, Any]:
        rating = rating.strip().lower()
        if rating not in {"relevant", "useful", "top_hit", "false_positive", "name_doppler", "counter_evidence", "not_relevant"}:
            raise ValueError("Unsupported feedback rating")
        result = self.get_result(result_id)
        fid = new_id("fb55_5")
        self.db.execute("INSERT INTO search_quality_feedback_55_5(feedback_id,result_id,case_id,entity_id,rating,note,created_at) VALUES(?,?,?,?,?,?,?)", [fid, result_id, result["case_id"], result["entity_id"], rating, note, now_ts()])
        self.audit.log("create", "search_quality_feedback_55_5", fid, result["case_id"], {"result_id": result_id, "rating": rating})
        return {"feedback_id": fid, "result_id": result_id, "rating": rating}

    def compute_benchmark(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        results = self.ranked_results(case_id, entity_id=entity_id, limit=500)
        top10 = results[:10]
        feedback_rows = self._feedback_rows(case_id, entity_id)
        relevant_ids = {r["result_id"] for r in feedback_rows if r["rating"] in {"relevant", "useful", "top_hit"}}
        false_ids = {r["result_id"] for r in feedback_rows if r["rating"] in {"false_positive", "name_doppler", "not_relevant"}}
        precision_at_10 = (sum(1 for r in top10 if r["result_id"] in relevant_ids) / len(top10)) if top10 else 0.0
        duplicate_rate = self._duplicate_rate(results)
        false_positive_rate = (len(false_ids) / len(feedback_rows)) if feedback_rows else 0.0
        query_rows = self.list_quality_queries(case_id, entity_id=entity_id)
        used_query_ids = {r.get("quality_query_id") for r in results if r.get("quality_query_id")}
        useful_query_rate = (len(used_query_ids) / len(query_rows)) if query_rows else 0.0
        metrics = {
            "precision_at_10": round(precision_at_10, 3),
            "useful_query_rate": round(useful_query_rate, 3),
            "duplicate_rate": round(duplicate_rate, 3),
            "false_positive_rate": round(false_positive_rate, 3),
            "top_result_count": len(top10),
            "feedback_count": len(feedback_rows),
            "ranked_result_count": len(results),
            "top_labels": self._counts([r["ranking_label"] for r in results[:50]]),
        }
        bid = new_id("bench55_5")
        self.db.execute('''INSERT INTO search_quality_benchmarks_55_5(benchmark_id,case_id,entity_id,precision_at_10,useful_query_rate,duplicate_rate,false_positive_rate,top_result_count,feedback_count,metrics_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [bid, case_id, entity_id, metrics["precision_at_10"], metrics["useful_query_rate"], metrics["duplicate_rate"], metrics["false_positive_rate"], len(top10), len(feedback_rows), dumps(metrics), now_ts()])
        self.audit.log("create", "search_quality_benchmark_55_5", bid, case_id, metrics)
        return {"benchmark_id": bid, "case_id": case_id, "entity_id": entity_id, "metrics": metrics, "quality_target": "Precision@10 erhöhen, Doppler-Risiko senken, Query-Pyramiden per Feedback verbessern."}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        queries = self.list_quality_queries(case_id, entity_id=entity_id)
        results = self.ranked_results(case_id, entity_id=entity_id, limit=20)
        clusters = self.duplicate_clusters(case_id, entity_id=entity_id)
        feedback = self._feedback_rows(case_id, entity_id)
        return {
            "build": "55.5",
            "case_id": case_id,
            "entity_id": entity_id,
            "query_count": len(queries),
            "queries_by_level": self._counts([q["level_key"] for q in queries]),
            "queries_by_category": self._counts([q["category_key"] for q in queries]),
            "top_results": results,
            "duplicate_clusters": clusters,
            "feedback_counts": self._counts([f["rating"] for f in feedback]),
            "benchmark_hint": "Nutze Precision@10, Doppler-Feedback und Duplikat-Cluster als Qualitäts-KPIs.",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _query_pyramid_for_category(self, fp: Dict[str, Any], category_key: str) -> List[QualityQuery]:
        category = self._category(category_key)
        redaction = category_key in RISKY_CATEGORY_KEYS
        review = True
        qs: List[QualityQuery] = []
        names = fp.get("names") or [fp.get("display_name", "")]
        places = fp.get("places") or []
        orgs = fp.get("organizations") or []
        roles = fp.get("roles") or []
        dates = fp.get("dates") or []
        identifiers = fp.get("identifiers") or []
        primary = names[0]
        last = fp.get("surname") or primary

        def add(level: str, title: str, query: str, precision: int, recall: int, evidence: str, *, redact: bool = redaction):
            q = " ".join(str(query).split()).strip()
            if q:
                qs.append(QualityQuery(category_key, level, title, q, precision, recall, evidence, review, redact))

        # L1: strongest anchors first
        add("L1_identity_anchor", "Exakter Name", f'"{primary}"', 92, 35, "Name appears exactly in public result")
        for place in places[:3]:
            add("L1_identity_anchor", "Name + Ort", f'"{primary}" "{place}"', 97, 30, "Name and place in same result")
        for org in orgs[:3]:
            add("L1_identity_anchor", "Name + Organisation", f'"{primary}" "{org}"', 98, 28, "Name and known organization in same result")
        for role in roles[:2]:
            add("L1_identity_anchor", "Name + Rolle", f'"{primary}" "{role}"', 94, 28, "Name and known role in same result")

        # Category-specific L2/L3
        if category_key == "person_core":
            add("L2_context_expansion", "Name + Presse/Vita", f'"{primary}" (Presse OR Vita OR Lebenslauf OR Profil OR Interview)', 82, 62, "public profile or press context")
            add("L3_source_dorks", "Name + PDF", f'"{primary}" filetype:pdf', 86, 58, "PDF mention")
            add("L3_source_dorks", "Name im Titel", f'intitle:"{primary}"', 78, 50, "title match")
        elif category_key == "person_organization":
            for org in orgs[:4] or ["Organisation"]:
                add("L2_context_expansion", "Organisation + Rolle", f'"{primary}" "{org}" (Vorstand OR Team OR Ansprechpartner OR Mitarbeiter OR Projekt)', 90, 60, "role inside organization")
                add("L3_source_dorks", "Organisation PDF", f'"{primary}" "{org}" filetype:pdf', 92, 52, "organization document/PDF")
                add("L3_source_dorks", "Organisation amtlich", f'"{primary}" "{org}" (Satzung OR Amtsblatt OR Protokoll OR Geschäftsbericht)', 84, 48, "official/organizational record")
        elif category_key == "person_images":
            add("L2_context_expansion", "Bildkontext", f'"{primary}" (Foto OR Bild OR Pressefoto OR Galerie OR Veranstaltung)', 78, 62, "image/caption context", redact=True)
            add("L3_source_dorks", "Bild-Dateitypen", f'"{primary}" (filetype:jpg OR filetype:png OR filetype:webp)', 70, 54, "image file candidate", redact=True)
            add("L3_source_dorks", "Bildseiten", f'"{primary}" (site:commons.wikimedia.org OR site:flickr.com)', 68, 42, "known image hosts", redact=True)
        elif category_key == "person_public_personal_data":
            add("L2_context_expansion", "Lebensdaten", f'"{primary}" (geboren OR Geburtsdatum OR Geburtsort OR verstorben OR Nachruf)', 82, 55, "public life event data", redact=True)
            add("L3_source_dorks", "Register/Archiv", f'"{primary}" (Personenstandsregister OR Sterberegister OR Kirchenbuch OR Geburtsregister)', 74, 42, "archival/register candidate", redact=True)
            add("L3_source_dorks", "Kontakt/Impressum", f'"{primary}" (Kontakt OR Impressum OR E-Mail OR Email) filetype:pdf', 70, 48, "public functional contact", redact=True)
        elif category_key == "person_legal_proceedings":
            add("L2_context_expansion", "Verfahren/Urteil", f'"{primary}" (Urteil OR Beschluss OR Aktenzeichen OR Gericht OR Prozess)', 84, 58, "legal/procedural mention", redact=True)
            add("L3_source_dorks", "Justiz-Dokument", f'"{primary}" (Urteil OR Beschluss OR Aktenzeichen) filetype:pdf', 88, 50, "court PDF candidate", redact=True)
            add("L3_source_dorks", "Amtliche Justizquellen", f'"{primary}" (site:justiz.de OR site:gerichte.* OR site:bund.de OR site:land.de) (Urteil OR Beschluss OR Aktenzeichen)', 80, 42, "official justice domain", redact=True)
        elif category_key == "person_networks_company_networks":
            add("L2_context_expansion", "Netzwerk/Rollen", f'"{primary}" (Vorstand OR Geschäftsführer OR Beirat OR Kuratorium OR Netzwerk OR Partner)', 86, 60, "network/role context")
            add("L3_source_dorks", "Register/Impressum", f'"{primary}" (Handelsregister OR Vereinsregister OR Unternehmensregister OR Impressum)', 84, 50, "public registry/imprint context")
            for identifier in identifiers[:3]:
                add("L3_source_dorks", "Identifier/Domain", f'"{primary}" "{identifier}"', 82, 38, "known identifier/domain with name")
        elif category_key == "person_public_financial_data":
            add("L2_context_expansion", "Finanz-/Berichtskontext", f'"{primary}" (Jahresabschluss OR Geschäftsbericht OR Bundesanzeiger OR Unternehmensregister OR Förderung OR Zuwendung)', 72, 50, "public financial/org record", redact=True)
            for org in orgs[:3]:
                add("L3_source_dorks", "Organisation + Finanzkontext", f'"{primary}" "{org}" (Jahresabschluss OR Geschäftsbericht OR Förderung OR Vergabe OR Bundesanzeiger)', 84, 42, "organization-linked financial record", redact=True)
            add("L3_source_dorks", "Insolvenz öffentlich", f'"{primary}" (Insolvenz OR Insolvenzbekanntmachung OR Restrukturierung) -Kredit -Schufa', 60, 40, "public insolvency candidate only", redact=True)

        # L4: countercheck / Doppler. Use weaker precision but high analytical value.
        add("L4_countercheck_doppler", "Namensdoppler ohne bekannte Orte", f'"{primary}" -' + " -".join(f'"{p}"' for p in places[:3]), 55, 70, "other people with same name / location mismatch", redact=False)
        if last and last != primary:
            add("L4_countercheck_doppler", "Nachname + Initiale", f'"{last}" "{fp.get("initials", "")[:1]}"', 48, 60, "possible name variant or doppler", redact=False)
        for place in places[:2]:
            add("L4_countercheck_doppler", "Name + anderer Kontext prüfen", f'"{primary}" "{place}" (nicht OR anderer OR unrelated OR "nicht identisch")', 42, 40, "counter-evidence wording", redact=False)

        # Dedupe and sort by pyramid order/precision.
        seen = set(); out: List[QualityQuery] = []
        level_order = {lvl["key"]: i for i, lvl in enumerate(LEVELS)}
        for q in sorted(qs, key=lambda x: (level_order.get(x.level_key, 99), -x.precision_bias, x.query)):
            key = q.query.lower()
            if key in seen:
                continue
            seen.add(key); out.append(q)
        return out

    def _persist_quality_query(self, case_id: str, entity_id: str, q: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.db.one("SELECT quality_query_id FROM search_quality_queries_55_5 WHERE case_id=? AND entity_id=? AND category_key=? AND level_key=? AND query=?", [case_id, entity_id, q["category_key"], q["level_key"], q["query"]])
        if existing:
            return {"quality_query_id": existing["quality_query_id"]}
        qid = new_id("qq55_5")
        self.db.execute('''INSERT INTO search_quality_queries_55_5(quality_query_id,case_id,entity_id,category_key,level_key,title,query,precision_bias,recall_bias,expected_evidence,review_required,redaction_required,created_at,status)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [qid, case_id, entity_id, q["category_key"], q["level_key"], q["title"], q["query"], q["precision_bias"], q["recall_bias"], q["expected_evidence"], int(q["review_required"]), int(q["redaction_required"]), now_ts(), "planned"])
        return {"quality_query_id": qid}

    def _ensure_chain_parameter(self, case_id: str, entity_id: str, q: Dict[str, Any]) -> str:
        if not self.search_chain:
            return ""
        existing = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND node_type='search_parameter' AND value=? AND metadata_json LIKE '%55.5%'", [case_id, entity_id, q["query"]])
        if existing:
            return existing["node_id"]
        root = self.db.one("SELECT node_id FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? AND node_type='seed_info' AND parent_node_id='' ORDER BY created_at LIMIT 1", [case_id, entity_id])
        parent = root["node_id"] if root else ""
        node = self.search_chain.add_node(
            case_id,
            "search_parameter",
            f"{q['level_label']}: {q['title']}",
            q["query"],
            entity_id=entity_id,
            parent_node_id=parent,
            relation_type="generated_quality_pyramid_parameter",
            relevance_score=int(q["precision_bias"]),
            confidence_label="quality_pyramid_parameter",
            metadata={"build": "55.5", "category_key": q["category_key"], "category_label": q["category_label"], "level_key": q["level_key"], "level_label": q["level_label"], "expected_evidence": q["expected_evidence"], "review_required": q["review_required"], "redaction_required": q["redaction_required"]},
            status="planned",
        )
        return node["node_id"]

    def _category(self, key: str) -> Dict[str, Any]:
        for c in SEARCH_CATEGORIES_55_1:
            if c["key"] == key:
                return dict(c)
        raise ValueError("Unknown search category: " + str(key))

    def _query_quality_profile(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not queries:
            return {"precision_avg": 0, "review_required": 0, "redaction_required": 0, "levels": {}}
        return {
            "precision_avg": round(sum(int(q["precision_bias"]) for q in queries) / len(queries), 1),
            "review_required": sum(1 for q in queries if q.get("review_required")),
            "redaction_required": sum(1 for q in queries if q.get("redaction_required")),
            "levels": self._counts([q["level_key"] for q in queries]),
        }

    def _sensitivity_notes(self, entity: Dict[str, Any]) -> List[str]:
        notes = []
        blob = " ".join([str(entity.get(k, "")) for k in ["display_name", "name", "notes", "dates", "places"]]).lower()
        if any(x in blob for x in ["kind", "minor", "minderjähr", "schüler"]):
            notes.append("minor_or_school_context_review_required")
        if any(x in blob for x in ["opfer", "zeuge", "victim", "witness"]):
            notes.append("victim_or_witness_context_review_required")
        return notes

    def _entity_from_db(self, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE entity_id=?", [entity_id])
        if not row:
            raise KeyError(entity_id)
        for col in ["known_names_json", "aliases_json", "dates_json", "places_json", "organizations_json", "roles_json", "identifiers_json", "public_links_json"]:
            row[col.replace("_json", "")] = loads(row.pop(col, "[]"), [])
        return row

    def _doppler_risk(self, fp: Dict[str, Any], *, title: str, snippet: str, url: str, matched_names: List[str], matched_anchors: List[Dict[str, Any]]) -> int:
        if not matched_names:
            return 35
        risk = 0
        if len(matched_anchors) == 0:
            risk += 28
        if fp.get("surname") and fp.get("surname", "").lower() in (title + snippet).lower() and len(matched_names) == 1 and " " not in matched_names[0]:
            risk += 20
        # Different city hints are not a hard contradiction; they trigger review.
        known_places = [p.lower() for p in fp.get("places", [])]
        other_city_markers = ["hamburg", "münchen", "munich", "frankfurt", "köln", "cologne", "berlin", "leipzig", "dresden"]
        hay = f"{title} {snippet} {url}".lower()
        if known_places and any(city in hay and all(city not in p for p in known_places) for city in other_city_markers):
            risk += 15
        return min(risk, 45)

    def _sensitivity_score(self, title: str, snippet: str, query: str, source_type: str) -> int:
        blob = f"{title} {snippet} {query} {source_type}".lower()
        score = 0
        for term in ["adresse", "anschrift", "geburtsdatum", "geburtsort", "sterbedatum", "telefon", "e-mail", "email"]:
            if term in blob:
                score += 8
        for term in ["urteil", "prozess", "anklage", "staatsanwaltschaft", "insolvenz", "finanz", "jahresabschluss"]:
            if term in blob:
                score += 7
        return min(score, 45)

    def _feedback_rows(self, case_id: str, entity_id: str = "") -> List[Dict[str, Any]]:
        sql = "SELECT * FROM search_quality_feedback_55_5 WHERE case_id=?"
        params: List[Any] = [case_id]
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        return self.db.all(sql, params)

    def _duplicate_rate(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.0
        clusters: Dict[str, int] = {}
        for r in results:
            clusters[r["duplicate_cluster_id"]] = clusters.get(r["duplicate_cluster_id"], 0) + 1
        duplicate_items = sum(count - 1 for count in clusters.values() if count > 1)
        return duplicate_items / len(results)

    def _counts(self, values: Iterable[str]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for v in values:
            out[str(v)] = out.get(str(v), 0) + 1
        return out
