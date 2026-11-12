"""Build 496: case-scoped, review-gated investigation plan workbench.

Nothing in this module fetches network content, executes a provider or passes
untrusted plan text as commands. Future AI models may *propose* bounded steps
to the service, but cannot approve their own plan or bypass provider grants.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application import plan496
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

KIND_LABELS = {
    "manual_source": "Öffentliche Quelle manuell prüfen",
    "provider_proposal": "Kontrollierte Provider-Abfrage vorschlagen",
    "web_capture_proposal": "WARC-Webbeleg vorschlagen",
    "document_review": "Dokument und Fundstellen prüfen",
    "entity_review": "Identitäts-/Entitätsvorschlag prüfen",
    "hypothesis_check": "Hypothese und Gegenbelege untersuchen",
}


def _link(case_id: str, *, plan_id: str = "") -> str:
    data = {"case_id": case_id}
    if plan_id:
        data["plan_id"] = plan_id
    return "/workbench/plan496?" + urlencode(data)


def _hidden(name: str, value: str) -> str:
    return ('<input type="hidden" name="' + escape(name, quote=True) +
            '" value="' + escape(str(value), quote=True) + '">')


def _form(action: str, request: Request, case_id: str, *, plan_id: str = "") -> str:
    csrf = request.cookies.get(CSRF_COOKIE, "")
    return ('<form method="post" action="' + escape(action, quote=True) + '">' +
            _hidden("case_id", case_id) + _hidden("csrf", csrf) +
            (_hidden("plan_id",plan_id) if plan_id else ""))


def _redirect(case_id: str, plan_id: str = ""):
    return RedirectResponse(_link(case_id, plan_id=plan_id), status_code=303)


def _problem(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, "Rechercheplan nicht gefunden.")
    message = str(exc)
    status = 409 if any(t in message.lower() for t in (
        "stale", "integrity", "already", "cannot be modified",
        "only approved", "already reviewed")) else 422
    return HTTPException(status, message[:260])


def attach_plan496(app, build: str) -> None:
    ctx = app.state.context
    plan496.initialize(ctx)
    app.state.investigation_plan496 = True

    @app.get("/workbench/plan496", response_class=HTMLResponse)
    def workbench(request: Request, case_id: str = "", plan_id: str = ""):
        user, case = case_access(app, request, case_id)
        capabilities = set(ctx.team_governance_359.effective_capabilities(user, case_id))
        can_edit = "research.run" in capabilities
        can_review = "source.review" in capabilities
        plans = plan496.list_plans(ctx, case_id)
        body = (
            "<p>Von der Leitfrage zur <strong>prüfbaren Rechercheplanung</strong>. "
            "Schritte können vorgeschlagen, freigegeben und als manuelle Ergebnisse "
            "dokumentiert werden. Ein genehmigter Plan ist noch keine Genehmigung "
            "für Netzwerkanfragen, Beobachtungen oder automatische KI-Aktionen.</p>"
            '<p class="warn">Diese Version führt keine Quellenabfragen oder KI-Tool-Aufrufe '
            'selbständig aus. Für jeden Live-Providerlauf sind die vorhandenen '
            'fallgebundenen Freigaben des Provider-Motors zusätzlich nötig.</p>'
        )
        if can_edit:
            body += (
                '<section class="card"><h2>Neuen Ermittlungsplan anlegen</h2>' +
                _form("/workbench/plan496/new", request, case_id) +
                '<label for="objective">Ermittlungsziel</label>'
                '<textarea id="objective" name="objective" minlength="15" maxlength="350" required></textarea>'
                '<label for="scope">Zulässige Quellen, Grenzen und Rechtsgrundlage</label>'
                '<textarea id="scope" name="scope" minlength="20" maxlength="1200" required></textarea>'
                '<button type="submit">Entwurf erstellen</button></form></section>'
            )
        body += "<h2>Fallbezogene Pläne (" + str(len(plans)) + ")</h2>"
        for item in plans:
            body += (
                '<section class="card"><h3><a href="' +
                escape(_link(case_id,plan_id=item["plan_id"]),quote=True) + '">' +
                escape(item["objective"]) + '</a></h3>'
                '<p>Status: ' + escape(item["state"]) +
                ' · Angelegt von ' + escape(item["created_by"]) + '</p></section>'
            )
        if not plans:
            body += "<p>Für diesen Fall gibt es noch keinen Rechercheplan.</p>"
        if plan_id:
            try:
                current = plan496.get_plan(ctx, case_id, plan_id)
                steps = plan496.list_steps(ctx, case_id, plan_id)
            except (KeyError, plan496.PlanError) as exc:
                raise _problem(exc) from exc
            body += (
                '<section class="card"><h2>Ausgewählter Ermittlungsplan</h2><p><strong>Ziel:</strong> ' +
                escape(current["objective"]) + '</p><p><strong>Grenzen:</strong> ' +
                escape(current["scope"]) + '</p><p><strong>Freigabestatus:</strong> ' +
                escape(current["state"]) + '</p></section>'
            )
            if current["state"] == "draft" and can_edit:
                opts = "".join(
                    '<option value="' + escape(key,quote=True) + '">' + escape(label) + '</option>'
                    for key,label in KIND_LABELS.items()
                )
                body += (
                    '<section class="card"><h2>Prüfschritt vorschlagen</h2>' +
                    _form("/workbench/plan496/step", request, case_id, plan_id=plan_id) +
                    '<label>Art des Schritts</label><select name="kind">' + opts + '</select>'
                    '<label>Arbeitsauftrag und zu klärende Frage</label>'
                    '<textarea name="instruction" minlength="15" maxlength="800" required></textarea>'
                    '<label>Provider-Key (nur für Provider-Vorschlag, exakter Katalogschlüssel)</label>'
                    '<input name="provider_key" maxlength="110">'
                    '<button type="submit">Schritt als Vorschlag speichern</button></form></section>'
                )
            if current["state"] == "draft" and can_review:
                body += (
                    '<section class="card"><h2>Plan prüfen</h2>' +
                    _form("/workbench/plan496/review", request, case_id, plan_id=plan_id) +
                    _hidden("expected_hash",current["record_hash"]) +
                    '<label>Entscheidung</label><select name="decision">'
                    '<option value="approved">Rechercheplan genehmigen – KEINE Netzwerkfreigabe</option>'
                    '<option value="rejected">Plan zurückweisen</option></select>'
                    '<label>Prüfbegründung</label><textarea name="reason" minlength="20" '
                    'maxlength="1200" required></textarea><button type="submit">Entscheidung protokollieren</button>'
                    '</form></section>'
                )
            if current["state"] != "draft":
                body += ('<p>Geprüft durch ' + escape(current["reviewed_by"]) +
                         ': ' + escape(current["review_note"]) + '</p>')
            if current["state"] == "draft" and getattr(app.state, "ai498", False):
                body += '<p><a href="/workbench/ai498?' + escape(urlencode({"case_id":case_id,"plan_id":plan_id}),quote=True) + '">Lokale KI-Schrittvorschläge prüfen</a></p>'
            if current["state"] == "approved" and getattr(app.state, "execution497", False):
                body += '<p><a href="/workbench/run497?' + escape(urlencode({"case_id":case_id,"plan_id":plan_id}),quote=True) + '">Genehmigte Provider-Schritte bearbeiten</a></p>'
            body += "<h2>Arbeitsschritte (" + str(len(steps)) + ")</h2>"
            for step in steps:
                body += (
                    '<section class="card"><h3>' + escape(KIND_LABELS.get(step["kind"],step["kind"])) +
                    '</h3><p>' + escape(step["instruction"]) + '</p><p>Status: ' +
                    escape(step["state"]) + '</p>'
                )
                if step["provider_key"]:
                    body += ('<p>Provider: <code>' + escape(step["provider_key"]) +
                             '</code> (separat freigeben)</p>')
                if step["state"] == "proposed" and current["state"] == "approved" and can_edit:
                    body += (
                        _form("/workbench/plan496/annotate", request, case_id, plan_id=plan_id) +
                        _hidden("step_id",step["step_id"]) +
                        _hidden("expected_hash",step["record_hash"]) +
                        '<label>Manuelle Rückmeldung</label><select name="decision">'
                        '<option value="done">Als manuell bearbeitet kennzeichnen</option>'
                        '<option value="blocked">Offene Prüfung / Hindernis</option></select>'
                        '<label>Ergebnisvermerk mit Quellenhinweis oder offener Unsicherheit</label>'
                        '<textarea name="note" minlength="20" maxlength="1400" required></textarea>'
                        '<button type="submit">Rückmeldung dokumentieren</button></form>'
                    )
                elif step["state"] != "proposed":
                    body += '<p>Vermerk: ' + escape(step["outcome"]) + '</p>'
                body += '</section>'
        body += '<p><a href="' + escape("/workbench/personosint495?" + urlencode({"case_id":case_id}),quote=True) + '">Zurück zur Personenrecherche</a></p>'
        return HTMLResponse(page("Ermittlungsplanung – Freigaben und Prüfschritte", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "same-origin"})

    @app.post("/workbench/plan496/new")
    async def new_plan(request: Request):
        form = await bounded_form(request,max_bytes=9_000)
        cid = str(form.get("case_id") or "")
        user, _ = case_access(app, request, cid, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            plan = plan496.create_plan(ctx,user,cid,str(form.get("objective") or ""),str(form.get("scope") or ""))
        except (ValueError,KeyError) as exc:
            raise _problem(exc) from exc
        return _redirect(cid,plan["plan_id"])

    @app.post("/workbench/plan496/step")
    async def create_step(request: Request):
        form = await bounded_form(request,max_bytes=9_000)
        cid = str(form.get("case_id") or "")
        user, _ = case_access(app, request, cid, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        pid = str(form.get("plan_id") or "")
        try:
            plan496.add_step(ctx,user,cid,pid,str(form.get("kind") or ""),
                str(form.get("instruction") or ""),str(form.get("provider_key") or ""))
        except (ValueError,KeyError) as exc:
            raise _problem(exc) from exc
        return _redirect(cid,pid)

    @app.post("/workbench/plan496/review")
    async def review(request: Request):
        form = await bounded_form(request,max_bytes=9_000)
        cid = str(form.get("case_id") or "")
        user, _ = case_access(app, request, cid, capability="source.review")
        verify_post(app, request, user, form.get("csrf", ""))
        pid = str(form.get("plan_id") or "")
        try:
            plan496.review_plan(ctx,user,cid,pid,str(form.get("decision") or ""),
                str(form.get("reason") or ""),str(form.get("expected_hash") or ""))
        except (ValueError,KeyError) as exc:
            raise _problem(exc) from exc
        return _redirect(cid,pid)

    @app.post("/workbench/plan496/annotate")
    async def annotate(request: Request):
        form = await bounded_form(request,max_bytes=9_000)
        cid = str(form.get("case_id") or "")
        user, _ = case_access(app, request, cid, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        pid = str(form.get("plan_id") or "")
        try:
            plan496.annotate_step(ctx,user,cid,pid,str(form.get("step_id") or ""),
                str(form.get("decision") or ""),str(form.get("note") or ""),
                str(form.get("expected_hash") or ""))
        except (ValueError,KeyError) as exc:
            raise _problem(exc) from exc
        return _redirect(cid,pid)
