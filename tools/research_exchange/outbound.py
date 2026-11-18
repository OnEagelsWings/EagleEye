"""Publish explicitly approved public-topic records without checking out remote files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from bridge import validate, REMOTE, BRANCH, MAX
from signed_approval import verify_signed
from local_key import read_key

def publish(raw, receipt, remote=REMOTE, branch=BRANCH, *, key):
    record = validate(raw)
    if not verify_signed(raw, key, "outbound", receipt):
        raise ValueError("approval missing or changed")
    path = "exchange/outbox/" + record["id"] + ".json"
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("GIT_"):
                env.pop(key)
        env.update(GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="EagleEye Bridge",
                   GIT_AUTHOR_EMAIL="bridge@localhost", GIT_COMMITTER_NAME="EagleEye Bridge",
                   GIT_COMMITTER_EMAIL="bridge@localhost")
        def run(*args, data=None, check=True):
            return subprocess.run(["git", "-C", tmp, *args], input=data,
                                  capture_output=True, check=check, timeout=90, env=env)
        run("init", "--quiet")
        for attempt in range(3):
            run("fetch", "--no-tags", remote, "refs/heads/" + branch)
            parent = run("rev-parse", "FETCH_HEAD").stdout.decode().strip()
            existing = run("ls-tree", parent, "--", path).stdout
            if existing:
                size = int(run("cat-file", "-s", parent + ":" + path).stdout)
                if size <= MAX and run("show", parent + ":" + path).stdout == raw:
                    return {"status":"duplicate", "commit":parent}
                raise ValueError("remote ID conflict")
            run("read-tree", parent)
            blob = run("hash-object", "-w", "--stdin", data=raw).stdout.decode().strip()
            run("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path)
            tree = run("write-tree").stdout.decode().strip()
            commit = run("commit-tree", tree, "-p", parent, "-m",
                         "Publish public research " + record["id"]).stdout.decode().strip()
            result = run("push", remote, commit + ":refs/heads/" + branch, check=False)
            if result.returncode == 0:
                return {"status":"published", "commit":commit}
        raise RuntimeError("push failed; retry after checking access or concurrent updates")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--key-file", type=Path, required=True,
                        help="Local 32-byte key outside all repositories")
    args = parser.parse_args()
    with args.record.open("rb") as f:
        raw = f.read(MAX + 1)
    with args.receipt.open("r", encoding="utf-8") as f:
        receipt = f.read(1024)
    key = read_key(args.key_file)
    result = publish(raw, receipt, key=key)
    result.update(id=validate(raw)["id"], sha256=hashlib.sha256(raw).hexdigest())
    with args.audit.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
