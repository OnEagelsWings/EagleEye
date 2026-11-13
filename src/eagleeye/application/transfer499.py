"""Build 499: recoverable cross-DB transfer of a reviewed candidate to the graph.

Human-selected *existing case document* is required. The resulting graph entry
remains UNVERIFIED and creates no relationship. The transfer ID is deterministic,
so an interrupted cross-SQLite write is safe to retry without a duplicate node.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from eagleeye.application import personosint494 as po
from eagleeye.application.entity_registry461 import EntityRegistry461

class TransferError(ValueError):pass

def _hash(row):
    return hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!="record_hash"},
          sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
def _now():return datetime.now(timezone.utc).isoformat(timespec="seconds")

def initialize(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS case_entity_transfers_499(
      candidate_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,entity_id TEXT NOT NULL,
      document_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,state TEXT NOT NULL,
      rationale TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,
      completed_at TEXT NOT NULL,record_hash TEXT NOT NULL
    )""")
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS case_transfer499_case ON case_entity_transfers_499(case_id,state)")
    ctx.db.conn.commit()

def rows(ctx,case_id):
    result=[dict(row) for row in ctx.db.all(
        "SELECT * FROM case_entity_transfers_499 WHERE case_id=? ORDER BY created_at,candidate_id",(case_id,))]
    for item in result:
        if item["record_hash"]!=_hash(item):raise TransferError("Transfer journal hash mismatch")
    return result

def _id(case_id,candidate_id):
    return "po499_"+hashlib.sha256((case_id+"\0"+candidate_id).encode()).hexdigest()[:32]

def transfer(ctx,user,case_id,candidate_id,document_id,rationale,*,base_dir):
    ctx.team_governance_359.authorize(user,case_id=case_id,capability="source.review",
                                      object_type="operational_case",object_id=case_id)
    rationale=" ".join(str(rationale or "").split())
    if not 30<=len(rationale)<=1200:
        raise TransferError("A substantive 30–1200 character source review is required")
    selection=next((r for r in po.candidates(ctx,case_id) if r["candidate_id"]==candidate_id),None)
    if not selection or selection["state"]!="for_manual_entry":
        raise TransferError("Candidate must be reviewed for manual entry in this case")
    documents=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
    allowed={d["document_id"] for d in documents}
    if document_id not in allowed:
        raise TransferError("A previously stored document from this case is required")
    entity_id=_id(case_id,candidate_id)
    source_hash=hashlib.sha256((document_id+":"+selection["record_hash"]).encode()).hexdigest()
    with ctx.audit.actor_scope(user["username"]),ctx.db.transaction(immediate=True):
        prev=ctx.db.one("SELECT * FROM case_entity_transfers_499 WHERE candidate_id=?",
                        (candidate_id,))
        if prev:
            prev=dict(prev)
            if prev["record_hash"]!=_hash(prev):raise TransferError("Existing journal hash mismatch")
            if (prev["case_id"],prev["document_id"],prev["entity_id"],prev["source_sha256"])!=(
                case_id,document_id,entity_id,source_hash):
                raise TransferError("Transfer already staged with different source")
            if prev["state"]=="completed":return prev
            if prev["state"]!="staged":raise TransferError("Unexpected transfer state")
            # Retry after an interrupted transfer: the rationale recorded when the
            # transfer was staged is authoritative. Using a re-typed text here would
            # make the idempotent graph upsert fail ("entry differs") and leave the
            # transfer permanently stuck, or let journal and graph notes diverge.
            rationale=prev["rationale"]
        else:
            row=dict(candidate_id=candidate_id,case_id=case_id,entity_id=entity_id,
                     document_id=document_id,source_sha256=source_hash,
                     state="staged",rationale=rationale,actor=user["username"],
                     created_at=_now(),completed_at="")
            row["record_hash"]=_hash(row)
            ctx.db.execute("INSERT INTO case_entity_transfers_499("+",".join(row)+") VALUES("+
                           ",".join("?" for _ in row)+")",tuple(row.values()))
            ctx.audit.log("entity_transfer_staged_499","entity_transfer",candidate_id,case_id,
                          {"graph_node_id":entity_id,"document_id":document_id,
                           "identity_confirmed":False,"relations_created":0})
    # Separate registry SQLite. Idempotent deterministic ID reconciles a crash
    # after graph write but before journal completion.
    path=(Path(base_dir) if base_dir is not None else ctx.base_dir)/"entity_registry_462.sqlite3"
    with EntityRegistry461(path) as graph:
        notes=("Unverifizierter PersonOSINT-Prüfkandidat. Quelle: doc458:"+document_id+
               ". Prüfbegründung: "+rationale+
               ". Keine Identitätsbestätigung oder automatische Verknüpfung.")
        graph.upsert_unverified_external_candidate(
            case_id=case_id,entity_id=entity_id,kind=selection["kind"],
            label=selection["label"],notes=notes)
    with ctx.audit.actor_scope(user["username"]),ctx.db.transaction(immediate=True):
        row=dict(ctx.db.one("SELECT * FROM case_entity_transfers_499 WHERE candidate_id=?",(candidate_id,)))
        if row["record_hash"]!=_hash(row):raise TransferError("Journal integrity failed")
        if row["state"]=="completed":return row
        row.update(state="completed",completed_at=_now())
        row["record_hash"]=_hash(row)
        ctx.db.execute("UPDATE case_entity_transfers_499 SET state='completed',completed_at=?,"
                       "record_hash=? WHERE candidate_id=? AND case_id=?",
                       (row["completed_at"],row["record_hash"],candidate_id,case_id))
        ctx.audit.log("entity_transfer_completed_499","entity_transfer",candidate_id,case_id,
                      {"graph_node_id":entity_id,"document_id":document_id,
                       "unverified_only":True,"relations_created":0})
        return row
