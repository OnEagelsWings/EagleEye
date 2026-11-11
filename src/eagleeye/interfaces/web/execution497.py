"""Build 497 provider execution workbench; deterministic services, no direct HTTP."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application import plan496, execution497
from .operations476 import page, case_access
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post

def attach_execution497(app,build):
    ctx=app.state.context
    execution497.initialize(ctx)
    app.state.execution497=True

    @app.get("/workbench/run497",response_class=HTMLResponse)
    def overview(request: Request,case_id: str="",plan_id: str=""):
        user,_case=case_access(app,request,case_id)
        allowed="research.run" in ctx.team_governance_359.effective_capabilities(user,case_id)
        plans=plan496.list_plans(ctx,case_id)
        body=("<p>Freigegebene Recherchepläne über den kanonischen ProviderCollection120-Motor ausführen. "
              "<strong>Replay</strong> verwendet gespeicherte Antworten ohne Netzwerkanfragen. "
              "<strong>Live</strong> benötigt zusätzlich einen bereits genehmigten Search-Intent "
              "und einen passenden genehmigten Query-Eintrag. Ergebnisse bleiben unbestätigte Kandidaten.</p>"
              "<p class='warn'>Keine automatischen Wiederholungen: Ein reservierter Schritt kann "
              "nicht erneut ausgeführt werden. Nach Abbruch ist eine manuelle Klärung nötig.</p>")
        for p in plans:
            if p["state"] != "approved":continue
            body += '<p><a href="/workbench/run497?'+escape(urlencode({"case_id":case_id,"plan_id":p["plan_id"]}),quote=True)+'">'+escape(p["objective"])+'</a></p>'
        if plan_id:
            try:
                plan=plan496.get_plan(ctx,case_id,plan_id)
                steps=plan496.list_steps(ctx,case_id,plan_id)
            except (KeyError,plan496.PlanError):
                raise HTTPException(404,"Unbekannter Ermittlungsplan")
            if plan["state"] != "approved":raise HTTPException(409,"Plan nicht freigegeben")
            token=escape(request.cookies.get(CSRF_COOKIE,""),quote=True)
            for step in steps:
                if step["kind"]!="provider_proposal":continue
                prior=execution497.get_execution(ctx,case_id,step["step_id"])
                body+=('<section class="card"><h2>'+escape(step["provider_key"])+'</h2>'
                       '<p>'+escape(step["instruction"])+'</p>')
                if prior:
                    body+=('<p>Status: '+escape(prior["state"])+" · Modus: "+escape(prior["mode"])+
                           " · Ausführung: "+escape(prior["provider_run_id"] or "noch nicht bestätigt")+'</p>')
                elif allowed and step["state"]=="proposed":
                    body+=(
                        '<form method="post" action="/workbench/run497">'
                        '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
                        '<input type="hidden" name="plan_id" value="'+escape(plan_id,quote=True)+'">'
                        '<input type="hidden" name="step_id" value="'+escape(step["step_id"],quote=True)+'">'
                        '<input type="hidden" name="csrf" value="'+token+'">'
                        '<label>Suchanfrage <input name="query" minlength="2" maxlength="230" required></label>'
                        '<label>Begründeter Zweck <textarea name="purpose" minlength="15" maxlength="450" required></textarea></label>'
                        '<label>Ausführung</label><select name="mode">'
                        '<option value="replay">Replay – offline, nur vorhandene Fixtures</option>'
                        '<option value="live">Live – zusätzlich genehmigter Suchauftrag nötig</option></select>'
                        '<label>Genehmigte Intent-ID (Live)</label><input name="search_intent_id" maxlength="110">'
                        '<label>Genehmigte Query-ID (Live)</label><input name="search_query_id" maxlength="110">'
                        '<label><input type="checkbox" name="confirm" value="yes" required> '
                        'Ich bestätige diesen konkreten Providerlauf, nicht pauschal andere Schritte.</label>'
                        '<button type="submit">Einmaligen Providerlauf starten</button></form>')
                body+="</section>"
        return HTMLResponse(page("Providerlauf – Build 497",case_id,body,build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"same-origin"})

    @app.post("/workbench/run497")
    async def run(request: Request):
        form=await bounded_form(request,max_bytes=11000)
        cid=str(form.get("case_id") or "")
        user,_=case_access(app,request,cid,capability="research.run")
        verify_post(app,request,user,form.get("csrf",""))
        if form.get("confirm")!="yes":raise HTTPException(422,"Ausführungsbestätigung fehlt")
        pid=str(form.get("plan_id") or "")
        try:
            execution497.run_step(
                ctx,user,cid,pid,str(form.get("step_id") or ""),
                query=str(form.get("query") or ""),purpose=str(form.get("purpose") or ""),
                mode=str(form.get("mode") or ""),confirmation=execution497.APPROVAL_PHRASE,
                search_intent_id=str(form.get("search_intent_id") or ""),
                search_query_id=str(form.get("search_query_id") or ""))
        except PermissionError:
            raise HTTPException(403,"Fehlende Fallberechtigung") from None
        except KeyError:
            raise HTTPException(404,"Fall oder Provider nicht gefunden") from None
        except (execution497.ExecutionError,plan496.PlanError) as exc:
            raise HTTPException(409,str(exc)[:220]) from exc
        return RedirectResponse("/workbench/run497?"+urlencode({"case_id":cid,"plan_id":pid}),
                                status_code=303)
