from __future__ import annotations
from typing import Any, Dict, List
from collections import Counter
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

NODE_TYPES = {
    "case", "person_target", "alias", "email", "username", "location", "company", "domain",
    "source", "capture", "review_item", "evidence", "identity_candidate", "risk_finding", "event"
}

RELATIONSHIP_TYPES = {
    "has_target", "has_alias", "has_email", "uses_username", "associated_location", "associated_company",
    "associated_domain", "contains_evidence", "captured_from", "supports", "contradicts",
    "mentions", "possibly_same_as", "risk_relates_to", "timeline_event_for", "evidence_links_to"
}

class GraphService:
    """Build 22.0 Graph Pro: fallbezogene, erklärbare Beziehungsanalyse.

    Wichtig: Dieses Modul bestätigt keine Identität automatisch. Knoten und Kanten bleiben
    Kandidaten, bis ein Analyst sie explizit prüft. Jede belastbare Kante kann eine Evidence-ID
    und eine Explainability-Begründung tragen.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def add_node(self, case_id: str, node_type: str, label: str, confidence: float=0.5, review_status: str="candidate", properties: Dict[str, Any] | None=None) -> Dict[str, Any]:
        node_type = node_type.strip() or "source"
        label = (label or "Unbenannter Knoten").strip()
        existing = self.db.one("SELECT * FROM graph_nodes WHERE case_id=? AND node_type=? AND label=?", [case_id,node_type,label])
        if existing:
            return existing
        nid = new_id("node")
        self.db.execute("INSERT INTO graph_nodes(node_id,case_id,node_type,label,confidence,review_status,properties_json) VALUES(?,?,?,?,?,?,?)", [nid,case_id,node_type,label,float(confidence),review_status,dumps(properties or {})])
        self.audit.log("create", "graph_node", nid, case_id, {"type": node_type, "label": label, "confidence": confidence})
        return self.db.one("SELECT * FROM graph_nodes WHERE node_id=?", [nid])

    def add_edge(self, case_id: str, source_node_id: str, target_node_id: str, relationship_type: str, source_evidence_id: str="", confidence: float=0.5, explanation: str="", review_status: str="candidate", relationship_category: str="association", analysis_tags: List[str] | None=None, counter_evidence: List[str] | None=None) -> Dict[str, Any]:
        if not self.db.one("SELECT node_id FROM graph_nodes WHERE node_id=? AND case_id=?", [source_node_id, case_id]):
            raise KeyError("Source-Knoten nicht gefunden.")
        if not self.db.one("SELECT node_id FROM graph_nodes WHERE node_id=? AND case_id=?", [target_node_id, case_id]):
            raise KeyError("Target-Knoten nicht gefunden.")
        relationship_type = relationship_type.strip() or "mentions"
        existing = self.db.one("""SELECT * FROM graph_edges WHERE case_id=? AND source_node_id=? AND target_node_id=? AND relationship_type=? AND COALESCE(source_evidence_id,'')=?""", [case_id, source_node_id, target_node_id, relationship_type, source_evidence_id or ""])
        if existing:
            return existing
        eid = new_id("edge")
        self.db.execute("""INSERT INTO graph_edges(edge_id,case_id,source_node_id,target_node_id,relationship_type,source_evidence_id,confidence,explanation,review_status,relationship_category,counter_evidence_json,analysis_tags_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [eid,case_id,source_node_id,target_node_id,relationship_type,source_evidence_id,float(confidence),explanation,review_status,relationship_category,dumps(counter_evidence or []),dumps(analysis_tags or [])])
        self.audit.log("create", "graph_edge", eid, case_id, {"relationship": relationship_type, "confidence": confidence, "evidence": source_evidence_id, "category": relationship_category})
        return self.db.one("SELECT * FROM graph_edges WHERE edge_id=?", [eid])

    def list_nodes(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM graph_nodes WHERE case_id=? ORDER BY node_type,label", [case_id])
        for r in rows:
            r["properties_json"] = loads(r.get("properties_json"), {})
        return rows

    def list_edges(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM graph_edges WHERE case_id=? ORDER BY relationship_type, confidence DESC", [case_id])
        for r in rows:
            r["analysis_tags_json"] = loads(r.get("analysis_tags_json"), [])
            r["counter_evidence_json"] = loads(r.get("counter_evidence_json"), [])
        return rows

    @staticmethod
    def _items(raw: str | None) -> List[str]:
        data = loads(raw, [])
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        if isinstance(raw, str):
            return [x.strip() for x in raw.split(',') if x.strip()]
        return []

    def rebuild_basic_graph(self, case_id: str) -> Dict[str, int]:
        return self.rebuild_pro_graph(case_id)

    def rebuild_pro_graph(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not case:
            raise KeyError("Fall nicht gefunden.")
        case_node = self.add_node(case_id, "case", case["title"], 1.0, "confirmed", {"case_id": case_id, "purpose": case.get("purpose")})
        created_edges = 0

        for t in self.db.all("SELECT * FROM targets WHERE case_id=?", [case_id]):
            tnode = self.add_node(case_id, "person_target", t["name"], 0.8, "candidate", {"target_id": t["target_id"], "note": "Zielperson/Anker, keine automatische Identitätsbestätigung"})
            self.add_edge(case_id, case_node["node_id"], tnode["node_id"], "has_target", "", 0.95, "Fallziel aus Fallanlage", "confirmed", "case_scope", ["target_anchor"]); created_edges += 1
            for node_type, rel, field, conf in [
                ("alias", "has_alias", "aliases_json", 0.68),
                ("email", "has_email", "emails_json", 0.72),
                ("username", "uses_username", "usernames_json", 0.68),
                ("location", "associated_location", "locations_json", 0.55),
                ("company", "associated_company", "companies_json", 0.62),
                ("domain", "associated_domain", "domains_json", 0.60),
            ]:
                for value in self._items(t.get(field)):
                    n = self.add_node(case_id, node_type, value, conf, "candidate", {"target_id": t["target_id"], "source_field": field})
                    self.add_edge(case_id, tnode["node_id"], n["node_id"], rel, "", conf, f"Ankerdaten aus Zielprofil-Feld {field}; muss quellenbasiert bestätigt werden.", "candidate", "target_anchor", ["needs_evidence"]); created_edges += 1

        case_evidence_node = self.add_node(case_id, "source", "Evidence Vault", 1.0, "confirmed", {"system": True})
        for ev in self.db.all("SELECT * FROM evidence_items WHERE case_id=?", [case_id]):
            evnode = self.add_node(case_id, "evidence", ev["title"], min(1.0, max(0.25, float(ev.get("reliability_score") or 0.55))), ev.get("review_decision") or "candidate", {"evidence_id": ev["evidence_id"], "category": ev.get("category"), "source_url": ev.get("source_url"), "content_hash": ev.get("content_hash")})
            self.add_edge(case_id, case_evidence_node["node_id"], evnode["node_id"], "contains_evidence", ev["evidence_id"], 0.75, "Evidence Item liegt im Evidence Vault und ist hashbasiert nachvollziehbar.", "candidate", "evidence_chain", ["hash", "vault"]); created_edges += 1
            statement = " ".join([ev.get("title") or "", ev.get("statement") or "", ev.get("source_url") or ""]).lower()
            for n in self.db.all("SELECT * FROM graph_nodes WHERE case_id=? AND node_type IN ('person_target','alias','email','username','location','company','domain')", [case_id]):
                label = (n.get("label") or "").lower()
                if label and label in statement:
                    self.add_edge(case_id, evnode["node_id"], n["node_id"], "evidence_links_to", ev["evidence_id"], min(0.88, 0.45 + float(ev.get("reliability_score") or 0.45) * 0.5), f"Evidence-Statement/URL enthält den Anker '{n.get('label')}'.", "candidate", "evidence_association", ["extracted_marker"]); created_edges += 1

        for cap in self.db.all("SELECT * FROM source_captures WHERE case_id=?", [case_id]):
            host = cap.get("host") or cap.get("url") or "public-source"
            snode = self.add_node(case_id, "capture", cap.get("title") or host, 0.55, "candidate", {"capture_id": cap.get("capture_id"), "url": cap.get("url"), "host": host, "content_hash": cap.get("content_hash")})
            self.add_edge(case_id, case_node["node_id"], snode["node_id"], "captured_from", "", 0.55, "Manuell erfasster öffentlicher Capture-Snapshot; in Review überführt.", "candidate", "source_capture", ["snapshot", "manual_public"]); created_edges += 1

        for ic in self.db.all("SELECT * FROM identity_candidates WHERE case_id=?", [case_id]):
            inode = self.add_node(case_id, "identity_candidate", ic.get("label") or ic.get("candidate_id"), float(ic.get("score") or 0.5), ic.get("status") or "candidate", {"candidate_id": ic.get("candidate_id"), "positive_markers": loads(ic.get("positive_markers_json"), []), "negative_markers": loads(ic.get("negative_markers_json"), [])})
            self.add_edge(case_id, case_node["node_id"], inode["node_id"], "possibly_same_as", "", float(ic.get("score") or 0.5), "Identity Resolution gibt nur Kandidatenlogik aus; menschliche Prüfung erforderlich.", ic.get("status") or "candidate", "identity_resolution", ["candidate_only"]); created_edges += 1

        for rf in self.db.all("SELECT * FROM risk_findings WHERE case_id=?", [case_id]):
            rnode = self.add_node(case_id, "risk_finding", rf.get("title") or rf.get("finding_id"), 0.55, rf.get("status") or "candidate", {"finding_id": rf.get("finding_id"), "severity": rf.get("severity"), "category": rf.get("category"), "rationale": rf.get("rationale")})
            self.add_edge(case_id, case_node["node_id"], rnode["node_id"], "risk_relates_to", rf.get("source_evidence_id") or "", 0.55, "Risiko-/Unsicherheitenregister bezieht sich auf den Fall; keine Schuld- oder Tatsachenbehauptung.", "candidate", "risk_context", ["risk", "uncertainty"]); created_edges += 1

        dashboard = self.graph_dashboard(case_id)
        self.audit.log("rebuild", "graph", case_id, case_id, {"nodes": dashboard["nodes"], "edges": dashboard["edges"], "mode": "pro"})
        return {"nodes": dashboard["nodes"], "edges": dashboard["edges"], "created_edges_attempted": created_edges, "dashboard": dashboard}

    def explain_edge(self, edge_id: str) -> Dict[str, Any]:
        edge = self.db.one("SELECT * FROM graph_edges WHERE edge_id=?", [edge_id])
        if not edge:
            raise KeyError("Kante nicht gefunden.")
        source = self.db.one("SELECT * FROM graph_nodes WHERE node_id=?", [edge["source_node_id"]]) or {}
        target = self.db.one("SELECT * FROM graph_nodes WHERE node_id=?", [edge["target_node_id"]]) or {}
        evidence = self.db.one("SELECT * FROM evidence_items WHERE evidence_id=?", [edge.get("source_evidence_id") or ""]) if edge.get("source_evidence_id") else None
        return {
            "edge_id": edge_id,
            "relationship": edge.get("relationship_type"),
            "category": edge.get("relationship_category"),
            "confidence": edge.get("confidence"),
            "review_status": edge.get("review_status"),
            "source_node": {"id": source.get("node_id"), "type": source.get("node_type"), "label": source.get("label")},
            "target_node": {"id": target.get("node_id"), "type": target.get("node_type"), "label": target.get("label")},
            "evidence": {"id": evidence.get("evidence_id"), "title": evidence.get("title"), "hash": evidence.get("content_hash"), "decision": evidence.get("review_decision")} if evidence else None,
            "explanation": edge.get("explanation") or "Keine Explanation hinterlegt.",
            "counter_evidence": loads(edge.get("counter_evidence_json"), []),
            "analysis_tags": loads(edge.get("analysis_tags_json"), []),
        }

    def add_counter_evidence_to_edge(self, edge_id: str, evidence_id: str, note: str="") -> Dict[str, Any]:
        edge = self.db.one("SELECT * FROM graph_edges WHERE edge_id=?", [edge_id])
        if not edge:
            raise KeyError("Kante nicht gefunden.")
        cur = loads(edge.get("counter_evidence_json"), [])
        item = {"evidence_id": evidence_id, "note": note, "added_at": now_ts()}
        cur.append(item)
        self.db.execute("UPDATE graph_edges SET counter_evidence_json=?, review_status=? WHERE edge_id=?", [dumps(cur), "conflicting", edge_id])
        self.audit.log("counter_evidence", "graph_edge", edge_id, edge["case_id"], item)
        return self.explain_edge(edge_id)

    def create_hypothesis(self, case_id: str, title: str, statement: str, hypothesis_type: str="relationship", confidence: float=0.5, supporting_evidence: List[str] | None=None, counter_evidence: List[str] | None=None, status: str="open", notes: str="") -> Dict[str, Any]:
        hid = new_id("hyp")
        ts = now_ts()
        self.db.execute("""INSERT INTO graph_hypotheses(hypothesis_id,case_id,title,hypothesis_type,statement,status,confidence,supporting_evidence_json,counter_evidence_json,created_at,updated_at,analyst,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", [hid, case_id, title, hypothesis_type, statement, status, float(confidence), dumps(supporting_evidence or []), dumps(counter_evidence or []), ts, ts, "local-analyst", notes])
        self.audit.log("create", "graph_hypothesis", hid, case_id, {"title": title, "confidence": confidence, "status": status})
        return self.db.one("SELECT * FROM graph_hypotheses WHERE hypothesis_id=?", [hid])

    def decide_hypothesis(self, hypothesis_id: str, status: str, confidence: float | None=None, notes: str="") -> Dict[str, Any]:
        if status not in {"open", "supported", "weakened", "rejected", "needs_more_evidence", "client_export_candidate"}:
            raise ValueError("Unbekannter Hypothesenstatus.")
        hyp = self.db.one("SELECT * FROM graph_hypotheses WHERE hypothesis_id=?", [hypothesis_id])
        if not hyp:
            raise KeyError("Hypothese nicht gefunden.")
        if confidence is None:
            confidence = float(hyp.get("confidence") or 0.5)
        note = notes or hyp.get("notes") or ""
        self.db.execute("UPDATE graph_hypotheses SET status=?, confidence=?, notes=?, updated_at=? WHERE hypothesis_id=?", [status, float(confidence), note, now_ts(), hypothesis_id])
        self.audit.log("decide", "graph_hypothesis", hypothesis_id, hyp["case_id"], {"status": status, "confidence": confidence})
        return self.db.one("SELECT * FROM graph_hypotheses WHERE hypothesis_id=?", [hypothesis_id])

    def add_contradiction(self, case_id: str, title: str, description: str, contradiction_type: str="conflict", severity: str="medium", related_nodes: List[str] | None=None, related_edges: List[str] | None=None, related_evidence: List[str] | None=None, notes: str="") -> Dict[str, Any]:
        cid = new_id("contra")
        ts = now_ts()
        self.db.execute("""INSERT INTO graph_contradictions(contradiction_id,case_id,title,contradiction_type,description,severity,status,related_node_ids_json,related_edge_ids_json,related_evidence_ids_json,created_at,updated_at,analyst,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [cid, case_id, title, contradiction_type, description, severity, "open", dumps(related_nodes or []), dumps(related_edges or []), dumps(related_evidence or []), ts, ts, "local-analyst", notes])
        self.audit.log("create", "graph_contradiction", cid, case_id, {"title": title, "severity": severity})
        return self.db.one("SELECT * FROM graph_contradictions WHERE contradiction_id=?", [cid])

    def list_hypotheses(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM graph_hypotheses WHERE case_id=? ORDER BY updated_at DESC", [case_id])
        for r in rows:
            r["supporting_evidence_json"] = loads(r.get("supporting_evidence_json"), [])
            r["counter_evidence_json"] = loads(r.get("counter_evidence_json"), [])
        return rows

    def list_contradictions(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM graph_contradictions WHERE case_id=? ORDER BY severity DESC, updated_at DESC", [case_id])
        for r in rows:
            r["related_node_ids_json"] = loads(r.get("related_node_ids_json"), [])
            r["related_edge_ids_json"] = loads(r.get("related_edge_ids_json"), [])
            r["related_evidence_ids_json"] = loads(r.get("related_evidence_ids_json"), [])
        return rows

    def graph_dashboard(self, case_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT node_type, review_status, COUNT(*) AS n, AVG(confidence) AS avg_conf FROM graph_nodes WHERE case_id=? GROUP BY node_type, review_status", [case_id])
        edges = self.db.all("SELECT relationship_type, review_status, COUNT(*) AS n, AVG(confidence) AS avg_conf FROM graph_edges WHERE case_id=? GROUP BY relationship_type, review_status", [case_id])
        totals = self.db.one("SELECT (SELECT COUNT(*) FROM graph_nodes WHERE case_id=?) AS nodes, (SELECT COUNT(*) FROM graph_edges WHERE case_id=?) AS edges", [case_id, case_id]) or {"nodes":0, "edges":0}
        hyp = self.db.all("SELECT status, COUNT(*) AS n FROM graph_hypotheses WHERE case_id=? GROUP BY status", [case_id])
        contra = self.db.all("SELECT severity, status, COUNT(*) AS n FROM graph_contradictions WHERE case_id=? GROUP BY severity,status", [case_id])
        return {
            "nodes": int(totals.get("nodes") or 0),
            "edges": int(totals.get("edges") or 0),
            "node_breakdown": [{"type": r["node_type"], "status": r["review_status"], "count": r["n"], "avg_confidence": round(float(r.get("avg_conf") or 0), 3)} for r in nodes],
            "edge_breakdown": [{"relationship": r["relationship_type"], "status": r["review_status"], "count": r["n"], "avg_confidence": round(float(r.get("avg_conf") or 0), 3)} for r in edges],
            "hypotheses": {r["status"]: r["n"] for r in hyp},
            "contradictions": [{"severity": r["severity"], "status": r["status"], "count": r["n"]} for r in contra],
        }

    def build_analysis_narrative(self, case_id: str, title: str="Graph-Analyse-Narrativ") -> Dict[str, Any]:
        dash = self.graph_dashboard(case_id)
        hypotheses = self.list_hypotheses(case_id)
        contradictions = self.list_contradictions(case_id)
        edges = self.list_edges(case_id)
        top_edges = sorted(edges, key=lambda e: float(e.get("confidence") or 0), reverse=True)[:8]
        lines = [
            "Build 22.0 Provider Integration Pro – Analyse-Narrativ.",
            "Alle Aussagen sind Kandidaten oder geprüfte OSINT-Beziehungen und ersetzen keine menschliche Bewertung.",
            f"Graphbestand: {dash['nodes']} Knoten, {dash['edges']} Kanten.",
            f"Hypothesen: {dash.get('hypotheses', {})}.",
            f"Offene Widersprüche/Gegenbelege: {dash.get('contradictions', [])}.",
            "Stärkste Beziehungen:",
        ]
        for e in top_edges:
            exp = self.explain_edge(e["edge_id"])
            lines.append(f"- {exp['source_node']['label']} --{exp['relationship']} ({exp['confidence']})--> {exp['target_node']['label']} | {exp['explanation']}")
        if hypotheses:
            lines.append("Hypothesenübersicht:")
            for h in hypotheses[:8]:
                lines.append(f"- [{h.get('status')}/{h.get('confidence')}] {h.get('title')}: {h.get('statement')}")
        if contradictions:
            lines.append("Widerspruchs-/Gegenbelegübersicht:")
            for c in contradictions[:8]:
                lines.append(f"- [{c.get('severity')}/{c.get('status')}] {c.get('title')}: {c.get('description')}")
        nid = new_id("narr")
        ts = now_ts()
        body = "\n".join(lines)
        self.db.execute("""INSERT INTO analysis_narratives(narrative_id,case_id,narrative_type,title,body,confidence_summary,source_object_ids_json,created_at,updated_at,analyst)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [nid, case_id, "graph", title, body, "candidate_with_human_review", dumps([e.get("edge_id") for e in top_edges]), ts, ts, "local-analyst"])
        self.audit.log("create", "analysis_narrative", nid, case_id, {"type": "graph", "title": title})
        return self.db.one("SELECT * FROM analysis_narratives WHERE narrative_id=?", [nid])

    def export_graph_bundle(self, case_id: str) -> Dict[str, Any]:
        return {
            "case_id": case_id,
            "generated_at": now_ts(),
            "dashboard": self.graph_dashboard(case_id),
            "nodes": self.list_nodes(case_id),
            "edges": [self.explain_edge(e["edge_id"]) for e in self.list_edges(case_id)],
            "hypotheses": self.list_hypotheses(case_id),
            "contradictions": self.list_contradictions(case_id),
        }
