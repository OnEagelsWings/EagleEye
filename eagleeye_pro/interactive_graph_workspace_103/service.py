from __future__ import annotations

import html as html_lib
import json
import math
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class InteractiveGraphWorkspace103Service:
    """Build 103.0: Interactive Graph Workspace Pro.

    This layer turns the existing graph model into a practical analyst workspace:
    - synchronizes graph nodes/edges from Browser Capture 102, Copy-Paste Intake 91,
      Evidence Vault 75 and Claim Engine 80;
    - renders a local, dependency-free HTML workspace with node/edge lists, SVG map,
      risk warnings and review forms;
    - lets analysts add nodes/edges and review candidate edges without treating them as facts.
    """

    HIGH_RISK_EDGE_TYPES = {"same_as_candidate", "belongs_to_possible", "associated_with"}
    SAFE_REVIEW_STATUSES = {"candidate", "needs_review", "accepted", "rejected", "disputed", "reviewed"}
    NODE_TYPES = {"person", "alias", "email", "username", "phone", "domain", "url", "organization", "location", "source", "capture", "finding", "claim", "document", "hypothesis"}
    EDGE_TYPES = {"mentions", "belongs_to_possible", "belongs_to_reviewed", "supports", "contradicts", "derived_from", "captured_from", "same_as_candidate", "same_as_rejected", "worked_for", "associated_with"}

    def __init__(
        self,
        db: Database,
        audit: AuditService,
        *,
        graph: Any = None,
        analytics: Any = None,
        security: Any = None,
        local_ai: Any = None,
        review_board: Any = None,
        workspace_actions: Any = None,
    ):
        self.db = db
        self.audit = audit
        self.graph = graph
        self.analytics = analytics
        self.security = security
        self.local_ai = local_ai
        self.review_board = review_board
        self.workspace_actions = workspace_actions
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_workspace_sessions_103(
              session_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              node_count INTEGER NOT NULL,
              edge_count INTEGER NOT NULL,
              unreviewed_edge_count INTEGER NOT NULL,
              high_risk_edge_count INTEGER NOT NULL,
              readiness_score INTEGER NOT NULL,
              security_decision TEXT DEFAULT '',
              analytics_json TEXT NOT NULL,
              warnings_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_graphws103_case ON graph_workspace_sessions_103(case_id, created_at);

            CREATE TABLE IF NOT EXISTS graph_review_actions_103(
              action_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT NOT NULL,
              decision TEXT NOT NULL,
              reason TEXT DEFAULT '',
              actor TEXT DEFAULT 'local-analyst',
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_graphreview103_case ON graph_review_actions_103(case_id, created_at);
            """
        )
        self.db.conn.commit()

    # ---------- public API ----------
    def build_workspace(self, case_id: str, *, sync_sources: bool = True, persist: bool = True) -> Dict[str, Any]:
        if not case_id:
            case_id = self._ensure_default_case()
        if sync_sources:
            self.sync_from_sources(case_id)
        graph = self._graph(case_id)
        warnings = self._warnings(graph)
        analytics = self._analytics(case_id)
        security_decision = "not_run"
        if self.security:
            try:
                sec = self.security.assess_case_security(case_id, scope="interactive_graph_workspace_103")
                security_decision = sec.get("decision") or sec.get("status") or "review_required"
            except Exception as exc:
                warnings.append({"level": "medium", "code": "security_check_failed", "message": str(exc)})
                security_decision = "review_required"
        metrics = graph.get("metrics") or {}
        readiness = self._readiness(graph, warnings, security_decision)
        session = {
            "session_id": new_id("gws103"),
            "case_id": case_id,
            "build": "103.0",
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "unreviewed_edge_count": len([e for e in graph.get("edges", []) if e.get("review_status") in {"candidate", "needs_review", ""}]),
            "high_risk_edge_count": len([e for e in graph.get("edges", []) if e.get("edge_type") in self.HIGH_RISK_EDGE_TYPES and e.get("review_status") not in {"accepted", "rejected"}]),
            "readiness_score": readiness,
            "security_decision": security_decision,
            "analytics": analytics,
            "warnings": warnings,
            "graph_metrics": metrics,
            "created_at": now_ts(),
        }
        if persist:
            self.db.execute(
                """INSERT INTO graph_workspace_sessions_103(session_id,case_id,node_count,edge_count,unreviewed_edge_count,high_risk_edge_count,readiness_score,security_decision,analytics_json,warnings_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [session["session_id"], case_id, session["node_count"], session["edge_count"], session["unreviewed_edge_count"], session["high_risk_edge_count"], readiness, security_decision, dumps(analytics), dumps(warnings), session["created_at"]],
            )
            self.audit.log("build", "interactive_graph_workspace_103", session["session_id"], case_id, {"readiness_score": readiness, "warnings": len(warnings)})
        return session | {"graph": graph}

    def latest(self, case_id: str = "") -> Dict[str, Any]:
        if case_id:
            row = self.db.one("SELECT * FROM graph_workspace_sessions_103 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        else:
            row = self.db.one("SELECT * FROM graph_workspace_sessions_103 ORDER BY created_at DESC LIMIT 1")
        if not row:
            return {}
        row["analytics"] = loads(row.pop("analytics_json", "{}"), {})
        row["warnings"] = loads(row.pop("warnings_json", "[]"), [])
        return row

    def add_node(self, case_id: str, node_type: str, label: str, *, value: str = "", confidence: int = 50, sensitivity: str = "normal", source_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not case_id:
            case_id = self._ensure_default_case()
        node = self._upsert_node(case_id, node_type, label, value=value, confidence=confidence, sensitivity=sensitivity, source_ref=source_ref, metadata={"manual_103": True, **(metadata or {})})
        self.audit.log("add", "graph_node_103", node["node_id"], case_id, {"node_type": node_type, "label": label})
        return node

    def add_edge(self, case_id: str, source_node_id: str, target_node_id: str, edge_type: str, *, confidence: int = 50, review_status: str = "candidate", evidence_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not case_id:
            src = self._node(source_node_id)
            case_id = src.get("case_id", "")
        edge = self._upsert_edge(case_id, source_node_id, target_node_id, edge_type, confidence=confidence, review_status=review_status, evidence_ref=evidence_ref, metadata={"manual_103": True, **(metadata or {})})
        self.audit.log("add", "graph_edge_103", edge["edge_id"], case_id, {"edge_type": edge_type, "review_status": review_status})
        return edge

    def review_edge(self, case_id: str, edge_id: str, decision: str, *, reason: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        if decision not in {"accepted", "rejected", "disputed", "needs_review", "reviewed"}:
            raise ValueError("decision must be accepted, rejected, disputed, needs_review or reviewed")
        edge = self._edge(edge_id)
        case_id = case_id or edge.get("case_id", "")
        new_status = decision
        new_conf = int(edge.get("confidence", 50) or 50)
        if decision == "accepted":
            new_conf = max(new_conf, 75)
        elif decision == "rejected":
            new_conf = min(new_conf, 10)
        elif decision == "disputed":
            new_conf = min(new_conf, 35)
        self.db.execute("UPDATE investigation_graph_edges_68 SET review_status=?, confidence=? WHERE edge_id=?", [new_status, new_conf, edge_id])
        action_id = new_id("grev103")
        self.db.execute(
            "INSERT INTO graph_review_actions_103(action_id,case_id,object_type,object_id,decision,reason,actor,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [action_id, case_id, "graph_edge_68", edge_id, decision, reason, actor, dumps({"previous_status": edge.get("review_status"), "previous_confidence": edge.get("confidence")}), now_ts()],
        )
        self.audit.log("review", "graph_edge_103", edge_id, case_id, {"decision": decision, "reason": reason, "actor": actor})
        return {"action_id": action_id, "edge": self._edge(edge_id), "decision": decision, "case_id": case_id}

    def sync_from_sources(self, case_id: str) -> Dict[str, Any]:
        created_nodes = created_edges = 0
        # Browser captures: URL -> capture -> evidence/source links
        if self._table_exists("browser_captures_102"):
            for cap in self.db.all("SELECT * FROM browser_captures_102 WHERE case_id=? ORDER BY created_at", [case_id]):
                url = cap.get("canonical_url") or cap.get("url") or ""
                title = cap.get("title") or url or cap.get("bridge_capture_id")
                url_node, n1 = self._upsert_node_changed(case_id, "url", url or title, value=url, confidence=70, source_ref=url, metadata={"source": "browser_capture_102", "bridge_capture_id": cap.get("bridge_capture_id")})
                cap_node, n2 = self._upsert_node_changed(case_id, "capture", title, value=cap.get("bridge_capture_id", ""), confidence=75, source_ref=url, metadata={"source": "browser_capture_102", "status": cap.get("status"), "security_decision": cap.get("security_decision")})
                if n1: created_nodes += 1
                if n2: created_nodes += 1
                if self._upsert_edge_changed(case_id, cap_node["node_id"], url_node["node_id"], "captured_from", confidence=75, review_status="candidate", evidence_ref=cap.get("evidence_id", ""), metadata={"source": "browser_capture_102"}):
                    created_edges += 1
                if cap.get("evidence_id"):
                    ev_node, n3 = self._upsert_node_changed(case_id, "document", f"Evidence {cap.get('evidence_id')}", value=cap.get("evidence_id"), confidence=80, source_ref=url, metadata={"source": "local_evidence_75", "linked_from": "browser_capture_102"})
                    if n3: created_nodes += 1
                    if self._upsert_edge_changed(case_id, ev_node["node_id"], cap_node["node_id"], "derived_from", confidence=80, review_status="candidate", evidence_ref=cap.get("evidence_id", ""), metadata={"source": "browser_capture_102"}):
                        created_edges += 1
        # Copy-paste findings
        if self._table_exists("pasted_findings_91"):
            for pf in self.db.all("SELECT * FROM pasted_findings_91 WHERE case_id=? ORDER BY created_at", [case_id]):
                title = pf.get("title") or pf.get("canonical_url") or pf.get("paste_id")
                find_node, n1 = self._upsert_node_changed(case_id, "finding", title, value=pf.get("paste_id", ""), confidence=55, source_ref=pf.get("canonical_url") or pf.get("url") or "", metadata={"source": "copy_paste_intake_91", "status": pf.get("status"), "classification": pf.get("classification"), "excerpt": pf.get("content_excerpt", "")[:280]})
                if n1: created_nodes += 1
                if pf.get("canonical_url") or pf.get("url"):
                    url = pf.get("canonical_url") or pf.get("url")
                    url_node, n2 = self._upsert_node_changed(case_id, "url", url, value=url, confidence=60, source_ref=url, metadata={"source": "copy_paste_intake_91"})
                    if n2: created_nodes += 1
                    if self._upsert_edge_changed(case_id, find_node["node_id"], url_node["node_id"], "captured_from", confidence=55, review_status="candidate", evidence_ref=pf.get("evidence_id", ""), metadata={"source": "copy_paste_intake_91"}):
                        created_edges += 1
        # Claims
        if self._table_exists("claims_v3_80"):
            for cl in self.db.all("SELECT * FROM claims_v3_80 WHERE case_id=? ORDER BY created_at", [case_id]):
                claim_node, n1 = self._upsert_node_changed(case_id, "claim", cl.get("statement", "")[:180], value=cl.get("claim_id", ""), confidence=self._claim_confidence(cl.get("grade", "")), source_ref=cl.get("claim_id", ""), metadata={"source": "claim_engine_v3_80", "grade": cl.get("grade"), "review_status": cl.get("review_status")})
                if n1: created_nodes += 1
                for ref in loads(cl.get("support_refs_json", "[]"), []):
                    ref_node = self._find_node_by_value(case_id, str(ref)) or self._find_node_by_label(case_id, str(ref))
                    if ref_node and self._upsert_edge_changed(case_id, claim_node["node_id"], ref_node["node_id"], "supports", confidence=60, review_status="candidate", evidence_ref=str(ref), metadata={"source": "claim_engine_v3_80"}):
                        created_edges += 1
                for ref in loads(cl.get("contra_refs_json", "[]"), []):
                    ref_node = self._find_node_by_value(case_id, str(ref)) or self._find_node_by_label(case_id, str(ref))
                    if ref_node and self._upsert_edge_changed(case_id, claim_node["node_id"], ref_node["node_id"], "contradicts", confidence=60, review_status="candidate", evidence_ref=str(ref), metadata={"source": "claim_engine_v3_80"}):
                        created_edges += 1
        self.audit.log("sync", "interactive_graph_workspace_103", case_id, case_id, {"created_nodes": created_nodes, "created_edges": created_edges})
        return {"case_id": case_id, "created_nodes": created_nodes, "created_edges": created_edges, "status": "synced"}

    def render_html(self, case_id: str = "", *, message: str = "", result: Dict[str, Any] | None = None) -> str:
        if not case_id:
            latest = self.latest("")
            case_id = latest.get("case_id", "") if latest else ""
        workspace = self.build_workspace(case_id or self._ensure_default_case(), sync_sources=True, persist=True)
        graph = workspace["graph"]
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        node_by_id = {n["node_id"]: n for n in nodes}
        svg = self._svg(nodes, edges)
        warnings_html = "".join(f"<li><b>{html_lib.escape(w.get('level',''))}</b> {html_lib.escape(w.get('code',''))}: {html_lib.escape(w.get('message',''))}</li>" for w in workspace.get("warnings", [])) or "<li>Keine kritischen Graph-Warnungen.</li>"
        edge_rows = []
        for e in edges:
            s = node_by_id.get(e.get("source_node_id"), {})
            t = node_by_id.get(e.get("target_node_id"), {})
            risk = " high-risk" if e.get("edge_type") in self.HIGH_RISK_EDGE_TYPES and e.get("review_status") not in {"accepted", "rejected"} else ""
            edge_rows.append(f"""
<tr class="{risk.strip()}"><td><code>{html_lib.escape(e.get('edge_id',''))}</code></td><td>{html_lib.escape(e.get('edge_type',''))}</td><td>{html_lib.escape(s.get('label','?'))}</td><td>{html_lib.escape(t.get('label','?'))}</td><td>{html_lib.escape(e.get('review_status',''))}</td><td>{html_lib.escape(str(e.get('confidence','')))}</td><td>
<form method="post" action="/review-edge"><input type="hidden" name="case_id" value="{html_lib.escape(case_id)}"><input type="hidden" name="edge_id" value="{html_lib.escape(e.get('edge_id',''))}"><select name="decision"><option>accepted</option><option>rejected</option><option>disputed</option><option>needs_review</option></select><input name="reason" placeholder="Grund" style="width:180px"><button>Review</button></form></td></tr>""")
        node_rows = "".join(f"<tr><td><code>{html_lib.escape(n.get('node_id',''))}</code></td><td>{html_lib.escape(n.get('node_type',''))}</td><td>{html_lib.escape(n.get('label',''))}</td><td>{html_lib.escape(str(n.get('confidence','')))}</td><td>{html_lib.escape(n.get('source_ref',''))}</td></tr>" for n in nodes)
        result_html = ""
        if result is not None:
            result_html = "<h2>Letzte Aktion</h2><pre>" + html_lib.escape(json.dumps(result, ensure_ascii=False, indent=2, default=str)) + "</pre>"
        msg_html = f'<p class="msg">{html_lib.escape(message)}</p>' if message else ""
        node_options = "".join(f"<option value='{html_lib.escape(n['node_id'])}'>{html_lib.escape(n['node_type'] + ': ' + n['label'][:80])}</option>" for n in nodes)
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>EagleEye Interactive Graph Workspace 103</title>
<style>body{{font-family:Arial,sans-serif;margin:28px;max-width:1400px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}textarea,input,select{{padding:7px;margin:4px}}button{{padding:7px 12px;font-weight:bold}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #ddd;padding:6px;vertical-align:top;text-align:left}}pre,code{{background:#f4f4f4}}pre{{white-space:pre-wrap;border:1px solid #ddd;padding:12px}}.warn{{background:#fff7dc;border:1px solid #e2c36a;padding:12px}}.msg{{background:#eef7ee;border:1px solid #9c9;padding:10px}}.high-risk td{{background:#fff0f0}}.card{{border:1px solid #ddd;padding:12px;margin:12px 0}}</style></head><body>
<h1>EagleEye Interactive Graph Workspace 103</h1>
<div class="warn"><b>Review-first:</b> Graph-Kanten wie <code>same_as_candidate</code>, <code>belongs_to_possible</code> und <code>associated_with</code> sind Kandidaten, keine Fakten. Keine Personenbehauptung ohne Identitäts- und Claim-Review.</div>
{msg_html}
<div class="grid"><div class="card"><h2>Fallstatus</h2><p><b>Case:</b> <code>{html_lib.escape(case_id)}</code><br><b>Nodes:</b> {workspace['node_count']} &nbsp; <b>Edges:</b> {workspace['edge_count']} &nbsp; <b>Unreviewed:</b> {workspace['unreviewed_edge_count']} &nbsp; <b>High-risk:</b> {workspace['high_risk_edge_count']}<br><b>Readiness:</b> {workspace['readiness_score']} / 100 &nbsp; <b>Security:</b> {html_lib.escape(workspace.get('security_decision',''))}</p><h3>Warnungen</h3><ul>{warnings_html}</ul></div><div class="card"><h2>Graph Map</h2>{svg}</div></div>
{result_html}
<div class="grid"><div class="card"><h2>Knoten hinzufügen</h2><form method="post" action="/add-node"><input type="hidden" name="case_id" value="{html_lib.escape(case_id)}"><select name="node_type">{''.join(f'<option>{t}</option>' for t in sorted(self.NODE_TYPES))}</select><input name="label" placeholder="Label" required><input name="value" placeholder="Wert optional"><input name="source_ref" placeholder="Quelle optional"><button>Knoten speichern</button></form></div>
<div class="card"><h2>Kante hinzufügen</h2><form method="post" action="/add-edge"><input type="hidden" name="case_id" value="{html_lib.escape(case_id)}"><select name="source_node_id">{node_options}</select><select name="target_node_id">{node_options}</select><select name="edge_type">{''.join(f'<option>{t}</option>' for t in sorted(self.EDGE_TYPES))}</select><select name="review_status"><option>candidate</option><option>needs_review</option><option>accepted</option><option>rejected</option></select><input name="evidence_ref" placeholder="Evidence/Source ref"><button>Kante speichern</button></form></div></div>
<h2>Edges / Review Queue</h2><table><tr><th>ID</th><th>Typ</th><th>Von</th><th>Nach</th><th>Status</th><th>Conf.</th><th>Aktion</th></tr>{''.join(edge_rows) or '<tr><td colspan="7">Keine Kanten.</td></tr>'}</table>
<h2>Nodes</h2><table><tr><th>ID</th><th>Typ</th><th>Label</th><th>Conf.</th><th>Quelle</th></tr>{node_rows or '<tr><td colspan="5">Keine Knoten.</td></tr>'}</table>
</body></html>'''

    # ---------- internals ----------
    def _graph(self, case_id: str) -> Dict[str, Any]:
        if self.graph:
            return self.graph.build_graph(case_id)
        nodes = self.db.all("SELECT * FROM investigation_graph_nodes_68 WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("investigation_graph_nodes_68") else []
        edges = self.db.all("SELECT * FROM investigation_graph_edges_68 WHERE case_id=? ORDER BY created_at", [case_id]) if self._table_exists("investigation_graph_edges_68") else []
        for n in nodes: n["metadata"] = loads(n.pop("metadata_json", "{}"), {})
        for e in edges: e["metadata"] = loads(e.pop("metadata_json", "{}"), {})
        return {"case_id": case_id, "nodes": nodes, "edges": edges, "metrics": {"node_count": len(nodes), "edge_count": len(edges)}}

    def _analytics(self, case_id: str) -> Dict[str, Any]:
        if self.analytics:
            try:
                return self.analytics.analyze(case_id)
            except Exception as exc:
                return {"available": False, "error": str(exc)}
        return {"available": False}

    def _warnings(self, graph: Dict[str, Any]) -> List[Dict[str, str]]:
        warnings: List[Dict[str, str]] = []
        edges = graph.get("edges", [])
        nodes = graph.get("nodes", [])
        high = [e for e in edges if e.get("edge_type") in self.HIGH_RISK_EDGE_TYPES and e.get("review_status") not in {"accepted", "rejected"}]
        if high:
            warnings.append({"level": "high", "code": "high_risk_identity_edges_unreviewed", "message": f"{len(high)} riskante Identitäts-/Assoziationskanten sind noch nicht final reviewed."})
        unreviewed = [e for e in edges if e.get("review_status") in {"candidate", "needs_review", ""}]
        if unreviewed:
            warnings.append({"level": "medium", "code": "candidate_edges_need_review", "message": f"{len(unreviewed)} Kanten sind Recherchekandidaten und brauchen Review."})
        if not nodes:
            warnings.append({"level": "medium", "code": "empty_graph", "message": "Der Fallgraph ist leer; zuerst Captures, Funde oder manuelle Knoten hinzufügen."})
        return warnings

    def _readiness(self, graph: Dict[str, Any], warnings: List[Dict[str, str]], security_decision: str) -> int:
        nodes = len(graph.get("nodes", [])); edges = len(graph.get("edges", []))
        accepted = len([e for e in graph.get("edges", []) if e.get("review_status") == "accepted"])
        high = len([w for w in warnings if w.get("level") == "high"])
        score = min(100, nodes * 4 + edges * 5 + accepted * 8)
        score -= high * 15
        if security_decision in {"blocked", "critical_review_required"}: score -= 25
        if security_decision == "review_required": score -= 8
        return max(0, int(score))

    def _upsert_node_changed(self, *args, **kwargs) -> Tuple[Dict[str, Any], bool]:
        before = self._find_node(args[0], args[1], args[2], kwargs.get("value", ""))
        node = self._upsert_node(*args, **kwargs)
        return node, before is None

    def _upsert_node(self, case_id: str, node_type: str, label: str, *, value: str = "", confidence: int = 50, sensitivity: str = "normal", source_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if node_type not in self.NODE_TYPES:
            raise ValueError(f"unsupported node_type: {node_type}")
        label = (label or value or node_type).strip()[:240]
        existing = self._find_node(case_id, node_type, label, value)
        if existing:
            merged = existing.get("metadata", {}) | (metadata or {})
            self.db.execute("UPDATE investigation_graph_nodes_68 SET confidence=?, source_ref=COALESCE(NULLIF(?,''),source_ref), metadata_json=?, updated_at=? WHERE node_id=?", [max(int(existing.get("confidence", 50)), int(confidence)), source_ref, dumps(merged), now_ts(), existing["node_id"]])
            return self._node(existing["node_id"])
        nid = new_id("g68n")
        ts = now_ts()
        self.db.execute("""INSERT INTO investigation_graph_nodes_68(node_id,case_id,node_type,label,value,confidence,sensitivity,source_ref,metadata_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [nid, case_id, node_type, label, value, max(0, min(100, int(confidence))), sensitivity, source_ref, dumps(metadata or {}), ts, ts])
        return self._node(nid)

    def _upsert_edge_changed(self, *args, **kwargs) -> bool:
        before = self._find_edge(args[0], args[1], args[2], args[3])
        self._upsert_edge(*args, **kwargs)
        return before is None

    def _upsert_edge(self, case_id: str, source_node_id: str, target_node_id: str, edge_type: str, *, confidence: int = 50, review_status: str = "candidate", evidence_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if edge_type not in self.EDGE_TYPES:
            raise ValueError(f"unsupported edge_type: {edge_type}")
        existing = self._find_edge(case_id, source_node_id, target_node_id, edge_type)
        if existing:
            merged = existing.get("metadata", {}) | (metadata or {})
            self.db.execute("UPDATE investigation_graph_edges_68 SET confidence=?, review_status=?, evidence_ref=COALESCE(NULLIF(?,''), evidence_ref), metadata_json=? WHERE edge_id=?", [max(int(existing.get("confidence", 50)), int(confidence)), existing.get("review_status") if existing.get("review_status") not in {"", "candidate"} else review_status, evidence_ref, dumps(merged), existing["edge_id"]])
            return self._edge(existing["edge_id"])
        eid = new_id("g68e")
        self.db.execute("""INSERT INTO investigation_graph_edges_68(edge_id,case_id,source_node_id,target_node_id,edge_type,confidence,review_status,evidence_ref,metadata_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [eid, case_id, source_node_id, target_node_id, edge_type, max(0, min(100, int(confidence))), review_status, evidence_ref, dumps(metadata or {}), now_ts()])
        return self._edge(eid)

    def _find_node(self, case_id: str, node_type: str, label: str, value: str = "") -> Dict[str, Any] | None:
        row = None
        if value:
            row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND node_type=? AND value=? LIMIT 1", [case_id, node_type, value])
        if not row:
            row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND node_type=? AND label=? LIMIT 1", [case_id, node_type, (label or value or node_type).strip()[:240]])
        return self._node(row["node_id"]) if row else None

    def _find_node_by_value(self, case_id: str, value: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND value=? LIMIT 1", [case_id, value])
        return self._node(row["node_id"]) if row else None

    def _find_node_by_label(self, case_id: str, label: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT node_id FROM investigation_graph_nodes_68 WHERE case_id=? AND label=? LIMIT 1", [case_id, label])
        return self._node(row["node_id"]) if row else None

    def _find_edge(self, case_id: str, source_node_id: str, target_node_id: str, edge_type: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT edge_id FROM investigation_graph_edges_68 WHERE case_id=? AND source_node_id=? AND target_node_id=? AND edge_type=? LIMIT 1", [case_id, source_node_id, target_node_id, edge_type])
        return self._edge(row["edge_id"]) if row else None

    def _node(self, node_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_graph_nodes_68 WHERE node_id=?", [node_id])
        if not row: raise KeyError(node_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def _edge(self, edge_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_graph_edges_68 WHERE edge_id=?", [edge_id])
        if not row: raise KeyError(edge_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))

    def _claim_confidence(self, grade: str) -> int:
        return {"strongly_supported": 80, "partially_supported": 65, "weakly_supported": 45, "unverified_hint": 25, "needs_manual_review": 35, "contradicted": 20, "rejected": 5}.get(grade, 40)

    def _ensure_default_case(self) -> str:
        row = self.db.one("SELECT case_id FROM cases WHERE title=? ORDER BY created_at DESC LIMIT 1", ["Interactive Graph Workspace Case"])
        if row: return row["case_id"]
        cid = new_id("case"); ts = now_ts()
        self.db.execute("""INSERT INTO cases(case_id,title,client,purpose,legal_basis,jurisdiction,risk_level,status,retention_until,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [cid, "Interactive Graph Workspace Case", "Local Analyst", "Public-only graph investigation workspace", "legitimate_interest / manual review required", "DE/EU", "medium", "draft", "", ts, ts])
        self.audit.log("create", "case", cid, cid, {"via": "interactive_graph_workspace_103_default_case"})
        return cid

    def _svg(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        if not nodes:
            return "<p>No graph nodes yet.</p>"
        w, h = 560, 360
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.36
        pos = {}
        for i, n in enumerate(nodes[:60]):
            a = 2 * math.pi * i / max(1, min(len(nodes), 60))
            pos[n["node_id"]] = (cx + r * math.cos(a), cy + r * math.sin(a))
        parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="border:1px solid #ddd;background:#fafafa">']
        for e in edges[:120]:
            if e.get("source_node_id") in pos and e.get("target_node_id") in pos:
                x1,y1 = pos[e["source_node_id"]]; x2,y2 = pos[e["target_node_id"]]
                stroke = "#c33" if e.get("edge_type") in self.HIGH_RISK_EDGE_TYPES and e.get("review_status") not in {"accepted", "rejected"} else "#777"
                dash = "4 3" if e.get("review_status") in {"candidate", "needs_review", ""} else ""
                parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1.6" stroke-dasharray="{dash}"/>')
        for n in nodes[:60]:
            x,y = pos[n["node_id"]]
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#fff" stroke="#333"/><text x="{x+14:.1f}" y="{y+4:.1f}" font-size="10">{html_lib.escape(n.get("node_type","") + ":" + n.get("label","")[:22])}</text>')
        parts.append("</svg>")
        return "".join(parts)
