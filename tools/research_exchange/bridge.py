"""Public-topic exchange staging; no automatic evidence import."""
import argparse
import os
import tempfile
import json
import pathlib
import re
import subprocess
import hashlib
from urllib.parse import urlsplit

REMOTE = "https://github.com/OnEagelsWings/MichaIntel.git"
BRANCH = "research-exchange"
ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
MAX = 256_000

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result

def reject_constant(value):
    raise ValueError("nonfinite JSON constant")

def validate(raw):
    if not isinstance(raw, bytes):
        raise ValueError("expected UTF-8 bytes")
    if len(raw) > MAX:
        raise ValueError("oversize")
    try:
        d = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                       parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid JSON encoding or depth") from exc
    # JSON escapes can introduce lone surrogates even in valid UTF-8 input.
    try:
        json.dumps(d, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid Unicode or depth") from exc
    if not isinstance(d, dict) or set(d) - {"schema","id","kind","classification","topic","summary","sources","synthetic"}:
        raise ValueError("unexpected fields")
    if type(d.get("schema")) is not int or d["schema"] != 1 or d.get("classification") != "public-topic":
        raise ValueError("classification/schema")
    if not isinstance(d.get("id"), str) or not ID.fullmatch(d["id"]):
        raise ValueError("id")
    if not isinstance(d.get("kind"), str) or d.get("kind") not in ("research_result","research_request"):
        raise ValueError("kind")
    for k in ("topic","summary"):
        if not isinstance(d.get(k),str) or not d[k].strip() or len(d[k]) > 20000:
            raise ValueError(k)
    if not isinstance(d.get("sources"),list) or len(d["sources"]) > 100:
        raise ValueError("sources")
    for s in d["sources"]:
        if not isinstance(s,dict) or set(s) != {"title","url"} or not all(isinstance(v,str) and 0<len(v)<=2048 for v in s.values()):
            raise ValueError("source")
        u=urlsplit(s["url"])
        if (u.scheme != "https" or not u.hostname or u.username or u.password
                or any(c.isspace() or ord(c) < 32 for c in s["url"])
                or "\\" in s["url"]):
            raise ValueError("source URL")
    if "synthetic" in d and type(d["synthetic"]) is not bool:
        raise ValueError("synthetic")
    return d

def git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True,timeout=90).stdout

def publish_record(target, raw):
    """Publish complete bytes without replacing an existing record.

    Requires a local filesystem supporting hard links (e.g. NTFS).
    A crash before publication can leave an ignored temporary file.
    """
    fd, name = tempfile.mkstemp(prefix=".staging-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(name, target)
        except FileExistsError:
            return "duplicate" if target.read_bytes() == raw else "conflict"
        if os.name == "posix":
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        return "staged"
    finally:
        os.unlink(name)


def stage(root,local, *, database=None):
    """Stage into SQLite when explicitly selected; never import evidence."""
    if database is not None:
        from staging_db import StagingDB
        store = StagingDB(database)
    else:
        store = None
    git(root,"fetch","--no-tags",REMOTE,BRANCH)
    commit=git(root,"rev-parse","FETCH_HEAD").decode().strip()
    paths=git(root,"ls-tree","-r","--name-only","-z",commit,"exchange/inbox").decode().split("\0")
    if store is None:
        local.mkdir(parents=True,exist_ok=True)
    for path in paths:
        if not re.fullmatch(r"exchange/inbox/[0-9a-f-]{36}\.json",path):
            continue
        try:
            size=int(git(root,"cat-file","-s",commit+":"+path))
            if size>MAX: raise ValueError("oversize")
            raw=git(root,"show",commit+":"+path)
            d=validate(raw)
            if pathlib.PurePosixPath(path).stem!=d["id"]: raise ValueError("filename mismatch")
            target=local/(d["id"]+".json")
            digest=hashlib.sha256(raw).hexdigest()
            if store is not None:
                status = store.stage(raw, commit)
            else:
                status=publish_record(target,raw)
                with (local/"audit.jsonl").open("a",encoding="utf-8") as f:
                    f.write(json.dumps({"id":d["id"],"commit":commit,"sha256":digest,"status":status})+"\n")
            print(d["id"],status)
        except (ValueError,TypeError,UnicodeError) as e:
            print("Rejected",path,type(e).__name__)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("git_directory",type=pathlib.Path)
    p.add_argument("local_inbox",type=pathlib.Path)
    p.add_argument("--database", type=pathlib.Path, help="Opt-in SQLite staging; does not migrate legacy files")
    a=p.parse_args()
    stage(a.git_directory,a.local_inbox,database=a.database)

if __name__=="__main__":
    main()
