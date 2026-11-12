"""Background runs for structure/OCR enrichment on the existing persistent job engine.

OCR of a long scan takes minutes. The request only enqueues a job; a single in-process
worker executes it page by page, records progress as checkpoints and stops between pages
when the job was cancelled. Anchors are written in one transaction at the very end, so a
cancelled or failed run leaves nothing behind.
"""
from __future__ import annotations

import json
import uuid

from . import docstructure

JOB_TYPE = "document_enrich_492"
WORKER_ID = "intel492-enrich"
ACTIVE = ("queued", "running")
LEASE_SECONDS = 3600  # engine maximum; a 160-page scan stays well below


def _payload(job: dict) -> dict:
    try:
        return json.loads(job.get("payload_json") or "{}")
    except ValueError:
        return {}


def _view(job: dict) -> dict:
    payload = _payload(job)
    try:
        checkpoint = json.loads(job.get("checkpoint_json") or "{}")
    except ValueError:
        checkpoint = {}
    return {"job_id": job["job_id"], "document_id": str(payload.get("document_id") or ""), "status": job["status"],
            "done": int(checkpoint.get("done") or 0), "total": int(checkpoint.get("total") or 0),
            "error": str(job.get("error_text") or ""), "created_at": job["created_at"]}


def jobs_for_case(ctx, case_id: str) -> dict[str, dict]:
    """Latest enrichment job per document of this case."""
    rows = ctx.db.all("SELECT * FROM phase15_jobs WHERE job_type=? AND case_id=? ORDER BY created_at ASC, rowid ASC",
                      (JOB_TYPE, str(case_id)))
    latest: dict[str, dict] = {}
    for row in rows:
        view = _view(dict(row))
        latest[view["document_id"]] = view
    return latest


def enqueue(ctx, *, identity: dict, document_id: str) -> dict:
    """Validate that there is work to do and queue it (one active job per document)."""
    service = ctx.document_intelligence_458
    doc = service._document(document_id)
    service._identity(identity, doc["case_id"], "research.run", document_id)
    ocr_ready, _ = docstructure.ocr_available()
    mode = docstructure.pending_work(doc, docstructure.enrichment_for(ctx, document_id), ocr_ready)
    if doc["media_type"] != "application/pdf":
        raise ValueError("Struktur- und OCR-Anker gibt es nur für PDF-Dokumente.")
    if doc["state"] != "review_required":
        raise ValueError("Das Dokument wurde bereits geprüft. Anker lassen sich nur vor der Extraktionsprüfung ergänzen.")
    if not mode:
        raise ValueError("Für dieses Dokument wurden die Anker bereits ergänzt.")
    current = jobs_for_case(ctx, doc["case_id"]).get(document_id)
    if current and current["status"] in ACTIVE:
        return current
    job = ctx.job_engine_348.enqueue(
        job_type=JOB_TYPE, case_id=doc["case_id"], max_attempts=1,
        payload={"document_id": document_id, "user_id": str(identity["user_id"]),
                 "username": str(identity["username"]), "mode": mode},
        idempotency_key="enrich492:" + document_id + ":" + uuid.uuid4().hex,
        resource_budget={"max_runtime_seconds": LEASE_SECONDS})
    ctx.audit.log("document_enrichment_queued_492", "document", document_id, doc["case_id"], {"mode": mode})
    return _view(job)


def cancel(ctx, *, case_id: str, job_id: str, actor: str) -> dict:
    job = ctx.job_engine_348.get(job_id)
    if job["job_type"] != JOB_TYPE or job["case_id"] != str(case_id):
        raise KeyError(job_id)
    return _view(ctx.job_engine_348.cancel(job_id, actor=actor))


def recover_interrupted(ctx) -> int:
    """After a restart no worker is alive: re-queue runs that were interrupted mid-way."""
    cur = ctx.db.execute("UPDATE phase15_jobs SET status='queued',lease_owner='',lease_expires_at='',checkpoint_json='{}' "
                         "WHERE job_type=? AND status='running' AND lease_owner=?", (JOB_TYPE, WORKER_ID))
    return int(cur.rowcount or 0)


def process_next(ctx) -> dict | None:
    """Run one queued enrichment job to completion. Returns its final view or None."""
    engine = ctx.job_engine_348
    job = engine.claim(worker_id=WORKER_ID, lease_seconds=LEASE_SECONDS, job_types=[JOB_TYPE])
    if job is None:
        return None
    job_id, payload = job["job_id"], _payload(job)

    def progress(done: int, total: int) -> None:
        try:
            engine.checkpoint(job_id, {"done": done, "total": total}, worker_id=WORKER_ID)
        except PermissionError:  # lease gone: the job was cancelled
            raise docstructure.Cancelled() from None

    def should_stop() -> bool:
        return engine.get(job_id)["status"] != "running"

    try:
        ocr_ready, engine_name = docstructure.ocr_available()
        identity = {"user_id": payload.get("user_id"), "username": payload.get("username"),
                    "session_id": "enrich492-job"}
        with ctx.audit.actor_scope(str(payload.get("username") or "system")):
            result = docstructure.enrich_document(
                ctx, identity=identity, document_id=str(payload.get("document_id") or ""),
                ocr_engine=docstructure.tesseract_page if ocr_ready else None, engine_name=engine_name,
                progress=progress, should_stop=should_stop)
        engine.complete(job_id, {"mode": result["mode"], "tables": result["tables"], "headings": result["headings"],
                                 "ocr_paragraphs": result["ocr_paragraphs"], "ocr_skipped": result["ocr_skipped"]},
                        worker_id=WORKER_ID)
    except docstructure.Cancelled:
        pass  # status is already "cancelled"; nothing was written
    except Exception as exc:  # the job records the reason; the worker keeps running
        message = str(exc) if isinstance(exc, (ValueError, PermissionError, KeyError)) else \
            "Unerwarteter Fehler bei der Verarbeitung (" + type(exc).__name__ + ")."
        try:
            engine.fail(job_id, message[:500], worker_id=WORKER_ID, retry_delay_seconds=0)
        except PermissionError:
            pass  # cancelled while failing
    return _view(engine.get(job_id))
