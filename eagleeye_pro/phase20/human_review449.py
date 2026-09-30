from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import secrets

BUILD = "449.0"
POLICY_ID = "phase20.human-review-team-workflow.v449"

OBJECT_TYPES = {"evidence", "claim", "dossier", "dossier_export"}
REVIEW_STATES = {"pending", "claimed", "completed", "denied", "stale", "cancelled"}
COMMENT_KINDS = {"comment", "challenge", "agreement", "counter_hypothesis"}

REQUEST_CAPABILITY = {
    "evidence": "research.run",
    "claim": "dossier.write",
    "dossier": "dossier.write",
    "dossier_export": "dossier.export.request",
}
REVIEW_CAPABILITY = {
    "evidence": "source.review",
    "claim": "dossier.review",
    "dossier": "dossier.review",
    "dossier_export": "dossier.export.approve",
}
CONFIRMATIONS = {
    "evidence": "REVIEW EVIDENCE 447",
    "claim": "REVIEW CLAIM 447",
    "dossier": "APPROVE DOSSIER 447",
    "dossier_export": "APPROVE DOSSIER EXPORT 449",
}
VALID_DECISIONS = {
    "evidence": {"accepted", "context_only", "rejected"},
    "claim": {"accepted_for_dossier", "needs_more_evidence", "rejected"},
    "dossier": {"approved_for_export", "changes_required"},
    "dossier_export": {"approve", "deny"},
}
POSITIVE_DECISIONS = {
    "evidence": {"accepted", "context_only"},
    "claim": {"accepted_for_dossier"},
    "dossier": {"approved_for_export"},
    "dossier_export": {"approve"},
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _clean(value, limit=6000):
    return " ".join(str(value or "").split())[:limit]


class HumanReviewTeamWorkflow449:
    """Formal four-eyes review and team handoff layer for Build-447 artifacts.

    The service never changes Evidence/Claim/Dossier semantics itself. It creates
    case-scoped review work, enforces reviewer separation, detects stale objects,
    and delegates the final object decision to the existing Build-447 review
    functions with their original confirmation phrases.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        closure447,
        workspace448,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.closure447 = closure447
        self.workspace448 = workspace448
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS review_request_449(
            review_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            object_hash_at_request TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            assigned_to TEXT NOT NULL,
            state TEXT NOT NULL,
            request_note TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            claimed_by TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            decision TEXT NOT NULL,
            completed_by TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            review_note TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_review449_case_state
            ON review_request_449(case_id,state,requested_at);
            CREATE INDEX IF NOT EXISTS idx_review449_object
            ON review_request_449(case_id,object_type,object_id,requested_at);

            CREATE TABLE IF NOT EXISTS review_comment_449(
            comment_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_review_comment449_review
            ON review_comment_449(review_id,created_at);

            CREATE TABLE IF NOT EXISTS review_export_execution_449(
            execution_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL UNIQUE,
            revision_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            export_id TEXT NOT NULL,
            package_hash TEXT NOT NULL,
            executed_by TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_review_export449_case
            ON review_export_execution_449(case_id,executed_at);
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
        return {**user, "session_id": str(identity.get("session_id") or "review449")}

    def _authorize(self, identity, case_id, capability, object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="human_review_449",
            object_id=str(object_id or case_id),
        )
        return ident

    def _object(self, object_type, object_id):
        object_type = str(object_type or "").strip().lower()
        if object_type not in OBJECT_TYPES:
            raise ValueError("unsupported review object type")
        if object_type == "evidence":
            item = self.closure447.evidence(str(object_id))
            creator = ""
            state = item["review_state"]
            case_id = item["case_id"]
        elif object_type == "claim":
            item = self.closure447.claim(str(object_id))
            creator = str(item.get("created_by") or "")
            state = item["state"]
            case_id = item["case_id"]
        else:
            item = self.closure447.dossier(str(object_id))
            creator = str(item.get("created_by") or "")
            state = item["state"]
            case_id = item["case_id"]
        return {
            "object_type": object_type,
            "object_id": str(object_id),
            "case_id": str(case_id),
            "creator": creator,
            "state": str(state),
            "record_hash": str(item.get("record_hash") or ""),
            "item": item,
        }

    @staticmethod
    def _requestable(obj):
        if obj["object_type"] == "evidence":
            return obj["state"] == "unreviewed"
        if obj["object_type"] == "claim":
            return obj["state"] == "candidate_review_required"
        if obj["object_type"] == "dossier":
            return obj["state"] == "draft_for_review"
        return obj["state"] == "approved_for_export"

    def eligible_reviewers(self, case_id, object_type):
        object_type = str(object_type or "").strip().lower()
        if object_type not in OBJECT_TYPES:
            raise ValueError("unsupported review object type")
        capability = REVIEW_CAPABILITY[object_type]
        rows = []
        seen = set()
        for membership in self.governance.identity.list_case_memberships(str(case_id)):
            if not bool(membership.get("active")):
                continue
            username = str(membership.get("username") or "")
            if not username or username in seen:
                continue
            try:
                caps = set(self.governance.effective_capabilities(username, str(case_id)))
            except (KeyError, PermissionError, ValueError):
                continue
            if capability not in caps:
                continue
            user = self.governance.identity.public_user(username)
            rows.append(
                {
                    "username": username,
                    "display_name": user.get("display_name") or username,
                    "global_role": user.get("global_role") or "",
                    "case_roles": self.governance.case_roles(username, str(case_id)),
                    "capability": capability,
                }
            )
            seen.add(username)
        return sorted(rows, key=lambda x: (x["display_name"].casefold(), x["username"]))

    def _reviewer_eligible(self, username, case_id, object_type):
        username = str(username or "").strip()
        if not username:
            return False
        return any(x["username"] == username for x in self.eligible_reviewers(case_id, object_type))

    def _decode_request(self, row):
        return dict(row)

    def review(self, review_id):
        row = self.db.one("SELECT * FROM review_request_449 WHERE review_id=?", (str(review_id),))
        if not row:
            raise KeyError("Build-449 review request not found")
        return self._decode_request(row)

    def comments(self, review_id):
        return [
            dict(row)
            for row in self.db.all(
                "SELECT * FROM review_comment_449 WHERE review_id=? ORDER BY created_at,rowid",
                (str(review_id),),
            )
        ]

    def _active_duplicate(self, case_id, object_type, object_id, object_hash):
        return self.db.one(
            "SELECT * FROM review_request_449 WHERE case_id=? AND object_type=? "
            "AND object_id=? AND object_hash_at_request=? AND state IN ('pending','claimed') "
            "ORDER BY requested_at DESC,rowid DESC LIMIT 1",
            (str(case_id), str(object_type), str(object_id), str(object_hash)),
        )

    def request_review(
        self,
        *,
        identity,
        object_type,
        object_id,
        note,
        assigned_to="",
    ):
        obj = self._object(object_type, object_id)
        ident = self._authorize(
            identity,
            obj["case_id"],
            REQUEST_CAPABILITY[obj["object_type"]],
            obj["object_id"],
        )
        if not self._requestable(obj):
            raise ValueError("object is not currently eligible for this review workflow")
        why = _clean(note, 4000)
        if len(why) < 8:
            raise ValueError("review request note must be documented")

        duplicate = self._active_duplicate(
            obj["case_id"], obj["object_type"], obj["object_id"], obj["record_hash"]
        )
        if duplicate:
            return self.review(duplicate["review_id"])

        assigned_to = str(assigned_to or "").strip()
        if assigned_to:
            if assigned_to.casefold() == str(ident["username"]).casefold():
                raise PermissionError("four-eyes workflow cannot assign the request to the requester")
            if obj["creator"] and assigned_to.casefold() == obj["creator"].casefold():
                raise PermissionError("four-eyes workflow cannot assign review to the object creator")
            if not self._reviewer_eligible(assigned_to, obj["case_id"], obj["object_type"]):
                raise PermissionError("assigned user is not an eligible case reviewer")

        now = _now()
        row = {
            "review_id": "review449_" + secrets.token_hex(10),
            "case_id": obj["case_id"],
            "object_type": obj["object_type"],
            "object_id": obj["object_id"],
            "object_hash_at_request": obj["record_hash"],
            "requested_by": str(ident["username"]),
            "assigned_to": assigned_to,
            "state": "pending",
            "request_note": why,
            "requested_at": now,
            "claimed_by": "",
            "claimed_at": "",
            "decision": "",
            "completed_by": "",
            "completed_at": "",
            "review_note": "",
            "updated_at": now,
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO review_request_449 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "review_requested_449",
            "review_request_449",
            row["review_id"],
            obj["case_id"],
            {
                "object_type": obj["object_type"],
                "object_id": obj["object_id"],
                "requested_by": ident["username"],
                "assigned_to": assigned_to,
                "four_eyes_required": True,
            },
        )
        return self.review(row["review_id"])

    def _update_review(self, review_id, **changes):
        row = dict(self.db.one("SELECT * FROM review_request_449 WHERE review_id=?", (str(review_id),)))
        if not row:
            raise KeyError("Build-449 review request not found")
        row.update(changes)
        row["updated_at"] = _now()
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE review_request_449 SET assigned_to=?,state=?,claimed_by=?,claimed_at=?,"
            "decision=?,completed_by=?,completed_at=?,review_note=?,updated_at=?,record_hash=? "
            "WHERE review_id=?",
            (
                row["assigned_to"], row["state"], row["claimed_by"], row["claimed_at"],
                row["decision"], row["completed_by"], row["completed_at"], row["review_note"],
                row["updated_at"], row["record_hash"], str(review_id),
            ),
        )
        return self.review(review_id)

    def _ensure_separation(self, ident, review, obj):
        username = str(ident["username"])
        if username.casefold() == str(review["requested_by"]).casefold():
            raise PermissionError("four-eyes review requires a different user than the requester")
        if obj["creator"] and username.casefold() == obj["creator"].casefold():
            raise PermissionError("four-eyes review requires a different user than the object creator")
        if review["assigned_to"] and username.casefold() != str(review["assigned_to"]).casefold():
            raise PermissionError("review is assigned to another reviewer")
        if not self._reviewer_eligible(username, review["case_id"], review["object_type"]):
            raise PermissionError("user is not an eligible reviewer for this case/object")

    def _mark_stale_if_changed(self, review, obj):
        if str(obj["record_hash"]) == str(review["object_hash_at_request"]):
            return False
        if review["state"] in {"pending", "claimed"}:
            self._update_review(review["review_id"], state="stale")
        return True

    def claim_review(self, *, identity, review_id):
        review = self.review(review_id)
        if review["state"] != "pending":
            raise ValueError("review request is not pending")
        obj = self._object(review["object_type"], review["object_id"])
        ident = self._authorize(
            identity,
            review["case_id"],
            REVIEW_CAPABILITY[review["object_type"]],
            review_id,
        )
        self._ensure_separation(ident, review, obj)
        if self._mark_stale_if_changed(review, obj):
            raise PermissionError("review request is stale because the reviewed object changed")
        now = _now()
        updated = self._update_review(
            review_id,
            state="claimed",
            assigned_to=str(review["assigned_to"] or ident["username"]),
            claimed_by=str(ident["username"]),
            claimed_at=now,
        )
        self.audit.log(
            "review_claimed_449",
            "review_request_449",
            review_id,
            review["case_id"],
            {"reviewer": ident["username"], "object_type": review["object_type"]},
        )
        return updated

    def complete_review(
        self,
        *,
        identity,
        review_id,
        decision,
        note,
        confirmation,
    ):
        review = self.review(review_id)
        if review["state"] != "claimed":
            raise ValueError("review request must be claimed before completion")
        obj = self._object(review["object_type"], review["object_id"])
        ident = self._authorize(
            identity,
            review["case_id"],
            REVIEW_CAPABILITY[review["object_type"]],
            review_id,
        )
        self._ensure_separation(ident, review, obj)
        if str(review["claimed_by"]).casefold() != str(ident["username"]).casefold():
            raise PermissionError("only the claiming reviewer may complete this review")
        if self._mark_stale_if_changed(review, obj):
            raise PermissionError("review request is stale because the reviewed object changed")

        decision = str(decision or "").strip().lower()
        if decision not in VALID_DECISIONS[review["object_type"]]:
            raise ValueError("unsupported review decision")
        why = _clean(note, 6000)
        if len(why) < 8:
            raise ValueError("review rationale must be documented")
        expected = CONFIRMATIONS[review["object_type"]]
        if str(confirmation or "").strip().upper() != expected:
            raise PermissionError(f"explicit {expected} confirmation required")

        if review["object_type"] == "evidence":
            result = self.closure447.review_evidence(
                identity=ident,
                evidence_id=review["object_id"],
                decision=decision,
                note=why,
                confirmation=expected,
            )
        elif review["object_type"] == "claim":
            result = self.closure447.review_claim(
                identity=ident,
                claim_id=review["object_id"],
                decision=decision,
                note=why,
                confirmation=expected,
            )
        elif review["object_type"] == "dossier":
            result = self.closure447.review_dossier(
                identity=ident,
                revision_id=review["object_id"],
                decision=decision,
                note=why,
                confirmation=expected,
            )
        else:
            result = {
                "revision_id": review["object_id"],
                "decision": decision,
                "approved": decision == "approve",
                "automatic_export": False,
            }

        final_state = "completed" if decision in POSITIVE_DECISIONS[review["object_type"]] else "denied"
        updated = self._update_review(
            review_id,
            state=final_state,
            decision=decision,
            completed_by=str(ident["username"]),
            completed_at=_now(),
            review_note=why,
        )
        self.audit.log(
            "review_completed_449",
            "review_request_449",
            review_id,
            review["case_id"],
            {
                "reviewer": ident["username"],
                "decision": decision,
                "state": final_state,
                "truth_determined": False,
                "automatic_export": False,
            },
        )
        return {"review": updated, "object": result}

    def add_comment(self, *, identity, review_id, kind, body):
        review = self.review(review_id)
        ident = self._authorize(identity, review["case_id"], "case.read", review_id)
        kind = str(kind or "").strip().lower()
        if kind not in COMMENT_KINDS:
            raise ValueError("unsupported review comment kind")
        body = _clean(body, 6000)
        if len(body) < 2:
            raise ValueError("comment body required")
        row = {
            "comment_id": "rcomment449_" + secrets.token_hex(10),
            "review_id": review_id,
            "case_id": review["case_id"],
            "kind": kind,
            "body": body,
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO review_comment_449 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "review_comment_added_449",
            "review_comment_449",
            row["comment_id"],
            review["case_id"],
            {"review_id": review_id, "kind": kind},
        )
        return dict(row)

    def execute_approved_export(self, *, identity, review_id, confirmation):
        review = self.review(review_id)
        if review["object_type"] != "dossier_export":
            raise ValueError("review is not a dossier export approval")
        if review["state"] != "completed" or review["decision"] != "approve":
            raise PermissionError("dossier export requires a completed approved four-eyes review")
        obj = self._object("dossier_export", review["object_id"])
        ident = self._authorize(
            identity,
            review["case_id"],
            "dossier.export.execute",
            review_id,
        )
        if self._mark_stale_if_changed(review, obj):
            raise PermissionError("export approval is stale because the dossier changed")
        if str(ident["username"]).casefold() == str(review["completed_by"]).casefold():
            raise PermissionError("export executor must differ from the approving reviewer")
        if self.db.one("SELECT * FROM review_export_execution_449 WHERE review_id=?", (review_id,)):
            raise ValueError("approved export review has already been executed")
        if str(confirmation or "").strip().upper() != "EXPORT DOSSIER 447":
            raise PermissionError("explicit EXPORT DOSSIER 447 confirmation required")

        export = self.closure447.export_dossier(
            identity=ident,
            revision_id=review["object_id"],
            confirmation="EXPORT DOSSIER 447",
        )
        row = {
            "execution_id": "rexec449_" + secrets.token_hex(10),
            "review_id": review_id,
            "revision_id": review["object_id"],
            "case_id": review["case_id"],
            "export_id": str(export["export_id"]),
            "package_hash": str(export["package_hash"]),
            "executed_by": str(ident["username"]),
            "executed_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO review_export_execution_449 VALUES(" + ",".join("?" for _ in row) + ")",
            tuple(row.values()),
        )
        self.audit.log(
            "approved_dossier_export_executed_449",
            "review_export_execution_449",
            row["execution_id"],
            review["case_id"],
            {
                "review_id": review_id,
                "reviewer": review["completed_by"],
                "executor": ident["username"],
                "package_hash": row["package_hash"],
            },
        )
        return {"review": self.review(review_id), "execution": row, "export": export}

    def queue(self, *, identity, case_id, include_closed=True):
        ident = self._authorize(identity, case_id, "case.read", case_id)
        sql = "SELECT * FROM review_request_449 WHERE case_id=?"
        args = [str(case_id)]
        if not include_closed:
            sql += " AND state IN ('pending','claimed','stale')"
        sql += " ORDER BY CASE state WHEN 'claimed' THEN 0 WHEN 'pending' THEN 1 WHEN 'stale' THEN 2 ELSE 3 END, requested_at DESC,rowid DESC"
        rows = [dict(x) for x in self.db.all(sql, tuple(args))]
        username = str(ident["username"])
        for row in rows:
            row["comments"] = self.comments(row["review_id"])
            row["assigned_to_me"] = bool(row["assigned_to"]) and row["assigned_to"].casefold() == username.casefold()
            row["requested_by_me"] = row["requested_by"].casefold() == username.casefold()
            row["can_claim"] = (
                row["state"] == "pending"
                and not row["requested_by_me"]
                and (not row["assigned_to"] or row["assigned_to_me"])
                and self._reviewer_eligible(username, row["case_id"], row["object_type"])
            )
            row["can_complete"] = row["state"] == "claimed" and row["claimed_by"].casefold() == username.casefold()
        return rows

    def snapshot(self, *, identity, case_id):
        ident = self._authorize(identity, case_id, "case.read", case_id)
        base = self.workspace448.snapshot(identity=ident, case_id=case_id)
        queue = self.queue(identity=ident, case_id=case_id, include_closed=True)
        memberships = [
            dict(x)
            for x in self.governance.identity.list_case_memberships(str(case_id))
            if bool(x.get("active"))
        ]
        pending = [x for x in queue if x["state"] == "pending"]
        claimed = [x for x in queue if x["state"] == "claimed"]
        stale = [x for x in queue if x["state"] == "stale"]
        assigned = [
            x for x in queue
            if x["state"] in {"pending", "claimed"}
            and (
                (x["assigned_to"] and x["assigned_to"].casefold() == ident["username"].casefold())
                or x["claimed_by"].casefold() == ident["username"].casefold()
            )
        ]
        review_metrics = {
            "pending": len(pending),
            "claimed": len(claimed),
            "stale": len(stale),
            "assigned_to_me": len(assigned),
            "team_members": len({x.get("username") for x in memberships}),
        }
        export_executions = [
            dict(x)
            for x in self.db.all(
                "SELECT * FROM review_export_execution_449 WHERE case_id=? "
                "ORDER BY executed_at,rowid",
                (str(case_id),),
            )
        ]
        base["build"] = BUILD
        base["team_review449"] = {
            "queue": queue,
            "memberships": memberships,
            "metrics": review_metrics,
            "export_executions": export_executions,
            "eligible_reviewers": {
                key: self.eligible_reviewers(case_id, key)
                for key in sorted(OBJECT_TYPES)
            },
            "four_eyes_required": True,
            "same_user_request_and_review_forbidden": True,
            "stale_object_revalidation_required": True,
            "comments_and_challenges_supported": True,
            "truth_determined": False,
        }
        if review_metrics["assigned_to_me"]:
            base["next_actions"].insert(
                0,
                {
                    "view": "operations",
                    "priority": "high",
                    "label": f"{review_metrics['assigned_to_me']} Review-Aufgabe(n) für mich",
                },
            )
        elif review_metrics["pending"]:
            base["next_actions"].append(
                {
                    "view": "operations",
                    "priority": "medium",
                    "label": f"{review_metrics['pending']} offene Team-Review-Aufgabe(n)",
                }
            )
        return base

    def verify_integrity(self):
        violations = []
        for table, key in (
            ("review_request_449", "review_id"),
            ("review_comment_449", "comment_id"),
            ("review_export_execution_449", "execution_id"),
        ):
            for row in self.db.all(f"SELECT * FROM {table}"):
                item = dict(row)
                if self._rh(item) != item.get("record_hash"):
                    violations.append({key: item.get(key), "table": table, "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not violations, "violations": violations}

    def status(self):
        total = int((self.db.one("SELECT COUNT(*) n FROM review_request_449") or {}).get("n") or 0)
        pending = int((self.db.one("SELECT COUNT(*) n FROM review_request_449 WHERE state='pending'") or {}).get("n") or 0)
        claimed = int((self.db.one("SELECT COUNT(*) n FROM review_request_449 WHERE state='claimed'") or {}).get("n") or 0)
        completed = int((self.db.one("SELECT COUNT(*) n FROM review_request_449 WHERE state='completed'") or {}).get("n") or 0)
        exports = int((self.db.one("SELECT COUNT(*) n FROM review_export_execution_449") or {}).get("n") or 0)
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "review_requests": total,
            "pending_reviews": pending,
            "claimed_reviews": claimed,
            "completed_positive_reviews": completed,
            "four_eyes_exports_executed": exports,
            "integrity_valid": self.verify_integrity()["valid"],
            "case_scoped_review_queue": True,
            "reviewer_assignment": True,
            "explicit_claiming": True,
            "creator_reviewer_separation": True,
            "requester_reviewer_separation": True,
            "stale_object_detection": True,
            "comments_challenges_agreement_counter_hypothesis": True,
            "dossier_export_four_eyes": True,
            "automatic_truth_determination": False,
            "automatic_review_completion": False,
            "production_release_ready": False,
            "next_build": "450.0",
            "next_hard_checkpoint": "450.0",
        }
