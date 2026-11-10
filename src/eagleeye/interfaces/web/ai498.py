"""Local-only Ollama proposal review screen, not a remote autonomous agent."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from eagleeye.application import ai498,plan496
from .operations476 import case_access,page
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form,verify_post

def attach_ai498(app,build):
    ctx=app.state.context
    ai498.initialize(ctx)
    app.state.ai498=True

    @app.get("/workbench/ai498",response_class=HTMLResponse)
    def view(request:Request,case_id:str="",plan_id:str=""):
        user,_=case_access(app,request,case_id)
        caps=set(ctx.team_governance_359.effective_capabilities(user,case_id))
        plans=plan496.list_plans(ctx,case_id)
        body=("<p>Die lokale KI erstellt <strong>unverbindliche, strikt geprüfte Schrittvorschläge</strong>. "
              "Weder Quellenzugriffe noch Identitätsfeststellungen oder Graph-Änderungen "
              "werden durch KI-Ausgaben ausgelöst. Keine Cloud-KI: ausschließlich Ollama auf 127.0.0.1.</p>")
        for item in plans:
            if item["state"]!="draft":continue
            body+=('<p><a href="/workbench/ai498?'+escape(urlencode({"case_id":case_id,"plan_id":item["plan_id"]}),quote=True)+'">'+escape(item["objective"])+'</a></p>')
        if plan_id:
            try:plan=plan496.get_plan(ctx,case_id,plan_id); rows=ai498.proposals(ctx,case_id,plan_id)
            except KeyError:raise HTTPException(404,"Plan nicht gefunden")
            body+='<h2>Ermittlungsziel: '+escape(plan["objective"])+'</h2>'
            csrf=escape(request.cookies.get(CSRF_COOKIE,""),quote=True)
            hidden=('<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
                    '<input type="hidden" name="plan_id" value="'+escape(plan_id,quote=True)+'">'
                    '<input type="hidden" name="csrf" value="'+csrf+'">')
            if plan["state"]=="draft" and "research.run" in caps:
                body+=('<section class="card"><h2>Lokalen Modellvorschlag anfordern</h2>'
                       '<form method="post" action="/workbench/ai498/generate">'+hidden+
                       '<label>Bereits in Ollama installiertes Modell</label>'
                       '<input name="model_name" maxlength="96" placeholder="z. B. llama3.2:3b" required>'
                       '<label><input type="checkbox" name="confirm" value="yes" required>'
                       ' Nur lokale Planung ohne automatische Ausführung</label>'
                       '<button type="submit">Schrittvorschläge erzeugen</button></form></section>')
            for proposal in rows:
                body+=('<section class="card"><h3>Lokaler Vorschlag '+escape(proposal["model"])+
                       '</h3><p>Status: '+escape(proposal["state"])+'</p><ol>')
                for item in proposal["steps"]:
                    body+='<li>'+escape(item["kind"])+': '+escape(item["instruction"])+'</li>'
                body+='</ol>'
                if proposal["state"]=="pending_review" and plan["state"]=="draft" and {"research.run","source.review"}<=caps:
                    body+=('<form method="post" action="/workbench/ai498/decide">'+hidden+
                           '<input type="hidden" name="proposal_id" value="'+escape(proposal["proposal_id"],quote=True)+'">'
                           '<label>Entscheidung</label><select name="decision">'
                           '<option value="rejected">Ablehnen</option><option value="accepted">Schritte manuell übernehmen</option></select>'
                           '<label>Prüfgrund</label><textarea name="reason" minlength="20" maxlength="700" required></textarea>'
                           '<button type="submit">Prüfung protokollieren</button></form>')
                body+='</section>'
        return HTMLResponse(page("Lokaler KI-Ermittlungsplan – 498",case_id,body,build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"same-origin"})

    @app.post("/workbench/ai498/generate")
    async def generate(request:Request):
        f=await bounded_form(request,max_bytes=3000)
        cid=str(f.get("case_id") or "")
        user,_=case_access(app,request,cid,capability="research.run")
        verify_post(app,request,user,f.get("csrf",""))
        if f.get("confirm")!="yes":raise HTTPException(422,"Bestätigung erforderlich")
        pid=str(f.get("plan_id") or "")
        try:ai498.generate(ctx,user,cid,pid,str(f.get("model_name") or ""))
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)[:200]) from exc
        except ConnectionError:raise HTTPException(503,"Lokales Ollama nicht erreichbar") from None
        return RedirectResponse("/workbench/ai498?"+urlencode({"case_id":cid,"plan_id":pid}),303)

    @app.post("/workbench/ai498/decide")
    async def decide(request:Request):
        f=await bounded_form(request,max_bytes=3000)
        cid=str(f.get("case_id") or "")
        user,_=case_access(app,request,cid,capability="source.review")
        verify_post(app,request,user,f.get("csrf",""))
        pid=str(f.get("plan_id") or "")
        try:ai498.decide(ctx,user,cid,pid,str(f.get("proposal_id") or ""),
                         str(f.get("decision") or ""),str(f.get("reason") or ""))
        except KeyError:raise HTTPException(404,"Vorschlag nicht gefunden") from None
        except (ValueError,PermissionError) as exc:raise HTTPException(409,str(exc)[:200]) from exc
        return RedirectResponse("/workbench/ai498?"+urlencode({"case_id":cid,"plan_id":pid}),303)
