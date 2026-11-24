"""Independent audit checkpoints to the PRIVATE MichaIntel research-exchange branch.

A checkpoint contains ONLY the sequence and keyed audit-chain head, never
records, identities, case data, credentials or signing keys. The remote Git
host is an independent trust domain. Git branch rewriting by its administrator
is outside this model; an immutable separately held commit SHA adds assurance.
No automatic upload: checkpoint publication needs explicit human confirmation.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from audit_chain import AuditLedger
from bridge import BRANCH, REMOTE
from local_key import read_key

CONFIRMATION = "ANCHOR PUBLIC RESEARCH AUDIT"
HEX = re.compile(r"[0-9a-f]{64}")
REMOTE_ROOT = "exchange/audit-anchors/v1"
MAX_ANCHOR_BYTES = 2048


def _encode(data):
    return json.dumps(data, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("ascii")


def _identity(key):
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("invalid DPAPI signing key")
    return hashlib.sha256(b"eagleeye/public-audit-key-id/v1\x00" + key).hexdigest()[:32]


def _git(directory, *args, data=None, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0",
               GIT_AUTHOR_NAME="EagleEye Audit Checkpoint",
               GIT_AUTHOR_EMAIL="audit@localhost",
               GIT_COMMITTER_NAME="EagleEye Audit Checkpoint",
               GIT_COMMITTER_EMAIL="audit@localhost")
    process = subprocess.run(
        ["git", "-C", str(directory), *args],
        input=data, capture_output=True, timeout=90, env=env,
    )
    if check and process.returncode != 0:
        # Don't surface command output: it could contain remote URL secrets.
        raise RuntimeError("Private audit Git operation failed: " + args[0])
    return process


def _manifest(events, key):
    if not events:
        raise ValueError("Cannot anchor an empty audit history")
    tail = events[-1]
    if tail["seq"] != len(events) or not HEX.fullmatch(tail["mac"]):
        raise ValueError("Invalid audited ledger tail")
    return {
        "schema": 1, "type": "public-topic-audit-anchor",
        "installation": _identity(key), "seq": tail["seq"],
        "head_mac": tail["mac"],
    }


def _parse(raw, identity, number):
    if len(raw) > MAX_ANCHOR_BYTES:
        raise ValueError("Remote audit anchor oversized")
    def no_duplicate(pairs):
        out = {}
        for k, value in pairs:
            if k in out:
                raise ValueError("Duplicate anchor JSON property")
            out[k] = value
        return out
    try:
        doc = json.loads(raw, object_pairs_hook=no_duplicate)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid remote audit anchor JSON") from exc
    if not isinstance(doc, dict) or set(doc) != {
            "schema", "type", "installation", "seq", "head_mac"}:
        raise ValueError("Unexpected remote audit anchor schema")
    if (type(doc["schema"]) is not int or doc["schema"] != 1
            or doc["type"] != "public-topic-audit-anchor"
            or doc["installation"] != identity
            or type(doc["seq"]) is not int or doc["seq"] != number
            or not isinstance(doc["head_mac"], str)
            or not HEX.fullmatch(doc["head_mac"])):
        raise ValueError("Remote audit anchor mismatched")
    return doc


def _remote_anchors(repo, revision, identity):
    """List only Git tree metadata. Fetch no unrelated research content."""
    prefix = f"{REMOTE_ROOT}/{identity}/"
    results = {}
    listing = _git(repo, "ls-tree", "-r", "--name-only", revision, "--",
                   prefix).stdout.decode("utf-8", errors="strict")
    for item in listing.splitlines():
        if not item.startswith(prefix):
            continue
        name = item[len(prefix):]
        if not re.fullmatch(r"[0-9]{12}\.json", name):
            raise ValueError("Unexpected object under audit anchor namespace")
        seq = int(name[:-5])
        if seq < 1 or seq in results:
            raise ValueError("Duplicate or invalid remote anchor sequence")
        results[seq] = item
    return results


def _fetch_latest(repo, remote, branch, identity, events):
    _git(repo, "fetch", "--no-tags", remote, "refs/heads/" + branch)
    parent = _git(repo, "rev-parse", "FETCH_HEAD").stdout.decode().strip()
    names = _remote_anchors(repo, parent, identity)
    if names:
        seq = max(names)
        if seq > len(events):
            raise ValueError("Local audit was truncated below independent checkpoint")
        raw = _git(repo, "show", parent + ":" + names[seq]).stdout
        doc = _parse(raw, identity, seq)
        if not hmac.compare_digest(doc["head_mac"], events[seq-1]["mac"]):
            raise ValueError("Independent audit anchor does not match local history")
        # Before publishing, also ensure ALL prior anchors still match.
        for earlier, path in sorted(names.items()):
            if earlier == seq:
                continue
            anchor = _parse(_git(repo, "show", parent + ":" + path).stdout,
                            identity, earlier)
            if not hmac.compare_digest(anchor["head_mac"],
                                       events[earlier-1]["mac"]):
                raise ValueError("Historical independent audit anchor mismatch")
    return parent, names


def verify_remote_anchor(ledger, *, remote=REMOTE, branch=BRANCH):
    """Read-only verification of ALL remote checkpoints against local ledger."""
    if not isinstance(ledger, AuditLedger):
        raise TypeError("AuditLedger expected")
    events = ledger.verify()
    identity = _identity(ledger.key)
    with tempfile.TemporaryDirectory(prefix="eagleeye-audit-verify-") as tmp:
        _git(tmp, "init", "--quiet")
        parent, names = _fetch_latest(tmp, remote, branch, identity, events)
        latest = max(names) if names else 0
        return {
            "status": "verified" if latest else "unanchored",
            "anchor_count": len(names), "latest_anchored_seq": latest,
            "local_seq": len(events),
            "pending_local_events": len(events) - latest,
            "private_branch_commit": parent,
            "installation": identity,
        }


def publish_remote_anchor(ledger, confirmation, *,
                          remote=REMOTE, branch=BRANCH):
    """Explicit checkpoint; non-overwriting Git commit, no force push."""
    if confirmation != CONFIRMATION:
        raise ValueError("Explicit audit checkpoint approval required")
    events = ledger.verify()
    identity = _identity(ledger.key)
    record = _manifest(events, ledger.key)
    name = f"{REMOTE_ROOT}/{identity}/{record['seq']:012d}.json"
    raw = _encode(record)
    with tempfile.TemporaryDirectory(prefix="eagleeye-audit-publish-") as tmp:
        _git(tmp, "init", "--quiet")
        for attempt in range(3):
            parent, names = _fetch_latest(tmp, remote, branch, identity, events)
            if record["seq"] in names:
                original = _git(tmp, "show",
                                parent + ":" + names[record["seq"]]).stdout
                if original != raw:
                    raise ValueError("Conflicting audit anchor already exists")
                return {"status": "duplicate", "sequence": record["seq"],
                        "commit": parent, "path": name}
            _git(tmp, "read-tree", parent)
            blob = _git(tmp, "hash-object", "-w", "--stdin",
                        data=raw).stdout.decode().strip()
            _git(tmp, "update-index", "--add", "--cacheinfo",
                 "100644," + blob + "," + name)
            tree = _git(tmp, "write-tree").stdout.decode().strip()
            commit = _git(tmp, "commit-tree", tree, "-p", parent, "-m",
                          "Anchor public research audit checkpoint "
                          + str(record["seq"])).stdout.decode().strip()
            push = _git(tmp, "push", remote,
                        commit + ":refs/heads/" + branch, check=False)
            if push.returncode == 0:
                return {"status": "published", "sequence": record["seq"],
                        "commit": commit, "path": name}
        raise RuntimeError("Audit anchor push lost a Git version race; retry")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("verify", "publish"))
    ap.add_argument("--confirmation", default="")
    args = ap.parse_args()
    if os.name != "nt":
        raise SystemExit("This installed audit checkpoint command requires Windows")
    root = Path(os.environ["LOCALAPPDATA"]) / "EagleEyeResearchBridge"
    key = read_key(root / "secrets" / "approval.dpapi")
    ledger = AuditLedger(root / "workspace" / "audit" / "ledger.sqlite", key)
    answer = (publish_remote_anchor(ledger, args.confirmation)
              if args.action == "publish" else verify_remote_anchor(ledger))
    print(json.dumps(answer, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
