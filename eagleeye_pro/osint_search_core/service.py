from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


CLAIM_SOURCE_TYPES = {
    "court_or_justice": "Gerichts-/Verfahrenshinweis",
    "registry": "Register-/Organisationshinweis",
    "official_public_record": "amtlicher öffentlicher Hinweis",
    "public_pdf": "öffentlicher Dokument-/PDF-Hinweis",
    "newspaper_press": "Presse-/Zeitungshinweis",
    "organization_site": "Organisations-/Rollenhinweis",
    "archival_source": "Archiv-/Lebensereignis-Hinweis",
    "image_media": "Bild-/Medienhinweis",
    "public_web": "öffentlicher Webhinweis",
}


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _canonical_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = _canonical_text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key); out.append(text)
    return out


class OSINTSearchCoreStableService:
    """Build 59.0 OSINT Search Core Stable.

    This service turns the existing Search Spearhead machinery into a stable
    professional OSINT core: result feed intake, graph construction, claim
    intelligence, adaptive next steps and measurable search quality. It stays
    public-only and does not bypass logins, CAPTCHAs, paywalls or access
    restrictions.
    """

    def __init__(self, db: Database, audit: AuditService, *, search_spearhead, person_detail=None, claim_builder=None, source_intel=None):
        self.db = db
        self.audit = audit
        self.search_spearhead = search_spearhead
        self.person_detail = person_detail
        self.claim_builder = claim_builder
        self.source_intel = source_intel
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_core_sessions_59 (
          session_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          mission_id TEXT NOT NULL,
          objective TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          quality_snapshot_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_osint59_sessions_entity ON osint_core_sessions_59(case_id, entity_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS osint_core_feeds_59 (
          feed_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          mission_id TEXT NOT NULL,
          engine TEXT DEFAULT '',
          query TEXT DEFAULT '',
          candidate_id TEXT DEFAULT '',
          result_count INTEGER DEFAULT 0,
          imported_result_ids_json TEXT NOT NULL,
          raw_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS osint_core_graph_nodes_59 (
          node_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          node_type TEXT NOT NULL,
          natural_key TEXT NOT NULL,
          label TEXT NOT NULL,
          data_json TEXT NOT NULL,
          weight INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          UNIQUE(session_id, node_type, natural_key)
        );
        CREATE INDEX IF NOT EXISTS idx_osint59_graph_node_type ON osint_core_graph_nodes_59(session_id, node_type);

        CREATE TABLE IF NOT EXISTS osint_core_graph_edges_59 (
          edge_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          from_node_id TEXT NOT NULL,
          to_node_id TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          explanation TEXT DEFAULT '',
          weight INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          UNIQUE(session_id, from_node_id, to_node_id, relation_type)
        );

        CREATE TABLE IF NOT EXISTS osint_core_claims_59 (
          claim_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          claim_type TEXT NOT NULL,
          statement TEXT NOT NULL,
          source_result_ids_json TEXT NOT NULL,
          evidence_count INTEGER DEFAULT 0,
          average_score REAL DEFAULT 0,
          identity_fit INTEGER DEFAULT 0,
          doppler_risk INTEGER DEFAULT 0,
          confidence_label TEXT DEFAULT 'candidate',
          reportability TEXT DEFAULT 'internal_review',
          uncertainty_json TEXT NOT NULL,
          counter_evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(session_id, claim_type, statement)
        );
        CREATE INDEX IF NOT EXISTS idx_osint59_claims_session ON osint_core_claims_59(session_id, average_score DESC);

        CREATE TABLE IF NOT EXISTS osint_core_next_actions_59 (
          action_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          action_type TEXT NOT NULL,
          priority INTEGER DEFAULT 50,
          title TEXT NOT NULL,
          query TEXT DEFAULT '',
          rationale TEXT NOT NULL,
          status TEXT DEFAULT 'planned',
          created_at TEXT NOT NULL,
          UNIQUE(session_id, action_type, title, query)
        );
        ''')
        self.db.conn.commit()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def start_session(self, case_id: str, entity: Dict[str, Any], category_key: str, *, objective: str = "osint_search_core_stable", max_queries: int = 35) -> Dict[str, Any]:
        mission = self.search_spearhead.create_search_mission(case_id, entity, category_key, objective=objective, max_queries=max_queries, max_engines_per_query=10, mode="precision_first")
        session_id = new_id("osc59")
        now = now_ts()
        snapshot = {"mission_id": mission["mission_id"], "query_count": mission.get("metrics", {}).get("query_count", 0), "readiness": self.search_spearhead.professional_readiness_score(mission["mission_id"])}
        self.db.execute('''INSERT INTO osint_core_sessions_59(session_id,case_id,entity_id,category_key,mission_id,objective,quality_snapshot_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', [session_id, case_id, entity.get("entity_id", ""), category_key, mission["mission_id"], objective, dumps(snapshot), now, now])
        self.audit.log("create", "osint_core_session_59", session_id, case_id, {"mission_id": mission["mission_id"], "category_key": category_key})
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM osint_core_sessions_59 WHERE session_id=?", [session_id])
        if not row:
            raise KeyError(session_id)
        row["quality_snapshot"] = loads(row.pop("quality_snapshot_json", "{}"), {})
        return row

    def list_sessions(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM osint_core_sessions_59 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for row in rows:
            row["quality_snapshot"] = loads(row.pop("quality_snapshot_json", "{}"), {})
        return rows

    def latest_or_start(self, case_id: str, entity: Dict[str, Any], category_key: str) -> Dict[str, Any]:
        existing = self.list_sessions(case_id, entity.get("entity_id", ""), limit=1)
        if existing and existing[0].get("category_key") == category_key:
            return existing[0]
        return self.start_session(case_id, entity, category_key)

    # ------------------------------------------------------------------
    # Result feed / capture layer
    # ------------------------------------------------------------------
    def import_result_feed(self, session_id: str, raw_text: str, *, engine: str = "", candidate_id: str = "") -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not candidate_id:
            top = self.search_spearhead.top_query_candidates(session["mission_id"], limit=1)
            candidate_id = top[0]["candidate_id"] if top else ""
        imported = self.search_spearhead.import_serp_text(session["mission_id"], raw_text, engine=engine, candidate_id=candidate_id)
        result_ids = [r.get("result_candidate_id") for r in imported.get("results", []) if r.get("result_candidate_id")]
        feed_id = new_id("feed59")
        query = ""
        if candidate_id:
            try:
                query = self.search_spearhead.get_query_candidate(candidate_id).get("query", "")
            except Exception:
                query = ""
        self.db.execute('''INSERT INTO osint_core_feeds_59(feed_id,session_id,mission_id,engine,query,candidate_id,result_count,imported_result_ids_json,raw_hash,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [feed_id, session_id, session["mission_id"], engine, query, candidate_id, len(result_ids), dumps(result_ids), _sha(raw_text)[:32], now_ts()])
        graph = self.build_source_graph(session_id)
        claims = self.build_claims(session_id)
        actions = self.generate_next_actions(session_id)
        self._refresh_session_quality(session_id)
        self.audit.log("import", "osint_core_result_feed_59", feed_id, session["case_id"], {"session_id": session_id, "result_count": len(result_ids)})
        return {"feed_id": feed_id, "session_id": session_id, "imported_result_ids": result_ids, "result_count": len(result_ids), "graph": graph, "claims": claims, "next_actions": actions}

    # ------------------------------------------------------------------
    # Source Intelligence Graph
    # ------------------------------------------------------------------
    def build_source_graph(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        mission_id = session["mission_id"]
        mission_node = self._node(session_id, "mission", mission_id, "Research Mission", {"mission_id": mission_id}, 80)
        entity_node = self._node(session_id, "entity", session["entity_id"], "Zielperson / Organisation", {"entity_id": session["entity_id"]}, 100)
        self._edge(session_id, mission_node["node_id"], entity_node["node_id"], "targets", "Mission bezieht sich auf Entity", 100)
        queries = self.search_spearhead.top_query_candidates(mission_id, limit=500)
        results = self.search_spearhead.ranked_candidates(mission_id, limit=500)
        qnodes: Dict[str, Dict[str, Any]] = {}
        for q in queries:
            qn = self._node(session_id, "query", q["candidate_id"], q.get("query", ""), {"stage": q.get("stage"), "intent": q.get("intent"), "priority": q.get("priority")}, int(q.get("priority", 50)))
            qnodes[q["candidate_id"]] = qn
            self._edge(session_id, mission_node["node_id"], qn["node_id"], "plans_query", q.get("intent", ""), int(q.get("priority", 50)))
        for r in results:
            rn = self._node(session_id, "result", r["result_candidate_id"], r.get("title", "Treffer"), {"url": r.get("url"), "domain": r.get("domain"), "score": r.get("total_score"), "label": r.get("ranking_label")}, int(r.get("total_score", 0)))
            domain = r.get("domain") or _domain(r.get("url", ""))
            if domain:
                dn = self._node(session_id, "domain", domain, domain, {"domain": domain}, int(r.get("source_weight", 0)))
                self._edge(session_id, rn["node_id"], dn["node_id"], "hosted_on", "Treffer-Domain", int(r.get("source_weight", 0)))
            if r.get("candidate_id") and r.get("candidate_id") in qnodes:
                self._edge(session_id, qnodes[r["candidate_id"]]["node_id"], rn["node_id"], "found_result", "Query fand Treffer", int(r.get("total_score", 0)))
            self._edge(session_id, rn["node_id"], entity_node["node_id"], "candidate_for", "Treffer wird gegen Entity geprüft", int(r.get("identity_fit", 0)))
        return self.graph_summary(session_id)

    def graph_summary(self, session_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT node_type, COUNT(*) c FROM osint_core_graph_nodes_59 WHERE session_id=? GROUP BY node_type", [session_id])
        edges = self.db.all("SELECT relation_type, COUNT(*) c FROM osint_core_graph_edges_59 WHERE session_id=? GROUP BY relation_type", [session_id])
        return {"session_id": session_id, "node_count": sum(int(n["c"]) for n in nodes), "edge_count": sum(int(e["c"]) for e in edges), "nodes_by_type": {n["node_type"]: n["c"] for n in nodes}, "edges_by_type": {e["relation_type"]: e["c"] for e in edges}}

    # ------------------------------------------------------------------
    # Claim Intelligence
    # ------------------------------------------------------------------
    def build_claims(self, session_id: str, *, min_score: int = 45) -> Dict[str, Any]:
        session = self.get_session(session_id)
        results = [r for r in self.search_spearhead.ranked_candidates(session["mission_id"], limit=500) if int(r.get("total_score", 0)) >= min_score]
        groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for r in results:
            stype = r.get("source_type", "public_web")
            group_key = (stype, r.get("domain", "") or "unknown_domain")
            groups.setdefault(group_key, []).append(r)
        created: List[Dict[str, Any]] = []
        for (stype, domain), items in groups.items():
            best = sorted(items, key=lambda x: int(x.get("total_score", 0)), reverse=True)[:8]
            claim_type = CLAIM_SOURCE_TYPES.get(stype, "öffentlicher Hinweis")
            statement = self._claim_statement(claim_type, domain, best)
            avg = round(sum(int(x.get("total_score", 0)) for x in best) / len(best), 1)
            fit = round(sum(int(x.get("identity_fit", 0)) for x in best) / len(best))
            doppler = round(sum(int(x.get("doppler_risk", 0)) for x in best) / len(best))
            confidence = "strong_public_indicator" if len(best) >= 2 and avg >= 70 and doppler < 30 else "review_indicator" if avg >= 55 else "candidate"
            reportability = "reportable_with_uncertainty" if confidence == "strong_public_indicator" else "internal_review"
            if any("sensitive_review_required" in (x.get("flags") or []) for x in best):
                reportability = "redaction_required"
            uncertainties = self._uncertainties_for_claim(best, doppler)
            counters = [x["result_candidate_id"] for x in best if x.get("ranking_label") == "weak_or_doppler_risk" or "name_doppler_review" in (x.get("flags") or [])]
            claim = self._upsert_claim(session, claim_type, statement, best, avg, fit, doppler, confidence, reportability, uncertainties, counters)
            created.append(claim)
        return {"session_id": session_id, "claim_count": len(created), "claims": created}

    def list_claims(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM osint_core_claims_59 WHERE session_id=? ORDER BY average_score DESC, evidence_count DESC LIMIT ?", [session_id, int(limit)])
        for r in rows:
            r["source_result_ids"] = loads(r.pop("source_result_ids_json", "[]"), [])
            r["uncertainty"] = loads(r.pop("uncertainty_json", "[]"), [])
            r["counter_evidence"] = loads(r.pop("counter_evidence_json", "[]"), [])
        return rows

    # ------------------------------------------------------------------
    # Adaptive Research Agent
    # ------------------------------------------------------------------
    def generate_next_actions(self, session_id: str, limit: int = 10) -> Dict[str, Any]:
        session = self.get_session(session_id)
        mission_id = session["mission_id"]
        rec = self.search_spearhead.recommend_next_queries(mission_id, limit=8, persist=True)
        results = self.search_spearhead.ranked_candidates(mission_id, limit=40)
        claims = self.list_claims(session_id, limit=20)
        planned: List[Dict[str, Any]] = []
        for q in rec.get("queries", [])[:4]:
            planned.append(self._upsert_action(session_id, "followup_query", 88 if not q.get("already_existing") else 70, "Nächste Anschlussquery prüfen", q.get("query", ""), q.get("intent", "adaptive Anschlussrecherche")))
        if not any(int(r.get("identity_fit", 0)) >= 70 for r in results[:10]):
            planned.append(self._upsert_action(session_id, "identity_anchor", 95, "Identitätsanker verstärken", "", "Top-Treffer haben noch keinen stabilen Identitätsfit; Ort/Organisation/Rolle ergänzen."))
        if any(int(r.get("doppler_risk", 0)) >= 30 for r in results[:10]):
            planned.append(self._upsert_action(session_id, "doppler_probe", 92, "Namensdoppler aktiv gegenprüfen", "", "Mehrere Top-Treffer tragen Doppler-Risiko; Gegenanker und Ausschlussqueries prüfen."))
        if not claims:
            planned.append(self._upsert_action(session_id, "claim_gap", 82, "Claims aus Funden bilden", "", "Noch keine berichtsfähigen Claim-Kandidaten vorhanden."))
        if any(c.get("reportability") == "redaction_required" for c in claims):
            planned.append(self._upsert_action(session_id, "redaction_review", 90, "Redaction vor Bericht prüfen", "", "Sensible Treffer/Claims dürfen nicht ungeprüft exportiert werden."))
        return {"session_id": session_id, "recommended_count": len(planned[:limit]), "actions": planned[:limit]}

    def list_next_actions(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM osint_core_next_actions_59 WHERE session_id=? ORDER BY priority DESC, created_at DESC LIMIT ?", [session_id, int(limit)])

    # ------------------------------------------------------------------
    # Professional readiness / integrated cycle
    # ------------------------------------------------------------------
    def dashboard(self, session_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id)
        spear = self.search_spearhead.dashboard(session["mission_id"])
        graph = self.graph_summary(session_id)
        claims = self.list_claims(session_id, limit=20)
        actions = self.list_next_actions(session_id, limit=20)
        score = self.professional_readiness(session_id, spear=spear, claims=claims, graph=graph)
        return {"build": "59.0", "session": session, "spearhead": spear, "graph": graph, "claims": claims, "next_actions": actions, "professional_readiness": score}

    def professional_readiness(self, session_id: str, *, spear: Dict[str, Any] | None = None, claims: List[Dict[str, Any]] | None = None, graph: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if spear is None:
            session = self.get_session(session_id); spear = self.search_spearhead.dashboard(session["mission_id"])
        if claims is None: claims = self.list_claims(session_id)
        if graph is None: graph = self.graph_summary(session_id)
        sp = spear.get("professional_readiness", {})
        metrics = spear.get("metrics", {})
        result_depth = min(1.0, (spear.get("result_count") or 0) / 25)
        claim_depth = min(1.0, len(claims or []) / 6)
        graph_depth = min(1.0, (graph.get("edge_count") or 0) / 40)
        precision_proxy = min(1.0, (metrics.get("top10_avg_score") or 0) / 80)
        doppler_control = sp.get("doppler_control", 0.5)
        feedback_depth = sp.get("feedback_depth", 0)
        score = round(100 * (0.22 * precision_proxy + 0.18 * result_depth + 0.18 * claim_depth + 0.16 * graph_depth + 0.16 * doppler_control + 0.10 * feedback_depth), 1)
        gaps = []
        if result_depth < 0.7: gaps.append("mehr SERP-/URL-Treffer importieren")
        if claim_depth < 0.5: gaps.append("aus Top-Funden Claims bilden")
        if graph_depth < 0.5: gaps.append("Source-Graph ist noch zu dünn")
        if precision_proxy < 0.7: gaps.append("Top-10-Trefferqualität verbessern")
        if doppler_control < 0.7: gaps.append("Namensdoppler stärker gegenprüfen")
        return {"score": score, "precision_proxy": round(precision_proxy, 2), "result_depth": round(result_depth, 2), "claim_depth": round(claim_depth, 2), "graph_depth": round(graph_depth, 2), "doppler_control": round(doppler_control, 2), "feedback_depth": round(feedback_depth, 2), "gaps": gaps}

    def run_integrated_search_core_cycle(self, case_id: str, entity: Dict[str, Any], category_key: str, *, serp_text: str = "", engine: str = "") -> Dict[str, Any]:
        session = self.start_session(case_id, entity, category_key)
        imported = {"result_count": 0, "imported_result_ids": []}
        if serp_text.strip():
            imported = self.import_result_feed(session["session_id"], serp_text, engine=engine)
        else:
            self.build_source_graph(session["session_id"])
            self.build_claims(session["session_id"])
            self.generate_next_actions(session["session_id"])
        return {"session_id": session["session_id"], "session": self.get_session(session["session_id"]), "import": imported, "dashboard": self.dashboard(session["session_id"])}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _node(self, session_id: str, node_type: str, natural_key: str, label: str, data: Dict[str, Any], weight: int) -> Dict[str, Any]:
        natural_key = str(natural_key or label or node_type)
        existing = self.db.one("SELECT * FROM osint_core_graph_nodes_59 WHERE session_id=? AND node_type=? AND natural_key=?", [session_id, node_type, natural_key])
        if existing:
            return existing
        node_id = new_id("ogn59")
        self.db.execute("INSERT INTO osint_core_graph_nodes_59(node_id,session_id,node_type,natural_key,label,data_json,weight,created_at) VALUES(?,?,?,?,?,?,?,?)", [node_id, session_id, node_type, natural_key, label[:240], dumps(data), int(weight), now_ts()])
        return self.db.one("SELECT * FROM osint_core_graph_nodes_59 WHERE node_id=?", [node_id]) or {"node_id": node_id}

    def _edge(self, session_id: str, from_node: str, to_node: str, relation_type: str, explanation: str, weight: int) -> Dict[str, Any]:
        existing = self.db.one("SELECT * FROM osint_core_graph_edges_59 WHERE session_id=? AND from_node_id=? AND to_node_id=? AND relation_type=?", [session_id, from_node, to_node, relation_type])
        if existing:
            return existing
        edge_id = new_id("oge59")
        self.db.execute("INSERT INTO osint_core_graph_edges_59(edge_id,session_id,from_node_id,to_node_id,relation_type,explanation,weight,created_at) VALUES(?,?,?,?,?,?,?,?)", [edge_id, session_id, from_node, to_node, relation_type, explanation[:600], int(weight), now_ts()])
        return self.db.one("SELECT * FROM osint_core_graph_edges_59 WHERE edge_id=?", [edge_id]) or {"edge_id": edge_id}

    def _claim_statement(self, claim_type: str, domain: str, items: List[Dict[str, Any]]) -> str:
        titles = _dedupe([i.get("title", "") for i in items])[:3]
        src = domain if domain and domain != "unknown_domain" else "öffentlichen Quellen"
        return f"{claim_type}: Die Zielperson/Organisation wird in {src} mit {len(items)} Treffer(n) erwähnt. Prüftitel: {'; '.join(titles)}"

    def _uncertainties_for_claim(self, items: List[Dict[str, Any]], doppler: int) -> List[str]:
        out = []
        if doppler >= 30:
            out.append("Namensdoppler-/Identitätsfit-Risiko manuell prüfen")
        if len(items) < 2:
            out.append("nur eine Quelle im Claim-Bündel")
        if any("sensitive_review_required" in (i.get("flags") or []) for i in items):
            out.append("sensible Daten / Redaction vor Export prüfen")
        if not out:
            out.append("Aussage bleibt öffentlicher Hinweis, keine automatische Identitätsbestätigung")
        return out

    def _upsert_claim(self, session: Dict[str, Any], claim_type: str, statement: str, items: List[Dict[str, Any]], avg: float, fit: int, doppler: int, confidence: str, reportability: str, uncertainties: List[str], counters: List[str]) -> Dict[str, Any]:
        existing = self.db.one("SELECT claim_id FROM osint_core_claims_59 WHERE session_id=? AND claim_type=? AND statement=?", [session["session_id"], claim_type, statement])
        ids = [i["result_candidate_id"] for i in items]
        now = now_ts()
        if existing:
            cid = existing["claim_id"]
            self.db.execute('''UPDATE osint_core_claims_59 SET source_result_ids_json=?, evidence_count=?, average_score=?, identity_fit=?, doppler_risk=?, confidence_label=?, reportability=?, uncertainty_json=?, counter_evidence_json=?, updated_at=? WHERE claim_id=?''', [dumps(ids), len(ids), avg, fit, doppler, confidence, reportability, dumps(uncertainties), dumps(counters), now, cid])
        else:
            cid = new_id("claim59")
            self.db.execute('''INSERT INTO osint_core_claims_59(claim_id,session_id,case_id,entity_id,claim_type,statement,source_result_ids_json,evidence_count,average_score,identity_fit,doppler_risk,confidence_label,reportability,uncertainty_json,counter_evidence_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [cid, session["session_id"], session["case_id"], session["entity_id"], claim_type, statement, dumps(ids), len(ids), avg, fit, doppler, confidence, reportability, dumps(uncertainties), dumps(counters), now, now])
        row = self.db.one("SELECT * FROM osint_core_claims_59 WHERE claim_id=?", [cid]) or {"claim_id": cid}
        if "source_result_ids_json" in row:
            row["source_result_ids"] = loads(row.pop("source_result_ids_json", "[]"), [])
            row["uncertainty"] = loads(row.pop("uncertainty_json", "[]"), [])
            row["counter_evidence"] = loads(row.pop("counter_evidence_json", "[]"), [])
        return row

    def _upsert_action(self, session_id: str, action_type: str, priority: int, title: str, query: str, rationale: str) -> Dict[str, Any]:
        existing = self.db.one("SELECT * FROM osint_core_next_actions_59 WHERE session_id=? AND action_type=? AND title=? AND query=?", [session_id, action_type, title, query])
        if existing:
            return existing
        aid = new_id("act59")
        self.db.execute("INSERT INTO osint_core_next_actions_59(action_id,session_id,action_type,priority,title,query,rationale,created_at) VALUES(?,?,?,?,?,?,?,?)", [aid, session_id, action_type, int(priority), title, query, rationale, now_ts()])
        return self.db.one("SELECT * FROM osint_core_next_actions_59 WHERE action_id=?", [aid]) or {"action_id": aid}

    def _refresh_session_quality(self, session_id: str) -> None:
        dash = self.dashboard(session_id)
        snapshot = {"professional_readiness": dash.get("professional_readiness", {}), "graph": dash.get("graph", {}), "claim_count": len(dash.get("claims", []))}
        self.db.execute("UPDATE osint_core_sessions_59 SET quality_snapshot_json=?, updated_at=? WHERE session_id=?", [dumps(snapshot), now_ts(), session_id])
