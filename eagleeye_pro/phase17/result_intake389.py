from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping

BUILD = "389.0"
POLICY_ID = "phase17.result-intake-evidence-normalization.v389"
CONFIRM_PROMOTE = "PROMOTE EVIDENCE"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


def _normalize(value: Any) -> Any:
    """Deterministic normalization for candidate hashing, not semantic truth inference."""
    if isinstance(value, Mapping):
        return {str(k).strip(): _normalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0])) if str(k).strip()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, str):
        return " ".join(value.split())[:20000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:20000]


@dataclass(frozen=True, slots=True)
class EvidenceCandidate389:
    candidate_id: str
    case_id: str
    session_id: str
    wave_number: int
    phase17_source_id: str
    canonical_source_id: str
    object_id: str
    parse_run_id: str
    record_index: int
    candidate_type: str
    canonical_hash: str
    duplicate_of_candidate_id: str
    review_status: str
    vault_state: str
    vault_artifact_id: str
    normalized: dict[str, Any]
    provenance: dict[str, Any]
    created_at: str


class ResultIntake389:
    """Normalize terminal crawler artifacts into review-only evidence candidates.

    It reuses Build-350 parser runs, preserves raw object provenance, links exact
    duplicates without deleting independent-source observations, exposes a bounded
    candidate feed to the AI investigator, and requires explicit human promotion
    before a candidate is copied into Evidence Vault. Promotion still leaves the
    vault artifact in ``needs_review``; no truth/evidence acceptance is automatic.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        waves388: Any,
        build350: Any,
        evidence_vault50: Any,
        review_board88: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.waves388 = waves388
        self.build350 = build350
        self.evidence_vault50 = evidence_vault50
        self.review_board88 = review_board88
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS result_intake_batch_389 (
              batch_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              source_result_count INTEGER NOT NULL,
              object_count INTEGER NOT NULL,
              candidate_count INTEGER NOT NULL,
              duplicate_links INTEGER NOT NULL,
              parse_failures INTEGER NOT NULL,
              quarantined_skipped INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_result_intake_batch_389_case ON result_intake_batch_389(case_id,created_at);

            CREATE TABLE IF NOT EXISTS evidence_candidate_389 (
              candidate_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              wave_number INTEGER NOT NULL,
              phase17_source_id TEXT NOT NULL,
              canonical_source_id TEXT NOT NULL,
              dispatch_id TEXT NOT NULL,
              job_id TEXT NOT NULL,
              crawl_run_id TEXT NOT NULL,
              search_run_id TEXT NOT NULL,
              object_id TEXT NOT NULL,
              object_sha256 TEXT NOT NULL,
              parse_run_id TEXT NOT NULL,
              record_index INTEGER NOT NULL,
              candidate_type TEXT NOT NULL,
              canonical_hash TEXT NOT NULL,
              duplicate_of_candidate_id TEXT NOT NULL DEFAULT '',
              independent_source_observation INTEGER NOT NULL DEFAULT 0,
              normalized_json TEXT NOT NULL,
              provenance_json TEXT NOT NULL,
              review_status TEXT NOT NULL,
              vault_state TEXT NOT NULL,
              vault_artifact_id TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(case_id,object_id,parse_run_id,record_index,canonical_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_evidence_candidate_389_case ON evidence_candidate_389(case_id,review_status,created_at);
            CREATE INDEX IF NOT EXISTS idx_evidence_candidate_389_hash ON evidence_candidate_389(case_id,canonical_hash);
            CREATE INDEX IF NOT EXISTS idx_evidence_candidate_389_session ON evidence_candidate_389(session_id,wave_number,created_at);

            CREATE TABLE IF NOT EXISTS evidence_candidate_promotion_389 (
              promotion_id TEXT PRIMARY KEY,
              candidate_id TEXT NOT NULL UNIQUE,
              case_id TEXT NOT NULL,
              vault_artifact_id TEXT NOT NULL,
              promoted_by TEXT NOT NULL,
              promoted_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(candidate_id) REFERENCES evidence_candidate_389(candidate_id)
            );
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(dict(identity), case_id=case_id, capability=capability, object_type="phase17_evidence_candidate_v389", object_id=object_id)

    def _candidate_row(self, case_id: str, candidate_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_candidate_389 WHERE candidate_id=? AND case_id=?", (candidate_id, case_id))
        if not row:
            raise KeyError(candidate_id)
        return row

    def _candidate_dict(self, row: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["normalized"] = _j(out.pop("normalized_json", "{}"), {})
        out["provenance"] = _j(out.pop("provenance_json", "{}"), {})
        out["independent_source_observation"] = bool(out.get("independent_source_observation"))
        out["truth_assigned"] = False
        out["automatic_evidence_acceptance"] = False
        return out

    def _insert_candidate(
        self,
        *,
        case_id: str,
        session_id: str,
        result_row: Mapping[str, Any],
        obj: Mapping[str, Any],
        parse_run_id: str,
        record_index: int,
        candidate_type: str,
        normalized: Mapping[str, Any],
        provenance: Mapping[str, Any],
        review_status: str = "needs_review",
    ) -> tuple[dict[str, Any], bool]:
        normalized_clean = _normalize(dict(normalized))
        canonical_hash = _sha(normalized_clean)
        existing = self.db.one(
            "SELECT * FROM evidence_candidate_389 WHERE case_id=? AND object_id=? AND parse_run_id=? AND record_index=? AND canonical_hash=?",
            (case_id, obj["object_id"], parse_run_id, int(record_index), canonical_hash),
        )
        if existing:
            return self._candidate_dict(existing), False
        duplicate = self.db.one(
            "SELECT candidate_id,canonical_source_id,object_id FROM evidence_candidate_389 WHERE case_id=? AND canonical_hash=? ORDER BY created_at,candidate_id LIMIT 1",
            (case_id, canonical_hash),
        )
        duplicate_id = str((duplicate or {}).get("candidate_id") or "")
        independent = bool(duplicate and str(duplicate.get("canonical_source_id") or "") != str(result_row.get("canonical_source_id") or ""))
        candidate_id = "cand389_" + secrets.token_hex(12)
        created = _now()
        row = {
            "candidate_id": candidate_id,
            "case_id": case_id,
            "session_id": session_id,
            "wave_number": int(result_row.get("wave_number") or 0),
            "phase17_source_id": str(result_row.get("phase17_source_id") or ""),
            "canonical_source_id": str(result_row.get("canonical_source_id") or ""),
            "dispatch_id": str(result_row.get("dispatch_id") or ""),
            "job_id": str(result_row.get("job_id") or ""),
            "crawl_run_id": str(result_row.get("crawl_run_id") or ""),
            "search_run_id": str(result_row.get("search_run_id") or ""),
            "object_id": str(obj.get("object_id") or ""),
            "object_sha256": str(obj.get("sha256") or ""),
            "parse_run_id": parse_run_id,
            "record_index": int(record_index),
            "candidate_type": candidate_type,
            "canonical_hash": canonical_hash,
            "duplicate_of_candidate_id": duplicate_id,
            "independent_source_observation": int(independent),
            "normalized_json": _canon(normalized_clean),
            "provenance_json": _canon(dict(provenance)),
            "review_status": review_status,
            "vault_state": "candidate_not_promoted",
            "vault_artifact_id": "",
            "created_at": created,
            "updated_at": created,
        }
        record_hash = _sha(row)
        self.db.execute(
            "INSERT INTO evidence_candidate_389(candidate_id,case_id,session_id,wave_number,phase17_source_id,canonical_source_id,dispatch_id,job_id,crawl_run_id,search_run_id,object_id,object_sha256,parse_run_id,record_index,candidate_type,canonical_hash,duplicate_of_candidate_id,independent_source_observation,normalized_json,provenance_json,review_status,vault_state,vault_artifact_id,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*row.values(), record_hash),
        )
        return self._candidate_dict({**row, "record_hash": record_hash}), True

    def normalize_session(self, *, case_id: str, session_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "case.read", session_id)
        session = self.waves388.session(case_id=case_id, session_id=session_id)
        if str(session.get("state") or "") not in {"active", "complete", "completed"}:
            raise PermissionError("wave session is not eligible for result intake")
        results = self.db.all(
            "SELECT * FROM research_wave_result_388 WHERE session_id=? AND job_status IN ('succeeded','failed','cancelled','dead_letter') ORDER BY wave_number,observed_at,result_id",
            (session_id,),
        )
        created: list[dict[str, Any]] = []
        objects_seen = 0
        parse_failures = 0
        quarantined = 0
        duplicate_links = 0
        actor = str(identity.get("username") or self.actor)[:120]
        with self.db.transaction(immediate=True):
            for result in results:
                object_ids = tuple(str(v) for v in (_j(result.get("object_ids_json"), []) or []) if str(v))
                for object_id in object_ids:
                    obj = self.db.one("SELECT * FROM phase15_objects WHERE object_id=? AND case_id=?", (object_id, case_id))
                    if not obj:
                        continue
                    objects_seen += 1
                    obj_prov = _j(obj.get("provenance_json"), {}) or {}
                    base_prov = {
                        "policy": POLICY_ID,
                        "case_id": case_id,
                        "session_id": session_id,
                        "wave_number": int(result.get("wave_number") or 0),
                        "dispatch_id": str(result.get("dispatch_id") or ""),
                        "job_id": str(result.get("job_id") or ""),
                        "crawl_run_id": str(result.get("crawl_run_id") or ""),
                        "search_run_id": str(result.get("search_run_id") or ""),
                        "phase17_source_id": str(result.get("phase17_source_id") or ""),
                        "canonical_source_id": str(result.get("canonical_source_id") or ""),
                        "object_id": object_id,
                        "object_sha256": str(obj.get("sha256") or ""),
                        "media_type": str(obj.get("media_type") or ""),
                        "security_state": str(obj.get("security_state") or ""),
                        "source_url": str(obj_prov.get("canonical_url") or obj_prov.get("url") or obj_prov.get("source_url") or ""),
                        "raw_object_preserved": True,
                    }
                    if str(obj.get("security_state") or "") == "quarantined":
                        quarantined += 1
                        cand, is_new = self._insert_candidate(
                            case_id=case_id, session_id=session_id, result_row=result, obj=obj,
                            parse_run_id="", record_index=-1, candidate_type="quarantined_artifact_review",
                            normalized={"object_id": object_id, "reason": "quarantined_requires_human_safe_review"},
                            provenance=base_prov, review_status="blocked_quarantined",
                        )
                        if is_new: created.append(cand)
                        continue
                    parse = self.db.one("SELECT * FROM phase15_parse_runs WHERE object_id=? ORDER BY created_at DESC LIMIT 1", (object_id,))
                    if not parse:
                        parsed = self.build350.parse_artifact(object_id)
                        parse = self.db.one("SELECT * FROM phase15_parse_runs WHERE parse_run_id=?", (parsed["parse_run_id"],))
                    if not parse or str(parse.get("status") or "") != "parsed":
                        parse_failures += 1
                        parse_id = str((parse or {}).get("parse_run_id") or "")
                        cand, is_new = self._insert_candidate(
                            case_id=case_id, session_id=session_id, result_row=result, obj=obj,
                            parse_run_id=parse_id, record_index=-1, candidate_type="parse_failure_review",
                            normalized={"object_id": object_id, "parse_error": str((parse or {}).get("error_text") or "parse_failed")[:2000]},
                            provenance={**base_prov, "parse_run_id": parse_id}, review_status="blocked_parse",
                        )
                        if is_new: created.append(cand)
                        continue
                    normalized_doc = _j(parse.get("normalized_json"), {}) or {}
                    records = normalized_doc.get("records") if isinstance(normalized_doc, dict) else None
                    if not isinstance(records, list) or not records:
                        records = [{"text": str(normalized_doc.get("text") or ""), "title": str(normalized_doc.get("title") or "")}]
                    for idx, record in enumerate(records[:5000]):
                        if not isinstance(record, Mapping):
                            record = {"value": record}
                        cand, is_new = self._insert_candidate(
                            case_id=case_id, session_id=session_id, result_row=result, obj=obj,
                            parse_run_id=str(parse.get("parse_run_id") or ""), record_index=idx,
                            candidate_type="normalized_record", normalized=dict(record),
                            provenance={**base_prov, "parse_run_id": str(parse.get("parse_run_id") or ""), "parser_version": str(parse.get("parser_version") or ""), "record_index": idx},
                        )
                        if is_new:
                            created.append(cand)
                            if cand.get("duplicate_of_candidate_id"): duplicate_links += 1
            batch_id = "intake389_" + secrets.token_hex(12)
            batch = {
                "batch_id": batch_id, "case_id": case_id, "session_id": session_id,
                "source_result_count": len(results), "object_count": objects_seen,
                "candidate_count": len(created), "duplicate_links": duplicate_links,
                "parse_failures": parse_failures, "quarantined_skipped": quarantined,
                "created_by": actor, "created_at": _now(),
            }
            self.db.execute(
                "INSERT INTO result_intake_batch_389(batch_id,case_id,session_id,source_result_count,object_count,candidate_count,duplicate_links,parse_failures,quarantined_skipped,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (*batch.values(), _sha(batch)),
            )
        self.audit.log("normalize", "phase17_result_intake_389", batch_id, case_id, {"session_id": session_id, "candidates": len(created), "duplicates": duplicate_links})
        return {**batch, "candidates": created, "automatic_evidence_promotion": False, "truth_assigned": False, "network_requests_created": 0}

    def candidates(self, *, case_id: str, identity: Mapping[str, Any] | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        n = max(1, min(int(limit), 1000))
        rows = self.db.all("SELECT * FROM evidence_candidate_389 WHERE case_id=? ORDER BY created_at DESC,candidate_id DESC LIMIT ?", (case_id, n))
        return [self._candidate_dict(r) for r in rows]

    def ai_candidate_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None, limit: int = 100) -> dict[str, Any]:
        rows = self.candidates(case_id=case_id, identity=identity, limit=limit)
        return {
            "case_id": case_id,
            "build": BUILD,
            "candidates": rows,
            "candidate_count": len(rows),
            "candidate_only": True,
            "truth_assigned": False,
            "identity_merge_authority": False,
            "automatic_evidence_acceptance": False,
            "instruction": "Treat candidates as review material with provenance, not as verified facts or independent confirmations merely because hashes match.",
        }

    def promote_candidate(self, *, case_id: str, candidate_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_PROMOTE:
            raise PermissionError(f"explicit confirmation {CONFIRM_PROMOTE} required")
        self._authorize(identity, case_id, "source.review", candidate_id)
        row = self._candidate_row(case_id, candidate_id)
        if str(row.get("review_status") or "") in {"blocked_parse", "blocked_quarantined"}:
            raise PermissionError("blocked candidate cannot be promoted before human remediation")
        if str(row.get("vault_artifact_id") or ""):
            return {"candidate": self._candidate_dict(row), "vault_artifact": self.evidence_vault50.get_artifact(str(row["vault_artifact_id"])), "idempotent": True}
        normalized = _j(row.get("normalized_json"), {}) or {}
        provenance = _j(row.get("provenance_json"), {}) or {}
        actor = str(identity.get("username") or self.actor)[:120]
        self.review_board88.decide(case_id, "evidence_candidate_389", candidate_id, "needs_more_evidence", reason="Explicit Build-389 promotion; not truth acceptance", actor=actor, metadata={"canonical_hash": row.get("canonical_hash"), "object_id": row.get("object_id")})
        artifact = self.evidence_vault50.ingest_text_artifact(
            case_id,
            title=f"Phase 17 evidence candidate {candidate_id}",
            content=_canon({"normalized": normalized, "provenance": provenance, "candidate_id": candidate_id}),
            source_url=str(provenance.get("source_url") or ""),
            source_type="phase17_evidence_candidate",
            linked_object_type="evidence_candidate_389",
            linked_object_id=candidate_id,
            notes="Promoted for human evidence review; candidate status is not a truth determination.",
            actor=actor,
        )
        updated_at = _now()
        with self.db.transaction(immediate=True):
            new_body = {k: row[k] for k in row if k != "record_hash"}
            new_body.update({"review_status": "promoted_needs_review", "vault_state": "promoted_needs_review", "vault_artifact_id": artifact["artifact_id"], "updated_at": updated_at})
            self.db.execute("UPDATE evidence_candidate_389 SET review_status=?,vault_state=?,vault_artifact_id=?,updated_at=?,record_hash=? WHERE candidate_id=?", ("promoted_needs_review", "promoted_needs_review", artifact["artifact_id"], updated_at, _sha(new_body), candidate_id))
            promotion = {"promotion_id": "prom389_" + secrets.token_hex(12), "candidate_id": candidate_id, "case_id": case_id, "vault_artifact_id": artifact["artifact_id"], "promoted_by": actor, "promoted_at": updated_at}
            self.db.execute("INSERT INTO evidence_candidate_promotion_389(promotion_id,candidate_id,case_id,vault_artifact_id,promoted_by,promoted_at,record_hash) VALUES(?,?,?,?,?,?,?)", (*promotion.values(), _sha(promotion)))
        return {"candidate": self._candidate_dict(self._candidate_row(case_id, candidate_id)), "vault_artifact": artifact, "automatic_truth_acceptance": False, "evidence_review_required": True}

    def verify_candidate(self, *, case_id: str, candidate_id: str) -> dict[str, Any]:
        row = self._candidate_row(case_id, candidate_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        valid = str(row.get("record_hash") or "") == _sha(body)
        object_row = self.db.one("SELECT sha256 FROM phase15_objects WHERE object_id=? AND case_id=?", (row["object_id"], case_id))
        source_intact = bool(object_row and str(object_row.get("sha256") or "") == str(row.get("object_sha256") or ""))
        return {"candidate_id": candidate_id, "valid": bool(valid and source_intact), "candidate_record_hash_valid": valid, "raw_object_binding_valid": source_intact}

    def status(self) -> dict[str, Any]:
        counts = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN review_status='needs_review' THEN 1 ELSE 0 END) needs_review,SUM(CASE WHEN vault_artifact_id<>'' THEN 1 ELSE 0 END) promoted,SUM(CASE WHEN duplicate_of_candidate_id<>'' THEN 1 ELSE 0 END) duplicate_links FROM evidence_candidate_389") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "result_normalization": True,
            "reuses_build350_parser": True,
            "raw_object_provenance_preserved": True,
            "logical_deduplication": True,
            "independent_source_observations_preserved": True,
            "ai_candidate_feed": True,
            "automatic_evidence_promotion": False,
            "automatic_truth_acceptance": False,
            "automatic_identity_merge": False,
            "direct_network_fetch": False,
            "candidates": int(counts.get("total") or 0),
            "needs_review": int(counts.get("needs_review") or 0),
            "promoted": int(counts.get("promoted") or 0),
            "duplicate_links": int(counts.get("duplicate_links") or 0),
        }
