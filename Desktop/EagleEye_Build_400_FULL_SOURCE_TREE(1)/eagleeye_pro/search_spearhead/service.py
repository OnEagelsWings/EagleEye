from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.categorized_search.service import SEARCH_CATEGORIES_55_1, TEN_SEARCH_ENGINES


STAGES_58_1 = [
    {"key": "identity_lock", "label": "Identitätsanker", "goal": "Name + stärkste Kontextanker zuerst prüfen"},
    {"key": "precision_source", "label": "Quellenpräzision", "goal": "hochwertige Quellenklassen gezielt abfragen"},
    {"key": "context_expansion", "label": "Kontexterweiterung", "goal": "Organisationen, Orte, Rollen, Daten kontrolliert erweitern"},
    {"key": "counter_doppler", "label": "Gegenprüfung/Namensdoppler", "goal": "falsche Personen, Widersprüche und Gegenbelege finden"},
    {"key": "adaptive_followup", "label": "Adaptive Folgequeries", "goal": "aus echten Funden neue Suchrichtungen ableiten"},
]

HIGH_VALUE_DOMAINS = {
    "bund.de": 18, "justiz.de": 22, "gerichte": 20, "registerportal": 20,
    "unternehmensregister": 20, "bundesanzeiger": 20, "deutsche-digitale-bibliothek": 16,
    "archive.org": 12, "wikipedia.org": 6,
}

ROLE_TERMS = [
    "Vorstand", "Geschäftsführer", "Geschäftsführerin", "Gesellschafter", "Beirat", "Kuratorium",
    "Schatzmeister", "Pressesprecher", "Ansprechpartner", "Inhaber", "Founder", "CEO", "CFO",
]

SOURCE_HINTS = [
    ("gericht", "court_or_justice"), ("justiz", "court_or_justice"), ("urteil", "court_or_justice"),
    ("register", "registry"), ("handelsregister", "registry"), ("unternehmensregister", "registry"),
    ("bundesanzeiger", "registry"), ("amtsblatt", "official_public_record"),
    ("pdf", "public_pdf"), ("zeitung", "newspaper_press"), ("presse", "newspaper_press"),
    ("foto", "image_media"), ("bild", "image_media"), ("archiv", "archival_source"),
]

SENSITIVE_TERMS = {
    "adresse", "anschrift", "telefon", "email", "e-mail", "geburtsdatum", "geburtsort", "sterbedatum",
    "urteil", "anklage", "insolvenz", "finanz", "minderjähr", "kind", "opfer", "zeuge",
}


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        s = re.sub(r"\s+", " ", str(value or "")).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key); out.append(s)
    return out


