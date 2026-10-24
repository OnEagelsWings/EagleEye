"""Build 477: real per-case document/source inventory, not synthetic fixtures."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse
from .operations476 import case_access, page

def attach_sources(app, build):
    ctx=app.state.context
    @app.get("/workbench/sources",response_class=HTMLResponse)
    def source_inventory(request:Request,case_id:str="",offset:int=0):
        user,case=case_access(app,request,case_id)
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        offset=max(0,min(offset,max(0,len(docs)-1)))
        selected=docs[offset:offset+50]
        rows=[]
        for row in selected:
            doc_id=str(row.get("document_id") or "")
            href="/documents458?"+urlencode({"case_id":case_id,"document_id":doc_id})
            title=str(row.get("title") or row.get("filename") or doc_id)
            state=str(row.get("state") or "ungeprüft")
            origin=str(row.get("source_url") or row.get("origin_url") or "Herkunft prüfen")
            pages=str(row.get("page_count") or "?")
            rows.append("<tr><td><a href='"+escape(href,quote=True)+"'>"+escape(title)+"</a></td>"
                        "<td>"+escape(state)+"</td><td>"+escape(pages)+"</td>"
                        "<td>"+escape(origin[:300])+"</td></tr>")
        table=("<table><thead><tr><th>Dokument und Anker</th><th>Status</th>"
               "<th>Seiten</th><th>Herkunft / Quellen-URL</th></tr></thead><tbody>"
               +("".join(rows) or '<tr><td colspan="4">Noch keine Quellen importiert.</td></tr>')
               +"</tbody></table>")
        next_url=("/workbench/sources?"+urlencode({"case_id":case_id,"offset":offset+50})
                  if offset+50<len(docs) else "")
        prev_url=("/workbench/sources?"+urlencode({"case_id":case_id,"offset":max(0,offset-50)})
                  if offset>0 else "")
        paging=" ".join('<a href="'+escape(h,quote=True)+'">'+label+'</a>'
                        for h,label in ((prev_url,"Zurück"),(next_url,"Weitere Quellen"))
                        if h)
        links=("<p><a href='/documents458?"+escape(urlencode({"case_id":case_id}),quote=True)
               +"'>Dokument lokal importieren →</a> · <a href='/collect469?"
               +escape(urlencode({"case_id":case_id}),quote=True)
               +"'>Öffentliche Metadaten abrufen →</a></p>")
        info=("<p>Fall: "+escape(str(case.get("title") or ""))+" · "
              +str(len(docs))+" Dokumente. Quelle und genaue Textanker im Original prüfen;"
              " gespeicherte Metadaten sind keine Tatsachenbestätigung.</p>")
        return HTMLResponse(page("Quelleninventar und Fundstellen",case_id,
                                 info+links+table+"<p>"+paging+"</p>",build),
                            headers={"Cache-Control":"no-store"})
