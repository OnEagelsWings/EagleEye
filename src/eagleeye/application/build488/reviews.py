"""Build 488: human-only, case-scoped candidate review ledger.

A decision is an analyst annotation, never an identity merge or Evidence/Claim.
Callers must authenticate the actor and supply entities from an authorized case.
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import HTTPException
from eagleeye.interfaces.web.sources487 import _hash

DECISIONS = frozenset({"possible_match", "not_same", "needs_evidence"})


def initialize(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS entity_candidate_reviews_488(
        case_id TEXT NOT NULL, left_entity_id TEXT NOT NULL,
        right_entity_id TEXT NOT NULL, decision TEXT NOT NULL,
        rationale TEXT NOT NULL, reviewed_by TEXT NOT NULL,
        reviewed_at TEXT NOT NULL, record_hash TEXT NOT NULL,
        PRIMARY KEY(case_id,left_entity_id,right_entity_id)
    )""")
    ctx.db.conn.execute(
        "CREATE INDEX IF NOT EXISTS candidate_reviews_488_case ON entity_candidate_reviews_488(case_id)"
    )
    ctx.db.conn.commit()


def reviews_for_case(ctx, user, case_id):
    ctx.team_governance_359.authorize(
        user, case_id=case_id, capability="case.read",
        object_type="operational_case", object_id=case_id)
    rows = [dict(row) for row in ctx.db.all(
        "SELECT * FROM entity_candidate_reviews_488 WHERE case_id=? ORDER BY reviewed_at",
        (case_id,))]
    if any(_hash(row) != row["record_hash"] for row in rows):
        raise HTTPException(409, "Entity-Reviewregister wurde verändert.")
    return rows


def record_review(ctx, user, case_id, candidate, decision, rationale):
    """Record an explicit analyst judgment for an authorized, current candidate."""
    if decision not in DECISIONS:
        raise HTTPException(422, "Ungültige Prüfentscheidung.")
    rationale = " ".join(str(rationale or "").split())
    if not 20 <= len(rationale) <= 1200:
        raise HTTPException(422, "Prüfbegründung muss 20–1200 Zeichen enthalten.")
    if candidate.get("case_id") != case_id or candidate.get("review_status") != "unreviewed":
        raise HTTPException(403, "Kein gültiger fallbezogener Kandidat.")
    left, right = (str(candidate.get(k) or "") for k in ("left_entity_id", "right_entity_id"))
    if not left or not right or left == right:
        raise HTTPException(422, "Zwei verschiedene Entitäten erforderlich.")
    left, right = sorted((left, right))
    ctx.team_governance_359.authorize(
        user, case_id=case_id, capability="research.run",
        object_type="operational_case", object_id=case_id)
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        existing = ctx.db.one(
            "SELECT * FROM entity_candidate_reviews_488 WHERE case_id=? AND left_entity_id=? AND right_entity_id=?",
            (case_id, left, right))
        if existing:
            row = dict(existing)
            if _hash(row) != row["record_hash"]:
                raise HTTPException(409, "Bestehende Prüfentscheidung ist nicht integer.")
            if row["decision"] == decision and row["rationale"] == rationale:
                return row
            raise HTTPException(409, "Bereits geprüft; Änderungen benötigen einen separaten Auditvorgang.")
        row = dict(case_id=case_id, left_entity_id=left, right_entity_id=right,
                   decision=decision, rationale=rationale, reviewed_by=user["username"],
                   reviewed_at=datetime.now(timezone.utc).isoformat())
        row["record_hash"] = _hash(row)
        cols = tuple(row)
        ctx.db.execute(
            "INSERT INTO entity_candidate_reviews_488 (" + ",".join(cols) +
            ") VALUES (" + ",".join("?" for _ in cols) + ")",
            tuple(row[k] for k in cols))
        ctx.audit.log("entity_candidate_reviewed_488", "entity_candidate_reviews_488",
                      left + ":" + right, case_id,
                      {"decision": decision, "left_entity_id": left,
                       "right_entity_id": right, "identity_confirmed": False,
                       "merged": False, "evidence_created": False})
        return row
