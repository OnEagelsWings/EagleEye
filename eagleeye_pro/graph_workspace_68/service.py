from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class GraphWorkspace68Service:
    """Build 68.0 investigation graph workspace foundation."""
    NODE_TYPES = {"person", "alias", "email", "username", "phone", "domain", "url", "organization", "location", "source", "capture", "finding", "claim", "document", "hypothesis", "ip_address", "archive_snapshot", "repository"}
    EDGE_TYPES = {"mentions", "belongs_to_possible", "belongs_to_reviewed", "supports", "contradicts", "derived_from", "captured_from", "same_as_candidate", "same_as_rejected", "worked_for", "associated_with", "resolves_to", "registered_to_candidate", "archived_as", "profile_on"}

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS investigation_graph_nodes_68 (
          node_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, node_type TEXT NOT NULL,
          label TEXT NOT NULL, value TEXT DEFAULT '', confidence INTEGER DEFAULT 50,
          sensitivity TEXT DEFAULT 'normal', source_ref TEXT DEFAULT '', metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_graph68_case ON investigation_graph_nodes_68(case_id,node_type,label);
        CREATE TABLE IF NOT EXISTS investigation_graph_edges_68 (
          edge_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_node_id TEXT NOT NULL,
          target_node_id TEXT NOT NULL, edge_type TEXT NOT NULL, confidence INTEGER DEFAULT 50,
          review_status TEXT DEFAULT 'candidate', evidence_ref TEXT DEFAULT '', metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_graph68_edges_case ON investigation_graph_edges_68(case_id,source_node_id,target_node_id);
        """)
        self.db.conn.commit()

    def add_node(self, case_id: str, node_type: str, label: str, value: str = "", confidence: int = 50, sensitivity: str = "normal", source_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if node_type not in self.NODE_TYPES:
            raise ValueError(f"unsupported node_type: {node_type}")
        nid = new_id("g68n")
        ts = now_ts()
        self.db.execute("""INSERT INTO investigation_graph_nodes_68(node_id,case_id,node_type,label,value,confidence,sensitivity,source_ref,metadata_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [nid, case_id, node_type, label.strip(), value, max(0, min(100, int(confidence))), sensitivity, source_ref, dumps(metadata or {}), ts, ts])
        self.audit.log("add", "graph_node_68", nid, case_id, {"node_type": node_type, "label": label})
        return self.get_node(nid)

    def add_edge(self, case_id: str, source_node_id: str, target_node_id: str, edge_type: str, confidence: int = 50, review_status: str = "candidate", evidence_ref: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if edge_type not in self.EDGE_TYPES:
            raise ValueError(f"unsupported edge_type: {edge_type}")
        if not self.get_node(source_node_id) or not self.get_node(target_node_id):
            raise KeyError("source or target node not found")
        eid = new_id("g68e")
        self.db.execute("""INSERT INTO investigation_graph_edges_68(edge_id,case_id,source_node_id,target_node_id,edge_type,confidence,review_status,evidence_ref,metadata_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [eid, case_id, source_node_id, target_node_id, edge_type, max(0, min(100, int(confidence))), review_status, evidence_ref, dumps(metadata or {}), now_ts()])
        self.audit.log("add", "graph_edge_68", eid, case_id, {"edge_type": edge_type, "source": source_node_id, "target": target_node_id})
        return self.get_edge(eid)

    def get_node(self, node_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_graph_nodes_68 WHERE node_id=?", [node_id])
        if not row:
            raise KeyError(node_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def get_edge(self, edge_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_graph_edges_68 WHERE edge_id=?", [edge_id])
        if not row:
            raise KeyError(edge_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def build_graph(self, case_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT * FROM investigation_graph_nodes_68 WHERE case_id=? ORDER BY created_at", [case_id])
        edges = self.db.all("SELECT * FROM investigation_graph_edges_68 WHERE case_id=? ORDER BY created_at", [case_id])
        for n in nodes:
            n["metadata"] = loads(n.pop("metadata_json", "{}"), {})
        for e in edges:
            e["metadata"] = loads(e.pop("metadata_json", "{}"), {})
        return {"case_id": case_id, "nodes": nodes, "edges": edges, "metrics": self.metrics(case_id)}

    def metrics(self, case_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT node_type, confidence FROM investigation_graph_nodes_68 WHERE case_id=?", [case_id])
        edges = self.db.all("SELECT edge_type, review_status, confidence FROM investigation_graph_edges_68 WHERE case_id=?", [case_id])
        node_types = sorted({n["node_type"] for n in nodes})
        reviewed_edges = [e for e in edges if e.get("review_status") in {"reviewed", "accepted", "rejected"}]
        readiness = min(100, int(len(nodes) * 5 + len(edges) * 8 + len(reviewed_edges) * 8 + len(node_types) * 4))
        return {"node_count": len(nodes), "edge_count": len(edges), "node_types": node_types, "reviewed_edge_count": len(reviewed_edges), "graph_readiness": readiness}
