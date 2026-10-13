from __future__ import annotations

import hashlib

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from eagleeye_pro.phase20.document_intelligence458 import MAX_DOCUMENT_BYTES

from .app457 import create_workspace_app457
from .app448 import COOKIE, render_workspace
from .app449 import _drop


def _bool_form(value: str) -> bool:
    raw = str(value or "").strip().casefold()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("boolean form value required")


def create_workspace_app458(*, base_dir=None):
    app = create_workspace_app457(base_dir=base_dir)
    ctx = app.state.context
    team = ctx.team_identity_359
    _ = ctx.build458
    app.title = "EagleEye Build 458.0 Document Intelligence 2.0"
    app.version = "458.0"

    _drop(app, "/", {"GET"})
    _drop(app, "/health", {"GET"})

    def auth(request: Request):
        fingerprint = hashlib.sha256(
            "|".join(
                (
                    request.headers.get("user-agent", ""),
                    request.headers.get("accept-language", ""),
                    request.client.host if request.client else "",
                )
            ).encode()
        ).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def visible_cases(identity):
        return ctx.team_governance_359.visible_cases(identity)

    def choose_case(cases, requested):
        if requested:
            for item in cases:
                if str(item.get("case_id")) == str(requested):
                    return item
        return cases[0] if cases else None

    @app.get("/", response_class=HTMLResponse)
    def workspace458(request: Request, view: str = "overview", case_id: str = ""):
        try:
            identity = auth(request)
        except HTTPException:
            destination = "/security/bootstrap" if team.bootstrap_required() else "/security/login"
            return RedirectResponse(destination, status_code=303)
        cases = visible_cases(identity)
        selected = choose_case(cases, case_id)
        if not selected:
            return RedirectResponse("/legacy", status_code=303)
        snap = ctx.workspace_reliability_457.snapshot(
            identity=identity,
            case_id=selected["case_id"],
        )
        snap["document_intelligence458"] = ctx.document_intelligence_458.case_manifest(
            identity=identity,
            case_id=selected["case_id"],
        )
        claim_anchors = {}
        for claim in snap.get("claims") or []:
            claim_anchors[claim["claim_id"]] = ctx.document_intelligence_458.claim_anchor_citations(
                identity=identity,
                claim_id=claim["claim_id"],
            )
        snap["claim_document_anchors458"] = claim_anchors
        audits = ctx.investigator_workspace_448.audit_history(selected["case_id"], limit=15)
        return HTMLResponse(render_workspace(snap, view=view, cases=cases, audits=audits))

    @app.get("/health")
    def health458():
        status = ctx.build458.build458_status()
        return {
            "ok": bool(status.get("integrity_valid")),
            "status": "ok" if status.get("integrity_valid") else "hold",
            "build": "458.0",
            "document_intelligence_2": True,
            "precise_document_anchors": True,
            "raw_payload_persisted": False,
            "full_research_gate_this_build": False,
            "next_checkpoint": "460.0",
            "production_release_ready": False,
            "integrity_valid": bool(status.get("integrity_valid")),
        }

    @app.get("/api/build458/status")
    def status458(request: Request):
        auth(request)
        return ctx.build458.build458_status()

    @app.get("/api/build458/cases/{case_id}/documents")
    def case_documents(case_id: str, request: Request):
        identity = auth(request)
        return ctx.document_intelligence_458.case_manifest(
            identity=identity, case_id=case_id
        )

    @app.get("/api/build458/documents/{document_id}")
    def document(document_id: str, request: Request):
        identity = auth(request)
        try:
            return ctx.build458.document_458(identity=identity, document_id=document_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/build458/evidence/{evidence_id}/documents")
    async def ingest_document(
        evidence_id: str,
        request: Request,
        file: UploadFile = File(...),
        expected_evidence_hash: str = Form(...),
        title: str = Form(""),
        allow_ocr: str = Form("false"),
        max_pages: int = Form(500),
        max_ocr_pages: int = Form(20),
    ):
        identity = auth(request)
        try:
            use_ocr = _bool_form(allow_ocr)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        raw = await file.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, "Dokument überschreitet das Build-458-Limit")
        media = str(file.content_type or "").split(";", 1)[0].strip().casefold()

        def run_extract():
            with ctx.audit.actor_scope(identity["username"]):
                return ctx.build458.ingest_document_458(
                    identity=identity,
                    evidence_id=evidence_id,
                    expected_evidence_hash=expected_evidence_hash,
                    content=raw,
                    title=title or file.filename or "",
                    media_type=media,
                    allow_ocr=use_ocr,
                    max_pages=max_pages,
                    max_ocr_pages=max_ocr_pages,
                )
        try:
            return await run_in_threadpool(run_extract)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (TypeError, ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/build458/claims/{claim_id}/anchors/{anchor_id}")
    async def link_anchor(claim_id: str, anchor_id: str, request: Request):
        identity = auth(request)
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(422, "gültiges JSON-Objekt erforderlich") from exc
        if not isinstance(payload, dict):
            raise HTTPException(422, "gültiges JSON-Objekt erforderlich")
        required = (
            "stance", "expected_claim_hash", "expected_evidence_hash", "expected_anchor_hash"
        )
        if any(not isinstance(payload.get(x), str) or not payload.get(x) for x in required):
            raise HTTPException(422, "stance und erwartete Hashes sind erforderlich")
        try:
            with ctx.audit.actor_scope(identity["username"]):
                return ctx.build458.link_claim_anchor_458(
                    identity=identity,
                    claim_id=claim_id,
                    anchor_id=anchor_id,
                    stance=payload["stance"],
                    note=payload.get("note", ""),
                    expected_claim_hash=payload["expected_claim_hash"],
                    expected_evidence_hash=payload["expected_evidence_hash"],
                    expected_anchor_hash=payload["expected_anchor_hash"],
                )
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/build458/claims/{claim_id}/anchors")
    def claim_anchors(claim_id: str, request: Request):
        identity = auth(request)
        return ctx.build458.claim_anchor_citations_458(
            identity=identity, claim_id=claim_id
        )

    @app.get("/api/build458/dossiers/{revision_id}/document-anchors")
    def dossier_anchors(revision_id: str, request: Request):
        identity = auth(request)
        return ctx.build458.dossier_anchor_manifest_458(
            identity=identity, revision_id=revision_id
        )

    return app


create_app = create_workspace_app458
