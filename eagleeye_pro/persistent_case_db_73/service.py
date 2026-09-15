from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class PersistentCaseDB73Service:
    """Build 73.0 canonical persistent case database v2.

    Creates a durable domain layer above legacy tables: entities, identifiers,
    sources, captures, findings, claims, graph refs, review decisions, export
    decisions, audit refs and artifacts. Existing Build 68/69/72 objects can be
    indexed into this model without data loss.
    """
    OBJECT_TYPES = {"case", "person_entity", "identifier", "source", "capture", "artifact", "finding", "claim", "graph_node", "graph_edge", "review_decision", "export_decision", "audit_event"}

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS canonical_case_objects_73 (
          object_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, label TEXT NOT NULL,
          status TEXT DEFAULT 'active', source_table TEXT DEFAULT '', source_id TEXT DEFAULT '', data_json TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_caseobj73_source ON canonical_case_objects_73(source_table, source_id);
        CREATE INDEX IF NOT EXISTS idx_caseobj73_case_type ON canonical_case_objects_73(case_id, object_type, status);
        CREATE TABLE IF NOT EXISTS canonical_case_links_73 (
          link_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_object_id TEXT NOT NULL, target_object_id TEXT NOT NULL,
          relation TEXT NOT NULL, confidence INTEGER DEFAULT 50, review_status TEXT DEFAULT 'candidate', data_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_caselinks73_case ON canonical_case_links_73(case_id, relation);
        """)
        self.db.conn.commit()

    def upsert_object(self, case_id: str, object_type: str, label: str, data: Dict[str, Any] | None = None, status: str = "active", source_table: str = "", source_id: str = "") -> Dict[str, Any]:
        if object_type not in self.OBJECT_TYPES:
            raise ValueError(f"unsupported object_type: {object_type}")
        existing = self.db.one("SELECT object_id FROM canonical_case_objects_73 WHERE source_table=? AND source_id=? AND source_table!='' AND source_id!=''", [source_table, source_id])
        ts = now_ts()
        if existing:
            oid = existing["object_id"]
            self.db.execute("UPDATE canonical_case_objects_73 SET label=?,status=?,data_json=?,updated_at=? WHERE object_id=?", [label, status, dumps(data or {}), ts, oid])
        else:
            oid = new_id("obj73")
            self.db.execute("INSERT INTO canonical_case_objects_73(object_id,case_id,object_type,label,status,source_table,source_id,data_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", [oid, case_id, object_type, label, status, source_table, source_id, dumps(data or {}), ts, ts])
        self.audit.log("upsert", "canonical_case_object_73", oid, case_id, {"object_type": object_type, "label": label})
        return self.get_object(oid)

    def link_objects(self, case_id: str, source_object_id: str, target_object_id: str, relation: str, confidence: int = 50, review_status: str = "candidate", data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        lid = new_id("lnk73")
        self.db.execute("INSERT INTO canonical_case_links_73(link_id,case_id,source_object_id,target_object_id,relation,confidence,review_status,data_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [lid, case_id, source_object_id, target_object_id, relation, max(0, min(100, int(confidence))), review_status, dumps(data or {}), now_ts()])
        self.audit.log("link", "canonical_case_link_73", lid, case_id, {"relation": relation, "source": source_object_id, "target": target_object_id})
        return self.get_link(lid)

    def index_existing_case(self, case_id: str) -> Dict[str, Any]:
        created: List[str] = []
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if case:
            created.append(self.upsert_object(case_id, "case", case.get("title", case_id), case, source_table="cases", source_id=case_id)["object_id"])
        for t in self.db.all("SELECT * FROM targets WHERE case_id=?", [case_id]):
            created.append(self.upsert_object(case_id, "person_entity", t.get("name", "target"), t, source_table="targets", source_id=t["target_id"])["object_id"])
        for n in self.db.all("SELECT * FROM investigation_graph_nodes_68 WHERE case_id=?", [case_id]):
            created.append(self.upsert_object(case_id, "graph_node", n.get("label", n["node_id"]), n, source_table="investigation_graph_nodes_68", source_id=n["node_id"])["object_id"])
        for e in self.db.all("SELECT * FROM investigation_graph_edges_68 WHERE case_id=?", [case_id]):
            created.append(self.upsert_object(case_id, "graph_edge", e.get("edge_type", e["edge_id"]), e, source_table="investigation_graph_edges_68", source_id=e["edge_id"])["object_id"])
        for c in self.db.all("SELECT * FROM capture_artifacts_69 WHERE case_id=?", [case_id]):
            created.append(self.upsert_object(case_id, "capture", c.get("title", c["artifact_id"]), c, source_table="capture_artifacts_69", source_id=c["artifact_id"])["object_id"])
        for cl in self.db.all("SELECT * FROM claim_reviews_72 WHERE case_id=?", [case_id]):
            created.append(self.upsert_object(case_id, "claim", cl.get("statement", cl["claim_id"]), cl, status=cl.get("status", "active"), source_table="claim_reviews_72", source_id=cl["claim_id"])["object_id"])
        summary = self.case_summary(case_id)
        self.audit.log("index", "persistent_case_db_73", case_id, case_id, {"object_count": summary["object_count"]})
        return {"case_id": case_id, "indexed_object_ids": created, "summary": summary}

    def case_summary(self, case_id: str) -> Dict[str, Any]:
        rows = self.db.all("SELECT object_type,status,COUNT(*) AS c FROM canonical_case_objects_73 WHERE case_id=? GROUP BY object_type,status", [case_id])
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        total = 0
        for r in rows:
            by_type[r["object_type"]] = by_type.get(r["object_type"], 0) + int(r["c"])
            by_status[r["status"]] = by_status.get(r["status"], 0) + int(r["c"])
            total += int(r["c"])
        links = self.db.one("SELECT COUNT(*) AS c FROM canonical_case_links_73 WHERE case_id=?", [case_id]) or {"c": 0}
        return {"case_id": case_id, "object_count": total, "link_count": int(links["c"]), "by_type": by_type, "by_status": by_status}

    def get_object(self, object_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_case_objects_73 WHERE object_id=?", [object_id])
        if not row:
            raise KeyError(object_id)
        row["data"] = loads(row.pop("data_json", "{}"), {})
        return row

    def get_link(self, link_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM canonical_case_links_73 WHERE link_id=?", [link_id])
        if not row:
            raise KeyError(link_id)
        row["data"] = loads(row.pop("data_json", "{}"), {})
        return row
