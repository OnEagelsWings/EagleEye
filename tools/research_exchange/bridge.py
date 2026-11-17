"""Public-topic exchange staging; no automatic evidence import."""
import argparse
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

def validate(raw):
    if len(raw) > MAX:
        raise ValueError("oversize")
    d = json.loads(raw)
    if not isinstance(d, dict) or set(d) - {"schema","id","kind","classification","topic","summary","sources","synthetic"}:
        raise ValueError("unexpected fields")
    if type(d.get("schema")) is not int or d["schema"] != 1 or d.get("classification") != "public-topic":
        raise ValueError("classification/schema")
    if not isinstance(d.get("id"), str) or not ID.fullmatch(d["id"]):
        raise ValueError("id")
    if d.get("kind") not in ("research_result","research_request"):
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
        if u.scheme != "https" or not u.hostname or u.username or u.password:
            raise ValueError("source URL")
    if "synthetic" in d and type(d["synthetic"]) is not bool:
        raise ValueError("synthetic")
    return d

def git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True,timeout=90).stdout

def stage(root,local):
    git(root,"fetch","--no-tags",REMOTE,BRANCH)
    commit=git(root,"rev-parse","FETCH_HEAD").decode().strip()
    paths=git(root,"ls-tree","-r","--name-only","-z",commit,"exchange/inbox").decode().split("\0")
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
            try:
                with target.open("xb") as f: f.write(raw)
                status="staged"
            except FileExistsError:
                status="duplicate" if target.read_bytes()==raw else "conflict"
            with (local/"audit.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps({"id":d["id"],"commit":commit,"sha256":digest,"status":status})+"\n")
            print(d["id"],status)
        except (ValueError,TypeError,UnicodeError) as e:
            print("Rejected",path,type(e).__name__)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("git_directory",type=pathlib.Path)
    p.add_argument("local_inbox",type=pathlib.Path)
    a=p.parse_args()
    stage(a.git_directory,a.local_inbox)

if __name__=="__main__":
    main()
