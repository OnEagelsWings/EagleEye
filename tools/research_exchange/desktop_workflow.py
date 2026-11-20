"""Manual public-research desktop workflow. No automatic transfers or evidence import.

Only exchange-schema public-topic records are accepted. The classification field
is a user assertion, not a personal-data detector: review before signing.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

import bridge
from bridge import MAX, validate, publish_record
from local_key import read_key
from outbound import publish
from review import review
from signed_approval import approve_signed, verify_signed, CONFIRMATION
from staging_db import StagingDB
from audit_chain import AuditLedger


_NAME = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json")


class DesktopWorkflow:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.workspace = self.root / "workspace"
        self.outbox = self.workspace / "outbox"
        self.inbox = self.workspace / "inbox"
        self.gitdir = self.workspace / "git"
        self.database = self.workspace / "staging.sqlite"
        self.audit = self.workspace / "audit" / "ledger.sqlite"
        self.key_path = self.root / "secrets" / "approval.dpapi"

    def list_inbound(self):
        if not self.database.is_file():
            return []
        # The list is only a navigation aid; preview reads and verifies the record.
        return review(self.database)

    def inbound_detail(self, ident):
        if not self.database.is_file():
            raise ValueError("No staged records")
        record_bytes = StagingDB(self.database).read(ident)
        if record_bytes is None:
            raise ValueError("Unknown staged record")
        result = review(self.database, ident)
        if hashlib.sha256(record_bytes).hexdigest() != result["sha256"]:
            raise ValueError("Staging changed during review")
        return result

    def review_inbound(self, ident, decision, confirmation):
        """Manually mark staged public-topic content; no import or upload."""
        phrase = CONFIRMATION if decision == "approved" else "DEFER PUBLIC RESEARCH"
        if decision not in {"approved", "deferred"} or confirmation != phrase:
            raise ValueError("Explicit inbound review confirmation required")
        if not self.database.is_file():
            raise ValueError("No staged research data")
        raw = StagingDB(self.database).read(ident)
        if raw is None:
            raise ValueError("Unknown staged record")
        record = validate(raw)
        if record["id"] != ident:
            raise ValueError("Staged ID mismatch")
        key = read_key(self.key_path)
        # The matching approval receipt is returned to the local operator only.
        receipt = approve_signed(raw, key, "inbound", CONFIRMATION) if decision == "approved" else None
        event = AuditLedger(self.audit, key).append(
            ident, hashlib.sha256(raw).hexdigest(), "inbound-" + decision)
        return {"event": event, "receipt": receipt}

    def list_remote_candidates(self):
        """Fetch metadata of remote inbox, WITHOUT reading any record content."""
        if not (self.gitdir / ".git").is_dir():
            raise ValueError("Local Git staging directory not initialized")
        bridge.git(self.gitdir, "fetch", "--no-tags", bridge.REMOTE, bridge.BRANCH)
        commit = bridge.git(self.gitdir, "rev-parse", "FETCH_HEAD").decode().strip()
        entries = bridge.git(self.gitdir, "ls-tree", "-r", "-z", commit,
                             "exchange/inbox").decode().split("\0")
        names = set()
        for entry in entries:
            if not entry:
                continue
            meta, path = entry.split("\t", 1)
            name = path.removeprefix("exchange/inbox/")
            if path.startswith("exchange/inbox/") and _NAME.fullmatch(name) \
                    and meta.startswith("100644 blob "):
                names.add(name[:-5])
        return sorted(names)

    def pull_inbound(self, ident):
        if not isinstance(ident, str) or not _NAME.fullmatch(ident + ".json"):
            raise ValueError("Select an exact remote record ID")
        if not (self.gitdir / ".git").is_dir():
            raise ValueError("Local Git staging directory not initialized")
        # Allowlist prevents reading any other record in the private Git tree.
        return bridge.stage(self.gitdir, self.inbox, database=self.database,
                            allowed_ids={ident})

    def _outgoing_path(self, filename):
        if not isinstance(filename, str) or not _NAME.fullmatch(filename):
            raise ValueError("Invalid outgoing filename")
        if self.outbox.is_symlink() or not self.outbox.is_dir():
            raise ValueError("Unsafe or missing outgoing directory")
        path = self.outbox / filename
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Unsafe outgoing record")
        if os.name == "nt" and info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Reparse point rejected")
        return path

    def _raw_outgoing(self, filename):
        path = self._outgoing_path(filename)
        with path.open("rb") as handle:
            raw = handle.read(MAX + 1)
        record = validate(raw)
        if filename != record["id"] + ".json":
            raise ValueError("Filename does not match record ID")
        return raw, record

    def list_outbound(self):
        if not self.outbox.is_dir():
            return []
        return sorted(
            p.name for p in self.outbox.iterdir()
            if _NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()
        )

    def create_draft(self, topic, summary, *, kind="research_request", sources=None, synthetic=False):
        if not self.outbox.is_dir() or self.outbox.is_symlink():
            raise ValueError("Outbox directory is missing or unsafe")
        record = dict(schema=1, id=str(uuid.uuid4()), kind=kind,
                      classification="public-topic", topic=topic,
                      summary=summary, sources=sources or [], synthetic=synthetic)
        raw = json.dumps(record, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":")).encode("ascii")
        validate(raw)
        path = self.outbox / (record["id"] + ".json")
        if publish_record(path, raw) != "staged":
            raise ValueError("Draft filename conflict")
        return path.name

    def outgoing_detail(self, filename):
        raw, record = self._raw_outgoing(filename)
        return {"record": record, "sha256": hashlib.sha256(raw).hexdigest()}

    def sign_outgoing(self, filename, confirmation):
        raw, record = self._raw_outgoing(filename)
        key = read_key(self.key_path)
        receipt = approve_signed(raw, key, "outbound", confirmation)
        return receipt, hashlib.sha256(raw).hexdigest()

    def audit_events(self):
        if not self.audit.is_file():
            return []
        return AuditLedger(self.audit, read_key(self.key_path)).verify()

    def publish_outgoing(self, filename, receipt):
        raw, record = self._raw_outgoing(filename)
        key = read_key(self.key_path)
        if not verify_signed(raw, key, "outbound", receipt):
            raise ValueError("Approval missing or record changed")
        ledger = AuditLedger(self.audit, key)
        digest = hashlib.sha256(raw).hexdigest()
        # Record the attempt durably BEFORE any network change. If power fails,
        # the next explicit request will retry safely and report a duplicate.
        ledger.append(record["id"], digest, "attempt")
        try:
            result = publish(raw, receipt, key=key)
        except Exception:
            ledger.append(record["id"], digest, "error")
            raise
        if result.get("status") not in {"published", "duplicate"}:
            raise ValueError("Unexpected publisher status")
        return ledger.append(record["id"], digest, result["status"], result["commit"])