def _split(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return _dedupe([str(v) for v in value])
    return _dedupe(str(value).replace(";", ",").split(","))


def _domain(url: str) -> str:
    try:
        return urlparse(url.strip()).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _canonical(url: str) -> str:
    try:
        p = urlparse(url.strip())
        return f"{(p.scheme or 'https').lower()}://{p.netloc.lower().replace('www.', '')}{p.path.rstrip('/') or '/'}"
    except Exception:
        return url.strip()


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _category(key: str) -> Dict[str, Any]:
    for c in SEARCH_CATEGORIES_55_1:
        if c["key"] == key:
            return dict(c)
    raise ValueError("Unknown category: " + str(key))


@dataclass(frozen=True)
class MissionQuery:
    stage: str
    category_key: str
    query: str
    intent: str
    priority: int
    precision_weight: int
    recall_weight: int
    pii_risk: str = "normal"
    source_focus: str = "public_web"


class SearchSpearheadEngineService:
    """Build 58.1 professional search machinery layer.

    It does not bypass logins, paywalls, CAPTCHAs or restricted systems. The
    purpose is search quality: mission planning, query selection, SERP paste
    import, candidate ranking, adaptive follow-up and measurable learning.
    """

    def __init__(self, db: Database, audit: AuditService, search_quality=None, result_capture=None, entity_resolution=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.result_capture = result_capture
        self.entity_resolution = entity_resolution
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS spearhead_search_missions_58_1 (
          mission_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          objective TEXT NOT NULL,
          mode TEXT DEFAULT 'precision_first',
          search_budget_json TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_spear581_mission_entity ON spearhead_search_missions_58_1(case_id, entity_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS spearhead_query_candidates_58_1 (
          candidate_id TEXT PRIMARY KEY,
          mission_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          stage TEXT NOT NULL,
          query TEXT NOT NULL,
          intent TEXT NOT NULL,
          priority INTEGER DEFAULT 50,
          precision_weight INTEGER DEFAULT 50,
          recall_weight INTEGER DEFAULT 50,
          pii_risk TEXT DEFAULT 'normal',
          source_focus TEXT DEFAULT 'public_web',
          engine_plan_json TEXT NOT NULL,
          status TEXT DEFAULT 'planned',
          quality_query_id TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          UNIQUE(mission_id, query, stage)
        );
        CREATE INDEX IF NOT EXISTS idx_spear581_query_priority ON spearhead_query_candidates_58_1(mission_id, priority DESC);

        CREATE TABLE IF NOT EXISTS spearhead_serp_imports_58_1 (
          serp_import_id TEXT PRIMARY KEY,
          mission_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          engine TEXT DEFAULT '',
          query TEXT DEFAULT '',
          parsed_count INTEGER DEFAULT 0,
          raw_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS spearhead_result_candidates_58_1 (
          result_candidate_id TEXT PRIMARY KEY,
          mission_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          candidate_id TEXT DEFAULT '',
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          source_type TEXT DEFAULT 'public_web',
          source_weight INTEGER DEFAULT 0,
          identity_fit INTEGER DEFAULT 0,
          doppler_risk INTEGER DEFAULT 0,
          sensitivity_score INTEGER DEFAULT 0,
          total_score INTEGER DEFAULT 0,
          ranking_label TEXT DEFAULT 'candidate',
          duplicate_group TEXT DEFAULT '',
          flags_json TEXT NOT NULL,
          recommended_actions_json TEXT NOT NULL,
          quality_result_id TEXT DEFAULT '',
          import_id TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(mission_id, canonical_url)
        );
        CREATE INDEX IF NOT EXISTS idx_spear581_results_rank ON spearhead_result_candidates_58_1(mission_id, total_score DESC);

        CREATE TABLE IF NOT EXISTS spearhead_learning_events_58_1 (
          learning_event_id TEXT PRIMARY KEY,
          mission_id TEXT NOT NULL,
          result_candidate_id TEXT DEFAULT '',
          rating TEXT NOT NULL,
          note TEXT DEFAULT '',
          learned_terms_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    # ------------------------------------------------------------------
    # Mission and query planning
    # ------------------------------------------------------------------
    def create_search_mission(self, case_id: str, entity: Dict[str, Any], category_key: str, *, objective: str = "high_precision_public_osint", max_queries: int = 28, max_engines_per_query: int = 10, mode: str = "precision_first") -> Dict[str, Any]:
        if not case_id:
            raise ValueError("case_id is required")
        entity_id = entity.get("entity_id") or entity.get("target_id") or ""
        if not entity_id:
            raise ValueError("entity_id is required")
        _category(category_key)
        fp = self._fingerprint(case_id, entity)
        mission_id = new_id("spear581")
        budget = {"max_queries": int(max_queries), "max_engines_per_query": int(max_engines_per_query), "max_tabs_per_action": min(10, int(max_engines_per_query)), "mode": mode, "public_only": True, "no_bypass": True}
        now = now_ts()
        self.db.execute('''INSERT INTO spearhead_search_missions_58_1(mission_id,case_id,entity_id,category_key,objective,mode,search_budget_json,metrics_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [mission_id, case_id, entity_id, category_key, objective, mode, dumps(budget), dumps({}), now, now])
        queries = self._mission_queries(fp, category_key)
        if mode == "recall_then_precision":
            queries.sort(key=lambda q: (-q.recall_weight, -q.priority, q.query))
        else:
            queries.sort(key=lambda q: (-q.priority, -q.precision_weight, q.query))
        created = []
        for q in queries[:max_queries]:
            created.append(self._insert_query_candidate(mission_id, case_id, entity_id, q, max_engines_per_query=max_engines_per_query))
        metrics = self._mission_metrics(mission_id)
        self.db.execute("UPDATE spearhead_search_missions_58_1 SET metrics_json=?, updated_at=? WHERE mission_id=?", [dumps(metrics), now_ts(), mission_id])
        self.audit.log("create", "spearhead_search_mission_58_1", mission_id, case_id, {"entity_id": entity_id, "category_key": category_key, "query_count": len(created)})
        return self.get_mission(mission_id)

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM spearhead_search_missions_58_1 WHERE mission_id=?", [mission_id])
        if not row:
            raise KeyError(mission_id)
        row["search_budget"] = loads(row.pop("search_budget_json", "{}"), {})
        row["metrics"] = loads(row.pop("metrics_json", "{}"), {})
        row["category"] = _category(row["category_key"])
        return row

    def list_missions(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM spearhead_search_missions_58_1 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["search_budget"] = loads(r.pop("search_budget_json", "{}"), {})
            r["metrics"] = loads(r.pop("metrics_json", "{}"), {})
        return rows

    def top_query_candidates(self, mission_id: str, limit: int = 10, stage: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = [mission_id]
        sql = "SELECT * FROM spearhead_query_candidates_58_1 WHERE mission_id=?"
        if stage:
            sql += " AND stage=?"; params.append(stage)
        sql += " ORDER BY priority DESC, precision_weight DESC, created_at LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["engine_plan"] = loads(r.pop("engine_plan_json", "[]"), [])
        return rows

    def engine_links_for_candidate(self, candidate_id: str, max_engines: int = 10) -> Dict[str, Any]:
        cand = self.db.one("SELECT * FROM spearhead_query_candidates_58_1 WHERE candidate_id=?", [candidate_id])
        if not cand:
            raise KeyError(candidate_id)
        engine_plan = loads(cand.pop("engine_plan_json", "[]"), [])[:max_engines]
        image_mode = cand["category_key"] == "person_images"
        links = []
        for ep in engine_plan:
            eng = next((e for e in TEN_SEARCH_ENGINES if e.key == ep.get("engine")), None)
            if not eng:
                continue
            links.append({"engine": eng.key, "engine_label": eng.label, "role": ep.get("role", "general"), "query": cand["query"], "url": eng.url(cand["query"], image_mode=image_mode)})
        self.db.execute("UPDATE spearhead_query_candidates_58_1 SET status='opened' WHERE candidate_id=?", [candidate_id])
        return {"candidate_id": candidate_id, "mission_id": cand["mission_id"], "query": cand["query"], "links": links, "count": len(links)}

    def preflight_opening_plan(self, mission_id: str, limit: int = 3, max_engines_per_query: int = 10) -> Dict[str, Any]:
        queries = self.top_query_candidates(mission_id, limit=limit)
        estimated_tabs = sum(min(max_engines_per_query, len(q.get("engine_plan", []))) for q in queries)
        warnings = []
        if estimated_tabs > 30:
            warnings.append("tab_budget_high_reduce_limit")
        if any(q.get("pii_risk") in {"high", "authority_sensitive", "financial_review"} for q in queries):
            warnings.append("sensitive_category_review_required")
        return {"mission_id": mission_id, "query_count": len(queries), "estimated_tabs": estimated_tabs, "warnings": warnings, "queries": queries}

    # ------------------------------------------------------------------
    # SERP import and ranking
    # ------------------------------------------------------------------
    def parse_serp_text(self, raw_text: str) -> List[Dict[str, str]]:
        lines = [re.sub(r"\s+", " ", line).strip() for line in (raw_text or "").splitlines()]
        lines = [line for line in lines if line]
        out: List[Dict[str, str]] = []
        url_re = re.compile(r"https?://[^\s)\]]+", re.I)
        for idx, line in enumerate(lines):
            m = url_re.search(line)
            if not m:
                continue
            url = m.group(0).rstrip(".,;)")
            prev = lines[idx - 1] if idx > 0 and not url_re.search(lines[idx - 1]) else ""
            nxt = lines[idx + 1] if idx + 1 < len(lines) and not url_re.search(lines[idx + 1]) else ""
            title = prev or _domain(url) or "Suchtreffer"
            snippet = nxt if nxt and nxt != title else ""
            out.append({"title": title[:240], "url": url, "snippet": snippet[:800]})
        # common fallback: blocks where URL is first line, title next line
        return self._dedupe_results(out)

    def import_serp_text(self, mission_id: str, raw_text: str, *, engine: str = "", candidate_id: str = "") -> Dict[str, Any]:
        mission = self.get_mission(mission_id)
        candidate = self._candidate(candidate_id) if candidate_id else None
        query = candidate.get("query", "") if candidate else ""
        parsed = self.parse_serp_text(raw_text)
        sid = new_id("serp581")
        self.db.execute('''INSERT INTO spearhead_serp_imports_58_1(serp_import_id,mission_id,case_id,entity_id,engine,query,parsed_count,raw_hash,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', [sid, mission_id, mission["case_id"], mission["entity_id"], engine, query, len(parsed), _sha(raw_text)[:32], now_ts()])
        results = []
        for item in parsed:
            results.append(self.add_result_candidate(mission_id, title=item["title"], url=item["url"], snippet=item.get("snippet", ""), candidate_id=candidate_id, engine=engine, query=query))
        self._refresh_mission_metrics(mission_id)
        self.audit.log("import", "spearhead_serp_text_58_1", sid, mission["case_id"], {"mission_id": mission_id, "parsed": len(parsed)})
        return {"serp_import_id": sid, "mission_id": mission_id, "parsed_count": len(parsed), "results": results}

    def add_result_candidate(self, mission_id: str, *, title: str, url: str, snippet: str = "", candidate_id: str = "", engine: str = "", query: str = "") -> Dict[str, Any]:
        mission = self.get_mission(mission_id)
        fp = self._fingerprint(mission["case_id"], self._entity_from_db(mission["entity_id"]))
        can = _canonical(url)
        source_type = self._source_type(title, url, snippet)
        score = self._score_result(fp, title=title, url=url, snippet=snippet, source_type=source_type, query=query)
        duplicate_group = _sha(can)[:24]
        now = now_ts()
        existing = self.db.one("SELECT result_candidate_id FROM spearhead_result_candidates_58_1 WHERE mission_id=? AND canonical_url=?", [mission_id, can])
        if existing:
            rid = existing["result_candidate_id"]
            self.db.execute('''UPDATE spearhead_result_candidates_58_1 SET title=?, snippet=?, engine=?, query=?, source_type=?, source_weight=?, identity_fit=?, doppler_risk=?, sensitivity_score=?, total_score=?, ranking_label=?, flags_json=?, recommended_actions_json=?, updated_at=? WHERE result_candidate_id=?''',
                [title, snippet, engine, query, source_type, score["source_weight"], score["identity_fit"], score["doppler_risk"], score["sensitivity_score"], score["total_score"], score["ranking_label"], dumps(score["flags"]), dumps(score["recommended_actions"]), now, rid])
        else:
            rid = new_id("sr581")
            self.db.execute('''INSERT INTO spearhead_result_candidates_58_1(result_candidate_id,mission_id,case_id,entity_id,candidate_id,title,url,canonical_url,domain,snippet,query,engine,source_type,source_weight,identity_fit,doppler_risk,sensitivity_score,total_score,ranking_label,duplicate_group,flags_json,recommended_actions_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                [rid, mission_id, mission["case_id"], mission["entity_id"], candidate_id, title, url, can, _domain(url), snippet, query, engine, source_type, score["source_weight"], score["identity_fit"], score["doppler_risk"], score["sensitivity_score"], score["total_score"], score["ranking_label"], duplicate_group, dumps(score["flags"]), dumps(score["recommended_actions"]), now, now])
        # Also push to existing Search Quality + Person Detail pipeline when available.
        quality_result_id = ""; import_id = ""
        if self.result_capture:
            try:
                imported = self.result_capture.import_public_result(mission["case_id"], mission["entity_id"], url=url, title=title, snippet=snippet, category_key=mission["category_key"], query=query, engine=engine, source_type=source_type)
                quality_result_id = imported.get("quality_result_id", ""); import_id = imported.get("import_id", "")
                self.db.execute("UPDATE spearhead_result_candidates_58_1 SET quality_result_id=?, import_id=? WHERE result_candidate_id=?", [quality_result_id, import_id, rid])
            except Exception:
                pass
        self._refresh_mission_metrics(mission_id)
        return self.get_result_candidate(rid)

    def get_result_candidate(self, result_candidate_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM spearhead_result_candidates_58_1 WHERE result_candidate_id=?", [result_candidate_id])
        if not row:
            raise KeyError(result_candidate_id)
        row["flags"] = loads(row.pop("flags_json", "[]"), [])
        row["recommended_actions"] = loads(row.pop("recommended_actions_json", "[]"), [])
        return row

    def ranked_candidates(self, mission_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM spearhead_result_candidates_58_1 WHERE mission_id=? ORDER BY total_score DESC, source_weight DESC, updated_at DESC LIMIT ?", [mission_id, int(limit)])
        out = []
        for r in rows:
            r["flags"] = loads(r.pop("flags_json", "[]"), [])
            r["recommended_actions"] = loads(r.pop("recommended_actions_json", "[]"), [])
            out.append(r)
        return out

    # ------------------------------------------------------------------
    # Adaptive learning and follow-up queries
    # ------------------------------------------------------------------
    def recommend_next_queries(self, mission_id: str, limit: int = 10, persist: bool = True) -> Dict[str, Any]:
        mission = self.get_mission(mission_id)
        fp = self._fingerprint(mission["case_id"], self._entity_from_db(mission["entity_id"]))
        top = self.ranked_candidates(mission_id, limit=30)
        anchors = self._extract_anchors(top)
        base_name = fp["display_name"]
        qtexts: List[MissionQuery] = []
        for org in anchors.get("organizations", [])[:5]:
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" "{org}"', "Fundanker Organisation weiterprüfen", 91, 88, 45, source_focus="organization_site"))
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" "{org}" filetype:pdf', "Organisation + PDF gegenprüfen", 88, 84, 42, source_focus="public_pdf"))
        for domain in anchors.get("domains", [])[:4]:
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" site:{domain}', "Domain-spezifische Anschlussrecherche", 86, 82, 40, source_focus="public_web"))
        for year in anchors.get("years", [])[:4]:
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" "{year}"', "Zeitanker Anschlussrecherche", 78, 70, 50))
        for role in anchors.get("roles", [])[:5]:
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" "{role}"', "Rollenanker Anschlussrecherche", 84, 80, 46))
        # If all obvious follow-ups already exist in the original mission, add
        # second-order combinations. This keeps the loop productive without
        # widening into blind mass-search.
        if not qtexts and top:
            qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'"{base_name}" filetype:pdf', "Fallback: PDF-Anschlussrecherche", 76, 70, 48, source_focus="public_pdf"))
        for domain in anchors.get("domains", [])[:3]:
            for role in anchors.get("roles", [])[:3] or [""]:
                tail = f' "{role}"' if role else ""
                qtexts.append(MissionQuery("adaptive_followup", mission["category_key"], f'site:{domain} "{base_name}"{tail}', "Domain + Rollenanker kombinieren", 87, 84, 35, source_focus="public_web"))
        existing_rows = {r["query"].lower(): r for r in self.top_query_candidates(mission_id, limit=500)}
        created = []
        recommended = []
        for q in _dedupe([qq.query for qq in qtexts])[:limit * 3]:
            mq = next(qq for qq in qtexts if qq.query == q)
            if q.lower() in existing_rows:
                item = dict(existing_rows[q.lower()])
                item["already_existing"] = True
                recommended.append(item)
            else:
                item = self._insert_query_candidate(mission_id, mission["case_id"], mission["entity_id"], mq, max_engines_per_query=mission["search_budget"].get("max_engines_per_query", 10)) if persist else mq.__dict__
                item["already_existing"] = False
                created.append(item); recommended.append(item)
            if len(recommended) >= limit:
                break
        self._refresh_mission_metrics(mission_id)
        return {"mission_id": mission_id, "anchors": anchors, "recommended_count": len(recommended), "created_count": len(created), "queries": recommended}

    def record_learning_feedback(self, result_candidate_id: str, rating: str, note: str = "") -> Dict[str, Any]:
        rating = rating.strip().lower()
        if rating not in {"top_hit", "relevant", "useful", "not_relevant", "false_positive", "name_doppler", "counter_evidence"}:
            raise ValueError("Unsupported rating")
        result = self.get_result_candidate(result_candidate_id)
        terms = self._learned_terms_from_result(result, rating)
        eid = new_id("learn581")
        self.db.execute("INSERT INTO spearhead_learning_events_58_1(learning_event_id,mission_id,result_candidate_id,rating,note,learned_terms_json,created_at) VALUES(?,?,?,?,?,?,?)", [eid, result["mission_id"], result_candidate_id, rating, note, dumps(terms), now_ts()])
        if self.search_quality and result.get("quality_result_id"):
            try:
                self.search_quality.record_feedback(result["quality_result_id"], "name_doppler" if rating == "name_doppler" else rating, note=note)
            except Exception:
                pass
        self._refresh_mission_metrics(result["mission_id"])
        self.audit.log("feedback", "spearhead_learning_58_1", eid, result["case_id"], {"rating": rating, "result_candidate_id": result_candidate_id})
        return {"learning_event_id": eid, "rating": rating, "learned_terms": terms}

    # ------------------------------------------------------------------
    # Dashboards and full cycle
    # ------------------------------------------------------------------
    def dashboard(self, mission_id: str) -> Dict[str, Any]:
        mission = self.get_mission(mission_id)
        queries = self.top_query_candidates(mission_id, limit=500)
        results = self.ranked_candidates(mission_id, limit=50)
        feedback = self.db.all("SELECT * FROM spearhead_learning_events_58_1 WHERE mission_id=? ORDER BY created_at DESC", [mission_id])
        metrics = self._mission_metrics(mission_id)
        return {
            "build": "58.1",
            "mission": mission,
            "query_count": len(queries),
            "queries_by_stage": self._counts([q["stage"] for q in queries]),
            "top_queries": queries[:10],
            "result_count": len(results),
            "top_results": results[:15],
            "feedback_counts": self._counts([f["rating"] for f in feedback]),
            "metrics": metrics,
            "professional_readiness": self.professional_readiness_score(mission_id),
        }

    def professional_readiness_score(self, mission_id: str) -> Dict[str, Any]:
        queries = self.top_query_candidates(mission_id, limit=500)
        results = self.ranked_candidates(mission_id, limit=500)
        feedback = self.db.all("SELECT * FROM spearhead_learning_events_58_1 WHERE mission_id=?", [mission_id])
        top = results[:10]
        stage_coverage = len(set(q["stage"] for q in queries)) / len(STAGES_58_1) if STAGES_58_1 else 0
        result_depth = min(1.0, len(results) / 20)
        ranked_quality = (sum(1 for r in top if r["total_score"] >= 70) / len(top)) if top else 0
        feedback_depth = min(1.0, len(feedback) / 10)
        doppler_control = 1.0 - ((sum(1 for r in top if r["doppler_risk"] >= 30) / len(top)) if top else 0.3)
        score = round(100 * (0.25 * stage_coverage + 0.25 * result_depth + 0.25 * ranked_quality + 0.15 * feedback_depth + 0.10 * doppler_control), 1)
        gaps = []
        if stage_coverage < 0.8: gaps.append("nicht alle Research-Stufen abgedeckt")
        if result_depth < 0.8: gaps.append("zu wenige importierte Treffer für belastbare Bewertung")
        if ranked_quality < 0.5: gaps.append("zu wenige Top-Treffer mit hoher Bewertung")
        if feedback_depth < 0.5: gaps.append("zu wenig Analystenfeedback für Lernschleife")
        return {"score": score, "stage_coverage": round(stage_coverage, 2), "result_depth": round(result_depth, 2), "ranked_quality": round(ranked_quality, 2), "feedback_depth": round(feedback_depth, 2), "doppler_control": round(doppler_control, 2), "gaps": gaps}

    def run_spearhead_cycle(self, case_id: str, entity: Dict[str, Any], category_key: str, *, serp_text: str = "", engine: str = "", objective: str = "high_precision_public_osint") -> Dict[str, Any]:
        mission = self.create_search_mission(case_id, entity, category_key, objective=objective)
        parsed = {"parsed_count": 0, "results": []}
        if serp_text.strip():
            first = self.top_query_candidates(mission["mission_id"], limit=1)
            parsed = self.import_serp_text(mission["mission_id"], serp_text, engine=engine, candidate_id=first[0]["candidate_id"] if first else "")
        followup = self.recommend_next_queries(mission["mission_id"], limit=8) if parsed.get("parsed_count") else {"recommended_count": 0, "queries": []}
        dash = self.dashboard(mission["mission_id"])
        return {"mission_id": mission["mission_id"], "mission": mission, "import": parsed, "followup": followup, "dashboard": dash}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fingerprint(self, case_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
        if self.search_quality:
            return self.search_quality.build_entity_fingerprint(case_id, entity).get("fingerprint", {})
        name = entity.get("display_name") or entity.get("name") or ""
        return {"entity_id": entity.get("entity_id", ""), "display_name": name, "names": [name], "places": _split(entity.get("places")), "organizations": _split(entity.get("organizations")), "roles": _split(entity.get("roles")), "dates": _split(entity.get("dates")), "identifiers": _split(entity.get("identifiers")), "domain_anchors": []}

    def _mission_queries(self, fp: Dict[str, Any], category_key: str) -> List[MissionQuery]:
        name = fp.get("display_name") or (fp.get("names") or [""])[0]
        places = fp.get("places") or []
        orgs = fp.get("organizations") or []
        roles = fp.get("roles") or []
        dates = fp.get("dates") or []
        ids = fp.get("identifiers") or []
        risk = "high" if category_key in {"person_public_personal_data", "person_legal_proceedings", "person_public_financial_data", "person_images"} else "normal"
        q: List[MissionQuery] = []
        def add(stage, query, intent, priority, p, r, source="public_web", pii=risk):
            if query.strip():
                q.append(MissionQuery(stage, category_key, " ".join(query.split()), intent, priority, p, r, pii, source))
        add("identity_lock", f'"{name}"', "exakter Name als Basisanker", 86, 92, 35)
        for place in places[:3]: add("identity_lock", f'"{name}" "{place}"', "Name + Ortsanker", 96, 96, 30)
        for org in orgs[:4]: add("identity_lock", f'"{name}" "{org}"', "Name + Organisationsanker", 98, 98, 28, "organization_site")
        for role in roles[:3]: add("identity_lock", f'"{name}" "{role}"', "Name + Rollenanker", 92, 93, 35)
        # professional source-focused dorks
        if category_key == "person_legal_proceedings":
            add("precision_source", f'"{name}" (Urteil OR Beschluss OR Aktenzeichen OR Gericht OR Prozess) filetype:pdf', "öffentliche Justiz-/PDF-Dokumente", 90, 86, 48, "court_or_justice")
            add("precision_source", f'"{name}" (site:justiz.de OR site:gerichte.* OR site:bund.de) (Urteil OR Beschluss OR Aktenzeichen)', "amtliche Justizdomains", 88, 84, 42, "court_or_justice")
        elif category_key == "person_public_financial_data":
            add("precision_source", f'"{name}" (Jahresabschluss OR Geschäftsbericht OR Bundesanzeiger OR Unternehmensregister OR Förderung OR Vergabe)', "öffentliche Finanz-/Registerhinweise", 78, 74, 50, "registry")
            for org in orgs[:3]: add("precision_source", f'"{org}" "{name}" (Jahresabschluss OR Geschäftsbericht OR Förderung OR Vergabe)', "Finanzbezug über Organisation", 86, 84, 40, "registry")
        elif category_key == "person_images":
            add("precision_source", f'"{name}" (Foto OR Bild OR Pressefoto OR Galerie OR Veranstaltung)', "Bild-/Caption-Kontext", 76, 72, 60, "image_media")
            add("precision_source", f'"{name}" (filetype:jpg OR filetype:png OR filetype:webp)', "Bilddatei-Kandidaten", 65, 58, 58, "image_media")
        elif category_key == "person_public_personal_data":
            add("precision_source", f'"{name}" (geboren OR Geburtsdatum OR Geburtsort OR verstorben OR Nachruf)', "öffentlich sichtbare Lebensdaten", 78, 72, 52, "archival_source")
            add("precision_source", f'"{name}" (Personenstandsregister OR Kirchenbuch OR Sterberegister OR Traueranzeige)', "Archiv-/Registerhinweise", 70, 60, 48, "archival_source")
        elif category_key == "person_networks_company_networks":
            add("precision_source", f'"{name}" (Vorstand OR Geschäftsführer OR Gesellschafter OR Beirat OR Kuratorium OR Impressum OR Handelsregister OR Vereinsregister)', "Netzwerk-/Rollen-/Registerprüfung", 88, 83, 54, "registry")
            for ident in ids[:3]: add("precision_source", f'"{name}" "{ident}"', "Identifier-/Domainanker", 84, 82, 38)
        elif category_key == "person_organization":
            for org in orgs[:4] or ["Organisation"]:
                add("precision_source", f'"{name}" "{org}" (Vorstand OR Team OR Ansprechpartner OR Projekt OR Mitglied OR Satzung OR Protokoll)', "Organisationsrolle prüfen", 91, 90, 55, "organization_site")
                add("precision_source", f'"{name}" "{org}" filetype:pdf', "Organisations-PDF prüfen", 90, 88, 45, "public_pdf")
        else:
            add("precision_source", f'"{name}" filetype:pdf', "PDF-Treffer prüfen", 85, 82, 55, "public_pdf")
            add("precision_source", f'"{name}" (Presse OR Profil OR Interview OR Vita OR Lebenslauf)', "Presse-/Profilkontext", 80, 78, 58, "newspaper_press")
        # context expansion
        for year in dates[:3]: add("context_expansion", f'"{name}" "{year}"', "Zeitanker erweitern", 72, 70, 62)
        for org in orgs[:3]: add("context_expansion", f'"{org}" "{name.split()[-1] if name.split() else name}"', "Organisation + Nachname breiter prüfen", 76, 70, 66, "organization_site")
        # counter / doppler
        if places:
            negative = " ".join(f'-"{p}"' for p in places[:3])
            add("counter_doppler", f'"{name}" {negative}', "Namensdoppler außerhalb bekannter Orte", 58, 45, 80, pii="normal")
        add("counter_doppler", f'"{name}" (anderer OR verwechselt OR nicht identisch OR Namensgleichheit)', "Widerspruchs-/Verwechslungsprüfung", 52, 42, 62, pii="normal")
        return self._dedupe_queries(q)

    def _insert_query_candidate(self, mission_id: str, case_id: str, entity_id: str, q: MissionQuery, *, max_engines_per_query: int) -> Dict[str, Any]:
        engine_plan = self._engine_plan(q, max_engines_per_query)
        existing = self.db.one("SELECT candidate_id FROM spearhead_query_candidates_58_1 WHERE mission_id=? AND query=? AND stage=?", [mission_id, q.query, q.stage])
        if existing:
            return self.get_query_candidate(existing["candidate_id"])
        cid = new_id("qq581")
        self.db.execute('''INSERT INTO spearhead_query_candidates_58_1(candidate_id,mission_id,case_id,entity_id,category_key,stage,query,intent,priority,precision_weight,recall_weight,pii_risk,source_focus,engine_plan_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [cid, mission_id, case_id, entity_id, q.category_key, q.stage, q.query, q.intent, q.priority, q.precision_weight, q.recall_weight, q.pii_risk, q.source_focus, dumps(engine_plan), now_ts()])
        return self.get_query_candidate(cid)

    def get_query_candidate(self, candidate_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM spearhead_query_candidates_58_1 WHERE candidate_id=?", [candidate_id])
        if not row:
            raise KeyError(candidate_id)
        row["engine_plan"] = loads(row.pop("engine_plan_json", "[]"), [])
        return row

    def _candidate(self, candidate_id: str) -> Dict[str, Any]:
        return self.get_query_candidate(candidate_id)

    def _engine_plan(self, q: MissionQuery, max_engines: int) -> List[Dict[str, str]]:
        roles = {
            "google": "broad_relevance", "bing": "pdf_and_alt_index", "brave": "independent_index",
            "duckduckgo": "mixed_meta", "startpage": "google_perspective", "qwant": "eu_perspective",
            "mojeek": "independent_secondary", "ecosia": "bing_variant", "yahoo": "bing_variant_secondary", "swisscows": "filtered_secondary",
        }
        plan = []
        for e in TEN_SEARCH_ENGINES[:max_engines]:
            plan.append({"engine": e.key, "label": e.label, "role": roles.get(e.key, "general"), "why": f"{q.stage}:{q.source_focus}"})
        return plan

    def _source_type(self, title: str, url: str, snippet: str) -> str:
        blob = f"{title} {url} {snippet}".lower()
        for needle, stype in SOURCE_HINTS:
            if needle in blob:
                return stype
        if url.lower().endswith(".pdf"):
            return "public_pdf"
        if any(x in blob for x in ["gmbh", "verein", "vorstand", "team", "impressum"]):
            return "organization_site"
        return "public_web"

    def _source_weight(self, source_type: str, domain: str) -> int:
        base = {"official_public_record": 25, "court_or_justice": 24, "registry": 23, "public_pdf": 17, "newspaper_press": 15, "organization_site": 14, "archival_source": 15, "image_media": 8, "public_web": 8}.get(source_type, 5)
        for d, boost in HIGH_VALUE_DOMAINS.items():
            if d in domain:
                base += boost
        return min(35, base)

    def _score_result(self, fp: Dict[str, Any], *, title: str, url: str, snippet: str, source_type: str, query: str) -> Dict[str, Any]:
        hay = f"{title} {snippet} {url}".lower()
        name_score = 0
        for name in fp.get("names", [])[:8]:
            if str(name).lower() in hay:
                name_score = max(name_score, 38 if " " in str(name) else 20)
        anchors = 0; matched = []
        for field, weight in [("places", 14), ("organizations", 22), ("roles", 14), ("dates", 8), ("identifiers", 15), ("domain_anchors", 15)]:
            for val in fp.get(field, [])[:12]:
                if str(val).lower() and str(val).lower() in hay:
                    anchors += weight; matched.append((field, val)); break
        doppler = 0
        if name_score == 0: doppler += 35
        if not matched: doppler += 25
        if fp.get("places") and any(city in hay for city in ["berlin", "hamburg", "münchen", "koeln", "köln", "frankfurt"] if all(city not in str(p).lower() for p in fp.get("places", []))):
            doppler += 10
        sens = sum(8 for t in SENSITIVE_TERMS if t in hay or t in query.lower())
        sw = self._source_weight(source_type, _domain(url))
        identity_fit = max(0, min(100, name_score + min(anchors, 45) - min(doppler, 45)))
        total = max(0, min(100, identity_fit + sw - max(0, sens - 22)))
        flags = []
        if doppler >= 30: flags.append("name_doppler_review")
        if sens >= 24: flags.append("sensitive_review_required")
        if not matched: flags.append("missing_context_anchor")
        if sw >= 24: flags.append("high_value_source")
        if source_type in {"court_or_justice", "registry"}: flags.append("authority_source_review")
        label = "priority_hit" if total >= 82 else "strong_candidate" if total >= 68 else "review_candidate" if total >= 48 else "weak_or_doppler_risk"
        actions = self._recommended_actions(label, flags, source_type)
        return {"identity_fit": identity_fit, "source_weight": sw, "doppler_risk": min(60, doppler), "sensitivity_score": min(60, sens), "total_score": total, "ranking_label": label, "flags": flags, "recommended_actions": actions}

    def _recommended_actions(self, label: str, flags: List[str], source_type: str) -> List[str]:
        actions = []
        if label in {"priority_hit", "strong_candidate"}: actions.append("in_personenakte_pruefen_und_ggf_inkludieren")
        if "name_doppler_review" in flags or "missing_context_anchor" in flags: actions.append("identitaetsanker_gegenpruefen")
        if "sensitive_review_required" in flags: actions.append("redaktion_exportblock_pruefen")
        if source_type in {"court_or_justice", "registry", "official_public_record"}: actions.append("quelle_und_dokumentdatum_sichern")
        if not actions: actions.append("als_kandidat_markieren_oder_verwerfen")
        return actions

    def _extract_anchors(self, results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        text = "\n".join(f"{r.get('title','')} {r.get('snippet','')} {r.get('url','')}" for r in results[:30])
        orgs = re.findall(r"\b[A-ZÄÖÜ][\wÄÖÜäöüß&.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß&.-]+){0,4}\s+(?:GmbH|AG|UG|e\.V\.|Verein|Stiftung|gGmbH)\b", text)
        years = re.findall(r"\b(?:19|20)\d{2}\b", text)
        domains = [_domain(u) for u in re.findall(r"https?://[^\s)\]]+", text)]
        roles = [term for term in ROLE_TERMS if term.lower() in text.lower()]
        return {"organizations": _dedupe(orgs), "years": _dedupe(years), "domains": _dedupe([d for d in domains if d]), "roles": _dedupe(roles)}

    def _learned_terms_from_result(self, result: Dict[str, Any], rating: str) -> Dict[str, List[str]]:
        anchors = self._extract_anchors([result])
        if rating in {"false_positive", "name_doppler", "not_relevant"}:
            return {"negative_terms": _dedupe(anchors.get("organizations", []) + anchors.get("domains", [])), "positive_terms": []}
        return {"positive_terms": _dedupe(anchors.get("organizations", []) + anchors.get("domains", []) + anchors.get("roles", [])), "negative_terms": []}

    def _entity_from_db(self, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE entity_id=?", [entity_id])
        if not row:
            raise KeyError(entity_id)
        for col in ["known_names_json", "aliases_json", "dates_json", "places_json", "organizations_json", "roles_json", "identifiers_json", "public_links_json"]:
            row[col.replace("_json", "")] = loads(row.pop(col, "[]"), [])
        return row

    def _dedupe_results(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set(); out = []
        for r in results:
            key = _canonical(r.get("url", ""))
            if not key or key in seen:
                continue
            seen.add(key); out.append(r)
        return out

    def _dedupe_queries(self, queries: List[MissionQuery]) -> List[MissionQuery]:
        seen = set(); out = []
        for q in queries:
            key = q.query.lower()
            if key in seen:
                continue
            seen.add(key); out.append(q)
        return out

    def _mission_metrics(self, mission_id: str) -> Dict[str, Any]:
        qrows = self.db.all("SELECT stage, status, priority FROM spearhead_query_candidates_58_1 WHERE mission_id=?", [mission_id])
        rrows = self.ranked_candidates(mission_id, limit=500)
        feedback = self.db.all("SELECT rating FROM spearhead_learning_events_58_1 WHERE mission_id=?", [mission_id])
        top10 = rrows[:10]
        dup_groups = self._counts([r["duplicate_group"] for r in rrows])
        duplicate_items = sum(v - 1 for v in dup_groups.values() if v > 1)
        return {
            "query_count": len(qrows),
            "queries_by_stage": self._counts([r["stage"] for r in qrows]),
            "opened_queries": sum(1 for r in qrows if r["status"] == "opened"),
            "result_count": len(rrows),
            "priority_hits": sum(1 for r in rrows if r["ranking_label"] == "priority_hit"),
            "strong_candidates": sum(1 for r in rrows if r["ranking_label"] in {"priority_hit", "strong_candidate"}),
            "duplicate_rate": round(duplicate_items / len(rrows), 3) if rrows else 0,
            "top10_avg_score": round(sum(r["total_score"] for r in top10) / len(top10), 1) if top10 else 0,
            "feedback_counts": self._counts([f["rating"] for f in feedback]),
        }

    def _refresh_mission_metrics(self, mission_id: str) -> None:
        self.db.execute("UPDATE spearhead_search_missions_58_1 SET metrics_json=?, updated_at=? WHERE mission_id=?", [dumps(self._mission_metrics(mission_id)), now_ts(), mission_id])

    def _counts(self, values: Iterable[str]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for v in values:
            out[str(v)] = out.get(str(v), 0) + 1
        return out
