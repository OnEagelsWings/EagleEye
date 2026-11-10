"""Build 494: review-only PersonOSINT entity queue in EagleEye's canonical case DB.

Foreign labels and types are suggestions, never verified identities. User,
case, credentials, photos, sensitive attributes and graph edges are NOT imported.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

from .personosint493 import MAX_EXPORT_BYTES, PersonOSINTImportError

MAX_ENTITIES = 150
MAPPED_TYPES = {
    "person": "person",
    "organisation": "organization",
    "organization": "organization",
    "unternehmen": "company",
    "company": "company",
    "ort": "place",
    "place": "place",
    "ereignis": "event",
    "event": "event",
    "dokument": "document",
    "document": "document",
}
DECISIONS = {"for_manual_entry", "dismissed"}


@dataclass(frozen=True)
class EntitySuggestion:
    source_id: str
    kind: str
    label: str


@dataclass(frozen=True)
class EntityPreview:
    foreign_case: str
    proposals: tuple[EntitySuggestion, ...]
    skipped: int


def _text(value, max_len: int) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    raw = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    return " ".join(raw.split())[:max_len].strip()


def parse_entity_suggestions(raw: bytes) -> EntityPreview:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EXPORT_BYTES:
        raise PersonOSINTImportError("PersonOSINT export exceeds 1 MB or is empty")
    try:
        source = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise PersonOSINTImportError("Invalid PersonOSINT JSON export") from exc
    if not isinstance(source, dict) or not isinstance(source.get("case"), dict):
        raise PersonOSINTImportError("Expected a PersonOSINT case export")
    entities = source.get("entities")
    if not isinstance(entities, list) or len(entities) > MAX_ENTITIES:
        raise PersonOSINTImportError("Entity list missing or larger than 150 records")
    case = source["case"]
    foreign_case = _text(case.get("reference") or case.get("id"), 80)
    if not foreign_case:
        raise PersonOSINTImportError("PersonOSINT case reference missing")
    proposals, seen = [], set()
    skipped = 0
    for row in entities:
        if not isinstance(row, dict):
            skipped += 1
            continue
        source_id = _text(row.get("id"), 80)
        label = _text(row.get("label"), 512)
        kind = MAPPED_TYPES.get(_text(row.get("type"), 40).casefold())
        # Do not infer identities or convert phone/account/vehicle identifiers.
        if not source_id or not label or not kind or (source_id,kind,label) in seen:
            skipped += 1
            continue
        seen.add((source_id,kind,label))
        proposals.append(EntitySuggestion(source_id,kind,label))
    if not proposals:
        raise PersonOSINTImportError("No supported PersonOSINT entity suggestions found")
    return EntityPreview(foreign_case, tuple(proposals), skipped)


SCHEMA = """CREATE TABLE IF NOT EXISTS personosint_entity_candidates_494(
    candidate_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
    foreign_case_sha256 TEXT NOT NULL, foreign_entity_sha256 TEXT NOT NULL,
    kind TEXT NOT NULL, label TEXT NOT NULL,
    state TEXT NOT NULL, rationale TEXT NOT NULL,
    created_by TEXT NOT NULL, created_at TEXT NOT NULL,
    reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL,
    record_hash TEXT NOT NULL
)"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(SCHEMA)
    ctx.db.conn.execute(
        "CREATE INDEX IF NOT EXISTS po_entity494_case ON personosint_entity_candidates_494(case_id,state)"
    )
    ctx.db.conn.commit()


def _digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(
        {k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def candidates(ctx, case_id: str) -> list[dict]:
    rows = [dict(r) for r in ctx.db.all(
        "SELECT * FROM personosint_entity_candidates_494 WHERE case_id=? ORDER BY created_at,candidate_id",
        (case_id,)
    )]
    for row in rows:
        if row["record_hash"] != _digest(row):
            raise ValueError("PersonOSINT candidate integrity failed")
    return rows


def queue(ctx, user: dict, case_id: str, preview: EntityPreview) -> int:
    """Store suggestions in the shared case DB. Never touch the graph registry."""
    imported = 0
    foreign = hashlib.sha256(preview.foreign_case.encode()).hexdigest()
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        for candidate in preview.proposals:
            source_ref = hashlib.sha256(candidate.source_id.encode()).hexdigest()
            key = json.dumps([case_id, foreign, source_ref, candidate.kind, candidate.label],
                             ensure_ascii=False, separators=(",", ":"))
            candidate_id = "po494_" + hashlib.sha256(key.encode()).hexdigest()[:32]
            row = {
                "candidate_id": candidate_id, "case_id": case_id,
                "foreign_case_sha256": foreign, "foreign_entity_sha256": source_ref,
                "kind": candidate.kind, "label": candidate.label,
                "state": "unreviewed", "rationale": "",
                "created_by": user["username"], "created_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": "", "reviewed_at": ""
            }
            row["record_hash"] = _digest(row)
            result = ctx.db.execute(
                "INSERT OR IGNORE INTO personosint_entity_candidates_494("
                + ",".join(row) + ") VALUES(" + ",".join("?" for _ in row) + ")",
                tuple(row.values())
            )
            imported += int(result.rowcount == 1)
        ctx.audit.log("personosint_entity_suggestions_494", "entity_candidates", case_id, case_id,
                      {"imported": imported, "skipped": preview.skipped,
                       "candidate_only": True, "graph_changed": False})
    return imported


def review(ctx, user: dict, case_id: str, candidate_id: str,
           decision: str, rationale: str) -> dict:
    if decision not in DECISIONS:
        raise ValueError("Invalid PersonOSINT review decision")
    rationale = " ".join(str(rationale or "").split())
    if not 20 <= len(rationale) <= 1200:
        raise ValueError("Review rationale must contain 20–1200 characters")
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        stored = ctx.db.one(
            "SELECT * FROM personosint_entity_candidates_494 WHERE case_id=? AND candidate_id=?",
            (case_id,candidate_id)
        )
        if not stored:
            raise KeyError("Candidate does not belong to this case")
        row = dict(stored)
        if row["record_hash"] != _digest(row):
            raise ValueError("PersonOSINT candidate integrity failed")
        if row["state"] != "unreviewed":
            raise ValueError("Candidate is already reviewed")
        row.update(state=decision, rationale=rationale, reviewed_by=user["username"],
                   reviewed_at=datetime.now(timezone.utc).isoformat())
        row["record_hash"] = _digest(row)
        ctx.db.execute(
            "UPDATE personosint_entity_candidates_494 SET state=?,rationale=?,reviewed_by=?,reviewed_at=?,record_hash=? "
            "WHERE case_id=? AND candidate_id=? AND state='unreviewed'",
            (row["state"],row["rationale"],row["reviewed_by"],row["reviewed_at"],
             row["record_hash"],case_id,candidate_id)
        )
        ctx.audit.log("personosint_entity_review_494", "entity_candidate", candidate_id, case_id,
                      {"decision": decision, "manual_creation_required": True,
                       "identity_confirmed": False, "graph_changed": False})
        return row
