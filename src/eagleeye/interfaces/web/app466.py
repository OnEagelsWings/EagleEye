"""Build 466: inspect provenance against existing case-authorized document store."""
from __future__ import annotations
import hashlib
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from eagleeye.application.entity_registry461 import EntityRegistry461
from .app465 import create_workspace_app465
from .app448 import COOKIE
from .app449 import _drop

def resolve_provenance(service, identity, case_id, graph):
    documents={d["document_id"]:d for d in service.documents(identity=identity,case_id=case_id)}
    items=[]
    loaded={}
    for relation in graph["relations"]:
        sources=[]
        for source in relation["sources"]:
            ref=source["source_ref"]
            detail={"ref":ref,"status":"unverified","title":"","sha256":"","captured_at":"","uri":"","anchors":0}
            if ref.startswith("doc458:"):
                doc_id=ref[7:]
                if doc_id in documents:
                    if doc_id not in loaded:
                        loaded[doc_id]=service.anchors(identity=identity,document_id=doc_id)
                    packet=loaded[doc_id]
                    doc=packet["document"]
                    # The underlying document and anchor rows remain the source of truth.
                    # Validate only records from this authorized document, not other cases.
                    record_valid=doc["record_hash"]==service._rh(doc)
                    for raw in service.db.all("SELECT * FROM phase20_document_anchor_458 WHERE document_id=?", (doc_id,)):
                        anchor=dict(raw)
                        if anchor["record_hash"]!=service._rh(anchor):
                            record_valid=False
                    detail.update(status="case_document",title=doc.get("title",""),
                        sha256=doc.get("document_sha256",""),
                        captured_at=doc.get("created_at") or doc.get("imported_at") or "",
                        uri=doc.get("source_url") or doc.get("canonical_url") or "",
                        anchors=len(packet.get("anchors",[])),document_id=doc_id,
                        stored_relpath=doc.get("stored_relpath",""),
                        record_integrity=record_valid)
                    if not all((detail["sha256"],detail["captured_at"],detail["uri"])):
                        detail["status"]="incomplete_provenance"
                else:
                    detail["status"]="missing_or_foreign_document"
            sources.append(detail)
        items.append({"id":relation["id"],"source_id":relation["source_id"],"target_id":relation["target_id"],
                      "predicate":relation["predicate"],"state":relation["state"],"sources":sources})
    return items

def create_workspace_app466(*, base_dir=None, workspace_build="466.0"):
    app=create_workspace_app465(base_dir=base_dir,workspace_build=workspace_build,
                                workspace_title="Document Provenance Inspection")
    ctx=app.state.context
    db=(Path(base_dir) if base_dir is not None else Path.home()/".eagleeye")/"entity_registry_462.sqlite3"
    _drop(app,"/health",{"GET"})

    @app.get("/health")
    def health466():
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,"next_checkpoint":"470.0"}

    @app.get("/provenance466",response_class=HTMLResponse)
    def provenance(request:Request,case_id:str=""):
        fingerprint=hashlib.sha256("|".join((
            request.headers.get("user-agent",""),request.headers.get("accept-language",""),
            request.client.host if request.client else "")).encode()).hexdigest()
        identity=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),client_fingerprint=fingerprint,touch=True)
        if not identity:
            return RedirectResponse("/security/login",status_code=303)
        if not any(str(c.get("case_id"))==case_id for c in ctx.team_governance_359.visible_cases(identity)):
            return RedirectResponse("/",status_code=303)
        with EntityRegistry461(db) as store:
            graph=store.graph(case_id)
        rows=resolve_provenance(ctx.document_intelligence_458,identity,case_id,graph)
        by_id={entity["id"]:entity["label"] for entity in graph["entities"]}
        checked={}
        for relation in rows:
            for source in relation["sources"]:
                if source["status"] not in ("case_document","incomplete_provenance"):
                    continue
                doc_id=source["document_id"]
                if doc_id not in checked:
                    digest=hashlib.sha256()
                    try:
                        candidate=(ctx.document_intelligence_458.root/source["stored_relpath"]).resolve()
                        root=ctx.document_intelligence_458.root.resolve()
                        if not source["stored_relpath"] or not candidate.is_relative_to(root):
                            raise ValueError("invalid document path")
                        with candidate.open("rb") as stream:
                            for chunk in iter(lambda:stream.read(1024*1024),b""):
                                digest.update(chunk)
                        checked[doc_id]=(bool(source["sha256"]) and digest.hexdigest()==source["sha256"]
                                         and source["record_integrity"])
                    except (OSError,ValueError):
                        checked[doc_id]=False
                source["file_integrity"]="bestanden" if checked[doc_id] else "HALT"
        overall=all(checked.values()) if checked else None
        sections=[]
        for row in rows:
            details=[]
            for source in row["sources"]:
                ref=source["ref"]
                if source["status"] in ("case_document","incomplete_provenance"):
                    link="/documents458?"+urlencode({"case_id":case_id,"document_id":ref[7:]})
                    detail='<a href="'+escape(link,quote=True)+'">'+escape(source["title"])+'</a>'
                    for title,key in (("SHA-256","sha256"),("Zeitstempel","captured_at"),
                                      ("Quellen-URL","uri")):
                        detail+='<p>'+title+': '+escape(source[key] or "UNBEKANNT")+'</p>'
                    detail+='<p>Textanker: '+str(source["anchors"])+'</p>'
                    detail+='<p>Datei-Integrität: '+source["file_integrity"]+'</p>'
                else:
                    detail=escape(ref)
                details.append('<li>'+detail+' · '+escape(source["status"])+'</li>')
            sections.append('<section><h2>'+escape(by_id.get(row["source_id"],"?"))+' → '+escape(row["predicate"])+' → '+escape(by_id.get(row["target_id"],"?"))+'</h2><p>Relations-ID: '+escape(row["id"] )+'</p><p>Status: '
                            +escape(row["state"])+'</p><ul>'+''.join(details)+'</ul></section>')
        back="/graph464?"+urlencode({"case_id":case_id})
        return HTMLResponse('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<title>EagleEye '+escape(workspace_build)+' – Provenienz</title><style>body{font:1rem system-ui;'
            'max-width:900px;margin:2rem auto;padding:1rem;background:#142236;color:#eaf3fd}'
            'a{color:#80dfd3}section{padding:1rem;border:1px solid #7e93a6;margin:1rem 0}</style>'
            '</head><body><main><a href="'+escape(back,quote=True)+'">Zurück zum Graph</a>'
            '<h1>Belegprüfung · Build '+escape(workspace_build)+'</h1><p>Integrität der verknüpften Falldokumente: '
            +("bestanden" if overall is True else ("HALT" if overall is False else "nicht geprüft"))+'</p><p>Quellenmetadaten sind keine '
            'Bestätigung von Behauptungen. Unbekannte Pflichtfelder bleiben sichtbar.</p>'
            +''.join(sections)+'</main></body></html>',headers={"Cache-Control":"no-store"})
    return app

create_app=create_workspace_app466
