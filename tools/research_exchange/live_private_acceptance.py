"""Explicit, SYNTHETIC-ONLY live exchange acceptance against private MichaIntel.

Does not read any pre-existing private-branch records or check out its contents.
Writes exactly one labelled synthetic request in outbox and one synthetic result
in inbox. Records remain in the private research-exchange branch for audit.
Only run when the account owner explicitly authorizes this live test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

import bridge
from bridge import validate
from desktop_workflow import DesktopWorkflow
from outbound import publish
from signed_approval import CONFIRMATION, approve_signed, verify_signed
from staging_db import StagingDB

PROMPT = "RUN SYNTHETIC PRIVATE BRANCH ACCEPTANCE"
REMOTE = bridge.REMOTE
REF = "refs/heads/" + bridge.BRANCH


def _git(repository, *args, data=None, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(GIT_AUTHOR_NAME="EagleEye Synthetic Acceptance",
               GIT_AUTHOR_EMAIL="synthetic@localhost",
               GIT_COMMITTER_NAME="EagleEye Synthetic Acceptance",
               GIT_COMMITTER_EMAIL="synthetic@localhost")
    return subprocess.run(
        ["git", "-C", str(repository), *args], input=data,
        capture_output=True, check=check, timeout=90, env=env
    ).stdout


def _remote_blob(repo, path):
    _git(repo, "fetch", "--no-tags", REMOTE, REF)
    rev = _git(repo, "rev-parse", "FETCH_HEAD").decode().strip()
    mode = _git(repo, "ls-tree", rev, "--", path)
    if not mode:
        raise RuntimeError("expected synthetic record not found on remote")
    if not mode.startswith(b"100644 blob "):
        raise RuntimeError("remote record is not regular Git blob")
    return _git(repo, "show", rev + ":" + path), rev


def _publish_synthetic_inbound(raw):
    record = validate(raw)
    if record.get("synthetic") is not True or record["kind"] != "research_result":
        raise ValueError("inbound acceptance requires synthetic research_result")
    path = "exchange/inbox/" + record["id"] + ".json"
    with tempfile.TemporaryDirectory(prefix="eagleeye-synthetic-in-") as name:
        repo = Path(name)
        _git(repo, "init", "--quiet")
        for attempt in range(3):
            _git(repo, "fetch", "--no-tags", REMOTE, REF)
            parent = _git(repo, "rev-parse", "FETCH_HEAD").decode().strip()
            if _git(repo, "ls-tree", parent, "--", path):
                existing = _git(repo, "show", parent + ":" + path)
                if existing != raw:
                    raise ValueError("synthetic inbound ID conflict")
                return {"status": "duplicate", "commit": parent}
            _git(repo, "read-tree", parent)
            blob = _git(repo, "hash-object", "-w", "--stdin", data=raw).decode().strip()
            _git(repo, "update-index", "--add", "--cacheinfo",
                 "100644," + blob + "," + path)
            tree = _git(repo, "write-tree").decode().strip()
            commit = _git(repo, "commit-tree", tree, "-p", parent, "-m",
                          "Synthetic public-topic inbound acceptance " + record["id"]).decode().strip()
            # A concurrent private-branch change is never force-pushed.
            result = subprocess.run(
                ["git", "-C", str(repo), "push", REMOTE, commit + ":" + REF],
                capture_output=True, timeout=90,
                env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            )
            if result.returncode == 0:
                return {"status": "published", "commit": commit}
        raise RuntimeError("synthetic inbound push raced with other changes")


def run(root):
    workflow = DesktopWorkflow(root)
    # Using only public synthetic astronomy text - no personal details.
    filename = workflow.create_draft(
        "Synthetic celestial mechanics acceptance",
        "Artificial research-exchange request; no real measurements or evidence.",
        synthetic=True,
    )
    outgoing_path = workflow.outbox / filename
    outgoing_raw = outgoing_path.read_bytes()
    outgoing = validate(outgoing_raw)
    assert outgoing["synthetic"] is True
    approval, digest = workflow.sign_outgoing(filename, CONFIRMATION)
    pushed = workflow.publish_outgoing(filename, approval)
    if pushed["status"] != "published":
        raise RuntimeError("outbound first publication was not newly published")
    with tempfile.TemporaryDirectory(prefix="eagleeye-verify-") as name:
        repo = Path(name)
        _git(repo, "init", "--quiet")
        verified, remote_out_commit = _remote_blob(
            repo, "exchange/outbox/" + outgoing["id"] + ".json")
        if verified != outgoing_raw:
            raise RuntimeError("outbound bytes differ from remote")
    # Crash/retry with identical bytes returns duplicate, not an overwrite.
    replay = workflow.publish_outgoing(filename, approval)
    if replay["status"] != "duplicate":
        raise RuntimeError("outbound idempotent retry failed")
    changed = dict(outgoing, summary="Synthetic changed payload that MUST NOT overwrite")
    changed_raw = json.dumps(changed, sort_keys=True).encode("utf-8")
    alternate_signature = approve_signed(
        changed_raw, workflow_key(root), "outbound", CONFIRMATION)
    try:
        publish(changed_raw, alternate_signature, key=workflow_key(root))
    except ValueError as exc:
        if "conflict" not in str(exc):
            raise
        conflict_blocked = True
    else:
        raise RuntimeError("conflicting record was unexpectedly published")
    # Other-direction synthetic response: protected Git plumbing, no checkout.
    incoming = {
        "schema": 1, "id": str(uuid4()), "kind": "research_result",
        "classification": "public-topic", "synthetic": True,
        "topic": "Synthetic celestial mechanics acceptance response",
        "summary": "Artificial test response to synthetic private-branch request "
                   + outgoing["id"] + ". No personal data.",
        "sources": [],
    }
    incoming_raw = json.dumps(
        incoming, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    validate(incoming_raw)
    inbound_pub = _publish_synthetic_inbound(incoming_raw)
    if inbound_pub["status"] != "published":
        raise RuntimeError("inbound first publication was not newly published")
    # Live fetch; allowed IDs guarantee pre-existing private records are not opened.
    bridge.stage(workflow.gitdir, workflow.inbox, database=workflow.database,
                 allowed_ids={incoming["id"]})
    actual = StagingDB(workflow.database).read(incoming["id"])
    if actual != incoming_raw:
        raise RuntimeError("inbound bytes differ from staged bytes")
    details = workflow.inbound_detail(incoming["id"])
    if details["record"] != incoming:
        raise RuntimeError("inbound preview mismatch")
    review = workflow.review_inbound(incoming["id"], "approved", CONFIRMATION)
    if not verify_signed(incoming_raw, workflow_key(root), "inbound",
                         review["receipt"]):
        raise RuntimeError("inbound approval signature failed")
    # Restart/replay, now a duplicate, no overwritten staging or duplicate audit.
    bridge.stage(workflow.gitdir, workflow.inbox, database=workflow.database,
                 allowed_ids={incoming["id"]})
    if StagingDB(workflow.database).read(incoming["id"]) != incoming_raw:
        raise RuntimeError("inbound replay modified data")
    all_events = workflow.audit_events()
    event_types = [event["status"] for event in all_events if
                   event["id"] in {outgoing["id"], incoming["id"]}]
    assert event_types == [
        "attempt", "published", "attempt", "duplicate", "inbound-approved"
    ], event_types
    return {
        "result": "PASS",
        "private_repo": "OnEagelsWings/MichaIntel",
        "branch": bridge.BRANCH,
        "outbound_id": outgoing["id"],
        "inbound_id": incoming["id"],
        "outbound_status": pushed["status"],
        "outbound_replay": replay["status"],
        "remote_out_commit": remote_out_commit,
        "inbound_status": inbound_pub["status"],
        "remote_in_commit": inbound_pub["commit"],
        "inbound_digest": hashlib.sha256(incoming_raw).hexdigest(),
        "outbound_digest": digest,
        "conflict_blocked": conflict_blocked,
        "private_other_records_read": False,
        "audit_events_for_test": event_types,
        "notes": "Only synthetic public-topic fixtures were written to the private branch.",
    }


def workflow_key(root):
    from local_key import read_key
    return read_key(Path(root) / "secrets" / "approval.dpapi")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-synthetic-live", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    if not args.run_synthetic_live or args.confirmation != PROMPT:
        raise SystemExit("No network write. Explicit synthetic-live confirmation required.")
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise SystemExit("Live acceptance is restricted to installed Windows workspace")
    root = Path(os.environ["LOCALAPPDATA"]) / "EagleEyeResearchBridge"
    result = run(root)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
