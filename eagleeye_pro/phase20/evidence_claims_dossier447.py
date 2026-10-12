from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import json
import secrets

from eagleeye_pro.reporting.docx_writer import write_docx
from eagleeye_pro.reporting.pdf_writer import write_pdf

BUILD = "447.0"
POLICY_ID = "phase20.evidence-claims-dossier-closure.v447"

EVIDENCE_CONFIRM = "REVIEW EVIDENCE 447"
CLAIM_CONFIRM = "REVIEW CLAIM 447"
DOSSIER_CONFIRM = "APPROVE DOSSIER 447"
EXPORT_CONFIRM = "EXPORT DOSSIER 447"

EVIDENCE_STATES = {"unreviewed", "accepted", "context_only", "rejected"}
CLAIM_STATES = {"candidate_review_required", "accepted_for_dossier", "needs_more_evidence", "rejected"}
DOSSIER_STATES = {"draft_for_review", "approved_for_export", "changes_required"}
STANCES = {"support", "contradict", "context"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value, limit=12000):
    return " ".join(str(value or "").split())[:limit]


class EvidenceClaimsDossier447:
    """Canonical Phase-20 Evidence -> Claims -> Dossier closure layer.

    The service persists references and snapshots, not duplicate raw payloads.
    Evidence observations never become claims automatically. Claims never become
    findings automatically. Dossier approval is an explicit human review action.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        cases,
        registry421,
        events422,
        content423,
        news429,
        social432,
        loop439,
        dispatcher446,
        matrix418,
        synthesis419,
        governance,
        base_dir,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.cases = cases
        self.registry421 = registry421
        self.events422 = events422
        self.content423 = content423
        self.news429 = news429
        self.social432 = social432
        self.loop439 = loop439
        self.dispatcher446 = dispatcher446
        self.matrix418 = matrix418
        self.synthesis419 = synthesis419
        self.governance = governance
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS evidence_item_447(
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            observation_id TEXT NOT NULL UNIQUE,
            event_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            evidence_kind TEXT NOT NULL,
            title TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            media_type TEXT NOT NULL,
            duplicate_kind TEXT NOT NULL,
            source_snapshot_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            usage_json TEXT NOT NULL,
            descriptive_json TEXT NOT NULL,
            source_record_hash TEXT NOT NULL,
            event_record_hash TEXT NOT NULL,
            content_record_hash TEXT NOT NULL,
            observation_record_hash TEXT NOT NULL,
            review_state TEXT NOT NULL,
            review_note TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_evidence447_case
            ON evidence_item_447(case_id,observed_at,evidence_id);

            CREATE TABLE IF NOT EXISTS claim_447(
            claim_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            statement TEXT NOT NULL,
            state TEXT NOT NULL,
            uncertainty_note TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            review_note TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_claim447_case
            ON claim_447(case_id,state,created_at);

            CREATE TABLE IF NOT EXISTS claim_evidence_link_447(
            link_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            stance TEXT NOT NULL,
            note TEXT NOT NULL,
            evidence_hash_at_link TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            UNIQUE(claim_id,evidence_id,stance)
            );
            CREATE INDEX IF NOT EXISTS idx_claim_link447_claim
            ON claim_evidence_link_447(claim_id,stance);

            CREATE TABLE IF NOT EXISTS dossier_revision_447(
            revision_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            loop_id TEXT NOT NULL,
            revision_no INTEGER NOT NULL,
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            review_note TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            UNIQUE(case_id,revision_no)
            );
            CREATE INDEX IF NOT EXISTS idx_dossier447_case
            ON dossier_revision_447(case_id,revision_no);

            CREATE TABLE IF NOT EXISTS dossier_export_447(
            export_id TEXT PRIMARY KEY,
            revision_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            paths_json TEXT NOT NULL,
            hashes_json TEXT NOT NULL,
            package_hash TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_dossier_export447_case
            ON dossier_export_447(case_id,created_at);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _sha({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "dossier447")}

    def _authorize(self, identity, case_id, capability, object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="evidence_claims_dossier_447",
            object_id=str(object_id or case_id),
        )
        return ident

    def _preflight(self):
        checks = {
            "registry421": self.registry421.verify_integrity()["valid"],
            "events422": self.events422.verify_integrity()["valid"],
            "content423": self.content423.verify_integrity()["valid"],
            "news429": self.news429.verify_integrity()["valid"],
            "social432": self.social432.verify_integrity()["valid"],
            "loop439": self.loop439.verify_integrity()["valid"],
            "dispatcher446": self.dispatcher446.verify_integrity()["valid"],
            "matrix418": self.matrix418.verify_integrity()["valid"],
            "synthesis419": self.synthesis419.verify_integrity()["valid"],
        }
        if not all(checks.values()):
            raise RuntimeError(
                "Build-447 preflight failed: "
                + ",".join(k for k, value in checks.items() if not value)
            )
        return checks

    def _row(self, table, key, value):
        row = self.db.one(f"SELECT * FROM {table} WHERE {key}=?", (str(value),))
        return dict(row) if row else None

    def _news_for(self, case_id, event_id, content_id):
        row = self.db.one(
            "SELECT * FROM news_item_429 WHERE case_id=? AND event_id=? AND content_id=? "
            "ORDER BY created_at LIMIT 1",
            (str(case_id), str(event_id), str(content_id)),
        )
        if not row:
            return None
        d = dict(row)
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}
        return d

    def _social_for(self, case_id, event_id, content_id):
        row = self.db.one(
            "SELECT * FROM social_observation_432 WHERE case_id=? AND event_id=? AND content_id=? "
            "ORDER BY created_at LIMIT 1",
            (str(case_id), str(event_id), str(content_id)),
        )
        if not row:
            return None
        d = dict(row)
        try:
            d["metrics"] = json.loads(d.get("metrics_json") or "{}")
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metrics"] = {}
            d["metadata"] = {}
        d["test_fixture"] = bool(d.get("test_fixture"))
        return d

    def _evidence_snapshot_from_observation(self, obs):
        event = self._row("acquisition_event_422", "event_id", obs["event_id"])
        content = self._row("content_object_423", "content_id", obs["content_id"])
        source = self._row("acquisition_source_421", "source_id", obs["source_id"])
        if not event or not content or not source:
            raise RuntimeError("observation provenance chain is incomplete")
        try:
            source_snapshot = json.loads(event.get("source_snapshot_json") or "{}")
            provenance = json.loads(event.get("provenance_json") or "{}")
            usage = json.loads(event.get("usage_json") or "{}")
        except Exception as exc:
            raise RuntimeError("observation provenance JSON is invalid") from exc

        news = self._news_for(obs["case_id"], obs["event_id"], obs["content_id"])
        social = self._social_for(obs["case_id"], obs["event_id"], obs["content_id"])
        if news:
            kind = "news"
            title = str(news.get("title") or "")
            url = str(news.get("canonical_url") or obs.get("target") or "")
            observed_at = str(news.get("published_at") or event.get("retrieved_at") or "")
            descriptive = {
                "news_item_id": news.get("news_item_id"),
                "publisher": news.get("publisher"),
                "author": news.get("author"),
                "published_at": news.get("published_at"),
                "connector_kind": news.get("connector_kind"),
                "external_id": news.get("external_id"),
                "metadata": news.get("metadata") or {},
            }
        elif social:
            kind = "social"
            title = (
                f"{social.get('platform') or 'social'} "
                f"{social.get('object_type') or 'object'} "
                f"{social.get('account_handle') or social.get('external_object_id') or ''}"
            ).strip()
            url = str(social.get("canonical_url") or obs.get("target") or "")
            observed_at = str(social.get("published_at") or event.get("retrieved_at") or "")
            descriptive = {
                "social_observation_id": social.get("observation_id"),
                "adapter": social.get("adapter"),
                "platform": social.get("platform"),
                "object_type": social.get("object_type"),
                "external_object_id": social.get("external_object_id"),
                "account_id": social.get("account_id"),
                "account_handle": social.get("account_handle"),
                "published_at": social.get("published_at"),
                "visibility": social.get("visibility"),
                "metrics": social.get("metrics") or {},
                "metadata": social.get("metadata") or {},
                "test_fixture": bool(social.get("test_fixture")),
            }
        else:
            kind = "content_observation"
            title = str(obs.get("target") or "Acquired content")
            url = str(obs.get("target") or "")
            observed_at = str(event.get("retrieved_at") or obs.get("created_at") or "")
            descriptive = {
                "method": event.get("method"),
                "status": event.get("status"),
                "related_content_id": obs.get("related_content_id"),
                "similarity": obs.get("similarity"),
            }

        return {
            "event": event,
            "content": content,
            "source": source,
            "kind": kind,
            "title": _clean(title, 1000),
            "canonical_url": url[:4000],
            "observed_at": observed_at,
            "source_snapshot": source_snapshot,
            "provenance": provenance,
            "usage": usage,
            "descriptive": descriptive,
        }

    def sync_case_evidence(self, *, identity, case_id):
        ident = self._authorize(identity, case_id, "dossier.write", case_id)
        preflight = self._preflight()
        observations = self.db.all(
            "SELECT * FROM content_observation_423 WHERE case_id=? "
            "ORDER BY created_at,observation_id",
            (str(case_id),),
        )
        created = 0
        refreshed = 0
        unchanged = 0
        ids = []
        for raw in observations:
            obs = dict(raw)
            snap = self._evidence_snapshot_from_observation(obs)
            existing = self.db.one(
                "SELECT * FROM evidence_item_447 WHERE observation_id=?",
                (obs["observation_id"],),
            )
            now = _now()
            if existing:
                row = dict(existing)
                candidate = {
                    "title": snap["title"],
                    "canonical_url": snap["canonical_url"],
                    "observed_at": snap["observed_at"],
                    "content_sha256": str(snap["content"].get("sha256") or ""),
                    "media_type": str(snap["content"].get("media_type") or ""),
                    "duplicate_kind": str(obs.get("duplicate_kind") or ""),
                    "source_snapshot_json": _canon(snap["source_snapshot"]),
                    "provenance_json": _canon(snap["provenance"]),
                    "usage_json": _canon(snap["usage"]),
                    "descriptive_json": _canon(snap["descriptive"]),
                    "source_record_hash": str(snap["source"].get("record_hash") or ""),
                    "event_record_hash": str(snap["event"].get("record_hash") or ""),
                    "content_record_hash": str(snap["content"].get("record_hash") or ""),
                    "observation_record_hash": str(obs.get("record_hash") or ""),
                }
                changed = any(str(row.get(k) or "") != str(v or "") for k, v in candidate.items())
                if changed:
                    row.update(candidate)
                    row["updated_at"] = now
                    row["record_hash"] = self._rh(row)
                    self.db.execute(
                        "UPDATE evidence_item_447 SET title=?,canonical_url=?,observed_at=?,content_sha256=?,"
                        "media_type=?,duplicate_kind=?,source_snapshot_json=?,provenance_json=?,usage_json=?,"
                        "descriptive_json=?,source_record_hash=?,event_record_hash=?,content_record_hash=?,"
                        "observation_record_hash=?,updated_at=?,record_hash=? WHERE evidence_id=?",
                        (
                            row["title"], row["canonical_url"], row["observed_at"], row["content_sha256"],
                            row["media_type"], row["duplicate_kind"], row["source_snapshot_json"],
                            row["provenance_json"], row["usage_json"], row["descriptive_json"],
                            row["source_record_hash"], row["event_record_hash"], row["content_record_hash"],
                            row["observation_record_hash"], row["updated_at"], row["record_hash"],
                            row["evidence_id"],
                        ),
                    )
                    refreshed += 1
                else:
                    unchanged += 1
                evidence_id = row["evidence_id"]
            else:
                row = {
                    "evidence_id": "ev447_" + secrets.token_hex(10),
                    "case_id": str(case_id),
                    "observation_id": str(obs["observation_id"]),
                    "event_id": str(obs["event_id"]),
                    "content_id": str(obs["content_id"]),
                    "source_id": str(obs["source_id"]),
                    "evidence_kind": snap["kind"],
                    "title": snap["title"],
                    "canonical_url": snap["canonical_url"],
                    "observed_at": snap["observed_at"],
                    "content_sha256": str(snap["content"].get("sha256") or ""),
                    "media_type": str(snap["content"].get("media_type") or ""),
                    "duplicate_kind": str(obs.get("duplicate_kind") or ""),
                    "source_snapshot_json": _canon(snap["source_snapshot"]),
                    "provenance_json": _canon(snap["provenance"]),
                    "usage_json": _canon(snap["usage"]),
                    "descriptive_json": _canon(snap["descriptive"]),
                    "source_record_hash": str(snap["source"].get("record_hash") or ""),
                    "event_record_hash": str(snap["event"].get("record_hash") or ""),
                    "content_record_hash": str(snap["content"].get("record_hash") or ""),
                    "observation_record_hash": str(obs.get("record_hash") or ""),
                    "review_state": "unreviewed",
                    "review_note": "",
                    "reviewed_by": "",
                    "reviewed_at": "",
                    "created_at": now,
                    "updated_at": now,
                }
                row["record_hash"] = self._rh(row)
                self.db.execute(
                    "INSERT INTO evidence_item_447 VALUES("
                    + ",".join("?" for _ in row)
                    + ")",
                    tuple(row.values()),
                )
                evidence_id = row["evidence_id"]
                created += 1
            ids.append(evidence_id)
        self.audit.log(
            "evidence_sync_447",
            "evidence_item_447",
            str(case_id),
            str(case_id),
            {
                "created": created,
                "refreshed": refreshed,
                "unchanged": unchanged,
                "automatic_claim_creation": False,
                "raw_payload_duplicated": False,
            },
        )
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "created": created,
            "refreshed": refreshed,
            "unchanged": unchanged,
            "evidence_ids": ids,
            "preflight": preflight,
            "automatic_claim_creation": False,
            "raw_payload_duplicated": False,
        }

    def _decode_evidence(self, row):
        d = dict(row)
        for key in ("source_snapshot_json", "provenance_json", "usage_json", "descriptive_json"):
            d[key[:-5]] = json.loads(d.pop(key))
        return d

    def evidence(self, evidence_id):
        row = self.db.one(
            "SELECT * FROM evidence_item_447 WHERE evidence_id=?",
            (str(evidence_id),),
        )
        if not row:
            raise KeyError("Build-447 evidence item not found")
        return self._decode_evidence(row)

    def case_evidence(self, case_id):
        return [
            self._decode_evidence(row)
            for row in self.db.all(
                "SELECT * FROM evidence_item_447 WHERE case_id=? "
                "ORDER BY observed_at,evidence_id",
                (str(case_id),),
            )
        ]

    def review_evidence(self, *, identity, evidence_id, decision, note, confirmation):
        item = self.evidence(evidence_id)
        ident = self._authorize(identity, item["case_id"], "source.review", evidence_id)
        if str(confirmation or "").strip().upper() != EVIDENCE_CONFIRM:
            raise PermissionError(f"explicit {EVIDENCE_CONFIRM} confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in EVIDENCE_STATES - {"unreviewed"}:
            raise ValueError("unsupported evidence review decision")
        why = _clean(note, 4000)
        if len(why) < 8:
            raise ValueError("evidence review note must be documented")
        row = dict(
            self.db.one("SELECT * FROM evidence_item_447 WHERE evidence_id=?", (evidence_id,))
        )
        row["review_state"] = decision
        row["review_note"] = why
        row["reviewed_by"] = str(ident["username"])
        row["reviewed_at"] = _now()
        row["updated_at"] = row["reviewed_at"]
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE evidence_item_447 SET review_state=?,review_note=?,reviewed_by=?,"
            "reviewed_at=?,updated_at=?,record_hash=? WHERE evidence_id=?",
            (
                row["review_state"], row["review_note"], row["reviewed_by"],
                row["reviewed_at"], row["updated_at"], row["record_hash"], evidence_id,
            ),
        )
        self.audit.log(
            "evidence_reviewed_447",
            "evidence_item_447",
            evidence_id,
            item["case_id"],
            {"decision": decision, "truth_assigned": False},
        )
        return self.evidence(evidence_id)

    def _decode_claim(self, row):
        d = dict(row)
        d["links"] = [
            dict(x)
            for x in self.db.all(
                "SELECT * FROM claim_evidence_link_447 WHERE claim_id=? "
                "ORDER BY stance,created_at,link_id",
                (d["claim_id"],),
            )
        ]
        return d

    def claim(self, claim_id):
        row = self.db.one("SELECT * FROM claim_447 WHERE claim_id=?", (str(claim_id),))
        if not row:
            raise KeyError("Build-447 claim not found")
        return self._decode_claim(row)

    def case_claims(self, case_id):
        return [
            self._decode_claim(row)
            for row in self.db.all(
                "SELECT * FROM claim_447 WHERE case_id=? ORDER BY created_at,claim_id",
                (str(case_id),),
            )
        ]

    def propose_claim(
        self,
        *,
        identity,
        case_id,
        statement,
        support_evidence_ids,
        contradiction_evidence_ids=None,
        context_evidence_ids=None,
        uncertainty_note="",
    ):
        ident = self._authorize(identity, case_id, "dossier.write", case_id)
        statement = _clean(statement, 12000)
        if not statement:
            raise ValueError("claim statement required")
        support = list(dict.fromkeys(str(x) for x in (support_evidence_ids or []) if str(x)))
        contra = list(dict.fromkeys(str(x) for x in (contradiction_evidence_ids or []) if str(x)))
        context = list(dict.fromkeys(str(x) for x in (context_evidence_ids or []) if str(x)))
        if not support:
            raise ValueError("at least one supporting evidence reference is required")
        all_ids = support + contra + context
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("one evidence item cannot have multiple stances on the same claim")
        if len(all_ids) > 50:
            raise ValueError("claim evidence-link limit exceeded")

        evidence = {}
        for evidence_id in all_ids:
            item = self.evidence(evidence_id)
            if item["case_id"] != str(case_id):
                raise PermissionError("claim evidence must belong to the same case")
            if item["review_state"] not in {"accepted", "context_only"}:
                raise PermissionError("claim evidence must be human-reviewed before linking")
            evidence[evidence_id] = item
        if any(evidence[x]["review_state"] != "accepted" for x in support):
            raise PermissionError("supporting evidence must be accepted, not context-only")

        uncertainty = _clean(uncertainty_note, 6000)
        if contra and len(uncertainty) < 12:
            raise ValueError("claims with counterevidence require an explicit uncertainty note")

        claim_id = "claim447_" + secrets.token_hex(10)
        now = _now()
        row = {
            "claim_id": claim_id,
            "case_id": str(case_id),
            "statement": statement,
            "state": "candidate_review_required",
            "uncertainty_note": uncertainty,
            "created_by": str(ident["username"]),
            "created_at": now,
            "reviewed_by": "",
            "reviewed_at": "",
            "review_note": "",
            "updated_at": now,
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO claim_447 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        for stance, ids in (("support", support), ("contradict", contra), ("context", context)):
            for evidence_id in ids:
                item = evidence[evidence_id]
                link = {
                    "link_id": "clink447_" + secrets.token_hex(10),
                    "claim_id": claim_id,
                    "case_id": str(case_id),
                    "evidence_id": evidence_id,
                    "stance": stance,
                    "note": "",
                    "evidence_hash_at_link": str(item["record_hash"]),
                    "created_by": str(ident["username"]),
                    "created_at": now,
                }
                link["record_hash"] = self._rh(link)
                self.db.execute(
                    "INSERT INTO claim_evidence_link_447 VALUES("
                    + ",".join("?" for _ in link)
                    + ")",
                    tuple(link.values()),
                )
        self.audit.log(
            "claim_proposed_447",
            "claim_447",
            claim_id,
            str(case_id),
            {
                "support": len(support),
                "contradict": len(contra),
                "context": len(context),
                "automatic_truth_acceptance": False,
            },
        )
        return self.claim(claim_id)

    def review_claim(self, *, identity, claim_id, decision, note, confirmation):
        claim = self.claim(claim_id)
        ident = self._authorize(identity, claim["case_id"], "dossier.review", claim_id)
        if str(confirmation or "").strip().upper() != CLAIM_CONFIRM:
            raise PermissionError(f"explicit {CLAIM_CONFIRM} confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in CLAIM_STATES - {"candidate_review_required"}:
            raise ValueError("unsupported claim review decision")
        why = _clean(note, 5000)
        if len(why) < 8:
            raise ValueError("claim review note must be documented")

        links = claim["links"]
        support = [x for x in links if x["stance"] == "support"]
        contra = [x for x in links if x["stance"] == "contradict"]
        if decision == "accepted_for_dossier":
            if not support:
                raise ValueError("accepted claim requires supporting evidence")
            for link in links:
                ev = self.evidence(link["evidence_id"])
                if ev["record_hash"] != link["evidence_hash_at_link"]:
                    raise PermissionError("linked evidence changed after claim proposal")
                if link["stance"] == "support" and ev["review_state"] != "accepted":
                    raise PermissionError("supporting evidence is no longer accepted")
            if contra and len(str(claim.get("uncertainty_note") or "")) < 12:
                raise ValueError("counterevidence requires an explicit uncertainty note")

        row = dict(self.db.one("SELECT * FROM claim_447 WHERE claim_id=?", (claim_id,)))
        row["state"] = decision
        row["reviewed_by"] = str(ident["username"])
        row["reviewed_at"] = _now()
        row["review_note"] = why
        row["updated_at"] = row["reviewed_at"]
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE claim_447 SET state=?,reviewed_by=?,reviewed_at=?,review_note=?,"
            "updated_at=?,record_hash=? WHERE claim_id=?",
            (
                row["state"], row["reviewed_by"], row["reviewed_at"], row["review_note"],
                row["updated_at"], row["record_hash"], claim_id,
            ),
        )
        self.audit.log(
            "claim_reviewed_447",
            "claim_447",
            claim_id,
            claim["case_id"],
            {"decision": decision, "truth_determined": False},
        )
        return self.claim(claim_id)

    def _claim_snapshot(self, claim):
        links = []
        for link in claim["links"]:
            ev = self.evidence(link["evidence_id"])
            links.append(
                {
                    "link_id": link["link_id"],
                    "stance": link["stance"],
                    "evidence_id": ev["evidence_id"],
                    "evidence_kind": ev["evidence_kind"],
                    "title": ev["title"],
                    "canonical_url": ev["canonical_url"],
                    "observed_at": ev["observed_at"],
                    "content_sha256": ev["content_sha256"],
                    "source_id": ev["source_id"],
                    "source_snapshot": ev["source_snapshot"],
                    "provenance": ev["provenance"],
                    "review_state": ev["review_state"],
                    "review_note": ev["review_note"],
                    "evidence_record_hash": ev["record_hash"],
                }
            )
        return {
            "claim_id": claim["claim_id"],
            "statement": claim["statement"],
            "state": claim["state"],
            "uncertainty_note": claim["uncertainty_note"],
            "review_note": claim["review_note"],
            "links": links,
        }

    def _latest_synthesis(self, session_id):
        row = self.db.one(
            "SELECT * FROM investigation_synthesis_419 "
            "WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (str(session_id),),
        )
        if not row:
            return None
        item = dict(row)
        item["summary"] = json.loads(item.get("summary_json") or "{}")
        return item

    def build_dossier(self, *, identity, case_id, title="", loop_id=""):
        ident = self._authorize(identity, case_id, "dossier.write", case_id)
        self._preflight()
        case = self.cases.get_case(str(case_id))
        claims = [x for x in self.case_claims(case_id) if x["state"] == "accepted_for_dossier"]
        if not claims:
            raise ValueError("at least one human-reviewed accepted claim is required")

        loop = None
        matrix = None
        synthesis = None
        executions = []
        if loop_id:
            loop = self.loop439.loop(loop_id)
            if loop["case_id"] != str(case_id):
                raise PermissionError("dossier loop must belong to the same case")
            matrix = self.matrix418.matrix(
                session_id=loop["session_id"],
                identity=ident,
            )
            synthesis = self._latest_synthesis(loop["session_id"])
            executions = self.dispatcher446.executions(loop_id)

        claim_snapshots = [self._claim_snapshot(x) for x in claims]
        evidence_ids = sorted(
            {
                link["evidence_id"]
                for claim in claim_snapshots
                for link in claim["links"]
            }
        )
        counter_links = [
            {"claim_id": claim["claim_id"], **link}
            for claim in claim_snapshots
            for link in claim["links"]
            if link["stance"] == "contradict"
        ]
        open_uncertainties = [
            {
                "claim_id": claim["claim_id"],
                "uncertainty_note": claim["uncertainty_note"],
            }
            for claim in claim_snapshots
            if claim["uncertainty_note"]
        ]
        if matrix:
            for gap in matrix.get("gaps") or []:
                open_uncertainties.append({"type": "hypothesis_gap", "detail": gap})
            for conflict in matrix.get("conflicts") or []:
                open_uncertainties.append({"type": "matrix_conflict", "detail": conflict})

        prior = self.db.one(
            "SELECT MAX(revision_no) n FROM dossier_revision_447 WHERE case_id=?",
            (str(case_id),),
        )
        revision_no = int((prior or {}).get("n") or 0) + 1
        snapshot = {
            "build": BUILD,
            "case": {
                "case_id": case.get("case_id"),
                "title": case.get("title"),
                "client": case.get("client"),
                "purpose": case.get("purpose"),
                "legal_basis": case.get("legal_basis"),
                "status": case.get("status"),
            },
            "loop": (
                {
                    "loop_id": loop.get("loop_id"),
                    "objective": loop.get("objective"),
                    "state": loop.get("state"),
                    "current_cycle": loop.get("current_cycle"),
                    "max_cycles": loop.get("max_cycles"),
                }
                if loop
                else None
            ),
            "claims": claim_snapshots,
            "evidence_ids": evidence_ids,
            "counterevidence": counter_links,
            "open_uncertainties": open_uncertainties,
            "hypothesis_matrix": matrix,
            "latest_synthesis": (
                {
                    "synthesis_id": synthesis.get("synthesis_id"),
                    "title": synthesis.get("title"),
                    "summary": synthesis.get("summary"),
                    "record_hash": synthesis.get("record_hash"),
                }
                if synthesis
                else None
            ),
            "build446_executions": [
                {
                    "execution_id": x["execution_id"],
                    "dispatch_id": x["dispatch_id"],
                    "source_id": x["source_id"],
                    "route": x["route"],
                    "state": x["state"],
                    "external_network": x["external_network"],
                }
                for x in executions
            ],
            "closure_contract": {
                "every_claim_has_source_trace": all(bool(c["links"]) for c in claim_snapshots),
                "counterevidence_preserved": True,
                "uncertainty_preserved": True,
                "automatic_truth_determination": False,
                "automatic_claim_acceptance": False,
                "human_review_required": True,
            },
        }
        now = _now()
        row = {
            "revision_id": "dos447_" + secrets.token_hex(10),
            "case_id": str(case_id),
            "loop_id": str(loop_id or ""),
            "revision_no": revision_no,
            "title": _clean(title or f"Living Dossier — {case.get('title') or case_id}", 1000),
            "state": "draft_for_review",
            "snapshot_json": _canon(snapshot),
            "created_by": str(ident["username"]),
            "created_at": now,
            "reviewed_by": "",
            "reviewed_at": "",
            "review_note": "",
            "updated_at": now,
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO dossier_revision_447 VALUES("
            + ",".join("?" for _ in row)
            + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "dossier_revision_created_447",
            "dossier_revision_447",
            row["revision_id"],
            str(case_id),
            {
                "revision_no": revision_no,
                "claims": len(claims),
                "evidence": len(evidence_ids),
                "state": "draft_for_review",
                "automatic_publication": False,
            },
        )
        return self.dossier(row["revision_id"])

    def _decode_dossier(self, row):
        d = dict(row)
        d["snapshot"] = json.loads(d.pop("snapshot_json"))
        return d

    def dossier(self, revision_id):
        row = self.db.one(
            "SELECT * FROM dossier_revision_447 WHERE revision_id=?",
            (str(revision_id),),
        )
        if not row:
            raise KeyError("Build-447 dossier revision not found")
        return self._decode_dossier(row)

    def case_dossiers(self, case_id):
        return [
            self._decode_dossier(row)
            for row in self.db.all(
                "SELECT * FROM dossier_revision_447 WHERE case_id=? "
                "ORDER BY revision_no,created_at",
                (str(case_id),),
            )
        ]

    def review_dossier(self, *, identity, revision_id, decision, note, confirmation):
        dossier = self.dossier(revision_id)
        ident = self._authorize(identity, dossier["case_id"], "dossier.review", revision_id)
        if str(confirmation or "").strip().upper() != DOSSIER_CONFIRM:
            raise PermissionError(f"explicit {DOSSIER_CONFIRM} confirmation required")
        decision = str(decision or "").strip().lower()
        if decision not in {"approved_for_export", "changes_required"}:
            raise ValueError("unsupported dossier review decision")
        why = _clean(note, 6000)
        if len(why) < 8:
            raise ValueError("dossier review note must be documented")
        if decision == "approved_for_export":
            integrity = self.verify_integrity()
            if not integrity["valid"]:
                raise PermissionError("Build-447 integrity must be valid before approval")
            snapshot = dossier["snapshot"]
            if not snapshot.get("claims"):
                raise ValueError("approved dossier requires accepted claims")
            for claim in snapshot["claims"]:
                if claim.get("state") != "accepted_for_dossier":
                    raise PermissionError("dossier contains a non-accepted claim")
                if not any(x.get("stance") == "support" for x in claim.get("links") or []):
                    raise PermissionError("every dossier claim requires supporting evidence")

        row = dict(
            self.db.one("SELECT * FROM dossier_revision_447 WHERE revision_id=?", (revision_id,))
        )
        row["state"] = decision
        row["reviewed_by"] = str(ident["username"])
        row["reviewed_at"] = _now()
        row["review_note"] = why
        row["updated_at"] = row["reviewed_at"]
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE dossier_revision_447 SET state=?,reviewed_by=?,reviewed_at=?,"
            "review_note=?,updated_at=?,record_hash=? WHERE revision_id=?",
            (
                row["state"], row["reviewed_by"], row["reviewed_at"],
                row["review_note"], row["updated_at"], row["record_hash"], revision_id,
            ),
        )
        self.audit.log(
            "dossier_reviewed_447",
            "dossier_revision_447",
            revision_id,
            dossier["case_id"],
            {"decision": decision, "truth_determined": False},
        )
        return self.dossier(revision_id)

    def _sections(self, dossier):
        snap = dossier["snapshot"]
        case = snap["case"]
        sections = []
        sections.append(
            (
                "1. Fallrahmen",
                [
                    f"Fall-ID: {case.get('case_id')}",
                    f"Titel: {case.get('title')}",
                    f"Zweck: {case.get('purpose')}",
                    f"Rechtsgrundlage: {case.get('legal_basis')}",
                    f"Dossier-Revision: {dossier.get('revision_no')}",
                    f"Review-Status: {dossier.get('state')}",
                ],
            )
        )
        claim_rows = [["Claim-ID", "Statement", "Uncertainty", "Review"]]
        for claim in snap.get("claims") or []:
            claim_rows.append(
                [
                    claim.get("claim_id", ""),
                    claim.get("statement", ""),
                    claim.get("uncertainty_note", ""),
                    claim.get("state", ""),
                ]
            )
        sections.append(("2. Human-reviewed Claims", claim_rows))

        link_rows = [["Claim", "Stance", "Evidence", "Kind", "Source", "URL", "SHA-256"]]
        for claim in snap.get("claims") or []:
            for link in claim.get("links") or []:
                link_rows.append(
                    [
                        claim.get("claim_id", ""),
                        link.get("stance", ""),
                        link.get("evidence_id", ""),
                        link.get("evidence_kind", ""),
                        link.get("source_id", ""),
                        link.get("canonical_url", ""),
                        link.get("content_sha256", ""),
                    ]
                )
        sections.append(("3. Claim ↔ Evidence Matrix", link_rows))

        counter_rows = [["Claim", "Evidence", "Source", "URL"]]
        for link in snap.get("counterevidence") or []:
            counter_rows.append(
                [
                    link.get("claim_id", ""),
                    link.get("evidence_id", ""),
                    link.get("source_id", ""),
                    link.get("canonical_url", ""),
                ]
            )
        sections.append(("4. Counterevidence", counter_rows))

        uncertainty_lines = [
            json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
            for x in (snap.get("open_uncertainties") or [])
        ] or ["Keine zusätzlichen offenen Unsicherheiten in dieser Revision dokumentiert."]
        sections.append(("5. Unsicherheiten und offene Prüfpfade", uncertainty_lines))

        synthesis = snap.get("latest_synthesis") or {}
        sections.append(
            (
                "6. Investigation Synthesis",
                [
                    f"Synthesis-ID: {synthesis.get('synthesis_id') or 'nicht gebunden'}",
                    json.dumps(synthesis.get("summary") or {}, ensure_ascii=False, sort_keys=True, default=str),
                ],
            )
        )

        provenance_rows = [["Evidence", "Source", "Observed", "Content Hash", "Source Snapshot"]]
        seen = set()
        for claim in snap.get("claims") or []:
            for link in claim.get("links") or []:
                if link.get("evidence_id") in seen:
                    continue
                seen.add(link.get("evidence_id"))
                provenance_rows.append(
                    [
                        link.get("evidence_id", ""),
                        link.get("source_id", ""),
                        link.get("observed_at", ""),
                        link.get("content_sha256", ""),
                        json.dumps(link.get("source_snapshot") or {}, ensure_ascii=False, sort_keys=True),
                    ]
                )
        sections.append(("7. Provenance Index", provenance_rows))
        sections.append(
            (
                "8. Schlussvermerk",
                [
                    "Dieses Dossier trennt Beobachtungen, Evidence, Claims, Hypothesen und Synthese.",
                    "Claim-Akzeptanz ist eine menschliche Review-Entscheidung und keine automatische Wahrheitsfeststellung.",
                    "Gegenbelege und Unsicherheiten sind Teil des Dossiers und dürfen nicht stillschweigend entfernt werden.",
                    "Das Case-Package enthält Referenzen und Hashes, nicht automatisch die Rohinhalte der Quellen.",
                ],
            )
        )
        return sections

    def export_dossier(self, *, identity, revision_id, confirmation):
        dossier = self.dossier(revision_id)
        ident = self._authorize(
            identity,
            dossier["case_id"],
            "dossier.export.execute",
            revision_id,
        )
        if str(confirmation or "").strip().upper() != EXPORT_CONFIRM:
            raise PermissionError(f"explicit {EXPORT_CONFIRM} confirmation required")
        if dossier["state"] != "approved_for_export":
            raise PermissionError("dossier must be human-approved before export")
        integrity = self.verify_integrity()
        if not integrity["valid"]:
            raise PermissionError("Build-447 integrity must be valid before export")

        export_id = "dexp447_" + secrets.token_hex(10)
        outdir = (
            self.base_dir
            / "exports"
            / "build447"
            / dossier["case_id"]
            / dossier["revision_id"]
            / export_id
        )
        outdir.mkdir(parents=True, exist_ok=False)
        base = outdir / "EagleEye_Living_Dossier"
        snapshot = {
            "revision": {
                k: dossier[k]
                for k in (
                    "revision_id", "case_id", "loop_id", "revision_no", "title",
                    "state", "created_by", "created_at", "reviewed_by", "reviewed_at",
                    "review_note", "record_hash",
                )
            },
            "snapshot": dossier["snapshot"],
        }
        json_path = base.with_suffix(".json")
        json_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2, default=str),
            encoding="utf-8",
        )
        sections = self._sections(dossier)
        docx_path = write_docx(base.with_suffix(".docx"), dossier["title"], sections)
        pdf_lines = []
        for heading, body in sections:
            pdf_lines.append(heading)
            if body and isinstance(body[0], list):
                for row in body:
                    pdf_lines.append(" | ".join(str(x) for x in row))
            else:
                pdf_lines.extend(str(x) for x in body)
            pdf_lines.append("")
        pdf_path = write_pdf(base.with_suffix(".pdf"), dossier["title"], pdf_lines)

        file_hashes = {}
        for path in (json_path, docx_path, pdf_path):
            file_hashes[path.name] = hashlib.sha256(Path(path).read_bytes()).hexdigest()

        manifest = {
            "build": BUILD,
            "case_id": dossier["case_id"],
            "revision_id": dossier["revision_id"],
            "revision_no": dossier["revision_no"],
            "dossier_record_hash": dossier["record_hash"],
            "files": file_hashes,
            "raw_source_payloads_included": False,
            "counterevidence_preserved": True,
            "uncertainty_preserved": True,
            "truth_determined": False,
            "created_at": _now(),
        }
        manifest_path = outdir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        file_hashes[manifest_path.name] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        package_path = outdir / "EagleEye_Case_Package_447.zip"
        with ZipFile(package_path, "w", ZIP_DEFLATED) as z:
            for path in (json_path, docx_path, pdf_path, manifest_path):
                z.write(path, arcname=Path(path).name)
        package_hash = hashlib.sha256(package_path.read_bytes()).hexdigest()
        paths = {
            "json": str(json_path),
            "docx": str(docx_path),
            "pdf": str(pdf_path),
            "manifest": str(manifest_path),
            "case_package": str(package_path),
        }
        export = {
            "export_id": export_id,
            "revision_id": revision_id,
            "case_id": dossier["case_id"],
            "paths_json": _canon(paths),
            "hashes_json": _canon(file_hashes),
            "package_hash": package_hash,
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        export["record_hash"] = self._rh(export)
        self.db.execute(
            "INSERT INTO dossier_export_447 VALUES("
            + ",".join("?" for _ in export)
            + ")",
            tuple(export.values()),
        )
        self.audit.log(
            "dossier_exported_447",
            "dossier_export_447",
            export["export_id"],
            dossier["case_id"],
            {
                "revision_id": revision_id,
                "package_hash": package_hash,
                "raw_source_payloads_included": False,
            },
        )
        return {
            **export,
            "paths": paths,
            "hashes": file_hashes,
            "raw_source_payloads_included": False,
        }

    def exports(self, case_id):
        out = []
        for row in self.db.all(
            "SELECT * FROM dossier_export_447 WHERE case_id=? ORDER BY created_at,export_id",
            (str(case_id),),
        ):
            d = dict(row)
            d["paths"] = json.loads(d.pop("paths_json"))
            d["hashes"] = json.loads(d.pop("hashes_json"))
            out.append(d)
        return out

    def run_case_selftest(self, *, identity, case_id):
        ident = self._identity(identity)
        live = self.dispatcher446.run_case_selftest(identity=ident, case_id=str(case_id))
        if live["result"] != "PASS":
            return {
                "build": BUILD,
                "case_id": str(case_id),
                "result": "FAIL",
                "checks": {"build446_dependency": False},
            }
        sync = self.sync_case_evidence(identity=ident, case_id=str(case_id))
        items = self.case_evidence(case_id)
        if len(items) < 2:
            raise RuntimeError("Build-447 selftest requires at least two evidence items")
        support = self.review_evidence(
            identity=ident,
            evidence_id=items[0]["evidence_id"],
            decision="accepted",
            note="Accepted as a synthetic provenance-qualified support item.",
            confirmation=EVIDENCE_CONFIRM,
        )
        contra = self.review_evidence(
            identity=ident,
            evidence_id=items[1]["evidence_id"],
            decision="accepted",
            note="Accepted as a synthetic counterevidence test item.",
            confirmation=EVIDENCE_CONFIRM,
        )
        claim = self.propose_claim(
            identity=ident,
            case_id=str(case_id),
            statement="Synthetic Build 447 claim used only to qualify Evidence-to-Dossier closure.",
            support_evidence_ids=[support["evidence_id"]],
            contradiction_evidence_ids=[contra["evidence_id"]],
            uncertainty_note="Synthetic counterevidence is intentionally retained to test uncertainty preservation.",
        )
        claim = self.review_claim(
            identity=ident,
            claim_id=claim["claim_id"],
            decision="accepted_for_dossier",
            note="Accepted only for deterministic Build-447 workflow qualification.",
            confirmation=CLAIM_CONFIRM,
        )
        dossier = self.build_dossier(
            identity=ident,
            case_id=str(case_id),
            loop_id=live["loop_id"],
            title="Build 447 deterministic Living Dossier",
        )
        dossier = self.review_dossier(
            identity=ident,
            revision_id=dossier["revision_id"],
            decision="approved_for_export",
            note="Approved only for deterministic Build-447 export qualification.",
            confirmation=DOSSIER_CONFIRM,
        )
        export = self.export_dossier(
            identity=ident,
            revision_id=dossier["revision_id"],
            confirmation=EXPORT_CONFIRM,
        )
        checks = {
            "build446_dependency": True,
            "evidence_synced": sync["created"] + sync["refreshed"] >= 2,
            "evidence_human_reviewed": support["review_state"] == "accepted" and contra["review_state"] == "accepted",
            "claim_has_support": any(x["stance"] == "support" for x in claim["links"]),
            "claim_has_counterevidence": any(x["stance"] == "contradict" for x in claim["links"]),
            "claim_human_reviewed": claim["state"] == "accepted_for_dossier",
            "dossier_starts_reviewable": dossier["state"] == "approved_for_export",
            "counterevidence_in_dossier": bool(dossier["snapshot"]["counterevidence"]),
            "uncertainty_in_dossier": bool(dossier["snapshot"]["open_uncertainties"]),
            "synthesis_bound": bool((dossier["snapshot"].get("latest_synthesis") or {}).get("synthesis_id")),
            "docx_created": Path(export["paths"]["docx"]).exists(),
            "pdf_created": Path(export["paths"]["pdf"]).exists(),
            "case_package_created": Path(export["paths"]["case_package"]).exists(),
            "raw_payload_not_packaged": export["raw_source_payloads_included"] is False,
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "loop_id": live["loop_id"],
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "claim_id": claim["claim_id"],
            "revision_id": dossier["revision_id"],
            "export_id": export["export_id"],
            "note": (
                "Deterministic closure qualification. Synthetic data only; "
                "claim and dossier review are explicit human actions."
            ),
        }

    def verify_integrity(self):
        bad = []
        upstream = {
            "acquisition_source_421": self.registry421.verify_integrity(),
            "acquisition_event_422": self.events422.verify_integrity(),
            "content_store_423": self.content423.verify_integrity(),
            "news_item_429": self.news429.verify_integrity(),
            "social_observation_432": self.social432.verify_integrity(),
        }
        for component, result in upstream.items():
            if not result.get("valid", False):
                bad.append(
                    {
                        "table": component,
                        "id": component,
                        "reason": "upstream_integrity_invalid",
                        "violations": result.get("violations") or [],
                    }
                )
        for table, key in (
            ("evidence_item_447", "evidence_id"),
            ("claim_447", "claim_id"),
            ("claim_evidence_link_447", "link_id"),
            ("dossier_revision_447", "revision_id"),
            ("dossier_export_447", "export_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    bad.append(
                        {"table": table, "id": item.get(key), "reason": "record_hash_mismatch"}
                    )

        for row in self.db.all("SELECT * FROM evidence_item_447"):
            ev = dict(row)
            current = {
                "source_record_hash": self._row(
                    "acquisition_source_421", "source_id", ev["source_id"]
                ),
                "event_record_hash": self._row(
                    "acquisition_event_422", "event_id", ev["event_id"]
                ),
                "content_record_hash": self._row(
                    "content_object_423", "content_id", ev["content_id"]
                ),
                "observation_record_hash": self._row(
                    "content_observation_423", "observation_id", ev["observation_id"]
                ),
            }
            for field, underlying in current.items():
                if not underlying:
                    bad.append(
                        {
                            "table": "evidence_item_447",
                            "id": ev["evidence_id"],
                            "reason": field.replace("_record_hash", "") + "_missing",
                        }
                    )
                elif str(underlying.get("record_hash") or "") != str(ev.get(field) or ""):
                    bad.append(
                        {
                            "table": "evidence_item_447",
                            "id": ev["evidence_id"],
                            "reason": field + "_changed",
                        }
                    )

        for row in self.db.all("SELECT * FROM claim_evidence_link_447"):
            link = dict(row)
            ev = self.db.one(
                "SELECT record_hash FROM evidence_item_447 WHERE evidence_id=?",
                (link["evidence_id"],),
            )
            if not ev:
                bad.append(
                    {
                        "table": "claim_evidence_link_447",
                        "id": link["link_id"],
                        "reason": "linked_evidence_missing",
                    }
                )
            elif str(ev["record_hash"]) != str(link["evidence_hash_at_link"]):
                bad.append(
                    {
                        "table": "claim_evidence_link_447",
                        "id": link["link_id"],
                        "reason": "linked_evidence_changed_after_claim",
                    }
                )
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        evidence = int(self.db.one("SELECT COUNT(*) n FROM evidence_item_447")["n"])
        claims = int(self.db.one("SELECT COUNT(*) n FROM claim_447")["n"])
        accepted = int(
            self.db.one(
                "SELECT COUNT(*) n FROM claim_447 WHERE state='accepted_for_dossier'"
            )["n"]
        )
        dossiers = int(self.db.one("SELECT COUNT(*) n FROM dossier_revision_447")["n"])
        exports = int(self.db.one("SELECT COUNT(*) n FROM dossier_export_447")["n"])
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "evidence_items": evidence,
            "claims": claims,
            "accepted_claims": accepted,
            "dossier_revisions": dossiers,
            "exports": exports,
            "integrity_valid": self.verify_integrity()["valid"],
            "evidence_viewer": True,
            "source_snapshots": True,
            "claim_evidence_links": True,
            "counterevidence_preserved": True,
            "uncertainty_preserved": True,
            "living_dossier_revisions": True,
            "docx_export": True,
            "pdf_export": True,
            "case_package_export": True,
            "raw_payload_duplicated": False,
            "automatic_claim_creation": False,
            "automatic_claim_acceptance": False,
            "automatic_truth_determination": False,
            "automatic_dossier_publication": False,
            "human_evidence_review_required": True,
            "human_claim_review_required": True,
            "human_dossier_review_required": True,
            "formal_four_eyes_export_workflow_deferred_to_build449": True,
            "production_release_ready": False,
        }
