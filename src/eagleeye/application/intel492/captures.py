"""Case-scoped persistence for Build-492 web captures.

The extracted text goes through the existing Build-458 document import, so anchors,
findings, review and citations work unchanged. The WARC file is stored next to the
Build-458 originals and bound to the document by hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path

from .webcapture import CaptureError, read_warc_response

TABLE = """CREATE TABLE IF NOT EXISTS web_capture_492(
    capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, document_id TEXT NOT NULL,
    kind TEXT NOT NULL, url TEXT NOT NULL, archive_url TEXT NOT NULL, captured_at TEXT NOT NULL,
    http_status INTEGER NOT NULL, ip_address TEXT NOT NULL, content_type TEXT NOT NULL,
    body_sha256 TEXT NOT NULL, warc_sha256 TEXT NOT NULL, warc_relpath TEXT NOT NULL,
    warc_bytes INTEGER NOT NULL, page_title TEXT NOT NULL, page_author TEXT NOT NULL,
    page_published TEXT NOT NULL, extractor TEXT NOT NULL, created_by TEXT NOT NULL,
    record_hash TEXT NOT NULL)"""


def _hash(row: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def warc_root(ctx) -> Path:
    root = Path(ctx.db.path).parent / "webcapture_492"
    root.mkdir(parents=True, exist_ok=True)
    return root


def initialize(ctx) -> None:
    ctx.db.conn.execute(TABLE)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS web_capture_492_case ON web_capture_492(case_id,captured_at)")
    ctx.db.conn.commit()


def store_capture(ctx, *, identity: dict, case_id: str, result: dict, kind: str) -> dict:
    """Write WARC atomically, import the text document, then record the binding."""
    if result.get("redirect"):
        raise CaptureError("Weiterleitungen werden nicht automatisch gespeichert.")
    capture_id = "cap492_" + secrets.token_hex(12)
    rel = capture_id + ".warc.gz"
    target = warc_root(ctx) / rel
    temp = target.with_name(rel + ".tmp")
    with temp.open("xb") as fh:
        fh.write(result["warc"])
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(temp, 0o600)
    temp.replace(target)
    try:
        imported = ctx.document_intelligence_458.import_bytes(
            identity=identity, case_id=case_id, filename=capture_id + ".txt", raw=result["document"],
            title=("Web: " if kind == "live" else "Archiv: ") + result["title"],
            source_url=result["url"])
        meta = result["metadata"]
        row = {"capture_id": capture_id, "case_id": case_id, "document_id": imported["document_id"],
               "kind": kind, "url": result["url"], "archive_url": result.get("archive_url", ""),
               "captured_at": result["captured_at"], "http_status": int(result["status"]),
               "ip_address": result["ip_address"], "content_type": result["content_type"],
               "body_sha256": result["body_sha256"], "warc_sha256": result["warc_sha256"],
               "warc_relpath": rel, "warc_bytes": len(result["warc"]), "page_title": meta["title"],
               "page_author": meta["author"], "page_published": meta["published"],
               "extractor": meta["extractor"], "created_by": str(identity["username"])}
        row["record_hash"] = _hash(row)
        with ctx.db.transaction(immediate=True):
            ctx.db.execute("INSERT INTO web_capture_492 VALUES(" + ",".join("?" for _ in row) + ")",
                           tuple(row.values()))
            ctx.audit.log("web_capture_stored_492", "web_capture", capture_id, case_id,
                          {"document_id": row["document_id"], "warc_sha256": row["warc_sha256"],
                           "kind": kind, "verified_claim": False})
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return row


def captures_for_case(ctx, case_id: str, limit: int = 200) -> list[dict]:
    rows = [dict(r) for r in ctx.db.all(
        "SELECT * FROM web_capture_492 WHERE case_id=? ORDER BY captured_at DESC LIMIT ?", (case_id, limit))]
    for row in rows:
        row["integrity_ok"] = verify_capture(ctx, row)
    return rows


def capture_row(ctx, capture_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM web_capture_492 WHERE capture_id=?", (str(capture_id),))
    if not row:
        raise KeyError("capture not found")
    return dict(row)


def warc_bytes(ctx, row: dict) -> bytes:
    if row["warc_relpath"] != row["capture_id"] + ".warc.gz":
        raise CaptureError("Ungültiger Speicherort.")
    return (warc_root(ctx) / row["warc_relpath"]).read_bytes()


def verify_capture(ctx, row: dict) -> bool:
    """Record hash, WARC hash and replay of the stored response must all match."""
    try:
        if _hash({k: v for k, v in row.items() if k != "integrity_ok"}) != row["record_hash"]:
            return False
        data = warc_bytes(ctx, row)
        if hashlib.sha256(data).hexdigest() != row["warc_sha256"]:
            return False
        _, status, payload = read_warc_response(data)
        return status == row["http_status"] and hashlib.sha256(payload).hexdigest() == row["body_sha256"]
    except (OSError, CaptureError, ValueError, KeyError):
        return False
