from __future__ import annotations

import hashlib
from html import escape

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool

from .app457 import create_workspace_app457
from .app448 import COOKIE
from .app449 import _drop

MAX_UPLOAD = 12 * 1024 * 1024


def create_workspace_app458(*, base_dir=None):
    app = create_workspace_app457(base_dir=base_dir)
    ctx = app.state.context
    service = ctx.document_intelligence_458
    app.title = "EagleEye Build 458.0 — Document Intelligence 2.0"
    app.version = "458.0"
    _drop(app, "/health", {"GET"})

    def auth(request: Request):
        material = "|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        ))
        identity = ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=hashlib.sha256(material.encode()).hexdigest(),touch=True)
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich")
        return identity

    def case_permission(identity,case_id,capability="case.read"):
        try:
            ctx.team_governance_359.authorize(identity,case_id=str(case_id),capability=capability,
                object_type="document_intelligence_458",object_id=str(case_id))
        except PermissionError as exc:
            raise HTTPException(403,"Keine Berechtigung für diesen Fall") from exc

    async def body_object(request):
        try:
            result = await request.json()
        except (ValueError,UnicodeError) as exc:
            raise HTTPException(422,"Ungültiger JSON-Body") from exc
        if not isinstance(result,dict):
            raise HTTPException(422,"JSON-Body muss ein Objekt sein")
        return result

    def fail(error):
        if isinstance(error,PermissionError):
            raise HTTPException(403,str(error)) from error
        if isinstance(error,KeyError):
            raise HTTPException(404,str(error)) from error
        if isinstance(error,ValueError):
            raise HTTPException(422,str(error)) from error
        raise error

    @app.get("/health")
    def health():
        status=ctx.build458.build458_status()
        return {"ok":True,"build":"458.0","status":"ok" if status["integrity_valid"] else "hold",
                "document_intelligence":True,"next_checkpoint":"460.0","integrity_valid":status["integrity_valid"]}

    @app.get("/api/build458/status")
    def status(request:Request):
        auth(request)
        return ctx.build458.build458_status()

    @app.get("/api/build458/cases/{case_id}/documents")
    def documents(case_id:str,request:Request):
        identity=auth(request)
        try:
            return service.documents(identity=identity,case_id=case_id)
        except (KeyError,PermissionError,ValueError) as exc:
            fail(exc)

    @app.post("/api/build458/cases/{case_id}/documents")
    async def upload(case_id:str,request:Request,file:UploadFile=File(...),
                     title:str=Form(""),source_url:str=Form("")):
        identity=auth(request)
        case_permission(identity,case_id,"research.run")
        try:
            raw=await file.read(MAX_UPLOAD+1)
            if len(raw)>MAX_UPLOAD:
                raise ValueError("document exceeds 12-MiB limit")
            def work():
                with ctx.audit.actor_scope(identity["username"]):
                    return service.import_bytes(
                        identity=identity,case_id=case_id,filename=file.filename,
                        raw=raw,title=title,source_url=source_url)
            return await run_in_threadpool(work)
        except (ValueError,PermissionError,KeyError) as exc:
            fail(exc)
        except Exception as exc:
            # No parser/zip library internal details are returned to untrusted callers.
            raise HTTPException(422,"Dokument kann nicht sicher extrahiert werden") from exc
        finally:
            await file.close()

    @app.get("/api/build458/documents/{document_id}/anchors")
    def anchors(document_id:str,request:Request):
        ident=auth(request)
        try:
            return service.anchors(identity=ident,document_id=document_id)
        except (PermissionError,KeyError) as exc:
            fail(exc)

    @app.post("/api/build458/documents/{document_id}/review")
    async def review(document_id:str,request:Request):
        ident=auth(request)
        payload=await body_object(request)
        try:
            with ctx.audit.actor_scope(ident["username"]):
                return service.review_extraction(
                    identity=ident,document_id=document_id,
                    expected_document_hash=payload.get("expected_document_hash",""),
                    decision=payload.get("decision",""),
                    note=payload.get("note",""),
                    confirmation=payload.get("confirmation",""))
        except (KeyError,ValueError,PermissionError) as exc:
            fail(exc)

    @app.post("/api/build458/claims/{claim_id}/citations")
    async def create_citation(claim_id:str,request:Request):
        ident=auth(request)
        payload=await body_object(request)
        try:
            with ctx.audit.actor_scope(ident["username"]):
                return service.cite_claim_anchor(
                    identity=ident,claim_id=claim_id,
                    link_id=payload.get("link_id",""),anchor_id=payload.get("anchor_id",""),
                    expected_evidence_hash=payload.get("expected_evidence_hash",""),
                    expected_anchor_hash=payload.get("expected_anchor_hash",""),
                    note=payload.get("note",""),confirmation=payload.get("confirmation",""))
        except (PermissionError,KeyError,ValueError) as exc:
            fail(exc)

    @app.get("/api/build458/claims/{claim_id}/citations")
    def citations(claim_id:str,request:Request):
        ident=auth(request)
        try:
            return service.claim_citations(identity=ident,claim_id=claim_id)
        except (PermissionError,KeyError) as exc:
            fail(exc)

    @app.get("/assets/build458/documents.js")
    def document_upload_script():
        script = """
"use strict";
const form = document.getElementById("upload");
const feedback = document.getElementById("feedback");
if (form && feedback) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const caseId = new URLSearchParams(window.location.search).get("case_id");
    if (!caseId) { feedback.textContent = "Fall-ID fehlt."; return; }
    feedback.textContent = "Prüfe Dokument …";
    try {
      const response = await fetch("/api/build458/cases/" + encodeURIComponent(caseId) + "/documents", {
        method: "POST", body: new FormData(form), credentials: "same-origin"
      });
      const result = await response.json();
      if (!response.ok) {
        feedback.textContent = result.detail || "Upload fehlgeschlagen (" + response.status + ")";
        return;
      }
      feedback.textContent = "Dokument aufgenommen.";
      window.location.reload();
    } catch (_) { feedback.textContent = "Netzwerkfehler beim Upload."; }
  });
}
"""
        return Response(script, media_type="application/javascript", headers={"Cache-Control": "no-store"})

    @app.get("/documents458",response_class=HTMLResponse)
    def document_browser(request:Request,case_id:str,document_id:str=""):
        ident=auth(request)
        try:
            all_docs=service.documents(identity=ident,case_id=case_id)
            anchors=service.anchors(identity=ident,document_id=document_id) if document_id else None
            if anchors and anchors["document"]["case_id"] != case_id:
                raise PermissionError("cross-case document display blocked")
        except (PermissionError,KeyError) as exc:
            fail(exc)
        case=escape(case_id,quote=True)
        options="".join(
            f'<li><a href="/documents458?case_id={case}&document_id={escape(x["document_id"],quote=True)}">'
            f'{escape(x["title"])} — {x["page_count"]} Seiten — {escape(x["state"])}</a></li>'
            for x in all_docs)
        details=""
        if anchors:
            details="<h2>Verifizierbare Fundstellen</h2><p>Quelle: "+escape(anchors["document"]["document_sha256"])+"</p>"
            for item in anchors["anchors"][:200]:
                details+=f'<article><strong>Seite {item["page_number"]} / Block {item["ordinal"]}</strong>'
                details+=f'<p>{escape(item["text_excerpt"])}</p><small>{escape(item["locator"])}</small></article>'
        html=(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye 458 · Document Intelligence</title>'
            '<style>body{font:16px system-ui;max-width:920px;margin:auto;padding:20px;line-height:1.5}'
            'article{border:1px solid #aaa;border-radius:7px;padding:12px;margin:12px 0}'
            'input,button{font:inherit;padding:8px;margin:5px}button{cursor:pointer}'
            'a{color:inherit}</style></head><body>'
            f'<h1>EagleEye 458 · Dokumente</h1><p>Fall: {case}</p>'
            '<p>Extraktion ist ein Prüfobjekt, keine bestätigte Aussage. '
            'Scans ohne Textschicht werden als OCR erforderlich markiert.</p>'
            '<form id="upload" enctype="multipart/form-data"><input name="file" type="file" '
            'accept=".pdf,.txt,.md" required><input name="title" placeholder="Titel">'
            '<input name="source_url" placeholder="Öffentliche Quellen-URL">'
            '<button type="submit">Dokument lokal aufnehmen</button></form><p id="feedback"></p>'
            f'<h2>Dokumente</h2><ul>{options}</ul>{details}'
            '<script src="/assets/build458/documents.js" defer></script></body></html>'
        )
        return HTMLResponse(html)

    return app


create_app=create_workspace_app458
