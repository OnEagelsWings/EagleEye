"""Human controlled, recoverable PersonOSINT candidate → graph handoff."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from eagleeye.application import transfer499,personosint494
from .operations476 import case_access,page
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form,verify_post

def attach_transfer499(app,build,base_dir):
    ctx=app.state.context
    transfer499.initialize(ctx)
    app.state.transfer499=True

    @app.get("/workbench/transfer499",response_class=HTMLResponse)
    def overview(request:Request,case_id:str=""):
        user,_case=case_access(app,request,case_id)
        caps=set(ctx.team_governance_359.effective_capabilities(user,case_id))
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        candidates=personosint494.candidates(ctx,case_id)
        existing={r["candidate_id"]:r for r in transfer499.rows(ctx,case_id)}
        opts="".join('<option value="'+escape(d["document_id"],quote=True)+'">'+
                   escape(d.get("title") or d["document_id"])+'</option>' for d in docs)
        token=escape(request.cookies.get(CSRF_COOKIE,""),quote=True)
        body=("<p>Nur bereits geprüfte PersonOSINT-Vorschläge können mit einem <strong>vorhandenen "
              "Falldokument</strong> als <em>unbestätigte</em> Graph-Entität erfasst werden. "
              "Weder Personenidentität noch eine Beziehung wird automatisch bestätigt.</p>"
              "<p>Ein journalsicherer Vorgang lässt sich nach Unterbrechung manuell wiederholen, "
              "ohne eine zweite Graph-Entität zu erzeugen.</p>")
        for item in candidates:
            if item["state"]!="for_manual_entry":continue
            prior=existing.get(item["candidate_id"])
            body+='<section class="card"><h2>'+escape(item["label"])+'</h2>'
            if prior:
                body+='<p>'+escape(prior["state"])+" · "+escape(prior["entity_id"])+'</p>'
            if "source.review" in caps and docs and (prior is None or prior["state"]=="staged"):
                body+=('<form method="post" action="/workbench/transfer499">'
                       '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
                       '<input type="hidden" name="csrf" value="'+token+'">'
                       '<input type="hidden" name="candidate_id" value="'+escape(item["candidate_id"],quote=True)+'">'
                       '<label>Bereits gespeichertes Falldokument (Belegverweis, keine automatische Verifikation)</label>'
                       '<select name="document_id" required>'+opts+'</select>'
                       '<label>Prüfvermerk und Zuordnungsgrund</label>'
                       '<textarea name="rationale" minlength="30" maxlength="1200" required></textarea>'
                       '<label><input type="checkbox" name="confirm" value="yes" required>'
                       ' Ich bestätige ausdrücklich die Erstellung einer unbestätigten Entität.</label>'
                       '<button type="submit">Entität mit Quelle erfassen</button></form>')
            body+='</section>'
        if not docs:body+='<p>Bitte zuerst ein Originaldokument in diesen Fall importieren.</p>'
        return HTMLResponse(page("Entitäten-Übernahme – Build 499",case_id,body,build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"same-origin"})

    @app.post("/workbench/transfer499")
    async def do_transfer(request:Request):
        f=await bounded_form(request,max_bytes=9000)
        cid=str(f.get("case_id") or "")
        user,_=case_access(app,request,cid,capability="source.review")
        verify_post(app,request,user,f.get("csrf",""))
        if f.get("confirm")!="yes":raise HTTPException(422,"Ausdrückliche Bestätigung erforderlich")
        try:
            transfer499.transfer(ctx,user,cid,str(f.get("candidate_id") or ""),
                 str(f.get("document_id") or ""),str(f.get("rationale") or ""),base_dir=base_dir)
        except (transfer499.TransferError,ValueError,KeyError) as exc:
            raise HTTPException(409,str(exc)[:240]) from exc
        return RedirectResponse("/workbench/transfer499?"+urlencode({"case_id":cid}),303)
