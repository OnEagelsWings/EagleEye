"""Read-only local review; never imports, approves or publishes records."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from bridge import validate


def review(path, ident=None):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=10)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        if ident is None:
            return [{"id": i, "sha256": d} for i, d in db.execute(
                "SELECT id,digest FROM records ORDER BY id")]
        row = db.execute("SELECT raw,digest FROM records WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise ValueError("unknown staged record")
        raw, digest = row
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("record digest mismatch")
        record = validate(raw)
        if record["id"] != ident:
            raise ValueError("record ID mismatch")
        events = [{"sha256": d, "source_commit": c, "status": s}
                  for d, c, s in db.execute(
                      "SELECT digest,source_commit,status FROM audit WHERE id=? ORDER BY seq",
                      (ident,))]
        return {"record": record, "sha256": digest, "audit": events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--id", help="Inspect one staged record and its audit history")
    args = parser.parse_args()
    print(json.dumps(review(args.database, args.id), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
